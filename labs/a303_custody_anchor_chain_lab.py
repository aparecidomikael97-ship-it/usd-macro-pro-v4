"""A303 LAB: cryptographic custody-anchor contract for A302 recovery evidence.

The trust root, its private key and the 'last seen' state are all SYNTHETIC and
host-controlled in tests. This classifies signatures and detects mismatches.
It NEVER proves independent custody, owner identity or permits recovery.
No network, worker, deploy, provider effects, orders, auto resend or real data.
"""
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from labs.a302_witness_receipt_contract_lab import (
    _encoded, _hash, _valid_hash, assess_signed_witness_receipts,
)

SCHEMA = "ATLASQUANT_AION_A303_CUSTODY_ANCHOR_LAB_V1"
DOMAIN = b"ATLASQUANT_AION_A303_CUSTODY_ANCHOR_LAB_V1\x00"
ANCHOR_FIELDS = frozenset({
    "schema", "root_key_id", "subject_id", "source_id", "conversation_id",
    "generation", "incident_epoch", "key_epoch", "anchor_sequence",
    "previous_anchor_hash", "manifest_sha256", "witness_keyset_sha256",
    "trusted_heads_sha256", "challenge_nonce", "signature_hex",
})
SIGNED_FIELDS = ANCHOR_FIELDS - {"signature_hex"}
HEX_128 = re.compile(r"[0-9a-f]{128}\Z")


def anchor_signing_bytes(anchor):
    """Canonical, domain-separated signing bytes (lab protocol version one)."""
    return DOMAIN + _encoded({k: anchor[k] for k in sorted(SIGNED_FIELDS)})


def _keyset_digest(keys):
    if (type(keys) is not dict or len(keys) != 2
            or not all(type(k) is str and k for k in keys)
            or not all(type(v) is bytes and len(v) == 32
                       for v in keys.values())):
        return None
    return _hash(_encoded({k: v.hex() for k, v in keys.items()}))


def _heads_digest(heads):
    if type(heads) is not dict:
        return None
    try:
        return _hash(_encoded(heads))
    except (TypeError, ValueError, OverflowError):
        return None


def assess_custody_anchor(*, a302_inputs, anchor, pinned_root_public_key,
                          pinned_root_key_id, expected_subject_id,
                          previous_anchor_sequence, previous_anchor_hash,
                          incident_epoch_floor, key_epoch_floor):
    """Verify an offline synthetic anchor and A302 receipts, always HARD NO-GO.

    Every floor and the public key are supplied by the *same test caller*.
    An attacker controlling those parameters can present a coherent rollback.
    A future off-host custodian would have to supply them independently.
    """
    issues = set()
    result = {
        "schema": SCHEMA, "research_only": True,
        "a302_receipts_verified": False,
        "cryptographic_anchor_verified": False,
        "local_package_consistent": False,
        "independent_root_proven": False,
        "off_host_monotonic_floor_verified": False,
        "revocation_status_proven": False,
        "owner_identity_proven": False,
        "can_resume": False, "can_authorize_real_effect": False,
        "hard_no_go": True, "zero_auto_resend": True,
        "automatic_retries": 0, "p0_homologated": 0,
        "new_paid_services": False,
    }
    if type(a302_inputs) is not dict or set(a302_inputs) != {
        "manifest", "receipts", "pinned_public_keys", "trusted_heads",
        "challenge_nonce", "a301_assessment",
    }:
        issues.add("A302_INPUTS_MISSING")
        a302_inputs = {}
    else:
        try:
            child = assess_signed_witness_receipts(**a302_inputs)
            result["a302_receipts_verified"] = bool(
                child["cryptographic_receipts_verified"])
            if not child["cryptographic_receipts_verified"]:
                issues.add("A302_RECEIPTS_INVALID")
        except (TypeError, ValueError, KeyError):
            issues.add("A302_RECEIPTS_INVALID")

    if type(anchor) is not dict or set(anchor) != ANCHOR_FIELDS:
        issues.add("ANCHOR_FIELDS_INVALID")
        anchor = {}
    if (type(pinned_root_public_key) is not bytes or
            len(pinned_root_public_key) != 32):
        issues.add("ROOT_PUBLIC_KEY_INVALID")
    if type(pinned_root_key_id) is not str or not pinned_root_key_id:
        issues.add("ROOT_ID_PIN_INVALID")
    if type(expected_subject_id) is not str or not expected_subject_id:
        issues.add("SUBJECT_PIN_INVALID")
    if (type(previous_anchor_sequence) is not int
            or previous_anchor_sequence < 0):
        issues.add("PREVIOUS_ANCHOR_SEQUENCE_INVALID")
    if not _valid_hash(previous_anchor_hash):
        issues.add("PREVIOUS_ANCHOR_HASH_INVALID")
    if type(incident_epoch_floor) is not int or incident_epoch_floor < 0:
        issues.add("INCIDENT_EPOCH_FLOOR_INVALID")
    if type(key_epoch_floor) is not int or key_epoch_floor < 0:
        issues.add("KEY_EPOCH_FLOOR_INVALID")

    keys = a302_inputs.get("pinned_public_keys")
    if (type(pinned_root_public_key) is bytes and
            type(keys) is dict and
            pinned_root_public_key in keys.values()):
        issues.add("ROOT_KEY_EQUALS_WITNESS_KEY")
    manifest = a302_inputs.get("manifest")
    heads = a302_inputs.get("trusted_heads")
    if type(manifest) is not dict:
        issues.add("A301_MANIFEST_INVALID")
        manifest = {}
    if anchor:
        if anchor["schema"] != SCHEMA:
            issues.add("ANCHOR_SCHEMA_MISMATCH")
        if anchor["root_key_id"] != pinned_root_key_id:
            issues.add("ROOT_ID_MISMATCH")
        if anchor["subject_id"] != expected_subject_id:
            issues.add("SUBJECT_SCOPE_MISMATCH")
        if anchor["source_id"] != manifest.get("source_id"):
            issues.add("SOURCE_SCOPE_MISMATCH")
        if anchor["conversation_id"] != manifest.get("conversation_id"):
            issues.add("CONVERSATION_SCOPE_MISMATCH")
        if type(anchor["generation"]) is not int or (
                anchor["generation"] != manifest.get("generation")):
            issues.add("GENERATION_MISMATCH")
        if (type(anchor["incident_epoch"]) is not int
                or (type(incident_epoch_floor) is int and
                    anchor["incident_epoch"] < incident_epoch_floor)):
            issues.add("INCIDENT_EPOCH_ROLLBACK")
        if (type(anchor["key_epoch"]) is not int
                or (type(key_epoch_floor) is int and
                    anchor["key_epoch"] < key_epoch_floor)):
            issues.add("KEY_EPOCH_ROLLBACK")
        if (type(anchor["anchor_sequence"]) is not int
                or type(previous_anchor_sequence) is not int
                or anchor["anchor_sequence"] != previous_anchor_sequence + 1):
            issues.add("ANCHOR_SEQUENCE_REPLAY_OR_GAP")
        if anchor["previous_anchor_hash"] != previous_anchor_hash:
            issues.add("ANCHOR_CHAIN_DISCONTINUITY")
        try:
            manifest_digest = _hash(_encoded(manifest))
        except (TypeError, ValueError, OverflowError):
            manifest_digest = None
        if anchor["manifest_sha256"] != manifest_digest:
            issues.add("MANIFEST_BINDING_MISMATCH")
        if anchor["witness_keyset_sha256"] != _keyset_digest(keys):
            issues.add("WITNESS_KEYSET_BINDING_MISMATCH")
        if anchor["trusted_heads_sha256"] != _heads_digest(heads):
            issues.add("WITNESS_HEADS_BINDING_MISMATCH")
        if anchor["challenge_nonce"] != a302_inputs.get("challenge_nonce"):
            issues.add("CHALLENGE_BINDING_MISMATCH")
        signature_hex = anchor["signature_hex"]
        if (type(signature_hex) is not str or
                HEX_128.fullmatch(signature_hex) is None):
            issues.add("ANCHOR_SIGNATURE_FORMAT_INVALID")
        elif (type(pinned_root_public_key) is bytes and
              len(pinned_root_public_key) == 32):
            try:
                Ed25519PublicKey.from_public_bytes(
                    pinned_root_public_key
                ).verify(
                    bytes.fromhex(signature_hex), anchor_signing_bytes(anchor)
                )
            except (InvalidSignature, ValueError, TypeError, KeyError):
                issues.add("ANCHOR_SIGNATURE_INVALID")
            else:
                result["cryptographic_anchor_verified"] = True

    result["local_package_consistent"] = (
        not issues and result["a302_receipts_verified"] and
        result["cryptographic_anchor_verified"]
    )
    # This is not a proof of an independent signing key or durable head;
    # the host may reset both. This issue NEVER disappears in A303.
    issues.add("EXTERNAL_ROOT_AND_ANTIROLLBACK_NOT_ATTESTED")
    result["issues"] = sorted(issues)
    return result


__all__ = [
    "SCHEMA", "ANCHOR_FIELDS", "anchor_signing_bytes",
    "assess_custody_anchor",
]
