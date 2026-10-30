"""A325 LAB: verify signatures on delivery receipts and their claimed issuers.

This module does NOT discover who controls the keys or independently fetch
an out-of-band origin pin. All pins, authority credentials, time and nonce
are caller-supplied synthetic test inputs. Even a 2/2 valid mathematical
chain MUST NOT authorize recovery, effect, replay or retry.

No network, external provider, secrets storage, DML, Worker or deploy.
"""
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from labs.a317_detached_signed_intent_anchor_lab import encode, sha
from labs.a320_offline_custody_ceremony_lab import _hex64, _nonneg_int, _safe_id
from labs.a324_recovery_evidence_triage_lab import (
    RECEIPT_FIELDS, _receipt_valid, investigate_recovery_evidence,
)
from labs.a321_signed_high_water_fork_detection_lab import _report_shape

SCHEMA = "ATLASQUANT_AION_A325_ORIGIN_ATTESTATION_CHAIN_LAB_V1"
ORIGIN_DOMAIN = b"ATLASQUANT_AION_A325_ORIGIN_ATTESTATION_LAB_V1\x00"
DELIVERY_DOMAIN = b"ATLASQUANT_AION_A325_DELIVERY_RECEIPT_LAB_V1\x00"
ATTEST_SIGNED_FIELDS = frozenset((
    "schema", "issuer_id", "custodian_id", "witness_key_hex",
    "root_generation", "incident_epoch", "checkpoint_sha256",
    "delivery_receipt_sha256", "challenge_nonce",
    "issued_at", "expires_at", "decision",
))
ATTEST_FIELDS = ATTEST_SIGNED_FIELDS | {"signature_hex"}
MAX_ATTEST_WINDOW = 120
HEX128 = set("0123456789abcdef")


def origin_signing_bytes(attestation):
    return ORIGIN_DOMAIN + encode({
        field: attestation[field] for field in sorted(ATTEST_SIGNED_FIELDS)
    })


def receipt_signing_bytes(receipt):
    return DELIVERY_DOMAIN + encode(receipt)


def _signature_shape(value):
    return (
        type(value) is str and len(value) == 128
        and all(char in HEX128 for char in value)
    )


def _verify(public_key_hex, signature_hex, message):
    if not _hex64(public_key_hex) or not _signature_shape(signature_hex):
        return False
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex)).verify(
            bytes.fromhex(signature_hex), message,
        )
        return True
    except (InvalidSignature, TypeError, ValueError, OverflowError):
        return False


def _attestation_shape(item):
    return (
        type(item) is dict and set(item) == ATTEST_FIELDS
        and item["schema"] == SCHEMA
        and all(_safe_id(item[field]) for field in (
            "issuer_id", "custodian_id",
        ))
        and all(_hex64(item[field]) for field in (
            "witness_key_hex", "checkpoint_sha256",
            "delivery_receipt_sha256", "challenge_nonce",
        ))
        and all(_nonneg_int(item[field]) for field in (
            "root_generation", "incident_epoch", "issued_at", "expires_at",
        ))
        and _signature_shape(item["signature_hex"])
        and item["decision"] == "HOLD_ONLY"
    )


def outcome(status, reasons, *, issuer_valid=0, delivery_valid=0,
            downstream_coherent=False):
    return {
        "schema": SCHEMA, "status": status,
        "reasons": sorted(set(reasons)),
        "mathematically_verified_issuer_signatures": issuer_valid,
        "mathematically_verified_delivery_signatures": delivery_valid,
        "synthetic_downstream_reconciliation_coherent": bool(downstream_coherent),
        "research_only": True,
        "synthetic_only": True,
        "investigation_only": True,
        "origin_pins_independently_provisioned": False,
        "issuer_identity_independently_authenticated": False,
        "witness_credential_real_world_custody_verified": False,
        "delivery_channel_independently_authenticated": False,
        "clock_and_nonce_externally_trusted": False,
        "off_host_immutable_head_verified": False,
        "provider_ack_authenticated": False,
        "semantic_exactly_once_proven": False,
        "can_restore": False, "can_resume": False,
        "can_replay": False, "can_resend": False,
        "can_auto_retry": False, "can_authorize_real_effect": False,
        "automatic_retries": 0, "zero_auto_resend": True,
        "hard_no_go": True, "p0_homologated": 0,
        "no_worker_deploy_provider_orders": True,
        "new_paid_services": False,
    }


def verify_claimed_receipt_origins(
    *, genesis_package, history_package, local_db_path, witness_receipts,
    declared_now_epoch, origin_attestations, pinned_origin_roots,
    signed_delivery_receipts, expected_nonce,
    incident_reopened=False, operation="VERIFY_ONLY",
):
    """Fail closed on missing origin credentials and tampering.

    BOTH an origin-issuer signature binding the A321 custodian public key
    AND a custodian signature of the A324 delivery receipt are required for
    each of two distinct claimed identities. Then redo A324/A323/A322/A321.
    No output can claim the caller's allegedly pinned roots came off-host.
    """
    if (type(operation) is not str or type(incident_reopened) is not bool
            or type(declared_now_epoch) is not int or declared_now_epoch < 0
            or not _hex64(expected_nonce)):
        return outcome("LAB_ORIGIN_PROCEDURAL_HOLD", ["CONTROL_INPUT_INVALID"])
    if incident_reopened:
        return outcome("LAB_ORIGIN_PROCEDURAL_HOLD", ["INCIDENT_REOPENED_FREEZE"])
    if operation != "VERIFY_ONLY":
        return outcome("LAB_ORIGIN_PROCEDURAL_HOLD", ["ACTION_REQUEST_DENIED"])
    if (type(origin_attestations) not in (list, tuple)
            or len(origin_attestations) != 2
            or type(witness_receipts) not in (list, tuple)
            or len(witness_receipts) != 2
            or type(pinned_origin_roots) is not dict
            or len(pinned_origin_roots) != 2
            or type(signed_delivery_receipts) is not dict
            or len(signed_delivery_receipts) != 2):
        return outcome("LAB_ORIGIN_MISSING_HOLD",
                       ["EXACT_TWO_ORIGIN_AND_DELIVERY_PROOFS_REQUIRED"])
    if (any(not _safe_id(k) or not _hex64(v)
            for k, v in pinned_origin_roots.items())
            or len(set(pinned_origin_roots.values())) != 2):
        return outcome("LAB_ORIGIN_QUORUM_VETO",
                       ["ORIGIN_PINSET_INVALID_OR_KEYS_REPEATED"])
    if (type(history_package) is not dict
            or type(history_package.get("ceremony_request")) is not dict
            or type(history_package["ceremony_request"].get("custodian_pins")) is not dict
            or type(history_package.get("checkpoints")) not in (list, tuple)
            or not history_package["checkpoints"]):
        return outcome("LAB_ORIGIN_MISSING_HOLD", ["SIGNED_HISTORY_OR_PINS_MISSING"])
    pins = history_package["ceremony_request"]["custodian_pins"]
    last = history_package["checkpoints"][-1]
    if (type(last) not in (tuple, list) or len(last) != 2
            or type(pins) is not dict or len(pins) != 2
            or any(not _safe_id(k) or not _hex64(v) for k, v in pins.items())
            or len(set(pins.values())) != 2):
        return outcome("LAB_ORIGIN_MISSING_HOLD", ["LATEST_WITNESS_SET_INVALID"])
    if set(pinned_origin_roots.values()) & set(pins.values()):
        return outcome("LAB_ORIGIN_QUORUM_VETO",
                       ["ORIGIN_ROOT_REUSED_AS_CUSTODIAN_KEY"])
    if any(not _report_shape(x) for x in last):
        return outcome("LAB_ORIGIN_MISSING_HOLD", ["LATEST_CHECKPOINT_INVALID"])
    last_map = {x["custodian_id"]: x for x in last}
    if set(last_map) != set(pins):
        return outcome("LAB_ORIGIN_QUORUM_VETO", ["LATEST_CUSTODIAN_SET_MISMATCH"])
    receipt_map = {}
    for r in witness_receipts:
        if not _receipt_valid(r):
            return outcome("LAB_ORIGIN_MISSING_HOLD", ["DELIVERY_RECEIPT_SHAPE_INVALID"])
        who = r.get("custodian_id")
        if not _safe_id(who) or who in receipt_map:
            return outcome("LAB_ORIGIN_QUORUM_VETO",
                           ["DUPLICATE_OR_INVALID_CUSTODIAN"])
        receipt_map[who] = r
    if set(receipt_map) != set(pins):
        return outcome("LAB_ORIGIN_QUORUM_VETO", ["DELIVERY_CUSTODIAN_SET_MISMATCH"])
    if (set(signed_delivery_receipts) != set(pins)
            or any(not _signature_shape(x)
                   for x in signed_delivery_receipts.values())):
        return outcome("LAB_ORIGIN_MISSING_HOLD",
                       ["SIGNED_DELIVERY_QUORUM_MISSING_OR_MALFORMED"])
    if (any(not _attestation_shape(x) for x in origin_attestations)):
        return outcome("LAB_ORIGIN_QUORUM_VETO", ["ORIGIN_ATTESTATION_INVALID"])
    issuer_ids = {x["issuer_id"] for x in origin_attestations}
    custodian_ids = {x["custodian_id"] for x in origin_attestations}
    if len(issuer_ids) != 2 or issuer_ids != set(pinned_origin_roots):
        return outcome("LAB_ORIGIN_QUORUM_VETO", ["TWO_DISTINCT_PINNED_ISSUERS_REQUIRED"])
    if len(custodian_ids) != 2 or custodian_ids != set(pins):
        return outcome("LAB_ORIGIN_QUORUM_VETO", ["TWO_DISTINCT_PINNED_CUSTODIANS_REQUIRED"])

    errors, issuer_ok, delivery_ok = set(), 0, 0
    for attestation in origin_attestations:
        issuer = attestation["issuer_id"]
        who = attestation["custodian_id"]
        checkpoint = last_map[who]
        delivery = receipt_map[who]
        if _verify(
            pinned_origin_roots[issuer],
            attestation["signature_hex"],
            origin_signing_bytes(attestation),
        ):
            issuer_ok += 1
        else:
            errors.add("ISSUER_SIGNATURE_INVALID")
        if _verify(
            pins[who], signed_delivery_receipts[who],
            receipt_signing_bytes(delivery),
        ):
            delivery_ok += 1
        else:
            errors.add("CUSTODIAN_DELIVERY_SIGNATURE_INVALID")
        if attestation["witness_key_hex"] != pins[who]:
            errors.add("ORIGIN_WITNESS_KEY_BINDING_MISMATCH")
        if attestation["checkpoint_sha256"] != sha(encode(checkpoint)):
            errors.add("ORIGIN_CHECKPOINT_BINDING_MISMATCH")
        if attestation["delivery_receipt_sha256"] != sha(encode(delivery)):
            errors.add("ORIGIN_DELIVERY_BINDING_MISMATCH")
        if attestation["root_generation"] != checkpoint.get("root_generation"):
            errors.add("ORIGIN_GENERATION_MISMATCH")
        if attestation["incident_epoch"] != checkpoint.get("incident_epoch"):
            errors.add("ORIGIN_INCIDENT_EPOCH_MISMATCH")
        if attestation["challenge_nonce"] != expected_nonce:
            errors.add("ORIGIN_CHALLENGE_REPLAY_OR_MISMATCH")
        t0, t1 = attestation["issued_at"], attestation["expires_at"]
        if (t1 <= t0 or t1 - t0 > MAX_ATTEST_WINDOW
                or t0 < checkpoint.get("issued_at", -1)
                or t0 > delivery.get("claimed_received_at", -1)
                or not t0 <= declared_now_epoch < t1
                or t1 > checkpoint.get("expires_at", -1)):
            errors.add("ORIGIN_ATTESTATION_TIME_INVALID")
    if errors or issuer_ok != 2 or delivery_ok != 2:
        return outcome("LAB_ORIGIN_QUORUM_VETO",
                       errors | {"CRYPTOGRAPHIC_QUORUM_NOT_MET"}
                       if issuer_ok != 2 or delivery_ok != 2 else errors,
                       issuer_valid=issuer_ok, delivery_valid=delivery_ok)
    try:
        triage = investigate_recovery_evidence(
            genesis_package=genesis_package,
            history_package=history_package, local_db_path=local_db_path,
            witness_receipts=witness_receipts,
            declared_now_epoch=declared_now_epoch,
            incident_reopened=False, operation="INVESTIGATE_ONLY",
        )
    except (TypeError, KeyError, ValueError, OverflowError, AttributeError):
        return outcome("LAB_DOWNSTREAM_EVIDENCE_HOLD",
                       ["A324_TRIAGE_UNVERIFIABLE"],
                       issuer_valid=issuer_ok, delivery_valid=delivery_ok)
    if triage["status"] != "LAB_COHERENT_EVIDENCE_STILL_HOLD":
        return outcome("LAB_DOWNSTREAM_EVIDENCE_HOLD",
                       ["A324_EVIDENCE_NOT_COHERENT"] + triage["reasons"],
                       issuer_valid=issuer_ok, delivery_valid=delivery_ok)
    return outcome("LAB_ORIGIN_SIGNATURES_MATCH_STILL_NOT_INDEPENDENT",
                   ["ORIGIN_BOOTSTRAP_NOT_EXTERNALLY_AUTHENTICATED",
                    "PROVIDER_ACK_NOT_VERIFIED"],
                   issuer_valid=issuer_ok, delivery_valid=delivery_ok,
                   downstream_coherent=True)


__all__ = [
    "SCHEMA", "ATTEST_FIELDS", "ATTEST_SIGNED_FIELDS", "MAX_ATTEST_WINDOW",
    "origin_signing_bytes", "receipt_signing_bytes",
    "verify_claimed_receipt_origins",
]
