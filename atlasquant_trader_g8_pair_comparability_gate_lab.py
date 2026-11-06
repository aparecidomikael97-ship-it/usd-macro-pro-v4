"""Document-period audit for G8 / 28 crosses, NOT a macro ranking.

Reads the SHA-pinned retrospective cases and asks whether CPI observation
periods even coincide. Equal months alone NEVER imply comparable methodology,
comparable monetary policy stance, a verified point-in-time vintage or FX edge.
No cross-currency numeric subtraction, HTTP, signals, or live publication.
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

SCHEMA = "ATLASQUANT_TRADER_G8_PAIR_COMPARABILITY_GATE_LAB_V1"
VALID_SOURCE_STATES = frozenset((
    "LAB_FOUR_DOCUMENT_REFERENCES_VISIBLE_BUT_PIT_UNATTESTED",
    "LAB_EIGHT_DOCUMENT_REFERENCES_VISIBLE_BUT_PIT_UNATTESTED",
    "LAB_PARTIAL_DOCUMENT_CONTEXT_ONLY_NO_FX_BIAS",
))
EVIDENCE_GATES_NOT_MET = (
    "OFFICIAL_ORIGINAL_BYTES_WITH_TIME_ATTESTATION",
    "HISTORICAL_POINT_IN_TIME_MACRO_VINTAGES",
    "CPI_METHODS_AND_FREQUENCIES_HARMONIZED",
    "CENTRAL_BANK_POLICY_STANCE_AND_EXPECTATIONS_HARMONIZED",
    "PRE_EVENT_CONSENSUS_ATTESTED",
    "PROSPECTIVE_D1_W1_PRICE_OUTCOMES_INDEPENDENTLY_VALIDATED",
)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "as_of_utc": None, "currencies_in_universe": 0,
        "pairs_in_universe": 0, "official_page_references_visible": 0,
        "monthly_same_period_pair_count_document_only": 0,
        "monthly_different_period_pair_count_document_only": 0,
        "mixed_quarterly_monthly_pair_count_document_only": 0,
        "pairs_missing_cpi_or_policy_asof": 0,
        "pair_rows": [], "evidence_gates_not_met": list(EVIDENCE_GATES_NOT_MET),
        "original_source_bytes_attested": False,
        "source_publication_time_independently_attested": False,
        "cpi_series_cross_country_comparable": False,
        "policy_stance_cross_country_comparable": False,
        "consensus_available_pre_event": False,
        "historical_price_outcomes_validated": False,
        "validated_prediction_count": 0, "validated_accuracy": None,
        "ranked_currencies": [], "best_pair_of_day": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "can_feed_live_radar": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0, "new_cost_brl": 0,
    }


def inspect_g8_pair_comparability_gate_lab(
    *, eurusd_casebook_raw: Any, gbpjpy_casebook_raw: Any,
    remaining_four_casebook_raw: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Identify pair-level CPI period blockers, never synthesize direction."""
    out = _blocked("INVALID_CASEBOOK_CLOCK_OR_UNIVERSE")
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None or len(CURRENCIES) != 8
            or len(OFFICIAL_PAIRS) != 28):
        return out
    now = as_of_utc.astimezone(timezone.utc)
    reports = (
        inspect_eurusd_nov6_official_asof_lab(eurusd_casebook_raw, as_of_utc=now),
        inspect_gbpjpy_nov6_official_asof_lab(gbpjpy_casebook_raw, as_of_utc=now),
        inspect_g8_remaining_four_official_asof_lab(
            remaining_four_casebook_raw, as_of_utc=now),
    )
    if any(report["state"] not in VALID_SOURCE_STATES for report in reports):
        return out

    by_currency: dict[str, dict[str, dict[str, Any] | None]] = {
        c: {"INFLATION": None, "POLICY": None} for c in CURRENCIES
    }
    for report in reports:
        for doc in report["visible_documents_as_retrospective_references"]:
            c, f = doc["currency"], doc["family"]
            if c not in by_currency or f not in by_currency[c] or by_currency[c][f] is not None:
                return out
            by_currency[c][f] = doc

    counter = {"MONTHLY_SAME_PERIOD_DOCUMENT_ONLY": 0,
               "MONTHLY_DIFFERENT_PERIOD": 0,
               "MONTHLY_VS_QUARTERLY": 0,
               "DOCUMENTS_NOT_YET_ADMISSIBLE_ASOF": 0}
    rows = []
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        b, q = by_currency[base], by_currency[quote]
        complete = all(v is not None for v in (b["INFLATION"], b["POLICY"],
                                                  q["INFLATION"], q["POLICY"]))
        bp = b["INFLATION"]["reference_period"] if b["INFLATION"] else None
        qp = q["INFLATION"]["reference_period"] if q["INFLATION"] else None
        if not complete:
            status = "DOCUMENTS_NOT_YET_ADMISSIBLE_ASOF"
        elif "-Q" in bp or "-Q" in qp:
            status = "MONTHLY_VS_QUARTERLY"
        elif bp == qp:
            status = "MONTHLY_SAME_PERIOD_DOCUMENT_ONLY"
        else:
            status = "MONTHLY_DIFFERENT_PERIOD"
        counter[status] += 1
        rows.append({
            "pair": pair, "base": base, "quote": quote,
            "inflation_base_period": bp, "inflation_quote_period": qp,
            "inflation_period_audit": status,
            "both_sides_cpi_and_policy_page_references_visible": complete,
            "official_page_values_historically_authenticated": False,
            "same_period_means_comparable_inflation": False,
            "policy_instrument_comparability_verified": False,
            "macro_score_available": False,
            "D1": "AGUARDAR", "W1": "AGUARDAR", "trade_authorized": False,
        })

    visible = sum(r["visible_document_count"] for r in reports)
    out.update({
        "state": "LAB_28_PAIR_COMPARABILITY_AUDIT_NO_FX_BIAS",
        "reason": "PERIOD_MATCH_ALONE_IS_NOT_A_VERIFIED_MACRO_COMPARISON",
        "as_of_utc": now.isoformat(),
        "currencies_in_universe": len(CURRENCIES),
        "pairs_in_universe": len(OFFICIAL_PAIRS),
        "official_page_references_visible": visible,
        "monthly_same_period_pair_count_document_only": counter[
            "MONTHLY_SAME_PERIOD_DOCUMENT_ONLY"],
        "monthly_different_period_pair_count_document_only": counter[
            "MONTHLY_DIFFERENT_PERIOD"],
        "mixed_quarterly_monthly_pair_count_document_only": counter[
            "MONTHLY_VS_QUARTERLY"],
        "pairs_missing_cpi_or_policy_asof": counter[
            "DOCUMENTS_NOT_YET_ADMISSIBLE_ASOF"],
        "pair_rows": rows,
    })
    return out


__all__ = ["SCHEMA", "EVIDENCE_GATES_NOT_MET",
           "inspect_g8_pair_comparability_gate_lab"]
