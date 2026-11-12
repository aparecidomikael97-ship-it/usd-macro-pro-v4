"""Paired, selective directional-regime benchmark -- OFFLINE LAB ONLY.

This measures whether an additional regime veto *selects a better subset* of
already-eligible D1/W1 FX hypotheses. The complete fixed manifest, original
market vintages and externally locked selection rules are NOT attested here;
caller-provided timestamps, prices and hash claims are not trusted originals.
Nothing here can authorize a live bias, a probability, or trades.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
import re

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_w1_ny17_dst_guard_lab import w1_ny17_dst_crossing_lab

SCHEMA = "ATLASQUANT_TRADER_REGIME_INCREMENT_PAIRED_OOS_LAB_V1"
BAR_DURATION = {"D1": timedelta(days=1), "W1": timedelta(days=7)}
ALLOWED_DIRECTIONS = frozenset(("ALTA", "BAIXA"))
MIN_BASELINE = 100
MIN_FILTERED = 30
MIN_BASELINE_PER_WINDOW = 20
MIN_FILTERED_PER_WINDOW = 5
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
IDENTIFIER = re.compile(r"[A-Z0-9][A-Z0-9_-]{3,79}\Z")
MAX_CASES = 2000


@dataclass(frozen=True)
class DirectionalCase:
    opportunity_id: str
    asset: str
    horizon: str
    candidate_direction: str
    decided_at: datetime
    regime_observed_at: datetime
    target_open_at: datetime
    target_close_at: datetime
    actual_observed_at: datetime
    start_price: str
    end_price: str
    baseline_eligible: bool
    regime_veto: bool
    decision_sha256_claim: str
    regime_source_sha256_claim: str
    price_source_sha256_claim: str


@dataclass(frozen=True)
class PredeclaredWindow:
    start_at: datetime
    end_at: datetime


def _utc(v: Any) -> datetime | None:
    if not isinstance(v, datetime) or v.tzinfo is None or v.utcoffset() is None:
        return None
    return v.astimezone(timezone.utc)


def _price(v: Any) -> Decimal | None:
    if not isinstance(v, str) or len(v) > 40 or len(v) == 0:
        return None
    try:
        d = Decimal(v)
    except (InvalidOperation, ValueError):
        return None
    return d if d.is_finite() and 0 < d <= Decimal("1000000000") else None


def _result(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_REGIME_BENCHMARK_BLOCKED", "reason": reason,
        "asset": None, "horizon": None,
        "manifest_total": 0, "count_observed": 0, "baseline_issued": 0,
        "filtered_issued": 0, "filtered_rejected": 0,
        "baseline_abstained": 0, "baseline_correct": 0,
        "filtered_correct": 0, "rejected_correct": 0,
        "baseline_flat": 0, "filtered_flat": 0,
        "baseline_hit_rate_documentary": None,
        "filtered_hit_rate_documentary": None,
        "rejected_hit_rate_documentary": None,
        "filtered_coverage_vs_baseline_documentary": None,
        "hit_rate_delta_percentage_points_documentary": None,
        "windows": [],
        "complete_declared_manifest_checked": False,
        "manifest_externally_precommitted": False,
        "real_market_data_loaded": False,
        "point_in_time_price_vintage_authenticated": False,
        "direction_precommitted_externally": False,
        "regime_rule_precommitted_externally": False,
        "selection_bias_ruled_out": False,
        "market_outcome_independence_verified": False,
        "multiple_testing_adjusted": False,
        "broker_calendar_verified": False,
        "costs_spread_slippage_included": False,
        "incremental_accuracy_validated": False,
        "validated_directional_accuracy": None,
        "calibrated_direction_probability": None,
        "fx_bias": None, "index_bias": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0,
        "new_cost_brl": 0, "research_only": True,
    }


def _pct(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(100 * numerator / denominator, 4)


def evaluate_regime_increment_lab(
    cases: Any, *, expected_opportunity_ids: Any,
    predeclared_windows: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Retrospective paired accounting, NEVER a causal or validated estimate.

    Comparison is among baseline-issued decisions only. Filtered results are a
    subset of the same records, not different entry/exit rules. Flat candles
    count as misses for both ALTA and BAIXA. There is no return/profit model.
    """
    out = _result("INVALID_INPUT_SCHEMA_OR_CLOCK")
    now = _utc(as_of_utc)
    if (now is None or not isinstance(cases, (list, tuple))
            or not isinstance(expected_opportunity_ids, (list, tuple))
            or not isinstance(predeclared_windows, (list, tuple))
            or len(cases) > MAX_CASES or len(expected_opportunity_ids) > MAX_CASES
            or not 3 <= len(predeclared_windows) <= 12):
        return out

    # Windows are fixed *before* scoring and must be strictly non-overlapping.
    windows = []
    for w in predeclared_windows:
        if not isinstance(w, PredeclaredWindow):
            return out
        start, end = _utc(w.start_at), _utc(w.end_at)
        if (start is None or end is None or not start < end <= now
                or windows and start < windows[-1][1]):
            out["reason"] = "INVALID_OR_OVERLAPPING_OOS_WINDOWS"
            return out
        windows.append((start, end))

    ids = list(expected_opportunity_ids)
    if (not ids or any(not isinstance(x, str) or IDENTIFIER.fullmatch(x) is None for x in ids)
            or len(set(ids)) != len(ids)):
        out["reason"] = "INVALID_OR_DUPLICATED_OPPORTUNITY_MANIFEST"
        return out
    out["manifest_total"] = len(ids)
    if len(cases) != len(ids) or any(not isinstance(c, DirectionalCase) for c in cases):
        out["reason"] = "MANIFEST_DOES_NOT_MATCH_ALL_CASES_NO_SILENT_OMISSION"
        return out
    if len({c.opportunity_id for c in cases}) != len(cases):
        out["reason"] = "DUPLICATED_OPPORTUNITY_ID"
        return out
    if {c.opportunity_id for c in cases} != set(ids):
        out["reason"] = "MANIFEST_DOES_NOT_MATCH_ALL_CASES_NO_SILENT_OMISSION"
        return out

    asset, horizon = cases[0].asset, cases[0].horizon
    if any(c.asset != asset or c.horizon != horizon for c in cases):
        out["reason"] = "MIXED_PAIR_OR_HORIZON_CANNOT_POOL_RESULTS"
        return out
    if asset not in OFFICIAL_PAIRS or horizon not in BAR_DURATION:
        out["reason"] = "OUTSIDE_28_FX_OR_NON_D1_W1"
        return out
    out["asset"] = asset
    out["horizon"] = horizon
    # Same asset + horizon + target candle may not be rebranded as two trials.
    targets = set()
    assigned: list[list[DirectionalCase]] = [[] for _ in windows]
    for c in cases:
        decided, regime, start, end, actual = (
            _utc(c.decided_at), _utc(c.regime_observed_at),
            _utc(c.target_open_at), _utc(c.target_close_at),
            _utc(c.actual_observed_at))
        if (c.asset != asset or c.horizon != horizon
                or c.candidate_direction not in ALLOWED_DIRECTIONS
                or type(c.baseline_eligible) is not bool
                or type(c.regime_veto) is not bool
                or any(v is None for v in (decided, regime, start, end, actual))):
            out["reason"] = "INVALID_PAIR_HORIZON_SIDE_OR_CLOCK"
            return out
        if (not regime <= decided < start < end <= actual <= now
                or end - start != BAR_DURATION[horizon]):
            out["reason"] = "POST_EVENT_OR_LOOKAHEAD_OR_INVALID_TARGET_WINDOW"
            return out
        if horizon == "W1":
            dst_risk = w1_ny17_dst_crossing_lab(start, end)
            if dst_risk is not False:
                out["reason"] = ("W1_NY17_DST_CLOSE_REQUIRES_BROKER_VERIFICATION"
                                 if dst_risk else "W1_NY_ZONEINFO_MISSING_OR_INVALID")
                return out
        if (any(not isinstance(s, str) or HEX64.fullmatch(s) is None for s in (
                c.decision_sha256_claim, c.regime_source_sha256_claim,
                c.price_source_sha256_claim))):
            out["reason"] = "INVALID_SOURCE_HASH_CLAIMS"
            return out
        if _price(c.start_price) is None or _price(c.end_price) is None:
            out["reason"] = "INVALID_PRICE_OR_NONFINITE_OUTCOME"
            return out
        key = (c.asset, c.horizon, start)
        if key in targets:
            out["reason"] = "DUPLICATE_TARGET_CANDLE_UNDER_DIFFERENT_ID"
            return out
        targets.add(key)
        matches = [i for i, (w_start, w_end) in enumerate(windows)
                   if w_start <= decided < w_end]
        if len(matches) != 1:
            out["reason"] = "OPPORTUNITY_OUTSIDE_PREDECLARED_WINDOW"
            return out
        assigned[matches[0]].append(c)

    out["complete_declared_manifest_checked"] = True
    out["count_observed"] = len(cases)
    rows = []
    baseline_n = filtered_n = rejected_n = baseline_hits = filtered_hits = rejected_hits = 0
    baseline_flat = filtered_flat = baseline_abstained = 0
    for index, group in enumerate(assigned):
        n_base = n_keep = n_drop = hits_base = hits_keep = hits_drop = 0
        for c in group:
            if not c.baseline_eligible:
                baseline_abstained += 1
                continue
            outcome = "ALTA" if _price(c.end_price) > _price(c.start_price) else (
                "BAIXA" if _price(c.end_price) < _price(c.start_price) else "SEM_VARIACAO")
            correct = c.candidate_direction == outcome
            if outcome == "SEM_VARIACAO":
                baseline_flat += 1
            n_base += 1
            hits_base += int(correct)
            if c.regime_veto:
                n_drop += 1
                hits_drop += int(correct)
            else:
                n_keep += 1
                hits_keep += int(correct)
                if outcome == "SEM_VARIACAO":
                    filtered_flat += 1
        rows.append({
            "window_index": index + 1, "start_utc": windows[index][0].isoformat(),
            "end_utc": windows[index][1].isoformat(), "registered": len(group),
            "baseline_issued": n_base, "baseline_correct": hits_base,
            "regime_issued": n_keep, "regime_correct": hits_keep,
            "regime_rejected": n_drop, "rejected_would_have_been_correct": hits_drop,
            "baseline_hit_rate_documentary": _pct(hits_base, n_base),
            "regime_hit_rate_documentary": _pct(hits_keep, n_keep),
        })
        baseline_n += n_base
        filtered_n += n_keep
        rejected_n += n_drop
        baseline_hits += hits_base
        filtered_hits += hits_keep
        rejected_hits += hits_drop
    out.update({
        "windows": rows, "baseline_issued": baseline_n,
        "filtered_issued": filtered_n, "filtered_rejected": rejected_n,
        "baseline_abstained": baseline_abstained,
        "baseline_correct": baseline_hits, "filtered_correct": filtered_hits,
        "rejected_correct": rejected_hits,
        "baseline_flat": baseline_flat, "filtered_flat": filtered_flat,
        "filtered_coverage_vs_baseline_documentary": _pct(filtered_n, baseline_n),
    })
    if (baseline_n < MIN_BASELINE or filtered_n < MIN_FILTERED
            or any(r["baseline_issued"] < MIN_BASELINE_PER_WINDOW
                   or r["regime_issued"] < MIN_FILTERED_PER_WINDOW for r in rows)):
        out["state"] = "LAB_SAMPLE_INSUFFICIENT_FOR_DESCRIPTIVE_COMPARISON"
        out["reason"] = "FIXED_WINDOW_OR_MATCHED_SAMPLE_TOO_SMALL"
        # Suppress rates (including per-window) on thin cohorts; retain counts.
        for row in rows:
            row["baseline_hit_rate_documentary"] = None
            row["regime_hit_rate_documentary"] = None
        return out
    base_rate = _pct(baseline_hits, baseline_n)
    filtered_rate = _pct(filtered_hits, filtered_n)
    out.update({
        "state": "LAB_PAIRED_COMPARISON_DESCRIPTIVE_UNATTESTED_NO_GO",
        "reason": "MATCHED_SELECTION_DESCRIPTION_NOT_PIT_OR_CAUSAL_VALIDATION",
        "baseline_hit_rate_documentary": base_rate,
        "filtered_hit_rate_documentary": filtered_rate,
        "rejected_hit_rate_documentary": _pct(rejected_hits, rejected_n),
        "hit_rate_delta_percentage_points_documentary": round(filtered_rate - base_rate, 4),
    })
    return out


__all__ = ["SCHEMA", "DirectionalCase", "PredeclaredWindow", "evaluate_regime_increment_lab"]
