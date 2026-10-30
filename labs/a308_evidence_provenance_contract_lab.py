"""A308 LAB-only: bind A306 evidence claims to bytes and Ed25519 receipts.

Cryptography is real, identities and pinsets are fabricated on one CI host.
NEVER equate a matching digest/signature with external provider acknowledgement.
ZERO_AUTO_RESEND, HARD NO-GO; no I/O, provider, worker, deployment or recovery.
"""
import hashlib
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from labs.a302_witness_receipt_contract_lab import _encoded
from labs.a306_manual_intent_reconciliation_lab import (
    SCHEMA as CASE_SCHEMA, CLAIM_FIELDS,
)

SCHEMA = "ATLASQUANT_AION_A308_EVIDENCE_PROVENANCE_LAB_V1"
DOMAIN = b"ATLASQUANT_AION_A308_EVIDENCE_PROVENANCE_LAB_V1\x00"
RECEIPT_FIELDS = frozenset({
    "schema", "source_id", "reference_id", "intent_id", "message_id",
    "observed_outcome", "evidence_sha256", "case_sha256", "challenge_nonce",
    "incident_epoch", "sequence", "previous_receipt_sha256", "issued_at",
    "expires_at", "signature_hex",
})
SIGNED_FIELDS = RECEIPT_FIELDS - {"signature_hex"}
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX128 = re.compile(r"[0-9a-f]{128}\Z")
MAX_EVIDENCE_BYTES = 16 * 1024
MAX_CLAIMS = 8
MAX_RECEIPT_LIFETIME = 900


def _valid_sha(value):
    return type(value) is str and HEX64.fullmatch(value) is not None


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def receipt_signing_bytes(receipt):
    """Canonical signed bytes with unambiguous purpose/domain separation."""
    return DOMAIN + _encoded({key: receipt[key] for key in sorted(SIGNED_FIELDS)})


def assess_evidence_provenance(
    *, review_case, manual_assessment, raw_evidence, signed_receipts,
    pinned_source_keys, last_seen_heads, challenge_nonce, now_epoch,
):
    """Check only mathematical/structural binding. NEVER authenticate origin.

    All public keys, heads, clock and nonce come from the same host/caller.
    Even two valid signatures can be fabricated alongside an old case.
    """
    issues = set()
    out = {
        "schema": SCHEMA, "research_only": True,
        "case_structure_locally_consistent": False,
        "payload_digests_match_locally": False,
        "cryptographically_verified_receipts": 0,
        "receipt_chain_locally_consistent": False,
        "evidence_provenance_independent": False,
        "actual_provider_outcome_verified": False,
        "last_seen_heads_off_host_verified": False,
        "trusted_clock_verified": False,
        "can_resume": False, "can_resend": False,
        "can_auto_retry": False, "can_authorize_real_effect": False,
        "automatic_retries": 0, "zero_auto_resend": True,
        "hard_no_go": True, "p0_homologated": 0,
        "new_paid_services": False, "no_provider_worker_deploy_orders": True,
    }
    if type(review_case) is not dict or review_case.get("schema") != CASE_SCHEMA:
        issues.add("REVIEW_CASE_INVALID")
        review_case = {}
    claims = review_case.get("claimed_evidence")
    if type(claims) is not list or not (1 <= len(claims) <= MAX_CLAIMS):
        issues.add("CLAIM_COUNT_INVALID")
        claims = []
    if (type(manual_assessment) is not dict or
        manual_assessment.get("schema") != CASE_SCHEMA or
        manual_assessment.get("case_file_locally_valid") is not True or
        manual_assessment.get("claimed_evidence_consistent_locally") is not True or
        manual_assessment.get("hard_no_go") is not True or
        manual_assessment.get("zero_auto_resend") is not True or
        manual_assessment.get("can_resume") is not False or
        manual_assessment.get("can_resend") is not False or
        manual_assessment.get("p0_homologated") != 0):
        issues.add("A306_A307_NEGATIVE_ASSESSMENT_MISSING")
    case_digest = None
    try:
        case_digest = _sha(_encoded(review_case))
    except (TypeError, ValueError, OverflowError, KeyError):
        issues.add("REVIEW_CASE_NONCANONICAL")
    if (case_digest is None or type(manual_assessment) is not dict or
            manual_assessment.get("case_digest_sha256") != case_digest):
        issues.add("REVIEW_CASE_HASH_MISMATCH")
    out["case_structure_locally_consistent"] = not bool(
        issues & {
            "REVIEW_CASE_INVALID", "CLAIM_COUNT_INVALID",
            "A306_A307_NEGATIVE_ASSESSMENT_MISSING",
            "REVIEW_CASE_NONCANONICAL", "REVIEW_CASE_HASH_MISMATCH",
        }
    )

    if type(raw_evidence) is not list or len(raw_evidence) != len(claims):
        issues.add("EVIDENCE_PAYLOAD_COUNT_INVALID")
        raw_evidence = []
    if (type(signed_receipts) is not list or
            len(signed_receipts) != len(claims)):
        issues.add("SIGNED_RECEIPT_COUNT_INVALID")
        signed_receipts = []
    if type(pinned_source_keys) is not dict or not pinned_source_keys:
        issues.add("SOURCE_PINSET_MISSING")
        pinned_source_keys = {}
    if type(last_seen_heads) is not dict or (
        set(last_seen_heads) != set(pinned_source_keys)
    ):
        issues.add("LAST_SEEN_HEADS_INVALID")
        last_seen_heads = {}
    if not _valid_sha(challenge_nonce):
        issues.add("CHALLENGE_NONCE_INVALID")
    if type(now_epoch) is not int or now_epoch < 0:
        issues.add("UNTRUSTED_NOW_FORMAT")

    keys = list(pinned_source_keys.values())
    if (any(type(key) is not bytes or len(key) != 32 for key in keys)
            or len(set(key for key in keys if type(key) is bytes)) != len(keys)):
        issues.add("SOURCE_PINS_NOT_DISTINCT_OR_INVALID")

    verified = 0
    local_digest_matches = 0
    seen_refs = set()
    seen_receipt_keys = set()
    for i, claim in enumerate(claims):
        if type(claim) is not dict or set(claim) != CLAIM_FIELDS:
            issues.add("CLAIM_RECORD_INVALID")
            continue
        source, ref = claim["source_id"], claim["reference_id"]
        if (type(source) is not str or not source or
            type(ref) is not str or not ref):
            issues.add("CLAIM_SOURCE_REFERENCE_INVALID")
            continue
        pair = (source, ref)
        if pair in seen_refs:
            issues.add("CLAIM_REFERENCE_REUSED")
        seen_refs.add(pair)
        if source not in pinned_source_keys:
            issues.add("SOURCE_NOT_IN_PINSET")
        payload = raw_evidence[i] if i < len(raw_evidence) else None
        if (type(payload) is not bytes or not (0 < len(payload) <= MAX_EVIDENCE_BYTES)):
            issues.add("EVIDENCE_BYTES_MISSING_OR_OVERSIZED")
        elif _sha(payload) != claim["evidence_sha256"]:
            issues.add("CLAIM_DIGEST_NOT_BOUND_TO_BYTES")
        else:
            local_digest_matches += 1
        receipt = signed_receipts[i] if i < len(signed_receipts) else None
        if type(receipt) is not dict or set(receipt) != RECEIPT_FIELDS:
            issues.add("RECEIPT_FIELDS_INVALID")
            continue
        # Verify each receipt is for exactly the associated claim, case and
        # incident; malformed source names are never free to pick a new key.
        for key in (
            "source_id", "reference_id", "intent_id", "message_id",
            "observed_outcome", "evidence_sha256",
        ):
            if receipt[key] != claim[key]:
                issues.add("SIGNED_CLAIM_BINDING_MISMATCH")
        if receipt["schema"] != SCHEMA:
            issues.add("RECEIPT_SCHEMA_MISMATCH")
        if receipt["case_sha256"] != case_digest:
            issues.add("SIGNED_CASE_BINDING_MISMATCH")
        if receipt["challenge_nonce"] != challenge_nonce:
            issues.add("RECEIPT_NONCE_REPLAY")
        if (type(receipt["incident_epoch"]) is not int or
                type(review_case.get("incident_epoch")) is not int or
                receipt["incident_epoch"] != review_case["incident_epoch"]):
            issues.add("SIGNED_INCIDENT_EPOCH_MISMATCH")
        head = last_seen_heads.get(source)
        if (type(head) is not dict or set(head) != {"sequence", "receipt_sha256"}
            or type(head["sequence"]) is not int or head["sequence"] < 0
            or not _valid_sha(head["receipt_sha256"])):
            issues.add("OFF_HOST_HEAD_NOT_PROVIDED")
        elif (type(receipt["sequence"]) is not int or
              receipt["sequence"] != head["sequence"] + 1 or
              receipt["previous_receipt_sha256"] != head["receipt_sha256"]):
            issues.add("RECEIPT_REPLAY_OR_CHAIN_GAP")
        if (type(receipt["issued_at"]) is not int or
            type(receipt["expires_at"]) is not int or
            receipt["issued_at"] < 0 or
            receipt["expires_at"] <= receipt["issued_at"] or
            receipt["expires_at"] - receipt["issued_at"] > MAX_RECEIPT_LIFETIME):
            issues.add("RECEIPT_TIME_WINDOW_INVALID")
        elif type(now_epoch) is int and (
            now_epoch < receipt["issued_at"] or
            now_epoch >= receipt["expires_at"]
        ):
            issues.add("RECEIPT_STALE_OR_FUTURE")
        signed_pair = (receipt["source_id"], receipt["reference_id"])
        if signed_pair in seen_receipt_keys:
            issues.add("SIGNED_RECEIPT_REUSED")
        seen_receipt_keys.add(signed_pair)
        sig = receipt["signature_hex"]
        if type(sig) is not str or HEX128.fullmatch(sig) is None:
            issues.add("SIGNATURE_HEX_INVALID")
            continue
        public = pinned_source_keys.get(source)
        if type(public) is not bytes or len(public) != 32:
            issues.add("SOURCE_PUBLIC_KEY_INVALID")
            continue
        try:
            Ed25519PublicKey.from_public_bytes(public).verify(
                bytes.fromhex(sig), receipt_signing_bytes(receipt)
            )
        except (InvalidSignature, TypeError, KeyError, ValueError):
            issues.add("SIGNATURE_NOT_VERIFIED")
        else:
            verified += 1

    out["cryptographically_verified_receipts"] = verified
    out["payload_digests_match_locally"] = (
        bool(claims) and local_digest_matches == len(claims) and
        "EVIDENCE_PAYLOAD_COUNT_INVALID" not in issues
    )
    out["receipt_chain_locally_consistent"] = (
        bool(claims) and verified == len(claims)
        and out["payload_digests_match_locally"]
        and not issues
    )
    # Real authority, independent clock, key enrollment, off-host custody and
    # genuine provider outcome remain UNATTESTED despite cryptography.
    issues.add("INDEPENDENT_EVIDENCE_ORIGIN_NOT_AUTHENTICATED")
    issues.add("ACK_UNKNOWN_NEVER_AUTO_RESEND")
    out["issues"] = sorted(issues)
    return out


__all__ = [
    "SCHEMA", "MAX_CLAIMS", "MAX_EVIDENCE_BYTES",
    "receipt_signing_bytes", "assess_evidence_provenance",
]
