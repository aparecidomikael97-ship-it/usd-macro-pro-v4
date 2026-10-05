"""Fail-closed SAGA coordination for multi-step AION work.

This module records ordered step outcomes and prepares compensation work after a
partial failure. It never executes the original action or its compensation.

Key invariants:
- OUTCOME_UNKNOWN always requires manual reconciliation.
- Confirmed external effects are never automatically retried.
- Compensation runs in reverse effect order and requires separate durable
  execution plus explicit authorization outside this module.
- Irreversible/non-compensatable confirmed effects force manual reconciliation.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from itertools import islice
import json
from typing import Any, Mapping, Sequence

SCHEMA = "ATLASQUANT_AION_SAGA_CONTROL_V1"
REGISTRY_SCHEMA = "ATLASQUANT_AION_SAGA_REGISTRY_V1"
VERSION = 1
MAX_SAGAS = 300
MAX_STEPS = 80
SAGA_STATES = (
    "PLANNED",
    "ACTIVE",
    "COMPLETED",
    "FAILED_SAFE",
    "COMPENSATION_REQUIRED",
    "COMPENSATING",
    "COMPENSATED",
    "MANUAL_RECONCILIATION_REQUIRED",
    "CANCELED",
)
STEP_MODES = ("LOCAL_SAFE", "EXTERNAL_EFFECT")
STEP_STATES = (
    "PENDING",
    "DONE",
    "FAILED_BEFORE_EFFECT",
    "OUTCOME_UNKNOWN",
    "COMPENSATION_PENDING",
    "COMPENSATED",
    "COMPENSATION_FAILED",
)
STEP_OUTCOMES = (
    "LOCAL_COMPLETED",
    "EFFECT_CONFIRMED",
    "NO_EFFECT_CONFIRMED",
    "FAILED_BEFORE_EFFECT",
    "OUTCOME_UNKNOWN",
)
COMPENSATION_OUTCOMES = (
    "COMPENSATED",
    "COMPENSATION_FAILED",
    "OUTCOME_UNKNOWN",
)
TERMINAL_SAGA_STATES = {
    "COMPLETED",
    "FAILED_SAFE",
    "COMPENSATED",
    "MANUAL_RECONCILIATION_REQUIRED",
    "CANCELED",
}


class SagaControlError(ValueError):
    def __init__(self, code: str, saga: Mapping[str, Any] | None = None):
        super().__init__(code)
        row = dict(saga or {})
        self.result = {
            "schema": SCHEMA,
            "state": "BLOCK",
            "error_code": code,
            "saga_id": row.get("saga_id", ""),
            "execution_allowed": False,
            "executes_action": False,
        }


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _upper(value: Any, limit: int = 80) -> str:
    return _clean(value, limit).upper()


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _aware(value: Any = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        out = value
    else:
        out = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if out.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return out.astimezone(timezone.utc)


def _scope(context: Mapping[str, Any] | None) -> dict[str, str]:
    raw = dict(context or {})
    owner = _clean(raw.get("owner_id") or raw.get("actor_id") or raw.get("subject_id"), 160)
    tenant = _clean(raw.get("tenant_id"), 120)
    workspace = _clean(raw.get("workspace_id"), 120)
    if not owner or not tenant or not workspace:
        raise ValueError("owner/tenant/workspace binding required")
    scope_digest = sha256(
        (owner + "|" + tenant + "|" + workspace).encode("utf-8")
    ).hexdigest()[:24]
    return {
        "owner_id": owner,
        "tenant_id": tenant,
        "workspace_id": workspace,
        "scope_digest": scope_digest,
    }


def _step_digest(step: Mapping[str, Any]) -> str:
    body = dict(step)
    body.pop("step_digest", None)
    return _digest(body)


def _saga_digest(saga: Mapping[str, Any]) -> str:
    body = dict(saga)
    body.pop("digest", None)
    return _digest(body)


def _normalize_step(raw: Mapping[str, Any], index: int) -> dict[str, Any]:
    item = dict(raw or {})
    step_id = _clean(item.get("step_id"), 100) or f"S{index+1:03d}"
    mode = _upper(item.get("mode"), 40)
    if mode not in STEP_MODES:
        raise ValueError("invalid saga step mode")
    effect_key = _clean(item.get("effect_key"), 240)
    idem = _clean(item.get("idempotency_key"), 240)
    payload_digest = _clean(item.get("payload_digest"), 180)
    if not effect_key or not idem or not payload_digest:
        raise ValueError("saga step effect/idempotency/payload binding required")
    compensatable = item.get("compensatable") is True
    irreversible = item.get("irreversible") is True
    if compensatable and irreversible:
        raise ValueError("irreversible step cannot be marked compensatable")
    compensation_action = _clean(item.get("compensation_action"), 180)
    compensation_payload_digest = _clean(item.get("compensation_payload_digest"), 180)
    if mode == "EXTERNAL_EFFECT" and compensatable:
        if not compensation_action or not compensation_payload_digest:
            raise ValueError("compensatable external step requires compensation binding")
    if mode == "LOCAL_SAFE":
        compensatable = False
        irreversible = False
        compensation_action = ""
        compensation_payload_digest = ""

    step = {
        "step_id": step_id,
        "title": _clean(item.get("title"), 300) or f"Passo {index+1}",
        "mode": mode,
        "effect_key": effect_key,
        "idempotency_key": idem,
        "payload_digest": payload_digest,
        "durable_task_id": _clean(item.get("durable_task_id"), 120),
        "durable_step_id": _clean(item.get("durable_step_id"), 120),
        "execution_ref": _clean(item.get("execution_ref"), 160),
        "compensatable": compensatable,
        "irreversible": irreversible,
        "compensation_action": compensation_action,
        "compensation_payload_digest": compensation_payload_digest,
        "state": "PENDING",
        "outcome": "",
        "outcome_evidence_digest": "",
        "outcome_recorded_at": "",
        "compensation_state": "",
        "compensation_evidence_digest": "",
        "compensation_recorded_at": "",
        "executes_action": False,
    }
    step["step_digest"] = _step_digest(step)
    return step


def new_saga(
    *,
    title: Any,
    steps: Sequence[Mapping[str, Any]],
    trusted_context: Mapping[str, Any] | None,
    mission_id: Any = "",
    durable_task_id: Any = "",
    created_at: Any = None,
) -> dict[str, Any]:
    scope = _scope(trusted_context)
    title_clean = _clean(title, 300)
    if not title_clean:
        raise ValueError("saga title required")
    rows = []
    ids = set()
    effect_keys = set()
    idempotency_keys = set()
    for index, raw in enumerate(islice(steps or (), MAX_STEPS)):
        if not isinstance(raw, Mapping):
            raise ValueError("saga step mapping required")
        step = _normalize_step(raw, index)
        if step["step_id"] in ids:
            raise ValueError("duplicate saga step id")
        if step["effect_key"] in effect_keys:
            raise ValueError("duplicate saga effect key")
        if step["idempotency_key"] in idempotency_keys:
            raise ValueError("duplicate saga idempotency key")
        ids.add(step["step_id"])
        effect_keys.add(step["effect_key"])
        idempotency_keys.add(step["idempotency_key"])
        rows.append(step)
    if not rows:
        raise ValueError("saga requires at least one step")
    created = _aware(created_at).isoformat()
    seed = {
        "scope_digest": scope["scope_digest"],
        "title": title_clean,
        "mission_id": _clean(mission_id, 120),
        "durable_task_id": _clean(durable_task_id, 120),
        "steps": [
            {
                "step_id": row["step_id"],
                "effect_key": row["effect_key"],
                "payload_digest": row["payload_digest"],
            }
            for row in rows
        ],
        "created_at": created,
    }
    saga = {
        "schema": SCHEMA,
        "version": VERSION,
        "saga_id": "SAGA-" + _digest(seed)[:24].upper(),
        "title": title_clean,
        **scope,
        "mission_id": _clean(mission_id, 120),
        "durable_task_id": _clean(durable_task_id, 120),
        "state": "PLANNED",
        "steps": rows,
        "cursor": 0,
        "compensation_order": [],
        "compensation_cursor": 0,
        "blocker": "",
        "created_at": created,
        "updated_at": created,
        "automatic_retry_external_effect": False,
        "automatic_compensation": False,
        "execution_allowed": False,
        "executes_action": False,
        "external_action_executed": False,
    }
    saga["digest"] = _saga_digest(saga)
    return saga


def validate_saga(
    saga: Mapping[str, Any] | None,
    *,
    trusted_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    expected = _scope(trusted_context)
    if not isinstance(saga, Mapping):
        return {
            "schema": SCHEMA,
            "state": "BLOCK",
            "valid": False,
            "blockers": ["SAGA_MAPPING_REQUIRED"],
            "execution_allowed": False,
        }
    row = dict(saga)
    blockers: list[str] = []
    if row.get("schema") != SCHEMA or row.get("version") != VERSION:
        blockers.append("SAGA_SCHEMA_OR_VERSION_MISMATCH")
    if row.get("state") not in SAGA_STATES:
        blockers.append("SAGA_STATE_INVALID")
    for key in ("owner_id", "tenant_id", "workspace_id", "scope_digest"):
        if row.get(key) != expected[key]:
            blockers.append("SAGA_SCOPE_MISMATCH")
            break
    steps = list(row.get("steps") or [])
    if not steps or len(steps) > MAX_STEPS:
        blockers.append("SAGA_STEP_COUNT_INVALID")
    ids = set()
    effects = set()
    idems = set()
    for index, step in enumerate(steps):
        if not isinstance(step, Mapping):
            blockers.append("SAGA_STEP_NOT_MAPPING")
            continue
        item = dict(step)
        sid = _clean(item.get("step_id"), 100)
        if not sid or sid in ids:
            blockers.append("SAGA_STEP_ID_INVALID_OR_DUPLICATE")
        ids.add(sid)
        effect = _clean(item.get("effect_key"), 240)
        idem = _clean(item.get("idempotency_key"), 240)
        if not effect or effect in effects:
            blockers.append("SAGA_EFFECT_KEY_INVALID_OR_DUPLICATE")
        if not idem or idem in idems:
            blockers.append("SAGA_IDEMPOTENCY_KEY_INVALID_OR_DUPLICATE")
        effects.add(effect)
        idems.add(idem)
        if item.get("mode") not in STEP_MODES:
            blockers.append("SAGA_STEP_MODE_INVALID")
        if item.get("state") not in STEP_STATES:
            blockers.append("SAGA_STEP_STATE_INVALID")
        if item.get("executes_action") is not False:
            blockers.append("SAGA_STEP_CANNOT_EXECUTE")
        if _clean(item.get("step_digest"), 64) != _step_digest(item):
            blockers.append("SAGA_STEP_DIGEST_MISMATCH")
    cursor = row.get("cursor")
    if isinstance(cursor, bool) or not isinstance(cursor, int) or not 0 <= cursor <= len(steps):
        blockers.append("SAGA_CURSOR_INVALID")
    comp_order = list(row.get("compensation_order") or [])
    if len(comp_order) != len(set(comp_order)):
        blockers.append("SAGA_COMPENSATION_ORDER_DUPLICATE")
    if any(step_id not in ids for step_id in comp_order):
        blockers.append("SAGA_COMPENSATION_ORDER_UNKNOWN_STEP")
    stored = _clean(row.get("digest"), 64)
    expected_digest = _saga_digest(row)
    if stored != expected_digest:
        blockers.append("SAGA_DIGEST_MISMATCH")
    return {
        "schema": SCHEMA,
        "state": "CONFIRMED" if not blockers else "BLOCK",
        "valid": not blockers,
        "blockers": sorted(set(blockers)),
        "stored_digest": stored,
        "expected_digest": expected_digest,
        "execution_allowed": False,
        "executes_action": False,
    }


def _completed_external_effects(saga: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(step)
        for step in list(saga.get("steps") or [])
        if isinstance(step, Mapping)
        and step.get("mode") == "EXTERNAL_EFFECT"
        and step.get("outcome") == "EFFECT_CONFIRMED"
    ]


def _failure_state_after_safe_non_effect(saga: Mapping[str, Any]) -> tuple[str, list[str]]:
    effects = _completed_external_effects(saga)
    if not effects:
        return "FAILED_SAFE", []
    if all(step.get("compensatable") is True and step.get("irreversible") is not True for step in effects):
        return "COMPENSATION_REQUIRED", [step["step_id"] for step in reversed(effects)]
    return "MANUAL_RECONCILIATION_REQUIRED", []


def record_saga_step_outcome(
    saga: Mapping[str, Any] | None,
    *,
    step_id: Any,
    outcome: Any,
    evidence_digest: Any,
    trusted_context: Mapping[str, Any] | None,
    recorded_at: Any = None,
) -> dict[str, Any]:
    audit = validate_saga(saga, trusted_context=trusted_context)
    if audit["valid"] is not True:
        raise SagaControlError("SAGA_SCOPE_OR_INTEGRITY_MISMATCH", saga)
    state = deepcopy(dict(saga or {}))
    if state["state"] in TERMINAL_SAGA_STATES:
        raise SagaControlError("SAGA_TERMINAL", state)
    if state["state"] in {"COMPENSATION_REQUIRED", "COMPENSATING"}:
        raise SagaControlError("SAGA_IN_COMPENSATION", state)

    target = _clean(step_id, 100)
    result = _upper(outcome, 40)
    evidence = _clean(evidence_digest, 180)
    if result not in STEP_OUTCOMES:
        raise SagaControlError("SAGA_OUTCOME_INVALID", state)
    if not evidence:
        raise SagaControlError("SAGA_OUTCOME_EVIDENCE_REQUIRED", state)
    if state["cursor"] >= len(state["steps"]):
        raise SagaControlError("SAGA_CURSOR_COMPLETE", state)
    step = state["steps"][state["cursor"]]
    if step["step_id"] != target:
        raise SagaControlError("SAGA_STEP_OUT_OF_ORDER", state)

    if step.get("outcome"):
        if step["outcome"] == result and step["outcome_evidence_digest"] == evidence:
            return {
                "schema": SCHEMA,
                "state": "IDEMPOTENT",
                "saga": state,
                "execution_allowed": False,
                "executes_action": False,
            }
        raise SagaControlError("SAGA_OUTCOME_REPLAY_CONFLICT", state)

    if step["mode"] == "LOCAL_SAFE" and result != "LOCAL_COMPLETED":
        raise SagaControlError("LOCAL_STEP_OUTCOME_INVALID", state)
    if step["mode"] == "EXTERNAL_EFFECT" and result == "LOCAL_COMPLETED":
        raise SagaControlError("EXTERNAL_STEP_OUTCOME_INVALID", state)

    when = _aware(recorded_at).isoformat()
    step["outcome"] = result
    step["outcome_evidence_digest"] = evidence
    step["outcome_recorded_at"] = when

    if result in {"LOCAL_COMPLETED", "EFFECT_CONFIRMED"}:
        step["state"] = "DONE"
        step["step_digest"] = _step_digest(step)
        state["cursor"] += 1
        state["state"] = "COMPLETED" if state["cursor"] >= len(state["steps"]) else "ACTIVE"
        state["blocker"] = ""
    elif result in {"NO_EFFECT_CONFIRMED", "FAILED_BEFORE_EFFECT"}:
        step["state"] = "FAILED_BEFORE_EFFECT"
        step["step_digest"] = _step_digest(step)
        next_state, order = _failure_state_after_safe_non_effect(state)
        state["state"] = next_state
        state["compensation_order"] = order
        state["compensation_cursor"] = 0
        state["blocker"] = result
        if next_state == "COMPENSATION_REQUIRED":
            for compensation_step_id in order:
                for prior in state["steps"]:
                    if prior["step_id"] == compensation_step_id:
                        prior["compensation_state"] = "COMPENSATION_PENDING"
                        prior["step_digest"] = _step_digest(prior)
    else:
        step["state"] = "OUTCOME_UNKNOWN"
        step["step_digest"] = _step_digest(step)
        state["state"] = "MANUAL_RECONCILIATION_REQUIRED"
        state["blocker"] = "OUTCOME_UNKNOWN"
        state["compensation_order"] = []
        state["compensation_cursor"] = 0

    state["updated_at"] = when
    state["digest"] = _saga_digest(state)
    return {
        "schema": SCHEMA,
        "state": state["state"],
        "saga": state,
        "automatic_retry_external_effect": False,
        "automatic_compensation": False,
        "execution_allowed": False,
        "executes_action": False,
    }


def prepare_compensation_plan(
    saga: Mapping[str, Any] | None,
    *,
    trusted_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    audit = validate_saga(saga, trusted_context=trusted_context)
    if audit["valid"] is not True:
        raise SagaControlError("SAGA_SCOPE_OR_INTEGRITY_MISMATCH", saga)
    state = dict(saga or {})
    if state["state"] not in {"COMPENSATION_REQUIRED", "COMPENSATING"}:
        return {
            "schema": SCHEMA,
            "state": "BLOCK",
            "reason": "COMPENSATION_NOT_REQUIRED",
            "plan": [],
            "execution_allowed": False,
            "executes_action": False,
        }
    by_id = {step["step_id"]: step for step in state["steps"]}
    plan = []
    for order_index, step_id in enumerate(state["compensation_order"], start=1):
        step = by_id[step_id]
        plan.append({
            "order": order_index,
            "step_id": step_id,
            "original_effect_key": step["effect_key"],
            "original_execution_ref": step.get("execution_ref", ""),
            "compensation_action": step["compensation_action"],
            "compensation_payload_digest": step["compensation_payload_digest"],
            "requires_new_idempotency_key": True,
            "requires_new_effect_key": True,
            "requires_new_durable_execution": True,
            "requires_explicit_authorization": True,
            "requires_provider_evidence": True,
            "execution_allowed": False,
            "executes_action": False,
        })
    return {
        "schema": SCHEMA,
        "state": "PLAN_READY",
        "saga_id": state["saga_id"],
        "plan": plan,
        "reverse_effect_order": True,
        "automatic_compensation": False,
        "execution_allowed": False,
        "executes_action": False,
    }


def record_compensation_outcome(
    saga: Mapping[str, Any] | None,
    *,
    step_id: Any,
    outcome: Any,
    evidence_digest: Any,
    reconciliation_authorized: Any,
    trusted_context: Mapping[str, Any] | None,
    recorded_at: Any = None,
) -> dict[str, Any]:
    audit = validate_saga(saga, trusted_context=trusted_context)
    if audit["valid"] is not True:
        raise SagaControlError("SAGA_SCOPE_OR_INTEGRITY_MISMATCH", saga)
    state = deepcopy(dict(saga or {}))
    if state["state"] not in {"COMPENSATION_REQUIRED", "COMPENSATING"}:
        raise SagaControlError("COMPENSATION_STATE_BLOCKED", state)
    if reconciliation_authorized is not True:
        raise SagaControlError("COMPENSATION_AUTHORIZATION_REQUIRED", state)
    result = _upper(outcome, 40)
    if result not in COMPENSATION_OUTCOMES:
        raise SagaControlError("COMPENSATION_OUTCOME_INVALID", state)
    evidence = _clean(evidence_digest, 180)
    if not evidence:
        raise SagaControlError("COMPENSATION_EVIDENCE_REQUIRED", state)
    target = _clean(step_id, 100)
    if state["compensation_cursor"] >= len(state["compensation_order"]):
        raise SagaControlError("COMPENSATION_CURSOR_COMPLETE", state)
    expected = state["compensation_order"][state["compensation_cursor"]]
    if target != expected:
        raise SagaControlError("COMPENSATION_OUT_OF_ORDER", state)
    step = next(row for row in state["steps"] if row["step_id"] == target)

    if step.get("compensation_evidence_digest"):
        if (
            step.get("compensation_state") == result
            and step["compensation_evidence_digest"] == evidence
        ):
            return {
                "schema": SCHEMA,
                "state": "IDEMPOTENT",
                "saga": state,
                "execution_allowed": False,
                "executes_action": False,
            }
        raise SagaControlError("COMPENSATION_REPLAY_CONFLICT", state)

    when = _aware(recorded_at).isoformat()
    step["compensation_state"] = result
    step["compensation_evidence_digest"] = evidence
    step["compensation_recorded_at"] = when

    if result == "COMPENSATED":
        step["state"] = "COMPENSATED"
        state["compensation_cursor"] += 1
        if state["compensation_cursor"] >= len(state["compensation_order"]):
            state["state"] = "COMPENSATED"
            state["blocker"] = ""
        else:
            state["state"] = "COMPENSATING"
    else:
        step["state"] = (
            "OUTCOME_UNKNOWN" if result == "OUTCOME_UNKNOWN"
            else "COMPENSATION_FAILED"
        )
        state["state"] = "MANUAL_RECONCILIATION_REQUIRED"
        state["blocker"] = result

    step["step_digest"] = _step_digest(step)
    state["updated_at"] = when
    state["digest"] = _saga_digest(state)
    return {
        "schema": SCHEMA,
        "state": state["state"],
        "saga": state,
        "business_invariant_restored": False,
        "automatic_compensation": False,
        "execution_allowed": False,
        "executes_action": False,
    }


def default_saga_registry(
    trusted_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    scope = _scope(trusted_context)
    sagas: list[dict[str, Any]] = []
    state = {
        "schema": REGISTRY_SCHEMA,
        "version": VERSION,
        **scope,
        "sagas": sagas,
        "automatic_compensation": False,
        "execution_allowed": False,
        "executes_action": False,
    }
    state["digest"] = _digest({
        "scope_digest": scope["scope_digest"],
        "sagas": sagas,
    })
    return state


def _registry_digest(state: Mapping[str, Any]) -> str:
    return _digest({
        "scope_digest": state.get("scope_digest"),
        "sagas": state.get("sagas") or [],
    })


def validate_saga_registry(
    registry: Mapping[str, Any] | None,
    *,
    trusted_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    expected = _scope(trusted_context)
    if not isinstance(registry, Mapping):
        return {
            "schema": REGISTRY_SCHEMA,
            "state": "BLOCK",
            "valid": False,
            "blockers": ["SAGA_REGISTRY_MAPPING_REQUIRED"],
        }
    row = dict(registry)
    blockers: list[str] = []
    if row.get("schema") != REGISTRY_SCHEMA or row.get("version") != VERSION:
        blockers.append("SAGA_REGISTRY_SCHEMA_OR_VERSION_MISMATCH")
    for key in ("owner_id", "tenant_id", "workspace_id", "scope_digest"):
        if row.get(key) != expected[key]:
            blockers.append("SAGA_REGISTRY_SCOPE_MISMATCH")
            break
    sagas = list(row.get("sagas") or [])
    if len(sagas) > MAX_SAGAS:
        blockers.append("SAGA_REGISTRY_CAPACITY_EXCEEDED")
    ids = set()
    for saga in sagas[: MAX_SAGAS + 1]:
        if not isinstance(saga, Mapping):
            blockers.append("SAGA_REGISTRY_ROW_INVALID")
            continue
        sid = _clean(saga.get("saga_id"), 120)
        if not sid or sid in ids:
            blockers.append("SAGA_REGISTRY_ID_INVALID_OR_DUPLICATE")
        ids.add(sid)
        audit = validate_saga(saga, trusted_context=trusted_context)
        if audit["valid"] is not True:
            blockers.append("SAGA_REGISTRY_CONTAINS_INVALID_SAGA")
    expected_digest = _registry_digest(row)
    if _clean(row.get("digest"), 64) != expected_digest:
        blockers.append("SAGA_REGISTRY_DIGEST_MISMATCH")
    return {
        "schema": REGISTRY_SCHEMA,
        "state": "CONFIRMED" if not blockers else "BLOCK",
        "valid": not blockers,
        "blockers": sorted(set(blockers)),
        "expected_digest": expected_digest,
        "stored_digest": _clean(row.get("digest"), 64),
        "execution_allowed": False,
        "executes_action": False,
    }


def upsert_saga(
    registry: Mapping[str, Any] | None,
    saga: Mapping[str, Any],
    *,
    trusted_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    registry_audit = validate_saga_registry(
        registry,
        trusted_context=trusted_context,
    )
    if registry_audit["valid"] is not True:
        raise SagaControlError("SAGA_REGISTRY_SCOPE_OR_INTEGRITY_MISMATCH")
    saga_audit = validate_saga(saga, trusted_context=trusted_context)
    if saga_audit["valid"] is not True:
        raise SagaControlError("SAGA_SCOPE_OR_INTEGRITY_MISMATCH", saga)

    state = deepcopy(dict(registry or {}))
    current = [
        dict(row)
        for row in list(state.get("sagas") or [])
        if isinstance(row, Mapping)
    ]
    target = saga["saga_id"]
    existing_index = next(
        (index for index, row in enumerate(current) if row.get("saga_id") == target),
        None,
    )
    if existing_index is None:
        if len(current) >= MAX_SAGAS:
            raise SagaControlError("SAGA_REGISTRY_CAPACITY_REACHED")
        current.append(deepcopy(dict(saga)))
    else:
        current[existing_index] = deepcopy(dict(saga))
    state["sagas"] = current
    state["digest"] = _registry_digest(state)
    return {
        "schema": REGISTRY_SCHEMA,
        "state": "RECORDED",
        "registry": state,
        "execution_allowed": False,
        "executes_action": False,
    }


def saga_summary(saga: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(saga, Mapping):
        return {
            "schema": SCHEMA,
            "state": "UNKNOWN",
            "execution_allowed": False,
            "executes_action": False,
        }
    row = dict(saga)
    steps = [item for item in list(row.get("steps") or []) if isinstance(item, Mapping)]
    return {
        "schema": SCHEMA,
        "saga_id": row.get("saga_id"),
        "state": row.get("state"),
        "steps": len(steps),
        "confirmed_external_effects": sum(
            step.get("outcome") == "EFFECT_CONFIRMED" for step in steps
        ),
        "unknown_outcomes": sum(
            step.get("outcome") == "OUTCOME_UNKNOWN"
            or step.get("compensation_state") == "OUTCOME_UNKNOWN"
            for step in steps
        ),
        "pending_compensations": max(
            0,
            len(list(row.get("compensation_order") or []))
            - int(row.get("compensation_cursor") or 0),
        ),
        "automatic_retry_external_effect": False,
        "automatic_compensation": False,
        "execution_allowed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "REGISTRY_SCHEMA",
    "VERSION",
    "SAGA_STATES",
    "STEP_MODES",
    "STEP_OUTCOMES",
    "COMPENSATION_OUTCOMES",
    "SagaControlError",
    "new_saga",
    "validate_saga",
    "record_saga_step_outcome",
    "prepare_compensation_plan",
    "record_compensation_outcome",
    "default_saga_registry",
    "validate_saga_registry",
    "upsert_saga",
    "saga_summary",
]
