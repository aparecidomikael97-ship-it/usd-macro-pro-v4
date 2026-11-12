"""LAB: do conservative observation-age ceilings outlast scheduled CPI cycles?

Uses only already SHA-pinned, retrospective official-calendar casebooks. A
calendar entry does not prove that a release occurred, that the preceding
observation exists in an authenticated historical vintage, or that any
directional bias is valid. No network, broker, scheduler, trades, or scoring.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import re
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_g8_eight_next_cpi_schedules_lab import (
    inspect_g8_eight_next_cpi_schedules_lab,
)
from atlasquant_trader_g8_macro_asof_lab import OBSERVATION_AGE_LIMIT_DAYS

SCHEMA = "ATLASQUANT_TRADER_G8_CPI_SCHEDULE_OBSERVATION_AGE_AUDIT_LAB_V1"
MONTH = re.compile(r"(20\d\d)-(0[1-9]|1[0-2])\Z")
QUARTER = re.compile(r"(20\d\d)-Q([1-4])\Z")


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "as_of_utc": None, "currency_rows": [], "pair_rows": [],
        "currencies_checked": 0, "pairs_checked": 0,
        "currencies_with_insufficient_ceiling": [], "smallest_margin_days": None,
        "source_calendar_consultation_time_attested": False,
        "historical_preceding_cpi_release_attested": False,
        "future_release_occurrence_attested": False,
        "policy_rate_calendar_validated": False,
        "original_point_in_time_vintages_verified": False,
        "operational_bias": "AGUARDAR", "fx_bias": None,
        "directional_accuracy": None, "trade_authorized": False,
        "can_feed_live_radar": False, "publishable": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "new_cost_brl": 0,
    }


def _previous_period_end(reference: Any, frequency: Any) -> date | None:
    if not isinstance(reference, str):
        return None
    month = MONTH.fullmatch(reference)
    if frequency == "MONTHLY" and month:
        return date(int(month.group(1)), int(month.group(2)), 1) - timedelta(days=1)
    quarter = QUARTER.fullmatch(reference)
    if frequency == "QUARTERLY" and quarter:
        return date(int(quarter.group(1)), 3 * (int(quarter.group(2)) - 1) + 1, 1) - timedelta(days=1)
    return None


def inspect_g8_cpi_schedule_age_audit_lab(
    *, five_calendar_casebook_raw: Any, three_calendar_casebook_raw: Any,
    as_of_utc: Any,
) -> dict[str, Any]:
    """Audit date-only *scheduled* windows, never infer actual releases/bias."""
    out = _base("INVALID_OR_NOT_YET_VISIBLE_CALENDAR_CASEBOOK")
    parent = inspect_g8_eight_next_cpi_schedules_lab(
        five_calendar_casebook_raw=five_calendar_casebook_raw,
        three_calendar_casebook_raw=three_calendar_casebook_raw,
        as_of_utc=as_of_utc,
    )
    if parent["state"] != "LAB_8_CURRENCIES_28_PAIRS_TWO_CALENDAR_DATES_EACH_NO_FX_BIAS":
        return out
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None or len(CURRENCIES) != 8
            or len(OFFICIAL_PAIRS) != 28):
        return out
    rows = []
    for event in parent["visible_official_calendar_events"]:
        currency = event["currency"]
        frequency = event["statistical_frequency"]
        end = _previous_period_end(event["reference_period"], frequency)
        try:
            scheduled = date.fromisoformat(event["scheduled_calendar_date"])
            cap = OBSERVATION_AGE_LIMIT_DAYS[("CPI_YOY", frequency)]
        except (TypeError, ValueError, KeyError, OverflowError):
            return out
        if (end is None or scheduled <= end or type(cap) is not int or cap <= 0):
            return out
        # Date-only projection: previous calendar day, with NO assertion about
        # the precise publishing hour or whether the prior release existed.
        days_before = (scheduled - timedelta(days=1) - end).days
        rows.append({
            "currency": currency, "reference_period_of_next_scheduled_cpi": event["reference_period"],
            "statistical_frequency": frequency,
            "next_scheduled_calendar_date": scheduled.isoformat(),
            "previous_expected_period_end_date": end.isoformat(),
            "previous_period_age_day_before_scheduled_release": days_before,
            "observation_age_ceiling_days": cap,
            "remaining_margin_days": cap - days_before,
            "ceiling_covers_day_before_scheduled_release": days_before <= cap,
            "next_event_is_only_calendar_metadata": True,
            "previous_observation_has_authenticated_actual": False,
        })
    by_currency = {r["currency"]: r for r in rows}
    if len(rows) != 8 or set(by_currency) != set(CURRENCIES):
        return out
    pair_rows = []
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        pair_rows.append({
            "pair": pair, "base": base, "quote": quote,
            "both_ceilings_cover_next_scheduled_cpi": (
                by_currency[base]["ceiling_covers_day_before_scheduled_release"]
                and by_currency[quote]["ceiling_covers_day_before_scheduled_release"]),
            "D1": "AGUARDAR", "W1": "AGUARDAR", "trade_authorized": False,
        })
    insuff = sorted(r["currency"] for r in rows if not r["ceiling_covers_day_before_scheduled_release"])
    out.update({
        "state": ("LAB_CPI_SCHEDULE_AGE_CEILINGS_COVER_ALL_EIGHT_UNATTESTED"
                  if not insuff else "LAB_CPI_SCHEDULE_AGE_CEILING_REVIEW_REQUIRED"),
        "reason": ("DATE_ONLY_CALENDAR_WINDOW_PASS_NOT_ACTUAL_RELEASE"
                   if not insuff else "AGE_CAP_EXPIRES_BEFORE_SCHEDULED_RELEASE"),
        "as_of_utc": as_of_utc.isoformat(), "currency_rows": rows,
        "pair_rows": pair_rows, "currencies_checked": 8,
        "pairs_checked": len(pair_rows), "currencies_with_insufficient_ceiling": insuff,
        "smallest_margin_days": min(r["remaining_margin_days"] for r in rows),
    })
    return out


__all__ = ["SCHEMA", "inspect_g8_cpi_schedule_age_audit_lab"]
