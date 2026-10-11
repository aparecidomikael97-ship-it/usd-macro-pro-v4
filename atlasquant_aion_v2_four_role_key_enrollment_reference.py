"""AION V2 four-role public-key enrollment ceremony -- MATH REFERENCE ONLY.

Four distinct Ed25519 role keys: HUMAN_OWNER, COLLECTOR, PRIMARY_WITNESS,
SECONDARY_ANCHOR. A complete roster is owner-reviewed and each listed signer
proves possession using a separate, role-bound and domain-separated challenge.
Transitions require the PREVIOUS pinned owner signature, full revocations,
exact previous roster digest and monotonic generation, plus new-key POP.

NO trusted enrollment: the initial owner pin, expected generation, previous
roster and asserted administrative domains ALL come from the fixture caller.
The module generates no keys, signs nothing, persists nothing, calls no
service or provider, and never authorizes model dispatch, spend or install.
A compromised caller who replaces ALL inputs can forge a math-valid genesis.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "ATLASQUANT_AION_V2_FOUR_ROLE_ENROLLMENT_REFERENCE_V1"
ROSTER_SCHEMA = "ATLASQUANT_AION_V2_PUBLIC_ROLE_ROSTER_V1"
PURPOSE = "REGISTER_FOUR_ROLE_KEYS_MATH_ONLY_NO_EXECUTION"
ROSTER_DOMAIN = b"ATLASQUANT_AION_V2_ROLE_ROSTER_V1\x00"
OWNER_APPROVAL_DOMAIN = b"ATLASQUANT_AION_V2_PRIOR_OWNER_ROSTER_APPROVAL_V1\x00"
POP_DOMAIN = b"ATLASQUANT_AION_V2_ROLE_PROOF_OF_POSSESSION_V1\x00"
CANDIDATE = "FOUR_ROLE_ROSTER_MATH_VALID_UNTRUSTED"
ZERO = "0" * 64
ROLES = ("HUMAN_OWNER", "COLLECTOR", "PRIMARY_WITNESS", "SECONDARY_ANCHOR")
_ENVELOPE_KEYS = frozenset({"roster", "owner_approval_signature_hex", "pop_signatures_hex"})
_ROSTER_KEYS = frozenset({
    "schema", "purpose", "generation", "previous_roster_sha256",
    "owner_id", "tenant_id", "workspace_id", "challenge_nonce_hex",
    "pins", "admin_domains", "revoked_public_key_sha256",
})
_PIN_KEYS = frozenset({"key_id", "public_key_hex"})
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,119}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_HEX128 = re.compile(r"[0-9a-f]{128}\Z")
FALSE_GATES = {
    "reference_only": True,
    "genesis_owner_identity_verified": False,
    "trusted_human_owner_consent": False,
    "owner_presence_verified": False,
    "owner_key_custody_verified": False,
    "collector_key_custody_verified": False,
    "witness_key_custody_verified": False,
    "anchor_key_custody_verified": False,
    "four_administrative_domains_independently_verified": False,
    "physical_key_enrollment_performed": False,
    "public_key_registry_protected": False,
    "externally_anchored_generation_verified": False,
    "replay_protected_registry_writes": False,
    "revocation_replicated_to_witnesses": False,
    "model_invocation_authorized": False,
    "real_budget_reserved": False,
    "provider_called": False,
    "billing_authorized": False,
    "network_called": False,
    "installer_authorized": False,
    "safe_to_resume": False,
}


def _int(value: Any, low: int, high: int) -> bool:
    return type(value) is int and low <= value <= high


def _token(value: Any) -> bool:
    return type(value) is str and bool(_TOKEN.fullmatch(value))


def _hex64(value: Any) -> bool:
    return type(value) is str and bool(_HEX64.fullmatch(value))


def _hex128(value: Any) -> bool:
    return type(value) is str and bool(_HEX128.fullmatch(value))


def _pin(value: Any) -> bool:
    return (type(value) is dict and set(value) == _PIN_KEYS
            and _token(value["key_id"]) and _hex64(value["public_key_hex"]))


def canonical_roster_bytes(roster: Mapping[str, Any]) -> bytes:
    """Exact versioned/domain-separated bytes, never an authority decision."""
    if type(roster) is not dict or set(roster) != _ROSTER_KEYS:
        raise ValueError("exact four-role roster schema required")
    return ROSTER_DOMAIN + json.dumps(
        roster, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def roster_sha256(roster: Mapping[str, Any]) -> str:
    return sha256(canonical_roster_bytes(roster)).hexdigest()


def owner_approval_transcript(roster: Mapping[str, Any]) -> bytes:
    return OWNER_APPROVAL_DOMAIN + canonical_roster_bytes(roster)


def role_pop_transcript(roster: Mapping[str, Any], role: Any) -> bytes:
    if role not in ROLES:
        raise ValueError("unsupported role")
    return POP_DOMAIN + role.encode("ascii") + b"\x00" + canonical_roster_bytes(roster)


def _verify(sig_hex: Any, pin: Any, message: bytes) -> bool:
    if not _pin(pin) or not _hex128(sig_hex):
        return False
    try:
        Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(pin["public_key_hex"])
        ).verify(bytes.fromhex(sig_hex), message)
        return True
    except (InvalidSignature, ValueError, TypeError, OverflowError):
        return False


def _out(state: str, reason: str, digest: str = "") -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": state,
        "reason": reason,
        "roster_sha256": digest if state == CANDIDATE else "",
        "mathematical_signatures_valid": state == CANDIDATE,
        **FALSE_GATES,
    }


def review_four_role_roster(
    envelope: Any, *, expected_owner_pin: Any,
    expected_admin_domains: Any,
    expected_generation: Any,
    expected_previous_roster: Any = None,
    expected_owner_id: Any,
    expected_tenant_id: Any,
    expected_workspace_id: Any,
    expected_challenge_nonce_hex: Any,
) -> dict[str, Any]:
    """Review a single proposed roster without accepting any external power.

    For rotation, the prior pinned owner key signs NEW full roster bytes.
    The new owner must ALSO prove possession. No fallback to new owner approval.
    """
    if (not _pin(expected_owner_pin)
        or type(expected_admin_domains) is not dict
        or set(expected_admin_domains) != set(ROLES)
        or not all(_token(expected_admin_domains[k]) for k in ROLES)
        or len(set(expected_admin_domains.values())) != len(ROLES)
        or not _int(expected_generation, 1, 2**31-1)
        or not all(_token(x) for x in (
            expected_owner_id, expected_tenant_id, expected_workspace_id,
        ))
        or not _hex64(expected_challenge_nonce_hex)
        or expected_challenge_nonce_hex == ZERO):
        return _out("BLOCKED", "TRUSTED_REFERENCE_INPUTS_INVALID")
    if type(envelope) is not dict or set(envelope) != _ENVELOPE_KEYS:
        return _out("BLOCKED", "ROSTER_ENVELOPE_SCHEMA_INVALID")
    roster=envelope["roster"]
    if type(roster) is not dict or set(roster) != _ROSTER_KEYS:
        return _out("BLOCKED", "EXACT_ROSTER_SCHEMA_REQUIRED")
    if (roster["schema"] != ROSTER_SCHEMA
        or roster["purpose"] != PURPOSE
        or roster["generation"] != expected_generation
        or roster["owner_id"] != expected_owner_id
        or roster["tenant_id"] != expected_tenant_id
        or roster["workspace_id"] != expected_workspace_id
        or roster["challenge_nonce_hex"] != expected_challenge_nonce_hex
        or roster["admin_domains"] != expected_admin_domains
        or not _hex64(roster["previous_roster_sha256"])):
        return _out("BLOCKED", "ROSTER_SCOPE_POLICY_CHALLENGE_OR_DOMAIN_MISMATCH")
    pins=roster["pins"]
    if (type(pins) is not dict or set(pins) != set(ROLES)
        or any(not _pin(pins[r]) for r in ROLES)
        or len({pins[r]["public_key_hex"] for r in ROLES}) != len(ROLES)
        or len({pins[r]["key_id"] for r in ROLES}) != len(ROLES)):
        return _out("BLOCKED", "KEY_ROLE_REUSE_OR_INVALID_PIN")
    revoked=roster["revoked_public_key_sha256"]
    if (type(revoked) is not list or any(not _hex64(k) for k in revoked)
        or revoked != sorted(set(revoked))
        or any(sha256(bytes.fromhex(pins[r]["public_key_hex"])).hexdigest()
               in revoked for r in ROLES)):
        return _out("BLOCKED", "REVOCATION_SET_INVALID_OR_ACTIVE_KEY_REVOKED")
    if expected_previous_roster is None:
        if (expected_generation != 1
            or roster["previous_roster_sha256"] != ZERO
            or revoked
            or pins["HUMAN_OWNER"] != expected_owner_pin):
            return _out("BLOCKED", "UNTRUSTED_GENESIS_OR_PRETEND_ROTATION")
    else:
        previous=expected_previous_roster
        if (type(previous) is not dict or set(previous) != _ROSTER_KEYS):
            return _out("BLOCKED", "PREVIOUS_ROSTER_REQUIRED")
        try:
            prev_hash=roster_sha256(previous)
        except (TypeError, ValueError, OverflowError):
            return _out("BLOCKED", "PREVIOUS_ROSTER_INVALID")
        old_pins=previous.get("pins")
        prior_revoked=previous.get("revoked_public_key_sha256")
        if (type(old_pins) is not dict or set(old_pins) != set(ROLES)
            or any(not _pin(old_pins[r]) for r in ROLES)
            or type(prior_revoked) is not list
            or any(not _hex64(x) for x in prior_revoked)
            or previous["generation"] != expected_generation-1
            or previous["owner_id"] != expected_owner_id
            or previous["tenant_id"] != expected_tenant_id
            or previous["workspace_id"] != expected_workspace_id
            or previous["admin_domains"] != expected_admin_domains
            or roster["previous_roster_sha256"] != prev_hash
            or expected_owner_pin != old_pins["HUMAN_OWNER"]):
            return _out("BLOCKED", "PRIOR_GENERATION_SCOPE_OR_OWNER_PIN_MISMATCH")
        required=set(prior_revoked)
        for role in ROLES:
            if old_pins[role]["public_key_hex"] != pins[role]["public_key_hex"]:
                required.add(sha256(bytes.fromhex(
                    old_pins[role]["public_key_hex"]
                )).hexdigest())
            elif old_pins[role] != pins[role]:
                return _out("BLOCKED", "OLD_KEY_ID_ALIAS_CHANGED")
        if set(revoked) != required:
            return _out("BLOCKED", "PREVIOUS_OR_REPLACED_KEY_NOT_REVOKED")
        if all(old_pins[r] == pins[r] for r in ROLES):
            return _out("BLOCKED", "NO_KEY_ROTATION_IN_NEW_GENERATION")
    proofs=envelope["pop_signatures_hex"]
    if type(proofs) is not dict or set(proofs) != set(ROLES):
        return _out("BLOCKED", "ALL_FOUR_ROLE_PROOFS_REQUIRED")
    try:
        root_bytes=owner_approval_transcript(roster)
        if not _verify(
            envelope["owner_approval_signature_hex"],
            expected_owner_pin, root_bytes,
        ):
            return _out("BLOCKED", "PRIOR_OWNER_SIGNATURE_MATH_INVALID")
        for role in ROLES:
            if not _verify(proofs[role], pins[role],
                           role_pop_transcript(roster, role)):
                return _out("BLOCKED", "ROLE_PROOF_OF_POSSESSION_INVALID")
        return _out(
            CANDIDATE, "MATH_ONLY_NOT_TRUSTED_ENROLLMENT_OR_OWNER_PRESENCE",
            digest=roster_sha256(roster),
        )
    except (TypeError, ValueError, OverflowError):
        return _out("BLOCKED", "INVALID_CANONICAL_ROSTER_OR_SIGNATURE")


__all__=[
    "SCHEMA", "ROSTER_SCHEMA", "PURPOSE", "ROSTER_DOMAIN",
    "OWNER_APPROVAL_DOMAIN", "POP_DOMAIN", "ROLES", "ZERO", "CANDIDATE",
    "FALSE_GATES", "canonical_roster_bytes", "roster_sha256",
    "owner_approval_transcript", "role_pop_transcript",
    "review_four_role_roster",
]
