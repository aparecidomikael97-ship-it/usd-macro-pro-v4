"""Reconcile caller-supplied ECB XML with frozen Nov 2-4 reference transcript.

This LAB check detects inconsistency; a match is NOT publisher-origin proof.
The reference transcript and expected ECB-format XML are not two independent
market-data sources. SHA-256 proves only the identity of supplied bytes.
No live signal, no forecast score, no network or automatic scheduling.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from atlasquant_trader_ecb_g8_xml_reference_history_lab import (
    inspect_ecb_g8_xml_reference_history_lab,
)
from atlasquant_trader_ecb_g8_three_day_reference_moves_lab import (
    DAYS, REFS, SOURCE_PAGES,
)

SCHEMA = "ATLASQUANT_ECB_G8_XML_VS_TRANSCRIPTION_RECONCILIATION_LAB_V1"
CURRENCIES_TO_COMPARE = ("USD", "GBP", "JPY", "CHF", "AUD", "CAD", "NZD")


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "reference_days": list(DAYS), "transcription_page_urls": dict(SOURCE_PAGES),
        "reference_currency_count": len(CURRENCIES_TO_COMPARE),
        "expected_reference_cells": len(DAYS) * len(CURRENCIES_TO_COMPARE),
        "matched_reference_cells": 0, "mismatched_reference_cells": [],
        "raw_xml_sha256": None, "raw_xml_bytes": None,
        "xml_structure_recognized": False,
        "transcription_consistent_with_supplied_xml": False,
        "original_xml_origin_authenticated": False,
        "transcription_independently_authenticated": False,
        "publication_instant_independently_witnessed": False,
        "historical_vintage_point_in_time_verified": False,
        "independent_broker_m15_prices_verified": False,
        "historical_directional_accuracy_verified": False,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "can_feed_live_radar": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "publishable": False, "new_cost_brl": 0,
        "external_http_requests": 0,
    }


def reconcile_ecb_g8_xml_against_transcript_lab(
    raw_xml: Any, *, captured_at_utc: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Compare 21 EUR-base cells to source-shaped XML without authenticating it.

    A mismatch always blocks the reconciliation. Even complete equality is
    only structural agreement between supplied data and a manual transcript.
    """
    out = _blocked("XML_UNAVAILABLE_OR_INVALID")
    parsed = inspect_ecb_g8_xml_reference_history_lab(
        raw_xml, captured_at_utc=captured_at_utc, as_of_utc=as_of_utc,
        requested_dates=list(DAYS),
    )
    if parsed["state"] != "LAB_G8_XML_REFERENCE_CROSSES_STRUCTURALLY_PARSED_UNATTESTED":
        out["reason"] = "XML_READER_BLOCKED_" + parsed["reason"]
        return out
    rows = {item["pair"]: item for item in parsed["pairs"]}
    if len(rows) != 28:
        out["reason"] = "XML_28_PAIR_REGISTRY_INCOMPLETE"
        return out
    mismatches: list[dict[str, str]] = []
    matches = 0
    for day in DAYS:
        for currency in CURRENCIES_TO_COMPARE:
            observed_row = rows.get(f"EUR/{currency}")
            if observed_row is None:
                out["reason"] = "MISSING_REQUIRED_EUR_CROSS"
                return out
            candidate = observed_row[
                "reference_rates_derived_from_ecb_eur_legs"
            ].get(day)
            expected = REFS[day][currency]
            if not isinstance(candidate, str):
                out["reason"] = "MISSING_REQUESTED_XML_DAY_VALUE"
                return out
            if Decimal(candidate) != Decimal(expected):
                mismatches.append({
                    "reference_day": day, "currency": currency,
                    "manual_reference": expected,
                    "supplied_xml_reference": candidate,
                })
            else:
                matches += 1
    out.update({
        "matched_reference_cells": matches,
        "mismatched_reference_cells": mismatches,
        "raw_xml_sha256": parsed["source_raw_sha256"],
        "raw_xml_bytes": parsed["source_bytes"],
        "xml_structure_recognized": True,
    })
    if mismatches:
        out["reason"] = "XML_AND_MANUAL_REFERENCE_DISAGREE_NO_SILENT_REPAIR"
        return out
    out.update({
        "state": "LAB_XML_TRANSCRIPTION_STRUCTURAL_MATCH_UNATTESTED",
        "reason": "21_VALUES_AGREE_BUT_ORIGINAL_HTTP_AND_HISTORICAL_VINTAGE_UNVERIFIED",
        "transcription_consistent_with_supplied_xml": True,
    })
    return out


__all__ = [
    "SCHEMA", "CURRENCIES_TO_COMPARE",
    "reconcile_ecb_g8_xml_against_transcript_lab",
]
