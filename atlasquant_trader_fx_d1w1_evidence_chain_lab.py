"""LAB-only FX D1/W1 evidence chain: fail-closed integration, never trading.

This module links an alleged pre-move forecast to the exact macro receipt bytes
that it used, checks that both currencies' macro observations were supposedly
captured before the forecast data cutoff, and optionally inspects an MT5 M15
CSV without treating broker-server times as UTC. All clock fields, source
origins, hashes and vintages are caller-provided, never external attestation.
Even a fully consistent structure is NOT proven historical forecast accuracy.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from atlasquant_trader_fx_premove_lab import audit_fx_premove_lab
from atlasquant_trader_g8_macro_asof_lab import inspect_g8_pair_macro_asof_lab
from atlasquant_trader_mt5_m15_bars_csv_lab import inspect_mt5_m15_bars_csv_lab

SCHEMA = "ATLASQUANT_TRADER_FX_D1W1_EVIDENCE_CHAIN_LAB_V1"
FORECAST_OK = "LAB_FORECAST_STRUCTURALLY_ACCEPTED_UNATTESTED"
MACRO_OK = "LAB_PAIR_MACRO_METADATA_COMPLETE_UNATTESTED"
MACRO_PARTIAL = "LAB_PAIR_MACRO_METADATA_INCOMPLETE_UNATTESTED"
M15_OK = "LAB_MT5_M15_CSV_STRUCTURE_VALID_SERVER_CLOCK_UNATTESTED"


def _empty() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_BLOCKED",
        "reason": "INVALID_FORECAST_OR_RESEARCH_CLOCK",
        "pair": None, "horizon": None,
        "forecast_receipt_structurally_valid": False,
        "macro_receipts_structurally_valid": False,
        "two_sided_pilot_indicators_present": False,
        "forecast_macro_pair_match": False,
        "macro_decision_time_equals_forecast_creation": False,
        "forecast_evidence_hash_binds_macro_bytes": False,
        "all_macro_captures_at_or_before_forecast_data_cutoff": False,
        "m15_csv_present": False,
        "m15_csv_structure_valid": False,
        "m15_rows": 0, "m15_server_local_start": None,
        "m15_server_local_end": None, "m15_server_local_gaps": None,
        "macro_missing_or_stale": [],
        "blocking_reasons": [],
        "forecast_sha256": None, "macro_sha256": None, "m15_sha256": None,
        "macroeconomic_source_independently_authenticated": False,
        "source_publication_times_independently_attested": False,
        "point_in_time_vintage_independently_verified": False,
        "forecast_external_precommit_independently_verified": False,
        "algorithm_frozen_before_forecast_verified": False,
        "broker_m15_timezone_independently_verified": False,
        "broker_bid_ask_executable_prices_verified": False,
        "historical_accuracy_verified": False,
        "validated_prediction_count": 0, "validated_accuracy": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False, "trade_authorized": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "external_http_requests": 0,
        "new_cost_brl": 0,
    }


def inspect_fx_d1w1_evidence_chain_lab(
    *, forecast_raw: Any, macro_raw: Any, as_of_utc: Any,
    mt5_m15_csv_raw: Any = None,
) -> dict[str, Any]:
    """Integrate independent existing validators, never promote self-attestation.

    Does not accept separately fabricated "passed" report dictionaries.
    The caller supplies the ORIGINAL research inputs, which are parsed again.
    """
    out = _empty()
    f = audit_fx_premove_lab(forecast_raw, as_of_utc=as_of_utc)
    if f["state"] != FORECAST_OK:
        out["blocking_reasons"] = ["FORECAST_RECEIPT_OR_FX_NY_WINDOW_INVALID"]
        return out
    out["forecast_receipt_structurally_valid"] = True
    out["forecast_sha256"] = f["forecast_sha256"]
    out["pair"], out["horizon"] = f["pair"], f["horizon"]
    # The strict forecast validator has already rejected duplicates, invalid
    # UTF-8, wrong field sets, invalid UTC and invalid times.
    forecast = json.loads(forecast_raw)
    m = inspect_g8_pair_macro_asof_lab(macro_raw, as_of_utc=as_of_utc)
    reasons: list[str] = []
    if m["state"] not in (MACRO_OK, MACRO_PARTIAL):
        reasons.append("MACRO_RECEIPTS_INVALID_OR_FUTURE_DATED")
    else:
        out["macro_receipts_structurally_valid"] = True
        out["macro_sha256"] = m["input_sha256"]
        out["macro_missing_or_stale"] = list(m["missing_or_stale"])
        out["two_sided_pilot_indicators_present"] = m["state"] == MACRO_OK
        out["forecast_macro_pair_match"] = m["pair"] == f["pair"]
        out["macro_decision_time_equals_forecast_creation"] = (
            m["decision_at_utc"] == forecast["created_at_utc"].replace("Z", "+00:00"))
        out["forecast_evidence_hash_binds_macro_bytes"] = (
            forecast["evidence_sha256"] == m["input_sha256"])
        # All recorded economic receipts, including old/non-selected periods,
        # must have been captured before the model's frozen data cutoff.
        # The macro validator has already established canonical UTC Z clocks.
        records = json.loads(macro_raw)["records"]
        out["all_macro_captures_at_or_before_forecast_data_cutoff"] = all(
            row["captured_at_utc"] <= forecast["data_cutoff_utc"]
            for row in records)
        if not out["two_sided_pilot_indicators_present"]:
            reasons.append("MACRO_FOR_EITHER_CURRENCY_MISSING_OR_STALE")
        if not out["forecast_macro_pair_match"]:
            reasons.append("FORECAST_MACRO_PAIR_MISMATCH")
        if not out["macro_decision_time_equals_forecast_creation"]:
            reasons.append("MACRO_DECISION_CLOCK_NOT_FORECAST_CREATION")
        if not out["forecast_evidence_hash_binds_macro_bytes"]:
            reasons.append("FORECAST_EVIDENCE_SHA_NOT_MACRO_BYTES")
        if not out["all_macro_captures_at_or_before_forecast_data_cutoff"]:
            reasons.append("MACRO_CAPTURE_AFTER_FORECAST_DATA_CUTOFF")
    out["m15_csv_present"] = mt5_m15_csv_raw is not None
    if mt5_m15_csv_raw is None:
        reasons.append("M15_HISTORY_NOT_SUPPLIED")
    else:
        mt5 = inspect_mt5_m15_bars_csv_lab(
            mt5_m15_csv_raw, declared_symbol=f["pair"].replace("/", ""))
        if mt5["state"] != M15_OK:
            reasons.append("M15_CSV_STRUCTURE_INVALID")
        else:
            out["m15_csv_structure_valid"] = True
            out["m15_sha256"] = mt5["source_sha256"]
            out["m15_rows"] = mt5["row_count"]
            out["m15_server_local_start"] = mt5["earliest_server_local_bar"]
            out["m15_server_local_end"] = mt5["latest_server_local_bar"]
            out["m15_server_local_gaps"] = mt5["non_15_minute_gaps_inside_broker_dates"]
    # Unlike a "readiness score", keep the unresolved *independent* proof as
    # hard blockers even if every provided file passes structural validation.
    reasons.extend((
        "MACRO_SOURCE_RELEASE_AND_VINTAGE_NOT_INDEPENDENTLY_ATTESTED",
        "FORECAST_NOT_EXTERNALLY_PRECOMMITTED_BEFORE_MOVE",
        "M15_TIMEZONE_BID_ASK_AND_EXECUTION_UNVERIFIED",
        "OUT_OF_SAMPLE_PREDICTIVE_ACCURACY_NOT_MEASURED",
    ))
    out.update({
        "state": ("LAB_STRUCTURAL_INPUTS_CONSISTENT_BUT_PROOF_MISSING"
                  if len(reasons) == 4
                  else "LAB_INCOMPLETE_OR_CONTRADICTORY_RESEARCH_EVIDENCE"),
        "reason": "HARD_NO_GO_EXTERNAL_PROVENANCE_AND_BACKTEST_NOT_VERIFIED",
        "blocking_reasons": reasons,
    })
    return out


__all__ = ["SCHEMA", "inspect_fx_d1w1_evidence_chain_lab"]
