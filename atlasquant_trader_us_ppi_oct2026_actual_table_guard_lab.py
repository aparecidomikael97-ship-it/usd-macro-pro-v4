"""US October-2026 PPI first-print candidate: offline Table-1 semantic gate.

Never treats a user-supplied URL, hash, status or clock as independent BLS
publisher attestation. Never creates a tradable bias, alert, or backtest result.
The future October release values are deliberately not bundled in this code.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html.parser import HTMLParser
import re
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_US_PPI_OCT2026_ACTUAL_TABLE_GUARD_LAB_V1"
OFFICIAL_URL = "https://www.bls.gov/news.release/archives/ppi_11132026.htm"
OFFICIAL_SCHEDULE = "https://www.bls.gov/schedule/news_release/ppi.htm"
RELEASE_UTC = datetime(2026, 11, 13, 13, 30, tzinfo=timezone.utc)
MAX_BYTES = 4 * 1024 * 1024
MAX_NON_UTF8_BYTES = 32
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_NUMBER = re.compile(r"[+-]?(?:0|[1-9]\d?)(?:\.\d{1,3})?\Z")
_HEADLINE = re.compile(
    r"The Producer Price Index for final demand\s+"
    r"(increased|rose|advanced|decreased|declined|fell)\s+"
    r"(\d+(?:\.\d+)?)\s+percent in October,\s+seasonally adjusted",
    re.I,
)


@dataclass(frozen=True)
class ClaimedPostReleaseHTTP:
    source_url: str
    status_code: int
    content_type: str
    started_utc: datetime
    finished_utc: datetime
    raw_sha256: str


class _BlsTables(HTMLParser):
    """Record table captions/preceding heading and row cells (not page regex)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_chunks: list[str] = []
        self.tables: list[tuple[str, list[tuple[str, ...]]]] = []
        self._active: list[tuple[str, ...]] | None = None
        self._scope: str = ""
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._hidden: str | None = None
        self._skip_depth = 0
        self._outside_since_last_table: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "table":
            if self._active is not None:
                # Nested layout tables are deliberately not supported for a
                # PPI result. Never guess row or column boundaries.
                raise ValueError("NESTED_TABLE")
            self._active = []
            self._scope = " ".join(self._outside_since_last_table)[-1800:]
            self._outside_since_last_table = []
        elif tag == "tr" and self._active is not None:
            if self._row is not None:
                raise ValueError("NESTED_ROW")
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            if self._cell is not None:
                raise ValueError("NESTED_CELL")
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self.text_chunks.append(data)
        if self._cell is not None:
            self._cell.append(data)
        elif self._active is not None:
            self._scope += " " + data
        else:
            self._outside_since_last_table.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in {"td", "th"} and self._cell is not None:
            if self._row is None:
                raise ValueError("ORPHAN_CELL")
            self._row.append(" ".join(" ".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._cell is not None:
                raise ValueError("UNCLOSED_CELL")
            self._active.append(tuple(self._row))  # type: ignore[union-attr]
            self._row = None
        elif tag == "table" and self._active is not None:
            if self._row is not None or self._cell is not None:
                raise ValueError("UNCLOSED_TABLE")
            self.tables.append((" ".join(self._scope.split()), self._active))
            self._active = None


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _decimal(text: str) -> Decimal | None:
    if not isinstance(text, str) or not _NUMBER.fullmatch(text):
        return None
    try:
        v = Decimal(text)
        return v if v.is_finite() and -20 <= v <= 20 else None
    except InvalidOperation:
        return None


def _empty(reason: str, state: str = "LAB_PPI_FIRST_PRINT_BLOCKED") -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": state, "reason": reason,
        "event_release_utc": RELEASE_UTC.isoformat(),
        "official_source_url": OFFICIAL_URL,
        "source_sha256": None, "source_capture_claim_utc": None,
        "headline_final_demand_sa_mom_pct_body_claim": None,
        "core_ex_food_energy_sa_mom_pct_body_claim": None,
        "ex_food_energy_trade_services_pct": None,
        "headline_vs_td_pre_event_diff_pp": None,
        "core_vs_td_pre_event_diff_pp": None,
        "official_actual_independently_attested": False,
        "actual_available_at_original_release_independently_attested": False,
        "point_in_time_backtest_eligible": False,
        "source_redistribution_licensed": False,
        "market_bias": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "scheduler_enabled": False, "worker_enabled": False,
        "http_requests": 0, "new_cost_brl": 0,
    }


# The last column of Table 1 need not be the MoM rate after a provider
# layout change.  Read the exact Sep-to-Oct seasonally adjusted column by its
# visible header; otherwise abstain rather than mistake year-on-year NSA,
# prior-month or weight figures for the October 2026 SA monthly surprise.
_MONTH_TO_MONTH = re.compile(
    r"\\bsep(?:t(?:ember)?)?[.]?\\s+to\\s+oct(?:ober)?[.]?\\b", re.I
)
_SEASONAL = re.compile(r"\\bsa\\b|\\bseasonally\\s+adjusted\\b", re.I)


def _oct2026_sa_month_column(rows: list[tuple[str, ...]]) -> tuple[int, int] | None:
    candidates: list[tuple[int, int]] = []
    for cells in rows:
        if len(cells) < 7 or cells[0].strip().casefold() != "grouping":
            continue
        if len(cells) < 3 or cells[1].casefold() != "commodity code":
            continue
        positions = [
            index for index, text in enumerate(cells)
            if _MONTH_TO_MONTH.search(text) and _SEASONAL.search(text)
            and "2025" not in text
        ]
        if len(positions) != 1:
            return None
        candidates.append((positions[0], len(cells)))
    return candidates[0] if len(candidates) == 1 else None


def _extract_table_value(rows: list[tuple[str, ...]], exact_label: str,
                         code: str, month_col: int, header_columns: int) -> Decimal | None:
    # Require exact group and commodity code, same number of cells as the
    # identified Table-1 header and extraction from its SA MoM column only.
    matches: list[Decimal] = []
    for cells in rows:
        if len(cells) < 3 or cells[0].casefold() != exact_label.casefold():
            continue
        if cells[1:3] != ("FD", code):
            continue
        if len(cells) != header_columns or month_col >= len(cells):
            return None
        monthly = _decimal(cells[month_col])
        if monthly is None:
            return None
        matches.append(monthly)
    return matches[0] if len(matches) == 1 else None


def inspect_ppi_oct2026_first_print_lab(*, raw_html: Any,
        receipt: Any, as_of_utc: Any) -> dict[str, Any]:
    """Extract documented SA MoM October 2026 values only from a candidate HTML."""
    now = _utc(as_of_utc)
    if now is None:
        return _empty("INVALID_AS_OF_CLOCK")
    if now < RELEASE_UTC:
        return _empty("WAIT_SCHEDULED_RELEASE", "LAB_WAIT_BLS_PPI_OCT2026_RELEASE")
    if raw_html is None or receipt is None:
        return _empty("WAIT_ARCHIVED_OFFICIAL_PPI_SOURCE", "LAB_WAIT_BLS_PPI_OCT2026_DOCUMENT")
    if not isinstance(receipt, ClaimedPostReleaseHTTP):
        return _empty("INVALID_POST_RELEASE_SOURCE_METADATA")
    start, end = _utc(receipt.started_utc), _utc(receipt.finished_utc)
    if (receipt.source_url != OFFICIAL_URL
            or type(receipt.status_code) is not int or receipt.status_code != 200
            or not isinstance(receipt.content_type, str)
            or receipt.content_type.split(";")[0].strip().lower() != "text/html"
            or start is None or end is None
            or not RELEASE_UTC <= start <= end <= now
            or (end - start).total_seconds() > 180):
        return _empty("SOURCE_STATUS_OR_CHRONOLOGY_NOT_ACCEPTABLE")
    if (not isinstance(raw_html, bytes)
            or not 150 <= len(raw_html) <= MAX_BYTES
            or not isinstance(receipt.raw_sha256, str)
            or not _SHA.fullmatch(receipt.raw_sha256)
            or sha256(raw_html).hexdigest() != receipt.raw_sha256):
        return _empty("RAW_BODY_SIZE_OR_DIGEST_MISMATCH")
    decoded = raw_html.decode("utf-8", "surrogateescape")
    bad_bytes = sum(0xDC80 <= ord(ch) <= 0xDCFF for ch in decoded)
    if bad_bytes > MAX_NON_UTF8_BYTES:
        return _empty("EXCESS_INVALID_UTF8_SOURCE_BYTES")
    try:
        doc = _BlsTables()
        doc.feed(decoded)
        doc.close()
        if doc._active is not None or doc._cell is not None or doc._row is not None:
            return _empty("UNFINISHED_HTML_TABLE")
    except (TypeError, ValueError, RecursionError, OverflowError):
        return _empty("INVALID_OR_UNPARSABLE_HTML_TABLE")
    text = " ".join(" ".join(doc.text_chunks).split())
    for mandatory in (
        "PRODUCER PRICE INDEXES - OCTOBER 2026",
        "Friday, November 13, 2026",
        "Producer Price Index for final demand",
    ):
        if mandatory.casefold() not in text.casefold():
            return _empty("WRONG_PPI_RELEASE_ID_OR_TARGET_PERIOD")
    heads = _HEADLINE.findall(text)
    if len(heads) != 1:
        return _empty("HEADLINE_PPI_MONTHLY_TEXT_NOT_EXACTLY_IDENTIFIED")
    action, number = heads[0]
    headline = _decimal(number)
    if headline is None:
        return _empty("HEADLINE_PPI_PERCENT_INVALID")
    if action.lower() in {"decreased", "declined", "fell"}:
        headline = -headline
    table1 = [rows for context, rows in doc.tables
              if "Table 1." in context and "October 2026" in context
              and "seasonally adjusted" in context.lower()]
    if len(table1) != 1:
        return _empty("MONTHLY_SA_TABLE1_MISSING_OR_AMBIGUOUS")
    rows = table1[0]
    monthly_header = _oct2026_sa_month_column(rows)
    if monthly_header is None:
        return _empty("MONTHLY_SA_TABLE1_COLUMN_HEADER_MISSING_OR_AMBIGUOUS")
    month_col, header_columns = monthly_header
    table_head = _extract_table_value(rows, "Final demand", "4",
                                      month_col, header_columns)
    table_core = _extract_table_value(rows, "Final demand less foods and energy", "49104",
                                      month_col, header_columns)
    if table_head is None or table_core is None or table_head != headline:
        return _empty("MONTHLY_SA_TABLE1_SERIES_MISSING_OR_HEADLINE_MISMATCH")
    out = _empty("LOCAL_DOCUMENTARY_BLS_PPI_TABLE1_EXTRACT_NOT_SOURCE_AUTHENTICATION",
                 "LAB_PPI_OCT2026_BLS_TABLE1_BODY_VALUES_UNATTESTED")
    out.update({
        "source_sha256": receipt.raw_sha256,
        "source_capture_claim_utc": end.isoformat(),
        "headline_final_demand_sa_mom_pct_body_claim": str(table_head),
        "core_ex_food_energy_sa_mom_pct_body_claim": str(table_core),
    })
    return out


def compare_ppi_actual_to_frozen_consensus_lab(*, actual: Any,
        td_snapshot: Any, te_snapshot: Any) -> dict[str, Any]:
    """Research-only arithmetic across two locked pre-release source claims."""
    if not isinstance(actual, dict):
        return _empty("NO_ACTUAL_REPORT")
    if actual.get("state") != "LAB_PPI_OCT2026_BLS_TABLE1_BODY_VALUES_UNATTESTED":
        return _empty("NO_ACCEPTED_FIRST_PRINT_CANDIDATE")
    # A fabricated report dict can never serve as source authentication.
    # Require the shape and order produced by the actual-document guard.
    try:
        captured = _utc(datetime.fromisoformat(actual["source_capture_claim_utc"]))
    except (KeyError, TypeError, ValueError, OverflowError):
        captured = None
    actual_hash = actual.get("source_sha256")
    if (actual.get("official_source_url") != OFFICIAL_URL
            or captured is None or captured < RELEASE_UTC
            or not isinstance(actual_hash, str) or _SHA.fullmatch(actual_hash) is None):
        return _empty("ACTUAL_DOCUMENT_PROVENANCE_CLAIM_INCOMPLETE")
    if not isinstance(td_snapshot, dict) or not isinstance(te_snapshot, dict):
        return _empty("MISSING_PRE_EVENT_SNAPSHOTS")
    expected = (
        (td_snapshot, "LAB_PRE_EVENT_PPI_CONSENSUS_ARCHIVED_LOCAL_NO_TRADE",
         "source_body_sha256", "5f9d9eb128e5a3763ec6a3081bee7ba8c248a665a9d50e0ee132e9cbe037a42a"),
        (te_snapshot, "LAB_TE_PRE_EVENT_CONSENSUS_AND_OWN_FORECAST_DISTINGUISHED",
         "source_sha256", "175c163514590db8e2ddd651f0c9865bd2eed298211f92072549233f670e23c0"),
    )
    for item, state, field, digest in expected:
        if item.get("state") != state or item.get(field) != digest:
            return _empty("PRE_EVENT_LOCK_STATE_OR_HASH_MISMATCH")
    try:
        if (td_snapshot.get("headline_consensus_mom_pct") != te_snapshot.get("headline_consensus_mom_pct")
                or td_snapshot.get("core_consensus_mom_pct") != te_snapshot.get("core_consensus_mom_pct")):
            return _empty("PRE_EVENT_CONSENSUS_CONFLICT")
        h_consensus = _decimal(td_snapshot["headline_consensus_mom_pct"])
        c_consensus = _decimal(td_snapshot["core_consensus_mom_pct"])
        h_actual = _decimal(actual["headline_final_demand_sa_mom_pct_body_claim"])
        c_actual = _decimal(actual["core_ex_food_energy_sa_mom_pct_body_claim"])
        if None in (h_consensus, c_consensus, h_actual, c_actual):
            return _empty("PPI_METRIC_NUMBER_INVALID")
    except (KeyError, TypeError, InvalidOperation):
        return _empty("PPI_METRIC_FIELD_MISSING_OR_INVALID")
    out = _empty("ARITHMETIC_DOCUMENTARY_NOT_DIRECTION_OR_PROBABILITY",
                 "LAB_PPI_RESEARCH_SURPRISE_ONLY_UNATTESTED")
    out.update({
        "headline_final_demand_sa_mom_pct_body_claim": str(h_actual),
        "core_ex_food_energy_sa_mom_pct_body_claim": str(c_actual),
        "headline_vs_td_pre_event_diff_pp": str(h_actual - h_consensus),
        "core_vs_td_pre_event_diff_pp": str(c_actual - c_consensus),
    })
    return out