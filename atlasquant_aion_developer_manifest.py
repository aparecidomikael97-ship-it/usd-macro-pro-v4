"""Canonical integrity helpers for the AION Developer chain.

Deterministic, read-only fingerprints and normalization rules shared across
planning, approval and sandbox contracts. This module never executes repository
code, writes files, calls a process/network, commits, merges, deploys or enables
production/trading authority.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
import unicodedata
from typing import Any, Mapping, Sequence

from atlasquant_aion_observability import redact_text
from atlasquant_aion_developer_principal_identity import (
    AUTHORIZATION_PRINCIPAL_FIELDS,
    PRINCIPAL_BINDING_VERSION,
    READINESS_PRINCIPAL_FIELDS,
    require_principal_id,
)

SCHEMA = "ATLASQUANT_AION_DEVELOPER_MANIFEST_V1"
SNAPSHOT_MANIFEST_VERSION = 2

_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
_RESERVED_BRANCH_ROOTS = frozenset({"main","master","prod","production","live"})


def clean(value: Any, limit: int = 1200) -> str:
    return " ".join(redact_text(value).replace("\x00","").split())[:limit]


def stable_digest(value: Any, *, prefix: str = "", length: int = 24) -> str:
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,default=str,separators=(",",":"))
    return prefix+sha256(raw.encode("utf-8")).hexdigest()[:length].upper()


def canonical_identity(value: Any) -> str:
    """NFKC plus casefold, without format or control characters.

    Invisible characters such as zero-width spaces, BOM, soft hyphen and ZWNJ
    must not create a second actor from the same logical identity.
    """
    normalized=unicodedata.normalize("NFKC",clean(value,160))
    visible="".join(
        ch for ch in normalized
        if unicodedata.category(ch) not in {"Cf","Cc"}
    )
    return " ".join(visible.split()).casefold()


def normalize_ref(value: Any, limit: int = 240) -> str:
    return unicodedata.normalize("NFKC",clean(value,limit))


def _reserved_branch_segment(part: str) -> bool:
    token=part.casefold()
    while token.endswith(".git"):
        token=token[:-4]
    return token in _RESERVED_BRANCH_ROOTS


def validate_isolated_branch(value: Any) -> str:
    branch=normalize_ref(value,240)
    while branch.startswith("refs/heads/"):
        branch=branch[len("refs/heads/"):]
    lower=branch.casefold()
    if not branch or lower.startswith("refs/remotes/") or lower.startswith("origin/"):
        raise ValueError("isolated local branch required")
    if branch.startswith("-") or branch.startswith("/") or branch.endswith("/") or "//" in branch:
        raise ValueError("invalid isolated branch")
    if any(ch in branch for ch in (" ","~","^",":","?","*","[","\\")):
        raise ValueError("invalid isolated branch")
    if ".." in branch or "@{" in branch or not _BRANCH_RE.fullmatch(branch):
        raise ValueError("invalid isolated branch")
    parts=branch.split("/")
    if any(not part or part in {".",".."} or part.endswith(".lock") for part in parts):
        raise ValueError("invalid isolated branch")
    if any(_reserved_branch_segment(part) for part in parts):
        raise ValueError("production/main branch family is forbidden")
    return branch


def validate_candidate_ref(value: Any, branch: Any) -> str:
    candidate=normalize_ref(value,240)
    logical_branch=validate_isolated_branch(branch)
    if not candidate:
        raise ValueError("candidate_ref required")
    candidate_branch, sep, candidate_suffix = candidate.partition("@")
    if candidate_branch.startswith("refs/heads/"):
        candidate_branch=candidate_branch[len("refs/heads/"):]
    if candidate_branch != logical_branch:
        raise ValueError("candidate_ref must be bound to the exact isolated branch")
    return logical_branch + (("@" + candidate_suffix) if sep else "")


def snapshot_digest_from_rows(root_name: Any, rows: Sequence[Mapping[str,Any]]) -> str:
    payload=[]
    for raw in sorted((dict(x) for x in rows),key=lambda x:str(x.get("path") or "")):
        payload.append({
            "path":str(raw.get("path") or ""),
            "category":str(raw.get("category") or ""),
            "size_bytes":int(raw.get("size_bytes") or 0),
            "imports":[str(x) for x in list(raw.get("imports") or [])],
            "syntax_state":str(raw.get("syntax_state") or ""),
            "content_sha256":str(raw.get("content_sha256") or ""),
        })
    return stable_digest({
        "manifest_version":SNAPSHOT_MANIFEST_VERSION,
        "root_name":clean(root_name,240),
        "files":payload,
    },prefix="REPO-",length=24)


def validate_snapshot_integrity(snapshot: Mapping[str,Any]) -> str:
    rows=[dict(x) for x in list(snapshot.get("files") or []) if isinstance(x,Mapping)]
    if int(snapshot.get("snapshot_manifest_version") or 0) != SNAPSHOT_MANIFEST_VERSION:
        raise ValueError("unsupported snapshot manifest version")
    if int(snapshot.get("file_count") or -1) != len(rows):
        raise ValueError("snapshot file_count mismatch")
    paths=[str(row.get("path") or "") for row in rows]
    if not paths or any(not path for path in paths) or len(set(paths)) != len(paths):
        raise ValueError("snapshot paths are invalid")
    for row in rows:
        digest=str(row.get("content_sha256") or "")
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest.lower()):
            raise ValueError("snapshot content hash missing")
    expected=snapshot_digest_from_rows(snapshot.get("root_name"),rows)
    actual=str(snapshot.get("snapshot_digest") or "")
    if actual != expected:
        raise ValueError("snapshot integrity mismatch")
    return actual


def correction_manifest_id(correction: Mapping[str,Any]) -> str:
    return stable_digest({
        "correction_id":correction.get("correction_id"),
        "lineage":correction.get("lineage"),
        "target_files":list(correction.get("target_files") or []),
        "test_candidates":list(correction.get("test_candidates") or []),
        "hypotheses":list(correction.get("hypotheses") or []),
        "risk_tags":list(correction.get("risk_tags") or []),
        "evidence_required":list(correction.get("evidence_required") or []),
    },prefix="DEVCORRMAN-",length=20)


def implementation_base_manifest_id(envelope: Mapping[str,Any]) -> str:
    rollback=envelope.get("rollback_contract") if isinstance(envelope.get("rollback_contract"),Mapping) else {}
    return stable_digest({
        "envelope_id":envelope.get("envelope_id"),
        "requested_trust_level":envelope.get("requested_trust_level"),
        "lineage":envelope.get("lineage"),
        "revision_contract":envelope.get("revision_contract"),
        "scope":envelope.get("scope"),
        "root_cause":envelope.get("root_cause"),
        "test_contract":envelope.get("test_contract"),
        "risk_tags":envelope.get("risk_tags"),
        "change_budget":envelope.get("change_budget"),
        "rollback_static":{
            "required":rollback.get("required"),
            "steps":list(rollback.get("steps") or []),
        },
    },prefix="DEVIMPLMAN-",length=20)


def implementation_readiness_manifest_id(envelope: Mapping[str,Any]) -> str:
    """Digest readiness authority. Display actors are not inputs.

    A legacy readiness document without principal ids fails closed here
    instead of hashing as equivalent to the principal-binding schema.
    """
    rollback=envelope.get("rollback_contract") if isinstance(envelope.get("rollback_contract"),Mapping) else {}
    readiness=envelope.get("readiness") if isinstance(envelope.get("readiness"),Mapping) else {}
    principals={
        field: require_principal_id(readiness.get(field), field)
        for field in READINESS_PRINCIPAL_FIELDS
    }
    return stable_digest({
        "principal_binding": PRINCIPAL_BINDING_VERSION,
        "base_manifest_id":implementation_base_manifest_id(envelope),
        "builder_principal_id":principals["builder_principal_id"],
        "reviewer_principal_id":principals["reviewer_principal_id"],
        "breaker_principal_id":principals["breaker_principal_id"],
        "readiness_refs":list(readiness.get("readiness_refs") or []),
        "roles_independent":readiness.get("roles_independent"),
        "scope_reviewed":readiness.get("scope_reviewed"),
        "tests_selected":readiness.get("tests_selected"),
        "rollback_recorded":readiness.get("rollback_recorded"),
        "rollback":{
            "recorded_for_this_change":rollback.get("recorded_for_this_change"),
            "change_specific_plan":rollback.get("change_specific_plan"),
        },
    },prefix="DEVREADYMAN-",length=20)


def authorization_manifest_id(envelope: Mapping[str,Any], authorization: Mapping[str,Any]) -> str:
    """Digest authorization authority. Display actors are not inputs.

    Missing principal ids raise. They are not coerced into the previous
    identity-key digest.
    """
    if not isinstance(authorization, Mapping):
        raise ValueError("implementation authorization must be an object")
    principals={
        field: require_principal_id(authorization.get(field), field)
        for field in AUTHORIZATION_PRINCIPAL_FIELDS
    }
    return stable_digest({
        "principal_binding": PRINCIPAL_BINDING_VERSION,
        "readiness_manifest_id":implementation_readiness_manifest_id(envelope),
        "trust_level":authorization.get("trust_level"),
        "approver_principal_id":principals["approver_principal_id"],
        "approval_refs":list(authorization.get("approval_refs") or []),
        "human_approved":authorization.get("human_approved"),
        "scope_expansion_allowed":authorization.get("scope_expansion_allowed"),
        "merge_main_allowed":authorization.get("merge_main_allowed"),
        "deploy_allowed":authorization.get("deploy_allowed"),
        "production_allowed":authorization.get("production_allowed"),
        "real_trading_allowed":authorization.get("real_trading_allowed"),
        "builder_principal_id":principals["builder_principal_id"],
        "reviewer_principal_id":principals["reviewer_principal_id"],
        "breaker_principal_id":principals["breaker_principal_id"],
        "rollback_recorded":authorization.get("rollback_recorded"),
    },prefix="DEVAUTH-",length=18)


def structural_request_roles() -> dict[str, str]:
    """Distinct fixture principals. Not derived from a display label."""
    return {
        "builder_principal_id": "prn_builder01",
        "reviewer_principal_id": "prn_reviewer1",
        "breaker_principal_id": "prn_breaker01",
        "approver_principal_id": "prn_approver1",
    }


REQUIRED_MANDATORY_GATES = (
    "TARGETED_TESTS",
    "RISK_REGRESSION_TESTS",
    "QUALITY_TESTS",
    "RELEASE_READINESS",
    "INDEPENDENT_REVIEW",
    "INDEPENDENT_BREAKER",
    "ROLLBACK_REVIEW",
)


def require_string_sequence(value: Any, field: str) -> list[str]:
    """Require an explicit list or tuple of strings.

    A bare string is a sequence of characters and must not be accepted as
    evidence, a gate list, or a file list. Mappings and scalars are rejected
    as well, including when the field is required and the value is missing.
    """
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field} must be an explicit list or tuple of strings")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or isinstance(item, (bytes, bytearray)):
            raise ValueError(f"{field} contains a non-string element")
        if not item or item != item.strip() or any(unicodedata.category(char) == "Cc" for char in item):
            raise ValueError(f"{field} contains an invalid string element")
        out.append(item)
    return out


def assert_required_mandatory_gates(gates: Sequence[str]) -> None:
    present = set(gates)
    if any(gate not in present for gate in REQUIRED_MANDATORY_GATES):
        raise ValueError("mandatory gates are incomplete")


def test_contract_manifest_id(contract: Mapping[str, Any]) -> str:
    """Digest the test contract fields that authorize later runner targets."""
    if not isinstance(contract, Mapping):
        raise ValueError("test contract must be an object")
    if contract.get("test_deletion_allowed") is not False or contract.get("test_weakening_allowed") is not False:
        raise ValueError("test deletion or weakening must remain forbidden")
    binding = {
        "candidate_tests": require_string_sequence(contract.get("candidate_tests"), "candidate_tests"),
        "mandatory_gates": require_string_sequence(contract.get("mandatory_gates"), "mandatory_gates"),
        "test_deletion_allowed": False,
        "test_weakening_allowed": False,
    }
    return stable_digest(binding, prefix="DEVTEST-", length=18)


def expected_builder_request_id(request: Mapping[str, Any]) -> str:
    """Recompute the builder request id from lineage, scope and test contract."""
    lineage = request.get("lineage") if isinstance(request.get("lineage"), Mapping) else {}
    branch = request.get("branch_contract") if isinstance(request.get("branch_contract"), Mapping) else {}
    scope = request.get("scope") if isinstance(request.get("scope"), Mapping) else {}
    contract = request.get("test_contract") if isinstance(request.get("test_contract"), Mapping) else {}
    roles = request.get("roles") if isinstance(request.get("roles"), Mapping) else {}
    principals = {
        field: require_principal_id(roles.get(field), field)
        for field in AUTHORIZATION_PRINCIPAL_FIELDS
    }
    seed = {
        "principal_binding": PRINCIPAL_BINDING_VERSION,
        "snapshot_digest": str(lineage.get("snapshot_digest") or ""),
        "envelope_id": str(lineage.get("implementation_envelope_id") or ""),
        "authorization_id": str(lineage.get("implementation_authorization_id") or ""),
        "branch": str(branch.get("branch") or ""),
        "baseline": str(branch.get("baseline_ref") or ""),
        "candidate": str(branch.get("candidate_ref") or ""),
        "files": require_string_sequence(scope.get("requested_files"), "requested_files"),
        "authorized_files": require_string_sequence(scope.get("authorized_files"), "authorized_files"),
        "test_contract_manifest_id": test_contract_manifest_id(contract),
        "builder_principal_id": principals["builder_principal_id"],
        "reviewer_principal_id": principals["reviewer_principal_id"],
        "breaker_principal_id": principals["breaker_principal_id"],
        "approver_principal_id": principals["approver_principal_id"],
    }
    return "DEVBUILD-" + stable_digest(seed, length=18)


def assert_builder_request_lineage(request: Mapping[str, Any]) -> str:
    """Fail closed when the stored ids no longer match the test contract."""
    contract = request.get("test_contract") if isinstance(request.get("test_contract"), Mapping) else {}
    manifest = test_contract_manifest_id(contract)
    if str(request.get("test_contract_manifest_id") or "") != manifest:
        raise ValueError("test contract manifest mismatch")
    if str(request.get("request_id") or "") != expected_builder_request_id(request):
        raise ValueError("builder request lineage mismatch")
    return manifest


def bind_builder_request_lineage(request: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy whose manifest and request id match the current contract."""
    out = dict(request)
    contract = out.get("test_contract") if isinstance(out.get("test_contract"), Mapping) else {}
    out["test_contract_manifest_id"] = test_contract_manifest_id(contract)
    out["request_id"] = expected_builder_request_id(out)
    return out


def release_sensitive_path(path: Any) -> bool:
    value=clean(path,500).replace("\\","/").lower()
    parts=[part for part in value.split("/") if part]
    return (
        value.startswith(".github/workflows/")
        or value.startswith("docs/release/")
        or value.startswith("deploy/")
        or value.startswith("deployment/")
        or value.startswith("release/")
        or any(part in {"deploy","deployment","release"} for part in parts)
        or value in {"render.yaml","render.yml"}
        or "production" in value
        or "release" in value
    )


__all__=[
    "SCHEMA","SNAPSHOT_MANIFEST_VERSION","clean","stable_digest",
    "canonical_identity","normalize_ref","validate_isolated_branch",
    "validate_candidate_ref","snapshot_digest_from_rows",
    "validate_snapshot_integrity","correction_manifest_id",
    "implementation_base_manifest_id","implementation_readiness_manifest_id",
    "authorization_manifest_id","structural_request_roles","REQUIRED_MANDATORY_GATES",
    "require_string_sequence","assert_required_mandatory_gates",
    "test_contract_manifest_id","expected_builder_request_id",
    "assert_builder_request_lineage","bind_builder_request_lineage",
    "release_sensitive_path",
]
