"""Read-only, offline price-label gate for archived MT5 AM12 closed candles.

An archive plus its own manifest can prove *internal consistency*, not broker
authenticity, UTC/session accuracy, historical point-in-time availability, or
the performance of a bias model. No terminal access, accounts, trades or I/O.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import gzip
from hashlib import sha256
from io import BytesIO, StringIO
from numbers import Integral
import re
from typing import Any, Mapping

from atlasquant_fx_universe import OFFICIAL_PAIRS


SCHEMA = "ATLASQUANT_MT5_FORWARD_LABEL_GATE_LAB_V1"
FIELDS = ("time_utc_epoch", "open", "high", "low", "close",
          "tick_volume", "spread", "real_volume")
EXPECTED = {"M15": 3000, "D1": 500, "W1": 200}
SECONDS = {"M15": 900, "D1": 86400, "W1": 604800}
MAX_GZIP_BYTES = 1024 * 1024
MAX_RAW_BYTES = 2 * 1024 * 1024


def _base(reason: str, pair: Any, timeframe: Any) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_MT5_FORWARD_PRICE_LABEL_BLOCKED",
        "reason": reason,
        "pair": pair if isinstance(pair, str) else None,
        "timeframe": timeframe if isinstance(timeframe, str) else None,
        "entry_bar_open_epoch_claim": None,
        "exit_bar_open_epoch_claim": None,
        "entry_close_price_documentary": None,
        "exit_close_price_documentary": None,
        "exit_bar_open_price_documentary": None,
        "exit_bar_open_to_close_bps_documentary": None,
        "observed_exit_bar_body_direction_only": None,
        "forward_price_change_bps_documentary": None,
        "observed_price_direction_only": None,
        "source_manifest_hash_self_consistent": False,
        "closed_bar_position_claim_only": False,
        "broker_price_source_authenticated": False,
        "mt5_candle_utc_time_independently_verified": False,
        "historical_point_in_time_verified": False,
        "decision_features_point_in_time_verified": False,
        "precommitted_prediction_present": False,
        "can_feed_validated_backtest": False,
        "validated_accuracy": None,
        "calibrated_probability": None,
        "operational_bias": "AGUARDAR",
        "publishable": False,
        "trade_authorized": False,
        "http_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
    }


def _positive_decimal(value: Any) -> Decimal:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("not a text decimal")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid decimal") from exc
    if not number.is_finite() or number <= 0:
        raise ValueError("non-positive or non-finite price")
    return number


def _epoch(value: Any) -> int:
    if not isinstance(value, Integral) or isinstance(value, bool) or value <= 0:
        raise ValueError("invalid epoch")
    datetime.fromtimestamp(int(value), timezone.utc)
    return int(value)


def inspect_mt5_forward_label_lab(
    *, pair: Any, timeframe: Any, manifest_record: Any,
    compressed_csv_gz: Any, entry_bar_open_epoch: Any,
    exit_bar_open_epoch: Any,
) -> dict[str, Any]:
    """Make a documentary one-bar close-to-close move from caller-supplied bytes.

    Both bar-open epochs must identify consecutive CSV rows separated by exactly
    one nominal bar period. Weekends, holidays, session/DST anomalies and absent
    candles intentionally block the label. No imputation or event-time join.
    """
    out = _base("INVALID_INPUT", pair, timeframe)
    if (not isinstance(pair, str) or pair not in OFFICIAL_PAIRS
            or not isinstance(timeframe, str) or timeframe not in EXPECTED):
        out["reason"] = "UNSUPPORTED_PAIR_OR_TIMEFRAME"
        return out
    if not isinstance(manifest_record, Mapping):
        out["reason"] = "MISSING_MANIFEST_RECORD"
        return out
    symbol = pair.replace("/", "")
    sha_claim = manifest_record.get("sha256_uncompressed_csv")
    if (manifest_record.get("symbol") != symbol
            or manifest_record.get("timeframe") != timeframe
            or manifest_record.get("snapshot_file") != f"{symbol}_{timeframe}_closedbar.csv.gz"
            or type(manifest_record.get("bar_position_start")) is not int
            or manifest_record["bar_position_start"] != 1
            or type(manifest_record.get("returned")) is not int
            or manifest_record["returned"] != EXPECTED[timeframe]
            or manifest_record.get("validation_errors") != []
            or not isinstance(sha_claim, str)
            or re.fullmatch(r"[0-9a-f]{64}", sha_claim) is None):
        out["reason"] = "MANIFEST_SERIES_OR_CLOSED_BARS_CLAIM_INVALID"
        return out
    out["closed_bar_position_claim_only"] = True

    if (not isinstance(compressed_csv_gz, bytes)
            or not compressed_csv_gz
            or len(compressed_csv_gz) > MAX_GZIP_BYTES):
        out["reason"] = "COMPRESSED_ARCHIVE_INVALID_OR_TOO_LARGE"
        return out
    try:
        with gzip.GzipFile(fileobj=BytesIO(compressed_csv_gz), mode="rb") as stream:
            raw = stream.read(MAX_RAW_BYTES + 1)
    except (EOFError, OSError, ValueError):
        out["reason"] = "GZIP_DECOMPRESSION_FAILED"
        return out
    if len(raw) > MAX_RAW_BYTES:
        out["reason"] = "UNCOMPRESSED_ARCHIVE_TOO_LARGE"
        return out
    if sha256(raw).hexdigest() != sha_claim:
        out["reason"] = "ARCHIVE_MANIFEST_HASH_MISMATCH"
        return out
    out["source_manifest_hash_self_consistent"] = True

    try:
        text = raw.decode("utf-8", "strict")
        reader = csv.DictReader(StringIO(text), restkey="__extra__")
        if reader.fieldnames != list(FIELDS):
            out["reason"] = "CSV_HEADER_MISMATCH"
            return out
        rows = list(reader)
        if len(rows) != EXPECTED[timeframe]:
            out["reason"] = "CSV_BAR_COUNT_MISMATCH"
            return out
        series: list[tuple[int, Decimal, Decimal]] = []
        prev_epoch: int | None = None
        for row in rows:
            if "__extra__" in row or set(row) != set(FIELDS) or any(row[k] is None for k in FIELDS):
                out["reason"] = "CSV_ROW_FIELD_MISMATCH"
                return out
            epoch = _epoch(int(row["time_utc_epoch"]))
            if prev_epoch is not None and epoch <= prev_epoch:
                out["reason"] = "NON_MONOTONIC_OR_DUPLICATE_BAR_TIMES"
                return out
            prev_epoch = epoch
            op, hi, lo, cl = (_positive_decimal(row[k]) for k in
                              ("open", "high", "low", "close"))
            if hi < max(op, cl) or lo > min(op, cl) or hi < lo:
                out["reason"] = "OHLC_INCONSISTENT"
                return out
            for key in ("tick_volume", "spread", "real_volume"):
                v = row[key]
                if not v.isascii() or not v.isdecimal() or int(v) < 0:
                    out["reason"] = "VOLUME_OR_SPREAD_INVALID"
                    return out
            series.append((epoch, op, cl))
        oldest = datetime.fromtimestamp(series[0][0], timezone.utc).isoformat()
        newest = datetime.fromtimestamp(series[-1][0], timezone.utc).isoformat()
        if (manifest_record.get("earliest_open_utc") != oldest
                or manifest_record.get("latest_open_utc") != newest):
            out["reason"] = "MANIFEST_BAR_TIME_RANGE_MISMATCH"
            return out
    except (ValueError, TypeError, OverflowError, OSError, InvalidOperation, UnicodeError, csv.Error):
        out["reason"] = "INVALID_CSV_BAR_VALUES_OR_TIMESTAMPS"
        return out

    try:
        entry_epoch = _epoch(entry_bar_open_epoch)
        exit_epoch = _epoch(exit_bar_open_epoch)
    except (ValueError, OverflowError, OSError):
        out["reason"] = "INVALID_SELECTED_BAR_TIMESTAMPS"
        return out
    positions = {v[0]: i for i, v in enumerate(series)}
    start = positions.get(entry_epoch)
    end = positions.get(exit_epoch)
    if start is None or end is None or end != start + 1:
        out["reason"] = "BAR_NOT_FOUND_OR_NOT_ADJACENT"
        return out
    if exit_epoch - entry_epoch != SECONDS[timeframe]:
        out["reason"] = "NON_NOMINAL_TIME_GAP_NO_IMPUTATION"
        return out
    entry_close = series[start][2]
    exit_open = series[end][1]
    exit_close = series[end][2]
    move = ((exit_close / entry_close) - Decimal(1)) * Decimal(10_000)
    body_move = ((exit_close / exit_open) - Decimal(1)) * Decimal(10_000)
    out.update({
        "state": "LAB_MT5_FORWARD_PRICE_LABEL_DOCUMENTARY_UNATTESTED",
        "reason": "LOCAL_CSV_INTEGRITY_ONLY_NOT_A_PREDICTION_OR_BACKTEST",
        "entry_bar_open_epoch_claim": entry_epoch,
        "exit_bar_open_epoch_claim": exit_epoch,
        "entry_close_price_documentary": str(entry_close),
        "exit_close_price_documentary": str(exit_close),
        "exit_bar_open_price_documentary": str(exit_open),
        "exit_bar_open_to_close_bps_documentary": str(body_move.quantize(Decimal("0.0001"))),
        "observed_exit_bar_body_direction_only": (
            "UP" if body_move > 0 else "DOWN" if body_move < 0 else "FLAT"),
        "forward_price_change_bps_documentary": str(move.quantize(Decimal("0.0001"))),
        "observed_price_direction_only": "UP" if move > 0 else "DOWN" if move < 0 else "FLAT",
    })
    return out
