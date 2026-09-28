"""AION Global Worker Durable Incident Closure Record V1.

Guarded persistence for a previously recorded human Global Worker incident
closure decision. This module persists only an evidence-bound closure record in
the shared runtime Checkpoint.

It does not change Incident Center computed status, feature flags, Global Worker
arming/activation state, leases, ticks, workflow schedules, or trading state.

Real persistence requires:
1. a session-only human closure decision from the prior ceremony;
2. a short-lived ADMIN persistence plan;
3. exact persistence phrase;
4. approval bound to runtime SHA/checkpoint digest/flag/worker state;
5. a second explicit confirmation immediately before the write;
6. CAS write + read-after-write verification;
7. rollback if post-write invariants fail.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from typing import Any, Mapping, Callable

from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_intelligence.evidence import digest, utc
from atlasquant_aion_core_runtime_bridge import authenticated_context
from atlasquant_aion_global_worker import GLOBAL_WORKER_NAMESPACE
from atlasquant_aion_global_worker_persisted_arming import (
    read_repository_feature_flag,
)
from atlasquant_aion_memory import (
    RuntimeConfig,
    checkpoint_source_digest,
    runtime_write_preflight,
    save_runtime_checkpoint,
)


SCHEMA = "ATLASQUANT_AION_GLOBAL_WORKER_DURABLE_INCIDENT_CLOSURE_V1"
PLAN_SCHEMA = "AION_GLOBAL_WORKER_DURABLE_CLOSURE_PLAN_V1"
APPROVAL_SCHEMA = "AION_GLOBAL_WORKER_DURABLE_CLOSURE_APPROVAL_V1"
LEDGER_SCHEMA = "ATLASQUANT_AION_GLOBAL_WORKER_INCIDENT_CLOSURE_LEDGER_V1"
RECORD_SCHEMA = "ATLASQUANT_AION_GLOBAL_WORKER_DURABLE_CLOSURE_RECORD_V1"

LEDGER_NAMESPACE = "aion_global_worker_incident_closure_ledger_v1"
CONFIRMATION_PHRASE = "PERSISTIR FECHAMENTO INCIDENTE WORKER GLOBAL"

DEFAULT_TTL_SECONDS = 600
MIN_TTL_SECONDS = 300
MAX_TTL_SECONDS = 1800
MAX_RECORDS = 100
KNOWN_FLAG_STATES = frozenset({"UNSET", "DISABLED", "ENABLED"})


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


def _worker_state_digest(checkpoint: Mapping[str, Any] | None) -> str:
    cp = dict(checkpoint or {})
    raw = cp.get(GLOBAL_WORKER_NAMESPACE)
    if isinstance(raw, Mapping):
        return digest({"present": True, "state": deepcopy(dict(raw))})
    return digest({"present": False, "state": None})


def _closure_contract(
    human_closure_record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    record = dict(human_closure_record or {})
    valid = bool(
        str(record.get("status") or "")
        == "HUMAN_CLOSURE_DECISION_RECORDED_SESSION_ONLY"
        and record.get("human_closure_decision_recorded") is True
        and str(record.get("human_closure_decision") or "") == "APPROVED"
        and record.get("authoritative_incident_closed") is False
        and record.get("persistent") is False
        and record.get("session_only") is True
        and record.get("reactivation_authorized") is False
        and record.get("executes_action") is False
    )
    closure_record_id = str(record.get("closure_record_id") or "").strip()
    closure_record_digest = str(
        record.get("closure_record_digest") or ""
    ).strip()
    closure_package_digest = str(
        record.get("closure_package_digest") or ""
    ).strip()
    incident_evidence_digest = str(
        record.get("incident_evidence_digest") or ""
    ).strip()
    remediation_digest = str(record.get("remediation_digest") or "").strip()
    recorded_at = _parse_iso(record.get("recorded_at"))

    if not (
        valid
        and closure_record_id.startswith("GW-CLOSE-")
        and closure_record_digest
        and closure_package_digest
        and incident_evidence_digest
        and remediation_digest
        and recorded_at is not None
    ):
        return {
            "state": "BLOCKED",
            "reason": "VALID_SESSION_HUMAN_CLOSURE_RECORD_REQUIRED",
        }

    return {
        "state": "READY",
        "reason": "",
        "closure_record_id": closure_record_id,
        "closure_record_digest": closure_record_digest,
        "closure_package_digest": closure_package_digest,
        "incident_evidence_digest": incident_evidence_digest,
        "remediation_digest": remediation_digest,
        "human_recorded_at": recorded_at.isoformat(),
        "operator_note_digest": digest(
            str(record.get("operator_note") or "").strip()
        ),
    }


def _ledger_digest_payload(ledger: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(ledger)
    raw.pop("digest", None)
    return raw


def _empty_ledger() -> dict[str, Any]:
    ledger = {
        "schema": LEDGER_SCHEMA,
        "records": [],
        "record_count": 0,
        "latest_record_id": "",
    }
    ledger["digest"] = digest(_ledger_digest_payload(ledger))
    return ledger


def load_closure_ledger(
    checkpoint: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    cp = dict(checkpoint or {})
    raw = cp.get(LEDGER_NAMESPACE)
    if raw is None:
        return _empty_ledger(), {
            "state": "ABSENT",
            "reason": "",
        }
    if not isinstance(raw, Mapping):
        return {}, {
            "state": "MISMATCH",
            "reason": "CLOSURE_LEDGER_NOT_MAPPING",
        }

    ledger = deepcopy(dict(raw))
    if str(ledger.get("schema") or "") != LEDGER_SCHEMA:
        return {}, {
            "state": "MISMATCH",
            "reason": "CLOSURE_LEDGER_SCHEMA_MISMATCH",
        }
    rows = ledger.get("records")
    if not isinstance(rows, list):
        return {}, {
            "state": "MISMATCH",
            "reason": "CLOSURE_LEDGER_RECORDS_INVALID",
        }
    stored = str(ledger.get("digest") or "")
    expected = digest(_ledger_digest_payload(ledger))
    if not stored or stored != expected:
        return {}, {
            "state": "MISMATCH",
            "reason": "CLOSURE_LEDGER_DIGEST_MISMATCH",
        }
    if int(ledger.get("record_count") or -1) != len(rows):
        return {}, {
            "state": "MISMATCH",
            "reason": "CLOSURE_LEDGER_COUNT_MISMATCH",
        }
    return ledger, {
        "state": "CONNECTED",
        "reason": "",
    }


def durable_record_state(
    checkpoint: Mapping[str, Any] | None,
    *,
    closure_record_id: str,
    closure_record_digest: str,
) -> dict[str, Any]:
    ledger, status = load_closure_ledger(checkpoint)
    if status.get("state") == "MISMATCH":
        return {
            "state": "BLOCKED",
            "reason": str(status.get("reason") or ""),
        }
    for row in list(ledger.get("records") or []):
        if not isinstance(row, Mapping):
            continue
        if str(row.get("closure_record_id") or "") != closure_record_id:
            continue
        if str(row.get("closure_record_digest") or "") == closure_record_digest:
            return {
                "state": "PERSISTED",
                "reason": "",
                "record": deepcopy(dict(row)),
            }
        return {
            "state": "CONFLICT",
            "reason": "CLOSURE_RECORD_ID_DIGEST_CONFLICT",
        }
    return {
        "state": "ABSENT",
        "reason": "",
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
    stored = str(plan.get("plan_digest") or "")
    expected = _payload_digest(plan, "plan_digest")
    return {
        "state": "MATCH" if stored and stored == expected else "MISMATCH",
        "stored": stored,
        "expected": expected,
    }


def approval_integrity(
    approval: Mapping[str, Any] | None,
) -> dict[str, str]:
    if not isinstance(approval, Mapping):
        return {"state": "ABSENT", "stored": "", "expected": ""}
    if str(approval.get("schema") or "") != APPROVAL_SCHEMA:
        return {
            "state": "MISMATCH",
            "stored": str(approval.get("approval_digest") or ""),
            "expected": APPROVAL_SCHEMA,
        }
    stored = str(approval.get("approval_digest") or "")
    expected = _payload_digest(approval, "approval_digest")
    return {
        "state": "MATCH" if stored and stored == expected else "MISMATCH",
        "stored": stored,
        "expected": expected,
    }


def prepare_durable_closure_plan(
    access: Mapping[str, Any] | None,
    human_closure_record: Mapping[str, Any],
    runtime_result: Mapping[str, Any],
    flag_evidence: Mapping[str, Any],
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Prepare a no-write plan bound to current runtime/flag/worker state."""
    current = utc(now or _now())
    context = authenticated_context(access, Domain.ADMIN)
    if context.role != "ADMIN":
        raise ValueError("ADMIN_REQUIRED")

    ttl = _exact_int(
        ttl_seconds,
        minimum=MIN_TTL_SECONDS,
        maximum=MAX_TTL_SECONDS,
        name="durable closure approval ttl",
    )
    closure = _closure_contract(human_closure_record)
    if closure.get("state") != "READY":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": str(closure.get("reason") or ""),
        }

    if str(runtime_result.get("status") or "").upper() != "CONFIRMED":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "CONFIRMED_RUNTIME_REQUIRED",
        }
    checkpoint = runtime_result.get("checkpoint")
    if not isinstance(checkpoint, Mapping):
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "RUNTIME_CHECKPOINT_REQUIRED",
        }
    preflight = runtime_write_preflight(runtime_result)
    if not preflight.get("allowed"):
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "RUNTIME_WRITE_PREFLIGHT_BLOCKED",
        }
    runtime_sha = str(runtime_result.get("sha") or "").strip()
    if not runtime_sha:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "RUNTIME_SHA_REQUIRED",
        }

    flag_status = str(flag_evidence.get("status") or "").upper()
    flag_state = str(flag_evidence.get("state") or "").upper()
    if flag_status != "CONFIRMED" or flag_state not in KNOWN_FLAG_STATES:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "AUTHORITATIVE_FEATURE_FLAG_EVIDENCE_REQUIRED",
        }

    ledger, ledger_status = load_closure_ledger(checkpoint)
    if ledger_status.get("state") == "MISMATCH":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": str(ledger_status.get("reason") or ""),
        }
    existing = durable_record_state(
        checkpoint,
        closure_record_id=str(closure["closure_record_id"]),
        closure_record_digest=str(closure["closure_record_digest"]),
    )
    if existing.get("state") == "PERSISTED":
        return {
            "schema": SCHEMA,
            "status": "ALREADY_PERSISTED",
            "reason": "",
            "record": existing.get("record"),
        }
    if existing.get("state") == "CONFLICT":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": str(existing.get("reason") or ""),
        }
    if len(list(ledger.get("records") or [])) >= MAX_RECORDS:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "CLOSURE_LEDGER_CAPACITY_REACHED",
        }

    expires = current + timedelta(seconds=ttl)
    plan = {
        "schema": PLAN_SCHEMA,
        "actor_id": context.actor_id,
        "scope": _scope_payload(context),
        "closure_record_id": closure["closure_record_id"],
        "closure_record_digest": closure["closure_record_digest"],
        "closure_package_digest": closure["closure_package_digest"],
        "incident_evidence_digest": closure["incident_evidence_digest"],
        "remediation_digest": closure["remediation_digest"],
        "human_recorded_at": closure["human_recorded_at"],
        "operator_note_digest": closure["operator_note_digest"],
        "source_runtime_sha": runtime_sha,
        "source_runtime_checkpoint_digest": checkpoint_source_digest(checkpoint),
        "source_worker_state_digest": _worker_state_digest(checkpoint),
        "source_ledger_digest": str(ledger.get("digest") or ""),
        "feature_flag_state": flag_state,
        "feature_flag_must_remain_unchanged": True,
        "worker_state_must_remain_unchanged": True,
        "created_at": current.isoformat(),
        "expires_at": expires.isoformat(),
        "ttl_seconds": ttl,
        "rollback": {
            "source_runtime_sha": runtime_sha,
            "source_runtime_checkpoint_digest": checkpoint_source_digest(
                checkpoint
            ),
            "automatic_on_post_write_invariant_violation": True,
        },
        "runtime_modified": False,
        "feature_flag_modified": False,
        "global_worker_modified": False,
        "reactivation_authorized": False,
        "real_trading_enabled": False,
    }
    plan["plan_digest"] = _payload_digest(plan, "plan_digest")
    return {
        "schema": SCHEMA,
        "status": "DURABLE_CLOSURE_PLAN_READY",
        "plan": plan,
        "runtime_modified": False,
        "feature_flag_modified": False,
        "global_worker_modified": False,
        "reactivation_authorized": False,
    }


def approve_durable_closure_plan(
    access: Mapping[str, Any] | None,
    plan: Mapping[str, Any],
    *,
    confirmation: bool,
    confirmation_phrase: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create a short-lived approval ticket. No persistence is performed."""
    current = utc(now or _now())
    context = authenticated_context(access, Domain.ADMIN)
    if confirmation is not True:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "EXPLICIT_CONFIRMATION_REQUIRED",
        }
    if str(confirmation_phrase or "").strip() != CONFIRMATION_PHRASE:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "CONFIRMATION_PHRASE_MISMATCH",
        }
    if plan_integrity(plan)["state"] != "MATCH":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "DURABLE_CLOSURE_PLAN_INTEGRITY_MISMATCH",
        }
    if (
        str(plan.get("actor_id") or "") != context.actor_id
        or plan.get("scope") != _scope_payload(context)
    ):
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "DURABLE_CLOSURE_PLAN_CONTEXT_MISMATCH",
        }
    expires = _parse_iso(plan.get("expires_at"))
    if expires is None or current >= expires:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "DURABLE_CLOSURE_PLAN_EXPIRED",
        }

    ticket = {
        "schema": APPROVAL_SCHEMA,
        "plan_digest": str(plan.get("plan_digest") or ""),
        "actor_id": context.actor_id,
        "scope": _scope_payload(context),
        "closure_record_id": str(plan.get("closure_record_id") or ""),
        "closure_record_digest": str(plan.get("closure_record_digest") or ""),
        "source_runtime_sha": str(plan.get("source_runtime_sha") or ""),
        "source_runtime_checkpoint_digest": str(
            plan.get("source_runtime_checkpoint_digest") or ""
        ),
        "source_worker_state_digest": str(
            plan.get("source_worker_state_digest") or ""
        ),
        "source_ledger_digest": str(plan.get("source_ledger_digest") or ""),
        "feature_flag_state": str(plan.get("feature_flag_state") or ""),
        "issued_at": current.isoformat(),
        "expires_at": str(plan.get("expires_at") or ""),
        "confirmation_phrase_digest": digest(CONFIRMATION_PHRASE),
        "runtime_modified": False,
        "feature_flag_modified": False,
        "global_worker_modified": False,
        "reactivation_authorized": False,
    }
    ticket["approval_digest"] = _payload_digest(ticket, "approval_digest")
    return {
        "schema": SCHEMA,
        "status": "APPROVED_FOR_DURABLE_CLOSURE_PERSISTENCE",
        "approval": ticket,
        "runtime_modified": False,
        "feature_flag_modified": False,
        "reactivation_authorized": False,
    }


def validate_durable_closure_approval(
    access: Mapping[str, Any] | None,
    human_closure_record: Mapping[str, Any],
    runtime_result: Mapping[str, Any],
    approval: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Fail closed if any evidence bound to the approval has changed."""
    current = utc(now or _now())
    context = authenticated_context(access, Domain.ADMIN)
    if approval_integrity(approval)["state"] != "MATCH":
        return {
            "state": "BLOCKED",
            "reason": "DURABLE_CLOSURE_APPROVAL_INTEGRITY_MISMATCH",
        }
    ticket = dict(approval or {})
    if (
        str(ticket.get("actor_id") or "") != context.actor_id
        or ticket.get("scope") != _scope_payload(context)
    ):
        return {
            "state": "BLOCKED",
            "reason": "DURABLE_CLOSURE_APPROVAL_CONTEXT_MISMATCH",
        }
    expires = _parse_iso(ticket.get("expires_at"))
    if expires is None or current >= expires:
        return {
            "state": "BLOCKED",
            "reason": "DURABLE_CLOSURE_APPROVAL_EXPIRED",
        }

    closure = _closure_contract(human_closure_record)
    if closure.get("state") != "READY":
        return {
            "state": "BLOCKED",
            "reason": str(closure.get("reason") or ""),
        }
    if (
        str(closure.get("closure_record_id") or "")
        != str(ticket.get("closure_record_id") or "")
        or str(closure.get("closure_record_digest") or "")
        != str(ticket.get("closure_record_digest") or "")
    ):
        return {
            "state": "BLOCKED",
            "reason": "DURABLE_CLOSURE_HUMAN_RECORD_CHANGED",
        }

    if str(runtime_result.get("status") or "").upper() != "CONFIRMED":
        return {
            "state": "BLOCKED",
            "reason": "CONFIRMED_RUNTIME_REQUIRED",
        }
    checkpoint = runtime_result.get("checkpoint")
    if not isinstance(checkpoint, Mapping):
        return {
            "state": "BLOCKED",
            "reason": "RUNTIME_CHECKPOINT_REQUIRED",
        }
    if str(runtime_result.get("sha") or "") != str(
        ticket.get("source_runtime_sha") or ""
    ):
        return {
            "state": "BLOCKED",
            "reason": "DURABLE_CLOSURE_RUNTIME_SHA_CHANGED",
        }
    if checkpoint_source_digest(checkpoint) != str(
        ticket.get("source_runtime_checkpoint_digest") or ""
    ):
        return {
            "state": "BLOCKED",
            "reason": "DURABLE_CLOSURE_RUNTIME_DIGEST_CHANGED",
        }
    if _worker_state_digest(checkpoint) != str(
        ticket.get("source_worker_state_digest") or ""
    ):
        return {
            "state": "BLOCKED",
            "reason": "DURABLE_CLOSURE_WORKER_STATE_CHANGED",
        }
    ledger, ledger_status = load_closure_ledger(checkpoint)
    if ledger_status.get("state") == "MISMATCH":
        return {
            "state": "BLOCKED",
            "reason": str(ledger_status.get("reason") or ""),
        }
    if str(ledger.get("digest") or "") != str(
        ticket.get("source_ledger_digest") or ""
    ):
        return {
            "state": "BLOCKED",
            "reason": "DURABLE_CLOSURE_LEDGER_CHANGED",
        }
    if str(ticket.get("confirmation_phrase_digest") or "") != digest(
        CONFIRMATION_PHRASE
    ):
        return {
            "state": "BLOCKED",
            "reason": "DURABLE_CLOSURE_CONFIRMATION_PROOF_MISMATCH",
        }

    return {
        "state": "APPROVED",
        "reason": "",
        "approval_digest": str(ticket.get("approval_digest") or ""),
        "source_runtime_sha": str(ticket.get("source_runtime_sha") or ""),
        "feature_flag_state": str(ticket.get("feature_flag_state") or ""),
    }


def build_durable_closure_checkpoint(
    checkpoint: Mapping[str, Any],
    human_closure_record: Mapping[str, Any],
    *,
    actor_id: str,
    source_runtime_sha: str,
    source_runtime_checkpoint_digest: str,
    feature_flag_state: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Pure builder; appends one immutable closure record to the ledger."""
    current = utc(now or _now())
    cp = deepcopy(dict(checkpoint or {}))
    closure = _closure_contract(human_closure_record)
    if closure.get("state") != "READY":
        raise ValueError(str(closure.get("reason") or "invalid closure record"))
    ledger, status = load_closure_ledger(cp)
    if status.get("state") == "MISMATCH":
        raise ValueError(str(status.get("reason") or "invalid closure ledger"))

    existing = durable_record_state(
        cp,
        closure_record_id=str(closure["closure_record_id"]),
        closure_record_digest=str(closure["closure_record_digest"]),
    )
    if existing.get("state") == "PERSISTED":
        return cp
    if existing.get("state") == "CONFLICT":
        raise ValueError("CLOSURE_RECORD_ID_DIGEST_CONFLICT")

    rows = [
        deepcopy(dict(row))
        for row in list(ledger.get("records") or [])
        if isinstance(row, Mapping)
    ]
    if len(rows) >= MAX_RECORDS:
        raise ValueError("CLOSURE_LEDGER_CAPACITY_REACHED")

    durable = {
        "schema": RECORD_SCHEMA,
        "closure_record_id": closure["closure_record_id"],
        "closure_record_digest": closure["closure_record_digest"],
        "closure_package_digest": closure["closure_package_digest"],
        "incident_evidence_digest": closure["incident_evidence_digest"],
        "remediation_digest": closure["remediation_digest"],
        "human_recorded_at": closure["human_recorded_at"],
        "operator_note_digest": closure["operator_note_digest"],
        "human_closure_decision": "APPROVED",
        "persisted_at": current.isoformat(),
        "persisted_by": str(actor_id or ""),
        "source_runtime_sha": str(source_runtime_sha or ""),
        "source_runtime_checkpoint_digest": str(
            source_runtime_checkpoint_digest or ""
        ),
        "feature_flag_state_at_persistence": str(
            feature_flag_state or ""
        ).upper(),
        "authoritative_incident_center_status_modified": False,
        "reactivation_authorized": False,
        "feature_flag_modified": False,
        "global_worker_modified": False,
        "real_trading_enabled": False,
    }
    durable["record_digest"] = _payload_digest(durable, "record_digest")
    rows.append(durable)

    updated_ledger = {
        "schema": LEDGER_SCHEMA,
        "records": rows,
        "record_count": len(rows),
        "latest_record_id": str(durable["closure_record_id"]),
    }
    updated_ledger["digest"] = digest(
        _ledger_digest_payload(updated_ledger)
    )
    cp[LEDGER_NAMESPACE] = updated_ledger
    return cp


def persist_human_incident_closure_record(
    access: Mapping[str, Any] | None,
    human_closure_record: Mapping[str, Any],
    runtime_result: Mapping[str, Any],
    approval: Mapping[str, Any] | None,
    config: RuntimeConfig,
    *,
    confirmation: bool,
    timeout: float = 15.0,
    flag_reader: Callable[..., Mapping[str, Any]] = read_repository_feature_flag,
    saver: Callable[..., Mapping[str, Any]] = save_runtime_checkpoint,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Perform the guarded CAS persistence after a second explicit confirmation."""
    current = utc(now or _now())
    if confirmation is not True:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "saved": False,
            "verified": False,
            "reason": "SECOND_EXPLICIT_CONFIRMATION_REQUIRED",
        }

    validation = validate_durable_closure_approval(
        access,
        human_closure_record,
        runtime_result,
        approval,
        now=current,
    )
    if validation.get("state") != "APPROVED":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "saved": False,
            "verified": False,
            "reason": str(
                validation.get("reason")
                or "DURABLE_CLOSURE_APPROVAL_REQUIRED"
            ),
        }

    context = authenticated_context(access, Domain.ADMIN)
    expected_flag_state = str(
        validation.get("feature_flag_state") or ""
    ).upper()
    pre_flag = dict(flag_reader(config, timeout=min(timeout, 10.0)) or {})
    if (
        str(pre_flag.get("status") or "").upper() != "CONFIRMED"
        or str(pre_flag.get("state") or "").upper() != expected_flag_state
        or expected_flag_state not in KNOWN_FLAG_STATES
    ):
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "saved": False,
            "verified": False,
            "reason": "FEATURE_FLAG_CHANGED_BEFORE_DURABLE_CLOSURE_WRITE",
            "feature_flag_state": str(
                pre_flag.get("state") or "UNKNOWN"
            ).upper(),
        }

    source_checkpoint = deepcopy(
        dict(runtime_result.get("checkpoint") or {})
    )
    source_sha = str(runtime_result.get("sha") or "")
    source_worker_digest = _worker_state_digest(source_checkpoint)
    closure = _closure_contract(human_closure_record)

    try:
        candidate = build_durable_closure_checkpoint(
            source_checkpoint,
            human_closure_record,
            actor_id=context.actor_id,
            source_runtime_sha=source_sha,
            source_runtime_checkpoint_digest=checkpoint_source_digest(
                source_checkpoint
            ),
            feature_flag_state=expected_flag_state,
            now=current,
        )
    except Exception as exc:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "saved": False,
            "verified": False,
            "reason": type(exc).__name__,
        }

    result = dict(
        saver(
            candidate,
            config,
            approved=True,
            expected_sha=source_sha,
            timeout=timeout,
        )
        or {}
    )
    if not (result.get("saved") and result.get("verified")):
        return {
            "schema": SCHEMA,
            "status": str(result.get("status") or "ERROR"),
            "saved": False,
            "verified": False,
            "reason": str(
                result.get("reason") or "DURABLE_CLOSURE_NOT_CONFIRMED"
            ),
            "save_result": result,
        }

    def _rollback_after_write(
        reason: str,
        *,
        flag_state: str = "UNKNOWN",
    ) -> dict[str, Any]:
        rollback = dict(
            saver(
                source_checkpoint,
                config,
                approved=True,
                expected_sha=str(result.get("sha") or ""),
                timeout=timeout,
            )
            or {}
        )
        rollback_ok = bool(
            rollback.get("saved") and rollback.get("verified")
        )
        return {
            "schema": SCHEMA,
            "status": (
                "ROLLED_BACK"
                if rollback_ok
                else "CRITICAL_ROLLBACK_FAILED"
            ),
            "saved": False if rollback_ok else True,
            "verified": rollback_ok,
            "reason": reason,
            "feature_flag_state": flag_state,
            "durable_closure_persisted": False if rollback_ok else True,
            "authoritative_incident_center_status_modified": False,
            "feature_flag_modified": False,
            "global_worker_modified": False,
            "reactivation_authorized": False,
            "real_trading_enabled": False,
            "rollback_performed": rollback_ok,
            "rollback_result": rollback,
        }

    persisted_checkpoint = result.get("checkpoint")
    if not isinstance(persisted_checkpoint, Mapping):
        return _rollback_after_write(
            "READ_AFTER_WRITE_CHECKPOINT_MISSING"
        )

    persisted = durable_record_state(
        persisted_checkpoint,
        closure_record_id=str(closure.get("closure_record_id") or ""),
        closure_record_digest=str(
            closure.get("closure_record_digest") or ""
        ),
    )
    if persisted.get("state") != "PERSISTED":
        return _rollback_after_write(
            "DURABLE_CLOSURE_RECORD_NOT_VERIFIED_AFTER_WRITE"
        )

    if _worker_state_digest(persisted_checkpoint) != source_worker_digest:
        return _rollback_after_write(
            "GLOBAL_WORKER_STATE_CHANGED_DURING_CLOSURE_PERSISTENCE"
        )

    post_flag = dict(
        flag_reader(config, timeout=min(timeout, 10.0)) or {}
    )
    post_state = str(post_flag.get("state") or "UNKNOWN").upper()
    if (
        str(post_flag.get("status") or "").upper() != "CONFIRMED"
        or post_state != expected_flag_state
    ):
        return _rollback_after_write(
            "FEATURE_FLAG_CHANGED_DURING_CLOSURE_PERSISTENCE",
            flag_state=post_state,
        )

    return {
        "schema": SCHEMA,
        "status": "CONFIRMED",
        "saved": True,
        "verified": True,
        "sha": str(result.get("sha") or ""),
        "checkpoint": persisted_checkpoint,
        "closure_record_id": str(
            closure.get("closure_record_id") or ""
        ),
        "durable_closure_persisted": True,
        "shared_closure_record_persisted": True,
        "authoritative_incident_center_status_modified": False,
        "feature_flag_state": expected_flag_state,
        "feature_flag_modified": False,
        "global_worker_modified": False,
        "global_worker_executed": False,
        "reactivation_authorized": False,
        "real_trading_enabled": False,
        "rollback_performed": False,
    }


__all__ = [
    "SCHEMA",
    "PLAN_SCHEMA",
    "APPROVAL_SCHEMA",
    "LEDGER_SCHEMA",
    "RECORD_SCHEMA",
    "LEDGER_NAMESPACE",
    "CONFIRMATION_PHRASE",
    "MAX_RECORDS",
    "load_closure_ledger",
    "durable_record_state",
    "plan_integrity",
    "approval_integrity",
    "prepare_durable_closure_plan",
    "approve_durable_closure_plan",
    "validate_durable_closure_approval",
    "build_durable_closure_checkpoint",
    "persist_human_incident_closure_record",
]
