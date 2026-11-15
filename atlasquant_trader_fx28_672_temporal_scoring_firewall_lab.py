"""Read-only firewall between Sunday M15 evidence and 672-slot scoring.

Prior modules independently inspect (a) exactly-one sealed campaign Sunday
M15 archive, (b) all 672 frozen D1/W1 slots, (c) the documented GMT+2/+3
history discrepancy, and (d) the frozen scoring rules. This bridge makes
their combined NO-GO visible at the SCORING INGEST BOUNDARY.

No claimed perfect 672/672 hit rate can bypass a missing start observation
or a time-axis P0. It does not alter the existing documentary counter;
downstream verified-score publication must explicitly require a separate
independent source attestation, which no current module provides.

Archive bytes are examined READ-ONLY. Historical observations are
caller-supplied unverified summaries; no MT5, internet, file writes,
scheduler, signals, trade, date shifting or bar interpolation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atlasquant_trader_fx28_first_m15_672_slot_outcome_quarantine_lab import (
    inspect_first_m15_672_slot_outcome_quarantine_lab,
)
from atlasquant_trader_fx28_sunday_server_utc_discrepancy_guard_lab import (
    inspect_fx28_sunday_server_utc_discrepancy_lab,
)
from atlasquant_trader_fx28_672_scoring_protocol_lab import (
    precommit_fx28_672_scoring_rules_lab,
)
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    FROZEN_END_UTC,
)

SCHEMA = "ATLASQUANT_FX28_672_TEMPORAL_SCORING_INGRESS_FIREWALL_LAB_V1"
FIRST_OK = "LAB_FX28_FIRST_M15_56_OUTCOMES_QUARANTINED_NO_GO"
CLOCK_OK = "LAB_FX28_SUNDAY_SERVER_OFFSET_ALIGNED_TIME_AXIS_P0_NO_GO"
BEFORE_END = "LAB_FX28_672_SCORING_PROTOCOL_FROZEN_AWAIT_RESULTS_NO_GO"


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_672_TEMPORAL_SCORING_FIREWALL_BLOCKED_NO_GO",
        "reason": reason,
        "frozen_total_slots": 672,
        "first_nominal_window_slots_quarantined": 0,
        "first_nominal_window_distinct_m15_prices_missing": None,
        "remaining_original_slots_unevaluated": 672,
        "first_window_horizons": {"D1":0,"W1":0},
        "first_window_label_status": "UNKNOWN_NO_VERIFIED_ARCHIVE",
        "sunday_clock_p0_status": "UNKNOWN_NO_DOCUMENTARY_CLOCK_AUDIT",
        "sunday_weekly_history_samples": 0,
        "matching_server_offset_weekly_minima": 0,
        "source_first_seen_broker_authenticated": False,
        "market_server_utc_mapping_independently_attested": False,
        "historical_3_week_clocks_independently_attested": False,
        "pre_event_forecasts_independently_authenticated": False,
        "source_price_window_complete": False,
        "scoring_ingress_allowed": False,
        "documentary_perfect_score_claim_can_unlock_ingress": False,
        "directional_accuracy_validated": False,
        "validated_accuracy": None,
        "calibrated_probability": None,
        "documentary_score_count_released": 0,
        "historical_rows_retimed": 0,
        "source_bars_backfilled": 0,
        "frozen_campaign_slots_modified": False,
        "mt5_calls": 0, "http_requests": 0, "file_writes": 0,
        "new_cost_brl": 0, "trade_authorized": False,
        "publishable": False, "scheduler_enabled": False,
        "operational_bias": "AGUARDAR",
    }


def inspect_fx28_672_temporal_scoring_ingress_lab(
    *, archive_root: Any, inspected_at_utc: Any,
    historical_sunday_summaries: Any,
    window_claims: Any = (),
    proposed_documentary_scoring_report: Any = None,
) -> dict[str, Any]:
    """Verify real sealed archive against the frozen ledger and timezone P0.

    `window_claims=()` means no caller-supplied witness claims. Never
    infer the absence of an external forecast from this empty input.
    A full documentary scoring report, even one reporting 672 correct
    predictions, is NOT an independent source receipt. It is never read
    as a score or accepted as a bypass of the temporal guard.
    """
    out = _base("INVALID_ARCHIVE_CLOCK_OR_FORECAST_CLAIM_INPUT")
    if (type(archive_root) is not Path or not archive_root.is_absolute()
            or type(window_claims) not in (tuple,list)
            or type(inspected_at_utc) is not datetime
            or inspected_at_utc.tzinfo is None
            or inspected_at_utc.utcoffset() is None
            or inspected_at_utc.microsecond
            or (proposed_documentary_scoring_report is not None
                and type(proposed_documentary_scoring_report) is not dict)):
        return out
    now = inspected_at_utc.astimezone(timezone.utc)

    scoring = precommit_fx28_672_scoring_rules_lab(as_of_utc=now)
    if now < FROZEN_END_UTC and scoring.get("state") != BEFORE_END:
        out["reason"] = "FROZEN_672_SCORING_RULES_PRECAMPAIGN_END_INCONSISTENT"
        return out
    # Never feed supplied directional joins to the scorer. Even after the
    # campaign ends the original scorer rejects incomplete/no-evidence joins,
    # but the temporal gate must *independently* block any posthoc numbers.
    if (scoring.get("expected_pair_horizon_slots") != 672
            or scoring.get("validated_hit_rate_percent") is not None
            or scoring.get("trade_authorized") is not False
            or scoring.get("publishable") is not False):
        out["reason"] = "FROZEN_SCORER_INVALID_OR_LEAKED_VALIDATED_HIT_RATE"
        return out

    first = inspect_first_m15_672_slot_outcome_quarantine_lab(
        archive_root=archive_root,
        window_claims=window_claims,
        inspected_at_utc=now)
    if first.get("state") != FIRST_OK:
        out["reason"] = "REAL_FIRST_M15_ARCHIVE_OR_672_LEDGER_NOT_CONFIRMED"
        return out
    if (first.get("ledger_slots_accounted") != 672
            or first.get("quarantined_first_window_slots") != 56
            or first.get("first_window_d1_slots") != 28
            or first.get("first_window_w1_slots") != 28
            or first.get("other_frozen_slots_not_assessed") != 616
            or first.get("missing_distinct_nominal_m15_start_prices") != 28
            or len(first.get("first_window_rows", ())) != 56
            or any(row.get("scored_as_hit") is not False
                   or row.get("scored_as_miss") is not False
                   or row.get("scored_as_trade") is not False
                   for row in first["first_window_rows"])
            or (first.get("mt5_calls"),first.get("http_requests"),
                first.get("file_writes")) != (0,0,0)
            or first.get("trade_authorized") is not False):
        out["reason"] = "FIRST_56_UNLABELABLE_SLOTS_NOT_INTEGRALLY_QUARANTINED"
        return out

    out.update({
        "first_nominal_window_slots_quarantined":56,
        "first_nominal_window_distinct_m15_prices_missing":28,
        "remaining_original_slots_unevaluated":616,
        "first_window_horizons":{"D1":28,"W1":28},
        "first_window_label_status":"UNLABELABLE_28_NOMINAL_M15_GAPS_CLAIM_ONLY",
        "source_price_window_complete":False,
    })

    clock = inspect_fx28_sunday_server_utc_discrepancy_lab(
        historical_sunday_summaries=historical_sunday_summaries,
        inspected_at_utc=now)
    if (clock.get("state") != CLOCK_OK
            or clock.get("historical_sundays_valid") != 3
            or clock.get("historical_pair_series") != 84
            or clock.get("weeks_with_min_lag_equal_published_server_offset") != 3
            or clock.get("all_minimum_lags_match_server_offset") is not True
            or clock.get("proven_api_time_conversion_error") is not False
            or clock.get("clock_rewrite_allowed") is not False
            or clock.get("trade_authorized") is not False
            or (clock.get("mt5_calls"),clock.get("http_requests"),
                clock.get("file_writes")) != (0,0,0)):
        out["reason"] = "SUNDAY_CLOCK_SOURCE_UNRESOLVED_OR_HISTORICAL_CLAIMS_INVALID"
        return out
    out.update({
        "state":"LAB_FX28_672_FIRST56_AND_SERVER_CLOCK_P0_SCORING_QUARANTINE_NO_GO",
        "reason":"28_M15_NOMINAL_GAPS_PLUS_3_WEEK_SERVER_OFFSET_MATCH_UNATTESTED",
        "sunday_clock_p0_status":"3_OF_3_SERVER_GMT_OFFSET_MATCH_HYPOTHESIS_ONLY",
        "sunday_weekly_history_samples":3,
        "matching_server_offset_weekly_minima":3,
    })
    return out


__all__ = ("SCHEMA","inspect_fx28_672_temporal_scoring_ingress_lab")
