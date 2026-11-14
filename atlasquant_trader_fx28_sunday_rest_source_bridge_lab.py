"""First NY17 FX28 Sunday control-room bridge: actual reports, NEVER forecast.

Combines the *output* of the explicit read-only GitHub REST inventory with
the real, separate FX28 documentary readiness panel, and independently
recounts all 672 frozen slots using the existing issuer ledger.

One successful REST GET is metadata-only and cannot prove a digest's
canonical roster bytes or a historical first-seen. Before Sunday 15 Nov
22:00 UTC the first 56 slots are FUTURE even when no precommitment exists.
After opening, absence in THIS observation is not proof that no one
issued a commitment earlier. There is no automatic posting or backfill.

A local panel may be absent because AM12 is offline. Such a case is
UNKNOWN, never 5/8 or 6/8 claimed current source coverage. Even an
upstream panel is a caller-supplied snapshot at this layer, not proof
of original issuer identity or that AM12 was actually contacted.

Pure Python, offline, no network, requests, files, billing, notifications,
model predictions, trade execution, or runtime modification.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import argparse
import json
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from atlasquant_trader_fx28_github_rest_comment_inventory_lab import (
    SCHEMA as REST_SCHEMA,
    collect_public_github_issue_snapshot_once_lab,
)
from atlasquant_trader_fx28_single_readiness_panel_lab import (
    SCHEMA as PANEL_SCHEMA,
)
from atlasquant_trader_fx28_ny17_672_slot_issuance_ledger_lab import (
    SCHEMA as LEDGER_SCHEMA, inspect_fx28_ny17_672_slot_issuance_ledger_lab,
)
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    FROZEN_START_UTC, EXPECTED_PAIR_HORIZON_SLOTS, _nominal_windows,
)

SCHEMA = "ATLASQUANT_FX28_SUNDAY_GITHUB_REST_LEDGER_SOURCE_BRIDGE_LAB_V1"
MAX_REST_SNAPSHOT_AGE = timedelta(minutes=10)
FIRST_PRECOMMIT_ALLOWED_UTC = FROZEN_START_UTC-timedelta(hours=12)
FIRST_D1, FIRST_W1 = _nominal_windows("D1")[0], _nominal_windows("W1")[0]
REST_READY = "LAB_GITHUB_REST_COMMENT_INVENTORY_COMPLETE_METADATA_ONLY_NO_GO"
PANEL_READY = "LAB_FX28_SINGLE_READINESS_PANEL_RECONCILED_NO_GO"
LEDGER_READY = "LAB_FX28_672_SLOTS_ACCOUNTED_UNATTESTED_NO_GO"


def _utc(value: Any) -> datetime | None:
    if type(value) is not datetime or value.tzinfo is None or value.microsecond:
        return None
    try:
        if value.utcoffset() is None:
            return None
        return value.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _stamp(value: Any) -> datetime | None:
    if type(value) is not str:
        return None
    try:
        d = datetime.fromisoformat(value)
        if d.isoformat() != value or d.utcoffset() is None or d.microsecond:
            return None
        return d.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_SUNDAY_FX28_CROSS_SOURCE_PREFLIGHT_BLOCKED_NO_GO",
        "reason": reason,
        "campaign_frozen_start_utc": FROZEN_START_UTC.isoformat(),
        "first_prewindow_open_utc": FIRST_PRECOMMIT_ALLOWED_UTC.isoformat(),
        "first_56_pair_horizon_slots": 56,
        "issue_rest_report_supplied": False,
        "rest_snapshot_age_seconds": None,
        "rest_comment_count_observed_claim": None,
        "rest_exact_headers_observed_claim": None,
        "rest_structural_eligible_count_observed_claim": None,
        "rest_first_window_candidate_count_claim": None,
        "rest_first_window_candidate_horizons_claim": [],
        "rest_candidate_roster_bytes_authenticated": False,
        "rest_server_timestamps_are_not_immutable_first_seen": True,
        "rest_snapshot_is_not_external_independent_precommit_proof": True,
        "local_panel_supplied": False,
        "local_am12_connection_and_originals_independently_verified": False,
        "local_policy_document_count_supplied_claim": None,
        "local_recent_24h_currency_count_supplied_claim": None,
        "local_recent_24h_pair_count_supplied_claim": None,
        "local_policy_missing_currencies_supplied_claim": [],
        "local_documentation_status": "UNKNOWN_NO_CURRENT_AM12_SOURCE_REPORT",
        "first_window_phase": None,
        "first_56_slots_due_now": None,
        "first_56_slots_not_yet_due": None,
        "ledger_slots_accounted": 0,
        "ledger_future_no_supplied_witness": None,
        "ledger_past_no_supplied_witness": None,
        "no_supplied_witness_never_proves_github_absence": True,
        "prewindow_absence_is_not_missing_forecast_yet": True,
        "all_56_first_window_forecasts_authenticated": False,
        "pre_event_risk_or_source_coverage_sufficient_for_direction": False,
        "macro_pit_independently_verified": False,
        "broker_price_point_in_time_verified": False,
        "validated_direction_accuracy": None,
        "calibrated_fx_probability": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "http_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_sunday_fx28_cross_source_preflight_lab(
    *, inspected_at_utc: Any, github_rest_inventory: Any,
    local_document_panel: Any = None,
) -> dict[str, Any]:
    """Join only EXISTING reports; no fake forecasts, no live source fetch."""
    out = _blocked("INVALID_ASOF_CLOCK_OR_FROZEN_CAMPAIGN")
    now = _utc(inspected_at_utc)
    if (now is None or now < FIRST_PRECOMMIT_ALLOWED_UTC-timedelta(days=2)
            or EXPECTED_PAIR_HORIZON_SLOTS != 672
            or len(_nominal_windows("D1")) != 20
            or len(_nominal_windows("W1")) != 4
            or FIRST_D1[0] != FIRST_W1[0]
            or FIRST_D1[0] != FROZEN_START_UTC
            or FIRST_PRECOMMIT_ALLOWED_UTC != datetime(
                2026,11,15,10,0,tzinfo=timezone.utc)):
        return out

    ledger = inspect_fx28_ny17_672_slot_issuance_ledger_lab(
        window_claims=(), inspected_at_utc=now)
    if (ledger.get("schema") != LEDGER_SCHEMA
            or ledger.get("state") != LEDGER_READY
            or ledger.get("slots_accounted") != 672
            or ledger.get("independently_authenticated_forecasts") != 0
            or ledger.get("absence_of_github_witness_independently_verified")
               is not False
            or ledger.get("github_comments_fetched") is not False
            or ledger.get("trade_authorized") is not False):
        out["reason"] = "FROZEN_672_LEDGER_FAILED_OR_INCONSISTENT"
        return out

    first_due = 56 if now >= FROZEN_START_UTC else 0
    first_future = 56-first_due
    out.update({
        "ledger_slots_accounted": 672,
        "ledger_future_no_supplied_witness": ledger["not_yet_due_slots"],
        "ledger_past_no_supplied_witness":
            ledger["not_issued_before_window_slots"],
        "first_56_slots_due_now": first_due,
        "first_56_slots_not_yet_due": first_future,
        "first_window_phase": (
            "NOT_ELIGIBLE_BEFORE_FIRST_12H"
            if now < FIRST_PRECOMMIT_ALLOWED_UTC else
            "PREWINDOW_OPEN_NOT_YET_DUE"
            if now < FROZEN_START_UTC else
            "OPENED_NO_RETROSPECTIVE_WITNESS")
    })
    try:
        nzdate = FROZEN_START_UTC.astimezone(ZoneInfo("America/Cuiaba"))
        nzpre = FIRST_PRECOMMIT_ALLOWED_UTC.astimezone(ZoneInfo("America/Cuiaba"))
        if ((nzdate.hour,nzdate.minute,nzdate.date().isoformat())
                != (18,0,"2026-11-15")
                or (nzpre.hour,nzpre.minute,nzpre.date().isoformat())
                != (6,0,"2026-11-15")):
            out["reason"] = "AMERICA_CUIABA_TIME_CROSSCHECK_FAILED"
            return out
    except (ZoneInfoNotFoundError, OverflowError, TypeError, ValueError):
        out["reason"] = "AMERICA_CUIABA_TIMEZONE_UNAVAILABLE"
        return out

    # A missing REST inventory is explicit UNKNOWN, never zero comments.
    if github_rest_inventory is None:
        out.update({
            "state": "LAB_SUNDAY_FX28_REST_NOT_OBSERVED_UNKNOWN_NO_GO",
            "reason": "MISSING_PUBLIC_GITHUB_INVENTORY_NO_ZERO_WITNESS_CLAIM",
        })
        return out
    inv = github_rest_inventory
    if (type(inv) is not dict or inv.get("schema") != REST_SCHEMA
            or inv.get("state") != REST_READY
            or inv.get("trade_authorized") is not False
            or inv.get("publishable") is not False
            or inv.get("independently_authenticated_forecasts") != 0
            or inv.get("canonical_28_pair_roster_bytes_reconciled") is not False
            or inv.get("publisher_and_first_seen_cryptographically_attested")
               is not False
            or type(inv.get("comments_reconciled")) is not int
            or type(inv.get("exact_witness_headers_found")) is not int
            or type(inv.get("structural_prewindow_metadata_candidates")) is not int
            or type(inv.get("candidate_witness_metadata")) is not list):
        out["reason"] = "GITHUB_REST_INVENTORY_NOT_A_VALID_BOUNDED_REPORT"
        return out
    seen = _stamp(inv.get("observed_at_utc_local_claim"))
    if (seen is None or not timedelta(0) <= now-seen <= MAX_REST_SNAPSHOT_AGE):
        out["reason"] = "GITHUB_REST_REPORT_OBSERVATION_CLOCK_MISSING_OR_STALE"
        return out
    candidates=inv["candidate_witness_metadata"]
    if (len(candidates) != inv["structural_prewindow_metadata_candidates"]
            or inv["comments_reconciled"] < inv["exact_witness_headers_found"]
            or inv["exact_witness_headers_found"] < len(candidates)
            or any(type(item) is not dict or
                   item.get("horizon") not in ("D1","W1")
                   for item in candidates)):
        out["reason"] = "GITHUB_REST_CANDIDATE_COUNTS_OR_SHAPE_INCONSISTENT"
        return out
    first=[]
    seen_ids=set()
    for item in candidates:
        horizon=item["horizon"]
        expected_start = FIRST_D1[0] if horizon=="D1" else FIRST_W1[0]
        expected_end = FIRST_D1[1] if horizon=="D1" else FIRST_W1[1]
        claimed_start = _stamp(item.get("start_utc"))
        claimed_end = _stamp(item.get("end_utc"))
        created = _stamp(item.get("created_at_utc_api_claim"))
        edited = _stamp(item.get("updated_at_utc_api_claim"))
        comment_id=item.get("comment_id")
        if (type(comment_id) is not int or comment_id <= 0
                or comment_id in seen_ids or claimed_start is None
                or claimed_end is None or created is None or edited is None
                or not claimed_start-timedelta(hours=12) <= created < claimed_start
                or created != edited or created > seen or seen >= claimed_start
                or item.get("not_independently_verified_forecast") is not True):
            out["reason"]="GITHUB_REST_CANDIDATE_CLOCK_EDIT_OR_ID_INCONSISTENT"
            return out
        seen_ids.add(comment_id)
        if claimed_start==expected_start and claimed_end==expected_end:
            first.append(horizon)
    if len(first) > 2 or len(first) != len(set(first)):
        out["reason"]="DUPLICATE_FIRST_WINDOW_HORIZON_CANDIDATE"
        return out
    out.update({
        "issue_rest_report_supplied": True,
        "rest_snapshot_age_seconds": int((now-seen).total_seconds()),
        "rest_comment_count_observed_claim": inv["comments_reconciled"],
        "rest_exact_headers_observed_claim": inv["exact_witness_headers_found"],
        "rest_structural_eligible_count_observed_claim":len(candidates),
        "rest_first_window_candidate_count_claim":len(first),
        "rest_first_window_candidate_horizons_claim":sorted(first),
    })

    # Reading AM12 documentation is optional here. Do not use the remembered
    # 5/8 as live evidence, or trust a supplied panel as external attestation.
    if local_document_panel is None:
        out["local_documentation_status"]="UNKNOWN_NO_CURRENT_AM12_SOURCE_REPORT"
    else:
        p=local_document_panel
        if (type(p) is not dict or p.get("schema") != PANEL_SCHEMA
                or p.get("state") != PANEL_READY
                or p.get("trade_authorized") is not False
                or p.get("publishable") is not False
                or p.get("witnesses_independently_authenticated") is not False
                or p.get("broker_m15_independently_authenticated") is not False
                or p.get("model_direction_calibrated") is not False
                or p.get("factors_with_calibrated_directional_effect") != 0
                or p.get("slots_expected") != 672
                or p.get("slots_accounted") != 672
                or p.get("slots_future_no_supplied_witness")
                   != ledger["not_yet_due_slots"]
                or p.get("slots_past_no_supplied_witness")
                   != ledger["not_issued_before_window_slots"]
                or type(p.get("issuer_policy_document_count")) is not int
                or not 0 <= p["issuer_policy_document_count"] <= 8
                or type(p.get("pairs_with_both_policy_documents")) is not int
                or (p["pairs_with_both_policy_documents"] !=
                    p["issuer_policy_document_count"]*
                    (p["issuer_policy_document_count"]-1)//2)
                or type(p.get("recent_24h_local_receipt_claim_count")) is not int
                or not 0 <= p["recent_24h_local_receipt_claim_count"] <= p["issuer_policy_document_count"]
                or p.get("recent_24h_bilateral_policy_pair_count") !=
                   p["recent_24h_local_receipt_claim_count"]*
                   (p["recent_24h_local_receipt_claim_count"]-1)//2
                or type(p.get("issuer_policy_missing_currencies")) is not list):
            out["reason"] = "LOCAL_PANEL_INCONSISTENT_WITH_FROZEN_LEDGER_OR_SOURCES"
            return out
        out.update({
            "local_panel_supplied": True,
            "local_documentation_status":
                "CALLER_SUPPLIED_LOCAL_PANEL_NOT_AM12_INDEPENDENT_ATTESTATION",
            "local_policy_document_count_supplied_claim":
                p["issuer_policy_document_count"],
            "local_recent_24h_currency_count_supplied_claim":
                p["recent_24h_local_receipt_claim_count"],
            "local_recent_24h_pair_count_supplied_claim":
                p["recent_24h_bilateral_policy_pair_count"],
            "local_policy_missing_currencies_supplied_claim":
                p["issuer_policy_missing_currencies"],
        })
    out.update({
        "state": "LAB_SUNDAY_FX28_REST_LEDGER_SOURCE_SEPARATED_NO_GO",
        "reason":
            "REST_COMMENT_METADATA_AND_LOCAL_SOURCE_DOCUMENTS_ARE_NOT_DIRECTIONAL_FORECASTS",
    })
    return out



def main(
    argv: list[str] | None = None, *,
    get_inventory: Any = collect_public_github_issue_snapshot_once_lab,
    observed_clock: Any = None,
) -> int:
    """Explicit one-shot REAL REST inventory -> 672-slot gate.

    The GitHub collector performs bounded GET only after the CLI flag. The
    bridge does not assume it can see AM12 local files from GitHub Actions.
    Prints a bounded diagnosis, not the issue comment body or private token.
    Both a failed REST request and a missing flag fail closed without
    classifying missing comments as an absence of forecasts.
    """
    parser = argparse.ArgumentParser(
        description="FX28 issue 1884 REST + 672 slot read-only preflight")
    parser.add_argument("--read-public-github", action="store_true")
    args = parser.parse_args(argv)
    if not args.read_public_github:
        print(json.dumps({
            "state": "LAB_SUNDAY_FX28_EXPLICIT_GITHUB_READ_REQUIRED_NO_GO",
            "operational_bias": "AGUARDAR", "trade_authorized": False,
            "github_comments_observed": False, "network_requests": 0,
        }, sort_keys=True))
        return 2
    if not callable(get_inventory):
        print("LAB_SUNDAY_FX28_INVALID_GITHUB_READER_NO_GO")
        return 2
    if observed_clock is None:
        observed_clock = lambda: datetime.now(timezone.utc).replace(
            microsecond=0)
    if not callable(observed_clock):
        print("LAB_SUNDAY_FX28_INVALID_UTC_CLOCK_NO_GO")
        return 2
    try:
        inventory = get_inventory(inspect_public_github=True)
        now = observed_clock()
        report = inspect_sunday_fx28_cross_source_preflight_lab(
            inspected_at_utc=now, github_rest_inventory=inventory,
            local_document_panel=None)
        # This CLI is different from the pure function above: its GitHub
        # reader HAS attempted HTTP. The pure gate's 'http_requests=0'
        # means only that the gate itself never fetched anything. Reuse
        # the collector's bounded count rather than outputting an
        # apparently contradictory zero after a real REST request.
        reported_gets = (
            inventory.get("http_requests_started")
            if type(inventory) is dict else None)
        if (type(reported_gets) is not int or
                not 1 <= reported_gets <= 5):
            report.update({
                "state": "LAB_SUNDAY_FX28_GITHUB_HTTP_COUNT_INVALID_NO_GO",
                "reason": "REST_READER_REQUEST_COUNT_MISSING_ZERO_OR_UNBOUNDED",
                "http_requests": None,
            })
        else:
            report["http_requests"] = reported_gets
        report["http_requests_provenance"] = (
            "GITHUB_REST_COLLECTOR_ATTEMPTED_GETS_NOT_NETWORK_INDEPENDENT_ATTESTATION"
        )
        report["github_rest_gets_attempted_claim"] = reported_gets
        report["am12_directly_contacted"] = False
        report["raw_issue_comment_bodies_disclosed"] = False
        print(json.dumps(report, sort_keys=True, ensure_ascii=False))
        return 0 if report["state"] == (
            "LAB_SUNDAY_FX28_REST_LEDGER_SOURCE_SEPARATED_NO_GO"
        ) else 2
    except (OSError, ValueError, TypeError, RuntimeError,
            OverflowError, RecursionError):
        print(json.dumps({
            "state": "LAB_SUNDAY_FX28_PUBLIC_REST_READ_EXCEPTION_NO_GO",
            "operational_bias": "AGUARDAR", "trade_authorized": False,
            "rest_witnesses_independently_attested": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "SCHEMA","FIRST_PRECOMMIT_ALLOWED_UTC","FIRST_D1","FIRST_W1",
    "inspect_sunday_fx28_cross_source_preflight_lab", "main",
)
