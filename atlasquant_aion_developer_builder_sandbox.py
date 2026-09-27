"""Builder Sandbox Request for AION Developer.

Turns a session-only level-2 implementation authorization into a bounded request
for a future isolated-branch builder. This module does not execute that request.

No function edits files, applies patches, runs tests, calls subprocess/network,
persists checkpoints, commits, merges, deploys, publishes or enables real
trading. Main/production branches and scope expansion fail closed.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Mapping, Sequence

from atlasquant_aion_developer_implementation import (
    AUTH_SCHEMA,
    REQUESTED_TRUST_LEVEL,
    SCHEMA as IMPLEMENTATION_SCHEMA,
)
from atlasquant_aion_developer_intelligence import (
    SCHEMA as INTELLIGENCE_SCHEMA,
    validate_snapshot_integrity,
)
from atlasquant_aion_observability import redact_text
from atlasquant_aion_developer_manifest import (
    REQUIRED_MANDATORY_GATES,
    assert_required_mandatory_gates,
    authorization_manifest_id,
    expected_builder_request_id,
    implementation_base_manifest_id,
    implementation_readiness_manifest_id,
    normalize_ref,
    release_sensitive_path,
    require_string_sequence,
    structural_request_roles,
    test_contract_manifest_id,
    validate_candidate_ref,
    validate_isolated_branch,
)
from atlasquant_aion_developer_principal_identity import (
    AUTHORIZATION_PRINCIPAL_FIELDS,
    READINESS_PRINCIPAL_FIELDS,
    require_distinct_principal_ids,
    require_principal_id,
)

SCHEMA = "ATLASQUANT_AION_DEVELOPER_BUILDER_SANDBOX_REQUEST_V1"
READY_STATE = "READY_FOR_BUILDER_SANDBOX"
BLOCKED_STATE = "BLOCKED"
MAX_FILES = 80
_RELEASE_BLOCKER = "RELEASE_SURFACE_REQUIRES_SEPARATE_RELEASE_REVIEW"
_MISSING_TESTS_BLOCKER = "TEST_CANDIDATES_MISSING"
_KNOWN_BLOCKERS = frozenset({_RELEASE_BLOCKER, _MISSING_TESTS_BLOCKER})
_BUILDER_INSTRUCTIONS = (
    "Modificar somente arquivos em requested_files.",
    "Não criar, excluir ou renomear arquivos neste contrato v1.",
    "Não ampliar autoridade, permissões, secrets ou efeitos externos.",
    "Preservar testes existentes e adicionar evidência quando necessário.",
    "Parar e pedir nova revisão se o escopo precisar crescer.",
    "Não fazer merge em main, deploy ou mudança de produção.",
)
_FALSE_FLAGS = (
    "execution_authorized",
    "executor_attached",
    "patch_generated",
    "writes_files",
    "runs_tests",
    "network_called",
    "subprocess_called",
    "automatic_commit",
    "automatic_merge",
    "automatic_deploy",
    "production_change_allowed",
    "real_trading_enabled",
    "tool_output_is_authority",
)
_LINEAGE_KEYS = frozenset({
    "snapshot_digest",
    "implementation_envelope_id",
    "implementation_authorization_id",
})
_BRANCH_KEYS = frozenset({
    "branch",
    "baseline_ref",
    "candidate_ref",
    "candidate_bound_to_branch",
    "main_branch_allowed",
    "force_push_allowed",
    "history_rewrite_allowed",
})
_ROLE_KEYS = frozenset({
    "builder_actor",
    "reviewer_actor",
    "breaker_actor",
    "approver_actor",
    "builder_principal_id",
    "reviewer_principal_id",
    "breaker_principal_id",
    "approver_principal_id",
    "roles_independent",
})
_SCOPE_KEYS = frozenset({
    "requested_files",
    "authorized_files",
    "scope_expansion_allowed",
    "new_file_allowed",
    "delete_file_allowed",
    "rename_file_allowed",
})
_TEST_KEYS = frozenset({
    "candidate_tests",
    "mandatory_gates",
    "test_deletion_allowed",
    "test_weakening_allowed",
    "tests_executed",
})
_CONTRACT_KEYS = frozenset({
    "schema",
    "request_id",
    "state",
    "lineage",
    "branch_contract",
    "roles",
    "scope",
    "test_contract",
    "blockers",
    "builder_instructions",
    "request_prepared",
    "test_contract_manifest_id",
}) | frozenset(_FALSE_FLAGS)

_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
_FORBIDDEN_BRANCHES = {
    "main", "master", "production", "prod", "live",
    "refs/heads/main", "refs/heads/master",
}


def _clean(value: Any, limit: int = 1200) -> str:
    return " ".join(redact_text(value).replace("\x00", "").split())[:limit]


def _normalize_ref(value: Any, limit: int = 240) -> str:
    return normalize_ref(value, limit)


def _unique(values: Sequence[Any] | None, limit: int = MAX_FILES) -> list[str]:
    out: list[str] = []
    for raw in list(values or [])[:limit * 2]:
        text = _clean(raw, 500).replace("\\", "/")
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _validate_branch(value: Any) -> str:
    return validate_isolated_branch(value)


def _validate_candidate_ref(value: Any, branch: str) -> str:
    return validate_candidate_ref(value, branch)


def _reject_closed(document: Mapping[str, Any], allowed: frozenset[str], label: str) -> None:
    unknown = sorted(set(document) - allowed)
    if unknown:
        raise ValueError(f"unknown {label} field {unknown[0]}")
    missing = sorted(allowed - set(document))
    if missing:
        raise ValueError(f"{label} is missing {missing[0]}")


def _nonempty_token(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{label} is required")
    return value


def _derived_builder_blockers(requested: Sequence[str], candidate_tests: Sequence[str]) -> list[str]:
    blockers: list[str] = []
    if any(release_sensitive_path(path) for path in requested):
        blockers.append(_RELEASE_BLOCKER)
    if not candidate_tests:
        blockers.append(_MISSING_TESTS_BLOCKER)
    return blockers

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
    validate_snapshot_integrity(snapshot)
    if bool(snapshot.get("truncated")):
        raise ValueError("truncated snapshot cannot enter builder sandbox")
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
        raise ValueError("legacy or missing authorization schema is not principal-bound")
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
    if str(implementation.get("envelope_manifest_id") or "") != implementation_base_manifest_id(implementation):
        raise ValueError("implementation envelope manifest mismatch")
    current_readiness_manifest = implementation_readiness_manifest_id(implementation)
    if str(implementation.get("readiness_manifest_id") or "") != current_readiness_manifest:
        raise ValueError("implementation readiness manifest mismatch")
    if str(auth.get("authorized_readiness_manifest_id") or "") != current_readiness_manifest:
        raise ValueError("authorization is not bound to current readiness manifest")
    if str(auth.get("authorization_id") or "") != authorization_manifest_id(implementation, auth):
        raise ValueError("implementation authorization integrity mismatch")

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
    if any(not actor for actor in actors):
        raise ValueError("developer role separation is invalid")
    readiness_principals = require_distinct_principal_ids(readiness, READINESS_PRINCIPAL_FIELDS)
    authorized_principals = require_distinct_principal_ids(auth, AUTHORIZATION_PRINCIPAL_FIELDS)
    for field in READINESS_PRINCIPAL_FIELDS:
        if authorized_principals[field] != readiness_principals[field]:
            raise ValueError("builder request principal differs from authorization")
    approver_principal = require_principal_id(
        authorized_principals["approver_principal_id"],
        "approver_principal_id",
    )
    if approver_principal in set(readiness_principals.values()):
        raise ValueError("approver principal is not independent")

    branch_name = _validate_branch(branch)
    baseline = _normalize_ref(baseline_ref, 240)
    candidate = _validate_candidate_ref(candidate_ref, branch_name)
    if not baseline or baseline.casefold() == candidate.casefold():
        raise ValueError("distinct baseline_ref and candidate_ref are required")
    revision = implementation.get("revision_contract") if isinstance(implementation.get("revision_contract"), Mapping) else {}
    if branch_name != str(revision.get("branch") or ""):
        raise ValueError("builder branch differs from approved revision contract")
    if baseline != str(revision.get("baseline_ref") or ""):
        raise ValueError("builder baseline differs from approved revision contract")
    if candidate != str(revision.get("candidate_ref") or ""):
        raise ValueError("builder candidate differs from approved revision contract")

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
    raw_editable = require_string_sequence(scope.get("editable_files"), "authorized_files")
    raw_source = require_string_sequence(scope.get("source_files"), "source_files")
    if len(raw_editable) > MAX_FILES or len(raw_source) > MAX_FILES:
        raise ValueError("authorized file scope exceeds builder limit")
    editable = _unique(raw_editable, MAX_FILES)
    source_files = set(_unique(raw_source, MAX_FILES))
    if not editable or not source_files:
        raise ValueError("authorized editable scope is empty")

    if requested_files is None:
        raw_requested = list(editable)
    else:
        raw_requested = require_string_sequence(requested_files, "requested_files")
    if len(raw_requested) > MAX_FILES:
        raise ValueError("builder request exceeds file limit")
    requested = _unique(raw_requested, MAX_FILES)
    if not requested:
        raise ValueError("builder request files are empty")
    if any(path not in editable for path in requested):
        raise ValueError("builder request attempts scope expansion")
    if any(path not in known for path in requested):
        raise ValueError("builder request contains unknown repository path")
    if not any(path in source_files for path in requested):
        raise ValueError("builder request must include at least one source file")

    blockers: list[str] = []
    release_files = [
        path for path in requested
        if str(known[path].get("category") or "") == "WORKFLOW"
        or release_sensitive_path(path)
    ]
    if release_files:
        blockers.append("RELEASE_SURFACE_REQUIRES_SEPARATE_RELEASE_REVIEW")

    test_contract = (
        implementation.get("test_contract")
        if isinstance(implementation.get("test_contract"), Mapping)
        else {}
    )
    if test_contract.get("test_deletion_allowed") is not False or test_contract.get("test_weakening_allowed") is not False:
        raise ValueError("test deletion or weakening must remain forbidden")
    raw_candidate_tests = require_string_sequence(test_contract.get("candidate_tests"), "candidate_tests")
    raw_gates = require_string_sequence(test_contract.get("mandatory_gates"), "mandatory_gates")
    if len(raw_candidate_tests) > 120:
        raise ValueError("candidate tests exceed builder limit")
    if len(raw_gates) > 40:
        raise ValueError("mandatory gates exceed builder limit")
    candidate_tests = _unique(raw_candidate_tests, 120)
    mandatory_gates = _unique(raw_gates, 40)
    if not candidate_tests:
        blockers.append("TEST_CANDIDATES_MISSING")
    assert_required_mandatory_gates(mandatory_gates)
    state = READY_STATE if not blockers else BLOCKED_STATE

    out = {
        "schema": SCHEMA,
        "request_id": "",
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
            "candidate_bound_to_branch": True,
            "main_branch_allowed": False,
            "force_push_allowed": False,
            "history_rewrite_allowed": False,
        },
        "roles": {
            "builder_actor": actors[0],
            "reviewer_actor": actors[1],
            "breaker_actor": actors[2],
            "approver_actor": str(auth.get("approver_actor") or ""),
            "builder_principal_id": readiness_principals["builder_principal_id"],
            "reviewer_principal_id": readiness_principals["reviewer_principal_id"],
            "breaker_principal_id": readiness_principals["breaker_principal_id"],
            "approver_principal_id": approver_principal,
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
        "builder_instructions": list(_BUILDER_INSTRUCTIONS),
        "request_prepared": True,
        **{field: False for field in _FALSE_FLAGS},
    }
    out["test_contract_manifest_id"] = test_contract_manifest_id(out["test_contract"])
    out["request_id"] = expected_builder_request_id(out)
    return out


def assert_builder_sandbox_request_integrity(request: Mapping[str, Any]) -> str:
    """Revalidate the builder document. A recomputed id is not a substitute.

    Lineage strings are checked for presence. They are not an independent
    proof that an implementation envelope or a repository snapshot exists.
    """
    if not isinstance(request, Mapping):
        raise ValueError("builder request must be an object")
    if request.get("schema") != SCHEMA:
        raise ValueError("invalid Builder Sandbox Request")
    _reject_closed(request, _CONTRACT_KEYS, "builder request")
    for field in _FALSE_FLAGS:
        if request.get(field) is not False:
            raise ValueError(f"builder request cannot claim {field}")
    if request.get("request_prepared") is not True:
        raise ValueError("builder request was not prepared")
    lineage = request.get("lineage")
    if not isinstance(lineage, Mapping):
        raise ValueError("builder lineage must be an object")
    _reject_closed(lineage, _LINEAGE_KEYS, "builder lineage")
    for field in _LINEAGE_KEYS:
        _nonempty_token(lineage.get(field), field)
    branch = request.get("branch_contract")
    if not isinstance(branch, Mapping):
        raise ValueError("builder branch contract must be an object")
    _reject_closed(branch, _BRANCH_KEYS, "builder branch contract")
    branch_name = validate_isolated_branch(branch.get("branch"))
    if branch.get("branch") != branch_name:
        raise ValueError("builder branch is not the isolated branch")
    baseline = normalize_ref(branch.get("baseline_ref"), 240)
    candidate = validate_candidate_ref(branch.get("candidate_ref"), branch_name)
    if branch.get("baseline_ref") != baseline or branch.get("candidate_ref") != candidate:
        raise ValueError("builder refs are not canonical")
    if not baseline or baseline.casefold() == candidate.casefold():
        raise ValueError("distinct baseline_ref and candidate_ref are required")
    if branch.get("candidate_bound_to_branch") is not True:
        raise ValueError("candidate ref is not bound to isolated branch")
    if branch.get("main_branch_allowed") is not False:
        raise ValueError("main branch authority must remain blocked")
    if branch.get("force_push_allowed") is not False:
        raise ValueError("force push must remain blocked")
    if branch.get("history_rewrite_allowed") is not False:
        raise ValueError("history rewrite must remain blocked")
    roles = request.get("roles")
    if not isinstance(roles, Mapping):
        raise ValueError("builder roles must be an object")
    _reject_closed(roles, _ROLE_KEYS, "builder roles")
    for actor in ("builder_actor", "reviewer_actor", "breaker_actor", "approver_actor"):
        _nonempty_token(roles.get(actor), actor)
    if roles.get("roles_independent") is not True:
        raise ValueError("independent developer roles required")
    principals = require_distinct_principal_ids(roles, AUTHORIZATION_PRINCIPAL_FIELDS)
    approver = principals["approver_principal_id"]
    if approver in {
        principals["builder_principal_id"],
        principals["reviewer_principal_id"],
        principals["breaker_principal_id"],
    }:
        raise ValueError("approver principal is not independent")
    scope = request.get("scope")
    if not isinstance(scope, Mapping):
        raise ValueError("builder scope must be an object")
    _reject_closed(scope, _SCOPE_KEYS, "builder scope")
    requested = require_string_sequence(scope.get("requested_files"), "requested_files")
    authorized = require_string_sequence(scope.get("authorized_files"), "authorized_files")
    if not requested:
        raise ValueError("requested file scope is empty")
    if any(path not in set(authorized) for path in requested):
        raise ValueError("requested files exceed authorized scope")
    if scope.get("scope_expansion_allowed") is not False:
        raise ValueError("scope expansion must remain blocked")
    for flag in ("new_file_allowed", "delete_file_allowed", "rename_file_allowed"):
        if scope.get(flag) is not False:
            raise ValueError(f"{flag} must remain false")
    tests = request.get("test_contract")
    if not isinstance(tests, Mapping):
        raise ValueError("builder test contract must be an object")
    _reject_closed(tests, _TEST_KEYS, "builder test contract")
    candidate_tests = require_string_sequence(tests.get("candidate_tests"), "candidate_tests")
    mandatory_gates = require_string_sequence(tests.get("mandatory_gates"), "mandatory_gates")
    if tests.get("test_deletion_allowed") is not False:
        raise ValueError("test deletion must remain blocked")
    if tests.get("test_weakening_allowed") is not False:
        raise ValueError("test weakening must remain blocked")
    if tests.get("tests_executed") is not False:
        raise ValueError("builder request cannot claim tests_executed")
    assert_required_mandatory_gates(mandatory_gates)
    if list(request.get("builder_instructions") or []) != list(_BUILDER_INSTRUCTIONS):
        raise ValueError("builder instructions are not canonical")
    blockers = request.get("blockers")
    if not isinstance(blockers, list):
        raise ValueError("builder blockers must be a list")
    derived = _derived_builder_blockers(requested, candidate_tests)
    state = request.get("state")
    if state == READY_STATE:
        if blockers or derived:
            raise ValueError("ready builder request cannot carry blockers")
    elif state == BLOCKED_STATE:
        if not blockers:
            raise ValueError("blocked builder request must name blockers")
        if any(item not in _KNOWN_BLOCKERS for item in blockers):
            raise ValueError("builder blocker was not derived")
        if any(item not in blockers for item in derived):
            raise ValueError("builder blockers omit a derived blocker")
    else:
        raise ValueError("builder request state is not an accepted design state")
    manifest = test_contract_manifest_id(tests)
    if request.get("test_contract_manifest_id") != manifest:
        raise ValueError("test contract manifest mismatch")
    if request.get("request_id") != expected_builder_request_id(request):
        raise ValueError("builder request id mismatch")
    return manifest


def structural_builder_sandbox_request(
    *,
    branch: str = "cursor/fix",
    baseline_ref: str = "main@aaa",
    candidate_ref: str = "cursor/fix@bbb",
    requested_files: Sequence[str] = ("test_module.py",),
    authorized_files: Sequence[str] | None = None,
    candidate_tests: Sequence[str] | None = None,
    mandatory_gates: Sequence[str] | None = None,
    roles: Mapping[str, Any] | None = None,
    lineage: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Seal a structural fixture. It is not an implementation-envelope proof."""
    role_values = dict(structural_request_roles() if roles is None else roles)
    role_values.setdefault("builder_actor", "builder")
    role_values.setdefault("reviewer_actor", "reviewer")
    role_values.setdefault("breaker_actor", "breaker")
    role_values.setdefault("approver_actor", "approver")
    role_values.setdefault("roles_independent", True)
    files = list(requested_files)
    authorized = list(files if authorized_files is None else authorized_files)
    tests = list(files if candidate_tests is None else candidate_tests)
    gates = list(REQUIRED_MANDATORY_GATES if mandatory_gates is None else mandatory_gates)
    lineage_values = {
        "snapshot_digest": "REPO-FIXTURE",
        "implementation_envelope_id": "DEVIMPL-FIXTURE",
        "implementation_authorization_id": "DEVAUTH-FIXTURE",
    }
    if lineage is not None:
        lineage_values.update(dict(lineage))
    derived = _derived_builder_blockers(files, tests)
    document = {
        "schema": SCHEMA,
        "request_id": "",
        "state": READY_STATE if not derived else BLOCKED_STATE,
        "lineage": lineage_values,
        "branch_contract": {
            "branch": branch,
            "baseline_ref": baseline_ref,
            "candidate_ref": candidate_ref,
            "candidate_bound_to_branch": True,
            "main_branch_allowed": False,
            "force_push_allowed": False,
            "history_rewrite_allowed": False,
        },
        "roles": role_values,
        "scope": {
            "requested_files": files,
            "authorized_files": authorized,
            "scope_expansion_allowed": False,
            "new_file_allowed": False,
            "delete_file_allowed": False,
            "rename_file_allowed": False,
        },
        "test_contract": {
            "candidate_tests": tests,
            "mandatory_gates": gates,
            "test_deletion_allowed": False,
            "test_weakening_allowed": False,
            "tests_executed": False,
        },
        "blockers": derived,
        "builder_instructions": list(_BUILDER_INSTRUCTIONS),
        "request_prepared": True,
        **{field: False for field in _FALSE_FLAGS},
    }
    document["test_contract_manifest_id"] = test_contract_manifest_id(document["test_contract"])
    document["request_id"] = expected_builder_request_id(document)
    assert_builder_sandbox_request_integrity(document)
    return document


__all__ = [
    "SCHEMA",
    "READY_STATE",
    "MAX_FILES",
    "build_builder_sandbox_request",
    "assert_builder_sandbox_request_integrity",
    "structural_builder_sandbox_request",
]
