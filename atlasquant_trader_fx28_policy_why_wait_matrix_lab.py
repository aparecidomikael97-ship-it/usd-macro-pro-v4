"""FX28 per-pair WHY AGUARDAR: policy source gaps, never a bias.

Standalone PURE adapter over the eight-bank local archive audit. It only
explains what the caller's report *claims* was locally checked. It never
authenticates an issuer, vintage, CPI, policy expectations, macro timing,
Pepperstone prices or a statistically calibrated directional forecast.

Even all 8 policy source bodies locally checked means 28 *NO-GO* pairs.
No file, network, MT5, alerts, scheduling, trading, deployment or costs.
"""
from __future__ import annotations

from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_fx28_policy_local_archive_replay_lab import (
    SCHEMA as ARCHIVE_SCHEMA,
)

SCHEMA = "ATLASQUANT_TRADER_FX28_POLICY_WHY_WAIT_MATRIX_LAB_V1"
_ACCEPTED = frozenset({
    "LAB_FX28_POLICY_ARCHIVE_EIGHT_ORIGINALS_LOCAL_ONLY_NO_GO",
    "LAB_FX28_POLICY_ARCHIVE_PARTIAL_OR_REJECTED_NO_GO",
})
_ROW_KEYS = frozenset({
    "pair", "base_policy_original_locally_checked",
    "quote_policy_original_locally_checked",
    "both_policy_sources_locally_checked",
    "cpi_both_currencies_authenticated",
    "fx_direction_admissible",
})


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_WHY_WAIT_INPUT_BLOCKED",
        "reason": reason,
        "total_pairs": len(OFFICIAL_PAIRS),
        "pairs_with_two_policy_sources_locally_checked": 0,
        "pairs_with_missing_or_rejected_policy_source": 0,
        "pairs_admitted_for_direction": 0,
        "per_pair": [],
        "source_claim_independently_authenticated": False,
        "first_seen_macro_vintage_independently_authenticated": False,
        "policy_instruments_harmonized": False,
        "bilateral_cpi_yo_y_verified": False,
        "historical_accuracy_validated": False,
        "calibrated_probability": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "scheduler_enabled": False,
        "worker_enabled": False,
        "http_requests": 0,
        "files_written": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def explain_fx28_policy_wait_lab(*, archive_report: Any) -> dict[str, Any]:
    """Explain all 28 pairs without trusting caller-supplied admission claims.

    A well-formed report can have caller-forged issuer bytes and timestamps.
    Therefore *every* result remains research-only AGUARDAR.
    """
    out = _base("INVALID_POLICY_ARCHIVE_REPORT")
    if (type(archive_report) is not dict
            or archive_report.get("schema") != ARCHIVE_SCHEMA
            or archive_report.get("state") not in _ACCEPTED
            or archive_report.get("operational_bias") != "AGUARDAR"
            or archive_report.get("trade_authorized") is not False
            or archive_report.get("publishable") is not False
            or archive_report.get("directional_bias") is not None
            or archive_report.get("calibrated_probability") is not None
            or archive_report.get("source_current_issuer_identity_independently_verified") is not False
            or archive_report.get("historical_point_in_time_vintage_verified") is not False
            or archive_report.get("cpi_for_all_eight_currencies_authenticated") is not False
            or archive_report.get("differing_policy_instruments_harmonized") is not False):
        return out
    checked = archive_report.get("currencies_locally_checked")
    missing = archive_report.get("currencies_missing")
    rejected = archive_report.get("currencies_rejected")
    coverage = archive_report.get("pair_policy_source_coverage")
    codes = set(CURRENCIES)
    if (type(checked) is not list or type(missing) is not list
            or type(rejected) is not dict or type(coverage) is not list
            or len(coverage) != len(OFFICIAL_PAIRS)
            or any(type(c) is not str for c in checked + missing)
            or any(type(c) is not str or type(v) is not str
                   or not v or len(v) > 200 for c, v in rejected.items())
            or len(set(checked)) != len(checked)
            or len(set(missing)) != len(missing)
            or set(checked) | set(missing) | set(rejected) != codes
            or (set(checked) & set(missing))
            or (set(checked) & set(rejected))
            or (set(missing) & set(rejected))):
        return _base("CURRENCY_PARTITION_INCONSISTENT")
    ready = set(checked)
    if (type(archive_report.get("currencies_with_local_original_bytes_validated")) is not int
            or archive_report["currencies_with_local_original_bytes_validated"] != len(ready)):
        return _base("SOURCE_CURRENCY_COUNTER_INCONSISTENT")
    if (archive_report["state"] == "LAB_FX28_POLICY_ARCHIVE_EIGHT_ORIGINALS_LOCAL_ONLY_NO_GO") != (len(ready) == 8):
        return _base("SOURCE_STATE_EIGHT_BANK_CONTRADICTION")

    expected_by_pair: dict[str, dict[str, bool | str]] = {}
    two = 0
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        both = base in ready and quote in ready
        two += int(both)
        expected_by_pair[pair] = {
            "pair": pair,
            "base_policy_original_locally_checked": base in ready,
            "quote_policy_original_locally_checked": quote in ready,
            "both_policy_sources_locally_checked": both,
            "cpi_both_currencies_authenticated": False,
            "fx_direction_admissible": False,
        }
    if (type(archive_report.get("pairs_with_both_policy_originals_locally_checked")) is not int
            or archive_report["pairs_with_both_policy_originals_locally_checked"] != two
            or type(archive_report.get("pairs_lacking_at_least_one_policy_original")) is not int
            or archive_report["pairs_lacking_at_least_one_policy_original"] != len(OFFICIAL_PAIRS) - two
            or any(type(row) is not dict or set(row) != _ROW_KEYS
                   or any(type(row.get(flag)) is not bool for flag in (
                       "base_policy_original_locally_checked",
                       "quote_policy_original_locally_checked",
                       "both_policy_sources_locally_checked",
                       "cpi_both_currencies_authenticated",
                       "fx_direction_admissible",
                   ))
                   or row != expected_by_pair.get(row.get("pair"))
                   for row in coverage)
            or len({row["pair"] for row in coverage if type(row) is dict}) != len(OFFICIAL_PAIRS)):
        return _base("FX28_SOURCE_COVERAGE_CONTRADICTS_CURRENCY_PARTITION")

    rows = []
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        absent = [c for c in (base, quote) if c in missing]
        invalid = {c: rejected[c] for c in (base, quote) if c in rejected}
        both = base in ready and quote in ready
        if invalid:
            reason_code = "POLICY_ORIGINAL_REJECTED"
            why = "Fonte local de política rejeitada; falta reconciliação documental e macro bilateral."
        elif absent:
            reason_code = "POLICY_ORIGINAL_MISSING"
            why = "Fonte local de política ausente para uma ou ambas as moedas."
        else:
            reason_code = "POLICY_ORIGINALS_LOCAL_ONLY_NO_BILATERAL_PIT_CPI"
            why = ("Duas fontes de política conferidas somente em arquivo local; "
                   "faltam CPI bilateral, vintages, expectativas e autenticação independente.")
        rows.append({
            "pair": pair, "base_currency": base, "quote_currency": quote,
            "policy_originals_locally_checked": both,
            "missing_policy_currency_codes": absent,
            "rejected_policy_currencies": invalid,
            "why_wait_code": reason_code,
            "why_wait_explanation": why,
            "independently_witnessed_directional_bias": None,
            "fx_direction_admissible": False,
            "operational_bias": "AGUARDAR",
            "trade_authorized": False,
        })
    out.update({
        "state": "LAB_FX28_POLICY_WHY_WAIT_MATRIX_COMPLETE_NO_GO",
        "reason": "SOURCE_COVERAGE_DOCUMENTARY_ONLY_NO_AUTHENTICATED_BILATERAL_BIAS",
        "pairs_with_two_policy_sources_locally_checked": two,
        "pairs_with_missing_or_rejected_policy_source": len(OFFICIAL_PAIRS) - two,
        "per_pair": rows,
    })
    return out


__all__ = ("SCHEMA", "explain_fx28_policy_wait_lab")
