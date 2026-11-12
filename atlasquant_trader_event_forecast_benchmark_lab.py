"""Pure LAB: paired historical error comparison, with missing-event accounting.

Caller supplies unverified forecast locks, actual claims and optional claimed
GitHub anchors. This is NOT an independently attested backtest, trading signal,
calibrated probability, or live data feed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from atlasquant_trader_event_forecast_lock_lab import (
    ActualClaim, ForecastLock, score_locked_forecast_lab,
)
from atlasquant_trader_forecast_anchor_lab import (
    AnchorTarget, ClaimedGitHubComment, _rebuild_lock,
    assess_claimed_github_anchor_lab,
)

SCHEMA = "ATLASQUANT_TRADER_PAIRED_EVENT_FORECAST_BENCHMARK_LAB_V1"
_MAX_ROWS = 1000


@dataclass(frozen=True)
class BenchmarkCase:
    locked_forecast: ForecastLock
    actual_claim: ActualClaim | None = None
    anchor_target: AnchorTarget | None = None
    anchor_comment_claim: ClaimedGitHubComment | None = None


def _utc(v: Any) -> datetime | None:
    if (not isinstance(v, datetime) or v.tzinfo is None
            or v.utcoffset() is None or v.microsecond != 0):
        return None
    return v.astimezone(timezone.utc)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BENCHMARK_BLOCKED", "reason": reason,
        "currency": None, "metric": None, "unit": None, "as_of_utc": None,
        "registered_events": 0, "scored_events_documentary": 0,
        "waiting_for_release": 0, "missing_actual_after_release": 0,
        "with_model_estimate_registered": 0, "without_model_estimate_registered": 0,
        "matched_model_and_consensus_scored": 0,
        "anchor_chronology_candidates_unattested": 0,
        "anchor_claim_missing": 0,
        "mae_model_matched_documentary": None,
        "mae_consensus_matched_documentary": None,
        "mae_previous_matched_documentary": None,
        "paired_model_skill_vs_consensus_documentary": None,
        "paired_model_closer_count_documentary": None,
        "paired_model_tie_count_documentary": None,
        "paired_model_worse_count_documentary": None,
        "paired_model_closer_share_documentary": None,
        "fully_scored_registered_cohort": False,
        "minimum_matched_sample_reached": False,
        "rows": [],
        "independent_pre_event_forecast_witnesses_verified": 0,
        "independently_authenticated_actual_count": 0,
        "dataset_point_in_time_independently_verified": False,
        "no_selection_bias_verified": False,
        "validated_prediction_count": 0, "validated_accuracy": None,
        "calibrated_direction_probability": None,
        "fx_bias": None, "index_bias": None, "operational_bias": "AGUARDAR",
        "publishable": False, "live_alert_allowed": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0, "file_writes": 0,
        "new_cost_brl": 0, "research_only": True,
    }


def _mean(values: list[Decimal]) -> str:
    return str(sum(values, Decimal(0)) / Decimal(len(values)))


def evaluate_event_forecast_cohort_lab(
    cases: Any, *, as_of_utc: Any, minimum_matched_sample: int = 30,
) -> dict[str, Any]:
    """Count all registered cases; paired MAE only after claims of actual exist.

    A caller can omit losing forecasts or invent outcomes; even 1000 synthetic
    samples therefore cannot establish predictive accuracy or provenance.
    """
    out = _blocked("INVALID_CASES_OR_CLOCK")
    now = _utc(as_of_utc)
    if (now is None or not isinstance(cases, (tuple, list))
            or not 1 <= len(cases) <= _MAX_ROWS
            or type(minimum_matched_sample) is not int
            or not 10 <= minimum_matched_sample <= _MAX_ROWS):
        return out

    seen_event_ids: set[str] = set()
    seen_observations: set[tuple[str, str, str, str]] = set()
    # Same metric/unit across two countries is not one comparable series.
    # CPI definitions, seasonal adjustments and publication vintages differ.
    series_key: tuple[str, str, str] | None = None
    rows: list[dict[str, Any]] = []
    sums_model: list[Decimal] = []
    sums_consensus: list[Decimal] = []
    sums_previous: list[Decimal] = []
    closer = ties = worse = 0
    waiting = missing = model_registered = no_model = scored = 0
    anchor_candidate = anchor_missing = 0

    for case in cases:
        if not isinstance(case, BenchmarkCase):
            return _blocked("INVALID_CASE_IN_COHORT")
        rebuilt = _rebuild_lock(case.locked_forecast)
        if rebuilt is None:
            return _blocked("INVALID_OR_UNREPRODUCIBLE_FORECAST_LOCK")
        data, captured, release = rebuilt
        if captured > now:
            return _blocked("FORECAST_CAPTURE_AFTER_RESEARCH_ASOF")
        observation_key = (data["currency"], data["metric"],
                           data["target_period"], data["unit"])
        if (data["event_id"] in seen_event_ids
                or observation_key in seen_observations):
            return _blocked("DUPLICATE_ECONOMIC_EVENT_IN_COHORT")
        seen_event_ids.add(data["event_id"])
        seen_observations.add(observation_key)
        metric_unit = (data["currency"], data["metric"], data["unit"])
        if series_key is not None and metric_unit[0] != series_key[0]:
            return _blocked("MIXED_CURRENCY_FORECAST_ERRORS_NOT_COMPARABLE")
        if series_key is not None and metric_unit[1:] != series_key[1:]:
            return _blocked("MIXED_METRIC_OR_UNIT_MAE_NOT_COMPARABLE")
        series_key = metric_unit

        if (case.anchor_target is None) != (case.anchor_comment_claim is None):
            return _blocked("INCOMPLETE_ANCHOR_PAIR")
        claimed_anchor = False
        if case.anchor_target is not None:
            candidate = assess_claimed_github_anchor_lab(
                case.locked_forecast, case.anchor_target,
                case.anchor_comment_claim, as_of_utc=now,
            )
            if candidate["state"] != "LAB_COMMENT_ANCHOR_CHRONOLOGY_CANDIDATE_UNATTESTED":
                return _blocked("INVALID_CLAIMED_EXTERNAL_ANCHOR")
            claimed_anchor = True
            anchor_candidate += 1
        else:
            anchor_missing += 1

        has_model = data["model_estimate"] is not None
        model_registered += int(has_model)
        no_model += int(not has_model)
        row = {
            "event_id": data["event_id"], "currency": data["currency"],
            "target_period": data["target_period"],
            "forecast_sha256": case.locked_forecast.payload_sha256,
            "claimed_anchor_chronology_only": claimed_anchor,
            "model_estimate_present": has_model,
            "model_abs_error_documentary": None,
            "consensus_abs_error_documentary": None,
            "state": "LAB_WAIT_RELEASE",
        }
        if case.actual_claim is not None and now < release:
            return _blocked("POST_RELEASE_ACTUAL_PROVIDED_BEFORE_RELEASE")
        if now < release:
            waiting += 1
        elif case.actual_claim is None:
            row["state"] = "LAB_MISSING_POST_RELEASE_ACTUAL"
            missing += 1
        else:
            result = score_locked_forecast_lab(
                case.locked_forecast, case.actual_claim, as_of_utc=now,
            )
            if result["state"] != "LAB_POST_EVENT_DESCRIPTIVE_SCORE_UNATTESTED":
                return _blocked("INVALID_POST_RELEASE_ACTUAL_CLAIM")
            scored += 1
            row["state"] = "LAB_SCORED_ACTUAL_CLAIM_UNATTESTED"
            row["model_abs_error_documentary"] = result["model_abs_error_documentary"]
            row["consensus_abs_error_documentary"] = result["consensus_abs_error_documentary"]
            if has_model:
                m = Decimal(result["model_abs_error_documentary"])
                c = Decimal(result["consensus_abs_error_documentary"])
                p = Decimal(result["previous_abs_error_documentary"])
                sums_model.append(m)
                sums_consensus.append(c)
                sums_previous.append(p)
                if m < c:
                    closer += 1
                elif m == c:
                    ties += 1
                else:
                    worse += 1
        rows.append(row)

    paired = len(sums_model)
    complete = waiting == 0 and missing == 0
    eligible = paired >= minimum_matched_sample and complete and no_model == 0
    out.update({
        "state": ("LAB_DOCUMENTARY_PAIRED_BENCHMARK_UNVERIFIED" if eligible
                  else "LAB_INCOMPLETE_OR_SMALL_COHORT_NO_PERFORMANCE_CLAIM"),
        "reason": ("ALL_SOURCES_AND_WITNESSES_STILL_UNATTESTED" if eligible
                   else "COUNT_MISSING_RESULTS_AND_REQUIRE_SUFFICIENT_PAIRED_EVENTS"),
        "currency": series_key[0], "metric": series_key[1],
        "unit": series_key[2],
        "as_of_utc": now.isoformat(),
        "registered_events": len(rows),
        "scored_events_documentary": scored,
        "waiting_for_release": waiting,
        "missing_actual_after_release": missing,
        "with_model_estimate_registered": model_registered,
        "without_model_estimate_registered": no_model,
        "matched_model_and_consensus_scored": paired,
        "anchor_chronology_candidates_unattested": anchor_candidate,
        "anchor_claim_missing": anchor_missing,
        "fully_scored_registered_cohort": complete,
        "minimum_matched_sample_reached": paired >= minimum_matched_sample,
        "rows": rows,
    })
    # Small or incomplete cohorts do not display a seemingly persuasive MAE.
    if not eligible:
        return out
    sum_model = sum(sums_model, Decimal(0))
    sum_consensus = sum(sums_consensus, Decimal(0))
    out.update({
        "mae_model_matched_documentary": _mean(sums_model),
        "mae_consensus_matched_documentary": _mean(sums_consensus),
        "mae_previous_matched_documentary": _mean(sums_previous),
        "paired_model_skill_vs_consensus_documentary": (
            str(Decimal(1) - sum_model / sum_consensus)
            if sum_consensus != 0 else None),
        "paired_model_closer_count_documentary": closer,
        "paired_model_tie_count_documentary": ties,
        "paired_model_worse_count_documentary": worse,
        "paired_model_closer_share_documentary": str(Decimal(closer) / Decimal(paired)),
    })
    return out


__all__ = ["SCHEMA", "BenchmarkCase", "evaluate_event_forecast_cohort_lab"]
