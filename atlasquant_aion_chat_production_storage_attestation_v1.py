"""AION Chat production storage attestation contract V1.

Design/CI-only and non-provisioning.

This contract evaluates supplied evidence for a future production chat storage
backend. It does not select a vendor, open a connection, read a secret, create a
database, migrate data, write runtime state, deploy, bill, or perform network I/O.

Maximum positive state:
READY_FOR_PRODUCTION_CHAT_STORAGE_ATTESTATION_REVIEW
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_CHAT_PRODUCTION_STORAGE_ATTESTATION_V1"
READY = "READY_FOR_PRODUCTION_CHAT_STORAGE_ATTESTATION_REVIEW"
NEXT_ALLOWED_STEP = "SUPPLY_ATTESTED_STORAGE_TO_PRODUCTION_CHAT_ACTIVATION"
OWNER_ID = "HUMAN_OWNER"

FALSE_FIELDS = (
    "vendor_selected",
    "database_created",
    "connection_opened",
    "credentials_loaded",
    "secrets_loaded",
    "network_called",
    "migration_executed",
    "write_executed",
    "restore_executed",
    "billing_authorized",
    "billing_executed",
    "deploy_authorized",
    "deploy_executed",
    "execution_allowed",
    "worker_armed",
    "worker_activated",
    "external_action_executed",
)

REQUIRED_EVIDENCE = (
    "PRODUCTION_BACKEND_NON_EPHEMERAL",
    "OWNER_TENANT_WORKSPACE_SCOPE_BOUND",
    "DEFAULT_DENY_ACCESS_POLICY",
    "ENCRYPTION_AT_REST_ATTESTED",
    "ENCRYPTION_IN_TRANSIT_ATTESTED",
    "BACKUP_POLICY_ATTESTED",
    "RESTORE_TEST_ATTESTED",
    "SCHEMA_MIGRATION_PLAN_ATTESTED",
    "HEALTH_CHECK_ATTESTED",
    "FAIL_CLOSED_ON_UNAVAILABLE",
    "DATA_RETENTION_POLICY_ATTESTED",
    "AUDITABILITY_ATTESTED",
)

def _mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}

def _result(state: str, blockers=(), **fields) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": state,
        "blockers": sorted(set(str(x) for x in blockers if str(x))),
        **fields,
        **{key: False for key in FALSE_FIELDS},
    }

def evaluate_production_storage_attestation(
    *,
    owner_context: Mapping[str, Any] | None,
    storage_evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Evaluate production storage evidence without touching storage."""
    owner = _mapping(owner_context)
    row = _mapping(storage_evidence)
    blockers: list[str] = []

    if owner.get("is_human_owner") is not True:
        blockers.append("HUMAN_OWNER_SESSION_REQUIRED")
    if str(owner.get("owner_id") or "") != OWNER_ID:
        blockers.append("HUMAN_OWNER_ID_REQUIRED")
    if owner.get("session_bound") is not True:
        blockers.append("HUMAN_OWNER_SESSION_BINDING_REQUIRED")

    checks = {
        "PRODUCTION_BACKEND_REQUIRED": row.get("production") is True,
        "NON_EPHEMERAL_STORAGE_REQUIRED": row.get("non_ephemeral") is True,
        "DURABLE_STORAGE_REQUIRED": row.get("durable") is True,
        "SCOPE_BINDING_REQUIRED": row.get("scope_bound") is True,
        "DEFAULT_DENY_REQUIRED": row.get("default_deny") is True,
        "ENCRYPTION_AT_REST_REQUIRED": row.get("encryption_at_rest_attested") is True,
        "ENCRYPTION_IN_TRANSIT_REQUIRED": row.get("encryption_in_transit_attested") is True,
        "BACKUP_POLICY_REQUIRED": row.get("backup_policy_attested") is True,
        "RESTORE_TEST_REQUIRED": row.get("restore_test_attested") is True,
        "SCHEMA_MIGRATION_PLAN_REQUIRED": row.get("schema_migration_plan_attested") is True,
        "HEALTH_CHECK_REQUIRED": row.get("health_check_attested") is True,
        "FAIL_CLOSED_UNAVAILABLE_REQUIRED": row.get("fail_closed_on_unavailable") is True,
        "RETENTION_POLICY_REQUIRED": row.get("retention_policy_attested") is True,
        "AUDITABILITY_REQUIRED": row.get("auditability_attested") is True,
    }
    for blocker, ok in checks.items():
        if not ok:
            blockers.append(blocker)

    if row.get("ephemeral_runtime_filesystem") is True:
        blockers.append("EPHEMERAL_RUNTIME_FILESYSTEM_FORBIDDEN")
    if row.get("staging_only") is True:
        blockers.append("STAGING_ONLY_STORAGE_FORBIDDEN")
    if row.get("production_ready") is not True:
        blockers.append("PRODUCTION_READY_ATTESTATION_REQUIRED")

    common = dict(
        attestation_design_only=True,
        vendor_neutral=True,
        owner_binding_required=True,
        production_backend_required=True,
        non_ephemeral_required=True,
        scope_binding_required=True,
        default_deny_required=True,
        encryption_at_rest_required=True,
        encryption_in_transit_required=True,
        backup_restore_required=True,
        migration_plan_required=True,
        health_check_required=True,
        fail_closed_unavailable_required=True,
        retention_policy_required=True,
        auditability_required=True,
        required_evidence=REQUIRED_EVIDENCE,
        next_allowed_step=NEXT_ALLOWED_STEP,
    )
    if blockers:
        return _result("BLOCKED", blockers, **common)
    return _result(READY, [], **common)

__all__ = [
    "SCHEMA",
    "READY",
    "NEXT_ALLOWED_STEP",
    "OWNER_ID",
    "FALSE_FIELDS",
    "REQUIRED_EVIDENCE",
    "evaluate_production_storage_attestation",
]
