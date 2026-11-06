"""Compose 16 retrospective official-page references into a 28-pair map.

Reference completeness is NOT PIT authenticity, consistent macro units,
currency strength, validated predictions, D1/W1 bias, or trade permission.
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

SCHEMA = "ATLASQUANT_TRADER_G8_EIGHT_CURRENCY_DOCUMENTARY_COVERAGE_LAB_V1"
VALID_STATES = frozenset((
    "LAB_FOUR_DOCUMENT_REFERENCES_VISIBLE_BUT_PIT_UNATTESTED",
    "LAB_EIGHT_DOCUMENT_REFERENCES_VISIBLE_BUT_PIT_UNATTESTED",
    "LAB_PARTIAL_DOCUMENT_CONTEXT_ONLY_NO_FX_BIAS",
))


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "accepted_casebook_sha256_by_group": {},
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


def inspect_g8_eight_currency_documentary_coverage_lab(
    *, eurusd_casebook_raw: Any, gbpjpy_casebook_raw: Any,
    remaining_four_casebook_raw: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Count documentation by pair; keep every direction at AGUARDAR."""
    out = _blocked("INVALID_CASEBOOK_OR_CLOCK_OR_G8_UNIVERSE")
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
    if any(r["state"] not in VALID_STATES for r in reports):
        return out

    seen: dict[str, dict[str, str | None]] = {
        c: {"INFLATION": None, "POLICY": None} for c in CURRENCIES
    }
    for report in reports:
        for doc in report["visible_documents_as_retrospective_references"]:
            currency, family = doc["currency"], doc["family"]
            if (currency not in seen or family not in seen[currency]
                    or seen[currency][family] is not None):
                return out
            seen[currency][family] = doc["record_id"]

    documented_currencies = sorted(
        c for c, families in seen.items() if all(families.values())
    )
    pairs: list[dict[str, Any]] = []
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        family_status = {
            f: ("BOTH_OFFICIAL_PAGE_REFERENCES_VISIBLE_UNATTESTED"
                if seen[base][f] and seen[quote][f]
                else "ONE_OR_BOTH_PAGE_REFERENCES_NOT_SUPPLIED_ASOF")
            for f in ("INFLATION", "POLICY")
        }
        complete = all(v == "BOTH_OFFICIAL_PAGE_REFERENCES_VISIBLE_UNATTESTED"
                       for v in family_status.values())
        pairs.append({
            "pair": pair, "base": base, "quote": quote,
            "documentary_family_status": family_status,
            "both_currencies_have_cpi_and_policy_page_references_claim_only": complete,
            "direct_statistical_or_rate_comparability_verified": False,
            "D1": "AGUARDAR", "W1": "AGUARDAR", "trade_authorized": False,
        })
    covered_pairs = [
        p["pair"] for p in pairs
        if p["both_currencies_have_cpi_and_policy_page_references_claim_only"]
    ]
    all_docs = sum(r["visible_document_count"] for r in reports)
    fully_documented = all_docs == 16 and len(covered_pairs) == 28
    out.update({
        "state": "LAB_G8_28_PAIR_DOCUMENTARY_COVERAGE_NO_DIRECTIONAL_BIAS",
        "reason": "REFERENCES_ONLY_NO_PIT_ATTESTATION_NO_NORMALIZED_MACRO_SIGNAL",
        "accepted_casebook_sha256_by_group": {
            "EUR_USD": reports[0]["accepted_casebook_sha256"],
            "GBP_JPY": reports[1]["accepted_casebook_sha256"],
            "CHF_AUD_CAD_NZD": reports[2]["accepted_casebook_sha256"],
        },
        "currency_count": len(CURRENCIES), "pair_count": len(OFFICIAL_PAIRS),
        "document_references_visible": all_docs,
        "currency_family_document_coverage": seen,
        "currencies_with_both_families_documented_claim_only": documented_currencies,
        "pairs_with_both_sides_documented_claim_only": covered_pairs,
        "pair_count_with_two_sided_four_family_documents": len(covered_pairs),
        "pairs": pairs,
        "complete_8_currency_16_source_documentary_coverage": fully_documented,
    })
    return out


__all__ = ["SCHEMA", "inspect_g8_eight_currency_documentary_coverage_lab"]
