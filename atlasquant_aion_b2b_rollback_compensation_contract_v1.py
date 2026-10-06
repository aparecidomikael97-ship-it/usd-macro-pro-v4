"""AION B2B rollback + compensation contract V1.

Design-only, fail-closed and non-executable.

This contract separates proven synthetic/pre-execution staging reversal from
any future real production compensation. A synthetic rollback proof MUST NOT be
promoted into a claim that a real external effect can be undone.

It does NOT call a provider, mutate production, execute a compensation,
restore state, bill, contact customers, write CRM, provision resources or
deploy.

Maximum positive state:
READY_FOR_ROLLBACK_COMPENSATION_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_idempotency_replay_contract_v1 as replay

SCHEMA = "ATLASQUANT_AION_B2B_ROLLBACK_COMPENSATION_CONTRACT_V1"
READY = "READY_FOR_ROLLBACK_COMPENSATION_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_FRESH_OWNER_EXECUTION_AUTHORIZATION_CONTRACT_ONLY"

PROVEN_SYNTHETIC_ROLLBACK_MODE = "PRE_EXECUTION_STAGING_REVERSAL_ONLY"

REVERSIBILITY_CLASSES = (
    "REVERSIBLE_PRE_EXECUTION_ONLY",
    "COMPENSATABLE_EXTERNAL_EFFECT",
    "MANUAL_REMEDIATION_REQUIRED",
    "IRREVERSIBLE_EXTERNAL_EFFECT",
)

REQUIRED_PROOFS = (
    "BEFORE_STATE_DIGEST_BOUND",
    "AFTER_STATE_DIGEST_BOUND",
    "ROLLBACK_PLAN_DIGEST_BOUND",
    "REVERSIBILITY_CLASS_EXPLICIT",
    "IRREVERSIBLE_BOUNDARY_EXPLICIT",
    "COMPENSATION_SIDE_EFFECTS_DECLARED",
    "COMPENSATION_FINOPS_IMPACT_DECLARED",
    "COMPENSATION_CUSTOMER_IMPACT_DECLARED",
    "COMPENSATION_PRECONDITIONS_DECLARED",
    "COMPENSATION_POSTCONDITIONS_DECLARED",
    "COMPENSATION_EVIDENCE_REQUIRED",
    "COMPENSATION_RECEIPT_REQUIRED",
    "SEPARATE_COMPENSATION_AUTHORIZATION_REQUIRED",
    "OUTCOME_UNKNOWN_BLOCKS_AUTOMATIC_COMPENSATION",
    "TENANT_SCOPE_BINDING_REQUIRED",
    "PROVIDER_IDENTITY_BINDING_REQUIRED",
    "IDEMPOTENCY_BINDING_REQUIRED",
)

REQUIRED_BINDINGS = (
    "owner_id",
    "tenant_id",
    "workspace_id",
    "customer_id",
    "pilot_id",
    "action_family",
    "operation_kind",
    "execution_request_digest",
    "authenticated_receipt_digest",
    "idempotency_key_digest",
    "effect_key_digest",
    "rollback_plan_digest",
    "before_state_digest",
    "after_state_digest",
    "provider_identity_ref",
)

FALSE_FIELDS = (
    "rollback_performed",
    "compensation_performed",
    "compensation_authorized",
    "state_restored",
    "production_state_changed",
    "external_effect_reversed",
    "automatic_compensation_allowed",
    "reconciliation_performed",
    "executor_created",
    "executor_selected",
    "executor_implementation_allowed",
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


def build_rollback_compensation_contract(
    *,
    idempotency_replay_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build a design-only rollback/compensation contract."""
    row = (
        dict(idempotency_replay_review)
        if isinstance(idempotency_replay_review, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != replay.SCHEMA:
        blockers.append("IDEMPOTENCY_REPLAY_SCHEMA_REQUIRED")
    if row.get("state") != replay.READY:
        blockers.append("IDEMPOTENCY_REPLAY_DESIGN_REVIEW_REQUIRED")
    if row.get("idempotency_replay_design_only") is not True:
        blockers.append("IDEMPOTENCY_REPLAY_NOT_DESIGN_ONLY")
    if row.get("reuses_existing_core_safety") is not True:
        blockers.append("CORE_SAFETY_REUSE_REQUIRED")
    if row.get("post_dispatch_ambiguity_requires_outcome_unknown") is not True:
        blockers.append("OUTCOME_UNKNOWN_REQUIREMENT_MISSING")
    if row.get("automatic_retry_after_unknown_forbidden") is not True:
        blockers.append("UNKNOWN_AUTOMATIC_RETRY_MUST_BE_FORBIDDEN")
    if row.get("explicit_reconciliation_required") is not True:
        blockers.append("EXPLICIT_RECONCILIATION_REQUIRED")
    if row.get("separate_reconciliation_authorization_required") is not True:
        blockers.append("SEPARATE_RECONCILIATION_AUTH_REQUIRED")
    if row.get("authorization_reuse_allowed") is not False:
        blockers.append("AUTHORIZATION_REUSE_MUST_BE_FORBIDDEN")
    if row.get("next_allowed_step") != replay.NEXT_ALLOWED_STEP:
        blockers.append("IDEMPOTENCY_REPLAY_NEXT_STEP_INVALID")

    for key in replay.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("IDEMPOTENCY_REPLAY_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            rollback_compensation_design_only=True,
            synthetic_rollback_is_not_production_rollback=True,
            fresh_owner_authorization_required=True,
            authorization_reuse_allowed=False,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        rollback_compensation_design_only=True,
        provider_neutral=True,
        synthetic_rollback_is_not_production_rollback=True,
        proven_synthetic_rollback_mode=PROVEN_SYNTHETIC_ROLLBACK_MODE,
        production_rollback_proven=False,
        production_compensation_proven=False,
        reversibility_classification_required=True,
        irreversible_boundary_detection_required=True,
        before_state_evidence_required=True,
        after_state_evidence_required=True,
        compensation_preconditions_required=True,
        compensation_postconditions_required=True,
        compensation_evidence_required=True,
        compensation_receipt_required=True,
        compensation_finops_guard_required=True,
        compensation_customer_impact_guard_required=True,
        separate_compensation_authorization_required=True,
        outcome_unknown_blocks_automatic_compensation=True,
        manual_reconciliation_precedes_compensation_when_unknown=True,
        fresh_owner_authorization_required=True,
        authorization_reuse_allowed=False,
        reversibility_classes=REVERSIBILITY_CLASSES,
        required_proofs=REQUIRED_PROOFS,
        required_bindings=REQUIRED_BINDINGS,
        independent_dynamic_audit_pending=bool(
            row.get("independent_dynamic_audit_pending", True)
        ),
        next_allowed_step=NEXT_ALLOWED_STEP,
    )


__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "PROVEN_SYNTHETIC_ROLLBACK_MODE",
    "REVERSIBILITY_CLASSES",
    "REQUIRED_PROOFS",
    "REQUIRED_BINDINGS",
    "FALSE_FIELDS",
    "build_rollback_compensation_contract",
]
