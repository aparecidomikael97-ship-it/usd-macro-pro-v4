"""Builder Sandbox Request for AION Developer.

Turns a session-only level-2 implementation authorization into a bounded request
for a future isolated-branch builder. This module does not execute that request.

No function edits files, applies patches, runs tests, calls subprocess/network,
persists checkpoints, commits, merges, deploys, publishes or enables real
trading. Main/production branches and scope expansion fail closed.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from atlasquant_aion_developer_implementation import (
    AUTH_SCHEMA,
    REQUESTED_TRUST_LEVEL,
    SCHEMA as IMPLEMENTATION_SCHEMA,
)
from atlasquant_aion_developer_intelligence import SCHEMA as INTELLIGENCE_SCHEMA
from atlasquant_aion_observability import redact_text

SCHEMA = "ATLASQUANT_AION_DEVELOPER_BUILDER_SANDBOX_REQUEST_V1"
MAX_FILES = 80

_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
_FORBIDDEN_BRANCHES = {
    "main", "master", "production", "prod", "live",
    "refs/heads/main", "refs/heads/master",
}


def _clean(value: Any, limit: int = 1200) -> str:
    return " ".join(redact_text(value).replace("\x00", "").split())[:limit]


def _unique(values: Sequence[Any] | None, limit: int = MAX_FILES) -> list[str]:
    out: list[str] = []
    for raw in list(values or [])[:limit * 2]:
        text = _clean(raw, 500).replace("\\", "/")
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


def _validate_branch(value: Any) -> str:
    branch = _clean(value, 240)
    lower = branch.lower()
    if not branch or lower in _FORBIDDEN_BRANCHES:
        raise ValueError("isolated non-main branch required")
    if branch.startswith("/") or branch.endswith("/") or "//" in branch:
        raise ValueError("invalid isolated branch")
    if ".." in branch or not _BRANCH_RE.fullmatch(branch):
        raise ValueError("invalid isolated branch")
    return branch


def build_builder_sandbox_request(
    snapshot: Mapping[str, Any],
    implementation: Mapping[str, Any],
    *,
    branch: Any,
    baseline_ref: Any,
    candidate_ref: Any,
    requested_files: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Prepare a bounded builder request; never execute it."""
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

    if implementation.get("schema") != IMPLEMENTATION_SCHEMA:
        raise ValueError("invalid implementation envelope")
    if str(implementation.get("state") or "") != "IMPLEMENTATION_AUTHORIZED_SESSION_ONLY":
        raise ValueError("session-only implementation authorization required")
    if implementation.get("implementation_authorized") is not True:
        raise ValueError("implementation authorization missing")
    if implementation.get("execution_authorized") is not False:
        raise ValueError("builder request must start with execution unauthorized")

    lineage = (
        implementation.get("lineage")
        if isinstance(implementation.get("lineage"), Mapping)
        else {}
    )
    if str(lineage.get("snapshot_digest") or "") != snapshot_digest:
        raise ValueError("implementation snapshot lineage mismatch")

    auth = (
        implementation.get("authorization")
        if isinstance(implementation.get("authorization"), Mapping)
        else {}
    )
    if auth.get("schema") != AUTH_SCHEMA:
        raise ValueError("implementation authorization schema missing")
    if auth.get("human_approved") is not True:
        raise ValueError("human implementation approval required")
    if int(auth.get("trust_level") or -1) != REQUESTED_TRUST_LEVEL:
        raise ValueError("unexpected implementation trust level")
    if auth.get("scope_expansion_allowed") is not False:
        raise ValueError("scope expansion must remain blocked")
    if any(bool(auth.get(key)) for key in (
        "merge_main_allowed",
        "deploy_allowed",
        "production_allowed",
        "real_trading_allowed",
    )):
        raise ValueError("implementation authorization widened external authority")
    if auth.get("rollback_recorded") is not True:
        raise ValueError("rollback must be recorded before builder request")

    readiness = (
        implementation.get("readiness")
        if isinstance(implementation.get("readiness"), Mapping)
        else {}
    )
    actors = [
        str(readiness.get("builder_actor") or ""),
        str(readiness.get("reviewer_actor") or ""),
        str(readiness.get("breaker_actor") or ""),
    ]
    if readiness.get("roles_independent") is not True:
        raise ValueError("independent developer roles required")
    if any(not actor for actor in actors) or len(set(actors)) != 3:
        raise ValueError("developer role separation is invalid")
    if str(auth.get("builder_actor") or "") != actors[0]:
        raise ValueError("authorized builder identity mismatch")

    branch_name = _validate_branch(branch)
    baseline = _clean(baseline_ref, 240)
    candidate = _clean(candidate_ref, 240)
    if not baseline or not candidate or baseline == candidate:
        raise ValueError("distinct baseline_ref and candidate_ref are required")

    known = {
        str(row.get("path") or ""): dict(row)
        for row in list(snapshot.get("files") or [])
        if isinstance(row, Mapping) and str(row.get("path") or "")
    }
    scope = (
        implementation.get("scope")
        if isinstance(implementation.get("scope"), Mapping)
        else {}
    )
    editable = _unique(scope.get("editable_files"), MAX_FILES)
    source_files = set(_unique(scope.get("source_files"), MAX_FILES))
    if not editable or not source_files:
        raise ValueError("authorized editable scope is empty")

    requested = _unique(
        requested_files if requested_files is not None else editable,
        MAX_FILES,
    )
    if not requested:
        raise ValueError("builder request files are empty")
    if any(path not in editable for path in requested):
        raise ValueError("builder request attempts scope expansion")
    if any(path not in known for path in requested):
        raise ValueError("builder request contains unknown repository path")
    if not any(path in source_files for path in requested):
        raise ValueError("builder request must include at least one source file")

    blockers: list[str] = []
    workflow_files = [
        path for path in requested
        if str(known[path].get("category") or "") == "WORKFLOW"
    ]
    if workflow_files:
        blockers.append("WORKFLOW_CHANGE_REQUIRES_SEPARATE_RELEASE_REVIEW")

    test_contract = (
        implementation.get("test_contract")
        if isinstance(implementation.get("test_contract"), Mapping)
        else {}
    )
    candidate_tests = _unique(test_contract.get("candidate_tests"), 120)
    mandatory_gates = _unique(test_contract.get("mandatory_gates"), 40)
    if not candidate_tests:
        blockers.append("TEST_CANDIDATES_MISSING")
    if not mandatory_gates:
        blockers.append("MANDATORY_GATES_MISSING")

    request_seed = {
        "snapshot_digest": snapshot_digest,
        "envelope_id": implementation.get("envelope_id"),
        "authorization_id": auth.get("authorization_id"),
        "branch": branch_name,
        "baseline": baseline,
        "candidate": candidate,
        "files": requested,
    }
    state = "READY_FOR_BUILDER_SANDBOX" if not blockers else "BLOCKED"

    return {
        "schema": SCHEMA,
        "request_id": "DEVBUILD-" + _digest(request_seed),
        "state": state,
        "lineage": {
            "snapshot_digest": snapshot_digest,
            "implementation_envelope_id": str(implementation.get("envelope_id") or ""),
            "implementation_authorization_id": str(auth.get("authorization_id") or ""),
        },
        "branch_contract": {
            "branch": branch_name,
            "baseline_ref": baseline,
            "candidate_ref": candidate,
            "main_branch_allowed": False,
            "force_push_allowed": False,
            "history_rewrite_allowed": False,
        },
        "roles": {
            "builder_actor": actors[0],
            "reviewer_actor": actors[1],
            "breaker_actor": actors[2],
            "roles_independent": True,
        },
        "scope": {
            "requested_files": requested,
            "authorized_files": editable,
            "scope_expansion_allowed": False,
            "new_file_allowed": False,
            "delete_file_allowed": False,
            "rename_file_allowed": False,
        },
        "test_contract": {
            "candidate_tests": candidate_tests,
            "mandatory_gates": mandatory_gates,
            "test_deletion_allowed": False,
            "test_weakening_allowed": False,
            "tests_executed": False,
        },
        "blockers": blockers,
        "builder_instructions": [
            "Modificar somente arquivos em requested_files.",
            "Não criar, excluir ou renomear arquivos neste contrato v1.",
            "Não ampliar autoridade, permissões, secrets ou efeitos externos.",
            "Preservar testes existentes e adicionar evidência quando necessário.",
            "Parar e pedir nova revisão se o escopo precisar crescer.",
            "Não fazer merge em main, deploy ou mudança de produção.",
        ],
        "request_prepared": True,
        "execution_authorized": False,
        "executor_attached": False,
        "patch_generated": False,
        "writes_files": False,
        "runs_tests": False,
        "network_called": False,
        "subprocess_called": False,
        "automatic_commit": False,
        "automatic_merge": False,
        "automatic_deploy": False,
        "production_change_allowed": False,
        "real_trading_enabled": False,
        "tool_output_is_authority": False,
    }


__all__ = [
    "SCHEMA",
    "MAX_FILES",
    "build_builder_sandbox_request",
]
