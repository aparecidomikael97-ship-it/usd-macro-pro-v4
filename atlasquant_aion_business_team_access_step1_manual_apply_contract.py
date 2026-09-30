"""AION BUSINESS Team Access Step 1 Manual Apply Contract V1.

Produces a short-lived, non-executing provider apply specification for Step 1
after the execution envelope and all of its source bindings have been verified.

This module never performs an HTTP request, never handles a bearer token, never
calls Keycloak and never creates a user.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping
import json
import re

from atlasquant_aion_business_team_access_sandbox_lifecycle_plan import (
    LIFECYCLE_STEP_IDS,
)
from atlasquant_aion_business_team_access_step1_execution_envelope import (
    SCHEMA as ENVELOPE_SCHEMA,
    verify_step1_execution_envelope,
    verify_step1_execution_envelope_source_binding,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_STEP1_MANUAL_APPLY_CONTRACT_V1"
VERSION = "1"

PROVIDER = "KEYCLOAK"
REALM = "atlasquant-sandbox"
HTTP_METHOD = "POST"
RESOURCE_PATH = "/admin/realms/atlasquant-sandbox/users"
EXPECTED_SUCCESS_STATUS = 201
CONFLICT_STATUS = 409
MAX_CONTRACT_AGE_SECONDS = 60

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


def _parse_time(value: Any) -> datetime | None:
    token = _clean(value, 100)
    if not token:
        return None
    try:
        parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def step1_manual_apply_contract_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "TEAM_ACCESS_STEP1_MANUAL_APPLY_CONTRACT_POLICY_DEFINED",
        "provider": PROVIDER,
        "realm": REALM,
        "http_method": HTTP_METHOD,
        "resource_path": RESOURCE_PATH,
        "expected_success_status": EXPECTED_SUCCESS_STATUS,
        "conflict_status": CONFLICT_STATUS,
        "max_contract_age_seconds": MAX_CONTRACT_AGE_SECONDS,
        "source_binding_required": True,
        "secret_material_allowed": False,
        "provider_command_generated": False,
        "http_request_executed": False,
        "physical_execution_performed": False,
        "automatic_execution_authorized": False,
        "executor_enabled": False,
        "production_authorized": False,
        "executes_action": False,
    }


def build_step1_manual_apply_contract(
    materialization: Mapping[str, Any] | None,
    preflight_packet: Mapping[str, Any] | None,
    decision_record: Mapping[str, Any] | None,
    execution_envelope: Mapping[str, Any] | None,
    *,
    evaluated_at: Any,
) -> dict[str, Any]:
    envelope = _mapping(execution_envelope)
    envelope_binding = verify_step1_execution_envelope(envelope)
    source_binding = verify_step1_execution_envelope_source_binding(
        materialization,
        preflight_packet,
        decision_record,
        envelope,
    )

    prepared_at = _parse_time(envelope.get("prepared_at"))
    evaluated = _parse_time(evaluated_at)
    contract_age_seconds = (
        (evaluated - prepared_at).total_seconds()
        if evaluated is not None and prepared_at is not None
        else None
    )

    target_username = _clean(envelope.get("target_username"), 160)
    tenant_ids = sorted(
        {
            _clean(item, 120)
            for item in list(envelope.get("tenant_ids") or [])
            if _clean(item, 120)
        }
    )
    factor_type = _clean(envelope.get("factor_type"), 60).upper()

    gates = {
        "envelope_schema_valid": envelope.get("schema") == ENVELOPE_SCHEMA,
        "envelope_state_ready": envelope.get("state")
        == "READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_1_APPLY",
        "envelope_binding_match": envelope_binding.get(
            "binding_match"
        ) is True,
        "source_binding_match": source_binding.get(
            "binding_match"
        ) is True,
        "evaluated_at_valid": evaluated is not None,
        "envelope_prepared_at_valid": prepared_at is not None,
        "contract_not_future": bool(
            contract_age_seconds is not None
            and contract_age_seconds >= 0
        ),
        "contract_still_fresh": bool(
            contract_age_seconds is not None
            and 0 <= contract_age_seconds <= MAX_CONTRACT_AGE_SECONDS
        ),
        "target_step_exact": bool(
            envelope.get("target_step_order") == 1
            and _clean(envelope.get("target_step_id"), 120).upper()
            == LIFECYCLE_STEP_IDS[0]
        ),
        "sandbox_username": bool(
            target_username and target_username.startswith("sandbox.")
        ),
        "tenant_scope_present": bool(tenant_ids),
        "manual_apply_eligible": envelope.get(
            "manual_apply_eligible"
        ) is True,
        "provider_command_absent": envelope.get(
            "provider_command_generated"
        ) is False,
        "physical_execution_absent": envelope.get(
            "physical_execution_performed"
        ) is False,
        "receipt_absent": envelope.get(
            "step_execution_receipt_present"
        ) is False,
        "ledger_append_not_authorized": envelope.get(
            "ledger_append_authorized"
        ) is False,
        "automatic_execution_off": envelope.get(
            "automatic_execution_authorized"
        ) is False,
        "executor_disabled": envelope.get("executor_enabled") is False,
        "production_not_authorized": envelope.get(
            "production_authorized"
        ) is False,
        "deploy_not_authorized": envelope.get(
            "deploy_authorized"
        ) is False,
        "runtime_not_authorized": envelope.get(
            "runtime_authorized"
        ) is False,
        "non_executing_envelope": envelope.get("executes_action") is False,
    }

    blockers = [name for name, passed in gates.items() if not passed]
    ready = not blockers

    request_body = {
        "username": target_username,
        "enabled": True,
    } if ready else {}

    operator_spec = {
        "provider": PROVIDER,
        "realm": REALM,
        "operation": "CREATE_INDIVIDUAL_SANDBOX_ACCOUNT",
        "http_method": HTTP_METHOD,
        "resource_path": RESOURCE_PATH,
        "content_type": "application/json",
        "request_body": request_body,
        "expected_success_status": EXPECTED_SUCCESS_STATUS,
        "terminal_conflict_status": CONFLICT_STATUS,
        "authorization_material_required_at_operator_time": True,
        "authorization_material_included": False,
        "base_url_included": False,
        "provider_command_included": False,
        "provider_command_generated": False,
        "http_request_executed": False,
    } if ready else {}

    postconditions = {
        "provider_status_must_equal": EXPECTED_SUCCESS_STATUS,
        "created_user_id_required": True,
        "exact_username_readback_required": True,
        "enabled_readback_required": True,
        "duplicate_username_forbidden": True,
        "post_execution_receipt_required": True,
        "automatic_ledger_append_forbidden": True,
        "cleanup_review_required_on_partial_failure": True,
    } if ready else {}

    payload = {
        "execution_envelope_digest": _clean(
            envelope.get("execution_envelope_digest"), 80
        ).lower(),
        "execution_observation_digest": _clean(
            envelope.get("execution_observation_digest"), 80
        ).lower(),
        "materialization_digest": _clean(
            envelope.get("materialization_digest"), 80
        ).lower(),
        "step1_packet_digest": _clean(
            envelope.get("step1_packet_digest"), 80
        ).lower(),
        "decision_record_digest": _clean(
            envelope.get("decision_record_digest"), 80
        ).lower(),
        "plan_digest": _clean(envelope.get("plan_digest"), 80).lower(),
        "target_step_order": 1,
        "target_step_id": LIFECYCLE_STEP_IDS[0],
        "target_username": target_username,
        "tenant_ids": tenant_ids,
        "factor_type": factor_type,
        "evaluated_at": (
            evaluated.isoformat() if evaluated is not None else ""
        ),
        "operator_spec": operator_spec,
        "postconditions": postconditions,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_OPERATOR_REVIEW_OF_SANDBOX_STEP_1_APPLY_SPEC"
            if ready
            else "TEAM_ACCESS_STEP1_MANUAL_APPLY_CONTRACT_BLOCKED"
        ),
        "gates": gates,
        "blockers": blockers,
        "contract_age_seconds": contract_age_seconds,
        "manual_apply_contract_digest": _digest(payload) if ready else "",
        "execution_envelope_digest": _clean(
            envelope.get("execution_envelope_digest"), 80
        ).lower() if ready else "",
        "target_step_order": 1 if ready else None,
        "target_step_id": LIFECYCLE_STEP_IDS[0] if ready else "",
        "target_username": target_username if ready else "",
        "tenant_ids": tenant_ids if ready else [],
        "factor_type": factor_type if ready else "",
        "evaluated_at": (
            evaluated.isoformat()
            if ready and evaluated is not None
            else ""
        ),
        "operator_spec": operator_spec,
        "postconditions": postconditions,
        "manual_operator_review_required": True,
        "manual_apply_performed": False,
        "provider_command_generated": False,
        "http_request_executed": False,
        "physical_execution_performed": False,
        "step_execution_receipt_present": False,
        "ledger_append_authorized": False,
        "automatic_execution_authorized": False,
        "automatic_ledger_append": False,
        "executor_enabled": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


def verify_step1_manual_apply_contract(
    contract: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(contract)
    operator_spec = _mapping(row.get("operator_spec"))
    postconditions = _mapping(row.get("postconditions"))

    contract_digest = _clean(
        row.get("manual_apply_contract_digest"), 80
    ).lower()
    envelope_digest = _clean(
        row.get("execution_envelope_digest"), 80
    ).lower()
    target_username = _clean(row.get("target_username"), 160)
    tenant_ids = sorted(
        {
            _clean(item, 120)
            for item in list(row.get("tenant_ids") or [])
            if _clean(item, 120)
        }
    )
    factor_type = _clean(row.get("factor_type"), 60).upper()
    evaluated_at = _parse_time(row.get("evaluated_at"))

    payload = {
        "execution_envelope_digest": envelope_digest,
        "execution_observation_digest": _clean(
            row.get("execution_observation_digest"), 80
        ).lower(),
        "materialization_digest": _clean(
            row.get("materialization_digest"), 80
        ).lower(),
        "step1_packet_digest": _clean(
            row.get("step1_packet_digest"), 80
        ).lower(),
        "decision_record_digest": _clean(
            row.get("decision_record_digest"), 80
        ).lower(),
        "plan_digest": _clean(row.get("plan_digest"), 80).lower(),
        "target_step_order": 1,
        "target_step_id": LIFECYCLE_STEP_IDS[0],
        "target_username": target_username,
        "tenant_ids": tenant_ids,
        "factor_type": factor_type,
        "evaluated_at": (
            evaluated_at.isoformat() if evaluated_at is not None else ""
        ),
        "operator_spec": operator_spec,
        "postconditions": postconditions,
    }

    gates = {
        "schema_valid": row.get("schema") == SCHEMA,
        "state_ready": row.get("state")
        == "READY_FOR_OPERATOR_REVIEW_OF_SANDBOX_STEP_1_APPLY_SPEC",
        "contract_digest_valid": bool(_DIGEST64.fullmatch(contract_digest)),
        "contract_digest_integrity": bool(
            _DIGEST64.fullmatch(contract_digest)
            and contract_digest == _digest(payload)
        ),
        "envelope_digest_valid": bool(_DIGEST64.fullmatch(envelope_digest)),
        "target_step_exact": bool(
            row.get("target_step_order") == 1
            and _clean(row.get("target_step_id"), 120).upper()
            == LIFECYCLE_STEP_IDS[0]
        ),
        "sandbox_username": bool(
            target_username and target_username.startswith("sandbox.")
        ),
        "tenant_scope_present": bool(tenant_ids),
        "evaluated_at_valid": evaluated_at is not None,
        "provider_exact": operator_spec.get("provider") == PROVIDER,
        "realm_exact": operator_spec.get("realm") == REALM,
        "method_exact": operator_spec.get("http_method") == HTTP_METHOD,
        "resource_path_exact": operator_spec.get(
            "resource_path"
        ) == RESOURCE_PATH,
        "success_status_exact": operator_spec.get(
            "expected_success_status"
        ) == EXPECTED_SUCCESS_STATUS,
        "conflict_status_exact": operator_spec.get(
            "terminal_conflict_status"
        ) == CONFLICT_STATUS,
        "request_body_exact": _mapping(
            operator_spec.get("request_body")
        ) == {
            "username": target_username,
            "enabled": True,
        },
        "authorization_material_absent": operator_spec.get(
            "authorization_material_included"
        ) is False,
        "base_url_absent": operator_spec.get("base_url_included") is False,
        "provider_command_absent": operator_spec.get(
            "provider_command_included"
        ) is False
        and operator_spec.get("provider_command_generated") is False,
        "http_request_not_executed": operator_spec.get(
            "http_request_executed"
        ) is False,
        "post_execution_receipt_required": postconditions.get(
            "post_execution_receipt_required"
        ) is True,
        "automatic_ledger_append_forbidden": postconditions.get(
            "automatic_ledger_append_forbidden"
        ) is True,
        "manual_operator_review_required": row.get(
            "manual_operator_review_required"
        ) is True,
        "manual_apply_not_performed": row.get(
            "manual_apply_performed"
        ) is False,
        "physical_execution_not_performed": row.get(
            "physical_execution_performed"
        ) is False,
        "receipt_absent": row.get(
            "step_execution_receipt_present"
        ) is False,
        "ledger_append_not_authorized": row.get(
            "ledger_append_authorized"
        ) is False,
        "automatic_execution_off": row.get(
            "automatic_execution_authorized"
        ) is False,
        "automatic_ledger_append_off": row.get(
            "automatic_ledger_append"
        ) is False,
        "executor_disabled": row.get("executor_enabled") is False,
        "production_not_authorized": row.get(
            "production_authorized"
        ) is False,
        "deploy_not_authorized": row.get("deploy_authorized") is False,
        "runtime_not_authorized": row.get("runtime_authorized") is False,
        "non_executing": row.get("executes_action") is False,
    }
    blockers = [name for name, passed in gates.items() if not passed]
    match = not blockers

    return {
        "schema": (
            "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_"
            "STEP1_MANUAL_APPLY_CONTRACT_BINDING_V1"
        ),
        "version": VERSION,
        "state": (
            "STEP1_MANUAL_APPLY_CONTRACT_BINDING_MATCH"
            if match
            else "STEP1_MANUAL_APPLY_CONTRACT_BINDING_MISMATCH"
        ),
        "binding_match": match,
        "gates": gates,
        "blockers": blockers,
        "manual_apply_contract_digest": contract_digest if match else "",
        "manual_apply_performed": False,
        "provider_command_generated": False,
        "http_request_executed": False,
        "physical_execution_performed": False,
        "ledger_append_authorized": False,
        "automatic_execution_authorized": False,
        "executor_enabled": False,
        "production_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "PROVIDER",
    "REALM",
    "HTTP_METHOD",
    "RESOURCE_PATH",
    "EXPECTED_SUCCESS_STATUS",
    "CONFLICT_STATUS",
    "MAX_CONTRACT_AGE_SECONDS",
    "step1_manual_apply_contract_policy",
    "build_step1_manual_apply_contract",
    "verify_step1_manual_apply_contract",
]
