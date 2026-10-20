"""P0 LAB: prospective Ed25519 trust-anchor bootstrap review, NEVER enrollment.

A caller-controlled bootstrap pin is NOT a real external trust anchor.
The function can compare a SHA-256 key fingerprint and call the earlier
Ed25519 LAB syntax inspector, but cannot prove separate administrators,
unrevoked issuer keys, monotonic off-host high-water, or fresh nonce cache.

All outcomes are BLOCKED. Do not import from production AION execution paths.
No network, key generation, signing or secrets at module level.
"""
from __future__ import annotations

from hashlib import sha256
import re
from typing import Any

from atlasquant_aion_p0_signed_incident_envelope_lab import (
    inspect_signed_incident_envelope_lab,
)
from atlasquant_aion_p0_incident_external_witness_proposal_lab import NO_GO_FLAGS

SCHEMA = "AION_P0_TRUST_ANCHOR_BOOTSTRAP_PREFLIGHT_LAB_V1"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._:/-]{2,127}\Z")
PIN_FIELDS = frozenset((
    "issuer_id", "scope", "key_id", "public_key_sha256",
    "policy_epoch", "minimum_sequence", "minimum_revocation_epoch",
    "key_status", "controller_executor", "controller_issuer",
    "controller_verifier", "controller_recovery",
))


def _id(value: Any) -> bool:
    return type(value) is str and bool(ID.fullmatch(value))


def _unsigned(value: Any) -> bool:
    return type(value) is int and 0 < value < (1 << 63)


def _deny(findings: list[str], *, key_matches: bool, crypto_valid: bool,
          old_inspector_blockers: tuple[str, ...]) -> dict[str, Any]:
    reasons = tuple(sorted(set(findings + [
        "OUT_OF_BAND_BOOTSTRAP_NOT_ATTESTED",
        "LATEST_EXTERNAL_HEAD_NOT_AUTHENTICATED",
        "PERSISTENT_EXTERNAL_NONCE_REPLAY_GUARD_MISSING",
        "ISSUER_REVOCATION_STATUS_NOT_AUTHENTICATED",
    ])))
    return {
        "schema": SCHEMA,
        "status": "BLOCKED",
        "allowed": False,
        "reason": reasons[0],
        "blockers": reasons,
        "key_fingerprint_matches_caller_pin_lab": key_matches,
        "signature_mathematically_valid_with_supplied_key_lab": crypto_valid,
        "signed_inspector_blockers": tuple(old_inspector_blockers),
        "bootstrap_material_is_caller_controlled": True,
        "off_host_root_authenticated": False,
        "off_host_revocation_authenticated": False,
        "off_host_latest_head_authenticated": False,
        "cross_process_nonce_replay_fenced": False,
        "can_issue_production_trust_token": False,
        "simulation_only": True,
        **{key: False for key in NO_GO_FLAGS},
    }


def assess_trust_anchor_bootstrap_lab(
    pin: Any, envelope: Any, signature: Any, candidate_public_key: Any,
    *, observed_head: Any = None, expected_nonce: Any = None,
    now_utc: Any = None,
) -> dict[str, Any]:
    """Negative-only assessment of an UNTRUSTED, caller-supplied pin.

    Even mathematically matching signature+pin or fresh-looking head
    does not constitute trusted enrollment: caller can replace both.
    """
    findings: list[str] = []
    matches = False
    valid = False
    inspector_blockers: tuple[str,...] = ()

    if type(pin) is not dict:
        findings.append("PIN_NOT_PLAIN_DICT")
        pin = {}
    if frozenset(pin) != PIN_FIELDS:
        findings.append("PIN_FIELDS_NOT_EXACT")
    for field in ("issuer_id","scope","key_id",
                  "controller_executor","controller_issuer",
                  "controller_verifier","controller_recovery"):
        if not _id(pin.get(field)):
            findings.append("PIN_FIELD_INVALID:" + field)
    controllers = [
        pin.get("controller_executor"),pin.get("controller_issuer"),
        pin.get("controller_verifier"),pin.get("controller_recovery"),
    ]
    if all(_id(c) for c in controllers):
        if len(set(controllers))!=4:
            findings.append("CLAIMED_ADMINISTRATIVE_DOMAINS_OVERLAP")
        # Even 4 distinct strings do not establish operational independence.
    digest = pin.get("public_key_sha256")
    if type(digest) is not str or not HEX64.fullmatch(digest):
        findings.append("PIN_KEY_FINGERPRINT_INVALID")
    for field in ("policy_epoch","minimum_sequence","minimum_revocation_epoch"):
        if not _unsigned(pin.get(field)):
            findings.append("PIN_FIELD_INVALID:" + field)
    if pin.get("key_status") not in ("ACTIVE","REVOKED","UNKNOWN") or (
        type(pin.get("key_status")) is not str
    ):
        findings.append("PIN_KEY_STATUS_INVALID")
    elif pin["key_status"]!="ACTIVE":
        findings.append("PIN_KEY_REVOKED_OR_UNKNOWN")

    if type(candidate_public_key) is not bytes or len(candidate_public_key)!=32:
        findings.append("CANDIDATE_KEY_BYTES_INVALID")
    elif type(digest) is str and HEX64.fullmatch(digest):
        matches=sha256(candidate_public_key).hexdigest()==digest
        if not matches:
            findings.append("CANDIDATE_KEY_FINGERPRINT_MISMATCH")

    if type(envelope) is not bytes or not (1<=len(envelope)<=4096):
        findings.append("ENVELOPE_BYTES_INVALID")
    if type(signature) is not bytes or len(signature)!=64:
        findings.append("SIGNATURE_BYTES_INVALID")

    # Avoid attacker-controlled class methods, coerced bool/int, and any
    # assertion that the caller's "pin" is externally enrolled.
    if (
        type(candidate_public_key) is bytes and len(candidate_public_key)==32
        and type(envelope) is bytes and 1<=len(envelope)<=4096
        and type(signature) is bytes and len(signature)==64
        and _id(pin.get("issuer_id")) and _id(pin.get("scope"))
        and _id(expected_nonce) and type(now_utc) is str
    ):
        observation=inspect_signed_incident_envelope_lab(
            envelope,signature,candidate_public_key,
            expected_issuer=pin["issuer_id"],expected_scope=pin["scope"],
            expected_nonce=expected_nonce,now_utc=now_utc,
            observed_head=observed_head,
        )
        valid = observation["signature_mathematically_valid_with_caller_key_in_lab"]
        inspector_blockers=observation["blockers"]
        findings.extend(
            "SIGNED_INSPECTOR:" + x for x in inspector_blockers
            if x not in (
                "OUT_OF_BAND_SIGNER_NOT_ENROLLED",
                "EXTERNAL_NONCE_REPLAY_GUARD_NOT_ENROLLED",
                "INDEPENDENT_LATEST_HEAD_NOT_AUTHENTICATED",
            )
        )
        # Compare only typed parsed data: our signed inspector's consistency
        # checks do not establish that the pin is the authoritative latest.
        import json
        try:
            decoded=json.loads(envelope.decode("utf-8"))
        except (UnicodeError,ValueError,TypeError,RecursionError):
            decoded={}
        if type(decoded) is dict:
            if type(decoded.get("key_id")) is not str or decoded.get("key_id")!=pin.get("key_id"):
                findings.append("PIN_ENVELOPE_KEY_ID_MISMATCH")
            for k,pinned in (
                ("epoch","policy_epoch"),
                ("sequence","minimum_sequence"),
                ("credential_revocation_epoch","minimum_revocation_epoch"),
            ):
                value=decoded.get(k)
                minimum=pin.get(pinned)
                if not (_unsigned(value) and _unsigned(minimum)) or value<minimum:
                    findings.append("PIN_MONOTONIC_FLOOR_FAILED:" + k)
        else:
            findings.append("ENVELOPE_NOT_OBJECT")

    return _deny(findings,key_matches=matches,crypto_valid=valid,
                 old_inspector_blockers=inspector_blockers)


__all__=["SCHEMA","PIN_FIELDS","assess_trust_anchor_bootstrap_lab"]
