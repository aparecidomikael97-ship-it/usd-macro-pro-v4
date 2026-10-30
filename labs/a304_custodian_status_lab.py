"""A304 LAB — signer outage, revocation, expiry and signed equivocation.

All status signing keys and the last-seen head are SYNTHETIC/local test data.
An Ed25519 valid status is not proof of independent current revocation state.
This module NEVER authorizes restore, retry, Worker, deploy or real effects.
"""
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from labs.a302_witness_receipt_contract_lab import _encoded, _hash, _valid_hash
from labs.a303_custody_anchor_chain_lab import assess_custody_anchor

SCHEMA = "ATLASQUANT_AION_A304_CUSTODIAN_STATUS_LAB_V1"
DOMAIN = b"ATLASQUANT_AION_A304_CUSTODIAN_STATUS_LAB_V1\x00"
STATUS_FIELDS = frozenset({
    "schema", "status_key_id", "root_key_id", "subject_id", "source_id",
    "anchor_sha256", "key_epoch", "incident_epoch", "status_sequence",
    "previous_status_hash", "valid_from", "expires_at", "decision",
    "signature_hex",
})
SIGNED_FIELDS = STATUS_FIELDS - {"signature_hex"}
DECISIONS = frozenset(("ACTIVE", "SUSPENDED", "REVOKED"))
HEX_128 = re.compile(r"[0-9a-f]{128}\Z")
MAX_STATUS_TTL = 900


def status_signing_bytes(status):
    """Sign exact, domain-separated canonical status statement."""
    return DOMAIN + _encoded({key: status[key] for key in sorted(SIGNED_FIELDS)})


def assess_custodian_status(
    *, a303_inputs, statuses, pinned_status_public_key,
    pinned_status_key_id, trusted_status_head, now_epoch,
    custodian_online,
):
    """Fail closed for any status uncertainty; local 'ACTIVE' is never GO.

    Even when signatures verify, the last-seen head, timestamp, trusted
    public keys and availability all originate in the caller's host.
    """
    issues = set()
    out = {
        "schema": SCHEMA, "research_only": True,
        "a303_local_package_consistent": False,
        "cryptographic_status_count": 0,
        "local_status_consistent": False,
        "independent_status_proven": False,
        "off_host_head_proven": False,
        "owner_authorization_proven": False,
        "revocation_completeness_proven": False,
        "can_resume": False, "can_authorize_real_effect": False,
        "zero_auto_resend": True, "automatic_retries": 0,
        "hard_no_go": True, "p0_homologated": 0,
        "new_paid_services": False,
    }

    if (type(a303_inputs) is not dict or set(a303_inputs) != {
        "a302_inputs", "anchor", "pinned_root_public_key",
        "pinned_root_key_id", "expected_subject_id",
        "previous_anchor_sequence", "previous_anchor_hash",
        "incident_epoch_floor", "key_epoch_floor",
    }):
        issues.add("A303_INPUTS_INVALID")
        a303_inputs = {}
    else:
        try:
            parent = assess_custody_anchor(**a303_inputs)
            out["a303_local_package_consistent"] = (
                parent["local_package_consistent"] is True
            )
            if not out["a303_local_package_consistent"]:
                issues.add("A303_ANCHOR_OR_RECEIPTS_INVALID")
        except (TypeError, ValueError, KeyError):
            issues.add("A303_ANCHOR_OR_RECEIPTS_INVALID")

    if type(pinned_status_public_key) is not bytes or len(
        pinned_status_public_key
    ) != 32:
        issues.add("STATUS_PUBLIC_KEY_INVALID")
    if type(pinned_status_key_id) is not str or not pinned_status_key_id:
        issues.add("STATUS_KEY_ID_INVALID")
    if type(custodian_online) is not bool or not custodian_online:
        issues.add("CUSTODIAN_OFFLINE_OR_UNVERIFIED")
    if type(now_epoch) is not int or now_epoch < 0:
        issues.add("UNTRUSTED_CLOCK_FORMAT")
    if (type(trusted_status_head) is not dict or
            set(trusted_status_head) != {"sequence", "status_hash"} or
            type(trusted_status_head["sequence"]) is not int or
            trusted_status_head["sequence"] < 0 or
            not _valid_hash(trusted_status_head["status_hash"])):
        issues.add("LAST_KNOWN_STATUS_HEAD_INVALID")
        trusted_status_head = None

    if type(a303_inputs.get("pinned_root_public_key")) is bytes and (
        pinned_status_public_key ==
        a303_inputs["pinned_root_public_key"]
    ):
        issues.add("STATUS_KEY_REUSES_ROOT_KEY")
    witnesses = a303_inputs.get("a302_inputs")
    if type(witnesses) is dict:
        keys = witnesses.get("pinned_public_keys")
        if type(keys) is dict and pinned_status_public_key in keys.values():
            issues.add("STATUS_KEY_REUSES_WITNESS_KEY")

    if type(statuses) is not list or not (1 <= len(statuses) <= 2):
        issues.add("STATUS_NOT_AVAILABLE_OR_TOO_MANY")
        statuses = []
    anchor = a303_inputs.get("anchor")
    if type(anchor) is not dict:
        anchor = {}
    anchor_sha = _hash(_encoded(anchor))
    accepted = []
    seen_hashes = set()
    for status in statuses:
        if type(status) is not dict or set(status) != STATUS_FIELDS:
            issues.add("STATUS_FIELDS_INVALID")
            continue
        if status["schema"] != SCHEMA:
            issues.add("STATUS_SCHEMA_INVALID")
        if status["status_key_id"] != pinned_status_key_id:
            issues.add("STATUS_KEY_ID_MISMATCH")
        if status["root_key_id"] != anchor.get("root_key_id"):
            issues.add("ROOT_ID_MISMATCH")
        if status["subject_id"] != anchor.get("subject_id"):
            issues.add("SUBJECT_SCOPE_MISMATCH")
        if status["source_id"] != anchor.get("source_id"):
            issues.add("SOURCE_SCOPE_MISMATCH")
        if status["anchor_sha256"] != anchor_sha:
            issues.add("ANCHOR_BINDING_MISMATCH")
        for key in ("key_epoch", "incident_epoch"):
            if type(status[key]) is not int or status[key] != anchor.get(key):
                issues.add("INCIDENT_OR_KEY_EPOCH_MISMATCH")
        if (trusted_status_head is None or
                type(status["status_sequence"]) is not int or
                status["status_sequence"] !=
                trusted_status_head["sequence"] + 1 or
                status["previous_status_hash"] !=
                trusted_status_head["status_hash"]):
            issues.add("STATUS_REPLAY_OR_HEAD_DISCONTINUITY")
        if (type(status["valid_from"]) is not int or
                type(status["expires_at"]) is not int or
                status["valid_from"] < 0 or
                status["expires_at"] <= status["valid_from"] or
                status["expires_at"] - status["valid_from"] > MAX_STATUS_TTL):
            issues.add("STATUS_TIME_WINDOW_INVALID")
        elif type(now_epoch) is int and (
                now_epoch < status["valid_from"] or
                now_epoch >= status["expires_at"]):
            issues.add("STATUS_STALE_OR_NOT_YET_VALID")
        if status["decision"] not in DECISIONS:
            issues.add("STATUS_DECISION_INVALID")
        sig = status["signature_hex"]
        if type(sig) is not str or HEX_128.fullmatch(sig) is None:
            issues.add("STATUS_SIGNATURE_FORMAT_INVALID")
            continue
        if (type(pinned_status_public_key) is not bytes or
                len(pinned_status_public_key) != 32):
            continue
        try:
            Ed25519PublicKey.from_public_bytes(
                pinned_status_public_key
            ).verify(bytes.fromhex(sig), status_signing_bytes(status))
        except (InvalidSignature, ValueError, TypeError, KeyError):
            issues.add("STATUS_SIGNATURE_INVALID")
        else:
            accepted.append(status)
            seen_hashes.add(_hash(_encoded(status)))
    out["cryptographic_status_count"] = len(accepted)
    if len(statuses) == 2:
        if len(accepted) == 2 and len(seen_hashes) == 2:
            issues.add("SIGNED_EQUIVOCATION_AT_SAME_STATUS_SEQUENCE")
        elif len(accepted) == 2 and len(seen_hashes) == 1:
            issues.add("DUPLICATE_STATUS_RECEIPT")
        else:
            issues.add("UNVERIFIABLE_CONFLICTING_STATUS")
    for item in accepted:
        if item["decision"] == "REVOKED":
            issues.add("CUSTODIAN_KEY_REVOKED")
        elif item["decision"] == "SUSPENDED":
            issues.add("CUSTODIAN_SUSPENDED")
    # No authenticated independent custody or online revocation source.
    out["local_status_consistent"] = (
        not issues and len(accepted) == 1 and
        accepted[0]["decision"] == "ACTIVE" and
        out["a303_local_package_consistent"]
    )
    issues.add("EXTERNAL_REVOCATION_AND_CUSTODY_NOT_ATTESTED")
    out["issues"] = sorted(issues)
    return out


__all__ = [
    "SCHEMA", "STATUS_FIELDS", "MAX_STATUS_TTL",
    "status_signing_bytes", "assess_custodian_status",
]
