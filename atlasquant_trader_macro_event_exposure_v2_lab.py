"""V2 official-page research calendar: partial, point-in-time and non-tradable.

This is a NEW calendar vintage, not a retroactive edit to the 03 Nov V1.
Dates were manually checked on official agency pages on 04 Nov 2026. There is
no archived source byte receipt, automatic revalidation or live custody.
Events may be rescheduled. No consensus, actual or directional inference.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_macro_event_exposure_lab import (
    HORIZONS, INDICES, US_INDICES, WINDOWS, _utc, _window_state,
)

SCHEMA = "ATLASQUANT_TRADER_MACRO_EVENT_EXPOSURE_LAB_V2"
REVIEW_DATE = date(2026, 11, 4)
FIELDS = frozenset((
    "event_id", "currency", "event_kind", "time_precision",
    "earliest_at_utc", "latest_at_utc", "source_url",
))

# Official primary pages, recorded as a documentary snapshot and NOT a feed.
# November NZDT = UTC+13; November AEDT = UTC+11; UK = GMT; US = EST.
# Canada's date is kept deliberately DATE_ONLY when a specific publication
# instant was not independently established by this reviewed source.
# Two reports issued on the same day must not be summed as independent votes.
CALENDAR = (
    {
        "event_id": "BOE_MPC_20261105", "currency": "GBP",
        "event_kind": "CENTRAL_BANK_DECISION", "time_precision": "SCHEDULED_MINUTE",
        "earliest_at_utc": "2026-11-05T12:00:00Z",
        "latest_at_utc": "2026-11-05T12:00:00Z",
        "source_url": "https://www.bankofengland.co.uk/events/upcoming-events",
    },
    {
        "event_id": "BLS_US_PRODUCTIVITY_20261105", "currency": "USD",
        "event_kind": "PRODUCTIVITY_RELEASE", "time_precision": "SCHEDULED_MINUTE",
        "earliest_at_utc": "2026-11-05T13:30:00Z",
        "latest_at_utc": "2026-11-05T13:30:00Z",
        "source_url": "https://www.bls.gov/schedule/2026/11_sched_list.htm",
    },
    {
        "event_id": "STATCAN_CA_LFS_20261106", "currency": "CAD",
        "event_kind": "LABOR_MARKET_RELEASE", "time_precision": "DATE_ONLY",
        "earliest_at_utc": "2026-11-06T00:00:00Z",
        "latest_at_utc": "2026-11-06T23:59:59Z",
        "source_url": "https://www150.statcan.gc.ca/n1/daily-quotidien/261009/dq261009a-eng.htm",
    },
    {
        "event_id": "BLS_US_EMPLOYMENT_20261106", "currency": "USD",
        "event_kind": "LABOR_MARKET_RELEASE", "time_precision": "SCHEDULED_MINUTE",
        "earliest_at_utc": "2026-11-06T13:30:00Z",
        "latest_at_utc": "2026-11-06T13:30:00Z",
        "source_url": "https://www.bls.gov/schedule/2026/11_sched_list.htm",
    },
    {
        "event_id": "BLS_US_CPI_20261110", "currency": "USD",
        "event_kind": "INFLATION_RELEASE", "time_precision": "SCHEDULED_MINUTE",
        "earliest_at_utc": "2026-11-10T13:30:00Z",
        "latest_at_utc": "2026-11-10T13:30:00Z",
        "source_url": "https://www.bls.gov/schedule/news_release/cpi.htm",
    },
    {
        "event_id": "ONS_UK_GDP_20261112", "currency": "GBP",
        "event_kind": "ACTIVITY_RELEASE", "time_precision": "SCHEDULED_MINUTE",
        "earliest_at_utc": "2026-11-12T07:00:00Z",
        "latest_at_utc": "2026-11-12T07:00:00Z",
        "source_url": "https://www.ons.gov.uk/releases/gdpmonthlyestimateukseptember2026",
    },
    {
        "event_id": "BLS_US_PPI_20261113", "currency": "USD",
        "event_kind": "INFLATION_RELEASE", "time_precision": "SCHEDULED_MINUTE",
        "earliest_at_utc": "2026-11-13T13:30:00Z",
        "latest_at_utc": "2026-11-13T13:30:00Z",
        "source_url": "https://www.bls.gov/schedule/news_release/ppi.htm",
    },
    {
        "event_id": "RBNZ_NZ_FSR_20261117", "currency": "NZD",
        "event_kind": "FINANCIAL_STABILITY_REPORT_NOT_POLICY_DECISION",
        "time_precision": "SCHEDULED_MINUTE",
        "earliest_at_utc": "2026-11-16T20:00:00Z",
        "latest_at_utc": "2026-11-16T20:00:00Z",
        "source_url": "https://www.rbnz.govt.nz/news-and-events/news/2026/10/updates-to-the-october-mpr-and-november-fsr",
    },
    {
        "event_id": "ONS_UK_LABOR_20261117", "currency": "GBP",
        "event_kind": "LABOR_MARKET_RELEASE", "time_precision": "SCHEDULED_MINUTE",
        "earliest_at_utc": "2026-11-17T07:00:00Z",
        "latest_at_utc": "2026-11-17T07:00:00Z",
        "source_url": "https://www.ons.gov.uk/releasecalendar?highlight=true&keywords=labour%20market&limit=10&page=1&release-type=type-upcoming&sort=date-newest",
    },
    {
        "event_id": "ABS_AU_LABOR_20261119", "currency": "AUD",
        "event_kind": "LABOR_MARKET_RELEASE", "time_precision": "SCHEDULED_MINUTE",
        "earliest_at_utc": "2026-11-19T00:30:00Z",
        "latest_at_utc": "2026-11-19T00:30:00Z",
        "source_url": "https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia",
    },
)


def _validate(schedule: Sequence[Mapping[str, Any]] | None) -> list[dict[str, str]]:
    source = CALENDAR if schedule is None else schedule
    if (not isinstance(source, (list, tuple)) or len(source) != len(CALENDAR)):
        raise ValueError("Full reviewed V2 documentary calendar required")
    checked = []
    for item, canonical in zip(source, CALENDAR):
        if (not isinstance(item, Mapping) or set(item) != FIELDS
                or dict(item) != canonical):
            raise ValueError("Unreviewed/altered canonical calendar entry")
        first, last = _utc(item["earliest_at_utc"]), _utc(item["latest_at_utc"])
        if (last < first or (item["time_precision"] == "SCHEDULED_MINUTE"
                            and first != last)):
            raise ValueError("Invalid release window")
        checked.append(dict(item))
    if len({x["event_id"] for x in checked}) != len(checked):
        raise ValueError("Duplicate reviewed event id")
    return checked


def build_macro_event_exposure_v2_lab(
    *, at: datetime, schedule: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Reproduce V2 documentary exposures, never real bias or executable risk."""
    if (not isinstance(at, datetime) or at.tzinfo is None
            or at.utcoffset() is None):
        raise ValueError("Evaluation needs timezone-aware clock")
    now = at.astimezone(timezone.utc)
    if now.date() < REVIEW_DATE:
        raise ValueError("V2 observations must not be projected into prior days")
    events = _validate(schedule)
    parsed = [(item, _utc(item["earliest_at_utc"]),
               _utc(item["latest_at_utc"])) for item in events]
    fx_rows: list[dict[str, Any]] = []
    index_rows: list[dict[str, Any]] = []
    for horizon in HORIZONS:
        end = now + WINDOWS[horizon]
        active = [(item, status) for item, first, last in parsed
                  if (status := _window_state(first, last, now, end)) is not None]
        for pair in OFFICIAL_PAIRS:
            base, quote = pair.split("/")
            exposure = [{"event_id": item["event_id"],
                         "currency": item["currency"],
                         "exposure_channel": "DIRECT_PAIR_CURRENCY",
                         "timing_state": status}
                        for item, status in active if item["currency"] in (base, quote)]
            fx_rows.append({
                "pair": pair, "horizon": horizon,
                "event_exposures": exposure,
                "risk_status": ("CURATED_EVENTS_IN_WINDOW" if exposure else
                                "NO_EVENT_FROM_THIS_PARTIAL_CALENDAR"),
                "bias": "AGUARDAR", "direction_probability": None,
                "trade_authorized": False,
            })
        for instrument in INDICES:
            exposure = [{"event_id": item["event_id"],
                         "currency": item["currency"],
                         "exposure_channel": ("US_DOMESTIC_MACRO_CONTEXT"
                                              if instrument in US_INDICES
                                              else "INDIRECT_US_CONTEXT_UNVERIFIED"),
                         "timing_state": status}
                        for item, status in active if item["currency"] == "USD"]
            index_rows.append({
                "instrument": instrument, "horizon": horizon,
                "event_exposures": exposure,
                "risk_status": ("CURATED_EVENTS_IN_WINDOW" if exposure else
                                "NO_EVENT_FROM_THIS_PARTIAL_CALENDAR"),
                "bias": "AGUARDAR", "direction_probability": None,
                "trade_authorized": False,
            })
    if len(fx_rows) != 84 or len(index_rows) != 15:
        raise RuntimeError("Canonical instrument matrix drifted")
    return {
        "schema": SCHEMA, "state": "LAB_CALENDAR_RISK_EXPOSURE_ONLY",
        "calendar_review_date_utc": REVIEW_DATE.isoformat(),
        "calendar_version": "V2_OFFICIAL_PAGE_REVIEW",
        "as_of_utc": now.isoformat(),
        "rolling_windows": {h: int(WINDOWS[h].total_seconds()) for h in HORIZONS},
        "events": events, "fx_rows": fx_rows, "index_rows": index_rows,
        "fx_row_count": len(fx_rows), "index_row_count": len(index_rows),
        "curated_event_count": len(events),
        "calendar_complete": False, "calendar_realtime_refreshed": False,
        "source_original_bytes_archived": False,
        "independent_source_receipt_verified": False,
        "consensus_verified": False, "actual_releases_verified": False,
        "market_price_reaction_verified": False,
        "real_oos_accuracy_proven": False, "accuracy_90_proven": False,
        "market_direction_inferred": False,
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "note": ("Revisao documental parcial de fontes oficiais; mudancas de data "
                 "ainda possiveis. Nenhuma fonte/cotacao live ou direcao validada."),
    }


__all__ = ["SCHEMA", "REVIEW_DATE", "CALENDAR",
           "build_macro_event_exposure_v2_lab"]
