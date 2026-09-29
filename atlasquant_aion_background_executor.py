"""Controlled local executor for due AION Core schedules.

V1 is an execution kernel, not an autonomous daemon. It only runs when the
authenticated administrator explicitly invokes it. It executes allowlisted
local/read-or-draft Core capabilities, persists idempotent receipts in the
working Checkpoint Mestre, applies retry backoff to exceptions, and never
performs physical/external actions.
"""
from __future__ import annotations

from bisect import insort
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import re
from typing import Any, Mapping

from atlasquant_aion_core import guardian_decision
from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_intelligence.evidence import digest, safe_text, utc
from atlasquant_aion_core_intelligence.router import words
from atlasquant_aion_core_intelligence.service import SENSITIVE_INTENTS
from atlasquant_aion_core_runtime_bridge import (
    authenticated_context,
    handle_runtime_intent,
)
from atlasquant_aion_core_voice_automation import CheckpointAutomationAdapter
from atlasquant_aion_observability import redact_text
from atlasquant_aion_action_receipt_bridge import seal_executor_receipt_envelope


SCHEMA = "ATLASQUANT_AION_BACKGROUND_EXECUTOR_V1"
EXECUTOR_NAMESPACE = "aion_core_executor_v1"
EXECUTOR_SCHEMA = "AION_CORE_EXECUTOR_CHECKPOINT_V1"

ALLOWLISTED_CAPABILITIES = frozenset({
    "ADMINISTRATION",
    "MEMORY",
    "RESEARCH",
    "VOICE",
    "CONTENT",
    "OBSERVABILITY",
})
DRAFT_CAPABILITIES = frozenset({"VOICE", "CONTENT"})
TERMINAL_STATES = frozenset({"SUCCEEDED", "BLOCKED"})
RECEIPT_STATES = frozenset({"SUCCEEDED", "FAILED", "BLOCKED"})
MAX_RECEIPTS = 1000
MAX_JOBS_PER_RUN = 20
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = (60, 300, 900)


def _select_due_schedules(values: Any, limit: int) -> tuple[list[Mapping[str, Any]], int]:
    """Select the earliest due rows with O(limit) memory while preserving total due count."""
    selected: list[tuple[str, str, int, Mapping[str, Any]]] = []
    due_count = 0
    sequence = 0
    for row in values or ():
        if not isinstance(row, Mapping) or row.get("due") is not True:
            continue
        due_count += 1
        entry = (
            str(row.get("due_at") or ""),
            str(row.get("schedule_id") or ""),
            sequence,
            row,
        )
        sequence += 1
        insort(selected, entry)
        if len(selected) > limit:
            selected.pop()
    return [entry[3] for entry in selected], due_count


def _scope_payload(context) -> list[str]:
    return json.loads(context.key)


def _bundle_digest(bundle: Mapping[str, Any]) -> str:
    raw = dict(bundle or {})
    raw.pop("digest", None)
    return digest(raw)


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


def _result_preview(payload: Any) -> str:
    try:
        raw = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    except Exception:
        raw = str(payload or "")
    text = re.sub(
        r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----",
        "[REDACTED]",
        raw,
        flags=re.S,
    )
    text = re.sub(
        r"(https?://)[^\s/@]+:[^\s/@]+@",
        r"\1[REDACTED]@",
        text,
    )
    return redact_text(text)[:4000]


def _schedule_fingerprint(schedule: Mapping[str, Any]) -> str:
    return digest({
        "schedule_id": str(schedule.get("schedule_id") or ""),
        "title": str(schedule.get("title") or ""),
        "prompt": str(schedule.get("prompt") or ""),
        "capability": str(schedule.get("capability") or ""),
        "cadence": str(schedule.get("cadence") or ""),
        "timezone": str(schedule.get("timezone") or ""),
        "hour": schedule.get("hour"),
        "minute": schedule.get("minute"),
        "weekday": schedule.get("weekday"),
        "run_at": str(schedule.get("run_at") or ""),
    })


def _occurrence_key(context, schedule: Mapping[str, Any], due_at: str) -> str:
    return digest({
        "scope": context.key,
        "schedule_fingerprint": _schedule_fingerprint(schedule),
        "due_at": due_at,
    })


def executor_integrity(raw: Mapping[str, Any] | None) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        return {"state": "ABSENT", "stored": "", "expected": ""}
    if raw.get("schema") != EXECUTOR_SCHEMA:
        return {"state": "MISMATCH", "stored": "", "expected": EXECUTOR_SCHEMA}
    supplied = str(raw.get("digest") or "").strip()
    expected = _bundle_digest(raw)
    return {
        "state": "MATCH" if supplied and supplied == expected else "MISMATCH",
        "stored": supplied,
        "expected": expected,
    }


def load_executor_receipts(
    context,
    checkpoint: Mapping[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = dict(checkpoint or {})
    raw = payload.get(EXECUTOR_NAMESPACE)
    if raw is None:
        return [], {"state": "EMPTY", "reason": "EXECUTOR_NAMESPACE_ABSENT"}
    if not isinstance(raw, Mapping):
        raise ValueError("EXECUTOR_CHECKPOINT_MISMATCH")
    integrity = executor_integrity(raw)
    if integrity["state"] != "MATCH":
        raise ValueError("EXECUTOR_CHECKPOINT_MISMATCH")
    if raw.get("scope") != _scope_payload(context):
        return [], {"state": "CONTEXT_ISOLATED", "reason": "EXECUTOR_CONTEXT_MISMATCH"}
    rows = raw.get("receipts", [])
    if not isinstance(rows, list) or len(rows) > MAX_RECEIPTS:
        raise ValueError("invalid executor receipts")
    clean = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("invalid executor receipt")
        item = dict(row)
        if str(item.get("state") or "") not in RECEIPT_STATES:
            raise ValueError("invalid executor receipt state")
        if not str(item.get("occurrence_key") or "").strip():
            raise ValueError("executor occurrence key required")
        clean.append(item)
    return clean, {"state": "CONNECTED", "reason": "", "count": len(clean)}


def attach_executor_receipts(
    checkpoint: Mapping[str, Any],
    context,
    receipts: list[Mapping[str, Any]],
    *,
    now: datetime,
) -> dict[str, Any]:
    rows = [deepcopy(dict(x)) for x in receipts]
    if len(rows) > MAX_RECEIPTS:
        rows = rows[-MAX_RECEIPTS:]
    out = deepcopy(dict(checkpoint or {}))
    previous = out.get(EXECUTOR_NAMESPACE)
    if isinstance(previous, Mapping) and previous.get("scope") != _scope_payload(context):
        raise ValueError("EXECUTOR_CONTEXT_MISMATCH")
    authorization_modes = sorted({
        str(row.get("authorization_mode") or "HUMAN_CLICK")
        for row in rows
        if isinstance(row, Mapping)
    })
    armed_worker_observed = "ARMED_WORKER" in authorization_modes
    global_worker_observed = "GLOBAL_WORKER" in authorization_modes
    bundle = {
        "schema": EXECUTOR_SCHEMA,
        "scope": _scope_payload(context),
        "updated_at": utc(now).isoformat(),
        "receipts": rows,
        "authorization_modes_observed": authorization_modes,
        "manual_invocation_only": not armed_worker_observed,
        "armed_worker_execution_observed": armed_worker_observed,
        "autonomous_worker_connected": False,
        "physical_action_adapter": "UNAVAILABLE",
    }
    bundle["digest"] = _bundle_digest(bundle)
    out[EXECUTOR_NAMESPACE] = bundle
    return out


def _sensitive_marker(prompt: str) -> str:
    tokens = words(prompt)
    matched = sorted(
        action.value
        for action, markers in SENSITIVE_INTENTS.items()
        if tokens & markers
    )
    return ",".join(matched)


def _guardian_action(capability: str) -> str:
    return "draft" if capability in DRAFT_CAPABILITIES else "read"


def _latest_for_occurrence(
    receipts: list[Mapping[str, Any]],
    occurrence_key: str,
) -> list[dict[str, Any]]:
    rows = [
        deepcopy(dict(x))
        for x in receipts
        if str(x.get("occurrence_key") or "") == occurrence_key
    ]
    rows.sort(key=lambda x: int(x.get("attempt") or 0))
    return rows


def _receipt(
    *,
    context,
    schedule: Mapping[str, Any],
    occurrence_key: str,
    due_at: str,
    attempt: int,
    state: str,
    now: datetime,
    guardian: Mapping[str, Any],
    reason: str,
    result: Mapping[str, Any] | None = None,
    retry_after: datetime | None = None,
    approval_digest: str,
    authorization_mode: str = "HUMAN_CLICK",
    execution_principal: str = "",
) -> dict[str, Any]:
    if state not in RECEIPT_STATES:
        raise ValueError("invalid receipt state")
    payload = (result or {}).get("payload") if isinstance(result, Mapping) else None
    return {
        "schema": "AION_CORE_EXECUTION_RECEIPT_V1",
        "receipt_id": "RCPT-" + digest({
            "occurrence_key": occurrence_key,
            "attempt": attempt,
            "state": state,
        })[:20].upper(),
        "occurrence_key": occurrence_key,
        "schedule_id": str(schedule.get("schedule_id") or ""),
        "schedule_fingerprint": _schedule_fingerprint(schedule),
        "due_at": due_at,
        "attempt": attempt,
        "state": state,
        "capability": str(schedule.get("capability") or ""),
        "guardian_action": _guardian_action(str(schedule.get("capability") or "")),
        "guardian_allowed": guardian.get("allowed") is True,
        "guardian_risk": str(guardian.get("risk") or "UNKNOWN"),
        "guardian_reason": str(guardian.get("reason") or ""),
        "human_confirmation_digest": approval_digest if authorization_mode == "HUMAN_CLICK" else "",
        "authorization_digest": approval_digest,
        "authorization_mode": authorization_mode,
        "human_principal": context.actor_id if authorization_mode == "HUMAN_CLICK" else "",
        "delegated_actor": context.actor_id,
        "execution_principal": (
            safe_text(execution_principal, 160)
            if execution_principal
            else context.actor_id
        ),
        "started_at": utc(now).isoformat(),
        "completed_at": utc(now).isoformat(),
        "reason": str(reason or ""),
        "result_status": str((result or {}).get("status") or ""),
        "result_digest": digest(result or {}),
        "result_preview": _result_preview(payload) if payload is not None else "",
        "retry_after": retry_after.isoformat() if retry_after else "",
        "provider_called": (result or {}).get("provider_called") is True,
        "external_action_executed": (result or {}).get("external_action_executed") is True,
        "real_trading_enabled": (result or {}).get("real_trading_enabled") is True,
        "execution_authorized": False,
        "external_persisted": False,
    }


def executor_snapshot(
    access: Mapping[str, Any] | None,
    checkpoint: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = utc(now or datetime.now(timezone.utc))
    context = authenticated_context(access, Domain.ADMIN)
    receipts, state = load_executor_receipts(context, checkpoint)
    scheduler = CheckpointAutomationAdapter(context, checkpoint).snapshot(current)
    counts = {name: 0 for name in RECEIPT_STATES}
    for row in receipts:
        state_name = str(row.get("state") or "")
        if state_name in counts:
            counts[state_name] += 1
    authorization_modes = sorted({
        str(row.get("authorization_mode") or "HUMAN_CLICK")
        for row in receipts
        if isinstance(row, Mapping)
    })
    armed_worker_observed = "ARMED_WORKER" in authorization_modes
    global_worker_observed = "GLOBAL_WORKER" in authorization_modes
    return {
        "schema": SCHEMA,
        "status": state["state"],
        "receipts": receipts,
        "receipt_count": len(receipts),
        "by_state": counts,
        "due_count": int(scheduler.get("due_count") or 0),
        "authorization_modes_observed": authorization_modes,
        "manual_invocation_only": not (armed_worker_observed or global_worker_observed),
        "manual_run_available": True,
        "armed_worker_execution_observed": armed_worker_observed,
        "global_worker_execution_observed": global_worker_observed,
        "autonomous_worker_connected": False,
        "physical_action_adapter": "UNAVAILABLE",
        "external_action_executed": False,
        "real_trading_enabled": False,
    }


def _execute_due_local_work_authorized(
    access: Mapping[str, Any] | None,
    checkpoint: Mapping[str, Any],
    *,
    system_context: Mapping[str, Any] | None = None,
    voice_status: Mapping[str, Any] | None = None,
    authorization_mode: str,
    authorization_digest: str,
    execution_principal: str = "",
    capability_allowlist: frozenset[str] | set[str] | tuple[str, ...] | list[str] | None = None,
    max_jobs: int = 5,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Internal kernel after an authenticated authorization boundary."""
    if authorization_mode not in {"HUMAN_CLICK", "ARMED_WORKER", "GLOBAL_WORKER"}:
        raise ValueError("invalid executor authorization mode")
    if not isinstance(authorization_digest, str) or not authorization_digest.strip():
        raise ValueError("executor authorization digest required")
    if type(max_jobs) is not int or not 1 <= max_jobs <= MAX_JOBS_PER_RUN:
        raise ValueError("invalid executor batch size")
    current = utc(now or datetime.now(timezone.utc))
    context = authenticated_context(access, Domain.ADMIN)
    if context.role != "ADMIN":
        raise ValueError("ADMIN_REQUIRED")

    receipts, receipt_state = load_executor_receipts(context, checkpoint)
    if receipt_state["state"] == "CONTEXT_ISOLATED":
        raise ValueError("EXECUTOR_CONTEXT_MISMATCH")
    scheduler = CheckpointAutomationAdapter(context, checkpoint).snapshot(current)
    due, due_count = _select_due_schedules(
        scheduler.get("schedules"),
        max_jobs,
    )

    approval_digest = authorization_digest
    allowed_capabilities = (
        frozenset(str(x).strip().upper() for x in capability_allowlist)
        if capability_allowlist is not None
        else ALLOWLISTED_CAPABILITIES
    )
    if not allowed_capabilities or not allowed_capabilities.issubset(ALLOWLISTED_CAPABILITIES):
        raise ValueError("invalid executor capability allowlist")
    outcomes = []
    action_receipts = []
    added = 0

    for schedule in due:
        due_at = str(schedule.get("due_at") or "")
        capability = str(schedule.get("capability") or "").strip().upper()
        occurrence_key = _occurrence_key(context, schedule, due_at)
        history = _latest_for_occurrence(receipts, occurrence_key)
        if any(str(x.get("state") or "") in TERMINAL_STATES for x in history):
            outcomes.append({
                "schedule_id": schedule.get("schedule_id"),
                "occurrence_key": occurrence_key,
                "state": "SKIPPED",
                "reason": "IDEMPOTENT_TERMINAL_RECEIPT_EXISTS",
            })
            continue

        failures = [x for x in history if str(x.get("state") or "") == "FAILED"]
        if len(failures) >= MAX_ATTEMPTS:
            outcomes.append({
                "schedule_id": schedule.get("schedule_id"),
                "occurrence_key": occurrence_key,
                "state": "SKIPPED",
                "reason": "RETRY_EXHAUSTED",
            })
            continue
        if failures:
            retry_at = _parse_iso(failures[-1].get("retry_after"))
            if retry_at and current < retry_at:
                outcomes.append({
                    "schedule_id": schedule.get("schedule_id"),
                    "occurrence_key": occurrence_key,
                    "state": "SKIPPED",
                    "reason": "RETRY_BACKOFF_ACTIVE",
                    "retry_after": retry_at.isoformat(),
                })
                continue

        attempt = len(failures) + 1
        guardian_action = _guardian_action(capability or "UNKNOWN")
        guardian = guardian_decision(
            guardian_action,
            access,
            approved=False,
        )

        reason = ""
        terminal_result = None
        receipt_state_name = "BLOCKED"

        if capability not in allowed_capabilities:
            reason = "CAPABILITY_NOT_BACKGROUND_ALLOWLISTED"
        elif guardian.get("allowed") is not True:
            reason = "GUARDIAN_BLOCKED:" + str(guardian.get("reason") or "")
        else:
            sensitive = _sensitive_marker(str(schedule.get("prompt") or ""))
            if sensitive:
                reason = "SENSITIVE_INTENT_REQUIRES_INTERACTIVE_APPROVAL:" + sensitive
            else:
                try:
                    terminal_result = handle_runtime_intent(
                        access,
                        str(schedule.get("prompt") or ""),
                        system_context=system_context,
                        legacy_checkpoint=checkpoint,
                        voice_status=voice_status,
                        capability=capability,
                        now=current,
                    )
                    safety_values = [
                        terminal_result.get(key, False)
                        for key in (
                            "provider_called",
                            "external_action_executed",
                            "real_trading_enabled",
                            "execution_authorized",
                        )
                    ]
                    unsafe = any(
                        value is True or not isinstance(value, bool)
                        for value in safety_values
                    )
                    if unsafe:
                        reason = "RUNTIME_SAFETY_FLAG_VIOLATION"
                    elif str(terminal_result.get("status") or "") == "COMPLETED":
                        receipt_state_name = "SUCCEEDED"
                        reason = "LOCAL_CORE_HANDLER_COMPLETED"
                    else:
                        reason = (
                            "LOCAL_CORE_HANDLER_BLOCKED:"
                            + str(terminal_result.get("status") or "UNKNOWN")
                            + ":"
                            + str(terminal_result.get("reason") or "")
                        )
                except Exception as exc:
                    receipt_state_name = "FAILED"
                    reason = "LOCAL_EXECUTOR_EXCEPTION:" + type(exc).__name__

        retry_after = None
        if receipt_state_name == "FAILED" and attempt < MAX_ATTEMPTS:
            retry_after = current + timedelta(
                seconds=RETRY_BACKOFF_SECONDS[min(attempt - 1, len(RETRY_BACKOFF_SECONDS) - 1)]
            )
        receipt = _receipt(
            context=context,
            schedule=schedule,
            occurrence_key=occurrence_key,
            due_at=due_at,
            attempt=attempt,
            state=receipt_state_name,
            now=current,
            guardian=guardian,
            reason=reason,
            result=terminal_result,
            retry_after=retry_after,
            approval_digest=approval_digest,
            authorization_mode=authorization_mode,
            execution_principal=execution_principal,
        )
        receipts.append(receipt)
        action_receipts.append(
            seal_executor_receipt_envelope(receipt, context=context)
        )
        added += 1
        outcomes.append({
            "schedule_id": schedule.get("schedule_id"),
            "occurrence_key": occurrence_key,
            "receipt_id": receipt["receipt_id"],
            "state": receipt_state_name,
            "reason": reason,
            "retry_after": receipt["retry_after"],
        })

    staged = (
        attach_executor_receipts(checkpoint, context, receipts, now=current)
        if added
        else deepcopy(dict(checkpoint or {}))
    )
    succeeded = sum(1 for x in outcomes if x.get("state") == "SUCCEEDED")
    failed = sum(1 for x in outcomes if x.get("state") == "FAILED")
    blocked = sum(1 for x in outcomes if x.get("state") == "BLOCKED")
    return {
        "schema": SCHEMA,
        "status": (
            "NO_DUE_WORK"
            if not due
            else "COMPLETED"
            if failed == 0
            else "PARTIAL"
        ),
        "checkpoint": staged,
        "due_count": due_count,
        "processed": added,
        "succeeded": succeeded,
        "failed": failed,
        "blocked": blocked,
        "outcomes": outcomes,
        "action_receipts": action_receipts,
        "action_receipts_are_authority": False,
        "requires_checkpoint_save": added > 0,
        "external_persisted": False,
        "manual_invocation_only": authorization_mode == "HUMAN_CLICK",
        "authorization_mode": authorization_mode,
        "autonomous_worker_started": authorization_mode in {"ARMED_WORKER", "GLOBAL_WORKER"},
        "background_worker_connected": authorization_mode in {"ARMED_WORKER", "GLOBAL_WORKER"},
        "provider_called": False,
        "external_action_executed": False,
        "real_trading_enabled": False,
        "payment_executed": False,
        "publication_executed": False,
        "deploy_executed": False,
    }



def execute_due_local_work(
    access: Mapping[str, Any] | None,
    checkpoint: Mapping[str, Any],
    *,
    system_context: Mapping[str, Any] | None = None,
    voice_status: Mapping[str, Any] | None = None,
    confirmation: bool,
    max_jobs: int = 5,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Execute due safe-local Core jobs after one explicit authenticated click."""
    if confirmation is not True:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "EXPLICIT_HUMAN_CONFIRMATION_REQUIRED",
            "checkpoint": dict(checkpoint or {}),
            "processed": 0,
            "authorization_mode": "HUMAN_CLICK",
            "autonomous_worker_started": False,
            "external_action_executed": False,
        }
    current = utc(now or datetime.now(timezone.utc))
    context = authenticated_context(access, Domain.ADMIN)
    approval_digest = digest({
        "actor": context.actor_id,
        "scope": context.key,
        "confirmed_at": current.isoformat(),
        "authorization_mode": "HUMAN_CLICK",
    })
    return _execute_due_local_work_authorized(
        access,
        checkpoint,
        system_context=system_context,
        voice_status=voice_status,
        authorization_mode="HUMAN_CLICK",
        authorization_digest=approval_digest,
        max_jobs=max_jobs,
        now=current,
    )


__all__ = [
    "SCHEMA",
    "EXECUTOR_NAMESPACE",
    "EXECUTOR_SCHEMA",
    "ALLOWLISTED_CAPABILITIES",
    "MAX_ATTEMPTS",
    "RETRY_BACKOFF_SECONDS",
    "executor_integrity",
    "load_executor_receipts",
    "attach_executor_receipts",
    "executor_snapshot",
    "execute_due_local_work",
]
