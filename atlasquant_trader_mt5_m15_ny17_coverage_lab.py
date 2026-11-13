"""Offline M15 timestamp coverage candidate for FX NY17 D1/W1 windows.

This accepts caller-supplied M15 candle-open epochs. It does NOT read the AM12
archive, verify a source hash, establish that broker sessions were continuous,
or calculate price direction. Missing even one expected candle blocks; a gap
may be a legitimate session/holiday condition requiring separate evidence.
Native AM12 D1 bars are on a UTC-midnight grid, whereas archived nominal W1
bars have seven-day widths: neither directly proves a 17:00 NY FX bias label.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx_ny_rollover_lab import (
    CONVENTION, inspect_fx_ny_close_window_lab,
)

SCHEMA = "ATLASQUANT_TRADER_MT5_M15_NY17_COVERAGE_LAB_V1"
FRAME_SECONDS = 15 * 60
MAX_CANDLES = 500
HEX = re.compile(r"[0-9a-f]{64}\Z")
VALID_NY17 = "LAB_FX_NY_ROLLOVER_WINDOW_STRUCTURALLY_VALID"


def _utc(x: Any) -> datetime | None:
    if (not isinstance(x, datetime) or x.tzinfo is None
            or x.utcoffset() is None):
        return None
    return x.astimezone(timezone.utc)


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_M15_NY17_COVERAGE_BLOCKED",
        "reason": reason,
        "pair": None, "horizon": None,
        "start_utc": None, "end_utc": None,
        "m15_expected_candle_count": None,
        "m15_received_candle_count": None,
        "first_mismatch_index": None,
        "first_expected_m15_open_present": None,
        "last_expected_m15_open_present": None,
        "first_observed_m15_open_utc": None,
        "last_observed_m15_open_utc": None,
        "first_observed_delay_minutes": None,
        "last_observed_early_minutes": None,
        "missing_expected_m15_slots": None,
        "missing_at_start_consecutive_m15_slots": None,
        "missing_at_end_consecutive_m15_slots": None,
        "missing_interior_m15_slots": None,
        "missing_m15_classification": None,
        "m15_boundary_input_integrity_valid": False,
        "archive_capture_utc_claim": None,
        "source_sha256_claim": None,
        "market_calendar_convention": CONVENTION,
        "contiguous_ny17_m15_timestamps_claim_only": False,
        "native_d1_utc_grid_is_ny17_equivalent": False,
        "native_w1_seven_day_bar_is_ny17_equivalent": False,
        "archive_original_bytes_supplied": False,
        "source_hash_independently_checked": False,
        "broker_m15_clock_independently_verified": False,
        "broker_session_calendar_independently_verified": False,
        "holiday_rollover_pauses_verified": False,
        "source_ohlc_independently_verified": False,
        "prediction_precommit_independently_verified": False,
        "historical_point_in_time_verified": False,
        "observed_direction": None,
        "validated_directional_accuracy": None,
        "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR",
        "publishable": False, "can_feed_live_radar": False,
        "trade_authorized": False, "live_alert_allowed": False,
        "scheduler_enabled": False, "worker_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_m15_ny17_coverage_lab(
    *, pair: Any, horizon: Any, start_at_utc: Any, end_at_utc: Any,
    m15_candle_open_epochs: Any, archive_captured_at_utc: Any,
    evaluated_at_utc: Any, source_sha256_claim: Any,
) -> dict[str, Any]:
    """Check exact contiguous M15 timestamp coverage; never score a bias.

    If even one timestamp is missing or non-canonical, reject the entire
    candidate rather than excluding difficult periods from the denominator.
    Clock, SHA and epoch values are caller claims, never broker attestation.
    """
    out = _base("INVALID_PAIR_HORIZON_OR_CLOCK")
    start, end, captured, evaluated = (
        _utc(v) for v in (start_at_utc, end_at_utc, archive_captured_at_utc,
                          evaluated_at_utc)
    )
    if (not isinstance(pair, str) or pair not in OFFICIAL_PAIRS
            or not isinstance(horizon, str) or horizon not in ("D1", "W1")
            or any(t is None for t in (start, end, captured, evaluated))
            or not start < end <= captured <= evaluated):
        return out
    out.update(pair=pair, horizon=horizon,
               start_utc=start.isoformat(), end_utc=end.isoformat())
    calendar = inspect_fx_ny_close_window_lab(
        horizon=horizon, start_at_utc=start, end_at_utc=end)
    if calendar["state"] != VALID_NY17:
        out["reason"] = "NONCANONICAL_FX_NY17_" + calendar["reason"]
        return out

    if (not isinstance(source_sha256_claim, str)
            or HEX.fullmatch(source_sha256_claim) is None):
        out["reason"] = "INVALID_UNATTESTED_SOURCE_HASH_CLAIM"
        return out
    out["source_sha256_claim"] = source_sha256_claim

    duration_seconds = int((end - start).total_seconds())
    if duration_seconds % FRAME_SECONDS:
        out["reason"] = "NY17_WINDOW_NOT_ON_M15_GRID"
        return out
    expected_count = duration_seconds // FRAME_SECONDS
    out["m15_expected_candle_count"] = expected_count
    if (not 1 <= expected_count <= MAX_CANDLES
            or not isinstance(m15_candle_open_epochs, (tuple, list))
            or len(m15_candle_open_epochs) > MAX_CANDLES):
        out["reason"] = "INVALID_M15_CANDLES_SHAPE_OR_SIZE"
        return out
    out["m15_received_candle_count"] = len(m15_candle_open_epochs)
    base_epoch = int(start.timestamp())
    last_epoch = base_epoch + (expected_count - 1) * FRAME_SECONDS

    # Classify boundary and interior gaps ONLY when each supplied epoch
    # is an honest, strictly monotonic member of the nominal M15 grid.
    # A caller that supplies duplicate, off-grid, future or forged epochs
    # is rejected below; do not offer a misleading partial-coverage report.
    epochs = m15_candle_open_epochs
    epochs_well_formed = (
        all(type(t) is int
            and base_epoch <= t <= last_epoch
            and (t - base_epoch) % FRAME_SECONDS == 0
            for t in epochs)
        and all(epochs[i] < epochs[i + 1]
                for i in range(len(epochs) - 1))
    )
    if epochs_well_formed:
        have = set(epochs)
        missing = expected_count - len(have)
        first_present = base_epoch in have
        last_present = last_epoch in have
        missing_first = next(
            (i for i in range(expected_count)
             if base_epoch + i * FRAME_SECONDS in have),
            expected_count,
        )
        missing_last = next(
            (i for i in range(expected_count)
             if last_epoch - i * FRAME_SECONDS in have),
            expected_count,
        )
        # On a totally empty input, the initial and final missing spans
        # overlap. Do not double count them as distinct intervals.
        if not have:
            missing_last = 0
        interior = missing - missing_first - missing_last
        if interior < 0:
            out["reason"] = "IMPOSSIBLE_M15_GAP_COUNT"
            return out
        out.update(
            first_expected_m15_open_present=first_present,
            last_expected_m15_open_present=last_present,
            first_observed_m15_open_utc=(
                datetime.fromtimestamp(epochs[0], timezone.utc).isoformat()
                if epochs else None),
            last_observed_m15_open_utc=(
                datetime.fromtimestamp(epochs[-1], timezone.utc).isoformat()
                if epochs else None),
            first_observed_delay_minutes=(
                (epochs[0] - base_epoch) // 60 if epochs else None),
            last_observed_early_minutes=(
                (last_epoch - epochs[-1]) // 60 if epochs else None),
            missing_expected_m15_slots=missing,
            missing_at_start_consecutive_m15_slots=missing_first,
            missing_at_end_consecutive_m15_slots=missing_last,
            missing_interior_m15_slots=interior,
            missing_m15_classification=(
                "MISSING_FIRST_AND_LAST_M15" if not first_present and not last_present else
                "MISSING_FIRST_M15" if not first_present else
                "MISSING_LAST_M15" if not last_present else
                "MISSING_INTERIOR_M15" if interior else
                "COMPLETE_M15_GRID_CLAIM_ONLY"),
            m15_boundary_input_integrity_valid=True,
        )
    for i in range(expected_count):
        if (i >= len(m15_candle_open_epochs)
                or type(m15_candle_open_epochs[i]) is not int
                or m15_candle_open_epochs[i] != base_epoch + FRAME_SECONDS * i):
            out["reason"] = "M15_MISSING_DUPLICATE_OR_WRONG_EPOCH"
            out["first_mismatch_index"] = i
            return out
    if len(m15_candle_open_epochs) != expected_count:
        out["reason"] = "M15_EXCESS_EPOCHS_OUTSIDE_NY17_WINDOW"
        out["first_mismatch_index"] = expected_count
        return out

    out.update(
        state="LAB_M15_NY17_TIMESTAMP_COVERAGE_CLAIM_ONLY_NO_GO",
        reason="CONTIGUOUS_CALLER_EPOCH_CLAIMS_NOT_ARCHIVE_OR_BROKER_PROOF",
        archive_capture_utc_claim=captured.isoformat(),
        contiguous_ny17_m15_timestamps_claim_only=True,
    )
    return out


__all__ = ("SCHEMA", "inspect_m15_ny17_coverage_lab")
