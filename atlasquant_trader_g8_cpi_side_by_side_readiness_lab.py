"""D1/W1 readiness contract: two real-world documentary CPI claims per FX pair.

The 8 frozen official-page casebooks and 8 next CPI calendar entries are joined
without manufacturing a numeric differential. Source-page transcriptions are
NOT independently witnessed historical vintages or an FX trading edge.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_eurusd_nov6_official_asof_lab import (
    inspect_eurusd_nov6_official_asof_lab,
)
from atlasquant_trader_gbpjpy_nov6_official_asof_lab import (
    inspect_gbpjpy_nov6_official_asof_lab,
)
from atlasquant_trader_g8_remaining_four_official_asof_lab import (
    inspect_g8_remaining_four_official_asof_lab,
)
from atlasquant_trader_g8_pair_comparability_gate_lab import (
    inspect_g8_pair_comparability_gate_lab,
)
from atlasquant_trader_g8_eight_next_cpi_schedules_lab import (
    inspect_g8_eight_next_cpi_schedules_lab,
)

SCHEMA = "ATLASQUANT_TRADER_G8_CPI_DOCUMENTARY_SIDE_BY_SIDE_D1W1_READINESS_LAB_V1"
CALENDAR_READY = "LAB_8_CURRENCIES_28_PAIRS_TWO_CALENDAR_DATES_EACH_NO_FX_BIAS"
MACRO_READY = "LAB_28_PAIR_COMPARABILITY_AUDIT_NO_FX_BIAS"
EXPECTED_SOURCE_CLAIM_FIELD_AND_TEXT = {
    "EUR": ("annual_flash_hicp_yoy", "4.0"),
    "USD": ("annual_cpi_yoy", "3.7"),
    "GBP": ("annual_cpi_yoy", "3.5"),
    "JPY": ("annual_national_cpi_yoy", "2.1"),
    "CHF": ("annual_cpi_yoy", "1.5"),
    "AUD": ("annual_cpi_yoy", "4.3"),
    "CAD": ("annual_cpi_yoy", "3.1"),
    "NZD": ("annual_quarterly_cpi_yoy", "3.7"),
}
EXPECTED_DOCUMENTARY_SOURCE_STATE = frozenset((
    "LAB_FOUR_DOCUMENT_REFERENCES_VISIBLE_BUT_PIT_UNATTESTED",
    "LAB_EIGHT_DOCUMENT_REFERENCES_VISIBLE_BUT_PIT_UNATTESTED",
))
ALWAYS_MISSING_GATES = (
    "ORIGINAL_SOURCE_BYTES_WITH_EXACT_RETRIEVAL_TIME_NOT_ATTESTED",
    "PRE_EVENT_MARKET_CONSENSUS_NOT_ATTESTED",
    "CROSS_COUNTRY_CPI_METHODOLOGY_NOT_HARMONIZED",
    "PROSPECTIVE_D1_W1_PRICE_VALIDATION_MISSING",
)
VALID_PERIOD_CLASSES = frozenset((
    "MONTHLY_SAME_PERIOD_DOCUMENT_ONLY",
    "MONTHLY_DIFFERENT_PERIOD", "MONTHLY_VS_QUARTERLY",
))


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "as_of_utc": None, "research_snapshot_date": "2026-11-06",
        "source_page_references": 0, "calendar_event_references": 0,
        "documented_currencies": 0, "pair_count": 0,
        "monthly_same_period_pair_count": 0,
        "monthly_different_period_pair_count": 0,
        "monthly_vs_quarterly_pair_count": 0,
        "pair_rows": [], "ranked_currencies": [],
        "best_pair_of_day": None, "market_surprises": {},
        "tradable_relative_cpi_spreads": {},
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "validated_forward_prediction_count": 0,
        "validated_accuracy": None,
        "can_feed_live_radar": False, "trade_authorized": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0, "new_cost_brl": 0,
        "source_original_bytes_independently_attested": False,
        "historical_point_in_time_vintages_attested": False,
        "pre_event_consensus_attested": False,
        "cross_country_methods_harmonized": False,
    }


def _inflation_side(document: dict[str, Any]) -> dict[str, Any]:
    currency = document["currency"]
    field, expected = EXPECTED_SOURCE_CLAIM_FIELD_AND_TEXT[currency]
    reported = document["reported_values_percent_document_claim"]
    if (not isinstance(reported, dict)
            or reported.get(field) != expected
            or not isinstance(document.get("reference_period"), str)
            or not isinstance(document.get("source_url"), str)
            or not isinstance(document.get("measurement_kind"), str)):
        raise ValueError("unexpected or changed official-page CPI claim")
    return {
        "currency": currency,
        "source_record_id": document["record_id"],
        "source_url": document["source_url"],
        "reference_period": document["reference_period"],
        "frequency": ("QUARTERLY" if "-Q" in document["reference_period"]
                      else "MONTHLY"),
        "measurement_kind": document["measurement_kind"],
        "annual_rate_percent_as_source_page_text_only": reported[field],
        "annual_rate_field_in_source": field,
        "is_provisional_flash_estimate": currency == "EUR",
        "historical_point_in_time_attested": False,
        "original_source_response_archived": False,
    }


def inspect_g8_cpi_side_by_side_readiness_lab(
    *, five_calendar_casebook_raw: Any, three_calendar_casebook_raw: Any,
    eurusd_macro_casebook_raw: Any, gbpjpy_macro_casebook_raw: Any,
    remaining_four_macro_casebook_raw: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Join official-calendar and documentary CPI metadata; no trade inference."""
    out = _blocked("INVALID_CLOCK_OR_PARENT_PROVENANCE_OR_CPI_METHOD")
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None
            or len(CURRENCIES) != 8 or len(OFFICIAL_PAIRS) != 28):
        return out
    now = as_of_utc.astimezone(timezone.utc)
    calendar = inspect_g8_eight_next_cpi_schedules_lab(
        five_calendar_casebook_raw=five_calendar_casebook_raw,
        three_calendar_casebook_raw=three_calendar_casebook_raw,
        as_of_utc=now,
    )
    macro = inspect_g8_pair_comparability_gate_lab(
        eurusd_casebook_raw=eurusd_macro_casebook_raw,
        gbpjpy_casebook_raw=gbpjpy_macro_casebook_raw,
        remaining_four_casebook_raw=remaining_four_macro_casebook_raw,
        as_of_utc=now,
    )
    # Fail closed before this research existed, even though some older releases
    # were historically published in October. Never backfill this JOIN earlier.
    if calendar["state"] == "LAB_RESEARCH_NOT_VISIBLE_AT_ASOF":
        out["state"] = "LAB_JOIN_NOT_ADMISSIBLE_ASOF"
        out["reason"] = "JOIN_RESEARCH_CANNOT_LEAK_TO_PRE_NOV7_TIMESTAMPS"
        return out
    if (calendar["state"] != CALENDAR_READY or macro["state"] != MACRO_READY
            or calendar["pair_count"] != 28
            or macro["pairs_in_universe"] != 28
            or macro["official_page_references_visible"] != 16
            or calendar["source_calendar_count"] != 8):
        return out
    sources = (
        inspect_eurusd_nov6_official_asof_lab(eurusd_macro_casebook_raw, as_of_utc=now),
        inspect_gbpjpy_nov6_official_asof_lab(gbpjpy_macro_casebook_raw, as_of_utc=now),
        inspect_g8_remaining_four_official_asof_lab(remaining_four_macro_casebook_raw,
                                                   as_of_utc=now),
    )
    if (any(s["state"] not in EXPECTED_DOCUMENTARY_SOURCE_STATE for s in sources)
            or sum(s["visible_document_count"] for s in sources) != 16):
        return out
    documents = {}
    policies = set()
    for source in sources:
        for doc in source["visible_documents_as_retrospective_references"]:
            currency = doc["currency"]
            if currency not in CURRENCIES:
                return out
            if doc["family"] == "INFLATION":
                if currency in documents:
                    return out
                documents[currency] = doc
            elif doc["family"] == "POLICY":
                if currency in policies:
                    return out
                policies.add(currency)
            else:
                return out
    if (set(documents) != set(CURRENCIES) or policies != set(CURRENCIES)
            or set(EXPECTED_SOURCE_CLAIM_FIELD_AND_TEXT) != set(CURRENCIES)):
        return out
    try:
        sides = {c: _inflation_side(documents[c]) for c in CURRENCIES}
    except (KeyError, TypeError, ValueError, AttributeError):
        return out

    calendar_rows = {r["pair"]: r for r in calendar["pair_rows"]}
    macro_rows = {r["pair"]: r for r in macro["pair_rows"]}
    if (len(calendar_rows) != 28 or len(macro_rows) != 28
            or set(calendar_rows) != set(OFFICIAL_PAIRS)
            or set(macro_rows) != set(OFFICIAL_PAIRS)):
        return out
    pair_rows = []
    counts = {k: 0 for k in VALID_PERIOD_CLASSES}
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        cr, mr = calendar_rows[pair], macro_rows[pair]
        period_class = mr["inflation_period_audit"]
        if (period_class not in VALID_PERIOD_CLASSES
                or cr["base"] != base or cr["quote"] != quote
                or mr["base"] != base or mr["quote"] != quote
                or cr["calendar_currency_count"] != 2
                or mr["inflation_base_period"] != sides[base]["reference_period"]
                or mr["inflation_quote_period"] != sides[quote]["reference_period"]):
            return out
        counts[period_class] += 1
        extra = (
            ["QUARTERLY_VS_MONTHLY_CPI_FREQ_MISMATCH"]
            if period_class == "MONTHLY_VS_QUARTERLY"
            else ["DIFFERENT_CPI_REFERENCE_MONTHS"]
            if period_class == "MONTHLY_DIFFERENT_PERIOD"
            else ["MATCHING_MONTH_DOES_NOT_HARMONIZE_CPI"]
        )
        pair_rows.append({
            "pair": pair, "base": base, "quote": quote,
            "base_last_documentary_cpi": dict(sides[base]),
            "quote_last_documentary_cpi": dict(sides[quote]),
            "base_policy_document_reference_present": True,
            "quote_policy_document_reference_present": True,
            "inflation_reference_period_audit": period_class,
            "next_cpi_date_for_pair": cr["next_calendar_date"],
            "next_cpi_events": list(cr["next_calendar_events"]),
            "all_calendar_events_in_this_snapshot": list(cr["calendar_events"]),
            "missing_prerequisites": [*extra, *ALWAYS_MISSING_GATES],
            "can_compute_cross_currency_inflation_spread": False,
            "macro_readiness": "DOCUMENTARY_CONTEXT_ONLY_NOT_VALIDATED_BIAS",
            "D1": "AGUARDAR", "W1": "AGUARDAR",
            "currency_strength_score": None, "fx_bias": None,
            "trade_authorized": False,
        })
    if sum(counts.values()) != 28:
        return out
    out.update({
        "state": "LAB_28_PAIRS_WITH_TWO_SIDED_CPI_DOCUMENTS_AND_NEXT_EVENTS_NO_BIAS",
        "reason": "CPI_DOCUMENT_CLAIMS_NOT_VINTAGE_CONSENSUS_HARMONIZATION_OR_EDGE",
        "as_of_utc": now.isoformat(),
        "source_page_references": 16,
        "calendar_event_references": 8,
        "documented_currencies": 8, "pair_count": 28,
        "monthly_same_period_pair_count": counts["MONTHLY_SAME_PERIOD_DOCUMENT_ONLY"],
        "monthly_different_period_pair_count": counts["MONTHLY_DIFFERENT_PERIOD"],
        "monthly_vs_quarterly_pair_count": counts["MONTHLY_VS_QUARTERLY"],
        "pair_rows": pair_rows,
    })
    return out


__all__ = ["SCHEMA", "ALWAYS_MISSING_GATES",
           "inspect_g8_cpi_side_by_side_readiness_lab"]
