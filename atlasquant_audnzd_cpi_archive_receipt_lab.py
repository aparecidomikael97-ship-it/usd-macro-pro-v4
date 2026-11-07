"""Verify two archived CPI documents for an AUD/NZD research receipt.

LAB only. The pinned digests prove the supplied BYTES match archived copies,
not that their contents were accessible at an earlier historical decision time.
The resulting figures are NOT FX forecasts, trade signals or profit odds.

Dependencies: stdlib and pypdf (only for PDF text extraction).
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
from io import BytesIO
import re
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

SCHEMA = "ATLASQUANT_AUDNZD_CPI_ARCHIVED_DOCUMENT_RECEIPT_LAB_V1"
AUD_SNAPSHOT_SHA256 = "59c89bf477cec8075dfa80f1c29f97654f16f148b11427bed35fbad869eb7d47"
NZD_SNAPSHOT_SHA256 = "c0c685d36bdaa6afcaabba7bd1b656e4b46120032eb41d0a4e6dc01af0901bb7"
AUD_SERIES = "A2325846C"  # ABS spreadsheet: Data1!J10, quarterly Australia all-groups CPI
AUD_PUBLISHER = "Australian Bureau of Statistics"
NZD_PUBLISHER = "Stats NZ"
SAFE_RESEARCH_AFTER = datetime(2026, 10, 29, tzinfo=timezone.utc)
XML_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _result(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "economic_period": "2026-Q3", "pair": "AUD/NZD", "source_receipts": {},
        "inflation_comparison": None, "research_only": True,
        "archived_bytes_verified": False, "historical_point_in_time_verified": False,
        "issuer_origin_independently_authenticated": False,
        "can_feed_live_radar": False, "operational_bias": "AGUARDAR",
        "score_0_to_10": None, "directional_win_probability": None,
        "trade_authorized": False, "automatic_alert_enabled": False,
        "new_cost_brl": 0,
    }


def _cell(root: ET.Element, address: str, strings: list[str]) -> str:
    match = root.find(f'.//{XML_NS}c[@r="{address}"]')
    if match is None:
        raise ValueError("ABS_CELL_MISSING_" + address)
    value = match.find(f"{XML_NS}v")
    if value is None or value.text is None:
        raise ValueError("ABS_CELL_BLANK_" + address)
    if match.attrib.get("t") == "s":
        return strings[int(value.text)]
    return value.text


def _abs_xlsx(raw: bytes) -> tuple[Decimal, Decimal]:
    with ZipFile(BytesIO(raw)) as z:
        if z.testzip() is not None:
            raise ValueError("ABS_ARCHIVE_ZIP_CRC_FAILED")
        book = ET.fromstring(z.read("xl/workbook.xml"))
        sheet = book.find(f'.//{XML_NS}sheet[@name="Data1"]')
        if sheet is None:
            raise ValueError("ABS_DATA1_SHEET_MISSING")
        root = ET.fromstring(z.read("xl/worksheets/sheet2.xml"))
        shared = ET.fromstring(z.read("xl/sharedStrings.xml"))
        strings = ["".join(n.itertext()) for n in shared.findall(f"{XML_NS}si")]
        if _cell(root, "J10", strings) != AUD_SERIES:
            raise ValueError("ABS_QUARTERLY_SERIES_ID_MISMATCH")
        if _cell(root, "J5", strings) != "Quarter":
            raise ValueError("ABS_SERIES_CADENCE_MISMATCH")
        if (_cell(root, "A319", strings), _cell(root, "A323", strings)) != ("45901", "46266"):
            raise ValueError("ABS_PERIOD_DATES_MISMATCH")
        old, new = Decimal(_cell(root, "J319", strings)), Decimal(_cell(root, "J323", strings))
        if old <= 0 or new <= 0:
            raise ValueError("ABS_INDEX_NONPOSITIVE")
        return old, new


def _nz_pdf(raw: bytes) -> tuple[Decimal, Decimal]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("PYPDF_REQUIRED_FOR_DOCUMENT_EXTRACTION") from exc
    reader = PdfReader(BytesIO(raw), strict=True)
    if len(reader.pages) != 2:
        raise ValueError("NZD_PDF_PAGE_COUNT_UNEXPECTED")
    annual = reader.pages[0].extract_text() or ""
    quarterly = reader.pages[1].extract_text() or ""
    if ("Consumers price index annual summary" not in annual
            or "September 2026 quarter" not in annual
            or "Consumers price index quarterly summary" not in quarterly
            or "September 2026 quarter" not in quarterly):
        raise ValueError("NZD_SUMMARY_DOCUMENT_MISMATCH")
    a = re.search(r"CPI all groups\s+([0-9]+\.[0-9]+)%\s+Annual change", annual)
    q = re.search(r"CPI all groups\s+([0-9]+\.[0-9]+)%\s+Quarterly change", quarterly)
    if a is None or q is None:
        raise ValueError("NZD_CPI_ALL_GROUPS_VALUE_MISSING")
    return Decimal(a.group(1)), Decimal(q.group(1))


def inspect_archived_audnzd_cpi_lab(*, aud_xlsx: Any, nzd_pdf: Any, as_of_utc: Any) -> dict[str, Any]:
    out = _result("UNVERIFIED_OR_MISSING_ARCHIVES")
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None):
        out["reason"] = "DECISION_CLOCK_INVALID"
        return out
    if as_of_utc.astimezone(timezone.utc) < SAFE_RESEARCH_AFTER:
        out["reason"] = "BEFORE_PUBLICATION_RESEARCH_FLOOR"
        return out
    if (not isinstance(aud_xlsx, bytes) or not isinstance(nzd_pdf, bytes)
            or len(aud_xlsx) > 2_000_000 or len(nzd_pdf) > 2_000_000):
        return out
    aud_hash, nzd_hash = sha256(aud_xlsx).hexdigest(), sha256(nzd_pdf).hexdigest()
    if aud_hash != AUD_SNAPSHOT_SHA256 or nzd_hash != NZD_SNAPSHOT_SHA256:
        out["reason"] = "ARCHIVE_SNAPSHOT_DIGEST_MISMATCH"
        return out
    try:
        old, new = _abs_xlsx(aud_xlsx)
        nz_annual, nz_quarter = _nz_pdf(nzd_pdf)
    except (ValueError, BadZipFile, ET.ParseError, KeyError, IndexError, RuntimeError, OSError) as exc:
        out["reason"] = "ARCHIVED_DOCUMENT_CONTENT_INVALID:" + type(exc).__name__
        return out
    aud_annual = ((new / old - 1) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    if nz_annual != Decimal("3.7") or nz_quarter != Decimal("0.7") or aud_annual != Decimal("3.9"):
        out["reason"] = "RESEARCH_ANCHOR_VALUE_MISMATCH"
        return out
    out.update({
        "state": "LAB_TWO_DOCUMENT_VALUES_MATCH_ARCHIVED_BYTES_UNATTESTED",
        "reason": "DOCUMENT_BYTES_MATCH_ARCHIVE_NOT_HISTORICAL_AVAILABILITY",
        "archived_bytes_verified": True,
        "source_receipts": {
            "AUD": {"publisher_claim": AUD_PUBLISHER,
                    "source_series_claim": AUD_SERIES,
                    "source_type": "TABLE17_QUARTERLY_ALL_GROUPS",
                    "archive_sha256": aud_hash, "cells": ["Data1!J319", "Data1!J323"],
                    "published_release_date_claim": "2026-10-28"},
            "NZD": {"publisher_claim": NZD_PUBLISHER,
                    "source_type": "PDF_ALL_GROUPS_SUMMARY_QUARTERLY",
                    "archive_sha256": nzd_hash, "page_annual": 1, "page_quarterly": 2,
                    "published_release_date_claim": "2026-10-22"},
        },
        "inflation_comparison": {
            "AUD_2025_Q3_index": str(old), "AUD_2026_Q3_index": str(new),
            "AUD_annual_yoy_pct_derived_from_rounded_index": str(aud_annual),
            "NZD_annual_yoy_pct_publisher_reported": str(nz_annual),
            "NZD_quarter_on_quarter_pct_publisher_reported": str(nz_quarter),
            "same_frequency": True, "methodology_equivalent_proven": False,
        },
    })
    return out

__all__ = ["SCHEMA", "AUD_SNAPSHOT_SHA256", "NZD_SNAPSHOT_SHA256", "inspect_archived_audnzd_cpi_lab"]