"""A321 LAB: 2/2 signed high-water continuity and fork detection.

This is a verifier of synthetic caller-supplied data, NOT off-host storage,
custodian identity, immutability, delivery, provider effects or P0 approval.
Both keys and the alleged pinned head can be reminted by the same host.
No network, real writes, Worker, deploy, privileged access or retry.
"""
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from labs.a317_detached_signed_intent_anchor_lab import encode
from labs.a320_offline_custody_ceremony_lab import (
    verify_offline_custody_ceremony, _safe_id, _hex64, _nonneg_int,
)

SCHEMA = "ATLASQUANT_AION_A321_HIGH_WATER_FORK_DETECTION_LAB_V1"
DOMAIN = b"ATLASQUANT_AION_A321_HIGH_WATER_FORK_DETECTION_LAB_V1\x00"
SIGN_FIELDS = frozenset((
    "schema", "custodian_id", "root_generation", "incident_epoch",
    "sequence", "previous_sequence", "previous_head_sha256",
    "head_sha256", "intent_digest", "challenge_nonce", "issued_at",
    "expires_at", "decision",
))
REPORT_FIELDS = SIGN_FIELDS | {"signature_hex"}
START_FIELDS = frozenset((
    "generation", "incident_epoch", "sequence", "head_sha256",
))
LIMIT_CHECKPOINTS = 4


def signing_bytes(record):
    return DOMAIN + encode({key: record[key] for key in sorted(SIGN_FIELDS)})


def _report_shape(r):
    return (
        type(r) is dict and set(r) == REPORT_FIELDS
        and r["schema"] == SCHEMA and r["decision"] == "HOLD_ONLY"
        and _safe_id(r["custodian_id"])
        and all(_nonneg_int(r[k]) for k in (
            "root_generation", "incident_epoch", "sequence",
            "previous_sequence", "issued_at", "expires_at",
        ))
        and all(_hex64(r[k]) for k in (
            "previous_head_sha256", "head_sha256",
            "intent_digest", "challenge_nonce",
        ))
        and type(r["signature_hex"]) is str
        and len(r["signature_hex"]) == 128
        and all(c in "0123456789abcdef" for c in r["signature_hex"])
    )


def _signature_ok(r, pin):
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(pin)).verify(
            bytes.fromhex(r["signature_hex"]), signing_bytes(r),
        )
        return True
    except (InvalidSignature, ValueError, TypeError, OverflowError, KeyError):
        return False


def report(status, issues, *, count=0):
    return {
        "schema": SCHEMA, "status": status, "issues": sorted(set(issues)),
        "mathematically_consistent_checkpoints": count,
        "mathematical_chain_consistency_observed": (
            status == "LAB_CONSISTENT_SIGNED_HISTORY_NO_EXTERNAL_CUSTODY"
        ),
        "research_only": True, "synthetic_only": True,
        "actual_custodians_independently_identified": False,
        "external_pin_independently_authenticated": False,
        "independent_delivery_authenticated": False,
        "off_host_high_water_authentic": False,
        "immutable_custody_proven": False,
        "trusted_nonce_origin_proven": False,
        "trusted_clock_proven": False,
        "provider_ack_verified": False,
        "semantic_exactly_once_proven": False,
        "can_authorize_real_effect": False, "can_resume": False,
        "can_resend": False, "can_auto_retry": False,
        "automatic_retries": 0, "zero_auto_resend": True,
        "hard_no_go": True, "p0_homologated": 0,
        "no_worker_deploy_provider_orders": True,
        "new_paid_services": False,
    }


def verify_signed_high_water_history(
    *, ceremony_request, starting_reference, checkpoints,
    expected_challenges, observed_clock_epoch, competing_reports=(),
    revoked_custodian_ids=(),
):
    """Cross-check a 2-of-2 sequence AFTER re-verifying A320 ceremony.

    Every proof is generated locally in LAB. Caller can replace the entire
    ceremony, keys, baseline, challenges and history, so even perfect 2/2
    signatures are never sufficient to authorize a real effect.
    """
    if type(ceremony_request) is not dict or set(ceremony_request) != {
        "transition_request", "offline_precommit",
        "custodian_packets", "custodian_pins",
    }:
        return report("LAB_HIGH_WATER_VETO", ["A320_ENVELOPE_INVALID"])
    try:
        ceremony = verify_offline_custody_ceremony(**ceremony_request)
    except (TypeError, KeyError, ValueError, OverflowError, AttributeError):
        return report("LAB_HIGH_WATER_VETO", ["A320_ENVELOPE_UNVERIFIABLE"])
    if ceremony["status"] != "LAB_TWO_CUSTODY_PACKETS_COHERENT_BUT_UNVERIFIED":
        return report("LAB_HIGH_WATER_VETO", ["A320_CEREMONY_VETO"])
    pre = ceremony_request["offline_precommit"]
    pins = ceremony_request["custodian_pins"]
    if (type(starting_reference) is not dict
            or set(starting_reference) != START_FIELDS
            or not all(_nonneg_int(starting_reference[k])
                       for k in ("generation", "incident_epoch", "sequence"))
            or not _hex64(starting_reference["head_sha256"])):
        return report("LAB_HIGH_WATER_VETO", ["BASELINE_REFERENCE_INVALID"])
    base = starting_reference
    if (
        base["generation"] != pre["root_generation"]
        or base["incident_epoch"] != pre["incident_epoch"]
        or base["sequence"] != pre["high_water_sequence"]
        or base["head_sha256"] != pre["high_water_sha256"]
    ):
        return report("LAB_HIGH_WATER_VETO", ["BASELINE_NOT_LINKED_TO_CEREMONY"])
    if (type(checkpoints) not in (list, tuple)
            or not 1 <= len(checkpoints) <= LIMIT_CHECKPOINTS
            or type(expected_challenges) not in (list, tuple)
            or len(expected_challenges) != len(checkpoints)):
        return report("LAB_HIGH_WATER_VETO", ["CHECKPOINT_COUNT_OR_CHALLENGES_INVALID"])
    if (type(observed_clock_epoch) is not int
            or observed_clock_epoch < 0
            or type(competing_reports) not in (list, tuple)
            or len(competing_reports) > 8
            or type(revoked_custodian_ids) not in (list, tuple, frozenset)
            or any(not _safe_id(x) for x in revoked_custodian_ids)):
        return report("LAB_HIGH_WATER_VETO", ["CLOCK_COMPETING_OR_REVOCATION_INVALID"])
    if (len(set(revoked_custodian_ids)) != len(revoked_custodian_ids)
            or any(x in pins for x in revoked_custodian_ids)):
        return report("LAB_HIGH_WATER_VETO", ["CUSTODIAN_REVOKED_OR_DUPLICATE"])
    if (any(not _hex64(nonce) for nonce in expected_challenges)
            or len(set(expected_challenges)) != len(expected_challenges)):
        return report("LAB_HIGH_WATER_VETO", ["CHALLENGE_INVALID_OR_REPLAYED"])

    issues = []
    prev_seq, prev_head = base["sequence"], base["head_sha256"]
    prev_issued = pre["recorded_at"]
    seen_signed = {}
    completed = 0
    for i, bundle in enumerate(checkpoints):
        if type(bundle) not in (list, tuple) or len(bundle) != 2:
            issues.append("EXACT_TWO_SIGNED_CHECKPOINTS_REQUIRED")
            break
        identities = set()
        common = None
        valid = 0
        for witness in bundle:
            if not _report_shape(witness):
                issues.append("CHECKPOINT_FIELDS_INVALID")
                continue
            who = witness["custodian_id"]
            if who in identities:
                issues.append("CHECKPOINT_CUSTODIAN_REUSED")
            identities.add(who)
            if who not in pins:
                issues.append("CHECKPOINT_CUSTODIAN_NOT_PINNED")
                continue
            if not _signature_ok(witness, pins[who]):
                issues.append("CHECKPOINT_SIGNATURE_INVALID")
                continue
            valid += 1
            matched = (
                witness["root_generation"], witness["incident_epoch"],
                witness["sequence"], witness["previous_sequence"],
                witness["previous_head_sha256"], witness["head_sha256"],
                witness["intent_digest"], witness["challenge_nonce"],
            )
            if common is None:
                common = matched
            elif common != matched:
                issues.append("SIGNED_CHECKPOINT_FORK_OR_DISAGREEMENT")
            if witness["root_generation"] != base["generation"]:
                issues.append("ROOT_GENERATION_REPLAY_OR_MISMATCH")
            if witness["incident_epoch"] != base["incident_epoch"]:
                issues.append("INCIDENT_EPOCH_ROLLBACK_OR_REOPEN")
            if witness["previous_sequence"] != prev_seq:
                issues.append("PREVIOUS_SEQUENCE_ROLLBACK_OR_GAP")
            if witness["sequence"] != prev_seq + 1:
                issues.append("CHECKPOINT_SEQUENCE_ROLLBACK_OR_GAP")
            if witness["previous_head_sha256"] != prev_head:
                issues.append("PREVIOUS_HEAD_MISMATCH")
            if witness["head_sha256"] == prev_head:
                issues.append("NO_FORWARD_HEAD_CHANGE")
            if witness["challenge_nonce"] != expected_challenges[i]:
                issues.append("CHALLENGE_NOT_AUTHORIZED_BY_CALLER")
            if (witness["issued_at"] <= prev_issued
                    or witness["expires_at"] <= witness["issued_at"]
                    or witness["expires_at"] - witness["issued_at"] > 900
                    or not witness["issued_at"] <= observed_clock_epoch
                    < witness["expires_at"]):
                issues.append("CHECKPOINT_TIME_INVALID")
            seen_signed[(who, witness["sequence"])] = witness["head_sha256"]
        if identities != set(pins) or valid != 2:
            issues.append("TWO_VERIFIED_DISTINCT_CUSTODIANS_REQUIRED")
        if issues:
            break
        prev_seq, prev_head = common[2], common[5]
        prev_issued = max(packet["issued_at"] for packet in bundle)
        completed += 1

    for extra in competing_reports:
        if not _report_shape(extra):
            issues.append("COMPETING_REPORT_MALFORMED")
            continue
        who = extra["custodian_id"]
        if who not in pins or not _signature_ok(extra, pins[who]):
            issues.append("COMPETING_REPORT_NOT_AUTHENTICATED_BY_DECLARED_PIN")
            continue
        key = (who, extra["sequence"])
        if key not in seen_signed:
            issues.append("UNEXPECTED_SIGNED_OUT_OF_BAND_SEQUENCE")
        elif seen_signed[key] != extra["head_sha256"]:
            issues.append("SIGNED_HIGH_WATER_EQUIVOCATION")
        else:
            issues.append("UNSOLICITED_SIGNED_CHECKPOINT_REPLAY")
    if issues:
        return report("LAB_HIGH_WATER_VETO", issues, count=completed)
    return report(
        "LAB_CONSISTENT_SIGNED_HISTORY_NO_EXTERNAL_CUSTODY",
        [], count=completed,
    )


__all__ = [
    "SCHEMA", "SIGN_FIELDS", "REPORT_FIELDS", "START_FIELDS",
    "signing_bytes", "verify_signed_high_water_history",
]
