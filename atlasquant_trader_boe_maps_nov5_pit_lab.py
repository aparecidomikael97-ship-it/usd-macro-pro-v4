"""BoE November 2026 decision vs two MaPS *public result vintages*.

This strictly fixed documentary case prevents an Oct survey answer, published
on Nov 6, from masquerading as public Nov 5 expectations. All source pages
were read retrospectively; historic receipt timestamps are NOT authenticated.
The old Sep survey is 48 days old, not a live pre-meeting consensus quote.
Never calculate policy surprise, GBP bias or predictive accuracy from it.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_BOE_MAPS_NOV5_PUBLIC_VINTAGE_PIT_LAB_V1"
KIND = "RETROSPECTIVE_DOCUMENTARY_TRANSCRIPTION_UNATTESTED"
MAX_BYTES = 6500
FRESHNESS_RESEARCH_DAYS = 30  # illustrative LAB policy, not calibrated

DECISION = {
    "meeting_date": "2026-11-05",
    "published_date": "2026-11-05",
    "earliest_conservative_after_publication_utc": "2026-11-06T00:00:00Z",
    "actual_bank_rate_percent": "4.00",
    "prior_bank_rate_percent": "3.75",
    "source_url": "https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes/2026/november-2026",
    "source_raw_bytes_archived": False,
}
SURVEYS = [
    {
        "survey_id": "MAPS_SEPTEMBER_2026_PUBLIC_RESULTS",
        "responses_closed_date": "2026-09-04",
        "results_published_date": "2026-09-18",
        "earliest_conservative_after_publication_utc": "2026-09-19T00:00:00Z",
        "target_meeting_date": "2026-11-05",
        "median_modal_post_meeting_bank_rate_percent": "3.75",
        "modal_question_respondents": 92,
        "mean_subjective_probability_4pct_percent": "35.0",
        "probability_question_respondents": 90,
        "source_url": "https://www.bankofengland.co.uk/markets/market-intelligence/survey-results/2026/market-participants-survey-results-september-2026",
        "source_raw_bytes_archived": False,
    },
    {
        "survey_id": "MAPS_NOVEMBER_2026_PUBLIC_RESULTS",
        "responses_closed_date": "2026-10-23",
        "results_published_date": "2026-11-06",
        "earliest_conservative_after_publication_utc": "2026-11-07T00:00:00Z",
        "target_meeting_date": "2026-11-05",
        "median_modal_post_meeting_bank_rate_percent": "4.00",
        "modal_question_respondents": 80,
        "mean_subjective_probability_4pct_percent": "86.0",
        "probability_question_respondents": 78,
        "source_url": "https://www.bankofengland.co.uk/markets/market-intelligence/survey-results/2026/market-participants-survey-results-november-2026",
        "source_raw_bytes_archived": False,
    },
]
EXPECTED = {
    "schema": SCHEMA, "data_kind": KIND, "retrospective_research_date": "2026-11-06",
    "decision": DECISION, "public_survey_results": SURVEYS,
}


def _unique(items: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in items:
        if key in out:
            raise ValueError("DUPLICATE_JSON_FIELD")
        out[key] = val
    return out


def _asof(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _utc(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "casebook_sha256": None, "decision_visible_after_document_date_only": False,
        "survey_ids_chronologically_visible_at_asof": [],
        "sep_survey_public_before_decision_by_document_date": False,
        "nov_survey_public_before_decision_by_document_date": False,
        "pre_event_historical_survey_context_id": None,
        "pre_event_historical_median_percent_claim": None,
        "pre_event_historical_survey_age_days": None,
        "pre_event_historical_survey_research_fresh": False,
        "old_survey_vs_actual_arithmetic_gap_bps_not_surprise": None,
        "post_event_november_median_percent_documentary": None,
        "post_event_november_result_must_not_be_backfilled": True,
        "source_publication_instant_independently_verified": False,
        "source_original_bytes_independently_authenticated": False,
        "historical_survey_capture_independently_verified": False,
        "pre_event_contemporaneous_market_consensus_verified": False,
        "policy_surprise_verified": False,
        "market_implied_probabilities_verified": False,
        "survey_subjective_probabilities_are_fx_probabilities": False,
        "point_in_time_eligible_for_backtest": False,
        "validated_prediction_count": 0, "validated_accuracy": None,
        "market_surprise_bps": None, "gbp_bias": None, "fx_bias": None,
        "operational_bias": "AGUARDAR", "can_feed_live_radar": False,
        "trade_authorized": False, "publishable": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "new_cost_brl": 0,
    }


def inspect_boe_maps_nov5_public_vintages_lab(
    casebook_raw: Any, *, as_of_utc: Any,
) -> dict[str, Any]:
    """Return *document chronology* only, with all trading gates closed.

    Survey response collection before a decision does NOT imply survey results
    were public by that decision. Later November survey can only be used as a
    retrospective description of the respondent sample, never as the known
    ex-ante median in a prospective audit or backtest.
    """
    out = _blocked("INVALID_CASEBOOK_OR_ASOF")
    now = _asof(as_of_utc)
    if (now is None or not isinstance(casebook_raw, bytes)
            or not 400 <= len(casebook_raw) <= MAX_BYTES):
        return out
    try:
        parsed = json.loads(
            casebook_raw.decode("utf-8", "strict"), object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE")),
        )
    except (ValueError, TypeError, UnicodeDecodeError, RecursionError):
        out["reason"] = "MALFORMED_JSON_OR_DUPLICATE_FIELDS"
        return out
    if parsed != EXPECTED:
        out["reason"] = "DOCUMENTARY_SNAPSHOT_VALUES_OR_DATES_CHANGED"
        return out
    decision_day = date.fromisoformat(DECISION["meeting_date"])
    sep, nov = SURVEYS
    sep_age = (decision_day - date.fromisoformat(sep["results_published_date"])).days
    eligible_old = date.fromisoformat(sep["results_published_date"]) < decision_day
    eligible_new = date.fromisoformat(nov["results_published_date"]) < decision_day
    seen = [r["survey_id"] for r in SURVEYS
            if now >= _utc(r["earliest_conservative_after_publication_utc"])]
    decision_seen = now >= _utc(DECISION["earliest_conservative_after_publication_utc"])
    # A level-gap to a 48-day-old modal median is at most an arithmetic
    # historical contrast; it is NEVER a contemporaneous monetary surprise.
    old_gap = (str((Decimal(DECISION["actual_bank_rate_percent"])
                    - Decimal(sep["median_modal_post_meeting_bank_rate_percent"])) * 100)
               if decision_seen and eligible_old and sep["survey_id"] in seen else None)
    out.update({
        "state": "LAB_BOE_MAPS_PUBLICATION_CHRONOLOGY_ONLY",
        "reason": "NOVEMBER_SURVEY_RESULTS_PUBLISHED_AFTER_DECISION_AND_OLD_SURVEY_STALE",
        "casebook_sha256": sha256(casebook_raw).hexdigest(),
        "decision_visible_after_document_date_only": decision_seen,
        "survey_ids_chronologically_visible_at_asof": seen,
        "sep_survey_public_before_decision_by_document_date": eligible_old,
        "nov_survey_public_before_decision_by_document_date": eligible_new,
        "pre_event_historical_survey_context_id": sep["survey_id"] if sep["survey_id"] in seen and eligible_old else None,
        "pre_event_historical_median_percent_claim": (
            sep["median_modal_post_meeting_bank_rate_percent"]
            if sep["survey_id"] in seen and eligible_old else None),
        "pre_event_historical_survey_age_days": sep_age,
        "pre_event_historical_survey_research_fresh": sep_age <= FRESHNESS_RESEARCH_DAYS,
        "old_survey_vs_actual_arithmetic_gap_bps_not_surprise": old_gap,
        "post_event_november_median_percent_documentary": (
            nov["median_modal_post_meeting_bank_rate_percent"] if nov["survey_id"] in seen else None),
    })
    return out


__all__ = ["SCHEMA", "KIND", "DECISION", "SURVEYS", "EXPECTED",
           "FRESHNESS_RESEARCH_DAYS", "inspect_boe_maps_nov5_public_vintages_lab"]
