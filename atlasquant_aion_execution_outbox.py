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

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from typing import Any, Callable, Mapping

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_action_payload_gate import clean_action_payload

SCHEMA = "ATLASQUANT_AION_EXECUTION_OUTBOX_V1"
MAX_AUTHORITY_TTL_SECONDS = 900
DEFAULT_LEASE_SECONDS = 30
MAX_LEASE_SECONDS = 300
STATES = frozenset({
    "PENDING",
    "RETRY",
    "CLAIMED",
    "BLOCKED_PRODUCER",
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


class ExecutionOutbox:
    """Scoped outbox bound to the same SQLite database as staged chat state."""

    def __init__(self, store: SQLiteChatStore, scope: Scope):
        if not isinstance(store, SQLiteChatStore):
            raise TypeError("SQLiteChatStore required")
        store.require_healthy()
        _scope(scope)
        self.store = store
        self.scope = scope
        self.db = store.db
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self.db:
            self.db.executescript("""
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
            """)

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

        # A89: typed JSON boundary + A88 no-redaction contract shared with Saga.
        # Never persist lossy stringifications or undetected tuple-borne secrets.
        safe_payload = clean_action_payload(payload)
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
        idempotency_key = _digest(key_material)
        decision_id = "DEC-" + idempotency_key[:24].upper()

        # A61: standalone enqueue still owns an IMMEDIATE transaction.
        # If Saga already owns that same SQLite connection's transaction,
        # use a SAVEPOINT: releasing it does NOT commit the outer Saga.
        # This cannot authorize an external effect or bypass producer gates.
        owns_transaction = not self.db.in_transaction
        if owns_transaction:
            self.db.execute("BEGIN IMMEDIATE")
        else:
            self.db.execute("SAVEPOINT aion_outbox_enqueue")
        try:
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
                if owns_transaction:
                    self.db.commit()
                else:
                    self.db.execute("RELEASE SAVEPOINT aion_outbox_enqueue")
                out = self.get(idempotency_key)
                return {**out, "enqueue_state": "IDEMPOTENT"}

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
            if owns_transaction:
                self.db.commit()
            else:
                self.db.execute("RELEASE SAVEPOINT aion_outbox_enqueue")
        except Exception:
            if owns_transaction:
                self.db.rollback()
            else:
                self.db.execute("ROLLBACK TO SAVEPOINT aion_outbox_enqueue")
                self.db.execute("RELEASE SAVEPOINT aion_outbox_enqueue")
            raise
        out = self.get(idempotency_key)
        return {**out, "enqueue_state": "ENQUEUED"}

    def release_expired_claims(self, *, now: Any | None = None) -> int:
        current = _iso(_utc(now))
        self.db.execute("BEGIN IMMEDIATE")
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
            self.db.commit()
            return count
        except Exception:
            self.db.rollback()
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
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute(
                """SELECT o.idempotency_key
                   FROM action_outbox o
                   JOIN action_decisions d ON d.decision_id=o.decision_id
                   WHERE o.owner=? AND o.tenant=? AND o.workspace=?
                     AND o.state IN ('PENDING','RETRY')
                     -- A.45: while no independently verifiable producer
                     -- admission exists, ONLY the first ordinal of each
                     -- scoped aggregate may be claimed. A previous Outbox row
                     -- (or even its local decision) can be deleted/rolled back;
                     -- a JOIN over surviving predecessor rows must never
                     -- make an ordinal 2+ look like the first action.
                     -- This is local fail-closed FIFO, not a witness against
                     -- rewriting the ordinal or rolling back the whole DB.
                     AND d.aggregate_seq=1
                   ORDER BY d.created_at,d.decision_id
                   LIMIT 1""",
                (owner, tenant, workspace),
            ).fetchone()
            if row is None:
                self.db.commit()
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
                self.db.rollback()
                return None
            self.db.commit()
            return self.get(key)
        except Exception:
            self.db.rollback()
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
            current = _mapping(authorize(dict(decision)))
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
            # An absent/blank scope is not a valid authorization assertion.
            if not supplied:
                return False, "REVOKED", {"reason": field.upper() + "_MISSING"}
            if supplied != wanted:
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
        self, key: str, state: str, reason: str, *, expected: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Block only the same observed state and lease, never a later effect."""
        if state not in {"REVOKED", "BLOCKED_REAPPROVAL"}:
            raise ValueError("invalid blocked state")
        if _clean(expected.get("idempotency_key"), 64) != key:
            raise ValueError("expected intent key mismatch")
        seen_state = _clean(expected.get("state"), 32)
        if seen_state not in {"CLAIMED", "UNCERTAIN", "SENT"}:
            raise ValueError("expected state cannot be blocked")
        with self.db:
            changed = self.db.execute(
                """UPDATE action_outbox
                   SET state=?,lease_owner='',lease_until='',last_error=?
                   WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                     AND state=? AND lease_owner=? AND lease_until=?""",
                (
                    state, _clean(reason, 240), key, *self._scope_args(),
                    seen_state, _clean(expected.get("lease_owner"), 128),
                    _clean(expected.get("lease_until"), 128),
                ),
            )
            if changed.rowcount != 1:
                raise RuntimeError("stale outbox state/lease; blocked mutation rejected")
        return self.get(key)

    def _confirm(
        self,
        key: str,
        *,
        expected: Mapping[str, Any],
        effect_ref: Any,
        confirmed_at: datetime,
        result: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """No trusted producer receipt verifier is enrolled in staging.

        A private Python method cannot confer external effect authority. This
        formerly committed adapter-supplied booleans as confirmed effects.
        Keep denial unconditional until a separately reviewed receipt admission
        boundary with independently pinned provenance, freshness and readback.
        """
        raise PermissionError("INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED")

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
        # A callable clock supports deterministic staging tests. A real host must
        # supply trusted time/lease fencing; caller-supplied values are NOT proof.
        def read_clock() -> datetime:
            return _utc(now() if callable(now) else now)

        now_dt = read_clock()
        intent = self.get(key)
        if intent["state"] != "CLAIMED":
            raise ValueError("intent must be CLAIMED before dispatch")
        if intent["lease_owner"] != worker:
            raise PermissionError("worker does not own claim")
        if not intent["lease_until"] or now_dt >= _utc(intent["lease_until"]):
            raise TimeoutError("claim lease expired before dispatch")

        def block_current(block_key: str, state: str, reason: str) -> dict[str, Any]:
            if block_key != key:
                raise ValueError("stale block key mismatch")
            return self._set_blocked(key, state, reason, expected=intent)

        allowed, blocked_state, auth = self._authorization_gate(intent, authorize, now_dt)
        if not allowed:
            return block_current(key, blocked_state, auth.get("reason", blocked_state))

        decision = _mapping(intent.get("decision"))
        budget_ref = _clean(decision.get("authority_budget_ref"), 128)
        if budget_ref:
            if not callable(cumulative_authority_guard):
                return block_current(
                    key,
                    "BLOCKED_REAPPROVAL",
                    "CUMULATIVE_AUTHORITY_GUARD_REQUIRED",
                )
            try:
                budget = _mapping(cumulative_authority_guard(dict(decision)))
            except Exception:
                return block_current(
                    key,
                    "BLOCKED_REAPPROVAL",
                    "CUMULATIVE_AUTHORITY_GUARD_FAILED",
                )
            if budget.get("allowed") is not True:
                return block_current(
                    key,
                    "BLOCKED_REAPPROVAL",
                    _clean(budget.get("reason") or "CUMULATIVE_AUTHORITY_BUDGET_EXCEEDED", 240),
                )
            if _clean(budget.get("authority_budget_ref"), 128) != budget_ref:
                return block_current(
                    key,
                    "BLOCKED_REAPPROVAL",
                    "CUMULATIVE_AUTHORITY_BUDGET_REF_MISMATCH",
                )
            if _clean(budget.get("transaction_id"), 128) != _clean(decision.get("transaction_id"), 128):
                return block_current(
                    key,
                    "BLOCKED_REAPPROVAL",
                    "CUMULATIVE_AUTHORITY_TRANSACTION_MISMATCH",
                )

        # V16-A.30 local-only preflight: preserve both authorization and
        # time-of-use checks even when productive enrollment is unavailable.
        # These checks are necessary but NEVER sufficient to enable a sender.
        # No adapter attribute is read and there are no external effects.
        # Callbacks can block or revoke authorization after the first check.
        # Recheck after those callbacks, then read time AGAIN after revalidation.
        pre_send_dt = read_clock()
        if pre_send_dt >= _utc(intent["lease_until"]):
            raise TimeoutError("claim lease expired during authorization callbacks")
        allowed, blocked_state, auth = self._authorization_gate(
            intent, authorize, pre_send_dt,
        )
        if not allowed:
            return block_current(key, blocked_state, auth.get("reason", blocked_state))
        fenced_at = read_clock()
        if fenced_at >= _utc(intent["lease_until"]):
            raise TimeoutError("claim lease expired before send")
        if fenced_at >= _utc(decision.get("valid_until")):
            return block_current(key, "BLOCKED_REAPPROVAL", "AUTHORITY_EXPIRED")

        # In this NO-PRODUCER state use a READ-ONLY guard equivalent to
        # the CAS admission predicates. It catches revoked claims, moved
        # leases and changed persisted deadlines, without writing UNCERTAIN.
        # It does not authorize or replace the later transactional CAS.
        available = self.db.execute(
            """SELECT 1 FROM action_outbox
               WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                 AND state='CLAIMED' AND lease_owner=?
                 AND lease_until=? AND lease_until>?
                 AND EXISTS (
                     SELECT 1 FROM action_decisions d
                     WHERE d.decision_id=action_outbox.decision_id
                       AND d.valid_until>?
                 )""",
            (
                key, *self._scope_args(), worker,
                intent["lease_until"], _iso(fenced_at), _iso(fenced_at),
            ),
        ).fetchone()
        if available is None:
            raise TimeoutError("claim/deadline changed before send; dispatch blocked")

        # V16-A.27: no independently enrolled producer, issuer, bound account
        # or monotonic witness is present in this staging implementation.
        # This is a mandatory pre-adapter hard stop, NOT a self-attested
        # adapter capability, user-controlled flag or fixture signature.
        # Even inspecting adapter.send may execute untrusted descriptor code.
        # Without a separately reviewed, externally rooted enrollment verifier
        # it is unsafe to CROSS the effect boundary merely because local
        # policy, clock, owner or lease checks passed.
        # The no-producer denial must survive process restarts and lease
        # expiry; otherwise each expired CLAIMED lease returns to RETRY and
        # attempts increase forever without any possible legitimate send.
        # BLOCKED_PRODUCER is NON-TERMINAL: it keeps following actions of the
        # same aggregate in PENDING, never releases FIFO or claims.
        # Only the exact observed worker/lease/decision can persist this deny.
        with self.db:
            blocked = self.db.execute(
                """UPDATE action_outbox
                   SET state='BLOCKED_PRODUCER',lease_owner='',lease_until='',
                       last_error='INDEPENDENT_PRODUCER_NOT_ENROLLED'
                   WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                     AND state='CLAIMED' AND lease_owner=? AND lease_until=?
                     AND lease_until>?
                     AND NOT EXISTS (
                         SELECT 1 FROM action_effects e
                         WHERE e.idempotency_key=action_outbox.idempotency_key
                           AND e.owner=action_outbox.owner
                           AND e.tenant=action_outbox.tenant
                           AND e.workspace=action_outbox.workspace
                     )
                     AND EXISTS (
                         SELECT 1 FROM action_decisions d
                         WHERE d.decision_id=action_outbox.decision_id
                           AND d.valid_until>?
                     )""",
                (
                    key, *self._scope_args(), worker,
                    intent["lease_until"], _iso(fenced_at), _iso(fenced_at),
                ),
            )
            if blocked.rowcount != 1:
                raise RuntimeError(
                    "stale producer enrollment denial; no state overwritten"
                )
        raise PermissionError("INDEPENDENT_PRODUCER_NOT_ENROLLED")

        # Do not remove the legacy adapter path below until its replacement
        # is reviewed. It is intentionally unreachable while enrollment is
        # absent; NO code after this gate constitutes a working producer verifier.
        send = getattr(adapter, "send", None)
        if not callable(send):
            raise TypeError("adapter.send required")

        # Keep the persisted UNCERTAIN transition atomic with a compare-and-swap
        # on claim owner, its exact lease and both persisted deadlines. No send
        # occurs if another writer or expiry invalidates the pre-send claim.
        # This local fence does NOT prevent late effects on an external provider.
        with self.db:
            cursor = self.db.execute(
                """UPDATE action_outbox
                   SET state='UNCERTAIN',dispatch_started_at=?,last_error='DISPATCH_IN_PROGRESS'
                   WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                     AND state='CLAIMED' AND lease_owner=?
                     AND lease_until=? AND lease_until>?
                     AND EXISTS (
                         SELECT 1 FROM action_decisions d
                         WHERE d.decision_id=action_outbox.decision_id
                           AND d.valid_until>?
                     )""",
                (
                    _iso(fenced_at), key, *self._scope_args(), worker,
                    intent["lease_until"], _iso(fenced_at), _iso(fenced_at),
                ),
            )
            if cursor.rowcount != 1:
                raise TimeoutError("claim/deadline changed before send; dispatch blocked")

        # Snapshot exactly the state admitted to the external boundary. A later
        # adapter response cannot rewrite a newer reconciliation or revocation.
        sent_snapshot = self.get(key)
        try:
            result = _mapping(send(dict(intent["decision"]), key))
        except Exception as exc:
            with self.db:
                changed = self.db.execute(
                    """UPDATE action_outbox
                       SET state='UNCERTAIN',lease_owner='',lease_until='',last_error=?
                       WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                         AND state='UNCERTAIN' AND lease_owner=? AND lease_until=?""",
                    (
                        "SEND_RESULT_UNKNOWN:" + type(exc).__name__,
                        key, *self._scope_args(),
                        sent_snapshot["lease_owner"], sent_snapshot["lease_until"],
                    ),
                )
                if changed.rowcount != 1:
                    raise RuntimeError("stale send error; state preserved") from exc
            out = self.get(key)
            return {**out, "dispatch_state": "UNCERTAIN_RECONCILE_REQUIRED"}

        if result.get("accepted") is not True or result.get("confirmed") is True:
            # Both negative and positive callback claims are untrusted. A
            # positive bool and effect_ref cannot create a confirmed effect
            # without an independently authenticated producer receipt.
            # Keep the entire aggregate blocked until real evidence exists.
            unverified_reason = (
                "ADAPTER_REJECTION_EFFECT_UNVERIFIED"
                if result.get("accepted") is not True
                else "ADAPTER_POSITIVE_EFFECT_UNVERIFIED"
            )
            with self.db:
                changed = self.db.execute(
                    """UPDATE action_outbox
                       SET state='UNCERTAIN',lease_owner='',lease_until='',
                           last_error=?
                       WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                         AND state='UNCERTAIN' AND lease_owner=? AND lease_until=?
                         AND NOT EXISTS (
                             SELECT 1 FROM action_effects e
                             WHERE e.idempotency_key=action_outbox.idempotency_key
                               AND e.owner=action_outbox.owner
                               AND e.tenant=action_outbox.tenant
                               AND e.workspace=action_outbox.workspace
                         )""",
                    (
                        unverified_reason, key, *self._scope_args(),
                        sent_snapshot["lease_owner"], sent_snapshot["lease_until"],
                    ),
                )
                if changed.rowcount != 1:
                    raise RuntimeError("stale unverified adapter claim; state preserved")
            return {**self.get(key), "dispatch_state": "UNCERTAIN_PROOF_REQUIRED"}

        effect_ref = _clean(result.get("effect_ref"), 128)

        with self.db:
            changed = self.db.execute(
                """UPDATE action_outbox
                   SET state='SENT',sent_at=?,effect_ref=?,lease_owner='',lease_until='',last_error=''
                   WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                     AND state='UNCERTAIN' AND lease_owner=? AND lease_until=?
                     AND NOT EXISTS (
                         SELECT 1 FROM action_effects e
                         WHERE e.idempotency_key=action_outbox.idempotency_key
                           AND e.owner=action_outbox.owner
                           AND e.tenant=action_outbox.tenant
                           AND e.workspace=action_outbox.workspace
                     )""",
                (
                    _iso(now_dt), effect_ref, key, *self._scope_args(),
                    sent_snapshot["lease_owner"], sent_snapshot["lease_until"],
                ),
            )
            if changed.rowcount != 1:
                raise RuntimeError("stale send result; SENT denied")
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
        # V16-A.33: unlike a trusted read-only local database lookup, an
        # injected adapter.reconcile property/callback is arbitrary executable
        # code. In this staging version no independent producer enrollment,
        # issuer root, account binding or monotonic witness is available.
        # Thus deny BEFORE even evaluating the potentially effectful property.
        # No current state or effect ledger mutation occurs. Historical
        # SENT/UNCERTAIN remains in doubt pending independently authenticated
        # receipts; no blind resend, release, or compensation is permitted.
        raise PermissionError("INDEPENDENT_PRODUCER_NOT_ENROLLED")

        # Unreachable legacy path, NOT a productive readback authorization.
        # Its enabling requires separately reviewed external enrollment gates.
        reconcile = getattr(adapter, "reconcile", None)
        if not callable(reconcile):
            raise TypeError("adapter.reconcile required")

        result = _mapping(reconcile(key, dict(intent["decision"])))
        if result.get("found") is True and result.get("confirmed") is True:
            # The adapter is not the external producer or a trust witness.
            # Do not promote SENT/UNCERTAIN or insert a local effects receipt.
            current = self.get(key)
            if (
                current["state"] != intent["state"]
                or current["lease_owner"] != intent["lease_owner"]
                or current["lease_until"] != intent["lease_until"]
                or current["effect_ref"] != intent["effect_ref"]
            ):
                return {**current, "reconcile_state": "STALE_OBSERVATION_IGNORED"}
            return {**current, "reconcile_state": "INDEPENDENT_POSITIVE_PROOF_REQUIRED"}

        if result.get("found") is False and result.get("authoritative_absence") is True:
            # Never accept "authoritative_absence" merely because an injected
            # adapter says so. A positive *independent* causal no-effect receipt,
            # with a producer-enforced late-effect fence, has no admission path
            # in this staging module yet; keeping UNCERTAIN/SENT is intentional.
            current = self.get(key)
            if (
                current["state"] != intent["state"]
                or current["lease_owner"] != intent["lease_owner"]
                or current["lease_until"] != intent["lease_until"]
                or current["effect_ref"] != intent["effect_ref"]
            ):
                return {**current, "reconcile_state": "STALE_OBSERVATION_IGNORED"}
            return {**current, "reconcile_state": "INDEPENDENT_ABSENCE_PROOF_REQUIRED"}

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
