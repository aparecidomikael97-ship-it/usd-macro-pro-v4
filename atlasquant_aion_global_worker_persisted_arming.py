"""Persisted Global Worker Arming Ceremony V1.

This module is the only guarded path that may persist the initial transition
into Global Worker ARMED state. It requires a second, short-lived approval bound
to the staged checkpoint and current runtime SHA.

The repository activation flag must be proven UNSET or DISABLED immediately
before the write. It is checked again after read-after-write; if it becomes
enabled during the transition, the module attempts a CAS rollback to the exact
pre-arming checkpoint.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
import json

from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_intelligence.evidence import digest, safe_text, utc
from atlasquant_aion_github_io import github_get
from atlasquant_aion_core_runtime_bridge import authenticated_context
from atlasquant_aion_global_worker import (
    GLOBAL_WORKER_NAMESPACE,
    load_global_worker_state,
)
from atlasquant_aion_memory import (
    RuntimeConfig,
    checkpoint_source_digest,
    runtime_write_preflight,
    save_runtime_checkpoint,
)


SCHEMA = "ATLASQUANT_AION_GLOBAL_WORKER_PERSISTED_ARMING_V1"
PLAN_SCHEMA = "AION_GLOBAL_WORKER_PERSISTENCE_PLAN_V1"
APPROVAL_SCHEMA = "AION_GLOBAL_WORKER_PERSISTENCE_APPROVAL_V1"
CONFIRMATION_PHRASE = "PERSISTIR WORKER GLOBAL ARMADO"

DEFAULT_TTL_SECONDS = 600
MIN_TTL_SECONDS = 300
MAX_TTL_SECONDS = 1800
FEATURE_FLAG_NAME = "ATLASQUANT_AION_GLOBAL_WORKER_ENABLED"
SAFE_FLAG_STATES = frozenset({"UNSET", "DISABLED"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return utc(parsed)
    except Exception:
        return None


def _scope_payload(context) -> list[str]:
    return json.loads(context.key)


def _payload_digest(value: Mapping[str, Any], field: str) -> str:
    raw = dict(value)
    raw.pop(field, None)
    return digest(raw)


def _exact_int(value: Any, *, minimum: int, maximum: int, name: str) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("invalid " + name)
    return value


def _flag_state(value: Any) -> str:
    raw = str(value or "").strip().casefold()
    if raw in {"0", "false", "no", "off"}:
        return "DISABLED"
    if raw in {"1", "true", "yes", "on"}:
        return "ENABLED"
    if not raw:
        return "UNSET"
    return "INVALID"


def _arming_contract(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    item = dict(raw or {})
    return {
        "arm_digest": str(item.get("arm_digest") or ""),
        "arming_plan_digest": str(item.get("arming_plan_digest") or ""),
        "arming_approval_digest": str(item.get("arming_approval_digest") or ""),
        "arming_approval_expires_at": str(item.get("arming_approval_expires_at") or ""),
        "armed_at": str(item.get("armed_at") or ""),
        "delegation": deepcopy(dict(item.get("delegation") or {})),
        "allowed_capabilities": list(item.get("allowed_capabilities") or []),
        "resource_budgets": deepcopy(dict(item.get("resource_budgets") or {})),
        "max_jobs": item.get("max_jobs"),
        "lease_seconds": item.get("lease_seconds"),
    }


def _arming_contract_digest(raw: Mapping[str, Any] | None) -> str:
    return digest(_arming_contract(raw))


def read_repository_feature_flag(
    config: RuntimeConfig,
    *,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Read the repository variable list; never writes or mutates variables."""
    if not config.repo or not config.token:
        return {
            "schema": SCHEMA,
            "status": "UNAVAILABLE",
            "state": "UNKNOWN",
            "safe_for_arming_persistence": False,
            "reason": "Repository/token required for authoritative flag read.",
        }
    url = f"https://api.github.com/repos/{config.repo}/actions/variables"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": "Bearer " + config.token,
    }
    try:
        response = github_get(
            url,
            headers=headers,
            params={"per_page": 100},
            timeout=timeout,
        )
        response.raise_for_status()
        obj = response.json()
        variables = obj.get("variables") if isinstance(obj, Mapping) else []
        found = None
        for item in list(variables or []):
            if not isinstance(item, Mapping):
                continue
            if str(item.get("name") or "") == FEATURE_FLAG_NAME:
                found = item
                break
        state = "UNSET" if found is None else _flag_state(found.get("value"))
        return {
            "schema": SCHEMA,
            "status": "CONFIRMED",
            "state": state,
            "safe_for_arming_persistence": state in SAFE_FLAG_STATES,
            "variable_present": found is not None,
            "created_at": str((found or {}).get("created_at") or ""),
            "updated_at": str((found or {}).get("updated_at") or ""),
            "checked_at": utc(_now()).isoformat(),
            "raw_value_exposed": False,
            "reason": "",
        }
    except Exception as exc:
        return {
            "schema": SCHEMA,
            "status": "ERROR",
            "state": "UNKNOWN",
            "safe_for_arming_persistence": False,
            "variable_present": False,
            "checked_at": utc(_now()).isoformat(),
            "raw_value_exposed": False,
            "reason": type(exc).__name__,
        }


def persisted_arming_transition_required(
    working_checkpoint: Mapping[str, Any] | None,
    persisted_checkpoint: Mapping[str, Any] | None,
) -> bool:
    working_raw = (
        working_checkpoint.get(GLOBAL_WORKER_NAMESPACE)
        if isinstance(working_checkpoint, Mapping)
        else None
    )
    if not isinstance(working_raw, Mapping):
        return False
    if str(working_raw.get("state") or "").upper() != "ARMED":
        return False

    persisted_raw = (
        persisted_checkpoint.get(GLOBAL_WORKER_NAMESPACE)
        if isinstance(persisted_checkpoint, Mapping)
        else None
    )
    if not isinstance(persisted_raw, Mapping):
        return True
    if str(persisted_raw.get("state") or "").upper() != "ARMED":
        return True

    return _arming_contract_digest(persisted_raw) != _arming_contract_digest(working_raw)


def plan_integrity(plan: Mapping[str, Any] | None) -> dict[str, str]:
    if not isinstance(plan, Mapping):
        return {"state": "ABSENT", "stored": "", "expected": ""}
    if str(plan.get("schema") or "") != PLAN_SCHEMA:
        return {
            "state": "MISMATCH",
            "stored": str(plan.get("plan_digest") or ""),
            "expected": PLAN_SCHEMA,
        }
    stored = str(plan.get("plan_digest") or "").strip()
    expected = _payload_digest(plan, "plan_digest")
    return {
        "state": "MATCH" if stored and stored == expected else "MISMATCH",
        "stored": stored,
        "expected": expected,
    }


def approval_integrity(ticket: Mapping[str, Any] | None) -> dict[str, str]:
    if not isinstance(ticket, Mapping):
        return {"state": "ABSENT", "stored": "", "expected": ""}
    if str(ticket.get("schema") or "") != APPROVAL_SCHEMA:
        return {
            "state": "MISMATCH",
            "stored": str(ticket.get("approval_digest") or ""),
            "expected": APPROVAL_SCHEMA,
        }
    stored = str(ticket.get("approval_digest") or "").strip()
    expected = _payload_digest(ticket, "approval_digest")
    return {
        "state": "MATCH" if stored and stored == expected else "MISMATCH",
        "stored": stored,
        "expected": expected,
    }


def prepare_persisted_arming_plan(
    access: Mapping[str, Any] | None,
    working_checkpoint: Mapping[str, Any],
    runtime_result: Mapping[str, Any],
    flag_evidence: Mapping[str, Any],
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = utc(now or _now())
    context = authenticated_context(access, Domain.ADMIN)
    if context.role != "ADMIN":
        raise ValueError("ADMIN_REQUIRED")
    ttl = _exact_int(
        ttl_seconds,
        minimum=MIN_TTL_SECONDS,
        maximum=MAX_TTL_SECONDS,
        name="persistence approval ttl",
    )
    preflight = runtime_write_preflight(runtime_result)
    if not preflight.get("allowed"):
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "RUNTIME_WRITE_PREFLIGHT_BLOCKED",
        }
    persisted = runtime_result.get("checkpoint")
    if not isinstance(persisted, Mapping):
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "PERSISTED_CHECKPOINT_REQUIRED",
        }
    if not persisted_arming_transition_required(working_checkpoint, persisted):
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "NO_NEW_ARMED_TRANSITION",
        }

    state, status = load_global_worker_state(working_checkpoint)
    if status.get("state") != "CONNECTED" or state.get("state") != "ARMED":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "VALID_STAGED_ARMED_STATE_REQUIRED",
        }
    if state.get("kill_switch") is not False:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "STAGED_ARMED_KILL_SWITCH_MUST_BE_OFF",
        }

    flag_status = str(flag_evidence.get("status") or "UNKNOWN").upper()
    flag_state = str(flag_evidence.get("state") or "UNKNOWN").upper()
    if (
        flag_status != "CONFIRMED"
        or flag_state not in SAFE_FLAG_STATES
        or flag_evidence.get("safe_for_arming_persistence") is not True
    ):
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "FEATURE_FLAG_NOT_PROVEN_DISABLED",
            "feature_flag_state": flag_state,
        }

    runtime_sha = str(runtime_result.get("sha") or "").strip()
    if not runtime_sha:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "RUNTIME_SHA_REQUIRED",
        }

    expires = current + timedelta(seconds=ttl)
    plan = {
        "schema": PLAN_SCHEMA,
        "actor_id": context.actor_id,
        "scope": _scope_payload(context),
        "working_checkpoint_digest": checkpoint_source_digest(working_checkpoint),
        "source_runtime_checkpoint_digest": checkpoint_source_digest(persisted),
        "source_runtime_sha": runtime_sha,
        "arming_plan_digest": str(state.get("arming_plan_digest") or ""),
        "arming_approval_digest": str(state.get("arming_approval_digest") or ""),
        "arm_digest": str(state.get("arm_digest") or ""),
        "resource_budgets": deepcopy(dict(state.get("resource_budgets") or {})),
        "feature_flag_state": flag_state,
        "feature_flag_proof_required_again_before_write": True,
        "feature_flag_proof_required_after_write": True,
        "created_at": current.isoformat(),
        "expires_at": expires.isoformat(),
        "ttl_seconds": ttl,
        "rollback": {
            "source_runtime_sha": runtime_sha,
            "source_runtime_checkpoint_digest": checkpoint_source_digest(persisted),
            "automatic_on_post_write_flag_violation": True,
        },
        "runtime_modified": False,
        "feature_flag_modified": False,
    }
    plan["plan_digest"] = _payload_digest(plan, "plan_digest")
    return {
        "schema": SCHEMA,
        "status": "PERSISTENCE_PLAN_READY",
        "plan": plan,
        "runtime_modified": False,
        "feature_flag_modified": False,
    }


def approve_persisted_arming_plan(
    access: Mapping[str, Any] | None,
    plan: Mapping[str, Any],
    *,
    confirmation: bool,
    confirmation_phrase: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = utc(now or _now())
    context = authenticated_context(access, Domain.ADMIN)
    if confirmation is not True:
        return {"schema": SCHEMA, "status": "BLOCKED", "reason": "EXPLICIT_CONFIRMATION_REQUIRED"}
    if str(confirmation_phrase or "").strip() != CONFIRMATION_PHRASE:
        return {"schema": SCHEMA, "status": "BLOCKED", "reason": "CONFIRMATION_PHRASE_MISMATCH"}
    if plan_integrity(plan)["state"] != "MATCH":
        return {"schema": SCHEMA, "status": "BLOCKED", "reason": "PERSISTENCE_PLAN_INTEGRITY_MISMATCH"}
    if str(plan.get("actor_id") or "") != context.actor_id or plan.get("scope") != _scope_payload(context):
        return {"schema": SCHEMA, "status": "BLOCKED", "reason": "PERSISTENCE_PLAN_CONTEXT_MISMATCH"}
    expires = _parse_iso(plan.get("expires_at"))
    if expires is None or current >= expires:
        return {"schema": SCHEMA, "status": "BLOCKED", "reason": "PERSISTENCE_PLAN_EXPIRED"}

    ticket = {
        "schema": APPROVAL_SCHEMA,
        "plan_digest": str(plan.get("plan_digest") or ""),
        "actor_id": context.actor_id,
        "scope": _scope_payload(context),
        "working_checkpoint_digest": str(plan.get("working_checkpoint_digest") or ""),
        "source_runtime_checkpoint_digest": str(plan.get("source_runtime_checkpoint_digest") or ""),
        "source_runtime_sha": str(plan.get("source_runtime_sha") or ""),
        "arming_plan_digest": str(plan.get("arming_plan_digest") or ""),
        "arming_approval_digest": str(plan.get("arming_approval_digest") or ""),
        "arm_digest": str(plan.get("arm_digest") or ""),
        "feature_flag_state_at_plan": str(plan.get("feature_flag_state") or ""),
        "issued_at": current.isoformat(),
        "expires_at": str(plan.get("expires_at") or ""),
        "confirmation_phrase_digest": digest(CONFIRMATION_PHRASE),
        "runtime_modified": False,
        "feature_flag_modified": False,
    }
    ticket["approval_digest"] = _payload_digest(ticket, "approval_digest")
    return {
        "schema": SCHEMA,
        "status": "APPROVED_FOR_PERSISTENCE",
        "approval": ticket,
        "runtime_modified": False,
        "feature_flag_modified": False,
    }


def validate_persisted_arming_approval(
    access: Mapping[str, Any] | None,
    working_checkpoint: Mapping[str, Any],
    runtime_result: Mapping[str, Any],
    approval: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = utc(now or _now())
    context = authenticated_context(access, Domain.ADMIN)
    if approval_integrity(approval)["state"] != "MATCH":
        return {"state": "BLOCKED", "reason": "PERSISTENCE_APPROVAL_INTEGRITY_MISMATCH"}
    ticket = dict(approval or {})
    if str(ticket.get("actor_id") or "") != context.actor_id or ticket.get("scope") != _scope_payload(context):
        return {"state": "BLOCKED", "reason": "PERSISTENCE_APPROVAL_CONTEXT_MISMATCH"}
    expires = _parse_iso(ticket.get("expires_at"))
    if expires is None or current >= expires:
        return {"state": "BLOCKED", "reason": "PERSISTENCE_APPROVAL_EXPIRED"}

    persisted = runtime_result.get("checkpoint")
    if not isinstance(persisted, Mapping):
        return {"state": "BLOCKED", "reason": "PERSISTED_CHECKPOINT_REQUIRED"}
    if str(runtime_result.get("sha") or "") != str(ticket.get("source_runtime_sha") or ""):
        return {"state": "BLOCKED", "reason": "PERSISTENCE_APPROVAL_RUNTIME_SHA_CHANGED"}
    if checkpoint_source_digest(persisted) != str(ticket.get("source_runtime_checkpoint_digest") or ""):
        return {"state": "BLOCKED", "reason": "PERSISTENCE_APPROVAL_RUNTIME_DIGEST_CHANGED"}
    if checkpoint_source_digest(working_checkpoint) != str(ticket.get("working_checkpoint_digest") or ""):
        return {"state": "BLOCKED", "reason": "PERSISTENCE_APPROVAL_WORKING_CHECKPOINT_CHANGED"}

    state, status = load_global_worker_state(working_checkpoint)
    if status.get("state") != "CONNECTED" or state.get("state") != "ARMED":
        return {"state": "BLOCKED", "reason": "STAGED_ARMED_STATE_REQUIRED"}
    for key in ("arming_plan_digest", "arming_approval_digest", "arm_digest"):
        if str(state.get(key) or "") != str(ticket.get(key) or ""):
            return {"state": "BLOCKED", "reason": "PERSISTENCE_APPROVAL_ARMING_STATE_CHANGED"}

    if str(ticket.get("confirmation_phrase_digest") or "") != digest(CONFIRMATION_PHRASE):
        return {"state": "BLOCKED", "reason": "PERSISTENCE_APPROVAL_CONFIRMATION_PROOF_MISMATCH"}

    return {
        "state": "APPROVED",
        "reason": "",
        "approval_digest": str(ticket.get("approval_digest") or ""),
        "source_runtime_sha": str(ticket.get("source_runtime_sha") or ""),
    }


def persist_staged_global_arming(
    access: Mapping[str, Any] | None,
    working_checkpoint: Mapping[str, Any],
    runtime_result: Mapping[str, Any],
    approval: Mapping[str, Any] | None,
    config: RuntimeConfig,
    *,
    confirmation: bool,
    timeout: float = 15.0,
    flag_reader=read_repository_feature_flag,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Perform the guarded persistence transition after second explicit approval."""
    if confirmation is not True:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "saved": False,
            "verified": False,
            "reason": "SECOND_EXPLICIT_CONFIRMATION_REQUIRED",
        }

    validation = validate_persisted_arming_approval(
        access,
        working_checkpoint,
        runtime_result,
        approval,
        now=now,
    )
    if validation.get("state") != "APPROVED":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "saved": False,
            "verified": False,
            "reason": str(validation.get("reason") or "PERSISTENCE_APPROVAL_REQUIRED"),
        }

    pre_flag = flag_reader(config, timeout=min(timeout, 10.0))
    if (
        str(pre_flag.get("status") or "") != "CONFIRMED"
        or str(pre_flag.get("state") or "") not in SAFE_FLAG_STATES
        or pre_flag.get("safe_for_arming_persistence") is not True
    ):
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "saved": False,
            "verified": False,
            "reason": "FEATURE_FLAG_NOT_PROVEN_DISABLED_BEFORE_WRITE",
            "feature_flag_state": str(pre_flag.get("state") or "UNKNOWN"),
        }

    source_checkpoint = deepcopy(dict(runtime_result.get("checkpoint") or {}))
    source_sha = str(runtime_result.get("sha") or "")
    result = save_runtime_checkpoint(
        deepcopy(working_checkpoint),
        config,
        approved=True,
        expected_sha=source_sha,
        allow_global_arming_transition=True,
        timeout=timeout,
    )
    if not (result.get("saved") and result.get("verified")):
        return {
            "schema": SCHEMA,
            "status": str(result.get("status") or "ERROR"),
            "saved": False,
            "verified": False,
            "reason": str(result.get("reason") or "PERSISTENCE_NOT_CONFIRMED"),
            "save_result": result,
        }

    def _rollback_after_write(reason: str, *, flag_state: str = "UNKNOWN") -> dict[str, Any]:
        rollback = save_runtime_checkpoint(
            source_checkpoint,
            config,
            approved=True,
            expected_sha=str(result.get("sha") or ""),
            timeout=timeout,
        )
        rollback_ok = bool(rollback.get("saved") and rollback.get("verified"))
        return {
            "schema": SCHEMA,
            "status": "ROLLED_BACK" if rollback_ok else "CRITICAL_ROLLBACK_FAILED",
            "saved": False if rollback_ok else True,
            "verified": rollback_ok,
            "reason": reason,
            "feature_flag_state": flag_state,
            "feature_flag_modified": False,
            "global_worker_executed": False,
            "real_trading_enabled": False,
            "rollback_performed": rollback_ok,
            "rollback_result": rollback,
        }

    persisted_checkpoint = result.get("checkpoint")
    if not isinstance(persisted_checkpoint, Mapping):
        return _rollback_after_write("READ_AFTER_WRITE_CHECKPOINT_MISSING")

    try:
        persisted_state, persisted_status = load_global_worker_state(persisted_checkpoint)
        working_state, _ = load_global_worker_state(working_checkpoint)
        state_matches = bool(
            persisted_status.get("state") == "CONNECTED"
            and persisted_state.get("state") == "ARMED"
            and persisted_state.get("arm_digest") == working_state.get("arm_digest")
            and persisted_state.get("arming_approval_digest") == working_state.get("arming_approval_digest")
            and _arming_contract_digest(persisted_checkpoint.get(GLOBAL_WORKER_NAMESPACE))
                == _arming_contract_digest(working_checkpoint.get(GLOBAL_WORKER_NAMESPACE))
        )
    except Exception:
        state_matches = False
    if not state_matches:
        return _rollback_after_write("PERSISTED_ARMED_STATE_DID_NOT_MATCH_STAGED_STATE")

    post_flag = flag_reader(config, timeout=min(timeout, 10.0))
    if (
        str(post_flag.get("status") or "") == "CONFIRMED"
        and str(post_flag.get("state") or "") in SAFE_FLAG_STATES
        and post_flag.get("safe_for_arming_persistence") is True
    ):
        return {
            "schema": SCHEMA,
            "status": "CONFIRMED",
            "saved": True,
            "verified": True,
            "sha": str(result.get("sha") or ""),
            "checkpoint": persisted_checkpoint,
            "arming_persisted": True,
            "feature_flag_state": str(post_flag.get("state") or ""),
            "feature_flag_modified": False,
            "global_worker_executed": False,
            "real_trading_enabled": False,
            "rollback_performed": False,
        }

    return _rollback_after_write(
        "FEATURE_FLAG_NOT_PROVEN_DISABLED_AFTER_WRITE",
        flag_state=str(post_flag.get("state") or "UNKNOWN"),
    )


__all__ = [
    "SCHEMA",
    "PLAN_SCHEMA",
    "APPROVAL_SCHEMA",
    "CONFIRMATION_PHRASE",
    "FEATURE_FLAG_NAME",
    "SAFE_FLAG_STATES",
    "read_repository_feature_flag",
    "persisted_arming_transition_required",
    "plan_integrity",
    "approval_integrity",
    "prepare_persisted_arming_plan",
    "approve_persisted_arming_plan",
    "validate_persisted_arming_approval",
    "persist_staged_global_arming",
]
