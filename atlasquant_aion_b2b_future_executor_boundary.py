"""AION B2B future executor boundary contract.

Design-only gate. It NEVER creates an executor, provider binding, command,
credential, network request or production mutation.

The gate intentionally remains BLOCKED until:
1) Adapter V2 owns an explicit local FinOps contract;
2) Adapter V1 is explicitly marked legacy/non-executable.

Even after those conditions are met, the maximum state is only
READY_FOR_FUTURE_EXECUTOR_DESIGN_REVIEW.
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_owner_renewal_action_adapter_plan as adapter_v1
import atlasquant_aion_b2b_owner_renewal_action_adapter_plan_v2 as adapter_v2
import atlasquant_aion_b2b_owner_renewal_action_adapter_receipt_v2 as receipt_v2

SCHEMA = "ATLASQUANT_AION_B2B_FUTURE_EXECUTOR_BOUNDARY_V1"
READY = "READY_FOR_FUTURE_EXECUTOR_DESIGN_REVIEW"
FINOPS_CAP_CENTS_REQUIRED = 20000

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


def _hardening_blockers() -> list[str]:
    blockers: list[str] = []

    if getattr(adapter_v2, "FINOPS_CAP_CENTS", None) != FINOPS_CAP_CENTS_REQUIRED:
        blockers.append("V2_FINOPS_CAP_VALUE_INVALID")
    if getattr(adapter_v2, "FINOPS_CONTRACT_SOURCE", None) != "LOCAL_V2_LITERAL":
        blockers.append("V2_FINOPS_NOT_LOCALLY_OWNED")
    if getattr(adapter_v2, "FINOPS_INPUT_TYPE", None) != "EXACT_INT":
        blockers.append("V2_FINOPS_TYPE_CONTRACT_MISSING")

    if getattr(adapter_v1, "LEGACY_NON_EXECUTABLE", None) is not True:
        blockers.append("V1_NOT_MARKED_LEGACY_NON_EXECUTABLE")
    if getattr(adapter_v1, "EXECUTOR_ELIGIBLE", None) is not False:
        blockers.append("V1_EXECUTOR_BOUNDARY_NOT_CLOSED")

    return blockers


def evaluate_future_executor_boundary(
    *,
    adapter_plan_v2: Mapping[str, Any] | None,
    synthetic_receipt_validation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Evaluate design eligibility only; never produces executable material."""
    blockers = _hardening_blockers()

    adapter_plan = dict(adapter_plan_v2) if isinstance(adapter_plan_v2, Mapping) else {}
    receipt = (
        dict(synthetic_receipt_validation)
        if isinstance(synthetic_receipt_validation, Mapping)
        else {}
    )

    if adapter_plan.get("schema") != adapter_v2.SCHEMA:
        blockers.append("ADAPTER_V2_SCHEMA_REQUIRED")
    if adapter_plan.get("state") != adapter_v2.READY:
        blockers.append("ADAPTER_V2_NOT_READY")
    if adapter_plan.get("scope_source") != "PERSISTED_EXECUTION_RECORD":
        blockers.append("ADAPTER_V2_SCOPE_PROVENANCE_INVALID")
    if adapter_plan.get("operation_kind_source") != "DERIVED_FROM_ACTION_FAMILY":
        blockers.append("ADAPTER_V2_OPERATION_PROVENANCE_INVALID")

    body = adapter_plan.get("adapter_plan")
    if not isinstance(body, Mapping):
        blockers.append("ADAPTER_V2_BODY_INVALID")
        body = {}

    if body.get("future_executor_requires_separate_contract") is not True:
        blockers.append("SEPARATE_EXECUTOR_CONTRACT_NOT_REQUIRED")

    for key in adapter_v2.FALSE_FIELDS:
        if adapter_plan.get(key) is not False:
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
    if receipt.get("actual_receipt_generated") is not False:
        blockers.append("REAL_RECEIPT_FORBIDDEN")
    if receipt.get("execution_verified") is not False:
        blockers.append("EXECUTION_VERIFICATION_FORBIDDEN")
    if receipt.get("provider_identity_authenticated") is not False:
        blockers.append("REAL_PROVIDER_AUTH_FORBIDDEN")
    if receipt.get("writer_identity_authenticated") is not False:
        blockers.append("REAL_WRITER_AUTH_FORBIDDEN")

    for key in adapter_v2.FALSE_FIELDS:
        if receipt.get(key) is not False:
            blockers.append("RECEIPT_V2_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            design_review_eligible=False,
            requires_codex_hardening=True,
            requires_red_team_reaudit=True,
            executor_contract_design_only=True,
            adapter_v1_legacy_required=True,
            adapter_v2_local_finops_required=True,
        )

    binding = body.get("binding") if isinstance(body.get("binding"), Mapping) else {}
    return _result(
        READY,
        [],
        design_review_eligible=True,
        requires_codex_hardening=False,
        requires_red_team_reaudit=True,
        executor_contract_design_only=True,
        adapter_v1_legacy_required=True,
        adapter_v2_local_finops_required=True,
        required_adapter_schema=adapter_v2.SCHEMA,
        required_receipt_schema=receipt_v2.SCHEMA,
        required_command_plan_version="V2",
        required_finops_cap_cents=FINOPS_CAP_CENTS_REQUIRED,
        binding_digest=adapter_v1.digest(binding) if binding else "",
        next_allowed_step="DESIGN_EXECUTOR_CONTRACT_ONLY",
    )


__all__ = [
    "SCHEMA",
    "READY",
    "FINOPS_CAP_CENTS_REQUIRED",
    "FALSE_FIELDS",
    "evaluate_future_executor_boundary",
]
