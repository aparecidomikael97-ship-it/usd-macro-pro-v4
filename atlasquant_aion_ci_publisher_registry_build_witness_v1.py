"""AION publisher registry and independent build-witness CI contracts V1.

SYNTHETIC ONLY: Ed25519 signatures verify bytes against supplied ephemeral
public keys, NOT real publisher identity, build independence, provenance or
owner approval. No signing, OS access, files, network, install or deployment.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atlasquant_aion_windows_signed_release_provenance_ci_fixture_v1 import (
    SCHEMA as RELEASE_SCHEMA, RELEASE_READY, EVIDENCE_KEYS,
    VERIFICATION_KEYS, VERIFICATION_TRUTH_FLAGS, VERIFICATION_DENIAL_FLAGS,
)

SCHEMA = "ATLASQUANT_AION_CI_PUBLISHER_REGISTRY_BUILD_WITNESS_V1"
REGISTRY_SCHEMA = "ATLASQUANT_AION_CI_SIGNER_REGISTRY_SNAPSHOT_V1"
WITNESS_SCHEMA = "ATLASQUANT_AION_CI_BUILD_WITNESS_STATEMENT_V1"
REGISTRY_READY = "CI_SIGNED_REGISTRY_SNAPSHOT_SHAPE_READY_UNTRUSTED"
WITNESS_READY = "CI_SEPARATE_BUILD_WITNESS_SHAPE_READY_UNTRUSTED"
REVIEW_READY = "READY_FOR_PUBLISHER_GOVERNANCE_AND_BUILD_WITNESS_SECURITY_REVIEW"
BLOCKED = "BLOCKED"
SCOPE = "EPHEMERAL_CI_SYNTHETIC_TRUST_ONLY"
SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
KEY_ID = re.compile(r"ci-key-[a-z0-9][a-z0-9-]{2,60}\Z")
REG_ID = re.compile(r"ci-reg-[a-z0-9][a-z0-9-]{2,60}\Z")

ENTRY_FIELDS = (
    "key_id", "public_key_sha256", "status", "activated_sequence",
    "revoked_sequence", "rotation_parent_id",
)
REGISTRY_FIELDS = (
    "schema", "scope", "registry_id", "sequence", "previous_snapshot_digest",
    "publisher_policy_digest", "governance_key_sha256",
    "registry_challenge_digest", "entries",
    "governance_authority_trusted", "production_key_imported",
    "owner_install_authorization_present",
)
REGISTRY_PROOF_FIELDS = (
    "registry_digest", "registry_id", "sequence", "previous_snapshot_digest",
    "publisher_policy_digest", "governance_key_sha256",
    "registry_challenge_digest", "active_key_id", "active_key_sha256",
    "governance_signature_sha256",
)
WITNESS_FIELDS = (
    "schema", "scope", "witness_key_sha256", "registry_digest",
    "registry_sequence", "active_publisher_key_sha256",
    "release_candidate_digest", "release_manifest_sha256",
    "release_file_table_digest", "release_id", "source_commit",
    "build_run_id", "build_workflow_digest", "build_environment_digest",
    "release_challenge_digest", "witness_challenge_digest",
    "build_independence_trusted", "slsa_attestation_trusted",
    "production_release_authorized",
)
WITNESS_PROOF_FIELDS = (
    "witness_statement_digest", "witness_key_sha256", "witness_signature_sha256",
    "registry_digest", "registry_sequence", "active_publisher_key_sha256",
    "release_candidate_digest", "release_manifest_sha256",
    "release_file_table_digest", "release_id", "source_commit",
    "build_run_id", "build_workflow_digest", "build_environment_digest",
    "release_challenge_digest", "witness_challenge_digest",
)
REVIEW_DENIALS = (
    "real_publisher_key_approved", "real_governance_root_trusted",
    "real_build_witness_independent", "slsa_provenance_verified",
    "production_release_authorized", "hsm_or_hardware_key_attested",
    "replay_protection_authoritative", "owner_approved_install",
    "owner_device_accessed", "production_key_generated",
    "package_installed", "worker_activated", "deploy_executed",
)

def _canonical_bytes(o: Any) -> bytes:
    return json.dumps(o, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")

def _digest(o: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(o)).hexdigest()

def _bytes_digest(b: bytes) -> str:
    return "sha256:" + hashlib.sha256(b).hexdigest()

def _sha(v: Any) -> bool:
    return type(v) is str and SHA.fullmatch(v) is not None

def _map(v: Any) -> dict[str, Any]:
    return dict(v) if isinstance(v, Mapping) else {}

def _key_digest(k: Any) -> str:
    return _bytes_digest(k) if type(k) is bytes and len(k) == 32 else ""

def _sig_digest(s: Any) -> str:
    return _bytes_digest(s) if type(s) is bytes and len(s) == 64 else ""

def _check_signature(public_key: Any, signature: Any, message: Any) -> bool:
    if not _key_digest(public_key) or not _sig_digest(signature):
        return False
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature, _canonical_bytes(message)
        )
        return True
    except (InvalidSignature, ValueError):
        return False

def _errors_registry(m: dict[str, Any]) -> list[str]:
    errors = []
    if set(m) != set(REGISTRY_FIELDS):
        errors.append("REGISTRY_EXACT_FIELDS_REQUIRED")
    if m.get("schema") != REGISTRY_SCHEMA or m.get("scope") != SCOPE:
        errors.append("CI_REGISTRY_SCOPE_REQUIRED")
    if type(m.get("registry_id")) is not str or not REG_ID.fullmatch(m["registry_id"]):
        errors.append("CI_REGISTRY_ID_INVALID")
    if type(m.get("sequence")) is not int or m["sequence"] < 1:
        errors.append("MONOTONIC_SEQUENCE_REQUIRED")
    for k in ("previous_snapshot_digest", "publisher_policy_digest",
              "governance_key_sha256", "registry_challenge_digest"):
        if not _sha(m.get(k)):
            errors.append("REGISTRY_BINDING_REQUIRED:" + k)
    for k in ("governance_authority_trusted", "production_key_imported",
              "owner_install_authorization_present"):
        if m.get(k) is not False:
            errors.append("FALSE_TRUST_ASSERTION_FORBIDDEN:" + k)
    entries = m.get("entries")
    if type(entries) is not list or not 1 <= len(entries) <= 8:
        return errors + ["REGISTRY_ENTRIES_INVALID"]
    seq = m.get("sequence")
    ids, fingerprints, active = [], [], []
    for index, raw in enumerate(entries):
        v = _map(raw)
        if set(v) != set(ENTRY_FIELDS):
            errors.append("EXACT_REGISTRY_ENTRY_FIELDS_REQUIRED:" + str(index))
        key_id, fp = v.get("key_id"), v.get("public_key_sha256")
        if type(key_id) is not str or not KEY_ID.fullmatch(key_id):
            errors.append("REGISTRY_KEY_ID_INVALID:" + str(index))
        else:
            ids.append(key_id)
        if not _sha(fp):
            errors.append("REGISTRY_KEY_FINGERPRINT_INVALID:" + str(index))
        else:
            fingerprints.append(fp)
        start = v.get("activated_sequence")
        revoke = v.get("revoked_sequence")
        if type(start) is not int or start < 1 or type(seq) is not int or start > seq:
            errors.append("REGISTRY_KEY_ACTIVATION_INVALID:" + str(index))
        if type(revoke) is not int or revoke < 0 or type(seq) is not int or revoke > seq:
            errors.append("REGISTRY_KEY_REVOCATION_INVALID:" + str(index))
        status = v.get("status")
        if status == "ACTIVE":
            active.append(v)
            if revoke != 0:
                errors.append("REVOKED_KEY_CANNOT_BE_ACTIVE")
        elif status == "REVOKED":
            if type(start) is not int or type(revoke) is not int or revoke < max(1, start):
                errors.append("REVOKED_KEY_REQUIRES_VALID_CUTOFF")
        elif status == "RETIRED":
            if revoke != 0:
                errors.append("RETIRED_KEY_MUST_NOT_HAVE_REVOCATION")
        else:
            errors.append("REGISTRY_KEY_STATUS_INVALID:" + str(index))
        parent = v.get("rotation_parent_id")
        if parent != "" and (type(parent) is not str or not KEY_ID.fullmatch(parent)
                             or parent == key_id):
            errors.append("ROTATION_PARENT_INVALID:" + str(index))
    if ids != sorted(ids) or len(ids) != len(set(ids)):
        errors.append("REGISTRY_KEY_IDS_ORDER_OR_DUPLICATION")
    if len(fingerprints) != len(set(fingerprints)):
        errors.append("REGISTRY_DUPLICATE_KEY_MATERIAL")
    if len(active) != 1:
        errors.append("EXACTLY_ONE_ACTIVE_SIGNER_REQUIRED")
    for v in entries:
        if not isinstance(v, Mapping):
            continue
        parent = v.get("rotation_parent_id")
        if parent and (parent not in ids or
                       next((r.get("status") for r in entries
                             if isinstance(r, Mapping) and r.get("key_id") == parent), "") == "ACTIVE"):
            errors.append("ROTATION_PARENT_MUST_BE_PRESENT_NONACTIVE")
        if v.get("status") == "ACTIVE" and len(entries) > 1 and not parent:
            errors.append("ACTIVE_ROTATION_PARENT_REQUIRED")
    return list(dict.fromkeys(errors))

def verify_ci_publisher_registry(
    snapshot: Mapping[str, Any] | None,
    governance_public_key: Any,
    governance_signature: Any,
    *,
    expected_registry_id: Any,
    expected_sequence: Any,
    expected_previous_snapshot_digest: Any,
    expected_policy_digest: Any,
    expected_challenge_digest: Any,
    expected_governance_key_sha256: Any,
) -> dict[str, Any]:
    m = _map(snapshot)
    errors = _errors_registry(m)
    expectations = {
        "registry_id": expected_registry_id,
        "sequence": expected_sequence,
        "previous_snapshot_digest": expected_previous_snapshot_digest,
        "publisher_policy_digest": expected_policy_digest,
        "registry_challenge_digest": expected_challenge_digest,
        "governance_key_sha256": expected_governance_key_sha256,
    }
    for name, value in expectations.items():
        if m.get(name) != value:
            errors.append("EXTERNAL_REGISTRY_EXPECTATION_MISMATCH:" + name)
    if type(expected_sequence) is not int or expected_sequence < 1:
        errors.append("EXPECTED_SEQUENCE_INVALID")
    for name in ("previous_snapshot_digest", "publisher_policy_digest",
                 "registry_challenge_digest", "governance_key_sha256"):
        if not _sha(expectations[name]):
            errors.append("EXPECTED_REGISTRY_DIGEST_INVALID:" + name)
    if _key_digest(governance_public_key) != m.get("governance_key_sha256"):
        errors.append("GOVERNANCE_PUBLIC_KEY_MISMATCH")
    if not _check_signature(governance_public_key, governance_signature, m):
        errors.append("REGISTRY_GOVERNANCE_SIGNATURE_INVALID")
    active = [row for row in m.get("entries", []) if isinstance(row, Mapping) and row.get("status") == "ACTIVE"] if isinstance(m.get("entries"), list) else []
    active_key = active[0] if len(active) == 1 else {}
    material = {
        "registry_digest": _digest(m),
        "registry_id": m.get("registry_id"),
        "sequence": m.get("sequence"),
        "previous_snapshot_digest": m.get("previous_snapshot_digest"),
        "publisher_policy_digest": m.get("publisher_policy_digest"),
        "governance_key_sha256": m.get("governance_key_sha256"),
        "registry_challenge_digest": m.get("registry_challenge_digest"),
        "active_key_id": active_key.get("key_id"),
        "active_key_sha256": active_key.get("public_key_sha256"),
        "governance_signature_sha256": _sig_digest(governance_signature),
    }
    errors = list(dict.fromkeys(errors))
    return {
        "schema": SCHEMA, "state": REGISTRY_READY if not errors else BLOCKED,
        "blockers": errors, **material,
        "registry_proof_candidate_digest": _digest(material) if not errors else "",
        "ci_signature_verified_against_supplied_root": not errors,
        "publisher_registry_root_trusted": False,
        "registry_antirollback_authoritatively_persisted": False,
        "real_publisher_key_approved": False,
        "revocation_checked_against_real_authority": False,
        "owner_install_authorization_consumed": False,
        "worker_activated": False, "deploy_executed": False,
    }

def verify_ci_separate_build_witness(
    statement: Mapping[str, Any] | None,
    witness_public_key: Any,
    witness_signature: Any,
    release_candidate: Mapping[str, Any] | None,
    registry_proof: Mapping[str, Any] | None,
    *,
    expected_witness_key_sha256: Any,
    expected_build_workflow_digest: Any,
    expected_build_environment_digest: Any,
    expected_witness_challenge_digest: Any,
) -> dict[str, Any]:
    s, r, g = _map(statement), _map(release_candidate), _map(registry_proof)
    errors = []
    if set(s) != set(WITNESS_FIELDS):
        errors.append("EXACT_WITNESS_FIELDS_REQUIRED")
    if s.get("schema") != WITNESS_SCHEMA or s.get("scope") != SCOPE:
        errors.append("CI_WITNESS_SCOPE_REQUIRED")
    if g.get("schema") != SCHEMA or g.get("state") != REGISTRY_READY:
        errors.append("REGISTRY_PROOF_REQUIRED")
    if g.get("registry_proof_candidate_digest") != _digest({
        name: g.get(name) for name in REGISTRY_PROOF_FIELDS
    }):
        errors.append("REGISTRY_PROOF_DIGEST_INVALID")
    if r.get("schema") != RELEASE_SCHEMA or r.get("state") != RELEASE_READY or r.get("blockers") != []:
        errors.append("CI_RELEASE_CANDIDATE_REQUIRED")
    if set(r) != VERIFICATION_KEYS or r.get("candidate_evidence_digest") != _digest({
        k: r.get(k) for k in EVIDENCE_KEYS
    }):
        errors.append("CI_RELEASE_CANDIDATE_DIGEST_INVALID")
    for name in VERIFICATION_TRUTH_FLAGS:
        if r.get(name) is not True:
            errors.append("CI_RELEASE_SHAPE_PROOF_REQUIRED:" + name)
    for name in VERIFICATION_DENIAL_FLAGS:
        if r.get(name) is not False:
            errors.append("CI_RELEASE_FALSE_TRUST_REQUIRED:" + name)
    expected = {
        "registry_digest": g.get("registry_digest"),
        "registry_sequence": g.get("sequence"),
        "active_publisher_key_sha256": g.get("active_key_sha256"),
        "release_candidate_digest": r.get("candidate_evidence_digest"),
        "release_manifest_sha256": r.get("manifest_sha256"),
        "release_file_table_digest": r.get("file_table_digest"),
        "release_id": r.get("release_id"),
        "source_commit": r.get("source_commit"),
        "build_run_id": r.get("build_run_id"),
        "release_challenge_digest": r.get("release_challenge_digest"),
        "build_workflow_digest": expected_build_workflow_digest,
        "build_environment_digest": expected_build_environment_digest,
        "witness_challenge_digest": expected_witness_challenge_digest,
        "witness_key_sha256": expected_witness_key_sha256,
    }
    for name, value in expected.items():
        if s.get(name) != value:
            errors.append("WITNESS_RELEASE_OR_REGISTRY_BINDING_MISMATCH:" + name)
    for name in ("witness_key_sha256", "build_workflow_digest",
                 "build_environment_digest", "witness_challenge_digest"):
        if not _sha(expected[name]):
            errors.append("EXPECTED_WITNESS_DIGEST_INVALID:" + name)
    for name in ("build_independence_trusted", "slsa_attestation_trusted",
                 "production_release_authorized"):
        if s.get(name) is not False:
            errors.append("WITNESS_TRUST_ESCALATION_FORBIDDEN:" + name)
    if _key_digest(witness_public_key) != s.get("witness_key_sha256"):
        errors.append("WITNESS_KEY_FINGERPRINT_MISMATCH")
    if (s.get("witness_key_sha256") in (
        g.get("governance_key_sha256"), g.get("active_key_sha256")
    ) or g.get("governance_key_sha256") == g.get("active_key_sha256")):
        errors.append("PUBLISHER_ROOT_AND_WITNESS_KEY_ROLES_MUST_DIFFER")
    if (r.get("public_key_sha256") != g.get("active_key_sha256") or
        s.get("active_publisher_key_sha256") != r.get("public_key_sha256")):
        errors.append("ACTIVE_PUBLISHER_KEY_MUST_MATCH_RELEASE_SIGNER")
    if not _check_signature(witness_public_key, witness_signature, s):
        errors.append("DETACHED_WITNESS_SIGNATURE_INVALID")
    material = {
        "witness_statement_digest": _digest(s),
        "witness_key_sha256": s.get("witness_key_sha256"),
        "witness_signature_sha256": _sig_digest(witness_signature),
        "registry_digest": s.get("registry_digest"),
        "registry_sequence": s.get("registry_sequence"),
        "active_publisher_key_sha256": s.get("active_publisher_key_sha256"),
        "release_candidate_digest": s.get("release_candidate_digest"),
        "release_manifest_sha256": s.get("release_manifest_sha256"),
        "release_file_table_digest": s.get("release_file_table_digest"),
        "release_id": s.get("release_id"),
        "source_commit": s.get("source_commit"),
        "build_run_id": s.get("build_run_id"),
        "build_workflow_digest": s.get("build_workflow_digest"),
        "build_environment_digest": s.get("build_environment_digest"),
        "release_challenge_digest": s.get("release_challenge_digest"),
        "witness_challenge_digest": s.get("witness_challenge_digest"),
    }
    errors = list(dict.fromkeys(errors))
    return {
        "schema": SCHEMA, "state": WITNESS_READY if not errors else BLOCKED,
        "blockers": errors, **material,
        "witness_proof_candidate_digest": _digest(material) if not errors else "",
        "witness_signed_by_supplied_separate_ci_key": not errors,
        "external_build_witness_identity_trusted": False,
        "witness_identity_verified_independent": False,
        "real_slsa_attestation_verified": False,
        "real_release_authorized": False,
        "replay_protection_authoritative": False,
        "owner_device_accessed": False,
        "worker_activated": False, "deploy_executed": False,
    }

def build_ci_publisher_and_build_review(
    registry_proof: Mapping[str, Any] | None,
    witness_proof: Mapping[str, Any] | None,
    release_candidate: Mapping[str, Any] | None,
    *,
    external_approval_policy_digest: Any,
    external_provenance_policy_digest: Any,
    expected_registry_sequence: Any,
) -> dict[str, Any]:
    g, w, r = map(_map, (registry_proof, witness_proof, release_candidate))
    errors = []
    if g.get("schema") != SCHEMA or g.get("state") != REGISTRY_READY or g.get("blockers") != []:
        errors.append("REGISTRY_PROOF_SHAPE_REQUIRED")
    if w.get("schema") != SCHEMA or w.get("state") != WITNESS_READY or w.get("blockers") != []:
        errors.append("WITNESS_PROOF_SHAPE_REQUIRED")
    if g.get("registry_proof_candidate_digest") != _digest({
        name: g.get(name) for name in REGISTRY_PROOF_FIELDS
    }):
        errors.append("REGISTRY_PROOF_REHASH_FAILED")
    if w.get("witness_proof_candidate_digest") != _digest({
        name: w.get(name) for name in WITNESS_PROOF_FIELDS
    }):
        errors.append("WITNESS_PROOF_REHASH_FAILED")
    if (w.get("registry_digest") != g.get("registry_digest")
        or w.get("registry_sequence") != g.get("sequence")
        or w.get("active_publisher_key_sha256") != g.get("active_key_sha256")
        or w.get("release_candidate_digest") != r.get("candidate_evidence_digest")
        or w.get("release_manifest_sha256") != r.get("manifest_sha256")
        or w.get("release_file_table_digest") != r.get("file_table_digest")
        or w.get("release_id") != r.get("release_id")
        or w.get("source_commit") != r.get("source_commit")
        or w.get("build_run_id") != r.get("build_run_id")):
        errors.append("CROSS_PROOF_BINDING_INVALID")
    if type(expected_registry_sequence) is not int or g.get("sequence") != expected_registry_sequence:
        errors.append("EXTERNAL_REGISTRY_SEQUENCE_MISMATCH")
    for name, val in (("external_approval_policy_digest", external_approval_policy_digest),
                      ("external_provenance_policy_digest", external_provenance_policy_digest)):
        if not _sha(val):
            errors.append("EXTERNAL_POLICY_REQUIRED:" + name)
    for proof in (g, w):
        for name, val in proof.items():
            if name.endswith(("_trusted", "_authorized", "_approved", "_attested")) and val is True:
                errors.append("PROOF_SELF_TRUST_PROMOTION_FORBIDDEN:" + name)
    errors = list(dict.fromkeys(errors))
    material = {
        "registry_proof_candidate_digest": g.get("registry_proof_candidate_digest"),
        "witness_proof_candidate_digest": w.get("witness_proof_candidate_digest"),
        "release_candidate_digest": r.get("candidate_evidence_digest"),
        "expected_registry_sequence": expected_registry_sequence,
        "external_approval_policy_digest": external_approval_policy_digest,
        "external_provenance_policy_digest": external_provenance_policy_digest,
    }
    return {
        "schema": SCHEMA, "state": REVIEW_READY if not errors else BLOCKED,
        "blockers": errors, **material,
        "review_candidate_digest": _digest(material) if not errors else "",
        **{name: False for name in REVIEW_DENIALS},
    }

def publisher_build_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA, "ci_only": True, "two_distinct_ci_signers": True,
        "governance_source_trusted": False,
        "ci_self_signed_registry_grants_real_trust": False,
        "self_supplied_build_witness_is_independent_provenance": False,
        "external_policy_digest_means_policy_approved": False,
        "registry_sequence_is_durably_anchored": False,
        "ci_pubkey_promoted_to_production": False,
        "release_ready_for_install": False,
        "owner_authorization_consumed": False,
        "owner_device_accessed": False,
        "production_signed_release_created": False,
        "aion_installed": False, "deploy_executed": False,
        "worker_activated": False,
    }
