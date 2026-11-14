"""Three dated pre-Dec-9 RBNZ analyst forecasts — DOCUMENTARY CONTEXT ONLY.

Observed via publicly accessible publisher references on 14 November 2026.
SOURCE PUBLICATION DAY is not an independently attested first availability
instant. No original bytes/SHA were archived here. A conservative
"research usable from 15 Nov 00:00 UTC" day floor prohibits pretending
to have recorded these facts in earlier market sessions.

ANZ (11 Nov): expects December +25bp OCR and 3.00% end-2026.
BNZ (29 Oct): expects +25bp in December after October 4:3 hold.
Westpac (9 Nov): December hike more likely than not; page 3 forecasts
3.00% after Dec, explicitly warns jobs/inflation risks could cause delay.

These are THREE BANK FORECASTS, not survey-weighted market consensus,
not market-implied OIS/futures odds, not independent issuer first-seen.
Three banks agreeing does NOT yield a 100% probability of an OCR hike,
let alone any probability of NZD appreciation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS, split_pair
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    _nominal_windows,
)

SCHEMA = "ATLASQUANT_RBNZ_DEC9_THREE_BANK_PRE_EVENT_FORECAST_RESEARCH_LAB_V1"
EVENT_UTC = datetime(2026, 12, 9, 1, 0, tzinfo=timezone.utc)
# Policy floor is later than 14 Nov research; NOT historical first-seen proof.
RESEARCH_SAFE_VISIBLE_FROM_UTC = datetime(
    2026, 11, 15, 0, 0, tzinfo=timezone.utc)
KNOWN_CURRENT_OCR_PCT = "2.75"
EXPECTED_HIKE_BPS_RESEARCH = 25


@dataclass(frozen=True)
class BankForecast:
    publisher: str
    source_url: str
    publication_day_claim: date
    expected_action: str
    expected_change_bps: int
    expected_dec2026_ocr_pct_claim: str
    evidence_kind: str
    caution: str


# Source day is disclosed in the report / publisher listing, not proof of
# timestamped immutable source contents as-of the author's stated date.
BANK_REPORTS = (
    BankForecast(
        "ANZ",
        "https://www.anz.co.nz/content/dam/anzconz/documents/"
        "economics-and-market-research/2026/ANZ-QEO-20261111.pdf",
        date(2026, 11, 11), "HIKE", 25, "3.00",
        "PUBLISHER_DATED_BANK_FORECAST_NOT_MARKET_SURVEY",
        "December hike forecast assumes global downside risks do not materialise",
    ),
    BankForecast(
        "BNZ",
        "https://www.bnz.co.nz/institutional-banking/research/"
        "publications/outlook-for-borrowers",
        date(2026, 10, 29), "HIKE", 25, "3.00",
        "PUBLISHER_DATED_BANK_FORECAST_NOT_MARKET_SURVEY",
        "After October hold BNZ expects 25bp hike in December, not certainty",
    ),
    BankForecast(
        "WESTPAC",
        "https://assets.dam.westpac.co.nz/is/content/wnzl/dist/"
        "all-of-bank/economic-reports/weekly-commentary/"
        "Weekly-Commentary_091126_report_09Nov26.pdf",
        date(2026, 11, 9), "HIKE", 25, "3.00",
        "PUBLISHER_DATED_BANK_FORECAST_NOT_MARKET_SURVEY",
        "Westpac describes hike as more likely than not but far from done deal",
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
    except (ValueError, TypeError, OverflowError):
        return None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_RBNZ_DEC9_THREE_BANK_FORECAST_RESEARCH_BLOCKED_NO_GO",
        "reason": reason,
        "release_event_utc": EVENT_UTC.isoformat(),
        "research_day_floor_utc": RESEARCH_SAFE_VISIBLE_FROM_UTC.isoformat(),
        "event_is_still_upcoming": False,
        "reference_policy_ocr_pct": KNOWN_CURRENT_OCR_PCT,
        "expected_rate_claim_if_25bp_hike_pct": None,
        "publisher_forecast_count": 0,
        "publisher_names": [],
        "bank_forecast_rows": [],
        "forecast_sources_independent_banks_not_independent_events": True,
        "economic_event_root_count": 1,
        "direct_nzd_pairs_in_fx28": [],
        "direct_pair_count": 0,
        "d1_w1_event_exposure_slots": 0,
        "consensus_universe_or_sample_frame_defined": False,
        "statistical_market_consensus_verified": False,
        "market_implied_hike_probability_verified": False,
        "publisher_document_original_bytes_retained": False,
        "publisher_first_seen_independently_attested": False,
        "publication_dates_are_calendar_only_claims": True,
        "safe_day_floor_is_not_actual_first_seen": True,
        "research_only_not_live_expectations": True,
        "forecast_might_be_revised_before_decision": True,
        "forecast_is_not_actual_ocr_decision": True,
        "fx_direction_from_ocr_expectations_established": False,
        "forecast_ocr_probability": None,
        "calibrated_nzd_fx_probability": None,
        "expected_nzd_pair_direction": None,
        "empirical_backtest_accuracy": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "live_alert_allowed": False,
        "publishable": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "http_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_rbnz_dec9_three_bank_forecasts_lab(*, as_of_utc: Any) -> dict[str, Any]:
    """Pure documented-source inventory. Never generate a trade/signal."""
    out = _base("INVALID_AS_OF_OR_RESEARCH_NOT_YET_ACCESSIBLE")
    now = _utc(as_of_utc)
    if now is None or now < RESEARCH_SAFE_VISIBLE_FROM_UTC:
        return out
    if (len(BANK_REPORTS) != 3
            or len({x.publisher for x in BANK_REPORTS}) != 3
            or len({x.source_url for x in BANK_REPORTS}) != 3
            or len(OFFICIAL_PAIRS) != 28):
        out["reason"] = "BANK_OR_FX28_REFERENCE_INCONSISTENT"
        return out
    if (any(f.publication_day_claim >= RESEARCH_SAFE_VISIBLE_FROM_UTC.date()
            or f.expected_action != "HIKE"
            or type(f.expected_change_bps) is not int
            or f.expected_change_bps != EXPECTED_HIKE_BPS_RESEARCH
            or Decimal(f.expected_dec2026_ocr_pct_claim) != (
                Decimal(KNOWN_CURRENT_OCR_PCT)
                + Decimal(f.expected_change_bps) / Decimal("100"))
            for f in BANK_REPORTS)):
        out["reason"] = "BANK_FORECAST_PUBDATE_ACTION_OR_TARGET_CONFLICT"
        return out

    nzd_pairs = [
        pair for pair in OFFICIAL_PAIRS if "NZD" in split_pair(pair)
    ]
    if len(nzd_pairs) != 7:
        out["reason"] = "FX28_NZD_BILATERAL_UNIVERSE_INCONSISTENT"
        return out
    windows = [
        (h, start, end)
        for h in ("D1", "W1")
        for start, end in _nominal_windows(h)
        if start <= EVENT_UTC < end
    ]
    if len(windows) != 2 or {h for h,_,_ in windows} != {"D1","W1"}:
        out["reason"] = "DEC9_EVENT_NOT_IN_FROZEN_D1_W1_CAMPAIGN"
        return out

    rows = []
    for bank in BANK_REPORTS:
        rows.append({
            "publisher": bank.publisher,
            "original_publisher_url": bank.source_url,
            "publisher_calendar_date_claim": bank.publication_day_claim.isoformat(),
            "kind": bank.evidence_kind,
            "forecast_target_event_utc": EVENT_UTC.isoformat(),
            "expected_policy_action_claim": bank.expected_action,
            "forecast_change_bps_claim": bank.expected_change_bps,
            "expected_dec2026_ocr_pct_claim": bank.expected_dec2026_ocr_pct_claim,
            "risk_note": bank.caution,
            "source_original_sha256": None,
            "source_captured_original_retained": False,
            "exact_issuer_publication_timestamp_independently_verified": False,
            "first_read_observed_at_pre_event_authenticated": False,
            "comparable_pre_event_market_price_quote": None,
            "has_population_representative_consensus_weight": False,
            "signed_nzd_fx_effect": None,
        })
    out.update({
        "state": (
            "LAB_RBNZ_DEC9_THREE_PUBLISHER_FORECASTS_UPCOMING_NO_GO"
            if now < EVENT_UTC else
            "LAB_RBNZ_DEC9_FORECAST_RESEARCH_EVENT_ALREADY_ELAPSED_NO_GO"
        ),
        "reason": (
            "THREE_BANK_VIEWS_NOT_MARKET_CONSENSUS_OR_FX_PROBABILITY"
            if now < EVENT_UTC else
            "AFTER_EVENT_HISTORICAL_REPORTS_NOT_NEW_PRE_EVENT_WITNESSES"
        ),
        "event_is_still_upcoming": now < EVENT_UTC,
        "expected_rate_claim_if_25bp_hike_pct": "3.00",
        "publisher_forecast_count": len(rows),
        "publisher_names": [x["publisher"] for x in rows],
        "bank_forecast_rows": rows,
        "direct_nzd_pairs_in_fx28": sorted(nzd_pairs),
        "direct_pair_count": len(nzd_pairs),
        "d1_w1_event_exposure_slots": len(nzd_pairs)*len(windows),
    })
    return out


__all__ = (
    "SCHEMA", "BANK_REPORTS", "EVENT_UTC", "RESEARCH_SAFE_VISIBLE_FROM_UTC",
    "inspect_rbnz_dec9_three_bank_forecasts_lab",
)
