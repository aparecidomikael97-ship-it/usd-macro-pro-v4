"""Offline structural validation of one 28-pair M15 research export.

H1/H4 are derived from M15 candles on UTC boundaries. Nothing here
authenticates a broker, timestamps, rights, prices, or an OOS forecast.
No network, terminal connection, signals, trading or scheduler.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping
from urllib.parse import urlsplit

from atlasquant_fx_universe import OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_TRADER_M15_EXPORT_LAB_V1"
STATE = "LAB_UNVERIFIED_BROKER_M15_EXPORT"
FIELDS = frozenset({"state", "source_id", "source_url", "exported_at_utc",
                    "time_basis", "price_kind", "license_status", "pairs"})
BAR = frozenset({"open_at_utc", "open", "high", "low", "close"})
STEP = timedelta(minutes=15)
DECIMAL = re.compile(r"[0-9]{1,5}(?:\.[0-9]{1,10})?")


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_M15_EXPORT_QUARANTINED",
        "reason": reason, "pair_coverage": 0, "m15_count": 0,
        "derived_h1": {}, "derived_h4": {},
        "real_currency_strength": None, "real_bias_28_pairs": None,
        "source_identity_attested": False, "broker_clock_attested": False,
        "point_in_time_capture_attested": False, "commercial_license_verified": False,
        "bid_ask_spread_verified": False, "independent_spot_quotes_verified": 0,
        "can_feed_live_radar": False, "can_feed_real_oos": False,
        "backtest_oos_authorized": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
    }


def _utc(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not 20 <= len(raw) <= 40:
        return None
    if not (raw.endswith("Z") or raw.endswith("+00:00")):
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        return None
    return value.astimezone(timezone.utc)


def _price(raw: Any) -> Decimal | None:
    if not isinstance(raw, str) or DECIMAL.fullmatch(raw) is None:
        return None
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        return None
    return amount if Decimal("0.0001") <= amount <= Decimal("10000") else None


def _combine(rows: list[tuple[datetime, Decimal, Decimal, Decimal, Decimal]]) -> dict[str, str]:
    return {
        "start_at_utc": rows[0][0].isoformat(),
        "end_at_utc": (rows[-1][0] + STEP).isoformat(),
        "open": str(rows[0][1]), "high": str(max(r[2] for r in rows)),
        "low": str(min(r[3] for r in rows)), "close": str(rows[-1][4]),
        "origin": "AGGREGATED_UNVERIFIED_M15_UTC_NOT_BROKER_NATIVE",
    }


def audit_m15_broker_export_lab(payload: Any, *, evaluated_at: datetime) -> dict[str, Any]:
    """Check 16 completed M15 bars per canonical pair, generate only LAB H1/H4."""
    if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None:
        raise ValueError("Evaluation time requires timezone")
    if not isinstance(payload, Mapping) or set(payload) != FIELDS:
        return _deny("Unexpected or missing export fields")
    if (payload["state"] != STATE or
            payload["time_basis"] != "UTC_DECLARED_UNATTESTED" or
            payload["price_kind"] != "BID_OHLC_UNVERIFIED" or
            payload["license_status"] != "UNREVIEWED_PERSONAL_LAB_ONLY"):
        return _deny("Cannot promote unreviewed rights, clock or price type")
    source = payload["source_id"]
    if not isinstance(source, str) or re.fullmatch(r"[A-Za-z0-9._-]{3,64}", source) is None:
        return _deny("Invalid source identity")
    source_url = payload["source_url"]
    if not isinstance(source_url, str) or not 1 <= len(source_url) <= 400:
        return _deny("Source URL required")
    try:
        u = urlsplit(source_url)
        url_ok = (u.scheme == "https" and bool(u.hostname) and not u.username
                  and not u.password and u.port in (None, 443) and not u.fragment)
    except ValueError:
        url_ok = False
    if not url_ok:
        return _deny("Only plain HTTPS attribution without credentials permitted")
    exported = _utc(payload["exported_at_utc"])
    now = evaluated_at.astimezone(timezone.utc)
    if exported is None or exported > now:
        return _deny("Missing, future or non-UTC export timestamp")
    pairs = payload["pairs"]
    if not isinstance(pairs, Mapping) or set(pairs) != set(OFFICIAL_PAIRS):
        return _deny("Exactly 28 canonical pairs needed; no inferred crosses")
    common_start = None
    h1, h4 = {}, {}
    for pair in OFFICIAL_PAIRS:
        raw_bars = pairs[pair]
        if not isinstance(raw_bars, list) or len(raw_bars) != 16:
            return _deny(f"{pair}: exactly 16 M15 bars required")
        rows = []
        for raw in raw_bars:
            if not isinstance(raw, Mapping) or set(raw) != BAR:
                return _deny(f"{pair}: malformed candle fields")
            t = _utc(raw["open_at_utc"])
            px = [_price(raw[k]) for k in ("open", "high", "low", "close")]
            if t is None or any(p is None for p in px):
                return _deny(f"{pair}: invalid UTC candle or decimal OHLC")
            op, high, low, close = px
            if not low <= min(op, close) <= max(op, close) <= high:
                return _deny(f"{pair}: inconsistent OHLC extremes")
            rows.append((t, op, high, low, close))
        start = rows[0][0]
        if start.hour % 4 or start.minute or start.second or start.microsecond:
            return _deny(f"{pair}: not aligned to research UTC H4 boundary")
        if common_start is None:
            common_start = start
        elif common_start != start:
            return _deny("28 pairs have different sample start times")
        if any(row[0] != start + STEP * n for n, row in enumerate(rows)):
            return _deny(f"{pair}: missing, duplicate or reordered M15 bars")
        if rows[-1][0] + STEP > exported:
            return _deny(f"{pair}: last bar still forming at export")
        h1[pair] = [_combine(rows[n:n + 4]) for n in range(0, 16, 4)]
        h4[pair] = _combine(rows)
    return {
        **_deny(""), "state": "LAB_M15_H1_H4_STRUCTURALLY_COMPLETE_UNTRUSTED",
        "reason": "OHLC layout only; prices, timestamp origin and license unverified",
        "pair_coverage": 28, "m15_count": 448,
        "window_start_utc": common_start.isoformat(),
        "window_end_utc": (common_start + STEP * 16).isoformat(),
        "derived_h1": h1, "derived_h4": h4,
        "why_not": "H1/H4 are algebraic UTC resamples of unverified bid-only M15; "
                   "broker-native H4 may use another session clock. No live/OOS permission.",
    }


__all__ = ["SCHEMA", "STATE", "audit_m15_broker_export_lab"]
