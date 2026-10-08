"""AION signed-release provenance V1: CI EPHEMERAL fixture ONLY.

Cryptographic Ed25519 verification of detached *synthetic release fixtures*
does not prove who owns the signing key, who built the binaries, or whether a
real AION package is legitimate. This module never signs, launches, writes,
installs, downloads, elevates, deploys, or accesses Windows APIs.

All trust / deployment / owner authorization remains false without exception.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "ATLASQUANT_AION_SIGNED_RELEASE_PROVENANCE_CI_FIXTURE_V1"
HANDOFF_SCHEMA = "ATLASQUANT_AION_SIGNED_RELEASE_HANDOFF_PLAN_V1"
RELEASE_READY = "CI_DETACHED_SIGNATURE_AND_MANIFEST_MATCH_UNTRUSTED"
HANDOFF_READY = "RELEASE_PROVENANCE_HANDOFF_SHAPE_READY_UNTRUSTED"
BLOCKED = "BLOCKED"
SCOPE = "CI_EPHEMERAL_SYNTHETIC_ARTIFACTS_ONLY"
KEY_SOURCE = "GENERATED_EPHEMERAL_CI_KEY_UNTRUSTED"
SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
NAME = re.compile(r"[a-z0-9][a-z0-9._/-]{0,119}\Z")
VERSION = re.compile(r"0\.[0-9]{1,5}\.[0-9]{1,5}-ci\.[0-9]{1,8}\Z")
RUN = re.compile(r"[1-9][0-9]{0,19}\Z")
ID = re.compile(r"ci-aion-[a-z0-9][a-z0-9-]{2,83}\Z")
WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul", "com1", "com2", "com3", "com4",
    "com5", "com6", "com7", "com8", "com9", "lpt1", "lpt2", "lpt3",
    "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
}
MAX_FILES = 32
MAX_FILE_BYTES = 4 * 1024 * 1024
MANIFEST_KEYS = (
    "schema", "scope", "release_id", "version",
    "source_commit", "build_workflow_digest", "build_run_id",
    "build_environment_digest", "ci_signer_public_key_sha256",
    "publisher_policy_digest", "release_challenge_digest", "files",
    "key_source", "publisher_identity_authorized",
    "build_provenance_independently_attested",
    "owner_install_authorization_present",
)
FILE_KEYS = ("path", "size_bytes", "sha256")
EXPECTED_KEYS = (
    "release_id", "version", "source_commit",
    "build_workflow_digest", "build_run_id",
    "build_environment_digest", "publisher_policy_digest",
    "release_challenge_digest", "ci_signer_public_key_sha256",
    "file_table_digest",
)
EVIDENCE_KEYS = (
    "manifest_sha256", "file_table_digest", "public_key_sha256",
    "signature_sha256", "release_id", "source_commit",
    "build_run_id", "release_challenge_digest",
)
VERIFICATION_TRUTH_FLAGS = (
    "signature_verified_with_supplied_ci_key",
    "artifact_bytes_match_manifest_ci_only", "ci_key_ephemeral_untrusted",
)
VERIFICATION_DENIAL_FLAGS = (
    "signed_by_authorized_aion_publisher", "trusted_source_commit_attested",
    "slsa_build_provenance_trusted", "reproducible_build_verified",
    "certificate_chain_and_revocation_trusted", "aion_release_approved",
    "owner_authorization_consumed", "install_token_consumed",
    "aion_package_installed", "worker_activated", "deploy_executed",
)
VERIFICATION_KEYS = set(EVIDENCE_KEYS) | {
    "schema", "state", "blockers", "candidate_evidence_digest",
} | set(VERIFICATION_TRUTH_FLAGS) | set(VERIFICATION_DENIAL_FLAGS)

def _canonical_bytes(data: Any) -> bytes:
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")

def _digest(data: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(data)).hexdigest()

def _bytes_digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()

def _sha(data: Any) -> bool:
    return type(data) is str and SHA.fullmatch(data) is not None

def _mapping(data: Any) -> dict[str, Any]:
    return dict(data) if isinstance(data, Mapping) else {}

def _safe_windows_relative_path(path: Any) -> bool:
    if type(path) is not str or not NAME.fullmatch(path):
        return False
    if path.startswith("/") or path.endswith("/") or "//" in path:
        return False
    for segment in path.split("/"):
        if segment in (".", "..") or segment.endswith(".") or segment.endswith(" "):
            return False
        if segment.split(".")[0] in WINDOWS_RESERVED:
            return False
    return True

def _file_table_errors(files: Any) -> list[str]:
    errors = []
    if type(files) is not list or not 1 <= len(files) <= MAX_FILES:
        return ["ARTIFACT_TABLE_COUNT_INVALID"]
    paths = []
    for index, raw in enumerate(files):
        row = _mapping(raw)
        if set(row) != set(FILE_KEYS):
            errors.append(f"EXACT_FILE_FIELDS_REQUIRED:{index}")
        path = row.get("path")
        if not _safe_windows_relative_path(path):
            errors.append(f"WINDOWS_ARTIFACT_PATH_UNSAFE:{index}")
        else:
            paths.append(path)
        if type(row.get("size_bytes")) is not int or not 1 <= row["size_bytes"] <= MAX_FILE_BYTES:
            errors.append(f"ARTIFACT_SIZE_INVALID:{index}")
        if not _sha(row.get("sha256")):
            errors.append(f"ARTIFACT_DIGEST_INVALID:{index}")
    if paths != sorted(paths) or len(paths) != len(set(p.casefold() for p in paths)):
        errors.append("ARTIFACT_ORDER_OR_CASE_COLLISION")
    return errors

def _manifest_errors(m: dict[str, Any]) -> list[str]:
    errors = []
    if set(m) != set(MANIFEST_KEYS):
        errors.append("EXACT_MANIFEST_FIELDS_REQUIRED")
    if m.get("schema") != SCHEMA or m.get("scope") != SCOPE:
        errors.append("CI_FIXTURE_SCOPE_REQUIRED")
    if m.get("key_source") != KEY_SOURCE:
        errors.append("EPHEMERAL_TEST_SIGNER_ONLY")
    if not isinstance(m.get("release_id"), str) or not ID.fullmatch(m["release_id"]):
        errors.append("CI_RELEASE_ID_INVALID")
    if not isinstance(m.get("version"), str) or not VERSION.fullmatch(m["version"]):
        errors.append("CI_RELEASE_VERSION_INVALID")
    if not isinstance(m.get("source_commit"), str) or not COMMIT.fullmatch(m["source_commit"]):
        errors.append("SOURCE_COMMIT_INVALID")
    if not isinstance(m.get("build_run_id"), str) or not RUN.fullmatch(m["build_run_id"]):
        errors.append("BUILD_RUN_ID_INVALID")
    for key in (
        "build_workflow_digest", "build_environment_digest",
        "ci_signer_public_key_sha256", "publisher_policy_digest",
        "release_challenge_digest",
    ):
        if not _sha(m.get(key)):
            errors.append("REQUIRED_MANIFEST_DIGEST_INVALID:" + key)
    for key in ("publisher_identity_authorized",
                "build_provenance_independently_attested",
                "owner_install_authorization_present"):
        if m.get(key) is not False:
            errors.append("FORBIDDEN_CI_TRUST_PROMOTION:" + key)
    errors.extend(_file_table_errors(m.get("files")))
    return list(dict.fromkeys(errors))

def verify_ci_detached_release(
    manifest: Mapping[str, Any] | None,
    artifacts: Mapping[str, bytes] | None,
    public_key_bytes: Any,
    detached_signature: Any,
    *,
    expected: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Actual signature verification with a UNTRUSTED self-supplied CI key.

    This is cryptographic verification relative to supplied bytes; it cannot
    authenticate their external source, intended publisher or release approval.
    """
    m = _mapping(manifest)
    e = _mapping(expected)
    errors = _manifest_errors(m)
    if set(e) != set(EXPECTED_KEYS):
        errors.append("EXACT_EXTERNAL_EXPECTATIONS_REQUIRED")
    if e.get("release_id") != m.get("release_id") or e.get("version") != m.get("version"):
        errors.append("RELEASE_ID_VERSION_BINDING_MISMATCH")
    for name in EXPECTED_KEYS:
        if e.get(name) != (
            _digest(m.get("files")) if name == "file_table_digest" else m.get(name)
        ):
            errors.append("RELEASE_EXPECTED_BINDING_MISMATCH:" + name)
    if type(public_key_bytes) is not bytes or len(public_key_bytes) != 32:
        errors.append("ED25519_PUBLIC_KEY_LENGTH_INVALID")
    if type(detached_signature) is not bytes or len(detached_signature) != 64:
        errors.append("ED25519_SIGNATURE_LENGTH_INVALID")
    if type(public_key_bytes) is bytes and len(public_key_bytes) == 32:
        if _bytes_digest(public_key_bytes) != m.get("ci_signer_public_key_sha256"):
            errors.append("PUBLIC_KEY_DIGEST_MISMATCH")
    if type(artifacts) is not dict:
        errors.append("EXACT_CI_ARTIFACT_BYTE_MAPPING_REQUIRED")
        actual_artifacts: dict[str, Any] = {}
    else:
        actual_artifacts = artifacts
    declared = _mapping({row.get("path"): row for row in m.get("files", [])
                         if isinstance(row, Mapping) and isinstance(row.get("path"), str)})
    if set(actual_artifacts) != set(declared):
        errors.append("MISSING_OR_UNDECLARED_ARTIFACT")
    for path, raw in actual_artifacts.items():
        if not _safe_windows_relative_path(path):
            errors.append("UNSAFE_ARTIFACT_MAP_PATH")
        if type(raw) is not bytes or not 1 <= len(raw) <= MAX_FILE_BYTES:
            errors.append("ARTIFACT_BYTES_INVALID:" + str(path))
        else:
            record = declared.get(path, {})
            if (record.get("size_bytes") != len(raw) or
                record.get("sha256") != _bytes_digest(raw)):
                errors.append("ARTIFACT_READBACK_DIGEST_MISMATCH:" + str(path))
    verified_signature = False
    if (not errors and type(public_key_bytes) is bytes and
        type(detached_signature) is bytes):
        try:
            Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(
                detached_signature, _canonical_bytes(m)
            )
            verified_signature = True
        except (InvalidSignature, ValueError):
            errors.append("DETACHED_SIGNATURE_INVALID")
    errors = list(dict.fromkeys(errors))
    material = {
        "manifest_sha256": _bytes_digest(_canonical_bytes(m)),
        "file_table_digest": _digest(m.get("files")),
        "public_key_sha256": _bytes_digest(public_key_bytes)
            if type(public_key_bytes) is bytes else "",
        "signature_sha256": _bytes_digest(detached_signature)
            if type(detached_signature) is bytes else "",
        "release_id": m.get("release_id"),
        "source_commit": m.get("source_commit"),
        "build_run_id": m.get("build_run_id"),
        "release_challenge_digest": m.get("release_challenge_digest"),
    }
    return {
        "schema": SCHEMA,
        "state": RELEASE_READY if not errors else BLOCKED,
        "blockers": errors,
        **material,
        "candidate_evidence_digest": _digest(material) if not errors else "",
        "signature_verified_with_supplied_ci_key": verified_signature,
        "artifact_bytes_match_manifest_ci_only": not errors,
        "ci_key_ephemeral_untrusted": True,
        "signed_by_authorized_aion_publisher": False,
        "trusted_source_commit_attested": False,
        "slsa_build_provenance_trusted": False,
        "reproducible_build_verified": False,
        "certificate_chain_and_revocation_trusted": False,
        "aion_release_approved": False,
        "owner_authorization_consumed": False,
        "install_token_consumed": False,
        "aion_package_installed": False,
        "worker_activated": False,
        "deploy_executed": False,
    }

def build_ci_release_handoff_plan(
    verification: Mapping[str, Any] | None,
    *,
    expected_installation_binding_digest: Any,
    approved_publisher_registry_digest: Any,
    independent_build_attestor_manifest_digest: Any,
    package_ingest_policy_digest: Any,
    owner_review_policy_digest: Any,
) -> dict[str, Any]:
    """Shape-only consumer handoff; does NOT assert registry or attestations."""
    v = _mapping(verification)
    errors = []
    if set(v) != VERIFICATION_KEYS:
        errors.append("EXACT_CI_CRYPTO_EVIDENCE_KEYS_REQUIRED")
    if v.get("schema") != SCHEMA or v.get("state") != RELEASE_READY or v.get("blockers") != []:
        errors.append("READY_CI_CRYPTO_CANDIDATE_REQUIRED")
    for flag in VERIFICATION_TRUTH_FLAGS:
        if v.get(flag) is not True:
            errors.append("MISSING_CI_CRYPTO_SHAPE:" + flag)
    for flag in VERIFICATION_DENIAL_FLAGS:
        if v.get(flag) is not False:
            errors.append("TRUST_ESCALATION_REFUSED:" + flag)
    if v.get("candidate_evidence_digest") != _digest({
        k: v.get(k) for k in EVIDENCE_KEYS
    }):
        errors.append("CI_CRYPTO_CANDIDATE_TAMPERED")
    if v.get("signature_verified_with_supplied_ci_key") is not True:
        errors.append("CI_SIGNATURE_PROOF_REQUIRED")
    external = {
        "expected_installation_binding_digest": expected_installation_binding_digest,
        "approved_publisher_registry_digest": approved_publisher_registry_digest,
        "independent_build_attestor_manifest_digest": independent_build_attestor_manifest_digest,
        "package_ingest_policy_digest": package_ingest_policy_digest,
        "owner_review_policy_digest": owner_review_policy_digest,
    }
    for key, val in external.items():
        if not _sha(val):
            errors.append("HANDOFF_DIGEST_INVALID:" + key)
    material = {
        "ci_release_candidate_digest": v.get("candidate_evidence_digest"),
        **external,
        "next_pc_phase": "INDEPENDENT_SIGNER_AND_BUILD_PROVENANCE_APPROVAL_REQUIRED",
    }
    errors = list(dict.fromkeys(errors))
    return {
        "schema": HANDOFF_SCHEMA,
        "state": HANDOFF_READY if not errors else BLOCKED,
        "blockers": errors,
        **material,
        "handoff_plan_digest": _digest(material) if not errors else "",
        "aion_authorized_publisher_proven": False,
        "release_bytes_trusted": False,
        "independent_build_attestation_verified": False,
        "release_approved_for_owner": False,
        "installation_authorized": False,
        "files_written": False,
        "owner_device_accessed": False,
        "deploy_executed": False,
        "worker_activated": False,
    }

def provenance_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "fixture_only": True,
        "ephemeral_ci_private_keys_only": True,
        "ci_key_proves_authorized_publisher": False,
        "matching_source_commit_proves_build_integrity": False,
        "signature_without_key_registry_is_trusted": False,
        "signature_matching_aion_release_is_known": False,
        "manifest_without_artifact_bytes_is_sufficient": False,
        "extra_artifacts_allowed": False,
        "unsafe_windows_paths_allowed": False,
        "self_attested_builder_allowed": False,
        "automatic_install_on_crypto_success": False,
        "owner_device_accessed": False,
        "owner_authorization_consumed": False,
        "install_token_consumed": False,
        "production_signing_key_generated": False,
        "production_signed_release_created": False,
        "package_installed": False,
        "deploy_executed": False,
        "worker_activated": False,
    }
