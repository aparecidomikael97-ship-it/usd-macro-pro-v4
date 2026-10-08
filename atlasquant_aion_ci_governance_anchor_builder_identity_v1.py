"""AION CI governance anchor and build identity provenance preflight V1.

Pure verification against caller-supplied ephemeral CI keys. A valid Ed25519
signature authenticates ONLY bytes under that key, not the HUMAN_OWNER,
hardware custody, external approved roots, a real builder, or production
SLSA/in-toto attestation. No private-key generation, storage, Windows IO,
network access, production trust promotion, install, merge or deploy.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atlasquant_aion_ci_publisher_registry_build_witness_v1 import (
    SCHEMA as UPSTREAM_SCHEMA, REGISTRY_READY, WITNESS_READY,
    REGISTRY_PROOF_FIELDS, WITNESS_PROOF_FIELDS,
    REGISTRY_PROOF_KEYS, WITNESS_PROOF_KEYS,
    REGISTRY_REQUIRED_TRUE, REGISTRY_REQUIRED_FALSE,
    WITNESS_REQUIRED_TRUE, WITNESS_REQUIRED_FALSE,
)
from atlasquant_aion_windows_signed_release_provenance_ci_fixture_v1 import (
    SCHEMA as RELEASE_SCHEMA, RELEASE_READY, VERIFICATION_KEYS,
    VERIFICATION_TRUTH_FLAGS, VERIFICATION_DENIAL_FLAGS, EVIDENCE_KEYS,
)

SCHEMA = "ATLASQUANT_AION_CI_GOVERNANCE_ANCHOR_BUILDER_IDENTITY_PREFLIGHT_V1"
ANCHOR_SCHEMA = "ATLASQUANT_AION_CI_GOVERNANCE_ANCHOR_PROPOSAL_V1"
BUILD_SCHEMA = "ATLASQUANT_AION_CI_BUILDER_IDENTITY_STATEMENT_V1"
SCOPE = "EPHEMERAL_CI_UNTRUSTED_IDENTITY_FIXTURES"
ANCHOR_READY = "CI_GOVERNANCE_ANCHOR_ENVELOPE_READY_UNTRUSTED"
BUILD_READY = "CI_BUILDER_IDENTITY_ENVELOPE_READY_UNTRUSTED"
REVIEW_READY = "READY_FOR_GOVERNANCE_ROOT_AND_BUILDER_IDENTITY_SECURITY_REVIEW"
BLOCKED = "BLOCKED"
SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
ANCHOR_ID = re.compile(r"ci-anchor-[a-z0-9][a-z0-9-]{2,59}\Z")
BUILD_ID = re.compile(r"ci-builder-[a-z0-9][a-z0-9-]{2,59}\Z")
ANCHOR_FIELDS = (
    "schema", "scope", "anchor_id", "checkpoint_sequence",
    "previous_anchor_digest", "registry_digest", "registry_sequence",
    "governance_key_sha256", "publisher_key_sha256",
    "custodian_review_key_sha256", "custodian_policy_digest",
    "owner_review_challenge_digest", "checkpoint_policy_digest",
    "owner_identity_attested", "custodian_review_authoritative",
    "rollback_counter_durably_verified", "production_root_activated",
)
BUILD_FIELDS = (
    "schema", "scope", "builder_id", "builder_public_key_sha256",
    "builder_identity_policy_digest", "builder_workload_identity_digest",
    "builder_workflow_digest", "builder_environment_digest",
    "source_commit", "build_run_id", "release_id",
    "release_manifest_sha256", "release_file_table_digest",
    "release_candidate_digest", "registry_digest", "registry_sequence",
    "witness_statement_digest", "witness_key_sha256",
    "governance_anchor_digest", "subject_digest",
    "builder_challenge_digest", "slsa_predicate_type",
    "production_builder_identity_verified", "external_issuer_validated",
    "real_slsa_statement_verified", "build_reproducibility_attested",
)
ANCHOR_PROOF_FIELDS = (
    "anchor_digest", "anchor_id", "checkpoint_sequence",
    "previous_anchor_digest", "registry_digest", "registry_sequence",
    "governance_key_sha256", "publisher_key_sha256",
    "custodian_review_key_sha256", "custodian_policy_digest",
    "owner_review_challenge_digest", "checkpoint_policy_digest",
    "custodian_signature_sha256",
)
BUILD_PROOF_FIELDS = (
    "builder_statement_digest", "builder_signature_sha256",
    "builder_id", "builder_public_key_sha256",
    "builder_identity_policy_digest", "builder_workload_identity_digest",
    "builder_workflow_digest", "builder_environment_digest",
    "source_commit", "build_run_id", "release_id",
    "release_manifest_sha256", "release_file_table_digest",
    "release_candidate_digest", "registry_digest", "registry_sequence",
    "witness_statement_digest", "witness_key_sha256",
    "governance_anchor_digest", "subject_digest",
    "builder_challenge_digest",
)
ANCHOR_TRUTHS = ("ci_custodian_signature_shape_valid",)
BUILD_TRUTHS = ("ci_builder_signature_shape_valid",)
ANCHOR_DENIALS = (
    "owner_custodian_identity_trusted", "real_owner_approval_verified",
    "hardware_root_attested", "root_antirollback_durably_anchored",
    "production_root_activated", "owner_authorization_consumed",
    "worker_activated", "deploy_executed",
)
BUILD_DENIALS = (
    "builder_workload_identity_trusted", "external_oidc_issuer_verified",
    "slsa_predicate_verified", "real_builder_provenance_attested",
    "actual_release_built_by_claimed_run", "aion_release_approved",
    "owner_device_accessed", "installation_authorized",
    "worker_activated", "deploy_executed",
)
ANCHOR_PROOF_KEYS = set(ANCHOR_PROOF_FIELDS) | {
    "schema", "state", "blockers", "anchor_proof_digest",
} | set(ANCHOR_TRUTHS) | set(ANCHOR_DENIALS)
BUILD_PROOF_KEYS = set(BUILD_PROOF_FIELDS) | {
    "schema", "state", "blockers", "builder_proof_digest",
} | set(BUILD_TRUTHS) | set(BUILD_DENIALS)
REVIEW_DENIALS = (
    "production_governance_root_trusted",
    "custodian_is_human_owner_verified",
    "real_builder_identity_authenticated",
    "real_slsa_or_intoto_verified",
    "release_independently_attested",
    "registry_rollback_prevented",
    "owner_install_approved", "owner_device_accessed",
    "release_published", "aion_installed",
    "worker_activated", "deploy_executed",
)

def _canonical(v: Any) -> bytes:
    return json.dumps(v, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")

def _digest(v: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(v)).hexdigest()

def _bdigest(v: bytes) -> str:
    return "sha256:" + hashlib.sha256(v).hexdigest()

def _sha(v: Any) -> bool:
    return type(v) is str and SHA.fullmatch(v) is not None

def _m(v: Any) -> dict[str, Any]:
    return dict(v) if isinstance(v, Mapping) else {}

def _verify(pk: Any, signature: Any, data: Any) -> bool:
    if type(pk) is not bytes or len(pk) != 32 or type(signature) is not bytes or len(signature) != 64:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(pk).verify(signature, _canonical(data))
        return True
    except (InvalidSignature, ValueError):
        return False

def _shape(errors: list[str], prefix: str, actual: Any, permitted: set[str]) -> None:
    if set(_m(actual)) != permitted:
        errors.append(prefix + "_EXACT_FIELDS_REQUIRED")

def _upstream_proof(
    errors: list[str], obj: Mapping[str, Any] | None, *,
    kind: str,
) -> dict[str, Any]:
    v = _m(obj)
    if kind == "registry":
        fields, names, ready = REGISTRY_PROOF_FIELDS, REGISTRY_PROOF_KEYS, REGISTRY_READY
        yes, no, digest_name = REGISTRY_REQUIRED_TRUE, REGISTRY_REQUIRED_FALSE, "registry_proof_candidate_digest"
    elif kind == "witness":
        fields, names, ready = WITNESS_PROOF_FIELDS, WITNESS_PROOF_KEYS, WITNESS_READY
        yes, no, digest_name = WITNESS_REQUIRED_TRUE, WITNESS_REQUIRED_FALSE, "witness_proof_candidate_digest"
    else:
        raise ValueError("UNKNOWN_UPSTREAM_PROOF_KIND")
    if set(v) != names or v.get("schema") != UPSTREAM_SCHEMA or v.get("state") != ready or v.get("blockers") != []:
        errors.append("UPSTREAM_" + kind.upper() + "_SHAPE_INVALID")
    if v.get(digest_name) != _digest({k: v.get(k) for k in fields}):
        errors.append("UPSTREAM_" + kind.upper() + "_DIGEST_INVALID")
    for k in yes:
        if v.get(k) is not True:
            errors.append("UPSTREAM_" + kind.upper() + "_EVIDENCE_FALSE:" + k)
    for k in no:
        if v.get(k) is not False:
            errors.append("UPSTREAM_" + kind.upper() + "_TRUST_ESCALATION:" + k)
    return v

def _release_proof(errors: list[str], release: Mapping[str, Any] | None) -> dict[str, Any]:
    v = _m(release)
    if set(v) != VERIFICATION_KEYS or v.get("schema") != RELEASE_SCHEMA or v.get("state") != RELEASE_READY or v.get("blockers") != []:
        errors.append("UPSTREAM_RELEASE_SHAPE_INVALID")
    if v.get("candidate_evidence_digest") != _digest({k: v.get(k) for k in EVIDENCE_KEYS}):
        errors.append("UPSTREAM_RELEASE_DIGEST_INVALID")
    for k in VERIFICATION_TRUTH_FLAGS:
        if v.get(k) is not True:
            errors.append("UPSTREAM_RELEASE_CI_EVIDENCE_MISSING:" + k)
    for k in VERIFICATION_DENIAL_FLAGS:
        if v.get(k) is not False:
            errors.append("UPSTREAM_RELEASE_TRUST_ESCALATION:" + k)
    return v

def verify_ci_governance_anchor(
    proposal: Mapping[str, Any] | None, custodian_public_key: Any,
    custodian_signature: Any, registry_proof: Mapping[str, Any] | None,
    *,
    expected_anchor_id: Any, expected_sequence: Any,
    expected_previous_anchor_digest: Any,
    expected_custodian_key_sha256: Any, expected_owner_review_challenge_digest: Any,
    expected_custodian_policy_digest: Any, expected_checkpoint_policy_digest: Any,
) -> dict[str, Any]:
    m = _m(proposal)
    errors: list[str] = []
    g = _upstream_proof(errors, registry_proof, kind="registry")
    _shape(errors, "ANCHOR", m, set(ANCHOR_FIELDS))
    if m.get("schema") != ANCHOR_SCHEMA or m.get("scope") != SCOPE:
        errors.append("CI_ANCHOR_SCOPE_REQUIRED")
    if type(m.get("anchor_id")) is not str or not ANCHOR_ID.fullmatch(m["anchor_id"]):
        errors.append("CI_ANCHOR_ID_INVALID")
    if type(m.get("checkpoint_sequence")) is not int or m.get("checkpoint_sequence") < 1:
        errors.append("CHECKPOINT_SEQUENCE_INVALID")
    checks = {
        "anchor_id": expected_anchor_id, "checkpoint_sequence": expected_sequence,
        "previous_anchor_digest": expected_previous_anchor_digest,
        "custodian_review_key_sha256": expected_custodian_key_sha256,
        "owner_review_challenge_digest": expected_owner_review_challenge_digest,
        "custodian_policy_digest": expected_custodian_policy_digest,
        "checkpoint_policy_digest": expected_checkpoint_policy_digest,
        "registry_digest": g.get("registry_digest"),
        "registry_sequence": g.get("sequence"),
        "governance_key_sha256": g.get("governance_key_sha256"),
        "publisher_key_sha256": g.get("active_key_sha256"),
    }
    for name, val in checks.items():
        if m.get(name) != val:
            errors.append("ANCHOR_BINDING_MISMATCH:" + name)
    for name in (
        "previous_anchor_digest", "custodian_review_key_sha256",
        "owner_review_challenge_digest", "custodian_policy_digest",
        "checkpoint_policy_digest",
    ):
        if not _sha(checks[name]):
            errors.append("ANCHOR_EXPECTED_DIGEST_INVALID:" + name)
    if type(expected_sequence) is not int or expected_sequence < 1:
        errors.append("EXTERNAL_CHECKPOINT_SEQUENCE_INVALID")
    if (type(custodian_public_key) is not bytes or len(custodian_public_key) != 32
        or _bdigest(custodian_public_key) != m.get("custodian_review_key_sha256")):
        errors.append("CUSTODIAN_PUBLIC_KEY_MISMATCH")
    if m.get("custodian_review_key_sha256") in (
        m.get("governance_key_sha256"), m.get("publisher_key_sha256")
    ):
        errors.append("CUSTODIAN_GOVERNANCE_PUBLISHER_ROLES_COLLIDE")
    for name in ("owner_identity_attested", "custodian_review_authoritative",
                 "rollback_counter_durably_verified", "production_root_activated"):
        if m.get(name) is not False:
            errors.append("ANCHOR_SELF_TRUST_CLAIM_FORBIDDEN:" + name)
    if not _verify(custodian_public_key, custodian_signature, m):
        errors.append("CUSTODIAN_DETACHED_SIGNATURE_INVALID")
    material = {
        "anchor_digest": _digest(m), "anchor_id": m.get("anchor_id"),
        "checkpoint_sequence": m.get("checkpoint_sequence"),
        "previous_anchor_digest": m.get("previous_anchor_digest"),
        "registry_digest": m.get("registry_digest"),
        "registry_sequence": m.get("registry_sequence"),
        "governance_key_sha256": m.get("governance_key_sha256"),
        "publisher_key_sha256": m.get("publisher_key_sha256"),
        "custodian_review_key_sha256": m.get("custodian_review_key_sha256"),
        "custodian_policy_digest": m.get("custodian_policy_digest"),
        "owner_review_challenge_digest": m.get("owner_review_challenge_digest"),
        "checkpoint_policy_digest": m.get("checkpoint_policy_digest"),
        "custodian_signature_sha256": _bdigest(custodian_signature)
            if type(custodian_signature) is bytes and len(custodian_signature) == 64 else "",
    }
    errors = list(dict.fromkeys(errors))
    return {
        "schema": SCHEMA, "state": ANCHOR_READY if not errors else BLOCKED,
        "blockers": errors, **material,
        "anchor_proof_digest": _digest(material) if not errors else "",
        "ci_custodian_signature_shape_valid": not errors,
        **{k: False for k in ANCHOR_DENIALS},
    }

def verify_ci_builder_identity(
    statement: Mapping[str, Any] | None, builder_public_key: Any,
    builder_signature: Any, anchor_proof: Mapping[str, Any] | None,
    registry_proof: Mapping[str, Any] | None, witness_proof: Mapping[str, Any] | None,
    release_proof: Mapping[str, Any] | None,
    *,
    expected_builder_id: Any, expected_builder_key_sha256: Any,
    expected_builder_identity_policy_digest: Any,
    expected_workload_identity_digest: Any,
    expected_challenge_digest: Any,
) -> dict[str, Any]:
    s, a = _m(statement), _m(anchor_proof)
    errors: list[str] = []
    g = _upstream_proof(errors, registry_proof, kind="registry")
    w = _upstream_proof(errors, witness_proof, kind="witness")
    r = _release_proof(errors, release_proof)
    _shape(errors, "ANCHOR_PROOF", a, ANCHOR_PROOF_KEYS)
    if a.get("schema") != SCHEMA or a.get("state") != ANCHOR_READY or a.get("blockers") != []:
        errors.append("ANCHOR_PROOF_REQUIRED")
    if a.get("anchor_proof_digest") != _digest({k: a.get(k) for k in ANCHOR_PROOF_FIELDS}):
        errors.append("ANCHOR_PROOF_DIGEST_MISMATCH")
    for k in ANCHOR_TRUTHS:
        if a.get(k) is not True:
            errors.append("ANCHOR_PROOF_POSITIVE_REQUIRED:" + k)
    for k in ANCHOR_DENIALS:
        if a.get(k) is not False:
            errors.append("ANCHOR_PROOF_FALSE_TRUST_REQUIRED:" + k)
    if (a.get("registry_digest") != g.get("registry_digest") or
        a.get("registry_sequence") != g.get("sequence") or
        a.get("governance_key_sha256") != g.get("governance_key_sha256") or
        a.get("publisher_key_sha256") != g.get("active_key_sha256")):
        errors.append("ANCHOR_REGISTRY_PROOF_DIVERGENCE")
    if (w.get("registry_digest") != g.get("registry_digest") or
        w.get("registry_sequence") != g.get("sequence") or
        w.get("active_publisher_key_sha256") != g.get("active_key_sha256") or
        w.get("release_candidate_digest") != r.get("candidate_evidence_digest") or
        w.get("release_manifest_sha256") != r.get("manifest_sha256") or
        w.get("release_file_table_digest") != r.get("file_table_digest") or
        w.get("release_id") != r.get("release_id") or
        w.get("source_commit") != r.get("source_commit") or
        w.get("build_run_id") != r.get("build_run_id")):
        errors.append("UPSTREAM_BUILD_WITNESS_RELEASE_DIVERGENCE")
    _shape(errors, "BUILDER", s, set(BUILD_FIELDS))
    if s.get("schema") != BUILD_SCHEMA or s.get("scope") != SCOPE:
        errors.append("CI_BUILDER_SCOPE_REQUIRED")
    if type(s.get("builder_id")) is not str or not BUILD_ID.fullmatch(s["builder_id"]):
        errors.append("CI_BUILDER_ID_INVALID")
    if s.get("slsa_predicate_type") != "CI_SHAPE_ONLY_NOT_A_REAL_SLSA_ATTESTATION":
        errors.append("REAL_SLSA_PREDICATE_CLAIM_FORBIDDEN")
    bindings = {
        "builder_id": expected_builder_id,
        "builder_public_key_sha256": expected_builder_key_sha256,
        "builder_identity_policy_digest": expected_builder_identity_policy_digest,
        "builder_workload_identity_digest": expected_workload_identity_digest,
        "builder_challenge_digest": expected_challenge_digest,
        "builder_workflow_digest": w.get("build_workflow_digest"),
        "builder_environment_digest": w.get("build_environment_digest"),
        "source_commit": r.get("source_commit"),
        "build_run_id": r.get("build_run_id"),
        "release_id": r.get("release_id"),
        "release_manifest_sha256": r.get("manifest_sha256"),
        "release_file_table_digest": r.get("file_table_digest"),
        "release_candidate_digest": r.get("candidate_evidence_digest"),
        "registry_digest": g.get("registry_digest"),
        "registry_sequence": g.get("sequence"),
        "witness_statement_digest": w.get("witness_statement_digest"),
        "witness_key_sha256": w.get("witness_key_sha256"),
        "governance_anchor_digest": a.get("anchor_digest"),
        "subject_digest": _digest({
            "release_manifest_sha256": r.get("manifest_sha256"),
            "release_file_table_digest": r.get("file_table_digest"),
            "release_candidate_digest": r.get("candidate_evidence_digest"),
        }),
    }
    for name, expected in bindings.items():
        if s.get(name) != expected:
            errors.append("BUILDER_IDENTITY_SUBJECT_BINDING_MISMATCH:" + name)
    for name in ("builder_public_key_sha256", "builder_identity_policy_digest",
                 "builder_workload_identity_digest", "builder_challenge_digest"):
        if not _sha(bindings[name]):
            errors.append("BUILDER_EXTERNAL_DIGEST_INVALID:" + name)
    if type(builder_public_key) is not bytes or len(builder_public_key) != 32 or _bdigest(builder_public_key) != s.get("builder_public_key_sha256"):
        errors.append("BUILDER_PUBLIC_KEY_MISMATCH")
    if s.get("builder_public_key_sha256") in (
        a.get("custodian_review_key_sha256"), g.get("governance_key_sha256"),
        g.get("active_key_sha256"), w.get("witness_key_sha256")
    ):
        errors.append("BUILDER_CUSTODIAN_PUBLISHER_WITNESS_ROLE_COLLISION")
    for name in ("production_builder_identity_verified", "external_issuer_validated",
                 "real_slsa_statement_verified", "build_reproducibility_attested"):
        if s.get(name) is not False:
            errors.append("BUILDER_SELF_TRUST_CLAIM_FORBIDDEN:" + name)
    if not _verify(builder_public_key, builder_signature, s):
        errors.append("BUILDER_DETACHED_SIGNATURE_INVALID")
    material = {
        "builder_statement_digest": _digest(s),
        "builder_signature_sha256": _bdigest(builder_signature)
            if type(builder_signature) is bytes and len(builder_signature) == 64 else "",
        **{name: s.get(name) for name in BUILD_PROOF_FIELDS
           if name not in ("builder_statement_digest", "builder_signature_sha256")},
    }
    errors = list(dict.fromkeys(errors))
    return {
        "schema": SCHEMA, "state": BUILD_READY if not errors else BLOCKED,
        "blockers": errors, **material,
        "builder_proof_digest": _digest(material) if not errors else "",
        "ci_builder_signature_shape_valid": not errors,
        **{k: False for k in BUILD_DENIALS},
    }

def review_ci_governance_builder_preflight(
    anchor_proof: Mapping[str, Any] | None,
    builder_proof: Mapping[str, Any] | None,
    registry_proof: Mapping[str, Any] | None,
    witness_proof: Mapping[str, Any] | None,
    release_proof: Mapping[str, Any] | None,
    *,
    minimum_expected_checkpoint_sequence: Any,
    external_anchor_digest: Any,
    independent_identity_policy_digest: Any,
) -> dict[str, Any]:
    a, b = _m(anchor_proof), _m(builder_proof)
    errors: list[str] = []
    g = _upstream_proof(errors, registry_proof, kind="registry")
    w = _upstream_proof(errors, witness_proof, kind="witness")
    r = _release_proof(errors, release_proof)
    _shape(errors, "ANCHOR_PROOF", a, ANCHOR_PROOF_KEYS)
    _shape(errors, "BUILDER_PROOF", b, BUILD_PROOF_KEYS)
    for p, role, ready, fields, yes, no, digest_name in (
        (a, "ANCHOR", ANCHOR_READY, ANCHOR_PROOF_FIELDS,
         ANCHOR_TRUTHS, ANCHOR_DENIALS, "anchor_proof_digest"),
        (b, "BUILDER", BUILD_READY, BUILD_PROOF_FIELDS,
         BUILD_TRUTHS, BUILD_DENIALS, "builder_proof_digest"),
    ):
        if p.get("schema") != SCHEMA or p.get("state") != ready or p.get("blockers") != []:
            errors.append(role + "_PROOF_READY_REQUIRED")
        if p.get(digest_name) != _digest({k: p.get(k) for k in fields}):
            errors.append(role + "_PROOF_REHASH_FAILED")
        for k in yes:
            if p.get(k) is not True:
                errors.append(role + "_POSITIVE_PROOF_MISSING:" + k)
        for k in no:
            if p.get(k) is not False:
                errors.append(role + "_TRUST_ESCALATION_FORBIDDEN:" + k)
    if type(minimum_expected_checkpoint_sequence) is not int or minimum_expected_checkpoint_sequence < 1:
        errors.append("MINIMUM_ANCHOR_SEQUENCE_INVALID")
    if type(a.get("checkpoint_sequence")) is not int or a.get("checkpoint_sequence") < minimum_expected_checkpoint_sequence:
        errors.append("ANCHOR_SEQUENCE_BELOW_EXTERNAL_MINIMUM")
    if not _sha(external_anchor_digest) or a.get("anchor_digest") != external_anchor_digest:
        errors.append("EXTERNAL_ANCHOR_DIGEST_MISMATCH")
    if not _sha(independent_identity_policy_digest):
        errors.append("INDEPENDENT_IDENTITY_POLICY_DIGEST_REQUIRED")
    links = (
        (a.get("registry_digest"), g.get("registry_digest")),
        (a.get("registry_sequence"), g.get("sequence")),
        (a.get("governance_key_sha256"), g.get("governance_key_sha256")),
        (a.get("publisher_key_sha256"), g.get("active_key_sha256")),
        (b.get("governance_anchor_digest"), a.get("anchor_digest")),
        (b.get("registry_digest"), g.get("registry_digest")),
        (b.get("registry_sequence"), g.get("sequence")),
        (b.get("witness_statement_digest"), w.get("witness_statement_digest")),
        (b.get("witness_key_sha256"), w.get("witness_key_sha256")),
        (b.get("builder_workflow_digest"), w.get("build_workflow_digest")),
        (b.get("builder_environment_digest"), w.get("build_environment_digest")),
        (b.get("source_commit"), r.get("source_commit")),
        (b.get("build_run_id"), r.get("build_run_id")),
        (b.get("release_id"), r.get("release_id")),
        (b.get("release_manifest_sha256"), r.get("manifest_sha256")),
        (b.get("release_file_table_digest"), r.get("file_table_digest")),
        (b.get("release_candidate_digest"), r.get("candidate_evidence_digest")),
        (w.get("registry_digest"), g.get("registry_digest")),
        (w.get("release_candidate_digest"), r.get("candidate_evidence_digest")),
    )
    if any(left != right for left, right in links):
        errors.append("CROSS_PROOF_RELEASE_ANCHOR_BUILDER_DIVERGENCE")
    errors = list(dict.fromkeys(errors))
    material = {
        "anchor_proof_digest": a.get("anchor_proof_digest"),
        "builder_proof_digest": b.get("builder_proof_digest"),
        "registry_proof_digest": g.get("registry_proof_candidate_digest"),
        "witness_proof_digest": w.get("witness_proof_candidate_digest"),
        "release_candidate_digest": r.get("candidate_evidence_digest"),
        "minimum_expected_checkpoint_sequence": minimum_expected_checkpoint_sequence,
        "external_anchor_digest": external_anchor_digest,
        "independent_identity_policy_digest": independent_identity_policy_digest,
    }
    return {
        "schema": SCHEMA, "state": REVIEW_READY if not errors else BLOCKED,
        "blockers": errors,
        **material,
        "review_digest": _digest(material) if not errors else "",
        **{k: False for k in REVIEW_DENIALS},
    }

def governance_builder_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA, "test_only": True,
        "ephemeral_ci_keys_only": True,
        "caller_supplied_governance_key_is_trusted": False,
        "external_anchor_digest_authenticates_source": False,
        "sequence_minimum_is_persisted_antirollback": False,
        "custodian_signature_proves_human_owner": False,
        "builder_signature_proves_independent_builder": False,
        "test_workload_identity_is_real_oidc_identity": False,
        "slsa_predicate_verified": False, "intoto_attestation_verified": False,
        "production_governance_root_activated": False,
        "official_aion_publisher_approved": False,
        "owner_authorization_consumed": False,
        "real_aion_release_signed": False,
        "owner_device_accessed": False,
        "windows_acl_or_startup_modified": False,
        "package_installed": False,
        "deploy_executed": False, "worker_activated": False,
    }
