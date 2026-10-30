"""A318 LAB: 2-of-2 Ed25519 witness quorum for A317 signed intent snapshot.

All public keys, roots, revocation list, high-water head and clock are
CALLER-SUPPLIED, never independently pinned. This is a VERIFIER CONTRACT
and negative security experiment, not custody, provider ACK or P0 closure.
NO network, database writes, Worker, deploy, paid service or retries.
"""
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from labs.a317_detached_signed_intent_anchor_lab import (
    HEX64, HEX128, ID, assess_detached_intent_anchor, encode, sha,
)

SCHEMA = "ATLASQUANT_AION_A318_TWO_WITNESS_CUSTODY_CONTRACT_LAB_V1"
DOMAIN = b"ATLASQUANT_AION_A318_TWO_WITNESS_CUSTODY_CONTRACT_LAB_V1\x00"
SIGNABLE = frozenset({
    "schema", "root_id", "root_generation", "anchor_sha256",
    "chain_sequence", "previous_anchor_sha256", "incident_epoch",
    "challenge_nonce", "issued_at", "expires_at", "decision",
})
ALL_FIELDS = SIGNABLE | {"signature_hex"}
MAX_VALIDITY = 900
QUORUM = 2


def statement_bytes(statement):
    """Canonical signature domain; never include signature_hex itself."""
    return DOMAIN + encode({name: statement[name] for name in sorted(SIGNABLE)})


def hold(status, reasons, *, local_ok=False, signatures_ok=0):
    return {
        "schema": SCHEMA, "status": status,
        "reasons": sorted(set(reasons)),
        "local_a317_signature_and_snapshot_valid": bool(local_ok),
        "mathematical_two_witness_quorum_valid": (
            signatures_ok == QUORUM and not reasons
        ),
        "verified_witness_signatures": signatures_ok,
        "required_witness_signatures": QUORUM,
        "research_only": True, "synthetic_only": True,
        "roots_independently_pinned": False,
        "root_rotation_independently_authorized": False,
        "revocations_independently_attested": False,
        "external_high_water_authenticated": False,
        "trusted_time_proven": False,
        "off_host_custody_proven": False,
        "independent_provider_ack_proven": False,
        "semantic_exactly_once_proven": False,
        "can_authorize_real_effect": False,
        "can_resume": False, "can_resend": False, "can_auto_retry": False,
        "automatic_retries": 0, "zero_auto_resend": True,
        "hard_no_go": True, "p0_homologated": 0,
        "no_worker_deploy_provider_orders": True,
        "new_paid_services": False,
    }


def verify_two_witness_hold(
    *, db_path, scope, intent_id, signed_anchor,
    pinned_a317_witness_key, previous_head, challenge_nonce,
    now_epoch, expected_incident_epoch, witness_statements,
    pinned_root_keys, revoked_root_ids, root_generation,
):
    """Check two detached signatures, then A317's real read-only fixture.

    Even a valid quorum is only a mathematical result. The caller controls
    both roots, the revocation set, high-water value and time. Always HOLD.
    """
    errors = []
    if type(pinned_root_keys) is not dict or len(pinned_root_keys) != QUORUM:
        errors.append("TWO_PINNED_ROOTS_REQUIRED")
        roots = {}
    else:
        roots = pinned_root_keys
    if any(
        type(name) is not str or not ID.fullmatch(name)
        or type(key) is not bytes or len(key) != 32
        for name, key in roots.items()
    ):
        errors.append("ROOT_KEY_OR_ID_INVALID")
    valid_keys = [
        key for key in roots.values()
        if type(key) is bytes and len(key) == 32
    ]
    if len(set(valid_keys)) != QUORUM:
        errors.append("ROOT_KEYS_NOT_DISTINCT")
    if type(pinned_a317_witness_key) is bytes:
        if pinned_a317_witness_key in valid_keys:
            errors.append("ROOT_NOT_DISTINCT_FROM_A317_SIGNER")
    if type(revoked_root_ids) not in (tuple, list, frozenset):
        errors.append("REVOCATION_SET_INVALID")
        revoked = set()
    else:
        if any(type(x) is not str or not ID.fullmatch(x)
               for x in revoked_root_ids):
            errors.append("REVOCATION_SET_INVALID")
        revoked = set(str(x) for x in revoked_root_ids)
    if type(root_generation) is not int or root_generation < 1:
        errors.append("ROOT_GENERATION_INVALID")
    if type(now_epoch) is not int or now_epoch < 0:
        errors.append("UNTRUSTED_TIME_INVALID")
    if type(expected_incident_epoch) is not int or expected_incident_epoch < 0:
        errors.append("INCIDENT_EPOCH_INVALID")
    if type(challenge_nonce) is not str or not HEX64.fullmatch(challenge_nonce):
        errors.append("CHALLENGE_INVALID")
    if (type(signed_anchor) is not dict
            or type(witness_statements) not in (list, tuple)
            or len(witness_statements) != QUORUM):
        return hold("LAB_ROOT_QUORUM_VETO",
                    errors + ["ANCHOR_OR_QUORUM_SHAPE_INVALID"])
    try:
        digest = sha(encode(signed_anchor))
    except (TypeError, ValueError, OverflowError):
        return hold("LAB_ROOT_QUORUM_VETO", errors + ["ANCHOR_NOT_CANONICAL"])
    used_ids = set()
    valid_signatures = 0
    for witness in witness_statements:
        if type(witness) is not dict or set(witness) != ALL_FIELDS:
            errors.append("WITNESS_FIELDS_INVALID")
            continue
        root = witness["root_id"]
        if type(root) is not str or not ID.fullmatch(root):
            errors.append("WITNESS_ROOT_ID_INVALID")
            continue
        if root in used_ids:
            errors.append("WITNESS_ROOT_REUSED")
        used_ids.add(root)
        if root not in roots:
            errors.append("WITNESS_ROOT_NOT_PINNED")
        if root in revoked:
            errors.append("WITNESS_ROOT_REVOKED")
        if witness["schema"] != SCHEMA or witness["decision"] != "HOLD_ONLY":
            errors.append("WITNESS_SCHEMA_OR_DECISION_INVALID")
        for name in ("root_generation", "chain_sequence", "incident_epoch",
                     "issued_at", "expires_at"):
            if type(witness[name]) is not int or witness[name] < 0:
                errors.append("WITNESS_NUMBER_INVALID")
        for name in ("anchor_sha256", "previous_anchor_sha256", "challenge_nonce"):
            if type(witness[name]) is not str or not HEX64.fullmatch(witness[name]):
                errors.append("WITNESS_HASH_INVALID")
        if (type(witness["signature_hex"]) is not str
                or not HEX128.fullmatch(witness["signature_hex"])):
            errors.append("WITNESS_SIGNATURE_FORMAT_INVALID")
        if witness["anchor_sha256"] != digest:
            errors.append("ANCHOR_DIGEST_MISMATCH")
        if witness["root_generation"] != root_generation:
            errors.append("ROOT_GENERATION_REPLAY_OR_MISMATCH")
        if witness["challenge_nonce"] != challenge_nonce:
            errors.append("CHALLENGE_REPLAY_OR_MISMATCH")
        if witness["incident_epoch"] != expected_incident_epoch:
            errors.append("INCIDENT_REOPEN_OR_EPOCH_MISMATCH")
        if (
            type(previous_head) is not dict
            or set(previous_head) != {"sequence", "sha256"}
            or type(previous_head.get("sequence")) is not int
            or previous_head["sequence"] < 0
            or type(previous_head.get("sha256")) is not str
            or not HEX64.fullmatch(previous_head["sha256"])
        ):
            errors.append("HIGH_WATER_HEAD_INVALID")
        else:
            if (witness["chain_sequence"] != previous_head["sequence"] + 1
                    or witness["previous_anchor_sha256"] != previous_head["sha256"]):
                errors.append("HIGH_WATER_ROLLBACK_OR_REPLAY")
        if (type(witness["issued_at"]) is int
                and type(witness["expires_at"]) is int
                and type(now_epoch) is int):
            if (witness["expires_at"] <= witness["issued_at"]
                    or witness["expires_at"] - witness["issued_at"] > MAX_VALIDITY
                    or not witness["issued_at"] <= now_epoch < witness["expires_at"]):
                errors.append("WITNESS_EXPIRED_FUTURE_OR_OVERSIZED")
        key = roots.get(root)
        if (
            type(key) is bytes and len(key) == 32
            and type(witness["signature_hex"]) is str
            and HEX128.fullmatch(witness["signature_hex"])
        ):
            try:
                Ed25519PublicKey.from_public_bytes(key).verify(
                    bytes.fromhex(witness["signature_hex"]),
                    statement_bytes(witness),
                )
                valid_signatures += 1
            except (InvalidSignature, TypeError, ValueError,
                    KeyError, OverflowError):
                errors.append("WITNESS_SIGNATURE_INVALID")
    if len(used_ids) != QUORUM or used_ids != set(roots):
        errors.append("TWO_DIFFERENT_PINNED_WITNESSES_REQUIRED")
    if errors or valid_signatures != QUORUM:
        if valid_signatures != QUORUM:
            errors.append("CRYPTOGRAPHIC_QUORUM_NOT_MET")
        return hold("LAB_ROOT_QUORUM_VETO", errors,
                    signatures_ok=valid_signatures)
    # A317's database check cannot be skipped by providing an alleged
    # success report. It rereads a marked, synthetic SQLite fixture.
    local = assess_detached_intent_anchor(
        db_path=db_path, scope=scope, intent_id=intent_id,
        signed_anchor=signed_anchor,
        pinned_witness_key=pinned_a317_witness_key,
        previous_head=previous_head, challenge_nonce=challenge_nonce,
        now_epoch=now_epoch, expected_incident_epoch=expected_incident_epoch,
    )
    if local["status"] != "LAB_SNAPSHOT_MATCH_NO_EXTERNAL_AUTHORITY":
        return hold(
            "LAB_LOCAL_ANCHOR_VETO",
            ["A317_LOCAL_OR_ANCHOR_REFUSED"] + local.get("issues", []),
            signatures_ok=valid_signatures,
        )
    return hold("LAB_TWO_SIGNATURES_MATCH_STILL_NO_EXTERNAL_AUTHORITY",
                [], local_ok=True, signatures_ok=valid_signatures)


__all__ = ["SCHEMA", "SIGNABLE", "ALL_FIELDS", "QUORUM", "statement_bytes",
           "verify_two_witness_hold"]
