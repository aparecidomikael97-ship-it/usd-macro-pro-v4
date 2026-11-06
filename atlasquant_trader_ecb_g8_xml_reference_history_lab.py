"""Offline G8/28-pair cross-reference reader for caller-supplied ECB 90d XML.

XML syntax and local SHA-256 are NOT publisher authentication, a witnessed
release vintage, actionable FX prices, or a broker M15 series. No networking.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from hashlib import sha256
import re
from typing import Any
from xml.etree import ElementTree as ET

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_TRADER_ECB_G8_XML_90D_REFERENCE_READER_LAB_V1"
SOURCE_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"
ECB_NS = "{http://www.ecb.int/vocabulary/2002-08-01/eurofxref}"
GESMES_NS = "{http://www.gesmes.org/xml/2002-08-01}"
MAX_BYTES = 400_000
MAX_DAYS = 110
MAX_CURRENCIES = 60
RATE = re.compile(r"(?:0|[1-9]\d{0,7})(?:\.\d{1,8})?\Z")
DAY = re.compile(r"20\d{2}-\d\d-\d\d\Z")
RATE_QUANT = Decimal("0.00000001")
RETURN_QUANT = Decimal("0.0001")
NON_EUR_G8 = frozenset(CURRENCIES) - {"EUR"}


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "source_url": SOURCE_URL, "reference_kind": "ECB_EUR_BASED_DAILY_INDICATIVE",
        "source_raw_sha256": None, "source_bytes": None,
        "capture_clock_claim_utc": None, "as_of_utc": None,
        "requested_dates": [], "xml_observation_count": 0,
        "currency_count": 0, "pair_count": 0,
        "observed_interval_count": 0, "pairs": [],
        "xml_structure_verified": False,
        "xml_bytes_original_http_origin_authenticated": False,
        "official_publication_instant_independently_attested": False,
        "archived_point_in_time_vintage_verified": False,
        "independent_broker_m15_prices_verified": False,
        "licensing_for_commercial_market_data_verified": False,
        "historical_accuracy_verified": False,
        "currency_strength_rank": None, "fx_bias": None,
        "D1": "AGUARDAR", "W1": "AGUARDAR",
        "trade_authorized": False, "can_feed_live_radar": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "external_http_requests": 0,
        "new_cost_brl": 0,
    }


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None):
        return None
    return value.astimezone(timezone.utc)


def _day(value: Any) -> date | None:
    if not isinstance(value, str) or DAY.fullmatch(value) is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _rate(value: Any) -> Decimal:
    if not isinstance(value, str) or RATE.fullmatch(value) is None:
        raise ValueError("malformed EUR reference quote")
    try:
        v = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("invalid ECB decimal") from error
    if not Decimal("0.000001") <= v <= Decimal("1000000"):
        raise ValueError("out-of-range ECB reference quote")
    return v


def inspect_ecb_g8_xml_reference_history_lab(
    raw: Any, *, captured_at_utc: Any, as_of_utc: Any,
    requested_dates: Any,
) -> dict[str, Any]:
    """Return 28 reference crosses on 2-10 specifically requested past days.

    Exact requested dates must be PRESENT; never backfill a missing bank day.
    Cross movement is retrospective and not a point-in-time model evaluation.
    """
    out = _deny("INVALID_INPUT_OR_CLOCK")
    captured, as_of = _utc(captured_at_utc), _utc(as_of_utc)
    if (captured is None or as_of is None or captured > as_of
            or not isinstance(raw, bytes) or not 250 <= len(raw) <= MAX_BYTES
            or not isinstance(requested_dates, (list, tuple))
            or not 2 <= len(requested_dates) <= 10):
        return out
    days = [_day(x) for x in requested_dates]
    if (any(x is None for x in days)
            or list(days) != sorted(set(days))
            or any(x.weekday() >= 5 for x in days)
            or days[-1] >= captured.date()):
        out["reason"] = "REQUESTED_DATE_OR_CONSERVATIVE_CAPTURE_BOUND_INVALID"
        return out
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper() or b"\x00" in raw:
        out["reason"] = "DTD_ENTITY_OR_NULL_DISALLOWED"
        return out
    if (len(OFFICIAL_PAIRS) != 28 or len(CURRENCIES) != 8
            or NON_EUR_G8 != frozenset(("USD", "GBP", "JPY", "CHF",
                                        "AUD", "CAD", "NZD"))):
        out["reason"] = "REGISTRY_DRIFT"
        return out
    try:
        root = ET.fromstring(raw)
        if root.tag != GESMES_NS + "Envelope" or root.attrib:
            return out
        header = list(root)
        if ([x.tag for x in header] != [
                GESMES_NS + "subject", GESMES_NS + "Sender", ECB_NS + "Cube"]):
            return out
        if ((header[0].text or "").strip() != "Reference rates"
                or header[0].attrib or list(header[0])):
            return out
        sender = list(header[1])
        if (header[1].attrib or len(sender) != 1
                or sender[0].tag != GESMES_NS + "name"
                or (sender[0].text or "").strip() != "European Central Bank"):
            return out
        if header[2].attrib:
            return out
        rows = list(header[2])
        if not 2 <= len(rows) <= MAX_DAYS:
            out["reason"] = "UNEXPECTED_XML_HISTORY_SIZE"
            return out
        observations: dict[date, dict[str, Decimal]] = {}
        previous: date | None = None
        for node in rows:
            if (node.tag != ECB_NS + "Cube"
                    or set(node.attrib) != {"time"}):
                return out
            d = _day(node.attrib["time"])
            if (d is None or d.weekday() >= 5
                    or previous is not None and d >= previous
                    or d > captured.date()):
                out["reason"] = "INVALID_UNSORTED_OR_FUTURE_REFERENCE_DAY"
                return out
            previous = d
            quotes: dict[str, Decimal] = {"EUR": Decimal("1")}
            leaves = list(node)
            if not 1 <= len(leaves) <= MAX_CURRENCIES:
                return out
            for leaf in leaves:
                if (leaf.tag != ECB_NS + "Cube" or list(leaf)
                        or set(leaf.attrib) != {"currency", "rate"}):
                    return out
                symbol = leaf.attrib["currency"]
                if (re.fullmatch(r"[A-Z]{3}", symbol) is None
                        or symbol in quotes):
                    out["reason"] = "DUPLICATE_INVALID_OR_EUR_RATE"
                    return out
                quotes[symbol] = _rate(leaf.attrib["rate"])
            observations[d] = quotes
        if not set(days).issubset(observations):
            out["reason"] = "REQUESTED_DAY_MISSING_NO_FORWARD_FILL"
            return out
        if any(not NON_EUR_G8.issubset(observations[d]) for d in days):
            out["reason"] = "G8_EUR_BASE_QUOTES_MISSING"
            return out
        derived_rows = []
        for pair in OFFICIAL_PAIRS:
            base, quote = split_pair(pair)
            exact = {d: observations[d][quote] / observations[d][base] for d in days}
            moves = {}
            for earlier, later in zip(days, days[1:]):
                pct = (exact[later] / exact[earlier] - 1) * 100
                moves[f"{earlier.isoformat()}_to_{later.isoformat()}"] = format(
                    pct.quantize(RETURN_QUANT, rounding=ROUND_HALF_EVEN), "f")
            derived_rows.append({
                "pair": pair, "unit": f"{quote}_PER_1_{base}",
                "reference_rates_derived_from_ecb_eur_legs": {
                    d.isoformat(): format(
                        exact[d].quantize(RATE_QUANT, rounding=ROUND_HALF_EVEN), "f")
                    for d in days
                },
                "observed_reference_moves_percent": moves,
                "prices_are_executable": False,
                "forecast_existed_before_move_attested": False,
                "currency_strength_rank": None, "fx_bias": None,
                "D1": "AGUARDAR", "W1": "AGUARDAR", "trade_authorized": False,
            })
        out.update({
            "state": "LAB_G8_XML_REFERENCE_CROSSES_STRUCTURALLY_PARSED_UNATTESTED",
            "reason": "CALLER_SUPPLIED_XML_NO_AUTHENTIC_RELEASE_OR_BROKER_PRICE",
            "source_raw_sha256": sha256(raw).hexdigest(),
            "source_bytes": len(raw), "capture_clock_claim_utc": captured.isoformat(),
            "as_of_utc": as_of.isoformat(),
            "requested_dates": [d.isoformat() for d in days],
            "xml_observation_count": len(observations),
            "currency_count": 8, "pair_count": 28,
            "observed_interval_count": 28 * (len(days) - 1),
            "xml_structure_verified": True,
            "pairs": derived_rows,
        })
        return out
    except (ET.ParseError, TypeError, ValueError, OverflowError,
            InvalidOperation, ArithmeticError):
        out["reason"] = "MALFORMED_XML_OR_REFERENCE_RATE"
        return out


__all__ = ["SCHEMA", "SOURCE_URL", "inspect_ecb_g8_xml_reference_history_lab"]
