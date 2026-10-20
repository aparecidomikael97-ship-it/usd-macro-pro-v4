"""AION P0 LAB: read-only screening of external incident witness proposals.

ABSOLUTE NO-GO: This code is NOT an issuer, signature verifier, fresh-head
reader, credential revocation oracle, replay cache or authorization gate.
It accepts only inert built-in dictionaries and tests *structural* consistency.
ALL results remain BLOCKED: no real out-of-band enrollment is available.
Never wire this lab class to Worker/Outbox/Saga, activation or first effect.
"""
from __future__ import annotations

import re
from typing import Any

SCHEMA = "AION_P0_INDEPENDENT_INCIDENT_WITNESS_ENROLLMENT_LAB_V1"
BLOCKED = "BLOCKED"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:/-]{2,127}$")
NO_GO_FLAGS = (
    "human_owner_authenticated",
    "signer_trust_root_enrolled",
    "issuer_signature_verified",
    "independent_highwater_authenticated",
    "fresher_incident_absence_verified",
    "nonce_replay_cache_verified",
    "credential_revocation_verified",
    "scope_bound_to_external_identity",
    "real_object_lock_readback_verified",
    "producer_effect_receipt_authenticated",
    "no_effect_fenced",
    "first_attempt_cleared",
    "worker_arming_allowed",
    "feature_flag_enable_allowed",
    "execution_allowed",
    "automatic_retry_allowed",
    "external_action_executed",
)
CONTROLLERS = ("executor", "custodian", "anchor", "head_issuer", "verifier")
REQUIRED = (
    "issuer_id", "key_id", "epoch", "sequence", "head_digest", "nonce",
    "scope", "credential_revocation_epoch", "incident_state"
)
STATES = {"NO_OPEN_INCIDENTS", "OPEN_INCIDENT", "UNKNOWN"}


def _string(value: Any) -> bool:
    return type(value) is str and bool(ID.fullmatch(value))


def _digest(value: Any) -> bool:
    return type(value) is str and bool(HEX64.fullmatch(value))


def _nonnegative_int(value: Any) -> bool:
    return type(value) is int and 0 <= value <= 2**63 - 1


def _result(blockers: list[str], observations: list[str]) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "status": BLOCKED, "allowed": False,
        "reason": blockers[0] if blockers else "INDEPENDENT_EXTERNAL_WITNESS_NOT_ENROLLED",
        "blockers": sorted(set(blockers or ["INDEPENDENT_EXTERNAL_WITNESS_NOT_ENROLLED"])),
        "observations": tuple(sorted(set(observations))),
        "lab_structural_review_only": True,
        **{key: False for key in NO_GO_FLAGS},
    }


def screen_external_incident_witness_proposal(
    packet: dict[str, Any] | None,
    pinned_head: dict[str, Any] | None,
    trust_domains: dict[str, Any] | None,
) -> dict[str, Any]:
    """Screen *untrusted* inert fixture metadata. Never authenticates it.

    Even a perfectly coherent fixture cannot establish externally signed,
    monotonic and fresh state, authorization by HUMAN_OWNER, or no prior effect.
    The "pinned_head" argument is itself caller-provided and UNTRUSTED.
    """
    blockers: list[str] = []
    observations: list[str] = []
    if type(packet) is not dict:
        blockers.append("PACKET_NOT_PLAIN_DICT")
        packet = {}
    if type(pinned_head) is not dict:
        blockers.append("PINNED_HEAD_NOT_PLAIN_DICT")
        pinned_head = {}
    if type(trust_domains) is not dict:
        blockers.append("TRUST_DOMAINS_NOT_PLAIN_DICT")
        trust_domains = {}

    for field in REQUIRED:
        if field not in packet:
            blockers.append("PACKET_MISSING:" + field)
    for field in ("issuer_id", "key_id", "nonce", "scope"):
        if field in packet and not _string(packet[field]):
            blockers.append("PACKET_INVALID:" + field)
    for field in ("epoch", "sequence", "credential_revocation_epoch"):
        if field in packet and not _nonnegative_int(packet[field]):
            blockers.append("PACKET_INVALID:" + field)
    if "head_digest" in packet and not _digest(packet["head_digest"]):
        blockers.append("PACKET_INVALID:head_digest")
    if "incident_state" in packet and (
        type(packet["incident_state"]) is not str
        or packet["incident_state"] not in STATES
    ):
        blockers.append("PACKET_INVALID:incident_state")
    if packet.get("incident_state") != "NO_OPEN_INCIDENTS":
        blockers.append("INCIDENT_STATE_UNSAFE_OR_UNKNOWN")

    for key in CONTROLLERS:
        if not _string(trust_domains.get(key)):
            blockers.append("ADMINISTRATIVE_CONTROLLER_UNKNOWN:" + key)
    values = [trust_domains.get(k) for k in CONTROLLERS]
    if all(_string(v) for v in values):
        if len(set(values)) != len(values):
            blockers.append("CLAIMED_ADMIN_DOMAINS_NOT_DISTINCT")
        else:
            observations.append("CONTROLLERS_CLAIMED_DISTINCT_NOT_VERIFIED")

    expected = {
        "issuer_id": packet.get("issuer_id"),
        "scope": packet.get("scope"),
        "head_digest": packet.get("head_digest"),
        "epoch": packet.get("epoch"),
        "sequence": packet.get("sequence"),
        "credential_revocation_epoch": packet.get("credential_revocation_epoch"),
    }
    for field, observed in expected.items():
        if field not in pinned_head:
            blockers.append("PINNED_HEAD_MISSING:" + field)
        elif type(pinned_head[field]) is not type(observed) or pinned_head[field] != observed:
            blockers.append("HEAD_MISMATCH:" + field)

    # Same metadata is not a cryptographically anchored, external monotonic head.
    for field in ("latest_external_version_id", "witnessed_nonce"):
        if not _string(pinned_head.get(field)):
            blockers.append("LATEST_HEAD_READBACK_MISSING:" + field)
    if pinned_head.get("witnessed_nonce") != packet.get("nonce"):
        blockers.append("NONCE_NOT_BOUND_TO_HEAD")

    if packet.get("credential_revocation_epoch") != pinned_head.get("credential_revocation_epoch"):
        blockers.append("CREDENTIAL_REVOCATION_EPOCH_MISMATCH")

    # These optimistic booleans are attacker-provided and never grant authority.
    if any(packet.get(key) is True for key in (
        "signed", "verified", "issuer_signature_verified",
        "external_authority_verified", "source_fresh", "no_incident_confirmed"
    )):
        observations.append("UNTRUSTED_BOOLEAN_SIGNATURE_CLAIMS_IGNORED")
    if any(pinned_head.get(key) is True for key in (
        "readback_authenticated", "independent_issuer_verified", "latest_head_verified"
    )):
        observations.append("UNTRUSTED_READBACK_CLAIMS_IGNORED")

    # This proposal has *no* authenticated freshness service or persistent
    # nonce cache enrolled outside a rollback domain. No caller value lifts NO-GO.
    blockers.append("INDEPENDENT_EXTERNAL_WITNESS_NOT_ENROLLED")
    blockers.append("EXTERNAL_SIGNER_AND_REVOCATION_ROOT_NOT_ENROLLED")
    blockers.append("LATEST_HEAD_AND_NONCE_REPLAY_PROOF_NOT_ENROLLED")
    return _result(blockers, observations)


__all__ = ["SCHEMA", "BLOCKED", "CONTROLLERS", "NO_GO_FLAGS",
           "screen_external_incident_witness_proposal"]
