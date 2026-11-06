"""Research-only, offline reader of Atlanta Fed MPT historical XLSX bytes.

The source workbook's LICENSE drawing limits data use to personal/educational
purposes. DO NOT redistribute data or use in a commercial AtlasQuant product.
MPT estimates a quarterly average SOFR distribution from options, NOT a Fed
target-rate consensus or the FOMC's announcement surprise. The downloaded
historical workbook is not an independently witnessed point-in-time vintage.
No HTTP, disk writes, orders, scheduler, or live-radar integration.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO
import re
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

SCHEMA = "ATLASQUANT_TRADER_US_MPT_HISTORY_XLSX_LAB_V1"
MAX_XLSX_BYTES = 10 * 1024 * 1024
MAX_DATA_XML_BYTES = 85 * 1024 * 1024
MAX_SHARED_XML_BYTES = 4 * 1024 * 1024
MAX_ROWS = 350_000
SOURCE_URL = ("https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/"
              "Documents/research-and-data/data/market-probability-tracker/"
              "mpt_histdata.xlsx")
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
ALLOWED_FIELDS = frozenset({
    "Rate: mean", "Rate: mode", "Rate: 25th percentile",
    "Rate: 75th percentile", "Prob: cut", "Prob: hike",
})
RATE_FIELDS = frozenset(f for f in ALLOWED_FIELDS if f.startswith("Rate:"))
DAY_RE = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}\Z")
RANGE_RE = re.compile(r"([0-9]{1,4})bps - ([0-9]{1,4})bps\Z")


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "source": "ATLANTA_FED_MPT_HISTORICAL_XLSX", "currency": "USD",
        "source_url": SOURCE_URL, "source_raw_sha256": None,
        "observation_date": None, "reference_start": None,
        "latest_observation_date_in_file": None,
        "fomc_target_range_on_observation_date_bps": None,
        "quarterly_sofr_implied_statistics": None,
        "metric_is_fomc_target_consensus": False,
        "historical_public_availability_witnessed": False,
        "source_origin_independently_authenticated": False,
        "commercial_reuse_authorized": False,
        "license_personal_educational_only": True,
        "pre_event_consensus_verified": False,
        "market_surprise_bps": None, "fx_bias": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "can_feed_live_radar": False, "publishable": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "new_cost_brl": 0,
    }


def _parse_day(s: Any) -> date | None:
    if not isinstance(s, str) or not DAY_RE.fullmatch(s):
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _strings(xml_bytes: bytes) -> list[str]:
    root = ET.fromstring(xml_bytes)
    if root.tag != NS + "sst":
        raise ValueError("sharedStrings root changed")
    values = []
    for item in root.findall(NS + "si"):
        # Rich text and plain text both concatenate the <t> children.
        values.append("".join((t.text or "") for t in item.iter(NS + "t")))
        if len(values) > 100_000:
            raise ValueError("too many shared strings")
    return values


def _shared(cell: ET.Element, values: list[str]) -> str:
    if cell.attrib.get("t") != "s" or cell.find(NS + "f") is not None:
        raise ValueError("expected literal shared string")
    node = cell.find(NS + "v")
    if node is None or node.text is None or not node.text.isascii() or not node.text.isdecimal():
        raise ValueError("invalid shared string index")
    return values[int(node.text)]


def _range(text: str) -> str:
    match = RANGE_RE.fullmatch(text)
    if not match or int(match[2]) - int(match[1]) not in (0, 25):
        raise ValueError("invalid target range")
    return text


def _serial_day(cell: ET.Element) -> date:
    if cell.attrib.get("t") not in (None, "n") or cell.find(NS + "f") is not None:
        raise ValueError("reference start must be a numeric Excel date")
    node = cell.find(NS + "v")
    text = node.text if node is not None else None
    if not isinstance(text, str) or not text.isascii() or not text.isdecimal():
        raise ValueError("Excel serial must be integral")
    serial = int(text)
    if not 40_000 <= serial <= 60_000:
        raise ValueError("Excel reference date out of range")
    return date(1899, 12, 30) + timedelta(days=serial)


def _number(text: str, field: str) -> str:
    if not re.fullmatch(r"\s*[0-9]{1,4}(?:\.[0-9]{1,4})?\s*", text):
        raise ValueError("invalid decimal statistic")
    try:
        number = Decimal(text.strip())
    except InvalidOperation as exc:
        raise ValueError("invalid decimal statistic") from exc
    if (field in RATE_FIELDS and not 0 <= number <= 2000
            or field not in RATE_FIELDS and not 0 <= number <= 100):
        raise ValueError("statistic outside expected units")
    return str(number)


def inspect_atlantafed_mpt_history_lab(
    raw: Any, *, observed_at_utc: datetime,
    requested_observation_date: str, requested_reference_start: str,
) -> dict[str, Any]:
    """Extract only selected research metadata; no PIT or trading eligibility.

    The user-supplied observed clock and workbook hash don't establish the
    publication date or that these values were available on the row's date.
    """
    out = _deny("XLSX_REJECTED")
    at = observed_at_utc
    today = (at.astimezone(timezone.utc).date() if isinstance(at, datetime)
             and at.tzinfo is not None and at.utcoffset() is not None else None)
    chosen = _parse_day(requested_observation_date)
    reference = _parse_day(requested_reference_start)
    if (today is None or chosen is None or reference is None or chosen > today
            or not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_XLSX_BYTES):
        return out
    try:
        with ZipFile(BytesIO(raw)) as archive:
            members = archive.infolist()
            names = [item.filename for item in members]
            if (len(members) > 60 or len(names) != len(set(names))
                    or any(name.startswith("/") or ".." in name.split("/")
                           or "\\" in name for name in names)):
                return out
            required = {
                "xl/workbook.xml", "xl/sharedStrings.xml",
                "xl/worksheets/sheet3.xml", "xl/drawings/drawing1.xml",
            }
            if not required.issubset(names):
                return out
            xml_size = archive.getinfo("xl/worksheets/sheet3.xml").file_size
            str_size = archive.getinfo("xl/sharedStrings.xml").file_size
            if (not 10 <= xml_size <= MAX_DATA_XML_BYTES
                    or not 10 <= str_size <= MAX_SHARED_XML_BYTES
                    or archive.getinfo("xl/drawings/drawing1.xml").file_size > 80_000):
                return out
            wb = ET.fromstring(archive.read("xl/workbook.xml"))
            sheet_names = [e.get("name") for e in wb.findall(f"{NS}sheets/{NS}sheet")]
            if sheet_names != ["LICENSE", "DICTIONARY", "DATA"]:
                return out
            drawing = ET.fromstring(archive.read("xl/drawings/drawing1.xml"))
            terms = " ".join((e.text or "") for e in drawing.iter()
                             if e.tag.endswith("}t")).lower()
            if "personal and educational purposes only" not in terms:
                out["reason"] = "LICENSE_RESTRICTION_NOT_READABLE"
                return out
            strings = _strings(archive.read("xl/sharedStrings.xml"))
            if not strings:
                return out

            count = 0
            earliest: date | None = None
            latest: date | None = None
            fields: dict[str, str] = {}
            target_on_date: str | None = None
            with archive.open("xl/worksheets/sheet3.xml") as data_stream:
                for _, row in ET.iterparse(data_stream, events=("end",)):
                    if row.tag != NS + "row":
                        continue
                    count += 1
                    if count > MAX_ROWS:
                        raise ValueError("data row budget exceeded")
                    cells = {re.sub(r"[0-9]+\Z", "", c.get("r", "")): c
                             for c in row.findall(NS + "c")}
                    if set(cells) != set("ABCDE"):
                        raise ValueError("unrecognized data columns")
                    if count == 1:
                        header = [_shared(cells[c], strings) for c in "ABCDE"]
                        if header != ["date", "reference_start", "target_range",
                                      "field", "value"]:
                            raise ValueError("unexpected data headers")
                    else:
                        day = _parse_day(_shared(cells["A"], strings))
                        if day is None or day > today:
                            raise ValueError("invalid or future observation date")
                        earliest = min(day, earliest) if earliest else day
                        latest = max(day, latest) if latest else day
                        if day == chosen and _serial_day(cells["B"]) == reference:
                            bound = _range(_shared(cells["C"], strings))
                            field = _shared(cells["D"], strings)
                            if field in ALLOWED_FIELDS:
                                if field in fields or (target_on_date and target_on_date != bound):
                                    raise ValueError("duplicate or mixed target-range research records")
                                target_on_date = bound
                                fields[field] = _number(_shared(cells["E"], strings), field)
                    row.clear()
            if count <= 1 or not fields or "Rate: mean" not in fields:
                out["reason"] = "REQUESTED_SOFR_RESEARCH_WINDOW_UNAVAILABLE"
                return out
            out.update({
                "state": "LAB_MPT_QUARTERLY_SOFR_RESEARCH_ONLY",
                "reason": "LICENSE_AND_HISTORICAL_VINTAGE_RESTRICTED",
                "source_raw_sha256": sha256(raw).hexdigest(),
                "observation_date": chosen.isoformat(),
                "reference_start": reference.isoformat(),
                "latest_observation_date_in_file": latest.isoformat() if latest else None,
                "first_observation_date_in_file": earliest.isoformat() if earliest else None,
                "data_rows_inspected": count - 1,
                "fomc_target_range_on_observation_date_bps": target_on_date,
                "quarterly_sofr_implied_statistics": fields,
                "collection_clock_utc": at.astimezone(timezone.utc).isoformat(),
            })
            return out
    except (BadZipFile, OSError, ET.ParseError, KeyError, ValueError,
            IndexError, OverflowError, RuntimeError):
        return out


__all__ = ["inspect_atlantafed_mpt_history_lab", "SOURCE_URL", "SCHEMA"]


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Offline personal MPT XLSX audit; no network")
    parser.add_argument("--file", required=True, help="private local XLSX evidence")
    parser.add_argument("--observation", required=True, help="YYYY-MM-DD")
    parser.add_argument("--reference-start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--confirm-personal-lab-read", action="store_true")
    args = parser.parse_args()
    if not args.confirm_personal_lab_read:
        parser.error("explicit --confirm-personal-lab-read required")
    report = inspect_atlantafed_mpt_history_lab(
        Path(args.file).read_bytes(), observed_at_utc=datetime.now(timezone.utc),
        requested_observation_date=args.observation,
        requested_reference_start=args.reference_start,
    )
    # Output metadata only: do not print or republish licensed rate values.
    public = {k: v for k, v in report.items()
              if k != "quarterly_sofr_implied_statistics"}
    public["research_statistic_fields_present"] = sorted(
        (report.get("quarterly_sofr_implied_statistics") or {}).keys())
    print(json.dumps(public, ensure_ascii=False, sort_keys=True))
