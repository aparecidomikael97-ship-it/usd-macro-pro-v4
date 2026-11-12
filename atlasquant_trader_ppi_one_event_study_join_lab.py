"""Fail-closed October 2026 US PPI surprise + seven-FX reaction study.

Read and revalidate the exact pre-event HTML snapshots, claimed post-release
BLS document and all seven M15 price files. Never accept a caller's fabricated
"passed" report. One PPI release remains ONE economic event, not seven
independent predictions or broker-executable trades.

This offline LAB module never performs network, MT5, order or scheduler IO.
The bytes, clock and HTTP metadata still need independent publisher/broker
attestation before being treated as point-in-time market evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import (
    LAST_REQUIRED_CLOSE_UTC, TD_PRE_EVENT_HTML_SHA256,
    TE_PRE_EVENT_HTML_SHA256, USD_FX, ClaimedLocalPriceArchive,
    inspect_ppi_fx_m15_forward_reaction_lab,
)
from atlasquant_trader_ppi_mt5_m15_capture_lab import load_local_receipt_lab
from atlasquant_trader_ppi_pre_event_protocol_lab import (
    AFTER as FROZEN_PROTOCOL_OK, inspect_ppi_frozen_research_protocol_lab,
)
from atlasquant_trader_ppi_m15_spread_context_lab import (
    PASS as SPREAD_OK, inspect_ppi_m15_spread_context_lab,
)
from atlasquant_trader_ppi_fx_breadth_lab import (
    DOCUMENTARY as BREADTH_OK, summarize_ppi_7fx_breadth_lab,
)
from atlasquant_trader_ppi_competing_calendar_lab import (
    PreEventCalendarClaim, audit_ppi_competing_calendar_lab,
)
from atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import (
    RELEASE_UTC, ClaimedPostReleaseHTTP,
    compare_ppi_actual_to_frozen_consensus_lab,
    inspect_ppi_oct2026_first_print_lab,
)
from atlasquant_trader_us_ppi_pre_event_preview_lab import (
    LocalCaptureClaim, inspect_ppi_pre_event_snapshot_lab,
)
from atlasquant_trader_us_ppi_te_second_consensus_lab import (
    Capture, inspect_te_ppi_snapshot_lab,
)

SCHEMA = "ATLASQUANT_TRADER_PPI_ONE_EVENT_SEVEN_FX_STUDY_JOIN_LAB_V1"
ROOT_EVENT = "US_PPI_OCT2026"
TD_OK = "LAB_PRE_EVENT_PPI_CONSENSUS_ARCHIVED_LOCAL_NO_TRADE"
TE_OK = "LAB_TE_PRE_EVENT_CONSENSUS_AND_OWN_FORECAST_DISTINGUISHED"
ACTUAL_OK = "LAB_PPI_OCT2026_BLS_TABLE1_BODY_VALUES_UNATTESTED"
SURPRISE_OK = "LAB_PPI_RESEARCH_SURPRISE_ONLY_UNATTESTED"
PRICE_OK = "LAB_PPI_FX_7PAIR_FORWARD_REACTION_DOCUMENTARY_NO_GO"


@dataclass(frozen=True)
class PpiStudyPacket:
    td_html: bytes
    td_capture: LocalCaptureClaim
    te_html: bytes
    te_capture: Capture
    bls_html: bytes
    bls_capture: ClaimedPostReleaseHTTP
    price_archive_root: Path | str
    price_archive_receipt: ClaimedLocalPriceArchive
    # Missing means unknown calendar, NOT "no other events".
    pre_event_calendar: PreEventCalendarClaim | None = None


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None):
        return None
    return value.astimezone(timezone.utc)


def _blocked(reason: str, state: str = "LAB_PPI_STUDY_BLOCKED") -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": state, "reason": reason,
        "event_root_id": ROOT_EVENT,
        "event_release_utc": RELEASE_UTC.isoformat(),
        "required_last_price_close_utc": LAST_REQUIRED_CLOSE_UTC.isoformat(),
        "planned_fx_symbols": list(USD_FX),
        "source_stage_states": {}, "one_event_study": None,
        "economic_events_authenticated": 0,
        "independent_directional_trials_verified": 0,
        "original_consensus_source_custody_independently_verified": False,
        "original_bls_release_time_independently_verified": False,
        "broker_history_and_bid_ask_independently_verified": False,
        "causal_effect_estimated": False,
        "directional_forecast": None,
        "validated_accuracy": None, "calibrated_probability": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
    }


def inspect_ppi_one_event_study_lab(
    *, packet: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Only report the *documentary* event study after ALL fixed inputs pass.

    A complete synthetic fixture is only a test of the plumbing. Genuine
    PPI and FX evidence require the historical AM12 files after the event.
    """
    now = _utc(as_of_utc)
    if now is None:
        return _blocked("INVALID_AS_OF_CLOCK")
    if now < RELEASE_UTC:
        return _blocked("PPI_NOT_RELEASED", "LAB_WAIT_PPI_OFFICIAL_RELEASE")
    if now < LAST_REQUIRED_CLOSE_UTC:
        return _blocked("FOUR_HOUR_FX_WINDOW_NOT_CLOSED", "LAB_WAIT_FX_FOUR_HOUR_WINDOW")
    if not isinstance(packet, PpiStudyPacket):
        return _blocked("COMPLETE_EIGHT_COMPONENT_PACKET_REQUIRED")

    # Pre-event protocol was committed with ABSTAIN, not a directional model.
    # A post-news seven-pair reaction must never count as seven forecasts.
    protocol = inspect_ppi_frozen_research_protocol_lab(as_of_utc=now)
    stages = {"PPI_PRE_EVENT_ABSTENTION_PROTOCOL": protocol.get("state")}
    if (protocol.get("state") != FROZEN_PROTOCOL_OK
            or protocol.get("pre_event_declared_abstention") is not True
            or protocol.get("pre_event_directional_forecasts_registered") != 0
            or protocol.get("event_count") != 1):
        out = _blocked("PRE_EVENT_RESEARCH_ABSTENTION_PROTOCOL_NOT_INTACT")
        out["source_stage_states"] = stages
        return out

    # The calendar is optional only for descriptive price measurements.
    # Missing ≠ no competing releases. Malformed purported provenance blocks
    # the study rather than being silently converted into "clean" windows.
    competing = audit_ppi_competing_calendar_lab(
        calendar=packet.pre_event_calendar, as_of_utc=now)
    stages["PRE_EVENT_CONCURRENT_MACRO_CALENDAR"] = competing.get("state")
    if competing.get("state") == "LAB_PPI_COMPETING_CALENDAR_BLOCKED":
        out = _blocked("COMPETING_EVENT_CALENDAR_INVALID_NO_CAUSAL_INTERPRETATION")
        out["source_stage_states"] = stages
        return out

    td = inspect_ppi_pre_event_snapshot_lab(
        raw_html=packet.td_html, receipt=packet.td_capture, as_of_utc=now)
    te = inspect_te_ppi_snapshot_lab(
        raw_html=packet.te_html, capture=packet.te_capture, as_of_utc=now)
    stages.update({"TD_PRE_EVENT": td.get("state"),
                   "TE_PRE_EVENT": te.get("state")})
    if (td.get("state") != TD_OK or te.get("state") != TE_OK
            or td.get("source_body_sha256") != TD_PRE_EVENT_HTML_SHA256
            or te.get("source_sha256") != TE_PRE_EVENT_HTML_SHA256):
        out = _blocked("PRE_EVENT_ORIGINAL_BYTES_NOT_MATCHING_FROZEN_SNAPSHOTS")
        out["source_stage_states"] = stages
        return out

    actual = inspect_ppi_oct2026_first_print_lab(
        raw_html=packet.bls_html, receipt=packet.bls_capture, as_of_utc=now)
    stages["BLS_FIRST_PRINT"] = actual.get("state")
    if actual.get("state") != ACTUAL_OK:
        out = _blocked("BLS_FIRST_PRINT_UNAVAILABLE_OR_INVALID")
        out["source_stage_states"] = stages
        return out

    surprise = compare_ppi_actual_to_frozen_consensus_lab(
        actual=actual, td_snapshot=td, te_snapshot=te)
    stages["SURPRISE_SAME_METRIC"] = surprise.get("state")
    if surprise.get("state") != SURPRISE_OK:
        out = _blocked("MATCHED_METRIC_CONSENSUS_COMPARISON_INVALID")
        out["source_stage_states"] = stages
        return out

    # Bind the post-release OHLC receipt to the original MT5 capture manifest.
    # Valid hashes supplied without that manifest bypass symbol/point checks.
    try:
        local_receipt = load_local_receipt_lab(Path(packet.price_archive_root))
    except (OSError, ValueError, TypeError):
        out = _blocked("MT5_CAPTURE_MANIFEST_MISSING_UNSAFE_OR_INVALID")
        out["source_stage_states"] = stages
        return out
    if (not isinstance(packet.price_archive_receipt, ClaimedLocalPriceArchive)
            or packet.price_archive_receipt != local_receipt):
        out = _blocked("MT5_MANIFEST_AND_PRICE_RECEIPT_DISAGREE")
        out["source_stage_states"] = stages
        return out
    stages["MT5_CAPTURE_MANIFEST"] = "LAB_MANIFEST_RECEIPT_MATCH_DOCUMENTARY_UNATTESTED"

    price = inspect_ppi_fx_m15_forward_reaction_lab(
        archive_root=packet.price_archive_root,
        receipt=packet.price_archive_receipt, as_of_utc=now)
    stages["SEVEN_FX_M15_WINDOWS"] = price.get("state")
    if (price.get("state") != PRICE_OK
            or set((price.get("price_reactions_usd_normalized_bps") or {})) != set(USD_FX)
            or price.get("independent_economic_event_sample_count") != 1):
        out = _blocked("FULL_SEVEN_PAIR_FX_ARCHIVE_MISSING_OR_FAILED")
        out["source_stage_states"] = stages
        return out

    spread = inspect_ppi_m15_spread_context_lab(
        archive_root=packet.price_archive_root,
        receipt=packet.price_archive_receipt, as_of_utc=now)
    stages["SPREAD_POINTS_CONTEXT"] = spread.get("state")
    if spread.get("state") != SPREAD_OK or spread.get("pair_count_documentary") != len(USD_FX):
        out = _blocked("FULL_SEVEN_PAIR_SPREAD_CONTEXT_REVALIDATION_FAILED")
        out["source_stage_states"] = stages
        return out

    # Read the already checked, USD-normalized price reaction from the full
    # source/manifest-validated stage. This is descriptive breadth, NEVER
    # seven independent votes, a currency forecast, or a causal estimate.
    breadth = summarize_ppi_7fx_breadth_lab(price_reaction_report=price)
    stages["SEVEN_FX_USD_NORMALIZED_BREADTH"] = breadth.get("state")
    if (breadth.get("state") != BREADTH_OK
            or breadth.get("fx_pair_count_documentary") != len(USD_FX)
            or set((breadth.get("cross_pair_breadth_by_horizon") or {}))
               != {"M15", "H1", "H4"}
            or breadth.get("economic_event_count_documentary") != 1):
        out = _blocked("FULL_SEVEN_PAIR_DESCRIPTIVE_BREADTH_INVALID")
        out["source_stage_states"] = stages
        return out

    out = _blocked("ONE_UNATTESTED_EVENT_NOT_A_PREDICTIVE_SAMPLE",
                   "LAB_PPI_ONE_EVENT_SEVEN_FX_DOCUMENTARY_NO_GO")
    out["source_stage_states"] = stages
    out["one_event_study"] = {
        "root_event_id": ROOT_EVENT,
        "economic_event_count_documentary": 1,
        "pre_event_research_protocol_sha256": protocol["frozen_protocol_sha256"],
        "pre_event_research_direction_registered": "ABSTAIN",
        "pre_event_directional_forecasts_registered": 0,
        "post_event_price_reactions_count_as_predictive_hits": False,
        "post_event_descriptive_study_not_predictive_accuracy": True,
        "forex_crosses_observed": len(USD_FX),
        "pre_event_td_sha256": td["source_body_sha256"],
        "pre_event_te_sha256": te["source_sha256"],
        "post_release_bls_sha256_claim": actual["source_sha256"],
        "headline_ppi_surprise_percentage_points": surprise["headline_vs_td_pre_event_diff_pp"],
        "core_ex_food_energy_surprise_percentage_points": surprise["core_vs_td_pre_event_diff_pp"],
        "fx_usd_normalized_m15_h1_h4_bps": price["price_reactions_usd_normalized_bps"],
        "usd_normalized_breadth_descriptive_not_forecast":
            breadth["cross_pair_breadth_by_horizon"],
        "m15_to_h4_opposing_spot_sign_pairs_documentary":
            breadth["cross_horizon_m15_to_h4_sign_reversals"],
        "seven_spot_observations_not_seven_independent_trials": True,
        "competing_macro_calendar_context_documentary": {
            "state": competing["state"],
            "candidate_other_root_count": competing["candidate_competing_root_count_documentary"],
            "candidate_other_roots_in_baseline": competing["candidate_baseline_contamination_roots_documentary"],
            "candidate_other_roots_by_window": competing["candidate_competing_roots_by_reaction_window"],
            "source_and_event_times_independently_verified": False,
            "ppi_causal_isolation_verified": False,
            "no_competing_events_proven": False,
            "requires_human_calendar_review": True,
        },
        "descriptive_reaction_cannot_be_exclusively_attributed_to_ppi": True,
        "m15_bar_spread_samples_not_intrabar_peak_or_transaction_cost": spread["per_pair_m15_spread_samples_points"],
        "zero_spread_context_requires_broker_review": spread["any_pair_all_17_spread_samples_zero"],
        "broker_execution_costs_not_verified": True,
        "m15_bar_spread_aggregation_not_independently_verified": True,
        "intrabar_max_spread_not_measured": True,
        "broker_price_capture_time_claim_utc": price["archive_captured_at_utc_claim"],
        "price_comparison_is_not_executable_return": True,
        "local_mt5_capture_manifest_matched_unattested": True,
        "mt5_server_or_broker_independently_authenticated": False,
    }
    return out


__all__ = ("SCHEMA", "ROOT_EVENT", "PpiStudyPacket", "inspect_ppi_one_event_study_lab")
