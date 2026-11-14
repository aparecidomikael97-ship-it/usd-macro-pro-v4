"""RBNZ 09-Dec-2026 expectation: exact-meeting OIS source + entitlement gate.

Issuer evidence researched 2026-11-14:
- RBNZ statistical B2 daily close has the DECIDED OCR, 30/60/90d
  bank bills and interest rate swaps keyed to 90-day bank bills, NOT
  the meeting-date OCR-based OIS contract.
- NZFMA official NZdata service explicitly marks NZD OIS RBNZ Meeting
  Date, OIS closes and live OCR Compound Index as FEE LIABLE.
- NZFMA delayed free data (24h) includes 1y/3y bank-bill-based swaps and
  the realised OCR Compound Index; its NZONIA is BACKWARD-looking, not
  a forward probability of a single future policy meeting.
- BNZ Nov09 65% figure is an estimate REPORTED in secondary analysis,
  not an actual quote from a uniquely identified instrument / provider.

Consequently there is NO authenticated pre-09-Dec meeting OIS quote and
NO permission/entitlement recorded for AtlasQuant to use the paid feed.
Do not subscribe, collect licensed data, scrape, guess prices, or call
a 2y swap "RBNZ meeting-date OIS". This checker is entirely offline.

Source categories concern DOCUMENTARY suitability only. They never
become a trading signal, probability, actual rate or issuer first-seen.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS, split_pair
from atlasquant_trader_nzd_rbnz_dec9_three_bank_forecast_context_lab import (
    EVENT_UTC, RESEARCH_SAFE_VISIBLE_FROM_UTC,
)

SCHEMA = "ATLASQUANT_RBNZ_DEC9_MEETING_OIS_ENTITLEMENT_GATE_LAB_V1"
NZFMA_SOURCE_URL = "https://www.nzfma.org/nzdata/"
NZFBF_NZOR_DEFINITION_URL = (
    "https://www.nzfbf.co.nz/benchmarks/closing-rates/nzor"
)
NZOR_BENCHMARK_CODE = "NZOR"
NZFMA_COMPOUND_URL = "https://www.nzfma.org/nzdata/nz-ocr-compound-index"
RBNZ_B2_SOURCE_URL = (
    "https://www.rbnz.govt.nz/statistics/series/"
    "exchange-and-interest-rates/wholesale-interest-rates"
)
BNZ_NOV09_SOURCE_URL = (
    "https://www.bnz.co.nz/assets/markets/research/"
    "20261109_BNZMO-v2.pdf?461461917d84fa9f5d027387b59329e258f8c950="
)


@dataclass(frozen=True)
class InstrumentCandidate:
    source_key: str
    published_by: str
    issuer_reference_url: str
    instrument_class: str
    access_tier: str
    meeting_date_ois_contract: bool
    historical_backward_looking: bool
    indicative_market_analysis: bool
    reason: str


CANDIDATES = (
    InstrumentCandidate(
        "NZFMA_MEETING_DATE_OIS_LICENSED",
        "NZFMA_NZDATA",
        NZFMA_SOURCE_URL,
        "OCR_OIS_ONE_RBNZ_MEETING",
        "SUBSCRIPTION_REQUIRED_NOT_CONNECTED",
        True, False, False,
        "CORRECT_INSTRUMENT_BUT_ATLASQUANT_HAS_NO_VERIFIED_ENTITLEMENT_OR_QUOTE",
    ),
    InstrumentCandidate(
        "RBNZ_B2_DAILY_OCR_DECIDED",
        "RBNZ",
        RBNZ_B2_SOURCE_URL,
        "POLICY_ACTUAL_OCR_NOT_MARKET_EXPECTATION",
        "PUBLIC_REFERENCE_DAILY_LAG",
        False, True, False,
        "DECIDED_OCR_IS_NOT_PRE_EVENT_EXPECTED_OCR",
    ),
    InstrumentCandidate(
        "RBNZ_B2_2Y_BANK_BILL_SWAP",
        "RBNZ_NZFMA_LSEG",
        RBNZ_B2_SOURCE_URL,
        "TWO_YEAR_SWAP_FLOATING_NZ_90_DAY_BANK_BILL",
        "PUBLIC_REFERENCE_DAILY_LAG_THIRD_PARTY_RIGHTS",
        False, False, False,
        "TWO_YEAR_SWAP_PATH_AND_BKBM_CREDIT_PREMIA_ARE_NOT_SINGLE_MEETING_OIS",
    ),
    InstrumentCandidate(
        "NZFMA_FREE_OCR_COMPOUND_INDEX_DELAYED",
        "NZFMA_NZFBF",
        NZFMA_COMPOUND_URL,
        "REALIZED_OCR_COMPOUNDED_IN_ARREARS",
        "FREE_WITH_24_HOUR_DELAY",
        False, True, False,
        "REALIZED_NZONIA_IS_BACKWARD_LOOKING_NOT_MEETING_EXPECTATION",
    ),
    InstrumentCandidate(
        "NZFMA_FREE_1Y_3Y_SWAP_DELAYED",
        "NZFMA_NZDATA",
        NZFMA_SOURCE_URL,
        "ONE_THREE_YEAR_NZD_SWAPS",
        "FREE_WITH_24_HOUR_DELAY",
        False, False, False,
        "LONGER_TENOR_BKBM_RATE_SWAPS_NOT_MEETING_OIS",
    ),
    InstrumentCandidate(
        "BNZ_REPORTED_65PCT_DEC09_NOV09",
        "BNZ_SECONDARY_REPORT",
        BNZ_NOV09_SOURCE_URL,
        "RESEARCH_WRITER_ESTIMATE_OF_MEETING_HIKE_ODDS",
        "PUBLIC_REPORT_WITH_UNLICENSED_UNDERLYING_BLOOMBERG",
        False, False, True,
        "SECONDARY_BANK_REPORT_NOT_RAW_MEETING_DATE_OIS_QUOTE",
    ),
)


def _utc(value: Any) -> datetime | None:
    if (type(value) is not datetime or value.tzinfo is None
            or value.microsecond != 0):
        return None
    try:
        if value.utcoffset() is None:
            return None
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError, TypeError):
        return None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_RBNZ_MEETING_OIS_SOURCE_GATE_BLOCKED_NO_GO",
        "reason": reason,
        "policy_event_utc": EVENT_UTC.isoformat(),
        "research_visible_floor_utc":
            RESEARCH_SAFE_VISIBLE_FROM_UTC.isoformat(),
        "issuer_source_catalog": [],
        "correct_benchmark_nzfbf_identifier": NZOR_BENCHMARK_CODE,
        "correct_benchmark_official_methodology_url":
            NZFBF_NZOR_DEFINITION_URL,
        "nz_or_is_closing_midrate_between_consecutive_ocr_meetings": True,
        "a_closing_midrate_is_not_automatically_a_pre_event_tick": True,
        "source_candidates_count": 0,
        "correct_instrument_sources_known": 0,
        "source_key_requested": None,
        "source_requested_classification": None,
        "source_requested_reason": None,
        "meeting_date_ois_license_independently_verified": False,
        "paid_subscription_active_or_committed": False,
        "issuer_market_quote_original_retained": False,
        "meeting_date_ois_quote_exists_in_atlasquant": False,
        "market_quote_bid_ask_settlement_reconciled": False,
        "quote_published_timestamp_independently_authenticated": False,
        "quote_capture_clock_before_event_verified": False,
        "vendor_redistribution_rights_confirmed": False,
        "provider_issued_price_and_convention_checked": False,
        "immediate_pre_dec9_expectation_available": False,
        "dec09_ocr_actual_already_announced": False,
        "actual_policy_surprise_basis_points": None,
        "dec09_25bps_hike_probability": None,
        "nzd_direction_probability": None,
        "fx28_operational_bias": "AGUARDAR",
        "direct_nzd_fx28_pair_count": 0,
        "direct_nzd_fx28_pairs": [],
        "d1_w1_potential_event_exposures": 0,
        "economic_event_roots": 1,
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "scheduler_enabled": False,
        "worker_enabled": False,
        "http_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_rbnz_dec9_ois_sources_lab(
    *, as_of_utc: Any, selected_source_key: Any = None,
) -> dict[str, Any]:
    """Admissibility check; never accept caller quote values as licensed."""
    result = _base("INVALID_CLOCK_OR_RESEARCH_NOT_YET_VISIBLE")
    now = _utc(as_of_utc)
    if now is None or now < RESEARCH_SAFE_VISIBLE_FROM_UTC:
        return result
    if (len(CANDIDATES) != 6 or len({c.source_key for c in CANDIDATES}) != 6
            or any(type(c) is not InstrumentCandidate or
                   not c.issuer_reference_url.startswith("https://") for c in CANDIDATES)
            or len(OFFICIAL_PAIRS) != 28):
        result["reason"] = "SOURCE_CATALOG_OR_UNIVERSE_INCONSISTENT"
        return result
    if (selected_source_key is not None
            and (type(selected_source_key) is not str
                 or selected_source_key not in {
                    x.source_key for x in CANDIDATES})):
        result["reason"] = "UNKNOWN_OR_UNSUPPORTED_SOURCE_KEY"
        return result
    pairs = sorted(p for p in OFFICIAL_PAIRS if "NZD" in split_pair(p))
    if len(pairs) != 7:
        result["reason"] = "FX28_NZD_BILATERAL_UNIVERSE_INCONSISTENT"
        return result
    results = []
    for source in CANDIDATES:
        results.append({
            "source_key": source.source_key,
            "published_by": source.published_by,
            "official_or_publisher_reference_url": source.issuer_reference_url,
            "instrument_class": source.instrument_class,
            "access_tier_as_officially_documented": source.access_tier,
            "is_exact_meeting_date_ois_kind": source.meeting_date_ois_contract,
            "is_backward_looking_rate": source.historical_backward_looking,
            "is_secondary_market_commentary": source.indicative_market_analysis,
            "can_supply_dec09_ois_quote_now": False,
            "source_original_bytes_or_quote_authenticated": False,
            "current_fx_bias_authorized": False,
            "source_rejection_reason": source.reason,
        })
    source = next(
        (x for x in results if x["source_key"] == selected_source_key),None
    )
    result.update({
        "state": (
            "LAB_RBNZ_DEC09_OIS_PROVENANCE_READY_FOR_RESEARCH_NO_GO"
            if now < EVENT_UTC else
            "LAB_RBNZ_DEC09_OIS_EVENT_ELAPSED_NO_RETRO_SNAPSHOT_NO_GO"
        ),
        "reason": (
            "REAL_MEETING_OIS_NEEDS_LICENSE_ORIGINAL_BIDASK_TIMES_NO_PROXY"
            if now < EVENT_UTC else
            "NO_HISTORICAL_IMMEDIATE_PRE_EVENT_OIS_CAN_BE_BACKFILLED"
        ),
        "issuer_source_catalog": results,
        "source_candidates_count": len(results),
        "correct_instrument_sources_known": sum(
            bool(x["is_exact_meeting_date_ois_kind"]) for x in results),
        "source_key_requested": selected_source_key,
        "source_requested_classification": (
            source["instrument_class"] if source is not None else None
        ),
        "source_requested_reason": (
            source["source_rejection_reason"] if source is not None else None
        ),
        "direct_nzd_fx28_pair_count": len(pairs),
        "direct_nzd_fx28_pairs": pairs,
        "d1_w1_potential_event_exposures": 2 * len(pairs),
    })
    return result


__all__ = (
    "SCHEMA", "NZFMA_SOURCE_URL", "NZFMA_COMPOUND_URL",
    "NZFBF_NZOR_DEFINITION_URL", "NZOR_BENCHMARK_CODE",
    "RBNZ_B2_SOURCE_URL", "CANDIDATES", "InstrumentCandidate",
    "inspect_rbnz_dec9_ois_sources_lab",
)
