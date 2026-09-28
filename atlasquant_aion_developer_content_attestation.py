"""Data-only content attestation for the AION Developer chain.

The attestation id is a digest of the binding payload. A caller-supplied id
is compared with that digest and never becomes the digest input. Structural
binding is not independent verification: no git object is read and no
external probe runs in this module.

content_binding_independently_verified stays false. A boolean
content_binding_verified flag is not evidence.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Mapping

from atlasquant_aion_developer_manifest import require_string_sequence, stable_digest
from atlasquant_aion_developer_principal_identity import (
    assert_attestor_independent,
    require_principal_id,
)

SCHEMA = "ATLASQUANT_AION_DEVELOPER_CONTENT_ATTESTATION_V2"
VERIFICATION_METHOD = "STRUCTURAL_MANIFEST_V1"
GIT_OBJECT_SOURCE_SYNTHETIC = "SYNTHETIC_FIXTURE"
GIT_OBJECT_SOURCE_PROBE = "EXTERNAL_PROBE"
_GIT_OBJECT_SOURCES = frozenset({
    GIT_OBJECT_SOURCE_SYNTHETIC,
    GIT_OBJECT_SOURCE_PROBE,
})

_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_BINDING_FIELDS = (
    "builder_request_id",
    "test_contract_manifest_id",
    "preflight_id",
    "patch_validation_id",
    "patch_digest",
    "baseline_ref",
    "candidate_ref",
    "baseline_commit_sha",
    "candidate_commit_sha",
    "baseline_tree_sha",
    "candidate_tree_sha",
    "verification_method",
    "verification_evidence_refs",
    "git_object_source",
    "attestor_principal_id",
)
_SHA_FIELDS = (
    "baseline_commit_sha",
    "candidate_commit_sha",
    "baseline_tree_sha",
    "candidate_tree_sha",
)
_CLAIM_FLAGS = (
    "content_binding_verified",
    "revision_content_verified",
    "content_binding_independently_verified",
    "execution_authorized",
    "executor_attached",
    "commands_executed",
    "writes_files",
    "runs_tests",
    "network_called",
    "subprocess_called",
    "automatic_commit",
    "automatic_merge",
    "automatic_deploy",
    "production_change_allowed",
    "real_trading_enabled",
    "executable_pinning_verified",
    "os_sandbox_verified",
)

# Synthetic placeholders for contract fixtures whose documents do not carry
# git object ids. They are accepted only as SYNTHETIC_FIXTURE claims. They
# are not observations of a repository and this module never reads git objects.
STRUCTURAL_BASELINE_COMMIT_SHA = "a" * 40
STRUCTURAL_CANDIDATE_COMMIT_SHA = "b" * 40
STRUCTURAL_BASELINE_TREE_SHA = "c" * 40
STRUCTURAL_CANDIDATE_TREE_SHA = "d" * 40
_PLACEHOLDER_SHAS = frozenset({
    STRUCTURAL_BASELINE_COMMIT_SHA,
    STRUCTURAL_CANDIDATE_COMMIT_SHA,
    STRUCTURAL_BASELINE_TREE_SHA,
    STRUCTURAL_CANDIDATE_TREE_SHA,
})
DEFAULT_ATTESTOR_PRINCIPAL_ID = "prn_attestor1"


def _strict_token(value: Any, field: str, limit: int = 240) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    if not value or value != value.strip() or len(value) > limit:
        raise ValueError(f"{field} is empty or malformed")
    if any(
        unicodedata.category(char) in {"Cc", "Cf"}
        or char.isspace()
        or unicodedata.category(char).startswith("Z")
        for char in value
    ):
        raise ValueError(f"{field} contains control, invisible, or whitespace characters")
    return value


def require_git_object_sha(value: Any, field: str) -> str:
    """Require a lowercase 40-character git object id.

    Uppercase hex, empty strings, short strings and 64-character file hashes
    are rejected. The value is not rewritten.
    """
    if not isinstance(value, str) or not _GIT_SHA_RE.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase 40-character git object sha")
    return value


def _reject_true_claims(payload: Mapping[str, Any]) -> None:
    for key in _CLAIM_FLAGS:
        if payload.get(key) is True:
            raise ValueError(f"{key} is not proof of content attestation")


def _validated_binding(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("content attestation must be an object")
    _reject_true_claims(payload)
    binding: dict[str, Any] = {
        "builder_request_id": _strict_token(payload.get("builder_request_id"), "builder_request_id"),
        "test_contract_manifest_id": _strict_token(
            payload.get("test_contract_manifest_id"),
            "test_contract_manifest_id",
        ),
        "preflight_id": _strict_token(payload.get("preflight_id"), "preflight_id"),
        "patch_validation_id": _strict_token(payload.get("patch_validation_id"), "patch_validation_id"),
        "patch_digest": _strict_token(payload.get("patch_digest"), "patch_digest"),
        "baseline_ref": _strict_token(payload.get("baseline_ref"), "baseline_ref"),
        "candidate_ref": _strict_token(payload.get("candidate_ref"), "candidate_ref"),
    }
    for field in _SHA_FIELDS:
        binding[field] = require_git_object_sha(payload.get(field), field)
    if binding["baseline_ref"] == binding["candidate_ref"]:
        raise ValueError("baseline and candidate refs must differ")
    if binding["baseline_commit_sha"] == binding["candidate_commit_sha"]:
        raise ValueError("baseline and candidate commit shas must differ")
    if binding["baseline_tree_sha"] == binding["candidate_tree_sha"]:
        raise ValueError("baseline and candidate tree shas must differ when a change is claimed")
    method = payload.get("verification_method")
    if method != VERIFICATION_METHOD:
        raise ValueError("verification method must be STRUCTURAL_MANIFEST_V1")
    evidence = require_string_sequence(
        payload.get("verification_evidence_refs"),
        "verification_evidence_refs",
    )
    if not evidence:
        raise ValueError("verification evidence refs are required")
    binding["verification_method"] = VERIFICATION_METHOD
    binding["verification_evidence_refs"] = evidence
    source = payload.get("git_object_source")
    if source not in _GIT_OBJECT_SOURCES:
        raise ValueError("git_object_source is missing or not allowlisted")
    placeholders = [field for field in _SHA_FIELDS if binding[field] in _PLACEHOLDER_SHAS]
    if source == GIT_OBJECT_SOURCE_PROBE:
        if placeholders:
            raise ValueError("synthetic placeholder sha cannot be claimed as an external probe")
        raise ValueError("EXTERNAL_PROBE has no implemented git object probe")
    if source != GIT_OBJECT_SOURCE_SYNTHETIC:
        raise ValueError("git_object_source is missing or not allowlisted")
    binding["git_object_source"] = GIT_OBJECT_SOURCE_SYNTHETIC
    binding["attestor_principal_id"] = require_principal_id(
        payload.get("attestor_principal_id"),
        "attestor_principal_id",
    )
    return binding


def content_attestation_id_for(binding: Mapping[str, Any]) -> str:
    """Digest only the binding fields. The caller id is not an input."""
    seed = {field: binding[field] for field in _BINDING_FIELDS}
    return stable_digest(seed, prefix="DEVATT-", length=18)


def build_content_attestation(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Seal a structural attestation. Independent verification stays false."""
    binding = _validated_binding(payload)
    attestation_id = content_attestation_id_for(binding)
    supplied = payload.get("content_attestation_id")
    if supplied is not None and supplied != attestation_id:
        raise ValueError("content attestation id mismatch")
    return {
        "schema": SCHEMA,
        "content_attestation_id": attestation_id,
        "state": "STRUCTURALLY_BOUND",
        **binding,
        "content_binding_structurally_bound": True,
        "content_binding_independently_verified": False,
        "execution_authorized": False,
        "executor_attached": False,
        "commands_executed": False,
        "writes_files": False,
        "runs_tests": False,
        "network_called": False,
        "subprocess_called": False,
        "automatic_commit": False,
        "automatic_merge": False,
        "automatic_deploy": False,
        "production_change_allowed": False,
        "real_trading_enabled": False,
    }


def assert_content_attestation_matches(
    attestation: Mapping[str, Any],
    builder_request: Mapping[str, Any],
    preflight: Mapping[str, Any],
    patch_validation: Mapping[str, Any],
) -> dict[str, Any]:
    """Recompute the attestation id and compare it to the sealed lineage.

    A stolen id, a mutated payload, or an attestation built for a different
    request, preflight, validation, digest or ref fails closed.
    """
    if not isinstance(attestation, Mapping):
        raise ValueError("content attestation must be an object")
    if attestation.get("schema") != SCHEMA:
        raise ValueError("invalid content attestation schema")
    if attestation.get("content_binding_structurally_bound") is not True:
        raise ValueError("content attestation is not structurally bound")
    if attestation.get("content_binding_independently_verified") is not False:
        raise ValueError("independent content verification cannot be claimed")
    binding = _validated_binding(attestation)
    expected = content_attestation_id_for(binding)
    if attestation.get("content_attestation_id") != expected:
        raise ValueError("content attestation id mismatch")
    if binding["builder_request_id"] != str(builder_request.get("request_id") or ""):
        raise ValueError("content attestation request mismatch")
    if binding["test_contract_manifest_id"] != str(builder_request.get("test_contract_manifest_id") or ""):
        raise ValueError("content attestation manifest mismatch")
    if binding["preflight_id"] != str(preflight.get("preflight_id") or ""):
        raise ValueError("content attestation preflight mismatch")
    if binding["patch_validation_id"] != str(patch_validation.get("validation_id") or ""):
        raise ValueError("content attestation validation mismatch")
    if binding["patch_digest"] != str(patch_validation.get("patch_digest") or ""):
        raise ValueError("content attestation patch digest mismatch")
    revision = (
        patch_validation.get("revision_binding")
        if isinstance(patch_validation.get("revision_binding"), Mapping)
        else {}
    )
    if binding["baseline_ref"] != str(revision.get("baseline_ref") or ""):
        raise ValueError("content attestation baseline ref mismatch")
    if binding["candidate_ref"] != str(revision.get("candidate_ref") or ""):
        raise ValueError("content attestation candidate ref mismatch")
    roles = (
        builder_request.get("roles")
        if isinstance(builder_request.get("roles"), Mapping)
        else {}
    )
    assert_attestor_independent(binding["attestor_principal_id"], roles)
    return binding


def attestation_for_documents(
    builder_request: Mapping[str, Any],
    preflight: Mapping[str, Any],
    patch_validation: Mapping[str, Any],
    **overrides: Any,
) -> dict[str, Any]:
    """Build a structural attestation from contract documents.

    Commit and tree SHAs default to synthetic placeholders because those
    documents do not carry git object ids. The result remains structurally
    bound only, with independent verification false.
    """
    revision = (
        patch_validation.get("revision_binding")
        if isinstance(patch_validation.get("revision_binding"), Mapping)
        else {}
    )
    payload: dict[str, Any] = {
        "builder_request_id": builder_request.get("request_id"),
        "test_contract_manifest_id": builder_request.get("test_contract_manifest_id"),
        "preflight_id": preflight.get("preflight_id"),
        "patch_validation_id": patch_validation.get("validation_id"),
        "patch_digest": patch_validation.get("patch_digest"),
        "baseline_ref": revision.get("baseline_ref"),
        "candidate_ref": revision.get("candidate_ref"),
        "baseline_commit_sha": STRUCTURAL_BASELINE_COMMIT_SHA,
        "candidate_commit_sha": STRUCTURAL_CANDIDATE_COMMIT_SHA,
        "baseline_tree_sha": STRUCTURAL_BASELINE_TREE_SHA,
        "candidate_tree_sha": STRUCTURAL_CANDIDATE_TREE_SHA,
        "verification_method": VERIFICATION_METHOD,
        "verification_evidence_refs": ["evidence:structural:1"],
        "git_object_source": GIT_OBJECT_SOURCE_SYNTHETIC,
        "attestor_principal_id": DEFAULT_ATTESTOR_PRINCIPAL_ID,
    }
    payload.update(overrides)
    return build_content_attestation(payload)


__all__ = [
    "SCHEMA",
    "VERIFICATION_METHOD",
    "GIT_OBJECT_SOURCE_SYNTHETIC",
    "GIT_OBJECT_SOURCE_PROBE",
    "STRUCTURAL_BASELINE_COMMIT_SHA",
    "STRUCTURAL_CANDIDATE_COMMIT_SHA",
    "STRUCTURAL_BASELINE_TREE_SHA",
    "STRUCTURAL_CANDIDATE_TREE_SHA",
    "DEFAULT_ATTESTOR_PRINCIPAL_ID",
    "require_git_object_sha",
    "content_attestation_id_for",
    "build_content_attestation",
    "assert_content_attestation_matches",
    "attestation_for_documents",
]
