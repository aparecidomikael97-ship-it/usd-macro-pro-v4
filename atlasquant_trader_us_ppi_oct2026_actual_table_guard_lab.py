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


def _strict_span(attrs: list, name: str) -> int:
    # Never infer a column when HTML declares malformed/duplicate spans.
    values = [v for k, v in attrs if k == name]
    if len(values) > 1:
        raise ValueError("DUPLICATED_TABLE_SPAN")
    raw = values[0] if values else "1"
    if not isinstance(raw, str) or re.fullmatch(r"[1-9][0-9]?", raw) is None:
        raise ValueError("INVALID_TABLE_SPAN")
    value = int(raw)
    if value > 32:
        raise ValueError("OVERSIZED_TABLE_SPAN")
    return value


class _BlsTables(HTMLParser):
    """Record table captions/preceding heading and row cells (not page regex)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_chunks: list[str] = []
        self.tables: list[tuple[str, list[tuple[str, ...]]]] = []
        # Parallel table layout, retaining TH/TD and rowspan/colspan metadata.
        self.table_layouts: list[list[tuple[tuple[str, str, int, int], ...]]] = []
        self._active_layout: list[tuple[tuple[str, str, int, int], ...]] | None = None
        self._row_layout: list[tuple[str, str, int, int]] | None = None
        self._cell_layout: tuple[str, int, int] | None = None
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
            self._active_layout = []
            self._scope = " ".join(self._outside_since_last_table)[-1800:]
            self._outside_since_last_table = []
        elif tag == "tr" and self._active is not None:
            if self._row is not None:
                raise ValueError("NESTED_ROW")
            self._row = []
            self._row_layout = []
        elif tag in {"td", "th"} and self._row is not None:
            if self._cell is not None:
                raise ValueError("NESTED_CELL")
            self._cell = []
            self._cell_layout = (tag, _strict_span(attrs, "rowspan"),
                                 _strict_span(attrs, "colspan"))

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
            cell_text = " ".join(" ".join(self._cell).split())
            self._row.append(cell_text)
            if self._row_layout is None or self._cell_layout is None:
                raise ValueError("MISSING_TABLE_CELL_LAYOUT")
            tag_name, row_span, col_span = self._cell_layout
            self._row_layout.append((cell_text, tag_name, row_span, col_span))
            self._cell = None
            self._cell_layout = None
        elif tag == "tr" and self._row is not None:
            if self._cell is not None:
                raise ValueError("UNCLOSED_CELL")
            self._active.append(tuple(self._row))  # type: ignore[union-attr]
            if self._active_layout is None or self._row_layout is None:
                raise ValueError("MISSING_TABLE_ROW_LAYOUT")
            self._active_layout.append(tuple(self._row_layout))
            self._row_layout = None
            self._row = None
        elif tag == "table" and self._active is not None:
            if self._row is not None or self._cell is not None:
                raise ValueError("UNCLOSED_TABLE")
            if self._active_layout is None:
                raise ValueError("MISSING_TABLE_LAYOUT")
            self.tables.append((" ".join(self._scope.split()), self._active))
            self.table_layouts.append(self._active_layout)
            self._active_layout = None
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
    r"\bsep(?:t(?:ember)?)?[.]?\s+to\s+oct(?:ober)?[.]?\b", re.I
)
_SEASONAL = re.compile(r"\bsa\b|\bseasonally\s+adjusted\b", re.I)


def _bls_implicit_oct2026_sa_month_column(
        layout_rows: list[tuple[tuple[str, str, int, int], ...]]
        ) -> tuple[int, int] | None:
    """Strictly recognize the *actual* BLS Table-1 implicit header layout.

    The BLS September 2026 publication has five top-level <th> cells
    (Grouping, Commodity code, Relative importance, Unadjusted 12-month,
    Seasonally adjusted 1-month), eight <th> cells in its second row and
    TEN physical data cells, WITHOUT rowspan/colspan HTML attributes.
    The monthly month-span must be derived from the exact lower header,
    never assumed to be the last number in the row.
    This is a fixed known-source grammar, not a generic guess about widths.
    """
    if len(layout_rows) < 2:
        return None
    top, lower = layout_rows[:2]
    if len(top) != 5 or len(lower) != 8:
        return None
    if any(tag != "th" or row_span != 1 or col_span != 1
           for cells in (top, lower)
           for _, tag, row_span, col_span in cells):
        return None
    parent = [" ".join(text.split()).casefold() for text, _, _, _ in top]
    child = [" ".join(text.split()).casefold() for text, _, _, _ in lower]
    if not (parent[0] == "grouping"
            and parent[1] == "commodity code"
            and "relative" in parent[2] and "importance" in parent[2]
            and "unadjusted" in parent[3] and "12-month" in parent[3]
            and "percent change" in parent[3]
            and "seasonally adjusted" in parent[4]
            and "1-month" in parent[4] and "percent change" in parent[4]):
        return None
    if not (child[0] == "group code" and child[1] == "item code"
            and "to" in child[2] and "2026" in child[2]):
        return None
    # Index 3..7 of the lower header are the five SA monthly subcolumns;
    # physical data index = lower index + 2 (two label/commodity columns).
    monthly_children = child[3:]
    if any("to" not in label or "2025" in label
           for label in monthly_children):
        return None
    matches = [index for index, label in enumerate(monthly_children)
               if _MONTH_TO_MONTH.search(label)]
    if matches != [4]:
        return None
    return (3 + matches[0] + 2, 10)


def _oct2026_sa_month_column(
        layout_rows: list[tuple[tuple[str, str, int, int], ...]]
        ) -> tuple[int, int] | None:
    """Resolve a monthly column across real BLS multi-row TH headers.

    Official BLS HTML uses either implicit two-row group labels without
    colspan/rowspan attributes, or explicit spans; treat these as separate
    strict grammars. Never guess from the last numeric cell.
    """
    implicit = _bls_implicit_oct2026_sa_month_column(layout_rows)
    if implicit is not None:
        return implicit
    header_grid: list[tuple[str, ...]] = []
    carry: dict[int, tuple[str, int]] = {}
    for cells in layout_rows:
        if not cells:
            continue
        if not any(tag == "th" for _, tag, _, _ in cells):
            break
        if any(tag != "th" for _, tag, _, _ in cells):
            # In BLS real data, grouping/title rows may contain both
            # <th> labels and <td> blanks after the header.
            if not header_grid:
                return None
            break
        populated = {idx: text for idx, (text, _) in carry.items()}
        next_carry = {idx: (text, remaining - 1)
                      for idx, (text, remaining) in carry.items()
                      if remaining > 1}
        pos = 0
        for text, _, row_span, col_span in cells:
            while pos in populated:
                pos += 1
            if pos + col_span > 32:
                return None
            for idx in range(pos, pos + col_span):
                if idx in populated:
                    return None
                populated[idx] = text
                if row_span > 1:
                    next_carry[idx] = (text, row_span - 1)
            pos += col_span
        if not populated or len(populated) != max(populated) + 1:
            return None
        header_grid.append(tuple(populated[idx]
                                 for idx in range(max(populated) + 1)))
        if len(header_grid) > 10:
            return None
        carry = next_carry
    if not header_grid or carry or any(len(row) != len(header_grid[0])
                                        for row in header_grid):
        return None
    width = len(header_grid[0])
    if not 7 <= width <= 32:
        return None
    labels = [" ".join(row[col] for row in header_grid)
              for col in range(width)]
    if "grouping" not in labels[0].casefold() or "commodity code" not in labels[1].casefold():
        return None
    candidates = [idx for idx, label in enumerate(labels)
                  if _MONTH_TO_MONTH.search(label)
                  and _SEASONAL.search(label)
                  and "2025" not in label
                  and idx >= 3]
    if len(candidates) != 1:
        return None
    return (candidates[0], width)

def _strip_bls_label_footnotes(label: str) -> str:
    # Real BLS Table 1 includes superscript citations e.g. "(5)" in the
    # FD/49104 row. Remove only trailing numbered footnotes, not words,
    # before checking the full series name AND the FD commodity code.
    return re.sub(r"(?:\s*\([0-9]{1,2}\))+\s*$", "", label).strip().casefold()


def _extract_table_value(rows: list[tuple[str, ...]], exact_label: str,
                         code: str, month_col: int, header_columns: int) -> Decimal | None:
    # Require exact group and commodity code, same number of cells as the
    # identified Table-1 header and extraction from its SA MoM column only.
    matches: list[Decimal] = []
    for cells in rows:
        if len(cells) < 3 or _strip_bls_label_footnotes(cells[0]) != exact_label.casefold():
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
    table1 = [(rows, doc.table_layouts[index])
              for index, (context, rows) in enumerate(doc.tables)
              if "Table 1." in context and "October 2026" in context
              and "seasonally adjusted" in context.lower()]
    if len(table1) != 1:
        return _empty("MONTHLY_SA_TABLE1_MISSING_OR_AMBIGUOUS")
    rows, layout_rows = table1[0]
    monthly_header = _oct2026_sa_month_column(layout_rows)
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