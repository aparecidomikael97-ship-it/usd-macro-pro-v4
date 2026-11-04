"""Publisher-documented RSS leads across the G8, without active collection.

The source directory is a research allow-list, *not* evidence of accessible
XML, current news, redistribution rights, feed custody or a reliable FX bias.
NZD's official-domain XML lead remains deliberately OUT of parser allow-lists
until a first-party directory and content/terms review is independently done.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from atlasquant_fx_universe import CURRENCIES

SCHEMA = "ATLASQUANT_TRADER_G8_OFFICIAL_RSS_LEADS_LAB_V1"
RESEARCH_DATE = date(2026, 11, 4)
PUBLISHER_DIRECTORY_LINKED = "OFFICIAL_PUBLISHER_DIRECTORY_LINKED_ONLY"
PENDING = "OFFICIAL_HOST_XML_LEAD_NOT_DIRECTORY_ATTESTED"

# Each directly linked URL was located on a first-party RSS directory.
# No RSS content, origin TLS custody or commercial terms were checked in-app.
DIRECTORY_LINKED_LEADS = {
    "UK_BOE_NEWS": {
        "currency": "GBP", "publisher": "UK_BANK_OF_ENGLAND",
        "topic": "CENTRAL_BANK_NEWS", "feed_url": "https://www.bankofengland.co.uk/rss/news",
        "hostname": "www.bankofengland.co.uk",
        "directory_url": "https://www.bankofengland.co.uk/rss",
        "directory_topic": "News",
    },
    "JP_BOJ_WHATSNEW": {
        "currency": "JPY", "publisher": "JP_BANK_OF_JAPAN",
        "topic": "CENTRAL_BANK_NEWS", "feed_url": "https://www.boj.or.jp/en/rss/whatsnew.xml",
        "hostname": "www.boj.or.jp",
        "directory_url": "https://www.boj.or.jp/en/tips.htm",
        "directory_topic": "Bank of Japan RSS",
    },
    "JP_BOJ_STATISTICS": {
        "currency": "JPY", "publisher": "JP_BANK_OF_JAPAN",
        "topic": "OFFICIAL_STATISTICS_NEWS", "feed_url": "https://www.boj.or.jp/en/rss/statistics.xml",
        "hostname": "www.boj.or.jp",
        "directory_url": "https://www.boj.or.jp/en/tips.htm",
        "directory_topic": "Statistics RSS",
    },
    "CH_SNB_MONETARY": {
        "currency": "CHF", "publisher": "CH_SWISS_NATIONAL_BANK",
        "topic": "MONETARY_POLICY", "feed_url": "https://www.snb.ch/public/rss/en/mopo",
        "hostname": "www.snb.ch",
        "directory_url": "https://www.snb.ch/en/services-events/digital-services/rss-calendar-feeds",
        "directory_topic": "Monetary policy",
    },
    "CH_SNB_STATISTICS": {
        "currency": "CHF", "publisher": "CH_SWISS_NATIONAL_BANK",
        "topic": "OFFICIAL_STATISTICS_NEWS", "feed_url": "https://www.snb.ch/public/rss/en/statistics",
        "hostname": "www.snb.ch",
        "directory_url": "https://www.snb.ch/en/services-events/digital-services/rss-calendar-feeds",
        "directory_topic": "Statistical publications",
    },
    "AU_RBA_MEDIA": {
        "currency": "AUD", "publisher": "AU_RESERVE_BANK",
        "topic": "CENTRAL_BANK_NEWS", "feed_url": "https://www.rba.gov.au/rss/rss-cb-media-releases.xml",
        "hostname": "www.rba.gov.au",
        "directory_url": "https://www.rba.gov.au/rss/",
        "directory_topic": "Media Releases",
    },
    "CA_BOC_PRESS": {
        "currency": "CAD", "publisher": "CA_BANK_OF_CANADA",
        "topic": "CENTRAL_BANK_NEWS",
        "feed_url": "https://www.bankofcanada.ca/content_type/press-releases/feed/",
        "hostname": "www.bankofcanada.ca",
        "directory_url": "https://www.bankofcanada.ca/rss-feeds/",
        "directory_topic": "Press releases",
    },
    "CA_STATCAN_LABOUR": {
        "currency": "CAD", "publisher": "CA_STATISTICS_CANADA",
        "topic": "EMPLOYMENT",
        "feed_url": "https://www150.statcan.gc.ca/n1/rss/dai-quo/14-eng.atom",
        "hostname": "www150.statcan.gc.ca",
        "directory_url": "https://www.statcan.gc.ca/en/sc/rss",
        "directory_topic": "Labour",
    },
    "CA_STATCAN_PRICES": {
        "currency": "CAD", "publisher": "CA_STATISTICS_CANADA",
        "topic": "INFLATION",
        "feed_url": "https://www150.statcan.gc.ca/n1/rss/dai-quo/18-eng.atom",
        "hostname": "www150.statcan.gc.ca",
        "directory_url": "https://www.statcan.gc.ca/en/sc/rss",
        "directory_topic": "Prices and price indexes",
    },
}

# XML endpoint discovered under official host but not linked in the current
# official publisher research page; do not pass it to the existing parser.
PENDING_LEADS = {
    "NZ_RBNZ_NEWS_PENDING": {
        "currency": "NZD", "publisher": "NZ_RESERVE_BANK",
        "topic": "CENTRAL_BANK_NEWS",
        "feed_url": "https://www.rbnz.govt.nz/feeds/news",
        "hostname": "www.rbnz.govt.nz",
        "directory_url": "https://www.rbnz.govt.nz/news-and-events/how-we-release-information",
        "directory_topic": "News-release webpage, not RSS directory",
    },
}

OFFICIAL_NEWS_FALLBACK_PAGES = {
    "NZD": (
        "https://www.rbnz.govt.nz/news-and-events/news",
        "https://www.stats.govt.nz/information-releases/",
    ),
}


def _official_url(value: Any, required_host: str) -> bool:
    if not isinstance(value, str) or len(value) > 1200:
        return False
    try:
        url = urlsplit(value)
        return (url.scheme == "https" and url.hostname == required_host
                and url.username is None and url.password is None
                and url.port in (None, 443) and not url.fragment)
    except ValueError:
        return False


def audit_g8_official_feed_leads_lab(*, at: datetime) -> dict[str, Any]:
    """Return immutable-value documentary directory status, never fetch feeds."""
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Timezone-aware evaluation clock required")
    stamp = at.astimezone(timezone.utc)
    if stamp.date() < RESEARCH_DATE:
        return {"schema": SCHEMA, "state": "LAB_BLOCKED", "reason": "REVIEW_NOT_YET_PERFORMED",
                "currency_coverage": {}, "eligible_sources": {}, "pending_sources": {},
                "live_news_verified": False, "external_http_requests": 0,
                "scheduler_enabled": False, "trade_authorized": False}
    checked = {}
    for source_id, src in (list(DIRECTORY_LINKED_LEADS.items())
                           + list(PENDING_LEADS.items())):
        if (src["currency"] not in CURRENCIES
                or not _official_url(src["feed_url"], src["hostname"])
                or not src["directory_url"].startswith("https://")):
            return {"schema": SCHEMA, "state": "LAB_BLOCKED",
                    "reason": "INVALID_RESEARCHED_SOURCE_LEAD",
                    "live_news_verified": False, "external_http_requests": 0}
        checked[source_id] = dict(src)
    ready = {}
    pending = {}
    for source_id, src in checked.items():
        book = ready if source_id in DIRECTORY_LINKED_LEADS else pending
        book[source_id] = {
            **src,
            "review_status": (PUBLISHER_DIRECTORY_LINKED
                              if source_id in DIRECTORY_LINKED_LEADS else PENDING),
            "feed_bytes_downloaded": False,
            "technical_parser_tested_on_real_feed": False,
            "publisher_terms_verified_for_product": False,
            "can_activate_collection": False,
        }
    coverage = {}
    for currency in CURRENCIES:
        approved = sorted(k for k, v in ready.items() if v["currency"] == currency)
        unconfirmed = sorted(k for k, v in pending.items() if v["currency"] == currency)
        coverage[currency] = {
            "publisher_directory_linked_leads": approved,
            "unconfirmed_official_host_leads": unconfirmed,
            "live_news_verified": False,
            "source_completeness_verified": False,
            "currency_strength_cause_verified": False,
        }
    return {
        "schema": SCHEMA, "state": "LAB_PUBLISHER_DIRECTORY_RESEARCH_ONLY",
        "reviewed_as_of_utc": stamp.isoformat(),
        "currency_coverage": coverage,
        "eligible_sources": ready,
        "pending_sources": pending,
        "nz_fallback_pages": list(OFFICIAL_NEWS_FALLBACK_PAGES["NZD"]),
        "research_directory_count": len(DIRECTORY_LINKED_LEADS),
        "pending_endpoint_count": len(PENDING_LEADS),
        "live_news_verified": False, "all_8_currency_feeds_verified": False,
        "realtime_calendar_verified": False,
        "source_payload_authenticated": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "external_http_requests": 0,
        "new_cost_brl": 0,
    }


__all__ = ["SCHEMA", "DIRECTORY_LINKED_LEADS", "PENDING_LEADS",
           "audit_g8_official_feed_leads_lab"]
