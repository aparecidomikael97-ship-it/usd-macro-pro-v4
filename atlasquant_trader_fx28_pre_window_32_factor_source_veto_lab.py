"""FX28 Motor A: CPI+PPI+G8 32-factor evidence check at frozen D1/W1 preflight.

This is a read-only pre-window BRIDGE to the existing *real local source*
32-factor validator, not an FX strategy. Outside the final 12 hours before a
frozen window it must NOT touch local archives. Inside that interval it checks
the 32 source types and labels every pair AGUARDAR, without any fabricated
pre-window forecast, price, probability, model score or source timestamp.

No network, broker, file writes, notifications, orders, worker, merge or deploy.
Even genuine first-print CPI/PPI numbers are POST-release documentary context,
not an independently timestamped consensus, calibrated USD strength, or
28 independent inflation surprises. The 672 opportunities remain unchanged.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    CAMPAIGN_ID, CALENDAR_ISSUE, EXPECTED_PAIR_HORIZON_SLOTS,
    FROZEN_START_UTC, FROZEN_END_UTC, _nominal_windows,
)
from atlasquant_trader_fx28_ny17_forecast_witness_lab import (
    CAMPAIGN_PUBLICATION_CLAIM_UTC,
)
from atlasquant_trader_fx28_pre_window_source_gate_lab import (
    PREFLIGHT_LOOKBACK, _next_for_horizon,
)
from atlasquant_trader_fx28_32_factor_source_admission_lab import (
    SCHEMA as FACTOR_SCHEMA,
    inspect_fx28_32_factor_source_admission_lab,
)

SCHEMA = "ATLASQUANT_FX28_PREWINDOW_32_FACTOR_SOURCE_VETO_LAB_V1"
CATEGORIES = (
    "policy_expectations", "inflation_impact", "activity_impact", "labor_impact",
)
FACTOR_STATE = "LAB_FX28_32_FACTOR_DOCUMENTARY_GAP_RECONCILED_NO_GO"


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError, TypeError):
        return None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_FX28_32_PREWINDOW_BLOCKED_NO_GO",
        "reason": reason, "campaign_id": CAMPAIGN_ID,
        "calendar_issue_url": CALENDAR_ISSUE,
        "campaign_start_utc": FROZEN_START_UTC.isoformat(),
        "campaign_end_utc": FROZEN_END_UTC.isoformat(),
        "expected_pair_horizon_opportunities": 672,
        "expected_d1_opportunities": 560, "expected_w1_opportunities": 112,
        "inspected_at_utc_claim": None,
        "inspected_clock_is_not_independent_public_witness": True,
        "preflight_lookback_hours": 12,
        "active_nominal_windows": 0, "potential_pair_horizon_slots": 0,
        "windows": [], "source_reader_was_called": False,
        "source_audit_state": "NOT_CALLED",
        "source_replayed_eight_banks_count": 0,
        "source_replayed_ppi_count": 0, "source_replayed_cpi_count": 0,
        "local_distinct_document_sha_claim_count": 0,
        "factor_slots_inspected": 0,
        "factor_slots_with_local_documentary_context": 0,
        "factor_slots_with_verified_signed_impact": 0,
        "factor_slots_with_verified_pre_event_consensus": 0,
        "ppi_and_cpi_are_two_us_documents_not_two_independent_fx_signals": True,
        "shared_us_data_cannot_be_counted_seven_times": True,
        "local_hash_does_not_authenticate_issuer_or_first_seen": True,
        "cpi_nsa_mom_is_not_cpi_sa_mom_or_yoy": True,
        "cpi_oct2026_yoy_unavailable": True,
        "ppi_oct2026_is_post_release_actual_not_pre_event_consensus": True,
        "first_seen_pit_authenticated": False,
        "broker_m15_authenticated": False,
        "directional_impact_calibrated": False,
        "forecasts_precommitted_to_github": False,
        "pre_event_forecast_issued": False,
        "forecast_direction": None, "calibrated_probability": None,
        "out_of_sample_accuracy": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "live_alert_allowed": False, "scheduler_enabled": False,
        "worker_enabled": False, "network_requests": 0,
        "file_writes": 0, "new_cost_brl": 0, "research_only": True,
    }


def _trusted_factor_audit(r: Any) -> bool:
    """Reject malformed, forged GO and a single positive probability/score."""
    if (type(r) is not dict or r.get("schema") != FACTOR_SCHEMA
            or r.get("state") != FACTOR_STATE
            or r.get("currency_count_expected") != 8
            or r.get("factor_slots_expected") != 32
            or r.get("factor_slots_inspected") != 32
            or r.get("pair_count_expected") != 28
            or r.get("operational_bias") != "AGUARDAR"
            or r.get("trade_authorized") is not False
            or r.get("publishable") is not False
            or r.get("real_directional_forecast_authorized") is not False
            or r.get("experimental_score_execution_authorized") is not False
            or r.get("fx28_forecast_witnessed_before_window") is not False
            or r.get("historical_macro_point_in_time_authenticated") is not False
            or r.get("broker_m15_price_history_authenticated") is not False
            or r.get("model_directional_effects_calibrated") is not False
            or r.get("calibrated_probability") is not None
            or r.get("validated_direction_accuracy") is not None
            or r.get("factor_slots_with_signed_impact_independently_admissible") != 0
            or r.get("factor_slots_with_pre_event_consensus_verified") != 0
            or r.get("factor_slots_with_calibrated_directional_effect") != 0
            or r.get("ppi_is_one_shared_us_event_not_seven_independent_inflation_events") is not True
            or r.get("policy_rates_are_not_forward_policy_expectations") is not True
            or r.get("network_requests") != 0 or r.get("file_writes") != 0
            or r.get("new_cost_brl") != 0):
        return False
    counts = (r.get("locally_replayed_policy_issuer_count"),
              r.get("locally_replayed_ppi_document_count"),
              r.get("locally_replayed_cpi_u_nsa_document_count"),
              r.get("distinct_original_document_sha_claim_count"),
              r.get("factor_slots_with_any_relevant_local_document"))
    if (any(type(x) is not int for x in counts)
            or not 0 <= counts[0] <= 8
            or not 0 <= counts[1] <= 1
            or not 0 <= counts[2] <= 1
            or not 0 <= counts[3] <= 10
            or not 0 <= counts[4] <= 9):
        return False
    if (counts[4] != counts[0] + int(counts[1] > 0 or counts[2] > 0)
            or counts[3] > sum(counts[:3])
            or (counts[2] == 1 and
                (r.get("cpi_reference_archive_reconciled_with_local_api_levels") is not True
                 or r.get("cpi_local_replay_original_but_archived_index_levels_disagree") is not False))):
        return False
    factors, pairs = r.get("factor_slots"), r.get("pairs")
    if type(factors) is not list or type(pairs) is not list:
        return False
    expected = {(c, cat) for c in CURRENCIES for cat in CATEGORIES}
    got: set[tuple[str, str]] = set()
    for row in factors:
        if (type(row) is not dict
                or (row.get("currency"), row.get("category")) not in expected
                or row.get("signed_impact_points_admitted") is not None
                or row.get("source_semantics_support_signed_factor") is not False
                or row.get("pre_event_consensus_independently_attested") is not False
                or type(row.get("missing_model_input_reason")) is not str
                or not row["missing_model_input_reason"]):
            return False
        key = (row["currency"], row["category"])
        if key in got:
            return False
        got.add(key)
    if got != expected or len(pairs) != 28:
        return False
    for i, row in enumerate(pairs):
        if (type(row) is not dict or row.get("pair") != OFFICIAL_PAIRS[i]
                or row.get("base_currency") != split_pair(row["pair"])[0]
                or row.get("quote_currency") != split_pair(row["pair"])[1]
                or row.get("forecast_direction") is not None
                or row.get("calibrated_probability") is not None
                or row.get("trade_authorized") is not False
                or row.get("operational_bias") != "AGUARDAR"
                or row.get("model_signed_factor_slots_admitted") != 0):
            return False
    return True


def inspect_fx28_32_factor_pre_window_lab(
    *, local_appdata: Any, inspected_at_utc: Any,
    ppi_archive_basename: Any = None, cpi_archive_basename: Any = None,
) -> dict[str, Any]:
    """Call the REAL local documentary factor gate only inside active 12h."""
    out = _base("INVALID_CAMPAIGN_CLOCK_OR_ARCHIVE_ARGS")
    now = _utc(inspected_at_utc)
    if (now is None or now < CAMPAIGN_PUBLICATION_CLAIM_UTC
            or len(OFFICIAL_PAIRS) != 28 or len(CURRENCIES) != 8
            or EXPECTED_PAIR_HORIZON_SLOTS != 672
            or len(_nominal_windows("D1")) != 20
            or len(_nominal_windows("W1")) != 4
            or _nominal_windows("D1")[0][0] != FROZEN_START_UTC
            or _nominal_windows("W1")[0][0] != FROZEN_START_UTC
            or _nominal_windows("D1")[-1][1] != FROZEN_END_UTC
            or _nominal_windows("W1")[-1][1] != FROZEN_END_UTC
            or PREFLIGHT_LOOKBACK.total_seconds() != 12 * 3600
            or type(local_appdata) is not str
            or type(ppi_archive_basename) not in (str, type(None))
            or type(cpi_archive_basename) not in (str, type(None))
            or ppi_archive_basename == "" or cpi_archive_basename == ""):
        return out
    out["inspected_at_utc_claim"] = now.isoformat()
    windows = [_next_for_horizon(h, now) for h in ("D1", "W1")]
    out["windows"] = windows
    active = [x for x in windows
              if x["status"] == "ACTIVE_SOURCE_READONLY_PREFLIGHT_NO_GO"]
    out["active_nominal_windows"] = len(active)
    out["potential_pair_horizon_slots"] = len(active) * 28
    if not active:
        out.update(state="LAB_FX28_32_PREWINDOW_INACTIVE_NO_GO",
                   reason="OUTSIDE_FROZEN_NEXT_12_HOURS_NO_ARCHIVE_READ")
        return out
    try:
        report = inspect_fx28_32_factor_source_admission_lab(
            local_appdata=local_appdata, decision_at_utc=now,
            ppi_archive_basename=ppi_archive_basename,
            cpi_archive_basename=cpi_archive_basename,
            hypothetical_factors=None,
        )
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, OverflowError):
        out["source_reader_was_called"] = True
        out["reason"] = "SOURCE_READER_EXCEPTION_NO_FORECAST"
        return out
    out["source_reader_was_called"] = True
    out["source_audit_state"] = (report.get("state")
                                  if type(report) is dict else "MALFORMED_REPORT")
    if not _trusted_factor_audit(report):
        out["reason"] = "SOURCE_AUDIT_MALFORMED_OR_UNSAFE_NO_FORECAST"
        return out
    out["source_replayed_eight_banks_count"] = report[
        "locally_replayed_policy_issuer_count"]
    out["source_replayed_ppi_count"] = report[
        "locally_replayed_ppi_document_count"]
    out["source_replayed_cpi_count"] = report[
        "locally_replayed_cpi_u_nsa_document_count"]
    out["local_distinct_document_sha_claim_count"] = report[
        "distinct_original_document_sha_claim_count"]
    out["factor_slots_inspected"] = report["factor_slots_inspected"]
    out["factor_slots_with_local_documentary_context"] = report[
        "factor_slots_with_any_relevant_local_document"]
    out["factor_slots_with_verified_signed_impact"] = report[
        "factor_slots_with_signed_impact_independently_admissible"]
    out["factor_slots_with_verified_pre_event_consensus"] = report[
        "factor_slots_with_pre_event_consensus_verified"]
    reason_by_currency = {
        c: [f["missing_model_input_reason"] for f in report["factor_slots"]
            if f["currency"] == c]
        for c in CURRENCIES
    }
    for window in active:
        window["status"] = "ACTIVE_32_FACTOR_SOURCE_AUDIT_NO_FORECAST"
        window["inspected_at_utc_claim"] = now.isoformat()
        window["pairs"] = []
        for p in report["pairs"]:
            base = p["base_currency"]
            quote = p["quote_currency"]
            window["pairs"].append({
                "pair": p["pair"], "base_currency": base,
                "quote_currency": quote,
                "base_factor_gaps": reason_by_currency[base],
                "quote_factor_gaps": reason_by_currency[quote],
                "usd_cpi_documentary_context_only": (
                    report["locally_replayed_cpi_u_nsa_document_count"] == 1
                    and "USD" in (base, quote)),
                "usd_ppi_documentary_context_only": (
                    report["locally_replayed_ppi_document_count"] == 1
                    and "USD" in (base, quote)),
                "cpi_and_ppi_are_not_two_independent_predictions": True,
                "forecast_issued": False, "forecast_direction": None,
                "calibrated_probability": None,
                "operational_bias": "AGUARDAR", "trade_authorized": False,
            })
    out.update(state="LAB_FX28_32_PREWINDOW_DOCUMENTARY_VETO_NO_GO",
               reason="32_DOCUMENTARY_FACTORS_NOT_SIGNED_PIT_IMPACTS_OR_FORECASTS")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only CPI+PPI+8 policy rate 32-factor D1/W1 veto")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--ppi-archive", default=None, metavar="BASENAME")
    parser.add_argument("--cpi-archive", default=None, metavar="BASENAME")
    args = parser.parse_args(argv)
    result = (_base("EXPLICIT_PREFLIGHT_REQUIRED")
              if not args.preflight else
              inspect_fx28_32_factor_pre_window_lab(
                  local_appdata=os.environ.get("LOCALAPPDATA", ""),
                  inspected_at_utc=datetime.now(timezone.utc).replace(microsecond=0),
                  ppi_archive_basename=args.ppi_archive,
                  cpi_archive_basename=args.cpi_archive))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 2  # A source read is never trading or forecast permission.


if __name__ == "__main__":
    raise SystemExit(main())

__all__ = ("SCHEMA", "inspect_fx28_32_factor_pre_window_lab", "main")
