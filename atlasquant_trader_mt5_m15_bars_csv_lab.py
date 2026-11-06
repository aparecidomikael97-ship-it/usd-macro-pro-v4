"""Read-only MT5 Bars CSV/TSV inspection, LAB / HARD NO-GO.

MT5 native Bars export timestamps can use broker-server time. The CSV alone
does not establish UTC, broker, quote side, vintage, licensing or trading.
Never silently convert to UTC or use bars as predictive/outcome evidence.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import sys
from typing import Any

from atlasquant_instrument_registry import FX_28

SCHEMA = "ATLASQUANT_TRADER_MT5_M15_BARS_CSV_READONLY_LAB_V1"
SOURCE_DOC = "https://www.metatrader5.com/en/terminal/help/trading/market_watch#history"
EXPECTED_HEADER = ("<DATE>", "<TIME>", "<OPEN>", "<HIGH>", "<LOW>",
                   "<CLOSE>", "<TICKVOL>", "<VOL>", "<SPREAD>")
MAX_BYTES = 8_000_000
MAX_ROWS = 50_000
DECIMAL = re.compile(r"(?:0|[1-9][0-9]{0,2})(?:\.[0-9]{1,8})?\Z")
INTEGER = re.compile(r"(?:0|[1-9][0-9]{0,12})\Z")
DATE = re.compile(r"20[0-9]{2}\.[0-9]{2}\.[0-9]{2}\Z")
TIME = re.compile(r"[0-2][0-9]:[0-5][0-9]:(?:00)\Z")
CANONICAL = frozenset(FX_28)
SEP = {"tab": "\t", "comma": ","}


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "source_doc": SOURCE_DOC, "source_kind_claim": "MT5_BAR_CSV_EXPORT_UNVERIFIED",
        "declared_symbol": None, "declared_timeframe": "M15",
        "source_sha256": None, "source_bytes": None,
        "csv_delimiter": None, "row_count": 0,
        "earliest_server_local_bar": None, "latest_server_local_bar": None,
        "non_15_minute_gaps_inside_broker_dates": None,
        "weekend_dated_bars": None, "zero_spread_bars": None,
        "broker_server_timezone": "UNKNOWN_UNATTESTED",
        "time_values_are_utc_verified": False,
        "source_broker_identified_independently": False,
        "symbol_identity_independently_verified": False,
        "bid_ask_price_side_verified": False,
        "source_original_export_authenticated": False,
        "historical_vintage_point_in_time_verified": False,
        "historical_m15_execution_price_verified": False,
        "fx_ny_1700_d1w1_aligned": False,
        "usable_for_directional_backtest": False,
        "historical_predictive_accuracy": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "can_feed_live_radar": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "publishable": False, "http_requests": 0, "new_cost_brl": 0,
    }


def _decimal(value: str) -> Decimal:
    if not isinstance(value, str) or DECIMAL.fullmatch(value) is None:
        raise ValueError("price not a strict decimal string")
    try:
        p = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid decimal") from exc
    if not p.is_finite() or not Decimal("0.0001") <= p <= 999:
        raise ValueError("price out of range")
    return p


def _integer(value: str, low: int, high: int) -> int:
    if not isinstance(value, str) or INTEGER.fullmatch(value) is None:
        raise ValueError("non-integer column")
    v = int(value)
    if not low <= v <= high:
        raise ValueError("out-of-range integer column")
    return v


def inspect_mt5_m15_bars_csv_lab(
    raw: Any, *, declared_symbol: Any, declared_timeframe: Any = "M15",
) -> dict[str, Any]:
    """Validate one caller-supplied native-shape CSV; NEVER translate clock to UTC.

    This is not an importer into the signals app. Its report is a structural
    audit of broker-server-local time and OHLC, without live prices or trades.
    """
    out = _blocked("INVALID_BYTES_OR_DECLARED_SYMBOL")
    if (not isinstance(raw, bytes) or not 50 <= len(raw) <= MAX_BYTES
            or not isinstance(declared_symbol, str)
            or declared_symbol not in CANONICAL
            or declared_timeframe != "M15"):
        return out
    try:
        source_text = raw.decode("utf-8-sig", "strict")
        if "\x00" in source_text or "\r" in source_text.replace("\r\n", ""):
            raise ValueError("null or lone carriage return")
        text = source_text.strip("\r\n")
        lines = text.splitlines()
        if not 2 <= len(lines) <= MAX_ROWS + 1:
            out["reason"] = "CSV_ROW_COUNT_OUT_OF_BOUNDS"
            return out
        header = lines[0]
        matching_separators = [name for name, sep in SEP.items()
                               if tuple(header.split(sep)) == EXPECTED_HEADER]
        if len(matching_separators) != 1:
            out["reason"] = "NATIVE_MT5_HEADER_NOT_RECOGNIZED"
            return out
        sep_name = matching_separators[0]
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=SEP[sep_name],
                            strict=True)
        if tuple(next(reader)) != EXPECTED_HEADER:
            raise ValueError("header changed under CSV parser")
        previous: datetime | None = None
        first: datetime | None = None
        count, gap_count, weekend_count, zero_spread_count = 0, 0, 0, 0
        for row in reader:
            if len(row) != len(EXPECTED_HEADER):
                raise ValueError("unexpected column count")
            day, time, *rest = row
            if DATE.fullmatch(day) is None or TIME.fullmatch(time) is None:
                raise ValueError("unrecognized server-local timestamp")
            bar = datetime.strptime(day + " " + time, "%Y.%m.%d %H:%M:%S")
            if bar.hour > 23 or bar.minute % 15 or bar.second:
                raise ValueError("not an M15 opening boundary")
            if previous is not None and bar <= previous:
                raise ValueError("duplicate or unsorted bar timestamp")
            if previous is not None and bar.date() == previous.date():
                diff = int((bar - previous).total_seconds())
                if diff != 900:
                    gap_count += (diff // 900 - 1)
            o, h, l, c = (_decimal(x) for x in rest[:4])
            if not l <= min(o, c) <= max(o, c) <= h:
                raise ValueError("inconsistent OHLC range")
            _integer(rest[4], 1, 10**9)
            _integer(rest[5], 0, 10**12)
            spread = _integer(rest[6], 0, 10**6)
            if spread == 0:
                zero_spread_count += 1
            if bar.weekday() >= 5:
                weekend_count += 1
            if first is None:
                first = bar
            previous = bar
            count += 1
        if count == 0:
            return out
        out.update({
            "state": "LAB_MT5_M15_CSV_STRUCTURE_VALID_SERVER_CLOCK_UNATTESTED",
            "reason": "BROKER_SERVER_TIME_NOT_UTC_OR_INDEPENDENT_EXECUTION_PROOF",
            "declared_symbol": declared_symbol,
            "source_sha256": sha256(raw).hexdigest(),
            "source_bytes": len(raw),
            "csv_delimiter": sep_name,
            "row_count": count,
            "earliest_server_local_bar": first.isoformat(),
            "latest_server_local_bar": previous.isoformat(),
            "non_15_minute_gaps_inside_broker_dates": gap_count,
            "weekend_dated_bars": weekend_count,
            "zero_spread_bars": zero_spread_count,
        })
        return out
    except (UnicodeDecodeError, ValueError, csv.Error, OverflowError,
            IndexError, TypeError):
        out["reason"] = "CSV_SCHEMA_OHLC_OR_TIME_REJECTED"
        return out


def main(argv: list[str] | None = None) -> int:
    """Read only a user-selected CSV; never start terminal, trade or connect."""
    parser = argparse.ArgumentParser(description="LAB read-only MT5 M15 bar CSV audit")
    parser.add_argument("--csv-file", required=True, help="existing MT5 Bars CSV file")
    parser.add_argument("--declared-symbol", required=True, help="EURUSD or another G8 pair")
    args = parser.parse_args(argv)
    out = _blocked("CSV_FILE_UNAVAILABLE_OR_TOO_LARGE")
    try:
        path = Path(args.csv_file)
        if path.is_file() and 50 <= path.stat().st_size <= MAX_BYTES:
            out = inspect_mt5_m15_bars_csv_lab(
                path.read_bytes(), declared_symbol=args.declared_symbol)
    except (OSError, ValueError):
        pass
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if out["state"] == "LAB_MT5_M15_CSV_STRUCTURE_VALID_SERVER_CLOCK_UNATTESTED" else 2


__all__ = ["SCHEMA", "EXPECTED_HEADER", "SOURCE_DOC",
           "inspect_mt5_m15_bars_csv_lab", "main"]


if __name__ == "__main__":
    sys.exit(main())
