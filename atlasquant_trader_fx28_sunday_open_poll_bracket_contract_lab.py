"""FX28 Sunday availability: two local MT5 poll cohorts, NOT broker-open time.

Designed for a separately authorized study after the frozen Nov-Dec 2026
campaign. The caller supplies observations; NO MT5, network, file writes,
scheduling, authentication, first-seen proof, trading or forecasting.

A candle opens at one UTC timestamp, closes 15 minutes later, and may be
returned by a local terminal at a different time. Two polling snapshots
are not proof that the broker market opened at either time. Distinguish
an earlier poll before candle closure from an already-closed candle that
was not returned by an earlier local query.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_sunday_open_research_protocol_lab import (
    FIRST_SEPARATE_SUNDAY, CAMPAIGN_END, MAX_HOURS,
)

SCHEMA = "ATLASQUANT_FX28_SUNDAY_OPEN_TWO_POLL_BRACKET_CLAIM_LAB_V1"
EXPECTED_TERMINAL = r"C:\Program Files\Pepperstone MetaTrader 5\terminal64.exe"
SOURCE = "LOCAL_PEPPERSTONE_MT5_HISTORY_UNATTESTED"
EMPTY = "EMPTY_ARRAY"
BAR = "CLOSED_M15_BAR_RETURNED"
ERROR = "MT5_RETURNED_NONE"
UTC = timezone.utc
NY = ZoneInfo("America/New_York")
BAR_TIME = timedelta(minutes=15)
MAX_QUERY_TIME = timedelta(seconds=20)
MAX_BATCH_SPAN = timedelta(minutes=10)
MAX_POLL_GAP = timedelta(minutes=30)


@dataclass(frozen=True)
class LocalM15PollClaim:
    """One *untrusted declaration*, not MT5 data or a verified source receipt."""
    pair: str
    started_at_utc: datetime
    finished_at_utc: datetime
    api_result_kind: str
    first_closed_bar_open_utc: datetime | None
    requested_history_start_at_utc: datetime
    requested_history_end_at_utc: datetime
    timeframe_claim: str
    mt5_terminal_path_claim: str = EXPECTED_TERMINAL
    source_kind_claim: str = SOURCE
    terminal_connected_claim: bool = True
    market_watch_visible_claim: bool = True


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(UTC)
    except (TypeError, ValueError, OverflowError):
        return None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_SUNDAY_OPEN_TWO_POLL_BLOCKED_NO_GO",
        "reason": reason,
        "frozen_campaign_end_utc": CAMPAIGN_END.isoformat(),
        "first_research_sunday_utc": FIRST_SEPARATE_SUNDAY.isoformat(),
        "pairs_expected": 28,
        "before_cohort_count": 0,
        "after_cohort_count": 0,
        "claimed_first_closed_candle_appeared_between_polls": 0,
        "claimed_not_returned_after_prior_close": 0,
        "previous_poll_before_candle_close": 0,
        "still_empty_in_both_polls": 0,
        "rows": [],
        "documentary_only": True,
        "mt5_terminal_path_not_broker_identity_proof": True,
        "first_seen_time_independently_attested": False,
        "broker_session_open_time_authenticated": False,
        "actual_market_open_inferred": False,
        "price_origin_independently_authenticated": False,
        "first_bar_20261115_backfilled": False,
        "original_672_slots_modified": False,
        "scheduler_enabled": False,
        "can_run_market_probe": False,
        "out_of_sample_accuracy": None,
        "calibrated_direction_probability": None,
        "trade_authorized": False,
        "publishable": False,
        "operational_bias": "AGUARDAR",
        "mt5_calls": 0,
        "http_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
    }


def _valid_cohort(
    rows: Any, *, nominal: datetime, inspected: datetime,
) -> tuple[dict[str, tuple[LocalM15PollClaim, datetime, datetime, datetime | None]],
           datetime, datetime] | None:
    if not isinstance(rows, (tuple, list)) or len(rows) != 28:
        return None
    known = set(OFFICIAL_PAIRS)
    if len(known) != 28:
        return None
    result: dict[str, tuple[LocalM15PollClaim, datetime, datetime, datetime | None]] = {}
    started: list[datetime] = []
    finished: list[datetime] = []
    for item in rows:
        if not isinstance(item, LocalM15PollClaim) or item.pair not in known or item.pair in result:
            return None
        begin = _utc(item.started_at_utc)
        end = _utc(item.finished_at_utc)
        opening = (_utc(item.first_closed_bar_open_utc)
                   if item.first_closed_bar_open_utc is not None else None)
        requested_start = _utc(item.requested_history_start_at_utc)
        requested_end = _utc(item.requested_history_end_at_utc)
        if (begin is None or end is None
                or item.timeframe_claim != "M15"
                or requested_start != nominal
                or requested_end != nominal + timedelta(hours=MAX_HOURS)
                or begin < nominal + BAR_TIME
                or not begin <= end <= inspected
                or end > nominal + timedelta(hours=MAX_HOURS) + BAR_TIME
                or end - begin > MAX_QUERY_TIME
                or item.mt5_terminal_path_claim != EXPECTED_TERMINAL
                or item.source_kind_claim != SOURCE
                or item.terminal_connected_claim is not True
                or item.market_watch_visible_claim is not True
                or item.api_result_kind not in (BAR, EMPTY)
                or (item.api_result_kind == EMPTY and item.first_closed_bar_open_utc is not None)
                or (item.api_result_kind == BAR and opening is None)):
            return None
        if opening is not None:
            if (not nominal <= opening < nominal + timedelta(hours=MAX_HOURS)
                    or opening.second or opening.minute % 15
                    or opening + BAR_TIME > end):
                return None
        result[item.pair] = (item, begin, end, opening)
        started.append(begin)
        finished.append(end)
    if (set(result) != known
            or max(finished) - min(started) > MAX_BATCH_SPAN):
        return None
    return result, min(started), max(finished)


def inspect_fx28_sunday_open_two_poll_bracket_lab(
    *, research_sunday_start_utc: Any,
    prior_cohort: Any, later_cohort: Any, inspected_at_utc: Any,
) -> dict[str, Any]:
    """Strict 28+28 caller-claims, no ability to prove true broker availability.

    Both cohorts MUST claim the SAME frozen 5h nominal-origin M15 query
    bounds. No local hash authenticates the actual API arguments. The preceding
    EMPTY call is meaningful only if its completed timestamp is after the
    first later-observed candle had already closed. Otherwise this is
    normal candle maturation rather than evidence of source latency.
    """
    out = _blocked("INVALID_RESEARCH_WINDOW_OR_INSPECTION_CLOCK")
    nominal = _utc(research_sunday_start_utc)
    now = _utc(inspected_at_utc)
    if (nominal is None or now is None or nominal < FIRST_SEPARATE_SUNDAY
            or nominal <= CAMPAIGN_END
            or nominal.astimezone(NY).weekday() != 6
            or nominal.astimezone(NY).hour != 17
            or nominal.astimezone(NY).minute
            or nominal.minute % 15 or nominal.second
            or now < nominal + BAR_TIME):
        return out
    first = _valid_cohort(prior_cohort, nominal=nominal, inspected=now)
    later = _valid_cohort(later_cohort, nominal=nominal, inspected=now)
    if first is None or later is None:
        out["reason"] = "INVALID_28_PAIR_POLL_COHORT_OR_MT5_RETURNED_NONE"
        return out
    previous, _, prev_end = first
    following, later_start, later_end = later
    if not prev_end < later_start or later_end - prev_end > MAX_POLL_GAP:
        out["reason"] = "POLL_COHORT_ORDER_GAP_TOO_LARGE_OR_OVERLAPPED"
        return out

    appeared = delayed_after_close = closed_in_gap = still_empty = 0
    rows = []
    for pair in OFFICIAL_PAIRS:
        earlier, _, prior_end, prior_open = previous[pair]
        observed, _, observed_end, later_open = following[pair]
        if earlier.api_result_kind == BAR:
            if observed.api_result_kind != BAR or later_open != prior_open:
                out["reason"] = "EARLIER_CLOSED_BAR_DISAPPEARED_OR_CHANGED"
                return out
            state = "SAME_FIRST_CLOSED_M15_IN_BOTH_POLLS_CLAIM_ONLY"
        elif observed.api_result_kind == EMPTY:
            state = "STILL_NO_CLOSED_M15_IN_BOTH_POLLS_CLAIM_ONLY"
            still_empty += 1
        else:
            if later_open is None:
                out["reason"] = "MISSING_LATER_FIRST_CLOSED_BAR_TIMESTAMP"
                return out
            appeared += 1
            if prior_end >= later_open + BAR_TIME:
                state = "CLOSED_M15_WAS_NOT_RETURNED_IN_EARLIER_LOCAL_POLL_CLAIM_ONLY"
                delayed_after_close += 1
            else:
                state = "M15_CLOSED_BETWEEN_POLLS_NO_SOURCE_LATENCY_INFERRED"
                closed_in_gap += 1
        rows.append({
            "pair": pair,
            "poll_comparison_class": state,
            "prior_poll_finished_at_utc_claim": prior_end.isoformat(),
            "later_poll_finished_at_utc_claim": observed_end.isoformat(),
            "first_closed_bar_open_at_utc_claim":
                later_open.isoformat() if later_open is not None else None,
            "broker_first_open_authenticated": False,
            "local_first_seen_time_authenticated": False,
        })
    out.update({
        "state": "LAB_FX28_SUNDAY_OPEN_28_PAIR_TWO_POLL_DOCUMENTARY_ONLY_NO_GO",
        "reason": "TWO_UNATTESTED_LOCAL_POLL_COHORTS_NOT_BROKER_SESSION_PROOF",
        "before_cohort_count": 28,
        "after_cohort_count": 28,
        "claimed_first_closed_candle_appeared_between_polls": appeared,
        "claimed_not_returned_after_prior_close": delayed_after_close,
        "previous_poll_before_candle_close": closed_in_gap,
        "still_empty_in_both_polls": still_empty,
        "rows": rows,
    })
    return out


__all__ = (
    "SCHEMA", "EXPECTED_TERMINAL", "SOURCE", "EMPTY", "BAR", "ERROR",
    "LocalM15PollClaim", "inspect_fx28_sunday_open_two_poll_bracket_lab",
)
