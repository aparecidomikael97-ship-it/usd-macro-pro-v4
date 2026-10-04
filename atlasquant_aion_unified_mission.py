"""AION Unified Mission — V2.2A.

Thin composition layer that transforms a validated ``AionRequest`` into an
auditable, fail-closed mission specification (``AionMission``). It COMPOSES the
existing core modules — unified runtime (canonical role/truth/authorization/
model lane), capability planner (capability states and evidence gates), durable
tasks (task skeleton) and role authority (8 official roles) — and never
executes anything: no provider call, no tool execution, no external action,
no trade, no billing, no automatic checkpoint write, no memory promotion.

Mission != Execution. ``READY_FOR_GUARDED_HANDOFF`` only means the mission may
be handed to a future execution gate; it never means an action was executed.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from atlasquant_aion_unified_runtime import AionRequest, process_aion_request
from atlasquant_aion_capability_planner import plan_agentic_mission
from atlasquant_aion_durable_tasks import new_durable_task
from atlasquant_aion_role_authority import OFFICIAL_ROLE_IDS, official_role_authority_matrix

SCHEMA = "ATLASQUANT_AION_UNIFIED_MISSION_V1"

MISSION_STATES = (
    "PREPARED",
    "WAITING_EVIDENCE",
    "WAITING_APPROVAL",
    "BLOCKED",
    "READY_FOR_GUARDED_HANDOFF",
)

MAX_OBJECTIVE_CHARS = 2000
MAX_STEPS = 32
MAX_EVIDENCE_REFS = 64
MAX_WARNINGS = 32
MAX_BLOCKERS = 32
MAX_ATTACHMENTS = 16
MAX_CAPABILITIES = 32

# Truth states that never release an operational handoff.
TRUTH_HARD_BLOCKED = frozenset({"CONFLICTING", "QUARANTINED", "REJECTED"})
# Truth states that require revalidation / fresh evidence.
TRUTH_NEEDS_EVIDENCE = frozenset({"STALE", "UNKNOWN", "INSUFFICIENT"})


class AionMissionError(ValueError):
    """Structured mission-layer failure."""

    def __init__(self, error_code: str, detail: str = "", *, request_id: str = "", mission_id: str = ""):
        self.error_code = error_code
        self.reason_detail = str(detail or "")[:240]
        self.request_id = request_id
        self.mission_id = mission_id
        super().__init__(f"{error_code}: {self.reason_detail}".strip())


def _clean(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _digest(payload: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _scope_fingerprint(owner_id: str, tenant_id: str, workspace_id: str) -> str:
    return _digest({
        "owner": _clean(owner_id, 256),
        "tenant": _clean(tenant_id, 256),
        "workspace": _clean(workspace_id, 256),
    })


def _request_digest(request: AionRequest) -> str:
    """Canonical digest of the logical request identity (no volatile timestamps)."""
    return _digest({
        "request_id": _clean(request.request_id, 256),
        "conversation_id": _clean(request.conversation_id, 256),
        "owner_id": _clean(request.owner_id, 256),
        "tenant_id": _clean(request.tenant_id, 256),
        "workspace_id": _clean(request.workspace_id, 256),
        "sector": _clean(request.sector, 80),
        "objective": _clean(request.user_message, MAX_OBJECTIVE_CHARS),
        "attachments": tuple(_clean(a, 256) for a in list(request.attachments)[:MAX_ATTACHMENTS]),
        "requested_action": _clean(request.requested_action, 120),
        "current_mode": _clean(request.current_mode, 80),
    })


def _mission_id(request: AionRequest, request_digest: str, scope_fp: str) -> str:
    return "AION-MSN-" + hashlib.sha256(
        (_clean(request.request_id, 256) + "|" + request_digest + "|" + scope_fp).encode("utf-8")
    ).hexdigest()[:16].upper()


def _validate_prior_mission(prior: Mapping[str, Any], request: AionRequest, req_digest: str, scope_fp: str) -> None:
    """Fail closed on a forged/cross-scope prior mission before any replay."""
    if not isinstance(prior, Mapping):
        raise AionMissionError("PRIOR_MISSION_INVALID", "prior_mission must be a mapping", request_id=request.request_id)
    if prior.get("schema") != SCHEMA:
        raise AionMissionError("PRIOR_MISSION_INVALID", "prior_mission schema mismatch", request_id=request.request_id)
    if prior.get("request_id") != request.request_id:
        raise AionMissionError("PRIOR_MISSION_REQUEST_MISMATCH", "request_id differs from prior mission", request_id=request.request_id)
    if prior.get("scope_fingerprint") != scope_fp:
        raise AionMissionError("CROSS_TENANT_REPLAY", "scope fingerprint differs from prior mission", request_id=request.request_id)
    if prior.get("request_digest") != req_digest:
        raise AionMissionError("REQUEST_PAYLOAD_MISMATCH", "same request_id with different payload", request_id=request.request_id)
    # Validate the prior mission digest itself (tamper detection).
    check = validate_aion_mission(prior)
    if check.get("valid") is not True:
        raise AionMissionError("PRIOR_MISSION_DIGEST_MISMATCH", "prior mission digest invalid", request_id=request.request_id)


def _normalize_capabilities(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for stage in list(plan.get("stages") or [])[:MAX_CAPABILITIES]:
        if not isinstance(stage, Mapping):
            continue
        rows.append({
            "id": _clean(stage.get("capability_id"), 120),
            "label": _clean(stage.get("label"), 200),
            "state": _clean(stage.get("state"), 40),
            "risk": _clean(stage.get("risk") or stage.get("reason"), 120),
            "dependency": _clean(stage.get("dependency"), 120),
            "feature_flag": _clean(stage.get("feature_flag"), 120),
            "required_evidence": tuple(_clean(e, 120) for e in list(stage.get("evidence_requirements") or [])[:MAX_EVIDENCE_REFS]),
            "requires_explicit_approval": stage.get("requires_explicit_approval") is True,
            "executes_action": stage.get("executes_action") is True,
        })
    return rows


def _build_steps(capabilities: Sequence[Mapping[str, Any]], evidence: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    available = set()
    for item in list(evidence or []):
        if isinstance(item, Mapping):
            for key in ("ref", "id", "source", "claim"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    available.add(_clean(value, 120))
    steps = []
    for index, cap in enumerate(list(capabilities)[:MAX_STEPS], start=1):
        required = tuple(cap.get("required_evidence") or ())
        missing = tuple(req for req in required if req not in available)
        steps.append({
            "step_id": f"S{index:03d}",
            "title": cap.get("label") or cap.get("id") or f"step-{index}",
            "capability_id": cap.get("id"),
            "state": cap.get("state"),
            "guardian_action": "read" if cap.get("state") in {"AVAILABLE_LOCAL", "EVIDENCE_REQUIRED"} else "review",
            "requires_approval": cap.get("requires_explicit_approval") is True,
            "external_side_effects": cap.get("executes_action") is True,
            "required_evidence": required,
            "available_evidence": tuple(req for req in required if req in available),
            "missing_evidence": missing,
            "evidence_refs": tuple(sorted(available))[:MAX_EVIDENCE_REFS],
        })
    return steps


def prepare_aion_mission(
    request: AionRequest,
    *,
    approved: bool = False,
    access: Mapping[str, Any] | None = None,
    feature_flags: Mapping[str, Any] | None = None,
    system_context: Mapping[str, Any] | None = None,
    provider_state: str = "ZERO_COST_LOCAL",
    budget: Mapping[str, Any] | None = None,
    prior_mission: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose a validated request into a fail-closed mission specification.

    Never executes: no provider call, no tool, no external action, no trade.
    """
    if not isinstance(request, AionRequest):
        raise TypeError("AionRequest required")
    objective = _clean(request.user_message, MAX_OBJECTIVE_CHARS)
    if not objective:
        raise AionMissionError("OBJECTIVE_EMPTY", "objective is empty", request_id=request.request_id)
    if len(str(request.user_message or "")) > MAX_OBJECTIVE_CHARS:
        raise AionMissionError("OBJECTIVE_TOO_LARGE", "objective exceeds bound", request_id=request.request_id)
    if len(list(request.attachments or ())) > MAX_ATTACHMENTS:
        raise AionMissionError("ATTACHMENTS_TOO_MANY", "too many attachments", request_id=request.request_id)

    approved_exact = approved is True  # strict boolean; 1/"yes"/"true" are NOT approval
    scope_fp = _scope_fingerprint(request.owner_id, request.tenant_id, request.workspace_id)
    req_digest = _request_digest(request)
    mission_id = _mission_id(request, req_digest, scope_fp)

    idempotent_replay = False
    if prior_mission is not None:
        _validate_prior_mission(prior_mission, request, req_digest, scope_fp)
        idempotent_replay = True

    # Canonical runtime view: role / truth / authorization / model lane.
    runtime = process_aion_request(
        request,
        approved=approved_exact,
        external_feature_enabled=bool((feature_flags or {}).get("external_llm") is True),
        provider_state=provider_state,
        budget=budget,
    )

    # Capability plan from the existing planner (never duplicated here).
    plan = plan_agentic_mission(
        objective,
        access=access or {},
        feature_flags=feature_flags or {},
        system_context=system_context or {},
    )
    capabilities = _normalize_capabilities(plan)
    steps = _build_steps(capabilities, request.evidence)
    if len(steps) > MAX_STEPS:
        raise AionMissionError("STEPS_TOO_MANY", "capability plan exceeds step bound", request_id=request.request_id, mission_id=mission_id)
    seen = set()
    for step in steps:
        if step["step_id"] in seen:
            raise AionMissionError("DUPLICATE_STEP_ID", step["step_id"], request_id=request.request_id, mission_id=mission_id)
        seen.add(step["step_id"])

    # Role authority validation (forged roles fail closed).
    matrix = official_role_authority_matrix()
    known_roles = {row["role_id"] for row in matrix.get("roles", [])}
    selected_role = _clean(runtime.selected_role, 40)
    if selected_role not in known_roles:
        raise AionMissionError("UNKNOWN_ROLE", selected_role, request_id=request.request_id, mission_id=mission_id)
    supporting_roles = tuple(_clean(r, 40) for r in list(runtime.supporting_roles or ()) if _clean(r, 40) in known_roles)

    truth_state = _clean(runtime.truth_state, 40)
    authorization_class = _clean(runtime.authorization_class, 40)
    model_lane = _clean(runtime.model_lane, 40)

    # Memory: PROPOSED_ONLY, never promoted.
    memory_candidates = []
    for update in list(runtime.memory_updates or ()):
        if isinstance(update, Mapping):
            memory_candidates.append({
                "claim": _clean(update.get("claim") or update.get("key"), 256),
                "state": "PROPOSED_ONLY",
                "automatic_promotion": False,
            })
        else:
            memory_candidates.append({"claim": _clean(update, 256), "state": "PROPOSED_ONLY", "automatic_promotion": False})
    if any(m.get("automatic_promotion") is not False for m in memory_candidates):
        raise AionMissionError("MEMORY_PROMOTION_FORBIDDEN", "automatic promotion detected", request_id=request.request_id, mission_id=mission_id)

    # Durable task skeleton (PLANNED; never RUNNING).
    task = new_durable_task(
        objective[:300] or "aion-mission",
        objective=objective,
        domain=_clean(request.sector, 80) or "central",
        mission_id=mission_id,
        steps=[{
            "step_id": s["step_id"],
            "title": s["title"],
            "capability_id": s["capability_id"],
            "guardian_action": s["guardian_action"],
            "requires_approval": s["requires_approval"],
            "external_side_effects": s["external_side_effects"],
            "evidence_refs": list(s["evidence_refs"]),
        } for s in steps],
    )
    if task.get("state") != "PLANNED":
        raise AionMissionError("DURABLE_TASK_STATE_INVALID", task.get("state"), request_id=request.request_id, mission_id=mission_id)

    # Evidence aggregation.
    missing_evidence = tuple(sorted({m for s in steps for m in s["missing_evidence"]}))[:MAX_EVIDENCE_REFS]

    # Quarantined/rejected evidence is a hard block, detected explicitly from
    # the raw evidence records (the truth module has no QUARANTINED state).
    quarantined_refs = []
    for item in list(request.evidence or ()):
        if isinstance(item, Mapping):
            state = str(item.get("truth_state") or item.get("kind") or "").upper()
            if state in {"QUARANTINED", "REJECTED", "DOUBTFUL", "INVALID"}:
                quarantined_refs.append(_clean(item.get("claim") or item.get("source") or "evidence", 120))

    # Blockers / warnings.
    blockers: list[str] = []
    warnings: list[str] = []
    for cap in capabilities:
        if cap["state"] == "BLOCKED":
            blockers.append(f"capability:{cap['id']}")
    if quarantined_refs:
        blockers.append("quarantined_evidence:" + ",".join(list(dict.fromkeys(quarantined_refs))[:8]))
    if authorization_class == "BLOCKED":
        blockers.append("authorization:BLOCKED")
    for warning in list(runtime.warnings or ()):
        warnings.append(_clean(warning, 120))
    if truth_state in TRUTH_HARD_BLOCKED:
        blockers.append(f"truth:{truth_state}")
    if "EVIDENCE_CONFLICT" in [str(w) for w in list(runtime.warnings or ())]:
        blockers.append("truth:CONFLICT")
    if truth_state in TRUTH_NEEDS_EVIDENCE:
        warnings.append(f"truth:{truth_state}:revalidation_required")
    blockers = tuple(dict.fromkeys(blockers))[:MAX_BLOCKERS]
    warnings = tuple(dict.fromkeys(warnings))[:MAX_WARNINGS]

    pending_approvals = []
    for approval in list(runtime.pending_approvals or ()):
        if isinstance(approval, Mapping):
            pending_approvals.append(_clean(approval.get("action") or approval.get("kind"), 120))
        else:
            pending_approvals.append(_clean(approval, 120))
    requires_approval = any(s["requires_approval"] for s in steps) or bool(pending_approvals) or authorization_class == "REQUIRES_APPROVAL"

    # Deterministic state precedence. Authorization class is an INDEPENDENT
    # safety source: a REQUIRES_APPROVAL action can never collapse to PREPARED
    # just because the capability plan happened to be local/empty.
    if blockers or authorization_class == "BLOCKED":
        mission_state = "BLOCKED"
    elif missing_evidence or truth_state in TRUTH_NEEDS_EVIDENCE:
        mission_state = "WAITING_EVIDENCE"
    elif (requires_approval or authorization_class == "REQUIRES_APPROVAL") and approved_exact is not True:
        mission_state = "WAITING_APPROVAL"
    elif requires_approval or authorization_class == "REQUIRES_APPROVAL" or any(s["external_side_effects"] for s in steps):
        mission_state = "READY_FOR_GUARDED_HANDOFF"
    else:
        mission_state = "PREPARED"

    mission_spec = {
        "schema": SCHEMA,
        "request_digest": req_digest,
        "scope_fingerprint": scope_fp,
        "objective": objective,
        "selected_role": selected_role,
        "supporting_roles": supporting_roles,
        "capabilities": capabilities,
        "logical_steps": steps,
        "evidence_requirements": missing_evidence,
        "truth_state": truth_state,
        "authorization_class": authorization_class,
        "approval_requirements": tuple(dict.fromkeys(pending_approvals))[:MAX_BLOCKERS],
        "model_lane": model_lane,
        "recovery_policy": {
            "restores_state_only": True,
            "automatic_resume_executes": False,
            "checkpoint_written": False,
            "external_action_executed": False,
            "memory_promoted": False,
        },
    }
    mission_digest = _digest(mission_spec)

    mission = {
        "schema": SCHEMA,
        "mission_id": mission_id,
        "request_id": request.request_id,
        "conversation_id": request.conversation_id,
        "scope": {
            "owner_id": request.owner_id,
            "tenant_id": request.tenant_id,
            "workspace_id": request.workspace_id,
        },
        "scope_fingerprint": scope_fp,
        "objective": objective,
        "request_digest": req_digest,
        "selected_role": selected_role,
        "supporting_roles": supporting_roles,
        "capabilities": capabilities,
        "steps": steps,
        "truth_state": truth_state,
        "authorization_class": authorization_class,
        "model_lane": model_lane,
        "evidence_requirements": missing_evidence,
        "missing_evidence": missing_evidence,
        "approval_requirements": mission_spec["approval_requirements"],
        "memory_candidates": memory_candidates,
        "attachment_refs": tuple(_clean(a, 256) for a in list(request.attachments or ()))[:MAX_ATTACHMENTS],
        "requires_library_review": bool(list(request.attachments or ())),
        "mission_state": mission_state,
        "blockers": blockers,
        "warnings": warnings,
        "durable_task_ref": {
            "task_id": task.get("durable_task_id"),
            "mission_id": mission_id,
            "state": task.get("state"),
            "revision": task.get("revision"),
            "correlation_id": mission_id,
        },
        "checkpoint_candidate": {
            "intended": True,
            "checkpoint_written": False,
            "automatic_checkpoint_write": False,
        },
        "journal_policy": {
            "request_journal_required": True,
            "persistence_layer": "V2.1D",
            "writes_during_prepare": False,
        },
        "recovery_policy": mission_spec["recovery_policy"],
        "planned_handoffs": [
            {"from": "orchestrator", "to": selected_role, "kind": "planned"},
        ] if selected_role != "orchestrator" else [],
        "mission_digest": mission_digest,
        "idempotent_replay": idempotent_replay,
        "external_action_executed": False,
        "execution_allowed": False,
        "requires_downstream_execution_gate": mission_state == "READY_FOR_GUARDED_HANDOFF",
        "real_orders_enabled": False,
        "executes_provider_call": False,
        "executes_billing": False,
    }
    return mission


def validate_aion_mission(mission: Mapping[str, Any]) -> dict[str, Any]:
    """Recompute the canonical mission digest; detect tampering without executing."""
    if not isinstance(mission, Mapping):
        return {"valid": False, "reason_code": "MISSION_NOT_MAPPING"}
    if mission.get("schema") != SCHEMA:
        return {"valid": False, "reason_code": "MISSION_SCHEMA_MISMATCH"}
    spec = {
        "schema": SCHEMA,
        "request_digest": mission.get("request_digest"),
        "scope_fingerprint": mission.get("scope_fingerprint"),
        "objective": mission.get("objective"),
        "selected_role": mission.get("selected_role"),
        "supporting_roles": mission.get("supporting_roles"),
        "capabilities": mission.get("capabilities"),
        "logical_steps": mission.get("steps"),
        "evidence_requirements": mission.get("evidence_requirements"),
        "truth_state": mission.get("truth_state"),
        "authorization_class": mission.get("authorization_class"),
        "approval_requirements": mission.get("approval_requirements"),
        "model_lane": mission.get("model_lane"),
        "recovery_policy": mission.get("recovery_policy"),
    }
    expected = _digest(spec)
    actual = mission.get("mission_digest")
    valid = expected == actual
    result = {
        "valid": valid,
        "reason_code": "OK" if valid else "MISSION_DIGEST_MISMATCH",
        "expected_digest": expected,
        "observed_digest": actual,
    }
    # Duplicate step ids are independently rejected.
    step_ids = [s.get("step_id") for s in list(mission.get("steps") or []) if isinstance(s, Mapping)]
    if len(step_ids) != len(set(step_ids)):
        result = {"valid": False, "reason_code": "DUPLICATE_STEP_ID", "expected_digest": expected, "observed_digest": actual}
    return result
