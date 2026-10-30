"""A306 LAB: read-only manual reconciliation of an unknown SQLite COMMIT.

A structured research case file is NOT an attestation, approval, provider
acknowledgement or a production recovery command. It never sends/retries,
mutates the SQLite store, or allows execution.
"""
import hashlib
import json
import re

from labs.a305_restart_revocation_no_resend_lab import (
    INTENT_ID, MESSAGE_ID, SCHEMA as A305_SCHEMA, assess_restart_attempt,
)

SCHEMA = "ATLASQUANT_AION_A306_MANUAL_INTENT_RECONCILIATION_LAB_V1"
REVIEW_FIELDS = frozenset({
    "schema", "case_id", "case_generation", "previous_case_sha256",
    "incident_epoch", "intent_id", "message_id", "reviewer_id",
    "reporter_id", "reviewer_acknowledged", "review_decision",
    "claimed_evidence",
})
CLAIM_FIELDS = frozenset({
    "source_id", "reference_id", "intent_id", "message_id",
    "observed_outcome", "evidence_sha256",
})
OUTCOMES = frozenset({"PRESENT", "ABSENT", "UNKNOWN"})
DECISIONS = frozenset({"HOLD", "ESCALATE"})
SHA64 = re.compile(r"[0-9a-f]{64}\Z")


def _sha_ok(text):
    return type(text) is str and SHA64.fullmatch(text) is not None


def _canonical(data):
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"),
        allow_nan=False, ensure_ascii=False,
    ).encode("utf-8")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _result():
    return {
        "schema": SCHEMA,
        "research_only": True,
        "requires_manual_review": True,
        "case_file_locally_valid": False,
        "claimed_evidence_consistent_locally": False,
        "a305_negative_barrier_present": False,
        "locally_observed_effect": False,
        "effect_category": "UNDETERMINED",
        "human_reviewer_identity_authenticated": False,
        "external_evidence_provenance_verified": False,
        "independent_outcome_verified": False,
        "independent_custody_authenticated": False,
        "can_resume": False,
        "can_resend": False,
        "can_auto_retry": False,
        "can_authorize_real_effect": False,
        "automatic_retries": 0,
        "zero_auto_resend": True,
        "hard_no_go": True,
        "p0_homologated": 0,
        "new_paid_services": False,
        "no_provider_worker_deploy_orders": True,
    }


def assess_manual_reconciliation(
    *, observation, before_status_inputs, after_status_inputs,
    previous_incident_epoch, recovery_incident_epoch, review_case,
    last_closed_case_generation,
):
    """Classify *claims* without proving external effect or authorizing it.

    The A305 observation is derived from real disposable SQLite in tests.
    All operator IDs, claims, case hashes, trusted heads and signed keys
    originate locally; a second ID/string is not independent authorization.
    """
    out = _result()
    issues = set()
    try:
        parent = assess_restart_attempt(
            observation=observation, before_status_inputs=before_status_inputs,
            after_status_inputs=after_status_inputs,
            previous_incident_epoch=previous_incident_epoch,
            recovery_incident_epoch=recovery_incident_epoch,
            requested_effect="READ_ONLY_REVIEW",
        )
    except (ValueError, TypeError, AttributeError, KeyError):
        parent = {}
        issues.add("A305_CHECK_FAILED")
    out["a305_negative_barrier_present"] = (
        parent.get("schema") == A305_SCHEMA and
        parent.get("hard_no_go") is True and
        parent.get("zero_auto_resend") is True and
        parent.get("can_resume") is False and
        parent.get("can_auto_retry") is False and
        parent.get("automatic_retries") == 0 and
        parent.get("p0_homologated") == 0
    )
    if not out["a305_negative_barrier_present"]:
        issues.add("A305_NEGATIVE_BARRIER_MISSING")
    if parent.get("real_sqlite_lab_observed") is not True:
        issues.add("SQLITE_OBSERVATION_NOT_RECORDED")
    if parent.get("commit_ack_unknown") is not True:
        issues.add("ACK_UNKNOWN_NOT_PROVEN")
    if parent.get("post_restart_revocation_seen") is True:
        issues.add("POST_RESTART_KEY_REVOKED")
    if parent.get("post_restart_suspension_seen") is True:
        issues.add("POST_RESTART_KEY_SUSPENDED")
    if parent.get("signed_status_advanced") is not True:
        issues.add("FRESH_POST_RESTART_STATUS_NOT_SHOWN")
    if parent.get("after_status_cryptographic") is not True:
        issues.add("POST_RESTART_STATUS_CRYPTO_MISSING")
    # The observation is *only local LAB evidence*, not a trusted record.
    # Nonetheless, do not promote an incomplete or self-inconsistent stub
    # to even the limited "locally observed" category.
    observation_integrity = (
        type(observation) is dict
        and observation.get("schema") == A305_SCHEMA
        and parent.get("real_sqlite_lab_observed") is True
        and parent.get("commit_ack_unknown") is True
        and observation.get("intent_id") == INTENT_ID
        and observation.get("message_id") == MESSAGE_ID
        and observation.get("source_pending_marker") is True
        and observation.get("source_reopen_refused") is True
        and observation.get("uncertain_error_raised") is True
        and observation.get("source_failure_reason")
            == "COMMIT_OUTCOME_UNKNOWN_ZERO_AUTO_RETRY"
        and observation.get("ack_state") == "ACK_UNKNOWN"
        and observation.get("no_retries_performed") is True
        and observation.get("no_restore_api_invoked") is True
        and observation.get("host_native_fd_attested") is False
        and observation.get("off_host_custody_attested") is False
    )
    if not observation_integrity:
        issues.add("OBSERVATION_INTEGRITY_INSUFFICIENT")
    # A305 itself remains locally sourced; no automatic authorization ever.
    if type(last_closed_case_generation) is not int or (
        last_closed_case_generation < 0
    ):
        issues.add("CASE_GENERATION_FLOOR_INVALID")
    if type(review_case) is not dict or set(review_case) != REVIEW_FIELDS:
        issues.add("REVIEW_CASE_FIELDS_INVALID")
        review_case = {}
    else:
        if review_case["schema"] != SCHEMA:
            issues.add("REVIEW_CASE_SCHEMA_INVALID")
        if type(review_case["case_id"]) is not str or not review_case["case_id"]:
            issues.add("CASE_ID_INVALID")
        if not _sha_ok(review_case["previous_case_sha256"]):
            issues.add("CASE_PREVIOUS_HASH_INVALID")
        if type(review_case["case_generation"]) is not int or (
            type(last_closed_case_generation) is int and
            review_case["case_generation"] <= last_closed_case_generation
        ):
            issues.add("REPLAYED_OR_INVALID_CASE_GENERATION")
        if type(review_case["incident_epoch"]) is not int or (
            review_case["incident_epoch"] != recovery_incident_epoch
        ):
            issues.add("INCIDENT_EPOCH_CHANGED")
        if review_case["intent_id"] != INTENT_ID or (
            review_case["message_id"] != MESSAGE_ID
        ):
            issues.add("SEMANTIC_INTENT_BINDING_MISMATCH")
        if (type(review_case["reporter_id"]) is not str or
            not review_case["reporter_id"] or
            type(review_case["reviewer_id"]) is not str or
            not review_case["reviewer_id"] or
            review_case["reviewer_id"] == review_case["reporter_id"]):
            issues.add("DISTINCT_HUMAN_ROLES_NOT_CLAIMED")
        if review_case["reviewer_acknowledged"] is not True:
            issues.add("REVIEWER_ACKNOWLEDGEMENT_MISSING")
        if (type(review_case["review_decision"]) is not str or
                review_case["review_decision"] not in DECISIONS):
            issues.add("UNSAFE_REVIEW_DECISION")

    claims = review_case.get("claimed_evidence", [])
    if type(claims) is not list or len(claims) > 20:
        issues.add("EVIDENCE_COLLECTION_INVALID")
        claims = []
    refs = set()
    sources = set()
    claims_outcomes = set()
    valid_claim_count = 0
    for item in claims:
        if type(item) is not dict or set(item) != CLAIM_FIELDS:
            issues.add("CLAIM_FIELDS_INVALID")
            continue
        if (type(item["source_id"]) is not str or not item["source_id"] or
                type(item["reference_id"]) is not str or
                not item["reference_id"]):
            issues.add("CLAIM_IDENTITY_INVALID")
            continue
        source_ref = (item["source_id"], item["reference_id"])
        if source_ref in refs:
            issues.add("DUPLICATE_EVIDENCE_REFERENCE")
        refs.add(source_ref)
        sources.add(item["source_id"])
        if item["intent_id"] != INTENT_ID or item["message_id"] != MESSAGE_ID:
            issues.add("CLAIM_SEMANTIC_INTENT_MISMATCH")
        if (type(item["observed_outcome"]) is not str or
                item["observed_outcome"] not in OUTCOMES):
            issues.add("CLAIM_OUTCOME_INVALID")
        else:
            claims_outcomes.add(item["observed_outcome"])
        if not _sha_ok(item["evidence_sha256"]):
            issues.add("CLAIM_DIGEST_INVALID")
        valid_claim_count += 1
    if "PRESENT" in claims_outcomes and "ABSENT" in claims_outcomes:
        issues.add("CONFLICTING_EFFECT_CLAIMS")
    if len(sources) == 1 and valid_claim_count > 1:
        issues.add("CLAIMS_FROM_SINGLE_SOURCE")
    if not claims:
        issues.add("EXTERNAL_OUTCOME_EVIDENCE_MISSING")

    # A forged/incomplete observation must not promote a local row into
    # "observed" without even passing the A305 negative research checks.
    # Passing these checks still does NOT attest an off-host effect.
    if (
        observation_integrity
        and type(observation) is dict
        and type(observation.get("sqlite_effect_count")) is int
        and observation.get("sqlite_effect_count") == 1
    ):
        out["locally_observed_effect"] = True
    if out["locally_observed_effect"] and "ABSENT" in claims_outcomes:
        issues.add("CLAIMED_ABSENCE_CONFLICTS_WITH_SQLITE")
    if "CONFLICTING_EFFECT_CLAIMS" in issues or (
        "CLAIMED_ABSENCE_CONFLICTS_WITH_SQLITE" in issues
    ):
        out["effect_category"] = "CONFLICTING_CLAIMS"
    elif out["locally_observed_effect"]:
        out["effect_category"] = "LOCAL_EFFECT_OBSERVED_ACK_UNKNOWN"
    else:
        # A missing local row is NOT independent evidence of nonexecution.
        out["effect_category"] = "UNDETERMINED"

    case_hash = None
    if review_case:
        try:
            raw = _canonical(review_case)
            if len(raw) > 65536:
                issues.add("REVIEW_CASE_TOO_LARGE")
            else:
                case_hash = _sha(raw)
        except (TypeError, ValueError, OverflowError):
            issues.add("REVIEW_CASE_NOT_CANONICAL")
    out["case_digest_sha256"] = case_hash
    evidence_defects = {
        "EVIDENCE_COLLECTION_INVALID", "CLAIM_FIELDS_INVALID",
        "CLAIM_IDENTITY_INVALID", "DUPLICATE_EVIDENCE_REFERENCE",
        "CLAIMS_FROM_SINGLE_SOURCE", "CLAIM_SEMANTIC_INTENT_MISMATCH",
        "CLAIM_OUTCOME_INVALID", "CLAIM_DIGEST_INVALID",
        "CONFLICTING_EFFECT_CLAIMS",
        "CLAIMED_ABSENCE_CONFLICTS_WITH_SQLITE",
    }
    out["claimed_evidence_consistent_locally"] = (
        bool(claims) and not bool(issues & evidence_defects)
    )
    # A local worksheet with missing claims may still be a review stub.
    # But any malformed, duplicated or contradictory claims must invalidate
    # its "locally valid" label: previously this gave false reassurance.
    # Neither local validity nor a self-computed digest is authority.
    out["case_file_locally_valid"] = not any(x in issues for x in {
        "A305_NEGATIVE_BARRIER_MISSING", "SQLITE_OBSERVATION_NOT_RECORDED",
        "ACK_UNKNOWN_NOT_PROVEN", "OBSERVATION_INTEGRITY_INSUFFICIENT",
        *evidence_defects,
        "REVIEW_CASE_FIELDS_INVALID", "REVIEW_CASE_SCHEMA_INVALID",
        "CASE_ID_INVALID", "CASE_PREVIOUS_HASH_INVALID",
        "REPLAYED_OR_INVALID_CASE_GENERATION", "INCIDENT_EPOCH_CHANGED",
        "SEMANTIC_INTENT_BINDING_MISMATCH",
        "DISTINCT_HUMAN_ROLES_NOT_CLAIMED",
        "REVIEWER_ACKNOWLEDGEMENT_MISSING", "UNSAFE_REVIEW_DECISION",
        "REVIEW_CASE_TOO_LARGE", "REVIEW_CASE_NOT_CANONICAL",
        "CASE_GENERATION_FLOOR_INVALID",
    }) and bool(review_case)
    # All claimed receipts and signatures are still from the same host.
    issues.add("INDEPENDENT_EVIDENCE_AND_REVIEWER_AUTHORITY_MISSING")
    issues.add("ACK_UNKNOWN_ZERO_AUTO_RESEND")
    out["issues"] = sorted(issues)
    return out


__all__ = [
    "SCHEMA", "INTENT_ID", "MESSAGE_ID", "REVIEW_FIELDS",
    "CLAIM_FIELDS", "assess_manual_reconciliation",
]
