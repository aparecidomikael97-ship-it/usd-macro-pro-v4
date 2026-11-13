"""FX28 Motor A D1/W1 PRE-WINDOW gate: real local source audits, NO forecasts.

Runs the exact 8-bank + post-release PPI read-only source bridge
BEFORE a frozen campaign NY17 session, never after its start.
For each next D1/W1 session:
  - >12 hours before opening: NOT_YET_IN_PREFLIGHT, no source reads
  - in final 12 hours: REPLAY candidate sources, explain 28 blockers
  - at/after opening: NEVER ISSUE OR BACKFILL THAT WINDOW

The 2026 October PPI may be background after 2026-11-13 release. It is
NOT a pre-event prediction of that release; it cannot provide a USD score
or be counted as 7 independent events. All policy/price/macroeconomic
provenance remains unverified even if every local SHA passes.

This is a *read-only* suitability gate; it NEVER creates a 28-forecast
roster, posts a GitHub witness, opens MT5, calls HTTP, sends notifications,
starts jobs or changes the 672 prospective opportunity denominator.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    CAMPAIGN_ID, CALENDAR_ISSUE, EXPECTED_PAIR_HORIZON_SLOTS,
    FROZEN_START_UTC, FROZEN_END_UTC, _nominal_windows,
)
from atlasquant_trader_fx28_ny17_forecast_witness_lab import (
    CAMPAIGN_PUBLICATION_CLAIM_UTC,
)
from atlasquant_trader_fx28_policy_ppi_unified_readiness_lab import (
    SCHEMA as UNIFIED_SCHEMA,
    inspect_fx28_policy_ppi_readiness_lab,
)

SCHEMA = "ATLASQUANT_FX28_PREWINDOW_PIT_SOURCE_GATE_LAB_V1"
PREFLIGHT_LOOKBACK = timedelta(hours=12)
_HORIZONS = ("D1", "W1")


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None):
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(timezone.utc)
    except (TypeError, OverflowError, ValueError):
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_PREWINDOW_SOURCE_GATE_BLOCKED_NO_GO",
        "reason": reason,
        "campaign_id": CAMPAIGN_ID,
        "calendar_issue_url": CALENDAR_ISSUE,
        "campaign_start_utc": FROZEN_START_UTC.isoformat(),
        "campaign_end_utc": FROZEN_END_UTC.isoformat(),
        "expected_nominal_opportunities": 672,
        "expected_d1_nominal_opportunities": 560,
        "expected_w1_nominal_opportunities": 112,
        "observed_at_utc_claim": None,
        "observed_clock_is_not_an_external_timestamp_witness": True,
        "max_source_preflight_hours_before_start": 12,
        "next_nominal_windows": [],
        "nominal_windows_in_active_preflight": 0,
        "potential_slots_now_audited": 0,
        "source_reader_was_called": False,
        "unified_source_audit_state": "NOT_CALLED",
        "policy_original_documents_locally_checked": 0,
        "policy_recent_local_capture_claims": 0,
        "ppi_oct2026_documentary_source_replayed": False,
        "ppi_post_event_context_not_pre_event_forecast": True,
        "ppi_shared_event_count_not_seven_independent_news": 1,
        "source_replay_not_issuer_identity_or_pit_proof": True,
        "issuer_first_seen_authenticated": False,
        "bilateral_cpi_pit_authenticated": False,
        "policy_expectations_pit_authenticated": False,
        "economic_impact_model_calibrated": False,
        "broker_m15_authenticated": False,
        "real_prior_forecast_rosters_authenticated": False,
        "pre_event_28_forecast_rosters_generated": False,
        "github_pre_event_hash_witness_posted": False,
        "out_of_sample_hit_rate": None,
        "calibrated_probability": None,
        "directional_bias": None,
        "ready_for_d1_forecast": False,
        "ready_for_w1_forecast": False,
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "operational_bias": "AGUARDAR",
        "worker_enabled": False,
        "scheduler_enabled": False,
        "http_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def _next_for_horizon(horizon: str, now: datetime) -> dict[str, Any]:
    future = [(start, end) for start, end in _nominal_windows(horizon)
              if start > now]
    if not future:
        return {
            "horizon": horizon,
            "status": "NO_FUTURE_FROZEN_WINDOWS_NO_BACKFILL",
            "next_start_utc": None,
            "next_end_utc": None,
            "preflight_opens_utc": None,
            "nominal_pair_slots": 0,
            "pairs": [],
            "forecast_issuance_authorized": False,
        }
    start, end = future[0]
    active = start - PREFLIGHT_LOOKBACK <= now < start
    return {
        "horizon": horizon,
        "status": ("ACTIVE_SOURCE_READONLY_PREFLIGHT_NO_GO"
                   if active else
                   "NOT_YET_IN_PREWINDOW_SOURCE_PREFLIGHT"),
        "next_start_utc": start.isoformat(),
        "next_end_utc": end.isoformat(),
        "preflight_opens_utc": (start-PREFLIGHT_LOOKBACK).isoformat(),
        "nominal_pair_slots": len(OFFICIAL_PAIRS) if active else 0,
        "pairs": [],
        "forecast_issuance_authorized": False,
    }


def _trusted_shape(report: Any) -> bool:
    """Reject fake GO, malformed 28-universe and surplus source claims.

    Actual source reader invoked in this module, not a caller-provided
    'PASS'. Even if structural report is valid: ALWAYS deny prediction.
    """
    if (type(report) is not dict
            or report.get("schema") != UNIFIED_SCHEMA
            or report.get("state") !=
                "LAB_FX28_POLICY_PPI_COMBINED_READONLY_NO_GO"
            or report.get("operational_bias") != "AGUARDAR"
            or report.get("trade_authorized") is not False
            or report.get("publishable") is not False
            or report.get("historical_macro_point_in_time_authenticated")
                is not False
            or report.get("broker_m15_authenticated") is not False
            or report.get("model_calibrated_for_fx28") is not False
            or report.get("pre_event_fx28_rosters_independently_witnessed")
                is not False
            or report.get("fx28_pairs_reported") != 28
            or report.get("ppi_direct_usd_leg_pairs") != 7
            or report.get("ppi_is_one_shared_catalyst_not_seven_independent_news")
                is not True):
        return False
    rows = report.get("per_pair")
    if type(rows) is not list or len(rows) != 28:
        return False
    for i, row in enumerate(rows):
        if (type(row) is not dict
                or row.get("pair") != OFFICIAL_PAIRS[i]
                or row.get("bias") != "AGUARDAR"
                or row.get("trade_authorized") is not False
                or row.get("ppi_fx_impact_calculated") is not False
                or row.get("ppi_validated_pre_event_consensus_available")
                    is not False
                or row.get("need_bilateral_cpi_point_in_time") is not True
                or row.get("need_expectations_point_in_time") is not True
                or row.get("need_broker_m15_authenticated") is not True
                or row.get("need_model_calibration") is not True
                or type(row.get("two_policy_originals_locally_checked"))
                    is not bool
                or type(row.get("two_policy_recent_local_receipt_claims"))
                    is not bool
                or row["two_policy_recent_local_receipt_claims"]
                    and not row["two_policy_originals_locally_checked"]):
            return False
    return True


def inspect_fx28_pre_window_source_gate_lab(
    *, local_appdata: Any, inspected_at_utc: Any,
    ppi_archive_basename: Any = None,
) -> dict[str, Any]:
    """Source readiness for upcoming D1/W1; does NOT issue a forecast."""
    out = _base("INVALID_CLOCK_OR_FROZEN_CAMPAIGN_CONTRACT")
    now = _utc(inspected_at_utc)
    d1, w1 = _nominal_windows("D1"), _nominal_windows("W1")
    if (now is None or now < CAMPAIGN_PUBLICATION_CLAIM_UTC
            or len(OFFICIAL_PAIRS) != 28
            or EXPECTED_PAIR_HORIZON_SLOTS != 672
            or len(d1) != 20 or len(w1) != 4
            or d1[0][0] != FROZEN_START_UTC
            or w1[0][0] != FROZEN_START_UTC
            or d1[-1][1] != FROZEN_END_UTC
            or w1[-1][1] != FROZEN_END_UTC
            or type(local_appdata) is not str
            or type(ppi_archive_basename) not in (str, type(None))
            or ppi_archive_basename == ""):
        return out
    out["observed_at_utc_claim"] = now.isoformat()
    windows = [_next_for_horizon(horizon, now) for horizon in _HORIZONS]
    active = [row for row in windows
              if row["status"] == "ACTIVE_SOURCE_READONLY_PREFLIGHT_NO_GO"]
    out["next_nominal_windows"] = windows
    out["nominal_windows_in_active_preflight"] = len(active)
    out["potential_slots_now_audited"] = len(active)*28
    if not active:
        out["state"] = "LAB_FX28_PREWINDOW_NOT_ACTIVE_NO_GO"
        out["reason"] = "NO_D1_OR_W1_WINDOW_IN_NEXT_12_HOURS"
        return out

    # Call the REAL integrated offline source reader, not a fictional score.
    # This may access LOCAL files but cannot write or fetch HTTP.
    try:
        report = inspect_fx28_policy_ppi_readiness_lab(
            local_appdata=local_appdata, decision_at_utc=now,
            ppi_archive_basename=ppi_archive_basename)
    except (OSError, RuntimeError, ValueError, TypeError, KeyError,
            OverflowError):
        out["reason"] = "SOURCE_READER_EXCEPTION_NOT_AN_ISSUED_FORECAST"
        out["source_reader_was_called"] = True
        return out
    out["source_reader_was_called"] = True
    out["unified_source_audit_state"] = (
        report.get("state") if type(report) is dict else "MALFORMED")
    if not _trusted_shape(report):
        out["reason"] = "SOURCE_READER_BLOCKED_OR_CLAIMS_NOT_COHERENT"
        return out

    out["policy_original_documents_locally_checked"] = report[
        "policy_source_documents_locally_checked"]
    out["policy_recent_local_capture_claims"] = report[
        "policy_source_recent_local_receipt_claims"]
    ppi_present = report["ppi_documentary_series_count"] == 3
    out["ppi_oct2026_documentary_source_replayed"] = ppi_present
    for row in active:
        row["source_audit_performed_at_claim_utc"] = now.isoformat()
        row["pairs"] = []
        for info in report["per_pair"]:
            blockers = [
                "ISSUER_FIRST_SEEN_NOT_INDEPENDENTLY_AUTHENTICATED",
                "BILATERAL_CPI_AND_MACRO_VINTAGE_MISSING",
                "MONETARY_EXPECTATIONS_AND_CALENDAR_PIT_MISSING",
                "BROKER_M15_PRICES_NOT_AUTHENTICATED",
                "FX28_DIRECTION_MODEL_NOT_CALIBRATED",
            ]
            if not info["two_policy_originals_locally_checked"]:
                blockers.append("ONE_OR_BOTH_POLICY_DOCUMENTS_NOT_VALIDATED")
            elif not info["two_policy_recent_local_receipt_claims"]:
                blockers.append("ONE_OR_BOTH_POLICY_RECEIPT_CLAIMS_STALE")
            # Optional post-release US PPI context is NOT a mandatory
            # universal forecast input or a signed strength factor.
            notes = []
            if info["ppi_direct_usd_issuer_leg"]:
                notes.append(
                    "USD_PPI_POST_RELEASE_DOCUMENTARY_ONLY_NO_CONSENSUS"
                    if ppi_present else "USD_PPI_LOCAL_DOCUMENT_NOT_REPLAYED")
            row["pairs"].append({
                "pair": info["pair"],
                "blocking_reasons": blockers,
                "supplemental_context_notes": notes,
                "policy_originals_checked_locally_only":
                    info["two_policy_originals_locally_checked"],
                "policy_recent_local_receipt_claims_only":
                    info["two_policy_recent_local_receipt_claims"],
                "ppi_as_signed_currency_factor": False,
                "forecast_issued": False,
                "forecast_sha_witness_posted": False,
                "forecast_authorized": False,
                "bias": "AGUARDAR",
                "calibrated_probability": None,
                "trade_authorized": False,
            })
        row["status"] = "BLOCKED_SOURCES_INSUFFICIENT_FOR_28_FORECASTS"
    out["state"] = "LAB_FX28_PREWINDOW_28_SOURCE_VETOES_NO_GO"
    out["reason"] = "DOCUMENTARY_READINESS_NEVER_VALIDATED_FORECAST_PROVENANCE"
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only FX28 pre-window D1/W1 macro source veto")
    parser.add_argument("--preflight", action="store_true",
                        help="Inspect next 12h frozen sessions, never trade")
    parser.add_argument("--ppi-archive", metavar="NAME", default=None,
                        help="Exact local BLS PPI archive basename")
    args = parser.parse_args(argv)
    out = (_base("EXPLICIT_READONLY_PREFLIGHT_REQUIRED")
           if not args.preflight else
           inspect_fx28_pre_window_source_gate_lab(
               local_appdata=os.environ.get("LOCALAPPDATA", ""),
               inspected_at_utc=_now(), ppi_archive_basename=args.ppi_archive))
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    # Always exit 2: even a complete source audit is not forecast permission.
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

__all__ = ("SCHEMA", "inspect_fx28_pre_window_source_gate_lab", "main")
