"""Retrospective publisher-page research inventory for the 28 G8 crosses.

This catalogues *which currencies* have official research pages for inflation
and policy by a conservative publisher boundary. The pages were inspected in
November 2026; historical copies at each decision have NOT been attested.
It cannot produce economic strength, scores, backtests or trading instructions.
No network, MetaTrader or account access is performed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_gbp_nzd_official_pilot_lab import (
    inspect_gbp_nzd_publisher_pilot_lab,
)
from atlasquant_trader_usd_eur_official_pilot_lab import (
    inspect_usd_eur_official_pilot_lab,
)
from atlasquant_trader_aud_cad_official_pilot_lab import (
    inspect_aud_cad_official_pilot_lab,
)

SCHEMA = "ATLASQUANT_TRADER_G8_OFFICIAL_RESEARCH_COVERAGE_LAB_V1"
REQUIRED_FAMILIES = ("INFLATION", "POLICY")
HORIZONS = ("D1", "W1")


def _empty(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_RESEARCH_COVERAGE_BLOCKED", "reason": reason,
        "horizon": None, "decision_at_utc": None,
        "currency_count": 0, "pair_count": 0, "currencies": {}, "pairs": {},
        "two_sided_research_pairs": 0, "one_sided_research_pairs": 0,
        "zero_sided_research_pairs": 0,
        "publisher_page_research_only": True,
        "original_point_in_time_vintage_attested": False,
        "issuer_values_independently_authenticated": False,
        "historical_backtest_approved": False,
        "cross_currency_strength_comparison_approved": False,
        "validated_directional_accuracy": None, "forecast_probability": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "new_cost_brl": 0,
    }


def inspect_g8_official_research_coverage_lab(
    *, decision_at_utc: datetime, horizon: str,
) -> dict[str, Any]:
    """List research coverage by currency and pair; never release numeric data.

    Chronological publisher-boundary passes are NOT historical evidence of
    an immutable contemporaneous data vintage. Do not use this as a source
    adapter for the separately guarded G8 macro as-of claim pipeline.
    """
    out = _empty("INVALID_HORIZON_OR_DECISION_CLOCK")
    if (horizon not in HORIZONS or not isinstance(decision_at_utc, datetime)
            or decision_at_utc.tzinfo is None or decision_at_utc.utcoffset() is None
            or decision_at_utc.microsecond != 0):
        return out
    if len(CURRENCIES) != 8 or len(OFFICIAL_PAIRS) != 28:
        out["reason"] = "NONCANONICAL_FX_UNIVERSE"
        return out

    decision = decision_at_utc.astimezone(timezone.utc)
    catalogs = (
        inspect_gbp_nzd_publisher_pilot_lab(decision_at_utc=decision),
        inspect_usd_eur_official_pilot_lab(decision_at_utc=decision),
        inspect_aud_cad_official_pilot_lab(decision_at_utc=decision),
    )
    currencies: dict[str, dict[str, Any]] = {}
    for currency in CURRENCIES:
        family_keys: dict[str, list[str]] = {family: [] for family in REQUIRED_FAMILIES}
        for catalog in catalogs:
            for key, row in catalog["observations"].items():
                if (row["currency"] == currency
                        and row["family"] in family_keys
                        and row["publisher_timing_status"] ==
                        "AFTER_CONSERVATIVE_PUBLISHER_BOUNDARY_ONLY"):
                    family_keys[row["family"]].append(key)
        for keys in family_keys.values():
            keys.sort()
        present = [family for family, keys in family_keys.items() if keys]
        currencies[currency] = {
            "family_research_keys": family_keys,
            "researched_families": sorted(present),
            "missing_families": sorted(set(REQUIRED_FAMILIES) - set(present)),
            "two_family_publisher_research": len(present) == len(REQUIRED_FAMILIES),
            "original_release_vintage_attested": False,
            "backtest_approved": False,
        }

    pairs: dict[str, dict[str, Any]] = {}
    totals = {0: 0, 1: 0, 2: 0}
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        sides = int(currencies[base]["two_family_publisher_research"]) + int(
            currencies[quote]["two_family_publisher_research"])
        totals[sides] += 1
        pairs[pair] = {
            "base": base, "quote": quote,
            "fully_researched_currency_sides": sides,
            "coverage": ("TWO_SIDED_RESEARCH_ONLY" if sides == 2 else
                         "ONE_SIDED_RESEARCH_ONLY" if sides == 1 else
                         "NO_TWO_FAMILY_RESEARCH"),
            "historical_pit_verified": False,
            "all_macroeconomic_drivers_verified": False,
            "backtest_approved": False,
            "operational_bias": "AGUARDAR",
        }

    out.update({
        "state": "LAB_RETROSPECTIVE_OFFICIAL_RESEARCH_INVENTORY_ONLY",
        "reason": "PUBLISHER_BOUNDARIES_NOT_PIT_ATTESTATION",
        "horizon": horizon, "decision_at_utc": decision.isoformat(),
        "currency_count": len(currencies), "pair_count": len(pairs),
        "currencies": currencies, "pairs": pairs,
        "two_sided_research_pairs": totals[2],
        "one_sided_research_pairs": totals[1],
        "zero_sided_research_pairs": totals[0],
    })
    return out


__all__ = ["SCHEMA", "REQUIRED_FAMILIES", "HORIZONS", "inspect_g8_official_research_coverage_lab"]
