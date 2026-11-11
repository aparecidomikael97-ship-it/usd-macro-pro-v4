"""October-2026 BLS CPI HTML body consistency gate: OFFLINE RESEARCH ONLY.

The supplied bytes and capture times are caller claims, NOT independent BLS
publisher authentication, original release proof or historical PIT evidence.
This extracts documented seasonally adjusted monthly rates and enforces the
missing October 2025 baseline for all-items October 2026 annual rates.
No network, trading, live worker, or market direction calculations.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html.parser import HTMLParser
import re
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_TRADER_US_OCT2026_CPI_RELEASE_TEXT_GUARD_LAB_V1"
URL = "https://www.bls.gov/news.release/archives/cpi_11102026.htm"
RELEASE_FLOOR_UTC = datetime(2026, 11, 10, 13, 30, tzinfo=timezone.utc)
MAX_HTML_BYTES = 2 * 1024 * 1024
SHA = re.compile(r"[0-9a-f]{64}\Z")
_HEAD = re.compile(
    r"Consumer Price Index for All Urban Consumers\s*\(CPI-U\)\s+"
    r"increased\s+([0-9]+(?:\.[0-9]+)?)\s+percent\s+"
    r"on a seasonally adjusted basis in October", re.I
)
_CORE = re.compile(
    r"index for all items less food and energy\s+rose\s+"
    r"([0-9]+(?:\.[0-9]+)?)\s+percent in October", re.I
)


@dataclass(frozen=True)
class ClaimedBLSHtmlReceipt:
    source_url: str
    http_status: int
    content_type: str
    captured_at_utc: datetime
    body_sha256_claim: str


class _TextOnly(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.chunks.append(data)


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _blocked(state: str, reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": state, "reason": reason,
        "as_of_utc": None, "source_url_claim": URL,
        "bls_release_floor_utc": RELEASE_FLOOR_UTC.isoformat(),
        "body_sha256_self_consistent": False,
        "non_utf8_source_byte_count": None,
        "headline_oct2026_sa_mom_pct_body_claim": None,
        "core_oct2026_sa_mom_pct_body_claim": None,
        "headline_oct2026_nsa_yoy_pct": None,
        "core_oct2026_nsa_yoy_pct": None,
        "headline_yoy_reported_missing_oct2025_baseline": False,
        "data_extracted_from_supplied_html_body": False,
        "publisher_original_bytes_independently_attested": False,
        "first_release_publication_timestamp_verified": False,
        "capture_clock_independently_attested": False,
        "point_in_time_archive_eligible": False,
        "pre_release_consensus_authenticated": False,
        "verified_surprise_percent": None,
        "usd_pair_count": 0, "usd_exposed_pairs": [],
        "fx_bias": None, "score_0_to_10": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0,
        "file_writes": 0, "new_cost_brl": 0,
    }


def _single_percentage(pattern: re.Pattern[str], text: str) -> str | None:
    matches = pattern.findall(text)
    # BLS repeats the core figure in both summary and detail paragraphs.
    # Multiple mentions are acceptable only when every number agrees.
    if not 1 <= len(matches) <= 4 or len(set(matches)) != 1:
        return None
    try:
        n = Decimal(matches[0])
    except InvalidOperation:
        return None
    return str(n) if n.is_finite() and Decimal("0") <= n < Decimal("15") else None


def inspect_bls_oct2026_release_text_lab(*, raw_html: Any,
        receipt: Any, as_of_utc: Any) -> dict[str, Any]:
    """Read candidate HTML, never infer authentication, consensus or USD direction."""
    now = _utc(as_of_utc)
    if now is None:
        return _blocked("LAB_INVALID_INPUT", "INVALID_AS_OF_CLOCK")
    if now < RELEASE_FLOOR_UTC:
        return _blocked("LAB_NOT_YET_RELEASED", "OFFICIAL_FIRST_RELEASE_FLOOR_NOT_REACHED")
    content_type = getattr(receipt, "content_type", None)
    if (not isinstance(receipt, ClaimedBLSHtmlReceipt)
            or receipt.source_url != URL
            or type(receipt.http_status) is not int or receipt.http_status != 200
            or not isinstance(content_type, str)
            or content_type.split(";")[0].strip().lower() != "text/html"):
        return _blocked("LAB_INVALID_INPUT", "RECEIPT_ORIGIN_HTTP_CLAIM_INVALID")
    captured = _utc(receipt.captured_at_utc)
    if captured is None or captured < RELEASE_FLOOR_UTC or captured > now:
        return _blocked("LAB_INVALID_INPUT", "CAPTURE_CLAIM_BEFORE_RELEASE_OR_AFTER_AS_OF")
    if (not isinstance(raw_html, bytes)
            or not 100 <= len(raw_html) <= MAX_HTML_BYTES
            or not isinstance(receipt.body_sha256_claim, str)
            or SHA.fullmatch(receipt.body_sha256_claim) is None
            or sha256(raw_html).hexdigest() != receipt.body_sha256_claim):
        return _blocked("LAB_INVALID_INPUT", "RAW_BODY_SIZE_OR_SHA256_CLAIM_MISMATCH")
    try:
        parser = _TextOnly()
        # Real browser-saved BLS HTML contains a few legacy 0x9d bytes.
        # surrogateescape preserves each non-UTF8 byte without silent loss;
        # refuse heavily malformed HTML instead of guessing an encoding.
        decoded = raw_html.decode("utf-8", "surrogateescape")
        malformed = sum(0xDC80 <= ord(ch) <= 0xDCFF for ch in decoded)
        if malformed > 16:
            return _blocked("LAB_INVALID_INPUT", "EXCESS_NON_UTF8_SOURCE_BYTES")
        parser.feed(decoded)
        parser.close()
        text = re.sub(r"\s+", " ", " ".join(parser.chunks)).strip()
    except (UnicodeError, ValueError, TypeError, RecursionError):
        return _blocked("LAB_INVALID_INPUT", "HTML_DECODE_OR_PARSE_FAILED")
    required = (
        "CONSUMER PRICE INDEX - OCTOBER 2026",
        "USDL-26-1685",
        "Tuesday, November 10, 2026",
        "BLS did not collect survey data for October 2025",
        "BLS cannot publish 12-month percent changes for October 2026",
    )
    if any(x.casefold() not in text.casefold() for x in required):
        return _blocked("LAB_SOURCE_TEXT_INSUFFICIENT", "RELEASE_ID_PERIOD_OR_MISSING_BASELINE_UNCONFIRMED")
    headline, core = _single_percentage(_HEAD, text), _single_percentage(_CORE, text)
    if headline is None or core is None:
        return _blocked("LAB_SOURCE_TEXT_INSUFFICIENT", "EXACT_HEADLINE_OR_CORE_MOM_CLAIM_NOT_EXTRACTED")
    affected = [pair for pair in OFFICIAL_PAIRS if "USD" in pair.split("/")]
    out = _blocked("LAB_BLS_HTML_MONTHLY_CONTEXT_UNATTESTED", "TEXT_PARSED_BUT_ISSUER_AND_PUBLICATION_NOT_ATTESTED")
    out.update(
        as_of_utc=now.isoformat(), body_sha256_self_consistent=True,
        non_utf8_source_byte_count=malformed,
        headline_oct2026_sa_mom_pct_body_claim=headline,
        core_oct2026_sa_mom_pct_body_claim=core,
        headline_yoy_reported_missing_oct2025_baseline=True,
        data_extracted_from_supplied_html_body=True,
        usd_pair_count=len(affected), usd_exposed_pairs=affected,
    )
    return out