"""28 FX crosses: which side has a *documentary-only* CPI observation?

The only real source adapter currently demonstrated is the October 2026
Eurostat EUR FLASH HTML. This is a coverage ledger, not a comparison of CPI
rates, a currency-strength score, PIT evidence or a signal generator.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_g8_cpi_eurostat_semantics_lab import SCHEMA as EUR_DOC_SCHEMA

SCHEMA = "ATLASQUANT_TRADER_G8_CPI_BILATERAL_COVERAGE_LAB_V1"
HORIZONS = ("D1", "W1", "M1")
_MONTH = re.compile(r"20\d\d-(?:0[1-9]|1[0-2])\Z")
_NUM = re.compile(r"(?:0|[1-9][0-9]?)(?:\.[0-9])?\Z")


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_CPI_COVERAGE_BLOCKED", "reason": reason,
        "horizon": None, "currency_count": 0, "pair_count": 0,
        "documented_currencies": [], "undocumented_currencies": [],
        "one_sided_pairs": 0, "two_sided_pairs": 0,
        "no_document_pairs": 0, "pairs": {},
        "value_independently_verified": False,
        "historical_point_in_time_verified": False,
        "two_sided_macro_comparison_allowed": False,
        "economic_value_used_for_direction": False,
        "directional_probability": None, "score_0_to_10": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0,
        "file_writes": 0, "new_cost_brl": 0,
    }


def _safe_decimal(text: Any) -> Decimal | None:
    if not isinstance(text, str) or not _NUM.fullmatch(text):
        return None
    try:
        val = Decimal(text)
        return val if val.is_finite() else None
    except InvalidOperation:
        return None


def _one_supported_eur_document(doc: Any) -> bool:
    """Unforgeable status is NOT claimed: only validates the reader's shape.

    A caller can fabricate any dict; the resulting ledger remains NO-GO.
    """
    if not isinstance(doc, dict):
        return False
    if (doc.get("schema") != EUR_DOC_SCHEMA
            or doc.get("state") != "LAB_EUR_CPI_FLASH_DOCUMENTARY_EXTRACTED_UNATTESTED"
            or doc.get("reference_period") != "2026-10"
            or doc.get("publication_stage") != "FLASH"
            or doc.get("local_archive_integrity_verified") is not True
            or doc.get("same_document_value_consistent") is not True
            or doc.get("operational_bias") != "AGUARDAR"):
        return False
    for field in ("value_independently_verified", "issuer_first_release_authenticated",
                  "clock_independently_authenticated", "historical_point_in_time_eligible",
                  "can_feed_macro_bias", "trade_authorized", "publishable",
                  "scheduler_enabled", "worker_enabled"):
        if doc.get(field) is not False:
            return False
    if (doc.get("file_writes") != 0 or doc.get("new_cost_brl") != 0
            or not isinstance(doc.get("source_publication_timestamp_claim"), str)):
        return False
    period = doc.get("reference_period")
    if not _MONTH.fullmatch(period):
        return False
    current = _safe_decimal(doc.get("documentary_cpi_yoy_percent"))
    previous = _safe_decimal(doc.get("documentary_previous_yoy_percent"))
    return current is not None and previous is not None


def inspect_g8_cpi_bilateral_coverage_lab(
    documentary_by_currency: Any, *, horizon: str,
) -> dict[str, Any]:
    """Inventory a single locally verified EUR document across 28 crosses.

    All other currencies are explicitly missing until their own issuer-specific
    adapters are independently implemented and examined. No as-of inference.
    """
    out = _blocked("INVALID_UNIVERSE_OR_HORIZON")
    if (horizon not in HORIZONS or not isinstance(documentary_by_currency, dict)
            or set(documentary_by_currency) != set(CURRENCIES)
            or len(OFFICIAL_PAIRS) != 28):
        return out
    for currency in CURRENCIES:
        value = documentary_by_currency[currency]
        if currency == "EUR":
            if value is not None and not _one_supported_eur_document(value):
                out["reason"] = "EUR_DOCUMENT_NOT_VERIFIED_OR_NOT_SUPPORTED"
                return out
        elif value is not None:
            out["reason"] = "OTHER_CURRENCY_ISSUER_ADAPTER_NOT_YET_VALIDATED"
            return out

    present = {"EUR"} if documentary_by_currency["EUR"] is not None else set()
    pairs: dict[str, Any] = {}
    one = both = none = 0
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        found = [c for c in (base, quote) if c in present]
        missing = [c for c in (base, quote) if c not in present]
        if len(found) == 2:
            # This cannot happen until a separate source adapter is enabled.
            both += 1
            status = "TWO_DOCUMENTS_UNATTESTED"
        elif len(found) == 1:
            one += 1
            status = "ONE_SIDE_DOCUMENTARY_ONLY"
        else:
            none += 1
            status = "NO_CPI_DOCUMENTS"
        pairs[pair] = {
            "base": base, "quote": quote, "coverage_state": status,
            "documented_currencies": found, "missing_currencies": missing,
            "two_sided_comparison_allowed": False,
            "same_indicator_cross_country_comparable": False,
            "historical_point_in_time_verified": False,
            "operational_bias": "AGUARDAR", "trade_authorized": False,
        }
    out.update({
        "state": "LAB_CPI_DOCUMENT_COVERAGE_REPORTED_NO_BIAS",
        "reason": "SINGLE_UNATTESTED_EUR_DOCUMENT_CANNOT_ESTABLISH_PAIR_BIAS",
        "horizon": horizon, "currency_count": len(CURRENCIES),
        "pair_count": len(pairs), "pairs": pairs,
        "documented_currencies": sorted(present),
        "undocumented_currencies": sorted(set(CURRENCIES) - present),
        "one_sided_pairs": one, "two_sided_pairs": both,
        "no_document_pairs": none,
    })
    return out


__all__ = ["SCHEMA", "HORIZONS", "inspect_g8_cpi_bilateral_coverage_lab"]
