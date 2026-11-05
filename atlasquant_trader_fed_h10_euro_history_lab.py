"""Offline H.10 EUR/USD historical table reader with weekly-publication gate.

Fed H.10 observed *daily* exchange rates are posted in its *weekly* Monday
release (normally 4:15 p.m. US Eastern, next business day for holidays).
An observation date is not a publication date; neither the noon observation
nor the release can be used as an M15 execution quote or consensus signal.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html.parser import HTMLParser
import re
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_FED_H10_EURO_HISTORY_LAB_V1"
SOURCE_URL = "https://www.federalreserve.gov/releases/h10/hist/dat00_eu.htm"
MAX_HTML_BYTES = 2 * 1024 * 1024
MAX_ROWS = 8_500
MONTHS = {m: i for i, m in enumerate(("JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                                       "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1)}
LONG_MONTHS = {m: i for i, m in enumerate(("January", "February", "March",
                                           "April", "May", "June", "July",
                                           "August", "September", "October",
                                           "November", "December"), 1)}
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _result(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "source_id": "FED_H10_EURO_NOON_RATE", "source_url": SOURCE_URL,
        "currency_pair": "EUR/USD", "unit": "USD_PER_EUR",
        "source_raw_sha256": None, "source_bytes": None,
        "captured_at_utc": None, "source_release_date": None,
        "release_time_1615_us_eastern_is_scheduled_not_witnessed": True,
        "source_release_instant_independently_verified": False,
        "historical_vintage_independently_verified": False,
        "data_are_noon_new_york_observations": True,
        "source_is_weekly_not_daily_publication": True,
        "source_publication_after_event_date": None,
        "source_unavailable_on_event_day": None,
        "event_at_utc": None,
        "first_observation_date": None, "last_observation_date": None,
        "numeric_observations": None, "missing_nd_observations": None,
        "start_date": None, "end_date": None,
        "start_observed_rate": None, "end_observed_rate": None,
        "historical_point_in_time_eligible": False,
        "independent_executable_m15_price_verified": False,
        "market_surprise_bps": None, "fx_bias": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "can_feed_live_radar": False, "publishable": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "new_cost_brl": 0,
    }


def _utc(value: Any) -> datetime | None:
    return (value.astimezone(timezone.utc)
            if isinstance(value, datetime) and value.tzinfo is not None
            and value.utcoffset() is not None else None)


def _iso_date(value: Any) -> date | None:
    if not isinstance(value, str) or not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _rate(value: str) -> Decimal | None:
    if value == "ND":
        return None
    if not re.fullmatch(r"(?:0|[1-9]\d{0,2})\.\d{1,6}", value):
        raise ValueError("unexpected H10 rate")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid numeric quote") from exc
    if not Decimal("0.001") <= number <= Decimal("100"):
        raise ValueError("unexpected H10 range")
    return number


class _H10EuroParser(HTMLParser):
    """Read only the named official H.10 EU Euro table and release label."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.table_count = 0
        self.in_table = False
        self.row: list[tuple[str, str]] | None = None
        self.cell_tag: str | None = None
        self.cell_text: list[str] = []
        self.release_div = False
        self.release_parts: list[str] = []
        self.unit_span = False
        self.unit_parts: list[str] = []
        self.heading_h5 = False
        self.heading_parts: list[str] = []
        self.rows: list[list[tuple[str, str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "div" and "dates" in (a.get("class") or "").split():
            self.release_div = True
        if tag == "span" and "tableunit" in (a.get("class") or "").split():
            self.unit_span = True
        if tag == "h5" and "tablehead" in (a.get("class") or "").split():
            self.heading_h5 = True
        if tag == "table":
            if self.in_table:
                raise ValueError("nested H10 table")
            if ("pubtables" in (a.get("class") or "").split()
                    and (a.get("title") or "").strip() == "Historical Rates for the EU Euro"):
                self.table_count += 1
                self.in_table = True
        elif self.in_table and tag == "tr":
            if self.row is not None:
                raise ValueError("nested H10 row")
            self.row = []
        elif self.in_table and self.row is not None and tag in ("th", "td"):
            if self.cell_tag is not None:
                raise ValueError("nested H10 cell")
            self.cell_tag, self.cell_text = tag, []

    def handle_data(self, data: str) -> None:
        if self.release_div:
            self.release_parts.append(data)
        if self.unit_span:
            self.unit_parts.append(data)
        if self.heading_h5:
            self.heading_parts.append(data)
        if self.cell_tag is not None:
            self.cell_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("th", "td") and self.cell_tag == tag and self.row is not None:
            self.row.append((tag, "".join(self.cell_text).strip()))
            self.cell_tag, self.cell_text = None, []
        elif tag == "tr" and self.in_table:
            if self.row is None or len(self.row) != 2:
                raise ValueError("unexpected table row")
            self.rows.append(self.row)
            if len(self.rows) > MAX_ROWS:
                raise ValueError("too many H10 rows")
            self.row = None
        elif tag == "table" and self.in_table:
            if self.row is not None:
                raise ValueError("unclosed H10 row")
            self.in_table = False
        elif tag == "div" and self.release_div:
            self.release_div = False
        elif tag == "span" and self.unit_span:
            self.unit_span = False
        elif tag == "h5" and self.heading_h5:
            self.heading_h5 = False


def _release_date(text: str) -> date:
    m = re.fullmatch(
        r"Release Date:\s*(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s*"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{1,2}),\s+(20\d{2})", text.strip())
    if m is None:
        raise ValueError("unrecognized release heading")
    d = date(int(m.group(4)), LONG_MONTHS[m.group(2)], int(m.group(3)))
    if WEEKDAYS[d.weekday()] != m.group(1) or d.weekday() not in (0, 1):
        raise ValueError("unexpected release weekday")
    return d


def _day_from_h10(text: str) -> date:
    m = re.fullmatch(r"([1-9]|[12]\d|3[01])-([A-Z]{3})-(\d\d)", text)
    if m is None or m.group(2) not in MONTHS:
        raise ValueError("unrecognized observation date")
    d = date(2000 + int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
    if d.weekday() >= 5:
        raise ValueError("weekend H10 observation")
    return d


def inspect_fed_h10_euro_history_lab(
    raw: Any, *, captured_at_utc: datetime, as_of_utc: datetime,
    requested_start_date: str, requested_end_date: str,
    event_at_utc: datetime,
) -> dict[str, Any]:
    """Check weekly release after an event; never certify ex-ante executable FX."""
    out = _result("INVALID_INPUT_OR_CAPTURE_BOUNDARY")
    captured, as_of, event = (_utc(captured_at_utc), _utc(as_of_utc),
                              _utc(event_at_utc))
    start, end = _iso_date(requested_start_date), _iso_date(requested_end_date)
    if (captured is None or as_of is None or event is None
            or captured > as_of or event > as_of
            or start is None or end is None or not start < end
            or end > captured.date() or end > as_of.date()
            or not isinstance(raw, bytes)
            or not 100 <= len(raw) <= MAX_HTML_BYTES or b"\x00" in raw):
        return out
    try:
        parser = _H10EuroParser()
        parser.feed(raw.decode("utf-8", errors="strict"))
        parser.close()
        if (parser.table_count != 1 or parser.in_table or parser.row is not None
                or parser.cell_tag is not None
                or " ".join(parser.unit_parts).strip()
                != "(Rates in U.S. dollars per EU euro)"
                or " ".join(parser.heading_parts).strip()
                != "Historical Rates for the EU Euro"
                or not 2 <= len(parser.rows) <= MAX_ROWS):
            return out
        release = _release_date(" ".join(parser.release_parts))
        if release > captured.date() or release > as_of.date():
            return out
        rates: dict[date, Decimal | None] = {}
        prev: date | None = None
        for cells in parser.rows:
            if tuple(c[0] for c in cells) != ("th", "td"):
                return out
            day = _day_from_h10(cells[0][1])
            if (prev is not None and day <= prev) or day >= release:
                return out
            prev = day
            rates[day] = _rate(cells[1][1])
        if start not in rates or end not in rates or rates[start] is None or rates[end] is None:
            out["reason"] = "H10_DAY_MISSING_OR_ND_NO_INTERPOLATION"
            return out
        after_event = release > event.date()
        out.update({
            "state": "LAB_H10_WEEKLY_RELEASE_DAILY_OBSERVATIONS_ONLY",
            "reason": ("H10_RELEASE_AFTER_EVENT_NO_PRE_EVENT_ACCESS"
                       if after_event else "NO_INDEPENDENT_HISTORICAL_VINTAGE_OR_M15_QUOTE"),
            "source_raw_sha256": sha256(raw).hexdigest(),
            "source_bytes": len(raw), "captured_at_utc": captured.isoformat(),
            "source_release_date": release.isoformat(),
            "source_publication_after_event_date": after_event,
            "source_unavailable_on_event_day": True if after_event else None,
            "event_at_utc": event.isoformat(),
            "first_observation_date": min(rates).isoformat(),
            "last_observation_date": max(rates).isoformat(),
            "numeric_observations": sum(v is not None for v in rates.values()),
            "missing_nd_observations": sum(v is None for v in rates.values()),
            "start_date": start.isoformat(), "end_date": end.isoformat(),
            "start_observed_rate": format(rates[start], "f"),
            "end_observed_rate": format(rates[end], "f"),
        })
        return out
    except (UnicodeDecodeError, ValueError, TypeError, OverflowError):
        out["reason"] = "HTML_SCHEMA_OR_VALUES_REJECTED"
        return out


__all__ = ["SCHEMA", "SOURCE_URL", "inspect_fed_h10_euro_history_lab"]
