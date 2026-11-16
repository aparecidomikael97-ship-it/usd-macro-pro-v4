"""Sunday FX28 first-M15 UTC/server-clock discrepancy, research-only P0 guard.

Compare caller-provided historical first-bar lags to Pepperstone's published
*general* FX server schedule; compare with MetaQuotes' stated UTC timestamp
contract for Python MT5 copy_rates_range. A coincidence between lags and
server GMT offsets is evidence of a possible TIME AXIS MIXUP, not proof
of one, and is NOT authorization to transform epoch timestamps.

Neither official page authenticates the user's particular MT5 account,
server, first quote, instrument schedule, downloaded history, nor realtime
point-in-time candle availability. NEVER retime the 672 frozen slots, fill
M15 gaps, generate trades, issue a directional forecast, or rerun MT5.
This module has no filesystem, terminal, network, scheduler or orders.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from atlasquant_trader_fx28_sunday_open_research_protocol_lab import (
    FIRST_SEPARATE_SUNDAY,
    inspect_fx28_sunday_open_research_protocol_lab,
)

UTC = timezone.utc
NY = ZoneInfo("America/New_York")
SCHEMA = "ATLASQUANT_FX28_SUNDAY_SERVER_UTC_DISCREPANCY_GUARD_LAB_V1"
PEPPERSTONE_HOURS_URL = "https://pepperstone.com/en/about-us/trading-hours"
METAQUOTES_API_URL = "https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesrange_py"
FX_SERVER_SCHEDULE = "FOREX_MONDAY_0001_SERVER_TIME_PUBLIC_WEB_PAGE"
MT5_API_CONTRACT = "COPY_RATES_RANGE_UTC_TIMESTAMP_PUBLIC_REFERENCE"
HISTORY_WEEKS = (
    ("2026-10-25", datetime(2026, 10, 25, 21, tzinfo=UTC)),
    ("2026-11-01", datetime(2026, 11, 1, 22, tzinfo=UTC)),
    ("2026-11-08", datetime(2026, 11, 8, 22, tzinfo=UTC)),
)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_SUNDAY_SERVER_UTC_DISCREPANCY_BLOCKED_NO_GO",
        "reason": reason,
        "source_urls": [PEPPERSTONE_HOURS_URL, METAQUOTES_API_URL],
        "official_pages_are_documentary_not_broker_account_attestation": True,
        "published_server_summer_offset_hours": 3,
        "published_server_winter_offset_hours": 2,
        "published_fx_first_trading_minute_server": "MONDAY 00:01",
        "mt5_copy_rates_range_documentation_says_utc": True,
        "historical_sundays_valid": 0,
        "historical_pair_series": 0,
        "observed_historical_nominal_m15_bars": None,
        "weeks_with_min_lag_equal_published_server_offset": 0,
        "clock_discrepancy_cases": [],
        "all_minimum_lags_match_server_offset": False,
        "actual_time_axis_shift_independently_proven": False,
        "true_broker_open_time_independently_proven": False,
        "mt5_epoch_values_independently_attested": False,
        "proven_api_time_conversion_error": False,
        "missing_20261115_bar_backfilled": False,
        "original_672_campaign_slots_modified": False,
        "clock_rewrite_allowed": False,
        "historical_accuracy_validated": False,
        "validated_directional_accuracy": None,
        "trade_authorized": False,
        "publishable": False,
        "scheduler_enabled": False,
        "operational_bias": "AGUARDAR",
        "http_requests": 0,
        "mt5_calls": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
    }


def inspect_fx28_sunday_server_utc_discrepancy_lab(
    *, historical_sunday_summaries: Any,
    inspected_at_utc: Any,
) -> dict[str, Any]:
    """No live data: compare 3 documentary weeks with published server offsets.

    `inspected_at_utc` is a caller clock, not a trusted external timestamp.
    The existing three-week analyzer checks complete 28-pair aggregations.
    """
    out = _blocked("INVALID_HISTORICAL_SAMPLES_OR_ASOF")
    if (not isinstance(inspected_at_utc, datetime)
            or inspected_at_utc.tzinfo is None):
        return out
    try:
        asof = inspected_at_utc.astimezone(UTC)
    except (OverflowError, ValueError, TypeError):
        return out
    if (inspected_at_utc.utcoffset() is None or inspected_at_utc.microsecond
            or asof < datetime(2026,11,15,22,tzinfo=UTC)):
        return out

    # All three weeks are historical and cannot be converted into a
    # future observation, forecasts, trading outcomes or execution schedule.
    validated = inspect_fx28_sunday_open_research_protocol_lab(
        historical_sunday_summaries=historical_sunday_summaries,
        separate_research_sunday_utc=FIRST_SEPARATE_SUNDAY)
    if (validated.get("state") !=
            "LAB_FX28_SUNDAY_OPEN_3_HISTORICAL_SAMPLES_PLAN_ONLY_NO_GO"
            or validated.get("historical_sunday_sessions") != 3
            or validated.get("pair_series_observed_claim_only") != 84
            or validated.get("can_run_market_probe") is not False
            or validated.get("retime_frozen_campaign") is not False):
        out["reason"] = "THREE_WEEK_HISTORICAL_DATA_UNVERIFIED_OR_INCOMPLETE"
        return out

    results = []
    matched = 0
    for source, (date, nominal) in zip(historical_sunday_summaries, HISTORY_WEEKS):
        if (source.get("historical_sunday") != date
                or source.get("frozen_start_utc_in_sample") != nominal.isoformat()):
            out["reason"] = "HISTORICAL_WEEK_OR_NOMINAL_FROZEN_UTC_DRIFT"
            return out
        ny = nominal.astimezone(NY)
        if (ny.weekday() != 6 or ny.hour != 17 or ny.minute or ny.second):
            out["reason"] = "NOT_17_00_NEW_YORK_SUNDAY"
            return out
        is_dst = ny.dst() != timedelta(0)
        broker_offset = 3 if is_dst else 2
        # The published FX table uses Monday 00:01 server time.
        server_midnight = nominal + timedelta(hours=broker_offset)
        if (server_midnight.weekday() != 0
                or server_midnight.time() != time(0,0)):
            out["reason"] = "BROKER_SERVER_MONDAY_MIDNIGHT_CLOCK_MISMATCH"
            return out
        first_minute_published_utc = (
            server_midnight + timedelta(minutes=1)
            - timedelta(hours=broker_offset))
        if first_minute_published_utc != nominal + timedelta(minutes=1):
            out["reason"] = "PUBLISHED_SERVER_FIRST_MINUTE_UTC_BRIDGE_MISMATCH"
            return out
        floor = source.get("min_observed_lag_min")
        maximum = source.get("max_observed_lag_min")
        expected_min = broker_offset*60
        offset_match = type(floor) is int and floor == expected_min
        matched += int(offset_match)
        results.append({
            "historical_sunday": date,
            "nominal_new_york_17_utc": nominal.isoformat(),
            "published_server_offset_hours": broker_offset,
            "expected_server_wallclock_at_nominal": "MONDAY 00:00",
            "published_first_fx_minute_at_nominal_plus_seconds": 60,
            "first_nominal_m15_historical_claim_count":
                source["first_nominal_m15_present_count"],
            "first_historical_bar_lag_min_claim_only": floor,
            "max_historical_bar_lag_min_claim_only": maximum,
            "minimum_lag_equals_published_server_offset": offset_match,
            "derived_pseudoutc_server_midnight_hypothesis_at_utc":
                server_midnight.isoformat(),
            "pseudoutc_hypothesis_is_unverified": True,
            "historical_bars_are_not_server_first_trade_confirmation": True,
        })

    out.update({
        "state": ("LAB_FX28_SUNDAY_SERVER_OFFSET_ALIGNED_TIME_AXIS_P0_NO_GO"
                  if matched == 3 else
                  "LAB_FX28_SUNDAY_SERVER_OFFSET_MIXED_HISTORY_P0_NO_GO"),
        "reason": (
            "HISTORICAL_LAG_COINCIDES_WITH_FX_SERVER_GMT_OFFSETS_NOT_PROOF"
            if matched == 3 else
            "SUNDAY_LAGS_DO_NOT_CONSISTENTLY_MATCH_PUBLISHED_OFFSETS"),
        "historical_sundays_valid":3,
        "historical_pair_series":84,
        "observed_historical_nominal_m15_bars":
            validated["historical_nominal_start_bars_claim_only"],
        "weeks_with_min_lag_equal_published_server_offset":matched,
        "clock_discrepancy_cases":results,
        "all_minimum_lags_match_server_offset":matched==3,
    })
    return out


__all__ = (
    "SCHEMA", "PEPPERSTONE_HOURS_URL", "METAQUOTES_API_URL",
    "inspect_fx28_sunday_server_utc_discrepancy_lab",
)
