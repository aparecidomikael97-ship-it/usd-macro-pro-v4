"""Offline NY Fed September 2026 SME reader: October FOMC context only.

The spreadsheet's `survey_release_date` is the *questionnaire distribution*
date (2 Sep), NOT the publication date of survey results. The NY Fed says
results post one business day after FOMC minutes (Sep minutes: 7 Oct); 8 Oct
is therefore an INFERENCE, not independently witnessed historic availability.
No network, paid feeds, signal, backtest authorization, broker or scheduler.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO
import re
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

SCHEMA = "ATLASQUANT_TRADER_NYFED_SME_SEP2026_OCTFOMC_LAB_V1"
SOURCE_URL = (
    "https://www.newyorkfed.org/medialibrary/media/markets/survey/"
    "2026/sep-2026-data.xlsx"
)
MAX_XLSX_BYTES = 2 * 1024 * 1024
MAX_SHEET_XML_BYTES = 7 * 1024 * 1024
MAX_ROWS = 5_000
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
HEADERS = (
    "survey_release_date", "survey_due_date", "panel_type",
    "spd_question_number", "theme", "subject_group", "subject",
    "question_type", "question_mode", "question_text", "question_tag",
    "value_tag", "top_header_value", "left_header_value", "horizon",
    "horizon_date", "bucket_range", "bucket_low", "bucket_high",
    "aggregation", "aggregation_value",
)
VALUE_TAG = "fftr_pathofmodes_20261028"
ROW_METADATA = {
    "A": "2026-09-02",  # questionnaire distributed, NOT results release
    "B": "2026-09-08",  # responses due, NOT results release
    "C": "Combined", "D": "2a", "E": "rate_policy_expectations",
    "F": "fed_funds_target_range", "G": "fed_funds_target_range",
    "H": "path_of_modes", "I": "levels", "K": "fftr_pathofmodes",
    "L": VALUE_TAG, "O": "Oct. 27-28 2026", "P": "2026-10-28",
}
AGGS = frozenset(("count", "pctl25", "pctl50", "pctl75"))


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "currency": "USD", "source_id": "NYFED_SME_SEPTEMBER_2026",
        "source_url": SOURCE_URL, "source_raw_sha256": None,
        "source_bytes": None,
        "questionnaire_distributed_on": None,
        "responses_due_on": None,
        "results_release_date_inferred_from_minutes_rule": "2026-10-08",
        "minutes_date_verified_from_fed_release": "2026-10-07",
        "results_publication_date_independently_verified": False,
        "results_publication_instant_independently_verified": False,
        "historical_survey_vintage_independently_verified": False,
        "survey_meeting_end_date": None,
        "median_target_range_midpoint_pct": None,
        "pctl25_target_range_midpoint_pct": None,
        "pctl75_target_range_midpoint_pct": None,
        "respondents_in_question": None,
        "aggregation_is_median_of_modal_point_forecasts": False,
        "meeting_consensus_public_before_event_verified": False,
        "historical_point_in_time_eligible": False,
        "market_surprise_bps": None, "fx_bias": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "can_feed_live_radar": False, "publishable": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "new_cost_brl": 0,
    }


def _cell(c: ET.Element | None, *, numeric: bool = False) -> str:
    if c is None or c.find(NS + "f") is not None:
        raise ValueError("missing cell or formula")
    if numeric:
        if c.get("t") not in ("n", None):
            raise ValueError("expected literal numeric cell")
        node = c.find(NS + "v")
        if node is None or node.text is None:
            raise ValueError("missing numeric value")
        return node.text
    if c.get("t") != "inlineStr":
        raise ValueError("expected inline literal text")
    node = c.find(NS + "is")
    if node is None:
        raise ValueError("missing inline text")
    return "".join(t.text or "" for t in node.iter(NS + "t"))


def _decimal(text: str, *, count: bool = False) -> Decimal:
    if not re.fullmatch(r"(?:0|[1-9][0-9]{0,2})(?:\.[0-9]{1,8})?", text):
        raise ValueError("unexpected numeric form")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("invalid number") from exc
    if (count and (value != value.to_integral_value() or not 1 <= value <= 100)
            or not count and not Decimal("0") <= value <= Decimal("0.20")):
        raise ValueError("unexpected value range")
    return value


def inspect_nyfed_sme_sep2026_oct_meeting_lab(
    raw: Any, *, captured_at_utc: datetime, as_of_utc: datetime,
    requested_meeting_end_date: str = "2026-10-28",
) -> dict[str, Any]:
    """Read four exact rows; never assert a public pre-October vintage.

    The XLSX aggregation_value is a *fraction*, e.g. 0.0363 = 3.63%,
    NOT a rate in percent, a range endpoint, or the realized FOMC target.
    """
    out = _deny("XLSX_REJECTED")
    capture = (captured_at_utc.astimezone(timezone.utc)
               if isinstance(captured_at_utc, datetime)
               and captured_at_utc.tzinfo is not None
               and captured_at_utc.utcoffset() is not None else None)
    as_of = (as_of_utc.astimezone(timezone.utc)
             if isinstance(as_of_utc, datetime)
             and as_of_utc.tzinfo is not None
             and as_of_utc.utcoffset() is not None else None)
    if (capture is None or as_of is None or capture > as_of
            or requested_meeting_end_date != "2026-10-28"
            or not isinstance(raw, bytes)
            or not 1 <= len(raw) <= MAX_XLSX_BYTES):
        return out
    try:
        with ZipFile(BytesIO(raw)) as zipf:
            infos = zipf.infolist()
            names = [i.filename for i in infos]
            if (len(names) > 60 or len(names) != len(set(names))
                    or any(name.startswith("/") or ".." in name.split("/")
                           or "\\" in name for name in names)
                    or any(i.file_size > MAX_SHEET_XML_BYTES for i in infos)
                    or not {"xl/workbook.xml", "xl/worksheets/sheet1.xml"}.issubset(names)):
                return out
            workbook = ET.fromstring(zipf.read("xl/workbook.xml"))
            sheetnames = [e.get("name") for e in workbook.findall(f"{NS}sheets/{NS}sheet")]
            if sheetnames != ["Sheet1"]:
                return out
            xml = zipf.read("xl/worksheets/sheet1.xml")
            if not 100 <= len(xml) <= MAX_SHEET_XML_BYTES:
                return out
            root = ET.fromstring(xml)
            if root.tag != NS + "worksheet":
                return out
            rows = root.findall(f"{NS}sheetData/{NS}row")
            if not 2 <= len(rows) <= MAX_ROWS:
                return out
            evidence: dict[str, Decimal] = {}
            found_rows = 0
            for idx, row in enumerate(rows, start=1):
                if row.get("r") != str(idx):
                    raise ValueError("duplicate or missing spreadsheet row")
                cells: dict[str, ET.Element] = {}
                for c in row.findall(NS + "c"):
                    coordinate = c.get("r", "")
                    matched = re.fullmatch(r"([A-U])([1-9][0-9]*)", coordinate)
                    if not matched or int(matched.group(2)) != idx:
                        raise ValueError("invalid cell position")
                    col = matched.group(1)
                    if col in cells:
                        raise ValueError("duplicate cell")
                    cells[col] = c
                if idx == 1:
                    actual = tuple(_cell(cells.get(chr(ord("A") + j))) for j in range(21))
                    if actual != HEADERS:
                        raise ValueError("schema drift in header")
                    continue
                if "L" not in cells or _cell(cells["L"]) != VALUE_TAG:
                    continue
                panel = _cell(cells.get("C"))
                if panel not in ("Combined", "Dealer", "Participant"):
                    raise ValueError("unknown survey panel")
                if panel != "Combined":
                    # A second and third set of the same value tags exists
                    # for Dealers and Participants. Never triple-count those.
                    continue
                found_rows += 1
                for col, expected in ROW_METADATA.items():
                    if _cell(cells.get(col)) != expected:
                        raise ValueError("mixed survey or meeting horizon")
                agg = _cell(cells.get("T"))
                if agg not in AGGS or agg in evidence:
                    raise ValueError("duplicate or unexpected aggregation")
                evidence[agg] = _decimal(_cell(cells.get("U"), numeric=True),
                                         count=(agg == "count"))
            if found_rows != 4 or set(evidence) != AGGS:
                out["reason"] = "EXPECTED_FOMC_MEDIAN_ROWS_MISSING"
                return out
            if not evidence["pctl25"] <= evidence["pctl50"] <= evidence["pctl75"]:
                out["reason"] = "SURVEY_PERCENTILES_NOT_MONOTONIC"
                return out

            pct = lambda n: format(evidence[n] * 100, ".2f")
            out.update({
                "state": "LAB_USD_OCTOBER_MEETING_SURVEY_CONTEXT_UNVERIFIED",
                "reason": "QUESTIONNAIRE_DATE_NOT_RESULTS_RELEASE_OR_PIT_PROOF",
                "source_raw_sha256": sha256(raw).hexdigest(),
                "source_bytes": len(raw),
                "questionnaire_distributed_on": "2026-09-02",
                "responses_due_on": "2026-09-08",
                "survey_meeting_end_date": "2026-10-28",
                "median_target_range_midpoint_pct": pct("pctl50"),
                "pctl25_target_range_midpoint_pct": pct("pctl25"),
                "pctl75_target_range_midpoint_pct": pct("pctl75"),
                "respondents_in_question": int(evidence["count"]),
                "aggregation_is_median_of_modal_point_forecasts": True,
                "captured_at_utc": capture.isoformat(),
            })
            return out
    except (BadZipFile, ET.ParseError, OSError, ValueError, KeyError,
            IndexError, OverflowError, RuntimeError):
        return out


__all__ = ["SCHEMA", "SOURCE_URL", "HEADERS",
           "inspect_nyfed_sme_sep2026_oct_meeting_lab"]
