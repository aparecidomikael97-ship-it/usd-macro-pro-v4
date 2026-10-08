"""AION Windows Authenticode and binary-integrity preflight V1.

Only classifies test observations captured by a CI PowerShell script on an
ephemeral GitHub-hosted Windows runner. Neither a digest nor an Authenticode
result for a Microsoft OS binary establishes provenance for AION artifacts.

No Windows APIs, filesystem, process launch, signing, install, disk writes,
network calls, owner authentication, production trust or deploy in this module.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json
import re

SCHEMA = "ATLASQUANT_AION_WINDOWS_CI_AUTHENTICODE_INTEGRITY_V1"
RELEASE_SCHEMA = "ATLASQUANT_AION_WINDOWS_FUTURE_RELEASE_SIGNER_PIN_PLAN_V1"
READY = "CI_SIGNED_OS_BINARY_AND_TAMPER_CLASSIFIED_UNTRUSTED"
RELEASE_READY = "AION_RELEASE_SIGNER_PIN_PLAN_SHAPE_READY_UNTRUSTED"
BLOCKED = "BLOCKED"
SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
KEYS = (
    "schema", "ci_scope", "artifact_role", "challenge_digest",
    "policy_digest", "verifier_source_digest", "baseline",
    "tampered", "tamper_operation", "tampered_copy_executed",
    "owner_device_accessed", "aion_binary_examined",
    "aion_release_signer_verified", "signed_artifact_installed",
)
RECORD = (
    "role", "binary_sha256", "byte_count", "pe_magic_mz",
    "signature_status", "signer_cert_sha256", "signer_cert_present",
)
RELEASE_FIELDS = (
    "installation_id", "expected_aion_binary_sha256",
    "pinned_aion_signer_certificate_sha256",
    "trusted_publisher_policy_digest", "release_manifest_digest",
    "owner_device_binding_digest", "owner_challenge_digest",
    "canonical_path_policy_digest", "revocation_policy_digest",
    "verifier_binary_manifest_digest",
)
FLAGS_FALSE = (
    "owner_device_accessed", "aion_binary_examined",
    "aion_release_signer_verified", "signed_artifact_installed",
)
POLICY = {
    "schema": SCHEMA,
    "ci_only": True,
    "observed_signature_is_owner_attestation": False,
    "ci_binary_is_aion_artifact": False,
    "ci_signer_is_aion_publisher": False,
    "get_authenticode_status_is_authoritative_release_pin": False,
    "tampered_copy_executed": False,
    "owner_device_accessed": False,
    "aion_installed": False,
    "signer_certificate_is_aion_pinned": False,
    "physical_aion_signature_verified": False,
    "trusted_independent_attestation_issued": False,
    "release_can_install": False,
    "owner_token_consumed": False,
    "install_token_consumed": False,
    "registry_changed": False,
    "acl_changed": False,
    "startup_changed": False,
    "worker_activated": False,
    "deploy_executed": False,
}

def _digest(v: Any) -> str:
    return "sha256:" + sha256(json.dumps(
        v, ensure_ascii=False, separators=(",", ":"), sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()

def _sha(v: Any) -> bool:
    return type(v) is str and SHA.fullmatch(v) is not None

def _map(v: Any) -> dict[str, Any]:
    return dict(v) if isinstance(v, Mapping) else {}

def evaluate_ci_authenticode_fixture(
    fixture: Mapping[str, Any] | None, *,
    expected_challenge_digest: Any,
    expected_policy_digest: Any,
    expected_verifier_source_digest: Any,
) -> dict[str, Any]:
    """Fail-closed envelope review, NOT a trusted issuer/certificate identity."""
    f = _map(fixture)
    errors: list[str] = []
    if set(f) != set(KEYS):
        errors.append("EXACT_CI_ENVELOPE_KEYS_REQUIRED")
    if f.get("schema") != SCHEMA or f.get("ci_scope") != "EPHEMERAL_WINDOWS_GITHUB_PR_RUNNER":
        errors.append("CI_WINDOWS_SCOPING_REQUIRED")
    if f.get("artifact_role") != "CI_SIGNED_WINDOWS_SYSTEM_POWERSHELL":
        errors.append("CI_OS_BINARY_ROLE_REQUIRED")
    for key, value in (
        ("challenge_digest", expected_challenge_digest),
        ("policy_digest", expected_policy_digest),
        ("verifier_source_digest", expected_verifier_source_digest),
    ):
        if not _sha(value) or f.get(key) != value:
            errors.append("EXACT_BINDING_REQUIRED:" + key)
    for field in FLAGS_FALSE:
        if f.get(field) is not False:
            errors.append("FORBIDDEN_TRUST_OR_MUTATION_CLAIM:" + field)
    if f.get("tamper_operation") != "ONE_BYTE_XOR_CI_SCRATCH_NOT_EXECUTED" or f.get("tampered_copy_executed") is not False:
        errors.append("TAMPER_TEST_SCOPE_INVALID")
    b, t = _map(f.get("baseline")), _map(f.get("tampered"))
    for name, row in (("baseline", b), ("tampered", t)):
        if set(row) != set(RECORD):
            errors.append("EXACT_RECORD_KEYS_REQUIRED:" + name)
        if not _sha(row.get("binary_sha256")):
            errors.append("BINARY_HASH_REQUIRED:" + name)
        if type(row.get("byte_count")) is not int or row.get("byte_count") < 512:
            errors.append("BINARY_BYTES_INVALID:" + name)
        if row.get("pe_magic_mz") is not True:
            errors.append("PE_MAGIC_REQUIRED:" + name)
        if type(row.get("signature_status")) is not str or not row.get("signature_status"):
            errors.append("SIGNATURE_STATUS_REQUIRED:" + name)
        if type(row.get("signer_cert_present")) is not bool:
            errors.append("CERT_PRESENCE_SHAPE_INVALID:" + name)
        if row.get("signer_cert_present") is True and not _sha(row.get("signer_cert_sha256")):
            errors.append("CERT_FINGERPRINT_REQUIRED:" + name)
        if row.get("signer_cert_present") is False and row.get("signer_cert_sha256") != "":
            errors.append("UNEXPECTED_CERT_FINGERPRINT:" + name)
    if b.get("role") != "WINDOWS_SYSTEM_POWERSHELL_EXE":
        errors.append("BASELINE_ROLE_INVALID")
    if t.get("role") != "MUTATED_CI_SCRATCH_COPY":
        errors.append("MUTATED_COPY_ROLE_INVALID")
    if b.get("signature_status") != "Valid" or b.get("signer_cert_present") is not True:
        errors.append("BASELINE_AUTHENTICODE_VALID_REQUIRED")
    if t.get("signature_status") == "Valid":
        errors.append("TAMPERED_BINARY_MUST_NOT_VALIDATE")
    if t.get("binary_sha256") == b.get("binary_sha256"):
        errors.append("SINGLE_BYTE_TAMPER_NOT_OBSERVED")
    if t.get("byte_count") != b.get("byte_count"):
        errors.append("TAMPER_BYTE_LENGTH_CHANGED")
    errors = list(dict.fromkeys(errors))
    material = {
        "fixture_digest": _digest({key: f.get(key) for key in KEYS}),
        "expected_challenge_digest": expected_challenge_digest,
        "expected_policy_digest": expected_policy_digest,
        "expected_verifier_source_digest": expected_verifier_source_digest,
        "baseline_binary_sha256": b.get("binary_sha256"),
        "baseline_signer_cert_sha256": b.get("signer_cert_sha256"),
        "tampered_binary_sha256": t.get("binary_sha256"),
        "tampered_signature_status": t.get("signature_status"),
    }
    return {
        "schema": SCHEMA,
        "state": READY if not errors else BLOCKED,
        "blockers": errors,
        **material,
        "review_digest": _digest(material) if not errors else "",
        "real_ci_authenticode_command_passed_shape_only": not errors,
        "ci_signed_system_binary_observed": not errors,
        "ci_tampered_copy_rejected_shape_only": not errors,
        "real_aion_binary_checked": False,
        "real_aion_publisher_verified": False,
        "release_signature_authoritatively_pinned": False,
        "trusted_independent_attestor_used": False,
        "install_ready": False,
        "runtime_healthy_trusted": False,
        "owner_pc_accessed": False,
        "deploy_executed": False,
        "worker_activated": False,
    }

def build_future_aion_release_signer_pin_plan(**fields: Any) -> dict[str, Any]:
    """Future policy shape; never adopts CI-system signer or self-pins a release."""
    errors = []
    if set(fields) != set(RELEASE_FIELDS):
        errors.append("EXACT_RELEASE_PIN_POLICY_FIELDS_REQUIRED")
    if type(fields.get("installation_id")) is not str or not (3 <= len(fields["installation_id"]) <= 180):
        errors.append("INSTALLATION_ID_REQUIRED")
    for key in RELEASE_FIELDS:
        if key != "installation_id" and not _sha(fields.get(key)):
            errors.append("PIN_OR_RELEASE_BINDING_REQUIRED:" + key)
    if (fields.get("expected_aion_binary_sha256") ==
        fields.get("pinned_aion_signer_certificate_sha256")):
        errors.append("CERTIFICATE_AND_BINARY_PIN_COLLISION")
    errors = list(dict.fromkeys(errors))
    material = {key: fields.get(key) for key in RELEASE_FIELDS}
    return {
        "schema": RELEASE_SCHEMA,
        "state": RELEASE_READY if not errors else BLOCKED,
        "blockers": errors,
        **material,
        "release_pin_plan_digest": _digest(material) if not errors else "",
        "publisher_pin_independently_attested": False,
        "pin_source_provenance_trusted": False,
        "revocation_checked_with_trusted_policy": False,
        "owner_identity_attested": False,
        "aion_binary_measured": False,
        "aion_signature_verified": False,
        "signed_release_authorized_to_install": False,
        "owner_authorization_consumed": False,
        "worker_activated": False,
        "deploy_executed": False,
    }

def ci_authenticode_policy() -> dict[str, Any]:
    return dict(POLICY)

__all__ = [
    "SCHEMA", "RELEASE_SCHEMA", "READY", "RELEASE_READY", "BLOCKED",
    "KEYS", "RECORD", "RELEASE_FIELDS", "evaluate_ci_authenticode_fixture",
    "build_future_aion_release_signer_pin_plan", "ci_authenticode_policy",
];
