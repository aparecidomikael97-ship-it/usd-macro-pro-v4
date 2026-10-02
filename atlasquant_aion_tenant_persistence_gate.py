"""AION tenant persistence activation gate.

Fail-closed readiness gate for durable tenant/workspace persistence. Evidence
can document progress but never grants authority or bypasses code-level policy.
"""
from __future__ import annotations

from typing import Any, Mapping
import re

from atlasquant_aion_tenant import tenant_policy_snapshot
from atlasquant_aion_tenant_store import tenant_store_policy
from atlasquant_aion_tenant_privacy import tenant_privacy_readiness

SCHEMA = "ATLASQUANT_AION_TENANT_PERSISTENCE_GATE_V1"
REQUIRED_EVIDENCE = (
    "IDENTITY_REGISTRY",
    "ACL_STORE",
    "DURABLE_STORE",
    "TENANT_E2E",
    "BACKUP_RESTORE",
    "REVOCATION_REPLAY",
)
_DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")


def _evidence_state(raw: Any) -> dict[str, Any]:
    row = dict(raw) if isinstance(raw, Mapping) else {}
    status = str(row.get("status") or "").strip().upper()
    digest = str(row.get("digest") or "").strip().lower()
    scope = str(row.get("scope") or "").strip().lower()
    valid = status == "PASS" and bool(_DIGEST.fullmatch(digest))
    return {
        "status": status or "MISSING",
        "digest": digest if valid else "",
        "scope": scope,
        "valid": valid,
    }


def tenant_persistence_readiness(
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    tenant = tenant_policy_snapshot()
    store = tenant_store_policy()
    privacy = tenant_privacy_readiness()
    supplied = dict(evidence or {})
    evidence_view = {
        name: _evidence_state(supplied.get(name))
        for name in REQUIRED_EVIDENCE
    }
    blockers: list[str] = []

    if store.get("network_io_implemented") is not True:
        blockers.append("DURABLE_IO_NOT_IMPLEMENTED")
    if privacy.get("persistence_enabled") is not True:
        blockers.append("TENANT_PERSISTENCE_DISABLED")
    if tenant.get("cross_tenant_access") is not False:
        blockers.append("CROSS_TENANT_POLICY_UNSAFE")
    if tenant.get("credential_bound_namespace") is not True:
        blockers.append("CREDENTIAL_BOUND_NAMESPACE_REQUIRED")
    if store.get("explicit_write_approval_required") is not True:
        blockers.append("EXPLICIT_WRITE_APPROVAL_REQUIRED")
    if store.get("automatic_overwrite") is not False:
        blockers.append("AUTOMATIC_OVERWRITE_MUST_STAY_DISABLED")

    for name, row in evidence_view.items():
        if row["status"] == "MISSING":
            blockers.append(f"EVIDENCE_{name}_MISSING")
        elif row["status"] != "PASS":
            blockers.append(f"EVIDENCE_{name}_NOT_PASS")
        elif not row["valid"]:
            blockers.append(f"EVIDENCE_{name}_DIGEST_INVALID")

    code_ready = (
        store.get("network_io_implemented") is True
        and privacy.get("persistence_enabled") is True
        and tenant.get("cross_tenant_access") is False
        and tenant.get("credential_bound_namespace") is True
        and store.get("explicit_write_approval_required") is True
        and store.get("automatic_overwrite") is False
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
