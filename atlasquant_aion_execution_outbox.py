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
        reauth = _clean(reauth_ref, 160)
        if requires_reauth and not reauth:
            raise ValueError("transaction reauthentication reference required")
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
        if semantic_event:
            if raw_payload.get("business_event_id") != semantic_event:
                raise ValueError("semantic event binding mismatch")
            if "business_event_id" not in redact(raw_payload):
                raise ValueError("semantic event must survive redaction")
        safe_payload = redact(raw_payload)
        payload_digest = _digest(safe_payload)
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
                """SELECT o.idempotency_key
                   FROM action_outbox o
                   JOIN action_decisions d ON d.decision_id=o.decision_id
                   WHERE o.owner=? AND o.tenant=? AND o.workspace=?
                     AND o.state IN ('PENDING','RETRY')
                     AND NOT EXISTS (
                         SELECT 1
                         FROM action_decisions earlier
                         JOIN action_outbox eo ON eo.decision_id=earlier.decision_id
                         WHERE earlier.owner=d.owner
                           AND earlier.tenant=d.tenant
                           AND earlier.workspace=d.workspace
                           AND earlier.aggregate_key=d.aggregate_key
                           AND earlier.aggregate_seq<d.aggregate_seq
                           AND eo.state NOT IN ('CONFIRMED','REVOKED','BLOCKED_REAPPROVAL','FAILED')
                     )
                   ORDER BY d.created_at,d.decision_id
                   LIMIT 1""",
                (owner, tenant, workspace),
            ).fetchone()
            if row is None:
                self._commit_or_quarantine()
                return None
            key = row["idempotency_key"]
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

    def _set_blocked(self, key: str, state: str, reason: str) -> dict[str, Any]:
        if state not in {"REVOKED", "BLOCKED_REAPPROVAL"}:
            raise ValueError("invalid blocked state")
        with self._managed_write_transaction():
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
    ) -> dict[str, Any]:
        effect = _token(effect_ref, "effect_ref", 128)
        encoded = _canonical(redact(dict(result or {})))
        self._begin_or_quarantine()
        try:
            existing = self.db.execute(
                """SELECT effect_ref FROM action_effects
                   WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?""",
                (key, *self._scope_args()),
            ).fetchone()
            if existing is not None and existing["effect_ref"] != effect:
                raise ValueError("effect ledger idempotency collision")
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
            self.db.execute(
                """UPDATE action_outbox
                   SET state='CONFIRMED',confirmed_at=?,effect_ref=?,
                       lease_owner='',lease_until='',last_error=''
                   WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?""",
                (_iso(confirmed_at), effect, key, *self._scope_args()),
            )
            self._commit_or_quarantine()
        except Exception as original_error:
            if self.db is not None:
                self._rollback_preserving_original(original_error)
            raise
        return self.get(key)

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

    def dispatch_claimed(
        self,
        idempotency_key: Any,
        *,
        worker_id: Any,
        authorize: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        adapter: Any,
        cumulative_authority_guard: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
        now: Any | None = None,
    ) -> dict[str, Any]:
        """Dispatch one claimed intent; uncertain outcomes require reconciliation."""
        key = _clean(idempotency_key, 64)
        worker = _token(worker_id, "worker_id")
        now_dt = _utc(now)
        intent = self.get(key)
        if intent["state"] != "CLAIMED":
            raise ValueError("intent must be CLAIMED before dispatch")
        if intent["lease_owner"] != worker:
            raise PermissionError("worker does not own claim")
        if not intent["lease_until"] or now_dt >= _utc(intent["lease_until"]):
            raise TimeoutError("claim lease expired before dispatch")

        allowed, blocked_state, auth = self._authorization_gate(intent, authorize, now_dt)
        if not allowed:
            return self._set_blocked(key, blocked_state, auth.get("reason", blocked_state))

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

        # A180: persist UNCERTAIN BEFORE contacting the witness. The witness
        # might reserve the first attempt and then time out: if the host dies
        # there, the original claim must NOT become an automatic RETRY.
        with self._managed_write_transaction():
            reserved = self.db.execute(
                """UPDATE action_outbox
                   SET state='UNCERTAIN',dispatch_started_at=?,
                       last_error='FIRST_ATTEMPT_WITNESS_PENDING'
                   WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                     AND state='CLAIMED' AND lease_owner=?""",
                (_iso(now_dt), key, *self._scope_args(), worker),
            )
            if reserved.rowcount != 1:
                raise RuntimeError("INFLIGHT_CLAIM_CHANGED_NO_SEND")

        # A first-attempt witness is a mandatory precondition for this
        # experimental Outbox. No callback, false, invalid signature, timeout
        # or lost response => DENY SEND, retain UNCERTAIN after restart.
        if not self._reserved_first_attempt(intent):
            with self._managed_write_transaction():
                self.db.execute(
                    """UPDATE action_outbox
                       SET state='UNCERTAIN',lease_owner='',lease_until='',
                           last_error='FIRST_ATTEMPT_WITNESS_UNVERIFIED_NO_SEND'
                       WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                         AND state='UNCERTAIN'""",
                    (key, *self._scope_args()),
                )
            return {**self.get(key),
                    "dispatch_state": "UNCERTAIN_PRE_DISPATCH_RESERVATION_REQUIRED"}

        # A possibly reserved first attempt can never be returned to RETRY
        # after a failed freshness check: preserve the UNCERTAIN reservation.
        freshness_failure = self._post_witness_freshness_lab(
            key=key, worker=worker, recorded=now_dt,
        )
        if freshness_failure:
            with self._managed_write_transaction():
                self.db.execute(
                    """UPDATE action_outbox
                       SET state='UNCERTAIN',lease_owner='',lease_until='',last_error=?
                       WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                         AND state='UNCERTAIN'""",
                    (freshness_failure, key, *self._scope_args()),
                )
            return {**self.get(key), "dispatch_state": "UNCERTAIN_RECONCILE_REQUIRED"}

        # No adapter attribute lookup (and therefore no user-defined property
        # getter) until the first-attempt witness passes. With G12 defaults
        # this line is unreachable regardless of caller-supplied callbacks.
        send = getattr(adapter, "send", None)
        if not callable(send):
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
            with self._managed_write_transaction():
                self.db.execute(
                    """UPDATE action_outbox
                       SET state='UNCERTAIN',lease_owner='',lease_until='',last_error=?
                       WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                         AND state='UNCERTAIN'""",
                    (getter_freshness_failure, key, *self._scope_args()),
                )
            return {**self.get(key), "dispatch_state": "UNCERTAIN_RECONCILE_REQUIRED"}

        try:
            result = _mapping(_bound_callback(send, dict(intent["decision"]), key))
        except Exception as exc:
            with self._managed_write_transaction():
                self.db.execute(
                    """UPDATE action_outbox
                       SET state='UNCERTAIN',lease_owner='',lease_until=?,last_error=?
                       WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?""",
                    (
                        "",
                        "SEND_RESULT_UNKNOWN:" + type(exc).__name__,
                        key,
                        *self._scope_args(),
                    ),
                )
            out = self.get(key)
            return {**out, "dispatch_state": "UNCERTAIN_RECONCILE_REQUIRED"}

        if result.get("accepted") is not True:
            # The external boundary was already crossed. A bare adapter flag
            # retryable=True cannot prove that no effect was committed.
            # Never convert a possibly executed send into an automatic retry.
            retry_claim = result.get("retryable") is True
            # A definitive rejection is also untrusted after send(): the
            # adapter may have produced the effect before returning False.
            # EFFECT_ZERO verification is never a permission to auto-retry.
            proved_zero = (not retry_claim and
                           self._verified_evidence("EFFECT_ZERO", intent, result))
            state = "FAILED" if proved_zero else "UNCERTAIN"
            reason = ("ADAPTER_EFFECT_ZERO_VERIFIED_LAB" if proved_zero
                      else "ADAPTER_REJECTION_UNVERIFIED_OUTCOME_UNKNOWN")
            with self._managed_write_transaction():
                self.db.execute(
                    """UPDATE action_outbox
                       SET state=?,lease_owner='',lease_until='',last_error=?
                       WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?""",
                    (state, reason, key, *self._scope_args()),
                )
            dispatch_state = ("UNCERTAIN_RECONCILE_REQUIRED"
                              if state == "UNCERTAIN" else "FAILED")
            return {**self.get(key), "dispatch_state": dispatch_state}

        effect_ref = _clean(result.get("effect_ref"), 128)
        if result.get("confirmed") is True and effect_ref and self._verified_evidence(
            "EFFECT_CONFIRMED", intent, result
        ):
            out = self._confirm(
                key,
                effect_ref=effect_ref,
                confirmed_at=now_dt,
                result=result,
            )
            return {**out, "dispatch_state": "CONFIRMED"}

        with self._managed_write_transaction():
            self.db.execute(
                """UPDATE action_outbox
                   SET state='SENT',sent_at=?,effect_ref=?,lease_owner='',lease_until='',last_error=''
                   WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?""",
                (_iso(now_dt), effect_ref, key, *self._scope_args()),
            )
        return {**self.get(key), "dispatch_state": "SENT_RECONCILE_REQUIRED"}

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
        intent = self.get(key)
        if intent["state"] not in {"UNCERTAIN", "SENT"}:
            raise ValueError("only SENT or UNCERTAIN intents require reconciliation")
        # Reconciliation adapters are caller-controlled Python objects too.
        # In default quarantine do not even inspect adapter.reconcile: its
        # property lookup may execute arbitrary host code. No confirmation.
        if not self._synthetic_lab_callbacks_enabled:
            return {**intent, "reconcile_state": "EXTERNAL_TRUST_NOT_CONFIGURED"}
        if self._strict_reconciliation_auth_lab and not self._reconciliation_authority_lab(
            intent, authorize,
        ):
            return {**intent, "reconcile_state": "RECONCILE_AUTH_DENIED_NO_LOOKUP"}
        reconcile = getattr(adapter, "reconcile", None)
        if not callable(reconcile):
            raise TypeError("adapter.reconcile required")

        try:
            result = _mapping(_bound_callback(reconcile, key, dict(intent["decision"])))
        except Exception:
            # A changed binding or a lost reconciliation response cannot
            # confirm an effect, nor grant a resend or retry permission.
            return {**self.get(key), "reconcile_state": "STILL_UNCERTAIN"}
        if result.get("found") is True and result.get("confirmed") is True:
            effect_ref = _clean(result.get("effect_ref"), 128)
            if effect_ref and self._verified_evidence(
                "EFFECT_CONFIRMED", intent, result
            ):
                out = self._confirm(
                    key,
                    effect_ref=effect_ref,
                    confirmed_at=now_dt,
                    result=result,
                )
                return {**out, "reconcile_state": "CONFIRMED"}
            # A self-asserted receipt or a disabled verifier is not evidence
            # of a trusted provider-side effect. Leave current state intact.
            return {**intent, "reconcile_state": "STILL_UNCERTAIN"}

        # A caller-controlled dictionary with found=False and
        # authoritative_absence=True is NOT an independently authenticated
        # guarantee that the provider produced no effect. Do not turn
        # UNCERTAIN/SENT into RETRY here. A future witnessed absence protocol
        # requires a separate reviewed contract before any retry authority.
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
