"""P0 WebAuthn ES256 assertion verifier: isolated cryptographic LAB / NEVER AUTHORITY.

This checks a *synthetic* assertion against an injected pre-existing credential
and expected server challenge. It does NOT enroll, authenticate a real owner,
verify real RP/account ownership, attest device custody, persist nonce/counter,
or authorize any operation. Caller controls all "pinned" records in LAB.
A cryptographically coherent assertion is still BLOCKED.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

SCHEMA = "AION_P0_WEBAUTHN_ES256_ASSERTION_DIAGNOSTIC_LAB_V1"
_CLIENT_ALLOWED = frozenset({"type", "challenge", "origin", "crossOrigin"})
_ASSERTION_FIELDS = frozenset({
    "credential_id", "client_data_json_b64", "authenticator_data_b64", "signature_b64",
})
_EXPECTED_FIELDS = frozenset({
    "credential_id", "owner_id", "tenant_id", "workspace_id",
    "rp_id", "origin", "challenge_b64", "issued_at", "expires_at",
})
_PIN_FIELDS = frozenset({
    "credential_id", "owner_id", "tenant_id", "workspace_id",
    "public_key_sec1_b64", "status", "stored_sign_count",
})
_CHALLENGE = re.compile(r"^[A-Za-z0-9_-]{43,86}$")
_RPID = re.compile(r"^[a-z0-9.-]{1,253}$")


def _out(reason: str, signature_checked: bool = False) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "reason": reason,
        "signature_checked": signature_checked,
        "cryptographic_assertion_consistent": signature_checked,
        "owner_identity_verified": False,
        "real_device_custody_verified": False,
        "independent_enrollment_verified": False,
        "nonce_durably_consumed": False,
        "counter_atomically_persisted": False,
        "owner_authenticated": False,
        "owner_decision_authorized": False,
        "worker_armed": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def _decode(text: Any, minimum: int, maximum: int) -> bytes:
    if not isinstance(text, str) or not text or len(text) > 8192:
        raise ValueError("invalid encoded value")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", text):
        raise ValueError("noncanonical encoding")
    try:
        raw = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (binascii.Error, ValueError) as exc:
        raise ValueError("base64 decode error") from exc
    if not minimum <= len(raw) <= maximum:
        raise ValueError("unexpected length")
    if base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii") != text:
        raise ValueError("base64 noncanonical")
    return raw


def _strict_pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for k, v in items:
        if k in obj:
            raise ValueError("JSON duplicate key")
        obj[k] = v
    return obj


def _time(text: Any) -> datetime | None:
    if not isinstance(text, str) or not text.endswith("Z"):
        return None
    try:
        ts = datetime.fromisoformat(text[:-1] + "+00:00")
        return ts.astimezone(timezone.utc)
    except (ValueError, OverflowError, TypeError):
        return None


def inspect_owner_webauthn_assertion_lab(
    assertion: Mapping[str, Any] | None,
    *,
    pinned_credential: Mapping[str, Any] | None,
    expected: Mapping[str, Any] | None,
    used_challenges: frozenset[str] | None,
    now: str,
) -> dict[str, Any]:
    """ES256 signed authenticatorData||SHA256(clientDataJSON), diagnostic only.

    Positive signature result is NOT authentication/owner bootstrap. Persistent
    atomic challenge claim, trusted credential storage and true RP origin
    configuration are absent by design. Client cannot assert owner authority.
    """
    if not isinstance(assertion, Mapping) or set(assertion) != _ASSERTION_FIELDS:
        return _out("P0_ASSERTION_SHAPE_INVALID")
    if not isinstance(expected, Mapping) or set(expected) != _EXPECTED_FIELDS:
        return _out("P0_EXPECTED_CONTEXT_UNAVAILABLE")
    if not isinstance(pinned_credential, Mapping) or set(pinned_credential) != _PIN_FIELDS:
        return _out("P0_CREDENTIAL_RECORD_UNAVAILABLE")
    if pinned_credential.get("status") != "ACTIVE":
        return _out("P0_CREDENTIAL_NOT_ACTIVE")
    for key in ("credential_id", "owner_id", "tenant_id", "workspace_id"):
        if (not isinstance(expected[key], str) or not expected[key]
                or pinned_credential[key] != expected[key]):
            return _out("P0_CREDENTIAL_SCOPE_MISMATCH")
    if (not isinstance(assertion["credential_id"], str)
            or assertion["credential_id"] != expected["credential_id"]):
        return _out("P0_CREDENTIAL_ID_MISMATCH")
    if not isinstance(used_challenges, frozenset):
        return _out("P0_REPLAY_REGISTRY_UNAVAILABLE")
    challenge = expected["challenge_b64"]
    if not isinstance(challenge, str) or not _CHALLENGE.fullmatch(challenge):
        return _out("P0_CHALLENGE_INVALID")
    try:
        _decode(challenge, 32, 64)
    except ValueError:
        return _out("P0_CHALLENGE_INVALID")
    if challenge in used_challenges:
        return _out("P0_CHALLENGE_REPLAYED")
    issued, expires, current = _time(expected["issued_at"]), _time(expected["expires_at"]), _time(now)
    if issued is None or expires is None or current is None:
        return _out("P0_TIME_INVALID")
    if (issued > current or current >= expires or expires <= issued
            or (expires - issued).total_seconds() > 180):
        return _out("P0_CHALLENGE_TIME_INVALID")
    rp_id, origin = expected["rp_id"], expected["origin"]
    if (not isinstance(rp_id, str) or not _RPID.fullmatch(rp_id)
            or rp_id.startswith(".") or rp_id.endswith(".")
            or ".." in rp_id or "." not in rp_id):
        return _out("P0_RP_ID_INVALID")
    if (not isinstance(origin, str)
            or origin != "https://" + rp_id):
        # Intentionally narrow LAB policy: a single exact first-party origin.
        # A future integration needs real RP-ID/origin/subdomain policy.
        return _out("P0_ORIGIN_POLICY_INVALID")
    try:
        client_raw = _decode(assertion["client_data_json_b64"], 2, 4096)
        client = json.loads(client_raw.decode("utf-8"), object_pairs_hook=_strict_pairs)
    except (ValueError, UnicodeError, TypeError):
        return _out("P0_CLIENT_DATA_MALFORMED")
    if not isinstance(client, dict) or not {"type", "challenge", "origin"} <= set(client):
        return _out("P0_CLIENT_DATA_SHAPE_INVALID")
    if set(client) - _CLIENT_ALLOWED:
        return _out("P0_CLIENT_DATA_EXTENSION_UNSUPPORTED")
    if client["type"] != "webauthn.get":
        return _out("P0_ASSERTION_TYPE_INVALID")
    if client["challenge"] != challenge:
        return _out("P0_CHALLENGE_MISMATCH")
    if client["origin"] != origin:
        return _out("P0_ORIGIN_MISMATCH")
    if client.get("crossOrigin", False) is not False:
        return _out("P0_CROSS_ORIGIN_DENIED")
    try:
        auth_data = _decode(assertion["authenticator_data_b64"], 37, 37)
    except ValueError:
        return _out("P0_AUTHENTICATOR_DATA_INVALID")
    if auth_data[:32] != hashlib.sha256(rp_id.encode("utf-8")).digest():
        return _out("P0_RP_ID_HASH_MISMATCH")
    flags = auth_data[32]
    if not flags & 0x01 or not flags & 0x04:
        return _out("P0_USER_PRESENCE_OR_VERIFICATION_MISSING")
    if flags & 0xC0 or (flags & 0x10 and not flags & 0x08):
        return _out("P0_AUTHENTICATOR_FLAGS_UNSUPPORTED")
    # Zero sign counter can be legitimate on synced passkeys. It is never
    # accepted as clone-prevention proof in this diagnostic.
    new_count = int.from_bytes(auth_data[33:37], "big")
    prior_count = pinned_credential["stored_sign_count"]
    if type(prior_count) is not int or not 0 <= prior_count <= (2**32 - 1):
        return _out("P0_COUNTER_STATE_INVALID")
    if new_count and prior_count and new_count <= prior_count:
        return _out("P0_SIGN_COUNTER_NONMONOTONIC")
    try:
        key_bytes = _decode(pinned_credential["public_key_sec1_b64"], 65, 65)
        pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), key_bytes)
        signature = _decode(assertion["signature_b64"], 64, 80)
        pub.verify(signature, auth_data + hashlib.sha256(client_raw).digest(), ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature, ValueError, TypeError):
        return _out("P0_ASSERTION_SIGNATURE_INVALID")
    return _out("P0_CRYPTO_VALID_BUT_REAL_OWNER_BOOTSTRAP_UNVERIFIED", signature_checked=True)
