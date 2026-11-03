"""Pre-event laboratory freeze for the Nov 4, 2026 Brazil Copom decision.

A prospective modal ECONOMIST SURVEY scenario is not a FX/Index prediction.
This source record is frozen as Git content before the event; caller clocks
and the local SHA-256 do not constitute an independent timestamp authority.
No network access, event outcome, rate probability, market quotes, money,
Worker, deployment, UI modification, or trading is involved.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from typing import Any, Mapping

from atlasquant_trader_bcb_focus_official_review_lab import (
    PINNED_ANNUAL, PINNED_MONTHLY,
)

SCHEMA = "ATLASQUANT_TRADER_COPOM_20261104_PRE_EVENT_LOCK_LAB_V1"
STATE = "LAB_DOCUMENTARY_PRE_EVENT_FREEZE_NO_TRADE"
DENIED = "LAB_COPOM_PRE_EVENT_CHECKPOINT_REFUSED"
RESEARCH_CUTOFF = datetime(2026, 11, 3, 15, tzinfo=timezone.utc)
FREEZE_DEADLINE = datetime(2026, 11, 4, 0, tzinfo=timezone.utc)
EARLIEST_RELEASE = datetime(2026, 11, 4, 21, 30, tzinfo=timezone.utc)

EXPECTED = {
    "schema": SCHEMA,
    "state": STATE,
    "research_day_utc": "2026-11-03",
    "conservative_research_cutoff_utc": "2026-11-03T15:00:00Z",
    "meeting_dates": ["2026-11-03", "2026-11-04"],
    "official_decision_day": "2026-11-04",
    "scheduled_announcement_not_before_utc": "2026-11-04T21:30:00Z",
    "announcement_time_is_exact": False,
    "source_bcb_calendar": "https://www.bcb.gov.br/detalhenoticia/20739/nota/https%3A/www3.bcb.gov.br/sgspub",
    "source_bcb_normative": "https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Comunicado&numero=43383",
    "source_focus_pdf": "https://www.bcb.gov.br/content/focus/focus/R20261030.pdf",
    "focus_reference_day": "2026-10-30",
    "focus_published_on": "2026-11-03",
    "focus_raw_pdf_archived": False,
    "focus_2026_year_end_selic_pct": "13.50",
    "focus_2026_november_month_end_selic_pct": "13.50",
    "focus_2027_year_end_selic_pct": "12.50",
    "source_reuters_poll": "https://www.reuters.com/world/americas/brazils-post-election-market-shock-clouds-path-cheaper-credit-2026-11-03/",
    "reuters_article_day": "2026-11-03",
    "reuters_poll_hold_responses": 33,
    "reuters_poll_total_respondents": 48,
    "current_selic_pct": "13.75",
    "survey_modal_scenario": "HOLD_13_75",
    "alternative_25bp_cut_scenario": "CUT_25BP_13_50",
    "other_policy_outcomes_supported": True,
    "other_poll_responses_not_assumed_to_all_predict_cut": True,
    "market_implied_probability": None,
    "directional_bias": "AGUARDAR",
    "financial_assets": ["WIN", "WDO"],
    "event_actual_known": False,
    "can_feed_live_radar": False,
    "trade_authorized": False,
    "worker_enabled": False,
    "scheduler_enabled": False,
    "render_configuration_changed": False,
}


def _refuse(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": DENIED, "reason": reason,
        "checkpoint_digest_sha256": None,
        "source_original_pdf_bytes_archived": False,
        "original_pdf_sha256": None,
        "independent_pre_event_publication_receipt_verified": False,
        "github_push_time_independently_verified_by_module": False,
        "post_event_actual_known": False,
        "actual_policy_rate": None,
        "survey_respondent_share_is_probability": False,
        "market_policy_probability": None,
        "market_implied_repricing_verified": False,
        "fx_directional_bias": "AGUARDAR",
        "win_wdo_directional_bias": "AGUARDAR",
        "forecast_hit_rate": None,
        "real_oos_accuracy_proven": False,
        "can_feed_live_radar": False,
        "trade_authorized": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "render_configuration_changed": False,
        "paid_provider_approved": False,
    }


def freeze_pre_copom_snapshot_lab(
    snapshot: Any, *, evaluated_at: datetime,
) -> dict[str, Any]:
    """Review the exact pre-Copom source note with no after-event knowledge.

    Historical credibility depends on retaining this frozen artifact AND
    externally verifying GitHub server-side creation before the event. The
    function itself cannot establish external receipt time, legal suitability
    of news reuse, PDF binary provenance or trading relevance.
    """
    if (not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None
            or evaluated_at.utcoffset() is None):
        raise ValueError("Evaluation clock needs explicit timezone")
    now = evaluated_at.astimezone(timezone.utc)
    if now < RESEARCH_CUTOFF or now >= FREEZE_DEADLINE:
        return _refuse("Cannot newly issue or backdate this pre-event document outside Nov3 research window")
    if not isinstance(snapshot, Mapping) or set(snapshot) != set(EXPECTED):
        return _refuse("Required frozen snapshot fields missing or unreviewed additions")
    for field, canonical in EXPECTED.items():
        current = snapshot[field]
        if type(current) is not type(canonical) or current != canonical:
            return _refuse("Frozen pre-event source contents changed: " + field)

    annual = {(name, year): (old, new) for name, year, old, new, _unit, _n
              in PINNED_ANNUAL}
    monthly = {(name, target): value for name, target, value, _unit
               in PINNED_MONTHLY}
    if (annual.get(("SELIC", "2026")) != ("13.25", snapshot["focus_2026_year_end_selic_pct"])
            or annual.get(("SELIC", "2027")) != ("11.75", snapshot["focus_2027_year_end_selic_pct"])
            or monthly.get(("SELIC", "2026-11")) != snapshot["focus_2026_november_month_end_selic_pct"]):
        return _refuse("Focus evidence no longer matches reviewed official PDF text")

    hold, total = snapshot["reuters_poll_hold_responses"], snapshot["reuters_poll_total_respondents"]
    share = Decimal(hold) / Decimal(total) * Decimal(100)
    if share != Decimal("68.75"):
        return _refuse("Reuters sample respondent percentage invalid")
    locked = json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                        ensure_ascii=False, allow_nan=False)
    digest = sha256(locked.encode("utf-8")).hexdigest()
    return {
        **_refuse(""), "state": STATE, "reason": None,
        "checkpoint_digest_sha256": digest,
        "snapshot_is_exact_pinned_record": True,
        "research_day_utc": snapshot["research_day_utc"],
        "meeting_dates": list(snapshot["meeting_dates"]),
        "official_decision_day": snapshot["official_decision_day"],
        "earliest_scheduled_announcement_utc": EARLIEST_RELEASE.isoformat(),
        "announcement_clock_is_exact": False,
        "monetary_policy_level_before_event_pct": snapshot["current_selic_pct"],
        "focus_year_end_2026_pct": snapshot["focus_2026_year_end_selic_pct"],
        "focus_november_month_end_pct": snapshot["focus_2026_november_month_end_selic_pct"],
        "focus_targets_are_next_meeting_distribution": False,
        "economist_hold_responses": hold,
        "economist_poll_respondents": total,
        "economist_hold_respondent_share_pct": str(share),
        "survey_respondent_share_is_probability": False,
        "modal_respondent_scenario": snapshot["survey_modal_scenario"],
        "alternative_25bp_scenario": snapshot["alternative_25bp_cut_scenario"],
        "other_outcomes_possible": True,
        "non_hold_respondents_all_predicted_25bp_cut": False,
        "conditional_scenarios_not_price_forecasts": [
            {"id":"HOLD_13_75", "rate_pct":"13.75",
             "description":"The observed policy rate, if later verified, equals the economist survey's modal hold expectation"},
            {"id":"CUT_25BP_13_50", "rate_pct":"13.50",
             "description":"A possible quarter-point cut, NOT the asserted view of all remaining respondents"},
            {"id":"OTHER", "rate_pct":None,
             "description":"Any other observed rate, or no independently verified actual"},
        ],
        "instruments_to_research": ["WIN", "WDO"],
        "source_evidence_class": "OFFICIAL_BCB_DOCUMENTARY_TEXT_AND_REUTERS_REPORT_ONLY",
        "post_event_actual_known": False,
        "market_policy_probability": None,
        "why_no_market_bias": (
            "Focus median is a different policy horizon from the next Copom; "
            "33/48 is a respondent share, not market odds; real futures DI, "
            "post-event reaction and causal FX/index direction are unverified."
        ),
        "why_no_independent_time_attestation": (
            "Digest is a local identifier; Git commit and push time, origin PDF "
            "binary and original news publication must be checked externally."
        ),
    }


__all__ = ["SCHEMA", "STATE", "DENIED", "RESEARCH_CUTOFF",
           "FREEZE_DEADLINE", "EARLIEST_RELEASE", "EXPECTED",
           "freeze_pre_copom_snapshot_lab"]
