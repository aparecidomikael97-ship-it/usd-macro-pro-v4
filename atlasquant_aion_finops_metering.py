"""AION FinOps metering and admission budget gate.

Pure staging contract for scoped usage accounting. It records explicit usage
evidence and returns ALLOW / DEGRADE / BLOCK decisions for callers to enforce.
It never calls a provider, switches a model, charges money, starts a worker or
executes external work.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

SCHEMA = "ATLASQUANT_AION_FINOPS_METERING_V1"
MAX_EVENTS = 5000
DIMENSIONS = ("user_id", "feature", "model", "provider")


def _text(value: Any, limit: int = 180) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _money(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out) or out < 0:
        return None
    return round(out, 9)


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out) or out < 0 or not out.is_integer():
        return None
    return int(out)


def _positive_limit(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out) or out <= 0:
        return None
    return out


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _trusted_scope(raw: Mapping[str, Any] | None) -> tuple[dict[str, str], list[str]]:
    item = dict(raw or {})
    scope = {
        "owner_id": _text(item.get("owner_id"), 100),
        "tenant_id": _text(item.get("tenant_id"), 100),
        "workspace_id": _text(item.get("workspace_id"), 100),
    }
    blockers = [f"{key.upper()}_REQUIRED" for key, value in scope.items() if not value]
    return scope, blockers


def normalize_meter_event(
    raw: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Normalize one metering event without trusting caller-claimed scope."""
    item = dict(raw or {})
    scope, blockers = _trusted_scope(trusted_scope)

    for key in ("owner_id", "tenant_id", "workspace_id"):
        claimed = _text(item.get(key), 100)
        if claimed and claimed != scope.get(key):
            blockers.append("SCOPE_MISMATCH")

    user_id = _text(item.get("user_id"), 100)
    feature = _text(item.get("feature"), 120).lower()
    model = _text(item.get("model"), 160)
    provider = _text(item.get("provider"), 120) or "local_or_unknown"
    occurred_at = _text(item.get("occurred_at"), 96)
    if not user_id:
        blockers.append("USER_ID_REQUIRED")
    if not feature:
        blockers.append("FEATURE_REQUIRED")
    if not model:
        blockers.append("MODEL_REQUIRED")
    if not occurred_at:
        blockers.append("OCCURRED_AT_REQUIRED")

    calls = _nonnegative_int(item.get("calls", 1))
    depth = _nonnegative_int(item.get("depth", 0))
    input_tokens = _nonnegative_int(item.get("input_tokens", 0))
    output_tokens = _nonnegative_int(item.get("output_tokens", 0))
    supplied_total = item.get("total_tokens")
    total_tokens = None
    if calls is None:
        blockers.append("CALLS_INVALID")
    if depth is None:
        blockers.append("DEPTH_INVALID")
    if input_tokens is None or output_tokens is None:
        blockers.append("TOKENS_INVALID")
    else:
        total_tokens = input_tokens + output_tokens
        if supplied_total is not None:
            normalized_total = _nonnegative_int(supplied_total)
            if normalized_total is None or normalized_total != total_tokens:
                blockers.append("TOKEN_TOTAL_MISMATCH")

    predicted = _money(item.get("predicted_cost_usd"))
    actual = _money(item.get("actual_cost_usd"))
    if item.get("predicted_cost_usd") is not None and predicted is None:
        blockers.append("PREDICTED_COST_INVALID")
    if item.get("actual_cost_usd") is not None and actual is None:
        blockers.append("ACTUAL_COST_INVALID")

    identity = {
        **scope,
        "user_id": user_id,
        "feature": feature,
        "model": model,
        "provider": provider,
        "occurred_at": occurred_at,
        "calls": calls,
        "depth": depth,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "predicted_cost_usd": predicted,
        "actual_cost_usd": actual,
    }
    event_id = _text(item.get("event_id"), 160) or ("METER-" + _digest(identity)[:24].upper())
    event_digest = _digest({**identity, "event_id": event_id})
    unique_blockers = list(dict.fromkeys(blockers))
    return {
        "schema": SCHEMA,
        **identity,
        "event_id": event_id,
        "event_digest": event_digest,
        "state": "ACCEPTED" if not unique_blockers else "REJECTED",
        "blockers": unique_blockers,
        "billable_claim": False,
        "grants_authority": False,
        "executes_action": False,
    }


def _empty_bucket() -> dict[str, Any]:
    return {
        "events": 0,
        "calls": 0,
        "tokens": 0,
        "predicted_cost_usd": 0.0,
        "actual_cost_usd": 0.0,
        "actual_cost_events": 0,
    }


def _add(bucket: dict[str, Any], row: Mapping[str, Any]) -> None:
    bucket["events"] += 1
    bucket["calls"] += int(row.get("calls") or 0)
    bucket["tokens"] += int(row.get("total_tokens") or 0)
    bucket["predicted_cost_usd"] = round(
        float(bucket["predicted_cost_usd"]) + float(row.get("predicted_cost_usd") or 0.0),
        9,
    )
    if row.get("actual_cost_usd") is not None:
        bucket["actual_cost_usd"] = round(
            float(bucket["actual_cost_usd"]) + float(row["actual_cost_usd"]),
            9,
        )
        bucket["actual_cost_events"] += 1


def build_metering_ledger(
    events: Sequence[Mapping[str, Any]] | None,
    *,
    trusted_scope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build an idempotent, scope-bound metering snapshot."""
    scope, scope_blockers = _trusted_scope(trusted_scope)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    duplicate_exact = 0

    for raw in list(events or [])[:MAX_EVENTS]:
        if not isinstance(raw, Mapping):
            rejected.append({"state": "REJECTED", "blockers": ["EVENT_INVALID"]})
            continue
        row = normalize_meter_event(raw, trusted_scope=scope)
        if row["state"] != "ACCEPTED":
            rejected.append(row)
            continue
        prior = seen.get(row["event_id"])
        if prior is not None:
            if prior == row["event_digest"]:
                duplicate_exact += 1
            else:
                conflict = dict(row)
                conflict["state"] = "REJECTED"
                conflict["blockers"] = ["EVENT_ID_CONFLICT"]
                rejected.append(conflict)
            continue
        seen[row["event_id"]] = row["event_digest"]
        accepted.append(row)

    total = _empty_bucket()
    by_dimension: dict[str, dict[str, dict[str, Any]]] = {name: {} for name in DIMENSIONS}
    for row in accepted:
        _add(total, row)
        for dim in DIMENSIONS:
            key = str(row[dim])
            bucket = by_dimension[dim].setdefault(key, _empty_bucket())
            _add(bucket, row)

    integrity_material = [
        {"event_id": row["event_id"], "event_digest": row["event_digest"]}
        for row in accepted
    ]
    return {
        "schema": SCHEMA,
        **scope,
        "state": "READY" if not scope_blockers else "BLOCKED",
        "scope_blockers": scope_blockers,
        "accepted_events": accepted,
        "accepted_count": len(accepted),
        "rejected_events": rejected,
        "rejected_count": len(rejected),
        "duplicate_exact_count": duplicate_exact,
        "totals": total,
        "by_dimension": by_dimension,
        "ledger_digest": _digest(integrity_material),
        "source_of_truth_for_billing": False,
        "automatic_charge": False,
        "automatic_model_switch": False,
        "executes_action": False,
    }


def reconcile_predicted_vs_actual(
    ledger: Mapping[str, Any] | None,
    *,
    divergence_threshold_pct: Any = 20.0,
) -> dict[str, Any]:
    data = dict(ledger or {})
    threshold = _positive_limit(divergence_threshold_pct)
    blockers: list[str] = []
    if threshold is None:
        blockers.append("THRESHOLD_INVALID")
        threshold = 20.0

    predicted = _money((data.get("totals") or {}).get("predicted_cost_usd")) or 0.0
    actual = _money((data.get("totals") or {}).get("actual_cost_usd")) or 0.0
    actual_events = _nonnegative_int((data.get("totals") or {}).get("actual_cost_events")) or 0

    if actual_events <= 0 or predicted <= 0:
        state = "UNKNOWN"
        divergence = None
    else:
        divergence = round(abs(actual - predicted) / predicted * 100.0, 4)
        state = "DIVERGENT" if divergence > threshold else "MATCH"

    return {
        "schema": SCHEMA,
        "state": "BLOCKED" if blockers else state,
        "predicted_cost_usd": predicted,
        "actual_cost_usd": actual,
        "actual_cost_events": actual_events,
        "divergence_pct": divergence,
        "threshold_pct": threshold,
        "requires_reconciliation": state == "DIVERGENT",
        "blockers": blockers,
        "executes_action": False,
    }


def _request_usage(
    raw: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    item = dict(raw or {})
    event_like = {
        **dict(trusted_scope),
        "event_id": "PROSPECTIVE",
        "user_id": item.get("user_id"),
        "feature": item.get("feature"),
        "model": item.get("model"),
        "provider": item.get("provider") or "local_or_unknown",
        "occurred_at": item.get("occurred_at") or "PROSPECTIVE",
        "calls": item.get("calls", 1),
        "depth": item.get("depth", 0),
        "input_tokens": item.get("input_tokens", 0),
        "output_tokens": item.get("output_tokens", 0),
        "predicted_cost_usd": item.get("predicted_cost_usd"),
    }
    row = normalize_meter_event(event_like, trusted_scope=trusted_scope)
    blockers = list(row["blockers"])
    if row.get("predicted_cost_usd") is None:
        blockers.append("PREDICTED_COST_REQUIRED")
    return row, list(dict.fromkeys(blockers))


def _limit_int(policy: Mapping[str, Any], key: str) -> int | None:
    raw = policy.get(key)
    if raw is None:
        return None
    value = _nonnegative_int(raw)
    if value is None or value <= 0:
        return None
    return value


def evaluate_finops_budget(
    ledger: Mapping[str, Any] | None,
    *,
    policy: Mapping[str, Any] | None,
    prospective_request: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return a pure admission decision; the caller remains responsible for enforcement."""
    data = dict(ledger or {})
    p = dict(policy or {})
    scope = {
        "owner_id": _text(data.get("owner_id"), 100),
        "tenant_id": _text(data.get("tenant_id"), 100),
        "workspace_id": _text(data.get("workspace_id"), 100),
    }
    blockers: list[str] = []
    degrade: list[str] = []
    if data.get("state") != "READY":
        blockers.append("LEDGER_NOT_READY")

    policy_id = _text(p.get("policy_id"), 120)
    revision = _nonnegative_int(p.get("revision"))
    if p.get("state") != "VERIFIED":
        blockers.append("POLICY_NOT_VERIFIED")
    if not policy_id:
        blockers.append("POLICY_ID_REQUIRED")
    if revision is None or revision < 1:
        blockers.append("POLICY_REVISION_INVALID")
    for key in ("owner_id", "tenant_id", "workspace_id"):
        if _text(p.get(key), 100) != scope[key]:
            blockers.append("POLICY_SCOPE_MISMATCH")
            break

    request, request_blockers = _request_usage(prospective_request, trusted_scope=scope)
    blockers.extend(request_blockers)

    window_budget = _positive_limit(p.get("window_budget_usd"))
    max_calls = _limit_int(p, "max_calls")
    max_tokens = _limit_int(p, "max_tokens")
    max_depth = _limit_int(p, "max_depth")
    max_user_calls = _limit_int(p, "max_user_calls")
    max_user_tokens = _limit_int(p, "max_user_tokens")
    required_limits = {
        "WINDOW_BUDGET": window_budget,
        "MAX_CALLS": max_calls,
        "MAX_TOKENS": max_tokens,
        "MAX_DEPTH": max_depth,
        "MAX_USER_CALLS": max_user_calls,
        "MAX_USER_TOKENS": max_user_tokens,
    }
    for name, value in required_limits.items():
        if value is None:
            blockers.append(f"POLICY_{name}_INVALID")

    soft_pct = _positive_limit(p.get("soft_limit_pct"))
    noisy_pct = _positive_limit(p.get("noisy_neighbor_share_pct"))
    if soft_pct is None or soft_pct >= 100:
        blockers.append("SOFT_LIMIT_INVALID")
        soft_pct = 80.0
    if noisy_pct is None or noisy_pct > 100:
        blockers.append("NOISY_NEIGHBOR_LIMIT_INVALID")
        noisy_pct = 70.0

    totals = dict(data.get("totals") or {})
    current_calls = int(totals.get("calls") or 0)
    current_tokens = int(totals.get("tokens") or 0)
    current_predicted = float(totals.get("predicted_cost_usd") or 0.0)
    req_calls = int(request.get("calls") or 0)
    req_tokens = int(request.get("total_tokens") or 0)
    req_cost = float(request.get("predicted_cost_usd") or 0.0)
    req_depth = int(request.get("depth") or 0)

    projected = {
        "calls": current_calls + req_calls,
        "tokens": current_tokens + req_tokens,
        "predicted_cost_usd": round(current_predicted + req_cost, 9),
    }

    if max_depth is not None and req_depth > max_depth:
        blockers.append("DEPTH_LIMIT")
    if max_calls is not None and projected["calls"] > max_calls:
        blockers.append("CALL_LIMIT")
    if max_tokens is not None and projected["tokens"] > max_tokens:
        blockers.append("TOKEN_LIMIT")
    if window_budget is not None and projected["predicted_cost_usd"] > window_budget:
        blockers.append("COST_LIMIT")

    user_id = str(request.get("user_id") or "")
    users = dict((data.get("by_dimension") or {}).get("user_id") or {})
    user_bucket = dict(users.get(user_id) or _empty_bucket())
    projected_user_calls = int(user_bucket.get("calls") or 0) + req_calls
    projected_user_tokens = int(user_bucket.get("tokens") or 0) + req_tokens
    if max_user_calls is not None and projected_user_calls > max_user_calls:
        blockers.append("USER_CALL_LIMIT")
    if max_user_tokens is not None and projected_user_tokens > max_user_tokens:
        blockers.append("USER_TOKEN_LIMIT")

    projected_user_cost = float(user_bucket.get("predicted_cost_usd") or 0.0) + req_cost
    if len(users) >= 2 and projected["predicted_cost_usd"] > 0:
        share = projected_user_cost / projected["predicted_cost_usd"] * 100.0
        if share > noisy_pct:
            blockers.append("NOISY_NEIGHBOR_SHARE")
    else:
        share = None

    def soft_check(current: float, limit: float | int | None, reason: str) -> None:
        if limit is None or float(limit) <= 0:
            return
        if current / float(limit) * 100.0 >= soft_pct:
            degrade.append(reason)

    soft_check(projected["calls"], max_calls, "CALL_SOFT_LIMIT")
    soft_check(projected["tokens"], max_tokens, "TOKEN_SOFT_LIMIT")
    soft_check(projected["predicted_cost_usd"], window_budget, "COST_SOFT_LIMIT")

    reconciliation = reconcile_predicted_vs_actual(
        data,
        divergence_threshold_pct=p.get("reconciliation_threshold_pct", 20.0),
    )
    if reconciliation["state"] == "DIVERGENT":
        if p.get("block_on_cost_divergence") is True:
            blockers.append("COST_RECONCILIATION_REQUIRED")
        else:
            degrade.append("COST_RECONCILIATION_REQUIRED")

    blockers = list(dict.fromkeys(blockers))
    degrade = list(dict.fromkeys(degrade))
    if blockers:
        state = "BLOCK"
        mode = "BLOCK_NEW_WORK"
    elif degrade:
        state = "DEGRADE"
        mode = "LOW_COST_MODE"
    else:
        state = "ALLOW"
        mode = "NORMAL"

    return {
        "schema": SCHEMA,
        "state": state,
        "mode": mode,
        "blockers": blockers,
        "degrade_reasons": degrade,
        "scope": scope,
        "policy": {
            "policy_id": policy_id,
            "revision": revision,
            "state": _text(p.get("state"), 40).upper(),
            "scope_bound": "POLICY_SCOPE_MISMATCH" not in blockers,
        },
        "request": {
            "user_id": user_id,
            "feature": request.get("feature"),
            "model": request.get("model"),
            "provider": request.get("provider"),
            "calls": req_calls,
            "tokens": req_tokens,
            "depth": req_depth,
            "predicted_cost_usd": req_cost,
        },
        "projected": projected,
        "projected_user": {
            "calls": projected_user_calls,
            "tokens": projected_user_tokens,
            "predicted_cost_usd": round(projected_user_cost, 9),
            "share_pct": None if share is None else round(share, 4),
        },
        "reconciliation": reconciliation,
        "throttle_decision_only": True,
        "automatic_provider_call": False,
        "automatic_model_switch": False,
        "automatic_charge": False,
        "grants_authority": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "MAX_EVENTS",
    "DIMENSIONS",
    "normalize_meter_event",
    "build_metering_ledger",
    "reconcile_predicted_vs_actual",
    "evaluate_finops_budget",
]
