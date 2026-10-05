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
from aion_chat.privacy import redact
from aion_chat.store import SQLiteChatStore

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

        safe_payload = redact(dict(payload or {}))
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

        self.db.execute("BEGIN IMMEDIATE")
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
                self.db.commit()
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
            self.db.commit()
        except Exception:
            self.db.rollback()
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
        with self.db:
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
        self.db.execute("BEGIN IMMEDIATE")
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
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.get(key)

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
                budget = _mapping(cumulative_authority_guard(dict(decision)))
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

        send = getattr(adapter, "send", None)
        if not callable(send):
            raise TypeError("adapter.send required")

        # Persist ambiguity BEFORE crossing the external boundary. If the process
        # dies after this commit, restart must reconcile and must not blind-retry.
        with self.db:
            self.db.execute(
                """UPDATE action_outbox
                   SET state='UNCERTAIN',dispatch_started_at=?,last_error='DISPATCH_IN_PROGRESS'
                   WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?
                     AND state='CLAIMED' AND lease_owner=?""",
                (_iso(now_dt), key, *self._scope_args(), worker),
            )

        try:
            result = _mapping(send(dict(intent["decision"]), key))
        except Exception as exc:
            with self.db:
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
            state = "RETRY" if result.get("retryable") is True else "FAILED"
            with self.db:
                self.db.execute(
                    """UPDATE action_outbox
                       SET state=?,lease_owner='',lease_until='',last_error=?
                       WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?""",
                    (
                        state,
                        _clean(result.get("reason") or "ADAPTER_REJECTED", 240),
                        key,
                        *self._scope_args(),
                    ),
                )
            return {**self.get(key), "dispatch_state": state}

        effect_ref = _clean(result.get("effect_ref"), 128)
        if result.get("confirmed") is True:
            if not effect_ref:
                raise ValueError("confirmed adapter result requires effect_ref")
            out = self._confirm(
                key,
                effect_ref=effect_ref,
                confirmed_at=now_dt,
                result=result,
            )
            return {**out, "dispatch_state": "CONFIRMED"}

        with self.db:
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
        reconcile = getattr(adapter, "reconcile", None)
        if not callable(reconcile):
            raise TypeError("adapter.reconcile required")

        result = _mapping(reconcile(key, dict(intent["decision"])))
        if result.get("found") is True and result.get("confirmed") is True:
            effect_ref = _clean(result.get("effect_ref"), 128)
            if not effect_ref:
                raise ValueError("confirmed reconciliation requires effect_ref")
            out = self._confirm(
                key,
                effect_ref=effect_ref,
                confirmed_at=now_dt,
                result=result,
            )
            return {**out, "reconcile_state": "CONFIRMED"}

        if result.get("found") is False and result.get("authoritative_absence") is True:
            allowed, blocked_state, auth = self._authorization_gate(intent, authorize, now_dt)
            if not allowed:
                out = self._set_blocked(
                    key,
                    blocked_state,
                    auth.get("reason", blocked_state),
                )
                return {**out, "reconcile_state": blocked_state}
            with self.db:
                self.db.execute(
                    """UPDATE action_outbox
                       SET state='RETRY',lease_owner='',lease_until='',
                           last_error='AUTHORITATIVE_ABSENCE_CONFIRMED'
                       WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?""",
                    (key, *self._scope_args()),
                )
            return {**self.get(key), "reconcile_state": "RETRY"}

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
