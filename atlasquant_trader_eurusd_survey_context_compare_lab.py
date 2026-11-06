"""No-lookahead EUR/USD quarterly-vs-meeting survey context audit.

The ECB SPF quarter-ahead DFR modal forecast and NY Fed SME FOMC target
range-midpoint modal forecast differ in horizon, population, rate measure and
historical release proof. Neither is a licensed/live trading signal. This
module intentionally performs NO numeric rate spread or directional ranking.
"""
from __future__ import annotations

from typing import Any

from atlasquant_trader_ecb_spf_dfr_context_lab import SCHEMA as EUR_SCHEMA
from atlasquant_trader_nyfed_sme_sep2026_lab import SCHEMA as USD_SCHEMA

SCHEMA = "ATLASQUANT_TRADER_EURUSD_SURVEY_CONTEXT_BRIDGE_LAB_V1"


def _sha_ok(value: Any) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


def compare_eurusd_survey_context_lab(eur: Any, usd: Any) -> dict[str, Any]:
    """Describe incompatibilities only; no rates/bps/bias can leave bridge."""
    e_valid = (
        isinstance(eur, dict) and eur.get("schema") == EUR_SCHEMA
        and eur.get("source_id") == "ECB_SPF_2026Q3"
        and eur.get("currency") == "EUR"
        and eur.get("quarterly_context_parsed") is True
        and eur.get("official_release_date") == "2026-07-24"
        and eur.get("q4_2026_modal_dfr_forecast_from_q3_pct") is not None
        and _sha_ok(eur.get("html_sha256"))
        and eur.get("historical_point_in_time_eligible") is False
        and eur.get("trade_authorized") is False
    )
    u_valid = (
        isinstance(usd, dict) and usd.get("schema") == USD_SCHEMA
        and usd.get("source_id") == "NYFED_SME_SEPTEMBER_2026"
        and usd.get("currency") == "USD"
        and usd.get("survey_meeting_end_date") == "2026-10-28"
        and usd.get("aggregation_is_median_of_modal_point_forecasts") is True
        and usd.get("median_target_range_midpoint_pct") is not None
        and _sha_ok(usd.get("source_raw_sha256"))
        and usd.get("historical_point_in_time_eligible") is False
        and usd.get("trade_authorized") is False
    )
    both = e_valid and u_valid
    return {
        "schema": SCHEMA,
        "state": ("LAB_BILATERAL_CONTEXTS_DISTINCT_NOT_RATE_COMPARABLE"
                  if both else "LAB_BILATERAL_CONTEXT_EVIDENCE_MISSING"),
        "reason": ("DIFFERENT_SURVEY_HORIZON_POLICY_MEASURE_AND_PIT_PROOF"
                   if both else "SOURCE_RECEIPT_NOT_ELIGIBLE"),
        "eur_context_receipt_present": e_valid,
        "usd_context_receipt_present": u_valid,
        "eur_measure": "ECB_DFR_QUARTERLY_MODAL_FORECAST" if e_valid else None,
        "usd_measure": "FOMC_TARGET_RANGE_MIDPOINT_MEETING_MEDIAN" if u_valid else None,
        "eur_horizon": "2026Q4" if e_valid else None,
        "usd_meeting_end_date": "2026-10-28" if u_valid else None,
        "eur_survey_release_date": "2026-07-24" if e_valid else None,
        "usd_questionnaire_distribution_date": "2026-09-02" if u_valid else None,
        "usd_results_release_date_inferred_unwitnessed": "2026-10-08" if u_valid else None,
        "same_horizon_and_policy_measure": False,
        "independent_historical_vintage_pair_verified": False,
        "bilateral_consensus_verified": False,
        "interest_rate_spread_bps": None,
        "market_surprise_bps": None, "fx_bias": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "can_feed_live_radar": False, "publishable": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "new_cost_brl": 0,
    }


__all__ = ["SCHEMA", "compare_eurusd_survey_context_lab"]
