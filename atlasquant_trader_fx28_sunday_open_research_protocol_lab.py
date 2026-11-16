"""Sunday FX28 M15 session-open research without market access or retiming.

Only interprets three *caller-supplied* historical aggregate observations;
they are NOT independently authenticated broker or point-in-time receipts.
The prospective output is a protocol for a separate research experiment
AFTER the original 15-Nov/11-Dec 672-slot campaign, never a scheduler.

No MT5, GitHub, filesystem, HTTP, orders, prices, interpolation, forecast,
accuracy, current campaign capture, automated retry or implementation of
a new market reader. Three highly correlated Sunday samples are THREE
weekly sessions, not 84 independent trading results.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

SCHEMA = "ATLASQUANT_FX28_SUNDAY_OPEN_SEPARATE_RESEARCH_PROTOCOL_LAB_V1"
UTC = timezone.utc
NY = ZoneInfo("America/New_York")
CAMPAIGN_END = datetime(2026, 12, 11, 22, tzinfo=UTC)
FIRST_SEPARATE_SUNDAY = datetime(2026, 12, 13, 22, tzinfo=UTC)
OBSERVED = (
    ("2026-10-25", datetime(2026, 10, 25, 21, tzinfo=UTC)),
    ("2026-11-01", datetime(2026, 11, 1, 22, tzinfo=UTC)),
    ("2026-11-08", datetime(2026, 11, 8, 22, tzinfo=UTC)),
)
FX_PAIRS = 28
MAX_HOURS = 5
BAR_MIN = 15


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_SUNDAY_OPEN_RESEARCH_PROTOCOL_BLOCKED_NO_GO",
        "reason": reason,
        "historical_sunday_sessions": 0,
        "pair_series_observed_claim_only": 0,
        "historical_nominal_start_bars_claim_only": None,
        "aggregated_first_bar_lags_minutes_claim_only": {},
        "historical_min_lag_min": None,
        "historical_max_lag_min": None,
        "candidate_separate_research_sunday_utc": None,
        "separate_research_history_window_end_utc": None,
        "first_separate_research_date_utc": FIRST_SEPARATE_SUNDAY.isoformat(),
        "frozen_campaign_end_utc": CAMPAIGN_END.isoformat(),
        "sample_weekly_sessions_not_independent_pairs": True,
        "historical_data_are_caller_claims_not_broker_attestation": True,
        "independent_broker_session_hours_attested": False,
        "absence_of_nominal_bar_proves_market_closed": False,
        "future_market_open_lag_guaranteed": False,
        "retime_frozen_campaign": False,
        "backfill_missing_20261115_candle": False,
        "score_missing_as_prediction_error": False,
        "score_missing_as_prediction_hit": False,
        "can_run_market_probe": False,
        "automatic_scheduler_enabled": False,
        "validated_accuracy": None,
        "calibrated_probability": None,
        "trade_authorized": False,
        "publishable": False,
        "operational_bias": "AGUARDAR",
        "http_requests": 0,
        "mt5_calls": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
    }


def _utc_no_subseconds(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.second or value.microsecond:
            return None
        return value.astimezone(UTC)
    except (ValueError, TypeError, OverflowError):
        return None


def inspect_fx28_sunday_open_research_protocol_lab(
    *, historical_sunday_summaries: Any,
    separate_research_sunday_utc: Any,
) -> dict[str, Any]:
    """Assess strict historical claims; return *nonexecuting* future protocol.

    The protocol NEVER queries market prices. Its 5h range is only a
    recommendation for an independently approved future measurement:
    it may not replace any frozen NY17 M15 D1/W1 outcome boundary.
    """
    result = _blocked("INVALID_HISTORICAL_SAMPLE_OR_FUTURE_RESEARCH_DATE")
    start = _utc_no_subseconds(separate_research_sunday_utc)
    if (not isinstance(historical_sunday_summaries, (list, tuple))
            or len(historical_sunday_summaries) != len(OBSERVED)
            or start is None
            or start < FIRST_SEPARATE_SUNDAY
            or start <= CAMPAIGN_END
            or start.astimezone(NY).weekday() != 6
            or (start.astimezone(NY).hour,
                start.astimezone(NY).minute) != (17, 0)):
        return result

    across: dict[int, int] = {}
    sample_rows: list[dict[str, Any]] = []
    nominal_present = 0
    for source, (day, nominal) in zip(historical_sunday_summaries, OBSERVED):
        if type(source) is not dict:
            result["reason"] = "HISTORICAL_SUMMARY_NOT_A_DICTIONARY"
            return result
        required = (
            source.get("historical_sunday") == day
            and source.get("frozen_start_utc_in_sample") == nominal.isoformat()
            and type(source.get("window_checked_hours")) is int
            and source.get("window_checked_hours") == MAX_HOURS
            and type(source.get("queried_28")) is int
            and source.get("queried_28") == FX_PAIRS
            and type(source.get("valid_nonempty_series_count")) is int
            and source.get("valid_nonempty_series_count") == FX_PAIRS
            and type(source.get("first_nominal_m15_present_count")) is int
            and 0 <= source.get("first_nominal_m15_present_count") <= FX_PAIRS
            and type(source.get("first_nominal_m15_missing_count_among_valid")) is int
            and source.get("first_nominal_m15_missing_count_among_valid")
                == FX_PAIRS-source.get("first_nominal_m15_present_count")
            and all(type(source.get(k)) is int and source.get(k) == 0 for k in (
                "mt5_api_none_count", "symbols_without_metadata_count",
                "empty_or_invalid_count", "visibility_changes_count"))
            and source.get("not_proof_future_market_open") is True
        )
        if not required:
            result["reason"] = "HISTORICAL_SOURCE_ERRORS_OR_INCONSISTENT_COUNTS"
            return result
        distribution = source.get("first_actual_m15_lag_minute_distribution")
        if type(distribution) is not dict or not distribution:
            result["reason"] = "HISTORICAL_LAG_DISTRIBUTION_MISSING"
            return result
        parsed: dict[int, int] = {}
        for raw_lag, count in distribution.items():
            if (type(raw_lag) is int and not isinstance(raw_lag, bool)):
                lag = raw_lag
            elif (type(raw_lag) is str and raw_lag.isascii()
                  and raw_lag.isdecimal() and str(int(raw_lag)) == raw_lag):
                lag = int(raw_lag)
            else:
                result["reason"] = "INVALID_LAG_BUCKET_OR_COUNT"
                return result
            if (lag < 0 or lag >= MAX_HOURS*60 or lag % BAR_MIN
                    or lag in parsed or type(count) is not int
                    or not 1 <= count <= FX_PAIRS):
                result["reason"] = "INVALID_LAG_BUCKET_OR_COUNT"
                return result
            parsed[lag] = count
        if (sum(parsed.values()) != FX_PAIRS
                or parsed.get(0, 0) != source["first_nominal_m15_present_count"]
                or (source.get("min_observed_lag_min") != min(parsed)
                    or source.get("max_observed_lag_min") != max(parsed))):
            result["reason"] = "HISTORICAL_FIRST_BAR_LAGS_DISAGREE_WITH_CENSUS"
            return result
        nominal_present += parsed.get(0, 0)
        for lag, count in parsed.items():
            across[lag] = across.get(lag, 0) + count
        sample_rows.append({
            "historical_sunday": day,
            "nominal_start_utc_claim_only": nominal.isoformat(),
            "pair_series_claim_only": FX_PAIRS,
            "nominal_first_bars_claim_only": parsed.get(0, 0),
            "first_available_lags_min_claim_only":
                {str(k): v for k, v in sorted(parsed.items())},
            "independently_authenticated": False,
        })

    if sum(across.values()) != 84 or len(sample_rows) != 3:
        result["reason"] = "THREE_SUNDAY_84_SERIES_CENSUS_NOT_MET"
        return result
    result.update({
        "state": "LAB_FX28_SUNDAY_OPEN_3_HISTORICAL_SAMPLES_PLAN_ONLY_NO_GO",
        "reason": "HISTORICAL_AGGREGATES_CONSISTENT_ONLY_NO_BROKER_PIT_PROOF",
        "historical_sunday_sessions": 3,
        "pair_series_observed_claim_only": 84,
        "historical_nominal_start_bars_claim_only": nominal_present,
        "aggregated_first_bar_lags_minutes_claim_only":
            {str(k): v for k, v in sorted(across.items())},
        "historical_min_lag_min": min(across),
        "historical_max_lag_min": max(across),
        "historical_samples_documentary": sample_rows,
        "candidate_separate_research_sunday_utc": start.isoformat(),
        "separate_research_history_window_end_utc":
            (start + timedelta(hours=MAX_HOURS)).isoformat(),
        "separate_research_measurement_minutes": MAX_HOURS*60,
        "distinct_weekly_sessions_not_84_independent_trials": 3,
        "nominal_bar_absence_not_broker_session_proof": True,
        "future_probe_requires_new_explicit_authorization": True,
    })
    return result


__all__ = ("SCHEMA", "FIRST_SEPARATE_SUNDAY",
           "inspect_fx28_sunday_open_research_protocol_lab")
