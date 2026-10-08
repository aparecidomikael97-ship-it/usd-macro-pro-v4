"""AION Advisor + Decision Support V1.

Pure advisory layer over the existing AION Data & Decision Fabric.

This module structures options, risks, mitigations, uncertainty and an optional
evidence-supported recommendation for HUMAN review. It never authorizes or
executes an action.

Important boundaries:
- recommendation != approval;
- approval != execution;
- confidence != probability of success;
- a probability estimate is optional and may only be represented as a bounded
  range with explicit method/calibration/evidence references;
- legal/contract risk flags are review aids, not legal conclusions.
"""
from __future__ import annotations

from hashlib import sha256
import json
import math
import re
from typing import Any, Mapping, Sequence

from atlasquant_aion_data_decision_fabric import (
    SCHEMA as FABRIC_SCHEMA,
    evaluate_decision_case,
)


SCHEMA = "ATLASQUANT_AION_ADVISOR_DECISION_SUPPORT_V1"
ASSESSMENT_SCHEMA = "ATLASQUANT_AION_ADVISORY_ASSESSMENT_V1"
VERIFY_SCHEMA = "ATLASQUANT_AION_ADVISORY_ASSESSMENT_VERIFY_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_ADVISOR_POLICY_V1"

ADVISORY_DOMAINS = (
    "GENERAL",
    "BUSINESS",
    "CONTRACT",
    "TECHNICAL",
    "SECURITY",
    "OPERATIONS",
    "PRODUCT",
    "TRADING",
    "INVESTMENTS",
)
RISK_SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
RISK_CATEGORIES = (
    "LEGAL_CONTRACT",
    "FINANCIAL",
    "SECURITY",
    "PRIVACY",
    "OPERATIONS",
    "TECHNICAL",
    "REPUTATION",
    "COMPLIANCE",
    "MARKET",
    "EXECUTION",
    "DEPENDENCY",
    "OTHER",
)
CONFIDENCE_POSTURES = (
    "INSUFFICIENT_EVIDENCE",
    "CONFLICTED_EVIDENCE",
    "EVIDENCE_SUPPORTED",
)
PROBABILITY_STATES = ("NOT_ESTIMATED", "EVIDENCE_SUPPORTED_RANGE")

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _clean(value: Any, limit: int = 1600) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _identity(value: Any, limit: int = 240) -> str:
    if type(value) is not str:
        return ""
    if not value or len(value) > limit or "\x00" in value:
        return ""
    if " ".join(value.split()) != value:
        return ""
    return value


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256(value: Any) -> str:
    token = _clean(value, 90)
    return token if _SHA256_RE.fullmatch(token) else ""


def _refs(value: Any, *, limit: int = 80) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in list(value)[: limit * 2]:
        token = _identity(raw, 320)
        if token and token not in out:
            out.append(token)
        if len(out) >= limit:
            break
    return out


def _finite_pct(value: Any) -> float | None:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out) or not 0.0 <= out <= 100.0:
        return None
    return round(out, 2)


def _option_rows(
    options: Sequence[Mapping[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    blockers: list[str] = []
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for index, raw in enumerate(list(options or []), start=1):
        if not isinstance(raw, Mapping):
            blockers.append(f"OPTION_INVALID:{index}")
            continue
        option_id = _identity(raw.get("option_id"), 120)
        title = _clean(raw.get("title"), 240)
        summary = _clean(raw.get("summary"), 1200)
        pros = [
            _clean(item, 600)
            for item in list(raw.get("pros") or [])[:20]
            if _clean(item, 600)
        ]
        cons = [
            _clean(item, 600)
            for item in list(raw.get("cons") or [])[:20]
            if _clean(item, 600)
        ]
        evidence_refs = _refs(raw.get("evidence_refs"))
        assumption_refs = _refs(raw.get("assumption_refs"))
        dependency_refs = _refs(raw.get("dependency_refs"))

        if not option_id:
            blockers.append(f"OPTION_ID_REQUIRED:{index}")
        elif option_id in seen:
            blockers.append(f"DUPLICATE_OPTION_ID:{option_id}")
        else:
            seen.add(option_id)
        if not title:
            blockers.append(f"OPTION_TITLE_REQUIRED:{index}")
        if not summary:
            blockers.append(f"OPTION_SUMMARY_REQUIRED:{index}")
        if not pros:
            blockers.append(f"OPTION_PROS_REQUIRED:{option_id or index}")
        if not cons:
            blockers.append(f"OPTION_CONS_REQUIRED:{option_id or index}")
        if not evidence_refs:
            blockers.append(f"OPTION_EVIDENCE_REQUIRED:{option_id or index}")

        rows.append(
            {
                "option_id": option_id,
                "title": title,
                "summary": summary,
                "pros": pros,
                "cons": cons,
                "evidence_refs": evidence_refs,
                "assumption_refs": assumption_refs,
                "dependency_refs": dependency_refs,
                "reversible": bool(raw.get("reversible", False)),
                "rollback_ref": _identity(raw.get("rollback_ref"), 320),
                "cost_band": _clean(raw.get("cost_band"), 80).upper(),
                "time_band": _clean(raw.get("time_band"), 80).upper(),
            }
        )

    if len(rows) < 2:
        blockers.append("AT_LEAST_TWO_OPTIONS_REQUIRED")

    return rows, list(dict.fromkeys(blockers))


def _risk_rows(
    risks: Sequence[Mapping[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    blockers: list[str] = []
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for index, raw in enumerate(list(risks or []), start=1):
        if not isinstance(raw, Mapping):
            blockers.append(f"RISK_INVALID:{index}")
            continue

        risk_id = _identity(raw.get("risk_id"), 120)
        category = _clean(raw.get("category"), 80).upper()
        severity = _clean(raw.get("severity"), 40).upper()
        statement = _clean(raw.get("statement"), 1200)
        mitigation = _clean(raw.get("mitigation"), 1200)
        evidence_refs = _refs(raw.get("evidence_refs"))
        clause_ref = _identity(raw.get("clause_ref"), 320)

        if not risk_id:
            blockers.append(f"RISK_ID_REQUIRED:{index}")
        elif risk_id in seen:
            blockers.append(f"DUPLICATE_RISK_ID:{risk_id}")
        else:
            seen.add(risk_id)
        if category not in RISK_CATEGORIES:
            blockers.append(f"RISK_CATEGORY_INVALID:{risk_id or index}")
        if severity not in RISK_SEVERITIES:
            blockers.append(f"RISK_SEVERITY_INVALID:{risk_id or index}")
        if not statement:
            blockers.append(f"RISK_STATEMENT_REQUIRED:{risk_id or index}")
        if severity in {"HIGH", "CRITICAL"} and not evidence_refs:
            blockers.append(f"HIGH_RISK_EVIDENCE_REQUIRED:{risk_id or index}")
        if severity in {"HIGH", "CRITICAL"} and not mitigation:
            blockers.append(f"HIGH_RISK_MITIGATION_REQUIRED:{risk_id or index}")
        if category == "LEGAL_CONTRACT" and not clause_ref:
            blockers.append(f"CONTRACT_CLAUSE_REF_REQUIRED:{risk_id or index}")

        rows.append(
            {
                "risk_id": risk_id,
                "category": category,
                "severity": severity,
                "statement": statement,
                "mitigation": mitigation,
                "evidence_refs": evidence_refs,
                "clause_ref": clause_ref,
                "legal_conclusion": False,
                "professional_review_recommended": bool(
                    category == "LEGAL_CONTRACT"
                    and severity in {"HIGH", "CRITICAL"}
                ),
            }
        )

    return rows, list(dict.fromkeys(blockers))


def _probability_range(
    raw: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    source = dict(raw or {})
    blockers: list[str] = []
    requested_state = _clean(
        source.get("state") or "NOT_ESTIMATED",
        60,
    ).upper()

    if requested_state not in PROBABILITY_STATES:
        return {
            "state": "NOT_ESTIMATED",
            "estimated": False,
            "single_point_probability_used": False,
        }, ["PROBABILITY_STATE_INVALID"]

    if requested_state == "NOT_ESTIMATED":
        return {
            "state": "NOT_ESTIMATED",
            "estimated": False,
            "reason": _clean(
                source.get("reason") or "No calibrated estimate supplied.",
                600,
            ),
            "single_point_probability_used": False,
        }, []

    low = _finite_pct(source.get("min_pct"))
    high = _finite_pct(source.get("max_pct"))
    method_ref = _identity(source.get("method_ref"), 320)
    calibration_ref = _identity(source.get("calibration_ref"), 320)
    evidence_refs = _refs(source.get("evidence_refs"))

    if low is None or high is None:
        blockers.append("PROBABILITY_RANGE_REQUIRED")
    elif low >= high:
        blockers.append("PROBABILITY_RANGE_ORDER_INVALID")
    elif high - low < 10.0:
        blockers.append("PROBABILITY_RANGE_TOO_PRECISE")
    if not method_ref:
        blockers.append("PROBABILITY_METHOD_REF_REQUIRED")
    if not calibration_ref:
        blockers.append("PROBABILITY_CALIBRATION_REF_REQUIRED")
    if not evidence_refs:
        blockers.append("PROBABILITY_EVIDENCE_REQUIRED")

    return {
        "state": "EVIDENCE_SUPPORTED_RANGE",
        "estimated": not blockers,
        "min_pct": low,
        "max_pct": high,
        "method_ref": method_ref,
        "calibration_ref": calibration_ref,
        "evidence_refs": evidence_refs,
        "single_point_probability_used": False,
        "range_width_minimum_pct_points": 10.0,
    }, blockers


def _assessment_material(assessment: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(assessment)
    raw.pop("assessment_digest", None)
    return raw


def build_advisory_assessment(
    decision_case: Mapping[str, Any] | None,
    fabric_events: Sequence[Mapping[str, Any]] | None,
    *,
    advisory_domain: Any,
    question: Any,
    options: Sequence[Mapping[str, Any]] | None,
    risks: Sequence[Mapping[str, Any]] | None = None,
    recommended_option_id: Any = "",
    recommendation_rationale: Any = "",
    probability_estimate: Mapping[str, Any] | None = None,
    now: Any = None,
) -> dict[str, Any]:
    """Build evidence-gated advice for human review only."""
    blockers: list[str] = []
    raw_case = dict(decision_case or {})
    if raw_case.get("schema") != FABRIC_SCHEMA:
        blockers.append("DECISION_CASE_SCHEMA_MISMATCH")

    evaluated: dict[str, Any] = {}
    if not blockers:
        try:
            evaluated = evaluate_decision_case(
                raw_case,
                fabric_events,
                now=now,
            )
        except Exception:
            blockers.append("DECISION_CASE_EVALUATION_FAILED")

    domain = _clean(advisory_domain, 60).upper()
    if domain not in ADVISORY_DOMAINS:
        blockers.append("ADVISORY_DOMAIN_INVALID")

    question_text = _clean(question, 1600)
    if not question_text:
        blockers.append("ADVISORY_QUESTION_REQUIRED")

    option_rows, option_blockers = _option_rows(options)
    risk_rows, risk_blockers = _risk_rows(risks)
    probability, probability_blockers = _probability_range(
        probability_estimate
    )
    blockers.extend(option_blockers)
    blockers.extend(risk_blockers)
    blockers.extend(probability_blockers)

    recommended_id = _identity(recommended_option_id, 120)
    rationale = _clean(recommendation_rationale, 1800)
    option_ids = {row["option_id"] for row in option_rows if row["option_id"]}

    fabric_state = _clean(evaluated.get("state"), 80).upper()
    evidence_summary = dict(evaluated.get("evidence_summary") or {})
    conflicts = list(evidence_summary.get("conflicts") or [])
    coverage = evaluated.get("evidence_coverage_pct", 0.0)

    if fabric_state == "HUMAN_REVIEW_CANDIDATE":
        confidence_posture = (
            "CONFLICTED_EVIDENCE"
            if conflicts
            else "EVIDENCE_SUPPORTED"
        )
    elif conflicts:
        confidence_posture = "CONFLICTED_EVIDENCE"
    else:
        confidence_posture = "INSUFFICIENT_EVIDENCE"

    can_recommend = bool(
        fabric_state == "HUMAN_REVIEW_CANDIDATE"
        and confidence_posture == "EVIDENCE_SUPPORTED"
        and not blockers
    )

    if recommended_id:
        if recommended_id not in option_ids:
            blockers.append("RECOMMENDED_OPTION_NOT_FOUND")
        if not rationale:
            blockers.append("RECOMMENDATION_RATIONALE_REQUIRED")
        if not can_recommend:
            blockers.append(
                "RECOMMENDATION_REQUIRES_HUMAN_REVIEW_CANDIDATE"
            )
    elif can_recommend:
        blockers.append("RECOMMENDED_OPTION_REQUIRED")

    high_or_critical = [
        row for row in risk_rows
        if row["severity"] in {"HIGH", "CRITICAL"}
    ]
    critical = [row for row in risk_rows if row["severity"] == "CRITICAL"]

    decision_blockers = list(evaluated.get("blockers") or [])
    blockers.extend("DECISION_GATE:" + item for item in decision_blockers)
    blockers = list(dict.fromkeys(blockers))

    if critical:
        advisory_state = "RISK_REVIEW_REQUIRED"
    elif fabric_state == "BLOCKED":
        advisory_state = "BLOCKED"
    elif fabric_state == "RESEARCH_REQUIRED":
        advisory_state = "RESEARCH_REQUIRED"
    elif fabric_state == "TEST_REQUIRED":
        advisory_state = "TEST_REQUIRED"
    elif fabric_state == "RISK_REVIEW":
        advisory_state = "RISK_REVIEW_REQUIRED"
    elif blockers:
        advisory_state = "BLOCKED"
    else:
        advisory_state = "READY_FOR_HUMAN_REVIEW"

    recommendation_ready = bool(
        advisory_state == "READY_FOR_HUMAN_REVIEW"
        and recommended_id
        and recommended_id in option_ids
    )

    assessment: dict[str, Any] = {
        "schema": ASSESSMENT_SCHEMA,
        "state": advisory_state,
        "blockers": blockers,
        "advisory_domain": domain,
        "question": question_text,
        "decision_id": _clean(evaluated.get("decision_id"), 160),
        "decision_state": fabric_state,
        "decision_risk_level": _clean(
            evaluated.get("risk_level"),
            40,
        ).upper(),
        "decision_impact": _clean(
            evaluated.get("impact"),
            40,
        ).upper(),
        "evidence_coverage_pct": coverage,
        "evidence_summary": evidence_summary,
        "confidence_posture": confidence_posture,
        "options": option_rows,
        "risks": risk_rows,
        "high_or_critical_risk_count": len(high_or_critical),
        "critical_risk_count": len(critical),
        "recommended_option_id": recommended_id if recommendation_ready else "",
        "recommendation_rationale": rationale if recommendation_ready else "",
        "recommendation_ready": recommendation_ready,
        "probability_estimate": probability,
        "probability_is_calibrated_claim": bool(
            probability.get("estimated") is True
        ),
        "single_point_success_probability_used": False,
        "false_precision_allowed": False,
        "legal_conclusion_issued": False,
        "owner_decision_required": True,
        "recommendation_is_approval": False,
        "approval_is_execution": False,
        "action_authorized": False,
        "automatic_execution": False,
        "trading_order_authorized": False,
        "payment_authorized": False,
        "contract_signed": False,
        "message_sent": False,
        "provider_called": False,
        "network_called": False,
        "memory_written": False,
        "checkpoint_written": False,
        "external_action_executed": False,
        "executes_action": False,
        "assessment_digest": "",
    }
    assessment["assessment_digest"] = _digest(
        _assessment_material(assessment)
    )
    return assessment


def verify_advisory_assessment(
    assessment: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw = dict(assessment or {})
    blockers: list[str] = []

    if raw.get("schema") != ASSESSMENT_SCHEMA:
        blockers.append("ASSESSMENT_SCHEMA_MISMATCH")

    supplied = _sha256(raw.get("assessment_digest"))
    expected = _digest(_assessment_material(raw))
    if not supplied or supplied != expected:
        blockers.append("ASSESSMENT_DIGEST_MISMATCH")

    if raw.get("confidence_posture") not in CONFIDENCE_POSTURES:
        blockers.append("CONFIDENCE_POSTURE_INVALID")
    probability = dict(raw.get("probability_estimate") or {})
    if probability.get("state") not in PROBABILITY_STATES:
        blockers.append("PROBABILITY_STATE_INVALID")

    if raw.get("single_point_success_probability_used") is not False:
        blockers.append("SINGLE_POINT_PROBABILITY_FORBIDDEN")
    if raw.get("false_precision_allowed") is not False:
        blockers.append("FALSE_PRECISION_FORBIDDEN")
    if raw.get("legal_conclusion_issued") is not False:
        blockers.append("LEGAL_CONCLUSION_MUST_NOT_BE_CLAIMED")
    if raw.get("owner_decision_required") is not True:
        blockers.append("OWNER_DECISION_REQUIRED")
    if raw.get("recommendation_is_approval") is not False:
        blockers.append("RECOMMENDATION_CANNOT_EQUAL_APPROVAL")
    if raw.get("approval_is_execution") is not False:
        blockers.append("APPROVAL_CANNOT_EQUAL_EXECUTION")

    for key in (
        "action_authorized",
        "automatic_execution",
        "trading_order_authorized",
        "payment_authorized",
        "contract_signed",
        "message_sent",
        "provider_called",
        "network_called",
        "memory_written",
        "checkpoint_written",
        "external_action_executed",
        "executes_action",
    ):
        if raw.get(key) is not False:
            blockers.append("ADVISORY_BOUNDARY_INVALID:" + key)

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": VERIFY_SCHEMA,
        "state": "VALID" if not blockers else "INVALID",
        "valid": not blockers,
        "blockers": blockers,
        "assessment_digest": supplied,
        "executes_action": False,
    }


def advisor_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "reuses_data_decision_fabric": True,
        "creates_second_decision_engine": False,
        "recommendation_requires_evidence_gate": True,
        "recommendation_requires_human_review_candidate": True,
        "recommendation_is_approval": False,
        "approval_is_execution": False,
        "owner_decision_required": True,
        "confidence_is_success_probability": False,
        "single_point_success_probability_allowed": False,
        "probability_requires_range": True,
        "probability_minimum_range_width_pct_points": 10.0,
        "probability_requires_method_ref": True,
        "probability_requires_calibration_ref": True,
        "probability_requires_evidence_refs": True,
        "legal_contract_risk_flags_supported": True,
        "legal_conclusion_authority": False,
        "high_contract_risk_professional_review_recommended": True,
        "critical_risk_can_be_auto_approved": False,
        "memory_can_grant_authority": False,
        "action_authorized": False,
        "automatic_execution": False,
        "trading_order_authorized": False,
        "payment_authorized": False,
        "contract_signed": False,
        "message_sent": False,
        "provider_called": False,
        "network_called": False,
        "memory_written": False,
        "worker_armed": False,
        "deploy_executed": False,
        "core_checkpoint_write": False,
        "external_action_executed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "ASSESSMENT_SCHEMA",
    "VERIFY_SCHEMA",
    "POLICY_SCHEMA",
    "ADVISORY_DOMAINS",
    "RISK_SEVERITIES",
    "RISK_CATEGORIES",
    "CONFIDENCE_POSTURES",
    "PROBABILITY_STATES",
    "build_advisory_assessment",
    "verify_advisory_assessment",
    "advisor_policy",
]
