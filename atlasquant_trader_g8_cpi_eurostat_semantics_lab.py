"""Read one locally archived Eurostat FLASH page as documentary LAB evidence.

Only same-document semantic consistency is checked. A mutable web page, even
when hash-preserved after retrieval, is NOT a historical publisher vintage,
independently clock-attested event, calibrated forecast or tradable bias.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from typing import Any

from atlasquant_trader_g8_cpi_local_archive_lab import (
    verify_g8_cpi_current_archive_lab,
)

SCHEMA = "ATLASQUANT_EUR_CPI_EUROSTAT_FLASH_SEMANTICS_LAB_V1"
_MONTHS = {
    "January": "01", "February": "02", "March": "03", "April": "04",
    "May": "05", "June": "06", "July": "07", "August": "08",
    "September": "09", "October": "10", "November": "11", "December": "12",
}
_NUMBER = re.compile(r"(?:0|[1-9][0-9]?)(?:\.[0-9])?\Z")
_STAMP = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")


def _clean(s: str) -> str:
    return " ".join(s.replace("\xa0", " ").split())


class _EurostatHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, list[str]] = {}
        self.headings: list[str] = []
        self.labels: list[str] = []
        self.tables: list[list[list[str]]] = []
        self._captured: list[dict[str, Any]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "meta" and attr.get("property") and attr.get("content"):
            self.meta.setdefault(attr["property"], []).append(attr["content"])
        for item in self._captured:
            item["depth"] += 1
        cls = attr.get("class") or ""
        if tag == "h1":
            self._captured.append({"type": "headings", "depth": 1, "text": []})
        if tag == "span" and "ecl-label--highlight" in cls:
            self._captured.append({"type": "labels", "depth": 1, "text": []})
        if tag == "table" and self._table is None:
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        for item in self._captured:
            item["text"].append(data)
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append(_clean("".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._table is not None and self._row is not None:
            self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None
        for item in self._captured:
            item["depth"] -= 1
        completed = [x for x in self._captured if x["depth"] == 0]
        self._captured = [x for x in self._captured if x["depth"] > 0]
        for item in completed:
            getattr(self, item["type"]).append(_clean("".join(item["text"])))


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_EUR_CPI_SEMANTIC_BLOCKED", "reason": reason,
        "reference_period": None, "publication_stage": None,
        "documentary_cpi_yoy_percent": None, "documentary_previous_yoy_percent": None,
        "source_publication_timestamp_claim": None,
        "local_archive_integrity_verified": False,
        "same_document_value_consistent": False,
        "value_independently_verified": False,
        "issuer_first_release_authenticated": False,
        "clock_independently_authenticated": False,
        "historical_point_in_time_eligible": False,
        "can_feed_macro_bias": False, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "scheduler_enabled": False, "worker_enabled": False,
        "new_cost_brl": 0, "file_writes": 0,
    }


def _parsed_number(raw: str) -> Decimal | None:
    if not _NUMBER.fullmatch(raw):
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def interpret_eurostat_flash_html_lab(body: bytes, *, period: str) -> dict[str, Any]:
    """Pure parser of archived HTML, never a source/network or trading adapter."""
    out = _blocked("EUROSTAT_DOCUMENT_SEMANTIC_INCONSISTENCY")
    if not isinstance(body, bytes) or len(body) > 1_048_576 or not body:
        return out
    if not isinstance(period, str) or not re.fullmatch(r"20\d\d-(?:0[1-9]|1[0-2])", period):
        return out
    try:
        page = _EurostatHTML()
        page.feed(body.decode("utf-8", errors="strict"))
        page.close()
    except (UnicodeError, ValueError):
        return out

    month_re = "|".join(_MONTHS)
    labels = [re.fullmatch(rf"Flash estimate - ({month_re}) (20\d\d)", x)
              for x in page.labels]
    labels = [m for m in labels if m is not None]
    if len(labels) != 1:
        return out
    named_period = labels[0].group(2) + "-" + _MONTHS[labels[0].group(1)]
    if named_period != period:
        return out
    h1 = [re.fullmatch(r"Euro area annual inflation (?:up|down) to ([0-9]+(?:\.[0-9])?)%", h)
          for h in page.headings]
    h1 = [m for m in h1 if m is not None]
    if len(h1) != 1:
        return out
    title_value = _parsed_number(h1[0].group(1))

    ogs = page.meta.get("og:description", [])
    if len(ogs) != 1:
        return out
    og = re.search(
        rf"Euro area annual inflation is expected to be ([0-9]+(?:\.[0-9])?)% "
        rf"in ({month_re}) (20\d\d),.*?according to a flash estimate from Eurostat",
        _clean(ogs[0]), flags=re.I,
    )
    if not og or og.group(3) + "-" + _MONTHS.get(og.group(2).title(), "") != period:
        return out
    description_value = _parsed_number(og.group(1))

    matches: list[list[str]] = []
    for table in page.tables:
        for i, row in enumerate(table):
            if row and row[0] == "All-items HICP":
                # The first Eurostat component table is annual rate + last
                # monthly rate. Separate the two Oct columns by their headers.
                header = " ".join(" ".join(x) for x in table[:i])
                if ("Euro area annual inflation and its components" in header
                        and "Annual rate" in header and "Monthly rate" in header
                        and "Sept 26" in header and "Oct 26" in header):
                    matches.append(row)
    if len(matches) != 1 or len(matches[0]) != 10:
        return out
    row = matches[0]
    flash_cell = row[-2]
    if not flash_cell.endswith("e"):
        return out
    table_value = _parsed_number(flash_cell[:-1])
    previous_value = _parsed_number(row[-3].removesuffix("e"))
    if (None in (title_value, description_value, table_value, previous_value)
            or title_value != description_value or title_value != table_value):
        return out
    publication = page.meta.get("article:published_time", [])
    if len(publication) != 1 or not _STAMP.fullmatch(publication[0]):
        return out
    try:
        datetime.fromisoformat(publication[0].replace("Z", "+00:00"))
    except ValueError:
        return out
    out.update({
        "state": "LAB_EUR_CPI_FLASH_DOCUMENTARY_EXTRACTED_UNATTESTED",
        "reason": "SAME_DOCUMENT_CONSISTENCY_ONLY_NOT_RELEASE_OR_PIT_ATTESTATION",
        "reference_period": period, "publication_stage": "FLASH",
        "documentary_cpi_yoy_percent": str(title_value),
        "documentary_previous_yoy_percent": str(previous_value),
        "source_publication_timestamp_claim": publication[0],
        "same_document_value_consistent": True,
    })
    return out


def interpret_eurostat_flash_archive_lab(manifest_path: str | Path) -> dict[str, Any]:
    """Only reads pre-existing local files after verifier checks their SHA."""
    out = _blocked("ARCHIVE_INTEGRITY_OR_ISSUER_REQUIREMENTS_NOT_MET")
    check = verify_g8_cpi_current_archive_lab(manifest_path)
    if not check["local_integrity_verified"]:
        return out
    try:
        manifest = json.loads(Path(check["manifest_path"]).read_text(encoding="utf-8"))
        if (manifest.get("currency") != "EUR" or manifest.get("publication_stage_claim") != "FLASH"
                or manifest.get("content_type") != "text/html"
                or manifest.get("source_url") !=
                "https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-04112026-ap"
                or manifest.get("reference_period_claim") != "2026-10"):
            return out
        body = Path(check["body_path"]).read_bytes()
        result = interpret_eurostat_flash_html_lab(body, period=manifest["reference_period_claim"])
        result["local_archive_integrity_verified"] = True
        return result
    except (OSError, ValueError, TypeError, KeyError):
        return out


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python atlasquant_trader_g8_cpi_eurostat_semantics_lab.py <local-manifest.json>")
        return 2
    result = interpret_eurostat_flash_archive_lab(argv[1])
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["same_document_value_consistent"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
