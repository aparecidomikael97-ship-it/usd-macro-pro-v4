"""FX28 Motor A: 32 actual-source slots vs 28 hypothetical score firewall.

This is a NEW, offline, read-only diagnostic seam. A documentary CPI, PPI or
policy-rate original is NOT a positive/negative FX impact, and a synthetic
relative score is NOT a calibrated probabilistic forecast. Reject malformed
or contradictory admission reports; never allow a hypothetical score into
the operational D1/W1/M1 bias, probabilities, alerts or trade decisions.

No HTTP, MT5, GitHub, files, orders, background jobs, scheduler or deploy.
"""
from __future__ import annotations

from typing import Any
import re

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_fx28_32_factor_source_admission_lab import (
    SCHEMA as ADMISSION_SCHEMA,
)
from atlasquant_trader_fx28_macro_relative_score_prototype_lab import (
    SCHEMA as HYPOTHETICAL_SCHEMA,
)

SCHEMA = "ATLASQUANT_FX28_REAL_SOURCE_TO_HYPOTHETICAL_BIAS_FIREWALL_LAB_V1"
CATEGORIES = (
    "policy_expectations", "inflation_impact", "activity_impact", "labor_impact",
)
EXPECTED_SLOTS = tuple((currency, factor)
                       for currency in sorted(CURRENCIES) for factor in CATEGORIES)
_EXPECTED_PAIRS = tuple(OFFICIAL_PAIRS)
_STATE = "LAB_FX28_32_FACTOR_DOCUMENTARY_GAP_RECONCILED_NO_GO"
_HYP_STATE = "LAB_FX28_HYPOTHETICAL_MACRO_SCORE_COHERENT_NO_GO"
_SHA256_HEX = re.compile(r"[0-9a-f]{64}\\Z")


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_MACRO_SOURCE_TO_BIAS_FIREWALL_BLOCKED_NO_GO",
        "reason": reason,
        "expected_currencies": len(CURRENCIES),
        "expected_fx_pairs": len(OFFICIAL_PAIRS),
        "expected_macro_factor_slots": 32,
        "factor_slots_validated": 0,
        "factor_slots_with_documentary_context": 0,
        "factor_slots_without_documentary_context": 32,
        "factor_slots_with_independently_calibrated_signed_effect": 0,
        "factor_slots_missing_consensus_or_effect_calibration": 32,
        "hypothetical_score_present": False,
        "hypothetical_labeled_pairs_quarantined": 0,
        "hypothetical_currency_points_authorized_as_live_bias": False,
        "hypothetical_score_is_not_calibrated_probability": True,
        "source_sha_does_not_authenticate_publication_or_first_seen": True,
        "issuer_origin_and_point_in_time_independently_verified": False,
        "policy_rate_is_not_policy_expectation": True,
        "post_event_actual_is_not_pre_event_surprise": True,
        "complete_bilateral_factors_for_any_pair": False,
        "macro_event_independence_validated": False,
        "independently_validated_out_of_sample_accuracy": None,
        "calibrated_directional_probability": None,
        "directional_bias": None,
        "monthly_bias_validated": False,
        "operational_bias": "AGUARDAR",
        "pairs": [],
        "by_currency_factor_gaps": {},
        "trade_authorized": False, "publishable": False,
        "live_alert_allowed": False,
        "source_replay_performed_by_this_module": False,
        "scorer_invoked_by_this_module": False,
        "scheduler_modified": False, "production_deployed": False,
        "http_requests": 0, "mt5_calls": 0, "file_writes": 0,
        "new_cost_brl": 0,
    }


def audit_macro_source_to_bias_firewall_lab(
    *, admission_report: Any, hypothetical_score_report: Any = None
) -> dict[str, Any]:
    """Reconcile untrusted existing reports without executing a scorer."""
    out = _base("ADMISSION_REPORT_INVALID_OR_UNTRUSTED")
    a = admission_report
    if (type(a) is not dict or a.get("schema") != ADMISSION_SCHEMA
            or a.get("state") != _STATE
            or a.get("factor_slots_expected") != 32
            or a.get("factor_slots_inspected") != 32
            or a.get("pair_count_expected") != 28
            or type(a.get("factor_slots")) is not list
            or len(a["factor_slots"]) != 32
            or type(a.get("pairs")) is not list
            or len(a["pairs"]) != 28
            or a.get("operational_bias") != "AGUARDAR"
            or a.get("trade_authorized") is not False
            or a.get("publishable") is not False
            or a.get("experimental_score_execution_authorized") is not False
            or a.get("real_directional_forecast_authorized") is not False
            or a.get("model_directional_effects_calibrated") is not False
            or a.get("issuer_identity_and_first_seen_independently_attested") is not False
            or a.get("historical_macro_point_in_time_authenticated") is not False
            or a.get("factor_slots_with_signed_impact_independently_admissible") != 0
            or a.get("factor_slots_with_calibrated_directional_effect") != 0
            or a.get("factor_slots_with_pre_event_consensus_verified") != 0
            or a.get("calibrated_probability") is not None
            or a.get("validated_direction_accuracy") is not None):
        return out
    rows = a["factor_slots"]
    if ([(r.get("currency"), r.get("category"))
         if type(r) is dict else (None, None) for r in rows]
            != list(EXPECTED_SLOTS)):
        out["reason"] = "INCOMPLETE_OR_REORDERED_32_FACTOR_ROSTER"
        return out
    pair_rows = a["pairs"]
    if [r.get("pair") if type(r) is dict else None for r in pair_rows] != list(_EXPECTED_PAIRS):
        out["reason"] = "INCOMPLETE_OR_REORDERED_28_PAIR_ROSTER"
        return out
    if any(type(r) is not dict
           or r.get("operational_bias") != "AGUARDAR"
           or r.get("trade_authorized") is not False
           or r.get("forecast_direction") is not None
           or r.get("calibrated_probability") is not None
           or r.get("model_signed_factor_slots_admitted") != 0
           for r in pair_rows):
        out["reason"] = "FAKE_PAIR_BIAS_OR_SIGNED_FACTOR_IN_SOURCE_REPORT"
        return out

    documented = 0
    by_currency: dict[str, dict[str, str]] = {c: {} for c in sorted(CURRENCIES)}
    for row in rows:
        source = row.get("source_replayed_for_documentary_context_only")
        digest = row.get("documentary_source_sha256_local_claim")
        kind = row.get("documentary_source_kind")
        if (type(source) is not bool
                or (source and
                    (type(digest) is not str
                     or _SHA256_HEX.fullmatch(digest) is None
                     or digest == "0" * 64
                     or type(kind) is not str
                     or not 1 <= len(kind) <= 128
                     or not kind.isascii()
                     or not all(c.isalnum() or c == "_" for c in kind)))
                or (not source and (digest is not None or kind is not None))
                or row.get("source_semantics_support_signed_factor") is not False
                or row.get("pre_event_consensus_independently_attested") is not False
                or row.get("signed_impact_points_admitted") is not None
                or row.get("source_sha_is_not_issuer_or_pit_attestation") is not True
                or type(row.get("missing_model_input_reason")) is not str
                or not row["missing_model_input_reason"]):
            out["reason"] = "SLOT_SOURCE_DOCUMENT_OR_SIGNED_EFFECT_CONTRADICTION"
            return out
        documented += int(source)
        by_currency[row["currency"]][row["category"]] = (
            "DOCUMENT_ONLY_NO_SIGNED_EFFECT" if source else
            "NO_DOCUMENT_OR_ADMISSIBLE_EFFECT"
        )

    if (type(a.get("factor_slots_with_any_relevant_local_document")) is not int
            or documented != a["factor_slots_with_any_relevant_local_document"]):
        out["reason"] = "DOCUMENTARY_FACTOR_COUNT_INFLATED_OR_INCOMPLETE"
        return out

    hypothetical_count = 0
    if hypothetical_score_report is not None:
        h = hypothetical_score_report
        if (type(h) is not dict or h.get("schema") != HYPOTHETICAL_SCHEMA
                or h.get("state") != _HYP_STATE
                or h.get("score_is_synthetic_relative_points_not_economic_measure") is not True
                or h.get("inputs_are_authenticated_macro_sources") is not False
                or h.get("prospective_forecast_witnessed") is not False
                or h.get("out_of_sample_accuracy_measured") is not False
                or h.get("calibrated_probability") is not None
                or h.get("directional_bias") is not None
                or h.get("trade_authorized") is not False
                or h.get("publishable") is not False
                or type(h.get("pairs")) is not list
                or len(h["pairs"]) != 28
                or [p.get("pair") if type(p) is dict else None for p in h["pairs"]]
                    != list(_EXPECTED_PAIRS)):
            out["reason"] = "HYPOTHETICAL_REPORT_FAKE_GO_OR_INVALID_SHAPE"
            return out
        for p in h["pairs"]:
            if (p.get("trade_authorized") is not False
                    or p.get("real_market_direction_authenticated") is not False
                    or p.get("research_relative_label") not in
                       ("AGUARDAR", "NEUTRAL", "BASE_RELATIVE", "QUOTE_RELATIVE")):
                out["reason"] = "HYPOTHETICAL_PAIR_CONTAINS_LIVE_AUTHORIZATION"
                return out
        hypothetical_count = sum(
            p["research_relative_label"] in ("BASE_RELATIVE", "QUOTE_RELATIVE")
            for p in h["pairs"]
        )
        if (type(h.get("hypothetical_labeled_pair_count")) is not int
                or h["hypothetical_labeled_pair_count"] != hypothetical_count):
            out["reason"] = "HYPOTHETICAL_LABEL_COUNT_INCONSISTENT"
            return out

    out.update({
        "state": "LAB_FX28_DOCUMENTARY_HYPOTHESIS_SEPARATION_VERIFIED_NO_GO",
        "reason": "ZERO_VERIFIED_SIGNED_FACTORS_NO_REAL_PROBABILISTIC_BIAS",
        "factor_slots_validated": 32,
        "factor_slots_with_documentary_context": documented,
        "factor_slots_without_documentary_context": 32 - documented,
        "factor_slots_missing_consensus_or_effect_calibration": 32,
        "hypothetical_score_present": hypothetical_score_report is not None,
        "hypothetical_labeled_pairs_quarantined": hypothetical_count,
        "by_currency_factor_gaps": by_currency,
        "pairs": [{
            "pair": pair, "bias": "AGUARDAR",
            "directional_probability": None,
            "document_is_not_market_effect": True,
            "trade_authorized": False,
        } for pair in _EXPECTED_PAIRS],
    })
    return out


__all__ = ("SCHEMA", "audit_macro_source_to_bias_firewall_lab")
