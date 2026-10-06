"""AION B2B provider adapter attestation contract V1.

Design-only, provider-neutral and non-executable.

This contract defines the evidence a future concrete provider adapter must
present before it can be considered for runtime binding. It does not select a
provider, load credentials, expose endpoints, construct payloads, call a
network, bill, contact customers, write CRM, provision, deploy or mutate
production.

Maximum positive state:
READY_FOR_PROVIDER_ADAPTER_ATTESTATION_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_runtime_execution_guards_contract_v1 as guards

SCHEMA = "ATLASQUANT_AION_B2B_PROVIDER_ADAPTER_ATTESTATION_CONTRACT_V1"
READY = "READY_FOR_PROVIDER_ADAPTER_ATTESTATION_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_PROVIDER_CAPABILITY_BINDING_CONTRACT_ONLY"

MODEL_GATEWAY_SCHEMA = "ATLASQUANT_AION_MODEL_GATEWAY_V2"
PROVIDER_REGISTRY_SCHEMA = "ATLASQUANT_AION_PROVIDER_NEUTRAL_MODEL_REGISTRY_V1"
CAPABILITY_SCOPE_SCHEMA = "ATLASQUANT_AION_CAPABILITY_SCOPE_GRANT_V1"

REQUIRED_ATTESTATIONS = (
    "ADAPTER_IDENTITY_STABLE",
    "ADAPTER_VERSION_PINNED",
    "ADAPTER_MANIFEST_DIGEST_BOUND",
    "ADAPTER_CODE_DIGEST_BOUND",
    "ADAPTER_SUPPLY_CHAIN_EVIDENCE_BOUND",
    "PROVIDER_IDENTITY_REFERENCE_BOUND",
    "TRANSPORT_CLASS_DECLARED",
    "CAPABILITY_ALLOWLIST_DECLARED",
    "FORBIDDEN_CAPABILITIES_DECLARED",
    "TENANT_SCOPE_BINDING_DECLARED",
    "ACTION_FAMILY_OPERATION_BINDING_DECLARED",
    "REQUEST_SCHEMA_DIGEST_BOUND",
    "RESPONSE_SCHEMA_DIGEST_BOUND",
    "ERROR_TAXONOMY_DECLARED",
    "TIMEOUT_POLICY_DECLARED",
    "RETRY_POLICY_DECLARED",
    "IDEMPOTENCY_SUPPORT_DECLARED",
    "EFFECT_KEY_SUPPORT_DECLARED",
    "HEALTH_EVIDENCE_SCHEMA_DECLARED",
    "COST_MODEL_DECLARED",
    "MAX_PER_ACTION_COST_DECLARED",
    "DATA_CLASSIFICATION_DECLARED",
    "DATA_RETENTION_POLICY_DECLARED",
    "LOG_REDACTION_POLICY_DECLARED",
    "SECRET_HANDLING_POLICY_DECLARED",
    "CREDENTIAL_SOURCE_POLICY_DECLARED",
    "AUDIT_RECEIPT_SCHEMA_DECLARED",
    "ROLLBACK_COMPENSATION_SUPPORT_DECLARED",
    "IRREVERSIBLE_EFFECTS_DECLARED",
    "LOCAL_FALLBACK_COMPATIBILITY_DECLARED",
    "NO_IMPLICIT_AUTHORITY_DECLARED",
)

FORBIDDEN_MANIFEST_MATERIAL = (
    "credential_value",
    "secret_value",
    "api_key_value",
    "access_token_value",
    "refresh_token_value",
    "password_value",
    "private_key_value",
    "authorization_header_value",
    "cookie_value",
    "provider_endpoint_value",
    "webhook_url_value",
    "callback_url_value",
    "request_payload_value",
    "shell_command_value",
)

FALSE_FIELDS = (
    "provider_adapter_attested",
    "provider_identity_verified",
    "adapter_manifest_loaded",
    "adapter_code_loaded",
    "adapter_selected",
    "provider_selected",
    "provider_bound",
    "credentials_loaded",
    "secrets_loaded",
    "endpoint_resolved",
    "request_schema_instantiated",
    "payload_constructed",
    "network_called",
    "provider_called",
    "billing_authorized",
    "billing_executed",
    "customer_contact_authorized",
    "customer_contact_performed",
    "crm_write_authorized",
    "crm_write_performed",
    "provisioning_authorized",
    "provisioning_performed",
    "deploy_authorized",
    "deploy_performed",
    "production_mutation_authorized",
    "production_mutation_performed",
    "external_action_executed",
    "execution_allowed",
    "executor_created",
    "executor_selected",
    "executor_implementation_allowed",
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


def build_provider_adapter_attestation_contract(
    *,
    runtime_guards_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build provider-adapter attestation requirements without loading an adapter."""
    row = (
        dict(runtime_guards_review)
        if isinstance(runtime_guards_review, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != guards.SCHEMA:
        blockers.append("RUNTIME_GUARDS_SCHEMA_REQUIRED")
    if row.get("state") != guards.READY:
        blockers.append("RUNTIME_GUARDS_DESIGN_REVIEW_REQUIRED")
    if row.get("runtime_guards_design_only") is not True:
        blockers.append("RUNTIME_GUARDS_NOT_DESIGN_ONLY")
    if row.get("provider_neutral") is not True:
        blockers.append("PROVIDER_NEUTRAL_BOUNDARY_REQUIRED")
    if row.get("provider_adapter_attestation_required") is not True:
        blockers.append("PROVIDER_ADAPTER_ATTESTATION_REQUIREMENT_MISSING")
    if row.get("provider_identity_binding_required") is not True:
        blockers.append("PROVIDER_IDENTITY_BINDING_REQUIREMENT_MISSING")
    if row.get("capability_allowlist_required") is not True:
        blockers.append("CAPABILITY_ALLOWLIST_REQUIREMENT_MISSING")
    if row.get("tenant_scope_binding_required") is not True:
        blockers.append("TENANT_SCOPE_BINDING_REQUIREMENT_MISSING")
    if row.get("runtime_finops_guard_required") is not True:
        blockers.append("RUNTIME_FINOPS_GUARD_REQUIREMENT_MISSING")
    if row.get("finops_cap_cents") != 20000:
        blockers.append("FINOPS_CAP_MUST_REMAIN_20000_CENTS")
    if row.get("authorization_reuse_allowed") is not False:
        blockers.append("AUTHORIZATION_REUSE_MUST_BE_FORBIDDEN")
    if row.get("next_allowed_step") != guards.NEXT_ALLOWED_STEP:
        blockers.append("RUNTIME_GUARDS_NEXT_STEP_INVALID")

    for key in guards.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("RUNTIME_GUARDS_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            provider_adapter_attestation_design_only=True,
            provider_neutral=True,
            no_implicit_authority=True,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        provider_adapter_attestation_design_only=True,
        provider_neutral=True,
        no_implicit_authority=True,
        concrete_adapter_not_loaded=True,
        concrete_provider_not_selected=True,
        provider_identity_reference_required=True,
        adapter_identity_required=True,
        adapter_version_pin_required=True,
        adapter_manifest_digest_required=True,
        adapter_code_digest_required=True,
        supply_chain_evidence_required=True,
        transport_declaration_required=True,
        capability_allowlist_required=True,
        forbidden_capabilities_required=True,
        tenant_scope_binding_required=True,
        action_operation_binding_required=True,
        request_response_schema_digest_required=True,
        error_taxonomy_required=True,
        timeout_retry_policy_required=True,
        idempotency_effect_support_declaration_required=True,
        health_evidence_required=True,
        cost_model_required=True,
        max_per_action_cost_required=True,
        data_classification_required=True,
        data_retention_policy_required=True,
        log_redaction_policy_required=True,
        secret_handling_policy_required=True,
        credential_source_policy_required=True,
        audit_receipt_schema_required=True,
        rollback_compensation_support_required=True,
        irreversible_effect_declaration_required=True,
        local_fallback_compatibility_required=True,
        model_gateway_schema=MODEL_GATEWAY_SCHEMA,
        provider_registry_schema=PROVIDER_REGISTRY_SCHEMA,
        capability_scope_schema=CAPABILITY_SCOPE_SCHEMA,
        required_attestations=REQUIRED_ATTESTATIONS,
        forbidden_manifest_material=FORBIDDEN_MANIFEST_MATERIAL,
        finops_cap_cents=20000,
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
    "MODEL_GATEWAY_SCHEMA",
    "PROVIDER_REGISTRY_SCHEMA",
    "CAPABILITY_SCOPE_SCHEMA",
    "REQUIRED_ATTESTATIONS",
    "FORBIDDEN_MANIFEST_MATERIAL",
    "FALSE_FIELDS",
    "build_provider_adapter_attestation_contract",
]
