"""Bridge EUR/USD and GBP/JPY official document cases to G8/28 coverage.

An inventory of RETROSPECTIVE PUBLIC PAGES is not authenticated market data,
not independent historical point-in-time capture, not inflation comparability,
not currency strength and not 28 tradable Forex signals.
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

SCHEMA = "ATLASQUANT_TRADER_G8_FOUR_CURRENCY_DOCUMENTARY_COVERAGE_LAB_V1"
FAMILIES = ("INFLATION", "POLICY")
DOCUMENT_OK = frozenset((
    "LAB_FOUR_DOCUMENT_REFERENCES_VISIBLE_BUT_PIT_UNATTESTED",
    "LAB_PARTIAL_DOCUMENT_CONTEXT_ONLY_NO_FX_BIAS",
))


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "documentary_source_case_sha256": {},
        "currency_count": 0, "pair_count": 0,
        "document_references_visible": 0,
        "currency_family_document_coverage": {},
        "currencies_with_both_families_documented_claim_only": [],
        "pairs_with_both_sides_documented_claim_only": [],
        "pair_count_with_two_sided_four_family_documents": 0,
        "pairs": [],
        "complete_8_currency_16_source_documentary_coverage": False,
        "official_document_original_bytes_attested": False,
        "source_publication_times_independently_witnessed": False,
        "vintage_and_statistical_method_comparability_verified": False,
        "independent_currency_strength_ranking_verified": False,
        "all_28_pairs_directionally_verified": False,
        "validated_prediction_count": 0, "validated_accuracy": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False, "trade_authorized": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0, "new_cost_brl": 0,
    }


def inspect_g8_four_currency_documentary_coverage_lab(
    *, eurusd_casebook_raw: Any, gbpjpy_casebook_raw: Any,
    as_of_utc: Any,
) -> dict[str, Any]:
    """Produce coverage status for ALL 28 crosses, zero buy/sell directions."""
    out = _blocked("INVALID_CLOCK_OR_CASEBOOK_OR_G8_UNIVERSE")
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None or len(CURRENCIES) != 8
            or len(OFFICIAL_PAIRS) != 28):
        return out
    now = as_of_utc.astimezone(timezone.utc)
    eurusd = inspect_eurusd_nov6_official_asof_lab(
        eurusd_casebook_raw, as_of_utc=now)
    gbpjpy = inspect_gbpjpy_nov6_official_asof_lab(
        gbpjpy_casebook_raw, as_of_utc=now)
    if eurusd["state"] not in DOCUMENT_OK or gbpjpy["state"] not in DOCUMENT_OK:
        return out
    seen: dict[str, dict[str, str | None]] = {
        c: {family: None for family in FAMILIES} for c in CURRENCIES}
    for report in (eurusd, gbpjpy):
        for doc in report["visible_documents_as_retrospective_references"]:
            currency, family = doc["currency"], doc["family"]
            if seen[currency][family] is not None:
                return out
            seen[currency][family] = doc["record_id"]
    covered = sorted(c for c, fam in seen.items() if all(fam.values()))
    pairs = []
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        families = {family: ("BOTH_OFFICIAL_PAGE_REFERENCES_VISIBLE_UNATTESTED"
                             if seen[base][family] and seen[quote][family]
                             else "ONE_OR_BOTH_PAGE_REFERENCES_NOT_SUPPLIED_ASOF")
                    for family in FAMILIES}
        complete = all(v == "BOTH_OFFICIAL_PAGE_REFERENCES_VISIBLE_UNATTESTED"
                       for v in families.values())
        pairs.append({
            "pair": pair, "base": base, "quote": quote,
            "documentary_family_status": families,
            "both_currencies_have_cpi_and_policy_page_references_claim_only": complete,
            "direct_statistical_or_rate_comparability_verified": False,
            "D1": "AGUARDAR", "W1": "AGUARDAR", "trade_authorized": False,
        })
    documented = [p["pair"] for p in pairs
                  if p["both_currencies_have_cpi_and_policy_page_references_claim_only"]]
    out.update({
        "state": "LAB_G8_28_PAIR_FOUR_CURRENCY_DOCUMENTARY_MAP_NO_BIAS",
        "reason": "ONLY_FOUR_CURRENCIES_HAVE_UNATTESTED_PAGE_REFERENCE_COVERAGE",
        "documentary_source_case_sha256": {
            "EUR_USD": eurusd["accepted_casebook_sha256"],
            "GBP_JPY": gbpjpy["accepted_casebook_sha256"]},
        "currency_count": len(CURRENCIES), "pair_count": len(OFFICIAL_PAIRS),
        "document_references_visible": (
            eurusd["visible_document_count"] + gbpjpy["visible_document_count"]),
        "currency_family_document_coverage": seen,
        "currencies_with_both_families_documented_claim_only": covered,
        "pairs_with_both_sides_documented_claim_only": documented,
        "pair_count_with_two_sided_four_family_documents": len(documented),
        "pairs": pairs,
    })
    return out


__all__ = ["SCHEMA", "inspect_g8_four_currency_documentary_coverage_lab"]
