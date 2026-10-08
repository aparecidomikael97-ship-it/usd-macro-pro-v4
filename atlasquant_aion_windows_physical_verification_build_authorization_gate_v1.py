"""AION Physical Verification -> Build Authorization Gate V1.

Design-only final barrier before any future first production Windows local-agent
build.

This layer deliberately separates:
1. physical sandbox verification,
2. verification-receipt persistence,
3. fresh HUMAN_OWNER build intent,
4. owner-authorization persistence,
5. a later launch gate.

Generic chat text is never build authorization.

The module may verify a synthetic/externally supplied Ed25519 owner signature
over an exact build-authorization request. It does not claim a nonce, persist an
authorization, issue a build token, spawn a build process, open a database, call
network, mutate a repository, deploy, or activate production.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atlasquant_aion_windows_immutable_evidence_receipt_persistence_v1 import (
    READY_STORE_STATE,
    READY_RECEIPT_PERSISTENCE_STATE,
)
from atlasquant_aion_windows_sandbox_physical_probe_plan_evidence_v1 import (
    PROBE_REQUIREMENTS,
)


SCHEMA = "ATLASQUANT_AION_WINDOWS_PHYSICAL_VERIFICATION_BUILD_AUTHORIZATION_GATE_V1"
GATE_CONTRACT_SCHEMA = "ATLASQUANT_AION_WINDOWS_BUILD_AUTHORIZATION_GATE_CONTRACT_V1"
PHYSICAL_CERTIFICATE_SCHEMA = "ATLASQUANT_AION_WINDOWS_PHYSICAL_VERIFICATION_CERTIFICATE_V1"
REQUEST_SCHEMA = "ATLASQUANT_AION_WINDOWS_BUILD_AUTHORIZATION_REQUEST_V1"
OWNER_VERIFICATION_SCHEMA = "ATLASQUANT_AION_WINDOWS_BUILD_OWNER_AUTHORIZATION_VERIFICATION_V1"
AUTH_PERSISTENCE_SCHEMA = "ATLASQUANT_AION_WINDOWS_BUILD_AUTHORIZATION_PERSISTENCE_ATTESTATION_V1"
LAUNCH_GATE_SCHEMA = "ATLASQUANT_AION_WINDOWS_BUILD_LAUNCH_GATE_CANDIDATE_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_WINDOWS_BUILD_AUTHORIZATION_GATE_POLICY_V1"

READY_CONTRACT_STATE = "BUILD_AUTHORIZATION_GATE_CONTRACT_READY"
READY_OWNER_SIGNATURE_STATE = "READY_FOR_EXTERNAL_HUMAN_OWNER_BUILD_SIGNATURE"
OWNER_AUTH_VERIFIED_PENDING_PERSISTENCE = (
    "OWNER_BUILD_AUTH_SIGNATURE_VERIFIED_PENDING_PERSISTENCE"
)
OWNER_DENIAL_VERIFIED = "OWNER_BUILD_DENIAL_SIGNATURE_VERIFIED"
READY_AUTH_PERSISTENCE_SHAPE_STATE = (
    "BUILD_AUTHORIZATION_PERSISTENCE_SHAPE_VALID_BUT_UNTRUSTED"
)
READY_LAUNCH_REVIEW_STATE = "READY_FOR_BUILD_LAUNCH_GATE_PHYSICAL_IMPLEMENTATION"
BLOCKED_STATE = "BLOCKED"

PURPOSE = "HUMAN_OWNER_EXPLICIT_WINDOWS_LOCAL_AGENT_FIRST_PRODUCTION_BUILD"
MECHANISM = "ED25519_EXTERNAL_OWNER_EXECUTION_KEY"
AUTHORIZE_DECISION = "AUTHORIZE_WINDOWS_LOCAL_AGENT_BUILD"
DENY_DECISION = "DENY_WINDOWS_LOCAL_AGENT_BUILD"
DECISIONS = (AUTHORIZE_DECISION, DENY_DECISION)
MAX_AUTHORIZATION_WINDOW_SECONDS = 120
MAX_PHYSICAL_CERTIFICATE_AGE_SECONDS = 60
EXPECTED_VERIFIED_REQUIREMENTS = len(PROBE_REQUIREMENTS)

OWNER_SIGNATURE_CONTEXT = (
    b"ATLASQUANT:AION:WINDOWS_LOCAL_AGENT:BUILD_AUTHORIZATION:"
)

REQUIRED_PHYSICAL_GATE_PROOFS = (
    "ALL_12_PHYSICAL_REQUIREMENTS_VERIFIED",
    "VERIFIER_RECEIPT_SIGNED",
    "VERIFIER_RECEIPT_SIGNATURE_VERIFIED",
    "VERIFICATION_RECEIPT_PERSISTED",
    "RECEIPT_WRITE_CAS_VERIFIED",
    "RECEIPT_READ_AFTER_WRITE_VERIFIED",
    "RECEIPT_REOPEN_VERIFIED",
    "EVIDENCE_CHAIN_REOPEN_VERIFIED",
    "PHYSICAL_CERTIFICATE_FRESH",
    "SAME_HOST_BINDING",
    "SAME_SANDBOX_PREFLIGHT_BINDING",
    "SAME_REPRODUCIBLE_BUILD_RECIPE_BINDING",
    "SAME_OFFLINE_INPUT_PROMOTION_BINDING",
    "SAME_COLLECTOR_MANIFEST_BINDING",
    "SAME_VERIFIER_MANIFEST_BINDING",
    "NO_UNRESOLVED_VERIFICATION_BLOCKERS",
)

REQUIRED_OWNER_AUTH_PROOFS = (
    "EXACT_BUILD_SCOPE_BOUND",
    "HUMAN_OWNER_EXPLICIT_DECISION",
    "ED25519_OWNER_SIGNATURE",
    "EXPECTED_OWNER_KEY_FINGERPRINT",
    "FRESH_NONCE",
    "PERSISTENT_NONCE_REPLAY_GUARD",
    "SINGLE_USE_AUTHORIZATION",
    "AUTHORIZATION_WINDOW_MAX_120_SECONDS",
    "AUTHORIZATION_PERSISTENCE_REQUIRED",
    "AUTHORIZATION_CAS_REQUIRED",
    "AUTHORIZATION_READ_AFTER_WRITE_REQUIRED",
    "AUTHORIZATION_REOPEN_REQUIRED",
    "GENERIC_CHAT_REJECTED",
)

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,239}$")
_NONCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{15,255}$")


class BuildAuthorizationGateError(ValueError):
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


def _aware(value: Any, label: str) -> datetime:
    try:
        if isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception as exc:
        raise BuildAuthorizationGateError(label + "_INVALID") from exc
    if dt.tzinfo is None:
        raise BuildAuthorizationGateError(label + "_TIMEZONE_REQUIRED")
    return dt.astimezone(timezone.utc)


def _public_key_bytes(public_key_b64: Any) -> bytes:
    text = _clean(public_key_b64, 8192)
    if not text:
        raise BuildAuthorizationGateError("OWNER_PUBLIC_KEY_REQUIRED")
    try:
        raw = base64.b64decode(text, validate=True)
    except Exception as exc:
        raise BuildAuthorizationGateError("OWNER_PUBLIC_KEY_INVALID") from exc
    if len(raw) != 32:
        raise BuildAuthorizationGateError("OWNER_PUBLIC_KEY_LENGTH_INVALID")
    return raw


def owner_key_fingerprint(public_key_b64: Any) -> str:
    return "sha256:" + sha256(_public_key_bytes(public_key_b64)).hexdigest()


def _signature_bytes(signature_b64: Any) -> bytes:
    text = _clean(signature_b64, 8192)
    if not text:
        raise BuildAuthorizationGateError("OWNER_SIGNATURE_REQUIRED")
    try:
        raw = base64.b64decode(text, validate=True)
    except Exception as exc:
        raise BuildAuthorizationGateError("OWNER_SIGNATURE_INVALID") from exc
    if len(raw) != 64:
        raise BuildAuthorizationGateError("OWNER_SIGNATURE_LENGTH_INVALID")
    return raw


def build_gate_contract(
    evidence_store_contract: Mapping[str, Any] | None,
    receipt_persistence_contract: Mapping[str, Any] | None,
    *,
    reproducible_build_recipe_digest: Any,
    offline_input_promotion_digest: Any,
    sandbox_preflight_digest: Any,
    package_manifest_digest: Any,
    package_attestation_policy_digest: Any,
    owner_binding_digest: Any,
) -> dict[str, Any]:
    """Define the final barrier, but grant no authority."""
    store = dict(evidence_store_contract or {})
    receipt = dict(receipt_persistence_contract or {})
    blockers: list[str] = []

    if store.get("state") != READY_STORE_STATE:
        blockers.append("READY_EVIDENCE_STORE_CONTRACT_REQUIRED")
    if receipt.get("state") != READY_RECEIPT_PERSISTENCE_STATE:
        blockers.append("READY_RECEIPT_PERSISTENCE_CONTRACT_REQUIRED")
    if receipt.get("receipt_issued") is not False:
        blockers.append("CURRENT_RECEIPT_MUST_REMAIN_UNISSUED")
    if receipt.get("receipt_persisted") is not False:
        blockers.append("CURRENT_RECEIPT_MUST_REMAIN_UNPERSISTED")

    digests = {}
    for key, value, label in (
        (
            "reproducible_build_recipe_digest",
            reproducible_build_recipe_digest,
            "REPRODUCIBLE_BUILD_RECIPE_DIGEST_REQUIRED",
        ),
        (
            "offline_input_promotion_digest",
            offline_input_promotion_digest,
            "OFFLINE_INPUT_PROMOTION_DIGEST_REQUIRED",
        ),
        (
            "sandbox_preflight_digest",
            sandbox_preflight_digest,
            "SANDBOX_PREFLIGHT_DIGEST_REQUIRED",
        ),
        (
            "package_manifest_digest",
            package_manifest_digest,
            "PACKAGE_MANIFEST_DIGEST_REQUIRED",
        ),
        (
            "package_attestation_policy_digest",
            package_attestation_policy_digest,
            "PACKAGE_ATTESTATION_POLICY_DIGEST_REQUIRED",
        ),
        (
            "owner_binding_digest",
            owner_binding_digest,
            "OWNER_BINDING_DIGEST_REQUIRED",
        ),
    ):
        digest = _sha256(value)
        digests[key] = digest
        if not digest:
            blockers.append(label)

    material = {
        "purpose": PURPOSE,
        "mechanism": MECHANISM,
        "evidence_store_contract_digest": _sha256(
            store.get("store_contract_digest")
        ),
        "receipt_persistence_contract_digest": _sha256(
            receipt.get("receipt_persistence_contract_digest")
        ),
        **digests,
        "required_physical_gate_proofs": list(REQUIRED_PHYSICAL_GATE_PROOFS),
        "required_owner_auth_proofs": list(REQUIRED_OWNER_AUTH_PROOFS),
        "verified_requirement_count_required": EXPECTED_VERIFIED_REQUIREMENTS,
        "max_physical_certificate_age_seconds":
            MAX_PHYSICAL_CERTIFICATE_AGE_SECONDS,
        "max_owner_authorization_window_seconds":
            MAX_AUTHORIZATION_WINDOW_SECONDS,
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": GATE_CONTRACT_SCHEMA,
        "state": READY_CONTRACT_STATE if not blockers else BLOCKED_STATE,
        "blockers": blockers,
        **material,
        "gate_contract_digest": _digest(material) if not blockers else "",
        "generic_chat_is_build_authorization": False,
        "owner_authorization_must_be_separate": True,
        "owner_authorization_must_be_fresh": True,
        "owner_authorization_must_be_single_use": True,
        "physical_certificate_required": True,
        "signed_persisted_receipt_required": True,
        "receipt_reopen_required": True,
        "evidence_chain_reopen_required": True,
        "build_authorized": False,
        "build_token_issued": False,
        "build_started": False,
        "process_spawned": False,
        "filesystem_modified": False,
        "network_called": False,
    }


def validate_physical_certificate_shape(
    gate_contract: Mapping[str, Any] | None,
    certificate: Mapping[str, Any] | None,
    *,
    now: Any,
) -> dict[str, Any]:
    """Validate future certificate shape while refusing to trust physical truth."""
    gate = dict(gate_contract or {})
    cert = dict(certificate or {})
    blockers: list[str] = []

    if gate.get("state") != READY_CONTRACT_STATE:
        blockers.append("READY_BUILD_AUTHORIZATION_GATE_CONTRACT_REQUIRED")
    if cert.get("schema") != PHYSICAL_CERTIFICATE_SCHEMA:
        blockers.append("PHYSICAL_CERTIFICATE_SCHEMA_MISMATCH")
    if cert.get("state") != "PHYSICAL_VERIFICATION_CERTIFICATE_VERIFIED":
        blockers.append("VERIFIED_PHYSICAL_CERTIFICATE_STATE_REQUIRED")

    required_equal = (
        ("reproducible_build_recipe_digest", "PHYSICAL_CERTIFICATE_RECIPE_MISMATCH"),
        ("offline_input_promotion_digest", "PHYSICAL_CERTIFICATE_INPUT_PROMOTION_MISMATCH"),
        ("sandbox_preflight_digest", "PHYSICAL_CERTIFICATE_SANDBOX_PREFLIGHT_MISMATCH"),
        ("owner_binding_digest", "PHYSICAL_CERTIFICATE_OWNER_BINDING_MISMATCH"),
    )
    for key, label in required_equal:
        if _sha256(cert.get(key)) != _sha256(gate.get(key)):
            blockers.append(label)

    for key, label in (
        ("verification_receipt_digest", "VERIFICATION_RECEIPT_DIGEST_REQUIRED"),
        ("verification_receipt_signature_digest", "VERIFICATION_RECEIPT_SIGNATURE_DIGEST_REQUIRED"),
        ("receipt_persistence_attestation_digest", "RECEIPT_PERSISTENCE_ATTESTATION_DIGEST_REQUIRED"),
        ("receipt_reopen_observation_digest", "RECEIPT_REOPEN_OBSERVATION_DIGEST_REQUIRED"),
        ("evidence_chain_digest", "EVIDENCE_CHAIN_DIGEST_REQUIRED"),
        ("evidence_chain_reopen_observation_digest", "EVIDENCE_CHAIN_REOPEN_OBSERVATION_DIGEST_REQUIRED"),
        ("collector_manifest_digest", "COLLECTOR_MANIFEST_DIGEST_REQUIRED"),
        ("verifier_manifest_digest", "VERIFIER_MANIFEST_DIGEST_REQUIRED"),
        ("host_binding_digest", "HOST_BINDING_DIGEST_REQUIRED"),
    ):
        if not _sha256(cert.get(key)):
            blockers.append(label)

    if int(cert.get("verified_total") or -1) != EXPECTED_VERIFIED_REQUIREMENTS:
        blockers.append("ALL_12_PHYSICAL_REQUIREMENTS_MUST_BE_VERIFIED")
    if int(cert.get("required_total") or -1) != EXPECTED_VERIFIED_REQUIREMENTS:
        blockers.append("PHYSICAL_CERTIFICATE_REQUIRED_TOTAL_INVALID")

    for field, label in (
        ("all_requirements_verified", "ALL_REQUIREMENTS_VERIFIED_REQUIRED"),
        ("receipt_signature_verified", "VERIFIER_RECEIPT_SIGNATURE_VERIFICATION_REQUIRED"),
        ("receipt_persisted_verified", "VERIFICATION_RECEIPT_PERSISTENCE_REQUIRED"),
        ("receipt_cas_verified", "RECEIPT_CAS_VERIFICATION_REQUIRED"),
        ("receipt_read_after_write_verified", "RECEIPT_READ_AFTER_WRITE_REQUIRED"),
        ("receipt_reopen_verified", "RECEIPT_REOPEN_VERIFICATION_REQUIRED"),
        ("evidence_chain_reopen_verified", "EVIDENCE_CHAIN_REOPEN_VERIFICATION_REQUIRED"),
        ("freshness_verified", "PHYSICAL_CERTIFICATE_FRESHNESS_REQUIRED"),
        ("no_unresolved_blockers", "NO_UNRESOLVED_PHYSICAL_VERIFICATION_BLOCKERS_REQUIRED"),
    ):
        if cert.get(field) is not True:
            blockers.append(label)

    try:
        issued = _aware(cert.get("issued_at"), "PHYSICAL_CERTIFICATE_ISSUED_AT")
        current = _aware(now, "NOW")
        age = (current - issued).total_seconds()
        if age < 0:
            blockers.append("PHYSICAL_CERTIFICATE_FROM_FUTURE")
        if age > MAX_PHYSICAL_CERTIFICATE_AGE_SECONDS:
            blockers.append("PHYSICAL_CERTIFICATE_STALE")
    except BuildAuthorizationGateError as exc:
        issued = None
        current = None
        blockers.append(exc.code)

    blockers = list(dict.fromkeys(blockers))
    material = {
        "gate_contract_digest": _sha256(gate.get("gate_contract_digest")),
        "certificate_digest": _sha256(cert.get("certificate_digest")),
        "verification_receipt_digest": _sha256(
            cert.get("verification_receipt_digest")
        ),
        "receipt_persistence_attestation_digest": _sha256(
            cert.get("receipt_persistence_attestation_digest")
        ),
        "evidence_chain_digest": _sha256(cert.get("evidence_chain_digest")),
        "host_binding_digest": _sha256(cert.get("host_binding_digest")),
        "issued_at": issued.isoformat() if issued else "",
        "checked_at": current.isoformat() if current else "",
    }
    return {
        "schema": PHYSICAL_CERTIFICATE_SCHEMA,
        "state": (
            "PHYSICAL_CERTIFICATE_SHAPE_VALID_BUT_EXTERNAL_TRUST_REQUIRED"
            if not blockers
            else BLOCKED_STATE
        ),
        "blockers": blockers,
        **material,
        "certificate_shape_valid": not blockers,
        "physical_truth_trusted_by_this_module": False,
        "build_authorized": False,
    }


def build_owner_authorization_request(
    gate_contract: Mapping[str, Any] | None,
    physical_certificate: Mapping[str, Any] | None,
    *,
    authorization_id: Any,
    decision: Any,
    nonce: Any,
    owner_public_key_b64: Any,
    expected_owner_key_fingerprint: Any,
    issued_at: Any,
    expires_at: Any,
    now: Any,
) -> dict[str, Any]:
    """Create exact material for a separate HUMAN_OWNER signature ceremony."""
    gate = dict(gate_contract or {})
    cert = dict(physical_certificate or {})
    blockers: list[str] = []

    cert_review = validate_physical_certificate_shape(gate, cert, now=now)
    if cert_review.get("state") != (
        "PHYSICAL_CERTIFICATE_SHAPE_VALID_BUT_EXTERNAL_TRUST_REQUIRED"
    ):
        blockers.append("PHYSICAL_CERTIFICATE_SHAPE_REQUIRED")

    auth_id = _identity(authorization_id, 180)
    if not auth_id:
        blockers.append("BUILD_AUTHORIZATION_ID_REQUIRED")

    decision_name = _clean(decision, 80).upper()
    if decision_name not in DECISIONS:
        blockers.append("BUILD_AUTHORIZATION_DECISION_INVALID")

    nonce_value = _clean(nonce, 280)
    if not _NONCE_RE.fullmatch(nonce_value):
        blockers.append("BUILD_AUTHORIZATION_NONCE_INVALID")

    try:
        fingerprint = owner_key_fingerprint(owner_public_key_b64)
    except BuildAuthorizationGateError as exc:
        fingerprint = ""
        blockers.append(exc.code)
    expected_fp = _sha256(expected_owner_key_fingerprint)
    if not expected_fp:
        blockers.append("EXPECTED_OWNER_KEY_FINGERPRINT_REQUIRED")
    elif fingerprint and fingerprint != expected_fp:
        blockers.append("OWNER_KEY_FINGERPRINT_MISMATCH")

    try:
        issued = _aware(issued_at, "BUILD_AUTH_ISSUED_AT")
        expires = _aware(expires_at, "BUILD_AUTH_EXPIRES_AT")
        current = _aware(now, "NOW")
        window = (expires - issued).total_seconds()
        if window <= 0:
            blockers.append("BUILD_AUTHORIZATION_WINDOW_INVALID")
        if window > MAX_AUTHORIZATION_WINDOW_SECONDS:
            blockers.append("BUILD_AUTHORIZATION_WINDOW_TOO_LONG")
        if current < issued:
            blockers.append("BUILD_AUTHORIZATION_NOT_YET_VALID")
        if current >= expires:
            blockers.append("BUILD_AUTHORIZATION_EXPIRED")
    except BuildAuthorizationGateError as exc:
        issued = None
        expires = None
        current = None
        blockers.append(exc.code)

    body = {
        "schema": REQUEST_SCHEMA,
        "authorization_id": auth_id,
        "purpose": PURPOSE,
        "mechanism": MECHANISM,
        "decision": decision_name,
        "gate_contract_digest": _sha256(gate.get("gate_contract_digest")),
        "physical_certificate_digest": _sha256(cert.get("certificate_digest")),
        "verification_receipt_digest": _sha256(
            cert.get("verification_receipt_digest")
        ),
        "receipt_persistence_attestation_digest": _sha256(
            cert.get("receipt_persistence_attestation_digest")
        ),
        "evidence_chain_digest": _sha256(cert.get("evidence_chain_digest")),
        "reproducible_build_recipe_digest": _sha256(
            gate.get("reproducible_build_recipe_digest")
        ),
        "offline_input_promotion_digest": _sha256(
            gate.get("offline_input_promotion_digest")
        ),
        "sandbox_preflight_digest": _sha256(
            gate.get("sandbox_preflight_digest")
        ),
        "package_manifest_digest": _sha256(
            gate.get("package_manifest_digest")
        ),
        "package_attestation_policy_digest": _sha256(
            gate.get("package_attestation_policy_digest")
        ),
        "owner_binding_digest": _sha256(gate.get("owner_binding_digest")),
        "owner_public_key_fingerprint": fingerprint,
        "nonce": nonce_value,
        "issued_at": issued.isoformat() if issued else "",
        "expires_at": expires.isoformat() if expires else "",
        "generic_chat_instruction_accepted_as_build_authorization": False,
        "build_authorized": False,
        "build_started": False,
    }
    blockers = list(dict.fromkeys(blockers))
    request_digest = _digest(body) if not blockers else ""
    return {
        "schema": REQUEST_SCHEMA,
        "state": READY_OWNER_SIGNATURE_STATE if not blockers else BLOCKED_STATE,
        "blockers": blockers,
        "request": body if not blockers else {},
        "request_digest": request_digest,
        "digest_to_sign": request_digest,
        "owner_signature_verified": False,
        "nonce_claimed": False,
        "authorization_persisted": False,
        "authorization_consumed": False,
        "build_authorized": False,
        "build_token_issued": False,
        "build_started": False,
    }


def verify_owner_authorization_signature(
    request_result: Mapping[str, Any] | None,
    *,
    owner_public_key_b64: Any,
    signature_b64: Any,
    expected_owner_key_fingerprint: Any,
    now: Any,
) -> dict[str, Any]:
    """Verify owner signature only. Nonce/persistence remain separate."""
    result = dict(request_result or {})
    blockers: list[str] = []

    if result.get("state") != READY_OWNER_SIGNATURE_STATE:
        blockers.append("READY_OWNER_SIGNATURE_REQUEST_REQUIRED")
    request = dict(result.get("request") or {})
    if request.get("schema") != REQUEST_SCHEMA:
        blockers.append("BUILD_AUTHORIZATION_REQUEST_SCHEMA_MISMATCH")

    supplied_digest = _sha256(result.get("request_digest"))
    expected_digest = _digest(request) if request else ""
    if not supplied_digest or supplied_digest != expected_digest:
        blockers.append("BUILD_AUTHORIZATION_REQUEST_DIGEST_MISMATCH")

    try:
        raw_key = _public_key_bytes(owner_public_key_b64)
        fingerprint = "sha256:" + sha256(raw_key).hexdigest()
    except BuildAuthorizationGateError as exc:
        raw_key = b""
        fingerprint = ""
        blockers.append(exc.code)

    expected_fp = _sha256(expected_owner_key_fingerprint)
    if not expected_fp:
        blockers.append("EXPECTED_OWNER_KEY_FINGERPRINT_REQUIRED")
    elif fingerprint and fingerprint != expected_fp:
        blockers.append("OWNER_KEY_FINGERPRINT_MISMATCH")
    if fingerprint and fingerprint != _sha256(
        request.get("owner_public_key_fingerprint")
    ):
        blockers.append("OWNER_KEY_REQUEST_FINGERPRINT_MISMATCH")

    try:
        current = _aware(now, "NOW")
        issued = _aware(request.get("issued_at"), "BUILD_AUTH_ISSUED_AT")
        expires = _aware(request.get("expires_at"), "BUILD_AUTH_EXPIRES_AT")
        if current < issued:
            blockers.append("BUILD_AUTHORIZATION_NOT_YET_VALID")
        if current >= expires:
            blockers.append("BUILD_AUTHORIZATION_EXPIRED")
    except BuildAuthorizationGateError as exc:
        blockers.append(exc.code)

    signature_verified = False
    try:
        signature = _signature_bytes(signature_b64)
        if raw_key and request:
            Ed25519PublicKey.from_public_bytes(raw_key).verify(
                signature,
                OWNER_SIGNATURE_CONTEXT + expected_digest.encode("ascii"),
            )
            signature_verified = True
    except (BuildAuthorizationGateError, InvalidSignature):
        blockers.append("OWNER_BUILD_AUTHORIZATION_SIGNATURE_INVALID")
    except Exception:
        blockers.append("OWNER_BUILD_AUTHORIZATION_SIGNATURE_VERIFICATION_FAILED")

    decision = request.get("decision")
    if decision not in DECISIONS:
        blockers.append("BUILD_AUTHORIZATION_DECISION_INVALID")

    blockers = list(dict.fromkeys(blockers))
    authorize = (
        not blockers
        and signature_verified
        and decision == AUTHORIZE_DECISION
    )
    deny = (
        not blockers
        and signature_verified
        and decision == DENY_DECISION
    )
    material = {
        "request_digest": expected_digest if not blockers else supplied_digest,
        "authorization_id": request.get("authorization_id"),
        "purpose": request.get("purpose"),
        "decision": decision,
        "owner_binding_digest": _sha256(request.get("owner_binding_digest")),
        "owner_public_key_fingerprint": fingerprint,
        "nonce_digest": (
            "sha256:" + sha256(str(request.get("nonce", "")).encode("utf-8")).hexdigest()
            if request.get("nonce")
            else ""
        ),
        "gate_contract_digest": _sha256(request.get("gate_contract_digest")),
        "physical_certificate_digest": _sha256(
            request.get("physical_certificate_digest")
        ),
        "verification_receipt_digest": _sha256(
            request.get("verification_receipt_digest")
        ),
        "signature_verified": signature_verified,
    }
    return {
        "schema": OWNER_VERIFICATION_SCHEMA,
        "state": (
            OWNER_AUTH_VERIFIED_PENDING_PERSISTENCE
            if authorize
            else OWNER_DENIAL_VERIFIED
            if deny
            else BLOCKED_STATE
        ),
        "blockers": blockers,
        **material,
        "owner_authorization_verification_digest": (
            _digest(material) if not blockers else ""
        ),
        "owner_identity_cryptographically_bound": signature_verified,
        "owner_signature_verified": signature_verified,
        "authorization_intent_verified": authorize,
        "denial_intent_verified": deny,
        "generic_chat_instruction_accepted_as_build_authorization": False,
        "nonce_claimed": False,
        "persistent_nonce_replay_guard_verified": False,
        "authorization_persisted": False,
        "authorization_consumed": False,
        "build_authorized": False,
        "build_token_issued": False,
        "build_started": False,
    }


def validate_authorization_persistence_shape(
    owner_verification: Mapping[str, Any] | None,
    *,
    nonce_registry_record_digest: Any,
    authorization_record_digest: Any,
    writer_manifest_digest: Any,
    write_receipt_digest: Any,
    cas_observation_digest: Any,
    read_after_write_observation_digest: Any,
    reopen_observation_digest: Any,
    persistent_nonce_replay_guard_observation_digest: Any,
    nonce_single_use_observation_digest: Any,
    authorization_consumed: bool,
    caller_claims_persistence_verified: bool = False,
) -> dict[str, Any]:
    """Validate persistence-attestation shape without trusting persistence."""
    owner = dict(owner_verification or {})
    blockers: list[str] = []

    if owner.get("state") != OWNER_AUTH_VERIFIED_PENDING_PERSISTENCE:
        blockers.append("VERIFIED_OWNER_BUILD_AUTHORIZATION_REQUIRED")
    if owner.get("authorization_intent_verified") is not True:
        blockers.append("OWNER_BUILD_AUTHORIZATION_INTENT_REQUIRED")
    if authorization_consumed is not False:
        blockers.append("BUILD_AUTHORIZATION_MUST_BE_UNCONSUMED")

    values = {}
    for key, value, label in (
        ("nonce_registry_record_digest", nonce_registry_record_digest, "NONCE_REGISTRY_RECORD_DIGEST_REQUIRED"),
        ("authorization_record_digest", authorization_record_digest, "AUTHORIZATION_RECORD_DIGEST_REQUIRED"),
        ("writer_manifest_digest", writer_manifest_digest, "AUTHORIZATION_WRITER_MANIFEST_DIGEST_REQUIRED"),
        ("write_receipt_digest", write_receipt_digest, "AUTHORIZATION_WRITE_RECEIPT_DIGEST_REQUIRED"),
        ("cas_observation_digest", cas_observation_digest, "AUTHORIZATION_CAS_OBSERVATION_DIGEST_REQUIRED"),
        ("read_after_write_observation_digest", read_after_write_observation_digest, "AUTHORIZATION_READ_AFTER_WRITE_DIGEST_REQUIRED"),
        ("reopen_observation_digest", reopen_observation_digest, "AUTHORIZATION_REOPEN_OBSERVATION_DIGEST_REQUIRED"),
        (
            "persistent_nonce_replay_guard_observation_digest",
            persistent_nonce_replay_guard_observation_digest,
            "PERSISTENT_NONCE_REPLAY_GUARD_OBSERVATION_DIGEST_REQUIRED",
        ),
        (
            "nonce_single_use_observation_digest",
            nonce_single_use_observation_digest,
            "NONCE_SINGLE_USE_OBSERVATION_DIGEST_REQUIRED",
        ),
    ):
        digest = _sha256(value)
        values[key] = digest
        if not digest:
            blockers.append(label)

    if caller_claims_persistence_verified is True:
        blockers.append("CALLER_AUTHORIZATION_PERSISTENCE_CLAIM_NOT_TRUSTED")

    material = {
        "owner_authorization_verification_digest": _sha256(
            owner.get("owner_authorization_verification_digest")
        ),
        "request_digest": _sha256(owner.get("request_digest")),
        "nonce_digest": _sha256(owner.get("nonce_digest")),
        **values,
        "authorization_consumed": False,
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": AUTH_PERSISTENCE_SCHEMA,
        "state": READY_AUTH_PERSISTENCE_SHAPE_STATE
        if not blockers else BLOCKED_STATE,
        "blockers": blockers,
        **material,
        "authorization_persistence_candidate_digest": (
            _digest(material) if not blockers else ""
        ),
        "shape_valid": not blockers,
        "nonce_claimed_trusted": False,
        "persistent_nonce_replay_guard_verified": False,
        "nonce_single_use_verified": False,
        "authorization_persisted_trusted": False,
        "cas_verified": False,
        "read_after_write_verified": False,
        "reopen_verified": False,
        "authorization_consumed": False,
        "build_authorized": False,
        "build_token_issued": False,
        "build_started": False,
    }


def build_launch_gate_implementation_review(
    gate_contract: Mapping[str, Any] | None,
    *,
    physical_certificate_verifier_design_digest: Any,
    owner_nonce_registry_design_digest: Any,
    authorization_writer_design_digest: Any,
    launch_token_design_digest: Any,
    prelaunch_revalidation_design_digest: Any,
) -> dict[str, Any]:
    """Close the design while keeping the launch gate physically absent."""
    gate = dict(gate_contract or {})
    blockers: list[str] = []

    if gate.get("state") != READY_CONTRACT_STATE:
        blockers.append("READY_BUILD_AUTHORIZATION_GATE_CONTRACT_REQUIRED")

    digests = {}
    for key, value, label in (
        (
            "physical_certificate_verifier_design_digest",
            physical_certificate_verifier_design_digest,
            "PHYSICAL_CERTIFICATE_VERIFIER_DESIGN_DIGEST_REQUIRED",
        ),
        (
            "owner_nonce_registry_design_digest",
            owner_nonce_registry_design_digest,
            "OWNER_NONCE_REGISTRY_DESIGN_DIGEST_REQUIRED",
        ),
        (
            "authorization_writer_design_digest",
            authorization_writer_design_digest,
            "AUTHORIZATION_WRITER_DESIGN_DIGEST_REQUIRED",
        ),
        (
            "launch_token_design_digest",
            launch_token_design_digest,
            "LAUNCH_TOKEN_DESIGN_DIGEST_REQUIRED",
        ),
        (
            "prelaunch_revalidation_design_digest",
            prelaunch_revalidation_design_digest,
            "PRELAUNCH_REVALIDATION_DESIGN_DIGEST_REQUIRED",
        ),
    ):
        digest = _sha256(value)
        digests[key] = digest
        if not digest:
            blockers.append(label)

    material = {
        "gate_contract_digest": _sha256(gate.get("gate_contract_digest")),
        **digests,
        "next_pc_phase":
            "IMPLEMENT_PHYSICAL_VERIFICATION_AND_FRESH_OWNER_BUILD_AUTHORIZATION_GATE",
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": LAUNCH_GATE_SCHEMA,
        "state": READY_LAUNCH_REVIEW_STATE
        if not blockers else BLOCKED_STATE,
        "blockers": blockers,
        **material,
        "launch_gate_implemented": False,
        "physical_certificate_trusted": False,
        "owner_nonce_registry_implemented": False,
        "owner_authorization_persistence_implemented": False,
        "prelaunch_revalidation_implemented": False,
        "build_token_implemented": False,
        "build_token_issued": False,
        "build_authorized": False,
        "build_started": False,
        "process_spawned": False,
        "filesystem_modified": False,
        "network_called": False,
        "github_api_called": False,
        "live_repository_mutation_performed": False,
    }


def build_authorization_gate_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "purpose": PURPOSE,
        "mechanism": MECHANISM,
        "decisions": list(DECISIONS),
        "required_physical_gate_proofs": list(REQUIRED_PHYSICAL_GATE_PROOFS),
        "required_owner_auth_proofs": list(REQUIRED_OWNER_AUTH_PROOFS),
        "verified_requirement_count_required": EXPECTED_VERIFIED_REQUIREMENTS,
        "max_physical_certificate_age_seconds":
            MAX_PHYSICAL_CERTIFICATE_AGE_SECONDS,
        "max_authorization_window_seconds": MAX_AUTHORIZATION_WINDOW_SECONDS,
        "generic_chat_is_build_authorization": False,
        "explicit_owner_signature_required": True,
        "owner_key_fingerprint_binding_required": True,
        "fresh_nonce_required": True,
        "persistent_nonce_replay_guard_required": True,
        "single_use_authorization_required": True,
        "authorization_persistence_required": True,
        "authorization_cas_required": True,
        "authorization_read_after_write_required": True,
        "authorization_reopen_required": True,
        "physical_certificate_required": True,
        "all_12_physical_requirements_required": True,
        "signed_verifier_receipt_required": True,
        "persisted_verifier_receipt_required": True,
        "receipt_reopen_required": True,
        "evidence_chain_reopen_required": True,
        "prelaunch_revalidation_required": True,
        "caller_physical_verification_claim_is_authority": False,
        "caller_authorization_persistence_claim_is_authority": False,
        "chat_acknowledgement_is_authorization": False,
        "launch_gate_implemented": False,
        "physical_certificate_trusted": False,
        "owner_nonce_registry_implemented": False,
        "owner_authorization_persistence_implemented": False,
        "build_token_implemented": False,
        "build_token_issued": False,
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
    "GATE_CONTRACT_SCHEMA",
    "PHYSICAL_CERTIFICATE_SCHEMA",
    "REQUEST_SCHEMA",
    "OWNER_VERIFICATION_SCHEMA",
    "AUTH_PERSISTENCE_SCHEMA",
    "LAUNCH_GATE_SCHEMA",
    "POLICY_SCHEMA",
    "READY_CONTRACT_STATE",
    "READY_OWNER_SIGNATURE_STATE",
    "OWNER_AUTH_VERIFIED_PENDING_PERSISTENCE",
    "OWNER_DENIAL_VERIFIED",
    "READY_AUTH_PERSISTENCE_SHAPE_STATE",
    "READY_LAUNCH_REVIEW_STATE",
    "BLOCKED_STATE",
    "PURPOSE",
    "MECHANISM",
    "AUTHORIZE_DECISION",
    "DENY_DECISION",
    "DECISIONS",
    "MAX_AUTHORIZATION_WINDOW_SECONDS",
    "MAX_PHYSICAL_CERTIFICATE_AGE_SECONDS",
    "EXPECTED_VERIFIED_REQUIREMENTS",
    "OWNER_SIGNATURE_CONTEXT",
    "REQUIRED_PHYSICAL_GATE_PROOFS",
    "REQUIRED_OWNER_AUTH_PROOFS",
    "BuildAuthorizationGateError",
    "owner_key_fingerprint",
    "build_gate_contract",
    "validate_physical_certificate_shape",
    "build_owner_authorization_request",
    "verify_owner_authorization_signature",
    "validate_authorization_persistence_shape",
    "build_launch_gate_implementation_review",
    "build_authorization_gate_policy",
]
