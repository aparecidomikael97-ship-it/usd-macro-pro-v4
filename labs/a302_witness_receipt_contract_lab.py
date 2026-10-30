"""A302 LAB only: Ed25519 recovery-witness research. NEVER authorizes restore.

Pinned keys and trusted heads here are supplied by a synthetic local fixture.
Two signatures do not establish independent owner, custodian or antirollback.
"""
import hashlib
import json
import re
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "ATLASQUANT_AION_A302_WITNESS_RECEIPT_LAB_V1"
MANIFEST_SCHEMA = "ATLASQUANT_AION_RECOVERY_EVIDENCE_CONTRACT_LAB_V1"
DOMAIN = b"ATLASQUANT_AION_A302_RECEIPT_LAB_V1\x00"
GENESIS = "0" * 64
RECEIPT_FIELDS = frozenset((
    "schema", "witness_id", "sequence", "previous_receipt_hash",
    "manifest_sha256", "challenge_nonce", "signature_hex",
))
SIGNED_FIELDS = RECEIPT_FIELDS - {"signature_hex"}
MANIFEST_FIELDS = frozenset((
    "schema", "source_id", "generation", "conversation_id",
    "db_sha256", "db_size", "history_sha256", "intent_sha256",
    "pending_marker_sha256",
))
HEX_64 = re.compile(r"[0-9a-f]{64}\Z")
HEX_128 = re.compile(r"[0-9a-f]{128}\Z")


def _encoded(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def _valid_hash(value):
    return type(value) is str and HEX_64.fullmatch(value) is not None


def signing_bytes(receipt):
    """Domain-separated canonical encoding for a synthetic witness receipt."""
    return DOMAIN + _encoded({k: receipt[k] for k in sorted(SIGNED_FIELDS)})


def assess_signed_witness_receipts(
    *, manifest, receipts, pinned_public_keys, trusted_heads,
    challenge_nonce, a301_assessment,
):
    """A cryptographic verifier that always refuses operational recovery.

    The pinset and heads must originate from a real independent authority in a
    future design. A302 CANNOT authenticate their origin or independence.
    """
    issues = set()
    output = {
        "schema": SCHEMA, "research_only": True,
        "cryptographic_receipts_verified": False,
        "local_recovery_consistency": False,
        "independent_authority_authenticated": False,
        "independent_custody_verified": False,
        "trusted_heads_off_host_verified": False,
        "can_resume": False, "can_authorize_real_effect": False,
        "zero_auto_resend": True, "automatic_retries": 0,
        "hard_no_go": True, "p0_homologated": 0,
        "new_paid_services": False,
    }
    if (type(manifest) is not dict or set(manifest) != MANIFEST_FIELDS
            or manifest.get("schema") != MANIFEST_SCHEMA
            or type(manifest.get("source_id")) is not str
            or not manifest["source_id"]
            or type(manifest.get("conversation_id")) is not str
            or not manifest["conversation_id"]
            or type(manifest.get("generation")) is not int
            or manifest["generation"] < 0
            or type(manifest.get("db_size")) is not int
            or manifest["db_size"] <= 0
            or any(not _valid_hash(manifest.get(k)) for k in
                   ("db_sha256", "history_sha256", "intent_sha256"))
            or not (manifest.get("pending_marker_sha256") is None or
                    _valid_hash(manifest["pending_marker_sha256"]))):
        issues.add("MANIFEST_INVALID")
    if type(challenge_nonce) is not str or not _valid_hash(challenge_nonce):
        issues.add("CHALLENGE_NONCE_INVALID")
    if (type(a301_assessment) is not dict or
            a301_assessment.get("schema") != MANIFEST_SCHEMA or
            a301_assessment.get("locally_consistent_only") is not True or
            a301_assessment.get("issues") !=
            ["INDEPENDENT_CUSTODY_NOT_AUTHENTICATED"] or
            a301_assessment.get("can_resume") is not False):
        issues.add("A301_LOCAL_EVIDENCE_NOT_COHERENT")
    else:
        output["local_recovery_consistency"] = True

    if type(pinned_public_keys) is not dict or len(pinned_public_keys) != 2:
        issues.add("PINNED_WITNESS_SET_INVALID")
        pinned_public_keys = {}
    if type(trusted_heads) is not dict or set(trusted_heads) != set(pinned_public_keys):
        issues.add("TRUSTED_HEAD_SET_INVALID")
        trusted_heads = {}
    if type(receipts) is not list or len(receipts) != 2:
        issues.add("WITNESS_QUORUM_MISSING")
        receipts = []
    key_materials = list(pinned_public_keys.values())
    if (any(type(v) is not bytes or len(v) != 32 for v in key_materials)
            or len(set(key_materials)) != len(key_materials)):
        issues.add("WITNESS_KEYS_NOT_DISTINCT_OR_INVALID")

    manifest_sha = None
    if "MANIFEST_INVALID" not in issues:
        try:
            manifest_sha = _hash(_encoded(manifest))
        except (TypeError, ValueError, OverflowError):
            issues.add("MANIFEST_INVALID")
    seen = set()
    verified = 0
    for receipt in receipts:
        if type(receipt) is not dict or set(receipt) != RECEIPT_FIELDS:
            issues.add("RECEIPT_FIELDS_INVALID")
            continue
        witness = receipt["witness_id"]
        if type(witness) is not str or witness not in pinned_public_keys:
            issues.add("UNPINNED_WITNESS")
            continue
        if witness in seen:
            issues.add("DUPLICATE_WITNESS")
            continue
        seen.add(witness)
        if receipt["schema"] != SCHEMA:
            issues.add("RECEIPT_SCHEMA_INVALID")
        if manifest_sha is None or receipt["manifest_sha256"] != manifest_sha:
            issues.add("MANIFEST_BINDING_MISMATCH")
        if receipt["challenge_nonce"] != challenge_nonce:
            issues.add("CHALLENGE_BINDING_MISMATCH")
        prior = trusted_heads.get(witness)
        if (type(prior) is not dict or set(prior) != {"sequence", "receipt_hash"}
                or type(prior["sequence"]) is not int
                or prior["sequence"] < 0 or
                not _valid_hash(prior["receipt_hash"])):
            issues.add("TRUSTED_HEAD_MISSING_OR_INVALID")
        elif (type(receipt["sequence"]) is not int or
              receipt["sequence"] != prior["sequence"] + 1 or
              receipt["previous_receipt_hash"] != prior["receipt_hash"]):
            issues.add("REPLAY_OR_CHAIN_DISCONTINUITY")
        sig = receipt["signature_hex"]
        if type(sig) is not str or HEX_128.fullmatch(sig) is None:
            issues.add("SIGNATURE_ENCODING_INVALID")
            continue
        key = pinned_public_keys.get(witness)
        if type(key) is not bytes or len(key) != 32:
            issues.add("WITNESS_PUBLIC_KEY_INVALID")
            continue
        try:
            Ed25519PublicKey.from_public_bytes(key).verify(
                bytes.fromhex(sig), signing_bytes(receipt))
        except (InvalidSignature, ValueError, TypeError, KeyError):
            issues.add("SIGNATURE_VERIFICATION_FAILED")
        else:
            verified += 1
    if seen != set(pinned_public_keys):
        issues.add("WITNESS_QUORUM_INCOMPLETE")
    output["cryptographic_receipts_verified"] = (verified == 2 and not issues)
    # The synthetic pinset and monotonic head can be forged/reset by host:
    # never promote cryptographic matching to authenticated external custody.
    issues.add("REAL_INDEPENDENCE_AND_ANTIROLLBACK_NOT_PROVEN")
    output["issues"] = sorted(issues)
    return output


__all__ = [
    "SCHEMA", "MANIFEST_SCHEMA", "GENESIS", "MANIFEST_FIELDS",
    "signing_bytes", "assess_signed_witness_receipts",
]
