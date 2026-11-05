"""Strict offline ECB EUR/USD reference-rate history reader (research only).

ECB observations are official daily *reference* rates: approximately 14:10
Central European Time fixing and around 16:00 publication. They are not
tradeable prices, intraday/M15 ticks, independently witnessed publication
instants, or point-in-time historical vintages. No network or scheduler.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import re
from typing import Any
from xml.etree import ElementTree as ET

SCHEMA = "ATLASQUANT_TRADER_ECB_EURUSD_REFERENCE_HISTORY_LAB_V1"
SOURCE_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"
ECB_NS = "{http://www.ecb.int/vocabulary/2002-08-01/eurofxref}"
GESMES_NS = "{http://www.gesmes.org/xml/2002-08-01}"
MAX_XML_BYTES = 300_000
MAX_OBSERVATIONS = 100
MAX_CURRENCIES_PER_DAY = 60


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "source_id": "ECB_EUROFXREF_HIST_90D", "source_url": SOURCE_URL,
        "base_currency": "EUR", "quote_currency": "USD",
        "quoted_unit": "USD_PER_1_EUR", "source_raw_sha256": None,
        "source_bytes": None, "captured_at_utc": None,
        "first_observation_date": None, "last_observation_date": None,
        "observation_count": None, "requested_start_date": None,
        "requested_end_date": None, "start_reference_rate": None,
        "end_reference_rate": None, "reference_rate_change_pct": None,
        "publication_time_is_approximate": True,
        "publication_instant_independently_verified": False,
        "archived_historical_vintage_independently_verified": False,
        "historical_point_in_time_eligible": False,
        "intraday_m15_price": False, "tradable_quote": False,
        "independent_execution_price_verified": False,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "can_feed_live_radar": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "new_cost_brl": 0,
    }


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None):
        return None
    return value.astimezone(timezone.utc)


def _day(value: Any) -> date | None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _rate(value: Any) -> Decimal:
    if (not isinstance(value, str)
            or not re.fullmatch(r"(?:0|[1-9]\d{0,7})(?:\.\d{1,8})?", value)):
        raise ValueError("invalid reference rate lexical form")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid reference rate") from exc
    if not Decimal("0") < result < Decimal("100000000"):
        raise ValueError("reference rate outside guard")
    return result


def inspect_ecb_eurusd_reference_history_lab(
    raw: Any, *, captured_at_utc: datetime, as_of_utc: datetime,
    requested_start_date: str, requested_end_date: str,
) -> dict[str, Any]:
    """Return only two *observed* ECB reference days, never infer event bias.

    An archive first downloaded after an event is NOT proof the same raw bytes,
    or specific historical revisions, were obtainable before that event.
    Missing requested dates are blocked rather than filled or interpolated.
    """
    out = _deny("XML_REJECTED")
    capture, as_of = _utc(captured_at_utc), _utc(as_of_utc)
    start, end = _day(requested_start_date), _day(requested_end_date)
    if (capture is None or as_of is None or capture > as_of
            or start is None or end is None or not start < end
            or end > capture.date() or end > as_of.date()
            or not isinstance(raw, bytes)
            or not 100 <= len(raw) <= MAX_XML_BYTES):
        out["reason"] = "INVALID_CAPTURE_OR_DATE_BOUNDARY"
        return out
    if (b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper()
            or b"\x00" in raw):
        return out

    try:
        root = ET.fromstring(raw)
        if root.tag != GESMES_NS + "Envelope":
            return out
        subject = root.find(GESMES_NS + "subject")
        sender = root.find(GESMES_NS + "Sender/" + GESMES_NS + "name")
        if (subject is None or subject.text != "Reference rates"
                or sender is None or sender.text != "European Central Bank"):
            return out
        cubes = root.findall(ECB_NS + "Cube")
        if len(cubes) != 1:
            return out
        daily = list(cubes[0])
        if not 2 <= len(daily) <= MAX_OBSERVATIONS:
            return out
        observations: dict[date, Decimal] = {}
        previous_date: date | None = None
        for day_node in daily:
            if day_node.tag != ECB_NS + "Cube":
                return out
            observation_date = _day(day_node.get("time"))
            if (observation_date is None or observation_date.weekday() >= 5
                    or previous_date is not None
                    and not observation_date < previous_date
                    or observation_date > capture.date()):
                return out
            previous_date = observation_date
            rates = list(day_node)
            if not 1 <= len(rates) <= MAX_CURRENCIES_PER_DAY:
                return out
            seen_currencies: set[str] = set()
            usd_rate: Decimal | None = None
            for item in rates:
                if item.tag != ECB_NS + "Cube" or list(item):
                    return out
                currency = item.get("currency")
                if (not isinstance(currency, str)
                        or not re.fullmatch(r"[A-Z]{3}", currency)
                        or currency in seen_currencies):
                    return out
                seen_currencies.add(currency)
                number = _rate(item.get("rate"))
                if currency == "USD":
                    if not Decimal("0.001") <= number <= Decimal("100"):
                        return out
                    usd_rate = number
            if usd_rate is None:
                out["reason"] = "USD_RATE_MISSING"
                return out
            observations[observation_date] = usd_rate

        if start not in observations or end not in observations:
            out["reason"] = "REQUESTED_DAILY_FIXING_MISSING_NO_FORWARD_FILL"
            return out
        out.update({
            "state": "LAB_ECB_EURUSD_DAILY_REFERENCE_CONTEXT_ONLY",
            "reason": "REFERENCE_NOT_TRADABLE_NO_VERIFIED_HISTORICAL_VINTAGE",
            "source_raw_sha256": sha256(raw).hexdigest(),
            "source_bytes": len(raw), "captured_at_utc": capture.isoformat(),
            "first_observation_date": min(observations).isoformat(),
            "last_observation_date": max(observations).isoformat(),
            "observation_count": len(observations),
            "requested_start_date": start.isoformat(),
            "requested_end_date": end.isoformat(),
            "start_reference_rate": format(observations[start], "f"),
            "end_reference_rate": format(observations[end], "f"),
            # Deliberately no directional/return score: this is an
            # indicative day-to-day *reference*, not an executable series.
        })
        return out
    except (ET.ParseError, ValueError, TypeError, OverflowError):
        return out


__all__ = ["SCHEMA", "SOURCE_URL", "inspect_ecb_eurusd_reference_history_lab"]
