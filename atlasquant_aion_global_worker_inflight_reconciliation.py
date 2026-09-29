"""Read-only reconciliation assessor for unresolved AION Global Worker inflight ticks.

This module never clears inflight state, retries work, writes the runtime,
changes feature flags, activates a worker, deploys, publishes, pays, or trades.
It only binds the persisted inflight work manifest to persisted executor
receipts so an operator can review a compact evidence package.
"""
from __future__ import annotations

from datetime import datetime, timezone
from itertools import islice
from typing import Any, Mapping

from atlasquant_aion_background_executor import load_executor_receipts
from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_intelligence.evidence import digest, utc
from atlasquant_aion_core_runtime_bridge import authenticated_context
from atlasquant_aion_global_worker import (
    MAX_JOBS,
    _delegated_access,
    load_global_worker_state,
)


SCHEMA = "ATLASQUANT_AION_GLOBAL_INFLIGHT_RECONCILIATION_V1"
TERMINAL_STATES = frozenset({"SUCCEEDED", "BLOCKED"})


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


def _receipt_is_safe(row: Mapping[str, Any]) -> bool:
    for key in (
        "provider_called",
        "external_action_executed",
        "real_trading_enabled",
        "execution_authorized",
    ):
        value = row.get(key, False)
        if not isinstance(value, bool) or value is True:
            return False
    return True


def assess_global_inflight_reconciliation(
    runtime_result: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a compact evidence package without mutating or retrying anything."""
    current = utc(now or _now())
    runtime = dict(runtime_result or {})
    if str(runtime.get("status") or "").upper() != "CONFIRMED":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "CONFIRMED_RUNTIME_REQUIRED",
            "reconciliation_required": True,
            "human_review_required": True,
            "automatic_clear_allowed": False,
            "automatic_retry_allowed": False,
            "executes_action": False,
        }
    checkpoint = runtime.get("checkpoint")
    if not isinstance(checkpoint, Mapping):
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "RUNTIME_CHECKPOINT_REQUIRED",
            "reconciliation_required": True,
            "human_review_required": True,
            "automatic_clear_allowed": False,
            "automatic_retry_allowed": False,
            "executes_action": False,
        }

    try:
        state, state_status = load_global_worker_state(checkpoint)
    except Exception as exc:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "GLOBAL_WORKER_STATE_INVALID:" + type(exc).__name__,
            "reconciliation_required": True,
            "human_review_required": True,
            "automatic_clear_allowed": False,
            "automatic_retry_allowed": False,
            "executes_action": False,
        }
    if state_status.get("state") != "CONNECTED":
        return {
            "schema": SCHEMA,
            "status": "NO_INFLIGHT",
            "reason": "GLOBAL_WORKER_STATE_NOT_CONNECTED",
            "reconciliation_required": False,
            "human_review_required": False,
            "automatic_clear_allowed": False,
            "automatic_retry_allowed": False,
            "executes_action": False,
        }

    inflight = state.get("inflight_tick")
    if not isinstance(inflight, Mapping) or not inflight:
        return {
            "schema": SCHEMA,
            "status": "NO_INFLIGHT",
            "reason": "",
            "reconciliation_required": False,
            "human_review_required": False,
            "automatic_clear_allowed": False,
            "automatic_retry_allowed": False,
            "executes_action": False,
        }

    claimed_at = _parse_iso(inflight.get("claimed_at"))
    if claimed_at is None:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "INFLIGHT_CLAIM_TIMESTAMP_INVALID",
            "reconciliation_required": True,
            "human_review_required": True,
            "automatic_clear_allowed": False,
            "automatic_retry_allowed": False,
            "executes_action": False,
        }

    try:
        delegated_access = _delegated_access(state.get("delegation") or {})
        context = authenticated_context(delegated_access, Domain.ADMIN)
        receipts, receipt_state = load_executor_receipts(context, checkpoint)
    except Exception as exc:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "EXECUTOR_EVIDENCE_INVALID:" + type(exc).__name__,
            "reconciliation_required": True,
            "human_review_required": True,
            "automatic_clear_allowed": False,
            "automatic_retry_allowed": False,
            "executes_action": False,
        }
    if str(receipt_state.get("state") or "") not in {"EMPTY", "CONNECTED"}:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "EXECUTOR_EVIDENCE_NOT_CONNECTED",
            "reconciliation_required": True,
            "human_review_required": True,
            "automatic_clear_allowed": False,
            "automatic_retry_allowed": False,
            "executes_action": False,
        }

    occurrences = [
        dict(row)
        for row in islice(inflight.get("work_occurrences") or (), MAX_JOBS)
        if isinstance(row, Mapping)
    ]
    evidence_rows = []
    unsafe_evidence = False
    terminal_proven = 0
    failed_proven = 0
    no_terminal_evidence = 0
    inconsistent = 0

    for expected in occurrences:
        occurrence_key = str(expected.get("occurrence_key") or "")
        matching = [
            dict(row)
            for row in receipts
            if str(row.get("occurrence_key") or "") == occurrence_key
        ]
        valid = []
        row_inconsistent = False
        for receipt in matching:
            completed_at = _parse_iso(receipt.get("completed_at"))
            if (
                str(receipt.get("schedule_id") or "")
                != str(expected.get("schedule_id") or "")
                or str(receipt.get("due_at") or "")
                != str(expected.get("due_at") or "")
                or str(receipt.get("authorization_mode") or "")
                != "GLOBAL_WORKER"
                or completed_at is None
                or completed_at < claimed_at
            ):
                row_inconsistent = True
                continue
            valid.append(receipt)
            if not _receipt_is_safe(receipt):
                unsafe_evidence = True

        valid.sort(key=lambda row: int(row.get("attempt") or 0))
        terminal = [row for row in valid if str(row.get("state") or "") in TERMINAL_STATES]
        failed = [row for row in valid if str(row.get("state") or "") == "FAILED"]

        if row_inconsistent:
            classification = "INCONSISTENT_EVIDENCE"
            inconsistent += 1
        elif terminal:
            classification = "TERMINAL_PROVEN"
            terminal_proven += 1
        elif failed:
            classification = "FAILED_PROVEN"
            failed_proven += 1
        else:
            classification = "NO_TERMINAL_EVIDENCE"
            no_terminal_evidence += 1

        latest = valid[-1] if valid else {}
        evidence_rows.append({
            "schedule_id": str(expected.get("schedule_id") or ""),
            "occurrence_key": occurrence_key,
            "due_at": str(expected.get("due_at") or ""),
            "capability": str(expected.get("capability") or ""),
            "classification": classification,
            "receipt_count": len(valid),
            "latest_receipt_id": str(latest.get("receipt_id") or ""),
            "latest_state": str(latest.get("state") or ""),
            "latest_attempt": int(latest.get("attempt") or 0),
            "latest_completed_at": str(latest.get("completed_at") or ""),
        })

    expected_count = int(inflight.get("work_intent_count") or 0)
    if expected_count != len(occurrences):
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "INFLIGHT_WORK_COUNT_MISMATCH",
            "reconciliation_required": True,
            "human_review_required": True,
            "automatic_clear_allowed": False,
            "automatic_retry_allowed": False,
            "executes_action": False,
        }

    if unsafe_evidence:
        status = "BLOCKED_UNSAFE_EVIDENCE"
        suggested_resolution = "PRESERVE_AND_ESCALATE"
    elif inconsistent:
        status = "INCONSISTENT_EVIDENCE_REVIEW_REQUIRED"
        suggested_resolution = "PRESERVE_AND_REVIEW"
    elif expected_count == 0:
        status = "EMPTY_BATCH_READY_FOR_HUMAN_CLEAR"
        suggested_resolution = "CLEAR_INFLIGHT_NO_WORK"
    elif terminal_proven == expected_count:
        status = "TERMINAL_EVIDENCE_READY_FOR_HUMAN_CLEAR"
        suggested_resolution = "CLEAR_INFLIGHT_KEEP_TERMINAL_EVIDENCE"
    elif terminal_proven or failed_proven:
        status = "PARTIAL_EVIDENCE_REVIEW_REQUIRED"
        suggested_resolution = "REVIEW_BEFORE_ANY_RETRY"
    else:
        status = "AMBIGUOUS_EXECUTION_REVIEW_REQUIRED"
        suggested_resolution = "REVIEW_BEFORE_ANY_RETRY"

    package = {
        "runtime_sha": str(runtime.get("sha") or ""),
        "inflight_intent_id": str(inflight.get("intent_id") or ""),
        "work_intent_digest": str(inflight.get("work_intent_digest") or ""),
        "claimed_at": claimed_at.isoformat(),
        "evidence": evidence_rows,
        "status": status,
    }
    return {
        "schema": SCHEMA,
        "status": status,
        "reason": "",
        "assessed_at": current.isoformat(),
        "runtime_sha": str(runtime.get("sha") or ""),
        "inflight_owner": str(inflight.get("owner") or ""),
        "inflight_fencing_token": int(inflight.get("fencing_token") or 0),
        "inflight_since": claimed_at.isoformat(),
        "claim_age_seconds": max(0, int((current - claimed_at).total_seconds())),
        "work_intent_digest": str(inflight.get("work_intent_digest") or ""),
        "work_intent_count": expected_count,
        "terminal_proven": terminal_proven,
        "failed_proven": failed_proven,
        "no_terminal_evidence": no_terminal_evidence,
        "inconsistent_evidence": inconsistent,
        "unsafe_evidence": unsafe_evidence,
        "occurrences": evidence_rows,
        "reconciliation_digest": digest(package),
        "suggested_resolution": suggested_resolution,
        "reconciliation_required": True,
        "human_review_required": True,
        "automatic_clear_allowed": False,
        "automatic_retry_allowed": False,
        "runtime_modified": False,
        "feature_flag_modified": False,
        "global_worker_tick_executed": False,
        "external_business_action_executed": False,
        "real_trading_enabled": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "assess_global_inflight_reconciliation",
]
