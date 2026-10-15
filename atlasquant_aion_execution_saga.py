"""Durable staged multi-tool saga coordinator for AION.

Coordinates multiple staged outbox intents without enabling any provider.
Confirmed partial effects are tracked durably. Failed transactions may prepare
compensation only for explicitly reversible steps; uncertainty blocks
compensation until reconciliation. Irreversible confirmed effects always
escalate to manual intervention.

Compensation is never automatic: it requires a fresh explicit approval and
transaction reauthentication, and it passes through the same cumulative
authority budget as forward effects.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_action_payload_gate import clean_action_payload
from atlasquant_aion_cumulative_authority_budget import (
    CAPABILITY_CLASSES,
    CumulativeAuthorityBudget,
)
from atlasquant_aion_execution_outbox import ExecutionOutbox
from atlasquant_aion_saga_sequence_policy import select_forward_step, select_compensation_step

SCHEMA = "ATLASQUANT_AION_EXECUTION_SAGA_V1"
MAX_STEPS = 12
SAGA_STATES = (
    "PLANNED",
    "RUNNING",
    "RECONCILIATION_REQUIRED",
    "PRODUCER_ENROLLMENT_REQUIRED",
    "FAILED",
    "COMPENSATION_REQUIRED",
    "COMPENSATING",
    "COMPLETED",
    "COMPENSATED",
    "MANUAL_INTERVENTION_REQUIRED",
)
STEP_STATES = (
    "PENDING",
    "ENQUEUED",
    "BLOCKED_PRODUCER",
    "CONFIRMED",
    "RETRY",
    "UNCERTAIN",
    "FAILED",
    "REVOKED",
    "BLOCKED_REAPPROVAL",
    "COMPENSATION_PENDING",
    "COMPENSATION_ENQUEUED",
    "COMPENSATED",
    "COMPENSATION_FAILED",
    "MANUAL_REQUIRED",
)
_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
GENESIS_HASH = "0" * 64


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _token(value: Any, name: str) -> str:
    text = _clean(value, 128)
    if not _SAFE_TOKEN.fullmatch(text):
        raise ValueError(f"invalid {name}")
    return text


def _utc(value: Any | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        out = value
    else:
        out = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if out.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return out.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _scope(scope: Scope) -> tuple[str, str, str]:
    if not isinstance(scope, Scope):
        raise TypeError("trusted Scope required")
    return scope.owner_id, scope.tenant_id, scope.workspace_id


class ExecutionSagaCoordinator:
    def __init__(
        self,
        store: SQLiteChatStore,
        scope: Scope,
        *,
        outbox: ExecutionOutbox,
        authority_budget: CumulativeAuthorityBudget,
    ):
        if not isinstance(store, SQLiteChatStore):
            raise TypeError("SQLiteChatStore required")
        if not isinstance(outbox, ExecutionOutbox):
            raise TypeError("ExecutionOutbox required")
        if not isinstance(authority_budget, CumulativeAuthorityBudget):
            raise TypeError("CumulativeAuthorityBudget required")
        store.require_healthy()
        if outbox.store is not store or authority_budget.store is not store:
            raise ValueError("saga components must share the same durable store handle")
        if _scope(scope) != _scope(outbox.scope) or _scope(scope) != _scope(authority_budget.scope):
            raise ValueError("saga component scope mismatch")
        self.store = store
        self.db = store.db
        self.scope = scope
        self.outbox = outbox
        self.authority_budget = authority_budget
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self.db:
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS aion_execution_sagas(
                saga_id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                tenant TEXT NOT NULL,
                workspace TEXT NOT NULL,
                state TEXT NOT NULL,
                authority_budget_ref TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                plan_digest TEXT NOT NULL,
                compensation_approval_ref TEXT NOT NULL DEFAULT '',
                compensation_reauth_ref TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS aion_execution_sagas_scope
              ON aion_execution_sagas(owner,tenant,workspace,created_at,saga_id);

            CREATE TABLE IF NOT EXISTS aion_execution_saga_steps(
                saga_id TEXT NOT NULL REFERENCES aion_execution_sagas(saga_id),
                ordinal INTEGER NOT NULL,
                step_key TEXT NOT NULL,
                action TEXT NOT NULL,
                payload TEXT NOT NULL,
                capability_class TEXT NOT NULL,
                risk_points INTEGER NOT NULL,
                reversible INTEGER NOT NULL,
                compensation_action TEXT NOT NULL,
                compensation_payload TEXT NOT NULL,
                compensation_risk_points INTEGER NOT NULL,
                state TEXT NOT NULL,
                outbox_key TEXT NOT NULL DEFAULT '',
                effect_ref TEXT NOT NULL DEFAULT '',
                compensation_outbox_key TEXT NOT NULL DEFAULT '',
                compensation_effect_ref TEXT NOT NULL DEFAULT '',
                last_error TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(saga_id,step_key),
                UNIQUE(saga_id,ordinal)
            );
            CREATE INDEX IF NOT EXISTS aion_execution_saga_step_state
              ON aion_execution_saga_steps(saga_id,state,ordinal);

            CREATE TABLE IF NOT EXISTS aion_execution_saga_events(
                saga_id TEXT NOT NULL REFERENCES aion_execution_sagas(saga_id),
                sequence INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                step_key TEXT NOT NULL,
                state TEXT NOT NULL,
                detail_digest TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(saga_id,sequence)
            );
            """)

    def _scope_args(self) -> tuple[str, str, str]:
        return _scope(self.scope)

    def _saga_row(self, saga_id: str):
        return self.db.execute(
            """SELECT * FROM aion_execution_sagas
               WHERE saga_id=? AND owner=? AND tenant=? AND workspace=?""",
            (saga_id, *self._scope_args()),
        ).fetchone()

    def _step_rows(self, saga_id: str):
        return self.db.execute(
            """SELECT * FROM aion_execution_saga_steps
               WHERE saga_id=? ORDER BY ordinal""",
            (saga_id,),
        ).fetchall()

    @staticmethod
    def _step_view(row) -> dict[str, Any]:
        return {
            "ordinal": int(row["ordinal"]),
            "step_key": row["step_key"],
            "action": row["action"],
            "payload": json.loads(row["payload"]),
            "capability_class": row["capability_class"],
            "risk_points": int(row["risk_points"]),
            "reversible": bool(row["reversible"]),
            "compensation_action": row["compensation_action"],
            "compensation_payload": json.loads(row["compensation_payload"]),
            "compensation_risk_points": int(row["compensation_risk_points"]),
            "state": row["state"],
            "outbox_key": row["outbox_key"],
            "effect_ref": row["effect_ref"],
            "compensation_outbox_key": row["compensation_outbox_key"],
            "compensation_effect_ref": row["compensation_effect_ref"],
            "last_error": row["last_error"],
        }

    def get(self, saga_id: Any) -> dict[str, Any]:
        sid = _token(saga_id, "saga_id")
        row = self._saga_row(sid)
        if row is None:
            raise LookupError("saga unavailable")
        steps = [self._step_view(x) for x in self._step_rows(sid)]
        return {
            "schema": SCHEMA,
            "saga_id": sid,
            "owner_id": row["owner"],
            "tenant_id": row["tenant"],
            "workspace_id": row["workspace"],
            "state": row["state"],
            "authority_budget_ref": row["authority_budget_ref"],
            "policy_version": row["policy_version"],
            "plan_digest": row["plan_digest"],
            "compensation_approval_ref": row["compensation_approval_ref"],
            "compensation_reauth_ref": row["compensation_reauth_ref"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "steps": steps,
            "automatic_compensation": False,
            "grants_authority": False,
            "executes_action": False,
        }

    def _append_event(
        self,
        saga_id: str,
        *,
        event_type: str,
        state: str,
        step_key: str = "",
        detail: Mapping[str, Any] | None = None,
        created_at: Any | None = None,
    ) -> None:
        previous = self.db.execute(
            """SELECT sequence,event_hash FROM aion_execution_saga_events
               WHERE saga_id=? ORDER BY sequence DESC LIMIT 1""",
            (saga_id,),
        ).fetchone()
        sequence = 1 if previous is None else int(previous["sequence"]) + 1
        previous_hash = GENESIS_HASH if previous is None else previous["event_hash"]
        detail_digest = _digest(dict(detail or {}))
        event = {
            "saga_id": saga_id,
            "sequence": sequence,
            "event_type": _clean(event_type, 80).upper(),
            "step_key": _clean(step_key, 128),
            "state": _clean(state, 80).upper(),
            "detail_digest": detail_digest,
            "previous_hash": previous_hash,
            "created_at": _iso(_utc(created_at)),
        }
        event_hash = _digest(event)
        self.db.execute(
            """INSERT INTO aion_execution_saga_events(
                saga_id,sequence,event_type,step_key,state,detail_digest,
                previous_hash,event_hash,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                saga_id,
                sequence,
                event["event_type"],
                event["step_key"],
                event["state"],
                detail_digest,
                previous_hash,
                event_hash,
                event["created_at"],
            ),
        )

    def create(
        self,
        *,
        saga_id: Any,
        steps: Sequence[Mapping[str, Any]],
        created_at: Any | None = None,
    ) -> dict[str, Any]:
        sid = _token(saga_id, "saga_id")
        rows = [dict(x) for x in list(steps or [])]
        if not 1 <= len(rows) <= MAX_STEPS:
            raise ValueError("saga step count outside bounds")
        existing = self._saga_row(sid)
        normalized = []
        seen = set()
        worst_case_risk = 0
        forward_risk = 0
        for ordinal, raw in enumerate(rows, start=1):
            key = _token(raw.get("step_key"), "step_key")
            if key in seen:
                raise ValueError("duplicate saga step_key")
            seen.add(key)
            action = _token(raw.get("action"), "action")
            capability = _clean(raw.get("capability_class"), 80).upper()
            risk = raw.get("risk_points")
            if isinstance(risk, bool) or not isinstance(risk, int) or not 1 <= risk <= 100:
                raise ValueError("invalid saga risk_points")
            if capability not in CAPABILITY_CLASSES:
                raise ValueError("invalid capability_class")
            if capability == "CRITICAL":
                raise ValueError("critical capability requires separate human-owned flow")
            reversible = raw.get("reversible") is True
            if raw.get("reversible") is not True and raw.get("reversible") is not False:
                raise ValueError("reversible must be exact boolean")
            compensation_action = _clean(raw.get("compensation_action"), 128)
            compensation_risk = raw.get("compensation_risk_points", risk if reversible else 0)
            if reversible:
                _token(compensation_action, "compensation_action")
                if (
                    isinstance(compensation_risk, bool)
                    or not isinstance(compensation_risk, int)
                    or not 1 <= compensation_risk <= 100
                ):
                    raise ValueError("invalid compensation_risk_points")
            else:
                compensation_action = ""
                compensation_risk = 0
            # A89: both forward and rollback actions need the same
            # identity-preserving pre-staging admission as the Outbox.
            payload = clean_action_payload(raw.get("payload"))
            compensation_payload = clean_action_payload(raw.get("compensation_payload"))
            normalized.append({
                "ordinal": ordinal,
                "step_key": key,
                "action": action,
                "payload": payload,
                "capability_class": capability,
                "risk_points": risk,
                "reversible": reversible,
                "compensation_action": compensation_action,
                "compensation_payload": compensation_payload,
                "compensation_risk_points": compensation_risk,
            })
            forward_risk += risk
            worst_case_risk += risk + compensation_risk

        reversible_count = sum(1 for row in normalized if row["reversible"])
        worst_case_effects = len(rows) + reversible_count
        if len(rows) > self.authority_budget.max_transaction_effects:
            raise ValueError("saga forward effect count exceeds transaction budget")
        if forward_risk > self.authority_budget.max_transaction_risk_points:
            raise ValueError("saga forward risk exceeds transaction budget")
        if worst_case_effects > self.authority_budget.max_transaction_effects:
            raise ValueError("saga rollback effect reserve exceeds transaction budget")
        if worst_case_risk > self.authority_budget.max_transaction_risk_points:
            raise ValueError("saga rollback risk reserve exceeds transaction budget")
        # Compensation is independently re-approved and consumes the same budget.
        # Reserving worst-case shape prevents starting a saga that is known to be
        # impossible to compensate within its declared transaction envelope.
        plan = {
            "schema": SCHEMA,
            "saga_id": sid,
            "scope": list(self._scope_args()),
            "authority_budget_ref": self.authority_budget.authority_budget_ref,
            "policy_version": self.authority_budget.policy_version,
            "steps": normalized,
            "forward_risk_points": forward_risk,
            "worst_case_risk_points": worst_case_risk,
            "worst_case_effects": worst_case_effects,
        }
        plan_digest = _digest(plan)
        if existing is not None:
            current = self.get(sid)
            if current["plan_digest"] != plan_digest:
                raise ValueError("saga idempotency collision")
            return {**current, "create_state": "IDEMPOTENT"}

        created = _iso(_utc(created_at))
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute(
                """INSERT INTO aion_execution_sagas(
                    saga_id,owner,tenant,workspace,state,authority_budget_ref,
                    policy_version,plan_digest,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    sid,
                    *self._scope_args(),
                    "PLANNED",
                    self.authority_budget.authority_budget_ref,
                    self.authority_budget.policy_version,
                    plan_digest,
                    created,
                    created,
                ),
            )
            for row in normalized:
                self.db.execute(
                    """INSERT INTO aion_execution_saga_steps(
                        saga_id,ordinal,step_key,action,payload,capability_class,
                        risk_points,reversible,compensation_action,
                        compensation_payload,compensation_risk_points,state
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'PENDING')""",
                    (
                        sid,
                        row["ordinal"],
                        row["step_key"],
                        row["action"],
                        _canonical(row["payload"]),
                        row["capability_class"],
                        row["risk_points"],
                        1 if row["reversible"] else 0,
                        row["compensation_action"],
                        _canonical(row["compensation_payload"]),
                        row["compensation_risk_points"],
                    ),
                )
            self._append_event(
                sid,
                event_type="SAGA_CREATED",
                state="PLANNED",
                detail={
                    "plan_digest": plan_digest,
                    "forward_risk_points": forward_risk,
                    "worst_case_risk_points": worst_case_risk,
                    "worst_case_effects": worst_case_effects,
                },
                created_at=created,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {**self.get(sid), "create_state": "CREATED"}

    def enqueue_next(
        self,
        saga_id: Any,
        *,
        authorization_ref: Any,
        valid_until: Any,
        created_at: Any | None = None,
        requires_reauth: bool = False,
        reauth_ref: Any = "",
    ) -> dict[str, Any]:
        # A61: Outbox and Saga share one SQLite connection. Begin the OUTER
        # IMMEDIATE transaction before reading the plan, verifying integrity,
        # choosing the step, or staging the Outbox row. Outbox.enqueue uses a
        # nested SAVEPOINT and does not independently commit this operation.
        # A failed Saga projection or event append must roll back both tables.
        # This is only local durability; it does not prove independent effects.
        self.db.execute("BEGIN IMMEDIATE")
        try:
            saga = self.get(saga_id)
            # A60: forged local plan/genesis/event must not stage an intent.
            if self.integrity_report(saga["saga_id"])["state"] != "MATCH":
                raise PermissionError("SAGA_LOCAL_INTEGRITY_MISMATCH")
            candidate = select_forward_step(saga["state"], saga["steps"])
            pending = saga["steps"][candidate]
            # A41: a locally forged preceding CONFIRMED step must not
            # authorize a later forward action without producer proof.
            if candidate > 0:
                raise PermissionError("INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED")

            item = self.outbox.enqueue(
                intent_ref=f"{saga['saga_id']}:{pending['step_key']}:forward",
                action=pending["action"],
                payload=pending["payload"],
                aggregate_key=f"saga:{saga['saga_id']}:forward",
                policy_version=self.authority_budget.policy_version,
                authorization_ref=authorization_ref,
                valid_until=valid_until,
                created_at=created_at,
                requires_reauth=requires_reauth,
                reauth_ref=reauth_ref,
                transaction_id=saga["saga_id"],
                authority_budget_ref=self.authority_budget.authority_budget_ref,
                risk_points=pending["risk_points"],
                capability_class=pending["capability_class"],
            )
            now_iso = _iso(_utc(created_at))
            self.db.execute(
                """UPDATE aion_execution_saga_steps
                   SET state='ENQUEUED',outbox_key=?,last_error=''
                   WHERE saga_id=? AND step_key=?""",
                (item["idempotency_key"], saga["saga_id"], pending["step_key"]),
            )
            self.db.execute(
                "UPDATE aion_execution_sagas SET state='RUNNING',updated_at=? WHERE saga_id=?",
                (now_iso, saga["saga_id"]),
            )
            self._append_event(
                saga["saga_id"],
                event_type="FORWARD_ENQUEUED",
                state="RUNNING",
                step_key=pending["step_key"],
                detail={"outbox_key": item["idempotency_key"]},
                created_at=created_at,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {
            "schema": SCHEMA,
            "state": "ENQUEUED",
            "saga": self.get(saga["saga_id"]),
            "outbox": item,
            "executes_action": False,
        }

    def authority_guard(self, decision: Mapping[str, Any], *, now: Any | None = None) -> dict[str, Any]:
        return self.authority_budget.guard(decision, now=now)

    def sync_forward_outcome(
        self,
        saga_id: Any,
        step_key: Any,
        *,
        now: Any | None = None,
    ) -> dict[str, Any]:
        saga = self.get(saga_id)
        key = _token(step_key, "step_key")
        step = next((row for row in saga["steps"] if row["step_key"] == key), None)
        if step is None or not step["outbox_key"]:
            raise LookupError("saga step/outbox binding unavailable")
        out = self.outbox.get(step["outbox_key"])
        state = out["state"]
        # V16-A.39: a local SQLite state/effects row is not authenticated
        # producer testimony. In particular, this staging system cannot
        # presently enroll or verify a real causal COMMITTED_EFFECT receipt
        # or a producer-enforced terminal NO_EFFECT_FENCED receipt. Fail
        # BEFORE writing Saga state or recording authority-budget effects.
        if state == "CONFIRMED":
            raise PermissionError("INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED")
        if state == "FAILED":
            raise PermissionError("INDEPENDENT_PRODUCER_NO_EFFECT_FENCE_NOT_ENROLLED")
        # A65: persisted REVOKED / BLOCKED_REAPPROVAL are also LOCAL
        # annotations. Even if a local authorization callback produced them
        # before a send, SQLite cannot independently prove a producer-enforced
        # terminal no-effect fence. Do not claim FAILED / compensation eligibility
        # from these rows while the independent producer is unenrolled.
        if state in {"REVOKED", "BLOCKED_REAPPROVAL"}:
            raise PermissionError("INDEPENDENT_PRODUCER_NO_EFFECT_FENCE_NOT_ENROLLED")
        mapped = {
            "PENDING": "ENQUEUED",
            "CLAIMED": "ENQUEUED",
            "BLOCKED_PRODUCER": "BLOCKED_PRODUCER",
            "RETRY": "RETRY",
            "UNCERTAIN": "UNCERTAIN",
            "SENT": "UNCERTAIN",
            "CONFIRMED": "CONFIRMED",
            "REVOKED": "REVOKED",
            "BLOCKED_REAPPROVAL": "BLOCKED_REAPPROVAL",
            "FAILED": "FAILED",
        }[state]
        now_iso = _iso(_utc(now))
        saga_state = saga["state"]
        effect_ref = step["effect_ref"]
        last_error = _clean(out.get("last_error"), 240)

        if mapped == "CONFIRMED":
            effect_ref = _token(out.get("effect_ref"), "effect_ref")
            self.authority_budget.record_confirmed(
                out["decision"],
                idempotency_key=out["idempotency_key"],
                effect_ref=effect_ref,
                confirmed_at=out.get("confirmed_at") or now_iso,
            )
            remaining = [
                row for row in saga["steps"]
                if row["ordinal"] > step["ordinal"] and row["state"] == "PENDING"
            ]
            saga_state = "RUNNING" if remaining else "COMPLETED"
        elif mapped == "UNCERTAIN":
            saga_state = "RECONCILIATION_REQUIRED"
        elif mapped == "BLOCKED_PRODUCER":
            # No send occurred. Never claim effect, terminal failure or a
            # compensation; producer onboarding needs separate verification.
            saga_state = "PRODUCER_ENROLLMENT_REQUIRED"
        elif mapped in {"FAILED", "REVOKED", "BLOCKED_REAPPROVAL"}:
            prior = [
                row for row in saga["steps"]
                if row["ordinal"] < step["ordinal"] and row["state"] == "CONFIRMED"
            ]
            if any(not row["reversible"] for row in prior):
                saga_state = "MANUAL_INTERVENTION_REQUIRED"
            elif any(row["reversible"] for row in prior):
                saga_state = "COMPENSATION_REQUIRED"
            else:
                saga_state = "FAILED"
        else:
            saga_state = "RUNNING"

        self.db.execute("BEGIN IMMEDIATE")
        try:
            # A62: re-evaluate local plan/genesis/event consistency under
            # the SQLite writer lock immediately before writing outcomes.
            # Caller-supplied or rehashed local data are never producer proof.
            if self.integrity_report(saga["saga_id"])["state"] != "MATCH":
                raise PermissionError("SAGA_LOCAL_INTEGRITY_MISMATCH")
            # A63: the previous Saga and Outbox reads happened BEFORE the
            # IMMEDIATE writer lock. A legitimate writer may commit between
            # those reads and BEGIN; do not apply any stale mapping. Compare
            # actual locked snapshots, not a caller-supplied "fresh" flag.
            if self.get(saga["saga_id"]) != saga:
                raise PermissionError("SAGA_SNAPSHOT_STALE")
            if self.outbox.get(step["outbox_key"]) != out:
                raise PermissionError("SAGA_OUTBOX_SNAPSHOT_STALE")
            # A64: a locally mutable step.outbox_key is not authorization to
            # consume any row in the same tenant. Check the decision's exact
            # Saga/step/action/budget binding while holding SQLite writer lock.
            # This is LOCAL linkage, not producer testimony or antirollback.
            d = out.get("decision")
            expected = {
                "idempotency_key": step["outbox_key"],
                "owner_id": saga["owner_id"],
                "tenant_id": saga["tenant_id"],
                "workspace_id": saga["workspace_id"],
                "intent_ref": f"{saga['saga_id']}:{key}:forward",
                "transaction_id": saga["saga_id"],
                "aggregate_key": f"saga:{saga['saga_id']}:forward",
                "action": step["action"],
                "payload": step["payload"],
                "policy_version": saga["policy_version"],
                "authority_budget_ref": saga["authority_budget_ref"],
                "risk_points": step["risk_points"],
                "capability_class": step["capability_class"],
            }
            if (
                not isinstance(d, dict)
                or out["idempotency_key"] != step["outbox_key"]
                or out["aggregate_key"] != expected["aggregate_key"]
                or any(d.get(field) != value for field, value in expected.items())
            ):
                raise PermissionError("SAGA_OUTBOX_BINDING_MISMATCH")
            self.db.execute(
                """UPDATE aion_execution_saga_steps
                   SET state=?,effect_ref=?,last_error=?
                   WHERE saga_id=? AND step_key=?""",
                (mapped, effect_ref, last_error, saga["saga_id"], key),
            )
            if saga_state == "MANUAL_INTERVENTION_REQUIRED":
                self.db.execute(
                    """UPDATE aion_execution_saga_steps
                       SET state='MANUAL_REQUIRED'
                       WHERE saga_id=? AND ordinal<? AND state='CONFIRMED' AND reversible=0""",
                    (saga["saga_id"], step["ordinal"]),
                )
            self.db.execute(
                "UPDATE aion_execution_sagas SET state=?,updated_at=? WHERE saga_id=?",
                (saga_state, now_iso, saga["saga_id"]),
            )
            self._append_event(
                saga["saga_id"],
                event_type="FORWARD_OUTCOME",
                state=saga_state,
                step_key=key,
                detail={
                    "outbox_state": state,
                    "mapped_step_state": mapped,
                    "effect_ref": effect_ref,
                    "last_error": last_error,
                },
                created_at=now,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {
            "schema": SCHEMA,
            "state": saga_state,
            "step_state": mapped,
            "saga": self.get(saga["saga_id"]),
            "executes_action": False,
        }

    def prepare_compensation(
        self,
        saga_id: Any,
        *,
        explicit_human_approval: bool,
        approval_ref: Any,
        reauth_ref: Any,
        now: Any | None = None,
    ) -> dict[str, Any]:
        saga = self.get(saga_id)
        if saga["state"] != "COMPENSATION_REQUIRED":
            raise ValueError("saga is not eligible for compensation")
        if explicit_human_approval is not True:
            raise ValueError("explicit human approval required for compensation")
        approval = _token(approval_ref, "approval_ref")
        reauth = _token(reauth_ref, "reauth_ref")
        confirmed = [row for row in saga["steps"] if row["state"] == "CONFIRMED"]
        if not confirmed:
            raise ValueError("no confirmed effects to compensate")
        if any(not row["reversible"] for row in confirmed):
            raise ValueError("irreversible confirmed effect requires manual intervention")
        # V16-A.42: a local Saga CONFIRMED row and caller-provided approval
        # booleans/refs cannot authenticate an external effect or HUMAN_OWNER.
        # Until independent producer proof + human approval verification exist,
        # NEVER promote these SQLite projections into a compensation plan.
        # Deny before any Saga mutation, event append or budget operation.
        raise PermissionError("INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED")
        now_iso = _iso(_utc(now))
        self.db.execute("BEGIN IMMEDIATE")
        try:
            for row in confirmed:
                self.db.execute(
                    """UPDATE aion_execution_saga_steps
                       SET state='COMPENSATION_PENDING'
                       WHERE saga_id=? AND step_key=?""",
                    (saga["saga_id"], row["step_key"]),
                )
            self.db.execute(
                """UPDATE aion_execution_sagas
                   SET state='COMPENSATING',compensation_approval_ref=?,
                       compensation_reauth_ref=?,updated_at=?
                   WHERE saga_id=?""",
                (approval, reauth, now_iso, saga["saga_id"]),
            )
            self._append_event(
                saga["saga_id"],
                event_type="COMPENSATION_APPROVED",
                state="COMPENSATING",
                detail={
                    "approval_ref": approval,
                    "reauth_ref_digest": _digest(reauth),
                    "candidate_steps": [row["step_key"] for row in confirmed],
                },
                created_at=now,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {
            "schema": SCHEMA,
            "state": "COMPENSATING",
            "saga": self.get(saga["saga_id"]),
            "automatic_compensation": False,
            "executes_action": False,
        }

    def enqueue_next_compensation(
        self,
        saga_id: Any,
        *,
        valid_until: Any,
        created_at: Any | None = None,
    ) -> dict[str, Any]:
        saga = self.get(saga_id)
        candidate = select_compensation_step(saga["state"], saga["steps"])
        step = saga["steps"][candidate]
        # V16-A.42: local COMPENSATING/COMPENSATION_PENDING, effect_ref and
        # approval/reauth refs may all be forged in SQLite. There is no
        # independently enrolled producer effect or owner authorization yet.
        # A pure sequence candidate is NEVER sufficient to stage a rollback.
        raise PermissionError("INDEPENDENT_PRODUCER_COMPENSATION_NOT_ENROLLED")
        item = self.outbox.enqueue(
            intent_ref=f"{saga['saga_id']}:{step['step_key']}:compensation",
            action=step["compensation_action"],
            payload={
                **step["compensation_payload"],
                "saga_id": saga["saga_id"],
                "original_step_key": step["step_key"],
                "original_effect_ref": step["effect_ref"],
            },
            aggregate_key=f"saga:{saga['saga_id']}:compensation",
            policy_version=self.authority_budget.policy_version,
            authorization_ref=saga["compensation_approval_ref"],
            valid_until=valid_until,
            created_at=created_at,
            requires_reauth=True,
            reauth_ref=saga["compensation_reauth_ref"],
            transaction_id=saga["saga_id"],
            authority_budget_ref=self.authority_budget.authority_budget_ref,
            risk_points=step["compensation_risk_points"],
            capability_class=step["capability_class"],
        )
        now_iso = _iso(_utc(created_at))
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute(
                """UPDATE aion_execution_saga_steps
                   SET state='COMPENSATION_ENQUEUED',compensation_outbox_key=?
                   WHERE saga_id=? AND step_key=?""",
                (item["idempotency_key"], saga["saga_id"], step["step_key"]),
            )
            self.db.execute(
                "UPDATE aion_execution_sagas SET updated_at=? WHERE saga_id=?",
                (now_iso, saga["saga_id"]),
            )
            self._append_event(
                saga["saga_id"],
                event_type="COMPENSATION_ENQUEUED",
                state="COMPENSATING",
                step_key=step["step_key"],
                detail={"outbox_key": item["idempotency_key"]},
                created_at=created_at,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {
            "schema": SCHEMA,
            "state": "COMPENSATION_ENQUEUED",
            "saga": self.get(saga["saga_id"]),
            "outbox": item,
            "executes_action": False,
        }

    def sync_compensation_outcome(
        self,
        saga_id: Any,
        step_key: Any,
        *,
        now: Any | None = None,
    ) -> dict[str, Any]:
        saga = self.get(saga_id)
        key = _token(step_key, "step_key")
        step = next((row for row in saga["steps"] if row["step_key"] == key), None)
        if step is None or not step["compensation_outbox_key"]:
            raise LookupError("compensation outbox binding unavailable")
        out = self.outbox.get(step["compensation_outbox_key"])
        now_iso = _iso(_utc(now))
        out_state = out["state"]
        # The compensation path is another possible effect-ledger/authority
        # elevation. A local CONFIRMED or FAILED row cannot prove the
        # external compensation or its terminal no-effect fence either.
        if out_state == "CONFIRMED":
            raise PermissionError("INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED")
        if out_state == "FAILED":
            raise PermissionError("INDEPENDENT_PRODUCER_NO_EFFECT_FENCE_NOT_ENROLLED")
        # A62: compensation admission and independent producer no-effect/
        # effect receipts are not enrolled. A local compensation_outbox_key,
        # REVOCATION or UNCERTAIN status can be forged in SQLite; it MUST NOT
        # promote Saga into MANUAL_INTERVENTION or RECONCILIATION_REQUIRED.
        # Do not turn this into a caller-controlled "verified" switch.
        raise PermissionError("INDEPENDENT_PRODUCER_COMPENSATION_NOT_ENROLLED")
        if out_state == "BLOCKED_PRODUCER":
            mapped = "BLOCKED_PRODUCER"
            saga_state = "PRODUCER_ENROLLMENT_REQUIRED"
        elif out_state in {"UNCERTAIN", "SENT"}:
            mapped = "UNCERTAIN"
            saga_state = "RECONCILIATION_REQUIRED"
        elif out_state == "CONFIRMED":
            mapped = "COMPENSATED"
            effect = _token(out.get("effect_ref"), "effect_ref")
            self.authority_budget.record_confirmed(
                out["decision"],
                idempotency_key=out["idempotency_key"],
                effect_ref=effect,
                confirmed_at=out.get("confirmed_at") or now_iso,
            )
            remaining = [
                row for row in saga["steps"]
                if row["step_key"] != key and row["state"] == "COMPENSATION_PENDING"
            ]
            saga_state = "COMPENSATING" if remaining else "COMPENSATED"
        elif out_state in {"FAILED", "REVOKED", "BLOCKED_REAPPROVAL"}:
            mapped = "COMPENSATION_FAILED"
            saga_state = "MANUAL_INTERVENTION_REQUIRED"
            effect = ""
        else:
            return {
                "schema": SCHEMA,
                "state": "WAITING",
                "saga": saga,
                "outbox_state": out_state,
                "executes_action": False,
            }
        effect = _clean(out.get("effect_ref"), 128) if out_state == "CONFIRMED" else ""
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute(
                """UPDATE aion_execution_saga_steps
                   SET state=?,compensation_effect_ref=?,last_error=?
                   WHERE saga_id=? AND step_key=?""",
                (
                    mapped,
                    effect,
                    _clean(out.get("last_error"), 240),
                    saga["saga_id"],
                    key,
                ),
            )
            self.db.execute(
                "UPDATE aion_execution_sagas SET state=?,updated_at=? WHERE saga_id=?",
                (saga_state, now_iso, saga["saga_id"]),
            )
            self._append_event(
                saga["saga_id"],
                event_type="COMPENSATION_OUTCOME",
                state=saga_state,
                step_key=key,
                detail={
                    "outbox_state": out_state,
                    "mapped_step_state": mapped,
                    "effect_ref": effect,
                },
                created_at=now,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {
            "schema": SCHEMA,
            "state": saga_state,
            "step_state": mapped,
            "saga": self.get(saga["saga_id"]),
            "executes_action": False,
        }

    def integrity_report(self, saga_id: Any) -> dict[str, Any]:
        saga = self.get(saga_id)
        rows = self.db.execute(
            """SELECT * FROM aion_execution_saga_events
               WHERE saga_id=? ORDER BY sequence""",
            (saga["saga_id"],),
        ).fetchall()
        previous = GENESIS_HASH
        blockers = []
        # Reconstruct immutable plan material from the persisted projection.
        # This detects local drift only; it is never producer/rollback proof.
        plan_fields = (
            "ordinal", "step_key", "action", "payload", "capability_class",
            "risk_points", "reversible", "compensation_action",
            "compensation_payload", "compensation_risk_points",
        )
        planned_steps = [{key: step[key] for key in plan_fields} for step in saga["steps"]]
        forward_risk = sum(step["risk_points"] for step in planned_steps)
        worst_case_risk = sum(
            step["risk_points"] + step["compensation_risk_points"] for step in planned_steps
        )
        worst_case_effects = len(planned_steps) + sum(
            1 for step in planned_steps if step["reversible"]
        )
        plan = {
            "schema": SCHEMA, "saga_id": saga["saga_id"],
            "scope": [saga["owner_id"], saga["tenant_id"], saga["workspace_id"]],
            "authority_budget_ref": saga["authority_budget_ref"],
            "policy_version": saga["policy_version"], "steps": planned_steps,
            "forward_risk_points": forward_risk,
            "worst_case_risk_points": worst_case_risk,
            "worst_case_effects": worst_case_effects,
        }
        if _digest(plan) != saga["plan_digest"]:
            blockers.append("PLAN_DIGEST_MISMATCH")
        if rows and rows[0]["detail_digest"] != _digest({
            "plan_digest": saga["plan_digest"], "forward_risk_points": forward_risk,
            "worst_case_risk_points": worst_case_risk,
            "worst_case_effects": worst_case_effects,
        }):
            blockers.append("GENESIS_PLAN_BINDING_MISMATCH")
        # A.43: an empty chain is not a valid intact saga merely because
        # there are no rows whose hashes can mismatch. Every created Saga
        # must have a SAGA_CREATED genesis event. This is local consistency,
        # NOT an independently authenticated antirollback witness.
        if not rows:
            blockers.append("EVENT_CHAIN_EMPTY")
        elif rows[0]["event_type"] != "SAGA_CREATED":
            blockers.append("GENESIS_EVENT_MISSING")
        for expected_sequence, row in enumerate(rows, start=1):
            if int(row["sequence"]) != expected_sequence:
                blockers.append("EVENT_SEQUENCE_MISMATCH")
                break
            if row["previous_hash"] != previous:
                blockers.append("EVENT_PREVIOUS_HASH_MISMATCH")
                break
            payload = {
                "saga_id": saga["saga_id"],
                "sequence": int(row["sequence"]),
                "event_type": row["event_type"],
                "step_key": row["step_key"],
                "state": row["state"],
                "detail_digest": row["detail_digest"],
                "previous_hash": row["previous_hash"],
                "created_at": row["created_at"],
            }
            expected_hash = _digest(payload)
            if row["event_hash"] != expected_hash:
                blockers.append("EVENT_HASH_MISMATCH")
                break
            previous = row["event_hash"]
        # Detect simple tail deletion or direct Saga-state rewrite where the
        # surviving local event chain no longer describes the current state.
        # Rehashing/replaying both tables remains possible without an
        # independent latest-head witness: never call this external proof.
        if rows and not blockers and rows[-1]["state"] != saga["state"]:
            blockers.append("LATEST_EVENT_STATE_MISMATCH")
        return {
            "schema": SCHEMA,
            "saga_id": saga["saga_id"],
            "state": "MATCH" if not blockers else "MISMATCH",
            "blockers": blockers,
            "events": len(rows),
            "tip_hash": previous,
            "proof_scope": "LOCAL_SQLITE_CHAIN_ONLY",
            "independent_witness_verified": False,
            "producer_effect_verified": False,
            "authorizes_execution": False,
            "automatic_compensation": False,
            "executes_action": False,
        }


__all__ = [
    "SCHEMA",
    "MAX_STEPS",
    "SAGA_STATES",
    "STEP_STATES",
    "ExecutionSagaCoordinator",
]
