"""AION Windows Probe Collector + Independent Verifier Contract V1.

Non-executing contract for the two future Windows components required after the
physical-probe plan from #1049:

1. Collector: measures the Windows sandbox and seals raw evidence.
2. Independent verifier: consumes immutable evidence and decides whether each
   measurement can be trusted.

The roles are deliberately separated by source/binary digests and Ed25519
signing identities. This module can verify synthetic release signatures for the
component manifests, but it does not implement or execute a Windows collector or
verifier.

No probe is executed, no file is opened, no process is spawned, no socket is
opened, no build is authorized, and no repository mutation is performed.
"""
from __future__ import annotations

import base64
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atlasquant_aion_windows_sandbox_physical_probe_plan_evidence_v1 import (
    PLAN_SCHEMA,
    PROBE_REQUIREMENTS,
    PROBE_SPECS,
    READY_PLAN_STATE,
)


SCHEMA = "ATLASQUANT_AION_WINDOWS_PROBE_COLLECTOR_INDEPENDENT_VERIFIER_CONTRACT_V1"
COLLECTOR_MANIFEST_SCHEMA = "ATLASQUANT_AION_WINDOWS_PROBE_COLLECTOR_MANIFEST_V1"
COLLECTOR_RELEASE_SCHEMA = "ATLASQUANT_AION_WINDOWS_PROBE_COLLECTOR_RELEASE_ATTESTATION_V1"
VERIFIER_MANIFEST_SCHEMA = "ATLASQUANT_AION_WINDOWS_PROBE_INDEPENDENT_VERIFIER_MANIFEST_V1"
VERIFIER_RELEASE_SCHEMA = "ATLASQUANT_AION_WINDOWS_PROBE_INDEPENDENT_VERIFIER_RELEASE_ATTESTATION_V1"
SEPARATION_SCHEMA = "ATLASQUANT_AION_WINDOWS_PROBE_COLLECTOR_VERIFIER_SEPARATION_V1"
RECEIPT_SCHEMA = "ATLASQUANT_AION_WINDOWS_PROBE_VERIFICATION_RECEIPT_TEMPLATE_V1"
REVIEW_SCHEMA = "ATLASQUANT_AION_WINDOWS_PROBE_COLLECTOR_VERIFIER_IMPLEMENTATION_REVIEW_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_WINDOWS_PROBE_COLLECTOR_VERIFIER_POLICY_V1"

READY_COLLECTOR_STATE = "WINDOWS_PROBE_COLLECTOR_MANIFEST_READY"
READY_VERIFIER_STATE = "WINDOWS_INDEPENDENT_VERIFIER_MANIFEST_READY"
READY_SEPARATION_STATE = "COLLECTOR_VERIFIER_SEPARATION_CONFIRMED"
READY_REVIEW_STATE = "READY_FOR_WINDOWS_COLLECTOR_VERIFIER_IMPLEMENTATION"
BLOCKED_STATE = "BLOCKED"

COLLECTOR_ROLE = "PHYSICAL_EVIDENCE_COLLECTOR_ONLY"
VERIFIER_ROLE = "IMMUTABLE_EVIDENCE_INDEPENDENT_VERIFIER_ONLY"

COLLECTOR_SIGNATURE_CONTEXT = b"ATLASQUANT:AION:WINDOWS_PROBE_COLLECTOR_RELEASE:"
VERIFIER_SIGNATURE_CONTEXT = b"ATLASQUANT:AION:WINDOWS_PROBE_VERIFIER_RELEASE:"

COLLECTOR_ALLOWED_MEASUREMENT_METHODS = tuple(
    PROBE_SPECS[requirement]["measurement_method"]
    for requirement in PROBE_REQUIREMENTS
)

COLLECTOR_FORBIDDEN_CAPABILITIES = (
    "AUTHORIZE_BUILD",
    "START_BUILD",
    "INSTALL_PACKAGE",
    "MUTATE_REPOSITORY",
    "MERGE_PULL_REQUEST",
    "DEPLOY",
    "LOAD_GITHUB_CREDENTIALS",
    "EXECUTE_ARBITRARY_COMMAND",
    "SHELL",
    "POWERSHELL",
    "CMD",
    "CHANGE_PROBE_PLAN",
    "VERIFY_OWN_EVIDENCE",
    "ISSUE_VERIFICATION_RECEIPT",
)

VERIFIER_FORBIDDEN_CAPABILITIES = (
    "EXECUTE_WINDOWS_PROBE",
    "COLLECT_RAW_EVIDENCE",
    "MODIFY_RAW_EVIDENCE",
    "MODIFY_COLLECTOR_EVIDENCE",
    "AUTHORIZE_BUILD",
    "START_BUILD",
    "INSTALL_PACKAGE",
    "MUTATE_REPOSITORY",
    "MERGE_PULL_REQUEST",
    "DEPLOY",
    "LOAD_GITHUB_CREDENTIALS",
    "EXECUTE_ARBITRARY_COMMAND",
    "SHELL",
    "POWERSHELL",
    "CMD",
)

VERIFIER_REQUIRED_CHECKS = (
    "PLAN_BINDING",
    "SANDBOX_PREFLIGHT_BINDING",
    "HOST_BINDING",
    "MEASUREMENT_PLAN_BINDING",
    "COLLECTOR_MANIFEST_BINDING",
    "COLLECTOR_RELEASE_SIGNATURE",
    "COLLECTOR_BINARY_DIGEST",
    "RAW_EVIDENCE_DIGEST",
    "SEQUENCE",
    "EXPECTED_OBSERVATION",
    "NEGATIVE_TEST_OBSERVATION",
    "FRESHNESS_WINDOW",
    "COLLECTOR_IDENTITY",
    "EVIDENCE_IMMUTABILITY",
)

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,239}$")


class CollectorVerifierContractError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _clean(value: Any, limit: int = 1000) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256(value: Any) -> str:
    token = _clean(value, 90)
    return token if _SHA256_RE.fullmatch(token) else ""


def _identity(value: Any, limit: int = 240) -> str:
    if type(value) is not str:
        return ""
    text = _clean(value, limit)
    if text != value or not _ID_RE.fullmatch(text):
        return ""
    return text


def _decode_public_key(public_key_b64: Any, label: str) -> bytes:
    text = _clean(public_key_b64, 8192)
    if not text:
        raise CollectorVerifierContractError(label + "_PUBLIC_KEY_REQUIRED")
    try:
        raw = base64.b64decode(text, validate=True)
    except Exception as exc:
        raise CollectorVerifierContractError(label + "_PUBLIC_KEY_INVALID") from exc
    if len(raw) != 32:
        raise CollectorVerifierContractError(label + "_PUBLIC_KEY_LENGTH_INVALID")
    return raw


def _decode_signature(signature_b64: Any, label: str) -> bytes:
    text = _clean(signature_b64, 8192)
    if not text:
        raise CollectorVerifierContractError(label + "_SIGNATURE_REQUIRED")
    try:
        raw = base64.b64decode(text, validate=True)
    except Exception as exc:
        raise CollectorVerifierContractError(label + "_SIGNATURE_INVALID") from exc
    if len(raw) != 64:
        raise CollectorVerifierContractError(label + "_SIGNATURE_LENGTH_INVALID")
    return raw


def public_key_fingerprint(public_key_b64: Any, *, label: str) -> str:
    raw = _decode_public_key(public_key_b64, label)
    return "sha256:" + sha256(raw).hexdigest()


def _measurement_contract(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    measurements = [
        item
        for item in plan.get("measurements", [])
        if isinstance(item, Mapping)
    ]
    rows: list[dict[str, Any]] = []
    for requirement in PROBE_REQUIREMENTS:
        found = next(
            (
                item
                for item in measurements
                if item.get("requirement") == requirement
            ),
            None,
        )
        if found is None:
            continue
        rows.append(
            {
                "requirement": requirement,
                "sequence": int(found.get("sequence") or 0),
                "measurement_method": found.get("measurement_method"),
                "measurement_plan_digest": _sha256(
                    found.get("measurement_plan_digest")
                ),
                "expected_observation": PROBE_SPECS[requirement][
                    "expected_observation"
                ],
                "negative_test": PROBE_SPECS[requirement]["negative_test"],
                "freshness_seconds": PROBE_SPECS[requirement][
                    "freshness_seconds"
                ],
            }
        )
    return rows


def build_collector_manifest(
    plan: Mapping[str, Any] | None,
    *,
    collector_id: Any,
    collector_source_digest: Any,
    collector_test_digest: Any,
    collector_binary_digest: Any,
    build_provenance_digest: Any,
    package_attestation_digest: Any,
    collector_public_key_b64: Any,
    expected_collector_key_fingerprint: Any,
) -> dict[str, Any]:
    """Build a collector identity/permission contract; never collect evidence."""
    plan_row = dict(plan or {})
    blockers: list[str] = []

    if plan_row.get("schema") != PLAN_SCHEMA:
        blockers.append("PROBE_PLAN_SCHEMA_MISMATCH")
    if plan_row.get("state") != READY_PLAN_STATE:
        blockers.append("READY_PROBE_PLAN_REQUIRED")

    collector = _identity(collector_id, 180)
    if not collector:
        blockers.append("COLLECTOR_ID_REQUIRED")

    digests = {}
    for key, value, label in (
        ("collector_source_digest", collector_source_digest, "COLLECTOR_SOURCE_DIGEST_REQUIRED"),
        ("collector_test_digest", collector_test_digest, "COLLECTOR_TEST_DIGEST_REQUIRED"),
        ("collector_binary_digest", collector_binary_digest, "COLLECTOR_BINARY_DIGEST_REQUIRED"),
        ("build_provenance_digest", build_provenance_digest, "COLLECTOR_BUILD_PROVENANCE_DIGEST_REQUIRED"),
        ("package_attestation_digest", package_attestation_digest, "COLLECTOR_PACKAGE_ATTESTATION_DIGEST_REQUIRED"),
    ):
        digest = _sha256(value)
        digests[key] = digest
        if not digest:
            blockers.append(label)

    try:
        fingerprint = public_key_fingerprint(
            collector_public_key_b64,
            label="COLLECTOR",
        )
    except CollectorVerifierContractError as exc:
        fingerprint = ""
        blockers.append(exc.code)
    expected_fp = _sha256(expected_collector_key_fingerprint)
    if not expected_fp:
        blockers.append("EXPECTED_COLLECTOR_KEY_FINGERPRINT_REQUIRED")
    elif fingerprint and fingerprint != expected_fp:
        blockers.append("COLLECTOR_KEY_FINGERPRINT_MISMATCH")

    contract = _measurement_contract(plan_row)
    if len(contract) != len(PROBE_REQUIREMENTS):
        blockers.append("COLLECTOR_MEASUREMENT_CONTRACT_INCOMPLETE")
    methods = tuple(row["measurement_method"] for row in contract)
    if methods != COLLECTOR_ALLOWED_MEASUREMENT_METHODS:
        blockers.append("COLLECTOR_MEASUREMENT_METHOD_SET_MISMATCH")

    material = {
        "collector_id": collector,
        "role": COLLECTOR_ROLE,
        "probe_plan_digest": _sha256(plan_row.get("probe_plan_digest")),
        "sandbox_preflight_digest": _sha256(
            plan_row.get("sandbox_preflight_digest")
        ),
        "host_binding_digest": _sha256(plan_row.get("host_binding_digest")),
        "plan_collector_manifest_digest": _sha256(
            plan_row.get("collector_manifest_digest")
        ),
        **digests,
        "collector_key_fingerprint": fingerprint,
        "measurement_contract": contract,
        "allowed_measurement_methods": list(COLLECTOR_ALLOWED_MEASUREMENT_METHODS),
        "forbidden_capabilities": list(COLLECTOR_FORBIDDEN_CAPABILITIES),
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": COLLECTOR_MANIFEST_SCHEMA,
        "state": READY_COLLECTOR_STATE if not blockers else BLOCKED_STATE,
        "blockers": blockers,
        **material,
        "collector_manifest_digest": _digest(material) if not blockers else "",
        "may_collect_raw_evidence_in_future_physical_phase": True,
        "may_verify_own_evidence": False,
        "may_issue_verification_receipt": False,
        "may_authorize_build": False,
        "collector_implemented": False,
        "collector_executed": False,
        "evidence_collected": False,
        "process_spawned": False,
        "filesystem_modified": False,
        "network_called": False,
        "build_authorized": False,
        "build_started": False,
    }


def build_verifier_manifest(
    plan: Mapping[str, Any] | None,
    collector_manifest: Mapping[str, Any] | None,
    *,
    verifier_id: Any,
    verifier_source_digest: Any,
    verifier_test_digest: Any,
    verifier_binary_digest: Any,
    raw_evidence_decoder_digest: Any,
    verification_policy_digest: Any,
    trust_policy_digest: Any,
    verifier_public_key_b64: Any,
    expected_verifier_key_fingerprint: Any,
) -> dict[str, Any]:
    """Build the independent verifier contract; never verify real evidence."""
    plan_row = dict(plan or {})
    collector_row = dict(collector_manifest or {})
    blockers: list[str] = []

    if plan_row.get("state") != READY_PLAN_STATE:
        blockers.append("READY_PROBE_PLAN_REQUIRED")
    if collector_row.get("state") != READY_COLLECTOR_STATE:
        blockers.append("READY_COLLECTOR_MANIFEST_REQUIRED")

    verifier = _identity(verifier_id, 180)
    if not verifier:
        blockers.append("VERIFIER_ID_REQUIRED")
    if verifier and verifier == collector_row.get("collector_id"):
        blockers.append("COLLECTOR_VERIFIER_IDENTITY_MUST_DIFFER")

    digests = {}
    for key, value, label in (
        ("verifier_source_digest", verifier_source_digest, "VERIFIER_SOURCE_DIGEST_REQUIRED"),
        ("verifier_test_digest", verifier_test_digest, "VERIFIER_TEST_DIGEST_REQUIRED"),
        ("verifier_binary_digest", verifier_binary_digest, "VERIFIER_BINARY_DIGEST_REQUIRED"),
        ("raw_evidence_decoder_digest", raw_evidence_decoder_digest, "RAW_EVIDENCE_DECODER_DIGEST_REQUIRED"),
        ("verification_policy_digest", verification_policy_digest, "VERIFICATION_POLICY_DIGEST_REQUIRED"),
        ("trust_policy_digest", trust_policy_digest, "VERIFIER_TRUST_POLICY_DIGEST_REQUIRED"),
    ):
        digest = _sha256(value)
        digests[key] = digest
        if not digest:
            blockers.append(label)

    try:
        fingerprint = public_key_fingerprint(
            verifier_public_key_b64,
            label="VERIFIER",
        )
    except CollectorVerifierContractError as exc:
        fingerprint = ""
        blockers.append(exc.code)
    expected_fp = _sha256(expected_verifier_key_fingerprint)
    if not expected_fp:
        blockers.append("EXPECTED_VERIFIER_KEY_FINGERPRINT_REQUIRED")
    elif fingerprint and fingerprint != expected_fp:
        blockers.append("VERIFIER_KEY_FINGERPRINT_MISMATCH")

    if fingerprint and fingerprint == collector_row.get(
        "collector_key_fingerprint"
    ):
        blockers.append("COLLECTOR_VERIFIER_SIGNING_KEYS_MUST_DIFFER")
    if digests.get("verifier_source_digest") == collector_row.get(
        "collector_source_digest"
    ):
        blockers.append("COLLECTOR_VERIFIER_SOURCE_MUST_DIFFER")
    if digests.get("verifier_binary_digest") == collector_row.get(
        "collector_binary_digest"
    ):
        blockers.append("COLLECTOR_VERIFIER_BINARY_MUST_DIFFER")

    material = {
        "verifier_id": verifier,
        "role": VERIFIER_ROLE,
        "probe_plan_digest": _sha256(plan_row.get("probe_plan_digest")),
        "sandbox_preflight_digest": _sha256(
            plan_row.get("sandbox_preflight_digest")
        ),
        "host_binding_digest": _sha256(plan_row.get("host_binding_digest")),
        "collector_manifest_digest": _sha256(
            collector_row.get("collector_manifest_digest")
        ),
        "collector_key_fingerprint": _sha256(
            collector_row.get("collector_key_fingerprint")
        ),
        **digests,
        "verifier_key_fingerprint": fingerprint,
        "required_checks": list(VERIFIER_REQUIRED_CHECKS),
        "forbidden_capabilities": list(VERIFIER_FORBIDDEN_CAPABILITIES),
        "requirements": list(PROBE_REQUIREMENTS),
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": VERIFIER_MANIFEST_SCHEMA,
        "state": READY_VERIFIER_STATE if not blockers else BLOCKED_STATE,
        "blockers": blockers,
        **material,
        "verifier_manifest_digest": _digest(material) if not blockers else "",
        "may_collect_evidence": False,
        "may_modify_evidence": False,
        "may_execute_probe": False,
        "may_authorize_build": False,
        "verifier_implemented": False,
        "verifier_executed": False,
        "evidence_verified": False,
        "verification_receipt_issued": False,
        "process_spawned": False,
        "filesystem_modified": False,
        "network_called": False,
        "build_authorized": False,
        "build_started": False,
    }


def _release_payload(
    *,
    component: str,
    manifest_digest: str,
    source_digest: str,
    test_digest: str,
    binary_digest: str,
    key_fingerprint: str,
) -> dict[str, Any]:
    return {
        "component": component,
        "manifest_digest": manifest_digest,
        "source_digest": source_digest,
        "test_digest": test_digest,
        "binary_digest": binary_digest,
        "key_fingerprint": key_fingerprint,
    }


def _verify_release_signature(
    *,
    component: str,
    manifest_digest: Any,
    source_digest: Any,
    test_digest: Any,
    binary_digest: Any,
    key_fingerprint: Any,
    public_key_b64: Any,
    signature_b64: Any,
    context: bytes,
) -> tuple[list[str], dict[str, Any], bool]:
    blockers: list[str] = []
    try:
        raw_key = _decode_public_key(public_key_b64, component)
        calculated_fp = "sha256:" + sha256(raw_key).hexdigest()
    except CollectorVerifierContractError as exc:
        raw_key = b""
        calculated_fp = ""
        blockers.append(exc.code)

    expected_fp = _sha256(key_fingerprint)
    if not expected_fp:
        blockers.append(component + "_KEY_FINGERPRINT_REQUIRED")
    elif calculated_fp and calculated_fp != expected_fp:
        blockers.append(component + "_KEY_FINGERPRINT_MISMATCH")

    try:
        signature = _decode_signature(signature_b64, component)
    except CollectorVerifierContractError as exc:
        signature = b""
        blockers.append(exc.code)

    payload = _release_payload(
        component=component,
        manifest_digest=_sha256(manifest_digest),
        source_digest=_sha256(source_digest),
        test_digest=_sha256(test_digest),
        binary_digest=_sha256(binary_digest),
        key_fingerprint=expected_fp,
    )
    for field in (
        "manifest_digest",
        "source_digest",
        "test_digest",
        "binary_digest",
        "key_fingerprint",
    ):
        if not payload[field]:
            blockers.append(component + "_RELEASE_" + field.upper() + "_REQUIRED")

    signature_verified = False
    if not blockers and raw_key and signature:
        try:
            Ed25519PublicKey.from_public_bytes(raw_key).verify(
                signature,
                context + _digest(payload).encode("ascii"),
            )
            signature_verified = True
        except InvalidSignature:
            blockers.append(component + "_RELEASE_SIGNATURE_INVALID")
        except Exception:
            blockers.append(component + "_RELEASE_SIGNATURE_VERIFICATION_FAILED")
    return list(dict.fromkeys(blockers)), payload, signature_verified


def attest_collector_release(
    manifest: Mapping[str, Any] | None,
    *,
    collector_public_key_b64: Any,
    signature_b64: Any,
) -> dict[str, Any]:
    row = dict(manifest or {})
    blockers: list[str] = []
    if row.get("state") != READY_COLLECTOR_STATE:
        blockers.append("READY_COLLECTOR_MANIFEST_REQUIRED")

    signature_blockers, payload, verified = _verify_release_signature(
        component="COLLECTOR",
        manifest_digest=row.get("collector_manifest_digest"),
        source_digest=row.get("collector_source_digest"),
        test_digest=row.get("collector_test_digest"),
        binary_digest=row.get("collector_binary_digest"),
        key_fingerprint=row.get("collector_key_fingerprint"),
        public_key_b64=collector_public_key_b64,
        signature_b64=signature_b64,
        context=COLLECTOR_SIGNATURE_CONTEXT,
    )
    blockers.extend(signature_blockers)
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": COLLECTOR_RELEASE_SCHEMA,
        "state": "COLLECTOR_RELEASE_SIGNATURE_VERIFIED"
        if not blockers and verified else BLOCKED_STATE,
        "blockers": blockers,
        **payload,
        "release_payload_digest": _digest(payload),
        "signature_verified": bool(verified and not blockers),
        "collector_executed": False,
        "evidence_collected": False,
        "build_authorized": False,
    }


def attest_verifier_release(
    manifest: Mapping[str, Any] | None,
    *,
    verifier_public_key_b64: Any,
    signature_b64: Any,
) -> dict[str, Any]:
    row = dict(manifest or {})
    blockers: list[str] = []
    if row.get("state") != READY_VERIFIER_STATE:
        blockers.append("READY_VERIFIER_MANIFEST_REQUIRED")

    signature_blockers, payload, verified = _verify_release_signature(
        component="VERIFIER",
        manifest_digest=row.get("verifier_manifest_digest"),
        source_digest=row.get("verifier_source_digest"),
        test_digest=row.get("verifier_test_digest"),
        binary_digest=row.get("verifier_binary_digest"),
        key_fingerprint=row.get("verifier_key_fingerprint"),
        public_key_b64=verifier_public_key_b64,
        signature_b64=signature_b64,
        context=VERIFIER_SIGNATURE_CONTEXT,
    )
    blockers.extend(signature_blockers)
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": VERIFIER_RELEASE_SCHEMA,
        "state": "VERIFIER_RELEASE_SIGNATURE_VERIFIED"
        if not blockers and verified else BLOCKED_STATE,
        "blockers": blockers,
        **payload,
        "release_payload_digest": _digest(payload),
        "signature_verified": bool(verified and not blockers),
        "verifier_executed": False,
        "evidence_verified": False,
        "build_authorized": False,
    }


def build_collector_verifier_separation(
    collector_manifest: Mapping[str, Any] | None,
    collector_release: Mapping[str, Any] | None,
    verifier_manifest: Mapping[str, Any] | None,
    verifier_release: Mapping[str, Any] | None,
    *,
    separate_process_boundary_required: bool,
    separate_writable_state_required: bool,
    verifier_raw_evidence_read_only_required: bool,
) -> dict[str, Any]:
    collector = dict(collector_manifest or {})
    collector_sig = dict(collector_release or {})
    verifier = dict(verifier_manifest or {})
    verifier_sig = dict(verifier_release or {})
    blockers: list[str] = []

    if collector.get("state") != READY_COLLECTOR_STATE:
        blockers.append("READY_COLLECTOR_MANIFEST_REQUIRED")
    if collector_sig.get("state") != "COLLECTOR_RELEASE_SIGNATURE_VERIFIED":
        blockers.append("VERIFIED_COLLECTOR_RELEASE_REQUIRED")
    if verifier.get("state") != READY_VERIFIER_STATE:
        blockers.append("READY_VERIFIER_MANIFEST_REQUIRED")
    if verifier_sig.get("state") != "VERIFIER_RELEASE_SIGNATURE_VERIFIED":
        blockers.append("VERIFIED_VERIFIER_RELEASE_REQUIRED")

    if collector.get("collector_id") == verifier.get("verifier_id"):
        blockers.append("COLLECTOR_VERIFIER_IDENTITY_MUST_DIFFER")
    if collector.get("collector_source_digest") == verifier.get(
        "verifier_source_digest"
    ):
        blockers.append("COLLECTOR_VERIFIER_SOURCE_MUST_DIFFER")
    if collector.get("collector_binary_digest") == verifier.get(
        "verifier_binary_digest"
    ):
        blockers.append("COLLECTOR_VERIFIER_BINARY_MUST_DIFFER")
    if collector.get("collector_key_fingerprint") == verifier.get(
        "verifier_key_fingerprint"
    ):
        blockers.append("COLLECTOR_VERIFIER_SIGNING_KEYS_MUST_DIFFER")

    for label, flag in (
        ("SEPARATE_PROCESS_BOUNDARY_REQUIRED", separate_process_boundary_required),
        ("SEPARATE_WRITABLE_STATE_REQUIRED", separate_writable_state_required),
        (
            "VERIFIER_RAW_EVIDENCE_READ_ONLY_REQUIRED",
            verifier_raw_evidence_read_only_required,
        ),
    ):
        if flag is not True:
            blockers.append(label)

    material = {
        "collector_manifest_digest": _sha256(
            collector.get("collector_manifest_digest")
        ),
        "collector_release_payload_digest": _sha256(
            collector_sig.get("release_payload_digest")
        ),
        "collector_key_fingerprint": _sha256(
            collector.get("collector_key_fingerprint")
        ),
        "verifier_manifest_digest": _sha256(
            verifier.get("verifier_manifest_digest")
        ),
        "verifier_release_payload_digest": _sha256(
            verifier_sig.get("release_payload_digest")
        ),
        "verifier_key_fingerprint": _sha256(
            verifier.get("verifier_key_fingerprint")
        ),
        "separate_process_boundary_required":
            separate_process_boundary_required is True,
        "separate_writable_state_required":
            separate_writable_state_required is True,
        "verifier_raw_evidence_read_only_required":
            verifier_raw_evidence_read_only_required is True,
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": SEPARATION_SCHEMA,
        "state": READY_SEPARATION_STATE if not blockers else BLOCKED_STATE,
        "blockers": blockers,
        **material,
        "separation_contract_digest": _digest(material) if not blockers else "",
        "collector_can_mark_verified": False,
        "verifier_can_collect": False,
        "verifier_can_modify_raw_evidence": False,
        "shared_private_key_allowed": False,
        "shared_binary_allowed": False,
        "shared_writable_state_allowed": False,
        "physical_separation_verified": False,
        "build_authorized": False,
    }


def build_unissued_verification_receipt_template(
    plan: Mapping[str, Any] | None,
    collector_manifest: Mapping[str, Any] | None,
    verifier_manifest: Mapping[str, Any] | None,
    separation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Define verifier output shape with all requirements still unverified."""
    plan_row = dict(plan or {})
    collector = dict(collector_manifest or {})
    verifier = dict(verifier_manifest or {})
    sep = dict(separation or {})
    blockers: list[str] = []

    if plan_row.get("state") != READY_PLAN_STATE:
        blockers.append("READY_PROBE_PLAN_REQUIRED")
    if collector.get("state") != READY_COLLECTOR_STATE:
        blockers.append("READY_COLLECTOR_MANIFEST_REQUIRED")
    if verifier.get("state") != READY_VERIFIER_STATE:
        blockers.append("READY_VERIFIER_MANIFEST_REQUIRED")
    if sep.get("state") != READY_SEPARATION_STATE:
        blockers.append("COLLECTOR_VERIFIER_SEPARATION_REQUIRED")

    requirement_rows = [
        {
            "requirement": requirement,
            "verification_state": "NOT_VERIFIED",
            "verification_blockers": [
                "PHYSICAL_EVIDENCE_NOT_COLLECTED",
                "INDEPENDENT_VERIFIER_NOT_EXECUTED",
            ],
            "evidence_digest": "",
            "verification_detail_digest": "",
        }
        for requirement in PROBE_REQUIREMENTS
    ]
    material = {
        "probe_plan_digest": _sha256(plan_row.get("probe_plan_digest")),
        "sandbox_preflight_digest": _sha256(
            plan_row.get("sandbox_preflight_digest")
        ),
        "host_binding_digest": _sha256(plan_row.get("host_binding_digest")),
        "collector_manifest_digest": _sha256(
            collector.get("collector_manifest_digest")
        ),
        "collector_key_fingerprint": _sha256(
            collector.get("collector_key_fingerprint")
        ),
        "verifier_manifest_digest": _sha256(
            verifier.get("verifier_manifest_digest")
        ),
        "verifier_key_fingerprint": _sha256(
            verifier.get("verifier_key_fingerprint")
        ),
        "separation_contract_digest": _sha256(
            sep.get("separation_contract_digest")
        ),
        "requirements": requirement_rows,
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": RECEIPT_SCHEMA,
        "state": "VERIFICATION_RECEIPT_TEMPLATE_READY_UNISSUED"
        if not blockers else BLOCKED_STATE,
        "blockers": blockers,
        **material,
        "receipt_template_digest": _digest(material) if not blockers else "",
        "verified_total": 0,
        "required_total": len(PROBE_REQUIREMENTS),
        "all_requirements_verified": False,
        "receipt_issued": False,
        "receipt_signed": False,
        "physical_proof_verified": False,
        "windows_sandbox_verified": False,
        "build_authorized": False,
        "build_started": False,
    }


def build_implementation_review(
    plan: Mapping[str, Any] | None,
    collector_manifest: Mapping[str, Any] | None,
    verifier_manifest: Mapping[str, Any] | None,
    separation: Mapping[str, Any] | None,
    receipt_template: Mapping[str, Any] | None,
    *,
    collector_windows_adapter_design_digest: Any,
    verifier_evidence_parser_design_digest: Any,
    verifier_trust_store_design_digest: Any,
    immutable_evidence_handoff_design_digest: Any,
) -> dict[str, Any]:
    plan_row = dict(plan or {})
    collector = dict(collector_manifest or {})
    verifier = dict(verifier_manifest or {})
    sep = dict(separation or {})
    receipt = dict(receipt_template or {})
    blockers: list[str] = []

    expected = (
        (plan_row, READY_PLAN_STATE, "READY_PROBE_PLAN_REQUIRED"),
        (collector, READY_COLLECTOR_STATE, "READY_COLLECTOR_MANIFEST_REQUIRED"),
        (verifier, READY_VERIFIER_STATE, "READY_VERIFIER_MANIFEST_REQUIRED"),
        (sep, READY_SEPARATION_STATE, "COLLECTOR_VERIFIER_SEPARATION_REQUIRED"),
        (
            receipt,
            "VERIFICATION_RECEIPT_TEMPLATE_READY_UNISSUED",
            "UNISSUED_VERIFICATION_RECEIPT_TEMPLATE_REQUIRED",
        ),
    )
    for row, state, label in expected:
        if row.get("state") != state:
            blockers.append(label)

    digests = {}
    for key, value, label in (
        (
            "collector_windows_adapter_design_digest",
            collector_windows_adapter_design_digest,
            "COLLECTOR_WINDOWS_ADAPTER_DESIGN_DIGEST_REQUIRED",
        ),
        (
            "verifier_evidence_parser_design_digest",
            verifier_evidence_parser_design_digest,
            "VERIFIER_EVIDENCE_PARSER_DESIGN_DIGEST_REQUIRED",
        ),
        (
            "verifier_trust_store_design_digest",
            verifier_trust_store_design_digest,
            "VERIFIER_TRUST_STORE_DESIGN_DIGEST_REQUIRED",
        ),
        (
            "immutable_evidence_handoff_design_digest",
            immutable_evidence_handoff_design_digest,
            "IMMUTABLE_EVIDENCE_HANDOFF_DESIGN_DIGEST_REQUIRED",
        ),
    ):
        digest = _sha256(value)
        digests[key] = digest
        if not digest:
            blockers.append(label)

    material = {
        "probe_plan_digest": _sha256(plan_row.get("probe_plan_digest")),
        "collector_manifest_digest": _sha256(
            collector.get("collector_manifest_digest")
        ),
        "verifier_manifest_digest": _sha256(
            verifier.get("verifier_manifest_digest")
        ),
        "separation_contract_digest": _sha256(
            sep.get("separation_contract_digest")
        ),
        "receipt_template_digest": _sha256(
            receipt.get("receipt_template_digest")
        ),
        **digests,
        "next_pc_phase":
            "IMPLEMENT_WINDOWS_COLLECTOR_AND_INDEPENDENT_VERIFIER_WITH_SYNTHETIC_PROBES",
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": REVIEW_SCHEMA,
        "state": READY_REVIEW_STATE if not blockers else BLOCKED_STATE,
        "blockers": blockers,
        **material,
        "implementation_review_digest": _digest(material) if not blockers else "",
        "collector_implemented": False,
        "collector_executed": False,
        "verifier_implemented": False,
        "verifier_executed": False,
        "physical_evidence_collected": False,
        "verification_receipt_issued": False,
        "physical_proof_verified": False,
        "windows_sandbox_verified": False,
        "build_authorized": False,
        "build_started": False,
        "package_built": False,
        "package_installed": False,
    }


def collector_verifier_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "collector_role": COLLECTOR_ROLE,
        "verifier_role": VERIFIER_ROLE,
        "requirements": list(PROBE_REQUIREMENTS),
        "collector_allowed_measurement_methods":
            list(COLLECTOR_ALLOWED_MEASUREMENT_METHODS),
        "collector_forbidden_capabilities":
            list(COLLECTOR_FORBIDDEN_CAPABILITIES),
        "verifier_required_checks": list(VERIFIER_REQUIRED_CHECKS),
        "verifier_forbidden_capabilities":
            list(VERIFIER_FORBIDDEN_CAPABILITIES),
        "collector_and_verifier_ids_must_differ": True,
        "collector_and_verifier_source_must_differ": True,
        "collector_and_verifier_binary_must_differ": True,
        "collector_and_verifier_signing_keys_must_differ": True,
        "collector_release_signature_required": True,
        "verifier_release_signature_required": True,
        "separate_process_boundary_required": True,
        "separate_writable_state_required": True,
        "verifier_raw_evidence_read_only_required": True,
        "collector_can_mark_verified": False,
        "collector_can_issue_verification_receipt": False,
        "verifier_can_collect_evidence": False,
        "verifier_can_modify_raw_evidence": False,
        "verification_receipt_unissued": True,
        "collector_implemented": False,
        "collector_executed": False,
        "verifier_implemented": False,
        "verifier_executed": False,
        "physical_evidence_collected": False,
        "physical_proof_verified": False,
        "windows_sandbox_verified": False,
        "build_authorized": False,
        "build_started": False,
        "package_built": False,
        "package_installed": False,
        "process_spawned": False,
        "filesystem_modified": False,
        "network_called": False,
        "github_api_called": False,
        "live_repository_mutation_authorized": False,
        "live_repository_mutation_performed": False,
        "production_repository_mutation_performed": False,
        "deploy_executed": False,
        "worker_activated": False,
        "provider_activated": False,
        "production_persistence_activated": False,
    }


__all__ = [
    "SCHEMA",
    "COLLECTOR_MANIFEST_SCHEMA",
    "COLLECTOR_RELEASE_SCHEMA",
    "VERIFIER_MANIFEST_SCHEMA",
    "VERIFIER_RELEASE_SCHEMA",
    "SEPARATION_SCHEMA",
    "RECEIPT_SCHEMA",
    "REVIEW_SCHEMA",
    "POLICY_SCHEMA",
    "READY_COLLECTOR_STATE",
    "READY_VERIFIER_STATE",
    "READY_SEPARATION_STATE",
    "READY_REVIEW_STATE",
    "COLLECTOR_ROLE",
    "VERIFIER_ROLE",
    "COLLECTOR_SIGNATURE_CONTEXT",
    "VERIFIER_SIGNATURE_CONTEXT",
    "COLLECTOR_ALLOWED_MEASUREMENT_METHODS",
    "COLLECTOR_FORBIDDEN_CAPABILITIES",
    "VERIFIER_REQUIRED_CHECKS",
    "VERIFIER_FORBIDDEN_CAPABILITIES",
    "CollectorVerifierContractError",
    "public_key_fingerprint",
    "build_collector_manifest",
    "build_verifier_manifest",
    "attest_collector_release",
    "attest_verifier_release",
    "build_collector_verifier_separation",
    "build_unissued_verification_receipt_template",
    "build_implementation_review",
    "collector_verifier_policy",
]
