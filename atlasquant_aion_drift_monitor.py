"""AION Data Drift + Decision Drift monitor.

Pure, evidence-bound monitoring. It does not retrain, promote, switch models,
change prompts, call providers or mutate production.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json
import math

SCHEMA = "ATLASQUANT_AION_DRIFT_MONITOR_V1"
EPSILON = 1e-9
MAX_FEATURES = 64
MAX_BINS = 64
MAX_DECISIONS = 64


def _text(value: Any, limit: int = 240) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    item = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(item.get("owner_id") or item.get("actor_id"), 120),
        "tenant_id": _text(item.get("tenant_id"), 120),
        "workspace_id": _text(item.get("workspace_id"), 120),
    }


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _refs(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:80]:
        text = _text(raw, 320)
        if text and text not in out:
            out.append(text)
    return out


def _distribution(
    value: Any,
    *,
    max_items: int,
) -> tuple[dict[str, float], list[str]]:
    blockers: list[str] = []
    if not isinstance(value, Mapping) or not value or len(value) > max_items:
        return {}, ["DISTRIBUTION_INVALID"]
    out: dict[str, float] = {}
    for raw_key, raw_value in value.items():
        key = _text(raw_key, 120)
        number = _number(raw_value)
        if not key or number is None or number < 0 or number > 1:
            blockers.append("DISTRIBUTION_VALUE_INVALID")
            continue
        if key in out:
            blockers.append("DISTRIBUTION_KEY_DUPLICATE")
            continue
        out[key] = number
    total = sum(out.values())
    if not out or abs(total - 1.0) > 1e-6:
        blockers.append("DISTRIBUTION_MUST_SUM_TO_ONE")
    return out, list(dict.fromkeys(blockers))


def _psi(reference: Mapping[str, float], current: Mapping[str, float]) -> float:
    keys = sorted(set(reference) | set(current))
    total = 0.0
    for key in keys:
        ref = max(float(reference.get(key, 0.0)), EPSILON)
        cur = max(float(current.get(key, 0.0)), EPSILON)
        total += (cur - ref) * math.log(cur / ref)
    return round(total, 9)


def _tvd(reference: Mapping[str, float], current: Mapping[str, float]) -> float:
    keys = set(reference) | set(current)
    return round(0.5 * sum(abs(float(current.get(k, 0.0)) - float(reference.get(k, 0.0))) for k in keys), 9)


def normalize_drift_policy(
    raw: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    item = dict(raw) if isinstance(raw, Mapping) else {}
    trusted = _scope(trusted_scope)
    blockers: list[str] = []
    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_REQUIRED")
    if item.get("state") != "VERIFIED":
        blockers.append("POLICY_NOT_VERIFIED")
    if any(_text(item.get(key), 120) != trusted[key] for key in trusted):
        blockers.append("POLICY_SCOPE_MISMATCH")
    policy_id = _text(item.get("policy_id"), 120)
    revision = _positive_int(item.get("revision"))
    min_sample = _positive_int(item.get("min_sample_size"))
    if not policy_id:
        blockers.append("POLICY_ID_REQUIRED")
    if revision is None:
        blockers.append("POLICY_REVISION_INVALID")
    if min_sample is None:
        blockers.append("MIN_SAMPLE_SIZE_INVALID")

    numeric_specs = (
        ("data_psi_warn", 0.0, None),
        ("data_psi_block", 0.0, None),
        ("decision_tvd_warn", 0.0, 1.0),
        ("decision_tvd_block", 0.0, 1.0),
        ("max_safety_violation_delta_pct_points", 0.0, 100.0),
        ("max_unknown_rate_pct", 0.0, 100.0),
        ("max_override_rate_pct", 0.0, 100.0),
    )
    values: dict[str, float | None] = {}
    for field, minimum, maximum in numeric_specs:
        value = _number(item.get(field))
        if value is None or value < minimum or (maximum is not None and value > maximum):
            blockers.append("POLICY_VALUE_INVALID:" + field)
            values[field] = None
        else:
            values[field] = value

    if (
        values["data_psi_warn"] is not None
        and values["data_psi_block"] is not None
        and values["data_psi_warn"] >= values["data_psi_block"]
    ):
        blockers.append("DATA_PSI_THRESHOLDS_INVALID")
    if (
        values["decision_tvd_warn"] is not None
        and values["decision_tvd_block"] is not None
        and values["decision_tvd_warn"] >= values["decision_tvd_block"]
    ):
        blockers.append("DECISION_TVD_THRESHOLDS_INVALID")

    return {
        "schema": SCHEMA,
        "state": "VERIFIED" if not blockers else "BLOCKED",
        "blockers": list(dict.fromkeys(blockers)),
        "policy_id": policy_id,
        "revision": revision,
        **trusted,
        "min_sample_size": min_sample,
        **values,
        "automatic_retraining": False,
        "automatic_promotion": False,
        "automatic_model_switch": False,
        "executes_action": False,
    }


def _snapshot(
    raw: Mapping[str, Any] | None,
    *,
    trusted: Mapping[str, str],
    min_sample: int,
) -> tuple[dict[str, Any], list[str]]:
    item = dict(raw) if isinstance(raw, Mapping) else {}
    blockers: list[str] = []
    if any(_text(item.get(key), 120) != trusted[key] for key in trusted):
        blockers.append("SNAPSHOT_SCOPE_MISMATCH")
    sample = _positive_int(item.get("sample_size"))
    if sample is None or sample < min_sample:
        blockers.append("SAMPLE_SIZE_INSUFFICIENT")
    version = _text(item.get("version"), 160)
    window = _text(item.get("window"), 160)
    refs = _refs(item.get("evidence_refs"))
    if not version:
        blockers.append("SNAPSHOT_VERSION_REQUIRED")
    if not window:
        blockers.append("SNAPSHOT_WINDOW_REQUIRED")
    if not refs:
        blockers.append("SNAPSHOT_EVIDENCE_REQUIRED")

    features_raw = item.get("features")
    features: dict[str, dict[str, float]] = {}
    if not isinstance(features_raw, Mapping) or not features_raw or len(features_raw) > MAX_FEATURES:
        blockers.append("FEATURES_INVALID")
    else:
        for raw_name, raw_dist in features_raw.items():
            name = _text(raw_name, 120)
            dist, errors = _distribution(raw_dist, max_items=MAX_BINS)
            if not name:
                blockers.append("FEATURE_NAME_INVALID")
                continue
            if errors:
                blockers.extend(f"FEATURE:{name}:{error}" for error in errors)
            features[name] = dist

    decisions, errors = _distribution(item.get("decisions"), max_items=MAX_DECISIONS)
    blockers.extend("DECISIONS:" + error for error in errors)

    rates: dict[str, float | None] = {}
    for field in ("safety_violation_rate_pct", "unknown_rate_pct", "override_rate_pct"):
        value = _number(item.get(field))
        if value is None or value < 0 or value > 100:
            blockers.append("RATE_INVALID:" + field)
            rates[field] = None
        else:
            rates[field] = value

    return {
        "version": version,
        "window": window,
        "sample_size": sample,
        "features": features,
        "decisions": decisions,
        **rates,
        "evidence_refs": refs,
    }, list(dict.fromkeys(blockers))


def evaluate_drift(
    *,
    trusted_scope: Mapping[str, Any] | None,
    policy: Mapping[str, Any] | None,
    reference_snapshot: Mapping[str, Any] | None,
    current_snapshot: Mapping[str, Any] | None,
) -> dict[str, Any]:
    trusted = _scope(trusted_scope)
    p = normalize_drift_policy(policy, trusted_scope=trusted)
    blockers = list(p["blockers"])
    degrade: list[str] = []

    if p["state"] != "VERIFIED":
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "blockers": blockers,
            "degrade_reasons": [],
            "scope": trusted,
            "policy": p,
            "data_drift": {},
            "decision_drift": {},
            "automatic_retraining": False,
            "automatic_promotion": False,
            "executes_action": False,
        }

    ref, ref_errors = _snapshot(
        reference_snapshot,
        trusted=trusted,
        min_sample=int(p["min_sample_size"]),
    )
    cur, cur_errors = _snapshot(
        current_snapshot,
        trusted=trusted,
        min_sample=int(p["min_sample_size"]),
    )
    blockers.extend("REFERENCE:" + x for x in ref_errors)
    blockers.extend("CURRENT:" + x for x in cur_errors)

    if set(ref["features"]) != set(cur["features"]):
        blockers.append("FEATURE_SET_MISMATCH")

    feature_psi: dict[str, float] = {}
    if not blockers:
        for name in sorted(ref["features"]):
            score = _psi(ref["features"][name], cur["features"][name])
            feature_psi[name] = score
            if score >= float(p["data_psi_block"]):
                blockers.append("DATA_DRIFT_BLOCK:" + name)
            elif score >= float(p["data_psi_warn"]):
                degrade.append("DATA_DRIFT_WARN:" + name)

    decision_tvd = None
    if not ref_errors and not cur_errors:
        decision_tvd = _tvd(ref["decisions"], cur["decisions"])
        if decision_tvd >= float(p["decision_tvd_block"]):
            blockers.append("DECISION_DRIFT_BLOCK")
        elif decision_tvd >= float(p["decision_tvd_warn"]):
            degrade.append("DECISION_DRIFT_WARN")

        safety_delta = float(cur["safety_violation_rate_pct"]) - float(ref["safety_violation_rate_pct"])
        if safety_delta > float(p["max_safety_violation_delta_pct_points"]):
            blockers.append("SAFETY_VIOLATION_REGRESSION")
        if float(cur["unknown_rate_pct"]) > float(p["max_unknown_rate_pct"]):
            blockers.append("UNKNOWN_RATE_LIMIT")
        if float(cur["override_rate_pct"]) > float(p["max_override_rate_pct"]):
            blockers.append("OVERRIDE_RATE_LIMIT")
    else:
        safety_delta = None

    blockers = list(dict.fromkeys(blockers))
    degrade = list(dict.fromkeys(degrade))
    state = "BLOCKED" if blockers else "DEGRADED" if degrade else "STABLE"

    data_drift = {
        "feature_psi": feature_psi,
        "max_psi": max(feature_psi.values()) if feature_psi else None,
        "warn_threshold": p["data_psi_warn"],
        "block_threshold": p["data_psi_block"],
    }
    decision_drift = {
        "tvd": decision_tvd,
        "warn_threshold": p["decision_tvd_warn"],
        "block_threshold": p["decision_tvd_block"],
        "safety_violation_delta_pct_points": safety_delta,
        "current_unknown_rate_pct": cur.get("unknown_rate_pct"),
        "current_override_rate_pct": cur.get("override_rate_pct"),
    }
    material = {
        "scope": trusted,
        "policy_id": p["policy_id"],
        "policy_revision": p["revision"],
        "reference_version": ref["version"],
        "current_version": cur["version"],
        "data_drift": data_drift,
        "decision_drift": decision_drift,
        "blockers": blockers,
        "degrade": degrade,
    }
    return {
        "schema": SCHEMA,
        "state": state,
        "blockers": blockers,
        "degrade_reasons": degrade,
        "scope": trusted,
        "policy": p,
        "reference": {
            "version": ref["version"],
            "window": ref["window"],
            "sample_size": ref["sample_size"],
        },
        "current": {
            "version": cur["version"],
            "window": cur["window"],
            "sample_size": cur["sample_size"],
        },
        "data_drift": data_drift,
        "decision_drift": decision_drift,
        "drift_digest": _digest(material),
        "promotion_recommendation": "REVIEW_OK" if state == "STABLE" else "HOLD_PROMOTION",
        "automatic_retraining": False,
        "automatic_promotion": False,
        "automatic_model_switch": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }


def drift_promotion_gate(report: Mapping[str, Any] | None) -> dict[str, Any]:
    item = dict(report) if isinstance(report, Mapping) else {}
    valid = item.get("schema") == SCHEMA
    stable = valid and item.get("state") == "STABLE"
    return {
        "schema": SCHEMA,
        "state": "HUMAN_REVIEW_CANDIDATE" if stable else "BLOCK_PROMOTION",
        "drift_digest": _text(item.get("drift_digest"), 128),
        "drift_state": _text(item.get("state"), 40).upper(),
        "promotion_authorized": False,
        "automatic_promotion": False,
        "automatic_retraining": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "normalize_drift_policy",
    "evaluate_drift",
    "drift_promotion_gate",
]
