"""AION B2B real receipt authenticator contract V1.

Design-only, provider-neutral and non-executable.

This module specifies the evidence a future authenticated real receipt verifier
must require. It does NOT verify a real signature, load a public/private key,
claim a nonce, write a replay registry, call a provider, emit credentials,
perform network I/O, mutate production, bill, contact a customer, write CRM,
provision resources or deploy.

Maximum positive state:
READY_FOR_REAL_RECEIPT_AUTHENTICATOR_DESIGN_REVIEW

A positive result authorizes design review only.
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_future_executor_capability_contract_v1 as capability

SCHEMA = "ATLASQUANT_AION_B2B_REAL_RECEIPT_AUTHENTICATOR_CONTRACT_V1"
READY = "READY_FOR_REAL_RECEIPT_AUTHENTICATOR_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_IDEMPOTENCY_REPLAY_CONTRACT_ONLY"

SIGNATURE_ALGORITHM_REQUIRED = "ED25519"
DIGEST_ALGORITHM_REQUIRED = "SHA256"
KEY_STATUS_REQUIRED = "ACTIVE"

REQUIRED_SIGNED_BINDINGS = (
    "owner_id",
    "tenant_id",
    "workspace_id",
    "customer_id",
    "pilot_id",
    "package",
    "action_family",
    "operation_kind",
    "execution_request_digest",
    "execution_record_digest",
    "execution_intent_writer_request_digest",
    "command_plan_digest",
    "adapter_plan_digest",
    "dry_run_digest",
    "rollback_plan_digest",
    "idempotency_key_digest",
    "before_state_digest",
    "after_state_digest",
    "provider_identity_ref",
    "writer_identity_ref",
    "issued_at",
    "expires_at",
    "nonce",
    "key_id",
    "key_version",
)

REQUIRED_VERIFIER_PROOFS = (
    "CANONICAL_RECEIPT_SCHEMA",
    "ED25519_SIGNATURE_VALID",
    "TRUST_ROOT_KEY_RESOLUTION",
    "KEY_STATUS_ACTIVE",
    "KEY_VERSION_MATCH",
    "KEY_NOT_BEFORE_SATISFIED",
    "KEY_NOT_AFTER_SATISFIED",
    "RECEIPT_FRESHNESS_VALID",
    "NONCE_FORMAT_VALID",
    "NONCE_NOT_PREVIOUSLY_CONSUMED",
    "TENANT_SCOPE_BINDING_VALID",
    "PROVIDER_IDENTITY_BINDING_VALID",
    "WRITER_IDENTITY_BINDING_VALID",
    "EXECUTION_REQUEST_BINDING_VALID",
    "COMMAND_PLAN_BINDING_VALID",
    "ADAPTER_PLAN_BINDING_VALID",
    "DRY_RUN_BINDING_VALID",
    "ROLLBACK_BINDING_VALID",
    "IDEMPOTENCY_BINDING_VALID",
    "BEFORE_AFTER_STATE_BINDING_VALID",
)

FORBIDDEN_IMPLEMENTATION_MATERIAL = (
    "private_key",
    "secret_key",
    "credential",
    "token",
    "provider_endpoint",
    "http_method",
    "headers",
    "payload",
    "shell_command",
    "executable_command",
    "production_target",
)

FALSE_FIELDS = (
    "real_receipt_verified",
    "signature_verified",
    "nonce_claimed",
    "replay_registry_written",
    "trust_root_read_performed",
    "key_material_loaded",
    "private_key_loaded",
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


def build_real_receipt_authenticator_contract(
    *,
    capability_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build an abstract real-receipt verifier contract; never authenticate."""
    row = dict(capability_review) if isinstance(capability_review, Mapping) else {}
    blockers: list[str] = []

    if row.get("schema") != capability.SCHEMA:
        blockers.append("CAPABILITY_CONTRACT_SCHEMA_REQUIRED")
    if row.get("state") != capability.READY:
        blockers.append("CAPABILITY_DESIGN_REVIEW_REQUIRED")
    if row.get("capability_design_only") is not True:
        blockers.append("CAPABILITY_CONTRACT_NOT_DESIGN_ONLY")
    if row.get("provider_neutral") is not True:
        blockers.append("CAPABILITY_CONTRACT_NOT_PROVIDER_NEUTRAL")
    if row.get("fresh_owner_authorization_required") is not True:
        blockers.append("FRESH_OWNER_AUTHORIZATION_REQUIREMENT_MISSING")
    if row.get("authorization_reuse_allowed") is not False:
        blockers.append("AUTHORIZATION_REUSE_MUST_BE_FORBIDDEN")
    if row.get("real_receipt_authenticator_required") is not True:
        blockers.append("REAL_RECEIPT_AUTHENTICATOR_REQUIREMENT_MISSING")
    if row.get("next_allowed_step") != capability.NEXT_ALLOWED_STEP:
        blockers.append("CAPABILITY_NEXT_STEP_INVALID")

    for key in capability.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("CAPABILITY_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            authenticator_design_only=True,
            fresh_owner_authorization_required=True,
            authorization_reuse_allowed=False,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        authenticator_design_only=True,
        provider_neutral=True,
        signature_algorithm_required=SIGNATURE_ALGORITHM_REQUIRED,
        digest_algorithm_required=DIGEST_ALGORITHM_REQUIRED,
        trust_root_required=True,
        key_lifecycle_validation_required=True,
        key_status_required=KEY_STATUS_REQUIRED,
        key_version_binding_required=True,
        key_not_before_required=True,
        key_not_after_required=True,
        receipt_freshness_required=True,
        nonce_required=True,
        persistent_nonce_registry_required=True,
        replay_rejection_required=True,
        exact_scope_binding_required=True,
        provider_identity_binding_required=True,
        writer_identity_binding_required=True,
        canonical_serialization_required=True,
        required_signed_bindings=REQUIRED_SIGNED_BINDINGS,
        required_verifier_proofs=REQUIRED_VERIFIER_PROOFS,
        forbidden_implementation_material=FORBIDDEN_IMPLEMENTATION_MATERIAL,
        fresh_owner_authorization_required=True,
        authorization_reuse_allowed=False,
        independent_dynamic_audit_pending=bool(
            row.get("independent_dynamic_audit_pending", True)
        ),
        next_allowed_step=NEXT_ALLOWED_STEP,
    )


__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "SIGNATURE_ALGORITHM_REQUIRED",
    "DIGEST_ALGORITHM_REQUIRED",
    "KEY_STATUS_REQUIRED",
    "REQUIRED_SIGNED_BINDINGS",
    "REQUIRED_VERIFIER_PROOFS",
    "FORBIDDEN_IMPLEMENTATION_MATERIAL",
    "FALSE_FIELDS",
    "build_real_receipt_authenticator_contract",
]
