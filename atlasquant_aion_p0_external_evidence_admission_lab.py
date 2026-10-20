"""P0 LAB ONLY — untrusted proof bundle structural admission preflight.

Inputs are ALL supplied by the calling fixture. This is not an external
issuer, verifier, readback service, producer, receipt or replay cache.
No cryptographic signature validation, I/O, clock reads or side effects.
Even a perfectly coherent bundle NEVER produces authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Any

from atlasquant_aion_p0_incident_external_witness_proposal_lab import NO_GO_FLAGS

SCHEMA = "AION_P0_EXTERNAL_EVIDENCE_ADMISSION_LAB_V1"
REQUEST_FIELDS = frozenset(("scope", "request_id", "intent_id", "key_id",
                            "credential_epoch", "epoch", "sequence",
                            "head_digest", "nonce"))
BUNDLE_FIELDS = frozenset(("issuer", "head", "challenge", "revocation",
                            "producer", "administration"))
CLAIM_FIELDS = {
    "issuer": frozenset(("key_id", "scope", "public_key_sha256", "algorithm",
                         "status")),
    "head": frozenset(("scope", "epoch", "sequence", "head_digest", "version_id",
                       "observed_at_utc")),
    "challenge": frozenset(("scope", "request_id", "nonce", "issued_at_utc",
                            "expires_at_utc", "issuer_id")),
    "revocation": frozenset(("key_id", "credential_epoch", "status",
                             "observed_at_utc")),
    "producer": frozenset(("request_id", "intent_id", "outcome",
                           "provider_message_id", "receipt_digest")),
    "administration": frozenset(("executor_root", "issuer_root",
                                 "verifier_root", "recovery_root",
                                 "nonce_cache_root", "producer_root")),
}
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/@-]{2,159}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
DATE = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
ADMIN_FIELDS = tuple(sorted(CLAIM_FIELDS["administration"]))
APPROVAL_GAPS = (
    "ISSUER_ROOT_NOT_INDEPENDENTLY_ENROLLED",
    "SIGNED_LATEST_HEAD_AND_CONSISTENCY_NOT_AUTHENTICATED",
    "VERIFIER_NONCE_DURABILITY_NOT_ATTESTED",
    "CREDENTIAL_REVOCATION_NOT_EXTERNALLY_AUTHENTICATED",
    "PRODUCER_EFFECT_OR_NO_EFFECT_NOT_AUTHENTICATED",
    "HUMAN_OWNER_APPROVAL_NOT_ESTABLISHED",
    "H0_PHYSICAL_RESTART_ROLLBACK_NOT_VERIFIED",
    "QUALITY_AND_SECURITY_CANONICAL_NOT_GREEN",
)


def _id(value: Any) -> bool:
    return type(value) is str and bool(IDENTIFIER.fullmatch(value))


def _digest(value: Any) -> bool:
    return type(value) is str and bool(DIGEST.fullmatch(value))


def _num(value: Any) -> bool:
    return type(value) is int and 0 <= value <= (2**63 - 1)


def _date(value: Any) -> datetime | None:
    if type(value) is not str or not DATE.fullmatch(value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def _validate_shape(kind: str, obj: Any, defects: list[str]) -> dict:
    if type(obj) is not dict or frozenset(obj) != CLAIM_FIELDS[kind]:
        defects.append("CLAIM_SHAPE_INVALID:" + kind)
        return {}
    return obj


def inspect_external_evidence_claims_lab(
    request: Any, bundle: Any, *, now_utc: Any,
    locally_seen_nonces: Any,
) -> dict[str, Any]:
    defects: list[str] = []
    r: dict[str, Any] = {}
    if type(request) is not dict or frozenset(request) != REQUEST_FIELDS:
        defects.append("REQUEST_SHAPE_INVALID")
    else:
        validators = {
            **{k: _id for k in ("scope", "request_id", "intent_id", "key_id", "nonce")},
            **{k: _num for k in ("credential_epoch", "epoch", "sequence")},
            "head_digest": _digest,
        }
        for field, func in validators.items():
            if not func(request[field]):
                defects.append("REQUEST_FIELD_INVALID:" + field)
        if not any(d.startswith("REQUEST_") for d in defects):
            r = request
    if type(bundle) is not dict or frozenset(bundle) != BUNDLE_FIELDS:
        defects.append("BUNDLE_SHAPE_INVALID")
        bundle = {}
    now = _date(now_utc)
    if now is None:
        defects.append("NOW_UTC_INVALID")
    if type(locally_seen_nonces) is not list or len(locally_seen_nonces) > 128:
        defects.append("LOCAL_NONCE_SET_INVALID")
        locally_seen_nonces = []
    elif not all(_id(x) for x in locally_seen_nonces):
        defects.append("LOCAL_NONCE_SET_INVALID")
        locally_seen_nonces = []
    claims = {k: _validate_shape(k, bundle.get(k), defects) for k in sorted(CLAIM_FIELDS)}

    issuer = claims["issuer"]
    if issuer:
        if not (_id(issuer["key_id"]) and _id(issuer["scope"])
                and _digest(issuer["public_key_sha256"])
                and type(issuer["algorithm"]) is str
                and issuer["algorithm"] == "ED25519_SHA_512"
                and type(issuer["status"]) is str
                and issuer["status"] in ("ACTIVE", "REVOKED", "UNKNOWN")):
            defects.append("ISSUER_FIELDS_INVALID")
        else:
            if issuer["status"] != "ACTIVE":
                defects.append("ISSUER_NOT_ACTIVE")
            if r and (issuer["key_id"] != r["key_id"]
                      or issuer["scope"] != r["scope"]):
                defects.append("ISSUER_REQUEST_BINDING_MISMATCH")
    head = claims["head"]
    if head:
        seen = _date(head["observed_at_utc"])
        if not (_id(head["scope"]) and _num(head["epoch"])
                and _num(head["sequence"]) and _digest(head["head_digest"])
                and _id(head["version_id"]) and seen is not None):
            defects.append("HEAD_FIELDS_INVALID")
        else:
            if r and any(head[k] != r[k] for k in (
                "scope", "epoch", "sequence", "head_digest"
            )):
                defects.append("HEAD_REQUEST_BINDING_MISMATCH")
            if now is not None and not (
                now - timedelta(seconds=120) <= seen <= now
            ):
                defects.append("HEAD_OBSERVATION_STALE_OR_FUTURE")
    challenge = claims["challenge"]
    if challenge:
        issued = _date(challenge["issued_at_utc"])
        expiry = _date(challenge["expires_at_utc"])
        if not (_id(challenge["scope"]) and _id(challenge["request_id"])
                and _id(challenge["nonce"]) and _id(challenge["issuer_id"])
                and issued is not None and expiry is not None):
            defects.append("CHALLENGE_FIELDS_INVALID")
        else:
            if r and any(challenge[k] != r[k] for k in (
                "scope", "request_id", "nonce"
            )):
                defects.append("CHALLENGE_BINDING_MISMATCH")
            if not (issued < expiry <= issued + timedelta(seconds=180)):
                defects.append("CHALLENGE_TTL_INVALID")
            if now is not None and not issued <= now < expiry:
                defects.append("CHALLENGE_EXPIRED_OR_NOT_YET_ISSUED")
            if challenge["nonce"] in locally_seen_nonces:
                defects.append("CLAIMED_NONCE_REPLAY_LOCAL")
    revocation = claims["revocation"]
    if revocation:
        seen = _date(revocation["observed_at_utc"])
        if not (_id(revocation["key_id"]) and _num(revocation["credential_epoch"])
                and type(revocation["status"]) is str
                and revocation["status"] in ("ACTIVE", "REVOKED", "UNKNOWN")
                and seen is not None):
            defects.append("REVOCATION_FIELDS_INVALID")
        else:
            if r and (revocation["key_id"] != r["key_id"]
                      or revocation["credential_epoch"] != r["credential_epoch"]):
                defects.append("REVOCATION_REQUEST_BINDING_MISMATCH")
            if revocation["status"] != "ACTIVE":
                defects.append("REVOCATION_STATUS_NOT_ACTIVE")
            if now is not None and not (
                now - timedelta(seconds=120) <= seen <= now
            ):
                defects.append("REVOCATION_OBSERVATION_STALE_OR_FUTURE")
    producer = claims["producer"]
    if producer:
        if not (_id(producer["request_id"]) and _id(producer["intent_id"])
                and type(producer["outcome"]) is str
                and producer["outcome"] in (
                    "COMMITTED_EFFECT", "NO_EFFECT_FENCED", "UNCERTAIN"
                ) and _id(producer["provider_message_id"])
                and _digest(producer["receipt_digest"])):
            defects.append("PRODUCER_FIELDS_INVALID")
        else:
            if r and any(producer[k] != r[k] for k in ("request_id", "intent_id")):
                defects.append("PRODUCER_BINDING_MISMATCH")
            if producer["outcome"] == "UNCERTAIN":
                defects.append("PRODUCER_UNCERTAIN_NO_TERMINAL_PROOF")
    administration = claims["administration"]
    if administration:
        if not all(_id(administration[k]) for k in ADMIN_FIELDS):
            defects.append("ADMIN_ROOT_FIELDS_INVALID")
        else:
            roots = [administration[k] for k in ADMIN_FIELDS]
            if len(set(roots)) != len(roots):
                defects.append("CLAIMED_ADMIN_ROOTS_OVERLAP")

    # Caller-supplied data can be substituted as a whole. There is no
    # trust origin, authenticated signer, monotonic head or durable nonce.
    problems = tuple(sorted(set(defects)))
    blockers = tuple(sorted(set(defects).union(APPROVAL_GAPS)))
    return {
        "schema": SCHEMA, "status": "BLOCKED", "allowed": False,
        "reason": blockers[0], "blockers": blockers,
        "structural_defects": problems,
        "claims_syntactically_coherent_lab": not bool(problems),
        "externally_authenticated": False,
        "off_host_nonce_guard_authenticated": False,
        "latest_head_authenticated": False,
        "no_effect_fence_authenticated": False,
        "simulation_only": True,
        **{flag: False for flag in NO_GO_FLAGS},
    }


__all__ = ["SCHEMA", "REQUEST_FIELDS", "CLAIM_FIELDS", "BUNDLE_FIELDS",
           "APPROVAL_GAPS", "inspect_external_evidence_claims_lab"]
