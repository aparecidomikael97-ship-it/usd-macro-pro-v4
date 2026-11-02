"""LAB-only point-in-time directional bias OOS evaluator.

Input is synthetic, caller-supplied, immutable-in-concept forecast and
future-settlement records. No API access, orders, real backtest certification,
model fitting or optimization. No simulated directional hit rate is an audited
historical result or probability of making money.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite, log
import re
from typing import Any, Mapping, Sequence

from atlasquant_fx_universe import OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_FX_BIAS_OOS_LAB_V1"
HORIZONS = ("D1", "W1", "MN1")
WINDOW_DAYS = {"D1": (0.7, 4), "W1": (4, 10), "MN1": (18, 42)}
SIDES = ("ALTA", "BAIXA", "NEUTRO", "AGUARDAR")
KEY_PATTERN = re.compile(r"^[A-Za-z0-9:_-]{3,100}$")
MAX_RECORDS = 10000


def _time(x: Any) -> datetime | None:
    if not isinstance(x, str) or len(x) > 60:
        return None
    try:
        d = datetime.fromisoformat(x.strip().replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return d.astimezone(timezone.utc) if d.tzinfo is not None else None


def _price(x: Any) -> float | None:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    value = float(x)
    return value if isfinite(value) and 0 < value <= 1e8 else None


def _rejected(reason: str) -> dict[str, Any]:
    return {"schema": SCHEMA, "state": "INVALID_OR_INCOMPLETE_FIXTURE",
            "reason": reason, "oos_proven": False, "historical_data_verified": False,
            "trade_authorized": False, "worker_enabled": False,
            "scheduler_enabled": False, "metrics": {}}


def _summarize(rows: Sequence[dict[str, Any]], *,
               sufficient: bool, deadband_bp: float) -> dict[str, Any]:
    total = len(rows)
    predicted = [r for r in rows if r["bias"] in ("ALTA", "BAIXA")]
    n = len(predicted)
    hits = sum(r["bias"] == r["realized_side"] for r in predicted)
    baseline_hits = sum(r["realized_side"] == "ALTA" for r in predicted)
    neutral = sum(r["bias"] == "NEUTRO" for r in rows)
    await_count = sum(r["bias"] == "AGUARDAR" for r in rows)
    flat_outcomes = sum(r["realized_side"] == "NEUTRO" for r in rows)
    return {
        "state": "SYNTHETIC_OOS_SAMPLE" if sufficient else "INSUFFICIENT_SYNTHETIC_SAMPLE",
        "samples": total, "directional_predictions": n,
        "neutral_forecasts": neutral, "await_forecasts": await_count,
        "realized_flat": flat_outcomes, "directional_hits": hits,
        "same_sample_always_up_hits": baseline_hits,
        "coverage_pct": round(100 * n / total, 2) if total else None,
        "directional_hit_rate_pct": round(100 * hits / n, 2) if sufficient and n else None,
        "always_up_baseline_hit_rate_pct": round(100 * baseline_hits / n, 2)
        if sufficient and n else None,
        "deadband_bp_lab": deadband_bp,
        "audited_real_accuracy": False,
        "probability_of_profit": None,
    }


def evaluate_bias_out_of_sample_lab(
    forecasts: Sequence[Mapping[str, Any]] | None,
    settlements: Sequence[Mapping[str, Any]] | None, *,
    split_at: datetime, at: datetime,
    min_train: int = 30, min_test: int = 30, min_test_days: int = 5,
    deadband_bp: float = 2.0,
) -> dict[str, Any]:
    """Evaluate precommitted directional forecasts only after future closes.

    The train/test split is fixed externally and strictly chronological.
    No train item whose future outcome crosses the split is included.
    Counts and hit rates are descriptive about provided synthetic fixtures;
    they say nothing about real-market forecast accuracy.
    """
    if any(not isinstance(t, datetime) or t.tzinfo is None for t in (split_at, at)):
        raise ValueError("Split/observation instants must include timezone")
    split = split_at.astimezone(timezone.utc)
    now = at.astimezone(timezone.utc)
    if split >= now:
        raise ValueError("Holdout split must precede evaluation instant")
    if any(isinstance(n, bool) or not isinstance(n, int) or not 3 <= n <= 100000
           for n in (min_train, min_test)) or (
            isinstance(min_test_days, bool) or not isinstance(min_test_days, int)
            or not 2 <= min_test_days <= 366):
        raise ValueError("Invalid evidence size thresholds")
    if (isinstance(deadband_bp, bool) or not isinstance(deadband_bp, (int, float)) or
            not isfinite(deadband_bp) or not 0 <= deadband_bp <= 100):
        raise ValueError("Invalid observation deadband")
    if not isinstance(forecasts, (list, tuple)) or not isinstance(settlements, (list, tuple)):
        return _rejected("Forecast/settlement arrays required.")
    if not forecasts or not settlements or len(forecasts) > MAX_RECORDS or len(settlements) > MAX_RECORDS:
        return _rejected("Empty/oversized fixture; no selective scoring.")

    f_by_id = {}
    evaluation_slots = set()
    methods = set()
    for item in forecasts:
        if not isinstance(item, Mapping):
            return _rejected("Invalid forecast record.")
        key = item.get("forecast_id")
        pair, horizon, bias = item.get("pair"), item.get("horizon"), item.get("bias")
        decision = _time(item.get("issued_at_utc"))
        evidence = _time(item.get("evidence_at_utc"))
        method = item.get("method_id")
        if (not isinstance(key, str) or not KEY_PATTERN.fullmatch(key) or
                key in f_by_id or pair not in OFFICIAL_PAIRS or horizon not in HORIZONS
                or bias not in SIDES or item.get("state") != "LAB_SYNTHETIC_BIAS"
                or not isinstance(method, str) or not 3 <= len(method) <= 100
                or decision is None or evidence is None
                or not evidence <= decision <= now):
            return _rejected("Invalid/duplicate/future forecast or missing point-in-time evidence.")
        # A directional accuracy sample is one pre-specified daily
        # evaluation per pair and horizon, not every intraday revision.
        # Same UTC date and market identity is one research observation,
        # even if IDs, local offsets or issuance times differ.
        slot = (pair, horizon, decision.date())
        if slot in evaluation_slots:
            return _rejected("DUPLICATE_PAIR_HORIZON_UTC_DAY_EVALUATION_SLOT")
        evaluation_slots.add(slot)
        f_by_id[key] = {"key": key, "pair": pair, "horizon": horizon,
                        "bias": bias, "decision": decision, "method": method}
        methods.add(method)
    if len(methods) != 1:
        return _rejected("Mixed forecast methods, not a fixed-method holdout.")

    s_by_id = {}
    for item in settlements:
        if not isinstance(item, Mapping):
            return _rejected("Invalid settlement record.")
        key = item.get("forecast_id")
        if not isinstance(key, str) or key not in f_by_id or key in s_by_id:
            return _rejected("Orphan or duplicate settlement.")
        f = f_by_id[key]
        entry = _time(item.get("entry_at_utc"))
        exit_at = _time(item.get("exit_at_utc"))
        initial = _price(item.get("entry_price"))
        final = _price(item.get("exit_price"))
        if (item.get("state") != "LAB_SYNTHETIC_SPOT_OUTCOME"
                or item.get("pair") != f["pair"]
                or entry is None or exit_at is None or initial is None or final is None
                or not f["decision"] < entry < exit_at <= now):
            return _rejected("Settlement availability, identity or quote is invalid.")
        if (entry - f["decision"]).total_seconds() > 4 * 86400:
            return _rejected("Outcome starts too long after forecast.")
        days = (exit_at - entry).total_seconds() / 86400
        lo, hi = WINDOW_DAYS[f["horizon"]]
        if not lo <= days <= hi:
            return _rejected("Outcome horizon inconsistent with forecast.")
        change_bp = (log(final) - log(initial)) * 10000
        if not isfinite(change_bp) or abs(change_bp) > 5000:
            return _rejected("Unbounded synthetic outcome return.")
        direction = ("ALTA" if change_bp > deadband_bp else
                     "BAIXA" if change_bp < -deadband_bp else "NEUTRO")
        s_by_id[key] = {"exit": exit_at, "change_bp": change_bp, "side": direction}
    if set(f_by_id) != set(s_by_id):
        return _rejected("Missing settlement; no silently dropped forecasts.")

    train, test = [], []
    purged = 0
    for key, f in f_by_id.items():
        o = s_by_id[key]
        record = {"pair": f["pair"], "horizon": f["horizon"], "bias": f["bias"],
                  "realized_side": o["side"], "issued_utc_day": f["decision"].date().isoformat()}
        if f["decision"] < split:
            if o["exit"] >= split:
                purged += 1  # prevent a label spanning the train/test boundary
            else:
                train.append(record)
        else:
            test.append(record)
    report = {}
    for horizon in HORIZONS:
        train_h = [row for row in train if row["horizon"] == horizon]
        test_h = [row for row in test if row["horizon"] == horizon]
        train_dir = [r for r in train_h if r["bias"] in ("ALTA", "BAIXA")]
        test_dir = [r for r in test_h if r["bias"] in ("ALTA", "BAIXA")]
        test_days = {r["issued_utc_day"] for r in test_dir}
        # In particular, 1 directional win cannot be reported as 100% accuracy.
        enough = (len(train_dir) >= min_train and len(test_dir) >= min_test
                  and len(test_days) >= min_test_days)
        metrics = _summarize(test_h, sufficient=enough, deadband_bp=float(deadband_bp))
        metrics.update({"train_samples": len(train_h),
                        "train_directional_samples": len(train_dir),
                        "directional_test_days": len(test_days),
                        "train_closed_before_split": True,
                        "threshold_min_train": min_train,
                        "threshold_min_test": min_test,
                        "threshold_min_test_days": min_test_days})
        report[horizon] = metrics
    pair_report = {}
    for pair in OFFICIAL_PAIRS:
        horizon_report = {}
        for h in HORIZONS:
            train_subset = [r for r in train if r["pair"] == pair and r["horizon"] == h
                            and r["bias"] in ("ALTA", "BAIXA")]
            test_subset = [r for r in test if r["pair"] == pair and r["horizon"] == h]
            dir_subset = [r for r in test_subset if r["bias"] in ("ALTA", "BAIXA")]
            days = {r["issued_utc_day"] for r in dir_subset}
            sufficient = (len(train_subset) >= min_train and
                          len(dir_subset) >= min_test and len(days) >= min_test_days)
            horizon_report[h] = _summarize(
                test_subset, sufficient=sufficient, deadband_bp=float(deadband_bp))
        pair_report[pair] = horizon_report
    return {
        "schema": SCHEMA, "state": "LAB_SYNTHETIC_HOLDOUT_ONLY",
        "split_at_utc": split.isoformat(), "evaluated_at_utc": now.isoformat(),
        "fixed_method_id": next(iter(methods)),
        "train_rows": len(train), "holdout_rows": len(test),
        "purged_boundary_rows": purged,
        "metrics": report, "pair_metrics": pair_report, "oos_proven": False, "historical_data_verified": False,
        "live_prediction_calibrated": False, "accuracy_probability": None,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False,
        "why_not": "Synthetic labels supplied by caller; immutable forecast provenance "
                   "and real point-in-time prices unverified. No trading inference.",
    }


__all__ = ["SCHEMA", "evaluate_bias_out_of_sample_lab"]
