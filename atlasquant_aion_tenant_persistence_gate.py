"""AION tenant persistence activation gate.

Fail-closed readiness gate for durable tenant/workspace persistence. Evidence
can document progress but never grants authority or bypasses code-level policy.
"""
from __future__ import annotations

from typing import Any, Mapping

from atlasquant_aion_tenant import tenant_policy_snapshot
from atlasquant_aion_tenant_store import tenant_store_policy
from atlasquant_aion_tenant_durable_store import durable_store_policy
from atlasquant_aion_tenant_privacy import tenant_privacy_readiness
from atlasquant_aion_tenant_evidence_binding import validate_evidence_record

SCHEMA = "ATLASQUANT_AION_TENANT_PERSISTENCE_GATE_V1"
REQUIRED_EVIDENCE = (
    "IDENTITY_REGISTRY",
    "ACL_STORE",
    "DURABLE_STORE",
    "TENANT_E2E",
    "BACKUP_RESTORE",
    "REVOCATION_REPLAY",
)
def _evidence_state(raw: Any, expected_kind: str) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {
            "status": "MISSING", "digest": "", "scope": "",
            "valid": False, "binding_valid": False, "reasons": ["MISSING"],
        }
    checked = validate_evidence_record(raw, expected_kind=expected_kind)
    status = str(checked.get("status") or "MISSING").upper()
    binding_valid = checked.get("valid") is True
    return {
        **checked,
        "status": status,
        "binding_valid": binding_valid,
        "valid": binding_valid and status == "PASS",
    }


def tenant_persistence_readiness(
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    tenant = tenant_policy_snapshot()
    store = tenant_store_policy()
    durable = durable_store_policy()
    privacy = tenant_privacy_readiness()
    supplied = dict(evidence or {})
    evidence_view = {
        name: _evidence_state(supplied.get(name), name)
        for name in REQUIRED_EVIDENCE
    }
    blockers: list[str] = []

    local_durable_ready = (
        durable.get("local_durable_io_implemented") is True
        and durable.get("identity_registry_implemented") is True
        and durable.get("acl_store_implemented") is True
        and durable.get("atomic_replace") is True
        and durable.get("optimistic_concurrency") is True
        and durable.get("backup_restore_implemented") is True
        and durable.get("network_io_implemented") is False
        and durable.get("production_persistence_activated") is False
    )
    if not local_durable_ready:
        blockers.append("LOCAL_DURABLE_STORE_NOT_READY")
    if tenant.get("cross_tenant_access") is not False:
        blockers.append("CROSS_TENANT_POLICY_UNSAFE")
    if tenant.get("credential_bound_namespace") is not True:
        blockers.append("CREDENTIAL_BOUND_NAMESPACE_REQUIRED")
    if store.get("explicit_write_approval_required") is not True:
        blockers.append("EXPLICIT_WRITE_APPROVAL_REQUIRED")
    if store.get("automatic_overwrite") is not False:
        blockers.append("AUTOMATIC_OVERWRITE_MUST_STAY_DISABLED")
    if privacy.get("cross_tenant_audit_ready") is not True:
        blockers.append("CROSS_TENANT_AUDIT_REQUIRED")

    for name, row in evidence_view.items():
        if row["status"] == "MISSING":
            blockers.append(f"EVIDENCE_{name}_MISSING")
        elif row["status"] != "PASS":
            blockers.append(f"EVIDENCE_{name}_NOT_PASS")
        elif not row["binding_valid"]:
            blockers.append(f"EVIDENCE_{name}_BINDING_INVALID")

    code_ready = (
        local_durable_ready
        and tenant.get("cross_tenant_access") is False
        and tenant.get("credential_bound_namespace") is True
        and store.get("explicit_write_approval_required") is True
        and store.get("automatic_overwrite") is False
        and privacy.get("cross_tenant_audit_ready") is True
    )
    evidence_ready = all(row["valid"] for row in evidence_view.values())
    state = "READY_FOR_ADMIN_REVIEW" if code_ready and evidence_ready and not blockers else "BLOCKED"
    return {
        "schema": SCHEMA,
        "state": state,
        "blockers": list(dict.fromkeys(blockers)),
        "code_ready": code_ready,
        "evidence_ready": evidence_ready,
        "tenant_policy": tenant,
        "store_policy": store,
        "durable_store_policy": durable,
        "local_durable_ready": local_durable_ready,
        "privacy_readiness": {
            "persistence_enabled": privacy.get("persistence_enabled"),
            "cross_tenant_audit_ready": privacy.get("cross_tenant_audit_ready"),
            "export_contract_ready": privacy.get("export_contract_ready"),
            "deletion_plan_contract_ready": privacy.get("deletion_plan_contract_ready"),
        },
        "evidence": evidence_view,
        "evidence_is_authority": False,
        "automatic_activation": False,
        "persistence_activation_authorized": False,
        "external_action_executed": False,
    }


__all__ = ["SCHEMA", "REQUIRED_EVIDENCE", "tenant_persistence_readiness"]
