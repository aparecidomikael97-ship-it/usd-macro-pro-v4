"""Structured AION Developer Engine workflow.

This module records PLAN → IMPLEMENT → TEST → REVIEW → RELEASE evidence. It
does not edit files, run commands, merge, deploy or elevate permissions.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

from atlasquant_aion_observability import redact_text
from atlasquant_aion_developer_manifest import canonical_identity, validate_isolated_branch

SCHEMA = "ATLASQUANT_AION_DEVELOPER_ENGINE_V1"
PHASES = ("REQUEST", "PLAN", "IMPLEMENT", "TEST", "REVIEW", "RELEASE")
TERMINAL_STATES = ("PASS", "FAIL", "BLOCKED", "WAITING_HUMAN")
MAX_CORRECTION_ATTEMPTS = 3
ADVERSARIAL_CHECKS = (
    "logic_and_edge_cases",
    "race_and_state_consistency",
    "regression_and_contracts",
    "mobile_and_accessibility",
    "exception_handling",
    "secret_exposure",
    "dependency_cycles",
    "performance",
    "dangerous_actions",
    "misleading_results",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any, limit: int = 1800) -> str:
    return redact_text(value).replace("\x00", "").strip()[:limit]


def _list(value: Sequence[Any] | None, limit: int = 100) -> list[str]:
    out = []
    for raw in list(value or [])[:limit * 2]:
        text = _clean(raw, 300)
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _id(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return "DEV-" + sha256(raw.encode("utf-8")).hexdigest()[:16].upper()


def new_development_workflow(
    request: Any,
    *,
    branch: Any,
    baseline_ref: Any,
    requested_by: Any,
    components: Sequence[Any] | None = None,
    dependencies: Sequence[Any] | None = None,
    impact: Any = "MEDIUM",
    created_at: str | None = None,
) -> dict[str, Any]:
    request_text = _clean(request, 1200)
    branch_text = validate_isolated_branch(branch)
    baseline = _clean(baseline_ref, 180)
    if not request_text or not branch_text or not baseline:
        raise ValueError("request, branch and baseline are required")
    created = str(created_at or _now())
    return {
        "schema": SCHEMA,
        "workflow_id": _id({"request": request_text, "branch": branch_text, "created_at": created}),
        "request": request_text,
        "branch": branch_text,
        "baseline_ref": baseline,
        "requested_by": _clean(requested_by, 120) or "UNKNOWN",
        "components": _list(components),
        "dependencies": _list(dependencies),
        "impact": _clean(impact, 30).upper() or "MEDIUM",
        "phases": [
            {"phase": phase, "state": "PASS" if phase == "REQUEST" else "PENDING", "actor": "", "summary": "", "evidence_refs": []}
            for phase in PHASES
        ],
        "test_attempts": [],
        "adversarial_review": {"state": "PENDING", "checks": [], "critic_independent": False},
        "rollback_plan": "",
        "documentation_refs": [],
        "status": "PLANNED",
        "created_at": created,
        "updated_at": created,
        "sandbox_only": True,
        "automatic_merge": False,
        "automatic_deploy": False,
        "production_change_allowed": False,
        "real_trading_enabled": False,
    }


def _phase_index(name: str) -> int:
    if name not in PHASES:
        raise ValueError("invalid development phase")
    return PHASES.index(name)


def record_phase(
    workflow: Mapping[str, Any],
    phase: Any,
    *,
    state: Any,
    actor: Any,
    summary: Any,
    evidence_refs: Sequence[Any] | None = None,
) -> dict[str, Any]:
    item = deepcopy(dict(workflow or {}))
    name = _clean(phase, 30).upper()
    phase_state = _clean(state, 30).upper()
    if name not in PHASES or phase_state not in {"PENDING", "RUNNING", *TERMINAL_STATES}:
        raise ValueError("invalid phase update")
    actor_text = _clean(actor, 120)
    refs = _list(evidence_refs)
    if phase_state in TERMINAL_STATES and (not actor_text or not refs):
        raise ValueError("terminal phase requires actor and evidence")
    phases = list(item.get("phases") or [])
    if len(phases) != len(PHASES):
        raise ValueError("invalid workflow phases")
    index = _phase_index(name)
    if index > 0 and phase_state != "PENDING":
        prior = phases[index - 1]
        if str(prior.get("state")) != "PASS":
            raise ValueError("development phases must advance in order")

    existing = phases[index]
    downstream = phases[index + 1:]
    downstream_progressed = any(str(row.get("state") or "PENDING") != "PENDING" for row in downstream)
    if downstream_progressed and (
        str(existing.get("state") or "") != phase_state
        or str(existing.get("actor") or "") != actor_text
        or str(existing.get("summary") or "") != _clean(summary, 1200)
        or list(existing.get("evidence_refs") or []) != refs
    ):
        raise ValueError("earlier phase cannot change after downstream progress")

    if name == "REVIEW":
        implement_actor = next((x.get("actor") for x in phases if x.get("phase") == "IMPLEMENT"), "")
        if (
            actor_text
            and implement_actor
            and canonical_identity(actor_text) == canonical_identity(implement_actor)
        ):
            raise ValueError("reviewer must be independent from builder")
    phases[index] = {
        "phase": name,
        "state": phase_state,
        "actor": actor_text,
        "summary": _clean(summary, 1200),
        "evidence_refs": refs,
    }
    item["phases"] = phases
    item["updated_at"] = _now()
    item["status"] = (
        "BLOCKED" if phase_state in {"FAIL", "BLOCKED"}
        else "WAITING_HUMAN" if phase_state == "WAITING_HUMAN"
        else "IN_PROGRESS"
    )
    return item


def record_test_attempt(
    workflow: Mapping[str, Any],
    *,
    command_label: Any,
    state: Any,
    error_type: Any = "",
    hypothesis: Any = "",
    cause: Any = "",
    evidence_refs: Sequence[Any] | None = None,
) -> dict[str, Any]:
    item = deepcopy(dict(workflow or {}))
    attempts = list(item.get("test_attempts") or [])
    if len(attempts) >= MAX_CORRECTION_ATTEMPTS:
        item["status"] = "BLOCKED"
        item["blocker"] = "AUTO_CORRECTION_LIMIT_REACHED"
        return item
    test_state = _clean(state, 20).upper()
    if test_state not in {"PASS", "FAIL"}:
        raise ValueError("test attempt must PASS or FAIL")
    refs = _list(evidence_refs)
    attempt = {
        "attempt": len(attempts) + 1,
        "command_label": _clean(command_label, 240),
        "state": test_state,
        "error_type": _clean(error_type, 120),
        "hypothesis": _clean(hypothesis, 1000),
        "cause": _clean(cause, 1000),
        "cause_truth": "UNKNOWN",
        "cause_source": "UNVERIFIED_TEST_ATTEMPT",
        "evidence_refs": refs,
        "created_at": _now(),
    }
    attempts.append(attempt)
    item["test_attempts"] = attempts
    if test_state == "PASS":
        item["status"] = "IN_PROGRESS"
        item.pop("blocker", None)
    elif len(attempts) >= MAX_CORRECTION_ATTEMPTS:
        item["status"] = "BLOCKED"
        item["blocker"] = "AUTO_CORRECTION_LIMIT_REACHED"
    else:
        item["status"] = "CORRECTION_REQUIRED"
    item["updated_at"] = _now()
    return item


def record_adversarial_review(
    workflow: Mapping[str, Any],
    *,
    critic_actor: Any,
    findings: Sequence[Mapping[str, Any]] | None,
    evidence_refs: Sequence[Any] | None,
) -> dict[str, Any]:
    item = deepcopy(dict(workflow or {}))
    phases = list(item.get("phases") or [])
    builder = next((str(x.get("actor") or "") for x in phases if x.get("phase") == "IMPLEMENT"), "")
    reviewer = next((str(x.get("actor") or "") for x in phases if x.get("phase") == "REVIEW"), "")
    critic = _clean(critic_actor, 120)
    refs = _list(evidence_refs)
    if not critic:
        raise ValueError("adversarial critic identity required")
    critic_key = canonical_identity(critic)
    independent_from = {
        canonical_identity(value)
        for value in (builder, reviewer)
        if value
    }
    if critic_key in independent_from:
        raise ValueError("adversarial critic must be independent from builder/reviewer")
    if not refs:
        raise ValueError("adversarial review requires evidence")
    normalized_findings = []
    for raw in list(findings or [])[:100]:
        if not isinstance(raw, Mapping):
            continue
        severity = _clean(raw.get("severity") or "MEDIUM", 20).upper()
        normalized_findings.append({
            "check": _clean(raw.get("check"), 100),
            "severity": severity if severity in {"LOW", "MEDIUM", "HIGH", "CRITICAL"} else "MEDIUM",
            "finding": _clean(raw.get("finding"), 1000),
            "resolved": bool(raw.get("resolved", False)),
        })
    critical_open = any(
        row["severity"] in {"HIGH", "CRITICAL"} and not row["resolved"]
        for row in normalized_findings
    )
    item["adversarial_review"] = {
        "state": "BLOCKED" if critical_open else "PASS",
        "critic_actor": critic,
        "critic_independent": True,
        "required_checks": list(ADVERSARIAL_CHECKS),
        "findings": normalized_findings,
        "evidence_refs": refs,
    }
    if critical_open:
        item["status"] = "BLOCKED"
        item["blocker"] = "ADVERSARIAL_FINDING_OPEN"
    item["updated_at"] = _now()
    return item


def definition_of_done(
    workflow: Mapping[str, Any],
    *,
    rollback_plan: Any = "",
    documentation_refs: Sequence[Any] | None = None,
) -> dict[str, Any]:
    item = deepcopy(dict(workflow or {}))
    phases = {str(row.get("phase")): str(row.get("state")) for row in list(item.get("phases") or [])}
    tests = list(item.get("test_attempts") or [])
    review = dict(item.get("adversarial_review") or {})
    rollback = _clean(rollback_plan or item.get("rollback_plan"), 1600)
    docs = _list(documentation_refs or item.get("documentation_refs"))
    checks = {
        "plan_passed": phases.get("PLAN") == "PASS",
        "implementation_passed": phases.get("IMPLEMENT") == "PASS",
        "test_phase_passed": phases.get("TEST") == "PASS",
        "tests_passed": bool(tests and tests[-1].get("state") == "PASS"),
        "review_passed": phases.get("REVIEW") == "PASS",
        "adversarial_review_passed": review.get("state") == "PASS",
        "rollback_documented": bool(rollback),
        "documentation_present": bool(docs),
        "release_not_automatic": True,
    }
    complete = all(checks.values())
    item["rollback_plan"] = rollback
    item["documentation_refs"] = docs
    item["definition_of_done"] = checks
    item["status"] = "HUMAN_RELEASE_REVIEW" if complete else "INCOMPLETE"
    item["automatic_merge"] = False
    item["automatic_deploy"] = False
    item["production_change_allowed"] = False
    item["real_trading_enabled"] = False
    return item


__all__ = [
    "SCHEMA", "PHASES", "MAX_CORRECTION_ATTEMPTS", "ADVERSARIAL_CHECKS",
    "new_development_workflow", "record_phase", "record_test_attempt",
    "record_adversarial_review", "definition_of_done",
]
