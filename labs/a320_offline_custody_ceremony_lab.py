"""A320 LAB: offline ceremony packet consistency, NOT independent custody.

No physical custody, off-host pins, external transport, authenticated human
custodians, or trusted clock can be proven from caller-provided JSON.
Every result is HARD NO-GO; no deployment, Worker, provider, resend, fee.
"""
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from labs.a317_detached_signed_intent_anchor_lab import encode, sha
from labs.a319_offline_root_continuity_lab import (
    SCHEMA as A319_SCHEMA, assess_offline_root_transition,
)

SCHEMA = "ATLASQUANT_AION_A320_OFFLINE_CUSTODY_CEREMONY_LAB_V1"
SIGN_DOMAIN = b"ATLASQUANT_AION_A320_CUSTODIAN_RECEIPT_LAB_V1\x00"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX128 = re.compile(r"[0-9a-f]{128}\Z")
SAFE_ID = re.compile(r"[A-Za-z0-9._-]{1,80}\Z")
TRANSITION_KEYS = frozenset((
    "previous_manifest", "candidate_manifest", "pinned_previous_digest",
    "old_root_signatures", "new_root_signatures", "expected_nonce",
    "expected_incident_epoch", "observed_clock_epoch",
))
PRECOMMIT_FIELDS = frozenset((
    "schema", "ceremony_id", "candidate_manifest_sha256",
    "previous_manifest_sha256", "root_generation", "incident_epoch",
    "high_water_sequence", "high_water_sha256", "challenge_nonce",
    "recorded_at",
))
SIGNED_FIELDS = PRECOMMIT_FIELDS | frozenset((
    "custodian_id", "custody_domain", "channel_id", "device_id",
    "evidence_digest", "witnessed_at", "decision",
))
ALL_FIELDS = SIGNED_FIELDS | {"signature_hex"}


def signable_bytes(packet):
    return SIGN_DOMAIN + encode({field: packet[field] for field in sorted(SIGNED_FIELDS)})


def outcome(status, issues, signatures=0, transition_math=False):
    return {
        "schema": SCHEMA, "status": status,
        "issues": sorted(set(issues)),
        "mathematically_valid_custodian_signatures": signatures,
        "root_rotation_mathematically_consistent": bool(transition_math),
        "packet_consistency_observed": (
            status == "LAB_TWO_CUSTODY_PACKETS_COHERENT_BUT_UNVERIFIED"
        ),
        "research_only": True, "synthetic_only": True,
        "physical_separation_independently_verified": False,
        "independent_custodian_identity_authenticated": False,
        "external_precommit_authenticated": False,
        "trusted_receipt_delivery_verified": False,
        "custodian_keys_independently_pinned": False,
        "trusted_clock_or_timestamp_verified": False,
        "external_high_water_proven": False,
        "durable_off_host_intent_custody_proven": False,
        "external_provider_ack_proven": False,
        "semantic_exactly_once_proven": False,
        "can_authorize_real_effect": False, "can_resume": False,
        "can_resend": False, "can_auto_retry": False,
        "automatic_retries": 0, "zero_auto_resend": True,
        "hard_no_go": True, "p0_homologated": 0,
        "no_worker_deploy_provider_orders": True,
        "new_paid_services": False,
    }


def _safe_id(value):
    return type(value) is str and SAFE_ID.fullmatch(value) is not None


def _hex64(value):
    return type(value) is str and HEX64.fullmatch(value) is not None


def _nonneg_int(value):
    return type(value) is int and value >= 0


def _shape_precommit(value):
    return (
        type(value) is dict and set(value) == PRECOMMIT_FIELDS
        and value["schema"] == SCHEMA
        and _safe_id(value["ceremony_id"])
        and all(_hex64(value[k]) for k in (
            "candidate_manifest_sha256", "previous_manifest_sha256",
            "high_water_sha256", "challenge_nonce",
        ))
        and all(_nonneg_int(value[k]) for k in (
            "root_generation", "incident_epoch", "high_water_sequence",
            "recorded_at",
        ))
    )


def _shape_packet(value):
    return (
        type(value) is dict and set(value) == ALL_FIELDS
        and value["schema"] == SCHEMA
        and all(_safe_id(value[k]) for k in (
            "ceremony_id", "custodian_id", "custody_domain", "channel_id",
            "device_id",
        ))
        and all(_hex64(value[k]) for k in (
            "candidate_manifest_sha256", "previous_manifest_sha256",
            "high_water_sha256", "challenge_nonce", "evidence_digest",
        ))
        and all(_nonneg_int(value[k]) for k in (
            "root_generation", "incident_epoch", "high_water_sequence",
            "recorded_at", "witnessed_at",
        ))
        and value["decision"] == "HOLD_ONLY"
        and type(value["signature_hex"]) is str
        and HEX128.fullmatch(value["signature_hex"]) is not None
    )


def verify_offline_custody_ceremony(
    *, transition_request, offline_precommit,
    custodian_packets, custodian_pins,
):
    """Validate a synthetic two-custodian paper-trail, always HOLD.

    Structural checks compare claimed human/device/channel separation, but
    the input is not evidence of physical or operator independence. Caller
    could mint both signers, channels, timestamps and precommit. No release.
    """
    issues = []
    if type(transition_request) is not dict or set(transition_request) != TRANSITION_KEYS:
        issues.append("ROOT_TRANSITION_ENVELOPE_INVALID")
    if not _shape_precommit(offline_precommit):
        issues.append("PRECOMMIT_MISSING_OR_MALFORMED")
    if type(custodian_packets) not in (tuple, list) or len(custodian_packets) != 2:
        issues.append("EXACT_TWO_CUSTODIAN_PACKETS_REQUIRED")
    if type(custodian_pins) is not dict or len(custodian_pins) != 2:
        issues.append("EXACT_TWO_CUSTODIAN_PINS_REQUIRED")
    if issues:
        return outcome("LAB_CUSTODY_CEREMONY_VETO", issues)
    candidate = transition_request["candidate_manifest"]
    previous = transition_request["previous_manifest"]
    if (type(candidate) is not dict or type(previous) is not dict
            or candidate.get("schema") != A319_SCHEMA
            or previous.get("schema") != A319_SCHEMA):
        return outcome("LAB_CUSTODY_CEREMONY_VETO",
                       ["ROOT_MANIFESTS_MISSING_OR_WRONG_SCHEMA"])

    rotation = assess_offline_root_transition(**transition_request)
    transition_math = (
        rotation["status"] == "LAB_MATH_CONTINUITY_VALID_NO_EXTERNAL_PIN"
    )
    if not transition_math:
        return outcome("LAB_CUSTODY_CEREMONY_VETO",
                       ["A319_ROTATION_MATHEMATICS_DENIED"])

    expected = {
        "schema": SCHEMA,
        "candidate_manifest_sha256": sha(encode(candidate)),
        "previous_manifest_sha256": sha(encode(previous)),
        "root_generation": candidate.get("generation"),
        "incident_epoch": candidate.get("incident_epoch"),
        "high_water_sequence": candidate.get("high_water_sequence"),
        "high_water_sha256": candidate.get("high_water_sha256"),
        "challenge_nonce": candidate.get("challenge_nonce"),
    }
    for k, value in expected.items():
        if offline_precommit.get(k) != value:
            issues.append("PRECOMMIT_" + k.upper() + "_MISMATCH")
    if offline_precommit.get("recorded_at", -1) >= candidate.get("issued_at", -1):
        issues.append("PRECOMMIT_NOT_BEFORE_ROTATION")

    if any(not _safe_id(k) or not _hex64(v) for k, v in custodian_pins.items()):
        return outcome("LAB_CUSTODY_CEREMONY_VETO",
                       ["CUSTODIAN_PIN_FORMAT_INVALID"], 0, transition_math)
    if len(set(custodian_pins.values())) != 2:
        issues.append("CUSTODIAN_PINS_REUSED")

    identities = []
    signatures = 0
    for packet in custodian_packets:
        if not _shape_packet(packet):
            issues.append("CUSTODIAN_PACKET_INVALID")
            continue
        identities.append((
            packet["custodian_id"], packet["custody_domain"],
            packet["channel_id"], packet["device_id"],
            packet["evidence_digest"],
        ))
        for k, v in offline_precommit.items():
            if packet.get(k) != v:
                issues.append("CUSTODIAN_PACKET_PRECOMMIT_MISMATCH")
                break
        if packet["witnessed_at"] <= offline_precommit["recorded_at"]:
            issues.append("CUSTODIAN_PACKET_BEFORE_PRECOMMIT")
        if packet["witnessed_at"] >= candidate["expires_at"]:
            issues.append("CUSTODIAN_PACKET_EXPIRED")
        pin = custodian_pins.get(packet["custodian_id"])
        if pin is None:
            issues.append("CUSTODIAN_NOT_IN_PINSET")
        elif _hex64(pin):
            try:
                Ed25519PublicKey.from_public_bytes(bytes.fromhex(pin)).verify(
                    bytes.fromhex(packet["signature_hex"]),
                    signable_bytes(packet),
                )
                signatures += 1
            except (InvalidSignature, ValueError, TypeError, OverflowError,
                    KeyError):
                issues.append("CUSTODIAN_SIGNATURE_INVALID")
    if len(identities) == 2:
        if {pair[0] for pair in identities} != set(custodian_pins):
            issues.append("CUSTODIAN_ID_SET_MISMATCH")
        for idx, label in enumerate((
            "CUSTODIAN_ID", "CUSTODY_DOMAIN", "DELIVERY_CHANNEL",
            "MEDIA_DEVICE", "EVIDENCE_DIGEST",
        )):
            if identities[0][idx] == identities[1][idx]:
                issues.append(label + "_REUSED")
    else:
        issues.append("BOTH_PACKET_IDENTITIES_UNVERIFIABLE")
    if signatures != 2:
        issues.append("TWO_VALID_CUSTODIAN_SIGNATURES_REQUIRED")
    if issues:
        return outcome("LAB_CUSTODY_CEREMONY_VETO", issues,
                       signatures, transition_math)
    return outcome(
        "LAB_TWO_CUSTODY_PACKETS_COHERENT_BUT_UNVERIFIED",
        [], signatures, transition_math,
    )


__all__ = [
    "SCHEMA", "TRANSITION_KEYS", "PRECOMMIT_FIELDS", "SIGNED_FIELDS",
    "ALL_FIELDS", "signable_bytes", "verify_offline_custody_ceremony",
]
