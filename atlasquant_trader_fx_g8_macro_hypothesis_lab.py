"""Experimental deterministic G8/28-pair macro ranking, LAB / HARD NO-GO.

Purpose: specify a fixed, auditable *hypothesis* for future prospective tests.
Inputs are explicitly synthetic signed shocks supplied by tests; they are NOT
actual central-bank/CPI/PMI/employment observations, verified forecasts, macro
surprises, asset prices, probabilities, buy/sell signals, or evidence of accuracy.

Each currency has four signed *hypothetical currency-response impulses* from
-2..+2. In particular CPI sign does NOT follow raw CPI: high inflation can
strengthen or weaken FX depending on monetary-policy expectations.
Missing sources, geopolitics and M15 execution are not silently filled.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_TRADER_FX_G8_MACRO_HYPOTHESIS_SYNTHETIC_LAB_V1"
INPUT = "ATLASQUANT_TRADER_G8_SYNTHETIC_MACRO_FACTORS_V1"
EXPECTED_FIELDS = frozenset(("schema", "data_kind", "horizon", "research_at_utc",
                             "currency_factors"))
FACTORS = ("policy_repricing", "inflation_repricing",
           "growth_surprise", "labor_surprise")
# Research weights (integer total=100): NOT calibrated, not forecasts.
WEIGHTS = {
    "D1": {"policy_repricing": 40, "inflation_repricing": 25,
           "growth_surprise": 20, "labor_surprise": 15},
    "W1": {"policy_repricing": 45, "inflation_repricing": 20,
           "growth_surprise": 20, "labor_surprise": 15},
}
MAX_INPUT_BYTES = 7000
UTC_PATTERN = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
NEUTRAL_DIFF_POINTS = 40
ALLOWED_IMPULSES = (-2, -1, 0, 1, 2)


def _reject(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "model_version": "LAB_MACRO_HYPOTHESIS_WEIGHTS_V1_UNCALIBRATED",
        "input_sha256": None, "horizon": None,
        "synthetic_currency_rank": [], "synthetic_pair_rank": [],
        "currency_count": 0, "pair_count": 0,
        "neutral_pair_count": 0,
        "highest_abs_pair_score": None,
        "source_kind": "SYNTHETIC_RESEARCH_ONLY",
        "input_factors_are_verified_official_statistics": False,
        "monetary_surprise_from_market_consensus_verified": False,
        "economic_surprises_from_pre_release_consensus_verified": False,
        "geopolitical_risk_model_implemented": False,
        "broker_m15_execution_prices_verified": False,
        "weights_empirically_calibrated": False,
        "macro_bias_predictive_accuracy_verified": False,
        "validated_prediction_count": 0, "validated_accuracy": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "publishable": False, "http_requests": 0, "new_cost_brl": 0,
    }


def _unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("DUPLICATE_JSON_FIELD")
        out[key] = value
    return out


def inspect_g8_synthetic_macro_hypothesis_lab(raw: Any) -> dict[str, Any]:
    """Calculate *only* synthetic comparative ranking with frozen weights.

    Returns zero operational market bias on ALL paths, including valid input.
    """
    out = _reject("INVALID_SYNTHETIC_INPUT")
    if not isinstance(raw, bytes) or not 100 <= len(raw) <= MAX_INPUT_BYTES:
        return out
    try:
        x = json.loads(raw.decode("utf-8", "strict"),
                       object_pairs_hook=_unique_fields,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
    except (ValueError, TypeError, UnicodeDecodeError, RecursionError):
        return out
    if not isinstance(x, dict) or set(x) != EXPECTED_FIELDS:
        return out
    if (x["schema"] != INPUT or x["data_kind"] != "SYNTHETIC_RESEARCH_ONLY"
            or x["horizon"] not in ("D1", "W1")
            or not isinstance(x["research_at_utc"], str)
            or UTC_PATTERN.fullmatch(x["research_at_utc"]) is None):
        return out
    try:
        at = datetime.strptime(x["research_at_utc"], "%Y-%m-%dT%H:%M:%SZ")
        if at.year < 2026 or not isinstance(x["currency_factors"], dict):
            return out
    except ValueError:
        return out
    factors = x["currency_factors"]
    if set(factors) != set(CURRENCIES) or len(CURRENCIES) != 8 or len(OFFICIAL_PAIRS) != 28:
        out["reason"] = "G8_UNIVERSE_MISSING_OR_UNKNOWN_CURRENCY"
        return out
    scores: dict[str, int] = {}
    weights = WEIGHTS[x["horizon"]]
    for currency in CURRENCIES:
        row = factors[currency]
        if not isinstance(row, dict) or set(row) != set(FACTORS):
            out["reason"] = "MACRO_FACTOR_MISSING_OR_UNKNOWN"
            return out
        if any(type(row[f]) is not int or row[f] not in ALLOWED_IMPULSES
               for f in FACTORS):
            out["reason"] = "MACRO_FACTOR_MUST_BE_INTEGER_MINUS2_TO_PLUS2"
            return out
        scores[currency] = sum(weights[f] * row[f] for f in FACTORS)
    currencies = sorted(
        [{"currency": c, "synthetic_points": scores[c]} for c in CURRENCIES],
        key=lambda item: (-item["synthetic_points"], item["currency"]),
    )
    pairs = []
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        differential = scores[base] - scores[quote]
        # These labels describe a synthetic comparison, never an instruction
        # or prediction of the actual pair movement.
        relation = ("BASE_RELATIVELY_FORTE" if differential > NEUTRAL_DIFF_POINTS
                    else "COTACAO_RELATIVAMENTE_FORTE" if differential < -NEUTRAL_DIFF_POINTS
                    else "INDEFINIDO_HIPOTESE")
        pairs.append({
            "pair": pair,
            "synthetic_relative_points": differential,
            "synthetic_relation": relation,
            "base": base, "quote": quote,
        })
    pairs.sort(key=lambda r: (-abs(r["synthetic_relative_points"]), r["pair"]))
    out.update({
        "state": "LAB_SYNTHETIC_MACRO_RANKING_ONLY_NOT_A_FORECAST",
        "reason": "UNVERIFIED_HYPOTHETICAL_INPUTS_AND_UNCALIBRATED_WEIGHTS",
        "input_sha256": sha256(raw).hexdigest(),
        "horizon": x["horizon"],
        "synthetic_currency_rank": currencies,
        "synthetic_pair_rank": pairs,
        "currency_count": len(currencies),
        "pair_count": len(pairs),
        "neutral_pair_count": sum(
            r["synthetic_relation"] == "INDEFINIDO_HIPOTESE" for r in pairs),
        "highest_abs_pair_score": (
            abs(pairs[0]["synthetic_relative_points"]) if pairs else None),
    })
    return out


__all__ = [
    "SCHEMA", "INPUT", "FACTORS", "WEIGHTS", "NEUTRAL_DIFF_POINTS",
    "inspect_g8_synthetic_macro_hypothesis_lab",
]
