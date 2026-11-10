"""Research inventory: EUR document plus *unattested* US BLS API candidate.

EUR HICP FLASH and US CPI-U are not a harmonized two-sided FX input. This
module calls the existing source gates on bytes, does not trust a claimed JSON
result, and NEVER promotes USD to documentary or operational eligibility.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_g8_cpi_bilateral_coverage_lab import (
    inspect_g8_cpi_bilateral_coverage_lab,
)
from atlasquant_trader_us_bls_cpi_snapshot_asof_lab import (
    inspect_bls_cpi_claimed_snapshot_asof_lab,
)

SCHEMA = "ATLASQUANT_TRADER_G8_CPI_DUAL_SOURCE_READINESS_LAB_V1"
_MONTH = re.compile(r"20\d\d-(?:0[1-9]|1[0-2])\Z")


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond != 0):
        return None
    return value.astimezone(timezone.utc)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_DUAL_CPI_READINESS_BLOCKED",
        "reason": reason, "pair_count": 0, "pairs": {},
        "eur_documentary_crosses": 0,
        "usd_parser_candidate_crosses": 0,
        "eur_usd_dual_pipeline_candidates": 0,
        "two_documented_pairs": 0,
        "usd_reference_period_claim": None,
        "eur_reference_period_claim": None,
        "usd_derived_yoy_claim_research_only": None,
        "usd_response_hash_self_consistent": False,
        "usd_source_authenticated": False,
        "eur_source_first_release_authenticated": False,
        "same_reference_period_for_eur_usd": False,
        "eur_hicp_us_cpi_u_methodology_harmonized": False,
        "country_inflation_rate_difference_directionally_interpretable": False,
        "historical_point_in_time_verified": False,
        "two_sided_macro_comparison_allowed": False,
        "validated_accuracy": None, "calibrated_probability": None,
        "score_0_to_10": None, "operational_bias": "AGUARDAR",
        "publishable": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
    }


def inspect_g8_cpi_dual_source_readiness_lab(
    documentary_by_currency: Any,
    *, usd_raw_response: Any, usd_receipt: Any, usd_reference_period: Any,
    horizon: Any, decision_at_utc: Any, evaluated_at_utc: Any,
) -> dict[str, Any]:
    """Show research readiness without admitting a new issuer as documented.

    USD requires exact BLS API bytes and its *claimed* receipt. No 'today's
    mutable API response was available yesterday' assumption is permitted.
    """
    out = _blocked("INVALID_SOURCE_COVERAGE_OR_EVALUATION_TIME")
    decision, evaluated = _utc(decision_at_utc), _utc(evaluated_at_utc)
    if decision is None or evaluated is None or decision > evaluated:
        return out
    eur_coverage = inspect_g8_cpi_bilateral_coverage_lab(
        documentary_by_currency, horizon=horizon)
    if eur_coverage["state"] != "LAB_CPI_DOCUMENT_COVERAGE_REPORTED_NO_BIAS":
        return out
    if not isinstance(usd_reference_period, str) or _MONTH.fullmatch(usd_reference_period) is None:
        out["reason"] = "USD_REFERENCE_PERIOD_INVALID"
        return out
    # CPI-U for a month cannot be a known complete monthly index before that
    # calendar month has even ended. This is weaker than an authenticated
    # release calendar, but rejects an obvious future-observation injection.
    if usd_reference_period >= decision.strftime("%Y-%m"):
        out["reason"] = "USD_MONTHLY_OBSERVATION_NOT_YET_ENDED_AT_DECISION"
        return out
    bls = inspect_bls_cpi_claimed_snapshot_asof_lab(
        usd_raw_response, usd_receipt,
        reference_period=usd_reference_period,
        decision_at_utc=decision, evaluated_at_utc=evaluated)
    if bls["state"] != "LAB_BLS_CAPTURE_SELF_CONSISTENT_AND_NONFUTURE_UNATTESTED":
        out["reason"] = (
            "USD_CAPTURE_AFTER_DECISION_NO_LOOKAHEAD"
            if bls["state"] == "LAB_BLS_CAPTURE_NOT_VISIBLE_AT_DECISION"
            else "USD_CAPTURE_CLAIM_BEFORE_KNOWN_BLS_RELEASE"
            if bls["state"] == "LAB_BLS_CAPTURE_CLAIM_PRECEDES_OFFICIAL_RELEASE"
            else "USD_BLS_BYTES_RECEIPT_OR_PERIOD_INVALID")
        return out

    eur_present = "EUR" in eur_coverage["documented_currencies"]
    eur_period = documentary_by_currency["EUR"]["reference_period"] if eur_present else None
    both_candidate = int(eur_present)
    pairs = {}
    for pair in OFFICIAL_PAIRS:
        base, quote = pair.split("/")
        has_eur_document = eur_present and "EUR" in (base, quote)
        has_usd_candidate = "USD" in (base, quote)
        combined_research_only = has_eur_document and has_usd_candidate
        pairs[pair] = {
            "base": base, "quote": quote,
            "eur_documentary_only": has_eur_document,
            "usd_api_arithmetic_candidate_only": has_usd_candidate,
            "combined_eur_usd_candidate_only": combined_research_only,
            "both_currency_issuers_authenticated": False,
            "comparable_cpi_concepts_and_periods": False,
            "economic_strength_direction": None,
            "two_sided_macro_comparison_allowed": False,
            "operational_bias": "AGUARDAR", "trade_authorized": False,
        }
    out.update({
        "state": "LAB_EUR_DOCUMENT_USD_API_CANDIDATE_ONLY_NO_BIAS",
        "reason": "USD_API_UNATTESTED_EUR_HICP_US_CPIU_NOT_HARMONIZED",
        "pair_count": len(pairs), "pairs": pairs,
        "eur_documentary_crosses": 7 if eur_present else 0,
        "usd_parser_candidate_crosses": 7,
        "eur_usd_dual_pipeline_candidates": both_candidate,
        "two_documented_pairs": eur_coverage["two_sided_pairs"],
        "usd_reference_period_claim": usd_reference_period,
        "eur_reference_period_claim": eur_period,
        "usd_derived_yoy_claim_research_only": bls["derived_yoy_percent"],
        "usd_response_hash_self_consistent": bls["local_body_hash_self_consistent"],
        "same_reference_period_for_eur_usd": (
            eur_period is not None and eur_period == usd_reference_period),
    })
    return out


__all__ = ["SCHEMA", "inspect_g8_cpi_dual_source_readiness_lab"]
