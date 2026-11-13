"""Real offline documentary evidence -> 32-slot macro factor admission (NO-GO).

This module closes the dangerous seam between:
  8 local issuer *policy-rate* original-byte receipts + BLS Oct 2026 PPI
  and the separate 8-currency × 4-*hypothetical impact* FX28 prototype.

A raw central bank policy RATE is NOT a monetary-policy EXPECTATION.
A US producer price ACTUAL is NOT a pre-release CPI surprise, a calibrated
currency impact, or independent inflation evidence for EUR, GBP, JPY etc.
Activity and labor forecasts require separately witnessed sources too.

Matching SHA-256 against an accepted local file verifies which *claimed*
original bytes were referenced. It does NOT prove the file came from its
claimed publisher, when it was first available, that economic data were
known pre-event, or that signed impact points have any predictive basis.

The gate calls the REAL eight-issuer+PPI local source verifier. This
module NEVER calls the experimental score function, makes predictions,
publishes forecasts, issues trades, downloads, reads broker data,
writes files, starts workers or changes the 672 opportunity campaign.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_fx28_macro_relative_score_prototype_lab import (
    HypotheticalMacroFactorClaim, WEIGHTS,
)
from atlasquant_trader_fx28_policy_ppi_unified_readiness_lab import (
    SCHEMA as UNIFIED_SCHEMA,
    inspect_fx28_policy_ppi_readiness_lab,
)
from atlasquant_trader_us_bls_cpi_u_nsa_mom_capture_lab import (
    replay_bls_cpi_u_nsa_original_lab,
)

SCHEMA = "ATLASQUANT_FX28_SOURCE_BACKED_32_FACTOR_ADMISSION_LAB_V1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_GOOD = "LAB_FX28_POLICY_PPI_COMBINED_READONLY_NO_GO"
_CATEGORIES = (
    "policy_expectations", "inflation_impact",
    "activity_impact", "labor_impact",
)
_EXPECTED_SLOTS = frozenset(
    (currency, category)
    for currency in CURRENCIES for category in _CATEGORIES
)


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_32_FACTOR_ADMISSION_BLOCKED_NO_GO",
        "reason": reason,
        "currency_count_expected": 8,
        "factor_categories_expected": list(_CATEGORIES),
        "factor_slots_expected": 32,
        "factor_slots_inspected": 0,
        "factor_slots": [],
        "pair_count_expected": 28,
        "pairs": [],
        "source_audit_state": "NOT_ATTEMPTED",
        "source_audit_reason": None,
        "locally_replayed_policy_issuer_count": 0,
        "locally_replayed_ppi_document_count": 0,
        "locally_replayed_cpi_u_nsa_document_count": 0,
        "cpi_u_nsa_oct2026_mom_pct_documentary": None,
        "cpi_u_nsa_is_not_pre_event_surprise": True,
        "cpi_u_nsa_oct2026_yoy_unavailable_missing_oct2025": True,
        "cpi_u_nsa_is_not_authenticated_first_print_vintage": True,
        "distinct_original_document_sha_claim_count": 0,
        "factor_slots_with_any_relevant_local_document": 0,
        "factor_slots_with_signed_impact_independently_admissible": 0,
        "factor_slots_with_pre_event_consensus_verified": 0,
        "factor_slots_with_calibrated_directional_effect": 0,
        "hypothetical_factor_claims_provided": False,
        "hypothetical_factor_claims_structurally_valid": False,
        "hypothetical_claims_matching_local_original_sha_only": 0,
        "hypothetical_claims_without_matching_documentary_source": 0,
        "ppi_is_one_shared_us_event_not_seven_independent_inflation_events": True,
        "ppi_actuals_are_not_cpi_consensus_or_usd_direction": True,
        "policy_rates_are_not_forward_policy_expectations": True,
        "hash_match_only_proves_local_byte_consistency": True,
        "issuer_identity_and_first_seen_independently_attested": False,
        "historical_macro_point_in_time_authenticated": False,
        "bilateral_cpi_and_pre_event_consensus_authenticated": False,
        "rate_expectation_surprises_authenticated": False,
        "activity_and_labor_suprisal_effects_authenticated": False,
        "broker_m15_price_history_authenticated": False,
        "model_directional_effects_calibrated": False,
        "fx28_forecast_witnessed_before_window": False,
        "experimental_score_execution_authorized": False,
        "real_directional_forecast_authorized": False,
        "validated_direction_accuracy": None,
        "calibrated_probability": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "network_requests": 0,
        "file_writes": 0,
        "scheduler_enabled": False,
        "worker_enabled": False,
        "new_cost_brl": 0,
        "research_only": True,
    }


def _claim_source_map(value: Any, now: datetime) -> dict[tuple[str, str], str] | None:
    if value is None:
        return {}
    if type(value) not in (tuple, list) or len(value) != len(_EXPECTED_SLOTS):
        return None
    seen: dict[tuple[str, str], str] = {}
    for claim in value:
        if (not isinstance(claim, HypotheticalMacroFactorClaim)
                or claim.currency not in CURRENCIES
                or claim.category not in _CATEGORIES
                or type(claim.signed_impact_points) is not int
                or not -100 <= claim.signed_impact_points <= 100
                or type(claim.source_sha256_claim) is not str
                or _SHA.fullmatch(claim.source_sha256_claim) is None
                or claim.source_sha256_claim == "0"*64):
            return None
        pub = _utc(claim.event_published_at_utc)
        captured = _utc(claim.source_locally_captured_at_utc)
        key = (claim.currency, claim.category)
        if (pub is None or captured is None or pub > captured
                or captured > now or key in seen):
            return None
        seen[key] = claim.source_sha256_claim
    return seen if set(seen) == _EXPECTED_SLOTS else None


def _trusted_unified(r: Any) -> bool:
    if (type(r) is not dict or r.get("schema") != UNIFIED_SCHEMA
            or r.get("state") != _GOOD
            or r.get("operational_bias") != "AGUARDAR"
            or r.get("trade_authorized") is not False
            or r.get("publishable") is not False
            or r.get("historical_macro_point_in_time_authenticated") is not False
            or r.get("bls_first_seen_independently_authenticated") is not False
            or r.get("broker_m15_authenticated") is not False
            or r.get("model_calibrated_for_fx28") is not False
            or r.get("ppi_can_be_fx28_directional_factor") is not False
            or r.get("fx28_pairs_reported") != 28
            or r.get("ppi_is_one_shared_catalyst_not_seven_independent_news")
                is not True):
        return False
    rows = r.get("per_pair")
    if (type(rows) is not list or len(rows) != len(OFFICIAL_PAIRS)
            or [x.get("pair") if type(x) is dict else None for x in rows]
               != list(OFFICIAL_PAIRS)):
        return False
    if any(x.get("trade_authorized") is not False
           or x.get("bias") != "AGUARDAR"
           or x.get("ppi_fx_impact_calculated") is not False
           for x in rows):
        return False
    ledger = r.get("policy_source_byte_sha_lineage_by_currency")
    if type(ledger) is not dict or any(k not in CURRENCIES for k in ledger):
        return False
    if (type(r.get("policy_source_originals_with_reproducible_sha_claims"))
            is not int or
            len(ledger) != r["policy_source_originals_with_reproducible_sha_claims"]):
        return False
    for doc in ledger.values():
        if (type(doc) is not dict
                or type(doc.get("source_original_sha256_local_claim")) is not str
                or _SHA.fullmatch(doc["source_original_sha256_local_claim"]) is None
                or doc.get("origin_pit_authenticated") != "false"):
            return False
    ppi = r.get("ppi_source_raw_sha256")
    n = r.get("ppi_documentary_series_count")
    if (ppi is not None and (type(ppi) is not str or
                             _SHA.fullmatch(ppi) is None or n != 3)
            or ppi is None and n != 0):
        return False
    return True


def inspect_fx28_32_factor_source_admission_lab(
    *, local_appdata: Any, decision_at_utc: Any,
    ppi_archive_basename: Any = None,
    cpi_archive_basename: Any = None,
    hypothetical_factors: Any = None,
) -> dict[str, Any]:
    """Pure caller-side inspection except real read-only LOCAL archive replay."""
    out = _blocked("INVALID_DECISION_TIME_OR_32_FACTOR_CONTRACT")
    now = _utc(decision_at_utc)
    if (now is None or type(local_appdata) is not str
            or not local_appdata
            or type(ppi_archive_basename) not in (str, type(None))
            or ppi_archive_basename == ""
            or type(cpi_archive_basename) not in (str, type(None))
            or cpi_archive_basename == ""
            or tuple(WEIGHTS) != _CATEGORIES
            or len(CURRENCIES) != 8 or len(OFFICIAL_PAIRS) != 28):
        return out
    inputs = _claim_source_map(hypothetical_factors, now)
    if inputs is None:
        out["reason"] = "INVALID_OR_FUTURE_HYPOTHETICAL_FACTOR_CLAIMS"
        out["hypothetical_factor_claims_provided"] = hypothetical_factors is not None
        return out
    out["hypothetical_factor_claims_provided"] = hypothetical_factors is not None
    out["hypothetical_factor_claims_structurally_valid"] = hypothetical_factors is not None
    try:
        source = inspect_fx28_policy_ppi_readiness_lab(
            local_appdata=local_appdata,
            decision_at_utc=now,
            ppi_archive_basename=ppi_archive_basename,
        )
    except (OSError, ValueError, KeyError, TypeError, RuntimeError,
            OverflowError):
        out["reason"] = "REAL_SOURCE_REPLAY_EXCEPTION_NO_FALLBACK"
        return out
    out["source_audit_state"] = (
        source.get("state") if type(source) is dict else "INVALID_RESULT")
    out["source_audit_reason"] = (
        source.get("reason") if type(source) is dict else "INVALID_RESULT")
    if not _trusted_unified(source):
        out["reason"] = "SOURCE_AUDIT_REPORT_MALFORMED_OR_GO_FORGED"
        return out
    ledger = source["policy_source_byte_sha_lineage_by_currency"]
    ppi = source["ppi_source_raw_sha256"]
    # The CPI-U official v1 index levels are a distinct US source from PPI.
    # This is a read-only replay of already captured bytes, never a GET.
    cpi_report = (
        replay_bls_cpi_u_nsa_original_lab(
            local_appdata=local_appdata,
            archive_basename=cpi_archive_basename,
            observed_at_utc=now,
        ) if cpi_archive_basename is not None else None
    )
    cpi_ok = (type(cpi_report) is dict
        and cpi_report.get("state") ==
            "LAB_US_BLS_CPI_U_NSA_MOM_LOCAL_DOCUMENT_REPLAY_NO_GO"
        and cpi_report.get("raw_original_bytes_retained_and_replayed_local_only")
            is True
        and cpi_report.get("source_first_seen_independently_attested") is False
        and cpi_report.get("asof_historical_vintage_authenticated") is False
        and cpi_report.get("independent_pre_release_consensus_authenticated")
            is False
        and cpi_report.get("trade_authorized") is False
        and cpi_report.get("fx28_direction_authorized") is False
        and cpi_report.get("calibrated_probability") is None
        and cpi_report.get("series_id") == "CUUR0000SA0"
        and cpi_report.get("seasonal_adjustment") == "NSA"
        and cpi_report.get("target_month") == "2026-10"
        and cpi_report.get("base_month") == "2026-09"
        and type(cpi_report.get("raw_body_sha256")) is str
        and _SHA.fullmatch(cpi_report["raw_body_sha256"]) is not None
        and type(cpi_report.get("calculated_mom_nsa_pct_documentary")) is str)
    cpi_sha = cpi_report["raw_body_sha256"] if cpi_ok else None
    source_hashes = {
        doc["source_original_sha256_local_claim"] for doc in ledger.values()
    }
    if ppi is not None:
        source_hashes.add(ppi)
    if cpi_sha is not None:
        source_hashes.add(cpi_sha)
    slots = []
    matched = 0
    documented = 0
    missing_matched = 0
    for currency in sorted(CURRENCIES):
        for category in _CATEGORIES:
            doc = ledger.get(currency)
            has_rate = doc is not None
            if category == "policy_expectations":
                documentary_sha = (
                    doc["source_original_sha256_local_claim"] if has_rate else None)
                reason = ("POLICY_RATE_IS_NOT_FORWARD_RATE_EXPECTATIONS"
                          if has_rate else "NO_LOCAL_POLICY_RATE_SOURCE")
                kind = "POLICY_RATE_ACTUAL_NOT_EXPECTATIONS" if has_rate else None
            elif category == "inflation_impact":
                documentary_sha = (
                    cpi_sha if currency == "USD" and cpi_sha is not None
                    else ppi if currency == "USD" else None)
                reason = (
                    "BLS_CPI_U_NSA_MOM_NOT_PRE_EVENT_CONSENSUS_OR_USD_IMPACT"
                    if currency == "USD" and cpi_sha is not None else
                    "BLS_PPI_ACTUAL_NOT_CPI_SURPRISE_OR_CURRENCY_EFFECT"
                    if currency == "USD" and ppi is not None else
                    "NO_CURRENCY_CPI_SURPRISE_WITH_PRE_EVENT_CONSENSUS")
                kind = (
                    "BLS_CPI_U_NSA_OCT2026_MOM_LOCAL_CALCULATION_ONLY"
                    if currency == "USD" and cpi_sha is not None else
                    "BLS_PPI_OCT2026_ACTUAL_ONLY" if documentary_sha else None)
            elif category == "activity_impact":
                documentary_sha, kind = None, None
                reason = "NO_ACTIVITY_SURPRISE_WITH_INDEPENDENT_PIT_CONSENSUS"
            else:
                documentary_sha, kind, recent = None, None, False
                reason = "NO_LABOR_SURPRISE_WITH_INDEPENDENT_PIT_CONSENSUS"
            documented += int(documentary_sha is not None)
            claimed = inputs.get((currency, category))
            agreement = (None if claimed is None
                         else claimed == documentary_sha)
            matched += int(agreement is True)
            missing_matched += int(agreement is False)
            slots.append({
                "currency": currency, "category": category,
                "weight_in_hypothetical_prototype_points":
                    WEIGHTS[category],
                "documentary_source_kind": kind,
                "documentary_source_sha256_local_claim": documentary_sha,
                "source_replayed_for_documentary_context_only":
                    documentary_sha is not None,
                "claimed_factor_sha_matches_local_document_only": agreement,
                "source_semantics_support_signed_factor": False,
                "pre_event_consensus_independently_attested": False,
                "signed_impact_points_admitted": None,
                "missing_model_input_reason": reason,
                "source_sha_is_not_issuer_or_pit_attestation": True,
            })
    rows = []
    for original in source["per_pair"]:
        pair = original["pair"]
        base, quote = split_pair(pair)
        rows.append({
            "pair": pair,
            "base_currency": base, "quote_currency": quote,
            "locally_checked_policy_originals_on_both_legs_only":
                original["two_policy_originals_locally_checked"],
            "ppi_is_post_release_context_on_direct_usd_leg_only":
                original["ppi_direct_usd_issuer_leg_documentary_context_replayed"],
            "model_signed_factor_slots_admitted": 0,
            "model_all_eight_macro_factors_for_pair_authenticated": False,
            "forecast_direction": None,
            "calibrated_probability": None,
            "operational_bias": "AGUARDAR",
            "trade_authorized": False,
        })
    out.update({
        "state": "LAB_FX28_32_FACTOR_DOCUMENTARY_GAP_RECONCILED_NO_GO",
        "reason": "SOURCE_BYTES_REPLAYED_NOT_CALIBRATED_SIGNED_MACRO_IMPACTS",
        "factor_slots_inspected": len(slots),
        "factor_slots": slots,
        "pairs": rows,
        "locally_replayed_policy_issuer_count": len(ledger),
        "locally_replayed_ppi_document_count": int(ppi is not None),
        "locally_replayed_cpi_u_nsa_document_count": int(cpi_sha is not None),
        "cpi_u_nsa_oct2026_mom_pct_documentary": (
            cpi_report["calculated_mom_nsa_pct_documentary"] if cpi_ok else None),
        "distinct_original_document_sha_claim_count": len(source_hashes),
        "factor_slots_with_any_relevant_local_document": documented,
        "hypothetical_claims_matching_local_original_sha_only": matched,
        "hypothetical_claims_without_matching_documentary_source": missing_matched,
    })
    return out


__all__ = ("SCHEMA", "inspect_fx28_32_factor_source_admission_lab")
