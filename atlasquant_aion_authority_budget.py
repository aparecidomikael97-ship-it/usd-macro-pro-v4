"""Cumulative authority-consumption budget for the AION shared core.

This module never grants authority and never executes an action. It tracks
verified authority/approval intent metadata over a rolling time window so many
individually acceptable requests cannot silently accumulate into broader
authority than trusted policy permits.

Cryptographic authority verification stays in atlasquant_aion_authority_verifier.
Human approval and downstream execution gates remain separate requirements.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_AUTHORITY_BUDGET_V1"
VERSION = 1
MAX_EVENTS = 1000
MAX_POLICY_CAPABILITIES = 128
MIN_WINDOW_SECONDS = 60
MAX_WINDOW_SECONDS = 2_592_000  # 30 days


def _clean(value: Any, limit: int = 400) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _aware(value: Any) -> datetime:
    if isinstance(value, datetime):
        out = value
    elif isinstance(value, str) and value:
        out = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("timezone-aware timestamp required")
    if out.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return out.astimezone(timezone.utc)


def _exact_int(value: Any, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("integer policy value required")
    if value < minimum or value > maximum:
        raise ValueError("integer policy value out of range")
    return value


def _scope(context: Mapping[str, Any] | None) -> dict[str, str]:
    raw = dict(context or {})
    subject = _clean(raw.get("subject_id") or raw.get("owner_id") or raw.get("actor_id"), 160)
    tenant = _clean(raw.get("tenant_id"), 120)
    workspace = _clean(raw.get("workspace_id"), 120)
    if not subject or not tenant or not workspace:
        raise ValueError("subject/tenant/workspace binding required")
    scope_digest = sha256(
        (subject + "|" + tenant + "|" + workspace).encode("utf-8")
    ).hexdigest()[:24]
    return {
        "subject_id": subject,
        "tenant_id": tenant,
        "workspace_id": workspace,
        "scope_digest": scope_digest,
    }


def normalize_authority_budget_policy(
    policy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(policy, Mapping):
        raise ValueError("trusted authority budget policy required")
    raw = dict(policy)
    window_seconds = _exact_int(
        raw.get("window_seconds"),
        minimum=MIN_WINDOW_SECONDS,
        maximum=MAX_WINDOW_SECONDS,
    )
    max_events = _exact_int(raw.get("max_events"), minimum=1, maximum=MAX_EVENTS)
    max_units = _exact_int(raw.get("max_units"), minimum=1, maximum=1_000_000)
    max_distinct_capabilities = _exact_int(
        raw.get("max_distinct_capabilities"),
        minimum=1,
        maximum=MAX_POLICY_CAPABILITIES,
    )
    max_distinct_resources = _exact_int(
        raw.get("max_distinct_resources"),
        minimum=1,
        maximum=MAX_EVENTS,
    )
    max_uses_per_grant = _exact_int(
        raw.get("max_uses_per_grant", 1),
        minimum=1,
        maximum=100,
    )

    capability_units_raw = raw.get("capability_units")
    capability_limits_raw = raw.get("capability_limits")
    if not isinstance(capability_units_raw, Mapping) or not capability_units_raw:
        raise ValueError("capability_units policy required")
    if not isinstance(capability_limits_raw, Mapping) or not capability_limits_raw:
        raise ValueError("capability_limits policy required")
    if len(capability_units_raw) > MAX_POLICY_CAPABILITIES:
        raise ValueError("too many authority budget capabilities")

    capability_units: dict[str, int] = {}
    capability_limits: dict[str, int] = {}
    for key, value in capability_units_raw.items():
        capability = _clean(key, 160)
        if not capability:
            raise ValueError("empty capability in authority budget policy")
        capability_units[capability] = _exact_int(
            value,
            minimum=1,
            maximum=1_000_000,
        )
    for key, value in capability_limits_raw.items():
        capability = _clean(key, 160)
        if capability not in capability_units:
            raise ValueError("capability limit missing unit policy")
        capability_limits[capability] = _exact_int(
            value,
            minimum=1,
            maximum=MAX_EVENTS,
        )
    if set(capability_limits) != set(capability_units):
        raise ValueError("every capability requires an explicit usage limit")

    sensitive = []
    for raw_cap in list(raw.get("sensitive_capabilities") or []):
        cap = _clean(raw_cap, 160)
        if cap and cap not in sensitive:
            sensitive.append(cap)
    if any(cap not in capability_units for cap in sensitive):
        raise ValueError("sensitive capability outside policy")

    policy_id = _clean(raw.get("policy_id"), 160)
    policy_version = _clean(raw.get("policy_version"), 80)
    if not policy_id or not policy_version:
        raise ValueError("policy id/version required")

    normalized = {
        "schema": SCHEMA,
        "policy_id": policy_id,
        "policy_version": policy_version,
        "window_seconds": window_seconds,
        "max_events": max_events,
        "max_units": max_units,
        "max_distinct_capabilities": max_distinct_capabilities,
        "max_distinct_resources": max_distinct_resources,
        "max_uses_per_grant": max_uses_per_grant,
        "capability_units": capability_units,
        "capability_limits": capability_limits,
        "sensitive_capabilities": sorted(sensitive),
        "budget_grants_authority": False,
        "executes_action": False,
    }
    normalized["policy_digest"] = _digest(normalized)
    return normalized


def default_authority_budget(
    trusted_context: Mapping[str, Any] | None,
    *,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    scope = _scope(trusted_context)
    normalized_policy = normalize_authority_budget_policy(policy)
    events: list[dict[str, Any]] = []
    state = {
        "schema": SCHEMA,
        "version": VERSION,
        **scope,
        "policy": normalized_policy,
        "events": events,
        "budget_grants_authority": False,
        "execution_allowed": False,
        "external_action_executed": False,
    }
    state["digest"] = _digest({
        "scope_digest": scope["scope_digest"],
        "policy_digest": normalized_policy["policy_digest"],
        "events": events,
    })
    return state


def _state_digest(state: Mapping[str, Any]) -> str:
    policy = state.get("policy") if isinstance(state.get("policy"), Mapping) else {}
    return _digest({
        "scope_digest": state.get("scope_digest"),
        "policy_digest": policy.get("policy_digest"),
        "events": state.get("events") or [],
    })


def validate_authority_budget(
    budget: Mapping[str, Any] | None,
    *,
    trusted_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    expected = _scope(trusted_context)
    if not isinstance(budget, Mapping):
        return {
            "schema": SCHEMA,
            "state": "BLOCK",
            "valid": False,
            "blockers": ["BUDGET_MAPPING_REQUIRED"],
            "execution_allowed": False,
        }
    raw = dict(budget)
    blockers: list[str] = []
    if raw.get("schema") != SCHEMA or raw.get("version") != VERSION:
        blockers.append("BUDGET_SCHEMA_OR_VERSION_MISMATCH")
    for key in ("subject_id", "tenant_id", "workspace_id", "scope_digest"):
        if raw.get(key) != expected[key]:
            blockers.append("BUDGET_SCOPE_MISMATCH")
            break
    try:
        policy = normalize_authority_budget_policy(
            raw.get("policy") if isinstance(raw.get("policy"), Mapping) else None
        )
    except Exception:
        policy = {}
        blockers.append("BUDGET_POLICY_INVALID")
    if policy and raw.get("policy", {}).get("policy_digest") != policy.get("policy_digest"):
        blockers.append("BUDGET_POLICY_DIGEST_MISMATCH")
    events = list(raw.get("events") or [])
    if len(events) > MAX_EVENTS:
        blockers.append("BUDGET_EVENT_CAPACITY_EXCEEDED")
    ids: set[str] = set()
    for row in events[: MAX_EVENTS + 1]:
        if not isinstance(row, Mapping):
            blockers.append("BUDGET_EVENT_NOT_MAPPING")
            continue
        event = dict(row)
        event_id = _clean(event.get("event_id"), 120)
        if not event_id or event_id in ids:
            blockers.append("BUDGET_EVENT_ID_INVALID_OR_DUPLICATE")
        ids.add(event_id)
        for key in ("subject_id", "tenant_id", "workspace_id", "scope_digest"):
            if event.get(key) != expected[key]:
                blockers.append("BUDGET_EVENT_SCOPE_MISMATCH")
                break
        if _clean(event.get("capability"), 160) not in policy.get("capability_units", {}):
            blockers.append("BUDGET_EVENT_CAPABILITY_INVALID")
        if event.get("execution_allowed") is not False:
            blockers.append("BUDGET_EVENT_CANNOT_GRANT_EXECUTION")

    expected_digest = _state_digest(raw)
    if _clean(raw.get("digest"), 64) != expected_digest:
        blockers.append("BUDGET_DIGEST_MISMATCH")
    return {
        "schema": SCHEMA,
        "state": "CONFIRMED" if not blockers else "BLOCK",
        "valid": not blockers,
        "blockers": sorted(set(blockers)),
        "expected_digest": expected_digest,
        "stored_digest": _clean(raw.get("digest"), 64),
        "execution_allowed": False,
        "budget_grants_authority": False,
    }


def _active_events(
    events: list[dict[str, Any]],
    *,
    now: datetime,
    window_seconds: int,
) -> list[dict[str, Any]]:
    cutoff = now - timedelta(seconds=window_seconds)
    out = []
    for row in events:
        try:
            used_at = _aware(row.get("used_at"))
        except Exception:
            continue
        if cutoff <= used_at <= now:
            out.append(row)
    return out


def evaluate_authority_intent(
    budget: Mapping[str, Any] | None,
    *,
    trusted_context: Mapping[str, Any] | None,
    capability: Any,
    resource_ref: Any,
    grant_id: Any,
    authority_verification: Mapping[str, Any] | None,
    approval_digest: Any = "",
    approval_verified: Any = False,
    role_id: Any = "",
    now: Any,
) -> dict[str, Any]:
    audit = validate_authority_budget(budget, trusted_context=trusted_context)
    if audit["valid"] is not True:
        return {
            "schema": SCHEMA,
            "state": "BLOCK",
            "blockers": ["BUDGET_SCOPE_OR_INTEGRITY_MISMATCH"],
            "within_budget": False,
            "execution_allowed": False,
            "budget_grants_authority": False,
        }

    state = dict(budget or {})
    policy = dict(state["policy"])
    scope = _scope(trusted_context)
    cap = _clean(capability, 160)
    resource = _clean(resource_ref, 300)
    grant = _clean(grant_id, 200)
    role = _clean(role_id, 80).casefold()
    approval = _clean(approval_digest, 200)
    blockers: list[str] = []
    current = _aware(now)

    if cap not in policy["capability_units"]:
        blockers.append("CAPABILITY_OUTSIDE_BUDGET_POLICY")
    if not resource:
        blockers.append("RESOURCE_BINDING_REQUIRED")
    if not grant:
        blockers.append("GRANT_ID_REQUIRED")

    verification = dict(authority_verification or {})
    if verification.get("authority_verified") is not True:
        blockers.append("CRYPTOGRAPHIC_AUTHORITY_NOT_VERIFIED")
    if verification.get("execution_authority_granted") is not True:
        blockers.append("CAPABILITY_GRANT_NOT_VERIFIED")
    if verification.get("execution_allowed") is not False:
        blockers.append("AUTHORITY_VERIFIER_EXECUTION_SEPARATION_BROKEN")
    verified_subject = _clean(verification.get("subject_id"), 160)
    verified_tenant = _clean(verification.get("tenant_id"), 120)
    verified_grant = _clean(
        verification.get("statement_id") or verification.get("grant_id"),
        200,
    )
    verified_caps = {
        _clean(item, 160)
        for item in list(verification.get("capabilities") or [])
        if _clean(item, 160)
    }
    if verified_subject != scope["subject_id"]:
        blockers.append("AUTHORITY_SUBJECT_MISMATCH")
    if verified_tenant != scope["tenant_id"]:
        blockers.append("AUTHORITY_TENANT_MISMATCH")
    if verified_grant and verified_grant != grant:
        blockers.append("AUTHORITY_GRANT_ID_MISMATCH")
    if cap and cap not in verified_caps:
        blockers.append("CAPABILITY_NOT_IN_VERIFIED_GRANT")

    sensitive = cap in set(policy["sensitive_capabilities"])
    if sensitive and (approval_verified is not True or not approval):
        blockers.append("SENSITIVE_CAPABILITY_REQUIRES_VERIFIED_HUMAN_APPROVAL")
    if approval_verified is not True and approval:
        blockers.append("UNVERIFIED_APPROVAL_DIGEST")

    expires_raw = verification.get("expires_at")
    if expires_raw:
        try:
            if current >= _aware(expires_raw):
                blockers.append("AUTHORITY_GRANT_EXPIRED")
        except Exception:
            blockers.append("AUTHORITY_EXPIRY_INVALID")

    events = [dict(row) for row in list(state.get("events") or []) if isinstance(row, Mapping)]
    active = _active_events(
        events,
        now=current,
        window_seconds=policy["window_seconds"],
    )
    grant_uses = sum(row.get("grant_id") == grant for row in active)
    cap_uses = sum(row.get("capability") == cap for row in active)
    distinct_caps = {row.get("capability") for row in active if row.get("capability")}
    distinct_resources = {row.get("resource_ref") for row in active if row.get("resource_ref")}
    used_units = sum(int(row.get("units") or 0) for row in active)
    prospective_units = policy["capability_units"].get(cap, 0)

    if len(active) + 1 > policy["max_events"]:
        blockers.append("CUMULATIVE_EVENT_BUDGET_EXCEEDED")
    if grant_uses + 1 > policy["max_uses_per_grant"]:
        blockers.append("GRANT_REUSE_BUDGET_EXCEEDED")
    if cap in policy["capability_limits"] and cap_uses + 1 > policy["capability_limits"][cap]:
        blockers.append("CAPABILITY_USAGE_BUDGET_EXCEEDED")
    if cap and cap not in distinct_caps and len(distinct_caps) + 1 > policy["max_distinct_capabilities"]:
        blockers.append("DISTINCT_CAPABILITY_BUDGET_EXCEEDED")
    if resource and resource not in distinct_resources and len(distinct_resources) + 1 > policy["max_distinct_resources"]:
        blockers.append("DISTINCT_RESOURCE_BUDGET_EXCEEDED")
    if used_units + prospective_units > policy["max_units"]:
        blockers.append("CUMULATIVE_AUTHORITY_UNITS_EXCEEDED")

    return {
        "schema": SCHEMA,
        "state": "WITHIN_BUDGET" if not blockers else "BLOCK",
        "blockers": sorted(set(blockers)),
        "within_budget": not blockers,
        "subject_id": scope["subject_id"],
        "tenant_id": scope["tenant_id"],
        "workspace_id": scope["workspace_id"],
        "capability": cap,
        "resource_ref": resource,
        "grant_id": grant,
        "role_id": role,
        "prospective_units": prospective_units,
        "active_events": len(active),
        "used_units": used_units,
        "window_seconds": policy["window_seconds"],
        "sensitive": sensitive,
        "human_approval_verified": approval_verified is True and bool(approval),
        "cryptographic_authority_verified": verification.get("authority_verified") is True,
        "budget_grants_authority": False,
        "execution_allowed": False,
        "requires_downstream_execution_gate": True,
        "external_action_executed": False,
    }


def record_authority_intent(
    budget: Mapping[str, Any] | None,
    *,
    trusted_context: Mapping[str, Any] | None,
    capability: Any,
    resource_ref: Any,
    grant_id: Any,
    authority_verification: Mapping[str, Any] | None,
    approval_digest: Any = "",
    approval_verified: Any = False,
    role_id: Any = "",
    now: Any,
) -> dict[str, Any]:
    decision = evaluate_authority_intent(
        budget,
        trusted_context=trusted_context,
        capability=capability,
        resource_ref=resource_ref,
        grant_id=grant_id,
        authority_verification=authority_verification,
        approval_digest=approval_digest,
        approval_verified=approval_verified,
        role_id=role_id,
        now=now,
    )
    if decision["within_budget"] is not True:
        return {
            **decision,
            "recorded": False,
            "budget": deepcopy(dict(budget or {})),
        }

    state = deepcopy(dict(budget or {}))
    scope = _scope(trusted_context)
    policy = state["policy"]
    current = _aware(now)
    cap = decision["capability"]
    grant = decision["grant_id"]
    resource = decision["resource_ref"]
    approval = _clean(approval_digest, 200)
    role = _clean(role_id, 80).casefold()
    verification = dict(authority_verification or {})
    event_seed = {
        "scope_digest": scope["scope_digest"],
        "grant_id": grant,
        "capability": cap,
        "resource_ref": resource,
        "approval_digest": approval,
        "used_at": current.isoformat(),
    }
    event_id = "AUT-" + _digest(event_seed)[:24].upper()
    for row in list(state.get("events") or []):
        if not isinstance(row, Mapping) or row.get("event_id") != event_id:
            continue
        same = (
            row.get("grant_id") == grant
            and row.get("capability") == cap
            and row.get("resource_ref") == resource
            and row.get("approval_digest") == approval
        )
        if same:
            return {
                **decision,
                "state": "IDEMPOTENT",
                "recorded": False,
                "event": deepcopy(dict(row)),
                "budget": state,
            }
        return {
            **decision,
            "state": "BLOCK",
            "blockers": ["AUTHORITY_EVENT_REPLAY_CONFLICT"],
            "within_budget": False,
            "recorded": False,
            "budget": state,
        }

    event = {
        "event_id": event_id,
        **scope,
        "policy_id": policy["policy_id"],
        "policy_version": policy["policy_version"],
        "grant_id": grant,
        "statement_id": _clean(verification.get("statement_id"), 200),
        "capability": cap,
        "resource_ref": resource,
        "role_id": role,
        "units": policy["capability_units"][cap],
        "approval_digest": approval,
        "approval_verified": approval_verified is True and bool(approval),
        "authority_verified": verification.get("authority_verified") is True,
        "used_at": current.isoformat(),
        "execution_allowed": False,
        "budget_grants_authority": False,
        "external_action_executed": False,
    }
    events = [
        dict(row)
        for row in list(state.get("events") or [])
        if isinstance(row, Mapping)
    ]
    if len(events) >= MAX_EVENTS:
        # Never silently roll away audit history merely to accept more authority.
        return {
            **decision,
            "state": "BLOCK",
            "blockers": ["BUDGET_EVENT_STORAGE_CAPACITY_REACHED"],
            "within_budget": False,
            "recorded": False,
            "budget": state,
        }
    state["events"] = [*events, event]
    state["digest"] = _state_digest(state)
    return {
        **decision,
        "state": "RECORDED",
        "recorded": True,
        "event": deepcopy(event),
        "budget": state,
        "execution_allowed": False,
        "budget_grants_authority": False,
    }


def authority_budget_summary(
    budget: Mapping[str, Any] | None,
    *,
    trusted_context: Mapping[str, Any] | None,
    now: Any,
) -> dict[str, Any]:
    audit = validate_authority_budget(budget, trusted_context=trusted_context)
    if audit["valid"] is not True:
        return {
            "schema": SCHEMA,
            "state": "BLOCK",
            "blockers": audit["blockers"],
            "execution_allowed": False,
            "budget_grants_authority": False,
        }
    state = dict(budget or {})
    policy = state["policy"]
    current = _aware(now)
    active = _active_events(
        [dict(row) for row in state["events"] if isinstance(row, Mapping)],
        now=current,
        window_seconds=policy["window_seconds"],
    )
    return {
        "schema": SCHEMA,
        "state": "CONFIRMED",
        "active_events": len(active),
        "stored_events": len(state["events"]),
        "used_units": sum(int(row.get("units") or 0) for row in active),
        "max_units": policy["max_units"],
        "distinct_capabilities": len({row.get("capability") for row in active}),
        "distinct_resources": len({row.get("resource_ref") for row in active}),
        "window_seconds": policy["window_seconds"],
        "policy_id": policy["policy_id"],
        "policy_version": policy["policy_version"],
        "budget_grants_authority": False,
        "execution_allowed": False,
        "external_action_executed": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "MAX_EVENTS",
    "normalize_authority_budget_policy",
    "default_authority_budget",
    "validate_authority_budget",
    "evaluate_authority_intent",
    "record_authority_intent",
    "authority_budget_summary",
]
