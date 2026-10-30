"""A319: offline root-continuity *math* and bootstrap veto (LAB only).

A caller-provided digest is NOT evidence that an independent custodian
actually pinned it. A valid 2-of-2 old->new key transition does not create
an independent root of trust. No live provider, DB writes, service or GO.
"""
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from labs.a317_detached_signed_intent_anchor_lab import encode, sha

SCHEMA = "ATLASQUANT_AION_A319_OFFLINE_ROOT_CONTINUITY_LAB_V1"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX128 = re.compile(r"[0-9a-f]{128}\Z")
IDENTIFIER = re.compile(r"[A-Za-z0-9._-]{1,80}\Z")
PREVIOUS_FIELDS = frozenset((
    "schema", "generation", "roots", "revoked_root_ids",
    "high_water_sequence", "high_water_sha256", "incident_epoch",
))
CANDIDATE_FIELDS = PREVIOUS_FIELDS | frozenset((
    "previous_manifest_sha256", "challenge_nonce", "issued_at",
    "expires_at", "decision",
))
OLD_DOMAIN = b"ATLASQUANT_AION_A319_OLD_ROOT_APPROVES_LAB_V1\x00"
NEW_DOMAIN = b"ATLASQUANT_AION_A319_NEW_ROOT_PROVES_POSSESSION_LAB_V1\x00"


def result(status, issues, *, old_count=0, new_count=0):
    return {
        "schema": SCHEMA, "status": status,
        "issues": sorted(set(issues)), "old_valid_signatures": old_count,
        "new_valid_signatures": new_count,
        "mathematical_dual_quorum": (
            not issues and old_count == 2 and new_count == 2
        ),
        "research_only": True, "synthetic_only": True,
        "first_bootstrap_allowed": False,
        "out_of_band_reference_independently_authenticated": False,
        "old_root_custody_independently_attested": False,
        "new_root_custody_independently_attested": False,
        "revocation_source_independently_authenticated": False,
        "high_water_off_host_authenticated": False,
        "trusted_clock_attested": False,
        "real_provider_ack_attested": False,
        "independent_intent_custody_proven": False,
        "can_authorize_real_effect": False, "can_resume": False,
        "can_resend": False, "can_auto_retry": False,
        "automatic_retries": 0, "zero_auto_resend": True,
        "hard_no_go": True, "p0_homologated": 0,
        "no_worker_deploy_provider_orders": True,
        "new_paid_services": False,
    }


def _roots_valid(roots):
    if type(roots) is not dict or len(roots) != 2:
        return False
    if any(type(k) is not str or not IDENTIFIER.fullmatch(k)
           or type(v) is not str or not HEX64.fullmatch(v)
           for k, v in roots.items()):
        return False
    return len(set(roots.values())) == 2


def _revoked_valid(value):
    return (
        type(value) is list
        and all(type(v) is str and IDENTIFIER.fullmatch(v)
                for v in value)
        and len(value) == len(set(value))
        and value == sorted(value)
    )


def _manifest_valid(doc, candidate=False):
    wanted = CANDIDATE_FIELDS if candidate else PREVIOUS_FIELDS
    if type(doc) is not dict or set(doc) != wanted:
        return False
    if doc["schema"] != SCHEMA or not _roots_valid(doc["roots"]):
        return False
    if any(type(doc[k]) is not int or doc[k] < 0
           for k in ("generation", "high_water_sequence", "incident_epoch")):
        return False
    if doc["generation"] < 1:
        return False
    if type(doc["high_water_sha256"]) is not str or not HEX64.fullmatch(doc["high_water_sha256"]):
        return False
    if not _revoked_valid(doc["revoked_root_ids"]):
        return False
    if set(doc["roots"]) & set(doc["revoked_root_ids"]):
        return False
    if candidate:
        for name in ("previous_manifest_sha256", "challenge_nonce"):
            if type(doc[name]) is not str or not HEX64.fullmatch(doc[name]):
                return False
        if (type(doc["issued_at"]) is not int or type(doc["expires_at"]) is not int
                or doc["issued_at"] < 0 or doc["expires_at"] < 0
                or doc["decision"] != "HOLD_ONLY"):
            return False
    return True


def authorization_bytes(candidate, *, new_root):
    """Domain-separate old authorization and new proof of possession."""
    return (NEW_DOMAIN if new_root else OLD_DOMAIN) + encode(candidate)


def _verify_quorum(keys, signatures, payload):
    """Require exactly 2 distinct IDs, valid Ed25519 signatures, no extras."""
    if type(signatures) is not dict or set(signatures) != set(keys):
        return 0, ["EXACT_TWO_SIGNATURE_IDS_REQUIRED"]
    count, issues = 0, []
    for root_id in sorted(keys):
        sig = signatures[root_id]
        if type(sig) is not str or not HEX128.fullmatch(sig):
            issues.append("SIGNATURE_SHAPE_INVALID")
            continue
        try:
            Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(keys[root_id])
            ).verify(bytes.fromhex(sig), payload)
            count += 1
        except (InvalidSignature, ValueError, TypeError, OverflowError):
            issues.append("SIGNATURE_UNVERIFIED")
    return count, issues


def assess_offline_root_transition(
    *, previous_manifest, candidate_manifest,
    pinned_previous_digest, old_root_signatures, new_root_signatures,
    expected_nonce, expected_incident_epoch, observed_clock_epoch,
):
    """Check root continuity but NEVER certify external custody or release.

    The caller supplies *all* references. Without independently authenticated
    pin, clock, and head, the outcome can only be a local mathematical HOLD.
    """
    problems = []
    if not _manifest_valid(previous_manifest):
        problems.append("PREVIOUS_ROOT_MANIFEST_INVALID_OR_UNTRUSTED")
    if not _manifest_valid(candidate_manifest, candidate=True):
        problems.append("CANDIDATE_ROOT_MANIFEST_INVALID")
    if (type(pinned_previous_digest) is not str
            or not HEX64.fullmatch(pinned_previous_digest)):
        problems.append("PREVIOUS_DIGEST_PIN_INVALID")
    if type(expected_nonce) is not str or not HEX64.fullmatch(expected_nonce):
        problems.append("NONCE_INVALID")
    if type(expected_incident_epoch) is not int or expected_incident_epoch < 0:
        problems.append("INCIDENT_EPOCH_INVALID")
    if type(observed_clock_epoch) is not int or observed_clock_epoch < 0:
        problems.append("UNTRUSTED_CLOCK_INVALID")
    if problems:
        return result("LAB_ROOT_TRANSITION_VETO", problems)

    old, new = previous_manifest, candidate_manifest
    expected_previous_hash = sha(encode(old))
    if (pinned_previous_digest != expected_previous_hash
            or new["previous_manifest_sha256"] != expected_previous_hash):
        problems.append("PREVIOUS_PIN_OR_LINK_MISMATCH")
    if new["generation"] != old["generation"] + 1:
        problems.append("ROOT_GENERATION_ROLLBACK_OR_GAP")
    if set(new["roots"]) & set(old["roots"]):
        problems.append("ROOT_ID_REUSED_ON_ROTATION")
    if set(new["roots"].values()) & set(old["roots"].values()):
        problems.append("ROOT_KEY_REUSED_ON_ROTATION")
    if set(new["revoked_root_ids"]) != (
        set(old["revoked_root_ids"]) | set(old["roots"])
    ):
        problems.append("REVOKED_ROOT_RESURRECTED_OR_NOT_REVOKED")
    if new["incident_epoch"] != old["incident_epoch"] or new["incident_epoch"] != expected_incident_epoch:
        problems.append("INCIDENT_EPOCH_ROLLBACK_OR_REOPEN")
    if new["high_water_sequence"] < old["high_water_sequence"]:
        problems.append("HIGH_WATER_SEQUENCE_ROLLBACK")
    if (new["high_water_sequence"] == old["high_water_sequence"]
            and new["high_water_sha256"] != old["high_water_sha256"]):
        problems.append("HIGH_WATER_HASH_REPLACED")
    if new["challenge_nonce"] != expected_nonce:
        problems.append("CHALLENGE_NONCE_REPLAY_OR_MISMATCH")
    if (new["expires_at"] <= new["issued_at"]
            or new["expires_at"] - new["issued_at"] > 900
            or not new["issued_at"] <= observed_clock_epoch < new["expires_at"]):
        problems.append("ROTATION_STALE_OR_FUTURE")
    old_count, old_issues = _verify_quorum(
        old["roots"], old_root_signatures,
        authorization_bytes(new, new_root=False),
    )
    new_count, new_issues = _verify_quorum(
        new["roots"], new_root_signatures,
        authorization_bytes(new, new_root=True),
    )
    problems.extend("OLD_" + x for x in old_issues)
    problems.extend("NEW_" + x for x in new_issues)
    if old_count != 2 or new_count != 2:
        problems.append("DUAL_QUORUM_NOT_MET")
    if problems:
        return result("LAB_ROOT_TRANSITION_VETO", problems,
                      old_count=old_count, new_count=new_count)
    return result("LAB_MATH_CONTINUITY_VALID_NO_EXTERNAL_PIN",
                  [], old_count=old_count, new_count=new_count)


__all__ = [
    "SCHEMA", "PREVIOUS_FIELDS", "CANDIDATE_FIELDS",
    "authorization_bytes", "assess_offline_root_transition",
]
