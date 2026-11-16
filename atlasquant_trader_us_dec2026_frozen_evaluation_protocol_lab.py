"""Pre-registered DEC-2026 CPI/PPI research evaluation protocol, NO-GO.

This freezes two macro event roots, seven *correlated* USD crosses, and M15,
H1, H4 descriptive price windows BEFORE either scheduled BLS release. This
code contains an explicit ABSTAIN for both events, NO model forecasts and
NO validated performance statistics. Neither source SHA claims nor a Git
commit itself independently attest source publication/first-seen timing.

It is NOT a trading strategy, accuracy computation, synthetic signal
generator or operational backtest. Individual price-pair observations must
never be counted as independent economic trials. A missing original or
competing macro release must NEVER silently remove an event from the census.

Pure Python (no network, disk, broker, API, worker, orders, subscriptions).
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import USD_FX, WINDOWS
from atlasquant_trader_us_dec2026_pre_event_consensus_custody_lab import (
    EVENTS, inspect_us_dec2026_pre_event_consensus_custody_lab,
)

SCHEMA = "ATLASQUANT_US_DEC2026_FROZEN_PRE_EVENT_EVALUATION_PLAN_LAB_V1"
PINNED_PLAN_SHA256 = "abfb469b0292f913694ebc3ebb7ee16f94fd210cbd9f8d0ca6c7e6a12ea77776"

# Plain literals, canonical JSON SHA-256 pinned in this pre-release Git PR.
# The pin verifies later code has not changed the plan. External Git
# timestamps are STILL needed to independently assess commitment time.
FROZEN_PLAN: dict[str, Any] = {
    "schema": SCHEMA,
    "issuer": "BLS",
    "period": "2026-11",
    "event_roots": [
        {
            "root_id": "US_CPI_NOV2026",
            "release_utc": "2026-12-10T13:30:00+00:00",
            "latest_pre_event_freeze_utc": "2026-12-10T12:30:00+00:00",
            "forecast_direction": "ABSTAIN",
        },
        {
            "root_id": "US_PPI_NOV2026",
            "release_utc": "2026-12-15T13:30:00+00:00",
            "latest_pre_event_freeze_utc": "2026-12-15T12:30:00+00:00",
            "forecast_direction": "ABSTAIN",
        },
    ],
    "usd_fx_crosses": ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD",
                       "USDJPY", "USDCHF", "USDCAD"],
    "analysis_windows_minutes": {"M15": 15, "H1": 60, "H4": 240},
    "primary_descriptive_horizon": "H4",
    "price_baseline_rule": "M15_CANDLE_OPEN_AT_RELEASE_MINUS_15_MINUTES",
    "price_endpoint_rule": "CLOSED_M15_CANDLE_AT_RELEASE_PLUS_WINDOW_MINUTES",
    "usd_sign_convention": "USD_BASE_DIRECT_USD_QUOTE_INVERTED",
    "data_must_include":
        "ORIGINAL_BLS_AND_PRE_RELEASE_CONSENSUS_BYTES_SAME_METRIC_AND_PIT_WITH_BROKER_PRICE_SPREAD",
    "ambiguous_or_missing_policy": "RETAIN_ECONOMIC_EVENT_IN_DENOMINATOR_AND_ABSTAIN",
    "news_confounder_policy":
        "OVERLAPPING_MACRO_EVENTS_MUST_BE_AUDITED_NO_EXCLUSIVE_CAUSALITY_ASSUMED",
    "independent_economic_event_roots": 2,
    "registered_forecasts": 0,
    "validated_model_version": None,
    "accuracy_claim_allowed": False,
    "publication_or_trade_allowed": False,
}


def _utc(t: Any) -> datetime | None:
    if type(t) is not datetime or t.tzinfo is None:
        return None
    try:
        return t.astimezone(timezone.utc) if t.utcoffset() is not None else None
    except (TypeError, OverflowError, ValueError):
        return None


def canonical_frozen_plan_bytes_lab(plan: Any) -> bytes | None:
    """Exactly the frozen fields/types, with no extra post-hoc dimensions."""
    if type(plan) is not dict or set(plan) != set(FROZEN_PLAN):
        return None
    try:
        return json.dumps(plan, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, OverflowError, ValueError, UnicodeError, RecursionError):
        return None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_DEC2026_FROZEN_EVALUATION_PROTOCOL_BLOCKED_NO_GO",
        "reason": reason,
        "frozen_event_roots": ["US_CPI_NOV2026", "US_PPI_NOV2026"],
        "frozen_economic_event_denominator": 2,
        "frozen_plan_sha256": None,
        "frozen_primary_descriptive_horizon": "H4",
        "events": [
            {
                "event_root": root, "reference_period": period,
                "release_utc": release.isoformat(),
                "pre_event_directional_research_decision": "ABSTAIN",
                "status": "UNVERIFIED",
                "source_snapshot_hash_count_locally_claimed_only": 0,
                "price_window_results_verified": False,
                "forecast_direction_verified": False,
                "scoreable_prediction": False,
            }
            for root, _, period, release in EVENTS
        ],
        "locally_replayed_source_snapshots": 0,
        "prospective_directional_forecasts_registered": 0,
        "independent_economic_prediction_trials_verified": 0,
        "independent_testable_out_of_sample_trials": 0,
        "descriptive_correlated_fx_observations_not_independent_predictions": True,
        "incomplete_economic_events_retained_in_denominator": True,
        "overlap_or_confounders_independently_ruled_out": False,
        "pre_event_commitment_git_timestamp_independently_authenticated": False,
        "publisher_first_seen_independently_authenticated": False,
        "broker_prices_spreads_and_slippage_authenticated": False,
        "directional_model_calibrated_and_locked": False,
        "forecast_accuracy": None,
        "forecast_probability": None,
        "usd_direction": None,
        "forex_trade_signal": None,
        "trade_authorized": False,
        "publishable": False,
        "operational_bias": "AGUARDAR",
        "new_trading_cost_brl": 0,
        "fx28_672_campaign_slots_modified": False,
        "http_requests": 0, "file_writes": 0, "mt5_calls": 0,
    }


def inspect_frozen_dec2026_evaluation_protocol_lab(
    *, inspected_at_utc: Any, source_snapshots: Any = (),
    submitted_plan: Any = None,
) -> dict[str, Any]:
    """Source custody may pass, but no untrained forecast can be invented."""
    out = _blocked("NO_FROZEN_OR_VERIFIABLE_EVALUATION_PROTOCOL")
    now = _utc(inspected_at_utc)
    if now is None:
        out["reason"] = "INVALID_RESEARCH_CUTOFF"
        return out
    encoded = canonical_frozen_plan_bytes_lab(FROZEN_PLAN)
    if encoded is None or sha256(encoded).hexdigest() != PINNED_PLAN_SHA256:
        out["reason"] = "FROZEN_CODE_POLICY_SHA_MISMATCH"
        return out
    if submitted_plan is not None:
        external = canonical_frozen_plan_bytes_lab(submitted_plan)
        if external is None or external != encoded:
            out["reason"] = "SUBMITTED_PROTOCOL_CHANGED_AFTER_PRE_REGISTRATION"
            return out
    expected_roots = [root for root, _, _, _ in EVENTS]
    expected_release = [dt.isoformat() for _, _, _, dt in EVENTS]
    expected_freeze = [
        (dt.replace(microsecond=0) -
         __import__("datetime").timedelta(hours=1)).isoformat()
        for _, _, _, dt in EVENTS
    ]
    if (FROZEN_PLAN["event_roots"] != [
            {
                "root_id": name,
                "release_utc": release,
                "latest_pre_event_freeze_utc": freeze,
                "forecast_direction": "ABSTAIN",
            }
            for name, release, freeze in zip(
                expected_roots, expected_release, expected_freeze
            )]
            or FROZEN_PLAN["usd_fx_crosses"] != list(USD_FX)
            or FROZEN_PLAN["analysis_windows_minutes"] != dict(WINDOWS)
            or FROZEN_PLAN["primary_descriptive_horizon"] != "H4"
            or FROZEN_PLAN["independent_economic_event_roots"] != len(EVENTS)
            or FROZEN_PLAN["registered_forecasts"] != 0
            or FROZEN_PLAN["validated_model_version"] is not None
            or FROZEN_PLAN["accuracy_claim_allowed"] is not False
            or FROZEN_PLAN["publication_or_trade_allowed"] is not False):
        out["reason"] = "RELEASE_CLOCK_HORIZON_CROSS_OR_ABSTENTION_PLAN_INCONSISTENT"
        return out
    sources = inspect_us_dec2026_pre_event_consensus_custody_lab(
        snapshots=source_snapshots, research_cutoff_utc=now
    )
    if (sources["state"] != "LAB_DEC2026_PRE_EVENT_SOURCE_CUSTODY_ONLY_NO_GO"
            or sources["frozen_upcoming_economic_event_denominator"] != len(EVENTS)
            or sources["economically_validated_pre_event_consensus_events"] != 0
            or sources["validated_out_of_sample_trading_trials"] != 0
            or sources["trade_authorized"] is not False
            or sources["publishable"] is not False):
        out["reason"] = "SOURCE_ARCHIVE_FAILED_CUSTODY_NO_PARTIAL_FORECAST"
        return out
    updated = []
    for (root, _, period, release), row, raw in zip(
        EVENTS, out["events"], sources["events"]
    ):
        if raw["root_id"] != root or raw["reference_period"] != period:
            return _blocked("SOURCE_ROSTER_CHANGED_OR_UNKNOWN_RELEASE")
        state = (
            "PRE_RELEASE_FROZEN_ABSTENTION" if now < release
            else "POST_RELEASE_DESCRIPTIVE_ONLY_NO_FORECAST"
        )
        updated.append({
            **row,
            "status": state,
            "source_snapshot_hash_count_locally_claimed_only":
                raw["locally_reconciled_source_count"],
        })
    out.update({
        "state": "LAB_DEC2026_FROZEN_DESCRIPTIVE_PROTOCOL_RECONCILED_NO_GO",
        "reason": "EXACT_PRE_EVENT_PROTOCOL_ABSTAIN_NO_VALIDATED_FOREX_MODEL",
        "frozen_plan_sha256": PINNED_PLAN_SHA256,
        "events": updated,
        "locally_replayed_source_snapshots":
            sources["locally_sha_reconciled_pre_event_source_documents"],
    })
    return out


__all__ = (
    "SCHEMA", "PINNED_PLAN_SHA256", "FROZEN_PLAN",
    "canonical_frozen_plan_bytes_lab",
    "inspect_frozen_dec2026_evaluation_protocol_lab",
)
