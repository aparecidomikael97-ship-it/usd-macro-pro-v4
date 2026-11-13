"""Map post-release BLS PPI documentary data to a TYPED USD macro context.

This bridge re-runs the EXISTING official Table-1 bytes+receipt parser and
two locked pre-event consensus guards. It does NOT accept standalone caller
actual numbers, calculated surprises or a supposed 'PASS' dict.

Only two EXACT homogeneous series are accepted here:
  - PPI final demand, October 2026, month-on-month, SA
  - PPI final demand less foods and energy, October 2026, MoM, SA
NOT final demand ex foods/energy/TRADE SERVICES. That is a different series.

No rate / consensus assumptions are baked in except those frozen by the
pre-event guard. Event comparisons are in percentage POINTS, not percent
changes or confidence probabilities. Data and clock provenance remain
UNATTESTED even on a locally consistent HTML snapshot. A PPI surprise
alone cannot be turned into USD directional strength, interest-rate paths,
FX28 model factor points, trading recommendations, or an entry signal.

No HTTP, file IO, broker, scheduler, MT5, trades, live alerts or costs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import (
    OFFICIAL_URL, RELEASE_UTC,
    inspect_ppi_oct2026_first_print_lab,
    compare_ppi_actual_to_frozen_consensus_lab,
)
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import (
    PRE_EVENT_HEADLINE_CONSENSUS_MOM, PRE_EVENT_CORE_CONSENSUS_MOM,
)

SCHEMA = "ATLASQUANT_TRADER_US_PPI_OCT2026_TYPED_MACRO_CONTEXT_LAB_V1"
STATE = "LAB_US_PPI_OCT2026_DOCUMENTARY_SURPRISE_CONTEXT_NO_GO"


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_US_PPI_MACRO_CONTEXT_BLOCKED",
        "reason": reason, "currency": "USD",
        "source_url_claim": OFFICIAL_URL,
        "issuer_release_schedule_utc": RELEASE_UTC.isoformat(),
        "observed_at_utc_claim": None,
        "reference_period": "2026-10",
        "series": [],
        "headline_core_concordance_claim": None,
        "pre_event_consensus_locked_locally": False,
        "actual_raw_html_checked_against_local_sha": False,
        "issuer_source_independently_authenticated": False,
        "true_first_seen_before_decision_independently_attested": False,
        "pre_event_prediction_was_recorded": False,
        "after_event_arithmetic_is_not_a_pre_event_prediction": True,
        "economic_surprise_is_not_fx_direction": True,
        "economic_impact_points": None,
        "calibrated_probability": None,
        "predicted_usd_strength": None,
        "realized_fx_return": None,
        "eligible_for_fx28_model_impact_points": False,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "publishable": False, "live_alert_allowed": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def _sign(value: Decimal) -> str:
    return "ABOVE_CONSENSUS" if value > 0 else (
        "BELOW_CONSENSUS" if value < 0 else "AT_CONSENSUS")


def inspect_oct2026_us_ppi_macro_context_lab(
    *, raw_bls_html: Any, original_http_receipt: Any,
    td_pre_event_snapshot: Any, te_pre_event_snapshot: Any,
    inspected_at_utc: Any,
) -> dict[str, Any]:
    """Re-parse actual bytes and frozen consensus; never trust a ready-made bias."""
    out = _base("DOCUMENT_OR_PRE_EVENT_CONSENSUS_MISSING_OR_INADMISSIBLE")
    asof = inspected_at_utc
    if (not isinstance(asof, datetime)
            or asof.tzinfo is None or asof.utcoffset() is None
            or asof.microsecond):
        out["reason"] = "INVALID_AS_OF_CLOCK"
        return out
    asof = asof.astimezone(timezone.utc)
    if asof < RELEASE_UTC:
        out["reason"] = "PPI_OCTOBER_NOT_YET_RELEASED_AT_DECISION_CUTOFF"
        return out
    actual = inspect_ppi_oct2026_first_print_lab(
        raw_html=raw_bls_html, receipt=original_http_receipt,
        as_of_utc=asof,
    )
    if (type(actual) is not dict
            or actual.get("state") != "LAB_PPI_OCT2026_BLS_TABLE1_BODY_VALUES_UNATTESTED"
            or actual.get("operational_bias") != "AGUARDAR"
            or actual.get("trade_authorized") is not False
            or actual.get("publishable") is not False):
        out["reason"] = "BLS_SOURCE_BODY_OR_RECEIPT_NOT_LOCALLY_ACCEPTED"
        return out
    compare = compare_ppi_actual_to_frozen_consensus_lab(
        actual=actual, td_snapshot=td_pre_event_snapshot,
        te_snapshot=te_pre_event_snapshot,
    )
    if (type(compare) is not dict
            or compare.get("state") != "LAB_PPI_RESEARCH_SURPRISE_ONLY_UNATTESTED"
            or compare.get("trade_authorized") is not False
            or compare.get("publishable") is not False
            or compare.get("operational_bias") != "AGUARDAR"):
        out["reason"] = "LOCKED_PRE_EVENT_CONSENSUS_OR_PPI_ARITHMETIC_REJECTED"
        return out
    try:
        h_actual = Decimal(actual["headline_final_demand_sa_mom_pct_body_claim"])
        c_actual = Decimal(actual["core_ex_food_energy_sa_mom_pct_body_claim"])
        h_consensus = Decimal(PRE_EVENT_HEADLINE_CONSENSUS_MOM)
        c_consensus = Decimal(PRE_EVENT_CORE_CONSENSUS_MOM)
        h_surprise = h_actual - h_consensus
        c_surprise = c_actual - c_consensus
        if (not all(x.is_finite() for x in (
                h_actual,c_actual,h_consensus,c_consensus,h_surprise,c_surprise))
                or str(h_surprise) != compare["headline_vs_td_pre_event_diff_pp"]
                or str(c_surprise) != compare["core_vs_td_pre_event_diff_pp"]):
            out["reason"] = "TYPED_PPI_ARITHMETIC_MISMATCH"
            return out
        captured = datetime.fromisoformat(actual["source_capture_claim_utc"])
        if captured.utcoffset() is None or captured > asof:
            out["reason"] = "SOURCE_CAPTURE_CLAIM_INVALID"
            return out
    except (KeyError, TypeError, ValueError, InvalidOperation, OverflowError):
        out["reason"] = "PPI_VALUE_OR_CAPTURE_CLAIM_INVALID"
        return out
    signals = (_sign(h_surprise), _sign(c_surprise))
    if signals[0] == signals[1] == "AT_CONSENSUS":
        concordance = "BOTH_AT_CONSENSUS"
    elif signals[0] == signals[1]:
        concordance = "BOTH_SAME_SURPRISE_DIRECTION"
    else:
        concordance = "MIXED_OR_UNCONFIRMED_DIRECTION"
    out.update({
        "state": STATE,
        "reason": "POST_RELEASE_LOCAL_DOCUMENTARY_CONTEXT_NOT_FX_SIGNAL",
        "observed_at_utc_claim": captured.astimezone(timezone.utc).isoformat(),
        "pre_event_consensus_locked_locally": True,
        "actual_raw_html_checked_against_local_sha": True,
        "headline_core_concordance_claim": concordance,
        "series": [
            {
                "id": "PPI_FINAL_DEMAND_ALL_MOM_SA",
                "reference_period": "2026-10", "measure": "MOM",
                "seasonal_adjustment": "SA",
                "unit": "PERCENT_CHANGE",
                "actual_pct_documentary_claim": str(h_actual),
                "pre_event_consensus_pct_documentary_claim": str(h_consensus),
                "surprise_percentage_points": str(h_surprise),
                "surprise_relative_to_consensus": signals[0],
                "issuer_first_seen_independently_attested": False,
            },
            {
                "id": "PPI_FINAL_DEMAND_EX_FOOD_ENERGY_MOM_SA",
                "reference_period": "2026-10", "measure": "MOM",
                "seasonal_adjustment": "SA",
                "unit": "PERCENT_CHANGE",
                "actual_pct_documentary_claim": str(c_actual),
                "pre_event_consensus_pct_documentary_claim": str(c_consensus),
                "surprise_percentage_points": str(c_surprise),
                "surprise_relative_to_consensus": signals[1],
                "issuer_first_seen_independently_attested": False,
            },
        ],
    })
    return out


__all__ = ("SCHEMA", "inspect_oct2026_us_ppi_macro_context_lab")
