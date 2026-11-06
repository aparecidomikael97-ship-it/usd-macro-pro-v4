"""Compare two supplied ONS CPI JSON vintages without claiming historical proof.

This is a research-only revision detector. The ONS calendar ``date`` field
does not establish the publication instant or the historical availability of
the supplied bytes. Neither output is eligible for FX decisions or backtests.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from atlasquant_trader_ons_gbp_cpi_current_lab import (
    parse_current_ons_gbp_d7g7_lab,
)

SCHEMA = "ATLASQUANT_TRADER_ONS_GBP_VINTAGE_DIFF_LAB_V1"
PARSED_STATE = "LAB_CURRENT_GBP_ONS_D7G7_QUARANTINED"


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_BLOCKED",
        "reason": reason,
        "currency": "GBP",
        "source_series": "ONS_D7G7_MM23",
        "earlier_claimed_release_date": None,
        "later_claimed_release_date": None,
        "earlier_raw_sha256": None,
        "later_raw_sha256": None,
        "as_of_utc": None,
        "captured_at_local_system_utc": None,
        "earlier_cutoff_status": None,
        "later_cutoff_status": None,
        "later_release_after_asof_calendar": None,
        "same_day_release_instant_unknown": None,
        "comparison_window": "LAST_15_MONTHLY_ROWS_PER_PROVIDED_SNAPSHOT",
        "revised_months": [],
        "newly_observed_months": [],
        "no_longer_observed_in_window": [],
        "unchanged_common_month_count": 0,
        "source_origin_independently_verified": False,
        "historical_vintage_archive_verified": False,
        "publication_instant_verified": False,
        "point_in_time_available_verified": False,
        "usable_in_historical_backtest": False,
        "methodologically_comparable_to_other_cpi": False,
        "fx_bias": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "can_feed_live_radar": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "publishable": False,
        "external_http_requests": 0,
        "new_cost_brl": 0,
    }


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None):
        return None
    return value.astimezone(timezone.utc)


def _date_status(reported_day: date, cutoff_day: date) -> str:
    if reported_day > cutoff_day:
        return "CALENDAR_RELEASE_AFTER_CUTOFF_BLOCKED"
    if reported_day == cutoff_day:
        return "SAME_CALENDAR_DAY_PUBLICATION_INSTANT_UNKNOWN_BLOCKED"
    return "CALENDAR_EARLIER_BUT_HISTORICAL_AVAILABILITY_UNATTESTED"


def compare_ons_gbp_d7g7_vintages_lab(
    *, earlier_vintage_raw: Any, later_vintage_raw: Any,
    captured_at_utc: Any, historical_cutoff_utc: Any,
) -> dict[str, Any]:
    """Diff two untrusted provided byte snapshots; no real archive verification."""
    out = _base("INVALID_INPUT_OR_CLOCK")
    captured = _utc(captured_at_utc)
    cutoff = _utc(historical_cutoff_utc)
    if (captured is None or cutoff is None or cutoff > captured
            or not isinstance(earlier_vintage_raw, bytes)
            or not isinstance(later_vintage_raw, bytes)):
        return out

    before = parse_current_ons_gbp_d7g7_lab(
        earlier_vintage_raw, observed_at_utc=captured,
    )
    after = parse_current_ons_gbp_d7g7_lab(
        later_vintage_raw, observed_at_utc=captured,
    )
    if before["state"] != PARSED_STATE or after["state"] != PARSED_STATE:
        out["reason"] = "EARLIER_OR_LATER_SNAPSHOT_INVALID"
        return out

    earlier_day = date.fromisoformat(before["release_date_calendar_only"])
    later_day = date.fromisoformat(after["release_date_calendar_only"])
    if earlier_day >= later_day:
        out["reason"] = "REPORTED_VINTAGE_DATES_NOT_STRICTLY_ORDERED"
        return out

    first = {row["period"]: row["annual_cpi_percent_claim"]
             for row in before["monthly_observations"]}
    second = {row["period"]: row["annual_cpi_percent_claim"]
              for row in after["monthly_observations"]}
    revisions = []
    unchanged = 0
    for period in sorted(first.keys() & second.keys()):
        old, new = first[period], second[period]
        # Numerical equivalence: "3.10" and "3.1" are not revisions.
        if (old is None and new is None) or (old is not None and new is not None
                                             and Decimal(old) == Decimal(new)):
            unchanged += 1
        else:
            revisions.append({"period": period, "earlier_annual_cpi_percent_claim": old,
                              "later_annual_cpi_percent_claim": new})

    earlier_status = _date_status(earlier_day, cutoff.date())
    later_status = _date_status(later_day, cutoff.date())
    out.update({
        "state": "LAB_UNATTESTED_VINTAGE_DIFFERENCES_QUARANTINED",
        "reason": "SUPPLIED_VINTAGES_AND_RELEASE_INSTANTS_NOT_INDEPENDENTLY_AUTHENTICATED",
        "earlier_claimed_release_date": earlier_day.isoformat(),
        "later_claimed_release_date": later_day.isoformat(),
        "earlier_raw_sha256": before["source_bytes_sha256"],
        "later_raw_sha256": after["source_bytes_sha256"],
        "as_of_utc": cutoff.isoformat(),
        "captured_at_local_system_utc": captured.isoformat(),
        "earlier_cutoff_status": earlier_status,
        "later_cutoff_status": later_status,
        "later_release_after_asof_calendar": later_day > cutoff.date(),
        "same_day_release_instant_unknown": (earlier_day == cutoff.date()
                                             or later_day == cutoff.date()),
        "revised_months": revisions,
        # A disappearing row can simply be outside the 15-month window.
        "newly_observed_months": sorted(second.keys() - first.keys()),
        "no_longer_observed_in_window": sorted(first.keys() - second.keys()),
        "unchanged_common_month_count": unchanged,
    })
    return out


__all__ = ["SCHEMA", "compare_ons_gbp_d7g7_vintages_lab"]
