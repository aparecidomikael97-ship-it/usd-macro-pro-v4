"""Official G8 policy-expectation survey leads and dated BoE example, LAB.

A PUBLIC SURVEY LEAD is not an authenticated time-matched market forward curve.
In particular, post-meeting survey RESULTS cannot be retroactively used to
forecast that same meeting. All pairs/horizons abstain from real FX direction.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_TRADER_G8_POLICY_SURVEY_LEADS_LAB_V1"
CONSERVATIVE_AVAILABLE = datetime(2026, 11, 4, tzinfo=timezone.utc)
HORIZONS = ("D1", "W1", "MN1")
SOURCE_FIELDS = frozenset((
    "currency", "source_id", "source_url", "category", "publication_granularity",
    "target_kind", "vintage_label", "review_limitation",
))
SURVEY = "OFFICIAL_POLICY_EXPECTATIONS_SURVEY_LEAD"
SUMMARY = "OFFICIAL_MARKET_EXPECTATIONS_SUMMARY_NO_RAW_CURVE"
GAP = "NO_PUBLIC_MATCHED_EXPECTATION_SURVEY_FOUND"
LEADS = (
    {
        "currency": "USD", "source_id": "NYFED_SME",
        "source_url": "https://www.newyorkfed.org/markets/market-intelligence/survey-of-market-expectations",
        "category": SURVEY, "publication_granularity": "AFTER_FOMC_MINUTES",
        "target_kind": "FED_FUNDS_LEVELS_AT_FOMC_MEETINGS", "vintage_label": "2026-09",
        "review_limitation": "October questions exist, but survey results are published after the corresponding FOMC, not a pre-meeting data release.",
    },
    {
        "currency": "EUR", "source_id": "ECB_SMA",
        "source_url": "https://www.ecb.europa.eu/stats/ecb_surveys/sma/html/index.en.html",
        "category": SURVEY, "publication_granularity": "MEETING_CYCLE",
        "target_kind": "DEPOSIT_FACILITY_RATE_BY_ECB_MEETING", "vintage_label": "2026-10",
        "review_limitation": "October survey results published after October decision; next event and survey target must be checked independently.",
    },
    {
        "currency": "GBP", "source_id": "BOE_MARKET_PARTICIPANTS",
        "source_url": "https://www.bankofengland.co.uk/markets/market-intelligence/survey-results/2026/market-participants-survey-results-september-2026",
        "category": SURVEY, "publication_granularity": "EIGHT_SURVEYS_YEAR",
        "target_kind": "MPC_MEETING_MODAL_AND_OUTCOME_PROBABILITIES", "vintage_label": "2026-09",
        "review_limitation": "September survey precedes November meeting but is not a current OIS curve or FX directional accuracy.",
    },
    {
        "currency": "JPY", "source_id": "BOJ_MONEY_MARKET",
        "source_url": "https://www.boj.or.jp/en/paym/market/",
        "category": GAP, "publication_granularity": "ANNUAL_MONEY_MARKET_FUNCTIONING",
        "target_kind": "MARKET_FUNCTIONING_NOT_FUTURE_POLICY_LEVEL", "vintage_label": "2025-08",
        "review_limitation": "BOJ market-functioning survey is not a public meeting-by-meeting interest-rate expectation series.",
    },
    {
        "currency": "CHF", "source_id": "SNB_POLICY_ASSESSMENT",
        "source_url": "https://www.snb.ch/en/the-snb/mandates-goals/monetary-policy/decisions",
        "category": GAP, "publication_granularity": "QUARTERLY_POLICY_DECISION",
        "target_kind": "SNB_DECISION_NOT_MARKET_EXPECTATION", "vintage_label": "2026-09",
        "review_limitation": "SNB conditional inflation forecast assumes a policy rate; this is not investors' future rate-path probability.",
    },
    {
        "currency": "CAD", "source_id": "BOC_MARKET_PARTICIPANTS",
        "source_url": "https://www.bankofcanada.ca/publications/market-participants-survey/",
        "category": SURVEY, "publication_granularity": "QUARTERLY_DELAYED",
        "target_kind": "BOC_POLICY_RATE_SURVEY_BY_QUARTER", "vintage_label": "2026-Q2",
        "review_limitation": "Quarterly results lag decisions; a November 9 release must not be used for an earlier cutoff.",
    },
    {
        "currency": "AUD", "source_id": "RBA_STATEMENT_MARKET_PATH",
        "source_url": "https://www.rba.gov.au/publications/smp/2026/nov/financial-conditions.html",
        "category": SUMMARY, "publication_granularity": "QUARTERLY_STATEMENT",
        "target_kind": "OIS_MARKET_PRICING_SUMMARY_ONLY", "vintage_label": "2026-11",
        "review_limitation": "Narrative/graph references third-party market prices; raw matched OIS history and reuse rights not validated.",
    },
    {
        "currency": "NZD", "source_id": "RBNZ_M14",
        "source_url": "https://www.rbnz.govt.nz/hub/home/statistics/series/economic-indicators/survey-of-expectations",
        "category": SURVEY, "publication_granularity": "QUARTERLY",
        "target_kind": "OCR_QUARTER_END_AND_ONE_YEAR_MEAN", "vintage_label": "2026-08",
        "review_limitation": "Averaged OCR expectation at quarter-end and one year; not meeting-by-meeting odds or daily D1 curve.",
    },
)
BOE_NOV5_URL = LEADS[2]["source_url"]
BOE_BUCKET_FIELDS = frozenset(("rate_after_mpc_band", "mean_respondent_probability_pct"))
# Official September 2026 Market Participants Survey, question 1cii;
# 90 respondents, rounded to 0.1 percentage point, so total = 100.1%.
BOE_NOV5_BUCKETS = (
    {"rate_after_mpc_band": "BELOW_3_50", "mean_respondent_probability_pct": "0.3"},
    {"rate_after_mpc_band": "3_50", "mean_respondent_probability_pct": "1.7"},
    {"rate_after_mpc_band": "3_75", "mean_respondent_probability_pct": "60.4"},
    {"rate_after_mpc_band": "4_00", "mean_respondent_probability_pct": "35.0"},
    {"rate_after_mpc_band": "4_25", "mean_respondent_probability_pct": "2.4"},
    {"rate_after_mpc_band": "ABOVE_4_25", "mean_respondent_probability_pct": "0.3"},
)


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_SURVEY_LEADS_REFUSED", "reason": reason,
        "source_leads": {}, "pair_horizons": [], "boe_nov5_documentary": None,
        "source_count": 0, "pair_count": 0,
        "same_tenor_expectation_curves_verified": False,
        "independent_source_receipts_verified": False,
        "market_quotes_verified": False, "fx_directional_oos_proven": False,
        "accuracy_90_proven": False, "probability_calibrated": None,
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "paid_services_enabled": False,
    }


def _verified_frozen_rows(
    supplied: Sequence[Mapping[str, Any]] | None,
    frozen: tuple[dict[str, str], ...],
    fields: frozenset[str],
) -> list[dict[str, str]]:
    raw = frozen if supplied is None else supplied
    if not isinstance(raw, (list, tuple)) or len(raw) != len(frozen):
        raise ValueError("Unexpected size of documentary material")
    checked = []
    for row, expected in zip(raw, frozen):
        if not isinstance(row, Mapping) or set(row) != fields or dict(row) != expected:
            raise ValueError("Unreviewed or altered official survey claim")
        checked.append(dict(row))
    return checked


def build_g8_policy_survey_leads_lab(
    *, at: datetime,
    sources: Sequence[Mapping[str, Any]] | None = None,
    boe_probabilities: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Read a dated SOURCE INVENTORY; never infer market-implied FX odds."""
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("Explicit timezone-aware research clock required")
    now = at.astimezone(timezone.utc)
    if now < CONSERVATIVE_AVAILABLE:
        return _deny("No independent intraday receipt for Nov 3 research compilation")
    try:
        catalog = _verified_frozen_rows(sources, LEADS, SOURCE_FIELDS)
        buckets = _verified_frozen_rows(boe_probabilities, BOE_NOV5_BUCKETS,
                                       BOE_BUCKET_FIELDS)
    except ValueError as exc:
        return _deny(str(exc))
    by_currency = {s["currency"]: s for s in catalog}
    if set(by_currency) != set(CURRENCIES):
        return _deny("Expected eight unique currency leads")
    try:
        total = sum(Decimal(x["mean_respondent_probability_pct"]) for x in buckets)
    except (InvalidOperation, ValueError):
        return _deny("Unusable survey probability")
    if total != Decimal("100.1"):
        return _deny("BoE published rounded sum differs from documented case")
    event_day = date(2026, 11, 5)
    if now.date() < event_day:
        mpc_state = "HISTORICAL_PRE_MEETING_SURVEY_NOT_CURRENT_CONSENSUS"
    elif now.date() == event_day:
        mpc_state = "MEETING_DAY_PUBLICATION_HOUR_UNATTESTED"
    else:
        mpc_state = "TARGET_MEETING_PASSED_NO_OUTCOME_IMPORTED"

    pair_rows = []
    for horizon in HORIZONS:
        for p in OFFICIAL_PAIRS:
            base, quote = split_pair(p)
            a, b = by_currency[base], by_currency[quote]
            if GAP in (a["category"], b["category"]):
                status = "MISSING_MEETING_RATE_EXPECTATION_LEAD"
            elif SUMMARY in (a["category"], b["category"]):
                status = "SUMMARY_WITHOUT_REUSABLE_MATCHED_CURVE"
            else:
                status = "SURVEY_TARGETS_AND_VINTAGES_NOT_COMPARABLE"
            pair_rows.append({
                "pair": p, "horizon": horizon, "base": base, "quote": quote,
                "research_gap": status, "paired_observations_available": False,
                "expectation_gap_bp": None, "directional_bias": "AGUARDAR",
                "probability_calibrated": None, "trade_authorized": False,
            })
    return {
        **_deny(""), "state": "LAB_G8_OFFICIAL_SURVEY_SOURCE_LEADS_ONLY",
        "reason": "Five public survey leads do not form eight synchronized forward-rate curves.",
        "research_as_of_utc": now.isoformat(),
        "catalog_available_from_utc": CONSERVATIVE_AVAILABLE.isoformat(),
        "source_leads": by_currency, "source_count": len(catalog),
        "survey_lead_count": sum(s["category"] == SURVEY for s in catalog),
        "commentary_only_count": sum(s["category"] == SUMMARY for s in catalog),
        "no_comparable_survey_lead_count": sum(s["category"] == GAP for s in catalog),
        "pair_horizons": pair_rows, "pair_count": len(OFFICIAL_PAIRS),
        "horizon_count": len(HORIZONS),
        "boe_nov5_documentary": {
            "source_url": BOE_NOV5_URL,
            "source_survey": "BOE_MARKET_PARTICIPANTS_SEPTEMBER_2026",
            "sample_collected_through": "2026-09-04",
            "published_on": "2026-09-18",
            "target_mpc_on": event_day.isoformat(),
            "respondents": 90, "probability_kind": "MEAN_OF_SURVEY_RESPONDENT_OPINIONS",
            "rate_buckets": buckets, "sum_after_one_decimal_rounding_pct": str(total),
            "survey_state": mpc_state,
            "publication_timestamp_independently_attested": False,
            "market_implied_ois_distribution": False,
            "currency_fx_probability": None,
            "trade_authorized": False,
        },
        "maturity_matched": False, "survey_freshness_individually_verified": False,
        "survey_source_reuse_rights_verified": False, "raw_cross_bank_rate_paths_available": False,
        "note": "BoE survey mean opinion probabilities are not currency directional odds; NY Fed results are released after the corresponding FOMC.",
    }


__all__ = ["SCHEMA", "LEADS", "BOE_NOV5_BUCKETS",
           "build_g8_policy_survey_leads_lab"]
