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
    normalized=unicodedata.normalize("NFKC",clean(value,160))
    return " ".join(normalized.split()).casefold()


def normalize_ref(value: Any, limit: int = 240) -> str:
    return unicodedata.normalize("NFKC",clean(value,limit))


def validate_isolated_branch(value: Any) -> str:
    branch=normalize_ref(value,240)
    if branch.startswith("refs/heads/"):
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
    if parts[0].casefold() in _RESERVED_BRANCH_ROOTS:
        raise ValueError("production/main branch family is forbidden")
    return branch


def validate_candidate_ref(value: Any, branch: Any) -> str:
    candidate=normalize_ref(value,240)
    logical_branch=validate_isolated_branch(branch)
    if not candidate:
        raise ValueError("candidate_ref required")
    candidate_branch=candidate.split("@",1)[0]
    if candidate_branch.startswith("refs/heads/"):
        candidate_branch=candidate_branch[len("refs/heads/"):]
    if candidate_branch != logical_branch:
        raise ValueError("candidate_ref must be bound to the exact isolated branch")
    return candidate


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
    rollback=envelope.get("rollback_contract") if isinstance(envelope.get("rollback_contract"),Mapping) else {}
    return stable_digest({
        "base_manifest_id":implementation_base_manifest_id(envelope),
        "readiness":envelope.get("readiness"),
        "rollback":{
            "recorded_for_this_change":rollback.get("recorded_for_this_change"),
            "change_specific_plan":rollback.get("change_specific_plan"),
        },
    },prefix="DEVREADYMAN-",length=20)


def authorization_manifest_id(envelope: Mapping[str,Any], authorization: Mapping[str,Any]) -> str:
    return stable_digest({
        "readiness_manifest_id":implementation_readiness_manifest_id(envelope),
        "trust_level":authorization.get("trust_level"),
        "approver_actor":authorization.get("approver_actor"),
        "approval_refs":list(authorization.get("approval_refs") or []),
        "human_approved":authorization.get("human_approved"),
        "scope_expansion_allowed":authorization.get("scope_expansion_allowed"),
        "merge_main_allowed":authorization.get("merge_main_allowed"),
        "deploy_allowed":authorization.get("deploy_allowed"),
        "production_allowed":authorization.get("production_allowed"),
        "real_trading_allowed":authorization.get("real_trading_allowed"),
        "builder_identity_key":authorization.get("builder_identity_key"),
        "reviewer_identity_key":authorization.get("reviewer_identity_key"),
        "breaker_identity_key":authorization.get("breaker_identity_key"),
        "rollback_recorded":authorization.get("rollback_recorded"),
    },prefix="DEVAUTH-",length=18)


def release_sensitive_path(path: Any) -> bool:
    value=clean(path,500).replace("\\","/").lower()
    return (
        value.startswith(".github/workflows/")
        or value.startswith("docs/release/")
        or value.startswith("deploy/")
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
    "authorization_manifest_id","release_sensitive_path",
]
