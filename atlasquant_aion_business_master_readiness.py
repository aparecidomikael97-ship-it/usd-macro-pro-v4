"""AION BUSINESS Master Readiness Panel V1.

Pure aggregation layer that distinguishes demo readiness, pilot-review readiness
and live runtime authority. Passing product/demo gates never activates runtime,
authorizes a pilot, contacts a client, publishes, charges or deploys.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

SCHEMA = "ATLASQUANT_AION_BUSINESS_MASTER_READINESS_V1"
VERSION = "1"

DEMO_GATES = (
    "business_certified",
    "demo_ui_ready",
    "training_ready",
    "diagnostic_proposal_ready",
    "client_portal_demo_ready",
    "onboarding_demo_ready",
    "customer_success_demo_ready",
    "finance_capacity_demo_ready",
    "trend_intelligence_ready",
    "commercial_acquisition_demo_ready",
    "integration_hub_readiness_ready",
    "privacy_audit_governance_ready",
)

PILOT_GATES = (
    "business_certified",
    "admin_training_completed",
    "package_scope_reviewed",
    "privacy_profile_reviewed",
    "support_sla_reviewed",
    "client_finance_reviewed",
    "capacity_reviewed",
    "integration_scope_reviewed",
    "rollback_plan_reviewed",
    "contract_template_reviewed",
    "human_operator_assigned",
)

LIVE_GATES = (
    "pilot_authorized",
    "runtime_approval_recorded",
    "real_credentials_provisioned",
    "provider_health_verified",
    "production_rollback_verified",
    "external_actions_approved",
)


def _exact_true(value: Any) -> bool:
    return type(value) is bool and value is True


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _gate_snapshot(source: Mapping[str, Any], names: Sequence[str]) -> dict[str, Any]:
    rows = []
    for name in names:
        passed = _exact_true(source.get(name))
        rows.append({"gate": name, "passed": passed})
    passed_count = sum(1 for row in rows if row["passed"])
    total = len(rows)
    pct = round(passed_count / total * 100, 1) if total else 0.0
    return {
        "rows": rows,
        "passed_count": passed_count,
        "total": total,
        "progress_pct": pct,
        "complete": bool(total and passed_count == total),
        "missing": [row["gate"] for row in rows if not row["passed"]],
    }


def master_readiness_snapshot(evidence: Mapping[str, Any] | None) -> dict[str, Any]:
    source = _mapping(evidence)
    demo = _gate_snapshot(source, DEMO_GATES)
    pilot = _gate_snapshot(source, PILOT_GATES)
    live = _gate_snapshot(source, LIVE_GATES)

    if demo["complete"]:
        demo_state = "DEMO_READY"
    elif demo["passed_count"] >= max(1, demo["total"] // 2):
        demo_state = "DEMO_IN_PROGRESS"
    else:
        demo_state = "DEMO_BLOCKED"

    if pilot["complete"]:
        pilot_state = "PILOT_REVIEW_REQUIRED"
    else:
        pilot_state = "PILOT_BLOCKED"

    # Live runtime is intentionally not derivable from product/demo readiness.
    live_state = "LIVE_REVIEW_REQUIRED" if live["complete"] else "RUNTIME_OFF"

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "demo": {**demo, "state": demo_state},
        "pilot": {**pilot, "state": pilot_state},
        "live": {**live, "state": live_state},
        "pilot_authorized": False,
        "live_runtime_authorized": False,
        "runtime_activated": False,
        "external_actions_enabled": False,
        "payment_enabled": False,
        "publication_enabled": False,
        "executes_action": False,
    }


def pilot_review_packet(
    snapshot: Mapping[str, Any] | None,
    *,
    requested_by: Any,
    pilot_scope: Any,
) -> dict[str, Any]:
    row = _mapping(snapshot)
    pilot = _mapping(row.get("pilot"))
    requester = str(requested_by or "").strip()[:120]
    scope = str(pilot_scope or "").strip()[:500]
    eligible = bool(
        row.get("schema") == SCHEMA
        and pilot.get("state") == "PILOT_REVIEW_REQUIRED"
        and pilot.get("complete") is True
        and requester
        and scope
        and row.get("runtime_activated") is False
    )
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_PILOT_REVIEW_PACKET_V1",
        "state": "PILOT_REVIEW_REQUIRED" if eligible else "BLOCKED",
        "requested_by": requester if eligible else "",
        "pilot_scope": scope if eligible else "",
        "eligible_for_human_review": eligible,
        "pilot_authorized": False,
        "runtime_activation_approved": False,
        "external_contact_authorized": False,
        "contract_signature_authorized": False,
        "payment_authorized": False,
        "publication_authorized": False,
        "executes_action": False,
    }


def status_rows(snapshot: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    row = _mapping(snapshot)
    demo = _mapping(row.get("demo"))
    pilot = _mapping(row.get("pilot"))
    live = _mapping(row.get("live"))
    return [
        {
            "layer": "DEMO",
            "state": demo.get("state") or "UNKNOWN",
            "progress_pct": float(demo.get("progress_pct") or 0),
            "next_step": (
                "Revisar experiência e testes."
                if demo.get("complete") else
                "Fechar os gates demo restantes."
            ),
        },
        {
            "layer": "PILOT",
            "state": pilot.get("state") or "UNKNOWN",
            "progress_pct": float(pilot.get("progress_pct") or 0),
            "next_step": (
                "Preparar revisão humana de piloto."
                if pilot.get("complete") else
                "Revisar operação, privacidade, SLA, margem, capacidade e contrato."
            ),
        },
        {
            "layer": "LIVE",
            "state": live.get("state") or "RUNTIME_OFF",
            "progress_pct": float(live.get("progress_pct") or 0),
            "next_step": (
                "Revisão humana separada de runtime."
                if live.get("complete") else
                "Runtime permanece OFF."
            ),
        },
    ]


def default_demo_evidence() -> dict[str, bool]:
    """Current product-demo gates only; deliberately excludes pilot/live approval."""
    return {
        "business_certified": True,
        "demo_ui_ready": True,
        "training_ready": True,
        "diagnostic_proposal_ready": True,
        "client_portal_demo_ready": True,
        "onboarding_demo_ready": True,
        "customer_success_demo_ready": True,
        "finance_capacity_demo_ready": True,
        "trend_intelligence_ready": True,
        "commercial_acquisition_demo_ready": True,
        "integration_hub_readiness_ready": True,
        "privacy_audit_governance_ready": True,
        # Pilot gates remain false until independently reviewed.
        "admin_training_completed": False,
        "package_scope_reviewed": False,
        "privacy_profile_reviewed": False,
        "support_sla_reviewed": False,
        "client_finance_reviewed": False,
        "capacity_reviewed": False,
        "integration_scope_reviewed": False,
        "rollback_plan_reviewed": False,
        "contract_template_reviewed": False,
        "human_operator_assigned": False,
        # Live gates remain false.
        "pilot_authorized": False,
        "runtime_approval_recorded": False,
        "real_credentials_provisioned": False,
        "provider_health_verified": False,
        "production_rollback_verified": False,
        "external_actions_approved": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "DEMO_GATES",
    "PILOT_GATES",
    "LIVE_GATES",
    "master_readiness_snapshot",
    "pilot_review_packet",
    "status_rows",
    "default_demo_evidence",
]
