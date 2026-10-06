"""AION B2B execution envelope contract V1.

Design-only, immutable-binding and non-executable.

The envelope is a future sealed proof container. It binds upstream evidence by
reference/digest only. It never contains live credentials, provider endpoints,
request payloads, HTTP material, shell commands or executable instructions.

Maximum positive state:
READY_FOR_EXECUTION_ENVELOPE_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_provider_capability_binding_contract_v1 as binding

SCHEMA = "ATLASQUANT_AION_B2B_EXECUTION_ENVELOPE_CONTRACT_V1"
READY = "READY_FOR_EXECUTION_ENVELOPE_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_PRE_DISPATCH_ATTESTATION_CONTRACT_ONLY"

ENVELOPE_MODE = "SEALED_DIGEST_REFERENCES_ONLY"
MAX_ENVELOPE_WINDOW_SECONDS = 120

REQUIRED_ENVELOPE_BINDINGS = (
    "owner_id",
    "tenant_id",
    "workspace_id",
    "domain",
    "customer_id",
    "pilot_id",
    "package",
    "action_family",
    "operation_kind",
    "execution_request_digest",
    "fresh_owner_authorization_digest",
    "authenticated_receipt_digest",
    "command_plan_digest",
    "adapter_plan_digest",
    "dry_run_digest",
    "rollback_plan_digest",
    "idempotency_key_digest",
    "effect_key_digest",
    "rollback_compensation_contract_digest",
    "runtime_execution_guards_digest",
    "provider_adapter_attestation_digest",
    "provider_capability_binding_digest",
    "effective_capabilities_digest",
    "provider_identity_ref",
    "finops_ceiling_digest",
    "before_state_digest",
    "expected_postcondition_digest",
    "issued_at",
    "expires_at",
    "envelope_nonce_digest",
)

REQUIRED_ENVELOPE_RULES = (
    "ALL_UPSTREAM_DIGESTS_REQUIRED",
    "EXACT_SCOPE_BINDING_REQUIRED",
    "EXACT_ACTION_OPERATION_BINDING_REQUIRED",
    "FRESH_OWNER_AUTHORIZATION_MUST_STILL_BE_VALID",
    "ENVELOPE_WINDOW_NOT_GREATER_THAN_AUTHORIZATION_WINDOW",
    "MAX_ENVELOPE_WINDOW_120_SECONDS",
    "AUTHORIZATION_SINGLE_USE_PRESERVED",
    "IDEMPOTENCY_BINDING_PRESERVED",
    "EFFECT_KEY_BINDING_PRESERVED",
    "CAPABILITY_BINDING_PRESERVED",
    "ROLLBACK_COMPENSATION_BINDING_PRESERVED",
    "FINOPS_CEILING_PRESERVED",
    "BEFORE_STATE_EVIDENCE_REQUIRED",
    "EXPECTED_POSTCONDITION_BOUND",
    "PROVIDER_IDENTITY_REFERENCE_ONLY",
    "NO_ENDPOINT_MATERIAL",
    "NO_CREDENTIAL_MATERIAL",
    "NO_REQUEST_PAYLOAD_MATERIAL",
    "NO_HTTP_MATERIAL",
    "NO_SHELL_OR_SUBPROCESS_MATERIAL",
    "NO_IMPLICIT_EXECUTION_AUTHORITY",
    "ENVELOPE_DIGEST_REQUIRED",
    "ENVELOPE_NONCE_REQUIRED",
    "ENVELOPE_SINGLE_USE_REQUIRED",
    "TAMPER_REBUILD_MISMATCH_BLOCKS",
)

FORBIDDEN_ENVELOPE_MATERIAL = (
    "credential",
    "secret",
    "password",
    "api_key",
    "access_token",
    "refresh_token",
    "private_key",
    "authorization_header",
    "cookie",
    "endpoint",
    "url",
    "webhook",
    "callback",
    "http_method",
    "headers",
    "payload",
    "body",
    "command",
    "shell",
    "subprocess",
    "powershell",
    "curl",
    "script",
)

FALSE_FIELDS = (
    "execution_envelope_built",
    "execution_envelope_signed",
    "execution_envelope_persisted",
    "envelope_nonce_claimed",
    "envelope_consumed",
    "pre_dispatch_attested",
    "provider_identity_verified",
    "provider_adapter_attested",
    "capability_binding_verified",
    "fresh_authorization_consumed",
    "idempotency_reserved",
    "effect_key_reserved",
    "lease_acquired",
    "dispatch_recorded",
    "payload_constructed",
    "credentials_loaded",
    "secrets_loaded",
    "endpoint_resolved",
    "network_called",
    "provider_called",
    "billing_authorized",
    "billing_executed",
    "customer_contact_authorized",
    "crm_write_authorized",
    "provisioning_authorized",
    "deploy_authorized",
    "production_mutation_authorized",
    "production_mutation_performed",
    "external_action_executed",
    "execution_allowed",
    "executor_created",
    "executor_selected",
    "executor_implementation_allowed",
    "execution_command_generated",
    "execution_command_executed",
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


def build_execution_envelope_contract(
    *,
    provider_capability_binding_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Define a sealed evidence envelope contract; build no real envelope."""
    row = (
        dict(provider_capability_binding_review)
        if isinstance(provider_capability_binding_review, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != binding.SCHEMA:
        blockers.append("PROVIDER_CAPABILITY_BINDING_SCHEMA_REQUIRED")
    if row.get("state") != binding.READY:
        blockers.append("PROVIDER_CAPABILITY_BINDING_DESIGN_REVIEW_REQUIRED")
    if row.get("provider_capability_binding_design_only") is not True:
        blockers.append("PROVIDER_CAPABILITY_BINDING_NOT_DESIGN_ONLY")
    if row.get("binding_mode") != binding.BINDING_MODE:
        blockers.append("CAPABILITY_BINDING_MODE_INVALID")
    if row.get("exact_intersection_required") is not True:
        blockers.append("EXACT_CAPABILITY_INTERSECTION_REQUIRED")
    if row.get("permission_expansion_forbidden") is not True:
        blockers.append("PERMISSION_EXPANSION_MUST_BE_FORBIDDEN")
    if row.get("binding_single_use_with_authorization_required") is not True:
        blockers.append("SINGLE_USE_AUTHORIZATION_BINDING_REQUIRED")
    if row.get("finops_cap_cents") != 20000:
        blockers.append("FINOPS_CAP_MUST_REMAIN_20000_CENTS")
    if row.get("authorization_reuse_allowed") is not False:
        blockers.append("AUTHORIZATION_REUSE_MUST_BE_FORBIDDEN")
    if row.get("next_allowed_step") != binding.NEXT_ALLOWED_STEP:
        blockers.append("PROVIDER_CAPABILITY_BINDING_NEXT_STEP_INVALID")

    for key in binding.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("PROVIDER_CAPABILITY_BINDING_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            execution_envelope_design_only=True,
            envelope_mode=ENVELOPE_MODE,
            digest_references_only=True,
            no_implicit_execution_authority=True,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        execution_envelope_design_only=True,
        envelope_mode=ENVELOPE_MODE,
        digest_references_only=True,
        immutable_after_seal_required=True,
        canonical_serialization_required=True,
        envelope_digest_required=True,
        envelope_nonce_required=True,
        envelope_single_use_required=True,
        tamper_rebuild_match_required=True,
        max_envelope_window_seconds=MAX_ENVELOPE_WINDOW_SECONDS,
        authorization_window_upper_bound_required=True,
        authorization_reuse_allowed=False,
        no_implicit_execution_authority=True,
        provider_identity_reference_only=True,
        endpoint_material_forbidden=True,
        credential_material_forbidden=True,
        request_payload_material_forbidden=True,
        http_material_forbidden=True,
        shell_material_forbidden=True,
        finops_cap_cents=20000,
        required_envelope_bindings=REQUIRED_ENVELOPE_BINDINGS,
        required_envelope_rules=REQUIRED_ENVELOPE_RULES,
        forbidden_envelope_material=FORBIDDEN_ENVELOPE_MATERIAL,
        independent_dynamic_audit_pending=bool(
            row.get("independent_dynamic_audit_pending", True)
        ),
        next_allowed_step=NEXT_ALLOWED_STEP,
    )


__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "ENVELOPE_MODE",
    "MAX_ENVELOPE_WINDOW_SECONDS",
    "REQUIRED_ENVELOPE_BINDINGS",
    "REQUIRED_ENVELOPE_RULES",
    "FORBIDDEN_ENVELOPE_MATERIAL",
    "FALSE_FIELDS",
    "build_execution_envelope_contract",
]
