"""Official Federal Reserve Board target federal-funds RANGE HTML receipt (LAB).

Only consume immutable-in-memory original HTML bytes supplied by a separate
manual fetcher. Extract the 2026 table specifically anchored to the official
Board's "Open Market Operations" page. Preserve lower/upper policy bounds;
never replace with midpoint or effective federal funds rate.

Critical distinctions:
* This Board table dates POLICY EFFECTIVE LEVELS, not timestamped FOMC
  announcements or the exact first-available time of any news.
* The webpage observed in 2026 does not attest its vintage in 2025 or
  before a historically frozen trading cutoff; an observed HTTP response
  is a local untrusted receipt, not an independent issuer-time witness.
* No actual forecast, macro comparison, FX direction, broker calls, account
  queries, orders, data backfill, chart changes or automated scheduling.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html.parser import HTMLParser
import re
from typing import Any

SCHEMA = "ATLASQUANT_US_FED_BOARD_TARGET_RANGE_HTML_RECEIPT_LAB_V1"
URL = "https://www.federalreserve.gov/monetarypolicy/openmarket.htm"
YEAR = 2026
MAX_BYTES = 240_000
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
RANGE = re.compile(r"(?:0|[1-9]\d{0,2})\.\d{2}-(?:0|[1-9]\d{0,2})\.\d{2}\Z")
POINT = re.compile(r"(?:0|[1-9]\d{0,2})\.\d{2}\Z")
BPS = re.compile(r"(?:0|[1-9]\d{0,2})\Z")
DAY = re.compile(
    r"(January|February|March|April|May|June|July|August|"
    r"September|October|November|December) ([1-9]|[12][0-9]|3[01])\Z"
)
RECEIPT_FIELDS = frozenset((
    "source_url", "final_url", "http_status", "content_type", "body_sha256",
    "started_at_utc", "finished_at_utc", "https_validation_claim",
    "redirects_followed",
))
HEADERS = ["Date", "Increase", "Decrease", "Level (%)"]


class _YearTable(HTMLParser):
    """Only the first pubtables following the exact target-year anchor."""
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.seen_year = False
        self.done_year = False
        self.table_count = 0
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.cell_parts: list[str] = []
        self.row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        props = dict(attrs)
        if tag == "a":
            if props.get("id") == str(YEAR):
                if self.seen_year:
                    raise ValueError("DUPLICATE_YEAR_ANCHOR")
                self.seen_year = True
            if props.get("id") == str(YEAR - 1) and self.seen_year:
                self.done_year = True
        if (tag == "table" and self.seen_year and not self.done_year
                and "pubtables" in (props.get("class") or "").split()):
            self.table_count += 1
            if self.in_table or self.table_count != 1:
                raise ValueError("DUPLICATE_POLICY_TABLE")
            self.in_table = True
        elif tag == "tr" and self.in_table:
            self.in_row = True
            self.row = []
        elif tag in ("th", "td") and self.in_row:
            if self.in_cell:
                raise ValueError("NESTED_TABLE_CELL")
            self.in_cell = True
            self.cell_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("th", "td") and self.in_cell:
            self.row.append(" ".join(" ".join(self.cell_parts).split()))
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            if self.in_cell:
                raise ValueError("UNCLOSED_CELL")
            self.rows.append(self.row)
            self.in_row = False
        elif tag == "table" and self.in_table:
            if self.in_row:
                raise ValueError("UNCLOSED_ROW")
            self.in_table = False


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FED_BOARD_TARGET_RANGE_RECEIPT_BLOCKED",
        "reason": reason,
        "currency": "USD",
        "issuer": "Federal Reserve Board",
        "instrument": "FED_FUNDS_TARGET_RANGE",
        "issuer_url": URL,
        "target_year": YEAR,
        "exact_html_sha256_verified_locally": False,
        "local_http_transport_claim_consistent": False,
        "table_structure_issuer_claim_consistent": False,
        "change_rows_checked": 0,
        "most_recent_effective_date_claim": None,
        "target_lower_pct_claim": None,
        "target_upper_pct_claim": None,
        "most_recent_change_increase_bp_claim": None,
        "most_recent_change_decrease_bp_claim": None,
        "capture_finished_at_utc_claim": None,
        "effective_date_is_not_release_timestamp": True,
        "target_range_not_compressed_to_midpoint": True,
        "issuer_first_publication_time_independently_attested": False,
        "historical_point_in_time_source_vintage_authenticated": False,
        "current_rate_from_issuer_independently_authenticated": False,
        "actual_effective_federal_funds_rate_conflated": False,
        "eight_currencies_macro_complete": False,
        "bilateral_fx28_macro_data_complete": False,
        "validated_forecast_accuracy": None,
        "calibrated_directional_probability": None,
        "directional_bias": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "live_alert_allowed": False,
        "http_requests": 0,
        "files_written": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def _utc(raw: Any) -> datetime | None:
    if type(raw) is not str or not re.fullmatch(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ", raw):
        return None
    try:
        t = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return t if t.year >= 2020 else None
    except ValueError:
        return None


def _decision(raw: Any) -> datetime | None:
    if not isinstance(raw, datetime) or raw.tzinfo is None:
        return None
    try:
        if raw.utcoffset() is None or raw.microsecond:
            return None
        return raw.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _pct(raw: str) -> Decimal | None:
    if type(raw) is not str or POINT.fullmatch(raw) is None:
        return None
    try:
        value = Decimal(raw)
        return value if value.is_finite() and Decimal("0") <= value <= Decimal("100") else None
    except InvalidOperation:
        return None


def _extract_2026_table(original_html: bytes) -> list[list[str]] | None:
    # UTF-8 and strict standard-library parser: never execute page JS.
    try:
        text = original_html.decode("utf-8-sig", "strict")
        if ("FOMC" not in text or "Open Market Operations" not in text
                or "target federal funds rate or range" not in text):
            return None
        parser = _YearTable()
        parser.feed(text)
        parser.close()
        if (not parser.seen_year or not parser.done_year
                or parser.table_count != 1 or parser.in_table
                or len(parser.rows) < 2 or parser.rows[0] != HEADERS):
            return None
        return parser.rows[1:]
    except (UnicodeError, ValueError, TypeError, OverflowError, AssertionError):
        return None


def inspect_fed_board_policy_target_range_receipt_lab(
    *, original_html: Any, receipt: Any, decision_at_utc: Any,
) -> dict[str, Any]:
    """Local byte/shape consistency only, NOT independent issuer authenticity."""
    out = _base("RAW_HTML_RECEIPT_OR_DECISION_CLOCK_INVALID")
    decision = _decision(decision_at_utc)
    if (type(original_html) is not bytes
            or not 100 <= len(original_html) <= MAX_BYTES
            or type(receipt) is not dict or set(receipt) != RECEIPT_FIELDS
            or decision is None):
        return out
    if (receipt["source_url"] != URL
            or receipt["final_url"] != URL
            or type(receipt["http_status"]) is not int
            or receipt["http_status"] != 200
            or type(receipt["content_type"]) is not str
            or receipt["content_type"].split(";")[0].strip().lower() != "text/html"
            or receipt["https_validation_claim"] is not True
            or receipt["redirects_followed"] is not False
            or type(receipt["body_sha256"]) is not str
            or SHA64.fullmatch(receipt["body_sha256"]) is None):
        out["reason"] = "NONOFFICIAL_URL_STATUS_OR_TRANSPORT_CLAIM"
        return out
    start = _utc(receipt["started_at_utc"])
    finish = _utc(receipt["finished_at_utc"])
    if (start is None or finish is None
            or not start <= finish <= decision
            or finish - start > timedelta(seconds=30)):
        out["reason"] = "FED_HTTP_OBSERVATION_AFTER_DECISION_OR_CLOCK_INVALID"
        return out
    if sha256(original_html).hexdigest() != receipt["body_sha256"]:
        out["reason"] = "FED_ORIGINAL_HTML_SHA256_MISMATCH"
        return out
    out["exact_html_sha256_verified_locally"] = True
    out["local_http_transport_claim_consistent"] = True

    rows = _extract_2026_table(original_html)
    if rows is None or not 1 <= len(rows) <= 20:
        out["reason"] = "FED_TARGET_YEAR_TABLE_SCHEMA_OR_HEADING_INVALID"
        return out
    seen: set[date] = set()
    dates: list[date] = []
    parsed = []
    for row in rows:
        if len(row) != 4 or DAY.fullmatch(row[0]) is None:
            out["reason"] = "FED_CHANGE_ROW_DATE_OR_COLUMNS_INVALID"
            return out
        try:
            effective = datetime.strptime(f"{row[0]} {YEAR}", "%B %d %Y").date()
        except ValueError:
            out["reason"] = "FED_CHANGE_DATE_CALENDAR_INVALID"
            return out
        if (effective in seen or effective >= finish.date()
                or dates and effective >= dates[-1]
                or BPS.fullmatch(row[1]) is None
                or BPS.fullmatch(row[2]) is None
                or RANGE.fullmatch(row[3]) is None):
            out["reason"] = "FED_RANGE_ROW_UNORDERED_DUPLICATE_FUTURE_OR_FORMAT_INVALID"
            return out
        low_text, high_text = row[3].split("-")
        low, high = _pct(low_text), _pct(high_text)
        if (low is None or high is None or low >= high
                or (int(row[1]) == 0) == (int(row[2]) == 0)):
            # The change row must be exactly one increase OR decrease.
            out["reason"] = "FED_RANGE_BOUNDS_OR_CHANGE_DIRECTION_INVALID"
            return out
        seen.add(effective)
        dates.append(effective)
        parsed.append((effective, low_text, high_text, int(row[1]), int(row[2])))

    effective, low, high, increase, decrease = parsed[0]
    out.update({
        "state": "LAB_USD_FED_BOARD_ORIGINAL_HTML_LOCALLY_CHECKED_NO_GO",
        "reason": "CURRENT_BOARD_HTML_OBSERVED_NOT_ORIGINAL_FOMC_RELEASE_VINTAGE",
        "table_structure_issuer_claim_consistent": True,
        "change_rows_checked": len(parsed),
        "most_recent_effective_date_claim": effective.isoformat(),
        "target_lower_pct_claim": low,
        "target_upper_pct_claim": high,
        "most_recent_change_increase_bp_claim": increase,
        "most_recent_change_decrease_bp_claim": decrease,
        "capture_finished_at_utc_claim": finish.isoformat(),
    })
    return out


__all__ = (
    "SCHEMA", "URL", "YEAR", "MAX_BYTES", "RECEIPT_FIELDS",
    "inspect_fed_board_policy_target_range_receipt_lab",
)
