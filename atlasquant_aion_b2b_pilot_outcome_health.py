"""AION B2B pilot outcome, realized-value and customer-health gate.

Pure/offline decision support. It evaluates evidence from a bounded pilot and
returns review candidates only. It never renews, pauses, terminates, bills,
contacts a customer, changes scope, deploys, or mutates production.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

SCHEMA = "ATLASQUANT_AION_B2B_PILOT_OUTCOME_HEALTH_V1"
MAX_MONTHLY_INFRA_BRL = 200.0


def _text(value: Any, limit: int = 320) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _pct(value: Any) -> float | None:
    out = _number(value)
    if out is None or out < 0 or out > 100:
        return None
    return out


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(data.get("owner_id"), 120),
        "tenant_id": _text(data.get("tenant_id"), 120),
        "workspace_id": _text(data.get("workspace_id"), 120),
    }


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _refs(value: Any, limit: int = 50) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:limit]:
        item = _text(raw, 320)
        if item and item not in out:
            out.append(item)
    return out


def _validate_contract(contract_result: Mapping[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    data = dict(contract_result) if isinstance(contract_result, Mapping) else {}
    blockers: list[str] = []
    if data.get("state") != "DRAFT_FOR_OWNER_APPROVAL":
        blockers.append("OPERATING_CONTRACT_NOT_REVIEWABLE")
    if data.get("activation_state") != "BLOCKED_UNTIL_OWNER_APPROVAL":
        blockers.append("OPERATING_CONTRACT_ACTIVATION_BOUNDARY_INVALID")
    if data.get("human_owner_approval_required") is not True:
        blockers.append("OWNER_APPROVAL_BOUNDARY_MISSING")
    if data.get("blockers"):
        blockers.append("OPERATING_CONTRACT_HAS_BLOCKERS")
    if not _text(data.get("contract_digest"), 180):
        blockers.append("OPERATING_CONTRACT_DIGEST_REQUIRED")
    core = data.get("contract")
    if not isinstance(core, Mapping):
        blockers.append("OPERATING_CONTRACT_PAYLOAD_REQUIRED")
        core = {}
    return dict(core), blockers


def _validate_owner_attestation(
    raw: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any],
    pilot_id: str,
) -> list[str]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    blockers: list[str] = []
    if data.get("state") != "CONFIRMED":
        blockers.append("OWNER_PILOT_APPROVAL_NOT_CONFIRMED")
    if data.get("approved_by_owner") is not True:
        blockers.append("OWNER_PILOT_APPROVAL_REQUIRED")
    if _scope(data) != _scope(trusted_scope):
        blockers.append("OWNER_APPROVAL_SCOPE_MISMATCH")
    if _text(data.get("pilot_id"), 120) != pilot_id:
        blockers.append("OWNER_APPROVAL_PILOT_MISMATCH")
    if not _text(data.get("approval_ref"), 320):
        blockers.append("OWNER_APPROVAL_REF_REQUIRED")
    return blockers


def _normalize_measurements(
    contract_kpis: Sequence[Mapping[str, Any]],
    measurements: Sequence[Mapping[str, Any]] | None,
) -> tuple[dict[str, dict[str, Any]], list[str], float, float]:
    expected = {
        _text(item.get("metric_id"), 100): dict(item)
        for item in contract_kpis
        if isinstance(item, Mapping) and _text(item.get("metric_id"), 100)
    }
    blockers: list[str] = []
    supplied: dict[str, Mapping[str, Any]] = {}
    for raw in measurements or []:
        if not isinstance(raw, Mapping):
            blockers.append("KPI_MEASUREMENT_INVALID")
            continue
        metric_id = _text(raw.get("metric_id"), 100)
        if not metric_id or metric_id in supplied:
            blockers.append("KPI_MEASUREMENT_ID_INVALID_OR_DUPLICATE")
            continue
        supplied[metric_id] = raw

    normalized: dict[str, dict[str, Any]] = {}
    valid = 0
    hits = 0
    for metric_id, kpi in expected.items():
        raw = supplied.get(metric_id)
        if raw is None:
            normalized[metric_id] = {"state": "MISSING", "target_hit": False}
            continue
        current = _number(raw.get("current"))
        source_ref = _text(raw.get("source_ref"), 320)
        if current is None or not source_ref:
            normalized[metric_id] = {"state": "INVALID", "target_hit": False}
            blockers.append(f"KPI_MEASUREMENT_INVALID:{metric_id}")
            continue
        valid += 1
        target = _number(kpi.get("target"))
        direction = _text(kpi.get("direction"), 20).upper()
        hit = bool(
            target is not None
            and (
                (direction == "HIGHER" and current >= target)
                or (direction == "LOWER" and current <= target)
            )
        )
        if hit:
            hits += 1
        normalized[metric_id] = {
            "state": "MEASURED",
            "current": current,
            "target": target,
            "direction": direction,
            "target_hit": hit,
            "source_ref": source_ref,
        }

    total = len(expected)
    completion = round(valid / total * 100.0, 2) if total else 0.0
    target_hit = round(hits / total * 100.0, 2) if total else 0.0
    if not expected:
        blockers.append("CONTRACT_KPIS_MISSING")
    return normalized, list(dict.fromkeys(blockers)), completion, target_hit


def evaluate_pilot_outcome(
    *,
    trusted_scope: Mapping[str, Any],
    contract_result: Mapping[str, Any],
    owner_activation_attestation: Mapping[str, Any],
    measurements: Sequence[Mapping[str, Any]] | None,
    observed: Mapping[str, Any],
) -> dict[str, Any]:
    core, blockers = _validate_contract(contract_result)
    trusted = _scope(trusted_scope)
    core_scope = _scope(core)
    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")
    if core_scope != trusted:
        blockers.append("OPERATING_CONTRACT_SCOPE_MISMATCH")

    pilot_id = _text(core.get("pilot_id"), 120)
    blockers.extend(
        _validate_owner_attestation(
            owner_activation_attestation,
            trusted_scope=trusted_scope,
            pilot_id=pilot_id,
        )
    )

    kpis = core.get("kpis") if isinstance(core.get("kpis"), (list, tuple)) else []
    progress, kpi_blockers, completion_pct, target_hit_pct = _normalize_measurements(kpis, measurements)
    blockers.extend(kpi_blockers)

    data = dict(observed) if isinstance(observed, Mapping) else {}
    if _scope(data) != trusted:
        blockers.append("OBSERVED_SCOPE_MISMATCH")
    if _text(data.get("pilot_id"), 120) != pilot_id:
        blockers.append("OBSERVED_PILOT_MISMATCH")

    adoption_pct = _pct(data.get("adoption_pct"))
    sla_met_pct = _pct(data.get("sla_met_pct"))
    reliability_pct = _pct(data.get("automation_reliability_pct"))
    evidence_coverage_pct = _pct(data.get("evidence_coverage_pct"))
    if adoption_pct is None:
        blockers.append("ADOPTION_PCT_INVALID")
    if sla_met_pct is None:
        blockers.append("SLA_MET_PCT_INVALID")
    if reliability_pct is None:
        blockers.append("AUTOMATION_RELIABILITY_PCT_INVALID")
    if evidence_coverage_pct is None:
        blockers.append("EVIDENCE_COVERAGE_PCT_INVALID")

    baseline_cost = _number(data.get("manual_baseline_cost_brl"))
    operating_cost = _number(data.get("observed_operating_cost_brl"))
    monthly_infra = _number(data.get("observed_monthly_infra_brl"))
    if baseline_cost is None or baseline_cost < 0:
        blockers.append("MANUAL_BASELINE_COST_INVALID")
    if operating_cost is None or operating_cost < 0:
        blockers.append("OBSERVED_OPERATING_COST_INVALID")
    if monthly_infra is None or monthly_infra < 0:
        blockers.append("OBSERVED_MONTHLY_INFRA_INVALID")
    elif monthly_infra > MAX_MONTHLY_INFRA_BRL:
        blockers.append("OBSERVED_MONTHLY_INFRA_CAP_EXCEEDED")

    evidence_refs = _refs(data.get("evidence_refs"))
    if len(evidence_refs) < 4:
        blockers.append("OBSERVED_EVIDENCE_INSUFFICIENT")

    savings_brl: float | None = None
    roi_pct: float | None = None
    if baseline_cost is not None and operating_cost is not None:
        savings_brl = round(baseline_cost - operating_cost, 2)
        if operating_cost > 0:
            roi_pct = round((savings_brl / operating_cost) * 100.0, 2)
        elif baseline_cost > 0:
            roi_pct = None

    critical_incidents = data.get("critical_incident_count")
    security_incidents = data.get("security_incident_count")
    privacy_incidents = data.get("privacy_incident_count")
    scope_breaches = data.get("scope_breach_count")
    for key, value in (
        ("CRITICAL_INCIDENT_COUNT", critical_incidents),
        ("SECURITY_INCIDENT_COUNT", security_incidents),
        ("PRIVACY_INCIDENT_COUNT", privacy_incidents),
        ("SCOPE_BREACH_COUNT", scope_breaches),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            blockers.append(f"{key}_INVALID")

    hard_stop_reasons: list[str] = []
    if isinstance(critical_incidents, int) and critical_incidents > 0:
        hard_stop_reasons.append("CRITICAL_INCIDENT_PRESENT")
    if isinstance(security_incidents, int) and security_incidents > 0:
        hard_stop_reasons.append("SECURITY_INCIDENT_PRESENT")
    if isinstance(privacy_incidents, int) and privacy_incidents > 0:
        hard_stop_reasons.append("PRIVACY_INCIDENT_PRESENT")
    if isinstance(scope_breaches, int) and scope_breaches > 0:
        hard_stop_reasons.append("SCOPE_BREACH_PRESENT")

    health_score: float | None = None
    if all(x is not None for x in (adoption_pct, sla_met_pct, reliability_pct, evidence_coverage_pct)):
        roi_component = 100.0 if roi_pct is not None and roi_pct >= 0 else 0.0
        health_score = round(
            target_hit_pct * 0.30
            + float(adoption_pct) * 0.15
            + float(sla_met_pct) * 0.15
            + float(reliability_pct) * 0.15
            + float(evidence_coverage_pct) * 0.10
            + roi_component * 0.15,
            2,
        )

    if blockers:
        decision = "BLOCKED"
        state = "BLOCKED"
    elif hard_stop_reasons:
        decision = "STOP_REVIEW"
        state = "STOP_REVIEW"
    elif completion_pct < 100.0:
        decision = "EVIDENCE_REVIEW"
        state = "EVIDENCE_INCOMPLETE"
    elif health_score is not None and health_score >= 80 and (roi_pct is not None and roi_pct >= 0):
        decision = "CONTINUE_REVIEW_CANDIDATE"
        state = "HEALTHY"
    elif health_score is not None and health_score >= 60:
        decision = "PAUSE_OR_REMEDIATE_REVIEW"
        state = "WATCH"
    else:
        decision = "EXIT_REVIEW_CANDIDATE"
        state = "UNHEALTHY"

    evidence = {
        "pilot_id": pilot_id,
        "scope": trusted,
        "contract_digest": _text(contract_result.get("contract_digest"), 180),
        "owner_activation_ref": _text(owner_activation_attestation.get("approval_ref"), 320),
        "kpi_completion_pct": completion_pct,
        "kpi_target_hit_pct": target_hit_pct,
        "health_score": health_score,
        "manual_baseline_cost_brl": baseline_cost,
        "observed_operating_cost_brl": operating_cost,
        "modeled_savings_brl": savings_brl,
        "observed_roi_pct": roi_pct,
        "observed_monthly_infra_brl": monthly_infra,
        "evidence_refs": evidence_refs,
    }

    return {
        "schema": SCHEMA,
        "state": state,
        "decision": decision,
        "pilot_id": pilot_id,
        "health_score": health_score,
        "kpi_completion_pct": completion_pct,
        "kpi_target_hit_pct": target_hit_pct,
        "progress": progress,
        "manual_baseline_cost_brl": baseline_cost,
        "observed_operating_cost_brl": operating_cost,
        "observed_savings_brl": savings_brl,
        "observed_roi_pct": roi_pct,
        "observed_monthly_infra_brl": monthly_infra,
        "hard_stop_reasons": hard_stop_reasons,
        "blockers": list(dict.fromkeys(blockers)),
        "evidence_digest": _digest(evidence),
        "owner_review_required": True,
        "automatic_renewal": False,
        "automatic_pause": False,
        "automatic_termination": False,
        "automatic_scope_expansion": False,
        "automatic_contract_change": False,
        "automatic_billing": False,
        "automatic_customer_contact": False,
        "automatic_deploy": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }


__all__ = ["SCHEMA", "MAX_MONTHLY_INFRA_BRL", "evaluate_pilot_outcome"]
