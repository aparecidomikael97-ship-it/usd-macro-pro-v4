"""LAB documentary macro-calendar exposure, NOT directional prediction.

The three curated official calendar leads are manually transcribed research
references. Their source bytes and custody are NOT attested. A scheduled date
must not be confused with actual/consensus, economic surprise or price response.
No network, trading, scheduler, UI, production or data-provider integration.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from atlasquant_fx_universe import OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_TRADER_MACRO_EVENT_EXPOSURE_LAB_V1"
HORIZONS = ("D1", "W1", "MN1")
WINDOWS = {"D1": timedelta(days=1), "W1": timedelta(days=7),
           "MN1": timedelta(days=30)}
INDICES = ("SPX500", "NAS100", "US30", "WIN", "WDO")
US_INDICES = frozenset(("SPX500", "NAS100", "US30"))
FIELDS = frozenset((
    "event_id", "currency", "event_kind", "time_precision",
    "earliest_at_utc", "latest_at_utc", "source_url",
))
# Two BLS publications are scheduled at 08:30 EST, which is 13:30 UTC in
# November 2026. BoE day-only precision intentionally does not invent an hour.
CALENDAR = (
    {
        "event_id": "BOE_MPC_20261105", "currency": "GBP",
        "event_kind": "CENTRAL_BANK_DECISION",
        "time_precision": "DATE_ONLY",
        "earliest_at_utc": "2026-11-05T00:00:00Z",
        "latest_at_utc": "2026-11-05T23:59:59Z",
        "source_url": "https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates",
    },
    {
        "event_id": "BLS_US_EMPLOYMENT_20261106", "currency": "USD",
        "event_kind": "LABOR_MARKET_RELEASE",
        "time_precision": "SCHEDULED_MINUTE",
        "earliest_at_utc": "2026-11-06T13:30:00Z",
        "latest_at_utc": "2026-11-06T13:30:00Z",
        "source_url": "https://www.bls.gov/schedule/news_release/empsit.htm",
    },
    {
        "event_id": "BLS_US_CPI_20261110", "currency": "USD",
        "event_kind": "INFLATION_RELEASE",
        "time_precision": "SCHEDULED_MINUTE",
        "earliest_at_utc": "2026-11-10T13:30:00Z",
        "latest_at_utc": "2026-11-10T13:30:00Z",
        "source_url": "https://www.bls.gov/schedule/news_release/cpi.htm",
    },
)


def _utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z") or len(value) > 40:
        raise ValueError("Calendar timestamps must be explicit canonical UTC")
    try:
        instant = datetime.fromisoformat(value[:-1] + "+00:00")
    except (ValueError, OverflowError) as exc:
        raise ValueError("Malformed official event instant") from exc
    if instant.utcoffset() != timedelta(0):
        raise ValueError("Event instant not UTC")
    return instant.astimezone(timezone.utc)


def _schedule(schedule: Sequence[Mapping[str, Any]] | None) -> list[dict[str, str]]:
    """Reject caller-supplied fake events, relocated hours, prices or odds.

    Extending this documentary pilot requires reviewing the official source and
    changing the versioned canonical schedule in code, never trusting a caller.
    """
    source = CALENDAR if schedule is None else schedule
    if (not isinstance(source, (tuple, list)) or len(source) != len(CALENDAR)):
        raise ValueError("Complete curated documentary calendar required")
    records: list[dict[str, str]] = []
    for incoming, canonical in zip(source, CALENDAR):
        if (not isinstance(incoming, Mapping)
                or set(incoming) != FIELDS or dict(incoming) != canonical):
            raise ValueError("Unreviewed or forged calendar entry")
        first = _utc(incoming["earliest_at_utc"])
        last = _utc(incoming["latest_at_utc"])
        if last < first:
            raise ValueError("Reversed calendar event window")
        if incoming["time_precision"] == "SCHEDULED_MINUTE" and first != last:
            raise ValueError("Minute-precision event has ambiguous time")
        records.append(dict(incoming))
    return records


def _window_state(first: datetime, last: datetime, now: datetime,
                  deadline: datetime) -> str | None:
    # An exact release at/before the evaluation instant is no longer upcoming.
    if last <= now or first > deadline:
        return None
    # A date-only source may already have been released during its full-day
    # uncertainty interval. Never advertise it as certainly still upcoming.
    if first <= now < last:
        return "DATE_ONLY_MAY_ALREADY_HAVE_OCCURRED"
    if last <= deadline:
        return "SCHEDULED_WITHIN_WINDOW"
    return "WINDOW_EDGE_TIME_UNCERTAIN"


def build_macro_event_exposure_lab(
    *, at: datetime,
    schedule: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Map documentary event *exposure* to 28 FX crosses and five indices.

    D1 is the next 24h, W1 the next 7x24h, MN1 the next 30x24h;
    these are rolling windows, NOT completed chart candles or forecasts.
    """
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("Evaluation time must be timezone aware")
    now = at.astimezone(timezone.utc)
    # This review was made on 2026-11-03; earlier backdated readings cannot
    # pretend the manually transcribed research was already known.
    if now.date().isoformat() < "2026-11-03":
        raise ValueError("Calendar research not available at requested historical date")
    records = _schedule(schedule)
    parsed = [(record, _utc(record["earliest_at_utc"]),
               _utc(record["latest_at_utc"])) for record in records]
    fx_rows: list[dict[str, Any]] = []
    index_rows: list[dict[str, Any]] = []
    for horizon in HORIZONS:
        deadline = now + WINDOWS[horizon]
        active = []
        for record, first, last in parsed:
            state = _window_state(first, last, now, deadline)
            if state is not None:
                active.append((record, state))

        for pair in OFFICIAL_PAIRS:
            base, quote = pair.split("/")
            exposures = [{
                "event_id": record["event_id"],
                "currency": record["currency"],
                "exposure_channel": "DIRECT_PAIR_CURRENCY",
                "timing_state": state,
            } for record, state in active
                if record["currency"] in (base, quote)]
            fx_rows.append({
                "pair": pair, "horizon": horizon,
                "event_exposures": exposures,
                "risk_status": ("CURATED_EVENTS_IN_WINDOW" if exposures
                                else "NO_EVENT_FROM_THIS_PARTIAL_CALENDAR"),
                "bias": "AGUARDAR", "direction_probability": None,
                "trade_authorized": False,
            })

        for instrument in INDICES:
            exposures = [{
                "event_id": record["event_id"],
                "currency": record["currency"],
                "exposure_channel": (
                    "US_DOMESTIC_MACRO_CONTEXT"
                    if instrument in US_INDICES
                    else "INDIRECT_US_CONTEXT_UNVERIFIED"
                ),
                "timing_state": state,
            } for record, state in active if record["currency"] == "USD"]
            index_rows.append({
                "instrument": instrument, "horizon": horizon,
                "event_exposures": exposures,
                "risk_status": ("CURATED_EVENTS_IN_WINDOW" if exposures
                                else "NO_EVENT_FROM_THIS_PARTIAL_CALENDAR"),
                "bias": "AGUARDAR", "direction_probability": None,
                "trade_authorized": False,
            })
    if len(fx_rows) != 84 or len(index_rows) != 15:
        raise RuntimeError("Canonical 28-pair/5-index event matrix violated")
    return {
        "schema": SCHEMA, "state": "LAB_CALENDAR_RISK_EXPOSURE_ONLY",
        "as_of_utc": now.isoformat(),
        "rolling_windows": {h: int(WINDOWS[h].total_seconds()) for h in HORIZONS},
        "events": records, "fx_rows": fx_rows, "index_rows": index_rows,
        "fx_row_count": len(fx_rows), "index_row_count": len(index_rows),
        "curated_event_count": len(records),
        "calendar_complete": False, "calendar_realtime_refreshed": False,
        "source_original_bytes_archived": False,
        "independent_source_receipt_verified": False,
        "consensus_verified": False, "actual_releases_verified": False,
        "market_price_reaction_verified": False, "real_oos_accuracy_proven": False,
        "accuracy_90_proven": False, "market_direction_inferred": False,
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "note": "Mapeia risco de agenda parcial; nao estima direcao, surpresa ou acerto.",
    }


__all__ = [
    "SCHEMA", "HORIZONS", "INDICES", "CALENDAR",
    "build_macro_event_exposure_lab",
]
