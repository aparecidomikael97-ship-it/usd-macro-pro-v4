"""Certified-skill bridge into the existing AION Tool Hub preflight.

Certification is a prerequisite, never authority. A CERTIFIED manifest may ask
the Tool Hub to build a preflight only for tools declared in that manifest.
The Tool Hub still revalidates source authority, Guardian, connector readiness,
scope, tests, rollback and side effects. No tool or connector is called here.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from atlasquant_aion_capabilities import CapabilityRegistry
from atlasquant_aion_skill_certification import assess_skill_manifest
from atlasquant_aion_tool_hub import plan_tool_call


SCHEMA = "ATLASQUANT_AION_SKILL_TOOL_BRIDGE_V1"


def _clean(value: Any, limit: int = 160) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def plan_certified_skill_tool_call(
    manifest: Mapping[str, Any] | None,
    tool_id: Any,
    *,
    trusted_context: Mapping[str, Any] | None,
    capability_registry: CapabilityRegistry | None = None,
    tool_hub: Mapping[str, Any] | None = None,
    test_evidence: Mapping[str, Any] | None = None,
    provenance_verifier: Callable[[Sequence[str]], Mapping[str, Any]] | None = None,
    review_approved: Any = False,
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
    """Build a Tool Hub preflight only after manifest certification succeeds."""
    certification = assess_skill_manifest(
        manifest,
        trusted_context=trusted_context,
        capability_registry=capability_registry,
        tool_hub=tool_hub,
        test_evidence=test_evidence,
        provenance_verifier=provenance_verifier,
        review_approved=review_approved,
    )
    requested_tool = _clean(tool_id, 96).lower()
    declared_tools = set(certification.get("manifest", {}).get("tool_ids") or [])

    blockers: list[str] = []
    if certification.get("state") != "CERTIFIED":
        blockers.append("SKILL_NOT_CERTIFIED:" + str(certification.get("state") or "UNKNOWN"))
    if not requested_tool or requested_tool not in declared_tools:
        blockers.append("TOOL_NOT_DECLARED_BY_SKILL")

    if blockers:
        return {
            "schema": SCHEMA,
            "state": "BLOCK",
            "reason": blockers[0],
            "blockers": blockers,
            "certification": certification,
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
        "certification": certification,
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
