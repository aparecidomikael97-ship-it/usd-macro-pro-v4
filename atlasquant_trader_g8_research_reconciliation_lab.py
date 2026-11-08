"""Reconcile G8 publisher research evidence against the 28-pair inventory.

The two upstream views describe the SAME unverified retrospective catalog.
Agreement catches drift/missing coverage but is not independent issuer proof,
historical point-in-time certification, a backtest, or a directional signal.
Offline LAB only: no MT5, network, scheduler, orders, or paid service.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_g8_official_research_coverage_lab import (
    REQUIRED_FAMILIES,
    inspect_g8_official_research_coverage_lab,
)
from atlasquant_trader_g8_publication_evidence_audit_lab import (
    inspect_g8_publication_evidence_lab,
)

SCHEMA = "ATLASQUANT_TRADER_G8_RESEARCH_RECONCILIATION_LAB_V1"
HORIZONS = ("D1", "W1")


def _blocked(reason: str, problems: list[str] | None = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_RESEARCH_RECONCILIATION_BLOCKED",
        "reason": reason, "problems": problems or [],
        "decision_at_utc": None, "horizon": None,
        "source_records": 0, "research_available_records": 0,
        "currency_count": 0, "pair_count": 0, "currencies": {}, "pairs": {},
        "two_sided_research_pairs": 0, "one_sided_research_pairs": 0,
        "zero_sided_research_pairs": 0,
        "research_metadata_reconciled": False,
        "independent_source_attestation": False,
        "historical_point_in_time_verified": False,
        "backtest_approved": False, "validated_accuracy": None,
        "directional_probability": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0, "new_cost_brl": 0,
    }


def inspect_g8_research_reconciliation_lab(
    *, decision_at_utc: datetime, horizon: str,
) -> dict[str, Any]:
    """Ensure the claimed 28-pair research inventory matches its source floors.

    Every currency's inflation/policy keys and every pair's researched-side
    count must match the independently constructed metadata view. Any mismatch
    fails closed; even a complete match cannot authorize an operational bias.
    """
    blocked = _blocked("INVALID_DECISION_OR_HORIZON")
    if (horizon not in HORIZONS or not isinstance(decision_at_utc, datetime)
            or decision_at_utc.tzinfo is None or decision_at_utc.utcoffset() is None
            or decision_at_utc.microsecond != 0):
        return blocked

    evidence = inspect_g8_publication_evidence_lab(
        decision_at_utc=decision_at_utc, horizon=horizon)
    coverage = inspect_g8_official_research_coverage_lab(
        decision_at_utc=decision_at_utc, horizon=horizon)
    if (evidence.get("state") != "LAB_RESEARCH_PUBLICATION_EVIDENCE_UNATTESTED"
            or coverage.get("state") != "LAB_RETROSPECTIVE_OFFICIAL_RESEARCH_INVENTORY_ONLY"
            or evidence.get("historical_backtest_approved") is not False
            or coverage.get("historical_backtest_approved") is not False
            or evidence.get("independently_attested_historical_vintages") != 0
            or evidence.get("backtest_ready_pairs") != 0
            or coverage.get("original_point_in_time_vintage_attested") is not False
            or coverage.get("issuer_values_independently_authenticated") is not False
            or coverage.get("cross_currency_strength_comparison_approved") is not False
            or evidence.get("trade_authorized") is not False
            or coverage.get("trade_authorized") is not False):
        return _blocked("UPSTREAM_RESEARCH_NOT_IN_SAFE_STATE")

    issues: list[str] = []
    currencies: dict[str, dict[str, Any]] = {}
    pairs: dict[str, dict[str, Any]] = {}
    counts = {0: 0, 1: 0, 2: 0}
    try:
        source_rows = evidence["sources"]
        inventory_rows = coverage["currencies"]
        pair_rows = coverage["pairs"]
        if (set(inventory_rows) != set(CURRENCIES)
                or set(pair_rows) != set(OFFICIAL_PAIRS)
                or evidence["catalogued_records"] != len(source_rows)
                or coverage["currency_count"] != len(CURRENCIES)
                or coverage["pair_count"] != len(OFFICIAL_PAIRS)):
            return _blocked("NONCANONICAL_RESEARCH_INVENTORY")

        for source in source_rows.values():
            if (source["currency"] not in CURRENCIES
                    or source["family"] not in REQUIRED_FAMILIES
                    or source["historical_vintage_attested"] is not False
                    or source["safe_for_backtest"] is not False):
                return _blocked("SOURCE_CLAIM_OUTSIDE_UNATTESTED_RESEARCH_SCOPE")

        seen_research = 0
        for currency in CURRENCIES:
            expected_keys = {
                family: sorted(key for key, source in source_rows.items()
                               if source["currency"] == currency
                               and source["family"] == family
                               and source["research_by_publisher_boundary"] is True)
                for family in REQUIRED_FAMILIES
            }
            seen_research += sum(len(v) for v in expected_keys.values())
            declared = inventory_rows[currency]
            if declared["family_research_keys"] != expected_keys:
                issues.append(f"{currency}:RESEARCH_KEYS_MISMATCH")
            present = sorted(f for f, keys in expected_keys.items() if keys)
            missing = sorted(set(REQUIRED_FAMILIES) - set(present))
            both = len(missing) == 0
            if (declared["researched_families"] != present
                    or declared["missing_families"] != missing
                    or declared["two_family_publisher_research"] is not both):
                issues.append(f"{currency}:FAMILY_COVERAGE_MISMATCH")
            currencies[currency] = {
                "research_families": present,
                "missing_research_families": missing,
                "publisher_research_only": True,
                "original_vintage_attested": False,
                "backtest_approved": False,
            }

        if evidence["research_available_records"] != seen_research:
            issues.append("TOTAL_RESEARCH_SOURCE_COUNT_MISMATCH")

        for pair in OFFICIAL_PAIRS:
            base, quote = split_pair(pair)
            researched = sum(not currencies[c]["missing_research_families"]
                             for c in (base, quote))
            counts[researched] += 1
            label = ("TWO_SIDED_RESEARCH_ONLY" if researched == 2
                     else "ONE_SIDED_RESEARCH_ONLY" if researched == 1
                     else "NO_TWO_FAMILY_RESEARCH")
            claimed = pair_rows[pair]
            if (claimed["base"] != base or claimed["quote"] != quote
                    or claimed["fully_researched_currency_sides"] != researched
                    or claimed["coverage"] != label
                    or claimed["historical_pit_verified"] is not False
                    or claimed["backtest_approved"] is not False):
                issues.append(f"{pair}:PAIR_COVERAGE_MISMATCH")
            pairs[pair] = {
                "fully_researched_currency_sides": researched,
                "research_coverage": label,
                "missing_research": {
                    currency: currencies[currency]["missing_research_families"]
                    for currency in (base, quote)
                },
                "historical_pit_verified": False,
                "backtest_approved": False,
                "operational_bias": "AGUARDAR",
            }

        if (coverage["two_sided_research_pairs"] != counts[2]
                or coverage["one_sided_research_pairs"] != counts[1]
                or coverage["zero_sided_research_pairs"] != counts[0]):
            issues.append("PAIR_TOTALS_MISMATCH")
        if issues:
            return _blocked("INCONSISTENT_PUBLISHER_RESEARCH_METADATA", issues)

        out = _blocked("RECONCILED_RESEARCH_NOT_PIT_ATTESTATION")
        out.update({
            "state": "LAB_RESEARCH_METADATA_RECONCILED_UNATTESTED",
            "decision_at_utc": evidence["decision_at_utc"], "horizon": horizon,
            "source_records": len(source_rows),
            "research_available_records": seen_research,
            "currency_count": len(currencies), "pair_count": len(pairs),
            "currencies": currencies, "pairs": pairs,
            "two_sided_research_pairs": counts[2],
            "one_sided_research_pairs": counts[1],
            "zero_sided_research_pairs": counts[0],
            "research_metadata_reconciled": True,
        })
        return out
    except (KeyError, TypeError, ValueError):
        return _blocked("MALFORMED_RESEARCH_METADATA")


__all__ = ["SCHEMA", "HORIZONS", "inspect_g8_research_reconciliation_lab"]
