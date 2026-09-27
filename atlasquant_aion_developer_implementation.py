"""Implementation-readiness envelope for AION Developer.

This contract bridges a human-confirmed root cause into the existing developer
trust policy. It does not execute implementation. It only defines bounded scope,
required tests and the human approval needed before a future isolated-branch
builder could be considered.

Authority remains in atlasquant_aion_workspaces.developer_trust_policy().
Level 2 (isolated branch) is never autonomous and requires human approval.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from atlasquant_aion_developer_correction import SCHEMA as CORRECTION_SCHEMA
from atlasquant_aion_developer_intelligence import SCHEMA as INTELLIGENCE_SCHEMA
from atlasquant_aion_developer_package import SCHEMA as PACKAGE_SCHEMA
from atlasquant_aion_observability import redact_text
from atlasquant_aion_workspaces import developer_step_allowed, developer_trust_policy

SCHEMA = "ATLASQUANT_AION_DEVELOPER_IMPLEMENTATION_ENVELOPE_V1"
AUTH_SCHEMA = "ATLASQUANT_AION_DEVELOPER_IMPLEMENTATION_AUTH_V1"
REQUESTED_TRUST_LEVEL = 2


def _clean(value: Any, limit: int = 1200) -> str:
    return " ".join(redact_text(value).replace("\x00", "").split())[:limit]


def _list(values: Sequence[Any] | None, limit: int = 100) -> list[str]:
    out: list[str] = []
    for raw in list(values or [])[:limit * 2]:
        text = _clean(raw, 500)
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _digest(value: Any, length: int = 18) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return sha256(raw.encode("utf-8")).hexdigest()[:length].upper()


def _known_paths(snapshot: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("path") or ""): dict(row)
        for row in list(snapshot.get("files") or [])
        if isinstance(row, Mapping) and str(row.get("path") or "")
    }


def _test_file(ref: str) -> str:
    return str(ref or "").split("::", 1)[0]


def _ui_sensitive(paths: Sequence[str], risk_tags: Sequence[str]) -> bool:
    tokens = (
        "admin", "ui", "panel", "dashboard", "home", "radar",
        "streamlit", "experience", "navigation",
    )
    return (
        "ADMIN" in {str(x).upper() for x in risk_tags}
        or any(any(token in str(path).lower() for token in tokens) for path in paths)
    )


def build_implementation_envelope(
    snapshot: Mapping[str, Any],
    package: Mapping[str, Any],
    correction: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a session-only readiness envelope; do not execute implementation."""
    if snapshot.get("schema") != INTELLIGENCE_SCHEMA:
        raise ValueError("invalid Developer Intelligence snapshot")
    snapshot_digest = str(snapshot.get("snapshot_digest") or "")
    if not snapshot_digest:
        raise ValueError("snapshot digest required")
    if any(bool(snapshot.get(key)) for key in (
        "content_included",
        "executes_repository_code",
        "writes_files",
        "network_called",
        "subprocess_called",
    )):
        raise ValueError("unsafe repository snapshot")

    if package.get("schema") != PACKAGE_SCHEMA:
        raise ValueError("invalid developer package")
    plan = package.get("plan") if isinstance(package.get("plan"), Mapping) else {}
    if str(plan.get("snapshot_digest") or "") != snapshot_digest:
        raise ValueError("package snapshot lineage mismatch")

    if correction.get("schema") != CORRECTION_SCHEMA:
        raise ValueError("invalid correction plan")
    if str(correction.get("state") or "") != "CAUSE_CONFIRMED_WAITING_IMPLEMENTATION":
        raise ValueError("human-confirmed cause required before implementation readiness")
    if correction.get("root_cause_confirmed") is not True:
        raise ValueError("root cause confirmation missing")
    if str(correction.get("root_cause_truth_status") or "") != "CONFIRMED":
        raise ValueError("root cause truth must be CONFIRMED by human review")

    lineage = correction.get("lineage") if isinstance(correction.get("lineage"), Mapping) else {}
    if str(lineage.get("snapshot_digest") or "") != snapshot_digest:
        raise ValueError("correction snapshot lineage mismatch")
    if str(lineage.get("package_id") or "") != str(package.get("package_id") or ""):
        raise ValueError("correction package lineage mismatch")

    confirmed = (
        correction.get("confirmed_root_cause")
        if isinstance(correction.get("confirmed_root_cause"), Mapping)
        else {}
    )
    if confirmed.get("human_approved") is not True:
        raise ValueError("human root-cause review evidence required")
    if str(confirmed.get("source") or "") != "HUMAN_REVIEW":
        raise ValueError("root cause must originate from human review")
    if not str(confirmed.get("reviewer_actor") or ""):
        raise ValueError("root-cause reviewer identity required")
    if not list(confirmed.get("evidence_refs") or []):
        raise ValueError("root-cause review evidence required")

    policy = developer_trust_policy()
    if int(policy.get("max_autonomous_level") or -1) >= REQUESTED_TRUST_LEVEL:
        raise ValueError("developer trust policy unexpectedly widened")
    if developer_step_allowed(REQUESTED_TRUST_LEVEL, human_approved=False):
        raise ValueError("level 2 must not be autonomously allowed")

    known = _known_paths(snapshot)
    source_scope = [
        path for path in _list(correction.get("target_files"), 50)
        if path in known
    ]
    if not source_scope:
        raise ValueError("implementation source scope is empty")

    tests = _list(correction.get("test_candidates"), 100)
    test_scope = []
    for ref in tests:
        path = _test_file(ref)
        if path in known and str(known[path].get("category") or "") == "TEST":
            if path not in test_scope:
                test_scope.append(path)

    editable_scope = _list(source_scope + test_scope, 80)
    risk_tags = sorted({
        str(tag)
        for path in source_scope
        for tag in list(known[path].get("risk_tags") or [])
        if str(tag)
    })

    mandatory_gates = [
        "TARGETED_TESTS",
        "RISK_REGRESSION_TESTS",
        "QUALITY_TESTS",
        "RELEASE_READINESS",
        "INDEPENDENT_REVIEW",
        "INDEPENDENT_BREAKER",
        "ROLLBACK_REVIEW",
    ]
    if _ui_sensitive(editable_scope, risk_tags):
        mandatory_gates.extend(["UI_SMOKE", "MOBILE_DOM"])

    envelope_seed = {
        "snapshot_digest": snapshot_digest,
        "package_id": package.get("package_id"),
        "correction_id": correction.get("correction_id"),
        "cause_confirmation": confirmed.get("confirmation_id"),
        "scope": editable_scope,
        "tests": tests,
    }

    return {
        "schema": SCHEMA,
        "envelope_id": "DEVIMPL-" + _digest(envelope_seed),
        "state": "WAITING_HUMAN_IMPLEMENTATION_APPROVAL",
        "requested_trust_level": REQUESTED_TRUST_LEVEL,
        "trust_policy": {
            "max_autonomous_level": int(policy.get("max_autonomous_level") or 0),
            "requested_level_name": "Branch isolada",
            "human_gate_required": True,
            "autonomous_allowed": False,
            "auto_merge": bool(policy.get("auto_merge", False)),
            "auto_deploy": bool(policy.get("auto_deploy", False)),
            "self_escalation": bool(policy.get("self_escalation", False)),
        },
        "lineage": {
            "snapshot_digest": snapshot_digest,
            "package_id": str(package.get("package_id") or ""),
            "correction_id": str(correction.get("correction_id") or ""),
            "cause_confirmation_id": str(confirmed.get("confirmation_id") or ""),
        },
        "scope": {
            "source_files": source_scope,
            "test_files": test_scope,
            "editable_files": editable_scope,
            "scope_expansion_allowed": False,
        },
        "root_cause": {
            "truth_status": "CONFIRMED",
            "hypothesis_label": str(confirmed.get("hypothesis_label") or ""),
            "reviewer_actor": str(confirmed.get("reviewer_actor") or ""),
            "review_evidence_refs": _list(confirmed.get("evidence_refs"), 40),
        },
        "test_contract": {
            "candidate_tests": tests,
            "mandatory_gates": list(dict.fromkeys(mandatory_gates)),
            "test_deletion_allowed": False,
            "test_weakening_allowed": False,
            "tests_executed": False,
        },
        "risk_tags": risk_tags,
        "change_budget": {
            "max_editable_files": len(editable_scope),
            "scope_expansion_allowed": False,
            "authority_delta_allowed": False,
            "secret_change_allowed": False,
            "production_config_change_allowed": False,
            "real_trading_change_allowed": False,
        },
        "forbidden_changes": [
            "Ampliar roles, scopes, permissões ou autoridade sem revisão separada.",
            "Remover, ignorar ou enfraquecer testes para obter PASS.",
            "Alterar secrets, credenciais ou autenticação administrativa.",
            "Habilitar produção, merge em main, deploy ou trading real.",
            "Editar arquivo fora do escopo autorizado.",
        ],
        "rollback_contract": {
            "required": True,
            "steps": list(policy.get("rollback") or []),
            "recorded_for_this_change": False,
        },
        "implementation_authorized": False,
        "execution_authorized": False,
        "human_approval_required": True,
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


def prepare_implementation_readiness(
    envelope: Mapping[str, Any],
    *,
    rollback_plan: Any,
    builder_actor: Any,
    reviewer_actor: Any,
    breaker_actor: Any,
    readiness_refs: Sequence[Any] | None,
) -> dict[str, Any]:
    """Record readiness prerequisites in-session; never execute implementation."""
    if envelope.get("schema") != SCHEMA:
        raise ValueError("invalid implementation envelope")
    if str(envelope.get("state") or "") != "WAITING_HUMAN_IMPLEMENTATION_APPROVAL":
        raise ValueError("implementation envelope is not awaiting readiness")

    rollback = _clean(rollback_plan, 2400)
    builder = _clean(builder_actor, 160)
    reviewer = _clean(reviewer_actor, 160)
    breaker = _clean(breaker_actor, 160)
    refs = _list(readiness_refs, 40)

    if not rollback:
        raise ValueError("change-specific rollback plan required")
    if not builder or not reviewer or not breaker:
        raise ValueError("builder, reviewer and breaker identities are required")
    if len({builder, reviewer, breaker}) != 3:
        raise ValueError("builder, reviewer and breaker must be independent actors")
    if not refs:
        raise ValueError("implementation readiness evidence required")

    scope = envelope.get("scope") if isinstance(envelope.get("scope"), Mapping) else {}
    test_contract = envelope.get("test_contract") if isinstance(envelope.get("test_contract"), Mapping) else {}
    if not list(scope.get("source_files") or []):
        raise ValueError("implementation source scope is empty")
    if not list(test_contract.get("candidate_tests") or []):
        raise ValueError("implementation test candidates are required")

    mandatory = {str(x) for x in list(test_contract.get("mandatory_gates") or [])}
    required = {
        "TARGETED_TESTS",
        "RISK_REGRESSION_TESTS",
        "QUALITY_TESTS",
        "RELEASE_READINESS",
        "INDEPENDENT_REVIEW",
        "INDEPENDENT_BREAKER",
        "ROLLBACK_REVIEW",
    }
    if not required.issubset(mandatory):
        raise ValueError("mandatory implementation gates are incomplete")

    out = deepcopy(dict(envelope))
    out["readiness"] = {
        "builder_actor": builder,
        "reviewer_actor": reviewer,
        "breaker_actor": breaker,
        "roles_independent": True,
        "readiness_refs": refs,
        "scope_reviewed": True,
        "tests_selected": True,
        "rollback_recorded": True,
    }
    rollback_contract = deepcopy(dict(out.get("rollback_contract") or {}))
    rollback_contract["recorded_for_this_change"] = True
    rollback_contract["change_specific_plan"] = rollback
    out["rollback_contract"] = rollback_contract
    out["state"] = "READY_FOR_HUMAN_IMPLEMENTATION_APPROVAL"
    out["implementation_authorized"] = False
    out["execution_authorized"] = False
    out["analysis_only"] = True
    out["persists_checkpoint"] = False
    out["executes_repository_code"] = False
    out["runs_tests"] = False
    out["writes_files"] = False
    out["network_called"] = False
    out["subprocess_called"] = False
    out["automatic_edit"] = False
    out["automatic_commit"] = False
    out["automatic_merge"] = False
    out["automatic_deploy"] = False
    out["production_change_allowed"] = False
    out["real_trading_enabled"] = False
    out["tool_output_is_authority"] = False
    return out


def approve_implementation_session(
    envelope: Mapping[str, Any],
    *,
    approved: bool,
    approver_actor: Any,
    approval_refs: Sequence[Any] | None,
) -> dict[str, Any]:
    """Record session-only level-2 approval; still do not execute implementation."""
    if envelope.get("schema") != SCHEMA:
        raise ValueError("invalid implementation envelope")
    if str(envelope.get("state") or "") != "READY_FOR_HUMAN_IMPLEMENTATION_APPROVAL":
        raise ValueError("implementation envelope is not ready for approval")
    if int(envelope.get("requested_trust_level") or -1) != REQUESTED_TRUST_LEVEL:
        raise ValueError("unexpected requested developer trust level")
    readiness = envelope.get("readiness") if isinstance(envelope.get("readiness"), Mapping) else {}
    rollback_contract = envelope.get("rollback_contract") if isinstance(envelope.get("rollback_contract"), Mapping) else {}
    actors = [
        str(readiness.get("builder_actor") or ""),
        str(readiness.get("reviewer_actor") or ""),
        str(readiness.get("breaker_actor") or ""),
    ]
    if readiness.get("roles_independent") is not True:
        raise ValueError("independent developer roles required")
    if any(not actor_name for actor_name in actors) or len(set(actors)) != 3:
        raise ValueError("builder, reviewer and breaker are not independent")
    if rollback_contract.get("recorded_for_this_change") is not True:
        raise ValueError("change-specific rollback must be recorded")
    if not str(rollback_contract.get("change_specific_plan") or ""):
        raise ValueError("change-specific rollback plan is empty")
    if not list(readiness.get("readiness_refs") or []):
        raise ValueError("readiness evidence required before approval")

    if approved is not True:
        raise ValueError("explicit human implementation approval required")

    actor = _clean(approver_actor, 160)
    refs = _list(approval_refs, 40)
    if not actor:
        raise ValueError("implementation approver identity required")
    if not refs:
        raise ValueError("implementation approval evidence required")
    if not developer_step_allowed(REQUESTED_TRUST_LEVEL, human_approved=True):
        raise ValueError("developer trust policy denied approved level 2")

    out = deepcopy(dict(envelope))
    auth_seed = {
        "envelope_id": envelope.get("envelope_id"),
        "actor": actor,
        "refs": refs,
    }
    out["authorization"] = {
        "schema": AUTH_SCHEMA,
        "authorization_id": "DEVAUTH-" + _digest(auth_seed),
        "trust_level": REQUESTED_TRUST_LEVEL,
        "approver_actor": actor,
        "approval_refs": refs,
        "human_approved": True,
        "scope_expansion_allowed": False,
        "merge_main_allowed": False,
        "deploy_allowed": False,
        "production_allowed": False,
        "real_trading_allowed": False,
        "builder_actor": actors[0],
        "reviewer_actor": actors[1],
        "breaker_actor": actors[2],
        "rollback_recorded": True,
    }
    out["state"] = "IMPLEMENTATION_AUTHORIZED_SESSION_ONLY"
    out["implementation_authorized"] = True
    out["execution_authorized"] = False
    out["analysis_only"] = True
    out["persists_checkpoint"] = False
    out["executes_repository_code"] = False
    out["runs_tests"] = False
    out["writes_files"] = False
    out["network_called"] = False
    out["subprocess_called"] = False
    out["automatic_edit"] = False
    out["automatic_commit"] = False
    out["automatic_merge"] = False
    out["automatic_deploy"] = False
    out["production_change_allowed"] = False
    out["real_trading_enabled"] = False
    out["tool_output_is_authority"] = False
    return out


__all__ = [
    "SCHEMA",
    "AUTH_SCHEMA",
    "REQUESTED_TRUST_LEVEL",
    "build_implementation_envelope",
    "prepare_implementation_readiness",
    "approve_implementation_session",
]
