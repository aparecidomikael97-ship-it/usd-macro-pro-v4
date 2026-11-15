"""Pure tick-versus-M15 UTC clock-axis comparison for a FUTURE separate study.

MetaTrader5 tick records have second-resolution 'time' and millisecond
'time_msc' fields; M15 bar records have opening 'time' in seconds. Treat
these numeric values as EPOCH claims only. No conversion from Pepperstone
GMT+2/+3 server display time is performed or permitted.

A matching timestamp does NOT prove the broker's timezone, first traded
tick, identity, availability at the time of polling or price accuracy.
A +/- 2/3 hour candidate with no same-bar sampled tick is ONLY a
possible axis inconsistency (could be sparse/bad sampling). Do not
reinterpret either dataset until independently checked.

No MT5 connection, network, file I/O, order, scheduler, new data or
2026-11-15 first-M15 replay. Does not change the frozen 672 slots.
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

SCHEMA = "ATLASQUANT_FX28_SUNDAY_TICK_M15_UTC_PAIR_GUARD_LAB_V1"
UTC = timezone.utc
NY = ZoneInfo("America/New_York")
M15_SECONDS = 900
MAX_TICKS_PER_PAIR = 16
MINUTES_5H = MAX_HOURS * 3600
SERVER_OFFSET_HOURS = (2, 3)
PRESENT = "BARS_PRESENT"
EMPTY = "EMPTY_ARRAY"
ERROR = "MT5_RETURNED_NONE"
TICKS_PRESENT = "SAMPLED_TICKS_PRESENT"
TICKS_EMPTY = "EMPTY_TICK_SAMPLE"
TERMINAL = r"C:\Program Files\Pepperstone MetaTrader 5\terminal64.exe"


@dataclass(frozen=True)
class LocalTickTimeClaim:
    time_seconds_utc_epoch: int
    time_msc_utc_epoch: int


@dataclass(frozen=True)
class LocalTickM15PairClaim:
    pair: str
    m15_result_kind: str
    first_m15_open_seconds_utc_epoch: int | None
    tick_result_kind: str
    tick_samples: tuple[LocalTickTimeClaim, ...]
    mt5_terminal_path_claim: str = TERMINAL
    tick_source_claim: str = "LOCAL_MT5_COPY_TICKS_RANGE_UNATTESTED"
    m15_source_claim: str = "LOCAL_MT5_COPY_RATES_RANGE_UNATTESTED"
    timeframe_claim: str = "M15"


def _utc_clock(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(UTC)
    except (TypeError, ValueError, OverflowError):
        return None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_SUNDAY_TICK_M15_UTC_PAIR_BLOCKED_NO_GO",
        "reason": reason,
        "roster_pairs_expected": 28,
        "roster_pairs_verified_claim_only": 0,
        "nominal_sunday_utc": None,
        "historical_window_minutes": 300,
        "pairs_with_m15": 0,
        "pairs_with_empty_m15": 0,
        "pairs_with_tick_samples": 0,
        "pairs_with_same_m15_bucket_tick": 0,
        "pairs_with_possible_2h_3h_shift_but_no_same_bucket_tick": 0,
        "pairs_with_insufficient_overlap_sample": 0,
        "pairs_with_no_m15_to_compare": 0,
        "comparison_rows": [],
        "utc_epoch_contract_checked_structurally": False,
        "mt5_local_tick_and_bar_records_are_not_independent": True,
        "sparse_tick_sample_does_not_prove_absence": True,
        "time_msc_does_not_independently_attest_timestamp": True,
        "broker_server_offset_not_applied_to_data": True,
        "pepperstone_broker_source_authenticated": False,
        "first_tick_at_actual_market_open_authenticated": False,
        "broker_open_time_authenticated": False,
        "historical_20261115_start_bar_reconstructed": False,
        "frozen_campaign_672_slots_modified": False,
        "clock_rewrite_allowed": False,
        "publishable": False,
        "trade_authorized": False,
        "scheduler_enabled": False,
        "validated_accuracy": None,
        "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR",
        "mt5_calls": 0, "http_requests": 0,
        "file_writes": 0, "new_cost_brl": 0,
    }


def _is_int(value: Any) -> bool:
    return type(value) is int


def inspect_fx28_sunday_tick_m15_utc_pair_lab(
    *, separate_sunday_start_utc: Any, inspected_at_utc: Any,
    pair_claims: Any,
) -> dict[str, Any]:
    """Validate 28 supplied pairs; distinguish corroboration from false proof."""
    out = _base("INVALID_SEPARATE_SUNDAY_OR_INSPECTION_CLOCK")
    nominal = _utc_clock(separate_sunday_start_utc)
    observed = _utc_clock(inspected_at_utc)
    if (nominal is None or observed is None
            or nominal < FIRST_SEPARATE_SUNDAY or nominal <= CAMPAIGN_END
            or (nominal.astimezone(NY).weekday(),
                nominal.astimezone(NY).hour,
                nominal.astimezone(NY).minute,
                nominal.astimezone(NY).second) != (6, 17, 0, 0)
            or not nominal <= observed
            or observed < nominal + timedelta(hours=MAX_HOURS, minutes=15)
            or observed > nominal + timedelta(hours=6)):
        return out
    if not isinstance(pair_claims, (tuple, list)) or len(pair_claims) != 28:
        out["reason"] = "INCOMPLETE_28_PAIR_COHORT"
        return out
    first = int(nominal.timestamp())
    last_open_exclusive = first + MINUTES_5H
    last_tick_exclusive_ms = (last_open_exclusive + M15_SECONDS) * 1000
    official = set(OFFICIAL_PAIRS)
    validated: dict[str, tuple[int | None, tuple[int, ...]]] = {}
    for record in pair_claims:
        if (not isinstance(record, LocalTickM15PairClaim)
                or record.pair not in official or record.pair in validated
                or record.mt5_terminal_path_claim != TERMINAL
                or record.timeframe_claim != "M15"
                or record.tick_source_claim != "LOCAL_MT5_COPY_TICKS_RANGE_UNATTESTED"
                or record.m15_source_claim != "LOCAL_MT5_COPY_RATES_RANGE_UNATTESTED"
                or record.m15_result_kind not in (PRESENT, EMPTY)
                or record.tick_result_kind not in (TICKS_PRESENT, TICKS_EMPTY)
                or type(record.tick_samples) is not tuple
                or len(record.tick_samples) > MAX_TICKS_PER_PAIR
                or ((record.tick_result_kind == TICKS_PRESENT)
                    != (len(record.tick_samples) > 0))
                or ((record.m15_result_kind == PRESENT)
                    != (record.first_m15_open_seconds_utc_epoch is not None))):
            out["reason"] = "INVALID_PAIR_SOURCE_OR_NONE_MISCLASSIFIED_AS_EMPTY"
            return out
        op = record.first_m15_open_seconds_utc_epoch
        if op is not None and (not _is_int(op)
            or not first <= op < last_open_exclusive
            or (op - first) % M15_SECONDS != 0):
            out["reason"] = "BAD_M15_OPEN_UTC_EPOCH_GRID"
            return out
        ticks: list[int] = []
        for tick in record.tick_samples:
            if not isinstance(tick, LocalTickTimeClaim):
                out["reason"] = "INVALID_TICK_RECORD"
                return out
            tsec, tms = tick.time_seconds_utc_epoch, tick.time_msc_utc_epoch
            if (not _is_int(tsec) or not _is_int(tms)
                    or not first <= tsec < last_open_exclusive + M15_SECONDS
                    or tms // 1000 != tsec
                    or not first * 1000 <= tms < last_tick_exclusive_ms
                    or (ticks and tms <= ticks[-1])):
                out["reason"] = "TICK_TIME_SECONDS_MILLISECONDS_OR_ORDER_CONFLICT"
                return out
            ticks.append(tms)
        validated[record.pair] = op, tuple(ticks)
    if set(validated) != official:
        out["reason"] = "FX28_ROSTER_MISSING_DUPLICATE_OR_CHANGED"
        return out

    same = shifted = insufficient = no_bar = 0
    count_bars = count_ticks = 0
    rows: list[dict[str, Any]] = []
    for pair in OFFICIAL_PAIRS:
        op, ticks = validated[pair]
        count_bars += int(op is not None)
        count_ticks += int(bool(ticks))
        label: str
        proposed_offsets: list[int] = []
        if op is None:
            label = "NO_M15_BAR_TO_COMPARE_CLAIM_ONLY"
            no_bar += 1
        elif not ticks:
            label = "NO_TICK_SAMPLE_TO_CORROBORATE_M15_CLAIM_ONLY"
            insufficient += 1
        else:
            # Any tick inside the unshifted bar is a LOCAL cross-check
            # within ONE API family, not independent broker confirmation.
            own = any(op * 1000 <= t < (op + M15_SECONDS)*1000 for t in ticks)
            # +/- 2/3 hour markers only; NEVER transform or return new OHLC.
            for hours in SERVER_OFFSET_HOURS:
                for sign in (-1, 1):
                    alternative = op + sign * hours * 3600
                    if any(alternative*1000 <= t <
                           (alternative+M15_SECONDS)*1000 for t in ticks):
                        proposed_offsets.append(sign*hours)
            if own:
                label = "SAME_UTC_M15_BUCKET_TICK_SAMPLED_CLAIM_ONLY"
                same += 1
            elif proposed_offsets:
                label = "POSSIBLE_UTC_SERVER_TIME_AXIS_MISMATCH_UNPROVEN"
                shifted += 1
            else:
                label = "SPARSE_OR_DISJOINT_TICK_SAMPLE_INSUFFICIENT"
                insufficient += 1
        rows.append({
            "pair": pair,
            "m15_open_epoch_claim": op,
            "sampled_tick_count": len(ticks),
            "classification": label,
            "candidate_offset_hours_no_timestamp_rewrite":
                sorted(set(proposed_offsets)),
            "is_broker_identity_proof": False,
            "is_first_trade_attestation": False,
        })
    if len(rows) != 28 or same + shifted + insufficient + no_bar != 28:
        out["reason"] = "INTERNAL_FX28_COUNT_DISAGREEMENT"
        return out
    out.update({
        "state": "LAB_FX28_SUNDAY_TICK_M15_UTC_CLOCK_CLAIMS_ONLY_NO_GO",
        "reason": "LOCAL_TICK_AND_BAR_EPOCHS_STRUCTURALLY_COMPARED_NOT_BROKER_ATTESTED",
        "roster_pairs_verified_claim_only": 28,
        "nominal_sunday_utc": nominal.isoformat(),
        "pairs_with_m15": count_bars,
        "pairs_with_empty_m15": 28-count_bars,
        "pairs_with_tick_samples": count_ticks,
        "pairs_with_same_m15_bucket_tick": same,
        "pairs_with_possible_2h_3h_shift_but_no_same_bucket_tick": shifted,
        "pairs_with_insufficient_overlap_sample": insufficient,
        "pairs_with_no_m15_to_compare": no_bar,
        "comparison_rows": rows,
        "utc_epoch_contract_checked_structurally": True,
    })
    return out


__all__ = (
    "SCHEMA", "LocalTickTimeClaim", "LocalTickM15PairClaim",
    "PRESENT", "EMPTY", "ERROR", "TICKS_PRESENT", "TICKS_EMPTY",
    "inspect_fx28_sunday_tick_m15_utc_pair_lab",
)
