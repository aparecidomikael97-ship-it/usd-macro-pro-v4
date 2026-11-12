"""PPI Oct-2026 documentary surprise vs. 7 USD-FX post-event reaction, LAB.

Reconciles *already accepted* offline candidate outputs, NEVER accepts a
caller-supplied value as independently verified PPI, consensus provenance or
broker historical data. Nothing is fetched, written, forecasted or traded.

A PPI headline/core actual minus pre-event consensus is a descriptive
economic surprise (percentage points). FX moves are observed *after* the
release, USD-normalized basis points for M15/H1/H4. The 7 exchange rates
react to ONE shared event, not 7 independent directional forecast trials.
Neither comparison proves PPI caused price moves or that trading was feasible.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import (
    SCHEMA as PPI_SCHEMA, RELEASE_UTC as PPI_EVENT_UTC,
)
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import (
    SCHEMA as FX_SCHEMA, EVENT_UTC, LAST_REQUIRED_CLOSE_UTC,
    USD_FX, WINDOWS, PRE_EVENT_HEADLINE_CONSENSUS_MOM,
    PRE_EVENT_CORE_CONSENSUS_MOM, TD_PRE_EVENT_HTML_SHA256,
    TE_PRE_EVENT_HTML_SHA256,
)

SCHEMA = "ATLASQUANT_TRADER_PPI_MACRO_SURPRISE_FX7_RECONCILIATION_LAB_V1"
PPI_GOOD = "LAB_PPI_RESEARCH_SURPRISE_ONLY_UNATTESTED"
FX_GOOD = "LAB_PPI_FX_7PAIR_FORWARD_REACTION_DOCUMENTARY_NO_GO"
SHA = re.compile(r"[0-9a-f]{64}\Z")
RATE = re.compile(r"[+-]?(?:0|[1-9][0-9]?)(?:\.[0-9]{1,3})?\Z")
BPS = re.compile(r"[+-]?(?:0|[1-9][0-9]{0,3})(?:\.[0-9]{1,2})?\Z")


def _block(reason: str, state: str = "LAB_PPI_MACRO_FX7_RECONCILIATION_BLOCKED") -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": state, "reason": reason,
        "event_release_utc": EVENT_UTC.isoformat(),
        "all_price_reaction_windows_closed": False,
        "economic_actual_and_consensus_candidate": False,
        "fx7_archive_candidate": False,
        "headline_surprise_pp": None, "core_surprise_pp": None,
        "headline_relative_to_consensus": None,
        "core_relative_to_consensus": None,
        "surprises_same_nonzero_direction": False,
        "usd_normalized_fx7_observed_reactions": None,
        "macro_spot_joint_evidence_status": "INSUFFICIENT_EVIDENCE",
        "studied_usd_fx_pairs": list(USD_FX),
        "independent_economic_event_sample_count": 0,
        "independent_directional_predictions_validated": 0,
        "causal_event_impact_identified": False,
        "official_ppi_first_print_independently_authenticated": False,
        "two_consensus_sources_independently_attested": False,
        "ppi_actual_available_at_original_release_independently_attested": False,
        "fx_prices_broker_pit_provenance_authenticated": False,
        "broker_bidask_spread_and_slippage_verified": False,
        "historical_out_of_sample_accuracy": None,
        "calibrated_probability": None,
        "directional_forecast": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "trade_authorized": False, "live_alert_allowed": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "files_written": 0, "http_requests": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _declared_utc(value: Any) -> datetime | None:
    if type(value) is not str:
        return None
    try:
        return _utc(datetime.fromisoformat(value))
    except (ValueError, TypeError, OverflowError):
        return None


def _number(value: Any, pattern: re.Pattern[str], max_abs: Decimal) -> Decimal | None:
    if type(value) is not str or pattern.fullmatch(value) is None:
        return None
    try:
        result = Decimal(value)
        return result if result.is_finite() and abs(result) <= max_abs else None
    except (ValueError, InvalidOperation, TypeError):
        return None


def _relative_to_consensus(value: Decimal) -> str:
    return ("ABOVE_CONSENSUS" if value > 0 else
            "BELOW_CONSENSUS" if value < 0 else "AT_CONSENSUS")


def reconcile_ppi_surprise_fx7_lab(
    *, ppi_comparison: Any, fx7_reaction: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Fail closed and return descriptive evidence only after closed H4 window."""
    now = _utc(as_of_utc)
    if now is None:
        return _block("INVALID_AS_OF_CLOCK")
    if PPI_EVENT_UTC != EVENT_UTC:
        return _block("EVENT_RELEASE_CONTRACTS_DISAGREE")
    if now < EVENT_UTC:
        return _block("PPI_EVENT_NOT_YET_RELEASED",
                      "LAB_WAIT_PPI_OCT2026_OFFICIAL_RELEASE")
    if now < LAST_REQUIRED_CLOSE_UTC:
        return _block("PPI_FX_H4_WINDOW_NOT_YET_CLOSED",
                      "LAB_WAIT_PPI_FX7_H4_CLOSE")

    if type(ppi_comparison) is not dict or type(fx7_reaction) is not dict:
        return _block("REQUIRED_DOCUMENTARY_SOURCE_REPORTS_MISSING")
    if ppi_comparison.get("schema") != PPI_SCHEMA or ppi_comparison.get("state") != PPI_GOOD:
        return _block("PPI_ACTUAL_VS_CONSENSUS_NOT_ACCEPTED")
    if fx7_reaction.get("schema") != FX_SCHEMA or fx7_reaction.get("state") != FX_GOOD:
        return _block("FX7_POST_RELEASE_REACTION_NOT_ACCEPTED")
    if (ppi_comparison.get("official_source_url")
            != "https://www.bls.gov/news.release/archives/ppi_11132026.htm"
            or ppi_comparison.get("event_release_utc") != EVENT_UTC.isoformat()
            or not isinstance(ppi_comparison.get("source_sha256"), type(None))):
        # The existing comparator intentionally returns source_sha256=None:
        # it does NOT re-attach authenticated official raw bytes.
        return _block("PPI_COMPARISON_SOURCE_STATUS_UNEXPECTED")
    if (ppi_comparison.get("official_actual_independently_attested") is not False
            or ppi_comparison.get("trade_authorized") is not False
            or ppi_comparison.get("publishable") is not False
            or ppi_comparison.get("operational_bias") != "AGUARDAR"):
        return _block("PPI_CLAIM_UNEXPECTEDLY_PROMOTED_TO_AUTHENTICATED_OR_TRADE")
    if (fx7_reaction.get("event_release_utc") != EVENT_UTC.isoformat()
            or fx7_reaction.get("cohort_symbols") != list(USD_FX)
            or fx7_reaction.get("window_minutes") != [v for _, v in WINDOWS]
            or fx7_reaction.get("independent_economic_event_sample_count") != 1
            or fx7_reaction.get("local_seven_file_hashes_match") is not True
            or fx7_reaction.get("source_broker_independently_authenticated") is not False
            or fx7_reaction.get("trade_authorized") is not False
            or fx7_reaction.get("operational_bias") != "AGUARDAR"):
        return _block("FX7_RECEIPT_OR_NO_TRADE_CONTRACT_UNEXPECTED")

    archive_claim = _declared_utc(fx7_reaction.get("archive_captured_at_utc_claim"))
    if archive_claim is None or not LAST_REQUIRED_CLOSE_UTC <= archive_claim <= now:
        return _block("FX7_ARCHIVE_CAPTURE_CLAIM_AFTER_H4_REQUIRED")
    frozen_hashes = fx7_reaction.get("pre_event_source_hashes")
    frozen_values = fx7_reaction.get("pre_event_consensus_mom_pct_claim")
    if (frozen_hashes != {"td": TD_PRE_EVENT_HTML_SHA256, "te": TE_PRE_EVENT_HTML_SHA256}
            or frozen_values != {
                "final_demand": PRE_EVENT_HEADLINE_CONSENSUS_MOM,
                "less_food_and_energy": PRE_EVENT_CORE_CONSENSUS_MOM
            }):
        return _block("FROZEN_CONSENSUS_MISMATCH")

    h_actual = _number(
        ppi_comparison.get("headline_final_demand_sa_mom_pct_body_claim"), RATE, Decimal(20))
    c_actual = _number(
        ppi_comparison.get("core_ex_food_energy_sa_mom_pct_body_claim"), RATE, Decimal(20))
    h_surprise = _number(
        ppi_comparison.get("headline_vs_td_pre_event_diff_pp"), RATE, Decimal(20))
    c_surprise = _number(
        ppi_comparison.get("core_vs_td_pre_event_diff_pp"), RATE, Decimal(20))
    if any(x is None for x in (h_actual, c_actual, h_surprise, c_surprise)):
        return _block("PPI_HEADLINE_CORE_OR_SURPRISE_MISSING")
    if (h_actual - Decimal(PRE_EVENT_HEADLINE_CONSENSUS_MOM) != h_surprise
            or c_actual - Decimal(PRE_EVENT_CORE_CONSENSUS_MOM) != c_surprise):
        return _block("PPI_SURPRISE_ARITHMETIC_DOES_NOT_RECONCILE")

    prices = fx7_reaction.get("price_reactions_usd_normalized_bps")
    if type(prices) is not dict or set(prices) != set(USD_FX):
        return _block("FX7_COHORT_NOT_EXACTLY_SEVEN_PAIRS")
    descriptive: dict[str, dict[str, Any]] = {}
    for horizon, minutes in WINDOWS:
        counts = {"usd_stronger_in_observed_close_count": 0,
                  "usd_weaker_in_observed_close_count": 0,
                  "unchanged_in_observed_close_count": 0}
        for sym in USD_FX:
            series = prices[sym]
            if type(series) is not dict or set(series) != {name for name, _ in WINDOWS}:
                return _block("FX7_MISSING_OR_EXTRA_M15_H1_H4_KEYS")
            bps = _number(series.get(horizon), BPS, Decimal(5000))
            if bps is None:
                return _block("FX7_REACTION_NUMERIC_RANGE_OR_FORMAT_INVALID")
            key = ("usd_stronger_in_observed_close_count" if bps > 0 else
                   "usd_weaker_in_observed_close_count" if bps < 0 else
                   "unchanged_in_observed_close_count")
            counts[key] += 1
        descriptive[horizon] = {
            "minutes_after_release": minutes, **counts,
            "correlated_currency_pairs_not_independent_events": True,
            "causality_not_established": True,
            "directional_forecast_not_authorized": True,
        }

    out = _block("DESCRIPTIVE_COMPARISON_ONLY_NOT_FORECAST_OR_CAUSALITY",
                 "LAB_PPI_SURPRISE_FX7_OBSERVED_JOINT_RESEARCH_NO_GO")
    out.update({
        "all_price_reaction_windows_closed": True,
        "economic_actual_and_consensus_candidate": True,
        "fx7_archive_candidate": True,
        "headline_surprise_pp": str(h_surprise),
        "core_surprise_pp": str(c_surprise),
        "headline_relative_to_consensus": _relative_to_consensus(h_surprise),
        "core_relative_to_consensus": _relative_to_consensus(c_surprise),
        "surprises_same_nonzero_direction": (
            (h_surprise > 0 and c_surprise > 0)
            or (h_surprise < 0 and c_surprise < 0)),
        "usd_normalized_fx7_observed_reactions": descriptive,
        "macro_spot_joint_evidence_status":
            "POST_EVENT_ASSOCIATION_ONLY_NO_CAUSAL_OR_DIRECTIONAL_FORECAST",
        "independent_economic_event_sample_count": 1,
    })
    return out


__all__ = ["SCHEMA", "reconcile_ppi_surprise_fx7_lab"]
