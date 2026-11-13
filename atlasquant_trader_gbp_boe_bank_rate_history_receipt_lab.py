"""Bank of England official Bank Rate *change-history* HTML receipt guard (LAB).

Pure/offline, accepts only raw issuer HTML bytes and a caller-asserted
HTTPS receipt. Source: https://www.bankofengland.co.uk/boeapps/database/Bank-Rate.asp
This is not monthly average (IUMABEDR), end-month (IUMBEDR), or a
verified original MPC announcement. The date of a change does NOT attest
the first publication time of that decision or historical first-seen vintage.

No network, files, broker, trades, account, forecasts, price labels or
calibrated probabilities. The collector is a separate manual-only script.
"""
from __future__ import annotations

from datetime import datetime, date, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html.parser import HTMLParser
import re
from typing import Any

SCHEMA = "ATLASQUANT_GBP_BOE_OFFICIAL_BANK_RATE_HISTORY_HTML_LAB_V1"
URL = "https://www.bankofengland.co.uk/boeapps/database/Bank-Rate.asp"
MAX_BYTES = 400_000
HEX64 = re.compile(r"[a-f0-9]{64}\Z")
RATE = re.compile(r"(?:0|[1-9]\d{0,1})(?:\.\d{1,4})?\Z")
DATE_TEXT = re.compile(r"\d{2} [A-Za-z]{3} \d{2}\Z")
RECEIPT_FIELDS = frozenset((
    "source_url", "final_url", "http_status", "content_type",
    "body_sha256", "started_at_utc", "finished_at_utc",
    "https_validation_claim", "redirects_followed",
))


class _BoEBankRateTables(HTMLParser):
    """Collect table text, never execute page script or follow links."""
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.row_depth = 0
        self.cell_depth = 0
        self.cell_parts: list[str] = []
        self.row: list[str] = []
        self.table_rows: list[list[str]] = []
        self.tables: list[list[list[str]]] = []
        self.text_parts: list[str] = []
        self.in_script = False
        self.in_style = False

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.in_script = True
        elif tag == "style":
            self.in_style = True
        if tag == "table":
            if self.depth == 0:
                self.table_rows = []
            self.depth += 1
        elif tag == "tr" and self.depth == 1:
            self.row_depth = 1
            self.row = []
        elif tag in ("th", "td") and self.depth == 1 and self.row_depth:
            self.cell_depth = 1
            self.cell_parts = []

    def handle_data(self, data):
        if not self.in_script and not self.in_style:
            self.text_parts.append(data)
            if self.cell_depth:
                self.cell_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_script = False
        elif tag == "style":
            self.in_style = False
        if tag in ("th", "td") and self.cell_depth:
            self.row.append(" ".join(" ".join(self.cell_parts).split()))
            self.cell_depth = 0
        elif tag == "tr" and self.row_depth:
            self.table_rows.append(self.row)
            self.row_depth = 0
        elif tag == "table" and self.depth:
            self.depth -= 1
            if self.depth == 0:
                self.tables.append(self.table_rows)

    def get_history(self):
        candidates = []
        for table in self.tables:
            for n, row in enumerate(table):
                if len(row) >= 2 and row[:2] == ["Date Changed", "Rate"]:
                    candidates.append(table[n+1:])
                    break
        return candidates


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_GBP_BOE_BANK_RATE_RECEIPT_BLOCKED",
        "reason": reason,
        "currency": "GBP",
        "instrument": "BOE_OFFICIAL_BANK_RATE",
        "source_url": URL,
        "raw_html_sha256_matches_receipt": False,
        "source_transport_claim_locally_coherent": False,
        "original_html_table_structure_consistent": False,
        "change_events_parsed": 0,
        "last_change_effective_date_claim": None,
        "latest_bank_rate_pct_claim": None,
        "snapshot_finished_at_utc_claim": None,
        "historical_issuer_first_release_verified": False,
        "issuer_decision_announcement_timestamp_verified": False,
        "policy_rate_first_seen_vintage_authenticated": False,
        "bank_rate_daily_series_IUDBEDR_crosschecked": False,
        "macro_cpi_bilateral_sources_complete": False,
        "g8_policy_rate_sources_complete": False,
        "fx28_directional_probability": None,
        "validated_signal_accuracy": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "live_alert_allowed": False, "worker_enabled": False,
        "scheduler_enabled": False, "network_calls": 0,
        "files_written": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def _utc(raw: Any) -> datetime | None:
    if type(raw) is not str or not re.fullmatch(
            r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ", raw):
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        return None


def _decision(raw: Any) -> datetime | None:
    if not isinstance(raw, datetime) or raw.tzinfo is None or raw.microsecond:
        return None
    try:
        return raw.astimezone(timezone.utc) if raw.utcoffset() is not None else None
    except (TypeError, OverflowError, ValueError):
        return None


def _bank_rate(raw: Any) -> Decimal | None:
    if type(raw) is not str or RATE.fullmatch(raw) is None:
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    return value if value.is_finite() and Decimal("0") <= value <= Decimal("30") else None


def inspect_boe_bank_rate_history_receipt_lab(
    *, original_html: Any, receipt: Any, decision_at_utc: Any,
) -> dict[str, Any]:
    """Validate local original bytes/schema; never claim issuer PIT proof."""
    result = _base("RAW_HTML_RECEIPT_OR_CLOCK_INVALID")
    now = _decision(decision_at_utc)
    if (type(original_html) is not bytes
            or not 120 <= len(original_html) <= MAX_BYTES
            or type(receipt) is not dict
            or set(receipt) != RECEIPT_FIELDS or now is None):
        return result
    if (receipt["source_url"] != URL or receipt["final_url"] != URL
            or type(receipt["http_status"]) is not int
            or receipt["http_status"] != 200
            or type(receipt["content_type"]) is not str
            or receipt["content_type"].split(";")[0].strip().lower() != "text/html"
            or receipt["https_validation_claim"] is not True
            or receipt["redirects_followed"] is not False
            or type(receipt["body_sha256"]) is not str
            or HEX64.fullmatch(receipt["body_sha256"]) is None):
        result["reason"] = "NONOFFICIAL_URL_HTTP_OR_TRANSPORT_CLAIM"
        return result
    start = _utc(receipt["started_at_utc"])
    finish = _utc(receipt["finished_at_utc"])
    if (start is None or finish is None
            or not start <= finish <= now
            or finish - start > timedelta(seconds=30)):
        result["reason"] = "CAPTURE_FUTURE_OR_CLOCK_INCOHERENT"
        return result
    if sha256(original_html).hexdigest() != receipt["body_sha256"]:
        result["reason"] = "BOE_ORIGINAL_HTML_HASH_MISMATCH"
        return result
    result["raw_html_sha256_matches_receipt"] = True
    result["source_transport_claim_locally_coherent"] = True

    try:
        html = original_html.decode("utf-8-sig", "strict")
        parser = _BoEBankRateTables()
        parser.feed(html)
        parser.close()
        if parser.depth or parser.row_depth or parser.cell_depth:
            raise ValueError("unclosed bank-rate table")
        visible = " ".join(" ".join(parser.text_parts).split())
        if ("Current official Bank Rate" not in visible
                or "Official Bank Rate" not in visible
                or len(parser.get_history()) != 1):
            result["reason"] = "BOE_OFFICIAL_RATE_TABLE_MISSING_OR_DUPLICATE"
            return result
        rows = parser.get_history()[0]
    except (UnicodeError, ValueError, TypeError, OverflowError, AssertionError):
        result["reason"] = "BOE_HTML_DOCUMENT_INVALID"
        return result
    if not 2 <= len(rows) <= 400:
        result["reason"] = "BOE_HISTORY_ROW_COUNT_OUT_OF_BOUNDS"
        return result
    seen = set()
    parsed: list[tuple[date, str]] = []
    for row in rows:
        if len(row) != 2 or DATE_TEXT.fullmatch(row[0]) is None:
            result["reason"] = "BOE_RATE_CHANGE_ROW_FORMAT_INVALID"
            return result
        try:
            effective = datetime.strptime(row[0], "%d %b %y").date()
        except ValueError:
            result["reason"] = "BOE_CHANGE_EFFECTIVE_DATE_INVALID"
            return result
        rate = _bank_rate(row[1])
        # Date-only changes on the collection day are not intraday release
        # proof. They must not be promoted into pre-collection source data.
        if (rate is None or effective >= finish.date()
                or effective in seen or parsed and effective >= parsed[-1][0]):
            result["reason"] = "BOE_RATE_INVALID_FUTURE_DUPLICATE_OR_UNORDERED"
            return result
        seen.add(effective)
        parsed.append((effective, row[1]))
    # A rate displayed as current can be non-unique on the page; the change
    # history latest row is used, and no hourly release time is inferred.
    last_date, last_rate = parsed[0]
    result.update({
        "state": "LAB_GBP_BOE_ORIGINAL_HISTORY_HTML_LOCALLY_CHECKED_NO_GO",
        "reason": "LOCAL_HTML_RECEIPT_NOT_ORIGINAL_MPC_PUBLICATION_VINTAGE",
        "original_html_table_structure_consistent": True,
        "change_events_parsed": len(parsed),
        "last_change_effective_date_claim": last_date.isoformat(),
        "latest_bank_rate_pct_claim": str(Decimal(last_rate)),
        "snapshot_finished_at_utc_claim": finish.isoformat(),
    })
    return result


__all__ = (
    "SCHEMA", "URL", "MAX_BYTES", "RECEIPT_FIELDS",
    "inspect_boe_bank_rate_history_receipt_lab",
)
