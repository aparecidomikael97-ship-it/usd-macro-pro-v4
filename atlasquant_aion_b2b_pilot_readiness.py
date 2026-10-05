"""AION B2B pilot readiness and acceptance/risk gate.

Pure/offline decision support for a controlled Managed Operations pilot.
It never approves a customer, signs a contract, charges, provisions, deploys,
calls a provider, or mutates production.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

SCHEMA = "ATLASQUANT_AION_B2B_PILOT_READINESS_V1"
MAX_MONTHLY_INFRA_BRL = 200.0
MIN_REFERENCE_TASKS = 1000
MIN_REFERENCE_COMPANIES = 3

_POSITIVE_WEIGHTS = {
    "problem_fit": 20.0,
    "process_repeatability": 15.0,
    "data_readiness": 10.0,
    "owner_sponsorship": 10.0,
    "integration_feasibility": 10.0,
    "expected_value": 20.0,
    "scope_clarity": 15.0,
}


def _text(value: Any, limit: int = 240) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _score_0_5(value: Any) -> float | None:
    number = _finite_number(value)
    if number is None or number < 0 or number > 5:
        return None
    return number


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    item = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(item.get("owner_id"), 120),
        "tenant_id": _text(item.get("tenant_id"), 120),
        "workspace_id": _text(item.get("workspace_id"), 120),
    }


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _refs(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:80]:
        item = _text(raw, 320)
        if item and item not in out:
            out.append(item)
    return out


def normalize_candidate(
    raw: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any],
) -> dict[str, Any]:
    item = dict(raw) if isinstance(raw, Mapping) else {}
    scope = _scope(item)
    expected_scope = _scope(trusted_scope)
    blockers: list[str] = []

    if not all(expected_scope.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")
    if scope != expected_scope:
        blockers.append("CANDIDATE_SCOPE_MISMATCH")

    candidate_id = _text(item.get("candidate_id"), 120)
    company_label = _text(item.get("company_label"), 180)
    if not candidate_id:
        blockers.append("CANDIDATE_ID_REQUIRED")
    if not company_label:
        blockers.append("COMPANY_LABEL_REQUIRED")

    positive: dict[str, float | None] = {}
    for key in _POSITIVE_WEIGHTS:
        positive[key] = _score_0_5(item.get(key))
        if positive[key] is None:
            blockers.append(f"{key.upper()}_SCORE_INVALID")

    privacy_risk = _score_0_5(item.get("privacy_risk"))
    operational_risk = _score_0_5(item.get("operational_risk"))
    if privacy_risk is None:
        blockers.append("PRIVACY_RISK_INVALID")
    if operational_risk is None:
        blockers.append("OPERATIONAL_RISK_INVALID")

    infra = _finite_number(item.get("planned_monthly_infra_brl"))
    if infra is None or infra < 0:
        blockers.append("MONTHLY_INFRA_INVALID")

    duration = item.get("pilot_duration_days")
    if isinstance(duration, bool) or not isinstance(duration, int) or duration < 1 or duration > 60:
        blockers.append("PILOT_DURATION_INVALID")

    evidence_refs = _refs(item.get("evidence_refs"))
    if len(evidence_refs) < 3:
        blockers.append("CANDIDATE_EVIDENCE_INSUFFICIENT")

    return {
        "candidate_id": candidate_id,
        "company_label": company_label,
        **scope,
        "positive_scores": positive,
        "privacy_risk": privacy_risk,
        "operational_risk": operational_risk,
        "planned_monthly_infra_brl": infra,
        "pilot_duration_days": duration if isinstance(duration, int) and not isinstance(duration, bool) else None,
        "evidence_refs": evidence_refs,
        "normalization_blockers": list(dict.fromkeys(blockers)),
    }


def _validate_platform_evidence(raw: Mapping[str, Any] | None) -> list[str]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    blockers: list[str] = []
    if data.get("state") != "PASS":
        blockers.append("MANAGED_OPERATIONS_SIM_NOT_PASS")
    if data.get("pilot_recommendation") != "HUMAN_REVIEW_CANDIDATE":
        blockers.append("MANAGED_OPERATIONS_NOT_REVIEW_CANDIDATE")
    if int(data.get("total_tasks") or 0) < MIN_REFERENCE_TASKS:
        blockers.append("REFERENCE_TASK_VOLUME_INSUFFICIENT")
    if int(data.get("company_count") or 0) < MIN_REFERENCE_COMPANIES:
        blockers.append("REFERENCE_COMPANY_COVERAGE_INSUFFICIENT")
    if int(data.get("classification_error_count") or 0) != 0:
        blockers.append("REFERENCE_CLASSIFICATION_ERRORS")
    if int(data.get("unsafe_escape_count") or 0) != 0:
        blockers.append("REFERENCE_UNSAFE_ESCAPE")
    if int(data.get("deny_escape_count") or 0) != 0:
        blockers.append("REFERENCE_DENY_ESCAPE")
    if not _text(data.get("evidence_digest"), 160):
        blockers.append("REFERENCE_EVIDENCE_DIGEST_REQUIRED")
    return blockers


def _validate_hardening_evidence(raw: Mapping[str, Any] | None) -> list[str]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    blockers: list[str] = []
    required_true = (
        "tenant_isolation_pass",
        "vault_backend_pass",
        "chaos_campaign_pass",
        "mission_control_ready",
        "approval_gate_ready",
        "audit_receipts_ready",
        "rollback_ready",
    )
    for key in required_true:
        if data.get(key) is not True:
            blockers.append(f"{key.upper()}_REQUIRED")
    if data.get("drift_state") != "STABLE":
        blockers.append("DRIFT_NOT_STABLE")
    if data.get("security_gate_state") != "PASS":
        blockers.append("SECURITY_GATE_NOT_PASS")
    return blockers


def assess_b2b_pilot_candidate(
    *,
    trusted_scope: Mapping[str, Any],
    candidate: Mapping[str, Any],
    platform_evidence: Mapping[str, Any],
    hardening_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = normalize_candidate(candidate, trusted_scope=trusted_scope)
    blockers = list(normalized["normalization_blockers"])
    blockers.extend(_validate_platform_evidence(platform_evidence))
    blockers.extend(_validate_hardening_evidence(hardening_evidence))

    infra = normalized["planned_monthly_infra_brl"]
    privacy_risk = normalized["privacy_risk"]
    operational_risk = normalized["operational_risk"]

    if infra is not None and infra > MAX_MONTHLY_INFRA_BRL:
        blockers.append("MONTHLY_INFRA_CAP_EXCEEDED")
    if privacy_risk is not None and privacy_risk >= 4:
        blockers.append("PRIVACY_RISK_TOO_HIGH")
    if operational_risk is not None and operational_risk >= 4:
        blockers.append("OPERATIONAL_RISK_TOO_HIGH")

    scores = normalized["positive_scores"]
    acceptance_score: float | None = None
    if all(scores.get(k) is not None for k in _POSITIVE_WEIGHTS):
        acceptance_score = round(
            sum((float(scores[k]) / 5.0) * weight for k, weight in _POSITIVE_WEIGHTS.items()),
            2,
        )

    risk_score: float | None = None
    if privacy_risk is not None and operational_risk is not None:
        risk_score = round(((privacy_risk + operational_risk) / 10.0) * 100.0, 2)

    priority_score: float | None = None
    if acceptance_score is not None and risk_score is not None:
        priority_score = round(acceptance_score * 0.75 + (100.0 - risk_score) * 0.25, 2)

    decision = "BLOCKED"
    if not blockers and priority_score is not None:
        if priority_score >= 75:
            decision = "PILOT_REVIEW_CANDIDATE"
        elif priority_score >= 60:
            decision = "REVIEW"
        else:
            decision = "DECLINE"

    review_reasons: list[str] = []
    if not blockers and decision == "REVIEW":
        review_reasons.append("PRIORITY_SCORE_REQUIRES_HUMAN_REVIEW")
    if not blockers and decision == "DECLINE":
        review_reasons.append("PRIORITY_SCORE_BELOW_PILOT_THRESHOLD")

    evidence = {
        "candidate": normalized,
        "platform_evidence_digest": _text(platform_evidence.get("evidence_digest"), 160),
        "hardening_evidence": dict(hardening_evidence),
        "acceptance_score": acceptance_score,
        "risk_score": risk_score,
        "priority_score": priority_score,
    }

    return {
        "schema": SCHEMA,
        "state": "READY_FOR_OWNER_REVIEW" if decision == "PILOT_REVIEW_CANDIDATE" else decision,
        "decision": decision,
        "candidate_id": normalized["candidate_id"],
        "scope": {
            "owner_id": normalized["owner_id"],
            "tenant_id": normalized["tenant_id"],
            "workspace_id": normalized["workspace_id"],
        },
        "acceptance_score": acceptance_score,
        "risk_score": risk_score,
        "priority_score": priority_score,
        "monthly_infra_cap_brl": MAX_MONTHLY_INFRA_BRL,
        "planned_monthly_infra_brl": infra,
        "pilot_duration_days": normalized["pilot_duration_days"],
        "blockers": list(dict.fromkeys(blockers)),
        "review_reasons": review_reasons,
        "evidence_digest": _digest(evidence),
        "human_owner_decision_required": True,
        "automatic_acceptance": False,
        "automatic_rejection_external_effect": False,
        "automatic_contract": False,
        "automatic_billing": False,
        "automatic_provisioning": False,
        "automatic_deploy": False,
        "provider_called": False,
        "customer_data_mutated": False,
        "production_mutation": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "MAX_MONTHLY_INFRA_BRL",
    "MIN_REFERENCE_TASKS",
    "MIN_REFERENCE_COMPANIES",
    "normalize_candidate",
    "assess_b2b_pilot_candidate",
]
