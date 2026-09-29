"""AION Global/Durable Worker V1.

This module adds a GitHub-runtime-backed global worker control plane inside the
existing Checkpoint Mestre. It is disabled by default and only runs when both:
1) ATLASQUANT_AION_GLOBAL_WORKER_ENABLED is explicitly enabled by the host; and
2) an authenticated ADMIN has staged and persisted an ARMED delegation.

The only automatic external write allowed here is operational runtime-data
persistence to the dedicated AtlasQuant runtime branch. Trading, payments,
publishing, deploys, provider calls and shell/subprocess execution remain
blocked by the executor contract.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import argparse
import base64
import json
import os
import re
import secrets
from typing import Any, Mapping

import requests

from atlasquant_aion_background_executor import (
    _execute_due_local_work_authorized,
    _occurrence_key,
)
from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_intelligence.evidence import digest, safe_text, utc
from atlasquant_aion_core_runtime_bridge import authenticated_context
from atlasquant_aion_core_voice_automation import CheckpointAutomationAdapter
from atlasquant_aion_global_worker_arming import validate_global_worker_arming_approval
from atlasquant_aion_memory import (
    MAX_RUNTIME_BYTES,
    RuntimeConfig,
    checkpoint_integrity_report,
    checkpoint_source_digest,
    config_from_mapping,
    ensure_operating_checkpoint,
    load_runtime_checkpoint,
    _runtime_write_receipt,
)
from atlasquant_runtime_store import require_runtime_branch


SCHEMA = "ATLASQUANT_AION_GLOBAL_DURABLE_WORKER_V1"
GLOBAL_WORKER_NAMESPACE = "aion_global_worker_v1"
GLOBAL_WORKER_SCHEMA = "AION_GLOBAL_WORKER_CHECKPOINT_V1"
GLOBAL_WORKER_STATES = ("DISABLED", "ARMED", "PAUSED", "KILLED")
GLOBAL_WORKER_CAPABILITIES = frozenset({
    "ADMINISTRATION",
    "MEMORY",
    "RESEARCH",
    "CONTENT",
    "OBSERVABILITY",
})
DEFAULT_LEASE_SECONDS = 1200
MIN_LEASE_SECONDS = 300
MAX_LEASE_SECONDS = 1800
DEFAULT_MAX_JOBS = 5
MAX_JOBS = 20
SERVICE_PRINCIPAL = "aion-global-worker"


def global_worker_feature_enabled(value: Any | None = None) -> bool:
    raw = (
        os.getenv("ATLASQUANT_AION_GLOBAL_WORKER_ENABLED", "")
        if value is None
        else value
    )
    return str(raw or "").strip().casefold() in {"1", "true", "yes", "on"}


def _scope_payload(context) -> list[str]:
    return json.loads(context.key)


def _bundle_digest(bundle: Mapping[str, Any]) -> str:
    raw = dict(bundle or {})
    raw.pop("digest", None)
    return digest(raw)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return utc(parsed)
    except Exception:
        return None


def _exact_int(value: Any, *, minimum: int, maximum: int, name: str) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("invalid " + name)
    return value


def _validated_runtime_id(value: Any) -> str:
    if type(value) is not str:
        raise ValueError("GLOBAL_RUNTIME_ID_REQUIRED")
    runtime = value.strip()
    if not runtime or len(runtime) > 160:
        raise ValueError("GLOBAL_RUNTIME_ID_REQUIRED")
    normalized = safe_text(runtime, 160)
    if not normalized or normalized != runtime:
        raise ValueError("GLOBAL_RUNTIME_ID_REQUIRED")
    return normalized


def _global_work_intent(
    context,
    checkpoint: Mapping[str, Any],
    *,
    max_jobs: int,
    now: datetime,
) -> dict[str, Any]:
    jobs = _exact_int(
        max_jobs,
        minimum=1,
        maximum=MAX_JOBS,
        name="global worker work intent max jobs",
    )
    current = utc(now)
    scheduler = CheckpointAutomationAdapter(context, checkpoint).snapshot(current)
    due = [
        row for row in list(scheduler.get("schedules") or [])
        if isinstance(row, Mapping) and row.get("due") is True
    ]
    due.sort(key=lambda row: (
        str(row.get("due_at") or ""),
        str(row.get("schedule_id") or ""),
    ))
    occurrences = []
    for row in due[:jobs]:
        due_at = str(row.get("due_at") or "")
        schedule_id = safe_text(str(row.get("schedule_id") or ""), 120)
        capability = safe_text(
            str(row.get("capability") or "").strip().upper(),
            80,
        )
        if not schedule_id or _parse_iso(due_at) is None:
            raise ValueError("invalid global work intent occurrence")
        occurrences.append({
            "schedule_id": schedule_id,
            "occurrence_key": _occurrence_key(context, row, due_at),
            "due_at": due_at,
            "capability": capability,
        })
    payload = {
        "as_of": current.isoformat(),
        "count": len(occurrences),
        "occurrences": occurrences,
    }
    return {
        **payload,
        "digest": digest(payload),
        "executes_action": False,
    }


def _empty_inflight_tick() -> dict[str, Any]:
    return {}


def _normalize_inflight_tick(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    item = dict(raw or {})
    if not item:
        return _empty_inflight_tick()
    if str(item.get("state") or "") != "CLAIMED":
        raise ValueError("invalid global inflight tick state")
    owner = _validated_runtime_id(item.get("owner"))
    token = safe_text(str(item.get("lease_token") or ""), 180)
    fence = item.get("fencing_token")
    claimed_at = str(item.get("claimed_at") or "")
    intent_id = str(item.get("intent_id") or "").strip()
    if not token:
        raise ValueError("invalid global inflight lease token")
    if type(fence) is not int or fence < 1:
        raise ValueError("invalid global inflight fencing token")
    if _parse_iso(claimed_at) is None:
        raise ValueError("invalid global inflight timestamp")

    raw_occurrences = item.get("work_occurrences", [])
    if not isinstance(raw_occurrences, list) or len(raw_occurrences) > MAX_JOBS:
        raise ValueError("invalid global inflight work occurrences")
    occurrences = []
    seen = set()
    for raw_row in raw_occurrences:
        if not isinstance(raw_row, Mapping):
            raise ValueError("invalid global inflight work occurrence")
        row = dict(raw_row)
        schedule_id = safe_text(str(row.get("schedule_id") or ""), 120)
        occurrence_key = str(row.get("occurrence_key") or "").strip().lower()
        due_at = str(row.get("due_at") or "")
        capability = safe_text(
            str(row.get("capability") or "").strip().upper(),
            80,
        )
        if (
            not schedule_id
            or re.fullmatch(r"[0-9a-f]{64}", occurrence_key) is None
            or _parse_iso(due_at) is None
            or occurrence_key in seen
        ):
            raise ValueError("invalid global inflight work occurrence")
        seen.add(occurrence_key)
        occurrences.append({
            "schedule_id": schedule_id,
            "occurrence_key": occurrence_key,
            "due_at": due_at,
            "capability": capability,
        })

    work_count = item.get("work_intent_count", len(occurrences))
    work_digest = str(item.get("work_intent_digest") or "").strip().lower()
    work_as_of = str(item.get("work_intent_as_of") or "")
    if type(work_count) is not int or work_count != len(occurrences):
        raise ValueError("invalid global inflight work count")
    if work_count:
        if _parse_iso(work_as_of) is None:
            raise ValueError("invalid global inflight work timestamp")
        expected_work_digest = digest({
            "as_of": work_as_of,
            "count": work_count,
            "occurrences": occurrences,
        })
        if work_digest != expected_work_digest:
            raise ValueError("invalid global inflight work digest")
    elif work_digest or work_as_of:
        if not work_digest or _parse_iso(work_as_of) is None:
            raise ValueError("invalid empty global inflight work intent")
        expected_work_digest = digest({
            "as_of": work_as_of,
            "count": 0,
            "occurrences": [],
        })
        if work_digest != expected_work_digest:
            raise ValueError("invalid global inflight work digest")

    expected_intent = digest({
        "owner": owner,
        "lease_token": token,
        "fencing_token": fence,
        "claimed_at": claimed_at,
        "work_intent_digest": work_digest,
    })
    if not intent_id or intent_id != expected_intent:
        raise ValueError("invalid global inflight intent")
    return {
        "state": "CLAIMED",
        "owner": owner,
        "lease_token": token,
        "fencing_token": fence,
        "claimed_at": claimed_at,
        "intent_id": intent_id,
        "work_intent_digest": work_digest,
        "work_intent_count": work_count,
        "work_intent_as_of": work_as_of,
        "work_occurrences": occurrences,
    }


def _empty_lease() -> dict[str, Any]:
    return {
        "owner": "",
        "token": "",
        "fencing_token": 0,
        "acquired_at": "",
        "heartbeat_at": "",
        "expires_at": "",
    }


def _empty_stats() -> dict[str, Any]:
    return {
        "ticks": 0,
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "blocked": 0,
        "lease_conflicts": 0,
        "checkpoint_conflicts": 0,
        "crash_recoveries": 0,
        "last_tick_at": "",
        "last_heartbeat_at": "",
        "last_status": "NEVER",
        "last_runtime_id": "",
    }


def _normalize_stats(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    source = dict(raw or {})
    out = _empty_stats()
    for key in (
        "ticks",
        "processed",
        "succeeded",
        "failed",
        "blocked",
        "lease_conflicts",
        "checkpoint_conflicts",
        "crash_recoveries",
    ):
        value = source.get(key, 0)
        if type(value) is int and value >= 0:
            out[key] = value
    for key in ("last_tick_at", "last_heartbeat_at"):
        value = str(source.get(key) or "")
        if value and _parse_iso(value) is None:
            raise ValueError("invalid global worker timestamp")
        out[key] = value
    out["last_status"] = safe_text(
        str(source.get("last_status") or "NEVER"), 120
    )
    runtime_id = str(source.get("last_runtime_id") or "").strip()
    out["last_runtime_id"] = safe_text(runtime_id, 160) if runtime_id else ""
    return out


def _normalize_lease(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    item = dict(raw or {})
    if not any(
        str(item.get(key) or "")
        for key in ("owner", "token", "acquired_at", "heartbeat_at", "expires_at")
    ):
        return _empty_lease()
    owner = safe_text(str(item.get("owner") or ""), 160)
    token = safe_text(str(item.get("token") or ""), 180)
    fence = item.get("fencing_token", 0)
    if type(fence) is not int or fence < 1:
        raise ValueError("invalid global fencing token")
    times = {}
    for key in ("acquired_at", "heartbeat_at", "expires_at"):
        text = str(item.get(key) or "")
        if _parse_iso(text) is None:
            raise ValueError("invalid global lease timestamp")
        times[key] = text
    if not owner or not token:
        raise ValueError("incomplete global worker lease")
    return {
        "owner": owner,
        "token": token,
        "fencing_token": fence,
        **times,
    }


def _delegation_from_access(access: Mapping[str, Any], context) -> dict[str, Any]:
    session = access.get("session") if isinstance(access, Mapping) else None
    if not isinstance(session, Mapping):
        raise ValueError("AUTHENTICATED_ADMIN_SESSION_REQUIRED")
    username = str(session.get("username") or "").strip().lower()
    fingerprint = str(session.get("credential_fingerprint") or "").strip().lower()
    if not username or not fingerprint:
        raise ValueError("AUTHENTICATED_IDENTITY_REQUIRED")
    material = fingerprint[:48]
    if len(material) < 8:
        raise ValueError("INVALID_SCOPE_FINGERPRINT")
    delegated = {
        "scope": _scope_payload(context),
        "username": username,
        "fingerprint_scope_material": material,
        "actor_id": context.actor_id,
        "role": "ADMIN",
    }
    verify = _delegated_access(delegated)
    if authenticated_context(verify, Domain.ADMIN).key != context.key:
        raise ValueError("DELEGATED_SCOPE_RECONSTRUCTION_FAILED")
    return delegated


def _delegated_access(delegation: Mapping[str, Any]) -> dict[str, Any]:
    username = safe_text(str(delegation.get("username") or ""), 120).lower()
    material = safe_text(
        str(delegation.get("fingerprint_scope_material") or ""), 64
    ).lower()
    if not username or len(material) < 8:
        raise ValueError("INVALID_GLOBAL_DELEGATION")
    return {
        "allowed": True,
        "mode": "AUTHENTICATED",
        "role": "ADMIN",
        "session": {
            "username": username,
            "role": "ADMIN",
            "credential_fingerprint": material,
            "permissions": ["app:read", "admin:read", "aion:admin"],
            "principal_type": "DELEGATED_SERVICE_SCOPE",
        },
    }


def _default_state() -> dict[str, Any]:
    state = {
        "schema": GLOBAL_WORKER_SCHEMA,
        "revision": 0,
        "state": "DISABLED",
        "kill_switch": True,
        "delegation": {},
        "arm_digest": "",
        "arming_plan_digest": "",
        "arming_approval_digest": "",
        "arming_approval_expires_at": "",
        "armed_at": "",
        "allowed_capabilities": sorted(GLOBAL_WORKER_CAPABILITIES),
        "resource_budgets": {
            "max_jobs_per_tick": DEFAULT_MAX_JOBS,
            "max_runtime_checkpoint_writes_per_tick": 2,
            "provider_calls_per_tick": 0,
            "paid_service_calls_per_tick": 0,
            "publications_per_tick": 0,
            "payments_per_tick": 0,
            "deploys_per_tick": 0,
            "merges_per_tick": 0,
            "subprocess_calls_per_tick": 0,
            "market_orders_per_tick": 0,
            "real_trading_enabled": False,
        },
        "max_jobs": DEFAULT_MAX_JOBS,
        "lease_seconds": DEFAULT_LEASE_SECONDS,
        "fencing_counter": 0,
        "lease": _empty_lease(),
        "inflight_tick": _empty_inflight_tick(),
        "stats": _empty_stats(),
        "runner": {
            "mode": "GITHUB_ACTIONS_EXISTING_AUTOPILOT_PULSE",
            "feature_flag_required": "ATLASQUANT_AION_GLOBAL_WORKER_ENABLED",
            "schedule_reused": "7,37 * * * *",
            "additional_cron_created": False,
        },
        "automatic_runtime_checkpoint_persistence": True,
        "automatic_external_business_actions": False,
        "provider_calls_allowed": False,
        "publication_allowed": False,
        "payment_allowed": False,
        "deploy_allowed": False,
        "merge_allowed": False,
        "real_trading_enabled": False,
    }
    state["digest"] = _bundle_digest(state)
    return state


def global_worker_integrity(raw: Mapping[str, Any] | None) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        return {"state": "ABSENT", "stored": "", "expected": ""}
    if raw.get("schema") != GLOBAL_WORKER_SCHEMA:
        return {
            "state": "MISMATCH",
            "stored": str(raw.get("digest") or ""),
            "expected": GLOBAL_WORKER_SCHEMA,
        }
    supplied = str(raw.get("digest") or "").strip()
    expected = _bundle_digest(raw)
    return {
        "state": "MATCH" if supplied and supplied == expected else "MISMATCH",
        "stored": supplied,
        "expected": expected,
    }


def _normalize_state(raw: Mapping[str, Any]) -> dict[str, Any]:
    if global_worker_integrity(raw)["state"] != "MATCH":
        raise ValueError("GLOBAL_WORKER_CHECKPOINT_MISMATCH")
    state_name = str(raw.get("state") or "").strip().upper()
    if state_name not in GLOBAL_WORKER_STATES:
        raise ValueError("invalid global worker state")
    revision = raw.get("revision", 0)
    fence_counter = raw.get("fencing_counter", 0)
    if type(revision) is not int or revision < 0:
        raise ValueError("invalid global worker revision")
    if type(fence_counter) is not int or fence_counter < 0:
        raise ValueError("invalid global worker fencing counter")
    max_jobs = _exact_int(
        raw.get("max_jobs", DEFAULT_MAX_JOBS),
        minimum=1,
        maximum=MAX_JOBS,
        name="global worker max jobs",
    )
    lease_seconds = _exact_int(
        raw.get("lease_seconds", DEFAULT_LEASE_SECONDS),
        minimum=MIN_LEASE_SECONDS,
        maximum=MAX_LEASE_SECONDS,
        name="global worker lease",
    )
    delegation = (
        deepcopy(dict(raw.get("delegation")))
        if isinstance(raw.get("delegation"), Mapping)
        else {}
    )
    allowed_raw = raw.get("allowed_capabilities", [])
    if not isinstance(allowed_raw, list):
        raise ValueError("invalid global capability allowlist")
    allowed = frozenset(str(x).strip().upper() for x in allowed_raw)
    if not allowed or not allowed.issubset(GLOBAL_WORKER_CAPABILITIES):
        raise ValueError("invalid global capability allowlist")
    armed_at = str(raw.get("armed_at") or "")
    if armed_at and _parse_iso(armed_at) is None:
        raise ValueError("invalid global arming timestamp")
    state = {
        "schema": GLOBAL_WORKER_SCHEMA,
        "revision": revision,
        "state": state_name,
        "kill_switch": bool(raw.get("kill_switch", True)),
        "delegation": delegation,
        "arm_digest": str(raw.get("arm_digest") or ""),
        "arming_plan_digest": str(raw.get("arming_plan_digest") or ""),
        "arming_approval_digest": str(raw.get("arming_approval_digest") or ""),
        "arming_approval_expires_at": str(raw.get("arming_approval_expires_at") or ""),
        "armed_at": armed_at,
        "allowed_capabilities": sorted(allowed),
        "resource_budgets": deepcopy(dict(raw.get("resource_budgets") or {
            "max_jobs_per_tick": max_jobs,
            "max_runtime_checkpoint_writes_per_tick": 2,
            "provider_calls_per_tick": 0,
            "paid_service_calls_per_tick": 0,
            "publications_per_tick": 0,
            "payments_per_tick": 0,
            "deploys_per_tick": 0,
            "merges_per_tick": 0,
            "subprocess_calls_per_tick": 0,
            "market_orders_per_tick": 0,
            "real_trading_enabled": False,
        })),
        "max_jobs": max_jobs,
        "lease_seconds": lease_seconds,
        "fencing_counter": fence_counter,
        "lease": _normalize_lease(
            raw.get("lease") if isinstance(raw.get("lease"), Mapping) else {}
        ),
        "inflight_tick": _normalize_inflight_tick(
            raw.get("inflight_tick") if isinstance(raw.get("inflight_tick"), Mapping) else {}
        ),
        "stats": _normalize_stats(
            raw.get("stats") if isinstance(raw.get("stats"), Mapping) else {}
        ),
        "runner": deepcopy(dict(raw.get("runner") or {})),
        "automatic_runtime_checkpoint_persistence": True,
        "automatic_external_business_actions": False,
        "provider_calls_allowed": False,
        "publication_allowed": False,
        "payment_allowed": False,
        "deploy_allowed": False,
        "merge_allowed": False,
        "real_trading_enabled": False,
    }
    if state_name == "ARMED":
        if (
            state["kill_switch"]
            or not state["arm_digest"]
            or not state["armed_at"]
            or not state["arming_plan_digest"]
            or not state["arming_approval_digest"]
            or _parse_iso(state["arming_approval_expires_at"]) is None
        ):
            raise ValueError("invalid armed global worker state")
        inflight = state["inflight_tick"]
        lease = state["lease"]
        if inflight and (
            not lease["owner"]
            or inflight["owner"] != lease["owner"]
            or inflight["lease_token"] != lease["token"]
            or inflight["fencing_token"] != lease["fencing_token"]
        ):
            raise ValueError("GLOBAL_INFLIGHT_LEASE_MISMATCH")
        budgets = state["resource_budgets"]
        zero_budget_fields = (
            "provider_calls_per_tick",
            "paid_service_calls_per_tick",
            "publications_per_tick",
            "payments_per_tick",
            "deploys_per_tick",
            "merges_per_tick",
            "subprocess_calls_per_tick",
            "market_orders_per_tick",
        )
        if (
            not isinstance(budgets, Mapping)
            or type(budgets.get("max_jobs_per_tick")) is not int
            or budgets.get("max_jobs_per_tick") != max_jobs
            or type(budgets.get("max_runtime_checkpoint_writes_per_tick")) is not int
            or budgets.get("max_runtime_checkpoint_writes_per_tick") != 2
            or any(
                type(budgets.get(key)) is not int or budgets.get(key) != 0
                for key in zero_budget_fields
            )
            or budgets.get("real_trading_enabled") is not False
        ):
            raise ValueError("invalid armed global worker resource budgets")
        access = _delegated_access(delegation)
        context = authenticated_context(access, Domain.ADMIN)
        if delegation.get("scope") != _scope_payload(context):
            raise ValueError("GLOBAL_DELEGATION_SCOPE_MISMATCH")
    if state_name != "ARMED" and state["inflight_tick"]:
        raise ValueError("GLOBAL_INFLIGHT_REQUIRES_ARMED_STATE")
    state["digest"] = _bundle_digest(state)
    return state


def _mutated(current_state: Mapping[str, Any], **changes: Any) -> dict[str, Any]:
    out = deepcopy(dict(current_state))
    out.update(changes)
    out["revision"] = int(out.get("revision") or 0) + 1
    out["digest"] = _bundle_digest(out)
    return out


def load_global_worker_state(
    checkpoint: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = dict(checkpoint or {})
    raw = payload.get(GLOBAL_WORKER_NAMESPACE)
    if raw is None:
        return _default_state(), {
            "state": "EMPTY",
            "reason": "GLOBAL_WORKER_NAMESPACE_ABSENT",
        }
    if not isinstance(raw, Mapping):
        raise ValueError("GLOBAL_WORKER_CHECKPOINT_MISMATCH")
    state = _normalize_state(raw)
    return state, {
        "state": "CONNECTED",
        "reason": "",
        "revision": state["revision"],
    }


def attach_global_worker_state(
    checkpoint: Mapping[str, Any],
    state: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = _normalize_state(state)
    out = deepcopy(dict(checkpoint or {}))
    out[GLOBAL_WORKER_NAMESPACE] = normalized
    return out


def stage_arm_global_worker(
    access: Mapping[str, Any] | None,
    checkpoint: Mapping[str, Any],
    *,
    confirmation: bool,
    arming_approval: Mapping[str, Any] | None = None,
    max_jobs: int = DEFAULT_MAX_JOBS,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    if confirmation is not True:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "EXPLICIT_ADMIN_GLOBAL_ARMING_REQUIRED",
            "checkpoint": dict(checkpoint or {}),
            "external_persisted": False,
        }
    current = utc(now or _now())
    context = authenticated_context(access, Domain.ADMIN)
    if context.role != "ADMIN":
        raise ValueError("ADMIN_REQUIRED")
    max_jobs = _exact_int(
        max_jobs, minimum=1, maximum=MAX_JOBS, name="global worker max jobs"
    )
    lease_seconds = _exact_int(
        lease_seconds,
        minimum=MIN_LEASE_SECONDS,
        maximum=MAX_LEASE_SECONDS,
        name="global worker lease",
    )
    approval = validate_global_worker_arming_approval(
        access,
        checkpoint,
        arming_approval,
        max_jobs=max_jobs,
        lease_seconds=lease_seconds,
        allowed_capabilities=GLOBAL_WORKER_CAPABILITIES,
        now=current,
    )
    if approval.get("state") != "APPROVED":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": str(approval.get("reason") or "VALID_ARMING_APPROVAL_REQUIRED"),
            "checkpoint": dict(checkpoint or {}),
            "requires_checkpoint_save": False,
            "external_persisted": False,
            "runner_feature_flag_required": True,
            "automatic_external_business_actions": False,
        }
    state, _ = load_global_worker_state(checkpoint)
    delegation = _delegation_from_access(access, context)
    arm_digest = digest({
        "scope": context.key,
        "actor": context.actor_id,
        "armed_at": current.isoformat(),
        "max_jobs": max_jobs,
        "lease_seconds": lease_seconds,
        "allowed_capabilities": sorted(GLOBAL_WORKER_CAPABILITIES),
        "arming_plan_digest": str(approval.get("plan_digest") or ""),
        "arming_approval_digest": str(approval.get("approval_digest") or ""),
    })
    state = _mutated(
        state,
        state="ARMED",
        kill_switch=False,
        delegation=delegation,
        arm_digest=arm_digest,
        arming_plan_digest=str(approval.get("plan_digest") or ""),
        arming_approval_digest=str(approval.get("approval_digest") or ""),
        arming_approval_expires_at=str(approval.get("expires_at") or ""),
        armed_at=current.isoformat(),
        allowed_capabilities=sorted(GLOBAL_WORKER_CAPABILITIES),
        resource_budgets=deepcopy(dict(approval.get("budgets") or {})),
        max_jobs=max_jobs,
        lease_seconds=lease_seconds,
        lease=_empty_lease(),
        inflight_tick=_empty_inflight_tick(),
    )
    return {
        "schema": SCHEMA,
        "status": "STAGED_ARMED",
        "checkpoint": attach_global_worker_state(checkpoint, state),
        "worker": state,
        "requires_checkpoint_save": True,
        "external_persisted": False,
        "runner_feature_flag_required": True,
        "arming_plan_digest": str(approval.get("plan_digest") or ""),
        "arming_approval_digest": str(approval.get("approval_digest") or ""),
        "arming_approval_expires_at": str(approval.get("expires_at") or ""),
        "automatic_external_business_actions": False,
    }


def stage_pause_global_worker(
    access: Mapping[str, Any] | None,
    checkpoint: Mapping[str, Any],
    *,
    confirmation: bool,
) -> dict[str, Any]:
    if confirmation is not True:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "checkpoint": dict(checkpoint or {}),
            "reason": "EXPLICIT_ADMIN_CONFIRMATION_REQUIRED",
        }
    context = authenticated_context(access, Domain.ADMIN)
    state, _ = load_global_worker_state(checkpoint)
    if state["state"] == "ARMED":
        delegated = _delegated_access(state["delegation"])
        if authenticated_context(delegated, Domain.ADMIN).key != context.key:
            raise ValueError("GLOBAL_WORKER_CONTEXT_MISMATCH")
    state = _mutated(
        state,
        state="PAUSED",
        kill_switch=False,
        lease=_empty_lease(),
        inflight_tick=_empty_inflight_tick(),
    )
    return {
        "schema": SCHEMA,
        "status": "STAGED_PAUSED",
        "checkpoint": attach_global_worker_state(checkpoint, state),
        "requires_checkpoint_save": True,
        "external_persisted": False,
    }


def stage_kill_global_worker(
    access: Mapping[str, Any] | None,
    checkpoint: Mapping[str, Any],
    *,
    confirmation: bool,
) -> dict[str, Any]:
    if confirmation is not True:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "checkpoint": dict(checkpoint or {}),
            "reason": "EXPLICIT_ADMIN_CONFIRMATION_REQUIRED",
        }
    context = authenticated_context(access, Domain.ADMIN)
    state, _ = load_global_worker_state(checkpoint)
    if state["delegation"]:
        delegated = _delegated_access(state["delegation"])
        if authenticated_context(delegated, Domain.ADMIN).key != context.key:
            raise ValueError("GLOBAL_WORKER_CONTEXT_MISMATCH")
    state = _mutated(
        state,
        state="KILLED",
        kill_switch=True,
        lease=_empty_lease(),
        inflight_tick=_empty_inflight_tick(),
    )
    return {
        "schema": SCHEMA,
        "status": "STAGED_KILLED",
        "checkpoint": attach_global_worker_state(checkpoint, state),
        "requires_checkpoint_save": True,
        "external_persisted": False,
    }


def global_worker_snapshot(
    access: Mapping[str, Any] | None,
    checkpoint: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = utc(now or _now())
    context = authenticated_context(access, Domain.ADMIN)
    state, status = load_global_worker_state(checkpoint)
    delegated_scope_matches = False
    if state["delegation"]:
        try:
            delegated = _delegated_access(state["delegation"])
            delegated_scope_matches = (
                authenticated_context(delegated, Domain.ADMIN).key == context.key
            )
        except Exception:
            delegated_scope_matches = False
    if state["delegation"] and not delegated_scope_matches:
        return {
            "schema": SCHEMA,
            "status": "CONTEXT_ISOLATED",
            "state": "UNKNOWN",
            "kill_switch": True,
            "revision": 0,
            "delegated_actor": "",
            "delegated_scope_matches": False,
            "allowed_capabilities": [],
            "max_jobs": 0,
            "lease_seconds": 0,
            "fencing_counter": 0,
            "lease_owner": "",
            "lease_fencing_token": 0,
            "lease_active": False,
            "lease_expires_at": "",
            "inflight_reconciliation_required": False,
            "inflight_owner": "",
            "inflight_fencing_token": 0,
            "inflight_since": "",
            "inflight_work_intent_digest": "",
            "inflight_work_intent_count": 0,
            "inflight_work_occurrences": [],
            "stats": {},
            "runner_mode": "UNKNOWN",
            "runner_feature_flag_required": True,
            "feature_flag_observed_here": global_worker_feature_enabled(),
            "additional_cron_created": False,
            "automatic_runtime_checkpoint_persistence": False,
            "automatic_external_business_actions": False,
            "provider_calls_allowed": False,
            "publication_allowed": False,
            "payment_allowed": False,
            "deploy_allowed": False,
            "merge_allowed": False,
            "real_trading_enabled": False,
        }
    lease = state["lease"]
    expires = _parse_iso(lease.get("expires_at"))
    return {
        "schema": SCHEMA,
        "status": status["state"],
        "state": state["state"],
        "kill_switch": state["kill_switch"],
        "revision": state["revision"],
        "delegated_actor": str(state["delegation"].get("actor_id") or ""),
        "delegated_scope_matches": delegated_scope_matches,
        "allowed_capabilities": list(state["allowed_capabilities"]),
        "max_jobs": state["max_jobs"],
        "lease_seconds": state["lease_seconds"],
        "fencing_counter": state["fencing_counter"],
        "lease_owner": lease["owner"],
        "lease_fencing_token": lease["fencing_token"],
        "lease_active": bool(expires and expires > current),
        "lease_expires_at": lease["expires_at"],
        "inflight_reconciliation_required": bool(state["inflight_tick"]),
        "inflight_owner": str(state["inflight_tick"].get("owner") or ""),
        "inflight_fencing_token": int(state["inflight_tick"].get("fencing_token") or 0),
        "inflight_since": str(state["inflight_tick"].get("claimed_at") or ""),
        "inflight_work_intent_digest": str(state["inflight_tick"].get("work_intent_digest") or ""),
        "inflight_work_intent_count": int(state["inflight_tick"].get("work_intent_count") or 0),
        "inflight_work_occurrences": deepcopy(list(state["inflight_tick"].get("work_occurrences") or [])),
        "stats": deepcopy(state["stats"]),
        "runner_mode": str(state["runner"].get("mode") or ""),
        "runner_feature_flag_required": True,
        "feature_flag_observed_here": global_worker_feature_enabled(),
        "additional_cron_created": False,
        "automatic_runtime_checkpoint_persistence": True,
        "automatic_external_business_actions": False,
        "provider_calls_allowed": False,
        "publication_allowed": False,
        "payment_allowed": False,
        "deploy_allowed": False,
        "merge_allowed": False,
        "real_trading_enabled": False,
    }


def _contents_url(cfg: RuntimeConfig) -> str:
    return f"https://api.github.com/repos/{cfg.repo}/contents/{cfg.path}"


def _headers(token: str) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    return headers


def _persist_runtime_checkpoint_cas(
    checkpoint: Mapping[str, Any],
    config: RuntimeConfig,
    *,
    expected_sha: str,
    operation: str,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """Narrow automatic writer used only by an already-authorized global tick."""
    require_runtime_branch(config.branch)
    if not config.write_ready or not str(expected_sha or "").strip():
        return {
            "schema": SCHEMA,
            "status": "UNAVAILABLE",
            "saved": False,
            "verified": False,
            "reason": "Global runtime CAS write prerequisites unavailable.",
        }
    payload = ensure_operating_checkpoint(checkpoint)
    payload = deepcopy(payload)
    payload["updated_at"] = utc(_now()).isoformat()
    if isinstance(payload.get("operating"), dict):
        payload["operating"]["dirty"] = False
    integrity = checkpoint_integrity_report(payload)
    if str(integrity.get("state") or "") in {"MISMATCH", "UNKNOWN"}:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "saved": False,
            "verified": False,
            "reason": "Checkpoint integrity does not permit global CAS persistence.",
            "integrity": integrity,
        }
    expected_digest = checkpoint_source_digest(payload)
    write_receipt = _runtime_write_receipt(
        config,
        expected_sha=str(expected_sha or "").strip(),
        expected_digest=expected_digest,
    )
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    if len(raw) > MAX_RUNTIME_BYTES:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "saved": False,
            "verified": False,
            "reason": "Checkpoint exceeds size limit.",
        }
    body = {
        "message": "AION Global Worker: " + safe_text(operation, 120),
        "content": base64.b64encode(raw).decode("ascii"),
        "branch": config.branch,
        "sha": str(expected_sha).strip(),
    }
    write_attempted = False
    try:
        write_attempted = True
        response = requests.put(
            _contents_url(config),
            headers=_headers(config.token),
            json=body,
            timeout=timeout,
        )
        if response.status_code in {409, 422}:
            write_receipt = _runtime_write_receipt(
                config,
                expected_sha=str(expected_sha or "").strip(),
                expected_digest=expected_digest,
                write_accepted=False,
            )
            return {
                "schema": SCHEMA,
                "status": "CONFLICT",
                "saved": False,
                "verified": False,
                "write_receipt": write_receipt,
                "reconciliation_required": False,
                "reason": "CAS conflict on runtime checkpoint.",
            }
        response.raise_for_status()
        obj = response.json()
        write_sha = str((obj.get("content") or {}).get("sha") or "").strip()
        write_receipt = _runtime_write_receipt(
            config,
            expected_sha=str(expected_sha or "").strip(),
            expected_digest=expected_digest,
            write_sha=write_sha,
            write_accepted=True,
        )
        verification = load_runtime_checkpoint(config, timeout=timeout)
        if verification.get("status") != "CONFIRMED":
            return {
                "schema": SCHEMA,
                "status": "UNVERIFIED",
                "saved": False,
                "verified": False,
                "write_accepted": True,
                "sha": write_sha,
                "write_receipt": write_receipt,
                "reconciliation_required": True,
                "reason": "CAS write accepted but read-after-write was not confirmed. Reconcile before any retry.",
            }
        actual = checkpoint_source_digest(verification.get("checkpoint"))
        read_sha = str(verification.get("sha") or "").strip()
        if not write_sha or write_sha != read_sha or actual != expected_digest:
            return {
                "schema": SCHEMA,
                "status": "CONFLICT",
                "saved": False,
                "verified": False,
                "write_accepted": True,
                "sha": read_sha or write_sha,
                "write_receipt": write_receipt,
                "reconciliation_required": True,
                "expected_digest": expected_digest,
                "actual_digest": actual,
                "reason": "Global runtime read-after-write diverged. Reconcile before any retry.",
            }
        return {
            "schema": SCHEMA,
            "status": "CONFIRMED",
            "saved": True,
            "verified": True,
            "sha": read_sha,
            "checkpoint": verification.get("checkpoint"),
            "digest": actual,
            "integrity": verification.get("integrity"),
            "write_receipt": write_receipt,
            "reconciliation_required": False,
            "automatic_runtime_checkpoint_persistence": True,
            "automatic_external_business_actions": False,
        }
    except Exception as exc:
        return {
            "schema": SCHEMA,
            "status": "ERROR",
            "saved": False,
            "verified": False,
            "write_outcome": "UNKNOWN" if write_attempted else "NOT_ATTEMPTED",
            "write_receipt": write_receipt,
            "reconciliation_required": bool(write_attempted),
            "reason": type(exc).__name__,
        }


def _lease_active(lease: Mapping[str, Any], now: datetime) -> bool:
    expires = _parse_iso(lease.get("expires_at"))
    return bool(expires and expires > utc(now))


def _claim_state(
    state: Mapping[str, Any],
    *,
    runtime_id: str,
    now: datetime,
    work_intent: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    current = utc(now)
    runtime = _validated_runtime_id(runtime_id)
    lease = _normalize_lease(
        state.get("lease") if isinstance(state.get("lease"), Mapping) else {}
    )
    active = _lease_active(lease, current)
    if active and lease["owner"] != runtime:
        return deepcopy(dict(state)), {
            "state": "LEASE_HELD",
            "owner": lease["owner"],
            "expires_at": lease["expires_at"],
            "fencing_token": lease["fencing_token"],
        }
    previous_owner = lease["owner"]
    reclaimed = bool(previous_owner and previous_owner != runtime and not active)
    stats = _normalize_stats(
        state.get("stats") if isinstance(state.get("stats"), Mapping) else {}
    )
    if reclaimed:
        stats["crash_recoveries"] += 1
    if active and previous_owner == runtime:
        fence = int(lease["fencing_token"])
        token = lease["token"]
        acquired_at = lease["acquired_at"]
    else:
        fence = int(state.get("fencing_counter") or 0) + 1
        token = secrets.token_urlsafe(24)
        acquired_at = current.isoformat()
    expires = current + timedelta(seconds=int(state["lease_seconds"]))
    claimed_at = current.isoformat()
    work = dict(work_intent or {})
    work_occurrences = [
        deepcopy(dict(row))
        for row in list(work.get("occurrences") or [])
        if isinstance(row, Mapping)
    ]
    work_digest = str(work.get("digest") or "").strip()
    work_as_of = str(work.get("as_of") or "")
    work_count = work.get("count", len(work_occurrences))
    if work:
        normalized_work = _normalize_inflight_tick({
            "state": "CLAIMED",
            "owner": runtime,
            "lease_token": token,
            "fencing_token": fence,
            "claimed_at": claimed_at,
            "work_intent_digest": work_digest,
            "work_intent_count": work_count,
            "work_intent_as_of": work_as_of,
            "work_occurrences": work_occurrences,
            "intent_id": digest({
                "owner": runtime,
                "lease_token": token,
                "fencing_token": fence,
                "claimed_at": claimed_at,
                "work_intent_digest": work_digest,
            }),
        })
        inflight_tick = normalized_work
    else:
        inflight_tick = {
            "state": "CLAIMED",
            "owner": runtime,
            "lease_token": token,
            "fencing_token": fence,
            "claimed_at": claimed_at,
            "work_intent_digest": "",
            "work_intent_count": 0,
            "work_intent_as_of": "",
            "work_occurrences": [],
        }
        inflight_tick["intent_id"] = digest({
            "owner": runtime,
            "lease_token": token,
            "fencing_token": fence,
            "claimed_at": claimed_at,
            "work_intent_digest": "",
        })
    stats["last_heartbeat_at"] = current.isoformat()
    stats["last_runtime_id"] = runtime
    claimed = _mutated(
        state,
        fencing_counter=max(int(state.get("fencing_counter") or 0), fence),
        lease={
            "owner": runtime,
            "token": token,
            "fencing_token": fence,
            "acquired_at": acquired_at,
            "heartbeat_at": current.isoformat(),
            "expires_at": expires.isoformat(),
        },
        inflight_tick=inflight_tick,
        stats=stats,
    )
    return claimed, {
        "state": "CLAIMED",
        "owner": runtime,
        "token": token,
        "fencing_token": fence,
        "expires_at": expires.isoformat(),
        "reclaimed": reclaimed,
    }


def _release_state(
    state: Mapping[str, Any],
    *,
    runtime_id: str,
    expected_lease_token: str,
    expected_fencing_token: int,
    now: datetime,
    batch: Mapping[str, Any],
    final_status: str,
) -> dict[str, Any]:
    lease = _normalize_lease(
        state.get("lease") if isinstance(state.get("lease"), Mapping) else {}
    )
    runtime = _validated_runtime_id(runtime_id)
    if lease["owner"] != runtime:
        raise ValueError("GLOBAL_LEASE_OWNER_MISMATCH")
    if type(expected_fencing_token) is not int or expected_fencing_token < 1:
        raise ValueError("GLOBAL_FENCE_TOKEN_REQUIRED")
    if not str(expected_lease_token or "").strip():
        raise ValueError("GLOBAL_LEASE_TOKEN_REQUIRED")
    if lease["token"] != str(expected_lease_token).strip():
        raise ValueError("GLOBAL_LEASE_TOKEN_MISMATCH")
    if lease["fencing_token"] != expected_fencing_token:
        raise ValueError("GLOBAL_FENCING_TOKEN_MISMATCH")
    inflight = _normalize_inflight_tick(
        state.get("inflight_tick") if isinstance(state.get("inflight_tick"), Mapping) else {}
    )
    if not inflight:
        raise ValueError("GLOBAL_INFLIGHT_TICK_REQUIRED")
    if inflight["owner"] != runtime:
        raise ValueError("GLOBAL_INFLIGHT_OWNER_MISMATCH")
    if inflight["lease_token"] != str(expected_lease_token).strip():
        raise ValueError("GLOBAL_INFLIGHT_TOKEN_MISMATCH")
    if inflight["fencing_token"] != expected_fencing_token:
        raise ValueError("GLOBAL_INFLIGHT_FENCE_MISMATCH")
    stats = _normalize_stats(
        state.get("stats") if isinstance(state.get("stats"), Mapping) else {}
    )
    stats["ticks"] += 1
    stats["processed"] += int(batch.get("processed") or 0)
    stats["succeeded"] += int(batch.get("succeeded") or 0)
    stats["failed"] += int(batch.get("failed") or 0)
    stats["blocked"] += int(batch.get("blocked") or 0)
    stats["last_tick_at"] = utc(now).isoformat()
    stats["last_heartbeat_at"] = utc(now).isoformat()
    stats["last_status"] = safe_text(final_status, 120)
    stats["last_runtime_id"] = runtime
    return _mutated(
        state,
        lease=_empty_lease(),
        inflight_tick=_empty_inflight_tick(),
        stats=stats,
    )


def _runtime_id(value: str | None = None) -> str:
    if value is not None:
        try:
            return _validated_runtime_id(value)
        except ValueError:
            return ""
    configured = str(os.getenv("AION_GLOBAL_WORKER_RUNTIME_ID", "")).strip()
    if configured:
        try:
            return _validated_runtime_id(configured)
        except ValueError:
            return ""
    run_id = str(os.getenv("GITHUB_RUN_ID", "")).strip()
    attempt = str(os.getenv("GITHUB_RUN_ATTEMPT", "")).strip()
    if run_id:
        generated = "gha-" + run_id + "-" + (attempt or "1")
        try:
            return _validated_runtime_id(generated)
        except ValueError:
            return ""
    return ""


def run_global_worker_once(
    *,
    config: RuntimeConfig | None = None,
    runtime_id: str | None = None,
    feature_enabled: bool | None = None,
    now: datetime | None = None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    enabled = (
        global_worker_feature_enabled()
        if feature_enabled is None
        else feature_enabled is True
    )
    if not enabled:
        return {
            "schema": SCHEMA,
            "status": "FEATURE_DISABLED",
            "network_called": False,
            "processed": 0,
            "automatic_runtime_checkpoint_persistence": False,
            "external_action_executed": False,
            "real_trading_enabled": False,
        }

    cfg = config or config_from_mapping()
    runtime = _runtime_id(runtime_id)
    if not runtime:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "GLOBAL_RUNTIME_ID_REQUIRED",
            "processed": 0,
            "network_called": False,
            "external_action_executed": False,
        }
    if not cfg.write_ready:
        return {
            "schema": SCHEMA,
            "status": "UNAVAILABLE",
            "reason": "Runtime write credential unavailable.",
            "processed": 0,
            "network_called": False,
            "external_action_executed": False,
        }

    current = utc(now or _now())
    loaded = load_runtime_checkpoint(cfg, timeout=timeout)
    if loaded.get("status") != "CONFIRMED":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "Runtime checkpoint not confirmed.",
            "runtime_status": loaded.get("status"),
            "processed": 0,
            "network_called": True,
            "external_action_executed": False,
        }
    checkpoint = ensure_operating_checkpoint(loaded.get("checkpoint"))
    state, state_status = load_global_worker_state(checkpoint)
    if state_status["state"] == "EMPTY":
        return {
            "schema": SCHEMA,
            "status": "NOT_ARMED",
            "reason": "Global worker state has not been persisted.",
            "processed": 0,
            "network_called": True,
            "external_action_executed": False,
        }
    if state["kill_switch"] or state["state"] == "KILLED":
        return {
            "schema": SCHEMA,
            "status": "KILLED",
            "processed": 0,
            "network_called": True,
            "external_action_executed": False,
        }
    if state["state"] != "ARMED":
        return {
            "schema": SCHEMA,
            "status": state["state"],
            "processed": 0,
            "network_called": True,
            "external_action_executed": False,
        }

    delegated_access = _delegated_access(state["delegation"])
    delegated_context = authenticated_context(delegated_access, Domain.ADMIN)
    if state["delegation"].get("scope") != _scope_payload(delegated_context):
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "GLOBAL_DELEGATION_SCOPE_MISMATCH",
            "processed": 0,
            "network_called": True,
            "external_action_executed": False,
        }

    if state["inflight_tick"]:
        return {
            "schema": SCHEMA,
            "status": "INFLIGHT_RECONCILIATION_REQUIRED",
            "reason": "Previous global tick has no confirmed terminal persistence.",
            "processed": 0,
            "inflight_owner": state["inflight_tick"]["owner"],
            "inflight_fencing_token": state["inflight_tick"]["fencing_token"],
            "inflight_since": state["inflight_tick"]["claimed_at"],
            "inflight_work_intent_digest": state["inflight_tick"]["work_intent_digest"],
            "inflight_work_intent_count": state["inflight_tick"]["work_intent_count"],
            "inflight_work_occurrences": deepcopy(state["inflight_tick"]["work_occurrences"]),
            "network_called": True,
            "reconciliation_required": True,
            "automatic_retry_allowed": False,
            "external_action_executed": False,
            "real_trading_enabled": False,
        }

    work_intent = _global_work_intent(
        delegated_context,
        checkpoint,
        max_jobs=int(state["max_jobs"]),
        now=current,
    )
    claimed, lease = _claim_state(
        state,
        runtime_id=runtime,
        now=current,
        work_intent=work_intent,
    )
    if lease["state"] == "LEASE_HELD":
        return {
            "schema": SCHEMA,
            "status": "LEASE_HELD",
            "processed": 0,
            "lease": lease,
            "network_called": True,
            "external_action_executed": False,
        }
    claim_checkpoint = attach_global_worker_state(checkpoint, claimed)
    claim_write = _persist_runtime_checkpoint_cas(
        claim_checkpoint,
        cfg,
        expected_sha=str(loaded.get("sha") or ""),
        operation="claim global lease",
        timeout=timeout,
    )
    if claim_write.get("status") != "CONFIRMED":
        return {
            "schema": SCHEMA,
            "status": "LEASE_CLAIM_" + str(claim_write.get("status") or "ERROR"),
            "processed": 0,
            "lease": lease,
            "network_called": True,
            "checkpoint_write": claim_write,
            "reconciliation_required": bool(claim_write.get("reconciliation_required")),
            "automatic_retry_allowed": False,
            "external_action_executed": False,
        }

    claimed_checkpoint = ensure_operating_checkpoint(claim_write.get("checkpoint"))
    claimed_state, _ = load_global_worker_state(claimed_checkpoint)
    active_lease = claimed_state["lease"]
    if (
        active_lease["owner"] != runtime
        or active_lease["token"] != lease["token"]
        or active_lease["fencing_token"] != lease["fencing_token"]
        or not _lease_active(active_lease, current)
    ):
        return {
            "schema": SCHEMA,
            "status": "FENCE_VERIFICATION_FAILED",
            "processed": 0,
            "network_called": True,
            "external_action_executed": False,
        }

    authorization_digest = digest({
        "mode": "GLOBAL_WORKER",
        "service_principal": SERVICE_PRINCIPAL,
        "delegated_scope": delegated_context.key,
        "arm_digest": claimed_state["arm_digest"],
        "runtime_id": runtime,
        "lease_token": active_lease["token"],
        "fencing_token": active_lease["fencing_token"],
        "lease_expires_at": active_lease["expires_at"],
    })
    batch = _execute_due_local_work_authorized(
        delegated_access,
        claimed_checkpoint,
        authorization_mode="GLOBAL_WORKER",
        authorization_digest=authorization_digest,
        execution_principal=SERVICE_PRINCIPAL + ":" + runtime,
        capability_allowlist=tuple(claimed_state["allowed_capabilities"]),
        max_jobs=int(claimed_state["max_jobs"]),
        now=current,
    )
    result_checkpoint = ensure_operating_checkpoint(
        batch.get("checkpoint") or claimed_checkpoint
    )
    result_state, _ = load_global_worker_state(result_checkpoint)
    try:
        final_state = _release_state(
            result_state,
            runtime_id=runtime,
            expected_lease_token=active_lease["token"],
            expected_fencing_token=active_lease["fencing_token"],
            now=current,
            batch=batch,
            final_status=str(batch.get("status") or "UNKNOWN"),
        )
    except ValueError as exc:
        return {
            "schema": SCHEMA,
            "status": "FENCE_RELEASE_FAILED",
            "reason": str(exc),
            "processed": int(batch.get("processed") or 0),
            "succeeded": int(batch.get("succeeded") or 0),
            "failed": int(batch.get("failed") or 0),
            "blocked": int(batch.get("blocked") or 0),
            "lease": lease,
            "network_called": True,
            "automatic_runtime_checkpoint_persistence": False,
            "automatic_retry_allowed": False,
            "external_action_executed": False,
            "real_trading_enabled": False,
        }
    final_checkpoint = attach_global_worker_state(
        result_checkpoint,
        final_state,
    )
    final_write = _persist_runtime_checkpoint_cas(
        final_checkpoint,
        cfg,
        expected_sha=str(claim_write.get("sha") or ""),
        operation="persist global worker tick",
        timeout=timeout,
    )
    if final_write.get("status") != "CONFIRMED":
        return {
            "schema": SCHEMA,
            "status": "FINAL_" + str(final_write.get("status") or "ERROR"),
            "processed": int(batch.get("processed") or 0),
            "succeeded": int(batch.get("succeeded") or 0),
            "failed": int(batch.get("failed") or 0),
            "blocked": int(batch.get("blocked") or 0),
            "lease": lease,
            "network_called": True,
            "automatic_runtime_checkpoint_persistence": False,
            "checkpoint_write": final_write,
            "reconciliation_required": bool(final_write.get("reconciliation_required")),
            "automatic_retry_allowed": False,
            "external_action_executed": False,
            "real_trading_enabled": False,
        }

    return {
        "schema": SCHEMA,
        "status": "CONFIRMED",
        "batch_status": str(batch.get("status") or "UNKNOWN"),
        "processed": int(batch.get("processed") or 0),
        "succeeded": int(batch.get("succeeded") or 0),
        "failed": int(batch.get("failed") or 0),
        "blocked": int(batch.get("blocked") or 0),
        "authorization_mode": "GLOBAL_WORKER",
        "service_principal": SERVICE_PRINCIPAL,
        "delegated_actor": delegated_context.actor_id,
        "fencing_token": lease["fencing_token"],
        "lease_reclaimed": bool(lease.get("reclaimed")),
        "work_intent_digest": work_intent["digest"],
        "work_intent_count": work_intent["count"],
        "runtime_sha": str(final_write.get("sha") or ""),
        "network_called": True,
        "automatic_runtime_checkpoint_persistence": True,
        "automatic_external_business_actions": False,
        "provider_called": False,
        "external_action_executed": False,
        "payment_executed": False,
        "publication_executed": False,
        "deploy_executed": False,
        "merge_executed": False,
        "real_trading_enabled": False,
    }


def _cli() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tick", action="store_true")
    args = parser.parse_args()
    if not args.tick:
        parser.error("--tick is required")
    result = run_global_worker_once()
    safe = {
        key: value
        for key, value in result.items()
        if key not in {"checkpoint", "checkpoint_write"}
    }
    print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
    status = str(result.get("status") or "")
    return 1 if status in {
        "ERROR",
        "BLOCKED",
        "FENCE_VERIFICATION_FAILED",
        "FENCE_RELEASE_FAILED",
        "INFLIGHT_RECONCILIATION_REQUIRED",
    } or status.startswith("FINAL_ERROR") else 0


if __name__ == "__main__":
    raise SystemExit(_cli())


__all__ = [
    "SCHEMA",
    "GLOBAL_WORKER_NAMESPACE",
    "GLOBAL_WORKER_SCHEMA",
    "GLOBAL_WORKER_STATES",
    "GLOBAL_WORKER_CAPABILITIES",
    "SERVICE_PRINCIPAL",
    "global_worker_feature_enabled",
    "global_worker_integrity",
    "load_global_worker_state",
    "attach_global_worker_state",
    "stage_arm_global_worker",
    "stage_pause_global_worker",
    "stage_kill_global_worker",
    "global_worker_snapshot",
    "run_global_worker_once",
]
