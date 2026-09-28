"""AION Global Worker Arming Ceremony V1.

This module prepares and approves a short-lived, scope-bound arming plan.
It never persists the Checkpoint and never changes the repository feature flag.

The actual worker state can only be staged later by
`stage_arm_global_worker(..., arming_approval=ticket)`, which validates the
ticket against the exact current checkpoint/context.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any, Mapping

from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_intelligence.evidence import digest, safe_text, utc
from atlasquant_aion_core_runtime_bridge import authenticated_context
from atlasquant_aion_memory import checkpoint_source_digest


SCHEMA = "ATLASQUANT_AION_GLOBAL_WORKER_ARMING_CEREMONY_V1"
PLAN_SCHEMA = "AION_GLOBAL_WORKER_ARMING_PLAN_V1"
APPROVAL_SCHEMA = "AION_GLOBAL_WORKER_ARMING_APPROVAL_V1"

CONFIRMATION_PHRASE = "ARMAR WORKER GLOBAL"

DEFAULT_APPROVAL_TTL_SECONDS = 900
MIN_APPROVAL_TTL_SECONDS = 300
MAX_APPROVAL_TTL_SECONDS = 3600

GLOBAL_WORKER_CAPABILITIES = frozenset({
    "ADMINISTRATION",
    "MEMORY",
    "RESEARCH",
    "CONTENT",
    "OBSERVABILITY",
})

MIN_LEASE_SECONDS = 300
MAX_LEASE_SECONDS = 1800
MAX_JOBS = 20

# The existing scheduled pulse runs twice per hour.
MAX_SCHEDULED_TICKS_PER_DAY = 48
MAX_RUNTIME_WRITES_PER_TICK = 2


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


def _exact_int(value: Any, *, minimum: int, maximum: int, name: str) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("invalid " + name)
    return value


def _payload_digest(value: Mapping[str, Any], digest_field: str) -> str:
    raw = dict(value)
    raw.pop(digest_field, None)
    return digest(raw)


def _budget_contract(max_jobs: int) -> dict[str, Any]:
    return {
        "max_jobs_per_tick": max_jobs,
        "max_scheduled_ticks_per_utc_day": MAX_SCHEDULED_TICKS_PER_DAY,
        "max_jobs_per_utc_day": max_jobs * MAX_SCHEDULED_TICKS_PER_DAY,
        "max_runtime_checkpoint_writes_per_tick": MAX_RUNTIME_WRITES_PER_TICK,
        "provider_calls_per_tick": 0,
        "paid_service_calls_per_tick": 0,
        "publications_per_tick": 0,
        "payments_per_tick": 0,
        "deploys_per_tick": 0,
        "merges_per_tick": 0,
        "subprocess_calls_per_tick": 0,
        "market_orders_per_tick": 0,
        "real_trading_enabled": False,
    }


def plan_integrity(plan: Mapping[str, Any] | None) -> dict[str, str]:
    if not isinstance(plan, Mapping):
        return {"state": "ABSENT", "stored": "", "expected": ""}
    if str(plan.get("schema") or "") != PLAN_SCHEMA:
        return {
            "state": "MISMATCH",
            "stored": str(plan.get("plan_digest") or ""),
            "expected": PLAN_SCHEMA,
        }
    supplied = str(plan.get("plan_digest") or "").strip()
    expected = _payload_digest(plan, "plan_digest")
    return {
        "state": "MATCH" if supplied and supplied == expected else "MISMATCH",
        "stored": supplied,
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
    supplied = str(ticket.get("approval_digest") or "").strip()
    expected = _payload_digest(ticket, "approval_digest")
    return {
        "state": "MATCH" if supplied and supplied == expected else "MISMATCH",
        "stored": supplied,
        "expected": expected,
    }


def prepare_global_worker_arming_plan(
    access: Mapping[str, Any] | None,
    checkpoint: Mapping[str, Any],
    *,
    max_jobs: int,
    lease_seconds: int,
    approval_ttl_seconds: int = DEFAULT_APPROVAL_TTL_SECONDS,
    readiness_stage: str = "READY_FOR_ADMIN_ARMING",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build an immutable arming plan without changing the checkpoint."""
    current = utc(now or _now())
    context = authenticated_context(access, Domain.ADMIN)
    if context.role != "ADMIN":
        raise ValueError("ADMIN_REQUIRED")
    jobs = _exact_int(
        max_jobs,
        minimum=1,
        maximum=MAX_JOBS,
        name="arming max jobs",
    )
    lease = _exact_int(
        lease_seconds,
        minimum=MIN_LEASE_SECONDS,
        maximum=MAX_LEASE_SECONDS,
        name="arming lease",
    )
    ttl = _exact_int(
        approval_ttl_seconds,
        minimum=MIN_APPROVAL_TTL_SECONDS,
        maximum=MAX_APPROVAL_TTL_SECONDS,
        name="arming approval ttl",
    )
    stage = safe_text(str(readiness_stage or ""), 100).upper()
    if stage != "READY_FOR_ADMIN_ARMING":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "READINESS_STAGE_NOT_ARMABLE",
            "checkpoint_modified": False,
            "runtime_modified": False,
            "feature_flag_modified": False,
        }

    source_digest = checkpoint_source_digest(checkpoint)
    expires = current + timedelta(seconds=ttl)
    plan = {
        "schema": PLAN_SCHEMA,
        "actor_id": context.actor_id,
        "scope": _scope_payload(context),
        "source_checkpoint_digest": source_digest,
        "readiness_stage": stage,
        "created_at": current.isoformat(),
        "expires_at": expires.isoformat(),
        "approval_ttl_seconds": ttl,
        "allowed_capabilities": sorted(GLOBAL_WORKER_CAPABILITIES),
        "lease_seconds": lease,
        "budgets": _budget_contract(jobs),
        "activation_flag_required": True,
        "activation_flag_name": "ATLASQUANT_AION_GLOBAL_WORKER_ENABLED",
        "activation_flag_changed_by_ceremony": False,
        "runtime_persistence_performed": False,
        "external_business_actions_allowed": False,
    }
    plan["plan_digest"] = _payload_digest(plan, "plan_digest")
    return {
        "schema": SCHEMA,
        "status": "PLAN_READY",
        "plan": plan,
        "plan_digest": plan["plan_digest"],
        "expires_at": plan["expires_at"],
        "checkpoint_modified": False,
        "runtime_modified": False,
        "feature_flag_modified": False,
        "worker_armed": False,
    }


def approve_global_worker_arming_plan(
    access: Mapping[str, Any] | None,
    plan: Mapping[str, Any],
    *,
    confirmation: bool,
    confirmation_phrase: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create a short-lived approval ticket; still no checkpoint mutation."""
    current = utc(now or _now())
    context = authenticated_context(access, Domain.ADMIN)
    if confirmation is not True:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "EXPLICIT_CONFIRMATION_REQUIRED",
            "runtime_modified": False,
            "worker_armed": False,
        }
    if str(confirmation_phrase or "").strip() != CONFIRMATION_PHRASE:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "CONFIRMATION_PHRASE_MISMATCH",
            "runtime_modified": False,
            "worker_armed": False,
        }
    if plan_integrity(plan)["state"] != "MATCH":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "ARMING_PLAN_INTEGRITY_MISMATCH",
            "runtime_modified": False,
            "worker_armed": False,
        }
    if str(plan.get("actor_id") or "") != context.actor_id:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "ARMING_PLAN_ACTOR_MISMATCH",
            "runtime_modified": False,
            "worker_armed": False,
        }
    if plan.get("scope") != _scope_payload(context):
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "ARMING_PLAN_SCOPE_MISMATCH",
            "runtime_modified": False,
            "worker_armed": False,
        }
    expires = _parse_iso(plan.get("expires_at"))
    if expires is None or current >= expires:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "ARMING_PLAN_EXPIRED",
            "runtime_modified": False,
            "worker_armed": False,
        }

    ticket = {
        "schema": APPROVAL_SCHEMA,
        "plan_digest": str(plan.get("plan_digest") or ""),
        "actor_id": context.actor_id,
        "scope": _scope_payload(context),
        "source_checkpoint_digest": str(plan.get("source_checkpoint_digest") or ""),
        "issued_at": current.isoformat(),
        "expires_at": str(plan.get("expires_at") or ""),
        "allowed_capabilities": list(plan.get("allowed_capabilities") or []),
        "lease_seconds": int(plan.get("lease_seconds") or 0),
        "budgets": dict(plan.get("budgets") or {}),
        "confirmation_phrase_digest": digest(CONFIRMATION_PHRASE),
        "runtime_modified": False,
        "feature_flag_modified": False,
        "worker_armed": False,
    }
    ticket["approval_digest"] = _payload_digest(ticket, "approval_digest")
    return {
        "schema": SCHEMA,
        "status": "APPROVED_FOR_STAGING",
        "approval": ticket,
        "approval_digest": ticket["approval_digest"],
        "expires_at": ticket["expires_at"],
        "runtime_modified": False,
        "feature_flag_modified": False,
        "worker_armed": False,
    }


def validate_global_worker_arming_approval(
    access: Mapping[str, Any] | None,
    checkpoint: Mapping[str, Any],
    approval: Mapping[str, Any] | None,
    *,
    max_jobs: int,
    lease_seconds: int,
    allowed_capabilities: set[str] | frozenset[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate the approval against the exact current context and checkpoint."""
    current = utc(now or _now())
    context = authenticated_context(access, Domain.ADMIN)
    if approval_integrity(approval)["state"] != "MATCH":
        return {"state": "BLOCKED", "reason": "ARMING_APPROVAL_INTEGRITY_MISMATCH"}

    ticket = dict(approval or {})
    if str(ticket.get("actor_id") or "") != context.actor_id:
        return {"state": "BLOCKED", "reason": "ARMING_APPROVAL_ACTOR_MISMATCH"}
    if ticket.get("scope") != _scope_payload(context):
        return {"state": "BLOCKED", "reason": "ARMING_APPROVAL_SCOPE_MISMATCH"}

    expires = _parse_iso(ticket.get("expires_at"))
    if expires is None or current >= expires:
        return {"state": "BLOCKED", "reason": "ARMING_APPROVAL_EXPIRED"}

    source_digest = checkpoint_source_digest(checkpoint)
    if str(ticket.get("source_checkpoint_digest") or "") != source_digest:
        return {
            "state": "BLOCKED",
            "reason": "ARMING_APPROVAL_CHECKPOINT_CHANGED",
        }

    budgets = ticket.get("budgets")
    if not isinstance(budgets, Mapping):
        return {"state": "BLOCKED", "reason": "ARMING_APPROVAL_BUDGETS_MISSING"}

    jobs = _exact_int(max_jobs, minimum=1, maximum=MAX_JOBS, name="arming max jobs")
    lease = _exact_int(
        lease_seconds,
        minimum=MIN_LEASE_SECONDS,
        maximum=MAX_LEASE_SECONDS,
        name="arming lease",
    )
    if int(budgets.get("max_jobs_per_tick") or 0) != jobs:
        return {"state": "BLOCKED", "reason": "ARMING_APPROVAL_JOB_BUDGET_MISMATCH"}
    if int(ticket.get("lease_seconds") or 0) != lease:
        return {"state": "BLOCKED", "reason": "ARMING_APPROVAL_LEASE_MISMATCH"}

    expected_caps = (
        frozenset(str(x).strip().upper() for x in allowed_capabilities)
        if allowed_capabilities is not None
        else GLOBAL_WORKER_CAPABILITIES
    )
    ticket_caps = frozenset(
        str(x).strip().upper()
        for x in list(ticket.get("allowed_capabilities") or [])
    )
    if ticket_caps != expected_caps:
        return {
            "state": "BLOCKED",
            "reason": "ARMING_APPROVAL_CAPABILITY_MISMATCH",
        }

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
    if any(int(budgets.get(key, -1)) != 0 for key in zero_budget_fields):
        return {
            "state": "BLOCKED",
            "reason": "ARMING_APPROVAL_EXTERNAL_BUDGET_NONZERO",
        }
    if budgets.get("real_trading_enabled") is not False:
        return {
            "state": "BLOCKED",
            "reason": "ARMING_APPROVAL_REAL_TRADING_NOT_FALSE",
        }
    if int(budgets.get("max_runtime_checkpoint_writes_per_tick") or 0) != 2:
        return {
            "state": "BLOCKED",
            "reason": "ARMING_APPROVAL_RUNTIME_WRITE_BUDGET_MISMATCH",
        }

    return {
        "state": "APPROVED",
        "reason": "",
        "approval_digest": str(ticket.get("approval_digest") or ""),
        "plan_digest": str(ticket.get("plan_digest") or ""),
        "expires_at": str(ticket.get("expires_at") or ""),
        "budgets": dict(budgets),
        "allowed_capabilities": sorted(expected_caps),
    }


__all__ = [
    "SCHEMA",
    "PLAN_SCHEMA",
    "APPROVAL_SCHEMA",
    "CONFIRMATION_PHRASE",
    "DEFAULT_APPROVAL_TTL_SECONDS",
    "GLOBAL_WORKER_CAPABILITIES",
    "plan_integrity",
    "approval_integrity",
    "prepare_global_worker_arming_plan",
    "approve_global_worker_arming_plan",
    "validate_global_worker_arming_approval",
]
