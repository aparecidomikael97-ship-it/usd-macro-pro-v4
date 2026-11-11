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

    td = inspect_ppi_pre_event_snapshot_lab(
        raw_html=packet.td_html, receipt=packet.td_capture, as_of_utc=now)
    te = inspect_te_ppi_snapshot_lab(
        raw_html=packet.te_html, capture=packet.te_capture, as_of_utc=now)
    stages = {"TD_PRE_EVENT": td.get("state"), "TE_PRE_EVENT": te.get("state")}
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

    out = _blocked("ONE_UNATTESTED_EVENT_NOT_A_PREDICTIVE_SAMPLE",
                   "LAB_PPI_ONE_EVENT_SEVEN_FX_DOCUMENTARY_NO_GO")
    out["source_stage_states"] = stages
    out["one_event_study"] = {
        "root_event_id": ROOT_EVENT,
        "economic_event_count_documentary": 1,
        "forex_crosses_observed": len(USD_FX),
        "pre_event_td_sha256": td["source_body_sha256"],
        "pre_event_te_sha256": te["source_sha256"],
        "post_release_bls_sha256_claim": actual["source_sha256"],
        "headline_ppi_surprise_percentage_points": surprise["headline_vs_td_pre_event_diff_pp"],
        "core_ex_food_energy_surprise_percentage_points": surprise["core_vs_td_pre_event_diff_pp"],
        "fx_usd_normalized_m15_h1_h4_bps": price["price_reactions_usd_normalized_bps"],
        "broker_price_capture_time_claim_utc": price["archive_captured_at_utc_claim"],
        "price_comparison_is_not_executable_return": True,
    }
    return out


__all__ = ("SCHEMA", "ROOT_EVENT", "PpiStudyPacket", "inspect_ppi_one_event_study_lab")
