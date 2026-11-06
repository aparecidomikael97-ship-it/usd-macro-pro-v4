"""Annotate G8 pairs with EUR HICP FLASH and USD CPI MODEL context.

Even for the same month, an official EA21 flash estimate and a US CPI-U model
nowcast are different indicators and forecast stages. They are not comparable
inflation surprises, FX differentials or proven D1/W1 bias. Offline LAB only.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_eurusd_nov6_official_asof_lab import (
    inspect_eurusd_nov6_official_asof_lab,
)
from atlasquant_trader_g8_usd_nowcast_context_routing_lab import (
    inspect_g8_usd_nowcast_context_routing_lab,
)

SCHEMA = "ATLASQUANT_TRADER_G8_EUR_HICP_FLASH_USD_CPI_MODEL_STAGE_CONTEXT_LAB_V1"
EXPECTED_EUR_PAIRS = frozenset((
    "EUR/USD", "EUR/GBP", "EUR/JPY", "EUR/CHF",
    "EUR/CAD", "EUR/AUD", "EUR/NZD",
))
EXPECTED_EUR_DOC_ID = "EUR_EUROSTAT_OCT2026_HICP_FLASH"
EXPECTED_EUR_URL = "https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-04112026-ap"
EXPECTED_EUR_KIND = "EURO_AREA_HICP_ALL_ITEMS_FLASH_ESTIMATE_YOY"
VALID_EUR_STATES = frozenset((
    "LAB_FOUR_DOCUMENT_REFERENCES_VISIBLE_BUT_PIT_UNATTESTED",
    "LAB_PARTIAL_DOCUMENT_CONTEXT_ONLY_NO_FX_BIAS",
))
VALID_USD_STATES = frozenset((
    "LAB_USD_DOCUMENTARY_CONTEXT_ROUTED_TO_7_CROSSES_NO_FX_BIAS",
    "LAB_28_PAIRS_NO_PRE_CPI_FORECAST_VISIBLE_ASOF",
))


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "as_of_utc": None,
        "pair_count": 0, "eur_pair_count": 0, "usd_pair_count": 0,
        "eur_crosses_with_flash_context": 0,
        "usd_crosses_with_model_context": 0,
        "two_sided_eur_usd_context_pairs": 0,
        "crosses_with_either_context": 0,
        "crosses_without_either_context": 0,
        "methodologically_comparable_two_currency_events": 0,
        "pair_rows": [], "ranked_currencies": [],
        "best_pair_of_day": None,
        "verified_market_surprise_by_currency": {},
        "eu_us_inflation_spread_pp": None,
        "relative_eur_usd_strength": None,
        "validated_forward_prediction_count": 0,
        "validated_accuracy": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False, "trade_authorized": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0, "new_cost_brl": 0,
    }


def inspect_g8_eur_hicp_usd_cpi_stage_context_lab(
    *, oct_us_nowcast_raw: Any, nov_us_nowcast_raw: Any,
    eurusd_macro_casebook_raw: Any, gbpjpy_macro_casebook_raw: Any,
    remaining_four_macro_casebook_raw: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Stage-aware metadata routing, not subtraction or direction."""
    out = _base("INVALID_CLOCK_UNIVERSE_OR_PROVENANCE")
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None
            or len(CURRENCIES) != 8 or len(OFFICIAL_PAIRS) != 28
            or {p for p in OFFICIAL_PAIRS if "EUR" in split_pair(p)} != EXPECTED_EUR_PAIRS):
        return out
    now = as_of_utc.astimezone(timezone.utc)
    usd_route = inspect_g8_usd_nowcast_context_routing_lab(
        oct_nowcast_receipt_raw=oct_us_nowcast_raw,
        nov_nowcast_receipt_raw=nov_us_nowcast_raw,
        eurusd_macro_casebook_raw=eurusd_macro_casebook_raw,
        gbpjpy_macro_casebook_raw=gbpjpy_macro_casebook_raw,
        remaining_four_macro_casebook_raw=remaining_four_macro_casebook_raw,
        as_of_utc=now,
    )
    eur_report = inspect_eurusd_nov6_official_asof_lab(
        eurusd_macro_casebook_raw, as_of_utc=now,
    )
    if (usd_route["state"] not in VALID_USD_STATES
            or eur_report["state"] not in VALID_EUR_STATES
            or len(usd_route["pair_rows"]) != 28):
        return out
    eur_docs = [d for d in eur_report["visible_documents_as_retrospective_references"]
                if d["record_id"] == EXPECTED_EUR_DOC_ID]
    if len(eur_docs) > 1:
        return out
    eur_doc = eur_docs[0] if eur_docs else None
    if eur_doc and (
        eur_doc["currency"] != "EUR"
        or eur_doc["family"] != "INFLATION"
        or eur_doc["reference_period"] != "2026-10"
        or eur_doc["source_url"] != EXPECTED_EUR_URL
        or eur_doc["measurement_kind"] != EXPECTED_EUR_KIND
        or eur_doc["reported_values_percent_document_claim"] != {
            "annual_flash_hicp_yoy": "4.0"
        }
    ):
        return out

    rows = []
    for original in usd_route["pair_rows"]:
        pair = original["pair"]
        base, quote = split_pair(pair)
        has_eur = base == "EUR" or quote == "EUR"
        has_usd_context = bool(original["usd_pre_cpi_model_context_documentary_only"])
        has_eur_context = has_eur and eur_doc is not None
        rows.append({
            "pair": pair, "base": base, "quote": quote,
            "eur_role": "BASE" if base == "EUR" else "QUOTE" if quote == "EUR" else "NONE",
            "usd_role": original["usd_role"],
            "eur_hicp_flash_context": ({
                "source": "EUROSTAT_EA21_HICP_FLASH_NOT_FINAL",
                "reference_month": "2026-10",
                "estimated_headline_yoy_percent": 4.0,
                "publication_calendar_date": "2026-11-04",
                "conservative_admissibility_utc": "2026-11-05T00:00:00Z",
                "full_release_scheduled_calendar_date": "2026-11-18",
            } if has_eur_context else None),
            "usd_cpi_model_context": original[
                "usd_pre_cpi_model_context_documentary_only"],
            "usd_current_pre_release_months": original[
                "current_pre_release_usd_forecast_months"],
            "both_sides_show_oct2026_but_different_statistical_stage": (
                has_eur_context and has_usd_context and pair == "EUR/USD"
            ),
            "can_subtract_two_percentages_as_macro_spread": False,
            "comparability_approved": False,
            "currency_strength_score": None,
            "D1": "AGUARDAR", "W1": "AGUARDAR",
            "trade_authorized": False,
        })
    eur_n = sum(r["eur_hicp_flash_context"] is not None for r in rows)
    usd_n = sum(bool(r["usd_cpi_model_context"]) for r in rows)
    intersection = sum(r["eur_hicp_flash_context"] is not None
                       and bool(r["usd_cpi_model_context"]) for r in rows)
    either = sum(r["eur_hicp_flash_context"] is not None
                 or bool(r["usd_cpi_model_context"]) for r in rows)
    if (len(rows) != 28 or eur_n not in (0, 7) or usd_n not in (0, 7)
            or intersection not in (0, 1) or either != eur_n + usd_n - intersection):
        return out
    out.update({
        "state": ("LAB_TWO_CURRENCY_OCTOBER_DIFFERENT_STAGE_CONTEXT_NO_BIAS"
                  if intersection else "LAB_PARTIAL_EUR_USD_DOCUMENTARY_CONTEXT_NO_BIAS"),
        "reason": "EUR_HICP_FLASH_NOT_US_CPI_MODEL_OR_SHARED_EVENT_CONSENSUS",
        "as_of_utc": now.isoformat(),
        "pair_count": 28,
        "eur_pair_count": len(EXPECTED_EUR_PAIRS),
        "usd_pair_count": usd_route["usd_pair_count"],
        "eur_crosses_with_flash_context": eur_n,
        "usd_crosses_with_model_context": usd_n,
        "two_sided_eur_usd_context_pairs": intersection,
        "crosses_with_either_context": either,
        "crosses_without_either_context": 28 - either,
        "pair_rows": rows,
    })
    return out


__all__ = ["SCHEMA", "EXPECTED_EUR_PAIRS",
           "inspect_g8_eur_hicp_usd_cpi_stage_context_lab"]
