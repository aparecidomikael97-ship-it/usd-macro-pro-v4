"""Activation gate for AION worker coordination modes.

V1 distinguishes the current GitHub checkpoint CAS posture from a future
multi-instance shared coordination adapter. Structural adapter evidence is not
operational proof. Therefore MULTI_INSTANCE_SHARED_ADAPTER stays fail-closed in
this version until a separate, live operational verification contract exists.
"""
from __future__ import annotations

from typing import Any, Mapping

from atlasquant_aion_coordination_adapter_readiness import PROBE_EVIDENCE_READY


SCHEMA = "ATLASQUANT_AION_COORDINATION_MODE_GATE_V1"
CURRENT_MODE = "CHECKPOINT_CAS_CURRENT"
MULTI_INSTANCE_MODE = "MULTI_INSTANCE_SHARED_ADAPTER"
MODES = frozenset({CURRENT_MODE, MULTI_INSTANCE_MODE})


def _clean(value: Any, limit: int = 160) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def coordination_activation_gate(
    mode: Any = CURRENT_MODE,
    *,
    coordination_readiness: Mapping[str, Any] | None = None,
    operational_verification: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    requested = _clean(mode, 80).upper()
    report = dict(coordination_readiness or {})

    if requested not in MODES:
        return {
            "schema": SCHEMA,
            "state": "BLOCK",
            "reason": "COORDINATION_MODE_INVALID",
            "mode": requested or "UNKNOWN",
            "adapter_id": "",
            "adapter_identity_digest": "",
            "structural_evidence_present": False,
            "operational_verification": "UNKNOWN",
            "multi_instance_verified": False,
            "allows_activation_plan": False,
            "executes_action": False,
            "changes_worker": False,
            "changes_feature_flag": False,
        }

    if requested == CURRENT_MODE:
        return {
            "schema": SCHEMA,
            "state": "READY_CURRENT_MODE",
            "reason": "CURRENT_CHECKPOINT_CAS_POSTURE",
            "mode": CURRENT_MODE,
            "adapter_id": "",
            "adapter_identity_digest": "",
            "structural_evidence_present": False,
            "operational_verification": "NOT_REQUIRED_FOR_CURRENT_MODE",
            "multi_instance_verified": False,
            "allows_activation_plan": True,
            "executes_action": False,
            "changes_worker": False,
            "changes_feature_flag": False,
        }

    structural = (
        report.get("state") == PROBE_EVIDENCE_READY
        and report.get("probe_evidence_accepted") is True
        and report.get("probe_receipt_structurally_valid") is True
    )
    operational = dict(operational_verification or {})
    adapter_digest = _clean(report.get("adapter_identity_digest"), 128)
    operational_matches = (
        operational.get("state") == "VERIFIED"
        and operational.get("multi_instance_verified") is True
        and _clean(operational.get("adapter_identity_digest"), 128) == adapter_digest
        and adapter_digest
    )

    if not report:
        reason = "COORDINATION_ADAPTER_EVIDENCE_REQUIRED"
    elif not structural:
        reason = "COORDINATION_STRUCTURAL_EVIDENCE_REQUIRED"
    elif not operational:
        reason = "COORDINATION_OPERATIONAL_VERIFICATION_REQUIRED"
    elif not operational_matches:
        reason = "COORDINATION_OPERATIONAL_VERIFICATION_INVALID"
    else:
        reason = "MULTI_INSTANCE_RUNTIME_INTEGRATION_REQUIRED"

    return {
        "schema": SCHEMA,
        "state": "VERIFIED_NOT_ACTIVATABLE" if operational_matches else "BLOCK",
        "reason": reason,
        "mode": MULTI_INSTANCE_MODE,
        "adapter_id": _clean(report.get("adapter_id"), 80),
        "adapter_identity_digest": adapter_digest,
        "structural_evidence_present": structural,
        "operational_verification": (
            "VERIFIED"
            if operational_matches
            else _clean(operational.get("operational_verification"), 40)
            or _clean(report.get("operational_verification"), 40)
            or "UNKNOWN"
        ),
        "multi_instance_verified": bool(operational_matches),
        "runtime_integration_ready": False,
        "allows_activation_plan": False,
        "executes_action": False,
        "changes_worker": False,
        "changes_feature_flag": False,
    }


__all__ = [
    "SCHEMA",
    "CURRENT_MODE",
    "MULTI_INSTANCE_MODE",
    "MODES",
    "coordination_activation_gate",
]
