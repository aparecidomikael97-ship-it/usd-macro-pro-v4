"""AION B2B provider capability binding contract V1.

Design-only, least-privilege and non-executable.

A future provider adapter may receive only the exact intersection of capability
authority already proven by upstream layers. This contract never creates a new
capability, expands a scope, selects/binds a provider, resolves an endpoint,
loads a credential or executes an external effect.

Maximum positive state:
READY_FOR_PROVIDER_CAPABILITY_BINDING_DESIGN_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

import atlasquant_aion_b2b_provider_adapter_attestation_contract_v1 as adapter

SCHEMA = "ATLASQUANT_AION_B2B_PROVIDER_CAPABILITY_BINDING_CONTRACT_V1"
READY = "READY_FOR_PROVIDER_CAPABILITY_BINDING_DESIGN_REVIEW"
NEXT_ALLOWED_STEP = "DESIGN_EXECUTION_ENVELOPE_CONTRACT_ONLY"

BINDING_MODE = "EXACT_INTERSECTION_FAIL_CLOSED"

CAPABILITY_SOURCES = (
    "FRESH_OWNER_AUTHORIZATION_SCOPE",
    "RUNTIME_GUARD_ALLOWLIST",
    "ADAPTER_ATTESTED_ALLOWLIST",
    "TENANT_WORKSPACE_DOMAIN_SCOPE",
    "ACTION_FAMILY_OPERATION_SCOPE",
)

REQUIRED_BINDING_RULES = (
    "EXACT_INTERSECTION_ONLY",
    "EMPTY_INTERSECTION_BLOCKS",
    "REQUESTED_EXTRA_CAPABILITY_BLOCKS",
    "NO_WILDCARDS",
    "NO_PERMISSION_EXPANSION",
    "NO_CROSS_TENANT",
    "NO_CROSS_WORKSPACE",
    "NO_CROSS_DOMAIN",
    "NO_CROSS_ACTION_FAMILY",
    "NO_CROSS_OPERATION_KIND",
    "OWNER_SCOPE_CANNOT_BE_OVERRIDDEN",
    "RUNTIME_GUARD_CANNOT_BE_OVERRIDDEN",
    "ADAPTER_FORBIDDEN_CAPABILITY_WINS",
    "ADAPTER_ALLOWLIST_IS_CEILING_NOT_AUTHORITY",
    "ROLE_SCOPE_MUST_REMAIN_VALID",
    "TOOL_ACTION_SCOPE_MUST_REMAIN_VALID",
    "COST_CEILING_MUST_REMAIN_WITHIN_FINOPS_CAP",
    "DATA_CLASSIFICATION_COMPATIBILITY_REQUIRED",
    "RETENTION_POLICY_COMPATIBILITY_REQUIRED",
    "LOCAL_FALLBACK_POLICY_PRESERVED",
    "BINDING_DIGEST_REQUIRED",
    "BINDING_FRESHNESS_REQUIRED",
    "BINDING_SINGLE_USE_WITH_AUTHORIZATION",
)

REQUIRED_BINDING_FIELDS = (
    "owner_id",
    "tenant_id",
    "workspace_id",
    "domain",
    "customer_id",
    "pilot_id",
    "action_family",
    "operation_kind",
    "authorization_digest",
    "runtime_guards_digest",
    "adapter_attestation_digest",
    "adapter_manifest_digest",
    "provider_identity_ref",
    "capability_scope_digest",
    "requested_capabilities_digest",
    "effective_capabilities_digest",
    "forbidden_capabilities_digest",
    "finops_ceiling_digest",
    "binding_issued_at",
    "binding_expires_at",
)

FALSE_FIELDS = (
    "capability_binding_verified",
    "capability_scope_loaded",
    "requested_capabilities_loaded",
    "effective_capabilities_materialized",
    "permissions_expanded",
    "wildcard_capability_allowed",
    "cross_tenant_allowed",
    "cross_workspace_allowed",
    "cross_domain_allowed",
    "cross_action_allowed",
    "cross_operation_allowed",
    "provider_adapter_attested",
    "provider_identity_verified",
    "adapter_selected",
    "provider_selected",
    "provider_bound",
    "credentials_loaded",
    "secrets_loaded",
    "endpoint_resolved",
    "payload_constructed",
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


def build_provider_capability_binding_contract(
    *,
    provider_adapter_attestation_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Define least-privilege binding requirements; bind nothing."""
    row = (
        dict(provider_adapter_attestation_review)
        if isinstance(provider_adapter_attestation_review, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != adapter.SCHEMA:
        blockers.append("PROVIDER_ADAPTER_ATTESTATION_SCHEMA_REQUIRED")
    if row.get("state") != adapter.READY:
        blockers.append("PROVIDER_ADAPTER_ATTESTATION_DESIGN_REVIEW_REQUIRED")
    if row.get("provider_adapter_attestation_design_only") is not True:
        blockers.append("PROVIDER_ADAPTER_ATTESTATION_NOT_DESIGN_ONLY")
    if row.get("provider_neutral") is not True:
        blockers.append("PROVIDER_NEUTRAL_BOUNDARY_REQUIRED")
    if row.get("no_implicit_authority") is not True:
        blockers.append("NO_IMPLICIT_AUTHORITY_REQUIREMENT_MISSING")
    if row.get("capability_allowlist_required") is not True:
        blockers.append("ADAPTER_CAPABILITY_ALLOWLIST_REQUIRED")
    if row.get("forbidden_capabilities_required") is not True:
        blockers.append("ADAPTER_FORBIDDEN_CAPABILITIES_REQUIRED")
    if row.get("tenant_scope_binding_required") is not True:
        blockers.append("ADAPTER_TENANT_SCOPE_BINDING_REQUIRED")
    if row.get("action_operation_binding_required") is not True:
        blockers.append("ADAPTER_ACTION_OPERATION_BINDING_REQUIRED")
    if row.get("finops_cap_cents") != 20000:
        blockers.append("FINOPS_CAP_MUST_REMAIN_20000_CENTS")
    if row.get("authorization_reuse_allowed") is not False:
        blockers.append("AUTHORIZATION_REUSE_MUST_BE_FORBIDDEN")
    if row.get("next_allowed_step") != adapter.NEXT_ALLOWED_STEP:
        blockers.append("PROVIDER_ADAPTER_ATTESTATION_NEXT_STEP_INVALID")

    for key in adapter.FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("PROVIDER_ADAPTER_ATTESTATION_UNSAFE_FIELD:" + key)

    if blockers:
        return _result(
            "BLOCKED",
            blockers,
            provider_capability_binding_design_only=True,
            provider_neutral=True,
            binding_mode=BINDING_MODE,
            no_implicit_authority=True,
            independent_dynamic_audit_pending=True,
        )

    return _result(
        READY,
        [],
        provider_capability_binding_design_only=True,
        provider_neutral=True,
        binding_mode=BINDING_MODE,
        no_implicit_authority=True,
        exact_intersection_required=True,
        empty_intersection_blocks=True,
        requested_extra_capability_blocks=True,
        wildcard_capabilities_forbidden=True,
        permission_expansion_forbidden=True,
        adapter_allowlist_is_authority=False,
        adapter_allowlist_is_ceiling=True,
        adapter_forbidden_capability_precedence=True,
        owner_scope_precedence=True,
        runtime_guard_precedence=True,
        tenant_workspace_domain_isolation_required=True,
        action_operation_isolation_required=True,
        role_tool_action_scope_preservation_required=True,
        finops_cap_cents=20000,
        cost_ceiling_preservation_required=True,
        data_policy_compatibility_required=True,
        local_fallback_policy_preservation_required=True,
        provider_identity_reference_binding_required=True,
        binding_digest_required=True,
        binding_freshness_required=True,
        binding_single_use_with_authorization_required=True,
        capability_scope_schema=adapter.CAPABILITY_SCOPE_SCHEMA,
        capability_sources=CAPABILITY_SOURCES,
        required_binding_rules=REQUIRED_BINDING_RULES,
        required_binding_fields=REQUIRED_BINDING_FIELDS,
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
    "BINDING_MODE",
    "CAPABILITY_SOURCES",
    "REQUIRED_BINDING_RULES",
    "REQUIRED_BINDING_FIELDS",
    "FALSE_FIELDS",
    "build_provider_capability_binding_contract",
]
