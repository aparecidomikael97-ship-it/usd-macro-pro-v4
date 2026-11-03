"""LAB: fixed official prior publications before three coming macro events.

Manually transcribed values, NOT an independently attested source archive or
live feed. Distinguishes previous published facts from pre-event consensus,
eventual actual release, macro surprise, and tradable directional bias.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_macro_event_exposure_lab import CALENDAR

SCHEMA = "ATLASQUANT_TRADER_PRE_EVENT_FUNDAMENTALS_LAB_V1"
RESEARCH_ON = date(2026, 11, 3)
FIELDS = frozenset((
    "event_id", "currency", "indicator_id", "measure", "value", "unit",
    "reference_period", "source_published_on", "source_url",
))
PRIOR_PUBLICATIONS = (
    {
        "event_id": "BOE_MPC_20261105", "currency": "GBP",
        "indicator_id": "POLICY_RATE", "measure": "BANK_RATE_DECISION_LEVEL",
        "value": "3.75", "unit": "PERCENT", "reference_period": "2026-09",
        "source_published_on": "2026-09-17",
        "source_url": "https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes/2026/september-2026",
    },
    {
        "event_id": "BLS_US_EMPLOYMENT_20261106", "currency": "USD",
        "indicator_id": "NFP", "measure": "PAYROLL_MONTHLY_CHANGE",
        "value": "29", "unit": "THOUSANDS", "reference_period": "2026-09",
        "source_published_on": "2026-10-02",
        "source_url": "https://www.bls.gov/news.release/archives/empsit_10022026.htm",
    },
    {
        "event_id": "BLS_US_EMPLOYMENT_20261106", "currency": "USD",
        "indicator_id": "UNEMPLOYMENT", "measure": "U3_UNEMPLOYMENT_RATE",
        "value": "4.2", "unit": "PERCENT", "reference_period": "2026-09",
        "source_published_on": "2026-10-02",
        "source_url": "https://www.bls.gov/news.release/archives/empsit_10022026.htm",
    },
    {
        "event_id": "BLS_US_CPI_20261110", "currency": "USD",
        "indicator_id": "CPI", "measure": "HEADLINE_CPI_SA_MOM",
        "value": "0.6", "unit": "PERCENT", "reference_period": "2026-09",
        "source_published_on": "2026-10-14",
        "source_url": "https://www.bls.gov/news.release/archives/cpi_10142026.htm",
    },
    {
        "event_id": "BLS_US_CPI_20261110", "currency": "USD",
        "indicator_id": "CPI", "measure": "HEADLINE_CPI_NSA_YOY",
        "value": "3.7", "unit": "PERCENT", "reference_period": "2026-09",
        "source_published_on": "2026-10-14",
        "source_url": "https://www.bls.gov/news.release/archives/cpi_10142026.htm",
    },
    {
        "event_id": "BLS_US_CPI_20261110", "currency": "USD",
        "indicator_id": "CORE_CPI", "measure": "CORE_CPI_SA_MOM",
        "value": "0.3", "unit": "PERCENT", "reference_period": "2026-09",
        "source_published_on": "2026-10-14",
        "source_url": "https://www.bls.gov/news.release/archives/cpi_10142026.htm",
    },
)


def _date(s: Any) -> date:
    if not isinstance(s, str) or len(s) != 10:
        raise ValueError("Documentary calendar date needs YYYY-MM-DD")
    try:
        result = date.fromisoformat(s)
    except ValueError as exc:
        raise ValueError("Invalid calendar date") from exc
    if result.isoformat() != s:
        raise ValueError("Noncanonical documentary date")
    return result


def _input_rows(incoming: Sequence[Mapping[str, Any]] | None) -> list[dict[str, str]]:
    rows = PRIOR_PUBLICATIONS if incoming is None else incoming
    if not isinstance(rows, (list, tuple)) or len(rows) != len(PRIOR_PUBLICATIONS):
        raise ValueError("Six complete documented historical readings required")
    normalized = []
    for item, expected in zip(rows, PRIOR_PUBLICATIONS):
        if (not isinstance(item, Mapping) or set(item) != FIELDS
                or dict(item) != expected):
            raise ValueError("Historical observation altered or falsely supplemented")
        try:
            amount = Decimal(item["value"])
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Invalid documentary measurement") from exc
        if not amount.is_finite() or abs(amount) > 100000:
            raise ValueError("Nonfinite or unbounded historical measurement")
        published = _date(item["source_published_on"])
        if published > RESEARCH_ON:
            raise ValueError("Source could not be known before research date")
        normalized.append(dict(item))
    if {x["event_id"] for x in normalized} != {x["event_id"] for x in CALENDAR}:
        raise ValueError("Historical records not linked to curated calendar events")
    return normalized


def build_pre_event_fundamentals_lab(
    *, at: datetime, observations: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Connect genuine previous release facts to macro events, never outcomes."""
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("Evaluation time must contain explicit timezone")
    now = at.astimezone(timezone.utc)
    if now.date() < RESEARCH_ON:
        raise ValueError("Cannot backdate this non-attested November research snapshot")
    rows = _input_rows(observations)
    events = []
    for calendar_row in CALENDAR:
        first = datetime.fromisoformat(calendar_row["earliest_at_utc"].replace("Z", "+00:00"))
        last = datetime.fromisoformat(calendar_row["latest_at_utc"].replace("Z", "+00:00"))
        if now < first:
            state = "PRIOR_CONTEXT_FOR_FUTURE_EVENT"
        elif now <= last:
            state = "DATE_ONLY_OR_RELEASE_TIME_IN_PROGRESS_REFRESH_REQUIRED"
        else:
            state = "EVENT_TIME_PASSED_NEW_RELEASE_REQUIRED"
        prior = [dict(item) for item in rows if item["event_id"] == calendar_row["event_id"]]
        if not prior or any(_date(item["source_published_on"]) >= first.date()
                            for item in prior):
            raise RuntimeError("Prior data must have existed before the target event")
        events.append({
            "event_id": calendar_row["event_id"], "currency": calendar_row["currency"],
            "event_state": state, "prior_observations": prior,
            "prior_count": len(prior),
            "current_event_actual_available": False,
            "current_event_consensus_available": False,
            "surprise_available": False,
            "fx_direction": "AGUARDAR",
        })
    by_currency = {
        currency: [dict(item) for item in rows if item["currency"] == currency]
        for currency in CURRENCIES
    }
    comparisons = []
    for pair in OFFICIAL_PAIRS:
        base, quote = pair.split("/")
        comparisons.append({
            "pair": pair,
            "base_prior_series_count": len(by_currency[base]),
            "quote_prior_series_count": len(by_currency[quote]),
            "comparison_state": "HETEROGENEOUS_SERIES_NO_COMPARABLE_DIFFERENTIAL",
            "bias": "AGUARDAR", "direction_probability": None,
            "trade_authorized": False,
        })
    return {
        "schema": SCHEMA, "state": "LAB_OFFICIAL_PRIOR_FACTS_UNATTESTED",
        "as_of_utc": now.isoformat(), "research_recorded_on": RESEARCH_ON.isoformat(),
        "events": events, "currency_evidence": by_currency,
        "pair_comparisons": comparisons, "historical_measure_count": len(rows),
        "currency_count": len(CURRENCIES), "pair_count": len(comparisons),
        "prior_publications_official_urls_cited": True,
        "original_source_bytes_archived": False,
        "source_capture_independently_attested": False,
        "source_live_refreshed": False, "full_g8_macro_coverage": False,
        "upcoming_consensus_verified": False, "upcoming_actual_verified": False,
        "economic_surprise_calculated": False,
        "relative_currency_strength_inferred": False,
        "real_oos_accuracy_proven": False, "accuracy_90_proven": False,
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "why_not": "Previous observations, unlike expectations and upcoming actuals, do not yield macro surprise or FX direction.",
    }


__all__ = ["SCHEMA", "PRIOR_PUBLICATIONS", "build_pre_event_fundamentals_lab"]
