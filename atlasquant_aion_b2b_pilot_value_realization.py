"""AION B2B Pilot Value Realization & Retention Review V1.

Pure/offline business decision support layered on top of the existing
pilot-outcome health gate.

It answers three separate questions:
1) Did the customer realize evidence-backed value?
2) Is the pilot operationally healthy?
3) Is delivery economically sustainable for AtlasQuant?

All outputs are human-review candidates only. The module never renews,
expands, pauses, terminates, bills, contacts customers, deploys, changes CRM,
or mutates production.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

SCHEMA = "ATLASQUANT_AION_B2B_PILOT_VALUE_REALIZATION_V1"
OUTCOME_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_OUTCOME_HEALTH_V1"
CONTRACT_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_OPERATING_CONTRACT_V1"
MAX_MONTHLY_INFRA_BRL = 200.0
MIN_VALUE_CHECKPOINTS = 2


def _text(value: Any, limit: int = 360) -> str:
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


def _refs(value: Any, limit: int = 80) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:limit]:
        item = _text(raw, 320)
        if item and item not in out:
            out.append(item)
    return out


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _validate_contract(
    contract_result: Mapping[str, Any] | None,
    trusted_scope: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    row = dict(contract_result) if isinstance(contract_result, Mapping) else {}
    blockers: list[str] = []

    if row.get("schema") != CONTRACT_SCHEMA:
        blockers.append("OPERATING_CONTRACT_SCHEMA_INVALID")
    if row.get("state") != "DRAFT_FOR_OWNER_APPROVAL":
        blockers.append("OPERATING_CONTRACT_NOT_REVIEWABLE")
    if row.get("activation_state") != "BLOCKED_UNTIL_OWNER_APPROVAL":
        blockers.append("OPERATING_CONTRACT_ACTIVATION_BOUNDARY_INVALID")
    if row.get("human_owner_approval_required") is not True:
        blockers.append("OPERATING_CONTRACT_OWNER_BOUNDARY_MISSING")
    if row.get("blockers"):
        blockers.append("OPERATING_CONTRACT_HAS_BLOCKERS")
    if not _text(row.get("contract_digest"), 180):
        blockers.append("OPERATING_CONTRACT_DIGEST_REQUIRED")

    for key in (
        "automatic_activation",
        "automatic_contract_signature",
        "automatic_customer_contact",
        "automatic_billing",
        "automatic_spend",
        "automatic_deploy",
        "provider_called",
        "production_mutation",
        "executes_action",
    ):
        if row.get(key) is not False:
            blockers.append("OPERATING_CONTRACT_UNSAFE_FIELD:" + key)

    core = row.get("contract")
    core = dict(core) if isinstance(core, Mapping) else {}
    if not core:
        blockers.append("OPERATING_CONTRACT_PAYLOAD_REQUIRED")
    if _scope(core) != _scope(trusted_scope):
        blockers.append("OPERATING_CONTRACT_SCOPE_MISMATCH")
    if not _text(core.get("pilot_id"), 120):
        blockers.append("OPERATING_CONTRACT_PILOT_ID_REQUIRED")
    if not isinstance(core.get("quick_wins"), (list, tuple)) or not core.get("quick_wins"):
        blockers.append("OPERATING_CONTRACT_QUICK_WINS_REQUIRED")

    return core, list(dict.fromkeys(blockers))


def _validate_outcome(
    outcome_health: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any],
    pilot_id: str,
) -> tuple[dict[str, Any], list[str]]:
    row = dict(outcome_health) if isinstance(outcome_health, Mapping) else {}
    blockers: list[str] = []

    if row.get("schema") != OUTCOME_SCHEMA:
        blockers.append("OUTCOME_HEALTH_SCHEMA_INVALID")
    if row.get("state") not in {
        "HEALTHY",
        "WATCH",
        "UNHEALTHY",
        "STOP_REVIEW",
        "EVIDENCE_INCOMPLETE",
    }:
        blockers.append("OUTCOME_HEALTH_STATE_INVALID")
    if row.get("decision") not in {
        "CONTINUE_REVIEW_CANDIDATE",
        "PAUSE_OR_REMEDIATE_REVIEW",
        "EXIT_REVIEW_CANDIDATE",
        "STOP_REVIEW",
        "EVIDENCE_REVIEW",
    }:
        blockers.append("OUTCOME_HEALTH_DECISION_INVALID")
    if _text(row.get("pilot_id"), 120) != pilot_id:
        blockers.append("OUTCOME_HEALTH_PILOT_MISMATCH")
    if row.get("owner_review_required") is not True:
        blockers.append("OUTCOME_HEALTH_OWNER_REVIEW_BOUNDARY_MISSING")
    if row.get("blockers"):
        blockers.append("OUTCOME_HEALTH_HAS_BLOCKERS")
    if not _text(row.get("evidence_digest"), 180):
        blockers.append("OUTCOME_HEALTH_EVIDENCE_DIGEST_REQUIRED")

    for key in (
        "automatic_renewal",
        "automatic_pause",
        "automatic_termination",
        "automatic_scope_expansion",
        "automatic_contract_change",
        "automatic_billing",
        "automatic_customer_contact",
        "automatic_deploy",
        "provider_called",
        "production_mutation",
        "executes_action",
    ):
        if row.get(key) is not False:
            blockers.append("OUTCOME_HEALTH_UNSAFE_FIELD:" + key)

    health_score = _pct(row.get("health_score"))
    if row.get("state") not in {"STOP_REVIEW", "EVIDENCE_INCOMPLETE"} and health_score is None:
        blockers.append("OUTCOME_HEALTH_SCORE_INVALID")

    observed_roi = _number(row.get("observed_roi_pct"))
    observed_savings = _number(row.get("observed_savings_brl"))
    observed_infra = _number(row.get("observed_monthly_infra_brl"))

    if observed_savings is None:
        blockers.append("OUTCOME_OBSERVED_SAVINGS_INVALID")
    if observed_infra is None or observed_infra < 0:
        blockers.append("OUTCOME_OBSERVED_INFRA_INVALID")
    elif observed_infra > MAX_MONTHLY_INFRA_BRL:
        blockers.append("OUTCOME_OBSERVED_INFRA_CAP_EXCEEDED")

    return row, list(dict.fromkeys(blockers))


def _quick_win_progress(
    expected_quick_wins: Sequence[Any],
    observations: Sequence[Mapping[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[str], float, float]:
    expected: list[str] = []
    for raw in list(expected_quick_wins)[:5]:
        item = _text(raw, 400)
        if item and item not in expected:
            expected.append(item)

    supplied: dict[str, Mapping[str, Any]] = {}
    blockers: list[str] = []
    for raw in observations or []:
        if not isinstance(raw, Mapping):
            blockers.append("QUICK_WIN_OBSERVATION_INVALID")
            continue
        quick_win = _text(raw.get("quick_win"), 400)
        if not quick_win or quick_win in supplied:
            blockers.append("QUICK_WIN_ID_INVALID_OR_DUPLICATE")
            continue
        supplied[quick_win] = raw

    for supplied_quick_win in supplied:
        if supplied_quick_win not in expected:
            blockers.append("QUICK_WIN_NOT_IN_CONTRACT:" + supplied_quick_win)

    progress: list[dict[str, Any]] = []
    valid = 0
    achieved_count = 0
    for quick_win in expected:
        raw = supplied.get(quick_win)
        if raw is None:
            progress.append(
                {
                    "quick_win": quick_win,
                    "state": "MISSING",
                    "achieved": False,
                    "realized_value_brl": None,
                }
            )
            continue

        achieved = raw.get("achieved")
        source_ref = _text(raw.get("source_ref"), 320)
        realized_value = _number(raw.get("realized_value_brl"))
        if (
            not isinstance(achieved, bool)
            or not source_ref
            or (realized_value is not None and realized_value < 0)
        ):
            progress.append(
                {
                    "quick_win": quick_win,
                    "state": "INVALID",
                    "achieved": False,
                    "realized_value_brl": None,
                }
            )
            blockers.append("QUICK_WIN_OBSERVATION_INVALID:" + quick_win)
            continue

        valid += 1
        if achieved:
            achieved_count += 1
        progress.append(
            {
                "quick_win": quick_win,
                "state": "MEASURED",
                "achieved": achieved,
                "realized_value_brl": (
                    round(realized_value, 2)
                    if realized_value is not None
                    else None
                ),
                "source_ref": source_ref,
            }
        )

    total = len(expected)
    completion_pct = round(valid / total * 100.0, 2) if total else 0.0
    achieved_pct = round(achieved_count / total * 100.0, 2) if total else 0.0
    if not expected:
        blockers.append("QUICK_WINS_MISSING")
    return progress, list(dict.fromkeys(blockers)), completion_pct, achieved_pct


def _value_trend(
    checkpoints: Sequence[Mapping[str, Any]] | None,
) -> tuple[str, list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    seen: set[str] = set()

    for raw in checkpoints or []:
        if not isinstance(raw, Mapping):
            blockers.append("VALUE_CHECKPOINT_INVALID")
            continue
        period_id = _text(raw.get("period_id"), 100)
        sequence = raw.get("sequence")
        source_ref = _text(raw.get("source_ref"), 320)
        savings = _number(raw.get("observed_savings_brl"))
        roi = _number(raw.get("observed_roi_pct"))
        health = _pct(raw.get("health_score"))
        if (
            not period_id
            or period_id in seen
            or isinstance(sequence, bool)
            or not isinstance(sequence, int)
            or sequence < 1
            or not source_ref
            or savings is None
            or roi is None
            or health is None
        ):
            blockers.append("VALUE_CHECKPOINT_INVALID")
            continue
        if any(item["sequence"] == sequence for item in rows):
            blockers.append("VALUE_CHECKPOINT_SEQUENCE_DUPLICATE")
            continue
        seen.add(period_id)
        rows.append(
            {
                "period_id": period_id,
                "sequence": sequence,
                "observed_savings_brl": round(savings, 2),
                "observed_roi_pct": round(roi, 2),
                "health_score": round(health, 2),
                "source_ref": source_ref,
            }
        )

    rows.sort(key=lambda item: item["sequence"])

    if len(rows) < MIN_VALUE_CHECKPOINTS:
        return "INSUFFICIENT", rows, list(dict.fromkeys(blockers))

    first = rows[0]
    latest = rows[-1]
    savings_first = first["observed_savings_brl"]
    savings_latest = latest["observed_savings_brl"]
    health_delta = latest["health_score"] - first["health_score"]

    if abs(savings_first) < 0.01:
        savings_ratio = 1.0 if savings_latest > 0 else 0.0
    else:
        savings_ratio = savings_latest / savings_first

    if (
        health_delta >= 5.0
        and savings_latest >= savings_first
    ) or (
        health_delta >= 0.0
        and savings_ratio >= 1.10
    ):
        trend = "IMPROVING"
    elif (
        health_delta <= -5.0
        or savings_ratio < 0.90
    ):
        trend = "DECLINING"
    else:
        trend = "STABLE"

    return trend, rows, list(dict.fromkeys(blockers))


def evaluate_pilot_value_realization(
    *,
    trusted_scope: Mapping[str, Any],
    contract_result: Mapping[str, Any],
    outcome_health: Mapping[str, Any],
    quick_win_observations: Sequence[Mapping[str, Any]] | None,
    value_checkpoints: Sequence[Mapping[str, Any]] | None,
    commercial_evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    trusted = _scope(trusted_scope)
    blockers: list[str] = []
    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")

    contract_core, contract_blockers = _validate_contract(
        contract_result,
        trusted_scope=trusted_scope,
    )
    blockers.extend(contract_blockers)

    pilot_id = _text(contract_core.get("pilot_id"), 120)
    outcome, outcome_blockers = _validate_outcome(
        outcome_health,
        trusted_scope=trusted_scope,
        pilot_id=pilot_id,
    )
    blockers.extend(outcome_blockers)

    quick_win_progress, quick_win_blockers, quick_win_completion_pct, quick_win_achieved_pct = (
        _quick_win_progress(
            contract_core.get("quick_wins") or [],
            quick_win_observations,
        )
    )
    blockers.extend(quick_win_blockers)

    trend, normalized_checkpoints, checkpoint_blockers = _value_trend(
        value_checkpoints
    )
    blockers.extend(checkpoint_blockers)

    commercial = (
        dict(commercial_evidence)
        if isinstance(commercial_evidence, Mapping)
        else {}
    )
    if _scope(commercial) != trusted:
        blockers.append("COMMERCIAL_EVIDENCE_SCOPE_MISMATCH")
    if _text(commercial.get("pilot_id"), 120) != pilot_id:
        blockers.append("COMMERCIAL_EVIDENCE_PILOT_MISMATCH")

    service_fee = _number(commercial.get("customer_fee_brl"))
    service_revenue = _number(commercial.get("recognized_service_revenue_brl"))
    delivery_labor = _number(commercial.get("delivery_labor_cost_brl"))
    support_cost = _number(commercial.get("support_cost_brl"))
    external_cost = _number(commercial.get("external_cost_brl"))
    infra_cost = _number(commercial.get("infra_cost_brl"))

    for label, value in (
        ("CUSTOMER_FEE", service_fee),
        ("SERVICE_REVENUE", service_revenue),
        ("DELIVERY_LABOR_COST", delivery_labor),
        ("SUPPORT_COST", support_cost),
        ("EXTERNAL_COST", external_cost),
        ("INFRA_COST", infra_cost),
    ):
        if value is None or value < 0:
            blockers.append(label + "_INVALID")

    if infra_cost is not None and infra_cost > MAX_MONTHLY_INFRA_BRL:
        blockers.append("COMMERCIAL_INFRA_CAP_EXCEEDED")

    commercial_refs = _refs(commercial.get("evidence_refs"))
    if len(commercial_refs) < 4:
        blockers.append("COMMERCIAL_EVIDENCE_INSUFFICIENT")

    observed_savings = _number(outcome.get("observed_savings_brl"))
    health_score = _pct(outcome.get("health_score"))
    observed_roi = _number(outcome.get("observed_roi_pct"))

    customer_value_to_fee_ratio: float | None = None
    customer_net_value_brl: float | None = None
    customer_payback_covered: bool | None = None
    if observed_savings is not None and service_fee is not None:
        customer_net_value_brl = round(observed_savings - service_fee, 2)
        if service_fee > 0:
            customer_value_to_fee_ratio = round(
                observed_savings / service_fee,
                4,
            )
            customer_payback_covered = observed_savings >= service_fee
        else:
            customer_payback_covered = observed_savings >= 0

    provider_delivery_cost_brl: float | None = None
    provider_gross_margin_brl: float | None = None
    provider_gross_margin_pct: float | None = None
    if all(
        value is not None
        for value in (
            service_revenue,
            delivery_labor,
            support_cost,
            external_cost,
            infra_cost,
        )
    ):
        provider_delivery_cost_brl = round(
            float(delivery_labor)
            + float(support_cost)
            + float(external_cost)
            + float(infra_cost),
            2,
        )
        provider_gross_margin_brl = round(
            float(service_revenue) - provider_delivery_cost_brl,
            2,
        )
        if float(service_revenue) > 0:
            provider_gross_margin_pct = round(
                provider_gross_margin_brl
                / float(service_revenue)
                * 100.0,
                2,
            )

    low_value_reasons: list[str] = []
    if observed_savings is not None and observed_savings <= 0:
        low_value_reasons.append("CUSTOMER_SAVINGS_NON_POSITIVE")
    if (
        customer_value_to_fee_ratio is not None
        and customer_value_to_fee_ratio < 1.0
    ):
        low_value_reasons.append("CUSTOMER_VALUE_BELOW_FEE")
    if quick_win_achieved_pct < 50.0:
        low_value_reasons.append("QUICK_WIN_ATTAINMENT_LOW")
    if trend == "DECLINING":
        low_value_reasons.append("VALUE_TREND_DECLINING")
    if (
        provider_gross_margin_brl is not None
        and provider_gross_margin_brl < 0
    ):
        low_value_reasons.append("PROVIDER_MARGIN_NEGATIVE")
    low_value_alert = bool(low_value_reasons)

    risk_score = 50.0
    if health_score is not None:
        risk_score -= (health_score - 50.0) * 0.55
    risk_score -= (quick_win_achieved_pct - 50.0) * 0.20
    if trend == "IMPROVING":
        risk_score -= 12.0
    elif trend == "DECLINING":
        risk_score += 18.0
    elif trend == "INSUFFICIENT":
        risk_score += 8.0

    if observed_roi is not None:
        if observed_roi < 0:
            risk_score += 18.0
        elif observed_roi >= 50:
            risk_score -= 8.0

    if (
        customer_value_to_fee_ratio is not None
        and customer_value_to_fee_ratio < 1.0
    ):
        risk_score += 12.0
    elif (
        customer_value_to_fee_ratio is not None
        and customer_value_to_fee_ratio >= 1.5
    ):
        risk_score -= 6.0

    if (
        provider_gross_margin_pct is not None
        and provider_gross_margin_pct < 0
    ):
        risk_score += 15.0
    elif (
        provider_gross_margin_pct is not None
        and provider_gross_margin_pct >= 30.0
    ):
        risk_score -= 5.0

    if outcome.get("state") == "STOP_REVIEW":
        risk_score = 100.0

    risk_score = round(_clamp(risk_score), 2)
    if risk_score <= 30:
        retention_risk = "LOW"
    elif risk_score <= 60:
        retention_risk = "MEDIUM"
    else:
        retention_risk = "HIGH"

    evidence_incomplete = (
        quick_win_completion_pct < 100.0
        or trend == "INSUFFICIENT"
    )

    if blockers:
        state = "BLOCKED"
        recommendation = "BLOCKED"
    elif outcome.get("state") == "STOP_REVIEW":
        state = "STOP_REVIEW"
        recommendation = "STOP_REVIEW"
    elif evidence_incomplete:
        state = "EVIDENCE_INCOMPLETE"
        recommendation = "VALUE_EVIDENCE_REVIEW"
    elif (
        outcome.get("state") == "HEALTHY"
        and quick_win_achieved_pct >= 80.0
        and trend == "IMPROVING"
        and (
            customer_value_to_fee_ratio is None
            or customer_value_to_fee_ratio >= 1.0
        )
        and (
            provider_gross_margin_pct is None
            or provider_gross_margin_pct >= 20.0
        )
        and risk_score <= 30.0
        and not low_value_alert
    ):
        state = "STRONG_VALUE"
        recommendation = "EXPANSION_REVIEW_CANDIDATE"
    elif (
        outcome.get("state") == "HEALTHY"
        and risk_score < 50.0
        and not low_value_alert
    ):
        state = "VALUE_CONFIRMED"
        recommendation = "CONTINUE_REVIEW_CANDIDATE"
    elif (
        outcome.get("state") == "UNHEALTHY"
        or risk_score >= 75.0
    ):
        state = "LOW_VALUE"
        recommendation = "EXIT_REVIEW_CANDIDATE"
    else:
        state = "VALUE_AT_RISK"
        recommendation = "REMEDIATE_REVIEW_CANDIDATE"

    reasons: list[str] = []
    reasons.extend(low_value_reasons)
    if trend == "IMPROVING":
        reasons.append("VALUE_TREND_IMPROVING")
    elif trend == "STABLE":
        reasons.append("VALUE_TREND_STABLE")
    elif trend == "DECLINING":
        reasons.append("VALUE_TREND_DECLINING")
    if quick_win_achieved_pct >= 80.0:
        reasons.append("QUICK_WINS_STRONG")
    elif quick_win_achieved_pct < 50.0:
        reasons.append("QUICK_WINS_WEAK")
    if provider_gross_margin_pct is not None:
        if provider_gross_margin_pct >= 30.0:
            reasons.append("PROVIDER_MARGIN_HEALTHY")
        elif provider_gross_margin_pct < 0:
            reasons.append("PROVIDER_MARGIN_NEGATIVE")
    if customer_payback_covered is True:
        reasons.append("CUSTOMER_PAYBACK_COVERED")
    elif customer_payback_covered is False:
        reasons.append("CUSTOMER_PAYBACK_NOT_COVERED")
    reasons = list(dict.fromkeys(reasons))

    evidence = {
        "pilot_id": pilot_id,
        "scope": trusted,
        "contract_digest": _text(contract_result.get("contract_digest"), 180),
        "outcome_evidence_digest": _text(outcome.get("evidence_digest"), 180),
        "quick_win_completion_pct": quick_win_completion_pct,
        "quick_win_achieved_pct": quick_win_achieved_pct,
        "value_trend": trend,
        "health_score": health_score,
        "observed_savings_brl": observed_savings,
        "observed_roi_pct": observed_roi,
        "customer_fee_brl": service_fee,
        "customer_value_to_fee_ratio": customer_value_to_fee_ratio,
        "customer_net_value_brl": customer_net_value_brl,
        "provider_delivery_cost_brl": provider_delivery_cost_brl,
        "provider_gross_margin_brl": provider_gross_margin_brl,
        "provider_gross_margin_pct": provider_gross_margin_pct,
        "retention_risk_score": risk_score,
        "commercial_evidence_refs": commercial_refs,
        "value_checkpoints": normalized_checkpoints,
    }

    review_packet = {
        "pilot_id": pilot_id,
        "state": state,
        "recommendation": recommendation,
        "health_score": health_score,
        "retention_risk": retention_risk,
        "retention_risk_score": risk_score,
        "value_trend": trend,
        "quick_win_achieved_pct": quick_win_achieved_pct,
        "observed_savings_brl": observed_savings,
        "observed_roi_pct": observed_roi,
        "customer_value_to_fee_ratio": customer_value_to_fee_ratio,
        "customer_net_value_brl": customer_net_value_brl,
        "provider_gross_margin_brl": provider_gross_margin_brl,
        "provider_gross_margin_pct": provider_gross_margin_pct,
        "low_value_alert": low_value_alert,
        "review_reasons": reasons[:12],
    }

    return {
        "schema": SCHEMA,
        "state": state,
        "recommendation": recommendation,
        "pilot_id": pilot_id,
        "scope": trusted,
        "health_score": health_score,
        "value_trend": trend,
        "quick_win_completion_pct": quick_win_completion_pct,
        "quick_win_achieved_pct": quick_win_achieved_pct,
        "quick_win_progress": quick_win_progress,
        "value_checkpoints": normalized_checkpoints,
        "observed_savings_brl": observed_savings,
        "observed_roi_pct": observed_roi,
        "customer_fee_brl": service_fee,
        "customer_value_to_fee_ratio": customer_value_to_fee_ratio,
        "customer_net_value_brl": customer_net_value_brl,
        "customer_payback_covered": customer_payback_covered,
        "provider_delivery_cost_brl": provider_delivery_cost_brl,
        "provider_gross_margin_brl": provider_gross_margin_brl,
        "provider_gross_margin_pct": provider_gross_margin_pct,
        "retention_risk": retention_risk,
        "retention_risk_score": risk_score,
        "low_value_alert": low_value_alert,
        "low_value_reasons": low_value_reasons,
        "review_reasons": reasons,
        "review_packet": review_packet,
        "blockers": list(dict.fromkeys(blockers)),
        "evidence_digest": _digest(evidence),
        "owner_review_required": True,
        "automatic_renewal": False,
        "automatic_expansion": False,
        "automatic_pause": False,
        "automatic_termination": False,
        "automatic_scope_change": False,
        "automatic_contract_change": False,
        "automatic_billing": False,
        "automatic_customer_contact": False,
        "automatic_provisioning": False,
        "automatic_deploy": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "OUTCOME_SCHEMA",
    "CONTRACT_SCHEMA",
    "MAX_MONTHLY_INFRA_BRL",
    "MIN_VALUE_CHECKPOINTS",
    "evaluate_pilot_value_realization",
]
