"""Fail-closed preflight policy for future AION Chat production PostgreSQL.

This module evaluates non-secret evidence only. It does not connect to a
provider, open a database connection, resolve credentials, apply migrations,
deploy AtlasQuant, arm a Worker, execute an external action, or mutate Core V1.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MAX_MONTHLY_BRL = 200.0

BLOCKED = "BLOCKED"
READY_FOR_PROVIDER_PROVISIONING = "READY_FOR_PROVIDER_PROVISIONING"
READY_FOR_ISOLATED_MIGRATION = "READY_FOR_ISOLATED_MIGRATION"
READY_FOR_CONNECTION_ATTESTATION = "READY_FOR_CONNECTION_ATTESTATION"

PROVIDER_PREFLIGHT_FIELDS = (
    "provider_name",
    "pricing_verified",
    "plan_persistent",
    "private_connectivity_supported",
    "tls_supported",
    "backup_supported",
)

PROVISIONED_SECURITY_FIELDS = (
    "same_region_as_app",
    "private_connectivity_enabled",
    "public_access_disabled",
    "tls_required",
    "least_privilege_role",
    "secret_injected_outside_repo",
    "backup_enabled",
    "recovery_point_verified",
)

POST_MIGRATION_FIELDS = (
    "migration_applied",
    "migration_checksum_verified",
    "schema_version_compatible",
    "schema_constraints_healthy",
    "transaction_health",
    "scope_policy_healthy",
    "cursor_signing_key_stable",
    "restore_drill_verified",
)


@dataclass(frozen=True)
class ProductionPostgresPreflightEvidence:
    ephemeral_binding_validated: bool = False
    core_v1_frozen: bool = False

    provider_name: str = ""
    pricing_verified: bool = False
    monthly_cost_brl: float | None = None
    plan_persistent: bool = False
    private_connectivity_supported: bool = False
    tls_supported: bool = False
    backup_supported: bool = False

    provider_instance_provisioned: bool = False
    same_region_as_app: bool = False
    private_connectivity_enabled: bool = False
    public_access_disabled: bool = False
    tls_required: bool = False
    least_privilege_role: bool = False
    app_role_is_superuser: bool = False
    secret_injected_outside_repo: bool = False
    backup_enabled: bool = False
    recovery_point_verified: bool = False

    migration_applied: bool = False
    migration_version: int | None = None
    migration_checksum: str = ""
    migration_checksum_verified: bool = False
    schema_version_compatible: bool = False
    schema_constraints_healthy: bool = False
    transaction_health: bool = False
    scope_policy_healthy: bool = False
    cursor_signing_key_stable: bool = False
    restore_drill_verified: bool = False

    secrets_committed_to_repo: bool = False
    deploy_executed: bool = False
    worker_armed: bool = False
    core_mutated: bool = False


def _required_true(evidence: ProductionPostgresPreflightEvidence, fields: tuple[str, ...]) -> list[str]:
    return [name for name in fields if not bool(getattr(evidence, name))]


def evaluate_production_postgres_preflight(
    evidence: ProductionPostgresPreflightEvidence,
    *,
    max_monthly_brl: float = MAX_MONTHLY_BRL,
) -> dict[str, Any]:
    """Return the highest safely proven next state and explicit blockers."""
    if not isinstance(evidence, ProductionPostgresPreflightEvidence):
        raise TypeError("ProductionPostgresPreflightEvidence required")
    if not isinstance(max_monthly_brl, (int, float)) or max_monthly_brl <= 0:
        raise ValueError("positive monthly budget ceiling required")

    blockers: list[str] = []

    if not evidence.ephemeral_binding_validated:
        blockers.append("EPHEMERAL_POSTGRES_BINDING_NOT_VALIDATED")
    if not evidence.core_v1_frozen:
        blockers.append("CORE_V1_FREEZE_NOT_PROVEN")

    if evidence.secrets_committed_to_repo:
        blockers.append("SECRET_MATERIAL_COMMITTED_TO_REPOSITORY")
    if evidence.deploy_executed:
        blockers.append("DEPLOY_OCCURRED_OUTSIDE_THIS_PREFLIGHT")
    if evidence.worker_armed:
        blockers.append("WORKER_ARMED_OUTSIDE_THIS_PREFLIGHT")
    if evidence.core_mutated:
        blockers.append("CORE_V1_MUTATED")
    if evidence.app_role_is_superuser:
        blockers.append("APPLICATION_ROLE_MUST_NOT_BE_SUPERUSER")

    if evidence.monthly_cost_brl is not None:
        try:
            monthly = float(evidence.monthly_cost_brl)
        except (TypeError, ValueError) as exc:
            raise ValueError("monthly_cost_brl must be numeric or None") from exc
        if monthly < 0:
            raise ValueError("monthly_cost_brl must not be negative")
        if monthly > float(max_monthly_brl):
            blockers.append("MONTHLY_COST_EXCEEDS_OWNER_CEILING")

    provider_missing = _required_true(evidence, PROVIDER_PREFLIGHT_FIELDS)
    if provider_missing:
        blockers.extend("MISSING_PROVIDER_EVIDENCE:" + field for field in provider_missing)
    if not str(evidence.provider_name or "").strip():
        blockers.append("MISSING_PROVIDER_EVIDENCE:provider_name")
    if evidence.pricing_verified and evidence.monthly_cost_brl is None:
        blockers.append("VERIFIED_PRICING_REQUIRES_MONTHLY_COST_BRL")

    hard_blockers = list(dict.fromkeys(blockers))
    if hard_blockers:
        return {
            "state": BLOCKED,
            "blockers": hard_blockers,
            "max_monthly_brl": float(max_monthly_brl),
            "provider_mutation_executed": False,
            "migration_executed": False,
            "deploy_authorized": False,
            "worker_authorized": False,
            "core_write_authorized": False,
        }

    if not evidence.provider_instance_provisioned:
        return {
            "state": READY_FOR_PROVIDER_PROVISIONING,
            "blockers": [],
            "max_monthly_brl": float(max_monthly_brl),
            "provider_mutation_executed": False,
            "migration_executed": False,
            "deploy_authorized": False,
            "worker_authorized": False,
            "core_write_authorized": False,
        }

    provisioned_missing = _required_true(evidence, PROVISIONED_SECURITY_FIELDS)
    if provisioned_missing:
        return {
            "state": BLOCKED,
            "blockers": [
                "MISSING_PROVISIONED_SECURITY_EVIDENCE:" + field
                for field in provisioned_missing
            ],
            "max_monthly_brl": float(max_monthly_brl),
            "provider_mutation_executed": False,
            "migration_executed": False,
            "deploy_authorized": False,
            "worker_authorized": False,
            "core_write_authorized": False,
        }

    if not evidence.migration_applied:
        return {
            "state": READY_FOR_ISOLATED_MIGRATION,
            "blockers": [],
            "max_monthly_brl": float(max_monthly_brl),
            "provider_mutation_executed": False,
            "migration_executed": False,
            "deploy_authorized": False,
            "worker_authorized": False,
            "core_write_authorized": False,
        }

    post_missing = _required_true(evidence, POST_MIGRATION_FIELDS)
    if evidence.migration_version is None or evidence.migration_version < 1:
        post_missing.append("migration_version")
    if not str(evidence.migration_checksum or "").strip():
        post_missing.append("migration_checksum")
    if post_missing:
        return {
            "state": BLOCKED,
            "blockers": [
                "MISSING_POST_MIGRATION_EVIDENCE:" + field
                for field in dict.fromkeys(post_missing)
            ],
            "max_monthly_brl": float(max_monthly_brl),
            "provider_mutation_executed": False,
            "migration_executed": False,
            "deploy_authorized": False,
            "worker_authorized": False,
            "core_write_authorized": False,
        }

    return {
        "state": READY_FOR_CONNECTION_ATTESTATION,
        "blockers": [],
        "max_monthly_brl": float(max_monthly_brl),
        "provider_mutation_executed": False,
        "migration_executed": False,
        "deploy_authorized": False,
        "worker_authorized": False,
        "core_write_authorized": False,
    }


def preflight_policy() -> dict[str, Any]:
    return {
        "schema": "ATLASQUANT_AION_CHAT_PRODUCTION_POSTGRES_PREFLIGHT_V1",
        "max_monthly_brl": MAX_MONTHLY_BRL,
        "provider_network_called": False,
        "database_connection_opened": False,
        "secret_resolved": False,
        "migration_executed": False,
        "deploy_executed": False,
        "worker_armed": False,
        "external_action_executed": False,
        "core_checkpoint_write": False,
        "allowed_states": [
            BLOCKED,
            READY_FOR_PROVIDER_PROVISIONING,
            READY_FOR_ISOLATED_MIGRATION,
            READY_FOR_CONNECTION_ATTESTATION,
        ],
    }


__all__ = [
    "MAX_MONTHLY_BRL",
    "BLOCKED",
    "READY_FOR_PROVIDER_PROVISIONING",
    "READY_FOR_ISOLATED_MIGRATION",
    "READY_FOR_CONNECTION_ATTESTATION",
    "ProductionPostgresPreflightEvidence",
    "evaluate_production_postgres_preflight",
    "preflight_policy",
]
