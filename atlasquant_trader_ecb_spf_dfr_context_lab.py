"""Strict offline reading of ECB SPF *quarterly* DFR context (research only).

The public release date comes from a separately inspected ECB release listing;
caller-provided HTML and timestamps are NOT proof of an immutable historical
vintage. A quarterly survey is never a meeting-level rate surprise or FX trade.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html.parser import HTMLParser
import re
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_ECB_SPF_DFR_QUARTERLY_CONTEXT_LAB_V1"
MAX_HTML_BYTES = 512 * 1024
OFFICIAL_BASE = (
    "https://www.ecb.europa.eu/stats/ecb_surveys/"
    "survey_of_professional_forecasters/html/"
)
# Dated ECB official *release index*, NOT an independently authenticated
# first-seen/publication instant. Revising a date requires documentary review.
RELEASES = {
    "ECB_SPF_2026Q3": {
        "release_date": "2026-07-24",
        "url": OFFICIAL_BASE + "ecb.spf2026q3.en.html",
        "title": "The ECB Survey of Professional Forecasters - Third quarter of 2026",
        "pattern": (
            r"For the third quarter of 2026, the modal expectation "
            r"remained at (?P<modal>\d{1,2}\.\d{1,2})%, reported by "
            r"(?P<share>\d{1,3})% of respondents"
        ),
        "q4_pattern": (
            r"modal expectation rising to (?P<q4>\d{1,2}\.\d{1,2})% "
            r"in the fourth quarter of 2026 and the first quarter of 2027"
        ),
    },
    "ECB_SPF_2026Q4": {
        "release_date": "2026-10-30",
        "url": OFFICIAL_BASE + "ecb.spf2026q4.en.html",
        "title": "The ECB Survey of Professional Forecasters - Fourth quarter of 2026",
        "pattern": (
            r"For the fourth quarter of 2026 the modal expectation for "
            r"the DFR remains at (?P<modal>\d{1,2}\.\d{1,2})%, "
            r"as reported by (?P<share>\d{1,3})% of respondents"
        ),
        "q4_pattern": None,
    },
}


class _PageText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self._in_body = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "body":
            self._in_body = True
        if tag in ("script", "style", "noscript", "svg"):
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "body":
            self._in_body = False
        if tag in ("script", "style", "noscript", "svg") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._in_body and not self._skip:
            self.parts.append(data)


def _result(source_id: Any, event_date: Any) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": "INVALID_INPUT",
        "source_id": source_id if isinstance(source_id, str) else None,
        "currency": "EUR", "event_date": event_date if isinstance(event_date, str) else None,
        "official_release_date": None, "official_url": None,
        "html_sha256": None, "html_bytes": None,
        "captured_at_utc": None, "capture_after_event_date": None,
        "survey_quarter_modal_dfr_pct": None,
        "survey_quarter_modal_share_pct": None,
        "q4_2026_modal_dfr_forecast_from_q3_pct": None,
        "quarterly_context_parsed": False,
        "release_date_is_catalog_metadata": True,
        "source_origin_independently_authenticated": False,
        "immutable_historical_vintage_verified": False,
        "exact_release_instant_verified": False,
        "pre_event_meeting_consensus_verified": False,
        "historical_point_in_time_eligible": False,
        "market_surprise_bps": None, "fx_bias": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "can_feed_live_radar": False, "publishable": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "new_cost_brl": 0,
    }


def _aware_utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _valid_date(value: Any) -> date | None:
    if not isinstance(value, str) or not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _one_match(pattern: str, text: str) -> re.Match[str] | None:
    matches = list(re.finditer(pattern, text))
    return matches[0] if len(matches) == 1 else None


def audit_ecb_spf_dfr_context_lab(
    *, source_id: str, event_date: str, captured_at_utc: datetime,
    as_of_utc: datetime, raw_html: bytes,
) -> dict[str, Any]:
    """Extract documented DFR context; never convert it into a policy surprise.

    A July survey can predate an October meeting *as a dated publication* even
    if its retrospective download is too late for an authenticated PIT backtest.
    """
    out = _result(source_id, event_date)
    info = RELEASES.get(source_id) if isinstance(source_id, str) else None
    event = _valid_date(event_date)
    capture = _aware_utc(captured_at_utc)
    as_of = _aware_utc(as_of_utc)
    if (info is None or event is None or capture is None or as_of is None
            or not isinstance(raw_html, bytes)
            or not 1 <= len(raw_html) <= MAX_HTML_BYTES
            or capture > as_of):
        return out
    out.update({
        "official_release_date": info["release_date"],
        "official_url": info["url"],
        "html_bytes": len(raw_html),
        "html_sha256": sha256(raw_html).hexdigest(),
        "captured_at_utc": capture.isoformat(),
        "capture_after_event_date": capture.date() > event,
    })
    try:
        html = raw_html.decode("utf-8", errors="strict")
        page = _PageText()
        page.feed(html)
        text = re.sub(r"\s+", " ", " ".join(page.parts)).strip()
    except (ValueError, UnicodeError):
        out["reason"] = "HTML_NOT_STRICTLY_READABLE"
        return out
    if text.count(info["title"]) != 1:
        out["reason"] = "SPF_RELEASE_TITLE_MISSING_OR_DUPLICATED"
        return out
    m = _one_match(info["pattern"], text)
    future = (_one_match(info["q4_pattern"], text)
              if info["q4_pattern"] else None)
    if m is None or (info["q4_pattern"] and future is None):
        out["reason"] = "SPF_DFR_CONTEXT_MISSING_OR_AMBIGUOUS"
        return out
    try:
        modal = Decimal(m.group("modal"))
        share = int(m.group("share"))
        q4 = Decimal(future.group("q4")) if future else None
    except (InvalidOperation, ValueError):
        out["reason"] = "SPF_DFR_VALUE_INVALID"
        return out
    if not (Decimal("0") <= modal <= Decimal("20")
            and 0 <= share <= 100
            and (q4 is None or Decimal("0") <= q4 <= Decimal("20"))):
        out["reason"] = "SPF_DFR_VALUE_INVALID"
        return out
    out.update({
        "survey_quarter_modal_dfr_pct": str(modal),
        "survey_quarter_modal_share_pct": share,
        "q4_2026_modal_dfr_forecast_from_q3_pct": str(q4) if q4 is not None else None,
        "quarterly_context_parsed": True,
    })
    release = date.fromisoformat(info["release_date"])
    if release > event:
        out["reason"] = "SPF_RELEASE_DATED_AFTER_EVENT"
    elif release == event:
        out["reason"] = "SPF_SAME_DAY_EVENT_INSTANT_UNKNOWN"
    else:
        out["state"] = "LAB_QUARTERLY_CONTEXT_DATE_PRECEDES_EVENT_UNVERIFIED"
        out["reason"] = "QUARTERLY_DFR_CONTEXT_NOT_MEETING_CONSENSUS_OR_PIT_PROOF"
    return out


__all__ = ["SCHEMA", "RELEASES", "audit_ecb_spf_dfr_context_lab"]
