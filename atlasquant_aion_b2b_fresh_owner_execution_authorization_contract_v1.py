"""AION B2B fresh Owner execution authorization contract V1.

Design-only, fail-closed and non-executable.

This layer DOES NOT create a second authorization system. It requires reuse of
the existing cryptographic B2B execution ceremony:
atlasquant_aion_b2b_owner_renewal_action_execution_ceremony.

A generic chat acknowledgement is never an execution authorization. A positive
design result does not verify a signature, claim a nonce, persist an execution
record or authorize a business action.

Maximum positive state:
READY_FOR_FRESH_OWNER_EXECUTION_AUTHORIZATION_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_owner_renewal_action_execution_ceremony as ceremony
import atlasquant_aion_b2b_rollback_compensation_contract_v1 as rollback

SCHEMA = "ATLASQUANT_AION_B2B_FRESH_OWNER_EXECUTION_AUTHORIZATION_CONTRACT_V1"
READY = "READY_FOR_FRESH_OWNER_EXECUTION_AUTHORIZATION_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_RUNTIME_EXECUTION_GUARDS_CONTRACT_ONLY"

EXISTING_EXECUTION_CEREMONY_SCHEMA = ceremony.SCHEMA
EXISTING_EXECUTION_REQUEST_SCHEMA = ceremony.REQUEST_SCHEMA
EXISTING_EXECUTION_RESULT_SCHEMA = ceremony.RESULT_SCHEMA
REQUIRED_PURPOSE = ceremony.PURPOSE
REQUIRED_MECHANISM = ceremony.MECHANISM
REQUIRED_DECISION = "AUTHORIZE_BUSINESS_ACTION_EXECUTION"
MAX_AUTHORIZATION_WINDOW_SECONDS = ceremony.MAX_WINDOW_SECONDS

REQUIRED_PROOFS = (
    "BUSINESS_ACTION_EXECUTION_PREFLIGHT_READY",
    "HUMAN_EXECUTION_CONFIRMATION_REQUIRED",
    "EXACT_OWNER_TENANT_WORKSPACE_BINDING",
    "EXACT_CUSTOMER_PILOT_PACKAGE_BINDING",
    "EXACT_ACTION_FAMILY_OPERATION_BINDING",
    "ROLLBACK_COMPENSATION_CONTRACT_BOUND",
    "AUTHENTICATED_RECEIPT_BOUND",
    "IDEMPOTENCY_EFFECT_IDENTITY_BOUND",
    "ED25519_EXTERNAL_OWNER_EXECUTION_SIGNATURE",
    "ACTIVE_TRUST_ROOT_KEY",
    "OWNER_PUBLIC_KEY_FINGERPRINT_BOUND",
    "FRESH_NONCE_REQUIRED",
    "PERSISTENT_NONCE_REPLAY_REJECTION",
    "AUTHORIZATION_WINDOW_MAX_120_SECONDS",
    "EXECUTION_REQUEST_REBUILD_MATCH",
    "EXECUTION_DECISION_AUTHORIZE_EXPLICIT",
    "EXECUTION_RECORD_PERSISTENCE_REQUIRED",
    "EXECUTION_PERSISTENCE_ATTESTATION_REQUIRED",
    "EXECUTION_WRITER_ATTESTATION_REQUIRED",
    "GENERIC_CHAT_REJECTED_AS_EXECUTION",
    "AUTHORIZATION_SINGLE_USE",
)

REQUIRED_BINDINGS = (
    "owner_id",
    "tenant_id",
    "workspace_id",
    "customer_id",
    "pilot_id",
    "package",
    "action_family",
    "operation_kind",
    "execution_request_digest",
    "authenticated_receipt_digest",
    "idempotency_key_digest",
    "effect_key_digest",
    "rollback_plan_digest",
    "rollback_compensation_contract_digest",
    "execution_environment_digest",
    "execution_preflight_digest",
)

FALSE_FIELDS = (
    "execution_request_issued",
    "owner_execution_identity_verified",
    "owner_execution_signature_verified",
    "execution_decision_verified",
    "execution_authorization_intent_verified",
    "nonce_claimed",
    "nonce_registry_written",
    "execution_record_created",
    "execution_record_persisted",
    "persistence_attested",
    "writer_attested",
    "fresh_execution_authorization_verified",
    "generic_chat_instruction_accepted_as_execution",
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


def build_fresh_owner_execution_authorization_contract(
    *,
    rollback_compensation_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build a design contract for fresh Owner execution authorization only."""
    row = (
        dict(rollback_compensation_review)
        if isinstance(rollback_compensation_review, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != rollback.SCHEMA:
        blockers.append("ROLLBACK_COMPENSATION_SCHEMA_REQUIRED")
    if row.get("state") != rollback.READY:
        blockers.append("ROLLBACK_COMPENSATION_DESIGN_REVIEW_REQUIRED")
    if row.get("rollback_compensation_design_only") is not True:
        blockers.append("ROLLBACK_COMPENSATION_NOT_DESIGN_ONLY")
    if row.get("synthetic_rollback_is_not_production_rollback") is not True:
        blockers.append("SYNTHETIC_PRODUCTION_ROLLBACK_BOUNDARY_MISSING")
    if row.get("production_rollback_proven") is not False:
        blockers.append("PRODUCTION_ROLLBACK_MUST_REMAIN_UNPROVEN")
    if row.get("production_compensation_proven") is not False:
        blockers.append("PRODUCTION_COMPENSATION_MUST_REMAIN_UNPROVEN")
    if row.get("separate_compensation_authorization_required") is not True:
        blockers.append("SEPARATE_COMPENSATION_AUTHORIZATION_REQUIRED")
    if row.get("authorization_reuse_allowed") is not False:
        blockers.append("AUTHORIZATION_REUSE_MUST_BE_FORBIDDEN")
    if row.get("fresh_owner_authorization_required") is not True:
        blockers.append("FRESH_OWNER_AUTHORIZATION_REQUIREMENT_MISSING")
    if row.get("next_allowed_step") != rollback.NEXT_ALLOWED_STEP:
        blockers.append("ROLLBACK_COMPENSATION_NEXT_STEP_INVALID")

    for key in rollback.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("ROLLBACK_COMPENSATION_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            fresh_owner_authorization_design_only=True,
            reuses_existing_execution_ceremony=True,
            authorization_reuse_allowed=False,
            generic_chat_is_authorization=False,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        fresh_owner_authorization_design_only=True,
        provider_neutral=True,
        reuses_existing_execution_ceremony=True,
        existing_execution_ceremony_schema=EXISTING_EXECUTION_CEREMONY_SCHEMA,
        existing_execution_request_schema=EXISTING_EXECUTION_REQUEST_SCHEMA,
        existing_execution_result_schema=EXISTING_EXECUTION_RESULT_SCHEMA,
        required_purpose=REQUIRED_PURPOSE,
        required_mechanism=REQUIRED_MECHANISM,
        required_decision=REQUIRED_DECISION,
        max_authorization_window_seconds=MAX_AUTHORIZATION_WINDOW_SECONDS,
        fresh_owner_authorization_required=True,
        authorization_reuse_allowed=False,
        generic_chat_is_authorization=False,
        persistent_nonce_registry_required=True,
        execution_record_persistence_required=True,
        execution_persistence_attestation_required=True,
        execution_writer_attestation_required=True,
        exact_state_rebuild_required=True,
        single_use_authorization_required=True,
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
    "EXISTING_EXECUTION_CEREMONY_SCHEMA",
    "EXISTING_EXECUTION_REQUEST_SCHEMA",
    "EXISTING_EXECUTION_RESULT_SCHEMA",
    "REQUIRED_PURPOSE",
    "REQUIRED_MECHANISM",
    "REQUIRED_DECISION",
    "MAX_AUTHORIZATION_WINDOW_SECONDS",
    "REQUIRED_PROOFS",
    "REQUIRED_BINDINGS",
    "FALSE_FIELDS",
    "build_fresh_owner_execution_authorization_contract",
]
