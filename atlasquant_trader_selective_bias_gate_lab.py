"""LAB: selective, low-frequency bias publication *preflight* (never publish).

The user wants fewer, better-supported Forex/index futures biases, not a
rolling buy/sell ticker. This checks abstention, W1/D1 agreement, distinct
confirmations, event blackout, duplicates and out-of-sample evidence.

Caller-provided flags and trial counts are NOT independently authenticated;
even a passing synthetic check is research-only with operational bias AGUARDAR.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import isfinite, sqrt
import re
from typing import Any, Iterable

from atlasquant_fx_universe import OFFICIAL_PAIRS


SCHEMA = "ATLASQUANT_TRADER_SELECTIVE_BIAS_ABSTENTION_LAB_V1"
ALLOWED_INDEX_IDS = frozenset({"WIN", "WDO", "US500", "NAS100", "US30"})
ALLOWED_SIDES = frozenset({"ALTA", "BAIXA", "NEUTRO"})
ALLOWED_HORIZONS = frozenset({"D1", "W1"})
MIN_DISPLAY_GRADE = 6.0  # ranking, never a 60% calibrated probability
MIN_HISTORY = 100
MIN_WINDOWS = 3
MIN_PER_WINDOW = 20
MIN_WILSON_LOWER = 0.80  # a *research goal*, not a promised win rate
MIN_CONFIRM_GAP = timedelta(minutes=30)
MAX_CONFIRM_GAP = timedelta(hours=3)
MAX_OBSERVATION_AGE = timedelta(hours=6)
MAX_MACRO_AGE = timedelta(hours=12)
ALERT_COOLDOWN = timedelta(hours=4)
HIGH_IMPACT_WINDOW = timedelta(minutes=30)
_HEX = re.compile(r"[0-9a-f]{64}\Z")


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _finite_grade(value: Any) -> bool:
    return type(value) in (int, float) and isfinite(value) and 0 <= value <= 10


@dataclass(frozen=True)
class BiasObservation:
    asset: str
    horizon: str
    evaluated_at: datetime
    weekly: str
    daily: str
    grade_0_to_10: float
    macro_captured_at: datetime
    snapshot_sha256: str


@dataclass(frozen=True)
class HoldoutWindow:
    asset: str
    horizon: str
    direction: str
    start_at: datetime
    end_at: datetime
    resolved_predictions: int
    correct_directions: int
    label: str = "CLOSED_BAR_DIRECTION_AFTER_ISSUED_BIAS"


@dataclass(frozen=True)
class SelectiveAuditClaims:
    macro_originals_and_pair_comparison_witnessed: bool
    out_of_sample_labels_pit_witnessed: bool
    geopol_macro_risk_reviewed: bool
    releases_captured_before_predictions: bool
    no_leakage_or_parameter_selection_on_holdout: bool
    market_data_license_reviewed: bool


@dataclass(frozen=True)
class LastAlert:
    asset: str
    horizon: str
    emitted_at: datetime
    direction: str


def _blocked(reason: str, *, history_n: int = 0) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_ABSTAIN", "reason": reason,
        "history_samples": history_n, "research_candidate_direction": None,
        "observed_holdout_hit_rate": None,
        "observed_holdout_wilson95_lower": None,
        "grade": None, "grade_is_probability": False,
        "calibrated_direction_probability": None,
        "score_0_to_10_certified": False,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "research_only": True, "worker_enabled": False,
        "scheduler_enabled": False, "new_cost_brl": 0,
        "source_and_trial_claims_independently_verified_by_this_module": False,
    }


def _wilson_lower(hits: int, count: int, z: float = 1.96) -> float:
    p = hits / count
    denominator = 1 + z * z / count
    center = p + z * z / (2 * count)
    margin = z * sqrt(p * (1 - p) / count + z * z / (4 * count * count))
    return max(0.0, (center - margin) / denominator)


def _valid_obs(row: Any, *, at: datetime) -> bool:
    if not isinstance(row, BiasObservation):
        return False
    when, macro = _utc(row.evaluated_at), _utc(row.macro_captured_at)
    if (when is None or macro is None or when > at or macro > when
            or at - when > MAX_OBSERVATION_AGE or when - macro > MAX_MACRO_AGE):
        return False
    if (not isinstance(row.horizon, str)
            or row.horizon not in ALLOWED_HORIZONS
            or not isinstance(row.asset, str)
            or row.asset not in set(OFFICIAL_PAIRS) | ALLOWED_INDEX_IDS
            or not isinstance(row.weekly, str) or not isinstance(row.daily, str)
            or row.weekly not in ALLOWED_SIDES or row.daily not in ALLOWED_SIDES
            or not _finite_grade(row.grade_0_to_10)
            or not isinstance(row.snapshot_sha256, str)
            or _HEX.fullmatch(row.snapshot_sha256) is None):
        return False
    return True


def _holdout_score(
    windows: Iterable[HoldoutWindow], before: datetime, *,
    asset: str, horizon: str, direction: str,
) -> tuple[str, int, int, float | None]:
    try:
        rows = list(windows)
    except (TypeError, ValueError):
        return "INVALID_OOS_WINDOWS", 0, 0, None
    if len(rows) < MIN_WINDOWS or len(rows) > 32:
        return "INSUFFICIENT_OOS_WINDOWS", 0, 0, None
    earlier = None
    n = hits = 0
    for row in rows:
        if not isinstance(row, HoldoutWindow):
            return "INVALID_OOS_WINDOW", 0, 0, None
        start, end = _utc(row.start_at), _utc(row.end_at)
        if (row.asset != asset or row.horizon != horizon or row.direction != direction
                or start is None or end is None or not start < end < before
                or earlier is not None and start <= earlier
                or type(row.resolved_predictions) is not int
                or type(row.correct_directions) is not int
                or row.resolved_predictions < MIN_PER_WINDOW
                or not 0 <= row.correct_directions <= row.resolved_predictions
                or row.label != "CLOSED_BAR_DIRECTION_AFTER_ISSUED_BIAS"):
            return "INVALID_OR_LEAKING_OOS_WINDOW", 0, 0, None
        earlier = end
        n += row.resolved_predictions
        hits += row.correct_directions
    if n < MIN_HISTORY:
        return "INSUFFICIENT_OOS_SAMPLE", n, hits, None
    return "DOCUMENTARY_OOS_SCORE_ONLY", n, hits, _wilson_lower(hits, n)


def assess_selective_bias_lab(
    candidate: Any, previous_confirmations: Any, holdout_windows: Any,
    audit_claims: Any, *, now: Any, high_impact_events: Any = (),
    unverified_event_actual_pending: bool = False,
    last_alert: Any = None, reversal_catalyst_claimed: bool = False,
) -> dict[str, Any]:
    """Return an internal research candidate or ABSTAIN, never a live bias.

    Data is caller-asserted; no amount of scores, hashes or flags can change
    operational_bias or authorize user-facing signals in this module.
    """
    current = _utc(now)
    if current is None or not _valid_obs(candidate, at=current):
        return _blocked("INVALID_STALE_OR_FUTURE_CANDIDATE")
    if candidate.weekly == "NEUTRO" or candidate.daily == "NEUTRO":
        return _blocked("NO_W1_D1_DIRECTION")
    if candidate.weekly != candidate.daily:
        return _blocked("W1_D1_CONFLICT")
    if candidate.grade_0_to_10 < MIN_DISPLAY_GRADE:
        return _blocked("GRADE_BELOW_RESEARCH_SELECTION_THRESHOLD")
    if (not isinstance(audit_claims, SelectiveAuditClaims)
            or any(type(getattr(audit_claims, name)) is not bool for name in (
                "macro_originals_and_pair_comparison_witnessed",
                "out_of_sample_labels_pit_witnessed", "geopol_macro_risk_reviewed",
                "releases_captured_before_predictions",
                "no_leakage_or_parameter_selection_on_holdout",
                "market_data_license_reviewed"))):
        return _blocked("INVALID_AUDIT_CLAIMS")
    if not all((
        audit_claims.macro_originals_and_pair_comparison_witnessed,
        audit_claims.out_of_sample_labels_pit_witnessed,
        audit_claims.geopol_macro_risk_reviewed,
        audit_claims.releases_captured_before_predictions,
        audit_claims.no_leakage_or_parameter_selection_on_holdout,
        audit_claims.market_data_license_reviewed,
    )):
        return _blocked("INDEPENDENT_MACRO_OOS_OR_RIGHTS_PROOF_MISSING")
    if type(unverified_event_actual_pending) is not bool or type(reversal_catalyst_claimed) is not bool:
        return _blocked("INVALID_EVENT_OR_REVERSAL_FLAGS")
    if unverified_event_actual_pending:
        return _blocked("EVENT_ACTUAL_NOT_VERIFIED")
    if isinstance(high_impact_events, (str, bytes)):
        return _blocked("INVALID_HIGH_IMPACT_EVENT_LIST")
    try:
        events = list(high_impact_events)
    except (TypeError, ValueError):
        return _blocked("INVALID_HIGH_IMPACT_EVENT_LIST")
    if len(events) > 100 or any(_utc(x) is None for x in events):
        return _blocked("INVALID_HIGH_IMPACT_EVENT_LIST")
    if any(abs(current - _utc(x)) <= HIGH_IMPACT_WINDOW for x in events):
        return _blocked("HIGH_IMPACT_NEWS_BLACKOUT")
    if any(_utc(candidate.macro_captured_at) < _utc(x) <= current for x in events):
        return _blocked("MACRO_CONTEXT_PREDATES_HIGH_IMPACT_RELEASE")
    if last_alert is not None:
        if (not isinstance(last_alert, LastAlert)
                or last_alert.asset != candidate.asset
                or last_alert.horizon != candidate.horizon
                or _utc(last_alert.emitted_at) is None
                or _utc(last_alert.emitted_at) > current
                or _utc(last_alert.emitted_at) > _utc(candidate.evaluated_at)
                or not isinstance(last_alert.direction, str)
                or last_alert.direction not in {"ALTA", "BAIXA"}):
            return _blocked("INVALID_LAST_ALERT")
        if last_alert.direction == candidate.daily:
            return _blocked("REPEATED_DIRECTION_ALREADY_PUBLISHED")
        if current - _utc(last_alert.emitted_at) < ALERT_COOLDOWN:
            return _blocked("REVERSAL_COOLDOWN")
        if not reversal_catalyst_claimed:
            return _blocked("REVERSAL_WITHOUT_MACRO_CATALYST")
    if not isinstance(previous_confirmations, (list, tuple)):
        return _blocked("INVALID_CONFIRMATION_SEQUENCE")
    required = 2 if last_alert is not None else 1
    if len(previous_confirmations) < required or len(previous_confirmations) > 12:
        return _blocked("INSUFFICIENT_DISTINCT_CONFIRMATIONS")
    recent = previous_confirmations[-required:]
    chain = [*recent, candidate]
    snapshots: set[str] = set()
    for prior in chain:
        if (not _valid_obs(prior, at=current)
                or prior.asset != candidate.asset
                or prior.horizon != candidate.horizon
                or prior.daily != candidate.daily
                or prior.weekly != candidate.weekly
                or prior.grade_0_to_10 < MIN_DISPLAY_GRADE
                or prior.snapshot_sha256 in snapshots):
            return _blocked("CONFLICTING_OR_REUSED_CONFIRMATION")
        snapshots.add(prior.snapshot_sha256)
    for before, after in zip(chain, chain[1:]):
        gap = _utc(after.evaluated_at) - _utc(before.evaluated_at)
        if not MIN_CONFIRM_GAP <= gap <= MAX_CONFIRM_GAP:
            return _blocked("CONFIRMATIONS_NOT_SEPARATED_IN_TIME")
    status, sample_size, hits, lower = _holdout_score(
        holdout_windows, _utc(candidate.evaluated_at),
        asset=candidate.asset, horizon=candidate.horizon,
        direction=candidate.daily)
    if status != "DOCUMENTARY_OOS_SCORE_ONLY":
        return _blocked(status, history_n=sample_size)
    result = _blocked("OOS_LOWER_BOUND_BELOW_RESEARCH_GOAL", history_n=sample_size)
    result.update({
        "grade": float(candidate.grade_0_to_10),
        "observed_holdout_hit_rate": round(hits / sample_size, 6),
        "observed_holdout_wilson95_lower": round(lower, 6),
        "oos_wilson_not_validated_for_dependent_market_outcomes": True,
        "oos_numbers_are_caller_claimed_not_authenticated": True,
    })
    if lower >= MIN_WILSON_LOWER:
        result.update({
            "state": "LAB_INTERNAL_RESEARCH_CANDIDATE_NOT_LIVE",
            "reason": "DESCRIPTIVE_SELECTION_ONLY_WITH_UNATTESTED_EVIDENCE",
            "research_candidate_direction": candidate.daily,
        })
    return result


__all__ = [
    "SCHEMA", "BiasObservation", "HoldoutWindow", "SelectiveAuditClaims",
    "LastAlert", "assess_selective_bias_lab",
]
