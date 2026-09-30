"""AION BUSINESS Team Access Sandbox Lifecycle Step Gate V1.

Provides a read-only preflight for exactly one next sandbox lifecycle step and a
post-step receipt review. It never executes the step, never calls providers and
never appends to the ledger automatically.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json
import re

from atlasquant_access_control import normalize_username
from atlasquant_aion_business_team_access_sandbox_lifecycle_plan import (
    SCHEMA as PLAN_SCHEMA,
    LIFECYCLE_STEP_IDS,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_authorization import (
    SCHEMA as AUTH_SCHEMA,
    verify_authorization_binding,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_evidence_ledger import (
    SCHEMA as LEDGER_SCHEMA,
    RECEIPT_SCHEMA,
    build_evidence_receipt,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_SANDBOX_LIFECYCLE_STEP_GATE_V1"
VERSION = "1"

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def _ledger_ready_for_next(ledger: Mapping[str, Any]) -> bool:
    return bool(
        ledger.get("schema") == LEDGER_SCHEMA
        and ledger.get("state")
        in (
            "READY_FOR_FIRST_SANDBOX_LIFECYCLE_STEP",
            "READY_FOR_NEXT_SANDBOX_LIFECYCLE_STEP",
        )
        and ledger.get("ledger_complete") is False
        and _DIGEST64.fullmatch(_clean(ledger.get("ledger_digest"), 80).lower())
        and _DIGEST64.fullmatch(
            _clean(ledger.get("chain_head_digest"), 80).lower()
        )
        and ledger.get("automatic_next_step_authorized") is False
        and ledger.get("executor_enabled") is False
        and ledger.get("production_authorized") is False
        and ledger.get("executes_action") is False
    )


def step_gate_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "TEAM_ACCESS_SANDBOX_STEP_GATE_POLICY_DEFINED",
        "one_step_at_a_time": True,
        "fresh_baseline_binding_required": True,
        "sandbox_health_required": True,
        "cleanup_path_required": True,
        "explicit_step_decision_required": True,
        "automatic_step_execution": False,
        "automatic_ledger_append": False,
        "production_authorized": False,
        "executes_action": False,
    }


def build_step_execution_preflight(
    plan: Mapping[str, Any] | None,
    authorization_record: Mapping[str, Any] | None,
    ledger: Mapping[str, Any] | None,
    *,
    target_step_order: Any,
    baseline_evidence_digest_observed: Any,
    sandbox_health_verified: Any,
    oidc_verified: Any,
    registry_schema_verified: Any,
    secrets_local: Any,
    production_targets_absent: Any,
    cleanup_path_ready: Any,
    requested_by: Any,
) -> dict[str, Any]:
    plan_row = _mapping(plan)
    auth = _mapping(authorization_record)
    ledger_row = _mapping(ledger)

    order = (
        target_step_order
        if isinstance(target_step_order, int)
        and not isinstance(target_step_order, bool)
        else None
    )
    expected_order = ledger_row.get("next_expected_step_order")
    expected_step = _clean(
        ledger_row.get("next_expected_step_id"), 120
    ).upper()
    plan_digest = _clean(plan_row.get("plan_digest"), 80).lower()
    baseline_digest = _clean(
        plan_row.get("baseline_evidence_digest"), 80
    ).lower()
    observed_baseline = _clean(
        baseline_evidence_digest_observed, 80
    ).lower()
    requester = normalize_username(requested_by)
    approved_by = normalize_username(auth.get("approved_by"))

    auth_binding = verify_authorization_binding(plan_row, auth)
    plan_steps = list(plan_row.get("steps") or [])
    target_row = (
        dict(plan_steps[order - 1])
        if order is not None
        and 1 <= order <= len(plan_steps)
        and isinstance(plan_steps[order - 1], Mapping)
        else {}
    )

    gates = {
        "plan_ready": bool(
            plan_row.get("schema") == PLAN_SCHEMA
            and plan_row.get("state")
            == "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_EXECUTION_DECISION"
            and _DIGEST64.fullmatch(plan_digest)
            and _DIGEST64.fullmatch(baseline_digest)
            and plan_row.get("executes_action") is False
        ),
        "authorization_binding_match": auth_binding.get("binding_match") is True,
        "authorization_manual_scope": bool(
            auth.get("schema") == AUTH_SCHEMA
            and auth.get("sandbox_lifecycle_manual_execution_authorized") is True
            and auth.get("automatic_execution_authorized") is False
            and auth.get("executor_enabled") is False
            and auth.get("production_authorized") is False
        ),
        "ledger_ready_for_next": _ledger_ready_for_next(ledger_row),
        "target_is_next_step": bool(
            order is not None
            and order == expected_order
            and expected_step
            and expected_step == _clean(target_row.get("id"), 120).upper()
            and expected_step == LIFECYCLE_STEP_IDS[order - 1]
        ),
        "baseline_digest_unchanged": bool(
            _DIGEST64.fullmatch(observed_baseline)
            and observed_baseline == baseline_digest
        ),
        "sandbox_health_verified": sandbox_health_verified is True,
        "oidc_verified": oidc_verified is True,
        "registry_schema_verified": registry_schema_verified is True,
        "secrets_local": secrets_local is True,
        "production_targets_absent": production_targets_absent is True,
        "cleanup_path_ready": cleanup_path_ready is True,
        "requester_matches_authorization": bool(
            requester and approved_by and requester == approved_by
        ),
    }
    blockers = [name for name, passed in gates.items() if not passed]
    ready = not blockers

    step_token = (
        f"AUTHORIZE_SANDBOX_LIFECYCLE_STEP_{order}_{expected_step}"
        if ready
        else ""
    )
    payload = {
        "plan_digest": plan_digest,
        "authorization_record_digest": _clean(
            auth.get("record_digest"), 80
        ).lower(),
        "ledger_digest": _clean(ledger_row.get("ledger_digest"), 80).lower(),
        "chain_head_digest": _clean(
            ledger_row.get("chain_head_digest"), 80
        ).lower(),
        "target_step_order": order,
        "target_step_id": expected_step,
        "baseline_evidence_digest": observed_baseline,
        "requested_by": requester,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_DECISION"
            if ready
            else "SANDBOX_LIFECYCLE_STEP_PREFLIGHT_BLOCKED"
        ),
        "gates": gates,
        "blockers": blockers,
        "target_step_order": order if ready else None,
        "target_step_id": expected_step if ready else "",
        "target_step_mutation": target_row.get("mutation")
        if ready
        else None,
        "preflight_digest": _digest(payload) if ready else "",
        "required_step_decision_token": step_token,
        "manual_apply_required": True,
        "step_execution_authorized": False,
        "automatic_execution_authorized": False,
        "automatic_ledger_append": False,
        "executor_enabled": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


def review_post_step_receipt(
    plan: Mapping[str, Any] | None,
    authorization_record: Mapping[str, Any] | None,
    ledger_before: Mapping[str, Any] | None,
    receipt: Mapping[str, Any] | None,
) -> dict[str, Any]:
    plan_row = _mapping(plan)
    auth = _mapping(authorization_record)
    ledger = _mapping(ledger_before)
    row = _mapping(receipt)

    expected_order = ledger.get("next_expected_step_order")
    expected_step = _clean(
        ledger.get("next_expected_step_id"), 120
    ).upper()
    chain_head = _clean(ledger.get("chain_head_digest"), 80).lower()

    recomputed = build_evidence_receipt(
        plan_row,
        auth,
        step_order=row.get("step_order"),
        step_id=row.get("step_id"),
        evidence_digest=row.get("evidence_digest"),
        observed_at=row.get("observed_at"),
        previous_entry_digest=row.get("previous_entry_digest"),
        mutation_observed=row.get("mutation_observed"),
        sandbox_only=row.get("sandbox_only"),
        production_targeted=row.get("production_targeted"),
        secret_material_included=row.get("secret_material_included"),
    )

    gates = {
        "ledger_ready_for_next": _ledger_ready_for_next(ledger),
        "receipt_schema_valid": row.get("schema") == RECEIPT_SCHEMA,
        "receipt_state_ready": row.get("state")
        == "SANDBOX_LIFECYCLE_STEP_EVIDENCE_RECEIPT_READY",
        "receipt_is_expected_step": bool(
            row.get("step_order") == expected_order
            and _clean(row.get("step_id"), 120).upper() == expected_step
        ),
        "receipt_chain_matches": bool(
            _clean(row.get("previous_entry_digest"), 80).lower()
            == chain_head
        ),
        "receipt_integrity_verified": bool(
            recomputed.get("state")
            == "SANDBOX_LIFECYCLE_STEP_EVIDENCE_RECEIPT_READY"
            and _clean(recomputed.get("receipt_digest"), 80).lower()
            == _clean(row.get("receipt_digest"), 80).lower()
        ),
        "raw_evidence_absent": row.get("raw_evidence_stored") is False,
        "executor_disabled": row.get("executor_enabled") is False,
        "production_not_authorized": row.get("production_authorized") is False,
        "non_executing_receipt": row.get("executes_action") is False,
    }
    blockers = [name for name, passed in gates.items() if not passed]
    ready = not blockers

    payload = {
        "ledger_digest_before": _clean(ledger.get("ledger_digest"), 80).lower(),
        "chain_head_before": chain_head,
        "receipt_digest": _clean(row.get("receipt_digest"), 80).lower(),
        "step_order": expected_order,
        "step_id": expected_step,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_MANUAL_LEDGER_APPEND_REVIEW"
            if ready
            else "POST_STEP_RECEIPT_REVIEW_BLOCKED"
        ),
        "gates": gates,
        "blockers": blockers,
        "step_order": expected_order if ready else None,
        "step_id": expected_step if ready else "",
        "review_digest": _digest(payload) if ready else "",
        "ledger_append_authorized": False,
        "automatic_next_step_authorized": False,
        "executor_enabled": False,
        "production_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "step_gate_policy",
    "build_step_execution_preflight",
    "review_post_step_receipt",
]
