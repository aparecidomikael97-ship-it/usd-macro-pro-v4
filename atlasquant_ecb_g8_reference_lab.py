"""Historical ECB euro-reference adapter for G8 research (OFFLINE ONLY).

Reads user-supplied ECB 90-day XML bytes. Does not download, authenticate,
execute orders, create live Forex quotes, or enter the VALIDATED_DAILY UI gate.
ECB fixes are daily informational references, not executable bid/ask prices.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from math import expm1, isfinite, log
from typing import Any
from xml.etree import ElementTree as ET

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_ECB_G8_REFERENCE_LAB_V1"
EUR_CROSSES = frozenset(CURRENCIES) - {"EUR"}
OFFICIAL_REFERENCE_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"
MAX_XML_BYTES = 600_000


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "BLOCKED", "reason": reason,
        "publishable": False, "provider_authenticated": False,
        "trade_authorized": False, "accuracy_verified": False,
        "reference_prices_only": True, "complete_pairs": 0,
        "rates": {}, "pair_returns_pct": {}, "currency_strength_log_pp": {},
        "top10": [],
    }


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_history(xml_data: bytes) -> dict[date, dict[str, float]] | None:
    if not isinstance(xml_data, bytes) or not 0 < len(xml_data) <= MAX_XML_BYTES:
        return None
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return None
    records: dict[date, dict[str, float]] = {}
    for elem in root.iter():
        if _local(elem.tag) != "Cube" or "time" not in elem.attrib:
            continue
        try:
            day = date.fromisoformat(elem.attrib["time"])
        except (ValueError, TypeError):
            return None
        if day in records:
            return None
        row = {"EUR": 1.0}
        for item in elem:
            if _local(item.tag) != "Cube" or "currency" not in item.attrib:
                continue
            ccy = item.attrib["currency"]
            if ccy not in EUR_CROSSES:
                continue
            if ccy in row:
                return None
            raw = item.attrib.get("rate")
            try:
                value = float(raw)
            except (TypeError, ValueError, OverflowError):
                return None
            if not isfinite(value) or value <= 0:
                return None
            row[ccy] = value
        if set(row) != set(CURRENCIES):
            return None
        records[day] = row
        if len(records) > 100:
            return None
    return records if len(records) >= 2 else None


def _reference_window(old: dict[str, float], new: dict[str, float],
                      start: date, end: date) -> dict[str, Any] | None:
    """Relative G8 changes; log arithmetic avoids unsafe rate division.

    Every quoted pair is still only algebraically derived from EUR fixes.
    """
    log_change = {c: log(new[c]) - log(old[c]) for c in CURRENCIES}
    mean_change = sum(log_change.values()) / len(CURRENCIES)
    strength = {c: (mean_change - log_change[c]) * 100 for c in CURRENCIES}
    pairs: dict[str, float] = {}
    logret: dict[str, float] = {}
    for symbol in OFFICIAL_PAIRS:
        base, quote = split_pair(symbol)
        pair_log = log_change[quote] - log_change[base]
        try:
            pct = expm1(pair_log) * 100
        except OverflowError:
            return None
        if not isfinite(pct):
            return None
        pairs[symbol] = pct
        logret[symbol] = pair_log * 100
    max_residual = max(
        abs(logret[s] - (strength[split_pair(s)[0]] - strength[split_pair(s)[1]]))
        for s in OFFICIAL_PAIRS
    )
    if not isfinite(max_residual) or max_residual > 1e-7:
        return None
    top = sorted(pairs.items(), key=lambda p: (-p[1], p[0]))
    return {
        "state": "RESEARCH_ONLY",
        "start_reference_date": start.isoformat(),
        "end_reference_date": end.isoformat(),
        "calendar_days_between_fixes": (end - start).days,
        "currency_strength_log_pp": {k: round(v, 6) for k, v in strength.items()},
        "currency_order": sorted(CURRENCIES, key=lambda c: (-strength[c], c)),
        "pair_returns_pct": {k: round(v, 6) for k, v in pairs.items()},
        "top10": [{"pair": k, "change_pct": round(v, 6)} for k, v in top[:10]],
        "max_algebraic_residual_log_pp": round(max_residual, 9),
        "has_executable_bid_ask": False,
        "publishable": False,
        "trade_authorized": False,
    }


def analyze_ecb_reference_xml(xml_data: bytes, *, now: datetime | None = None) -> dict[str, Any]:
    """Compare latest two complete ECB working-day reference observations.

    A 28-pair cross-product *derived* from seven EUR fixes is NOT 28
    independently quoted market prices. Output never authorizes trading.
    """
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    current = current.astimezone(timezone.utc)
    rows = _parse_history(xml_data)
    if rows is None:
        return _blocked("XML_INVALID_OR_INCOMPLETE_G8")
    days = sorted(rows)
    latest, previous = days[-1], days[-2]
    if latest > current.date() or previous >= latest:
        return _blocked("FUTURE_OR_INVALID_REFERENCE_DATE")
    old = rows[previous]
    new = rows[latest]
    if (latest - previous).days > 7:
        return _blocked("LAST_TWO_REFERENCE_DATES_TOO_FAR_APART_FOR_D1")
    daily = _reference_window(old, new, previous, latest)
    if daily is None:
        return _blocked("NUMERIC_RANGE_INVALID")
    # Research windows always use an actual historical ECB fixing on or
    # before the target date, never interpolate missing weekends/holidays.
    def historical_window(calendar_days: int) -> dict[str, Any] | None:
        cutoff = latest - timedelta(days=calendar_days)
        candidates = [d for d in days if d <= cutoff]
        if candidates:
            start = candidates[-1]
            if (latest - start).days <= calendar_days + 7:
                return _reference_window(rows[start], new, start, latest)
            # Do not relabel a 60-day comparison as a 30-day period merely
            # because it is the nearest available older reference in XML.
            candidates = []
        return {
            "state": "INSUFFICIENT_REFERENCE_HISTORY",
            "reason": ("NO_REFERENCE_ON_OR_BEFORE_WEEK_START" if calendar_days == 7
                       else "NO_REFERENCE_ON_OR_BEFORE_MONTH_START"),
            "target_calendar_days": calendar_days,
            "end_reference_date": latest.isoformat(),
            "currency_strength_log_pp": {},
            "currency_order": [],
            "pair_returns_pct": {},
            "top10": [],
            "has_executable_bid_ask": False,
            "publishable": False,
            "trade_authorized": False,
        }
    weekly = historical_window(7)
    monthly = historical_window(30)
    if weekly is None or monthly is None:
        return _blocked("NUMERIC_RANGE_INVALID")
    result = _blocked("REFERENCE_ONLY_NOT_TRADEABLE")
    result.update({
        "state": "RESEARCH_ONLY", "complete_pairs": 28,
        "reference_date": latest.isoformat(),
        "previous_reference_date": previous.isoformat(),
        "reference_age_days": (current.date() - latest).days,
        "same_day_reference": current.date() == latest,
        "source_claim": "ECB_EURO_REFERENCE_XML_OFFLINE",
        "official_documentation_url": OFFICIAL_REFERENCE_URL,
        "direct_eur_fixes": 7,
        "derived_non_eur_crosses": 21,
        "all_pairs_are_derived_reference_rates": True,
        "has_executable_bid_ask": False,
        "rates": dict(new),
        "pair_returns_pct": daily["pair_returns_pct"],
        "currency_strength_log_pp": daily["currency_strength_log_pp"],
        "currency_order": daily["currency_order"],
        "top10": daily["top10"],
        "max_algebraic_residual_log_pp": daily["max_algebraic_residual_log_pp"],
        "research_windows": {"D1": daily, "W1": weekly, "MN1": monthly},
        "monthly_window_is_rolling_30_calendar_days": True,
        "notice": "Historical ECB reference only: D1/W1/MN1 are ex-post, not Forex live, spread, signal or accuracy.",
    })
    return result


__all__ = ["SCHEMA", "OFFICIAL_REFERENCE_URL", "analyze_ecb_reference_xml"]

