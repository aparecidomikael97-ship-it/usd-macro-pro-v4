"""Offline US Treasury 10Y real/nominal yield context for XAUUSD research.

The caller supplies actual CSV bytes and *claimed* acquisition/publication clocks.
Neither clocks nor source origin are authenticated by this pure function.
No network, persistence, MT5, price feed, scoring, bias or trading.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import StringIO
from typing import Any

SCHEMA = "ATLASQUANT_XAUUSD_UST10Y_CSV_CONTEXT_LAB_V1"
OFFICIAL_SOURCE_PAGES = {
    "NOMINAL_10Y": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve",
    "REAL_TIPS_10Y": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_real_yield_curve",
}
MAX_CSV_BYTES = 1_048_576
MAX_CSV_ROWS = 4096
MAX_AGE_CALENDAR_DAYS = 7  # conservative weekend tolerance; NOT a verified holiday calendar


@dataclass(frozen=True)
class TreasuryCsvReceipt:
    curve_kind: str
    declared_source_page: str
    csv_bytes: bytes
    published_at_utc_claim: datetime
    captured_at_utc_claim: datetime


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond != 0):
        return None
    return value.astimezone(timezone.utc)


def _fail(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_XAUUSD_TREASURY_CONTEXT_BLOCKED",
        "reason": reason, "asset": "METAL:XAUUSD",
        "nominal_latest_10y_pct": None, "real_tips_latest_10y_pct": None,
        "real_tips_change_percentage_points": None,
        "nominal_change_percentage_points": None,
        "nominal_minus_real_yield_spread_pct_proxy": None,
        "observation_dates": None, "csv_sha256_local_only": None,
        "source_originals_independently_authenticated": False,
        "publication_timestamps_independently_authenticated": False,
        "daily_broker_gold_price_verified": False,
        "gold_direction_inferred_from_yields": False,
        "real_yields_alone_are_not_gold_trade_signals": True,
        "monthly_bias_validated": False,
        "directional_accuracy_validated": False,
        "validated_accuracy": None,
        "calibrated_direction_probability": None,
        "research_candidate_direction": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def _parse_document(
    row: Any, *, expected_kind: str, now: datetime, freeze: datetime,
) -> tuple[str, tuple[tuple[date, Decimal], ...], str] | str:
    if (not isinstance(row, TreasuryCsvReceipt)
            or row.curve_kind != expected_kind
            or type(row.declared_source_page) is not str
            or row.declared_source_page != OFFICIAL_SOURCE_PAGES[expected_kind]):
        return "WRONG_CURVE_KIND_OR_DECLARED_SOURCE"
    published = _utc(row.published_at_utc_claim)
    captured = _utc(row.captured_at_utc_claim)
    if (published is None or captured is None
            or not published <= captured <= freeze <= now):
        return "RELEASE_OR_CAPTURE_AFTER_DECISION_OR_INVALID_CLOCK"
    raw = row.csv_bytes
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_CSV_BYTES:
        return "INVALID_OR_OVERSIZED_CSV_BYTES"
    try:
        content = raw.decode("utf-8-sig")
        reader = csv.DictReader(StringIO(content, newline=""))
        columns = reader.fieldnames
        if (not isinstance(columns, list) or len(columns) != len(set(columns))
                or "Date" not in columns or "10 Yr" not in columns):
            return "CSV_MISSING_UNIQUE_DATE_OR_10YR_HEADER"
        points: list[tuple[date, Decimal]] = []
        seen: set[date] = set()
        for item in reader:
            if len(points) >= MAX_CSV_ROWS or None in item:
                return "CSV_TOO_MANY_ROWS_OR_EXTRA_FIELDS"
            raw_date, raw_yield = item.get("Date"), item.get("10 Yr")
            if not isinstance(raw_date, str) or not isinstance(raw_yield, str):
                return "CSV_DATE_OR_RATE_MISSING"
            d = datetime.strptime(raw_date.strip(), "%m/%d/%Y").date()
            if d in seen or d > published.date() or d > freeze.date():
                return "CSV_DATE_DUPLICATE_OR_FUTURE"
            seen.add(d)
            try:
                value = Decimal(raw_yield.strip())
            except (InvalidOperation, ValueError):
                return "CSV_10YR_NON_NUMERIC_OR_NA"
            if not value.is_finite() or not Decimal("-20") <= value <= Decimal("50"):
                return "CSV_10YR_NONFINITE_OR_OUT_OF_RANGE"
            points.append((d, value))
        if len(points) < 2:
            return "CSV_NEEDS_TWO_HISTORICAL_DATES"
        points.sort(key=lambda p: p[0])
        return expected_kind, tuple(points[-2:]), sha256(raw).hexdigest()
    except (UnicodeDecodeError, ValueError, csv.Error, OverflowError):
        return "CSV_MALFORMED_DATE_OR_TEXT"


def inspect_xauusd_treasury_yields_lab(
    nominal: Any, real_tips: Any, *, as_of_utc: Any, decision_freeze_utc: Any,
) -> dict[str, Any]:
    """Use only same-date 10Y nominal and TIPS curves known before freeze.

    Returned figures are descriptive and documentary. Nominal minus real is a
    break-even-inflation *proxy*, not a pure forecast of inflation; liquidity
    and risk premia can matter. This module never emits XAUUSD direction.
    """
    now, freeze = _utc(as_of_utc), _utc(decision_freeze_utc)
    if now is None or freeze is None or freeze > now:
        return _fail("INVALID_AS_OF_OR_FORECAST_FREEZE")
    items = {}
    hashes = {}
    for kind, row in (("NOMINAL_10Y", nominal), ("REAL_TIPS_10Y", real_tips)):
        parsed = _parse_document(row, expected_kind=kind, now=now, freeze=freeze)
        if isinstance(parsed, str):
            return _fail(kind + ":" + parsed)
        _, last_two, digest = parsed
        items[kind] = last_two
        hashes[kind] = digest
    nominal_data, real_data = items["NOMINAL_10Y"], items["REAL_TIPS_10Y"]
    if [p[0] for p in nominal_data] != [p[0] for p in real_data]:
        return _fail("NOMINAL_AND_REAL_CURVE_DATES_NOT_ALIGNED")
    latest_date = nominal_data[-1][0]
    if not 0 <= (freeze.date() - latest_date).days <= MAX_AGE_CALENDAR_DAYS:
        return _fail("TREASURY_CONTEXT_STALE_FOR_FORECAST_FREEZE")
    n0, n1 = nominal_data[0][1], nominal_data[1][1]
    r0, r1 = real_data[0][1], real_data[1][1]
    output = _fail("SOURCE_OR_PIT_STILL_UNATTESTED")
    output.update({
        "state": "LAB_XAUUSD_TREASURY_CONTEXT_DOCUMENTARY_UNATTESTED",
        "observation_dates": [d.isoformat() for d, _ in nominal_data],
        "nominal_latest_10y_pct": str(n1),
        "real_tips_latest_10y_pct": str(r1),
        "nominal_change_percentage_points": str(n1 - n0),
        "real_tips_change_percentage_points": str(r1 - r0),
        "nominal_minus_real_yield_spread_pct_proxy": str(n1 - r1),
        "csv_sha256_local_only": hashes,
    })
    return output


__all__ = ["SCHEMA", "OFFICIAL_SOURCE_PAGES", "TreasuryCsvReceipt",
           "inspect_xauusd_treasury_yields_lab"]
