"""AION CI custody rotation and external-provenance acceptance preflight V1.

Verification-only, synthetic fixture design. Cryptographic signatures prove
possession of supplied CI test keys, never real publisher authority, HUMAN_OWNER
custody, durable anti-rollback, GitHub OIDC issuer, or SLSA provenance.
No private-key generation, file, network, OS, installer or Worker operations.
"""
from __future__ import annotations
from hashlib import sha256
import json
import re
from typing import Any, Mapping
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atlasquant_aion_ci_governance_anchor_builder_identity_v1 import (
    SCHEMA as PARENT_SCHEMA, ANCHOR_READY, BUILD_READY,
    ANCHOR_PROOF_FIELDS, BUILD_PROOF_FIELDS, ANCHOR_PROOF_KEYS,
    BUILD_PROOF_KEYS, ANCHOR_TRUTHS, ANCHOR_DENIALS,
    BUILD_TRUTHS, BUILD_DENIALS,
)

SCHEMA = "ATLASQUANT_AION_CI_CUSTODY_ROTATION_PROVENANCE_GATE_V1"
CUSTODY_SCHEMA = "ATLASQUANT_AION_CI_CUSTODY_ROTATION_PROPOSAL_V1"
PROVENANCE_SCHEMA = "ATLASQUANT_AION_CI_EXTERNAL_PROVENANCE_FIXTURE_V1"
SCOPE = "EPHEMERAL_CI_FIXTURE_NO_PRODUCTION_AUTHORITY"
CUSTODY_READY = "CI_CUSTODY_ROTATION_CANDIDATE_UNTRUSTED"
PROVENANCE_READY = "CI_PROVENANCE_SHAPE_AND_EPHEMERAL_SIGNATURE_READY_UNTRUSTED"
REVIEW_READY = "READY_FOR_CUSTODY_AND_EXTERNAL_PROVENANCE_SECURITY_REVIEW"
BLOCKED = "BLOCKED"
SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
CI_ID = re.compile(r"ci-[a-z0-9][a-z0-9-]{3,79}\Z")
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
RUN_ID = re.compile(r"[1-9][0-9]{0,19}\Z")
CUSTODY_FIELDS = (
    "schema", "scope", "ceremony_id", "anchor_digest", "registry_digest",
    "checkpoint_sequence", "previous_rotation_digest",
    "previous_epoch", "next_epoch", "old_root_key_sha256",
    "new_root_key_sha256", "revoked_before", "revoked_after",
    "custody_policy_digest", "owner_challenge_digest",
    "recovery_quorum_policy_digest", "rotation_reason",
    "human_owner_approved", "external_custody_attested",
    "hsm_control_verified", "authoritative_antirollback_committed",
    "production_root_activated",
)
PROVENANCE_FIELDS = (
    "schema", "scope", "statement_id", "builder_proof_digest",
    "anchor_digest", "registry_digest", "release_manifest_sha256",
    "release_candidate_digest", "artifact_subject_digest",
    "source_commit", "build_run_id", "build_workflow_digest",
    "builder_workload_identity_digest", "issuer", "audience",
    "repository", "workflow_ref", "provenance_policy_digest",
    "statement_challenge_digest", "fixture_signer_key_sha256",
    "predicate_type", "issuer_token_verified",
    "workflow_identity_authoritative", "slsa_or_intoto_verified",
    "builder_is_independent", "artifact_from_verified_builder",
    "production_release_approved",
)
CUSTODY_EVIDENCE = (
    "ceremony_digest", "ceremony_id", "anchor_digest",
    "registry_digest", "checkpoint_sequence",
    "previous_rotation_digest", "previous_epoch", "next_epoch",
    "old_root_key_sha256", "new_root_key_sha256",
    "revoked_set_digest", "custody_policy_digest",
    "owner_challenge_digest", "recovery_quorum_policy_digest",
    "old_signature_digest", "new_signature_digest",
)
PROVENANCE_EVIDENCE = (
    "statement_digest", "statement_id", "builder_proof_digest",
    "anchor_digest", "registry_digest", "release_manifest_sha256",
    "release_candidate_digest", "artifact_subject_digest",
    "source_commit", "build_run_id", "build_workflow_digest",
    "builder_workload_identity_digest", "issuer", "audience",
    "repository", "workflow_ref", "provenance_policy_digest",
    "statement_challenge_digest", "fixture_signer_key_sha256",
    "fixture_signature_digest",
)
CUSTODY_FALSE = (
    "human_owner_approved", "external_custody_attested",
    "hsm_control_verified", "authoritative_antirollback_committed",
    "production_root_activated",
)
PROVENANCE_FALSE = (
    "issuer_token_verified", "workflow_identity_authoritative",
    "slsa_or_intoto_verified", "builder_is_independent",
    "artifact_from_verified_builder", "production_release_approved",
)
CUSTODY_PROOF_FALSE = (
    "real_owner_approval_verified", "real_root_rotated",
    "old_root_revoked_authoritatively", "antirollback_durable",
    "approved_recovery_quorum_verified", "owner_device_accessed",
    "production_root_authorized", "deploy_executed", "worker_activated",
)
PROVENANCE_PROOF_FALSE = (
    "oidc_signature_and_claims_authoritative",
    "trusted_external_builder_verified",
    "slsa_or_intoto_statement_verified", "real_artifact_provenance_verified",
    "production_release_approved", "owner_device_accessed",
    "deploy_executed", "worker_activated",
)
CUSTODY_PROOF_KEYS = set(CUSTODY_EVIDENCE) | {
    "schema", "state", "blockers", "candidate_digest",
    "two_ephemeral_signatures_valid", "synthetic_only",
} | set(CUSTODY_PROOF_FALSE)
PROVENANCE_PROOF_KEYS = set(PROVENANCE_EVIDENCE) | {
    "schema", "state", "blockers", "candidate_digest",
    "one_ephemeral_signature_valid", "synthetic_only",
} | set(PROVENANCE_PROOF_FALSE)
REVIEW_FALSE = (
    "owner_identity_authenticated", "release_publisher_authorized",
    "real_builder_identity_authenticated", "external_provenance_verified",
    "root_rotation_authoritative", "revocations_persisted",
    "slsa_or_intoto_verified", "real_release_signed",
    "owner_install_authorized", "installation_executed",
    "production_persistence_enabled", "deploy_executed", "worker_activated",
)

def _canonical(x: Any) -> bytes:
    return json.dumps(x, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
                      allow_nan=False).encode("ascii")

def _digest(x: Any) -> str:
    return "sha256:" + sha256(_canonical(x)).hexdigest()

def _hash_bytes(data: bytes) -> str:
    return "sha256:" + sha256(data).hexdigest()

def _sha(x: Any) -> bool:
    return type(x) is str and SHA.fullmatch(x) is not None

def _map(x: Any) -> dict[str, Any]:
    return dict(x) if isinstance(x, Mapping) else {}

def _signature(pk: Any, sig: Any, payload: Any) -> bool:
    if type(pk) is not bytes or len(pk) != 32 or type(sig) is not bytes or len(sig) != 64:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(pk).verify(sig, _canonical(payload))
        return True
    except (InvalidSignature, ValueError):
        return False

def _upstream(errors: list[str], proof: Mapping[str, Any] | None, role: str) -> dict[str, Any]:
    v = _map(proof)
    if role == "anchor":
        fields, allowed, state, yes, no, digest_field = (
            ANCHOR_PROOF_FIELDS, ANCHOR_PROOF_KEYS, ANCHOR_READY,
            ANCHOR_TRUTHS, ANCHOR_DENIALS, "anchor_proof_digest")
    else:
        fields, allowed, state, yes, no, digest_field = (
            BUILD_PROOF_FIELDS, BUILD_PROOF_KEYS, BUILD_READY,
            BUILD_TRUTHS, BUILD_DENIALS, "builder_proof_digest")
    if set(v) != allowed or v.get("schema") != PARENT_SCHEMA or v.get("state") != state or v.get("blockers") != []:
        errors.append("UPSTREAM_" + role.upper() + "_SHAPE_INVALID")
    if v.get(digest_field) != _digest({f: v.get(f) for f in fields}):
        errors.append("UPSTREAM_" + role.upper() + "_REHASH_FAILED")
    for f in yes:
        if v.get(f) is not True:
            errors.append("UPSTREAM_" + role.upper() + "_POSITIVE_REQUIRED:" + f)
    for f in no:
        if v.get(f) is not False:
            errors.append("UPSTREAM_" + role.upper() + "_TRUST_PROMOTION:" + f)
    return v

def verify_ci_custody_rotation(
    ceremony: Mapping[str, Any] | None,
    previous_root_public_key: Any, next_root_public_key: Any,
    previous_signature: Any, next_signature: Any,
    anchor_proof: Mapping[str, Any] | None,
    *, expected_previous_epoch: Any, expected_previous_rotation_digest: Any,
    expected_challenge_digest: Any, expected_policy_digest: Any,
    expected_recovery_quorum_policy_digest: Any,
) -> dict[str, Any]:
    m, errors = _map(ceremony), []
    anchor = _upstream(errors, anchor_proof, "anchor")
    if set(m) != set(CUSTODY_FIELDS):
        errors.append("CUSTODY_EXACT_FIELDS_REQUIRED")
    if m.get("schema") != CUSTODY_SCHEMA or m.get("scope") != SCOPE:
        errors.append("CI_CUSTODY_SCOPE_REQUIRED")
    if type(m.get("ceremony_id")) is not str or not CI_ID.fullmatch(m["ceremony_id"]):
        errors.append("CEREMONY_ID_INVALID")
    for k, expected in (
        ("anchor_digest", anchor.get("anchor_digest")),
        ("registry_digest", anchor.get("registry_digest")),
        ("checkpoint_sequence", anchor.get("checkpoint_sequence")),
        ("previous_epoch", expected_previous_epoch),
        ("previous_rotation_digest", expected_previous_rotation_digest),
        ("owner_challenge_digest", expected_challenge_digest),
        ("custody_policy_digest", expected_policy_digest),
        ("recovery_quorum_policy_digest", expected_recovery_quorum_policy_digest),
    ):
        if m.get(k) != expected:
            errors.append("CUSTODY_EXPECTATION_MISMATCH:" + k)
    for k in ("previous_rotation_digest", "owner_challenge_digest",
              "custody_policy_digest", "recovery_quorum_policy_digest"):
        if not _sha(m.get(k)):
            errors.append("CUSTODY_DIGEST_INVALID:" + k)
    if (type(expected_previous_epoch) is not int or expected_previous_epoch < 1
        or type(m.get("previous_epoch")) is not int
        or type(m.get("next_epoch")) is not int
        or m.get("next_epoch") != expected_previous_epoch + 1):
        errors.append("CUSTODY_EPOCH_MONOTONICITY_REQUIRED")
    if (_hash_bytes(previous_root_public_key) if type(previous_root_public_key) is bytes else "") != m.get("old_root_key_sha256"):
        errors.append("OLD_ROOT_KEY_MISMATCH")
    if (_hash_bytes(next_root_public_key) if type(next_root_public_key) is bytes else "") != m.get("new_root_key_sha256"):
        errors.append("NEW_ROOT_KEY_MISMATCH")
    role_keys = (
        m.get("old_root_key_sha256"), m.get("new_root_key_sha256"),
        anchor.get("governance_key_sha256"), anchor.get("publisher_key_sha256"),
        anchor.get("custodian_review_key_sha256"),
    )
    if any(not _sha(k) for k in role_keys) or len(set(role_keys)) != len(role_keys):
        errors.append("CUSTODY_KEY_ROLES_MUST_BE_DISTINCT")
    before, after = m.get("revoked_before"), m.get("revoked_after")
    if (type(before) is not list or type(after) is not list
        or len(before) > 16 or len(after) > 17
        or any(not _sha(k) for k in before + after)
        or before != sorted(set(before))
        or after != sorted(set(after))):
        errors.append("REVOCATION_SETS_INVALID")
    else:
        if m.get("old_root_key_sha256") in before or m.get("new_root_key_sha256") in after:
            errors.append("ROOT_REVOCATION_CONFLICT")
        if set(after) != (set(before) | {m.get("old_root_key_sha256")}):
            errors.append("REVOCATION_MUST_BE_MONOTONIC_AND_RETIRE_OLD")
    if m.get("rotation_reason") not in ("SCHEDULED_CI_ROTATION", "SYNTHETIC_COMPROMISE_RECOVERY"):
        errors.append("EXPLICIT_ROTATION_REASON_REQUIRED")
    for k in CUSTODY_FALSE:
        if m.get(k) is not False:
            errors.append("CUSTODY_FALSE_TRUST_CLAIM:" + k)
    old_ok = _signature(previous_root_public_key, previous_signature, m)
    new_ok = _signature(next_root_public_key, next_signature, m)
    if not old_ok:
        errors.append("OLD_ROOT_DETACHED_SIGNATURE_INVALID")
    if not new_ok:
        errors.append("NEW_ROOT_DETACHED_SIGNATURE_INVALID")
    material = {
        "ceremony_digest": _digest(m),
        **{k: m.get(k) for k in (
            "ceremony_id", "anchor_digest", "registry_digest",
            "checkpoint_sequence", "previous_rotation_digest",
            "previous_epoch", "next_epoch", "old_root_key_sha256",
            "new_root_key_sha256", "custody_policy_digest",
            "owner_challenge_digest", "recovery_quorum_policy_digest",
        )},
        "revoked_set_digest": _digest(after),
        "old_signature_digest": _hash_bytes(previous_signature) if type(previous_signature) is bytes else "",
        "new_signature_digest": _hash_bytes(next_signature) if type(next_signature) is bytes else "",
    }
    errors = list(dict.fromkeys(errors))
    return {
        "schema": SCHEMA, "state": CUSTODY_READY if not errors else BLOCKED,
        "blockers": errors, **material,
        "candidate_digest": _digest(material) if not errors else "",
        "two_ephemeral_signatures_valid": bool(old_ok and new_ok and not errors),
        "synthetic_only": True,
        **{f: False for f in CUSTODY_PROOF_FALSE},
    }

def verify_ci_external_provenance_fixture(
    statement: Mapping[str, Any] | None, fixture_public_key: Any,
    fixture_signature: Any,
    anchor_proof: Mapping[str, Any] | None,
    builder_proof: Mapping[str, Any] | None,
    *,
    expected_issuer: Any, expected_audience: Any,
    expected_repository: Any, expected_workflow_ref: Any,
    expected_provenance_policy_digest: Any,
    expected_statement_challenge_digest: Any,
) -> dict[str, Any]:
    m, errors = _map(statement), []
    a = _upstream(errors, anchor_proof, "anchor")
    b = _upstream(errors, builder_proof, "builder")
    if set(m) != set(PROVENANCE_FIELDS):
        errors.append("PROVENANCE_EXACT_FIELDS_REQUIRED")
    if m.get("schema") != PROVENANCE_SCHEMA or m.get("scope") != SCOPE:
        errors.append("CI_PROVENANCE_SCOPE_REQUIRED")
    if type(m.get("statement_id")) is not str or not CI_ID.fullmatch(m["statement_id"]):
        errors.append("STATEMENT_ID_INVALID")
    expected = {
        "builder_proof_digest": b.get("builder_proof_digest"),
        "anchor_digest": a.get("anchor_digest"),
        "registry_digest": a.get("registry_digest"),
        "release_manifest_sha256": b.get("release_manifest_sha256"),
        "release_candidate_digest": b.get("release_candidate_digest"),
        "artifact_subject_digest": b.get("subject_digest"),
        "source_commit": b.get("source_commit"),
        "build_run_id": b.get("build_run_id"),
        "build_workflow_digest": b.get("builder_workflow_digest"),
        "builder_workload_identity_digest": b.get("builder_workload_identity_digest"),
        "issuer": expected_issuer, "audience": expected_audience,
        "repository": expected_repository, "workflow_ref": expected_workflow_ref,
        "provenance_policy_digest": expected_provenance_policy_digest,
        "statement_challenge_digest": expected_statement_challenge_digest,
    }
    for k, wanted in expected.items():
        if m.get(k) != wanted:
            errors.append("PROVENANCE_BINDING_MISMATCH:" + k)
    for k in ("provenance_policy_digest", "statement_challenge_digest",
              "fixture_signer_key_sha256"):
        if not _sha(m.get(k)):
            errors.append("PROVENANCE_DIGEST_INVALID:" + k)
    for k in ("issuer", "audience", "repository", "workflow_ref"):
        v = m.get(k)
        if type(v) is not str or not 1 <= len(v) <= 160 or "\n" in v:
            errors.append("IDENTITY_STRING_INVALID:" + k)
    if not isinstance(m.get("source_commit"), str) or not SHA40.fullmatch(m["source_commit"]):
        errors.append("SOURCE_COMMIT_INVALID")
    if not isinstance(m.get("build_run_id"), str) or not RUN_ID.fullmatch(m["build_run_id"]):
        errors.append("BUILD_RUN_ID_INVALID")
    if m.get("predicate_type") != "CI_PROVENANCE_FIXTURE_NOT_SLSA_OR_INTOTO":
        errors.append("REAL_SLSA_OR_INTOTO_PREDICATE_REFUSED")
    for k in PROVENANCE_FALSE:
        if m.get(k) is not False:
            errors.append("FALSE_EXTERNAL_ATTESTATION_CLAIM:" + k)
    if (_hash_bytes(fixture_public_key) if type(fixture_public_key) is bytes else "") != m.get("fixture_signer_key_sha256"):
        errors.append("PROVENANCE_FIXTURE_PUBLIC_KEY_MISMATCH")
    if m.get("fixture_signer_key_sha256") in (
        a.get("custodian_review_key_sha256"), a.get("governance_key_sha256"),
        a.get("publisher_key_sha256"), b.get("builder_public_key_sha256"),
        b.get("witness_key_sha256"),
    ):
        errors.append("PROVENANCE_FIXTURE_SIGNER_ROLE_COLLISION")
    sig_ok = _signature(fixture_public_key, fixture_signature, m)
    if not sig_ok:
        errors.append("PROVENANCE_FIXTURE_SIGNATURE_INVALID")
    material = {
        "statement_digest": _digest(m),
        **{k: m.get(k) for k in PROVENANCE_EVIDENCE
           if k not in ("statement_digest", "fixture_signature_digest")},
        "fixture_signature_digest": _hash_bytes(fixture_signature) if type(fixture_signature) is bytes else "",
    }
    errors = list(dict.fromkeys(errors))
    return {
        "schema": SCHEMA, "state": PROVENANCE_READY if not errors else BLOCKED,
        "blockers": errors, **material,
        "candidate_digest": _digest(material) if not errors else "",
        "one_ephemeral_signature_valid": bool(sig_ok and not errors),
        "synthetic_only": True,
        **{f: False for f in PROVENANCE_PROOF_FALSE},
    }

def review_ci_custody_provenance(
    custody_proof: Mapping[str, Any] | None,
    provenance_proof: Mapping[str, Any] | None,
    anchor_proof: Mapping[str, Any] | None,
    builder_proof: Mapping[str, Any] | None,
    *,
    expected_anchor_digest: Any,
    minimum_expected_custody_epoch: Any,
    external_issuer_policy_digest: Any,
    independent_publisher_approval_policy_digest: Any,
) -> dict[str, Any]:
    c, p, errors = _map(custody_proof), _map(provenance_proof), []
    a = _upstream(errors, anchor_proof, "anchor")
    b = _upstream(errors, builder_proof, "builder")
    for proof, kind, names, state, fields, truth, negatives in (
        (c, "CUSTODY", CUSTODY_PROOF_KEYS, CUSTODY_READY, CUSTODY_EVIDENCE,
         "two_ephemeral_signatures_valid", CUSTODY_PROOF_FALSE),
        (p, "PROVENANCE", PROVENANCE_PROOF_KEYS, PROVENANCE_READY, PROVENANCE_EVIDENCE,
         "one_ephemeral_signature_valid", PROVENANCE_PROOF_FALSE),
    ):
        if set(proof) != names or proof.get("schema") != SCHEMA or proof.get("state") != state or proof.get("blockers") != []:
            errors.append(kind + "_EXACT_READY_PROOF_REQUIRED")
        if proof.get("candidate_digest") != _digest({k: proof.get(k) for k in fields}):
            errors.append(kind + "_REHASH_MISMATCH")
        if proof.get(truth) is not True or proof.get("synthetic_only") is not True:
            errors.append(kind + "_SYNTHETIC_SIGNATURE_SHAPE_REQUIRED")
        for flag in negatives:
            if proof.get(flag) is not False:
                errors.append(kind + "_FALSE_TRUST_REQUIRED:" + flag)
    if not _sha(expected_anchor_digest) or c.get("anchor_digest") != expected_anchor_digest:
        errors.append("EXTERNAL_ANCHOR_PIN_MISMATCH")
    if c.get("anchor_digest") != a.get("anchor_digest") or p.get("anchor_digest") != a.get("anchor_digest"):
        errors.append("ANCHOR_PROOF_CHAIN_MISMATCH")
    if (c.get("registry_digest") != a.get("registry_digest") or
        p.get("registry_digest") != a.get("registry_digest")):
        errors.append("REGISTRY_PROOF_CHAIN_MISMATCH")
    if (p.get("builder_proof_digest") != b.get("builder_proof_digest") or
        p.get("artifact_subject_digest") != b.get("subject_digest") or
        p.get("source_commit") != b.get("source_commit") or
        p.get("build_run_id") != b.get("build_run_id") or
        p.get("release_manifest_sha256") != b.get("release_manifest_sha256") or
        p.get("release_candidate_digest") != b.get("release_candidate_digest")):
        errors.append("RELEASE_BUILD_SUBJECT_MISMATCH")
    if (type(minimum_expected_custody_epoch) is not int or
        minimum_expected_custody_epoch < 1 or
        type(c.get("next_epoch")) is not int or
        c.get("next_epoch") < minimum_expected_custody_epoch):
        errors.append("CUSTODY_EPOCH_BELOW_EXPECTED_MINIMUM")
    for k, val in (
        ("external_issuer_policy_digest", external_issuer_policy_digest),
        ("independent_publisher_approval_policy_digest", independent_publisher_approval_policy_digest),
    ):
        if not _sha(val):
            errors.append("REQUIRED_UNTRUSTED_POLICY_DIGEST:" + k)
    errors = list(dict.fromkeys(errors))
    material = {
        "custody_candidate_digest": c.get("candidate_digest"),
        "provenance_candidate_digest": p.get("candidate_digest"),
        "anchor_proof_digest": a.get("anchor_proof_digest"),
        "builder_proof_digest": b.get("builder_proof_digest"),
        "minimum_expected_custody_epoch": minimum_expected_custody_epoch,
        "external_anchor_digest": expected_anchor_digest,
        "external_issuer_policy_digest": external_issuer_policy_digest,
        "independent_publisher_approval_policy_digest": independent_publisher_approval_policy_digest,
    }
    return {
        "schema": SCHEMA, "state": REVIEW_READY if not errors else BLOCKED,
        "blockers": errors, **material,
        "review_candidate_digest": _digest(material) if not errors else "",
        "all_inputs_synthetic_untrusted": True,
        **{flag: False for flag in REVIEW_FALSE},
    }

def custody_provenance_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA, "ci_only": True, "ephemeral_signing_keys_only": True,
        "real_publisher_custody_validated": False,
        "authoritative_revocation_persisted": False,
        "real_owner_recovery_quorum_verified": False,
        "trusted_external_identity_provider_contacted": False,
        "external_oidc_token_validated": False,
        "actual_slsa_or_intoto_statement_verified": False,
        "real_github_build_artifacts_fetched": False,
        "release_published": False,
        "production_signing_key_generated": False,
        "owner_authorization_consumed": False,
        "owner_pc_accessed": False,
        "windows_registry_acl_startup_modified": False,
        "aion_installed": False, "worker_activated": False,
        "deploy_executed": False,
    }
