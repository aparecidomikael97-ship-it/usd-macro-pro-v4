"""AION Developer planning package.

Bridges read-only Developer Intelligence into the existing Developer Engine,
Digital Twin and Dev Fusion contracts without executing repository code or
promoting any phase automatically.

This module only creates in-memory planning records. It does not edit files,
run tests, spawn processes, call the network, persist checkpoints, commit,
merge, deploy, publish, move money or enable real trading.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from atlasquant_aion_developer_engine import (
    new_development_workflow,
    record_phase,
)
from atlasquant_aion_developer_intelligence import (
    SCHEMA as INTELLIGENCE_SCHEMA,
    build_development_plan,
)
from atlasquant_aion_digital_twin import new_digital_twin
from atlasquant_aion_dev_fusion import new_dev_fusion_pipeline
from atlasquant_aion_observability import redact_text

SCHEMA = "ATLASQUANT_AION_DEVELOPER_PACKAGE_V1"

RISK_TEST_HINTS = {
    "AUTHORITY": (
        "guardian", "access_control", "entitlement", "approval",
        "tenant_privacy", "account_change_audit",
    ),
    "SECRETS": (
        "repository_secret_hygiene", "observability", "vault", "secret",
    ),
    "TRADING": (
        "risk_guardian", "paper_trading", "trading", "execution",
    ),
    "FINANCIAL": (
        "billing", "investment", "sales", "treasury",
    ),
    "RELEASE": (
        "release_gate", "release_guard", "release_readiness",
        "production_workflows", "render",
    ),
    "ADMIN": (
        "aion_admin", "access_panel", "tenant", "account",
    ),
}

REQUIRED_GATES = (
    "PLAN_HUMAN_REVIEW",
    "ROLLBACK_PLAN",
    "TEST_SELECTION",
    "INDEPENDENT_REVIEWER",
    "INDEPENDENT_BREAKER",
    "EVALUATION_LAB",
    "RELEASE_REVIEW",
)


def _clean(value: Any, limit: int = 1200) -> str:
    return " ".join(redact_text(value).replace("\x00", "").split())[:limit]


def _digest(value: Any, length: int = 16) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return sha256(raw.encode("utf-8")).hexdigest()[:length].upper()


def _validate_snapshot(snapshot: Mapping[str, Any]) -> None:
    item = dict(snapshot or {})
    if item.get("schema") != INTELLIGENCE_SCHEMA:
        raise ValueError("invalid Developer Intelligence snapshot")
    if not str(item.get("snapshot_digest") or ""):
        raise ValueError("snapshot digest required")
    unsafe = (
        bool(item.get("content_included"))
        or bool(item.get("executes_repository_code"))
        or bool(item.get("writes_files"))
        or bool(item.get("network_called"))
        or bool(item.get("subprocess_called"))
    )
    if unsafe:
        raise ValueError("unsafe Developer Intelligence snapshot")


def _risk_test_candidates(
    snapshot: Mapping[str, Any],
    risk_tags: Sequence[Any] | None,
) -> dict[str, list[str]]:
    tests = [
        str(row.get("path") or "")
        for row in list(snapshot.get("files") or [])
        if isinstance(row, Mapping)
        and str(row.get("category") or "") == "TEST"
        and str(row.get("path") or "")
    ]
    out: dict[str, list[str]] = {}
    for raw_tag in list(risk_tags or []):
        tag = _clean(raw_tag, 40).upper()
        hints = RISK_TEST_HINTS.get(tag, ())
        if not hints:
            continue
        matches = sorted({
            path for path in tests
            if any(hint in path.lower() for hint in hints)
        })
        out[tag] = matches[:40]
    return out


def build_developer_package(
    request: Any,
    snapshot: Mapping[str, Any],
    *,
    branch: Any,
    baseline_ref: Any,
    candidate_ref: Any,
    changed_paths: Sequence[Any] | None = None,
    requested_by: Any = "AION_ANALYSIS",
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create a human-gated planning package; never execute or persist it."""
    _validate_snapshot(snapshot)
    request_text = _clean(request, 1200)
    branch_text = _clean(branch, 240)
    baseline = _clean(baseline_ref, 240)
    candidate = _clean(candidate_ref, 240)
    requester = _clean(requested_by, 120) or "AION_ANALYSIS"
    if not request_text or not branch_text or not baseline or not candidate:
        raise ValueError("request, branch, baseline_ref and candidate_ref are required")
    if baseline == candidate:
        raise ValueError("candidate_ref must differ from baseline_ref")

    plan = build_development_plan(
        request_text,
        snapshot,
        branch=branch_text,
        baseline_ref=baseline,
        changed_paths=changed_paths,
    )
    risk_matrix = _risk_test_candidates(snapshot, plan.get("risk_tags"))
    risk_tests = sorted({
        path for rows in risk_matrix.values() for path in rows
    })
    required_tests = sorted(set(
        list(plan.get("recommended_tests") or []) + risk_tests
    ))

    workflow = new_development_workflow(
        request_text,
        branch=branch_text,
        baseline_ref=baseline,
        requested_by=requester,
        components=list(plan.get("impacted_files") or []),
        dependencies=list(plan.get("risk_tags") or []),
        impact="HIGH" if plan.get("risk_tags") else "MEDIUM",
        created_at=created_at,
    )
    workflow = record_phase(
        workflow,
        "PLAN",
        state="WAITING_HUMAN",
        actor="AION_DEVELOPER_INTELLIGENCE",
        summary=(
            "Plano estrutural preparado a partir de snapshot somente leitura; "
            "aprovação humana é necessária antes de IMPLEMENT."
        ),
        evidence_refs=[
            str(plan.get("snapshot_digest") or ""),
            str(plan.get("plan_id") or ""),
        ],
    )

    twin = new_digital_twin(
        f"Digital Twin · {request_text[:160]}",
        baseline_ref=baseline,
        candidate_ref=candidate,
        scope=list(plan.get("impacted_files") or []),
        dependencies=list(plan.get("risk_tags") or []),
        expected_impacts=list(plan.get("warnings") or []) + list(plan.get("risk_tags") or []),
        rollback_plan="",
        created_by=requester,
        created_at=created_at,
    )

    fusion = new_dev_fusion_pipeline(
        f"Dev Fusion · {plan.get('plan_id')}",
        twin_id=twin["twin_id"],
        baseline_ref=baseline,
        candidate_ref=candidate,
        created_by=requester,
        created_at=created_at,
    )

    gaps = []
    if plan.get("unmatched_code"):
        gaps.append("PYTHON_WITHOUT_LIKELY_TEST")
    if bool(snapshot.get("truncated")):
        gaps.append("REPOSITORY_SNAPSHOT_TRUNCATED")
    if int(snapshot.get("syntax_errors") or 0):
        gaps.append("SNAPSHOT_SYNTAX_ERRORS_PRESENT")
    if not required_tests and plan.get("impacted_files"):
        gaps.append("NO_TEST_CANDIDATES")

    gates = [
        {
            "gate": "PLAN_HUMAN_REVIEW",
            "state": "WAITING_HUMAN",
            "detail": "Plano gerado pelo AION não aprova a própria implementação.",
        },
        {
            "gate": "ROLLBACK_PLAN",
            "state": "REQUIRED",
            "detail": "Digital Twin permanece sem rollback até registro explícito.",
        },
        {
            "gate": "TEST_SELECTION",
            "state": "REVIEW_REQUIRED" if gaps else "READY_FOR_REVIEW",
            "detail": "Testes são candidatos estruturais; seleção final exige revisão.",
        },
        {
            "gate": "INDEPENDENT_REVIEWER",
            "state": "REQUIRED",
            "detail": "Reviewer deve ser independente do Builder.",
        },
        {
            "gate": "INDEPENDENT_BREAKER",
            "state": "REQUIRED",
            "detail": "Breaker/Red-Team deve ser independente de Builder e Reviewer.",
        },
        {
            "gate": "EVALUATION_LAB",
            "state": "REQUIRED",
            "detail": "Dev Fusion só pode avançar com Evaluation Lab documentado.",
        },
        {
            "gate": "RELEASE_REVIEW",
            "state": "REQUIRED",
            "detail": "Release continua sujeito a revisão humana.",
        },
    ]

    package_seed = {
        "plan_id": plan.get("plan_id"),
        "workflow_id": workflow.get("workflow_id"),
        "twin_id": twin.get("twin_id"),
        "pipeline_id": fusion.get("pipeline_id"),
        "snapshot_digest": plan.get("snapshot_digest"),
    }
    return {
        "schema": SCHEMA,
        "package_id": "DEVPACK-" + _digest(package_seed),
        "state": "WAITING_HUMAN",
        "plan": plan,
        "developer_workflow": workflow,
        "digital_twin": twin,
        "dev_fusion": fusion,
        "test_strategy": {
            "recommended_tests": list(plan.get("recommended_tests") or []),
            "risk_based_tests": risk_matrix,
            "required_test_candidates": required_tests,
            "unmatched_code": list(plan.get("unmatched_code") or []),
            "selection_is_heuristic": True,
            "tests_executed": False,
        },
        "gaps": gaps,
        "gates": gates,
        "required_gate_names": list(REQUIRED_GATES),
        "roles": {
            "builder": "UNASSIGNED",
            "reviewer": "UNASSIGNED_INDEPENDENT",
            "breaker": "UNASSIGNED_INDEPENDENT",
            "evaluator": "UNASSIGNED",
            "release_reviewer": "HUMAN_REQUIRED",
        },
        "evidence_refs": [
            str(plan.get("snapshot_digest") or ""),
            str(plan.get("plan_id") or ""),
        ],
        "analysis_only": True,
        "persists_checkpoint": False,
        "executes_repository_code": False,
        "runs_tests": False,
        "writes_files": False,
        "network_called": False,
        "subprocess_called": False,
        "automatic_edit": False,
        "automatic_commit": False,
        "automatic_merge": False,
        "automatic_deploy": False,
        "production_change_allowed": False,
        "real_trading_enabled": False,
        "tool_output_is_authority": False,
    }


__all__ = [
    "SCHEMA",
    "RISK_TEST_HINTS",
    "REQUIRED_GATES",
    "build_developer_package",
]
