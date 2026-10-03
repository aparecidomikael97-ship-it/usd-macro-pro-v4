"""Tamper-evident lifecycle journal for the AION unified request runtime.

This journal records deterministic request lifecycle facts only. It is scoped
to owner/tenant/workspace/request, hash chained, secret-redacted and bounded.
It never authorizes or executes external actions, promotes memory, or writes
the Checkpoint Mestre automatically.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping
import json
import math

from aion_chat.models import Scope
from atlasquant_aion_observability import redact_text

SCHEMA = "ATLASQUANT_AION_UNIFIED_JOURNAL_V1"
GENESIS = "GENESIS"
MAX_EVENTS = 256
MAX_METADATA_KEYS = 32
MAX_COLLECTION = 32

ROLE_IDS = frozenset({
    "orchestrator", "architect", "guardian", "prime",
    "shadow", "sentinel", "commercial", "educator",
})
ACTION_CLASSES = frozenset({"READ_ONLY", "LOW_RISK", "REQUIRES_APPROVAL", "BLOCKED"})
TRUTH_STATES = frozenset({"CONFIRMED", "INFERENCE", "HYPOTHESIS", "UNKNOWN"})
EVENT_TYPES = frozenset({
    "REQUEST_ACCEPTED",
    "ROLE_ROUTED",
    "PREFLIGHT_COMPLETED",
    "APPROVAL_PENDING",
    "DURABLE_HANDOFF_PREPARED",
    "RECOVERY_PREPARED",
    "REQUEST_BLOCKED",
})
_SECRET_MARKERS = (
    "secret", "token", "password", "credential", "api_key", "apikey",
    "authorization", "cookie", "private_key",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any, limit: int = 1200) -> str:
    return " ".join(redact_text(str(value or "")).replace("\x00", "").split())[:limit]


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
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _safe_value(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return "[TRUNCATED]"
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        return _clean(value, 1200)
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for index, (raw_key, raw_value) in enumerate(value.items()):
            if index >= MAX_METADATA_KEYS:
                break
            key = _clean(raw_key, 80)
            if not key:
                continue
            folded = key.casefold().replace("-", "_")
            if any(marker in folded for marker in _SECRET_MARKERS):
                out[key] = "[REDACTED]"
            else:
                out[key] = _safe_value(raw_value, depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        return [_safe_value(item, depth + 1) for item in list(value)[:MAX_COLLECTION]]
    return _clean(value, 1200)


def _scope_payload(scope: Scope) -> dict[str, str]:
    if not isinstance(scope, Scope):
        raise TypeError("Scope required")
    return {
        "owner_id": scope.owner_id,
        "tenant_id": scope.tenant_id,
        "workspace_id": scope.workspace_id,
    }


def new_request_journal(scope: Scope, request_id: str, conversation_id: str) -> dict[str, Any]:
    identity = _scope_payload(scope)
    rid = _clean(request_id, 160)
    cid = _clean(conversation_id, 160)
    if not rid or not cid:
        raise ValueError("request_id and conversation_id required")
    return {
        "schema": SCHEMA,
        **identity,
        "scope_fingerprint": _digest(identity),
        "request_id": rid,
        "conversation_id": cid,
        "revision": 0,
        "events": [],
        "head_digest": "",
        "external_persisted": False,
        "automatic_checkpoint_write": False,
        "memory_promoted": False,
        "external_action_executed": False,
    }


def verify_request_journal(
    journal: Mapping[str, Any],
    *,
    scope: Scope | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    row = dict(journal or {})
    reasons: list[str] = []
    if row.get("schema") != SCHEMA:
        reasons.append("SCHEMA_MISMATCH")

    identity = {
        "owner_id": _clean(row.get("owner_id"), 160),
        "tenant_id": _clean(row.get("tenant_id"), 160),
        "workspace_id": _clean(row.get("workspace_id"), 160),
    }
    if not all(identity.values()):
        reasons.append("SCOPE_MISSING")
    if row.get("scope_fingerprint") != _digest(identity):
        reasons.append("SCOPE_FINGERPRINT_MISMATCH")

    if scope is not None:
        expected = _scope_payload(scope)
        if identity != expected:
            reasons.append("SCOPE_MISMATCH")

    rid = _clean(row.get("request_id"), 160)
    cid = _clean(row.get("conversation_id"), 160)
    if not rid or not cid:
        reasons.append("REQUEST_IDENTITY_MISSING")
    if request_id is not None and rid != _clean(request_id, 160):
        reasons.append("REQUEST_MISMATCH")

    events = row.get("events")
    if not isinstance(events, list):
        reasons.append("EVENTS_INVALID")
        events = []
    if len(events) > MAX_EVENTS:
        reasons.append("EVENT_CAPACITY_EXCEEDED")

    revision = row.get("revision")
    if type(revision) is not int or revision != len(events):
        reasons.append("REVISION_MISMATCH")

    previous = GENESIS
    for index, raw in enumerate(events, start=1):
        if not isinstance(raw, Mapping):
            reasons.append(f"EVENT_{index}_INVALID")
            continue
        event = dict(raw)
        if event.get("sequence") != index:
            reasons.append(f"EVENT_{index}_SEQUENCE_MISMATCH")
        if event.get("request_id") != rid or event.get("conversation_id") != cid:
            reasons.append(f"EVENT_{index}_REQUEST_MISMATCH")
        if event.get("prev_digest") != previous:
            reasons.append(f"EVENT_{index}_CHAIN_MISMATCH")
        if event.get("event_type") not in EVENT_TYPES:
            reasons.append(f"EVENT_{index}_TYPE_INVALID")
        role = str(event.get("selected_role") or "")
        if role and role not in ROLE_IDS:
            reasons.append(f"EVENT_{index}_ROLE_INVALID")
        action_class = str(event.get("authorization_class") or "")
        if action_class and action_class not in ACTION_CLASSES:
            reasons.append(f"EVENT_{index}_AUTH_INVALID")
        truth = str(event.get("truth_state") or "")
        if truth and truth not in TRUTH_STATES:
            reasons.append(f"EVENT_{index}_TRUTH_INVALID")
        if event.get("external_action_executed") is not False:
            reasons.append(f"EVENT_{index}_EXECUTION_CLAIM_INVALID")

        body = dict(event)
        supplied_digest = str(body.pop("event_digest", "") or "")
        try:
            expected_digest = _digest(body)
        except Exception:
            expected_digest = ""
        if not supplied_digest or supplied_digest != expected_digest:
            reasons.append(f"EVENT_{index}_DIGEST_MISMATCH")
        previous = supplied_digest or previous

    expected_head = "" if not events else previous
    if str(row.get("head_digest") or "") != expected_head:
        reasons.append("HEAD_DIGEST_MISMATCH")
    if row.get("external_action_executed") is not False:
        reasons.append("JOURNAL_EXECUTION_CLAIM_INVALID")
    if row.get("memory_promoted") is not False:
        reasons.append("JOURNAL_MEMORY_CLAIM_INVALID")
    if row.get("automatic_checkpoint_write") is not False:
        reasons.append("JOURNAL_CHECKPOINT_CLAIM_INVALID")

    return {
        "schema": SCHEMA,
        "status": "CONFIRMED" if not reasons else "MISMATCH",
        "valid": not reasons,
        "reasons": reasons,
        "revision": len(events),
        "head_digest": expected_head,
        "external_action_executed": False,
    }


def append_request_event(
    journal: Mapping[str, Any],
    *,
    event_type: str,
    selected_role: str = "",
    authorization_class: str = "",
    truth_state: str = "",
    state: str = "",
    metadata: Mapping[str, Any] | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    current = deepcopy(dict(journal or {}))
    verification = verify_request_journal(current)
    if verification["valid"] is not True:
        raise ValueError("journal integrity mismatch")
    if len(current["events"]) >= MAX_EVENTS:
        raise ValueError("journal capacity reached")

    kind = _clean(event_type, 80).upper()
    if kind not in EVENT_TYPES:
        raise ValueError("invalid journal event type")
    role = _clean(selected_role, 80).lower()
    if role and role not in ROLE_IDS:
        raise ValueError("invalid journal role")
    action_class = _clean(authorization_class, 80).upper()
    if action_class and action_class not in ACTION_CLASSES:
        raise ValueError("invalid authorization class")
    truth = _clean(truth_state, 80).upper()
    if truth and truth not in TRUTH_STATES:
        raise ValueError("invalid truth state")

    sequence = len(current["events"]) + 1
    body = {
        "schema": SCHEMA,
        "sequence": sequence,
        "request_id": current["request_id"],
        "conversation_id": current["conversation_id"],
        "event_type": kind,
        "selected_role": role,
        "authorization_class": action_class,
        "truth_state": truth,
        "state": _clean(state, 80).upper(),
        "metadata": _safe_value(dict(metadata or {})),
        "observed_at": _clean(observed_at or _now(), 120),
        "prev_digest": current["head_digest"] or GENESIS,
        "external_action_executed": False,
    }
    event = {**body, "event_digest": _digest(body)}
    current["events"].append(event)
    current["revision"] = sequence
    current["head_digest"] = event["event_digest"]
    return current


def journal_runtime_exchange(request: Any, response: Any, *, observed_at: str | None = None) -> dict[str, Any]:
    scope = request.scope
    if not isinstance(scope, Scope):
        raise TypeError("request scope required")
    if str(response.request_id) != str(request.request_id):
        raise ValueError("response request mismatch")
    if str(response.conversation_id) != str(request.conversation_id):
        raise ValueError("response conversation mismatch")

    journal = new_request_journal(scope, request.request_id, request.conversation_id)
    journal = append_request_event(
        journal,
        event_type="REQUEST_ACCEPTED",
        authorization_class=response.authorization_class,
        state="ACCEPTED",
        metadata={
            "requested_action": request.requested_action,
            "sector": request.sector,
            "attachment_count": len(tuple(request.attachments or ())),
            "message_digest": _digest(_clean(request.user_message, 4000)),
        },
        observed_at=observed_at,
    )
    journal = append_request_event(
        journal,
        event_type="ROLE_ROUTED",
        selected_role=response.selected_role,
        authorization_class=response.authorization_class,
        truth_state=response.truth_state,
        state="ROUTED",
        metadata={"supporting_roles": list(response.supporting_roles)},
        observed_at=observed_at,
    )
    state = str((response.task_events[0] if response.task_events else {}).get("state") or "PLANNED")
    journal = append_request_event(
        journal,
        event_type="REQUEST_BLOCKED" if response.authorization_class == "BLOCKED" else "PREFLIGHT_COMPLETED",
        selected_role=response.selected_role,
        authorization_class=response.authorization_class,
        truth_state=response.truth_state,
        state=state,
        metadata={
            "warnings": list(response.warnings),
            "pending_approvals": len(response.pending_approvals),
            "provider_state": response.provider_state,
            "model_lane": response.model_lane,
        },
        observed_at=observed_at,
    )
    if response.pending_approvals:
        journal = append_request_event(
            journal,
            event_type="APPROVAL_PENDING",
            selected_role=response.selected_role,
            authorization_class=response.authorization_class,
            truth_state=response.truth_state,
            state="WAITING_APPROVAL",
            metadata={"count": len(response.pending_approvals)},
            observed_at=observed_at,
        )
    return journal


__all__ = [
    "SCHEMA", "GENESIS", "MAX_EVENTS", "EVENT_TYPES",
    "new_request_journal", "verify_request_journal",
    "append_request_event", "journal_runtime_exchange",
]
