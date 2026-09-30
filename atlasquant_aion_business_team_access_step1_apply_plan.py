"""AION BUSINESS Team Access Step 1 Provider Apply Plan V1.

Freezes the exact non-secret Keycloak operation shape for lifecycle Step 1
without generating an executable command and without calling the provider.
"""
from __future__ import annotations

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
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_STEP1_PROVIDER_APPLY_PLAN_V1"
VERSION = "1"

PROVIDER = "KEYCLOAK"
REALM = "atlasquant-sandbox"
HTTP_METHOD = "POST"
RELATIVE_PATH = "/admin/realms/atlasquant-sandbox/users"
EXPECTED_HTTP_STATUS = 201

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")
_SESSION32 = re.compile(r"^[0-9a-f]{32}$")


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


def step1_apply_plan_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "TEAM_ACCESS_STEP1_PROVIDER_APPLY_PLAN_POLICY_DEFINED",
        "provider": PROVIDER,
        "realm": REALM,
        "method": HTTP_METHOD,
        "relative_path": RELATIVE_PATH,
        "expected_http_status": EXPECTED_HTTP_STATUS,
        "provider_command_generated": False,
        "authorization_header_included": False,
        "access_token_included": False,
        "secret_material_included": False,
        "physical_execution_performed": False,
        "receipt_created": False,
        "ledger_append_authorized": False,
        "automatic_execution_authorized": False,
        "executor_enabled": False,
        "production_authorized": False,
        "executes_action": False,
    }


def build_step1_apply_plan(
    execution_envelope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    envelope = _mapping(execution_envelope)
    binding = verify_step1_execution_envelope(envelope)

    envelope_digest = _clean(
        envelope.get("execution_envelope_digest"), 80
    ).lower()
    plan_digest = _clean(envelope.get("plan_digest"), 80).lower()
    session_id = _clean(
        envelope.get("operator_session_id"), 64
    ).lower()
    baseline_digest = _clean(
        envelope.get("baseline_evidence_digest"), 80
    ).lower()
    username = _clean(envelope.get("target_username"), 160)
    factor = _clean(envelope.get("factor_type"), 60).upper()
    tenants = sorted(
        {
            _clean(item, 120)
            for item in list(envelope.get("tenant_ids") or [])
            if _clean(item, 120)
        }
    )

    user_representation = {
        "username": username,
        "enabled": True,
        "emailVerified": False,
        "requiredActions": [],
        "attributes": {
            "atlasquant_sandbox_only": ["true"],
            "atlasquant_operator_session_id": [session_id],
            "atlasquant_tenants": tenants,
            "atlasquant_lifecycle_step": ["1"],
        },
    }

    gates = {
        "envelope_schema_valid": envelope.get("schema") == ENVELOPE_SCHEMA,
        "envelope_binding_match": binding.get("binding_match") is True,
        "envelope_state_ready": envelope.get("state")
        == "READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_1_APPLY",
        "manual_apply_eligible": envelope.get("manual_apply_eligible") is True,
        "provider_command_not_generated": envelope.get(
            "provider_command_generated"
        ) is False,
        "physical_execution_not_performed": envelope.get(
            "physical_execution_performed"
        ) is False,
        "ledger_append_not_authorized": envelope.get(
            "ledger_append_authorized"
        ) is False,
        "automatic_execution_not_authorized": envelope.get(
            "automatic_execution_authorized"
        ) is False,
        "executor_disabled": envelope.get("executor_enabled") is False,
        "production_not_authorized": envelope.get(
            "production_authorized"
        ) is False,
        "envelope_non_executing": envelope.get("executes_action") is False,
        "envelope_digest_valid": bool(_DIGEST64.fullmatch(envelope_digest)),
        "plan_digest_valid": bool(_DIGEST64.fullmatch(plan_digest)),
        "session_valid": bool(_SESSION32.fullmatch(session_id)),
        "baseline_digest_valid": bool(_DIGEST64.fullmatch(baseline_digest)),
        "target_step_exact": bool(
            envelope.get("target_step_order") == 1
            and _clean(envelope.get("target_step_id"), 120).upper()
            == LIFECYCLE_STEP_IDS[0]
        ),
        "target_username_is_sandbox": bool(
            username and username.startswith("sandbox.")
        ),
        "tenant_scope_present": bool(tenants),
        "factor_present": bool(factor),
    }

    blockers = [name for name, passed in gates.items() if not passed]
    ready = not blockers

    provider_operation = {
        "provider": PROVIDER,
        "realm": REALM,
        "base_url_source": "LOCAL_SANDBOX_ENV",
        "method": HTTP_METHOD,
        "relative_path": RELATIVE_PATH,
        "content_type": "application/json",
        "expected_http_status": EXPECTED_HTTP_STATUS,
        "hard_stop_http_statuses": [400, 403, 409, 500],
        "body": user_representation,
        "authorization_header_included": False,
        "access_token_included": False,
        "secret_material_included": False,
    } if ready else {}

    payload = {
        "execution_envelope_digest": envelope_digest,
        "plan_digest": plan_digest,
        "operator_session_id": session_id,
        "baseline_evidence_digest": baseline_digest,
        "target_step_order": 1,
        "target_step_id": LIFECYCLE_STEP_IDS[0],
        "target_username": username,
        "tenant_ids": tenants,
        "factor_type": factor,
        "provider_operation": provider_operation,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_ADMIN_TEAM_ACCESS_STEP1_PROVIDER_APPLY_PLAN_REVIEW"
            if ready
            else "TEAM_ACCESS_STEP1_PROVIDER_APPLY_PLAN_BLOCKED"
        ),
        "gates": gates,
        "blockers": blockers,
        "execution_envelope_digest": envelope_digest if ready else "",
        "plan_digest": plan_digest if ready else "",
        "operator_session_id": session_id if ready else "",
        "baseline_evidence_digest": baseline_digest if ready else "",
        "target_step_order": 1 if ready else None,
        "target_step_id": LIFECYCLE_STEP_IDS[0] if ready else "",
        "target_username": username if ready else "",
        "tenant_ids": tenants if ready else [],
        "factor_type": factor if ready else "",
        "provider_operation": provider_operation,
        "apply_plan_digest": _digest(payload) if ready else "",
        "provider_command_generated": False,
        "powershell_command": "",
        "curl_command": "",
        "authorization_header_included": False,
        "access_token_included": False,
        "secret_material_included": False,
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


def verify_step1_apply_plan(
    apply_plan: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(apply_plan)
    operation = _mapping(row.get("provider_operation"))
    body = _mapping(operation.get("body"))
    attrs = _mapping(body.get("attributes"))

    envelope_digest = _clean(
        row.get("execution_envelope_digest"), 80
    ).lower()
    plan_digest = _clean(row.get("plan_digest"), 80).lower()
    session_id = _clean(row.get("operator_session_id"), 64).lower()
    baseline_digest = _clean(
        row.get("baseline_evidence_digest"), 80
    ).lower()
    username = _clean(row.get("target_username"), 160)
    factor = _clean(row.get("factor_type"), 60).upper()
    tenants = sorted(
        {
            _clean(item, 120)
            for item in list(row.get("tenant_ids") or [])
            if _clean(item, 120)
        }
    )
    apply_plan_digest = _clean(
        row.get("apply_plan_digest"), 80
    ).lower()

    canonical_operation = {
        "provider": PROVIDER,
        "realm": REALM,
        "base_url_source": "LOCAL_SANDBOX_ENV",
        "method": HTTP_METHOD,
        "relative_path": RELATIVE_PATH,
        "content_type": "application/json",
        "expected_http_status": EXPECTED_HTTP_STATUS,
        "hard_stop_http_statuses": [400, 403, 409, 500],
        "body": {
            "username": username,
            "enabled": True,
            "emailVerified": False,
            "requiredActions": [],
            "attributes": {
                "atlasquant_sandbox_only": ["true"],
                "atlasquant_operator_session_id": [session_id],
                "atlasquant_tenants": tenants,
                "atlasquant_lifecycle_step": ["1"],
            },
        },
        "authorization_header_included": False,
        "access_token_included": False,
        "secret_material_included": False,
    }

    payload = {
        "execution_envelope_digest": envelope_digest,
        "plan_digest": plan_digest,
        "operator_session_id": session_id,
        "baseline_evidence_digest": baseline_digest,
        "target_step_order": 1,
        "target_step_id": LIFECYCLE_STEP_IDS[0],
        "target_username": username,
        "tenant_ids": tenants,
        "factor_type": factor,
        "provider_operation": canonical_operation,
    }

    gates = {
        "schema_valid": row.get("schema") == SCHEMA,
        "state_ready": row.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_STEP1_PROVIDER_APPLY_PLAN_REVIEW",
        "envelope_digest_valid": bool(_DIGEST64.fullmatch(envelope_digest)),
        "plan_digest_valid": bool(_DIGEST64.fullmatch(plan_digest)),
        "session_valid": bool(_SESSION32.fullmatch(session_id)),
        "baseline_digest_valid": bool(_DIGEST64.fullmatch(baseline_digest)),
        "target_is_step1": bool(
            row.get("target_step_order") == 1
            and _clean(row.get("target_step_id"), 120).upper()
            == LIFECYCLE_STEP_IDS[0]
        ),
        "username_is_sandbox": bool(
            username and username.startswith("sandbox.")
        ),
        "tenant_scope_present": bool(tenants),
        "provider_exact": operation == canonical_operation,
        "body_username_exact": _clean(body.get("username"), 160) == username,
        "body_session_exact": list(
            attrs.get("atlasquant_operator_session_id") or []
        ) == [session_id],
        "body_tenants_exact": sorted(
            {
                _clean(item, 120)
                for item in list(attrs.get("atlasquant_tenants") or [])
                if _clean(item, 120)
            }
        ) == tenants,
        "credentials_absent": "credentials" not in body,
        "password_absent": "password" not in json.dumps(
            body, ensure_ascii=False
        ).lower(),
        "command_absent": bool(
            row.get("provider_command_generated") is False
            and not _clean(row.get("powershell_command"), 500)
            and not _clean(row.get("curl_command"), 500)
        ),
        "authorization_material_absent": bool(
            row.get("authorization_header_included") is False
            and row.get("access_token_included") is False
            and row.get("secret_material_included") is False
        ),
        "execution_not_performed": row.get(
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
        "executor_disabled": row.get("executor_enabled") is False,
        "production_not_authorized": row.get(
            "production_authorized"
        ) is False,
        "non_executing": row.get("executes_action") is False,
        "apply_plan_digest_valid": bool(
            _DIGEST64.fullmatch(apply_plan_digest)
        ),
        "apply_plan_digest_integrity": bool(
            _DIGEST64.fullmatch(apply_plan_digest)
            and apply_plan_digest == _digest(payload)
        ),
    }
    blockers = [name for name, passed in gates.items() if not passed]
    match = not blockers

    return {
        "schema": (
            "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_"
            "STEP1_PROVIDER_APPLY_PLAN_BINDING_V1"
        ),
        "version": VERSION,
        "state": (
            "STEP1_PROVIDER_APPLY_PLAN_BINDING_MATCH"
            if match
            else "STEP1_PROVIDER_APPLY_PLAN_BINDING_MISMATCH"
        ),
        "binding_match": match,
        "gates": gates,
        "blockers": blockers,
        "apply_plan_digest": apply_plan_digest if match else "",
        "provider_command_generated": False,
        "physical_execution_performed": False,
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
    "RELATIVE_PATH",
    "EXPECTED_HTTP_STATUS",
    "step1_apply_plan_policy",
    "build_step1_apply_plan",
    "verify_step1_apply_plan",
]
