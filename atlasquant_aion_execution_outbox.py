"""Transactional staging outbox for future AION external actions.

This module deliberately contains no provider, network, subprocess or connector
implementation. It establishes the execution semantics required before any
external adapter may be enabled:

- decision + action intent recorded in one SQLite transaction;
- deterministic idempotency key per trusted scope + intent;
- aggregate ordering;
- one-worker claim lease;
- authority/policy revalidation at the instant of dispatch;
- uncertain send => reconcile, never blind resend;
- confirmed effects recorded in an idempotent execution ledger.

Adapters are injected by tests/future hosts. No adapter is enabled here.
"""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math
import re
from typing import Any, Callable, Mapping

from aion_chat.models import Scope
from aion_chat.privacy import redact
from aion_chat.store import SQLiteChatStore, StorageUnavailableError

SCHEMA = "ATLASQUANT_AION_EXECUTION_OUTBOX_V1"
MAX_AUTHORITY_TTL_SECONDS = 900
DEFAULT_LEASE_SECONDS = 30
MAX_LEASE_SECONDS = 300
STATES = frozenset({
    "PENDING",
    "RETRY",
    "CLAIMED",
    "UNCERTAIN",
    "SENT",
    "CONFIRMED",
    "REVOKED",
    "BLOCKED_REAPPROVAL",
    "FAILED",
})
TERMINAL_STATES = frozenset({
    "CONFIRMED",
    "REVOKED",
    "BLOCKED_REAPPROVAL",
    "FAILED",
})
_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _token(value: Any, name: str, limit: int = 128) -> str:
    text = _clean(value, limit)
    if not _SAFE_TOKEN.fullmatch(text):
        raise ValueError(f"invalid {name}")
    return text


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        allow_nan=False,
    )


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _utc(value: Any | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _scope(scope: Scope) -> tuple[str, str, str]:
    if not isinstance(scope, Scope):
        raise TypeError("trusted Scope required")
    return scope.owner_id, scope.tenant_id, scope.workspace_id


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _bound_callback(callback: Callable[..., Any], *arguments: Any) -> Any:
    """Isolate a synthetic callback and reject changed argument bindings.

    Each boundary gets private nested data. Neither a retained argument nor a
    returned mutable object is shared with later callbacks or ledger writes.
    This is local data integrity, not evidence that a callback is trustworthy;
    a hostile in-process host can still replace code, state and trust roots.
    """
    private = tuple(deepcopy(value) for value in arguments)
    bindings = tuple(_canonical(value) for value in private)
    result = callback(*private)
    if any(_canonical(value) != binding for value, binding in zip(private, bindings)):
        raise ValueError("CALLBACK_ARGUMENT_BINDING_CHANGED")
    return deepcopy(result)


class ExecutionOutbox:
    """Scoped outbox bound to the same SQLite database as staged chat state."""

    def __init__(
        self, store: SQLiteChatStore, scope: Scope, *,
        evidence_verifier: Callable[[str, Mapping[str, Any], Mapping[str, Any]], bool] | None = None,
        first_attempt_guard: Callable[[Mapping[str, Any]], bool] | None = None,
        unsafe_allow_synthetic_lab_callbacks: bool = False,
        strict_authority_scope_lab: bool = False,
        strict_reconciliation_auth_lab: bool = False,
        fresh_dispatch_clock_lab: Callable[[], Any] | None = None,
        strict_claim_fencing_lab: bool = False,
        strict_reconcile_snapshot_cas_lab: bool = False,
        strict_projection_lab: bool = False,
        strict_binding_integrity_lab: bool = False,
    ):
        if not isinstance(store, SQLiteChatStore):
            raise TypeError("SQLiteChatStore required")
        if evidence_verifier is not None and not callable(evidence_verifier):
            raise TypeError("callable evidence_verifier required")
        if first_attempt_guard is not None and not callable(first_attempt_guard):
            raise TypeError("callable first_attempt_guard required")
        if type(unsafe_allow_synthetic_lab_callbacks) is not bool:
            raise TypeError("unsafe_allow_synthetic_lab_callbacks must be bool")
        if type(strict_authority_scope_lab) is not bool:
            raise TypeError("strict_authority_scope_lab must be bool")
        if type(strict_reconciliation_auth_lab) is not bool:
            raise TypeError("strict_reconciliation_auth_lab must be bool")
        if fresh_dispatch_clock_lab is not None and not callable(fresh_dispatch_clock_lab):
            raise TypeError("fresh_dispatch_clock_lab must be callable")
        if type(strict_claim_fencing_lab) is not bool:
            raise TypeError("strict_claim_fencing_lab must be bool")
        if type(strict_reconcile_snapshot_cas_lab) is not bool:
            raise TypeError("strict_reconcile_snapshot_cas_lab must be bool")
        if type(strict_projection_lab) is not bool:
            raise TypeError("strict_projection_lab must be bool")
        if type(strict_binding_integrity_lab) is not bool:
            raise TypeError("strict_binding_integrity_lab must be bool")
        store.require_healthy()
        _scope(scope)
        self.store = store
        self.scope = scope
        self.db = store.db
        # Opt-in LAB candidate. Legacy callers remain unchanged for comparison.
        self._strict_authority_scope_lab = strict_authority_scope_lab
        self._strict_reconciliation_auth_lab = strict_reconciliation_auth_lab
        # A synthetic clock is NOT independently trusted and requires test
        # configuration. Legacy dispatch keeps its prior behavior for regressions.
        self._fresh_dispatch_clock_lab = fresh_dispatch_clock_lab
        # Persisted attempts rises atomically in claim_next: G41 uses it
        # as a LOCAL fencing epoch, not independent rollback protection.
        self._strict_claim_fencing_lab = strict_claim_fencing_lab
        # This optional LAB gate detects reconcile replies against stale local
        # state. No source/receipt is independently authenticated by it.
        self._strict_reconcile_snapshot_cas_lab = strict_reconcile_snapshot_cas_lab
        # Opt-in LAB: fresh confirmation updates its JSON projection in the
        # same SQLite transaction. Historical rows require explicit dry-run.
        self._strict_projection_lab = strict_projection_lab
        self._strict_binding_integrity_lab = strict_binding_integrity_lab
        # Default fail-closed. This LAB callback boundary is NOT a verified
        # identity/receipt trust root: callers can inject synthetic verifiers.
        # Production admission requires separately pinned external trust.
        self._evidence_verifier = evidence_verifier
        # DENY by default: no witness/proof, no adapter send. Tests may inject
        # synthetic callbacks ONLY in isolated LAB fixtures.
        self._first_attempt_guard = first_attempt_guard
        # A190 G12: even supplied true-returning callbacks are quarantined by
        # default. The explicit unsafe opt-in exists ONLY to retain isolated
        # state-machine LAB tests and is NOT a production trust boundary: an
        # in-process caller could deliberately enable it. HARD NO-GO remains.
        self._synthetic_lab_callbacks_enabled = unsafe_allow_synthetic_lab_callbacks
        self._ensure_schema()

    def _reserved_first_attempt(self, intent: Mapping[str, Any]) -> bool:
        # A180 candidate calls a separately pinned synthetic witness contract.
        # An arbitrary injected true-returning callback is NOT trustworthy
        # and must be prohibited by any future operational host.
        if not self._synthetic_lab_callbacks_enabled or self._first_attempt_guard is None:
            return False
        try:
            return _bound_callback(self._first_attempt_guard, dict(intent)) is True
        except Exception:
            return False

    def _verified_evidence(
        self, kind: str, intent: Mapping[str, Any], result: Mapping[str, Any],
    ) -> bool:
        """No evidence, exception or ambiguous result can authorize an effect."""
        if not self._synthetic_lab_callbacks_enabled or self._evidence_verifier is None:
            return False
        try:
            return _bound_callback(self._evidence_verifier, kind, dict(intent), dict(result)) is True
        except Exception:
            return False

    def _rollback_preserving_original(self, original_error: Exception) -> None:
        """Keep the first transaction failure as the primary exception.

        If rollback itself fails, quarantine and detach the SQLite store
        before propagating the original error. No retry, repair or new
        connection is attempted. Any later work requires explicit recovery.
        """
        try:
            self.db.rollback()
        except Exception as rollback_error:
            self.store.quarantine_failed_transaction()
            self.db = None
            if hasattr(original_error, "add_note"):
                original_error.add_note(
                    "AION_OUTBOX_ROLLBACK_FAILED_STORE_QUARANTINED_NO_RETRY"
                )
            raise original_error from rollback_error

    def _begin_or_quarantine(self) -> None:
        """BEGIN error can follow a successful SQLite lock/transaction start.

        Fail closed even on an apparent busy/error response; never infer
        that no transaction began, and never resend an external operation.
        """
        if self.db is None:
            raise StorageUnavailableError("OUTBOX_BEGIN_STORE_QUARANTINED")
        self.store.require_healthy()
        try:
            self.db.execute("BEGIN IMMEDIATE")
        except Exception as begin_error:
            self.store.quarantine_failed_transaction()
            self.db = None
            if hasattr(begin_error, "add_note"):
                begin_error.add_note(
                    "AION_OUTBOX_BEGIN_OUTCOME_UNCERTAIN_NO_AUTO_RETRY"
                )
            raise

    def _commit_or_quarantine(self) -> None:
        """Any COMMIT exception has UNKNOWN durability: never infer absence.

        The database may have committed before an acknowledgement was lost.
        Detach shared store and Outbox handles, never rollback after a failed
        commit or automatically requeue the effect.
        """
        try:
            self.db.commit()
        except Exception as commit_error:
            self.store.quarantine_failed_transaction()
            self.db = None
            if hasattr(commit_error, "add_note"):
                commit_error.add_note(
                    "AION_OUTBOX_COMMIT_OUTCOME_UNCERTAIN_NO_AUTO_RESEND"
                )
            raise

    @contextmanager
    def _managed_write_transaction(self):
        """Explicit Outbox write transaction; fail closed after ambiguous COMMIT.

        sqlite3.Connection context manager hides COMMIT acknowledgements.
        Each state transition must be atomic and propagate uncertainty.
        """
        if self.db is None:
            raise StorageUnavailableError("OUTBOX_TRANSACTION_QUARANTINED")
        self.store.require_healthy()
        self._begin_or_quarantine()
        try:
            yield
        except Exception as primary_error:
            if self.db is not None:
                self._rollback_preserving_original(primary_error)
            raise
        else:
            self._commit_or_quarantine()

    def _ensure_schema(self) -> None:
        # executescript() commits before running DDL and can leave a partial
        # schema. Execute static statements under one explicit transaction.
        schema_sql = """
            CREATE TABLE IF NOT EXISTS action_decisions(
                decision_id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                tenant TEXT NOT NULL,
                workspace TEXT NOT NULL,
                intent_ref TEXT NOT NULL,
                action TEXT NOT NULL,
                aggregate_key TEXT NOT NULL,
                aggregate_seq INTEGER NOT NULL,
                payload_digest TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                authorization_ref TEXT NOT NULL,
                valid_until TEXT NOT NULL,
                created_at TEXT NOT NULL,
                data TEXT NOT NULL,
                UNIQUE(owner,tenant,workspace,intent_ref),
                UNIQUE(owner,tenant,workspace,aggregate_key,aggregate_seq)
            );
            CREATE INDEX IF NOT EXISTS action_decision_scope
                ON action_decisions(owner,tenant,workspace,created_at,decision_id);

            CREATE TABLE IF NOT EXISTS action_outbox(
                idempotency_key TEXT PRIMARY KEY,
                decision_id TEXT NOT NULL REFERENCES action_decisions(decision_id),
                owner TEXT NOT NULL,
                tenant TEXT NOT NULL,
                workspace TEXT NOT NULL,
                state TEXT NOT NULL,
                lease_owner TEXT NOT NULL DEFAULT '',
                lease_until TEXT NOT NULL DEFAULT '',
                attempts INTEGER NOT NULL DEFAULT 0,
                dispatch_started_at TEXT NOT NULL DEFAULT '',
                sent_at TEXT NOT NULL DEFAULT '',
                confirmed_at TEXT NOT NULL DEFAULT '',
                last_error TEXT NOT NULL DEFAULT '',
                effect_ref TEXT NOT NULL DEFAULT '',
                data TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS action_outbox_scope_state
                ON action_outbox(owner,tenant,workspace,state,decision_id);

            CREATE TABLE IF NOT EXISTS action_effects(
                idempotency_key TEXT PRIMARY KEY REFERENCES action_outbox(idempotency_key),
                owner TEXT NOT NULL,
                tenant TEXT NOT NULL,
                workspace TEXT NOT NULL,
                effect_ref TEXT NOT NULL,
                confirmed_at TEXT NOT NULL,
                data TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS action_effect_scope
                ON action_effects(owner,tenant,workspace,confirmed_at,idempotency_key);

            CREATE TABLE IF NOT EXISTS semantic_reservations_lab(
                owner TEXT NOT NULL,
                tenant TEXT NOT NULL,
                business_event_id TEXT NOT NULL,
                workspace TEXT NOT NULL,
                intent_ref TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                payload_digest TEXT NOT NULL,
                PRIMARY KEY(tenant,business_event_id)
            );
            """
        with self._managed_write_transaction():
            for statement in schema_sql.split(";"):
                statement = statement.strip()
                if statement:
                    self.db.execute(statement)

    def _scope_args(self) -> tuple[str, str, str]:
        return _scope(self.scope)

    def _g44_assert_binding_lab(self, key: str) -> None:
        if not self._strict_binding_integrity_lab:
            return
        # Local structural integrity is NOT authentic commercial evidence.
        from atlasquant_aion_outbox_binding_lab import binding_issue_lab
        reason = binding_issue_lab(self.db, key, self._scope_args())
        if reason != "OK":
            raise RuntimeError("G44_BINDING_INTEGRITY_DENIED:" + reason)

    def _g44_assert_predecessors_lab(self, row) -> None:
        """Check ALL earlier scoped decisions under claim's BEGIN IMMEDIATE.

        A terminal predecessor with missing/mismatched effect ledger must not
        authorize the next claim. No provider proof is implied by local checks.
        """
        if not self._strict_binding_integrity_lab:
            return
        earlier = self.db.execute(
            """SELECT eo.idempotency_key
               FROM action_decisions d
               LEFT JOIN action_outbox eo ON eo.decision_id=d.decision_id
                 AND eo.owner=d.owner AND eo.tenant=d.tenant
                 AND eo.workspace=d.workspace
               WHERE d.owner=? AND d.tenant=? AND d.workspace=?
                 AND d.aggregate_key=? AND d.aggregate_seq<?
               ORDER BY d.aggregate_seq""",
            (*self._scope_args(), row["aggregate_key"], row["aggregate_seq"]),
        ).fetchall()
        for predecessor in earlier:
            if not predecessor["idempotency_key"]:
                raise RuntimeError("G44_PREDECESSOR_MISSING_DENY")
            self._g44_assert_binding_lab(predecessor["idempotency_key"])

    def _decision_row(self, decision_id: str):
        return self.db.execute(
            """SELECT * FROM action_decisions
               WHERE decision_id=? AND owner=? AND tenant=? AND workspace=?""",
            (decision_id, *self._scope_args()),
        ).fetchone()

    def _outbox_row(self, key: str):
        return self.db.execute(
            """SELECT o.*, d.data AS decision_data, d.aggregate_key, d.aggregate_seq
               FROM action_outbox o
               JOIN action_decisions d ON d.decision_id=o.decision_id
                 AND d.owner=o.owner AND d.tenant=o.tenant
                 AND d.workspace=o.workspace
               WHERE o.idempotency_key=? AND
                     o.owner=? AND o.tenant=? AND o.workspace=?""",
            (key, *self._scope_args()),
        ).fetchone()

    @staticmethod
    def _view(row) -> dict[str, Any]:
        if row is None:
            raise LookupError("action intent unavailable")
        decision = json.loads(row["decision_data"])
        return {
            "schema": SCHEMA,
            "idempotency_key": row["idempotency_key"],
            "decision_id": row["decision_id"],
            "state": row["state"],
            "attempts": int(row["attempts"]),
            "lease_owner": row["lease_owner"],
            "lease_until": row["lease_until"],
            "dispatch_started_at": row["dispatch_started_at"],
            "sent_at": row["sent_at"],
            "confirmed_at": row["confirmed_at"],
            "last_error": row["last_error"],
            "effect_ref": row["effect_ref"],
            "aggregate_key": row["aggregate_key"],
            "aggregate_seq": int(row["aggregate_seq"]),
            "decision": decision,
            "executes_action": False,
        }

    def get(self, idempotency_key: str) -> dict[str, Any]:
        return self._view(self._outbox_row(_clean(idempotency_key, 64)))

    def list(self, *, state: str = "") -> list[dict[str, Any]]:
        args: list[Any] = [*self._scope_args()]
        sql = """SELECT o.*, d.data AS decision_data, d.aggregate_key, d.aggregate_seq
                 FROM action_outbox o
                 JOIN action_decisions d ON d.decision_id=o.decision_id
                   AND d.owner=o.owner AND d.tenant=o.tenant
                   AND d.workspace=o.workspace
                 WHERE o.owner=? AND o.tenant=? AND o.workspace=?"""
        normalized = _clean(state, 40).upper()
        if normalized:
            if normalized not in STATES:
                raise ValueError("invalid outbox state")
            sql += " AND o.state=?"
            args.append(normalized)
        sql += " ORDER BY d.created_at,d.decision_id"
        return [self._view(row) for row in self.db.execute(sql, args).fetchall()]

    def enqueue(
        self,
        *,
        intent_ref: Any,
        action: Any,
        payload: Mapping[str, Any] | None,
        aggregate_key: Any,
        policy_version: Any,
        authorization_ref: Any,
        valid_until: Any,
        created_at: Any | None = None,
        requires_reauth: bool = False,
        reauth_ref: Any = "",
        transaction_id: Any = "",
        authority_budget_ref: Any = "",
        risk_points: Any = 0,
        capability_class: Any = "",
        semantic_event_id_lab: Any = "",
    ) -> dict[str, Any]:
        self.store.require_healthy()
        owner, tenant, workspace = self._scope_args()
        intent = _token(intent_ref, "intent_ref")
        action_name = _token(action, "action")
        aggregate = _token(aggregate_key, "aggregate_key")
        policy = _token(policy_version, "policy_version")
        authorization = _token(authorization_ref, "authorization_ref")
        created_dt = _utc(created_at)
        valid_dt = _utc(valid_until)
        if valid_dt <= created_dt:
            raise ValueError("authority must expire after creation")
        if (valid_dt - created_dt).total_seconds() > MAX_AUTHORITY_TTL_SECONDS:
            raise ValueError("authority validity exceeds staging maximum")
        # G47 LAB: do not let non-boolean values silently disable reauth.
        if type(requires_reauth) is not bool:
            raise TypeError("requires_reauth must be an exact boolean")
        if not isinstance(reauth_ref, str):
            raise TypeError("reauth_ref must be a string")
        reauth = _clean(reauth_ref, 160)
        if requires_reauth and not reauth:
            raise ValueError("transaction reauthentication reference required")
        if not requires_reauth and reauth:
            raise ValueError("reauth_ref without required reauthentication denied")
        transaction = _clean(transaction_id, 128)
        budget_ref = _clean(authority_budget_ref, 128)
        capability = _clean(capability_class, 80).upper()
        if isinstance(risk_points, bool) or not isinstance(risk_points, int) or not 0 <= risk_points <= 100:
            raise ValueError("risk_points must be an integer from 0 to 100")
        if transaction or budget_ref or risk_points or capability:
            if not transaction or not budget_ref or risk_points < 1 or not capability:
                raise ValueError("transaction authority budget binding incomplete")
            _token(transaction, "transaction_id")
            _token(budget_ref, "authority_budget_ref")
            _token(capability, "capability_class")

        # LAB-only strict semantic identity, never proof of event truth.
        # Identity must be an explicitly asserted, non-redacted event token.
        raw_payload = dict(payload or {})
        semantic_event = (
            _token(semantic_event_id_lab, "semantic_event_id_lab")
            if semantic_event_id_lab else ""
        )
        # G57: declaring a business event in the payload but omitting its
        # asserted semantic ID silently skipped the tenant-wide reservation.
        # Reject new unbound admissions; do not backfill historic rows, infer
        # identity from untrusted text, or claim external event authenticity.
        if "business_event_id" in raw_payload and not semantic_event:
            raise ValueError("G57_SEMANTIC_ASSERTION_REQUIRED")
        if semantic_event:
            if raw_payload.get("business_event_id") != semantic_event:
                raise ValueError("semantic event binding mismatch")
            if "business_event_id" not in redact(raw_payload):
                raise ValueError("semantic event must survive redaction")
        safe_payload = redact(raw_payload)
        try:
            # G60: never persist non-standard JSON numeric tokens. This
            # runs BEFORE BEGIN, so no reservation/intent can be partially
            # admitted after a serialization failure.
            payload_digest = _digest(safe_payload)
        except ValueError:
            raise ValueError("G60_NONFINITE_PAYLOAD_DENY") from None
        key_material = {
            "scope": [owner, tenant, workspace],
            "intent_ref": intent,
            "action": action_name,
            "aggregate_key": aggregate,
            "payload_digest": payload_digest,
            "transaction_id": transaction,
            "authority_budget_ref": budget_ref,
            "risk_points": risk_points,
            "capability_class": capability,
        }
        if semantic_event:
            key_material["semantic_event_id_lab"] = semantic_event
        # G47: a required reauthentication is part of the immutable intent
        # identity; ordinary false/empty legacy key material is unchanged.
        if requires_reauth:
            key_material["requires_reauth"] = True
            key_material["reauth_ref"] = reauth
        idempotency_key = _digest(key_material)
        decision_id = "DEC-" + idempotency_key[:24].upper()

        self._begin_or_quarantine()
        try:
            semantic_lock = None
            if semantic_event:
                semantic_lock = self.db.execute(
                    """SELECT idempotency_key, payload_digest
                       FROM semantic_reservations_lab
                       WHERE tenant=? AND business_event_id=?""",
                    (tenant, semantic_event),
                ).fetchone()
                if semantic_lock is not None and (
                    semantic_lock["idempotency_key"] != idempotency_key
                    or semantic_lock["payload_digest"] != payload_digest
                ):
                    raise ValueError("semantic business event collision")
            if semantic_event:
                # G58 LAB: a reservation is not sufficient when older local
                # decisions may lack their semantic lock. Scan SAME-TENANT
                # decisions under the existing BEGIN IMMEDIATE transaction;
                # never backfill, trust JSON with ambiguous keys, or infer
                # absence of a provider effect from missing local custody.
                def g58_unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
                    result: dict[str, Any] = {}
                    for label, value in pairs:
                        if label in result:
                            raise ValueError("duplicate historical JSON key")
                        result[label] = value
                    return result

                def g58_bad_constant(value: str) -> Any:
                    raise ValueError("nonfinite historical JSON value: " + value)

                def g60_parse_finite_float(value: str) -> float:
                    # parse_constant handles literal NaN/Infinity, but does
                    # NOT detect valid JSON exponent overflow (e.g. 1e999).
                    number = float(value)
                    if not math.isfinite(number):
                        raise ValueError("historical JSON float overflow")
                    return number

                older_decisions = self.db.execute(
                    """SELECT d.data, d.decision_id,
                              d.owner AS decision_owner,
                              d.tenant AS decision_tenant,
                              d.workspace AS decision_workspace,
                              d.intent_ref AS historical_intent,
                              d.action AS historical_action,
                              d.aggregate_key AS historical_aggregate,
                              d.aggregate_seq AS historical_sequence,
                              d.payload_digest AS historical_digest,
                              d.policy_version AS historical_policy,
                              d.authorization_ref AS historical_authority,
                              d.valid_until AS historical_valid_until,
                              d.created_at AS historical_created_at,
                              o.idempotency_key AS historical_key,
                              o.owner AS outbox_owner,
                              o.tenant AS outbox_tenant,
                              o.workspace AS outbox_workspace
                       FROM action_decisions d
                       LEFT JOIN action_outbox o
                         ON o.decision_id=d.decision_id
                       WHERE d.tenant=?
                       ORDER BY d.decision_id""",
                    (tenant,),
                ).fetchall()
                for historical in older_decisions:
                    try:
                        decoded = json.loads(
                            historical["data"],
                            object_pairs_hook=g58_unique_pairs,
                            parse_constant=g58_bad_constant,
                            parse_float=g60_parse_finite_float,
                        )
                        if not isinstance(decoded, dict):
                            raise ValueError("historical root is not an object")
                        historical_payload = decoded.get("payload")
                        if not isinstance(historical_payload, dict):
                            raise ValueError("historical payload is not an object")
                        if (historical["historical_key"] is None
                                or historical["outbox_owner"] != historical["decision_owner"]
                                or historical["outbox_tenant"] != tenant
                                or historical["outbox_workspace"] != historical["decision_workspace"]):
                            raise ValueError("historical decision/outbox scope missing")
                        # G59: historical identity must be internally
                        # consistent, regardless of whether its old semantic
                        # reservation survived. A syntactically valid edit to
                        # business_event_id cannot disguise an old obligation.
                        if _digest(historical_payload) != historical["historical_digest"]:
                            raise RuntimeError("G59_HISTORICAL_BINDING_DENY")
                        historic_expected = {
                            "schema": SCHEMA,
                            "decision_id": historical["decision_id"],
                            "idempotency_key": historical["historical_key"],
                            "owner_id": historical["decision_owner"],
                            "tenant_id": historical["decision_tenant"],
                            "workspace_id": historical["decision_workspace"],
                            "intent_ref": historical["historical_intent"],
                            "action": historical["historical_action"],
                            "aggregate_key": historical["historical_aggregate"],
                            "aggregate_seq": historical["historical_sequence"],
                            "payload_digest": historical["historical_digest"],
                            "policy_version": historical["historical_policy"],
                            "authorization_ref": historical["historical_authority"],
                            "valid_until": historical["historical_valid_until"],
                            "created_at": historical["historical_created_at"],
                        }
                        if (any(decoded.get(name) != value
                                for name,value in historic_expected.items())
                                or decoded.get("grants_authority") is not False):
                            raise RuntimeError("G59_HISTORICAL_BINDING_DENY")
                        # G59: the digest and JSON fields alone could be
                        # rewritten together. Bind semantic ID and reconstruct
                        # the ORIGINAL local idempotency material as well.
                        historic_semantic=decoded.get("semantic_event_id_lab","")
                        historic_reauth=decoded.get("requires_reauth",False)
                        historic_reauth_ref=decoded.get("reauth_ref","")
                        historic_risk=decoded.get("risk_points",0)
                        if (not isinstance(historic_semantic,str)
                                or type(historic_reauth) is not bool
                                or not isinstance(historic_reauth_ref,str)
                                or (historic_reauth and not historic_reauth_ref)
                                or (not historic_reauth and historic_reauth_ref)
                                or type(historic_risk) is not int
                                or not 0 <= historic_risk <= 100):
                            raise RuntimeError("G59_HISTORICAL_BINDING_DENY")
                        if (historic_semantic and
                                historical_payload.get("business_event_id") != historic_semantic):
                            raise RuntimeError("G59_HISTORICAL_BINDING_DENY")
                        historic_material={
                            "scope":[historical["decision_owner"],tenant,
                                     historical["decision_workspace"]],
                            "intent_ref":historical["historical_intent"],
                            "action":historical["historical_action"],
                            "aggregate_key":historical["historical_aggregate"],
                            "payload_digest":historical["historical_digest"],
                            "transaction_id":decoded.get("transaction_id",""),
                            "authority_budget_ref":decoded.get("authority_budget_ref",""),
                            "risk_points":historic_risk,
                            "capability_class":decoded.get("capability_class",""),
                        }
                        if historic_semantic:
                            historic_material["semantic_event_id_lab"]=historic_semantic
                        if historic_reauth:
                            historic_material["requires_reauth"]=True
                            historic_material["reauth_ref"]=historic_reauth_ref
                        if (_digest(historic_material) != historical["historical_key"]
                                or historical["decision_id"] !=
                                "DEC-"+historical["historical_key"][:24].upper()):
                            raise RuntimeError("G59_HISTORICAL_BINDING_DENY")
                        if "business_event_id" in historical_payload:
                            stored_event = historical_payload["business_event_id"]
                            if (not isinstance(stored_event, str)
                                    or not _SAFE_TOKEN.fullmatch(stored_event)):
                                raise ValueError("historical event identity invalid")
                    except (ValueError, TypeError, UnicodeError):
                        raise RuntimeError(
                            "G58_HISTORICAL_JSON_UNTRUSTED_DENY"
                        ) from None
                    if (historical_payload.get("business_event_id") == semantic_event
                            and historical["historical_key"] != idempotency_key):
                        raise RuntimeError(
                            "G58_HISTORICAL_SEMANTIC_CUSTODY_DENY"
                        )
            existing = self.db.execute(
                """SELECT o.idempotency_key, d.data AS decision_data
                   FROM action_decisions d
                   JOIN action_outbox o ON o.decision_id=d.decision_id
                   WHERE d.owner=? AND d.tenant=? AND d.workspace=? AND d.intent_ref=?""",
                (owner, tenant, workspace, intent),
            ).fetchone()
            if existing is not None:
                if existing["idempotency_key"] != idempotency_key:
                    raise ValueError("intent_ref idempotency collision")
                if semantic_event and semantic_lock is None:
                    raise ValueError("semantic lock missing for existing intent")
                # G48: even a same-key existing intent may have been poisoned
                # after its first admission. Never label it IDEMPOTENT until
                # its persisted decision, reauth and ledger bind correctly.
                from atlasquant_aion_outbox_binding_lab import binding_issue_lab
                existing_issue = binding_issue_lab(
                    self.db, idempotency_key, self._scope_args()
                )
                if existing_issue != "OK":
                    raise RuntimeError(
                        "G48_EXISTING_BINDING_DENIED:" + existing_issue
                    )
                self._commit_or_quarantine()
                out = self.get(idempotency_key)
                return {**out, "enqueue_state": "IDEMPOTENT"}

            if semantic_event:
                # Unique per TENANT+event across owners and workspaces.
                # No trusted source namespace exists yet: legitimate source
                # collisions must fail closed rather than silently duplicate.
                # The unique reservation and Outbox rows are written inside
                # ONE SQLite transaction, never as separate auto-commits.
                self.db.execute(
                    """INSERT INTO semantic_reservations_lab(
                        owner,tenant,business_event_id,workspace,intent_ref,
                        idempotency_key,payload_digest
                    ) VALUES (?,?,?,?,?,?,?)""",
                    (owner, tenant, semantic_event, workspace, intent,
                     idempotency_key, payload_digest),
                )
            seq = int(
                self.db.execute(
                    """SELECT COALESCE(MAX(aggregate_seq),0)+1
                       FROM action_decisions
                       WHERE owner=? AND tenant=? AND workspace=? AND aggregate_key=?""",
                    (owner, tenant, workspace, aggregate),
                ).fetchone()[0]
            )
            decision = {
                "schema": SCHEMA,
                "decision_id": decision_id,
                "owner_id": owner,
                "tenant_id": tenant,
                "workspace_id": workspace,
                "intent_ref": intent,
                "action": action_name,
                "aggregate_key": aggregate,
                "aggregate_seq": seq,
                "payload": safe_payload,
                "payload_digest": payload_digest,
                "semantic_event_id_lab": semantic_event,
                "policy_version": policy,
                "authorization_ref": authorization,
                "valid_until": _iso(valid_dt),
                "created_at": _iso(created_dt),
                "requires_reauth": requires_reauth is True,
                "reauth_ref": reauth,
                "transaction_id": transaction,
                "authority_budget_ref": budget_ref,
                "risk_points": risk_points,
                "capability_class": capability,
                "idempotency_key": idempotency_key,
                "grants_authority": False,
            }
            encoded = _canonical(decision)
            self.db.execute(
                """INSERT INTO action_decisions(
                    decision_id,owner,tenant,workspace,intent_ref,action,
                    aggregate_key,aggregate_seq,payload_digest,policy_version,
                    authorization_ref,valid_until,created_at,data
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    decision_id,
                    owner,
                    tenant,
                    workspace,
                    intent,
                    action_name,
                    aggregate,
                    seq,
                    payload_digest,
                    policy,
                    authorization,
                    _iso(valid_dt),
                    _iso(created_dt),
                    encoded,
                ),
            )
            self.db.execute(
                """INSERT INTO action_outbox(
                    idempotency_key,decision_id,owner,tenant,workspace,state,data
                ) VALUES (?,?,?,?,?,'PENDING',?)""",
                (
                    idempotency_key,
                    decision_id,
                    owner,
                    tenant,
                    workspace,
                    _canonical({
                        "idempotency_key": idempotency_key,
                        "decision_id": decision_id,
                        "state": "PENDING",
                    }),
                ),
            )
            self._commit_or_quarantine()
        except Exception as original_error:
            if self.db is not None:
                self._rollback_preserving_original(original_error)
            raise
        out = self.get(idempotency_key)
        return {**out, "enqueue_state": "ENQUEUED"}

    def release_expired_claims(self, *, now: Any | None = None) -> int:
        current = _iso(_utc(now))
        self._begin_or_quarantine()
        try:
            cursor = self.db.execute(
                """UPDATE action_outbox
                   SET state='RETRY',lease_owner='',lease_until='',
                       last_error='CLAIM_LEASE_EXPIRED_BEFORE_DISPATCH'
                   WHERE owner=? AND tenant=? AND workspace=?
                     AND state='CLAIMED' AND lease_until<>'' AND lease_until<?""",
                (*self._scope_args(), current),
            )
            count = int(cursor.rowcount)
            self._commit_or_quarantine()
            return count
        except Exception as original_error:
            if self.db is not None:
                self._rollback_preserving_original(original_error)
            raise

    def claim_next(
        self,
        worker_id: Any,
        *,
        now: Any | None = None,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
    ) -> dict[str, Any] | None:
        worker = _token(worker_id, "worker_id")
        if isinstance(lease_seconds, bool) or not 1 <= int(lease_seconds) <= MAX_LEASE_SECONDS:
            raise ValueError("invalid lease_seconds")
        now_dt = _utc(now)
        now_iso = _iso(now_dt)
        lease_until = _iso(now_dt + timedelta(seconds=int(lease_seconds)))
        owner, tenant, workspace = self._scope_args()

        self.release_expired_claims(now=now_dt)
        self._begin_or_quarantine()
        try:
            row = self.db.execute(
                """SELECT o.idempotency_key, d.aggregate_key, d.aggregate_seq
                   FROM action_outbox o
                   JOIN action_decisions d ON d.decision_id=o.decision_id
                     AND d.owner=o.owner AND d.tenant=o.tenant
                     AND d.workspace=o.workspace
                   WHERE o.owner=? AND o.tenant=? AND o.workspace=?
                     AND o.state IN ('PENDING','RETRY')
                     AND NOT EXISTS (
                         SELECT 1
                         FROM action_decisions earlier
                         LEFT JOIN action_outbox eo ON eo.decision_id=earlier.decision_id
                            AND eo.owner=earlier.owner AND eo.tenant=earlier.tenant
                            AND eo.workspace=earlier.workspace
                         WHERE earlier.owner=d.owner
                           AND earlier.tenant=d.tenant
                           AND earlier.workspace=d.workspace
                           AND earlier.aggregate_key=d.aggregate_key
                           AND earlier.aggregate_seq<d.aggregate_seq
                           AND (eo.idempotency_key IS NULL OR
                                 eo.state NOT IN ('CONFIRMED','REVOKED','BLOCKED_REAPPROVAL','FAILED'))
                     )
                   ORDER BY d.created_at,d.decision_id
                   LIMIT 1""",
                (owner, tenant, workspace),
            ).fetchone()
            if row is None:
                self._commit_or_quarantine()
                return None
            key = row["idempotency_key"]
            self._g44_assert_binding_lab(key)
            self._g44_assert_predecessors_lab(row)
            cursor = self.db.execute(
                """UPDATE action_outbox
                   SET state='CLAIMED',lease_owner=?,lease_until=?,attempts=attempts+1,last_error=''
                   WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                     AND state IN ('PENDING','RETRY')""",
                (worker, lease_until, key, owner, tenant, workspace),
            )
            if cursor.rowcount != 1:
                try:
                    self.db.rollback()
                except Exception as rollback_error:
                    self.store.quarantine_failed_transaction()
                    self.db = None
                    raise StorageUnavailableError(
                        "OUTBOX_CLAIM_ROLLBACK_UNCERTAIN_NO_RETRY"
                    ) from rollback_error
                return None
            self._commit_or_quarantine()
            return self.get(key)
        except Exception as original_error:
            if self.db is not None:
                self._rollback_preserving_original(original_error)
            raise

    def _authorization_gate(
        self,
        intent: Mapping[str, Any],
        authorize: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        now_dt: datetime,
    ) -> tuple[bool, str, dict[str, Any]]:
        if not callable(authorize):
            raise TypeError("authorization revalidator required")
        decision = _mapping(intent.get("decision"))
        # G48: malformed local reauth metadata must never be interpreted as
        # false/absent, even when optional G44 binding is not enabled.
        requires_reauth = decision.get("requires_reauth")
        reauth_ref = decision.get("reauth_ref")
        if (type(requires_reauth) is not bool or
                not isinstance(reauth_ref, str) or
                (requires_reauth and
                 (not reauth_ref or reauth_ref.strip() != reauth_ref)) or
                (not requires_reauth and reauth_ref)):
            return False, "BLOCKED_REAPPROVAL", {
                "reason": "REAUTH_MATERIAL_INVALID"
            }
        if now_dt >= _utc(decision.get("valid_until")):
            return False, "BLOCKED_REAPPROVAL", {"reason": "AUTHORITY_EXPIRED"}
        try:
            current = _mapping(_bound_callback(authorize, dict(decision)))
        except Exception:
            return False, "REVOKED", {"reason": "AUTHORITY_REVALIDATION_FAILED"}
        if current.get("allowed") is not True:
            return False, "REVOKED", {"reason": "AUTHORITY_REVOKED"}
        if _clean(current.get("actor_id"), 128) != self.scope.owner_id:
            return False, "REVOKED", {"reason": "ACTOR_MISMATCH"}
        for field, wanted in (
            ("tenant_id", self.scope.tenant_id),
            ("workspace_id", self.scope.workspace_id),
        ):
            supplied = _clean(current.get(field), 128)
            if self._strict_authority_scope_lab and not supplied:
                return False, "REVOKED", {"reason": field.upper() + "_REQUIRED"}
            if supplied and supplied != wanted:
                return False, "REVOKED", {"reason": field.upper() + "_MISMATCH"}
        if _clean(current.get("policy_version"), 128) != _clean(decision.get("policy_version"), 128):
            return False, "BLOCKED_REAPPROVAL", {"reason": "POLICY_VERSION_CHANGED"}
        if _clean(current.get("authorization_ref"), 128) != _clean(decision.get("authorization_ref"), 128):
            return False, "BLOCKED_REAPPROVAL", {"reason": "AUTHORIZATION_CHANGED"}
        if decision.get("requires_reauth") is True:
            if current.get("reauthenticated") is not True:
                return False, "BLOCKED_REAPPROVAL", {"reason": "REAUTH_REQUIRED"}
            if _clean(current.get("reauth_ref"), 160) != _clean(decision.get("reauth_ref"), 160):
                return False, "BLOCKED_REAPPROVAL", {"reason": "REAUTH_TRANSACTION_MISMATCH"}
        return True, "ALLOW", current

    def _set_blocked(
        self, key: str, state: str, reason: str, *,
        worker_lab: str = "", generation_lab: int = 0,
    ) -> dict[str, Any]:
        if state not in {"REVOKED", "BLOCKED_REAPPROVAL"}:
            raise ValueError("invalid blocked state")
        with self._managed_write_transaction():
            if self._strict_claim_fencing_lab:
                cursor = self.db.execute(
                    """UPDATE action_outbox
                       SET state=?,lease_owner='',lease_until='',last_error=?
                       WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                         AND state='CLAIMED' AND lease_owner=? AND attempts=?""",
                    (state, _clean(reason, 240), key, *self._scope_args(),
                     worker_lab, generation_lab),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("FENCE_STALE_AUTHORITY_TRANSITION_NO_WRITE")
            else:
                self.db.execute(
                    """UPDATE action_outbox
                       SET state=?,lease_owner='',lease_until='',last_error=?
                       WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?""",
                    (state, _clean(reason, 240), key, *self._scope_args()),
                )
        return self.get(key)

    def _confirm(
        self,
        key: str,
        *,
        effect_ref: Any,
        confirmed_at: datetime,
        result: Mapping[str, Any] | None = None,
        fence_lab: tuple[str, int] | None = None,
        reconcile_snapshot_lab: tuple[str, int, str, str, str] | None = None,
    ) -> dict[str, Any]:
        effect = _token(effect_ref, "effect_ref", 128)
        encoded = _canonical(redact(dict(result or {})))
        self._begin_or_quarantine()
        try:
            self._g44_assert_binding_lab(key)
            if reconcile_snapshot_lab is None and fence_lab is None:
                # G53: direct confirmation is idempotent/terminal-immutable
                # regardless of optional integrity flags. Fence and snapshot
                # callers retain their original stricter protocol precedence.
                # Local SQLite integrity only; NOT trusted provider evidence.
                existing_state = self._outbox_row(key)
                if existing_state is None:
                    raise RuntimeError("G42_CONFIRM_OUTBOX_ABSENT")
                if existing_state["state"] == "CONFIRMED":
                    original_effect = self.db.execute(
                        """SELECT effect_ref, confirmed_at FROM action_effects
                           WHERE idempotency_key=? AND owner=? AND tenant=?
                             AND workspace=?""",
                        (key, *self._scope_args()),
                    ).fetchone()
                    if (original_effect is None or
                            original_effect["effect_ref"] != effect or
                            existing_state["effect_ref"] != effect or
                            original_effect["confirmed_at"] !=
                            existing_state["confirmed_at"]):
                        raise RuntimeError("G42_CONFIRMED_LEDGER_INVARIANT_DENY")
                    if self._strict_projection_lab:
                        # G55: idempotent replay must not silently accept a
                        # corrupt/stale raw JSON projection. Strict mode
                        # validates but NEVER repairs a historical record.
                        expected_projection = self._g43_projection_candidate_lab(
                            existing_state
                        )
                        if expected_projection != existing_state["data"]:
                            raise RuntimeError(
                                "G55_CONFIRMED_PROJECTION_INTEGRITY_DENY"
                            )
                    self._commit_or_quarantine()
                    return self.get(key)
                if existing_state["state"] not in {"UNCERTAIN", "SENT"}:
                    raise RuntimeError("G42_UNSAFE_PRECONFIRM_PHASE_DENY")
                # Nonterminal row plus an existing effect is a contradictory
                # local history, never authority to rewrite its timestamp.
                orphan_effect = self.db.execute(
                    """SELECT 1 FROM action_effects
                       WHERE idempotency_key=? AND owner=? AND tenant=?
                         AND workspace=?""",
                    (key, *self._scope_args()),
                ).fetchone()
                if orphan_effect is not None:
                    raise RuntimeError("G53_NONCONFIRMED_HAS_EFFECT_DENY")
            if reconcile_snapshot_lab is not None:
                # Read under BEGIN IMMEDIATE: no other SQLite writer can
                # change the row between this preflight and the ledger insert.
                phase, epoch, owner, until, original_ref = reconcile_snapshot_lab
                current = self._outbox_row(key)
                if (current is None or phase not in {"SENT", "UNCERTAIN"}
                        or current["state"] != phase
                        or int(current["attempts"]) != epoch
                        or current["lease_owner"] != owner
                        or current["lease_until"] != until
                        or current["effect_ref"] != original_ref):
                    raise RuntimeError("G42_RECONCILE_SNAPSHOT_STALE_NO_LEDGER")
            existing = self.db.execute(
                """SELECT effect_ref FROM action_effects
                   WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?""",
                (key, *self._scope_args()),
            ).fetchone()
            if existing is not None and existing["effect_ref"] != effect:
                raise ValueError("effect ledger idempotency collision")
            if existing is not None:
                # G54: fence and snapshot paths cannot adopt a preexisting
                # synthetic ledger while the associated row is nonterminal.
                # A matching receipt reference is NOT proof of consistency.
                # Collision denial above intentionally keeps G41 precedence.
                current_effect_owner = self._outbox_row(key)
                if (current_effect_owner is None or
                        current_effect_owner["state"] != "CONFIRMED"):
                    raise RuntimeError("G54_NONCONFIRMED_LEDGER_INCONSISTENT_DENY")
            if existing is None:
                self.db.execute(
                    """INSERT INTO action_effects(
                        idempotency_key,owner,tenant,workspace,effect_ref,confirmed_at,data
                    ) VALUES (?,?,?,?,?,?,?)""",
                    (
                        key,
                        *self._scope_args(),
                        effect,
                        _iso(confirmed_at),
                        encoded,
                    ),
                )
            owner, epoch = fence_lab if fence_lab else ("", 0)
            if reconcile_snapshot_lab is None:
                reconcile_snapshot_lab = ("", 0, "", "", "")
            phase, observed_epoch, observed_owner, observed_until, original_ref = (
                reconcile_snapshot_lab
            )
            cursor = self.db.execute(
                """UPDATE action_outbox
                   SET state='CONFIRMED',confirmed_at=?,effect_ref=?,
                       lease_owner='',lease_until='',last_error=''
                   WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                     AND (?=1 OR (state='UNCERTAIN' AND lease_owner=? AND attempts=?))
                     AND (?=1 OR (state=? AND attempts=? AND lease_owner=?
                                  AND lease_until=? AND effect_ref=?))""",
                (_iso(confirmed_at), effect, key, *self._scope_args(),
                 int(fence_lab is None), owner, epoch,
                 int(not phase), phase, observed_epoch, observed_owner,
                 observed_until, original_ref),
            )
            if fence_lab and cursor.rowcount != 1:
                raise RuntimeError("FENCE_STALE_CONFIRM_NO_LEDGER_WRITE")
            if phase and cursor.rowcount != 1:
                raise RuntimeError("G42_RECONCILE_SNAPSHOT_STALE_NO_LEDGER")
            if self._strict_projection_lab:
                self._g43_sync_projection_in_tx_lab(key)
            self._commit_or_quarantine()
        except Exception as original_error:
            if self.db is not None:
                self._rollback_preserving_original(original_error)
            raise
        return self.get(key)

    # A190 G43 — opt-in LAB projection coherence. This only synchronizes
    # copies of columns in an existing JSON field; NOT a provider receipt,
    # trusted migration, remote CAS, or authorization to dispatch.
    _G43_PROJECTED_FIELDS = (
        "state", "attempts", "lease_owner", "lease_until",
        "dispatch_started_at", "sent_at", "confirmed_at",
        "last_error", "effect_ref",
    )

    def _g43_projection_candidate_lab(self, row):
        try:
            document = json.loads(row["data"])
        except (TypeError, ValueError) as exc:
            raise RuntimeError("G43_PROJECTION_INVALID_JSON_DENY") from exc
        if not isinstance(document, dict):
            raise RuntimeError("G43_PROJECTION_NOT_OBJECT_DENY")
        if (document.get("idempotency_key") != row["idempotency_key"] or
                document.get("decision_id") != row["decision_id"]):
            raise RuntimeError("G43_PROJECTION_IDENTITY_MISMATCH_DENY")
        if document.get("state") not in STATES:
            raise RuntimeError("G43_PROJECTION_STATE_INVALID_DENY")
        ledger = self.db.execute(
            """SELECT effect_ref,confirmed_at FROM action_effects
               WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?""",
            (row["idempotency_key"], *self._scope_args()),
        ).fetchall()
        if len(ledger) > 1:
            raise RuntimeError("G43_DUPLICATE_LEDGER_DENY")
        if row["state"] == "CONFIRMED":
            if (len(ledger) != 1 or
                    ledger[0]["effect_ref"] != row["effect_ref"] or
                    ledger[0]["confirmed_at"] != row["confirmed_at"]):
                raise RuntimeError("G43_CONFIRMED_LEDGER_INCONSISTENT_DENY")
        elif ledger:
            raise RuntimeError("G43_NONCONFIRMED_HAS_EFFECT_DENY")
        for field in self._G43_PROJECTED_FIELDS:
            document[field] = int(row[field]) if field == "attempts" else row[field]
        return _canonical(document)

    def _g43_sync_projection_in_tx_lab(self, key: str) -> bool:
        # Caller owns BEGIN IMMEDIATE; compare current raw document and phase.
        row = self._outbox_row(key)
        if row is None:
            raise RuntimeError("G43_PROJECTION_OUTBOX_ABSENT")
        expected = self._g43_projection_candidate_lab(row)
        if expected == row["data"]:
            return False
        cursor = self.db.execute(
            """UPDATE action_outbox SET data=?
               WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                 AND data=? AND state=? AND attempts=? AND effect_ref=?""",
            (expected, key, *self._scope_args(), row["data"], row["state"],
             row["attempts"], row["effect_ref"]),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("G43_PROJECTION_CAS_LOST_DENY")
        return True

    def projection_plan_lab(self, idempotency_key: str) -> dict[str, Any]:
        """READ ONLY. Reports a one-row dry run, no implicit historical repair."""
        if not self._strict_projection_lab:
            raise RuntimeError("G43_PROJECTION_OPT_IN_REQUIRED")
        key = _clean(idempotency_key, 64)
        self.store.require_healthy()
        row = self._outbox_row(key)
        if row is None:
            raise LookupError("G43_PROJECTION_ROW_UNAVAILABLE")
        replacement = self._g43_projection_candidate_lab(row)
        return {
            "schema": "AION-A190-G43-PROJECTION-DRYRUN-V1",
            "idempotency_key": key,
            "owner": self.scope.owner_id,
            "tenant": self.scope.tenant_id,
            "workspace": self.scope.workspace_id,
            "original_data_sha256": sha256(row["data"].encode("utf-8")).hexdigest(),
            "state": row["state"],
            "attempts": int(row["attempts"]),
            "lease_owner": row["lease_owner"],
            "lease_until": row["lease_until"],
            "effect_ref": row["effect_ref"],
            "confirmed_at": row["confirmed_at"],
            "changed": replacement != row["data"],
        }

    def apply_projection_plan_lab(
        self, plan: Mapping[str, Any], *, explicit_approval: bool = False,
    ) -> dict[str, Any]:
        """LAB only: one approved row, one conditional update, zero ledger writes.

        Approval is an explicit argument, NOT inferred from the dry-run.
        Production migration/recovery remains unapproved and HARD NO-GO.
        """
        if not self._strict_projection_lab:
            raise RuntimeError("G43_PROJECTION_OPT_IN_REQUIRED")
        if explicit_approval is not True:
            raise RuntimeError("G43_EXPLICIT_APPROVAL_REQUIRED")
        if not isinstance(plan, Mapping):
            raise RuntimeError("G43_INVALID_PLAN")
        if (plan.get("schema") != "AION-A190-G43-PROJECTION-DRYRUN-V1" or
                tuple(plan.get(k) for k in ("owner", "tenant", "workspace"))
                != self._scope_args()):
            raise RuntimeError("G43_PLAN_SCOPE_OR_VERSION_DENIED")
        key = _clean(plan.get("idempotency_key"), 64)
        with self._managed_write_transaction():
            row = self._outbox_row(key)
            if row is None:
                raise RuntimeError("G43_PLAN_OUTBOX_ABSENT")
            snapshot = (
                sha256(row["data"].encode("utf-8")).hexdigest(),
                row["state"], int(row["attempts"]), row["lease_owner"],
                row["lease_until"], row["effect_ref"], row["confirmed_at"],
            )
            expected = (
                plan.get("original_data_sha256"),
                plan.get("state"), plan.get("attempts"), plan.get("lease_owner"),
                plan.get("lease_until"), plan.get("effect_ref"),
                plan.get("confirmed_at"),
            )
            if snapshot != expected:
                raise RuntimeError("G43_STALE_DRYRUN_REFUSED")
            changed = self._g43_sync_projection_in_tx_lab(key)
        return {"idempotency_key": key, "updated": changed,
                "state": self.get(key)["state"],
                "schema": "AION-A190-G43-PROJECTION-DRYRUN-V1"}

    def _reconciliation_authority_lab(
        self, intent: Mapping[str, Any],
        authorize: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    ) -> bool:
        """Separate LOOKUP permission; never grants SEND or changes state.

        Historical SEND validity is deliberately NOT required to reconcile
        an already ambiguous effect. Returns False on missing authority.
        """
        if not callable(authorize):
            return False
        try:
            current = _mapping(_bound_callback(authorize, dict(intent["decision"])))
        except Exception:
            return False
        required = {
            "actor_id": self.scope.owner_id,
            "tenant_id": self.scope.tenant_id,
            "workspace_id": self.scope.workspace_id,
            "purpose": "RECONCILE_LOOKUP",
        }
        return current.get("allowed") is True and all(
            type(current.get(field)) is str and current.get(field) == wanted
            for field, wanted in required.items()
        )

    def _post_witness_freshness_lab(
        self, *, key: str, worker: str, recorded: datetime,
    ) -> str | None:
        """Fail closed after uncertain reservation on expired/rewound clock.

        This is a synthetic test-only clock; not a credible independent clock.
        No adapter access if any condition cannot be established.
        """
        if self._fresh_dispatch_clock_lab is None:
            return None
        try:
            fresh = _utc(_bound_callback(self._fresh_dispatch_clock_lab))
            record = self.get(key)
            if fresh < recorded:
                return "CLOCK_REWOUND_NO_SEND"
            if record["state"] != "UNCERTAIN" or record["lease_owner"] != worker:
                return "CLAIM_CHANGED_NO_SEND"
            if not record["lease_until"] or fresh >= _utc(record["lease_until"]):
                return "LEASE_EXPIRED_NO_SEND"
            if fresh >= _utc(record["decision"]["valid_until"]):
                return "AUTHORITY_EXPIRED_AFTER_WITNESS_NO_SEND"
        except Exception:
            return "FRESH_CLOCK_UNAVAILABLE_NO_SEND"
        return None

    def _fence_assert_lab(
        self, key: str, worker: str, epoch: int, expected_state: str,
    ) -> dict[str, Any]:
        """Read-only local persisted fencing preflight, NOT provider custody."""
        record = self.get(key)
        if (record["state"] != expected_state or
                record["lease_owner"] != worker or
                record["attempts"] != epoch):
            raise RuntimeError("FENCE_STALE_GENERATION_OR_STATE_NO_SEND")
        return record

    def dispatch_claimed(
        self,
        idempotency_key: Any,
        *,
        worker_id: Any,
        authorize: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        adapter: Any,
        cumulative_authority_guard: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
        now: Any | None = None,
        claim_generation_lab: int | None = None,
    ) -> dict[str, Any]:
        """Dispatch one claimed intent; uncertain outcomes require reconciliation."""
        key = _clean(idempotency_key, 64)
        worker = _token(worker_id, "worker_id")
        now_dt = _utc(now)
        self._g44_assert_binding_lab(key)
        intent = self.get(key)
        if self._strict_claim_fencing_lab:
            if type(claim_generation_lab) is not int or claim_generation_lab < 1:
                raise ValueError("FENCE_GENERATION_REQUIRED")
            if claim_generation_lab != intent["attempts"]:
                raise RuntimeError("FENCE_STALE_GENERATION_OR_STATE_NO_SEND")
        if intent["state"] != "CLAIMED":
            raise ValueError("intent must be CLAIMED before dispatch")
        if intent["lease_owner"] != worker:
            raise PermissionError("worker does not own claim")
        if not intent["lease_until"] or now_dt >= _utc(intent["lease_until"]):
            raise TimeoutError("claim lease expired before dispatch")

        allowed, blocked_state, auth = self._authorization_gate(intent, authorize, now_dt)
        self._g44_assert_binding_lab(key)
        if self._strict_claim_fencing_lab:
            self._fence_assert_lab(key, worker, claim_generation_lab, "CLAIMED")
        if not allowed:
            return self._set_blocked(
                key, blocked_state, auth.get("reason", blocked_state),
                worker_lab=worker, generation_lab=claim_generation_lab or 0,
            )

        decision = _mapping(intent.get("decision"))
        budget_ref = _clean(decision.get("authority_budget_ref"), 128)
        if budget_ref:
            if not callable(cumulative_authority_guard):
                return self._set_blocked(
                    key,
                    "BLOCKED_REAPPROVAL",
                    "CUMULATIVE_AUTHORITY_GUARD_REQUIRED",
                )
            try:
                budget = _mapping(_bound_callback(cumulative_authority_guard, dict(decision)))
            except Exception:
                return self._set_blocked(
                    key,
                    "BLOCKED_REAPPROVAL",
                    "CUMULATIVE_AUTHORITY_GUARD_FAILED",
                )
            if budget.get("allowed") is not True:
                return self._set_blocked(
                    key,
                    "BLOCKED_REAPPROVAL",
                    _clean(budget.get("reason") or "CUMULATIVE_AUTHORITY_BUDGET_EXCEEDED", 240),
                )
            if _clean(budget.get("authority_budget_ref"), 128) != budget_ref:
                return self._set_blocked(
                    key,
                    "BLOCKED_REAPPROVAL",
                    "CUMULATIVE_AUTHORITY_BUDGET_REF_MISMATCH",
                )
            if _clean(budget.get("transaction_id"), 128) != _clean(decision.get("transaction_id"), 128):
                return self._set_blocked(
                    key,
                    "BLOCKED_REAPPROVAL",
                    "CUMULATIVE_AUTHORITY_TRANSACTION_MISMATCH",
                )

        if self._strict_claim_fencing_lab:
            self._fence_assert_lab(key, worker, claim_generation_lab, "CLAIMED")
        # A180: persist UNCERTAIN BEFORE contacting the witness. The witness
        # might reserve the first attempt and then time out: if the host dies
        # there, the original claim must NOT become an automatic RETRY.
        with self._managed_write_transaction():
            reserved = self.db.execute(
                """UPDATE action_outbox
                   SET state='UNCERTAIN',dispatch_started_at=?,
                       last_error='FIRST_ATTEMPT_WITNESS_PENDING'
                   WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                     AND state='CLAIMED' AND lease_owner=?
                     AND (?=1 OR attempts=?)""",
                (_iso(now_dt), key, *self._scope_args(), worker,
                 int(not self._strict_claim_fencing_lab),
                 claim_generation_lab or 0),
            )
            if reserved.rowcount != 1:
                raise RuntimeError("INFLIGHT_CLAIM_CHANGED_NO_SEND")

        # A first-attempt witness is a mandatory precondition for this
        # experimental Outbox. No callback, false, invalid signature, timeout
        # or lost response => DENY SEND, retain UNCERTAIN after restart.
        if not self._reserved_first_attempt(intent):
            if self._strict_claim_fencing_lab:
                self._fence_assert_lab(key, worker, claim_generation_lab, "UNCERTAIN")
            with self._managed_write_transaction():
                cursor = self.db.execute(
                    """UPDATE action_outbox
                       SET state='UNCERTAIN',lease_owner='',lease_until='',
                           last_error='FIRST_ATTEMPT_WITNESS_UNVERIFIED_NO_SEND'
                       WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                         AND state='UNCERTAIN'
                         AND (?=1 OR (lease_owner=? AND attempts=?))""",
                    (key, *self._scope_args(), int(not self._strict_claim_fencing_lab),
                     worker, claim_generation_lab or 0),
                )
                if self._strict_claim_fencing_lab and cursor.rowcount != 1:
                    raise RuntimeError("FENCE_STALE_WITNESS_RESULT_NO_WRITE")
            return {**self.get(key),
                    "dispatch_state": "UNCERTAIN_PRE_DISPATCH_RESERVATION_REQUIRED"}

        # A possibly reserved first attempt can never be returned to RETRY
        # after a failed freshness check: preserve the UNCERTAIN reservation.
        freshness_failure = self._post_witness_freshness_lab(
            key=key, worker=worker, recorded=now_dt,
        )
        if freshness_failure:
            if self._strict_claim_fencing_lab:
                self._fence_assert_lab(key, worker, claim_generation_lab, "UNCERTAIN")
            with self._managed_write_transaction():
                self.db.execute(
                    """UPDATE action_outbox
                       SET state='UNCERTAIN',lease_owner='',lease_until='',last_error=?
                       WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                         AND state='UNCERTAIN'""",
                    (freshness_failure, key, *self._scope_args()),
                )
            return {**self.get(key), "dispatch_state": "UNCERTAIN_RECONCILE_REQUIRED"}

        if self._strict_claim_fencing_lab:
            self._fence_assert_lab(key, worker, claim_generation_lab, "UNCERTAIN")
        # No adapter attribute lookup (and therefore no user-defined property
        # getter) until the first-attempt witness passes. With G12 defaults
        # this line is unreachable regardless of caller-supplied callbacks.
        self._g44_assert_binding_lab(key)
        send = getattr(adapter, "send", None)
        self._g44_assert_binding_lab(key)
        if not callable(send):
            if self._strict_claim_fencing_lab:
                self._fence_assert_lab(key, worker, claim_generation_lab, "UNCERTAIN")
            # After UNCERTAIN reservation, any missing adapter must stay
            # uncertain; never make a fresh claim or silently retry.
            with self._managed_write_transaction():
                self.db.execute(
                    """UPDATE action_outbox SET state='UNCERTAIN',lease_owner='',
                       lease_until='',last_error='ADAPTER_SEND_MISSING_NO_SEND'
                       WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                         AND state='UNCERTAIN'""",
                    (key, *self._scope_args()),
                )
            return {**self.get(key), "dispatch_state": "UNCERTAIN_RECONCILE_REQUIRED"}

        # Adapter properties are caller-controlled code too; they can block,
        # advance time, or even alter the local claim between our first fresh
        # check and the actual send() call. Recheck AFTER getter, BEFORE call.
        getter_freshness_failure = self._post_witness_freshness_lab(
            key=key, worker=worker, recorded=now_dt,
        )
        if getter_freshness_failure:
            if self._strict_claim_fencing_lab:
                self._fence_assert_lab(key, worker, claim_generation_lab, "UNCERTAIN")
            with self._managed_write_transaction():
                self.db.execute(
                    """UPDATE action_outbox
                       SET state='UNCERTAIN',lease_owner='',lease_until='',last_error=?
                       WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                         AND state='UNCERTAIN'""",
                    (getter_freshness_failure, key, *self._scope_args()),
                )
            return {**self.get(key), "dispatch_state": "UNCERTAIN_RECONCILE_REQUIRED"}

        # G49: adapter.send property lookup can execute arbitrary in-process
        # code. A locally consistent CONFIRMED ledger can pass the G44 binder
        # even though the original UNCERTAIN attempt has been consumed.
        # Always recheck the original phase, claimant, lease and generation
        # immediately after the getter, even without optional G41 fencing or
        # a synthetic clock. Never invoke send for a superseded attempt.
        current_before_send = self.get(key)
        if self._strict_claim_fencing_lab:
            # Preserve G41's specific generation denial precedence.
            self._fence_assert_lab(key, worker, claim_generation_lab, "UNCERTAIN")
        if (current_before_send["state"] != "UNCERTAIN" or
                current_before_send["lease_owner"] != worker or
                current_before_send["lease_until"] != intent["lease_until"] or
                current_before_send["attempts"] != intent["attempts"]):
            raise RuntimeError("G49_GETTER_CHANGED_CLAIM_NO_SEND")
        self._g44_assert_binding_lab(key)
        if self._strict_claim_fencing_lab:
            self._fence_assert_lab(key, worker, claim_generation_lab, "UNCERTAIN")
        # G50 LAB: send() is untrusted and may reenter SQLite locally.
        # Record its exact pre-callback phase, lease and generation; a later
        # response cannot take ownership of a superseded attempt.
        g50_send_snapshot = self._g42_reconcile_snapshot_lab(current_before_send)

        def g50_reply_is_stale() -> bool:
            return self._g42_reconcile_snapshot_lab(self.get(key)) != g50_send_snapshot

        def g50_stale_result() -> dict[str, Any]:
            return {**self.get(key),
                    "dispatch_state": "G50_STALE_SEND_REPLY_NO_WRITE"}

        try:
            result = _mapping(_bound_callback(send, dict(intent["decision"]), key))
        except Exception as exc:
            if g50_reply_is_stale():
                if self._strict_claim_fencing_lab:
                    raise RuntimeError("FENCE_STALE_SEND_EXCEPTION_NO_WRITE")
                return g50_stale_result()
            with self._managed_write_transaction():
                cursor = self.db.execute(
                    """UPDATE action_outbox
                       SET state='UNCERTAIN',lease_owner='',lease_until=?,last_error=?
                       WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                         AND (?=1 OR (state='UNCERTAIN' AND lease_owner=? AND attempts=?))
                         AND state=? AND attempts=? AND lease_owner=?
                         AND lease_until=? AND effect_ref=?""",
                    (
                        "",
                        "SEND_RESULT_UNKNOWN:" + type(exc).__name__,
                        key, *self._scope_args(),
                        int(not self._strict_claim_fencing_lab), worker,
                        claim_generation_lab or 0, *g50_send_snapshot,
                    ),
                )
                if self._strict_claim_fencing_lab and cursor.rowcount != 1:
                    raise RuntimeError("FENCE_STALE_SEND_EXCEPTION_NO_WRITE")
            if cursor.rowcount != 1:
                return g50_stale_result()
            out = self.get(key)
            return {**out, "dispatch_state": "UNCERTAIN_RECONCILE_REQUIRED"}

        self._g44_assert_binding_lab(key)
        if self._strict_claim_fencing_lab:
            self._fence_assert_lab(key, worker, claim_generation_lab, "UNCERTAIN")
        if g50_reply_is_stale():
            return g50_stale_result()
        if result.get("accepted") is not True:
            # A possibly executed send is never authority for automatic retry.
            retry_claim = result.get("retryable") is True
            proved_zero = (not retry_claim and
                           self._verified_evidence("EFFECT_ZERO", intent, result))
            if g50_reply_is_stale():
                return g50_stale_result()
            state = "FAILED" if proved_zero else "UNCERTAIN"
            reason = ("ADAPTER_EFFECT_ZERO_VERIFIED_LAB" if proved_zero
                      else "ADAPTER_REJECTION_UNVERIFIED_OUTCOME_UNKNOWN")
            with self._managed_write_transaction():
                cursor = self.db.execute(
                    """UPDATE action_outbox
                       SET state=?,lease_owner='',lease_until='',last_error=?
                       WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                         AND (?=1 OR (state='UNCERTAIN' AND lease_owner=? AND attempts=?))
                         AND state=? AND attempts=? AND lease_owner=?
                         AND lease_until=? AND effect_ref=?""",
                    (state, reason, key, *self._scope_args(),
                     int(not self._strict_claim_fencing_lab), worker,
                     claim_generation_lab or 0, *g50_send_snapshot),
                )
                if self._strict_claim_fencing_lab and cursor.rowcount != 1:
                    raise RuntimeError("FENCE_STALE_SEND_REJECTION_NO_WRITE")
            if cursor.rowcount != 1:
                return g50_stale_result()
            dispatch_state = ("UNCERTAIN_RECONCILE_REQUIRED"
                              if state == "UNCERTAIN" else "FAILED")
            return {**self.get(key), "dispatch_state": dispatch_state}

        effect_ref = _clean(result.get("effect_ref"), 128)
        if result.get("confirmed") is True and effect_ref and self._verified_evidence(
            "EFFECT_CONFIRMED", intent, result
        ):
            if g50_reply_is_stale() and not self._strict_claim_fencing_lab:
                return g50_stale_result()
            try:
                out = self._confirm(
                    key,
                    effect_ref=effect_ref,
                    confirmed_at=now_dt,
                    result=result,
                    fence_lab=(worker, claim_generation_lab) if
                        self._strict_claim_fencing_lab else None,
                    reconcile_snapshot_lab=(
                        None if self._strict_claim_fencing_lab
                        else g50_send_snapshot
                    ),
                )
            except RuntimeError as exc:
                if str(exc) == "G42_RECONCILE_SNAPSHOT_STALE_NO_LEDGER":
                    return g50_stale_result()
                raise
            return {**out, "dispatch_state": "CONFIRMED"}

        if g50_reply_is_stale():
            return g50_stale_result()
        with self._managed_write_transaction():
            cursor = self.db.execute(
                """UPDATE action_outbox
                   SET state='SENT',sent_at=?,effect_ref=?,lease_owner='',lease_until='',last_error=''
                   WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                     AND (?=1 OR (state='UNCERTAIN' AND lease_owner=? AND attempts=?))
                     AND state=? AND attempts=? AND lease_owner=?
                     AND lease_until=? AND effect_ref=?""",
                (_iso(now_dt), effect_ref, key, *self._scope_args(),
                 int(not self._strict_claim_fencing_lab), worker,
                 claim_generation_lab or 0, *g50_send_snapshot),
            )
            if self._strict_claim_fencing_lab and cursor.rowcount != 1:
                raise RuntimeError("FENCE_STALE_SEND_RESULT_NO_WRITE")
        if cursor.rowcount != 1:
            return g50_stale_result()
        return {**self.get(key), "dispatch_state": "SENT_RECONCILE_REQUIRED"}

    @staticmethod
    def _g42_reconcile_snapshot_lab(intent: Mapping[str, Any]) -> tuple[str, int, str, str, str]:
        return (
            str(intent["state"]), int(intent["attempts"]),
            str(intent["lease_owner"]), str(intent["lease_until"]),
            str(intent["effect_ref"]),
        )

    def reconcile(
        self,
        idempotency_key: Any,
        *,
        adapter: Any,
        authorize: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        now: Any | None = None,
    ) -> dict[str, Any]:
        """Resolve SENT/UNCERTAIN without ever blind-resending an ambiguous effect."""
        key = _clean(idempotency_key, 64)
        now_dt = _utc(now)
        self._g44_assert_binding_lab(key)
        intent = self.get(key)
        if intent["state"] not in {"UNCERTAIN", "SENT"}:
            raise ValueError("only SENT or UNCERTAIN intents require reconciliation")
        # G52: a stale reconciliation reply must never override a newer
        # local row even when the historical strict opt-in is disabled.
        # This is still a local SQLite snapshot, NOT provider authority.
        snapshot_lab = self._g42_reconcile_snapshot_lab(intent)

        def no_stale_reply_lab() -> bool:
            return (snapshot_lab is None or
                    self._g42_reconcile_snapshot_lab(self.get(key)) == snapshot_lab)

        def stale_reply_lab() -> dict[str, Any]:
            return {**self.get(key), "reconcile_state": "G42_STALE_REPLY_NO_WRITE"}

        # Reconciliation adapters are caller-controlled Python objects too.
        # In default quarantine do not even inspect adapter.reconcile: its
        # property lookup may execute arbitrary host code. No confirmation.
        if not self._synthetic_lab_callbacks_enabled:
            return {**intent, "reconcile_state": "EXTERNAL_TRUST_NOT_CONFIGURED"}
        if self._strict_reconciliation_auth_lab and not self._reconciliation_authority_lab(
            intent, authorize,
        ):
            # Authorization callback may itself have changed the local phase.
            # Never return an obsolete pre-authorization snapshot as current.
            if not no_stale_reply_lab():
                return stale_reply_lab()
            return {**intent, "reconcile_state": "RECONCILE_AUTH_DENIED_NO_LOOKUP"}
        if not no_stale_reply_lab():
            return stale_reply_lab()
        self._g44_assert_binding_lab(key)
        reconcile = getattr(adapter, "reconcile", None)
        self._g44_assert_binding_lab(key)
        if not callable(reconcile):
            raise TypeError("adapter.reconcile required")
        if not no_stale_reply_lab():
            return stale_reply_lab()

        try:
            result = _mapping(_bound_callback(reconcile, key, dict(intent["decision"])))
        except Exception:
            # A changed binding or lost response has no retry authority.
            if not no_stale_reply_lab():
                return stale_reply_lab()
            return {**self.get(key), "reconcile_state": "STILL_UNCERTAIN"}
        if not no_stale_reply_lab():
            return stale_reply_lab()
        self._g44_assert_binding_lab(key)
        if result.get("found") is True and result.get("confirmed") is True:
            effect_ref = _clean(result.get("effect_ref"), 128)
            if effect_ref and self._verified_evidence(
                "EFFECT_CONFIRMED", intent, result
            ):
                try:
                    out = self._confirm(
                        key,
                        effect_ref=effect_ref,
                        confirmed_at=now_dt,
                        result=result,
                        reconcile_snapshot_lab=snapshot_lab,
                    )
                except RuntimeError as exc:
                    if str(exc) == "G42_RECONCILE_SNAPSHOT_STALE_NO_LEDGER":
                        return stale_reply_lab()
                    raise
                return {**out, "reconcile_state": "CONFIRMED"}
            # A self-asserted receipt or a disabled verifier is not evidence
            # of a trusted provider-side effect. Leave current state intact.
            if not no_stale_reply_lab():
                return stale_reply_lab()
            return {**intent, "reconcile_state": "STILL_UNCERTAIN"}

        # A caller-controlled dictionary with found=False and
        # authoritative_absence=True is NOT an independently authenticated
        # guarantee that the provider produced no effect. Do not turn
        # UNCERTAIN/SENT into RETRY here. A future witnessed absence protocol
        # requires a separate reviewed contract before any retry authority.
        if not no_stale_reply_lab():
            return stale_reply_lab()
        return {**intent, "reconcile_state": "STILL_UNCERTAIN"}

    def effect_count(self) -> int:
        return int(
            self.db.execute(
                """SELECT count(*) FROM action_effects
                   WHERE owner=? AND tenant=? AND workspace=?""",
                self._scope_args(),
            ).fetchone()[0]
        )


__all__ = [
    "SCHEMA",
    "MAX_AUTHORITY_TTL_SECONDS",
    "DEFAULT_LEASE_SECONDS",
    "STATES",
    "TERMINAL_STATES",
    "ExecutionOutbox",
]
