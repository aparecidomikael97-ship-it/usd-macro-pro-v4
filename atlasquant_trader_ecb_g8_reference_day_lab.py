"""Frozen ECB 2026-11-04 G8 daily reference cross arithmetic, LAB ONLY.

Quotes were manually transcribed from ECB and Banca d'Italia public pages,
NOT the original XML response. Derived cross rates are NOT executable prices,
M15 bars, historical vintages, predictive biases or currency strength.
"""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any
from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_TRADER_ECB_G8_ONE_DAY_REFERENCE_LAB_V1"
ECB_URL = "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html"
ITALY_URL = "https://www.bancaditalia.it/compiti/operazioni-cambi/cambio/cambi_rif_20261104/?com.dotmarketing.htmlpage.language=1"
XML_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"
EUR_QUOTES = {"EUR": "1", "USD": "1.1267", "GBP": "0.83460", "JPY": "178.30",
              "CHF": "0.9188", "AUD": "1.6061", "CAD": "1.5701", "NZD": "1.9988"}
NEXT_DAY = datetime(2026, 11, 5, tzinfo=timezone.utc)


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "observation_date": "2026-11-04", "ecb_page": ECB_URL,
        "italy_archive": ITALY_URL, "original_xml_url": XML_URL,
        "entry_mode": "MANUALLY_TRANSCRIBED_PUBLIC_REFERENCE_VALUES",
        "research_as_of_utc": None,
        "original_xml_bytes_obtained": False, "source_raw_sha256": None,
        "source_original_http_authenticated": False,
        "release_instant_verified": False, "point_in_time_vintage_verified": False,
        "broker_m15_execution_quotes_verified": False,
        "historical_accuracy_verified": False,
        "currency_count": 0, "pair_count": 0, "eur_quotes": {}, "pairs": [],
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "can_feed_live_radar": False,
        "publishable": False, "worker_enabled": False, "scheduler_enabled": False,
        "external_http_requests": 0, "new_cost_brl": 0,
    }


def build_ecb_g8_reference_day_lab(*, as_of_utc: Any) -> dict[str, Any]:
    result = _base("AS_OF_INVALID_OR_NOT_AFTER_REFERENCE_DATE")
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None):
        return result
    as_of = as_of_utc.astimezone(timezone.utc)
    # Conservative safety boundary, not a witnessed release timestamp.
    if as_of < NEXT_DAY:
        return result
    if (set(CURRENCIES) != set(EUR_QUOTES) or len(OFFICIAL_PAIRS) != 28
            or len({frozenset(split_pair(p)) for p in OFFICIAL_PAIRS}) != 28):
        return _base("CANONICAL_G8_28_REGISTRY_CHANGED")
    rates = {k: Decimal(v) for k, v in EUR_QUOTES.items()}
    pairs = []
    for symbol in OFFICIAL_PAIRS:
        base, quote = split_pair(symbol)
        derived = (rates[quote] / rates[base]).quantize(
            Decimal("0.00000001"), rounding=ROUND_HALF_EVEN)
        pairs.append({
            "pair": symbol, "unit": f"{quote}_PER_1_{base}",
            "derived_reference_rate": format(derived, "f"),
            "base_eur_reference": EUR_QUOTES[base],
            "quote_eur_reference": EUR_QUOTES[quote],
            "observed_broker_quote": False, "trade_authorized": False,
            "currency_strength_rank": None, "fx_bias": None,
            "D1": "AGUARDAR", "W1": "AGUARDAR",
        })
    result.update({
        "state": "LAB_ECB_G8_ONE_DAY_REFERENCE_CROSS_ARITHMETIC_ONLY",
        "reason": "WEB_TRANSCRIPTION_NOT_XML_OR_EXECUTABLE_M15_DATA",
        "research_as_of_utc": as_of.isoformat(), "currency_count": 8,
        "pair_count": 28, "eur_quotes": dict(EUR_QUOTES), "pairs": pairs,
    })
    return result


__all__ = ["SCHEMA", "ECB_URL", "ITALY_URL", "XML_URL", "EUR_QUOTES",
           "build_ecb_g8_reference_day_lab"]
