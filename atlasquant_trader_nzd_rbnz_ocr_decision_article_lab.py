"""RBNZ official OCR decision ARTICLE bytes: realized vote and rate only.

The official RSS feed was retrieved by AtlasQuant on 2026-11-14
(GitHub Actions #43590310919, SHA 0554652e...) and supplied two article
URLs + claimed pubDates. This research module allows ONLY those exact two
official media-release links. Two explicit, non-retrying GETs may validate
the decision sentence in the articles, but NOT historical publisher first
seen, a pre-event consensus, a rate expectation, an FX effect, a profitable
trade or data ownership of any third party.

An OCR **HOLD at 2.75%** is not a **HIKE to 2.75%**. The vote 4:3 for
October, versus consensus MPC September vote, is committee agreement,
not consensus of market economists surveyed before an announcement.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
import re
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import (
    Request, build_opener, HTTPRedirectHandler, HTTPSHandler,
)
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from atlasquant_trader_nzd_rbnz_access_terms_lab import (
    TERMS_LAST_UPDATED, REQUIRED_USER_AGENT_PATTERN,
)
from atlasquant_trader_nzd_rbnz_xml_news_feed_lab import USER_AGENT

SCHEMA = "ATLASQUANT_RBNZ_OCR_DECISION_MEDIA_RELEASE_BYTES_LAB_V1"
MAX_HTML_BYTES = 400_000
ISSUER_ORIGIN = "https://www.rbnz.govt.nz"
OCTOBER = (
    "https://www.rbnz.govt.nz/news-and-events/news/2026/10/"
    "ocr-held-at-2-75-percent"
)
SEPTEMBER = (
    "https://www.rbnz.govt.nz/news-and-events/news/2026/09/"
    "ocr-increased-by-25-basis-points-to-2-75"
)
RELEASES = {
    "2026-09": (
        SEPTEMBER, "2026-09-01T12:00:00+00:00", "2026-09-02",
        "HIKE", "25", None
    ),
    "2026-10": (
        OCTOBER, "2026-10-27T11:00:00+00:00", "2026-10-28",
        "HOLD", None, (4, 3)
    ),
}
_RECEIPT_KEYS = frozenset((
    "source_url", "final_url", "http_status", "content_type",
    "body_sha256", "started_at_utc", "finished_at_utc",
    "https_validation_claim", "redirects_followed",
))
_STAMP = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
_RATE = r"(?P<rate>[0-9]{1,2}(?:\.[0-9]{1,2})?)"
_HOLD = re.compile(
    r"The Monetary Policy Committee today voted "
    r"(?P<for>[0-9])\s*-\s*(?P<against>[0-9]) "
    r"to hold the OCR at "+_RATE+r"\s+percent\.",
    re.I,
)
_HIKE = re.compile(
    r"The Monetary Policy Committee today reached consensus "
    r"to increase the OCR by (?P<bps>[0-9]{1,3}) basis points "
    r"to "+_RATE+r"\s+percent\.",
    re.I,
)


class _Visible(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden: list[str] = []
        self.in_body = False
    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self.in_body = True
        if tag in ("script", "style", "noscript", "svg", "nav", "footer",
                   "template", "iframe"):
            self.hidden.append(tag)
    def handle_endtag(self, tag):
        if tag == "body":
            self.in_body = False
        if tag in self.hidden:
            # No visible words from scripts, style, menus, or related links
            # embedded in hidden tags; conservative nested recovery.
            last = len(self.hidden)-1-self.hidden[::-1].index(tag)
            del self.hidden[last:]
    def handle_data(self, data):
        if self.in_body and not self.hidden:
            self.parts.append(data)


def _utc(value: Any) -> datetime | None:
    if type(value) is not datetime or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(timezone.utc)
    except (TypeError, OverflowError, ValueError):
        return None


def _stamp(value: Any) -> datetime | None:
    if type(value) is not str or _STAMP.fullmatch(value) is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        return None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_RBNZ_OCR_DECISION_ARTICLE_BLOCKED_NO_GO",
        "reason": reason,
        "issuer_origin": ISSUER_ORIGIN,
        "terms_last_updated_claim": TERMS_LAST_UPDATED,
        "user_agent_pattern": REQUIRED_USER_AGENT_PATTERN,
        "rss_article_link_and_pubdate_observed_in_nov14_snapshot": True,
        "rss_nov14_historical_original_is_not_replayed_in_this_module": True,
        "article_url": None,
        "article_original_sha256_local": None,
        "article_received_utc_local_claim": None,
        "policy_event_month": None,
        "policy_event_date_nz_from_feed_claim": None,
        "action": None,
        "ocr_percent_claim": None,
        "rate_change_basis_points_claim": None,
        "committee_votes_to_hold": None,
        "committee_votes_against_hold": None,
        "committee_unanimity_phrase_detected": None,
        "market_economist_consensus_pre_event_verified": False,
        "issuer_first_release_seen_time_independently_authenticated": False,
        "policy_event_is_not_currency_direction": True,
        "current_ocr_as_of_future_release_verified": False,
        "article_html_retained": False,
        "am12_source_archived": False,
        "calibrated_nzd_directional_probability": None,
        "out_of_sample_accuracy": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "scheduler_enabled": False,
        "worker_enabled": False,
        "http_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_rbnz_ocr_decision_article_bytes_lab(
    *, event_month: Any, original_html: Any, receipt: Any,
    inspected_at_utc: Any,
) -> dict[str, Any]:
    """Strict two-date release classification; no FX signals or first seen."""
    out = _blocked("UNKNOWN_EVENT_OR_MISSING_RAW_SOURCE")
    now = _utc(inspected_at_utc)
    if (type(event_month) is not str or event_month not in RELEASES
            or now is None or type(original_html) is not bytes
            or not 100 <= len(original_html) <= MAX_HTML_BYTES
            or type(receipt) is not dict or set(receipt) != _RECEIPT_KEYS):
        return out

    url, pub_raw, published_local_date, expected_action, expected_bps, expected_votes = (
        RELEASES[event_month]
    )
    begin, end = _stamp(receipt["started_at_utc"]), _stamp(receipt["finished_at_utc"])
    if (receipt["source_url"] != url or receipt["final_url"] != url
            or type(receipt["http_status"]) is not int
            or receipt["http_status"] != 200
            or type(receipt["content_type"]) is not str
            or receipt["content_type"].split(";")[0].strip().lower() != "text/html"
            or receipt["body_sha256"] != sha256(original_html).hexdigest()
            or receipt["https_validation_claim"] is not True
            or receipt["redirects_followed"] is not False
            or begin is None or end is None or end < begin
            or end-begin > timedelta(seconds=30)
            or end > now or now-end > timedelta(seconds=30)):
        out["reason"] = "OFFICIAL_SOURCE_URL_TLS_SHA_OR_RECEIPT_CLOCK_INVALID"
        return out

    try:
        nz = ZoneInfo("Pacific/Auckland")
        published_utc = datetime.fromisoformat(pub_raw)
        if (published_utc.astimezone(nz).date().isoformat() != published_local_date
                or end < published_utc):
            out["reason"] = "ISSUER_RSS_PUBLICATION_TIME_CALENDAR_MISMATCH"
            return out
        body = original_html.decode("utf-8-sig", "strict")
        reader = _Visible()
        reader.feed(body)
        reader.close()
        visible = " ".join(" ".join(reader.parts).split())
    except (ValueError, UnicodeError, TypeError, OverflowError,
            ZoneInfoNotFoundError):
        out["reason"] = "UNPARSEABLE_NZ_TIMEZONE_OR_HTML"
        return out

    if not ("Reserve Bank of New Zealand" in visible
            or "Te Pūtea Matua" in visible
            or "Monetary Policy Committee" in visible):
        out["reason"] = "ISSUER_ORIGINAL_PAGE_CONTENT_NOT_IDENTIFIED"
        return out

    # Rate MUST occur in THE decision sentence, not in economic commentary,
    # forecasts, market expectations, other meetings or background text.
    holds = list(_HOLD.finditer(visible))
    hikes = list(_HIKE.finditer(visible))
    if ((len(holds), len(hikes)) !=
            ((1, 0) if expected_action == "HOLD" else (0, 1))):
        out["reason"] = "POLICY_DECISION_SENTENCE_MISSING_DUPLICATED_OR_AMBIGUOUS"
        return out
    match = holds[0] if expected_action == "HOLD" else hikes[0]
    if (match.group("rate") != "2.75"
            or (expected_action == "HOLD" and
                tuple(map(int, (
                    match.group("for"), match.group("against"),
                ))) != expected_votes)
            or (expected_action == "HIKE"
                and match.group("bps") != expected_bps)):
        out["reason"] = "OFFICIAL_OCR_ACTUAL_OR_VOTE_DIFFERS_FROM_RELEASE_CONTRACT"
        return out

    out.update({
        "state": "LAB_RBNZ_OCR_ACTUAL_DECISION_SENTENCE_EPHEMERAL_CHECKED_NO_GO",
        "reason": "REALIZED_POLICY_DECISION_ONLY_NOT_PRE_EVENT_EXPECTATIONS_OR_FX_BIAS",
        "article_url": url,
        "article_original_sha256_local": receipt["body_sha256"],
        "article_received_utc_local_claim": end.isoformat(),
        "policy_event_month": event_month,
        "policy_event_date_nz_from_feed_claim": published_local_date,
        "action": expected_action,
        "ocr_percent_claim": match.group("rate"),
        "rate_change_basis_points_claim": (
            0 if expected_action == "HOLD" else int(match.group("bps"))
        ),
        "committee_votes_to_hold": (
            expected_votes[0] if expected_action == "HOLD" else None
        ),
        "committee_votes_against_hold": (
            expected_votes[1] if expected_action == "HOLD" else None
        ),
        "committee_unanimity_phrase_detected": (
            expected_action == "HIKE"
        ),
    })
    return out


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check_both_official_articles_once_lab(
    *, explicit_request: Any,
    opener: Callable[..., Any] | None = None,
    now_stamp: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Two exact feed-listed article GETs only; no fallback or retries."""
    base = {
        "state": "LAB_RBNZ_POLICY_ARTICLE_CHAIN_NOT_EXECUTED_NO_GO",
        "reason": "EXPLICIT_ARTICLE_SOURCE_REQUEST_FLAG_REQUIRED",
        "requests_started": 0, "source_results": {},
        "both_articles_validated_ephemerally": False,
        "change_from_september_to_october_bps": None,
        "paper_forecast_or_consensus_verified": False,
        "issuer_first_seen_authenticated": False,
        "am12_originals_persisted": False,
        "trade_authorized": False, "publishable": False,
        "operational_bias": "AGUARDAR", "file_writes": 0,
        "new_cost_brl": 0, "research_only": True,
    }
    if explicit_request is not True:
        return base
    if opener is None:
        opener = build_opener(_NoRedirect, HTTPSHandler).open
    if now_stamp is None:
        now_stamp = lambda: datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
    if not callable(opener) or not callable(now_stamp):
        base["reason"] = "INVALID_HTTP_PROVIDER_OR_CLOCK"
        return base

    for month in ("2026-09", "2026-10"):
        url = RELEASES[month][0]
        req = Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html",
        }, method="GET")
        base["requests_started"] += 1
        try:
            start = now_stamp()
            with opener(req, timeout=12) as response:
                raw = response.read(MAX_HTML_BYTES + 1)
                receipt = {
                    "source_url": url, "final_url": response.geturl(),
                    "http_status": response.status,
                    "content_type": response.headers.get("Content-Type", ""),
                    "body_sha256": sha256(raw).hexdigest(),
                    "started_at_utc": start, "finished_at_utc": now_stamp(),
                    "https_validation_claim": True,
                    "redirects_followed": response.geturl() != url,
                }
            at = _stamp(receipt["finished_at_utc"])
            result = inspect_rbnz_ocr_decision_article_bytes_lab(
                event_month=month, original_html=raw, receipt=receipt,
                inspected_at_utc=at)
            base["source_results"][month] = result
        except HTTPError as exc:
            base["reason"] = "OFFICIAL_ARTICLE_HTTP_DENIED_NO_RETRY"
            base["source_results"][month] = {
                "status": "HTTP_REFUSED", "http_status": exc.code,
                "article_url": url,
            }
            return base
        except (URLError, OSError, ValueError, TypeError, KeyError,
                OverflowError, RuntimeError):
            base["reason"] = "OFFICIAL_ARTICLE_TRANSPORT_OR_PARSER_FAILED_NO_RETRY"
            base["source_results"][month] = {
                "status": "SOURCE_ERROR_NOT_ACCEPTED", "article_url": url,
            }
            return base
        if result["state"] != (
            "LAB_RBNZ_OCR_ACTUAL_DECISION_SENTENCE_EPHEMERAL_CHECKED_NO_GO"
        ):
            base["reason"] = "EXACT_ISSUER_ARTICLE_DECISION_NOT_VALIDATED"
            return base

    sept, octo = (base["source_results"][k] for k in ("2026-09", "2026-10"))
    if (sept["action"] != "HIKE" or octo["action"] != "HOLD"
            or sept["ocr_percent_claim"] != octo["ocr_percent_claim"]
            or sept["rate_change_basis_points_claim"] != 25
            or octo["rate_change_basis_points_claim"] != 0):
        base["reason"] = "DECISION_CHRONOLOGY_OR_RATE_CONFLICT"
        return base
    base["state"] = "LAB_RBNZ_TWO_ORIGINAL_POLICY_RELEASES_CHECKED_NO_GO"
    base["reason"] = "SEPT_HIKE_OCT_HOLD_DOCUMENTED_NOT_FX_DIRECTION_OR_EXPECTATION"
    base["both_articles_validated_ephemerally"] = True
    base["change_from_september_to_october_bps"] = 0
    return base


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--inspect-two-official-once", action="store_true")
    a = p.parse_args(argv)
    result = check_both_official_articles_once_lab(
        explicit_request=a.inspect_two_official_once)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["both_articles_validated_ephemerally"] else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "SCHEMA", "OCTOBER", "SEPTEMBER", "RELEASES",
    "inspect_rbnz_ocr_decision_article_bytes_lab",
    "check_both_official_articles_once_lab",
)
