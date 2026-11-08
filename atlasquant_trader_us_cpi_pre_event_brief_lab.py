"""Read-only briefing: September CPI previous vs October reported analyst poll.

This is a DOCUMENTARY comparison of *reported* numbers, not a forecast of the
October actual, surprise, USD direction or trade. No network, clock or I/O.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from atlasquant_trader_us_cpi_previous_mom_preflight_lab import (
    EXPECTED_PREVIOUS, inspect_us_cpi_previous_mom_preflight_lab,
)
from atlasquant_trader_us_oct2026_cpi_metric_availability_consensus_lab import (
    EXPECTED_CONSENSUS, REUTERS_URL,
)
from atlasquant_trader_us_cpi_source_custody_lab import (
    RELEASE, inspect_us_cpi_pre_event_bundle_lab,
)


SCHEMA = "ATLASQUANT_TRADER_US_CPI_OCT2026_DOCUMENTARY_PRE_EVENT_BRIEF_LAB_V1"
DOCUMENTARY_VISIBLE_AFTER = datetime(2026, 11, 9, tzinfo=timezone.utc)
EXPECTED_PREVIOUS_MONTH = "2026-09"
EXPECTED_EVENT_MONTH = "2026-10"
CONSENSUS_CLAIM = "0.3"
PREVIOUS_CLAIM = "0.6"


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BRIEF_BLOCKED", "reason": reason,
        "event_month": EXPECTED_EVENT_MONTH, "metric": "CPI_U_HEADLINE_MOM_SA_PERCENT",
        "scheduled_release_utc": RELEASE.isoformat(),
        "previous_month": None, "previous_mom_sa_percent_documentary": None,
        "reported_event_poll_mom_sa_percent_documentary": None,
        "consensus_minus_previous_percentage_points_documentary": None,
        "documentary_interpretation": None,
        "official_october_mom_actual": None, "actual_minus_consensus_surprise": None,
        "market_reaction_probability": None, "forecast_value": None,
        "directional_accuracy": None, "fx_bias": None, "index_bias": None,
        "source_bytes_self_consistent_unattested": False,
        "source_document_origin_verified": False,
        "poll_exact_event_semantics_independently_audited": False,
        "point_in_time_conclusively_witnessed": False,
        "pre_event_operational_ready": False,
        "research_only": True, "operational_bias": "AGUARDAR",
        "worker_enabled": False, "scheduler_enabled": False,
        "trade_authorized": False, "publishable": False,
        "network_requests": 0, "new_cost_brl": 0,
    }


def inspect_us_cpi_oct2026_pre_event_brief_lab(
    *, previous_casebook_raw: Any, as_of_utc: Any,
    previous_source_receipt: Any = None, consensus_source_receipt: Any = None,
) -> dict[str, Any]:
    """Interpret reported slowing as context only; never imply positive edge."""
    result = _base("INVALID_CLOCK_OR_DOCUMENTARY_RESEARCH")
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None):
        return result
    now = as_of_utc.astimezone(timezone.utc)
    if now < DOCUMENTARY_VISIBLE_AFTER:
        return _base("RESEARCH_NOT_VISIBLE_BEFORE_NOV9_UTC")
    previous = inspect_us_cpi_previous_mom_preflight_lab(
        previous_casebook_raw, as_of_utc=now,
    )
    if previous["state"] != "LAB_DOCUMENTARY_PREVIOUS_AVAILABLE_NOT_PIT_ATTESTED":
        return result
    if (EXPECTED_CONSENSUS["target_period"] != EXPECTED_EVENT_MONTH
            or EXPECTED_CONSENSUS["target_metric"] !=
            "SEASONALLY_ADJUSTED_MONTH_OVER_MONTH_PERCENT_CHANGE"
            or EXPECTED_CONSENSUS["source_url"] != REUTERS_URL
            or EXPECTED_CONSENSUS["consensus_mom_percent_as_documentary_claim"] != CONSENSUS_CLAIM
            or previous["prior_cpi_mom_sa_percent_documentary"] != float(PREVIOUS_CLAIM)):
        return _base("CONSENSUS_AND_PREVIOUS_DOCUMENTARY_METRIC_MISMATCH")

    prior_percent = float(PREVIOUS_CLAIM)
    poll_percent = float(CONSENSUS_CLAIM)
    result.update({
        "state": ("LAB_DOCUMENTARY_PRE_EVENT_EXPECTED_SLOWING_ONLY"
                  if now < RELEASE else "LAB_RELEASE_CLOCK_PASSED_WITHOUT_AUTHENTICATED_ACTUAL"),
        "reason": "DOCUMENTARY_ANALYST_POLL_AND_PREVIOUS_NOT_INDEPENDENTLY_ATTESTED",
        "previous_month": EXPECTED_PREVIOUS_MONTH,
        "previous_mom_sa_percent_documentary": prior_percent,
        "reported_event_poll_mom_sa_percent_documentary": poll_percent,
        "consensus_minus_previous_percentage_points_documentary": round(poll_percent - prior_percent, 6),
        "documentary_interpretation": (
            "ANALYSTS_EXPECTED_SLOWER_MONTHLY_CPI_VS_SEPTEMBER"
            if now < RELEASE else "PAST_POLL_NOT_A_CURRENT_OR_VERIFIED_ACTUAL"),
        "bls_previous_source_url": EXPECTED_PREVIOUS["source_url"],
        "reuters_reported_poll_source_url": REUTERS_URL,
    })
    # Even a pair of self-consistent local receipts is NOT independent source
    # authentication. Passing them cannot change the numeric/operational gates.
    if now < RELEASE and (previous_source_receipt is not None
                          or consensus_source_receipt is not None):
        evidence = inspect_us_cpi_pre_event_bundle_lab(
            previous_source_receipt, consensus_source_receipt,
            as_of_utc=now, forecast_cutoff_utc=now,
        )
        result["source_bytes_self_consistent_unattested"] = (
            evidence["state"] == "LAB_TWO_SOURCE_DOCUMENTARY_CANDIDATE_UNATTESTED")
        result["source_evidence_state"] = evidence["state"]
        result["source_evidence_reason"] = evidence["reason"]
    return result


__all__ = ["SCHEMA", "inspect_us_cpi_oct2026_pre_event_brief_lab"]
