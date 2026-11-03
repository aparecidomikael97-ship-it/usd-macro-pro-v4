"""Brazil Focus Oct30 reports and Nov4 Copom meeting-survey separation.

All NOV 3 figures are manually reviewed *secondary-source reports* and NOT
authenticated official BCB raw PDF/OData. Earlier Oct23 values are frozen
in the existing primary-documentary LAB. This module DOES NOT publish a real
pre-event bias, market probabilities, operational WIN/WDO recommendations,
an API subscription, worker or trade. LAB / HARD NO-GO.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Sequence

from atlasquant_trader_brazil_focus_documentary_lab import MEDIANS

SCHEMA = "ATLASQUANT_TRADER_BRAZIL_FOCUS_NEW_SECONDARY_TRIAGE_LAB_V1"
STATE = "LAB_SECONDARY_FOCUS_REVISION_PRE_COPOM_UNATTESTED"
DENIED = "LAB_SECONDARY_FOCUS_REVISION_REFUSED"
RESEARCH_DATE = date(2026, 11, 3)
PRIOR_REFERENCE_DATE = "2026-10-23"
REPORTED_REFERENCE_DATE = "2026-10-30"
SOURCE_REPORTS = (
    "https://safras.com.br/focus-eleva-projecoes-para-inflacao-selic-e-dolar/",
    "https://istoedinheiro.com.br/boletim-focus-selic-dolar-inflacao-pib-3-novembro-2026",
)
REUTERS_POLL_URL = (
    "https://www.reuters.com/world/americas/"
    "brazils-post-election-market-shock-clouds-path-cheaper-credit-2026-11-03/"
)
COPOM_TARGET_DECISION_DATE = "2026-11-04"
# Each reported value is a manually transcribed secondary-source median.
# Foreign-exchange estimates refer to December *average*, NOT current spot.
REPORTED_NEW = (
    ("IPCA", "CALENDAR_YEAR_CHANGE", "2026", "5.22", "PCT"),
    ("IPCA", "CALENDAR_YEAR_CHANGE", "2027", "4.76", "PCT"),
    ("SELIC", "YEAR_END_POLICY_TARGET", "2026", "13.50", "PCT_AA"),
    ("SELIC", "YEAR_END_POLICY_TARGET", "2027", "12.50", "PCT_AA"),
    ("FX_BRL_PER_USD", "DECEMBER_AVERAGE_FX", "2026", "5.34", "BRL_PER_USD"),
    ("FX_BRL_PER_USD", "DECEMBER_AVERAGE_FX", "2027", "5.40", "BRL_PER_USD"),
    ("REAL_GDP", "CALENDAR_YEAR_CHANGE", "2026", "1.76", "PCT"),
    ("REAL_GDP", "CALENDAR_YEAR_CHANGE", "2027", "1.20", "PCT"),
)
# 33 / 48 is the survey RESPONDENT SHARE predicting "hold". It is not
# a probability that the Copom will hold, and not OIS market pricing.
REUTERS_REPORTED_POLL = {
    "source_url": REUTERS_POLL_URL,
    "source_published_on": "2026-11-03",
    "target_meeting": COPOM_TARGET_DECISION_DATE,
    "survey_type": "REUTERS_ECONOMIST_POLL_NEWS_REPORT",
    "current_selic_pct_aa": "13.75",
    "hold_at_current_rate_responses": 33,
    "total_responses": 48,
    "respondents_meeting_expectation": "HOLD_13_75",
}


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": DENIED, "reason": reason,
        "revision_rows": [], "revision_count": 0,
        "focus_new_original_pdf_authenticated": False,
        "focus_new_odataset_original_authenticated": False,
        "new_source_publication_time_independently_attested": False,
        "poll_sample_independently_authenticated": False,
        "next_copom_consensus_percent_from_focus": None,
        "market_implied_copom_probability": None,
        "copom_result_known": False,
        "real_fx_or_index_bias": "AGUARDAR",
        "can_feed_live_radar": False,
        "can_feed_real_oos": False,
        "trade_authorized": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "render_configuration_changed": False,
        "paid_provider_approved": False,
        "probability_calibrated": None,
    }


def triage_reported_focus_revision_lab(
    *, at: datetime,
    new_reports: Sequence[tuple[str, str, str, str, str]] | None = None,
    reuters_poll: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare official PRIOR medians to NEWS-REPORTED new medians, fail-closed.

    The result is documentary research, never a verified BCB vintage or
    real as-of trading evidence. Caller cannot inject quotes, timestamps,
    meeting probabilities or stronger authority through optional arguments.
    """
    if (not isinstance(at, datetime) or at.tzinfo is None
            or at.utcoffset() is None):
        raise ValueError("Timezone-aware research evaluation instant required")
    now = at.astimezone(timezone.utc)
    if now.date() < RESEARCH_DATE:
        return _deny("Cannot backdate November research discovery")
    new = REPORTED_NEW if new_reports is None else new_reports
    if (not isinstance(new, (list, tuple)) or len(new) != len(REPORTED_NEW)
            or tuple(new) != REPORTED_NEW):
        return _deny("New Focus figures must remain fixed as secondary reports")
    poll = REUTERS_REPORTED_POLL if reuters_poll is None else reuters_poll
    if (not isinstance(poll, Mapping) or set(poll) != set(REUTERS_REPORTED_POLL)
            or dict(poll) != REUTERS_REPORTED_POLL):
        return _deny("Meeting poll must not be altered or inflated to probability")
    prior = {(x["indicator"], x["target_type"], x["target_period"]): x
             for x in MEDIANS}
    rows = []
    for indicator, target, period, reported_value, unit in REPORTED_NEW:
        previous = prior.get((indicator, target, period))
        if (previous is None or previous["value_unit"] != unit
                or previous["source_reference"] != PRIOR_REFERENCE_DATE
                or previous["source_published_on"] != "2026-10-26"):
            return _deny("Cannot reconcile news report with previous official Focus")
        old = Decimal(previous["median_value"])
        new_value = Decimal(reported_value)
        delta = new_value - old
        rows.append({
            "indicator": indicator,
            "target_type": target,
            "target_period": period,
            "unit": unit,
            "old_official_reference": PRIOR_REFERENCE_DATE,
            "old_official_value": str(old),
            "new_secondary_report_reference": REPORTED_REFERENCE_DATE,
            "new_secondary_report_value": str(new_value),
            "signed_revision": str(delta),
            "signed_revision_unit": ("PERCENTAGE_POINTS" if unit in ("PCT", "PCT_AA")
                                     else "BRL_PER_USD"),
            "direction_of_revision": ("UP" if delta > 0 else
                                      "DOWN" if delta < 0 else "UNCHANGED"),
            "new_report_is_primary_source_authenticated": False,
            "value_is_actual_economic_release": False,
            "is_next_meeting_consensus": False,
            "is_fx_spot_quote": False,
        })
    if len(rows) != 8:
        return _deny("Expected 8 matched annual medians")
    n = poll["total_responses"]
    hold = poll["hold_at_current_rate_responses"]
    if type(n) is not int or type(hold) is not int or n <= 0 or not 0 <= hold <= n:
        return _deny("Invalid economist poll counts")
    return {
        **_deny(""), "state": STATE, "reason": None,
        "as_researched_on": RESEARCH_DATE.isoformat(),
        "old_focus_reference": PRIOR_REFERENCE_DATE,
        "new_reported_focus_reference": REPORTED_REFERENCE_DATE,
        "new_focus_secondary_source_urls": list(SOURCE_REPORTS),
        "focus_new_original_pdf_sha256": None,
        "revision_rows": rows, "revision_count": len(rows),
        "meeting_survey": {
            "target_meeting": COPOM_TARGET_DECISION_DATE,
            "published_on_date_only": poll["source_published_on"],
            "source_url": poll["source_url"],
            "survey_type": poll["survey_type"],
            "survey_current_selic_pct_aa": poll["current_selic_pct_aa"],
            "hold_responses": hold,
            "all_respondents": n,
            "hold_respondent_share_pct": str(
                (Decimal(hold) * Decimal(100) / Decimal(n)).quantize(Decimal("0.01"))),
            "hold_respondent_share_is_event_probability": False,
            "next_copom_result_verified": False,
            "survey_independently_authenticated": False,
            "market_implied_probability": None,
            "explicit_difference_from_focus": (
                "Reuters poll asks about Nov 4 meeting; Focus 2026 year-end "
                "median targets a different date and instrument interpretation."
            ),
        },
        "meeting_consensus_from_two_distinct_sources_agreed": None,
        "requires_official_focus_pdf_or_odata": True,
        "requires_pre_event_market_forward_prices": True,
        "requires_independent_pre_event_receipt": True,
        "why_no_bias": (
            "Oct30 Focus medians are reported by media, not independently verified "
            "in a primary BCB PDF/OData capture; Reuters economist hold share is "
            "not a next-meeting probability. Neither identifies BRL, WIN or WDO "
            "direction without rates, growth/risk and market positioning."
        ),
    }


__all__ = [
    "SCHEMA", "STATE", "DENIED", "REPORTED_NEW", "REUTERS_REPORTED_POLL",
    "triage_reported_focus_revision_lab",
]
