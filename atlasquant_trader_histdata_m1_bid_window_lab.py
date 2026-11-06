"""Offline HistData generic ASCII M1 (Bid-only, *fixed* EST) event-window gate.

HistData publishes YYYYMMDD HHMMSS;O;H;L;C;Volume and declares ALL
timestamps EST UTC-05:00 WITHOUT daylight-saving adjustments. The source
supplies Bid bars with no genuine traded volume or Ask/spread. Never mistake
EST for America's seasonally changing New York time zone.

This is an untrusted historical export parser, not a downloader or a licensed
real-time source. It cannot authorize a backtest score or trading.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import re
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_HISTDATA_GENERIC_ASCII_M1_BID_WINDOW_LAB_V1"
SOURCE_SPEC = "https://www.histdata.com/f-a-q/data-files-detailed-specification/"
CURRENCIES = frozenset(("EUR", "USD", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD"))
EST_FIXED = timezone(timedelta(hours=-5))
MAX_BYTES = 6 * 1024 * 1024
MAX_M1_ROWS = 50_000
M1_SECONDS = 60
M15_SECONDS = 900
PRE_POST_M15 = 4
LINE = re.compile(
    r"(\d{4})(\d\d)(\d\d) (\d\d)(\d\d)00;"
    r"([^;]+);([^;]+);([^;]+);([^;]+);([0-9]+)"
)


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "source_id": "HISTDATA_GENERIC_ASCII_M1", "source_spec": SOURCE_SPEC,
        "symbol": None, "source_filename": None,
        "source_raw_sha256": None, "source_bytes": None,
        "source_capture_utc": None, "event_at_utc": None,
        "first_m1_open_utc": None, "last_m1_open_utc": None,
        "total_m1_rows": None, "pre_event_full_m15_bars": None,
        "post_event_full_m15_bars": None,
        "excluded_event_straddling_m15": None,
        "source_timezone_fixed_est_utc_minus_5": True,
        "source_applies_no_daylight_saving": True,
        "bar_price_side": "BID", "ask_prices_present": False,
        "spread_at_event_known": False, "volume_known": False,
        "downloaded_source_authenticity_verified": False,
        "market_data_product_license_verified": False,
        "historical_point_in_time_eligible": False,
        "m15_execution_price_verified": False,
        "historical_backtest_accuracy_verified": False,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "can_feed_live_radar": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "new_cost_brl": 0,
    }


def _utc(value: Any) -> datetime | None:
    return (value.astimezone(timezone.utc)
            if isinstance(value, datetime) and value.tzinfo is not None
            and value.utcoffset() is not None else None)


def _price(s: str) -> Decimal:
    if not re.fullmatch(r"(?:0|[1-9]\d{0,2})\.\d{1,8}", s):
        raise ValueError("invalid price form")
    try:
        d = Decimal(s)
    except InvalidOperation as exc:
        raise ValueError("invalid decimal") from exc
    if not Decimal("0.0001") <= d <= Decimal("1000"):
        raise ValueError("outside price bounds")
    return d


def inspect_histdata_m1_bid_window_lab(
    raw: Any, *, filename: str, expected_symbol: str,
    captured_at_utc: datetime, as_of_utc: datetime, event_at_utc: datetime,
) -> dict[str, Any]:
    """Check 4 x 15 complete M1 bars either side of a UTC event, no M15 price.

    No API, account, subscription, market signal, forward fill, or FX return.
    Source identity and licensing always remain unverified.
    """
    out = _deny("INVALID_INPUT_OR_CLOCK")
    capture, as_of, event = (_utc(captured_at_utc), _utc(as_of_utc),
                             _utc(event_at_utc))
    if (capture is None or as_of is None or event is None or capture > as_of
            or event > as_of or not isinstance(raw, bytes)
            or not 100 <= len(raw) <= MAX_BYTES
            or not isinstance(expected_symbol, str)
            or not re.fullmatch(r"[A-Z]{6}", expected_symbol)
            or expected_symbol[:3] not in CURRENCIES
            or expected_symbol[3:] not in CURRENCIES
            or expected_symbol[:3] == expected_symbol[3:]
            or not isinstance(filename, str)):
        return out
    match = re.fullmatch(r"DAT_ASCII_([A-Z]{6})_M1_(20\d{4})\.csv", filename)
    if not match or match.group(1) != expected_symbol:
        out["reason"] = "UNSUPPORTED_SOURCE_FILENAME"
        return out
    year, month = int(match.group(2)[:4]), int(match.group(2)[4:])
    if not 1 <= month <= 12:
        return out

    try:
        lines = raw.decode("ascii", errors="strict").splitlines()
        if not 1 <= len(lines) <= MAX_M1_ROWS:
            out["reason"] = "INSUFFICIENT_OR_EXCESSIVE_M1_ROWS"
            return out
        minutes: dict[int, tuple[Decimal, Decimal, Decimal, Decimal]] = {}
        previous: int | None = None
        for line in lines:
            m = LINE.fullmatch(line)
            if m is None:
                raise ValueError("unexpected HistData M1 line")
            y, mo, d, h, minute = [int(m.group(i)) for i in range(1, 6)]
            if (y, mo) != (year, month):
                raise ValueError("mixed source month")
            est = datetime(y, mo, d, h, minute, tzinfo=EST_FIXED)
            utc_epoch = int(est.timestamp())
            if (previous is not None and utc_epoch <= previous
                    or utc_epoch % M1_SECONDS != 0
                    or utc_epoch + M1_SECONDS > int(capture.timestamp())):
                raise ValueError("duplicate, unsorted or future M1")
            previous = utc_epoch
            o, hi, lo, c = (_price(m.group(i)) for i in range(6, 10))
            if not lo <= min(o, c) <= max(o, c) <= hi:
                raise ValueError("malformed M1 OHLC")
            if m.group(10) != "0":
                # HistData states volume is unavailable in these exports.
                raise ValueError("unexpected volume field")
            minutes[utc_epoch] = (o, hi, lo, c)
        if not minutes:
            return out

        event_ts = event.timestamp()
        anchor = int(event_ts // M15_SECONDS) * M15_SECONDS
        pre = [anchor - M15_SECONDS * i for i in range(4, 0, -1)]
        post = [anchor + M15_SECONDS * i for i in range(
            0 if event_ts == anchor else 1,
            (0 if event_ts == anchor else 1) + PRE_POST_M15)]
        crossing = event_ts != anchor
        required = pre + ([anchor] if crossing else []) + post

        for quarter in required:
            opens = [quarter + i * M1_SECONDS for i in range(15)]
            if not all(ts in minutes for ts in opens):
                out["reason"] = "M1_MISSING_IN_REQUIRED_M15_WINDOW_NO_FILL"
                return out
            # Pure aggregation consistency, without emitting bars, prices,
            # direction, tick count or a misleading execution quote.
            first, last = minutes[opens[0]], minutes[opens[-1]]
            high = max(minutes[ts][1] for ts in opens)
            low = min(minutes[ts][2] for ts in opens)
            if not low <= min(first[0], last[3]) <= max(first[0], last[3]) <= high:
                raise ValueError("malformed aggregated M15")

        keys = list(minutes)
        out.update({
            "state": "LAB_HISTDATA_BID_M15_WINDOW_STRUCTURALLY_COMPLETE_UNVERIFIED",
            "reason": "UNVERIFIED_SOURCE_LICENSE_ASK_SPREAD_AND_HISTORICAL_VINTAGE",
            "symbol": expected_symbol, "source_filename": filename,
            "source_raw_sha256": sha256(raw).hexdigest(),
            "source_bytes": len(raw), "source_capture_utc": capture.isoformat(),
            "event_at_utc": event.isoformat(),
            "first_m1_open_utc": datetime.fromtimestamp(keys[0], timezone.utc).isoformat(),
            "last_m1_open_utc": datetime.fromtimestamp(keys[-1], timezone.utc).isoformat(),
            "total_m1_rows": len(keys),
            "pre_event_full_m15_bars": PRE_POST_M15,
            "post_event_full_m15_bars": PRE_POST_M15,
            "excluded_event_straddling_m15": crossing,
        })
        return out
    except (UnicodeDecodeError, OverflowError, ValueError, TypeError):
        out["reason"] = "HISTDATA_M1_SCHEMA_OR_VALUES_REJECTED"
        return out


__all__ = ["SCHEMA", "SOURCE_SPEC", "inspect_histdata_m1_bid_window_lab"]
