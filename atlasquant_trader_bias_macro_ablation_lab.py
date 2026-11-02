"""Compare a precommitted synthetic strength bias with a macro risk VETO.

This is a paired LAB-only ablation. A macro veto may ONLY change a D1
directional hypothesis to AGUARDAR, never invent a new direction. It must
cite an already captured, released synthetic macro event affecting one of
the two currencies in the pair.

No actual macro theory, real sources, immutability, signal, model training,
API, return on capital, deployment, worker, background run, or accuracy proof.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import log
from typing import Any, Mapping, Sequence

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_bias_daily_freeze_lab import (
    freeze_daily_bias_observation_lab,
)
from atlasquant_trader_bias_forecast_bridge_lab import (
    FIXED_METHOD,
)
from atlasquant_trader_bias_oos_lab import evaluate_bias_out_of_sample_lab

SCHEMA = "ATLASQUANT_TRADER_MACRO_VETO_ABLATION_LAB_V1"
MACRO_METHOD = FIXED_METHOD + "_MACRO_VETO_LAB_V1"
MAX_SESSIONS = 100


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 60:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None


def _deny(reason: str) -> dict[str, Any]:
    return {"schema": SCHEMA, "state": "LAB_REJECTED_ABLATION",
            "reason": reason, "baseline_oos": None, "macro_gate_oos": None,
            "paired_holdout": {},
            "real_point_in_time_proven": False,
            "actual_macro_effect_proven": False,
            "accuracy_improvement_proven": False,
            "profitability_proven": False,
            "trade_authorized": False, "worker_enabled": False,
            "scheduler_enabled": False}


def compare_frozen_macro_veto_lab(
    observations: Sequence[Mapping[str, Any]] | None,
    settlements: Sequence[Mapping[str, Any]] | None, *,
    split_at: datetime, evaluated_at: datetime,
    min_train: int = 30, min_test: int = 30,
    min_test_days: int = 5, deadband_bp: float = 2.0,
) -> dict[str, Any]:
    """Evaluate a D1 macro veto versus strength-only on IDENTICAL outcomes.

    A caller-provided veto is a research hypothesis, not inferred from the
    sign or surprise of a raw release. "Better accuracy" with fewer coverage
    days is NOT proven predictive uplift: compare retained rows separately.
    """
    if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None:
        raise ValueError("Evaluation clock requires timezone")
    if not isinstance(split_at, datetime) or split_at.tzinfo is None:
        raise ValueError("Split clock requires timezone")
    if (not isinstance(observations, (list, tuple)) or not observations
            or len(observations) > MAX_SESSIONS
            or not isinstance(settlements, (list, tuple))):
        return _deny("Missing or oversized synthetic observation/outcome batch")
    now = evaluated_at.astimezone(timezone.utc)
    split = split_at.astimezone(timezone.utc)
    base, gated = [], []
    fingerprints = []
    session_days = set()
    baseline_ids = set()
    veto_count = 0
    veto_event_ids = set()
    previous = None
    for session in observations:
        if not isinstance(session, Mapping):
            return _deny("Malformed research session")
        batch, evidence, vetoes = (
            session.get("batch"), session.get("evidences"), session.get("macro_vetoes")
        )
        frozen = freeze_daily_bias_observation_lab(
            batch, evidence, checked_at=now,
        )
        if frozen["state"] != "LAB_FROZEN_SYNTHETIC_OBSERVATION":
            return _deny("Invalid or post-cutoff frozen observation")
        issue = _utc(frozen["issued_at_utc"])
        day = frozen["session_label_lab"]
        if day in session_days or (previous is not None and issue <= previous):
            return _deny("Duplicated or nonchronological fixed daily session")
        session_days.add(day)
        previous = issue
        fingerprints.append(frozen["frozen_observation_digest"])
        if not isinstance(vetoes, list) or len(vetoes) > len(OFFICIAL_PAIRS):
            return _deny("Invalid count of predeclared daily macro vetoes")
        event_index = {
            ev["evidence_id"]: ev for ev in evidence
            if ev.get("kind") == "MACRO_ACTUAL_RELEASED"
        }
        index = {row["forecast_id"]: row for row in batch["forecasts"]}
        selected = set()
        for veto in vetoes:
            allowed_keys = {"state", "forecast_id", "decided_at_utc",
                            "trade_authorized", "rationale", "evidence_ids"}
            if (not isinstance(veto, Mapping) or
                    set(veto) != allowed_keys or
                    veto.get("state") != "LAB_SYNTHETIC_MACRO_VETO"):
                return _deny("Invalid synthetic macro veto or future-data field")
            fid = veto.get("forecast_id")
            row = index.get(fid) if isinstance(fid, str) else None
            if (row is None or row["horizon"] != "D1" or
                    row["bias"] not in ("ALTA", "BAIXA") or fid in selected or
                    _utc(veto.get("decided_at_utc")) != issue or
                    veto.get("trade_authorized") is not False):
                return _deny("Veto not predeclared at exact D1 forecast cutoff")
            rationale = veto.get("rationale")
            ids = veto.get("evidence_ids")
            if (not isinstance(rationale, str) or not 5 <= len(rationale.strip()) <= 300
                    or not isinstance(ids, (list, tuple)) or not 1 <= len(ids) <= 5
                    or any(not isinstance(eid, str) for eid in ids)
                    or len(set(ids)) != len(ids)):
                return _deny("Veto needs a bounded rationale and unique evidence references")
            base_cc, quote_cc = split_pair(row["pair"])
            for eid in ids:
                event = event_index.get(eid)
                if event is None or event.get("currency") not in (base_cc, quote_cc):
                    return _deny("Veto cites unavailable or unrelated released macro evidence")
                released = _utc(event.get("released_at_utc"))
                captured = _utc(event.get("captured_at_utc"))
                if released is None or captured is None or released > captured or captured > issue:
                    return _deny("Veto cites after-cutoff macro information")
                veto_event_ids.add(eid)
            selected.add(fid)
        for forecast in batch["forecasts"]:
            fid = forecast["forecast_id"]
            if fid in baseline_ids:
                return _deny("Duplicate forecast across research days")
            baseline_ids.add(fid)
            base.append(dict(forecast))
            gated_row = dict(forecast)
            gated_row["method_id"] = MACRO_METHOD
            if fid in selected:
                gated_row["bias"] = "AGUARDAR"
                # Never pretend an actual release was known at the candle open.
                used = [
                    _utc(event_index[eid]["captured_at_utc"])
                    for veto in vetoes if veto["forecast_id"] == fid
                    for eid in veto["evidence_ids"]
                ]
                gated_row["evidence_at_utc"] = max(
                    [_utc(forecast["evidence_at_utc"])] + used
                ).isoformat()
            gated.append(gated_row)
        veto_count += len(selected)
    if len(set(fingerprints)) != len(fingerprints):
        return _deny("Repeated synthetic content cannot inflate research samples")
    if len(base) != len(settlements):
        return _deny("Every baseline prediction must have a matched future outcome")
    # Reuse the existing strict OOS evaluator twice, on exactly the same
    # pair/horizon/session ids, future prices, split, and hold periods.
    params = {"split_at": split, "at": now, "min_train": min_train,
              "min_test": min_test, "min_test_days": min_test_days,
              "deadband_bp": deadband_bp}
    baseline = evaluate_bias_out_of_sample_lab(base, settlements, **params)
    macro = evaluate_bias_out_of_sample_lab(gated, settlements, **params)
    if (baseline["state"] != "LAB_SYNTHETIC_HOLDOUT_ONLY" or
            macro["state"] != "LAB_SYNTHETIC_HOLDOUT_ONLY"):
        return _deny("Underlying paired OOS validation failed; no cherry-picking")
    outcomes = {item["forecast_id"]: item for item in settlements}
    # A veto can only abstain. For directional predictions retained by the
    # macro gate, baseline direction is identical, hence their matched
    # directional accuracy is necessarily equal. Show effect as coverage.
    report = {}
    for horizon in ("D1", "W1", "MN1"):
        by_pair = {}
        for pair in OFFICIAL_PAIRS:
            included = [(b, g) for b, g in zip(base, gated)
                        if b["pair"] == pair and b["horizon"] == horizon
                        and _utc(b["issued_at_utc"]) >= split]
            retained = [(b, g) for b, g in included
                        if g["bias"] in ("ALTA", "BAIXA")]
            baseline_directed = sum(b["bias"] in ("ALTA", "BAIXA") for b, _ in included)
            correct = 0
            for b, g in retained:
                o = outcomes[b["forecast_id"]]
                move = log(o["exit_price"] / o["entry_price"]) * 10000
                side = ("ALTA" if move > deadband_bp else
                        "BAIXA" if move < -deadband_bp else "NEUTRO")
                correct += g["bias"] == side
            days = { _utc(b["issued_at_utc"]).date() for b, _ in retained }
            # Count only training labels that were FULLY closed before the split,
            # matching the OOS evaluator's purge rule at that same boundary.
            trained = sum(
                1 for b in base if b["pair"] == pair and b["horizon"] == horizon
                and b["bias"] in ("ALTA", "BAIXA")
                and _utc(b["issued_at_utc"]) < split
                and _utc(outcomes[b["forecast_id"]]["exit_at_utc"]) < split
            )
            enough = (trained >= min_train and len(retained) >= min_test
                      and len(days) >= min_test_days)
            by_pair[pair] = {
                "test_rows": len(included),
                "baseline_directional": baseline_directed,
                "macro_gate_directional": len(retained),
                "macro_vetoed_test_rows": sum(
                    b["bias"] in ("ALTA", "BAIXA") and g["bias"] == "AGUARDAR"
                    for b, g in included
                ),
                "matched_retained_hits": correct,
                "matched_retained_hit_rate_pct": (
                    round(100 * correct / len(retained), 2)
                    if enough and retained else None
                ),
                "baseline_on_exact_retained_sample_pct": (
                    round(100 * correct / len(retained), 2)
                    if enough and retained else None
                ),
                "test_coverage_change_pp": (
                    round(100 * (len(retained) - baseline_directed) / len(included), 2)
                    if included else None
                ),
                "macro_direction_flips": 0,
                "statistical_uplift_proven": False,
            }
        report[horizon] = by_pair
    return {
        "schema": SCHEMA, "state": "LAB_SYNTHETIC_PAIRED_ABLATION",
        "observed_sessions": len(observations),
        "baseline_predictions": len(base),
        "macro_vetoed_all_periods": veto_count,
        "macro_released_evidence_ids_used": sorted(veto_event_ids),
        "baseline_oos": baseline,
        "macro_gate_oos": macro,
        "paired_holdout": report,
        "comparability": "IDENTICAL_FUTURE_OUTCOMES_SPLIT_AND_HORIZONS",
        "no_direction_flips": True,
        "macro_veto_tradeoff": "Coverage/abstention only. The matched retained "
                                "directions cannot differ from baseline.",
        "real_point_in_time_proven": False,
        "actual_macro_effect_proven": False,
        "accuracy_improvement_proven": False,
        "profitability_proven": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False,
        "why_not": "Only synthetic caller-controlled freezes, macro vetoes and "
                   "future settlements. No authenticated historical market proof.",
    }


__all__ = ["SCHEMA", "MACRO_METHOD", "compare_frozen_macro_veto_lab"]
