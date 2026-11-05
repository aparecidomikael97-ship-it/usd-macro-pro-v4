"""Exploratory offline reader of Japan national CPI *extracted page text*.

The Statistics Bureau page is not a live JSON API. This only checks supplied
plain UTF-8 text with a pinned structural contract. No original HTTP bytes,
independent origin, release instant, historical vintage or FX signal is proven.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import re
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_JP_NATIONAL_CPI_TEXT_LAB_V1"
SOURCE_URL = "https://www.stat.go.jp/data/cpi/sokuhou/tsuki/index-z.html"
JST = timezone(timedelta(hours=9))
MAX_BYTES = 64 * 1024
HEADER = re.compile(
    r"2025年基準\s*消費者物価指数\s*全国\s*"
    r"(?P<year>20\d{2})年（令和(?P<era>\d{1,2})年）"
    r"(?P<month>\d{1,2})月分（(?P<release_year>20\d{2})年"
    r"(?P<release_month>\d{1,2})月(?P<release_day>\d{1,2})日公表）"
)
_VALUE = r"(?:0|[1-9]\d{0,2})(?:\.\d{1,2})?"
_LABELS = {
    "headline_all_items": (1, "総合指数"),
    "excluding_fresh_food": (2, "生鮮食品を除く総合指数"),
    "excluding_fresh_food_and_energy": (3, "生鮮食品及びエネルギーを除く総合指数"),
}


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_BLOCKED",
        "reason": reason,
        "currency": "JPY",
        "publisher": "STATISTICS_BUREAU_JAPAN",
        "source_page": SOURCE_URL,
        "source_sha256": None,
        "source_byte_count": None,
        "observed_at_local_system_utc": None,
        "reference_period": None,
        "base_year": None,
        "release_date_japan_calendar_only": None,
        "national_headline_all_items": None,
        "national_excluding_fresh_food": None,
        "national_excluding_fresh_food_and_energy": None,
        "tokyo_preliminary_included": False,
        "source_is_official_original_http_response": False,
        "parsed_text_authenticity_independently_verified": False,
        "individual_release_instant_verified": False,
        "historical_vintage_verified": False,
        "consensus_pre_event_attested": False,
        "cross_country_methods_equivalent": False,
        "commercial_redistribution_rights_verified": False,
        "fx_bias": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "can_feed_live_radar": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "publishable": False,
        "external_http_requests": 0,
        "new_cost_brl": 0,
    }


def _read_row(body: str, number: int, label: str) -> dict[str, str] | None:
    # The national headline sentence explicitly states the 2025 base;
    # the two exclusion variants on the official summary omit that phrase.
    base_phrase = "2025年を100として" if number == 1 else ""
    pat = re.compile(
        rf"\({number}\)\s*{label}は{base_phrase}(?P<index>{_VALUE})\s*"
        rf"前年同月比は(?P<rate>{_VALUE})[%％]の(?P<direction>上昇|下落|横ばい)"
    )
    hits = list(pat.finditer(body))
    if len(hits) != 1:
        return None
    item = hits[0]
    try:
        index, rate = Decimal(item["index"]), Decimal(item["rate"])
    except InvalidOperation:
        return None
    direction = item["direction"]
    if not 50 <= index <= 300 or rate > 50:
        return None
    if direction == "横ばい" and rate != 0:
        return None
    if direction != "横ばい" and rate == 0:
        return None
    signed = -rate if direction == "下落" else rate
    return {
        "index_2025_base_claim": item["index"],
        "reported_yoy_percent_claim": str(signed),
        "reported_japanese_direction": direction,
    }


def parse_jp_national_cpi_summary_text_lab(
    raw_text_utf8: Any, *, observed_at_utc: Any,
) -> dict[str, Any]:
    out = _blocked("INVALID_BYTES_OR_CAPTURE_CLOCK")
    if (not isinstance(raw_text_utf8, bytes)
            or not 100 <= len(raw_text_utf8) <= MAX_BYTES
            or not isinstance(observed_at_utc, datetime)
            or observed_at_utc.tzinfo is None
            or observed_at_utc.utcoffset() is None):
        return out
    captured = observed_at_utc.astimezone(timezone.utc)
    try:
        body = raw_text_utf8.decode("utf-8", "strict")
    except UnicodeDecodeError:
        out["reason"] = "INVALID_UTF8_TEXT"
        return out
    if ("<html" in body.lower() or "<script" in body.lower()
            or "\x00" in body or "\ufffd" in body):
        out["reason"] = "HTML_OR_CORRUPT_TEXT_NOT_SUPPORTED"
        return out
    headers = list(HEADER.finditer(body))
    if len(headers) != 1 or body.count("≪ポイント≫") != 1:
        out["reason"] = "JAPAN_NATIONAL_2025_BASE_HEADER_OR_POINTS_MISSING"
        return out
    h = headers[0]
    try:
        year, month = int(h["year"]), int(h["month"])
        release = date(int(h["release_year"]), int(h["release_month"]),
                       int(h["release_day"]))
        observation = date(year, month, 1)
    except ValueError:
        out["reason"] = "INVALID_REFERENCE_MONTH_OR_RELEASE_DAY"
        return out
    if (int(h["era"]) != year - 2018
            or (release.year, release.month) <= (year, month)
            or release > captured.astimezone(JST).date()):
        out["reason"] = "ERA_RELEASE_SEQUENCE_OR_CAPTURE_DATE_MISMATCH"
        return out

    points = body.split("≪ポイント≫", 1)[1].split("次回の公表日は", 1)[0]
    # Do not let an unrelated Tokyo CPI paragraph outside the 3 numbered
    # national rows substitute for one of the headline components.
    values = {}
    for key, (number, label) in _LABELS.items():
        row = _read_row(points, number, label)
        if row is None:
            out["reason"] = "MISSING_AMBIGUOUS_OR_MALFORMED_NATIONAL_CPI_ROW"
            return out
        values[key] = row
    out.update({
        "state": "LAB_JP_NATIONAL_CPI_SUPPLIED_TEXT_QUARANTINED",
        "reason": "TRANSCRIBED_TEXT_NOT_ORIGINAL_SOURCE_OR_HISTORICAL_VINTAGE",
        "source_sha256": sha256(raw_text_utf8).hexdigest(),
        "source_byte_count": len(raw_text_utf8),
        "observed_at_local_system_utc": captured.isoformat(),
        "reference_period": observation.strftime("%Y-%m"),
        "base_year": 2025,
        "release_date_japan_calendar_only": release.isoformat(),
        "national_headline_all_items": values["headline_all_items"],
        "national_excluding_fresh_food": values["excluding_fresh_food"],
        "national_excluding_fresh_food_and_energy": values[
            "excluding_fresh_food_and_energy"],
    })
    return out


__all__ = ["SCHEMA", "SOURCE_URL", "parse_jp_national_cpi_summary_text_lab"]
