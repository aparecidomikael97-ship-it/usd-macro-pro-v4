"""TE pre-event US PPI calendar: separate consensus, previous and own forecast.

Only offline, exact-bytes local research. No source publisher attestation,
licensed redistribution, historical backtest eligibility or FX direction.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import re
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_US_PPI_TE_PRE_EVENT_CONSENSUS_LAB_V1"
SOURCE = "https://tradingeconomics.com/united-states/calendar"
EVENT = datetime(2026, 11, 13, 13, 30, tzinfo=timezone.utc)
MAX_BYTES = 2 * 1024 * 1024
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_PCT = re.compile(r"(0|[1-9]\d?)(?:\.\d{1,3})?%\Z")
ROWS = {
    "/united-states/producer-price-inflation-mom": "PPI MoM OCT",
    "/united-states/core-producer-prices-mom": "Core PPI MoM OCT",
}

@dataclass(frozen=True)
class Capture:
    source_url: str
    http_status: int
    content_type: str
    started_utc: datetime
    finished_utc: datetime
    response_date_http: str
    rendered_at_utc: datetime
    source_sha256: str
    source_bytes: int

def _utc(v: Any) -> datetime | None:
    if not isinstance(v, datetime) or v.tzinfo is None or v.utcoffset() is None:
        return None
    return v.astimezone(timezone.utc)

class _Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active = False
        self.depth = 0
        self.key = ""
        self.date_class = ""
        self.cells = []
        self.cell = None
        self.th = None
        self.headers = []
        self.rows = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "svg", "noscript"):
            self.hidden += 1
            return
        if self.hidden:
            return
        if tag == "th" and not self.active:
            self.th = []
        if tag == "tr" and not self.active and a.get("data-url") in ROWS:
            self.active = True
            self.depth = 1
            self.key = a["data-url"]
            self.cells = []
            self.date_class = ""
            return
        if not self.active:
            return
        if tag == "tr":
            self.depth += 1
        elif tag == "td" and self.depth == 1:
            if self.cell is not None:
                raise ValueError("overlapping outer td")
            self.cell = []
            if len(self.cells) == 0:
                self.date_class = a.get("class", "")
    
    def handle_data(self, data):
        if self.hidden:
            return
        if self.th is not None and not self.active:
            self.th.append(data)
        if self.active and self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "svg", "noscript") and self.hidden:
            self.hidden -= 1
            return
        if self.hidden:
            return
        if tag == "th" and self.th is not None:
            self.headers.append(" ".join(" ".join(self.th).split()))
            self.th = None
        if not self.active:
            return
        if tag == "td" and self.depth == 1 and self.cell is not None:
            self.cells.append(" ".join(" ".join(self.cell).split()))
            self.cell = None
        if tag == "tr":
            self.depth -= 1
            if self.depth == 0:
                self.rows.append((self.key, self.date_class, tuple(self.cells)))
                self.active = False

def _pct(v: Any) -> str | None:
    if not isinstance(v, str) or not _PCT.fullmatch(v):
        return None
    try:
        n = Decimal(v[:-1])
        return str(n) if n.is_finite() and 0 <= n < 20 else None
    except InvalidOperation:
        return None

def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_TE_PPI_SOURCE_BLOCKED",
        "reason": reason, "source_url": SOURCE, 
        "event_release_utc": EVENT.isoformat(), "source_sha256": None,
        "headline_consensus_mom_pct": None, "core_consensus_mom_pct": None,
        "headline_te_own_forecast_mom_pct": None,
        "core_te_own_forecast_mom_pct": None,
        "headline_previous_mom_pct": None, "core_previous_mom_pct": None,
        "both_consensus_and_forecast_separate": False,
        "pre_event_local_snapshot_readable": False,
        "original_publisher_timestamp_independently_attested": False,
        "poll_methodology_independently_verified": False,
        "market_direction": None, "operational_bias": "AGUARDAR",
        "ppi_actual": None, "ppi_surprise": None,
        "trade_authorized": False, "publishable": False,
        "scheduler_enabled": False, "new_cost_brl": 0,
    }

def inspect_te_ppi_snapshot_lab(*, raw_html: Any, capture: Any, as_of_utc: Any) -> dict[str, Any]:
    now = _utc(as_of_utc)
    if not isinstance(capture, Capture) or now is None:
        return _blocked("INVALID_CAPTURE_OR_CLOCK")
    start, end, rendered = (_utc(capture.started_utc),
                            _utc(capture.finished_utc), _utc(capture.rendered_at_utc))
    try:
        http_date = _utc(parsedate_to_datetime(capture.response_date_http))
    except (ValueError, TypeError, IndexError, OverflowError):
        http_date = None
    if (capture.source_url != SOURCE or type(capture.http_status) is not int
            or capture.http_status != 200 or not isinstance(capture.content_type, str)
            or capture.content_type.split(";")[0].strip().lower() != "text/html"
            or start is None or end is None or rendered is None or http_date is None
            or type(capture.source_bytes) is not int):
        return _blocked("SOURCE_OR_HTTP_CLAIM_INVALID")
    if (start < datetime(2026, 11, 10, tzinfo=timezone.utc)
            or start > end or end >= EVENT or end > now
            or end - start > timedelta(minutes=2)
            or abs((http_date-end).total_seconds()) > 120
            or abs((rendered-end).total_seconds()) > 120
            or rendered >= EVENT):
        return _blocked("FUTURE_OR_POST_EVENT_SNAPSHOT")
    if (not isinstance(raw_html, bytes) or not 1000 < len(raw_html) <= MAX_BYTES
            or len(raw_html) != capture.source_bytes
            or not isinstance(capture.source_sha256, str)
            or not _HEX.fullmatch(capture.source_sha256)
            or sha256(raw_html).hexdigest() != capture.source_sha256):
        return _blocked("HTML_SIZE_OR_HASH_MISMATCH")
    try:
        p = _Reader()
        p.feed(raw_html.decode("utf-8", "strict"))
        p.close()
    except (UnicodeError, ValueError, TypeError, RecursionError):
        return _blocked("HTML_DECODE_OR_PARSE_FAILURE")
    if (p.active or len(p.rows) != 2
            or not any(p.headers[i:i+4] == ["Actual", "Previous", "Consensus", "Forecast"]
                       for i in range(max(0,len(p.headers)-3)))):
        return _blocked("EVENT_ROWS_OR_COLUMN_HEADER_MISSING")
    out = {}
    for key, expected in ROWS.items():
        m = [row for row in p.rows if row[0] == key]
        if len(m) != 1:
            return _blocked("DUPLICATE_OR_MISSING_PPI_ROW")
        _, date_class, cells = m[0]
        if (not re.search(r"(?:^|\s)2026-11-13(?:\s|$)", date_class)
                or len(cells) != 10 or cells[2].strip() != expected
                or cells[3] != ""):
            return _blocked("UNEXPECTED_PPI_DATE_PERIOD_ACTUAL_OR_METRIC")
        previous, consensus, forecast = map(_pct, cells[4:7])
        if any(v is None for v in (previous,consensus,forecast)):
            return _blocked("PPI_CONSENSUS_PREVIOUS_OR_FORECAST_INVALID")
        out[key] = (previous,consensus,forecast)
    h,c=(out[k] for k in ROWS)
    result = _blocked("TWO_PRE_EVENT_TE_COLUMNS_PARSED_ONLY_NOT_TRADABLE")
    result.update({
        "state":"LAB_TE_PRE_EVENT_CONSENSUS_AND_OWN_FORECAST_DISTINGUISHED",
        "source_sha256":capture.source_sha256,
        "headline_previous_mom_pct":h[0],
        "headline_consensus_mom_pct":h[1],
        "headline_te_own_forecast_mom_pct":h[2],
        "core_previous_mom_pct":c[0],
        "core_consensus_mom_pct":c[1],
        "core_te_own_forecast_mom_pct":c[2],
        "both_consensus_and_forecast_separate":True,
        "pre_event_local_snapshot_readable":True,
    })
    return result
