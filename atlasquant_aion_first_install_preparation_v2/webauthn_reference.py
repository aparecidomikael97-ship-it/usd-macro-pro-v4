"""Bounded ES256 assertion mathematics for fixtures; NEVER owner enrollment.

No authenticator access, registration, network, credentials or durable replay
database. Callers must supply known revocation/replay state; production denied.
"""
import base64
from hashlib import sha256
import json
from urllib.parse import urlsplit

from fido2 import cbor
from fido2.cose import CoseKey
from cryptography.exceptions import InvalidSignature

from atlasquant_aion_first_install_preparation.ceremony import prepare_intent
from atlasquant_aion_first_install_preparation.contracts import (ContractError, binding, digest, digest_value, exact,
                        integer, result, tokens)

CREDENTIAL_FIELDS = frozenset({"schema", "role", "scope_digest", "credential_id",
    "public_key_cose", "generation", "backup_eligible", "stored_sign_count",
    "expires_at"})
PACKET_FIELDS = frozenset({"client_data_json", "authenticator_data", "signature",
                           "credential_id"})

def challenge_for(intent):
    value = prepare_intent(intent)
    data = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode()
    return base64.urlsafe_b64encode(sha256(b"AION_WEBAUTHN_FIXTURE_V2\0" + data).digest()).rstrip(b"=").decode()

def _bytes(value, lo, hi):
    if type(value) is not bytes or not lo <= len(value) <= hi:
        raise ContractError("BYTE_BOUND_INVALID")

def _key(raw):
    _bytes(raw, 1, 256)
    key = cbor.decode(raw)
    if (type(key) is not dict or set(key) != {1, 3, -1, -2, -3}
            or any(type(k) is not int for k in key)
            or any(type(key[k]) is not int for k in (1, 3, -1))
            or (key[1], key[3], key[-1]) != (2, -7, 1)
            or cbor.encode(key) != raw):
        raise ContractError("COSE_PROFILE_INVALID")
    _bytes(key[-2], 32, 32); _bytes(key[-3], 32, 32)
    return CoseKey.parse(key)

def verify_signature_reference(public_key_cose, message, signature):
    """For public vendor vectors, not a complete WebAuthn ceremony."""
    try:
        _bytes(message, 1, 8192); _bytes(signature, 8, 80)
        _key(public_key_cose).verify(message, signature)
        return result("REFERENCE_SIGNATURE_VALID_UNTRUSTED", "FIXTURE_MATH_ONLY",
                      cryptographic_signature_valid=True)
    except (ValueError, TypeError, KeyError, IndexError, RecursionError, InvalidSignature):
        return result("BLOCKED", "SIGNATURE_REJECTED", cryptographic_signature_valid=False)

def _pairs(items):
    out = {}
    for key, value in items:
        if key in out:
            raise ContractError("DUPLICATE_JSON_FIELD")
        out[key] = value
    return out

def verify_assertion_reference(intent, packet, credential, *, expected_binding,
        expected_public_key_sha256, expected_generation, rp_id, origin, now,
        revoked_credentials=None, consumed_challenges=None):
    try:
        request = prepare_intent(intent)
        scope = binding(expected_binding)
        if request["binding"] != scope:
            raise ContractError("SCOPE_MISMATCH")
        if not integer(now) or not request["not_before"] <= now < request["expires_at"]:
            raise ContractError("EXPIRED_INTENT")
        if not tokens(revoked_credentials, 128):
            raise ContractError("REVOCATION_UNKNOWN")
        if (type(consumed_challenges) is not list or len(consumed_challenges) > 128
                or any(type(x) is not str or len(x) != 43 for x in consumed_challenges)
                or len(set(consumed_challenges)) != len(consumed_challenges)):
            raise ContractError("REPLAY_STATE_UNKNOWN")
        challenge = challenge_for(request)
        if challenge in consumed_challenges:
            raise ContractError("REPLAY")
        if scope["credential_id"] in revoked_credentials:
            raise ContractError("REVOKED")
        exact(credential, CREDENTIAL_FIELDS); exact(packet, PACKET_FIELDS)
        if (credential["schema"] != "AION_WEBAUTHN_DISPOSABLE_CREDENTIAL_V2"
                or credential["role"] != "OWNER_CEREMONY_FIXTURE"
                or credential["scope_digest"] != digest(scope)
                or credential["credential_id"] != scope["credential_id"]
                or packet["credential_id"] != scope["credential_id"]):
            raise ContractError("UNENROLLED_OR_WRONG_FIXTURE")
        if (not integer(expected_generation, 1) or credential["generation"] != expected_generation
                or not integer(credential["generation"], 1)
                or not digest_value(expected_public_key_sha256)
                or type(credential["backup_eligible"]) is not bool
                or not integer(credential["stored_sign_count"], 0, 2**32-1)
                or not integer(credential["expires_at"]) or now >= credential["expires_at"]):
            raise ContractError("CREDENTIAL_POLICY_INVALID")
        _bytes(credential["public_key_cose"], 1, 256)
        if sha256(credential["public_key_cose"]).hexdigest() != expected_public_key_sha256:
            raise ContractError("ROTATED_KEY_MISMATCH")
        if (type(rp_id) is not str or not 1 <= len(rp_id) <= 253
                or not rp_id.endswith(".invalid") or not rp_id.isascii()
                or any(not x or not all(c.isalnum() or c == '-' for c in x) for x in rp_id.split('.'))
                or type(origin) is not str or len(origin) > 300):
            raise ContractError("FIXTURE_RP_REQUIRED")
        parsed = urlsplit(origin)
        if (parsed.scheme != "https" or parsed.netloc != rp_id or parsed.path
                or parsed.query or parsed.fragment or parsed.username or parsed.password):
            raise ContractError("FIXTURE_ORIGIN_REQUIRED")
        raw = packet["client_data_json"]
        _bytes(raw, 1, 4096)
        client = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(ContractError("NONFINITE")))
        if type(client) is not dict or set(client) not in (
                {"type", "challenge", "origin"}, {"type", "challenge", "origin", "crossOrigin"}):
            raise ContractError("CLIENT_SCHEMA_INVALID")
        if (client["type"] != "webauthn.get" or client["challenge"] != challenge
                or client["origin"] != origin or client.get("crossOrigin", False) is not False):
            raise ContractError("CLIENT_BINDING_INVALID")
        auth = packet["authenticator_data"]
        _bytes(auth, 37, 37)
        if auth[:32] != sha256(rp_id.encode("ascii")).digest():
            raise ContractError("RP_HASH_MISMATCH")
        flags = auth[32]
        if (flags & 5 != 5 or flags & ~0x1d
                or bool(flags & 8) != credential["backup_eligible"]
                or flags & 16 and not flags & 8):
            raise ContractError("AUTHENTICATOR_FLAGS_INVALID")
        count = int.from_bytes(auth[33:], "big")
        previous = credential["stored_sign_count"]
        if (count or previous) and count <= previous:
            raise ContractError("COUNTER_NOT_INCREASING")
        _bytes(packet["signature"], 8, 80)
        _key(credential["public_key_cose"]).verify(auth + sha256(raw).digest(), packet["signature"])
        return result("REFERENCE_ASSERTION_CRYPTO_VALID_UNTRUSTED", "FIXTURE_NOT_OWNER_OR_DEVICE_PROOF",
            cryptographic_signature_valid=True, reference_sign_count=count,
            counter_assurance="NONE" if count == previous == 0 else "FIXTURE_INCREASE_ONLY",
            durable_replay_protection=False)
    except (ValueError, TypeError, KeyError, IndexError, UnicodeError, RecursionError, InvalidSignature):
        return result("BLOCKED", "ASSERTION_REJECTED", cryptographic_signature_valid=False)
