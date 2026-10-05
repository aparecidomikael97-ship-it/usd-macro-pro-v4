"""AION B2B Diagnostic Intake V1.

Pure/offline diagnostic dossier for AION Negócios.

It structures evidence about the candidate operation before the existing Pilot
Readiness score is used. The diagnostic measures completeness only. It never
invents acceptance/risk scores, contacts a lead, writes CRM data, prices a
service, signs a contract, provisions, deploys, bills, or mutates production.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

SCHEMA = "ATLASQUANT_AION_B2B_DIAGNOSTIC_INTAKE_V1"
SCORING_INPUT_SCHEMA = "ATLASQUANT_AION_B2B_DIAGNOSTIC_SCORING_INPUT_V1"

DIAGNOSTIC_AREAS = (
    "sales",
    "customer_service",
    "billing",
    "team",
    "systems",
    "bottlenecks",
)

SCORE_DIMENSIONS = (
    "problem_fit",
    "process_repeatability",
    "data_readiness",
    "owner_sponsorship",
    "integration_feasibility",
    "expected_value",
    "scope_clarity",
)

_REQUIRED_BASELINE_AREAS = frozenset({"sales", "customer_service", "billing"})


def _text(value: Any, limit: int = 360) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(data.get("owner_id"), 120),
        "tenant_id": _text(data.get("tenant_id"), 120),
        "workspace_id": _text(data.get("workspace_id"), 120),
    }


def _refs(value: Any, limit: int = 60) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:limit]:
        item = _text(raw, 320)
        if item and item not in out:
            out.append(item)
    return out


def _texts(value: Any, *, limit: int, item_limit: int = 320) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:limit]:
        item = _text(raw, item_limit)
        if item and item not in out:
            out.append(item)
    return out


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _score(value: Any) -> float | None:
    out = _number(value)
    if out is None or out < 0 or out > 5:
        return None
    return out


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _normalize_metric(raw: Mapping[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    blockers: list[str] = []

    metric_id = _text(data.get("metric_id"), 100)
    label = _text(data.get("label"), 160)
    unit = _text(data.get("unit"), 80)
    value = _number(data.get("value"))
    source_ref = _text(data.get("source_ref"), 320)

    if not metric_id:
        blockers.append("BASELINE_METRIC_ID_REQUIRED")
    if not label:
        blockers.append("BASELINE_METRIC_LABEL_REQUIRED")
    if not unit:
        blockers.append("BASELINE_METRIC_UNIT_REQUIRED")
    if value is None:
        blockers.append("BASELINE_METRIC_VALUE_INVALID")
    if not source_ref:
        blockers.append("BASELINE_METRIC_SOURCE_REQUIRED")

    return {
        "metric_id": metric_id,
        "label": label,
        "unit": unit,
        "value": value,
        "source_ref": source_ref,
    }, blockers


def _normalize_area(name: str, raw: Mapping[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    blockers: list[str] = []

    current_process = _text(data.get("current_process"), 800)
    pain_points = _texts(data.get("pain_points"), limit=10, item_limit=400)
    evidence_refs = _refs(data.get("evidence_refs"), limit=20)
    systems = _texts(data.get("systems"), limit=20, item_limit=180)

    if not current_process:
        blockers.append(f"{name.upper()}_CURRENT_PROCESS_REQUIRED")
    if not pain_points:
        blockers.append(f"{name.upper()}_PAIN_POINTS_REQUIRED")
    if not evidence_refs:
        blockers.append(f"{name.upper()}_EVIDENCE_REQUIRED")

    metrics: list[dict[str, Any]] = []
    seen: set[str] = set()
    raw_metrics = data.get("baseline_metrics")
    if raw_metrics is not None and not isinstance(raw_metrics, (list, tuple)):
        blockers.append(f"{name.upper()}_BASELINE_METRICS_INVALID")
        raw_metrics = []

    for raw_metric in list(raw_metrics or [])[:20]:
        metric, metric_blockers = _normalize_metric(
            raw_metric if isinstance(raw_metric, Mapping) else None
        )
        if metric_blockers:
            blockers.extend(f"{name.upper()}_{item}" for item in metric_blockers)
            continue
        metric_id = metric["metric_id"]
        if metric_id in seen:
            blockers.append(f"{name.upper()}_BASELINE_METRIC_DUPLICATE")
            continue
        seen.add(metric_id)
        metrics.append(metric)

    if name in _REQUIRED_BASELINE_AREAS and not metrics:
        blockers.append(f"{name.upper()}_BASELINE_REQUIRED")

    return {
        "area": name,
        "current_process": current_process,
        "pain_points": pain_points,
        "systems": systems,
        "baseline_metrics": metrics,
        "evidence_refs": evidence_refs,
    }, list(dict.fromkeys(blockers))


def build_diagnostic_intake(
    raw: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build a structured evidence dossier, not a commercial decision."""
    data = dict(raw) if isinstance(raw, Mapping) else {}
    scope = _scope(trusted_scope)
    blockers: list[str] = []

    if not all(scope.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")
    for key, expected in scope.items():
        claimed = _text(data.get(key), 120)
        if claimed and claimed != expected:
            blockers.append("DIAGNOSTIC_SCOPE_MISMATCH")

    candidate_id = _text(data.get("candidate_id"), 120)
    lead_id = _text(data.get("lead_id"), 120)
    company_key = _text(data.get("company_key"), 120)
    company_label = _text(data.get("company_label"), 180)
    assessor_context_ref = _text(data.get("assessor_context_ref"), 320)

    if not candidate_id:
        blockers.append("CANDIDATE_ID_REQUIRED")
    if not lead_id:
        blockers.append("LEAD_ID_REQUIRED")
    if not company_key:
        blockers.append("COMPANY_KEY_REQUIRED")
    if not company_label:
        blockers.append("COMPANY_LABEL_REQUIRED")
    if not assessor_context_ref:
        blockers.append("ASSESSOR_CONTEXT_REF_REQUIRED")

    areas: dict[str, dict[str, Any]] = {}
    raw_areas = data.get("areas") if isinstance(data.get("areas"), Mapping) else {}
    for name in DIAGNOSTIC_AREAS:
        area, area_blockers = _normalize_area(
            name,
            raw_areas.get(name) if isinstance(raw_areas, Mapping) else None,
        )
        areas[name] = area
        blockers.extend(area_blockers)

    objectives = _texts(data.get("objectives"), limit=8, item_limit=400)
    constraints = _texts(data.get("constraints"), limit=12, item_limit=400)
    quick_win_candidates = _texts(
        data.get("quick_win_candidates"), limit=8, item_limit=400
    )
    integration_candidates = _texts(
        data.get("integration_candidates"), limit=20, item_limit=180
    )
    evidence_refs = _refs(data.get("evidence_refs"), limit=60)

    if not objectives:
        blockers.append("DIAGNOSTIC_OBJECTIVES_REQUIRED")
    if not constraints:
        blockers.append("DIAGNOSTIC_CONSTRAINTS_REQUIRED")
    if not quick_win_candidates:
        blockers.append("QUICK_WIN_CANDIDATE_REQUIRED")
    if len(evidence_refs) < 3:
        blockers.append("DIAGNOSTIC_EVIDENCE_INSUFFICIENT")

    total_checks = (
        len(DIAGNOSTIC_AREAS) * 3
        + len(_REQUIRED_BASELINE_AREAS)
        + 4
    )
    completed_checks = 0
    for name, area in areas.items():
        completed_checks += int(bool(area["current_process"]))
        completed_checks += int(bool(area["pain_points"]))
        completed_checks += int(bool(area["evidence_refs"]))
        if name in _REQUIRED_BASELINE_AREAS:
            completed_checks += int(bool(area["baseline_metrics"]))
    completed_checks += int(bool(objectives))
    completed_checks += int(bool(constraints))
    completed_checks += int(bool(quick_win_candidates))
    completed_checks += int(len(evidence_refs) >= 3)

    completeness_pct = round(
        completed_checks / total_checks * 100.0,
        2,
    ) if total_checks else 0.0

    blockers = list(dict.fromkeys(blockers))
    dossier = {
        **scope,
        "candidate_id": candidate_id,
        "lead_id": lead_id,
        "company_key": company_key,
        "company_label": company_label,
        "assessor_context_ref": assessor_context_ref,
        "areas": areas,
        "objectives": objectives,
        "constraints": constraints,
        "quick_win_candidates": quick_win_candidates,
        "integration_candidates": integration_candidates,
        "evidence_refs": evidence_refs,
        "completeness_pct": completeness_pct,
    }

    return {
        "schema": SCHEMA,
        "state": "READY_FOR_HUMAN_SCORING" if not blockers else "INCOMPLETE",
        "dossier": dossier,
        "blockers": blockers,
        "diagnostic_digest": _digest(dossier),
        "automatic_score_generation": False,
        "automatic_acceptance": False,
        "automatic_rejection_external_effect": False,
        "automatic_outreach": False,
        "automatic_proposal": False,
        "automatic_pricing": False,
        "automatic_contract": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }


def build_pilot_scoring_input(
    diagnostic: Mapping[str, Any] | None,
    *,
    human_assessment: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Bind explicit human scores to a completed diagnostic.

    This function does not call the Pilot Readiness gate. It prepares the exact
    candidate payload for that existing gate while proving scores were supplied
    explicitly by a human assessor rather than inferred by this module.
    """
    diag = dict(diagnostic) if isinstance(diagnostic, Mapping) else {}
    assessment = (
        dict(human_assessment)
        if isinstance(human_assessment, Mapping)
        else {}
    )
    blockers: list[str] = []

    if diag.get("schema") != SCHEMA:
        blockers.append("DIAGNOSTIC_SCHEMA_INVALID")
    if diag.get("state") != "READY_FOR_HUMAN_SCORING":
        blockers.append("DIAGNOSTIC_NOT_READY_FOR_SCORING")
    if diag.get("automatic_score_generation") is not False:
        blockers.append("DIAGNOSTIC_SCORE_BOUNDARY_UNSAFE")
    if diag.get("executes_action") is not False:
        blockers.append("DIAGNOSTIC_EXECUTION_BOUNDARY_UNSAFE")

    dossier = (
        dict(diag.get("dossier"))
        if isinstance(diag.get("dossier"), Mapping)
        else {}
    )
    scope = _scope(dossier)
    if not all(scope.values()):
        blockers.append("DIAGNOSTIC_SCOPE_INVALID")

    human_assessed = assessment.get("human_assessed") is True
    assessor_ref = _text(assessment.get("assessor_ref"), 320)
    if not human_assessed:
        blockers.append("EXPLICIT_HUMAN_ASSESSMENT_REQUIRED")
    if not assessor_ref:
        blockers.append("ASSESSOR_REF_REQUIRED")

    scores: dict[str, float | None] = {}
    for key in SCORE_DIMENSIONS:
        scores[key] = _score(assessment.get(key))
        if scores[key] is None:
            blockers.append(f"{key.upper()}_SCORE_INVALID")

    privacy_risk = _score(assessment.get("privacy_risk"))
    operational_risk = _score(assessment.get("operational_risk"))
    if privacy_risk is None:
        blockers.append("PRIVACY_RISK_INVALID")
    if operational_risk is None:
        blockers.append("OPERATIONAL_RISK_INVALID")

    infra = _number(assessment.get("planned_monthly_infra_brl"))
    if infra is None or infra < 0:
        blockers.append("MONTHLY_INFRA_INVALID")

    duration = assessment.get("pilot_duration_days")
    if (
        isinstance(duration, bool)
        or not isinstance(duration, int)
        or duration < 1
        or duration > 60
    ):
        blockers.append("PILOT_DURATION_INVALID")

    assessment_refs = _refs(assessment.get("evidence_refs"), limit=40)
    if len(assessment_refs) < 2:
        blockers.append("ASSESSMENT_EVIDENCE_INSUFFICIENT")

    diagnostic_digest = _text(diag.get("diagnostic_digest"), 180)
    if not diagnostic_digest:
        blockers.append("DIAGNOSTIC_DIGEST_REQUIRED")

    candidate = {
        **scope,
        "candidate_id": _text(dossier.get("candidate_id"), 120),
        "company_label": _text(dossier.get("company_label"), 180),
        **scores,
        "privacy_risk": privacy_risk,
        "operational_risk": operational_risk,
        "planned_monthly_infra_brl": infra,
        "pilot_duration_days": (
            duration
            if isinstance(duration, int) and not isinstance(duration, bool)
            else None
        ),
        "evidence_refs": list(
            dict.fromkeys(
                [
                    diagnostic_digest,
                    assessor_ref,
                    *_refs(dossier.get("evidence_refs"), limit=60),
                    *assessment_refs,
                ]
            )
        ),
    }

    blockers = list(dict.fromkeys(blockers))
    binding = {
        "diagnostic_digest": diagnostic_digest,
        "assessor_ref": assessor_ref,
        "candidate": candidate,
    }

    return {
        "schema": SCORING_INPUT_SCHEMA,
        "state": "READY_FOR_PILOT_READINESS" if not blockers else "BLOCKED",
        "candidate": candidate,
        "blockers": blockers,
        "binding_digest": _digest(binding),
        "human_assessment_bound": bool(human_assessed and assessor_ref),
        "automatic_score_generation": False,
        "calls_pilot_readiness": False,
        "grants_authority": False,
        "automatic_acceptance": False,
        "automatic_outreach": False,
        "automatic_proposal": False,
        "automatic_pricing": False,
        "automatic_contract": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "SCORING_INPUT_SCHEMA",
    "DIAGNOSTIC_AREAS",
    "SCORE_DIMENSIONS",
    "build_diagnostic_intake",
    "build_pilot_scoring_input",
]
