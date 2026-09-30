"""AION BUSINESS Team Access Sandbox E2E V1.

Fail-closed sandbox lifecycle validation for Business Team & Access.

The reference sandbox stack is Keycloak + OIDC for identity, PostgreSQL for the
versioned membership registry, and a Keycloak Admin REST adapter contract for
session/account revocation. This module never calls those providers. It only
validates caller-supplied sandbox evidence and reuses the production-binding
attestation contract from PR #451.

No account provisioning, MFA enrollment, registry write, session revocation,
account disable, permission escalation, deploy, billing or runtime activation
is executed here.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

from atlasquant_aion_business_team_access_production_binding import (
    GENESIS_DIGEST,
    account_provisioning_attestation,
    registry_persistence_attestation,
    revocation_execution_attestation,
    strong_auth_attestation,
    team_access_activation_review,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_SANDBOX_E2E_V1"
VERSION = "1"

REFERENCE_IDENTITY_PROVIDER = "KEYCLOAK"
REFERENCE_IDENTITY_PROTOCOL = "OIDC"
REFERENCE_REGISTRY_STORAGE = "POSTGRESQL"
REFERENCE_REVOCATION_CONNECTOR = "KEYCLOAK_ADMIN_REST"
REFERENCE_STRONG_AUTH = ("PASSKEY", "SECURITY_KEY", "TOTP")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = 300) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _tokens(value: Any) -> set[str]:
    rows: Sequence[Any]
    if isinstance(value, (list, tuple, set, frozenset)):
        rows = list(value)
    else:
        rows = []
    return {_clean(row, 80).upper() for row in rows if _clean(row, 80)}


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def selected_sandbox_stack() -> dict[str, Any]:
    """Return the bounded reference choice for non-production validation."""
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "TEAM_ACCESS_SANDBOX_REFERENCE_STACK_SELECTED",
        "identity_provider": {
            "provider": REFERENCE_IDENTITY_PROVIDER,
            "protocol": REFERENCE_IDENTITY_PROTOCOL,
            "required_strong_auth": list(REFERENCE_STRONG_AUTH),
        },
        "registry_storage": {
            "provider": REFERENCE_REGISTRY_STORAGE,
            "requires_transactional_write": True,
            "requires_versioned_snapshot": True,
            "requires_exact_readback": True,
        },
        "session_revocation": {
            "connector": REFERENCE_REVOCATION_CONNECTOR,
            "requires_session_revocation": True,
            "requires_account_disable": True,
            "requires_verification_readback": True,
        },
        "selection_scope": "SANDBOX_VALIDATION_ONLY",
        "production_provider_activation_authorized": False,
        "secret_configuration_authorized": False,
        "network_calls_executed_here": False,
        "executes_action": False,
    }


def identity_provider_sandbox_binding(
    observation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(observation)
    factors = _tokens(row.get("strong_auth_factors"))
    provider = _clean(row.get("provider_name"), 80).upper()
    protocol = _clean(row.get("protocol"), 40).upper()
    environment = _clean(row.get("environment"), 40).upper()
    issuer_ref = _clean(row.get("issuer_ref"), 300)
    admin_api_ref = _clean(row.get("admin_api_ref"), 300)

    gates = {
        "sandbox_environment": environment == "SANDBOX",
        "production_environment_false": row.get("production_environment") is False,
        "provider_is_reference": provider == REFERENCE_IDENTITY_PROVIDER,
        "protocol_is_oidc": protocol == REFERENCE_IDENTITY_PROTOCOL,
        "issuer_ref_present": bool(issuer_ref),
        "admin_api_ref_present": bool(admin_api_ref),
        "strong_auth_supported": bool(factors.intersection(REFERENCE_STRONG_AUTH)),
        "individual_accounts_supported": row.get("supports_individual_accounts") is True,
        "account_disable_supported": row.get("supports_account_disable") is True,
        "session_revocation_supported": row.get("supports_session_revocation") is True,
        "secret_material_absent": row.get("secret_material_present") is False,
        "side_effects_absent": row.get("external_side_effects_executed") is False,
    }
    ready = all(gates.values())
    payload = {
        "provider": provider,
        "protocol": protocol,
        "environment": environment,
        "issuer_ref": issuer_ref,
        "admin_api_ref": admin_api_ref,
        "strong_auth_factors": sorted(factors),
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "IDENTITY_PROVIDER_SANDBOX_BINDING_READY"
            if ready
            else "IDENTITY_PROVIDER_SANDBOX_BINDING_BLOCKED"
        ),
        "gates": gates,
        "provider": provider if ready else "",
        "protocol": protocol if ready else "",
        "issuer_ref": issuer_ref if ready else "",
        "admin_api_ref": admin_api_ref if ready else "",
        "strong_auth_factors": sorted(factors) if ready else [],
        "binding_digest": _digest(payload) if ready else "",
        "credentials_stored": False,
        "account_provisioned": False,
        "mfa_enrolled": False,
        "executes_action": False,
    }


def registry_storage_sandbox_binding(
    observation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(observation)
    provider = _clean(row.get("provider_name"), 80).upper()
    environment = _clean(row.get("environment"), 40).upper()
    storage_ref = _clean(row.get("storage_ref"), 300)

    gates = {
        "sandbox_environment": environment == "SANDBOX",
        "production_environment_false": row.get("production_environment") is False,
        "provider_is_reference": provider == REFERENCE_REGISTRY_STORAGE,
        "storage_ref_present": bool(storage_ref),
        "transactional_writes_supported": row.get("supports_transactional_writes") is True,
        "versioned_snapshot_supported": row.get("supports_versioned_snapshot") is True,
        "exact_readback_supported": row.get("supports_exact_readback") is True,
        "secret_material_absent": row.get("secret_material_present") is False,
        "side_effects_absent": row.get("external_side_effects_executed") is False,
    }
    ready = all(gates.values())
    payload = {
        "provider": provider,
        "environment": environment,
        "storage_ref": storage_ref,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "REGISTRY_STORAGE_SANDBOX_BINDING_READY"
            if ready
            else "REGISTRY_STORAGE_SANDBOX_BINDING_BLOCKED"
        ),
        "gates": gates,
        "provider": provider if ready else "",
        "storage_ref": storage_ref if ready else "",
        "binding_digest": _digest(payload) if ready else "",
        "registry_written": False,
        "database_mutation_authorized": False,
        "executes_action": False,
    }


def revocation_connector_sandbox_binding(
    observation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(observation)
    connector = _clean(row.get("connector_name"), 120).upper()
    environment = _clean(row.get("environment"), 40).upper()
    connector_ref = _clean(row.get("connector_ref"), 300)

    gates = {
        "sandbox_environment": environment == "SANDBOX",
        "production_environment_false": row.get("production_environment") is False,
        "connector_is_reference": connector == REFERENCE_REVOCATION_CONNECTOR,
        "connector_ref_present": bool(connector_ref),
        "session_revocation_supported": row.get("supports_session_revocation") is True,
        "account_disable_supported": row.get("supports_account_disable") is True,
        "registry_readback_verification_supported": (
            row.get("supports_registry_readback_verification") is True
        ),
        "secret_material_absent": row.get("secret_material_present") is False,
        "side_effects_absent": row.get("external_side_effects_executed") is False,
    }
    ready = all(gates.values())
    payload = {
        "connector": connector,
        "environment": environment,
        "connector_ref": connector_ref,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "REVOCATION_CONNECTOR_SANDBOX_BINDING_READY"
            if ready
            else "REVOCATION_CONNECTOR_SANDBOX_BINDING_BLOCKED"
        ),
        "gates": gates,
        "connector": connector if ready else "",
        "connector_ref": connector_ref if ready else "",
        "binding_digest": _digest(payload) if ready else "",
        "session_revocation_executed": False,
        "account_disable_executed": False,
        "executes_action": False,
    }


def run_team_access_sandbox_e2e(
    invitation_plan: Mapping[str, Any] | None,
    registry_audit: Mapping[str, Any] | None,
    revocation_plan: Mapping[str, Any] | None,
    *,
    identity_binding: Mapping[str, Any] | None,
    storage_binding: Mapping[str, Any] | None,
    revocation_binding: Mapping[str, Any] | None,
    account_evidence: Mapping[str, Any] | None,
    strong_auth_evidence: Mapping[str, Any] | None,
    registry_evidence: Mapping[str, Any] | None,
    revocation_evidence: Mapping[str, Any] | None,
    requested_by: Any,
) -> dict[str, Any]:
    """Validate a full sandbox lifecycle using only supplied evidence."""
    identity = _mapping(identity_binding)
    storage = _mapping(storage_binding)
    rev_binding = _mapping(revocation_binding)
    account_ev = _mapping(account_evidence)
    auth_ev = _mapping(strong_auth_evidence)
    registry_ev = _mapping(registry_evidence)
    revoke_ev = _mapping(revocation_evidence)

    provider_ready = (
        identity.get("schema") == SCHEMA
        and identity.get("state") == "IDENTITY_PROVIDER_SANDBOX_BINDING_READY"
        and identity.get("provider") == REFERENCE_IDENTITY_PROVIDER
        and identity.get("protocol") == REFERENCE_IDENTITY_PROTOCOL
        and len(_clean(identity.get("binding_digest"), 80)) == 64
        and identity.get("credentials_stored") is False
        and identity.get("account_provisioned") is False
        and identity.get("mfa_enrolled") is False
        and identity.get("executes_action") is False
    )
    storage_ready = (
        storage.get("schema") == SCHEMA
        and storage.get("state") == "REGISTRY_STORAGE_SANDBOX_BINDING_READY"
        and storage.get("provider") == REFERENCE_REGISTRY_STORAGE
        and len(_clean(storage.get("binding_digest"), 80)) == 64
        and storage.get("registry_written") is False
        and storage.get("database_mutation_authorized") is False
        and storage.get("executes_action") is False
    )
    revocation_ready = (
        rev_binding.get("schema") == SCHEMA
        and rev_binding.get("state") == "REVOCATION_CONNECTOR_SANDBOX_BINDING_READY"
        and rev_binding.get("connector") == REFERENCE_REVOCATION_CONNECTOR
        and len(_clean(rev_binding.get("binding_digest"), 80)) == 64
        and rev_binding.get("session_revocation_executed") is False
        and rev_binding.get("account_disable_executed") is False
        and rev_binding.get("executes_action") is False
    )

    account = account_provisioning_attestation(
        invitation_plan,
        provider_ref=identity.get("issuer_ref") if provider_ready else "",
        account_ref=account_ev.get("account_ref"),
        account_username=account_ev.get("username"),
        individual_account_verified=account_ev.get("individual_account_verified"),
        shared_account_detected=account_ev.get("shared_account_detected"),
        account_active_verified=account_ev.get("account_active_verified"),
        observed_at=account_ev.get("observed_at"),
    )

    auth = strong_auth_attestation(
        account,
        factor_type=auth_ev.get("factor_type"),
        factor_ref=auth_ev.get("factor_ref"),
        enrollment_verified=auth_ev.get("enrollment_verified"),
        challenge_verified=auth_ev.get("challenge_verified"),
        observed_at=auth_ev.get("observed_at"),
    )

    registry = registry_persistence_attestation(
        registry_audit,
        storage_ref=storage.get("storage_ref") if storage_ready else "",
        revision=registry_ev.get("revision"),
        previous_revision_digest=registry_ev.get(
            "previous_revision_digest", GENESIS_DIGEST
        ),
        readback_registry_digest=registry_ev.get("readback_registry_digest"),
        persistence_verified=registry_ev.get("persistence_verified"),
        readback_verified=registry_ev.get("readback_verified"),
        observed_at=registry_ev.get("observed_at"),
    )

    activation = team_access_activation_review(
        invitation_plan,
        account,
        auth,
        registry,
        requested_by=requested_by,
    )

    revocation = revocation_execution_attestation(
        revocation_plan,
        provider_ref=identity.get("issuer_ref") if provider_ready else "",
        evidence_ref=revoke_ev.get("evidence_ref"),
        account_disabled_verified=revoke_ev.get("account_disabled_verified"),
        sessions_revoked_verified=revoke_ev.get("sessions_revoked_verified"),
        registry_membership_inactive_verified=revoke_ev.get(
            "registry_membership_inactive_verified"
        ),
        registry_readback_verified=revoke_ev.get("registry_readback_verified"),
        observed_at=revoke_ev.get("observed_at"),
    )

    gates = {
        "identity_binding_ready": provider_ready,
        "storage_binding_ready": storage_ready,
        "revocation_binding_ready": revocation_ready,
        "account_attestation_ready": account.get("state")
        == "ACCOUNT_PROVISIONING_ATTESTATION_READY",
        "strong_auth_attestation_ready": auth.get("state")
        == "STRONG_AUTH_ATTESTATION_READY",
        "strong_auth_bound_to_provider": bool(
            auth.get("factor_type")
            and auth.get("factor_type") in list(identity.get("strong_auth_factors") or [])
        ),
        "registry_attestation_ready": registry.get("state")
        == "REGISTRY_PERSISTENCE_ATTESTATION_READY",
        "activation_review_ready": activation.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_ACTIVATION_REVIEW",
        "revocation_verification_ready": revocation.get("state")
        == "TEAM_REVOCATION_EXTERNALLY_VERIFIED",
    }
    blockers = [name for name, passed in gates.items() if not passed]
    ready = not blockers

    evidence = {
        "identity_binding_digest": identity.get("binding_digest"),
        "storage_binding_digest": storage.get("binding_digest"),
        "revocation_binding_digest": rev_binding.get("binding_digest"),
        "account_attestation_digest": account.get("attestation_digest"),
        "strong_auth_attestation_digest": auth.get("attestation_digest"),
        "registry_attestation_digest": registry.get("attestation_digest"),
        "activation_review_digest": activation.get("review_digest"),
        "revocation_verification_digest": revocation.get("verification_digest"),
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_EXIT_REVIEW"
            if ready
            else "TEAM_ACCESS_SANDBOX_E2E_BLOCKED"
        ),
        "gates": gates,
        "blockers": blockers,
        "reference_stack": selected_sandbox_stack(),
        "evidence_digest": _digest(evidence) if ready else "",
        "activation_review": activation,
        "revocation_verification": revocation,
        "production_provider_activation_authorized": False,
        "production_registry_write_authorized": False,
        "production_session_revocation_authorized": False,
        "permission_escalation_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "REFERENCE_IDENTITY_PROVIDER",
    "REFERENCE_IDENTITY_PROTOCOL",
    "REFERENCE_REGISTRY_STORAGE",
    "REFERENCE_REVOCATION_CONNECTOR",
    "REFERENCE_STRONG_AUTH",
    "selected_sandbox_stack",
    "identity_provider_sandbox_binding",
    "registry_storage_sandbox_binding",
    "revocation_connector_sandbox_binding",
    "run_team_access_sandbox_e2e",
]
