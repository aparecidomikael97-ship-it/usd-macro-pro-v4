"""P0 owner enrollment envelope diagnostic -- NEVER enroll or authorize.

This deliberately cannot authenticate who supplied an owner key or who holds
the custody authority. It inspects untrusted shape only and ALWAYS blocks
operational enrollment. For WebAuthn/passkeys, authenticator assertion and RP
verification are also NOT implemented. NO IO and NO signing.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping
import re

SCHEMA = "AION_P0_OWNER_ENROLLMENT_UNTRUSTED_LAB_V1"
MANDATORY = frozenset({
    "schema", "intent", "owner_id", "tenant_id", "workspace_id",
    "credential_id", "credential_version", "credential_kind",
    "public_key_fingerprint", "challenge_nonce",
    "issued_at", "expires_at", "proposed_custodian_id",
})
TRUST_CLAIMS = frozenset({
    "trusted", "owner_identity_verified", "owner_verified",
    "biometric_verified", "user_verified", "witness_verified",
    "independent_custody_verified", "enrollment_authorized",
    "fido2_verified", "activation_allowed", "owner_approved",
})
HEX64 = re.compile(r"^sha256:[0-9a-f]{64}$")
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{3,127}$")
NONCE = re.compile(r"^[A-Za-z0-9_-]{24,160}$")


def _ts(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.endswith("Z"):
        return None
    try:
        value = datetime.fromisoformat(raw[:-1] + "+00:00")
        return value.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def inspect_untrusted_owner_enrollment(
    proposal: Mapping[str, Any] | None,
    *,
    expected_owner_id: str,
    expected_tenant_id: str,
    expected_workspace_id: str,
    now: str,
) -> dict[str, Any]:
    """Pure risk triage, never accept a user-supplied trust-root authority.

    Even expected_* are caller-provided in this LAB. Exact matching them
    demonstrates only *format* agreement, not independent enrollment.
    """
    reasons: list[str] = []
    payload = dict(proposal) if isinstance(proposal, Mapping) else {}
    extras = set(payload) - MANDATORY
    missing = MANDATORY - set(payload)
    if not isinstance(proposal, Mapping):
        reasons.append("P0_ENROLLMENT_ENVELOPE_REQUIRED")
    if missing:
        reasons.append("P0_ENROLLMENT_FIELDS_MISSING")
    if extras:
        reasons.append("P0_ENROLLMENT_EXTRA_FIELDS")
    if extras & TRUST_CLAIMS:
        reasons.append("P0_CALLER_TRUST_FLAGS_FORBIDDEN")
    if payload.get("schema") != SCHEMA:
        reasons.append("P0_ENROLLMENT_SCHEMA_INVALID")
    if payload.get("intent") != "ENROLL":
        reasons.append("P0_OWNER_TRANSITION_NOT_APPROVED")
    for key, expected in (
        ("owner_id", expected_owner_id),
        ("tenant_id", expected_tenant_id),
        ("workspace_id", expected_workspace_id),
    ):
        if not isinstance(expected, str) or not expected or payload.get(key) != expected:
            reasons.append("P0_" + key.upper() + "_MISMATCH")
    for field in ("credential_id", "proposed_custodian_id"):
        value = payload.get(field)
        if not isinstance(value, str) or not ID.fullmatch(value):
            reasons.append("P0_" + field.upper() + "_INVALID")
    version = payload.get("credential_version")
    if type(version) is not int or version != 1:
        reasons.append("P0_CREDENTIAL_VERSION_INVALID")
    if payload.get("credential_kind") not in ("ED25519_EXTERNAL", "WEBAUTHN_PENDING_ADAPTER"):
        reasons.append("P0_CREDENTIAL_KIND_UNSUPPORTED")
    fingerprint = payload.get("public_key_fingerprint")
    if not isinstance(fingerprint, str) or not HEX64.fullmatch(fingerprint):
        reasons.append("P0_PUBLIC_KEY_FINGERPRINT_INVALID")
    nonce = payload.get("challenge_nonce")
    if not isinstance(nonce, str) or not NONCE.fullmatch(nonce):
        reasons.append("P0_ENROLLMENT_NONCE_INVALID")
    start, stop, clock = (
        _ts(payload.get("issued_at")),
        _ts(payload.get("expires_at")),
        _ts(now),
    )
    if start is None or stop is None or clock is None:
        reasons.append("P0_ENROLLMENT_TIME_INVALID")
    elif stop <= start or (stop-start).total_seconds() > 180:
        reasons.append("P0_ENROLLMENT_WINDOW_INVALID")
    elif start > clock:
        reasons.append("P0_ENROLLMENT_FROM_FUTURE")
    elif clock >= stop:
        reasons.append("P0_ENROLLMENT_EXPIRED")

    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "reason": "INDEPENDENT_OWNER_CUSTODY_NOT_ESTABLISHED",
        "format_consistent": not reasons,
        "format_blockers": sorted(set(reasons)),
        "owner_identity_verified": False,
        "independent_custody_verified": False,
        "enrollment_authorized": False,
        "private_key_collected": False,
        "trust_root_changed": False,
        "signature_capture_performed": False,
        "decision_authorized": False,
        "worker_armed": False,
        "external_action_executed": False,
        "executes_action": False,
    }
