"""Controlled learning contracts for AtlasQuant/AION.

This module turns observations into auditable learning records without allowing
silent self-modification. It supports:
- prediction/decision journal entries;
- explicit outcome settlement;
- error-cause tagging without invented causality;
- confidence calibration from settled observations;
- research/backtest evidence references;
- champion/challenger experiments with out-of-sample + shadow gates;
- human-review-only promotion candidacy.

Nothing here changes live market scores, production weights, broker execution,
feature flags or deployment state.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

SCHEMA = "ATLASQUANT_AION_CONTROLLED_LEARNING_V1"

MAX_EPISODES = 2000
MAX_EXPERIMENTS = 400
MAX_RESEARCH_REFS = 2000

FORECAST_TYPES = ("DIRECTIONAL", "CATEGORICAL", "NUMERIC", "SCENARIO")
EPISODE_STATES = ("OPEN", "SETTLED")
CAUSE_TAGS = (
    "DATA_QUALITY",
    "NEWS_SHOCK",
    "REVISION",
    "REGIME_SHIFT",
    "TIMING",
    "CORRELATION_BREAK",
    "MODEL_WEIGHT",
    "INSUFFICIENT_EVIDENCE",
    "EXECUTION_ASSUMPTION",
    "UNKNOWN",
)
RESEARCH_KINDS = (
    "BACKTEST",
    "PAPER",
    "FORWARD",
    "SHADOW",
    "OUT_OF_SAMPLE",
    "CALIBRATION",
    "NEWS_REPLAY",
    "MARKET_REPLAY",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any, limit: int = 800) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _norm_label(value: Any) -> str:
    return _clean(value, 180).strip().upper()


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _confidence(value: Any) -> float:
    number = _finite(value)
    if number is None:
        return 0.0
    return round(max(0.0, min(100.0, number)), 2)


def _list_text(value: Any, *, limit: int = 30, item_limit: int = 240) -> list[str]:
    rows = value if isinstance(value, (list, tuple)) else []
    out: list[str] = []
    for item in rows:
        text = _clean(item, item_limit)
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _stable_digest(payload: Any, *, length: int = 16) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:length]


def _episode_id(subject: str, created_at: str, model_version: str) -> str:
    return "LEARN-" + _stable_digest(
        {"subject": subject, "created_at": created_at, "model_version": model_version},
        length=14,
    ).upper()


def _experiment_id(
    champion_version: str,
    challenger_version: str,
    created_at: str,
) -> str:
    return "EXP-" + _stable_digest(
        {
            "champion": champion_version,
            "challenger": challenger_version,
            "created_at": created_at,
        },
        length=14,
    ).upper()


def _research_id(kind: str, ref_id: str) -> str:
    return "REF-" + _stable_digest({"kind": kind, "ref": ref_id}, length=14).upper()


def new_learning_episode(
    subject: Any,
    *,
    forecast_type: Any = "CATEGORICAL",
    prediction: Any = "",
    confidence_pct: Any = 0,
    model_version: Any = "",
    domain: Any = "trading",
    evidence_refs: Sequence[Any] | None = None,
    context_note: Any = "",
    numeric_prediction: Any = None,
    numeric_tolerance: Any = None,
    created_at: str | None = None,
    source: Any = "AION",
) -> dict[str, Any]:
    subject_text = _clean(subject, 240)
    if not subject_text:
        raise ValueError("learning subject required")
    ftype = _norm_label(forecast_type)
    if ftype not in FORECAST_TYPES:
        raise ValueError("invalid forecast type")
    created = str(created_at or _now())
    version = _clean(model_version, 120) or "UNVERSIONED"
    numeric_value = _finite(numeric_prediction)
    tolerance = _finite(numeric_tolerance)
    if tolerance is not None and tolerance < 0:
        raise ValueError("numeric tolerance must be non-negative")

    return {
        "schema": SCHEMA,
        "episode_id": _episode_id(subject_text, created, version),
        "state": "OPEN",
        "domain": _clean(domain, 80).lower() or "trading",
        "subject": subject_text,
        "forecast_type": ftype,
        "prediction": _clean(prediction, 500),
        "numeric_prediction": numeric_value,
        "numeric_tolerance": tolerance,
        "forecast_confidence_pct": _confidence(confidence_pct),
        "confidence_meaning": "FORECAST_SELF_CONFIDENCE_NOT_PROFIT_PROBABILITY",
        "model_version": version,
        "evidence_refs": _list_text(evidence_refs, limit=40),
        "context_note": _clean(context_note, 1200),
        "source": _clean(source, 120) or "AION",
        "created_at": created,
        "settled_at": "",
        "actual_outcome": "",
        "actual_numeric": None,
        "evaluation": "UNRESOLVED",
        "correct": None,
        "absolute_error": None,
        "signed_error": None,
        "error_cause": "UNKNOWN",
        "error_cause_truth": "UNKNOWN",
        "outcome_note": "",
        "automatic_weight_change": False,
        "automatic_rule_change": False,
        "automatic_promotion": False,
        "real_orders_enabled": False,
    }


def normalize_learning_episode(raw: Mapping[str, Any]) -> dict[str, Any]:
    item = dict(raw or {})
    subject = _clean(item.get("subject"), 240)
    if not subject:
        raise ValueError("learning subject required")
    created = _clean(item.get("created_at"), 80) or _now()
    ftype = _norm_label(item.get("forecast_type"))
    if ftype not in FORECAST_TYPES:
        ftype = "CATEGORICAL"
    state = _norm_label(item.get("state"))
    if state not in EPISODE_STATES:
        state = "OPEN"
    cause = _norm_label(item.get("error_cause"))
    if cause not in CAUSE_TAGS:
        cause = "UNKNOWN"
    correct_raw = item.get("correct")
    correct = correct_raw if isinstance(correct_raw, bool) else None

    return {
        "schema": SCHEMA,
        "episode_id": _clean(item.get("episode_id"), 80)
        or _episode_id(subject, created, _clean(item.get("model_version"), 120)),
        "state": state,
        "domain": _clean(item.get("domain"), 80).lower() or "trading",
        "subject": subject,
        "forecast_type": ftype,
        "prediction": _clean(item.get("prediction"), 500),
        "numeric_prediction": _finite(item.get("numeric_prediction")),
        "numeric_tolerance": _finite(item.get("numeric_tolerance")),
        "forecast_confidence_pct": _confidence(item.get("forecast_confidence_pct")),
        "confidence_meaning": "FORECAST_SELF_CONFIDENCE_NOT_PROFIT_PROBABILITY",
        "model_version": _clean(item.get("model_version"), 120) or "UNVERSIONED",
        "evidence_refs": _list_text(item.get("evidence_refs"), limit=40),
        "context_note": _clean(item.get("context_note"), 1200),
        "source": _clean(item.get("source"), 120) or "AION",
        "created_at": created,
        "settled_at": _clean(item.get("settled_at"), 80),
        "actual_outcome": _clean(item.get("actual_outcome"), 500),
        "actual_numeric": _finite(item.get("actual_numeric")),
        "evaluation": _clean(item.get("evaluation"), 80).upper() or "UNRESOLVED",
        "correct": correct,
        "absolute_error": _finite(item.get("absolute_error")),
        "signed_error": _finite(item.get("signed_error")),
        "error_cause": cause,
        "error_cause_truth": (
            "CONFIRMED"
            if cause != "UNKNOWN" and _norm_label(item.get("error_cause_truth")) == "CONFIRMED"
            else "UNKNOWN"
        ),
        "outcome_note": _clean(item.get("outcome_note"), 1200),
        "automatic_weight_change": False,
        "automatic_rule_change": False,
        "automatic_promotion": False,
        "real_orders_enabled": False,
    }


def normalize_learning_episodes(
    rows: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in list(rows or [])[-MAX_EPISODES * 2 :]:
        if not isinstance(raw, Mapping):
            continue
        try:
            item = normalize_learning_episode(raw)
        except Exception:
            continue
        eid = item["episode_id"]
        if eid in seen:
            continue
        seen.add(eid)
        out.append(item)
    return out[-MAX_EPISODES:]


def settle_learning_episode(
    episode: Mapping[str, Any],
    *,
    actual_outcome: Any = "",
    actual_numeric: Any = None,
    error_cause: Any = "UNKNOWN",
    error_cause_confirmed: bool = False,
    outcome_note: Any = "",
    settled_at: str | None = None,
) -> dict[str, Any]:
    item = normalize_learning_episode(episode)
    actual_text = _clean(actual_outcome, 500)
    numeric_actual = _finite(actual_numeric)
    correct: bool | None = None
    evaluation = "RECORDED"
    abs_error = None
    signed_error = None

    if item["forecast_type"] == "NUMERIC":
        predicted = item.get("numeric_prediction")
        if predicted is not None and numeric_actual is not None:
            signed_error = round(float(numeric_actual) - float(predicted), 8)
            abs_error = round(abs(signed_error), 8)
            tolerance = item.get("numeric_tolerance")
            if tolerance is not None:
                correct = bool(abs_error <= float(tolerance))
                evaluation = "MATCH" if correct else "MISMATCH"
            else:
                evaluation = "NUMERIC_ERROR_RECORDED"
        else:
            evaluation = "INSUFFICIENT_OUTCOME"
    else:
        predicted_label = _norm_label(item.get("prediction"))
        actual_label = _norm_label(actual_text)
        if predicted_label and actual_label:
            correct = predicted_label == actual_label
            evaluation = "MATCH" if correct else "MISMATCH"
        else:
            evaluation = "INSUFFICIENT_OUTCOME"

    cause = _norm_label(error_cause)
    if cause not in CAUSE_TAGS:
        cause = "UNKNOWN"
    cause_truth = "CONFIRMED" if cause != "UNKNOWN" and bool(error_cause_confirmed) else "UNKNOWN"

    item.update({
        "state": "SETTLED",
        "settled_at": str(settled_at or _now()),
        "actual_outcome": actual_text,
        "actual_numeric": numeric_actual,
        "evaluation": evaluation,
        "correct": correct,
        "absolute_error": abs_error,
        "signed_error": signed_error,
        "error_cause": cause if not correct else "UNKNOWN",
        "error_cause_truth": cause_truth if not correct else "UNKNOWN",
        "outcome_note": _clean(outcome_note, 1200),
    })
    return normalize_learning_episode(item)


def upsert_learning_episode(
    rows: Sequence[Mapping[str, Any]] | None,
    episode: Mapping[str, Any],
) -> list[dict[str, Any]]:
    current = normalize_learning_episodes(rows)
    item = normalize_learning_episode(episode)
    replaced = False
    out: list[dict[str, Any]] = []
    for row in current:
        if row["episode_id"] == item["episode_id"]:
            out.append(item)
            replaced = True
        else:
            out.append(row)
    if not replaced:
        out.append(item)
    return out[-MAX_EPISODES:]


def confidence_calibration(
    episodes: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    settled = [
        row for row in normalize_learning_episodes(episodes)
        if row["state"] == "SETTLED" and isinstance(row.get("correct"), bool)
    ]
    bins = [
        (0.0, 20.0, "0–20"),
        (20.0, 40.0, "21–40"),
        (40.0, 60.0, "41–60"),
        (60.0, 80.0, "61–80"),
        (80.0, 100.00001, "81–100"),
    ]
    rows: list[dict[str, Any]] = []
    weighted_gap = 0.0
    total = len(settled)
    for lo, hi, label in bins:
        group = [
            item for item in settled
            if lo <= float(item["forecast_confidence_pct"]) < hi
        ]
        n = len(group)
        avg_conf = (
            sum(float(x["forecast_confidence_pct"]) for x in group) / n
            if n else None
        )
        accuracy = (
            100.0 * sum(1 for x in group if x["correct"]) / n
            if n else None
        )
        gap = (
            abs(float(avg_conf) - float(accuracy))
            if avg_conf is not None and accuracy is not None
            else None
        )
        if gap is not None:
            weighted_gap += gap * n
        rows.append({
            "band": label,
            "samples": n,
            "average_confidence_pct": None if avg_conf is None else round(avg_conf, 2),
            "observed_accuracy_pct": None if accuracy is None else round(accuracy, 2),
            "absolute_calibration_gap_pct": None if gap is None else round(gap, 2),
        })

    mean_gap = None if total == 0 else round(weighted_gap / total, 2)
    if total < 30:
        state = "INSUFFICIENT"
    elif mean_gap is not None and mean_gap <= 10:
        state = "CALIBRATED_REVIEW"
    else:
        state = "RECALIBRATION_REVIEW"

    return {
        "schema": SCHEMA,
        "state": state,
        "samples": total,
        "mean_absolute_calibration_gap_pct": mean_gap,
        "bands": rows,
        "confidence_is_profit_probability": False,
        "auto_recalibration_allowed": False,
        "automatic_weight_change": False,
        "executes_action": False,
    }


def error_pattern_summary(
    episodes: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    rows = normalize_learning_episodes(episodes)
    settled = [x for x in rows if x["state"] == "SETTLED"]
    errors = [x for x in settled if x.get("correct") is False]
    confirmed_causes = Counter(
        x["error_cause"]
        for x in errors
        if x.get("error_cause_truth") == "CONFIRMED"
        and x.get("error_cause") != "UNKNOWN"
    )
    unknown_cause = sum(
        1 for x in errors
        if x.get("error_cause_truth") != "CONFIRMED"
    )
    return {
        "schema": SCHEMA,
        "settled": len(settled),
        "errors": len(errors),
        "confirmed_cause_counts": dict(confirmed_causes.most_common()),
        "errors_without_confirmed_cause": unknown_cause,
        "causality_inferred_automatically": False,
        "executes_action": False,
    }


def new_research_reference(
    kind: Any,
    ref_id: Any,
    *,
    strategy: Any = "",
    summary: Any = "",
    evidence_refs: Sequence[Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    kind_norm = _norm_label(kind)
    if kind_norm not in RESEARCH_KINDS:
        raise ValueError("invalid research kind")
    ref = _clean(ref_id, 240)
    if not ref:
        raise ValueError("research ref id required")
    created = str(created_at or _now())
    return {
        "schema": SCHEMA,
        "research_id": _research_id(kind_norm, ref),
        "kind": kind_norm,
        "ref_id": ref,
        "strategy": _clean(strategy, 180),
        "summary": _clean(summary, 1000),
        "evidence_refs": _list_text(evidence_refs, limit=40),
        "created_at": created,
        "research_only": True,
        "no_live_gate_effect": True,
        "automatic_promotion": False,
    }


def normalize_research_references(
    rows: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in list(rows or [])[-MAX_RESEARCH_REFS * 2 :]:
        if not isinstance(raw, Mapping):
            continue
        try:
            item = new_research_reference(
                raw.get("kind"),
                raw.get("ref_id"),
                strategy=raw.get("strategy"),
                summary=raw.get("summary"),
                evidence_refs=raw.get("evidence_refs"),
                created_at=_clean(raw.get("created_at"), 80) or None,
            )
        except Exception:
            continue
        rid = item["research_id"]
        if rid in seen:
            continue
        seen.add(rid)
        out.append(item)
    return out[-MAX_RESEARCH_REFS:]


def new_learning_experiment(
    champion_version: Any,
    challenger_version: Any,
    *,
    rationale: Any,
    evidence_refs: Sequence[Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    champion = _clean(champion_version, 120)
    challenger = _clean(challenger_version, 120)
    why = _clean(rationale, 1200)
    if not champion or not challenger or champion == challenger:
        raise ValueError("distinct champion and challenger required")
    if not why:
        raise ValueError("experiment rationale required")
    created = str(created_at or _now())
    return {
        "schema": SCHEMA,
        "experiment_id": _experiment_id(champion, challenger, created),
        "state": "PLANNED",
        "champion_version": champion,
        "challenger_version": challenger,
        "rationale": why,
        "evidence_refs": _list_text(evidence_refs, limit=60),
        "created_at": created,
        "evaluated_at": "",
        "evaluation": {},
        "hypothesis_truth": "HYPOTHESIS",
        "automatic_promotion": False,
        "production_change_allowed": False,
        "real_orders_enabled": False,
    }


def normalize_learning_experiment(raw: Mapping[str, Any]) -> dict[str, Any]:
    item = dict(raw or {})
    base = new_learning_experiment(
        item.get("champion_version"),
        item.get("challenger_version"),
        rationale=item.get("rationale"),
        evidence_refs=item.get("evidence_refs"),
        created_at=_clean(item.get("created_at"), 80) or None,
    )
    base["experiment_id"] = _clean(item.get("experiment_id"), 80) or base["experiment_id"]
    state = _norm_label(item.get("state"))
    base["state"] = state if state in {
        "PLANNED", "RUNNING", "NEED_MORE_EVIDENCE", "REJECTED_FOR_NOW", "HUMAN_REVIEW_CANDIDATE"
    } else "PLANNED"
    base["evaluated_at"] = _clean(item.get("evaluated_at"), 80)
    base["evaluation"] = (
        deepcopy(dict(item.get("evaluation")))
        if isinstance(item.get("evaluation"), Mapping)
        else {}
    )
    return base


def normalize_learning_experiments(
    rows: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in list(rows or [])[-MAX_EXPERIMENTS * 2 :]:
        if not isinstance(raw, Mapping):
            continue
        try:
            item = normalize_learning_experiment(raw)
        except Exception:
            continue
        eid = item["experiment_id"]
        if eid in seen:
            continue
        seen.add(eid)
        out.append(item)
    return out[-MAX_EXPERIMENTS:]


def _metric(metrics: Mapping[str, Any], key: str) -> float | None:
    return _finite(metrics.get(key)) if isinstance(metrics, Mapping) else None


def evaluate_learning_experiment(
    experiment: Mapping[str, Any],
    *,
    champion_metrics: Mapping[str, Any] | None,
    challenger_metrics: Mapping[str, Any] | None,
    shadow_summary: Mapping[str, Any] | None,
    min_oos_samples: int = 100,
    min_expectancy_improvement_r: float = 0.02,
) -> dict[str, Any]:
    item = normalize_learning_experiment(experiment)
    champion = dict(champion_metrics or {})
    challenger = dict(challenger_metrics or {})
    shadow = dict(shadow_summary or {})

    c_samples = int(_metric(challenger, "oos_samples") or 0)
    champion_exp = _metric(champion, "expectancy_r")
    challenger_exp = _metric(challenger, "expectancy_r")
    champion_dd = _metric(champion, "max_drawdown_r")
    challenger_dd = _metric(challenger, "max_drawdown_r")
    champion_cal = _metric(champion, "calibration_error_pct")
    challenger_cal = _metric(challenger, "calibration_error_pct")
    champion_false = _metric(champion, "false_alert_rate_pct")
    challenger_false = _metric(challenger, "false_alert_rate_pct")

    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    add(
        "OOS_SAMPLE",
        c_samples >= int(min_oos_samples),
        f"challenger OOS {c_samples} / mínimo {int(min_oos_samples)}",
    )
    expectancy_known = champion_exp is not None and challenger_exp is not None
    expectancy_better = bool(
        expectancy_known
        and challenger_exp >= champion_exp + float(min_expectancy_improvement_r)
    )
    add(
        "EXPECTANCY_IMPROVEMENT",
        expectancy_better,
        (
            f"champion {champion_exp} R · challenger {challenger_exp} R · "
            f"mínimo +{float(min_expectancy_improvement_r):.3f} R"
        ),
    )

    dd_known = champion_dd is not None and challenger_dd is not None
    drawdown_not_worse = bool(dd_known and challenger_dd <= champion_dd)
    add(
        "DRAWDOWN_NON_DEGRADATION",
        drawdown_not_worse,
        f"champion {champion_dd} R · challenger {challenger_dd} R",
    )

    calibration_checkable = champion_cal is not None and challenger_cal is not None
    calibration_not_worse = bool(
        calibration_checkable and challenger_cal <= champion_cal
    )
    add(
        "CALIBRATION_NON_DEGRADATION",
        calibration_not_worse,
        f"champion {champion_cal}% · challenger {challenger_cal}%",
    )

    if champion_false is None or challenger_false is None:
        false_alert_ok = False
        false_detail = "taxa de falso alerta ausente"
    else:
        false_alert_ok = challenger_false <= champion_false
        false_detail = f"champion {champion_false}% · challenger {challenger_false}%"
    add("FALSE_ALERT_NON_DEGRADATION", false_alert_ok, false_detail)

    shadow_eligible = bool(shadow.get("eligible_for_manual_review", False))
    critical_mismatch = int(shadow.get("critical_mismatches") or 0)
    shadow_ok = bool(shadow_eligible and critical_mismatch == 0)
    add(
        "SHADOW_REVIEW_GATE",
        shadow_ok,
        (
            f"eligible_for_manual_review={shadow_eligible} · "
            f"critical_mismatches={critical_mismatch}"
        ),
    )

    required_known = all(
        value is not None
        for value in (
            champion_exp,
            challenger_exp,
            champion_dd,
            challenger_dd,
            champion_cal,
            challenger_cal,
            champion_false,
            challenger_false,
        )
    )
    passed = sum(1 for check in checks if check["passed"])
    all_passed = bool(checks and passed == len(checks))

    if not required_known or c_samples < int(min_oos_samples):
        state = "NEED_MORE_EVIDENCE"
    elif all_passed:
        state = "HUMAN_REVIEW_CANDIDATE"
    else:
        state = "REJECTED_FOR_NOW"

    evaluation = {
        "state": state,
        "checks": checks,
        "checks_passed": passed,
        "checks_total": len(checks),
        "required_metrics_complete": required_known,
        "shadow_gate_passed": shadow_ok,
        "oos_samples": c_samples,
        "eligible_for_human_review": state == "HUMAN_REVIEW_CANDIDATE",
        "automatic_promotion": False,
        "production_change_allowed": False,
        "reason": (
            "Challenger reuniu evidência mínima para revisão humana; nenhuma promoção é automática."
            if state == "HUMAN_REVIEW_CANDIDATE"
            else
            "Evidência insuficiente ou critério de não degradação falhou; Champion permanece oficial."
        ),
    }

    item["state"] = state
    item["evaluated_at"] = _now()
    item["evaluation"] = evaluation
    return item


def upsert_learning_experiment(
    rows: Sequence[Mapping[str, Any]] | None,
    experiment: Mapping[str, Any],
) -> list[dict[str, Any]]:
    current = normalize_learning_experiments(rows)
    item = normalize_learning_experiment(experiment)
    out: list[dict[str, Any]] = []
    replaced = False
    for row in current:
        if row["experiment_id"] == item["experiment_id"]:
            out.append(item)
            replaced = True
        else:
            out.append(row)
    if not replaced:
        out.append(item)
    return out[-MAX_EXPERIMENTS:]


def learning_summary(
    episodes: Sequence[Mapping[str, Any]] | None,
    experiments: Sequence[Mapping[str, Any]] | None = None,
    research_refs: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    e = normalize_learning_episodes(episodes)
    x = normalize_learning_experiments(experiments)
    r = normalize_research_references(research_refs)
    settled = [row for row in e if row["state"] == "SETTLED"]
    scored = [row for row in settled if isinstance(row.get("correct"), bool)]
    correct = sum(1 for row in scored if row["correct"])
    calibration = confidence_calibration(e)
    errors = error_pattern_summary(e)
    review_candidates = sum(
        1 for row in x if row["state"] == "HUMAN_REVIEW_CANDIDATE"
    )
    return {
        "schema": SCHEMA,
        "episodes": len(e),
        "open_episodes": sum(1 for row in e if row["state"] == "OPEN"),
        "settled_episodes": len(settled),
        "scored_episodes": len(scored),
        "observed_match_rate_pct": (
            None if not scored else round(100.0 * correct / len(scored), 2)
        ),
        "calibration_state": calibration["state"],
        "calibration_gap_pct": calibration["mean_absolute_calibration_gap_pct"],
        "errors": errors["errors"],
        "errors_without_confirmed_cause": errors["errors_without_confirmed_cause"],
        "experiments": len(x),
        "human_review_candidates": review_candidates,
        "research_references": len(r),
        "automatic_learning_changes": False,
        "automatic_promotion": False,
        "real_orders_enabled": False,
    }


def learning_digest(
    episodes: Sequence[Mapping[str, Any]] | None,
    experiments: Sequence[Mapping[str, Any]] | None,
    research_refs: Sequence[Mapping[str, Any]] | None,
) -> str:
    payload = {
        "episodes": normalize_learning_episodes(episodes),
        "experiments": normalize_learning_experiments(experiments),
        "research_refs": normalize_research_references(research_refs),
    }
    return _stable_digest(payload, length=24)


__all__ = [
    "SCHEMA",
    "FORECAST_TYPES",
    "CAUSE_TAGS",
    "RESEARCH_KINDS",
    "new_learning_episode",
    "normalize_learning_episode",
    "normalize_learning_episodes",
    "settle_learning_episode",
    "upsert_learning_episode",
    "confidence_calibration",
    "error_pattern_summary",
    "new_research_reference",
    "normalize_research_references",
    "new_learning_experiment",
    "normalize_learning_experiment",
    "normalize_learning_experiments",
    "evaluate_learning_experiment",
    "upsert_learning_experiment",
    "learning_summary",
    "learning_digest",
]
