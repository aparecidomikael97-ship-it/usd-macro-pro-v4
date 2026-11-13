"""Read-only adapter: supplied AM12-style MT5 M15 CSV.gz -> NY17 coverage.

This checks *local* gzip/CSV/manifest integrity before giving epochs to the
NY17 D1/W1 M15 coverage gate. It never opens the terminal or file system,
authenticates a broker or prediction, derives profit, or publishes a bias.

The 3000-row archive can contain historical weekends, early closes and gaps.
No missing candle is interpolated: the full requested NY17 window must be
covered; otherwise study remains AGUARDAR pending source/calendar review.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import gzip
from hashlib import sha256
from io import BytesIO, StringIO
import re
from typing import Any, Mapping

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_mt5_forward_label_gate_lab import (
    EXPECTED, FIELDS, MAX_GZIP_BYTES, MAX_RAW_BYTES,
)
from atlasquant_trader_mt5_m15_ny17_coverage_lab import (
    inspect_m15_ny17_coverage_lab,
)

SCHEMA = "ATLASQUANT_TRADER_MT5_M15_ARCHIVE_NY17_JOIN_LAB_V1"
FRAME = "M15"
FRAME_SECONDS = 900
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
DECIMAL_MAX = Decimal("1000000000")
TARGET_STATE = "LAB_M15_NY17_TIMESTAMP_COVERAGE_CLAIM_ONLY_NO_GO"


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None):
        return None
    return value.astimezone(timezone.utc)


def _positive(v: Any) -> Decimal | None:
    if not isinstance(v, str) or not 1 <= len(v) <= 40:
        return None
    try:
        d = Decimal(v)
    except (InvalidOperation, ValueError):
        return None
    return d if d.is_finite() and 0 < d < DECIMAL_MAX else None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_MT5_M15_ARCHIVE_NY17_JOIN_BLOCKED", "reason": reason,
        "pair": None, "horizon": None,
        "manifest_local_hash_consistent": False,
        "csv_full_row_count_and_order_verified_locally": False,
        "m15_rows_examined": 0, "window_m15_rows_found": 0,
        "window_expected_m15_rows": None,
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
        "window_coverage": None,
        "price_window_start_open_documentary": None,
        "price_window_end_close_documentary": None,
        "price_open_to_close_bps_documentary": None,
        "price_movement_direction_documentary": None,
        "price_window_label_method": "FIRST_M15_OPEN_TO_LAST_M15_CLOSE",
        "original_archive_bytes_provided_by_caller": False,
        "source_independently_authenticated": False,
        "source_broker_identity_verified": False,
        "broker_m15_epoch_timezone_independently_verified": False,
        "broker_session_calendar_verified": False,
        "holiday_gap_classification_verified": False,
        "source_ohlc_independently_verified": False,
        "history_point_in_time_verified": False,
        "model_prediction_externally_precommitted": False,
        "market_direction_from_archive": None,
        "validated_accuracy": None, "calibrated_probability": None,
        "operational_bias": "AGUARDAR",
        "publishable": False, "can_feed_live_radar": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "external_http_requests": 0, "file_writes": 0,
        "new_cost_brl": 0, "research_only": True,
    }


def inspect_mt5_m15_archive_ny17_join_lab(
    *, pair: Any, horizon: Any, start_at_utc: Any, end_at_utc: Any,
    manifest_record: Any, compressed_csv_gz: Any,
    archive_captured_at_utc: Any, evaluated_at_utc: Any,
) -> dict[str, Any]:
    """Inspect local archive bytes and exact M15 NY17 coverage; NO price label.

    The caller supplies one manifest record and its raw gzip bytes. The hash
    checks self-consistency with that manifest, NOT exchange/broker authenticity.
    """
    out = _base("INVALID_INPUT_OR_CLOCK")
    start, end, captured, evaluated = (
        _utc(t) for t in (start_at_utc, end_at_utc,
                         archive_captured_at_utc, evaluated_at_utc)
    )
    if (not isinstance(pair, str) or pair not in OFFICIAL_PAIRS
            or horizon not in ("D1", "W1")
            or any(t is None for t in (start, end, captured, evaluated))
            or not start < end <= captured <= evaluated
            or not isinstance(manifest_record, Mapping)):
        return out
    out["pair"], out["horizon"] = pair, horizon
    symbol = pair.replace("/", "")
    claimed_hash = manifest_record.get("sha256_uncompressed_csv")
    if (manifest_record.get("symbol") != symbol
            or manifest_record.get("timeframe") != FRAME
            or manifest_record.get("snapshot_file") != f"{symbol}_M15_closedbar.csv.gz"
            or type(manifest_record.get("bar_position_start")) is not int
            or manifest_record["bar_position_start"] != 1
            or type(manifest_record.get("returned")) is not int
            or manifest_record["returned"] != EXPECTED[FRAME]
            or manifest_record.get("validation_errors") != []
            or not isinstance(claimed_hash, str)
            or HEX64.fullmatch(claimed_hash) is None):
        out["reason"] = "MANIFEST_IDENTITY_OR_CLOSED_BAR_CLAIM_INVALID"
        return out
    if (not isinstance(compressed_csv_gz, bytes) or not compressed_csv_gz
            or len(compressed_csv_gz) > MAX_GZIP_BYTES):
        out["reason"] = "INVALID_COMPRESSED_ARCHIVE_OR_OVERSIZED"
        return out
    out["original_archive_bytes_provided_by_caller"] = True
    try:
        with gzip.GzipFile(fileobj=BytesIO(compressed_csv_gz), mode="rb") as gz:
            raw = gz.read(MAX_RAW_BYTES + 1)
            if len(raw) > MAX_RAW_BYTES:
                raise ValueError("DECOMPRESSED_ARCHIVE_OVERSIZED")
            if gz.read(1):
                raise ValueError("EXCESS_DECOMPRESSED_ARCHIVE_DATA")
    except (OSError, EOFError, ValueError, OverflowError) as exc:
        out["reason"] = ("DECOMPRESSED_ARCHIVE_OVERSIZED"
                         if str(exc) == "DECOMPRESSED_ARCHIVE_OVERSIZED"
                         else "GZIP_CONTENTS_CORRUPT_OR_TOO_LARGE")
        return out
    if sha256(raw).hexdigest() != claimed_hash:
        out["reason"] = "ARCHIVE_MANIFEST_LOCAL_HASH_MISMATCH"
        return out
    out["manifest_local_hash_consistent"] = True
    try:
        reader = csv.DictReader(StringIO(raw.decode("utf-8", "strict"),
                                         newline=""), restkey="__extra__")
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError("CSV_HEADER_MISMATCH")
        epochs: list[int] = []
        window_price_points: dict[int, tuple[Decimal, Decimal]] = {}
        start_epoch, end_epoch = int(start.timestamp()), int(end.timestamp())
        for row in reader:
            if ("__extra__" in row or set(row) != set(FIELDS)
                    or any(row[k] is None for k in FIELDS)):
                raise ValueError("CSV_ROW_FIELDS_INVALID")
            t = row["time_utc_epoch"]
            if (not isinstance(t, str) or not t.isascii()
                    or not t.isdecimal() or len(t) > 12):
                raise ValueError("CSV_EPOCH_INVALID")
            epoch = int(t)
            if epoch <= 0 or epochs and epoch <= epochs[-1]:
                raise ValueError("CSV_EPOCH_DUPLICATE_OR_NON_MONOTONIC")
            # Validate every archived M15 timestamp, not just the requested
            # NY17 window: a shifted candle elsewhere still invalidates the
            # integrity claim of the full supplied snapshot.
            if epoch % FRAME_SECONDS != 0:
                raise ValueError("CSV_M15_EPOCH_NOT_ON_UTC_QUARTER_HOUR")
            prices = [_positive(row[k]) for k in ("open", "high", "low", "close")]
            if any(p is None for p in prices):
                raise ValueError("CSV_PRICE_INVALID")
            op, hi, lo, cl = prices
            if hi < max(op, cl) or lo > min(op, cl) or hi < lo:
                raise ValueError("CSV_OHLC_INCONSISTENT")
            for k in ("tick_volume", "spread", "real_volume"):
                value = row[k]
                if (not value or not value.isascii() or not value.isdecimal()
                        or len(value) > 24):
                    raise ValueError("CSV_VOLUME_OR_SPREAD_INVALID")
            epochs.append(epoch)
            if start_epoch <= epoch < end_epoch:
                window_price_points[epoch] = (op, cl)
            if len(epochs) > EXPECTED[FRAME]:
                raise ValueError("CSV_ROW_COUNT_INVALID")
        if len(epochs) != EXPECTED[FRAME]:
            raise ValueError("CSV_ROW_COUNT_INVALID")
        first = datetime.fromtimestamp(epochs[0], timezone.utc).isoformat()
        last = datetime.fromtimestamp(epochs[-1], timezone.utc).isoformat()
        if (manifest_record.get("earliest_open_utc") != first
                or manifest_record.get("latest_open_utc") != last):
            raise ValueError("MANIFEST_CSV_TIME_RANGE_MISMATCH")
        # AM12 exports nominally closed positions 1..N. Do not treat the
        # latest still-open bar as a historical completed outcome.
        if datetime.fromtimestamp(epochs[-1] + FRAME_SECONDS, timezone.utc) > captured:
            raise ValueError("ARCHIVE_CAPTURE_BEFORE_LATEST_M15_CLOSE")
    except (ValueError, TypeError, OverflowError, OSError,
            UnicodeError, csv.Error) as exc:
        out["reason"] = str(exc) if isinstance(exc, ValueError) else "CSV_PARSE_INVALID"
        return out
    out["m15_rows_examined"] = len(epochs)
    out["csv_full_row_count_and_order_verified_locally"] = True

    start_epoch, end_epoch = int(start.timestamp()), int(end.timestamp())
    window = [t for t in epochs if start_epoch <= t < end_epoch]
    out["window_m15_rows_found"] = len(window)
    covered = inspect_m15_ny17_coverage_lab(
        pair=pair, horizon=horizon, start_at_utc=start, end_at_utc=end,
        m15_candle_open_epochs=window, archive_captured_at_utc=captured,
        evaluated_at_utc=evaluated, source_sha256_claim=claimed_hash,
    )
    out["window_expected_m15_rows"] = covered["m15_expected_candle_count"]
    out["first_mismatch_index"] = covered["first_mismatch_index"]
    # Preserve provenance-neutral endpoint diagnostics even on a blocked
    # archive. Never attach a return or claim an observed direction if
    # the first, last or any interior M15 bar is missing.
    for field in (
        "first_expected_m15_open_present",
        "last_expected_m15_open_present",
        "first_observed_m15_open_utc",
        "last_observed_m15_open_utc",
        "first_observed_delay_minutes",
        "last_observed_early_minutes",
        "missing_expected_m15_slots",
        "missing_at_start_consecutive_m15_slots",
        "missing_at_end_consecutive_m15_slots",
        "missing_interior_m15_slots",
        "missing_m15_classification",
        "m15_boundary_input_integrity_valid",
    ):
        out[field] = covered[field]
    if covered["state"] != TARGET_STATE:
        out["reason"] = "M15_NY17_COVERAGE_" + covered["reason"]
        return out

    # Price movement is the OPEN of the first M15 bar to the CLOSE of
    # the final *closed* M15 bar. It is NOT a close-to-close return,
    # executable trade, spread-adjusted P&L, or direction forecast.
    try:
        first_open = window_price_points[start_epoch][0]
        final_close = window_price_points[end_epoch - FRAME_SECONDS][1]
        raw_bps = (final_close / first_open - 1) * Decimal("10000")
        if abs(raw_bps) > Decimal("1000000"):
            out["reason"] = "DOCUMENTARY_PRICE_RATIO_OUTSIDE_RESEARCH_GUARDRAIL"
            return out
        bps = raw_bps.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    except (KeyError, InvalidOperation, OverflowError, ZeroDivisionError):
        out["reason"] = "DOCUMENTARY_PRICE_LABEL_UNAVAILABLE_OR_INVALID"
        return out
    direction = "UP" if final_close > first_open else (
        "DOWN" if final_close < first_open else "FLAT")

    out.update({
        "price_window_start_open_documentary": str(first_open),
        "price_window_end_close_documentary": str(final_close),
        "price_open_to_close_bps_documentary": str(bps),
        "price_movement_direction_documentary": direction,
        "state": "LAB_MT5_M15_ARCHIVE_NY17_LOCAL_JOIN_NO_GO",
        "reason": "LOCAL_ARCHIVE_AND_NY17_SHAPE_ONLY_NOT_BROKER_ATTESTATION",
        "window_coverage": covered,
    })
    return out


__all__ = ("SCHEMA", "inspect_mt5_m15_archive_ny17_join_lab")
