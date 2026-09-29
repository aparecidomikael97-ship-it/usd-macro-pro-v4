"""Certified-record bridge into the existing AION Tool Hub preflight.

A sealed CERTIFIED record is a prerequisite, never authority. The bridge also
revalidates the manifest against the current Capability Registry and Tool Hub
before asking Tool Hub for its own preflight. SUSPENDED, REVOKED, tampered or
scope-mismatched records stop before Tool Hub. No tool or connector is called.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from atlasquant_aion_capabilities import CapabilityRegistry
from atlasquant_aion_skill_certification import (
    SCHEMA as CERTIFICATION_SCHEMA,
    assess_skill_manifest,
    certification_record_fingerprint,
    manifest_fingerprint,
)
from atlasquant_aion_tool_hub import plan_tool_call


SCHEMA = "ATLASQUANT_AION_SKILL_TOOL_BRIDGE_V1"


def _clean(value: Any, limit: int = 160) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _record_gate(
    record: Mapping[str, Any] | None,
    *,
    trusted_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw = dict(record or {})
    trusted = dict(trusted_context or {})
    manifest = (
        dict(raw.get("manifest"))
        if isinstance(raw.get("manifest"), Mapping)
        else {}
    )
    state = _clean(raw.get("state"), 40).upper()
    record_fingerprint = _clean(raw.get("record_fingerprint"), 128)
    blockers: list[str] = []

    if raw.get("schema") != CERTIFICATION_SCHEMA:
        blockers.append("CERTIFICATION_RECORD_SCHEMA_INVALID")
    if not manifest or not _clean(raw.get("fingerprint"), 128):
        blockers.append("CERTIFICATION_RECORD_INCOMPLETE")
    elif manifest_fingerprint(manifest) != _clean(raw.get("fingerprint"), 128):
        blockers.append("CERTIFICATION_MANIFEST_FINGERPRINT_MISMATCH")
    if not record_fingerprint:
        blockers.append("CERTIFICATION_RECORD_FINGERPRINT_REQUIRED")
    elif certification_record_fingerprint(raw) != record_fingerprint:
        blockers.append("CERTIFICATION_RECORD_FINGERPRINT_MISMATCH")
    if state != "CERTIFIED":
        blockers.append("SKILL_RECORD_NOT_CERTIFIED:" + (state or "UNKNOWN"))
    if (
        raw.get("tests_pass") is not True
        or raw.get("provenance_verified") is not True
        or raw.get("review_approved") is not True
    ):
        blockers.append("CERTIFICATION_EVIDENCE_NOT_SEALED")

    trusted_tenant = _clean(trusted.get("tenant_id"), 120)
    trusted_workspace = _clean(trusted.get("workspace_id"), 96).lower()
    bound_tenant = _clean(manifest.get("bound_tenant_id"), 120)
    bound_workspace = _clean(manifest.get("bound_workspace_id"), 96).lower()
    workspaces = {
        _clean(item, 96).lower()
        for item in list(manifest.get("workspace_ids") or [])
        if _clean(item, 96)
    }
    if (
        not trusted_tenant
        or not trusted_workspace
        or bound_tenant != trusted_tenant
        or bound_workspace != trusted_workspace
        or trusted_workspace not in workspaces
    ):
        blockers.append("CERTIFICATION_SCOPE_MISMATCH")

    blockers = list(dict.fromkeys(blockers))
    return {
        "valid": not blockers,
        "state": state,
        "manifest": manifest,
        "fingerprint": _clean(raw.get("fingerprint"), 128),
        "record_fingerprint": record_fingerprint,
        "blockers": blockers,
    }


def plan_certified_skill_tool_call(
    certification_record: Mapping[str, Any] | None,
    tool_id: Any,
    *,
    trusted_context: Mapping[str, Any] | None,
    capability_registry: CapabilityRegistry | None = None,
    tool_hub: Mapping[str, Any] | None = None,
    portable_core: Mapping[str, Any] | None = None,
    access: Mapping[str, Any] | None = None,
    source_kind: Any = "ADMIN",
    authenticated_admin: Any = False,
    approved: Any = False,
    feature_flags: Mapping[str, Any] | None = None,
    scope: Any = "",
    artifacts: Sequence[Any] | None = None,
    tests: Sequence[Mapping[str, Any]] | None = None,
    rollback_plan: Any = "",
    uncertainty_pct: Any = 100,
    impact: Any = "MEDIUM",
    reversible: Any = False,
) -> dict[str, Any]:
    """Build Tool Hub preflight from a sealed, currently valid certification."""
    record = dict(certification_record or {})
    record_gate = _record_gate(record, trusted_context=trusted_context)
    manifest = dict(record_gate.get("manifest") or {})

    current_policy = assess_skill_manifest(
        manifest,
        trusted_context=trusted_context,
        capability_registry=capability_registry,
        tool_hub=tool_hub,
        test_evidence=None,
        provenance_verifier=None,
        review_approved=False,
    )
    requested_tool = _clean(tool_id, 96).lower()
    declared_tools = set(manifest.get("tool_ids") or [])

    blockers: list[str] = list(record_gate.get("blockers") or [])
    for blocker in list(current_policy.get("blockers") or []):
        blockers.append("CURRENT_POLICY_BLOCKED:" + str(blocker))
    if (
        record_gate.get("fingerprint")
        and current_policy.get("fingerprint") != record_gate.get("fingerprint")
    ):
        blockers.append("CERTIFICATION_POLICY_DRIFT")
    if not requested_tool or requested_tool not in declared_tools:
        blockers.append("TOOL_NOT_DECLARED_BY_SKILL")
    blockers = list(dict.fromkeys(blockers))

    if blockers:
        return {
            "schema": SCHEMA,
            "state": "BLOCK",
            "reason": blockers[0],
            "blockers": blockers,
            "certification_record": record,
            "record_gate": record_gate,
            "current_policy": current_policy,
            "tool_preflight": None,
            "certification_is_authority": False,
            "activates_skill": False,
            "activates_connector": False,
            "executes_tool": False,
            "tool_called": False,
            "connector_called": False,
            "expands_permissions": False,
            "creates_entitlement": False,
            "real_trading_enabled": False,
        }

    tool_preflight = plan_tool_call(
        requested_tool,
        hub=tool_hub,
        portable_core=portable_core,
        access=access,
        source_kind=source_kind,
        authenticated_admin=authenticated_admin is True,
        approved=approved is True,
        feature_flags=feature_flags,
        scope=scope,
        artifacts=artifacts,
        tests=tests,
        rollback_plan=rollback_plan,
        uncertainty_pct=uncertainty_pct,
        impact=impact,
        reversible=reversible is True,
    )
    downstream_blockers = [
        str(item)
        for item in list(tool_preflight.get("blockers") or [])
        if str(item)
    ]
    return {
        "schema": SCHEMA,
        "state": str(tool_preflight.get("state") or "BLOCK"),
        "reason": str(tool_preflight.get("reason") or ""),
        "blockers": downstream_blockers,
        "certification_record": record,
        "record_gate": record_gate,
        "current_policy": current_policy,
        "tool_preflight": tool_preflight,
        "certification_is_authority": False,
        "activates_skill": False,
        "activates_connector": False,
        "executes_tool": False,
        "tool_called": False,
        "connector_called": False,
        "expands_permissions": False,
        "creates_entitlement": False,
        "real_trading_enabled": False,
    }


__all__ = ["SCHEMA", "plan_certified_skill_tool_call"]
