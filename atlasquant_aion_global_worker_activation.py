"""AION Global Worker Activation Ceremony V1.

This module prepares the final repository-variable activation step after a
Global Worker ARMED state is already persisted and Activation Readiness reports
READY_FOR_FLAG_ENABLE.

Building/importing this module does nothing. The feature flag is mutated only
through an explicit ADMIN activation function guarded by a short-lived ticket
and a final confirmation. A successful flag write is reported only as
ACTIVATED_PENDING_LIVE_EVIDENCE; it never proves that a worker heartbeat ran.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import quote

from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_intelligence.evidence import digest, utc
from atlasquant_aion_github_io import github_patch, github_post
from atlasquant_aion_core_runtime_bridge import authenticated_context
from atlasquant_aion_coordination_mode_gate import (
    CURRENT_MODE as CURRENT_COORDINATION_MODE,
    coordination_activation_gate,
)
from atlasquant_aion_global_worker import (
    GLOBAL_WORKER_NAMESPACE,
    load_global_worker_state,
)
from atlasquant_aion_global_worker_persisted_arming import (
    FEATURE_FLAG_NAME,
    SAFE_FLAG_STATES,
    read_repository_feature_flag,
)
from atlasquant_aion_memory import (
    RuntimeConfig,
    checkpoint_source_digest,
    load_runtime_checkpoint,
)
from atlasquant_aion_global_worker_readiness import (
    AUTOPILOT_WORKFLOW,
    activation_readiness_snapshot,
    fetch_recent_autopilot_pulses,
)
from atlasquant_aion_global_worker_reactivation_gate import (
    reactivation_gate_requirement,
    validate_reactivation_gate_for_execution,
    validate_reactivation_gate_for_plan,
)


SCHEMA = "ATLASQUANT_AION_GLOBAL_WORKER_ACTIVATION_CEREMONY_V1"
PLAN_SCHEMA = "AION_GLOBAL_WORKER_ACTIVATION_PLAN_V1"
APPROVAL_SCHEMA = "AION_GLOBAL_WORKER_ACTIVATION_APPROVAL_V1"

CONFIRMATION_PHRASE = "ATIVAR WORKER GLOBAL"
DEACTIVATION_PHRASE = "DESATIVAR WORKER GLOBAL"

DEFAULT_TTL_SECONDS = 600
MIN_TTL_SECONDS = 300
MAX_TTL_SECONDS = 1800

READY_STAGE = "READY_FOR_FLAG_ENABLE"
ENABLED_VALUE = "1"
DISABLED_VALUE = "0"


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


def _variable_collection_url(config: RuntimeConfig) -> str:
    return f"https://api.github.com/repos/{config.repo}/actions/variables"


def _variable_url(config: RuntimeConfig) -> str:
    name = quote(FEATURE_FLAG_NAME, safe="")
    return f"{_variable_collection_url(config)}/{name}"


def _headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": "Bearer " + token,
    }


def _runtime_armed_contract(
    runtime_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    result = dict(runtime_result or {})
    if str(result.get("status") or "").upper() != "CONFIRMED":
        return {"state": "BLOCKED", "reason": "RUNTIME_NOT_CONFIRMED"}
    checkpoint = result.get("checkpoint")
    if not isinstance(checkpoint, Mapping):
        return {"state": "BLOCKED", "reason": "RUNTIME_CHECKPOINT_REQUIRED"}
    runtime_sha = str(result.get("sha") or "").strip()
    if not runtime_sha:
        return {"state": "BLOCKED", "reason": "RUNTIME_SHA_REQUIRED"}

    try:
        worker, status = load_global_worker_state(checkpoint)
    except Exception:
        return {"state": "BLOCKED", "reason": "GLOBAL_WORKER_STATE_INVALID"}

    if status.get("state") != "CONNECTED" or worker.get("state") != "ARMED":
        return {"state": "BLOCKED", "reason": "PERSISTED_ARMED_STATE_REQUIRED"}
    if worker.get("kill_switch") is not False:
        return {"state": "BLOCKED", "reason": "GLOBAL_KILL_SWITCH_MUST_BE_OFF"}

    lease = worker.get("lease") if isinstance(worker.get("lease"), Mapping) else {}
    if str(lease.get("owner") or "").strip():
        return {"state": "BLOCKED", "reason": "GLOBAL_LEASE_MUST_BE_EMPTY_BEFORE_ACTIVATION"}

    return {
        "state": "READY",
        "reason": "",
        "checkpoint": checkpoint,
        "runtime_sha": runtime_sha,
        "runtime_checkpoint_digest": checkpoint_source_digest(checkpoint),
        "arm_digest": str(worker.get("arm_digest") or ""),
        "arming_plan_digest": str(worker.get("arming_plan_digest") or ""),
        "arming_approval_digest": str(worker.get("arming_approval_digest") or ""),
        "allowed_capabilities": list(worker.get("allowed_capabilities") or []),
        "resource_budgets": deepcopy(dict(worker.get("resource_budgets") or {})),
        "max_jobs": worker.get("max_jobs"),
        "lease_seconds": worker.get("lease_seconds"),
    }


def _readiness_contract(
    readiness: Mapping[str, Any] | None,
) -> dict[str, Any]:
    report = dict(readiness or {})
    blockers = list(report.get("blockers") or [])
    if (
        str(report.get("status") or "").upper() != "PASS"
        or str(report.get("activation_stage") or "") != READY_STAGE
        or blockers
        or report.get("read_only") is not True
        or report.get("runtime_modified") is not False
        or report.get("feature_flag_modified") is not False
    ):
        return {"state": "BLOCKED", "reason": "READINESS_NOT_READY_FOR_FLAG_ENABLE"}

    runtime = report.get("runtime") if isinstance(report.get("runtime"), Mapping) else {}
    feature = (
        report.get("feature_flag")
        if isinstance(report.get("feature_flag"), Mapping)
        else {}
    )
    if (
        str(runtime.get("state") or "") != "PASS"
        or str(runtime.get("global_worker_state") or "") != "ARMED"
        or runtime.get("global_kill_switch") is not False
        or str(feature.get("state") or "") not in SAFE_FLAG_STATES
    ):
        return {"state": "BLOCKED", "reason": "READINESS_EVIDENCE_INCONSISTENT"}

    checked_at = _parse_iso(report.get("checked_at"))
    if checked_at is None:
        return {"state": "BLOCKED", "reason": "READINESS_TIMESTAMP_REQUIRED"}

    return {
        "state": "READY",
        "reason": "",
        "checked_at": checked_at.isoformat(),
        "feature_flag_state": str(feature.get("state") or ""),
        "runtime_checkpoint_integrity": str(runtime.get("checkpoint_integrity") or ""),
        "pulse_state": str(
            ((report.get("pulse") or {}) if isinstance(report.get("pulse"), Mapping) else {}).get("state")
            or ""
        ),
        "shadow_state": str(
            ((report.get("shadow_protocol") or {}) if isinstance(report.get("shadow_protocol"), Mapping) else {}).get("state")
            or ""
        ),
    }


def collect_activation_readiness_evidence(
    config: RuntimeConfig,
    runtime_result: Mapping[str, Any],
    *,
    timeout: float = 12.0,
    now: datetime | None = None,
    flag_reader: Callable[..., Mapping[str, Any]] = read_repository_feature_flag,
    pulse_reader: Callable[..., Mapping[str, Any]] = fetch_recent_autopilot_pulses,
    workflow_path: str = AUTOPILOT_WORKFLOW,
) -> dict[str, Any]:
    """Collect current readiness with GET-only evidence and in-memory shadow checks."""
    current = utc(now or _now())
    flag = dict(flag_reader(config, timeout=min(timeout, 10.0)) or {})
    flag_status = str(flag.get("status") or "").upper()
    flag_state = str(flag.get("state") or "UNKNOWN").upper()
    if flag_status != "CONFIRMED":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "activation_stage": "BLOCKED",
            "blockers": ["FEATURE_FLAG_EVIDENCE_UNAVAILABLE"],
            "feature_flag": {
                "name": FEATURE_FLAG_NAME,
                "state": "UNKNOWN",
                "value_exposed": False,
            },
            "flag_evidence": flag,
            "read_only": True,
            "runtime_modified": False,
            "feature_flag_modified": False,
            "global_worker_executed": False,
        }

    pulses = dict(
        pulse_reader(
            config,
            token=config.token,
            timeout=timeout,
            per_page=5,
        )
        or {}
    )
    if str(pulses.get("status") or "").upper() != "CONFIRMED":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "activation_stage": "BLOCKED",
            "blockers": ["PULSE_EVIDENCE_UNAVAILABLE"],
            "feature_flag": {
                "name": FEATURE_FLAG_NAME,
                "state": flag_state,
                "value_exposed": False,
            },
            "flag_evidence": flag,
            "pulse_source_status": str(pulses.get("status") or "UNKNOWN"),
            "read_only": True,
            "runtime_modified": False,
            "feature_flag_modified": False,
            "global_worker_executed": False,
        }

    try:
        workflow_text = Path(workflow_path).read_text(encoding="utf-8")
    except Exception as exc:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "activation_stage": "BLOCKED",
            "blockers": ["WORKFLOW_SOURCE_UNAVAILABLE"],
            "feature_flag": {
                "name": FEATURE_FLAG_NAME,
                "state": flag_state,
                "value_exposed": False,
            },
            "flag_evidence": flag,
            "pulse_source_status": str(pulses.get("status") or "UNKNOWN"),
            "read_only": True,
            "runtime_modified": False,
            "feature_flag_modified": False,
            "global_worker_executed": False,
            "error_type": type(exc).__name__,
        }

    raw_state = {
        "UNSET": "",
        "DISABLED": "0",
        "ENABLED": "1",
    }.get(flag_state, "INVALID")
    report = activation_readiness_snapshot(
        runtime_result=runtime_result,
        config=config,
        feature_flag_raw=raw_state,
        workflow_text=workflow_text,
        pulse_rows=pulses.get("runs"),
        now=current,
    )
    report = dict(report)
    report["flag_evidence"] = flag
    report["pulse_source_status"] = str(pulses.get("status") or "UNKNOWN")
    report["global_worker_executed"] = False
    return report


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


def prepare_global_worker_activation_plan(
    access: Mapping[str, Any] | None,
    runtime_result: Mapping[str, Any],
    readiness: Mapping[str, Any],
    flag_evidence: Mapping[str, Any],
    *,
    reactivation_gate: Mapping[str, Any] | None = None,
    coordination_mode: Any = CURRENT_COORDINATION_MODE,
    coordination_readiness: Mapping[str, Any] | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Prepare a read-only activation plan. Never mutates a repository variable."""
    current = utc(now or _now())
    context = authenticated_context(access, Domain.ADMIN)
    if context.role != "ADMIN":
        raise ValueError("ADMIN_REQUIRED")
    ttl = _exact_int(
        ttl_seconds,
        minimum=MIN_TTL_SECONDS,
        maximum=MAX_TTL_SECONDS,
        name="activation approval ttl",
    )

    runtime = _runtime_armed_contract(runtime_result)
    if runtime.get("state") != "READY":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": str(runtime.get("reason") or "RUNTIME_NOT_READY"),
            "feature_flag_modified": False,
            "global_worker_executed": False,
        }

    ready = _readiness_contract(readiness)
    if ready.get("state") != "READY":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": str(ready.get("reason") or "READINESS_NOT_READY"),
            "feature_flag_modified": False,
            "global_worker_executed": False,
        }

    coordination = coordination_activation_gate(
        coordination_mode,
        coordination_readiness=coordination_readiness,
        operational_verification=coordination_operational_verification,
    )
    if coordination.get("allows_activation_plan") is not True:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": str(
                coordination.get("reason")
                or "COORDINATION_MODE_NOT_READY"
            ),
            "coordination": coordination,
            "feature_flag_modified": False,
            "global_worker_executed": False,
        }

    flag_status = str(flag_evidence.get("status") or "").upper()
    flag_state = str(flag_evidence.get("state") or "").upper()
    if (
        flag_status != "CONFIRMED"
        or flag_state not in SAFE_FLAG_STATES
        or flag_evidence.get("safe_for_arming_persistence") is not True
    ):
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "FEATURE_FLAG_NOT_PROVEN_DISABLED",
            "feature_flag_state": flag_state or "UNKNOWN",
            "feature_flag_modified": False,
            "global_worker_executed": False,
        }
    if flag_state != ready.get("feature_flag_state"):
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "READINESS_FLAG_EVIDENCE_CHANGED",
            "feature_flag_modified": False,
            "global_worker_executed": False,
        }

    gate_validation = validate_reactivation_gate_for_plan(
        runtime_result,
        readiness,
        flag_evidence,
        reactivation_gate,
        now=current,
    )
    if gate_validation.get("state") != "READY":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": str(
                gate_validation.get("reason")
                or "POST_INCIDENT_REACTIVATION_GATE_REQUIRED"
            ),
            "post_incident_gate_required": bool(
                reactivation_gate_requirement(runtime_result).get("required")
            ),
            "feature_flag_modified": False,
            "global_worker_executed": False,
        }

    expires = current + timedelta(seconds=ttl)
    plan = {
        "schema": PLAN_SCHEMA,
        "actor_id": context.actor_id,
        "scope": _scope_payload(context),
        "runtime_sha": runtime["runtime_sha"],
        "runtime_checkpoint_digest": runtime["runtime_checkpoint_digest"],
        "arm_digest": runtime["arm_digest"],
        "arming_plan_digest": runtime["arming_plan_digest"],
        "arming_approval_digest": runtime["arming_approval_digest"],
        "resource_budgets": runtime["resource_budgets"],
        "max_jobs": runtime["max_jobs"],
        "lease_seconds": runtime["lease_seconds"],
        "coordination_mode": str(coordination.get("mode") or ""),
        "coordination_gate_state": str(coordination.get("state") or ""),
        "coordination_adapter_id": str(coordination.get("adapter_id") or ""),
        "coordination_adapter_identity_digest": str(
            coordination.get("adapter_identity_digest") or ""
        ),
        "multi_instance_operationally_verified": (
            coordination.get("multi_instance_verified") is True
        ),
        "readiness_stage": READY_STAGE,
        "readiness_checked_at": ready["checked_at"],
        "readiness_pulse_state": ready["pulse_state"],
        "readiness_shadow_state": ready["shadow_state"],
        "feature_flag_state": flag_state,
        "feature_flag_target_state": "ENABLED",
        "feature_flag_name": FEATURE_FLAG_NAME,
        "post_incident_gate_required": bool(
            gate_validation.get("gate_required")
        ),
        "post_incident_gate_digest_at_plan": str(
            gate_validation.get("gate_digest") or ""
        ),
        "post_incident_closure_ledger_digest": str(
            gate_validation.get("closure_ledger_digest") or ""
        ),
        "post_incident_latest_closure_record_id": str(
            gate_validation.get("latest_closure_record_id") or ""
        ),
        "created_at": current.isoformat(),
        "expires_at": expires.isoformat(),
        "ttl_seconds": ttl,
        "requires_live_evidence_after_activation": True,
        "activation_does_not_execute_worker_tick": True,
        "runtime_checkpoint_modified": False,
        "feature_flag_modified": False,
        "global_worker_executed": False,
        "real_trading_enabled": False,
    }
    plan["plan_digest"] = _payload_digest(plan, "plan_digest")
    return {
        "schema": SCHEMA,
        "status": "ACTIVATION_PLAN_READY",
        "plan": plan,
        "runtime_checkpoint_modified": False,
        "feature_flag_modified": False,
        "global_worker_executed": False,
    }


def approve_global_worker_activation_plan(
    access: Mapping[str, Any] | None,
    plan: Mapping[str, Any],
    *,
    confirmation: bool,
    confirmation_phrase: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create a short-lived activation ticket; still no repository mutation."""
    current = utc(now or _now())
    context = authenticated_context(access, Domain.ADMIN)
    if confirmation is not True:
        return {"schema": SCHEMA, "status": "BLOCKED", "reason": "EXPLICIT_CONFIRMATION_REQUIRED"}
    if str(confirmation_phrase or "").strip() != CONFIRMATION_PHRASE:
        return {"schema": SCHEMA, "status": "BLOCKED", "reason": "CONFIRMATION_PHRASE_MISMATCH"}
    if plan_integrity(plan)["state"] != "MATCH":
        return {"schema": SCHEMA, "status": "BLOCKED", "reason": "ACTIVATION_PLAN_INTEGRITY_MISMATCH"}
    if str(plan.get("actor_id") or "") != context.actor_id or plan.get("scope") != _scope_payload(context):
        return {"schema": SCHEMA, "status": "BLOCKED", "reason": "ACTIVATION_PLAN_CONTEXT_MISMATCH"}
    expires = _parse_iso(plan.get("expires_at"))
    if expires is None or current >= expires:
        return {"schema": SCHEMA, "status": "BLOCKED", "reason": "ACTIVATION_PLAN_EXPIRED"}

    ticket = {
        "schema": APPROVAL_SCHEMA,
        "plan_digest": str(plan.get("plan_digest") or ""),
        "actor_id": context.actor_id,
        "scope": _scope_payload(context),
        "runtime_sha": str(plan.get("runtime_sha") or ""),
        "runtime_checkpoint_digest": str(plan.get("runtime_checkpoint_digest") or ""),
        "arm_digest": str(plan.get("arm_digest") or ""),
        "arming_plan_digest": str(plan.get("arming_plan_digest") or ""),
        "arming_approval_digest": str(plan.get("arming_approval_digest") or ""),
        "coordination_mode": str(plan.get("coordination_mode") or ""),
        "coordination_gate_state": str(plan.get("coordination_gate_state") or ""),
        "coordination_adapter_id": str(plan.get("coordination_adapter_id") or ""),
        "coordination_adapter_identity_digest": str(
            plan.get("coordination_adapter_identity_digest") or ""
        ),
        "multi_instance_operationally_verified": (
            plan.get("multi_instance_operationally_verified") is True
        ),
        "feature_flag_state_at_plan": str(plan.get("feature_flag_state") or ""),
        "feature_flag_target_state": "ENABLED",
        "post_incident_gate_required": bool(
            plan.get("post_incident_gate_required")
        ),
        "post_incident_gate_digest_at_plan": str(
            plan.get("post_incident_gate_digest_at_plan") or ""
        ),
        "post_incident_closure_ledger_digest": str(
            plan.get("post_incident_closure_ledger_digest") or ""
        ),
        "post_incident_latest_closure_record_id": str(
            plan.get("post_incident_latest_closure_record_id") or ""
        ),
        "issued_at": current.isoformat(),
        "expires_at": str(plan.get("expires_at") or ""),
        "confirmation_phrase_digest": digest(CONFIRMATION_PHRASE),
        "runtime_checkpoint_modified": False,
        "feature_flag_modified": False,
        "global_worker_executed": False,
    }
    ticket["approval_digest"] = _payload_digest(ticket, "approval_digest")
    return {
        "schema": SCHEMA,
        "status": "APPROVED_FOR_ACTIVATION",
        "approval": ticket,
        "runtime_checkpoint_modified": False,
        "feature_flag_modified": False,
        "global_worker_executed": False,
    }


def validate_global_worker_activation_approval(
    access: Mapping[str, Any] | None,
    runtime_result: Mapping[str, Any],
    approval: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = utc(now or _now())
    context = authenticated_context(access, Domain.ADMIN)
    if approval_integrity(approval)["state"] != "MATCH":
        return {"state": "BLOCKED", "reason": "ACTIVATION_APPROVAL_INTEGRITY_MISMATCH"}
    ticket = dict(approval or {})
    if str(ticket.get("actor_id") or "") != context.actor_id or ticket.get("scope") != _scope_payload(context):
        return {"state": "BLOCKED", "reason": "ACTIVATION_APPROVAL_CONTEXT_MISMATCH"}
    expires = _parse_iso(ticket.get("expires_at"))
    if expires is None or current >= expires:
        return {"state": "BLOCKED", "reason": "ACTIVATION_APPROVAL_EXPIRED"}

    runtime = _runtime_armed_contract(runtime_result)
    if runtime.get("state") != "READY":
        return {
            "state": "BLOCKED",
            "reason": str(runtime.get("reason") or "RUNTIME_NOT_READY"),
        }
    if runtime["runtime_sha"] != str(ticket.get("runtime_sha") or ""):
        return {"state": "BLOCKED", "reason": "ACTIVATION_APPROVAL_RUNTIME_SHA_CHANGED"}
    if runtime["runtime_checkpoint_digest"] != str(ticket.get("runtime_checkpoint_digest") or ""):
        return {"state": "BLOCKED", "reason": "ACTIVATION_APPROVAL_RUNTIME_DIGEST_CHANGED"}
    for key in ("arm_digest", "arming_plan_digest", "arming_approval_digest"):
        if str(runtime.get(key) or "") != str(ticket.get(key) or ""):
            return {"state": "BLOCKED", "reason": "ACTIVATION_APPROVAL_ARMING_STATE_CHANGED"}
    if str(ticket.get("confirmation_phrase_digest") or "") != digest(CONFIRMATION_PHRASE):
        return {"state": "BLOCKED", "reason": "ACTIVATION_APPROVAL_CONFIRMATION_PROOF_MISMATCH"}
    if str(ticket.get("coordination_mode") or "") != CURRENT_COORDINATION_MODE:
        return {
            "state": "BLOCKED",
            "reason": "MULTI_INSTANCE_EXECUTION_NOT_AVAILABLE",
        }
    if str(ticket.get("coordination_gate_state") or "") != "READY_CURRENT_MODE":
        return {
            "state": "BLOCKED",
            "reason": "COORDINATION_GATE_STATE_INVALID",
        }
    if ticket.get("multi_instance_operationally_verified") is not False:
        return {
            "state": "BLOCKED",
            "reason": "COORDINATION_EVIDENCE_INCONSISTENT",
        }

    return {
        "state": "APPROVED",
        "reason": "",
        "approval_digest": str(ticket.get("approval_digest") or ""),
        "runtime_sha": runtime["runtime_sha"],
        "coordination_mode": CURRENT_COORDINATION_MODE,
        "multi_instance_operationally_verified": False,
    }


def write_repository_feature_flag_enabled(
    config: RuntimeConfig,
    prior_state: str,
    *,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Enable only the named Global Worker repository variable."""
    if not config.repo or not config.token:
        return {
            "status": "UNAVAILABLE",
            "modified": False,
            "reason": "Repository/token required for flag mutation.",
        }
    state = str(prior_state or "").upper()
    if state not in SAFE_FLAG_STATES:
        return {
            "status": "BLOCKED",
            "modified": False,
            "reason": "Feature flag is not in an enable-safe prior state.",
        }

    headers = _headers(config.token)
    try:
        if state == "UNSET":
            response = github_post(
                _variable_collection_url(config),
                headers=headers,
                json={"name": FEATURE_FLAG_NAME, "value": ENABLED_VALUE},
                timeout=timeout,
            )
        else:
            response = github_patch(
                _variable_url(config),
                headers=headers,
                json={"name": FEATURE_FLAG_NAME, "value": ENABLED_VALUE},
                timeout=timeout,
            )
        response.raise_for_status()
        return {
            "status": "WRITE_ACCEPTED",
            "modified": True,
            "previous_state": state,
            "target_state": "ENABLED",
            "raw_value_exposed": False,
        }
    except Exception as exc:
        return {
            "status": "ERROR",
            "modified": False,
            "reason": type(exc).__name__,
            "previous_state": state,
            "target_state": "ENABLED",
            "raw_value_exposed": False,
        }


def force_disable_repository_feature_flag(
    config: RuntimeConfig,
    *,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Safety rollback: ensure the variable is present with a disabled value."""
    if not config.repo or not config.token:
        return {
            "status": "UNAVAILABLE",
            "modified": False,
            "reason": "Repository/token required for safety rollback.",
        }
    headers = _headers(config.token)
    try:
        response = github_patch(
            _variable_url(config),
            headers=headers,
            json={"name": FEATURE_FLAG_NAME, "value": DISABLED_VALUE},
            timeout=timeout,
        )
        if response.status_code == 404:
            response = github_post(
                _variable_collection_url(config),
                headers=headers,
                json={"name": FEATURE_FLAG_NAME, "value": DISABLED_VALUE},
                timeout=timeout,
            )
        response.raise_for_status()
        return {
            "status": "DISABLED",
            "modified": True,
            "target_state": "DISABLED",
            "raw_value_exposed": False,
        }
    except Exception as exc:
        return {
            "status": "ERROR",
            "modified": False,
            "reason": type(exc).__name__,
            "target_state": "DISABLED",
            "raw_value_exposed": False,
        }


def activate_global_worker_feature_flag(
    access: Mapping[str, Any] | None,
    runtime_result: Mapping[str, Any],
    approval: Mapping[str, Any] | None,
    config: RuntimeConfig,
    *,
    confirmation: bool,
    reactivation_gate: Mapping[str, Any] | None = None,
    timeout: float = 10.0,
    flag_reader: Callable[..., Mapping[str, Any]] = read_repository_feature_flag,
    flag_writer: Callable[..., Mapping[str, Any]] = write_repository_feature_flag_enabled,
    flag_disabler: Callable[..., Mapping[str, Any]] = force_disable_repository_feature_flag,
    runtime_reader: Callable[..., Mapping[str, Any]] = load_runtime_checkpoint,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Enable the wake-up flag after final confirmation; never runs a worker tick."""
    if confirmation is not True:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "FINAL_EXPLICIT_CONFIRMATION_REQUIRED",
            "feature_flag_modified": False,
            "global_worker_executed": False,
        }
    current = utc(now or _now())
    fresh_runtime = dict(
        runtime_reader(config, timeout=min(timeout, 10.0)) or {}
    )
    validation = validate_global_worker_activation_approval(
        access,
        fresh_runtime,
        approval,
        now=now,
    )
    if validation.get("state") != "APPROVED":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": str(validation.get("reason") or "ACTIVATION_APPROVAL_REQUIRED"),
            "feature_flag_modified": False,
            "global_worker_executed": False,
        }

    pre_flag = dict(flag_reader(config, timeout=timeout) or {})
    pre_state = str(pre_flag.get("state") or "").upper()
    if (
        str(pre_flag.get("status") or "").upper() != "CONFIRMED"
        or pre_state not in SAFE_FLAG_STATES
        or pre_flag.get("safe_for_arming_persistence") is not True
    ):
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "FEATURE_FLAG_NOT_PROVEN_DISABLED_BEFORE_ACTIVATION",
            "feature_flag_state": pre_state or "UNKNOWN",
            "feature_flag_modified": False,
            "global_worker_executed": False,
        }
    if pre_state != str((approval or {}).get("feature_flag_state_at_plan") or ""):
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "ACTIVATION_APPROVAL_FLAG_STATE_CHANGED",
            "feature_flag_state": pre_state,
            "feature_flag_modified": False,
            "global_worker_executed": False,
        }

    gate_execution = validate_reactivation_gate_for_execution(
        fresh_runtime,
        pre_flag,
        approval,
        reactivation_gate,
        now=current,
    )
    if gate_execution.get("state") != "READY":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": str(
                gate_execution.get("reason")
                or "FRESH_POST_INCIDENT_REACTIVATION_GATE_REQUIRED"
            ),
            "feature_flag_state": pre_state,
            "feature_flag_modified": False,
            "global_worker_executed": False,
            "reactivation_gate_checked": True,
        }

    write = dict(flag_writer(config, pre_state, timeout=timeout) or {})
    if write.get("status") != "WRITE_ACCEPTED" or write.get("modified") is not True:
        observed_after_failed_write = dict(
            flag_reader(config, timeout=timeout) or {}
        )
        observed_state = str(
            observed_after_failed_write.get("state") or ""
        ).upper()
        if observed_state == "ENABLED":
            rollback = dict(flag_disabler(config, timeout=timeout) or {})
            rollback_confirm = dict(flag_reader(config, timeout=timeout) or {})
            rollback_safe = bool(
                str(rollback_confirm.get("status") or "").upper() == "CONFIRMED"
                and str(rollback_confirm.get("state") or "").upper()
                in SAFE_FLAG_STATES
            )
            return {
                "schema": SCHEMA,
                "status": (
                    "ACTIVATION_ROLLED_BACK"
                    if rollback_safe
                    else "CRITICAL_ACTIVATION_ROLLBACK_FAILED"
                ),
                "reason": "FEATURE_FLAG_WRITE_OUTCOME_UNCERTAIN_AND_ENABLED",
                "feature_flag_modified": not rollback_safe,
                "global_worker_executed": False,
                "live_heartbeat_confirmed": False,
                "runtime_checkpoint_modified": False,
                "real_trading_enabled": False,
                "flag_write": write,
                "rollback": rollback,
                "rollback_verified_safe": rollback_safe,
            }
        return {
            "schema": SCHEMA,
            "status": "ERROR",
            "reason": str(write.get("reason") or "FEATURE_FLAG_ENABLE_WRITE_FAILED"),
            "feature_flag_modified": False,
            "global_worker_executed": False,
            "flag_write": write,
            "observed_feature_flag_state": observed_state or "UNKNOWN",
        }

    post_flag = dict(flag_reader(config, timeout=timeout) or {})
    post_runtime = dict(
        runtime_reader(config, timeout=min(timeout, 10.0)) or {}
    )
    post_runtime_validation = validate_global_worker_activation_approval(
        access,
        post_runtime,
        approval,
        now=now,
    )
    if (
        str(post_flag.get("status") or "").upper() == "CONFIRMED"
        and str(post_flag.get("state") or "").upper() == "ENABLED"
        and post_runtime_validation.get("state") == "APPROVED"
    ):
        return {
            "schema": SCHEMA,
            "status": "ACTIVATED_PENDING_LIVE_EVIDENCE",
            "feature_flag_state": "ENABLED",
            "feature_flag_modified": True,
            "global_worker_executed": False,
            "live_heartbeat_confirmed": False,
            "live_receipt_confirmed": False,
            "runtime_checkpoint_modified": False,
            "real_trading_enabled": False,
            "activation_approval_digest": str((approval or {}).get("approval_digest") or ""),
            "post_incident_gate_required": bool(
                (approval or {}).get("post_incident_gate_required")
            ),
            "post_incident_gate_verified_before_write": True,
            "reactivation_authorized_by_gate": False,
            "activated_at": current.isoformat(),
            "runtime_sha_verified_after_write": str(post_runtime.get("sha") or ""),
            "next_required_evidence": "GLOBAL_WORKER_LIVE_HEARTBEAT_AND_RECEIPT",
        }

    rollback = dict(flag_disabler(config, timeout=timeout) or {})
    rollback_confirm = dict(flag_reader(config, timeout=timeout) or {})
    rollback_safe = bool(
        str(rollback_confirm.get("status") or "").upper() == "CONFIRMED"
        and str(rollback_confirm.get("state") or "").upper() in SAFE_FLAG_STATES
    )
    return {
        "schema": SCHEMA,
        "status": (
            "ACTIVATION_ROLLED_BACK"
            if rollback_safe
            else "CRITICAL_ACTIVATION_ROLLBACK_FAILED"
        ),
        "reason": (
            "RUNTIME_CHANGED_DURING_ACTIVATION"
            if post_runtime_validation.get("state") != "APPROVED"
            else "FEATURE_FLAG_ENABLE_NOT_CONFIRMED_AFTER_WRITE"
        ),
        "feature_flag_modified": not rollback_safe,
        "global_worker_executed": False,
        "live_heartbeat_confirmed": False,
        "runtime_checkpoint_modified": False,
        "real_trading_enabled": False,
        "flag_write": write,
        "rollback": rollback,
        "rollback_verified_safe": rollback_safe,
        "rollback_feature_flag_state": str(
            rollback_confirm.get("state") or "UNKNOWN"
        ),
    }


def deactivate_global_worker_feature_flag(
    access: Mapping[str, Any] | None,
    config: RuntimeConfig,
    *,
    confirmation: bool,
    confirmation_phrase: str,
    timeout: float = 10.0,
    flag_reader: Callable[..., Mapping[str, Any]] = read_repository_feature_flag,
    flag_disabler: Callable[..., Mapping[str, Any]] = force_disable_repository_feature_flag,
) -> dict[str, Any]:
    """Explicit ADMIN stop path for future activated deployments."""
    context = authenticated_context(access, Domain.ADMIN)
    if context.role != "ADMIN":
        raise ValueError("ADMIN_REQUIRED")
    if confirmation is not True:
        return {"schema": SCHEMA, "status": "BLOCKED", "reason": "EXPLICIT_CONFIRMATION_REQUIRED"}
    if str(confirmation_phrase or "").strip() != DEACTIVATION_PHRASE:
        return {"schema": SCHEMA, "status": "BLOCKED", "reason": "DEACTIVATION_PHRASE_MISMATCH"}

    before = dict(flag_reader(config, timeout=timeout) or {})
    if (
        str(before.get("status") or "").upper() == "CONFIRMED"
        and str(before.get("state") or "").upper() in SAFE_FLAG_STATES
    ):
        return {
            "schema": SCHEMA,
            "status": "ALREADY_DISABLED",
            "feature_flag_state": str(before.get("state") or ""),
            "feature_flag_modified": False,
            "global_worker_executed": False,
        }

    disabled = dict(flag_disabler(config, timeout=timeout) or {})
    after = dict(flag_reader(config, timeout=timeout) or {})
    confirmed = bool(
        str(after.get("status") or "").upper() == "CONFIRMED"
        and str(after.get("state") or "").upper() in SAFE_FLAG_STATES
    )
    return {
        "schema": SCHEMA,
        "status": "DISABLED" if confirmed else "CRITICAL_DISABLE_NOT_CONFIRMED",
        "feature_flag_state": str(after.get("state") or "UNKNOWN"),
        "feature_flag_modified": bool(disabled.get("modified")),
        "global_worker_executed": False,
        "real_trading_enabled": False,
        "disable_result": disabled,
    }


__all__ = [
    "SCHEMA",
    "PLAN_SCHEMA",
    "APPROVAL_SCHEMA",
    "CONFIRMATION_PHRASE",
    "DEACTIVATION_PHRASE",
    "READY_STAGE",
    "collect_activation_readiness_evidence",
    "plan_integrity",
    "approval_integrity",
    "prepare_global_worker_activation_plan",
    "approve_global_worker_activation_plan",
    "validate_global_worker_activation_approval",
    "write_repository_feature_flag_enabled",
    "force_disable_repository_feature_flag",
    "activate_global_worker_feature_flag",
    "deactivate_global_worker_feature_flag",
]
