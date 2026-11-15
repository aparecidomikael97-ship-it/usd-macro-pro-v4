"""Offline normalizer for caller-supplied MT5 structured bars/ticks, FX28.

MetaTrader5 Python normally returns NumPy structured arrays: M15 bars have
a named 'time' field in epoch seconds; ticks have 'time' in seconds and
'time_msc' in milliseconds. Multiple different ticks can share the SAME
time_msc, as shown in the official MetaQuotes example. Equal time_msc is
valid, decreasing time_msc is NOT.

A complete raw 5h+15m tick array may be large; sample deterministically
the FIRST supplied tick in each of at most 21 M15 buckets. This is NOT
proof that the API supplied all available ticks, that a first quote was
captured, or that sparse samples disprove a time-axis error.

This function NEVER imports/calls MetaTrader5 or numpy, never accesses
network/files/accounts, never writes prices. All inputs are caller-supplied
untrusted rows; only time/time_msc fields are read. No timezone adjustment,
no server-time conversion, no retiming of the frozen Nov-Dec campaign.
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
from atlasquant_trader_fx28_sunday_tick_m15_utc_pair_guard_lab import (
    LocalTickM15PairClaim, LocalTickTimeClaim,
    inspect_fx28_sunday_tick_m15_utc_pair_lab,
    PRESENT, EMPTY, TICKS_PRESENT, TICKS_EMPTY, TERMINAL,
    M15_SECONDS, MAX_TICKS_PER_PAIR,
)

SCHEMA = "ATLASQUANT_FX28_SUNDAY_MT5_RAW_TIME_ADAPTER_LAB_V1"
UTC = timezone.utc
NY = ZoneInfo("America/New_York")
MAX_RAW_TICK_ROWS = 120_000
MAX_RAW_M15_ROWS = MAX_HOURS * 4
TICK_SCOPE = "COPY_TICKS_ALL"
BAR_SCOPE = "TIMEFRAME_M15"
HISTORY_SECONDS = MAX_HOURS * 3600
TICK_WINDOW_SECONDS = HISTORY_SECONDS + M15_SECONDS
OK_GUARD = "LAB_FX28_SUNDAY_TICK_M15_UTC_CLOCK_CLAIMS_ONLY_NO_GO"


@dataclass(frozen=True)
class SuppliedMT5RawPairRows:
    """No API calls: user-provided numpy-like arrays or lists of dict records."""
    pair: str
    m15_rows: Any
    tick_rows: Any
    m15_request_start_utc: datetime
    m15_request_end_inclusive_utc: datetime
    tick_request_start_utc: datetime
    tick_request_end_exclusive_utc: datetime
    m15_timeframe_claim: str = BAR_SCOPE
    tick_flags_claim: str = TICK_SCOPE
    terminal_path_claim: str = TERMINAL


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(UTC)
    except (ValueError, TypeError, OverflowError):
        return None


def _length_and_rows(value: Any, maximum: int) -> tuple[int, Any] | None:
    if value is None:
        return None  # Real MT5 None means API error, never an empty response.
    if type(value) in (tuple, list):
        rows = value
    else:
        # MT5 returns numpy structured arrays with named fields.
        names = getattr(getattr(value, "dtype", None), "names", None)
        if (not isinstance(names, tuple) or "time" not in names
                or not callable(getattr(value, "__iter__", None))):
            return None
        rows = value
    try:
        count = len(rows)
    except (TypeError, ValueError, OverflowError):
        return None
    if type(count) is not int or not 0 <= count <= maximum:
        return None
    return count, rows


def _field_integer(row: Any, key: str) -> int | None:
    try:
        if type(row) is dict:
            raw = row[key]
        else:
            names = getattr(getattr(row, "dtype", None), "names", None)
            if not isinstance(names, tuple) or key not in names:
                return None
            raw = row[key]
        if type(raw) is not int:
            # NumPy scalar .item() converts np.int64/np.uint64 to Python int.
            raw = raw.item()
        return raw if type(raw) is int else None  # reject float, bool, str
    except (AttributeError, ValueError, KeyError, TypeError, OverflowError):
        return None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_SUNDAY_RAW_MT5_TIME_NORMALIZATION_BLOCKED_NO_GO",
        "reason": reason,
        "normalized_pair_count": 0,
        "m15_rows_structurally_read": 0,
        "tick_rows_structurally_read": 0,
        "m15_bucket_samples_retained": 0,
        "raw_m15_empty_pairs": 0,
        "raw_tick_empty_pairs": 0,
        "guard_state": None,
        "guard_classification_summary": {},
        "normalized_pair_claims": (),
        "raw_prices_never_inspected_or_returned": True,
        "raw_api_outputs_supplied_by_caller_not_authenticated": True,
        "first_tick_per_quarterhour_bucket_not_full_tick_coverage": True,
        "identical_time_msc_can_be_valid": True,
        "broker_source_authenticated": False,
        "observed_at_point_in_time_authenticated": False,
        "actual_market_open_authenticated": False,
        "server_clock_offset_applied": False,
        "historical_20261115_campaign_replayed": False,
        "frozen_campaign_672_slots_modified": False,
        "validated_accuracy": None,
        "publishable": False,
        "trade_authorized": False,
        "scheduler_enabled": False,
        "operational_bias": "AGUARDAR",
        "mt5_calls": 0, "http_requests": 0, "file_writes": 0,
        "new_cost_brl": 0,
    }


def inspect_supplied_fx28_sunday_mt5_raw_time_lab(
    *, separate_sunday_start_utc: Any, inspected_at_utc: Any,
    pair_raw_rows: Any,
) -> dict[str, Any]:
    """Validate supplied arrays; pass bounded time-only claims to prior guard."""
    result = _base("INVALID_TIME_OR_RESEARCH_WINDOW")
    start = _utc(separate_sunday_start_utc)
    now = _utc(inspected_at_utc)
    if (start is None or now is None or start < FIRST_SEPARATE_SUNDAY
            or start <= CAMPAIGN_END
            or (start.astimezone(NY).weekday(),
                start.astimezone(NY).hour,
                start.astimezone(NY).minute,
                start.astimezone(NY).second) != (6, 17, 0, 0)
            or not start+timedelta(hours=5, minutes=15) <= now
            <= start+timedelta(hours=6)):
        return result
    if type(pair_raw_rows) not in (list, tuple) or len(pair_raw_rows) != 28:
        result["reason"] = "INCOMPLETE_28_PAIR_RAW_ROSTER"
        return result
    first = int(start.timestamp())
    tick_end = first + TICK_WINDOW_SECONDS
    seen: set[str] = set()
    claims: list[LocalTickM15PairClaim] = []
    n_bars = n_ticks = n_sample = empty_bars = empty_ticks = 0
    for row in pair_raw_rows:
        if (not isinstance(row, SuppliedMT5RawPairRows)
                or row.pair not in OFFICIAL_PAIRS or row.pair in seen
                or row.terminal_path_claim != TERMINAL
                or row.m15_timeframe_claim != BAR_SCOPE
                or row.tick_flags_claim != TICK_SCOPE
                or _utc(row.m15_request_start_utc) != start
                or _utc(row.m15_request_end_inclusive_utc)
                   != start+timedelta(hours=5,minutes=-15)
                or _utc(row.tick_request_start_utc) != start
                or _utc(row.tick_request_end_exclusive_utc)
                   != start+timedelta(hours=5,minutes=15)):
            result["reason"] = "RAW_PAIR_OR_QUERY_TIMEFRAME_CLOCK_DRIFT"
            return result
        seen.add(row.pair)
        barset = _length_and_rows(row.m15_rows,MAX_RAW_M15_ROWS)
        tickset = _length_and_rows(row.tick_rows,MAX_RAW_TICK_ROWS)
        if barset is None or tickset is None:
            result["reason"] = "MT5_RETURNED_NONE_MALFORMED_OR_OVERSIZED_RAW_ROWS"
            return result

        bar_count, bars = barset
        prev_open: int | None = None
        first_open: int | None = None
        read_bar_count=0
        try:
            for bar in bars:
                opening = _field_integer(bar,"time")
                if (opening is None or not first <= opening < first+HISTORY_SECONDS
                        or (opening-first)%M15_SECONDS
                        or (prev_open is not None and opening <= prev_open)):
                    result["reason"] = "M15_RAW_TIME_NOT_STRICTLY_ASCENDING_ON_UTC_GRID"
                    return result
                if first_open is None:
                    first_open = opening
                prev_open=opening
                read_bar_count += 1
        except (TypeError, ValueError, KeyError, AttributeError, OverflowError):
            result["reason"] = "MALFORMED_RAW_M15_RECORD_ITERATION"
            return result
        if read_bar_count != bar_count:
            result["reason"]="RAW_M15_ROW_COUNT_CHANGED_DURING_ITERATION"
            return result

        tick_count, ticks = tickset
        prev_msc: int | None = None
        earliest_bucket: dict[int, LocalTickTimeClaim] = {}
        read_tick_count=0
        try:
            for tick in ticks:
                seconds = _field_integer(tick,"time")
                msc = _field_integer(tick,"time_msc")
                if (seconds is None or msc is None
                        or not first <= seconds < tick_end
                        or msc // 1000 != seconds
                        or (prev_msc is not None and msc < prev_msc)):
                    result["reason"] = "RAW_TICK_SECONDS_MSC_OR_SORTING_INVALID"
                    return result
                prev_msc=msc
                bucket=(seconds-first)//M15_SECONDS
                if bucket not in earliest_bucket:
                    earliest_bucket[bucket]=LocalTickTimeClaim(
                        time_seconds_utc_epoch=seconds,
                        time_msc_utc_epoch=msc)
                read_tick_count+=1
        except (TypeError, ValueError, KeyError, AttributeError, OverflowError):
            result["reason"] = "MALFORMED_RAW_TICK_RECORD_ITERATION"
            return result
        if read_tick_count != tick_count:
            result["reason"]="RAW_TICK_ROW_COUNT_CHANGED_DURING_ITERATION"
            return result
        ordered=tuple(earliest_bucket[key] for key in sorted(earliest_bucket))
        if len(ordered)>MAX_TICKS_PER_PAIR:
            result["reason"]="M15_BUCKET_SAMPLE_EXCEEDS_GUARD_LIMIT"
            return result
        claims.append(LocalTickM15PairClaim(
            pair=row.pair,
            m15_result_kind=PRESENT if bar_count else EMPTY,
            first_m15_open_seconds_utc_epoch=first_open,
            tick_result_kind=TICKS_PRESENT if tick_count else TICKS_EMPTY,
            tick_samples=ordered,
        ))
        n_bars+=bar_count
        n_ticks+=tick_count
        n_sample+=len(ordered)
        empty_bars+=int(bar_count==0)
        empty_ticks+=int(tick_count==0)
    if seen != set(OFFICIAL_PAIRS) or len(claims)!=28:
        result["reason"]="RAW_FX28_ROSTER_CHANGED"
        return result

    check=inspect_fx28_sunday_tick_m15_utc_pair_lab(
        separate_sunday_start_utc=start,
        inspected_at_utc=now,
        pair_claims=tuple(claims))
    if (check.get("state") !=
            "LAB_FX28_SUNDAY_TICK_M15_UTC_CLOCK_CLAIMS_ONLY_NO_GO"
            or check.get("roster_pairs_verified_claim_only")!=28
            or check.get("mt5_calls")!=0
            or check.get("trade_authorized") is not False):
        result["reason"]="PRIOR_TICK_M15_GUARD_BLOCKED"
        return result
    result.update({
        "state":"LAB_FX28_SUNDAY_RAW_MT5_TIME_ONLY_CLAIMS_NORMALIZED_NO_GO",
        "reason":"SUPPLIED_ROWS_STRUCTURAL_ONLY_NOT_LIVE_BROKER_OR_FIRST_TICK_PROOF",
        "normalized_pair_count":28,
        "m15_rows_structurally_read":n_bars,
        "tick_rows_structurally_read":n_ticks,
        "m15_bucket_samples_retained":n_sample,
        "raw_m15_empty_pairs":empty_bars,
        "raw_tick_empty_pairs":empty_ticks,
        "guard_state":check["state"],
        "guard_classification_summary":{
            "same_utc_m15_bucket_tick_claim_only":
                check["pairs_with_same_m15_bucket_tick"],
            "possible_2h_3h_offset_unproven":
                check["pairs_with_possible_2h_3h_shift_but_no_same_bucket_tick"],
            "insufficient_overlap_claim_only":
                check["pairs_with_insufficient_overlap_sample"],
            "no_m15_for_comparison_claim_only":
                check["pairs_with_no_m15_to_compare"],
        },
        "normalized_pair_claims":tuple(claims),
    })
    return result


__all__=(
    "SCHEMA","SuppliedMT5RawPairRows",
    "inspect_supplied_fx28_sunday_mt5_raw_time_lab",
)
