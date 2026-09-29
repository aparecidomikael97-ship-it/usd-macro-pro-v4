"""AION staged-release / feature-flag governance V1.

Pure, read-only release eligibility contract for the AtlasQuant Núcleo.

This module never flips a feature flag, deploys, publishes, charges, starts a
worker, changes entitlements or authorizes real trading. It only evaluates
whether evidence is sufficient for a requested exposure layer.

Layers:
- DISABLED: feature is not exposed;
- INTERNAL: admin/internal validation only;
- PILOT: explicitly approved limited exposure;
- GENERAL: broad exposure after stronger evidence and approval.

A feature flag being ON is necessary evidence for exposure, but never proves
that the integration is operational or safe.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence


SCHEMA = "ATLASQUANT_AION_RELEASE_LAYERS_V1"

LAYERS = ("DISABLED", "INTERNAL", "PILOT", "GENERAL")
STATES = ("BLOCKED", "EVIDENCE_PENDING", "HUMAN_REVIEW_READY", "ELIGIBLE")

HIGH_RISK_FEATURES = frozenset({
    "external_llm",
    "social_publish",
    "marketplace_publish",
    "marketplace_orders",
    "payment_provider",
    "promotion_activation",
    "entitlement_activation",
    "production_deploy",
    "auto_merge",
    "real_broker_execution",
})

NEVER_GENERAL_FEATURES = frozenset({
    "auto_merge",
    "real_broker_execution",
})


def _text(value: Any, limit: int = 180) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _bool(value: Any) -> bool:
    return value is True


def _layer(value: Any) -> str:
    raw = _text(value, 40).upper()
    return raw if raw in LAYERS else "DISABLED"


def _feature(value: Any) -> str:
    return _text(value, 80).lower()


def _evidence_flags(evidence: Mapping[str, Any] | None) -> dict[str, bool]:
    data = dict(evidence or {})
    return {
        "operational_verified": _bool(data.get("operational_verified")),
        "health_confirmed": _bool(data.get("health_confirmed")),
        "release_gate_confirmed": _bool(data.get("release_gate_confirmed")),
        "cost_reviewed": _bool(data.get("cost_reviewed")),
        "rollback_ready": _bool(data.get("rollback_ready")),
        "privacy_reviewed": _bool(data.get("privacy_reviewed")),
        "tenant_isolation_confirmed": _bool(data.get("tenant_isolation_confirmed")),
    }


def required_evidence(feature: Any, requested_layer: Any) -> tuple[str, ...]:
    """Return evidence keys required for eligibility; no side effects."""
    feat = _feature(feature)
    layer = _layer(requested_layer)

    if layer == "DISABLED":
        return ()

    base = (
        "operational_verified",
        "health_confirmed",
        "release_gate_confirmed",
    )

    if layer == "INTERNAL":
        return base

    pilot = base + (
        "cost_reviewed",
        "rollback_ready",
        "privacy_reviewed",
    )

    if layer == "PILOT":
        return pilot

    general = pilot + ("tenant_isolation_confirmed",)
    if feat in {"production_deploy", "auto_merge"}:
        # These are administrative/production actions rather than subscriber
        # experiences; tenant isolation is not meaningful for their eligibility.
        general = pilot
    return general


def assess_feature_release(
    *,
    feature: Any,
    requested_layer: Any,
    current_layer: Any = "DISABLED",
    feature_flag_enabled: bool = False,
    evidence: Mapping[str, Any] | None = None,
    admin_approved: bool = False,
) -> dict[str, Any]:
    """Evaluate staged-release eligibility without changing any live control."""
    feat = _feature(feature)
    requested = _layer(requested_layer)
    current = _layer(current_layer)
    flags = _evidence_flags(evidence)

    reasons: list[str] = []
    blockers: list[str] = []

    if not feat:
        blockers.append("FEATURE_REQUIRED")

    if feat == "real_broker_execution":
        blockers.append("REAL_TRADING_ALWAYS_BLOCKED")

    if requested == "GENERAL" and feat in NEVER_GENERAL_FEATURES:
        blockers.append("GENERAL_LAYER_FORBIDDEN")

    if requested != "DISABLED" and not feature_flag_enabled:
        blockers.append("FEATURE_FLAG_OFF")

    required = required_evidence(feat, requested)
    missing = [key for key in required if not flags.get(key, False)]

    if missing:
        reasons.append("MISSING_EVIDENCE")

    approval_required = requested in {"PILOT", "GENERAL"}
    if approval_required and not admin_approved:
        reasons.append("ADMIN_APPROVAL_REQUIRED")

    if blockers:
        state = "BLOCKED"
    elif requested == "DISABLED":
        state = "ELIGIBLE"
    elif missing:
        state = "EVIDENCE_PENDING"
    elif approval_required and not admin_approved:
        state = "HUMAN_REVIEW_READY"
    else:
        state = "ELIGIBLE"

    can_apply = bool(
        state == "ELIGIBLE"
        and requested != "DISABLED"
        and feat != "real_broker_execution"
    )

    return {
        "schema": SCHEMA,
        "feature": feat,
        "current_layer": current,
        "requested_layer": requested,
        "state": state,
        "feature_flag_enabled": bool(feature_flag_enabled),
        "required_evidence": list(required),
        "missing_evidence": missing,
        "evidence": flags,
        "admin_approval_required": approval_required,
        "admin_approved": bool(admin_approved),
        "blockers": blockers,
        "reasons": reasons,
        "eligible_for_manual_application": can_apply,
        "automatic_flag_change": False,
        "automatic_deploy": False,
        "automatic_publish": False,
        "automatic_charge": False,
        "automatic_entitlement_change": False,
        "real_trading_enabled": False,
        "executes_action": False,
        "interpretation": (
            "Elegibilidade significa apenas que a evidência mínima para revisão "
            "da camada solicitada está presente. Nenhuma flag é alterada automaticamente."
        ),
    }


def build_release_matrix(
    requests: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Evaluate multiple features and summarize staged-release posture."""
    rows = []
    for raw in list(requests or [])[:100]:
        if not isinstance(raw, Mapping):
            continue
        rows.append(
            assess_feature_release(
                feature=raw.get("feature"),
                requested_layer=raw.get("requested_layer"),
                current_layer=raw.get("current_layer", "DISABLED"),
                feature_flag_enabled=raw.get("feature_flag_enabled") is True,
                evidence=raw.get("evidence")
                if isinstance(raw.get("evidence"), Mapping)
                else {},
                admin_approved=raw.get("admin_approved") is True,
            )
        )

    counts = {state: 0 for state in STATES}
    for row in rows:
        counts[row["state"]] += 1

    if counts["BLOCKED"]:
        state = "BLOCKED"
    elif counts["EVIDENCE_PENDING"]:
        state = "EVIDENCE_PENDING"
    elif counts["HUMAN_REVIEW_READY"]:
        state = "HUMAN_REVIEW_READY"
    elif rows:
        state = "ELIGIBLE"
    else:
        state = "UNKNOWN"

    return {
        "schema": SCHEMA,
        "state": state,
        "items": rows,
        "counts": counts,
        "total": len(rows),
        "eligible_manual_items": sum(
            1 for row in rows if row["eligible_for_manual_application"]
        ),
        "automatic_flag_change": False,
        "automatic_deploy": False,
        "automatic_publish": False,
        "automatic_charge": False,
        "real_trading_enabled": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "LAYERS",
    "STATES",
    "HIGH_RISK_FEATURES",
    "NEVER_GENERAL_FEATURES",
    "required_evidence",
    "assess_feature_release",
    "build_release_matrix",
]
