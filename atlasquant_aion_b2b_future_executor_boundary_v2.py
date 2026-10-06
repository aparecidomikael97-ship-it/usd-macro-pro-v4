"""AION B2B future executor boundary V2.

Design-only, fail-closed and non-executable.
This module never selects a provider, creates credentials, emits executable
commands, performs network I/O, mutates production, bills, contacts customers,
writes CRM, provisions resources or deploys.

Maximum positive state:
READY_FOR_FUTURE_EXECUTOR_DESIGN_REVIEW

That state permits design review only. It is not execution authority.
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_owner_renewal_action_command_plan as command_v1
import atlasquant_aion_b2b_owner_renewal_action_adapter_plan as adapter_v1
import atlasquant_aion_b2b_owner_renewal_action_adapter_dry_run as dry_v1
import atlasquant_aion_b2b_owner_renewal_action_adapter_receipt as receipt_v1
import atlasquant_aion_b2b_owner_renewal_action_command_plan_v2 as command_v2
import atlasquant_aion_b2b_owner_renewal_action_adapter_plan_v2 as adapter_v2
import atlasquant_aion_b2b_owner_renewal_action_adapter_dry_run_v2 as dry_v2
import atlasquant_aion_b2b_owner_renewal_action_adapter_receipt_v2 as receipt_v2
from atlasquant_aion_b2b_v2_input_contract import _MATERIAL_KEYS

SCHEMA = "ATLASQUANT_AION_B2B_FUTURE_EXECUTOR_BOUNDARY_V2"
READY = "READY_FOR_FUTURE_EXECUTOR_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_EXECUTOR_CONTRACT_ONLY"

FINOPS_CAP_CENTS_REQUIRED = 20000
MAX_ENVIRONMENT_WINDOW_SECONDS_REQUIRED = 180
ENVIRONMENT_SCHEMA_REQUIRED = "ATLASQUANT_AION_B2B_SYNTHETIC_ADAPTER_ENVIRONMENT_V1"
RISKS_REQUIRED = (
    "billing_dispute",
    "security_incident",
    "privacy_incident",
    "contract_conflict",
    "irreversible_boundary_detected",
)
DANGEROUS_MATERIAL_REQUIRED = frozenset((
    "secret", "password", "token", "api_key", "credential", "credentials",
    "cookie", "authorization", "endpoint", "url", "ip", "method", "http_method",
    "headers", "header", "payload", "body", "command", "shell", "subprocess",
    "powershell", "curl", "script", "request", "private_key", "access_token",
    "api_base", "webhook", "callback", "invoke", "transport", "provider_config",
    "connection", "secret_ref",
))

FALSE_FIELDS = (
    "executor_created",
    "executor_selected",
    "executor_contract_issued",
    "executor_generation_allowed",
    "provider_selected",
    "provider_bound",
    "provider_called",
    "network_called",
    "credential_material_included",
    "secret_material_included",
    "provider_endpoint_included",
    "http_method_included",
    "headers_included",
    "executable_payload_included",
    "execution_token_issued",
    "shell_command_generated",
    "execution_command_generated",
    "execution_command_executed",
    "business_action_authorized",
    "billing_authorized",
    "customer_contact_authorized",
    "crm_write_authorized",
    "provisioning_authorized",
    "deploy_authorized",
    "production_mutation_authorized",
    "production_mutation_performed",
    "external_action_executed",
    "executes_action",
)


def _result(state: str, blockers=(), **fields) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": state,
        "blockers": sorted(set(blockers)),
        **fields,
        **{key: False for key in FALSE_FIELDS},
    }


def _legacy_marked_non_executable(module) -> bool:
    # The stable archival marker is declarative; behavioral exclusion is proven
    # separately by the V2-only receipt contract and V2 schema validators.
    text = module.__doc__ or ""
    return "LEGACY / NON-EXECUTABLE V1" in text


def _hardening_blockers() -> list[str]:
    blockers: list[str] = []

    if adapter_v2.FINOPS_CAP_CENTS != FINOPS_CAP_CENTS_REQUIRED:
        blockers.append("V2_FINOPS_CAP_INVALID")
    if adapter_v2.MAX_ENVIRONMENT_WINDOW_SECONDS != MAX_ENVIRONMENT_WINDOW_SECONDS_REQUIRED:
        blockers.append("V2_ENVIRONMENT_WINDOW_INVALID")
    if adapter_v2.ENVIRONMENT_SCHEMA != ENVIRONMENT_SCHEMA_REQUIRED:
        blockers.append("V2_ENVIRONMENT_SCHEMA_INVALID")
    if tuple(adapter_v2.RISKS) != RISKS_REQUIRED:
        blockers.append("V2_RISKS_POLICY_INVALID")
    if not DANGEROUS_MATERIAL_REQUIRED.issubset(_MATERIAL_KEYS):
        blockers.append("V2_DANGEROUS_MATERIAL_GUARD_INCOMPLETE")

    for name, module in (
        ("COMMAND", command_v1),
        ("ADAPTER", adapter_v1),
        ("DRY_RUN", dry_v1),
        ("RECEIPT", receipt_v1),
    ):
        if not _legacy_marked_non_executable(module):
            blockers.append("V1_NOT_LEGACY_NON_EXECUTABLE:" + name)

    contract = receipt_v2.owner_renewal_action_receipt_contract_v2()
    required = {
        "required_command_plan_schema": command_v2.SCHEMA,
        "required_adapter_plan_schema": adapter_v2.SCHEMA,
        "required_dry_run_schema": dry_v2.SCHEMA,
        "required_receipt_schema": receipt_v2.SYNTHETIC_RECEIPT_SCHEMA,
        "legacy_v1_allowed": False,
        "actual_receipt_generated": False,
        "execution_verified": False,
        "provider_identity_authenticated": False,
        "writer_identity_authenticated": False,
    }
    for key, expected in required.items():
        if contract.get(key) != expected:
            blockers.append("RECEIPT_V2_CONTRACT_INVALID:" + key)

    return blockers


def evaluate_future_executor_boundary(
    *,
    adapter_plan_v2: Mapping[str, Any] | None,
    synthetic_receipt_validation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Evaluate eligibility for design review only; never execution."""
    blockers = _hardening_blockers()
    plan = dict(adapter_plan_v2) if isinstance(adapter_plan_v2, Mapping) else {}
    receipt = (
        dict(synthetic_receipt_validation)
        if isinstance(synthetic_receipt_validation, Mapping)
        else {}
    )

    if plan.get("schema") != adapter_v2.SCHEMA:
        blockers.append("ADAPTER_V2_SCHEMA_REQUIRED")
    if plan.get("state") != adapter_v2.READY:
        blockers.append("ADAPTER_V2_NOT_READY")
    if plan.get("scope_source") != "PERSISTED_EXECUTION_RECORD":
        blockers.append("ADAPTER_V2_SCOPE_PROVENANCE_INVALID")
    if plan.get("operation_kind_source") != "DERIVED_FROM_ACTION_FAMILY":
        blockers.append("ADAPTER_V2_OPERATION_PROVENANCE_INVALID")

    body = plan.get("adapter_plan")
    if type(body) is not dict:
        blockers.append("ADAPTER_V2_BODY_INVALID")
        body = {}
    if body.get("future_executor_requires_separate_contract") is not True:
        blockers.append("SEPARATE_EXECUTOR_CONTRACT_REQUIRED")

    for key in adapter_v2.FALSE_FIELDS:
        if plan.get(key) is not False:
            blockers.append("ADAPTER_V2_UNSAFE_FIELD:" + key)
        if body.get(key) is not False:
            blockers.append("ADAPTER_V2_BODY_UNSAFE_FIELD:" + key)

    if receipt.get("schema") != receipt_v2.SCHEMA:
        blockers.append("RECEIPT_V2_SCHEMA_REQUIRED")
    if receipt.get("state") != "SYNTHETIC_RECEIPT_VALIDATED":
        blockers.append("SYNTHETIC_RECEIPT_VALIDATION_REQUIRED")
    if receipt.get("command_plan_version") != "V2":
        blockers.append("RECEIPT_V2_COMMAND_PLAN_VERSION_REQUIRED")
    if receipt.get("synthetic") is not True:
        blockers.append("SYNTHETIC_RECEIPT_REQUIRED")
    for key in (
        "actual_receipt_generated",
        "execution_verified",
        "provider_identity_authenticated",
        "writer_identity_authenticated",
    ):
        if receipt.get(key) is not False:
            blockers.append("RECEIPT_REAL_AUTHORITY_FORBIDDEN:" + key)

    for key in adapter_v2.FALSE_FIELDS:
        if receipt.get(key) is not False:
            blockers.append("RECEIPT_V2_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            design_review_eligible=False,
            executor_contract_design_only=True,
            red_team_pass_required=True,
            independent_dynamic_audit_pending=True,
        )

    binding = body.get("binding") if type(body.get("binding")) is dict else {}
    return _result(
        READY,
        [],
        design_review_eligible=True,
        executor_contract_design_only=True,
        red_team_pass_required=True,
        independent_dynamic_audit_pending=True,
        required_command_plan_schema=command_v2.SCHEMA,
        required_adapter_schema=adapter_v2.SCHEMA,
        required_dry_run_schema=dry_v2.SCHEMA,
        required_receipt_schema=receipt_v2.SYNTHETIC_RECEIPT_SCHEMA,
        required_finops_cap_cents=FINOPS_CAP_CENTS_REQUIRED,
        binding_digest=adapter_v1.digest(binding) if binding else "",
        next_allowed_step=NEXT_ALLOWED_STEP,
    )


__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "FALSE_FIELDS",
    "evaluate_future_executor_boundary",
]
