"""AION P0 LAB: cryptographic syntax of signed incident source proposals.

NO external trust root, current-head reader, verifier-issued nonce, external
replay cache, authenticated owner or producer is enrolled. Never use this
module as a production gate. Mathematically valid Ed25519 signature using a
CALLER-PROVIDED key NEVER establishes a trusted external issuer. ALWAYS DENY.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atlasquant_aion_p0_incident_external_witness_proposal_lab import NO_GO_FLAGS

SCHEMA = "ATLASQUANT_AION_INCIDENT_ENVELOPE_LAB_V1"
DOMAIN = b"ATLASQUANT:AION:P0:INCIDENT_WITNESS:LAB:V1\x00"
ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._:/-]{2,127}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
FIELDS = frozenset({
    "schema", "issuer_id", "key_id", "scope", "nonce", "epoch", "sequence",
    "credential_revocation_epoch", "head_digest", "incident_state",
    "issued_at", "expires_at",
})


def canonical_json_lab(value: dict[str, Any]) -> bytes:
    """Fixture-only serialization; does NOT canonicalize untrusted input."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, value in pairs:
        if name in out:
            raise ValueError("duplicate JSON member")
        out[name] = value
    return out


def _utc(value: Any) -> datetime | None:
    if type(value) is not str or not re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value
    ):
        return None
    try:
        out = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        return out.replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError):
        return None


def _str_id(v: Any) -> bool:
    return type(v) is str and bool(ID.fullmatch(v))


def _uint(v: Any) -> bool:
    return type(v) is int and 0 < v < 2**63


def inspect_signed_incident_envelope_lab(
    payload: Any, signature: Any, public_key: Any, *,
    expected_issuer: Any, expected_scope: Any, expected_nonce: Any,
    now_utc: Any, observed_head: Any = None,
) -> dict[str, Any]:
    """Observe cryptographic form; NEVER return execution permission.

    Key material, expected values, observed_head, time and nonce are all
    supplied by the LOCAL CALLER, not from an external trust authority.
    All failures are fail-closed and all success is explicitly LAB_ONLY.
    """
    defects: list[str] = []
    signature_valid = False
    envelope: dict[str, Any] = {}
    if type(payload) is not bytes or not (1 <= len(payload) <= 4096):
        defects.append("ENVELOPE_BYTES_INVALID")
    else:
        try:
            decoded = json.loads(payload.decode("utf-8"),
                                 object_pairs_hook=_unique_pairs,
                                 parse_constant=lambda _: (_ for _ in ()).throw(
                                     ValueError("nonfinite JSON")))
            if type(decoded) is not dict:
                defects.append("ENVELOPE_NOT_OBJECT")
            elif canonical_json_lab(decoded) != payload:
                defects.append("ENVELOPE_NOT_CANONICAL")
            elif frozenset(decoded) != FIELDS:
                defects.append("ENVELOPE_FIELDS_MISMATCH")
            else:
                envelope = decoded
        except (ValueError, UnicodeError, TypeError, OverflowError):
            defects.append("ENVELOPE_PARSE_INVALID")
    if type(signature) is not bytes or len(signature) != 64:
        defects.append("SIGNATURE_BYTES_INVALID")
    if type(public_key) is not bytes or len(public_key) != 32:
        defects.append("PUBLIC_KEY_BYTES_INVALID")
    if not defects:
        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(
                signature, DOMAIN + payload)
            signature_valid = True
        except (InvalidSignature, ValueError, TypeError):
            defects.append("SIGNATURE_INVALID")
    if envelope:
        for field in ("issuer_id","key_id","scope","nonce"):
            if not _str_id(envelope[field]):
                defects.append("FIELD_INVALID:" + field)
        for field in ("epoch","sequence","credential_revocation_epoch"):
            if not _uint(envelope[field]):
                defects.append("FIELD_INVALID:" + field)
        if type(envelope["head_digest"]) is not str or not DIGEST.fullmatch(
            envelope["head_digest"]
        ):
            defects.append("HEAD_DIGEST_INVALID")
        if envelope["schema"] != SCHEMA:
            defects.append("WRONG_SCHEMA")
        if type(envelope["incident_state"]) is not str or (
            envelope["incident_state"] != "NO_OPEN_INCIDENTS"
        ):
            defects.append("INCIDENT_UNSAFE_OR_UNKNOWN")
        for field, required in (
            ("issuer_id", expected_issuer),
            ("scope", expected_scope),
            ("nonce", expected_nonce),
        ):
            if not _str_id(required) or envelope[field] != required:
                defects.append("EXPECTED_BINDING_MISMATCH:" + field)
        issued = _utc(envelope["issued_at"])
        expires = _utc(envelope["expires_at"])
        now = _utc(now_utc)
        if issued is None or expires is None or now is None:
            defects.append("TIME_FORMAT_INVALID")
        elif issued > now or now >= expires or (
            expires - issued
        ).total_seconds() > 300:
            defects.append("TIME_WINDOW_UNSAFE")
        if type(observed_head) is dict:
            for field in ("epoch","sequence","credential_revocation_epoch","head_digest"):
                v = observed_head.get(field)
                current = envelope[field]
                valid = _uint(v) if field != "head_digest" else (
                    type(v) is str and bool(DIGEST.fullmatch(v))
                )
                if not valid or current != v:
                    defects.append("LOCAL_HEAD_MISMATCH:" + field)
        else:
            defects.append("EXTERNAL_HEAD_NOT_READ")
    else:
        defects.append("ENVELOPE_NOT_VERIFIABLE")

    # Real signatures would require independently enrolled signer and
    # challenge; fresh latest-head readback and replay resistance live OUTSIDE
    # both the executing AION and its restorable databases.
    defects.extend((
        "OUT_OF_BAND_SIGNER_NOT_ENROLLED",
        "EXTERNAL_NONCE_REPLAY_GUARD_NOT_ENROLLED",
        "INDEPENDENT_LATEST_HEAD_NOT_AUTHENTICATED",
    ))
    return {
        "schema": SCHEMA,
        "status": "BLOCKED",
        "allowed": False,
        "reason": sorted(set(defects))[0],
        "blockers": tuple(sorted(set(defects))),
        "signature_mathematically_valid_with_caller_key_in_lab": signature_valid,
        "external_signature_trust_verified": False,
        "external_highwater_authenticated": False,
        "credential_revocation_verified": False,
        "simulation_only": True,
        **{flag: False for flag in NO_GO_FLAGS},
    }


__all__ = ["SCHEMA", "DOMAIN", "FIELDS", "canonical_json_lab",
           "inspect_signed_incident_envelope_lab"]
