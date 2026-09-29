"""Registry-aware model routing bridge for AION.

The low-level router remains provider-neutral and independent. This bridge
combines its budget/privacy gates with the evidence-based Model Registry.
An external lane is eligible only when the exact scoped model record is
APPROVED, integrity-matching and eligible_as_default=True.

No provider is called and no billing occurs here.
"""
from __future__ import annotations

from typing import Any, Mapping

from atlasquant_aion_model_registry import (
    canonical_fingerprint,
    read_model,
)
from atlasquant_aion_model_router import route_intelligence

SCHEMA = "ATLASQUANT_AION_MODEL_ROUTING_BRIDGE_V1"


def _record_integrity(record: Mapping[str, Any]) -> bool:
    presented = str(record.get("fingerprint") or "").strip()
    if not presented:
        return False
    body = {
        key: value
        for key, value in dict(record).items()
        if key not in {"fingerprint", "authority", "persisted"}
    }
    return presented == canonical_fingerprint(body)


def route_registered_model(
    task: Any,
    *,
    registry: Mapping[str, Any] | None,
    provider: Any,
    model_id: Any,
    version: Any,
    trusted_context: Mapping[str, Any] | None,
    provider_state: Any = "ZERO_COST_LOCAL",
    external_feature_enabled: Any = False,
    budget: Mapping[str, Any] | None = None,
    estimated_request_cost_usd: Any = 0.0,
    request_approved: Any = False,
    force_private: Any = False,
) -> dict[str, Any]:
    """Choose a route only after registry eligibility is rechecked."""
    model = read_model(
        registry,
        provider=provider,
        model_id=model_id,
        version=version,
        trusted_context=trusted_context,
    )
    integrity_ok = _record_integrity(model)
    registry_approved = (
        integrity_ok
        and model.get("approval_state") == "APPROVED"
        and model.get("eligible_as_default") is True
        and not list(model.get("blockers") or [])
    )
    requested_external = external_feature_enabled is True
    route = route_intelligence(
        task,
        provider_state=provider_state if registry_approved else "REGISTRY_BLOCKED",
        external_feature_enabled=requested_external and registry_approved,
        budget=budget,
        estimated_request_cost_usd=estimated_request_cost_usd,
        request_approved=request_approved is True,
        force_private=force_private is True,
    )
    blockers = list(model.get("blockers") or [])
    if not integrity_ok:
        blockers.append("MODEL_RECORD_INTEGRITY_FAILED")
    if model.get("approval_state") != "APPROVED":
        blockers.append("MODEL_NOT_APPROVED")
    if model.get("eligible_as_default") is not True:
        blockers.append("MODEL_NOT_DEFAULT_ELIGIBLE")
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": SCHEMA,
        "route": route,
        "lane": route["lane"],
        "registry_approved": registry_approved,
        "registry_integrity": "MATCH" if integrity_ok else "MISMATCH",
        "registry_blockers": blockers,
        "model_ref": {
            "provider": str(provider or ""),
            "model_id": str(model_id or ""),
            "version": str(version or ""),
            "fingerprint": str(model.get("fingerprint") or ""),
        },
        "external_lane_allowed": (
            registry_approved
            and requested_external
            and route["lane"] in {"EXTERNAL_FAST", "EXTERNAL_REASONING"}
        ),
        "executes_provider_call": False,
        "executes_billing": False,
        "activates_paid_api": False,
        "real_trading_enabled": False,
    }


__all__ = ["SCHEMA", "route_registered_model"]
