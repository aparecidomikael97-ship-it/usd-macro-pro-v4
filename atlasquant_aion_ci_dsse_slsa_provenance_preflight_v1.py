"""AION CI DSSE / in-toto SLSA provenance acceptance V1 — UNTRUSTED FIXTURES.

Cryptographic verification of *real DSSE PAE/signature bytes* using ephemeral
caller-provided Ed25519 CI keys. Restrictive synthetic subset of in-toto
Statement v1 and SLSA provenance/v1; NOT a full SLSA/in-toto conformance
validator. No independent OIDC/certificate validation, attestor trust, GitHub
artifact fetching, signing, filesystem, network, device, installation or deploy.
"""
from __future__ import annotations

import base64
import binascii
from hashlib import sha256
import json
import re
from typing import Any, Mapping
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from atlasquant_aion_ci_custody_rotation_external_provenance_gate_v1 import (
    SCHEMA as PREVIOUS_SCHEMA, CUSTODY_READY, PROVENANCE_READY,
    CUSTODY_PROOF_KEYS, PROVENANCE_PROOF_KEYS,
    CUSTODY_PROOF_FALSE, PROVENANCE_PROOF_FALSE,
    CUSTODY_EVIDENCE, PROVENANCE_EVIDENCE,
)

SCHEMA = "ATLASQUANT_AION_CI_DSSE_SLSA_INDEPENDENT_TRUST_PREFLIGHT_V1"
DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
SLSA_PREDICATE_TYPE = "https://slsa.dev/provenance/v1"
READY = "CI_DSSE_ED25519_SLSA_SUBSET_CRYPTO_VERIFIED_UNTRUSTED"
REVIEW_READY = "READY_FOR_REAL_DSSE_ATTESTOR_IDENTITY_SECURITY_REVIEW"
BLOCKED = "BLOCKED"
HEX = re.compile(r"[0-9a-f]{64}\Z")
SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
RUN = re.compile(r"[1-9][0-9]{0,19}\Z")
MAX_PAYLOAD = 32768
MAX_ARTIFACT = 1048576
ENVELOPE_FIELDS = {"payloadType", "payload", "signatures"}
SIGNATURE_FIELDS = {"keyid", "sig"}
STATEMENT_FIELDS = {"_type", "subject", "predicateType", "predicate"}
SUBJECT_FIELDS = {"name", "digest"}
PREDICATE_FIELDS = {"buildDefinition", "runDetails"}
DEFINITION_FIELDS = {"buildType", "externalParameters"}
RUN_DETAILS_FIELDS = {"builder", "metadata"}
BUILDER_FIELDS = {"id"}
METADATA_FIELDS = {"invocationId"}
PARAM_FIELDS = {
    "sourceCommit", "repository", "workflowRef", "issuer", "audience",
    "challengeDigest", "anchorDigest", "registryDigest",
    "custodyCandidateDigest", "builderProofDigest",
    "artifactSubjectDigest", "releaseManifestSha256",
}
EXPECTED_FIELDS = {
    "subject_name", "subject_sha256", "source_commit", "repository",
    "workflow_ref", "issuer", "audience", "builder_id", "build_type",
    "run_id", "challenge_digest", "anchor_digest", "registry_digest",
    "custody_candidate_digest", "builder_proof_digest",
    "artifact_subject_digest", "release_manifest_sha256",
    "expected_signer_key_sha256", "external_policy_digest",
}
CRYPTO_EVIDENCE_FIELDS = (
    "dsse_envelope_digest", "payload_sha256", "public_key_sha256",
    "signature_sha256", "subject_name", "subject_sha256", "source_commit",
    "run_id", "builder_id", "build_type", "repository", "workflow_ref",
    "issuer", "audience", "anchor_digest", "registry_digest",
    "custody_candidate_digest", "builder_proof_digest",
    "artifact_subject_digest", "release_manifest_sha256",
    "challenge_digest", "external_policy_digest",
)
DENIAL_FIELDS = (
    "real_attestor_identity_verified", "authorized_aion_publisher_verified",
    "github_oidc_issuer_verified", "sigstore_chain_verified",
    "transparency_log_inclusion_verified", "slsa_level_attested",
    "in_toto_full_spec_conformance_verified",
    "actual_builder_executed_claimed_run", "real_aion_artifact_fetched",
    "owner_install_approved", "production_release_authorized",
    "owner_device_accessed", "worker_activated", "deploy_executed",
)
CANDIDATE_KEYS = set(CRYPTO_EVIDENCE_FIELDS) | {
    "schema", "state", "blockers", "candidate_digest",
    "dsse_pae_signature_verified_under_supplied_ci_key",
    "synthetic_fixture_only",
} | set(DENIAL_FIELDS)

def _canonical(v: Any) -> bytes:
    return json.dumps(v, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("ascii")

def _hash(data: bytes) -> str:
    return "sha256:" + sha256(data).hexdigest()

def _digest(v: Any) -> str:
    return _hash(_canonical(v))

def _sha(v: Any) -> bool:
    return type(v) is str and SHA.fullmatch(v) is not None

def _m(v: Any) -> dict[str, Any]:
    return dict(v) if isinstance(v, Mapping) else {}

def dsse_pae(payload_type: str, payload: bytes) -> bytes:
    """DSSEv1 byte-length PAE per secure-systems-lab/dsse/envelope.proto."""
    if type(payload_type) is not str or type(payload) is not bytes:
        raise ValueError("DSSE_TYPE_AND_BYTES_REQUIRED")
    pt = payload_type.encode("utf-8")
    if not pt or not payload or len(pt) > 128 or len(payload) > MAX_PAYLOAD:
        raise ValueError("DSSE_PAE_INPUT_OUT_OF_RANGE")
    return (b"DSSEv1 " + str(len(pt)).encode("ascii") + b" " + pt
            + b" " + str(len(payload)).encode("ascii") + b" " + payload)

def _strict_json(payload: bytes) -> Any:
    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in pairs:
            if k in out:
                raise ValueError("DUPLICATE_JSON_FIELD")
            out[k] = v
        return out
    def bad_constant(s: str) -> None:
        raise ValueError("INVALID_JSON_NUMBER:" + s)
    return json.loads(payload.decode("utf-8"), object_pairs_hook=no_duplicates,
                      parse_constant=bad_constant)

def _b64(s: Any) -> bytes:
    if type(s) is not str or not s or len(s) > 55000:
        raise ValueError("BASE64_STRING_INVALID")
    try:
        data = base64.b64decode(s, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("NONCANONICAL_BASE64")
    if base64.b64encode(data).decode("ascii") != s:
        raise ValueError("NONCANONICAL_BASE64")
    return data

def verify_ci_dsse_slsa_subset(
    envelope: Mapping[str, Any] | None,
    public_key: Any,
    expected: Mapping[str, Any] | None,
    artifact_bytes: Any,
) -> dict[str, Any]:
    """Verify real DSSE Ed25519 and strict synthetic SLSA subset, no trust."""
    errors: list[str] = []
    env, ex = _m(envelope), _m(expected)
    if set(env) != ENVELOPE_FIELDS:
        errors.append("DSSE_EXACT_ENVELOPE_FIELDS_REQUIRED")
    if set(ex) != EXPECTED_FIELDS:
        errors.append("EXACT_EXTERNAL_EXPECTATIONS_REQUIRED")
    if env.get("payloadType") != DSSE_PAYLOAD_TYPE:
        errors.append("DSSE_PAYLOAD_TYPE_NOT_ALLOWED")
    signatures = env.get("signatures")
    if type(signatures) is not list or len(signatures) != 1:
        signatures = []
        errors.append("EXACTLY_ONE_DSSE_SIGNATURE_REQUIRED")
    sig_item = _m(signatures[0]) if signatures else {}
    if set(sig_item) != SIGNATURE_FIELDS:
        errors.append("DSSE_SIGNATURE_FIELDS_INVALID")
    if sig_item.get("keyid") != ex.get("expected_signer_key_sha256"):
        errors.append("DSSE_UNTRUSTED_KEYID_MISMATCH")
    if type(public_key) is not bytes or len(public_key) != 32:
        errors.append("ED25519_PUBLIC_KEY_REQUIRED")
        pk_hash = ""
    else:
        pk_hash = _hash(public_key)
        if pk_hash != ex.get("expected_signer_key_sha256"):
            errors.append("EXTERNAL_SIGNER_KEY_PIN_MISMATCH")
    if not _sha(ex.get("expected_signer_key_sha256")):
        errors.append("EXTERNAL_SIGNER_PIN_SHAPE_INVALID")
    for field in ("subject_sha256",):
        if type(ex.get(field)) is not str or not HEX.fullmatch(ex[field]):
            errors.append("SUBJECT_SHA256_FORMAT_INVALID")
    for field in ("challenge_digest", "anchor_digest", "registry_digest",
                  "custody_candidate_digest", "builder_proof_digest",
                  "artifact_subject_digest", "release_manifest_sha256",
                  "external_policy_digest"):
        if not _sha(ex.get(field)):
            errors.append("EXTERNAL_DIGEST_INVALID:" + field)
    if type(ex.get("source_commit")) is not str or not COMMIT.fullmatch(ex["source_commit"]):
        errors.append("SOURCE_COMMIT_INVALID")
    if type(ex.get("run_id")) is not str or not RUN.fullmatch(ex["run_id"]):
        errors.append("RUN_ID_INVALID")
    for field in ("subject_name", "repository", "workflow_ref", "issuer",
                  "audience", "builder_id", "build_type"):
        value = ex.get(field)
        if type(value) is not str or not 1 <= len(value) <= 180 or any(
            c in value for c in ("\x00", "\n", "\r")
        ):
            errors.append("EXTERNAL_IDENTITY_SHAPE_INVALID:" + field)
    payload, sig = b"", b""
    try:
        payload, sig = _b64(env.get("payload")), _b64(sig_item.get("sig"))
    except ValueError:
        errors.append("DSSE_BASE64_DECODE_FAILED")
    if len(payload) > MAX_PAYLOAD or len(sig) != 64:
        errors.append("DSSE_PAYLOAD_OR_SIGNATURE_LENGTH_INVALID")
    statement: dict[str, Any] = {}
    if payload:
        try:
            parsed = _strict_json(payload)
            if type(parsed) is not dict:
                raise ValueError("STATEMENT_NOT_OBJECT")
            statement = parsed
            if _canonical(statement) != payload:
                errors.append("FIXTURE_NONCANONICAL_JSON_BYTES")
        except (UnicodeError, ValueError, TypeError, RecursionError):
            errors.append("DSSE_PAYLOAD_JSON_INVALID")
    else:
        errors.append("DSSE_PAYLOAD_MISSING")
    if set(statement) != STATEMENT_FIELDS:
        errors.append("STATEMENT_EXACT_FIELDS_REQUIRED")
    if statement.get("_type") != STATEMENT_TYPE:
        errors.append("IN_TOTO_STATEMENT_V1_REQUIRED")
    if statement.get("predicateType") != SLSA_PREDICATE_TYPE:
        errors.append("SLSA_PROVENANCE_V1_PREDICATE_REQUIRED")
    subjects = statement.get("subject")
    if type(subjects) is not list or len(subjects) != 1:
        errors.append("ONE_CI_SUBJECT_REQUIRED")
        sub = {}
    else:
        sub = _m(subjects[0])
    if set(sub) != SUBJECT_FIELDS or sub.get("name") != ex.get("subject_name"):
        errors.append("SUBJECT_NAME_OR_SHAPE_INVALID")
    subhash = _m(sub.get("digest"))
    if set(subhash) != {"sha256"} or subhash.get("sha256") != ex.get("subject_sha256"):
        errors.append("SUBJECT_SHA256_MISMATCH")
    predicate = _m(statement.get("predicate"))
    if set(predicate) != PREDICATE_FIELDS:
        errors.append("PREDICATE_EXACT_FIELDS_REQUIRED")
    definition = _m(predicate.get("buildDefinition"))
    details = _m(predicate.get("runDetails"))
    if set(definition) != DEFINITION_FIELDS:
        errors.append("BUILD_DEFINITION_EXACT_FIELDS_REQUIRED")
    if definition.get("buildType") != ex.get("build_type"):
        errors.append("BUILD_TYPE_MISMATCH")
    params = _m(definition.get("externalParameters"))
    if set(params) != PARAM_FIELDS:
        errors.append("EXTERNAL_PARAMETERS_EXACT_FIELDS_REQUIRED")
    pairs = {
        "sourceCommit": "source_commit", "repository": "repository",
        "workflowRef": "workflow_ref", "issuer": "issuer",
        "audience": "audience", "challengeDigest": "challenge_digest",
        "anchorDigest": "anchor_digest", "registryDigest": "registry_digest",
        "custodyCandidateDigest": "custody_candidate_digest",
        "builderProofDigest": "builder_proof_digest",
        "artifactSubjectDigest": "artifact_subject_digest",
        "releaseManifestSha256": "release_manifest_sha256",
    }
    for p, e in pairs.items():
        if params.get(p) != ex.get(e):
            errors.append("BUILD_INPUT_IDENTITY_MISMATCH:" + p)
    if set(details) != RUN_DETAILS_FIELDS:
        errors.append("RUN_DETAILS_EXACT_FIELDS_REQUIRED")
    builder = _m(details.get("builder"))
    metadata = _m(details.get("metadata"))
    if set(builder) != BUILDER_FIELDS or builder.get("id") != ex.get("builder_id"):
        errors.append("BUILDER_ID_MISMATCH")
    if set(metadata) != METADATA_FIELDS or metadata.get("invocationId") != ex.get("run_id"):
        errors.append("BUILD_INVOCATION_ID_MISMATCH")
    if (type(artifact_bytes) is not bytes or not 1 <= len(artifact_bytes) <= MAX_ARTIFACT
        or _hash(artifact_bytes)[7:] != ex.get("subject_sha256")):
        errors.append("ACTUAL_CI_SUBJECT_BYTES_MISMATCH")
    signature_valid = False
    if (not errors and type(public_key) is bytes and len(public_key) == 32):
        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(
                sig, dsse_pae(DSSE_PAYLOAD_TYPE, payload)
            )
            signature_valid = True
        except (ValueError, InvalidSignature):
            errors.append("DSSE_ED25519_SIGNATURE_INVALID")
    material = {
        "dsse_envelope_digest": _digest(env),
        "payload_sha256": _hash(payload), "public_key_sha256": pk_hash,
        "signature_sha256": _hash(sig),
        **{f: ex.get(f) for f in (
            "subject_name", "subject_sha256", "source_commit", "run_id",
            "builder_id", "build_type", "repository", "workflow_ref",
            "issuer", "audience", "anchor_digest", "registry_digest",
            "custody_candidate_digest", "builder_proof_digest",
            "artifact_subject_digest", "release_manifest_sha256",
            "challenge_digest", "external_policy_digest",
        )},
    }
    errors = list(dict.fromkeys(errors))
    return {
        "schema": SCHEMA, "state": READY if not errors else BLOCKED,
        "blockers": errors, **material,
        "candidate_digest": _digest(material) if not errors else "",
        "dsse_pae_signature_verified_under_supplied_ci_key": signature_valid,
        "synthetic_fixture_only": True,
        **{flag: False for flag in DENIAL_FIELDS},
    }

def review_ci_attestation_trust_handoff(
    candidate: Mapping[str, Any] | None,
    custody: Mapping[str, Any] | None,
    provenance: Mapping[str, Any] | None,
    *,
    expected_issuer_policy_digest: Any,
    expected_external_anchor_digest: Any,
    expected_minimum_rotation_epoch: Any,
) -> dict[str, Any]:
    """Shape/consistency review, NOT independent trust-root verification."""
    v, c, p = _m(candidate), _m(custody), _m(provenance)
    errors: list[str] = []
    if set(v) != CANDIDATE_KEYS or v.get("schema") != SCHEMA or v.get("state") != READY or v.get("blockers") != []:
        errors.append("ATTESTATION_CANDIDATE_SHAPE_REQUIRED")
    if v.get("candidate_digest") != _digest({k:v.get(k) for k in CRYPTO_EVIDENCE_FIELDS}):
        errors.append("ATTESTATION_CANDIDATE_TAMPERED")
    if v.get("dsse_pae_signature_verified_under_supplied_ci_key") is not True or v.get("synthetic_fixture_only") is not True:
        errors.append("ONLY_SIGNED_CI_FIXTURE_ALLOWED")
    for flag in DENIAL_FIELDS:
        if v.get(flag) is not False:
            errors.append("ATTESTATION_TRUST_ESCALATION_DENIED:" + flag)
    for proof, role, keys, material_keys, ready, denial in (
        (c, "CUSTODY", CUSTODY_PROOF_KEYS, CUSTODY_EVIDENCE, CUSTODY_READY, CUSTODY_PROOF_FALSE),
        (p, "PROVENANCE", PROVENANCE_PROOF_KEYS, PROVENANCE_EVIDENCE, PROVENANCE_READY, PROVENANCE_PROOF_FALSE),
    ):
        if set(proof) != keys or proof.get("schema") != PREVIOUS_SCHEMA or proof.get("state") != ready or proof.get("blockers") != []:
            errors.append(role + "_PROOF_EXACT_READY_FIELDS_REQUIRED")
        if proof.get("candidate_digest") != _digest({k:proof.get(k) for k in material_keys}):
            errors.append(role + "_PROOF_DIGEST_INVALID")
        if proof.get("synthetic_only") is not True:
            errors.append(role + "_SYNTHETIC_INDICATOR_REQUIRED")
        for flag in denial:
            if proof.get(flag) is not False:
                errors.append(role + "_FALSE_TRUST_CLAIM:" + flag)
    if c.get("anchor_digest") != v.get("anchor_digest") or p.get("anchor_digest") != v.get("anchor_digest") or v.get("anchor_digest") != expected_external_anchor_digest:
        errors.append("ANCHORED_RELEASE_CHAIN_MISMATCH")
    if c.get("registry_digest") != v.get("registry_digest") or p.get("registry_digest") != v.get("registry_digest"):
        errors.append("REGISTRY_CHAIN_MISMATCH")
    if v.get("custody_candidate_digest") != c.get("candidate_digest"):
        errors.append("CUSTODY_CANDIDATE_BINDING_MISMATCH")
    if v.get("builder_proof_digest") != p.get("builder_proof_digest"):
        errors.append("BUILDER_CHAIN_MISMATCH")
    if v.get("source_commit") != p.get("source_commit") or v.get("run_id") != p.get("build_run_id"):
        errors.append("BUILD_RUN_SOURCE_MISMATCH")
    if (v.get("artifact_subject_digest") != p.get("artifact_subject_digest") or
        v.get("release_manifest_sha256") != p.get("release_manifest_sha256")):
        errors.append("RELEASE_SUBJECT_AND_MANIFEST_CHAIN_MISMATCH")
    if v.get("external_policy_digest") != expected_issuer_policy_digest or not _sha(expected_issuer_policy_digest):
        errors.append("EXTERNAL_POLICY_BINDING_MISMATCH")
    if (type(expected_minimum_rotation_epoch) is not int
        or type(c.get("next_epoch")) is not int
        or c.get("next_epoch") < expected_minimum_rotation_epoch
        or expected_minimum_rotation_epoch < 1):
        errors.append("ROTATION_EPOCH_BELOW_EXPECTATION")
    material = {
        "attestation_candidate_digest": v.get("candidate_digest"),
        "custody_candidate_digest": c.get("candidate_digest"),
        "provenance_candidate_digest": p.get("candidate_digest"),
        "expected_external_anchor_digest": expected_external_anchor_digest,
        "expected_issuer_policy_digest": expected_issuer_policy_digest,
        "expected_minimum_rotation_epoch": expected_minimum_rotation_epoch,
    }
    errors = list(dict.fromkeys(errors))
    return {
        "schema": SCHEMA, "state": REVIEW_READY if not errors else BLOCKED,
        "blockers": errors, **material,
        "review_digest": _digest(material) if not errors else "",
        "ci_dsse_crypto_check_passed_untrusted": not errors,
        **{flag: False for flag in (
            "independent_attestor_trusted", "real_oidc_identity_authenticated",
            "authorized_aion_release_verified", "production_root_pinned",
            "verified_official_slsa_build", "real_package_bytes_verified",
            "human_owner_approved_install", "owner_device_accessed",
            "package_installed", "deploy_executed", "worker_activated",
        )},
    }

def dsse_preflight_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA, "ci_only": True, "ephemeral_keys_only": True,
        "dsse_pae_implemented": True,
        "in_toto_slsa_v1_fixture_subset_only": True,
        "real_jwt_oidc_verified": False, "certificate_chain_verified": False,
        "real_attestor_authority_anchored": False,
        "actual_slsa_level_certified": False,
        "full_slsa_spec_conformance": False,
        "external_attestation_fetched": False,
        "real_aion_package_fetched": False,
        "production_root_activated": False,
        "owner_device_accessed": False, "install_authorized": False,
        "production_persistence_enabled": False,
        "deploy_executed": False, "worker_activated": False,
    }
