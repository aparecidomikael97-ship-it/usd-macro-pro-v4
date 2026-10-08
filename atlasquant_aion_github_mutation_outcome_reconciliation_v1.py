"""AION GitHub Mutation Outcome Reconciliation V1.

Pure, non-executing reconciliation contracts for an immutable GitHub mutation
outcome receipt whose primary outcome is OUTCOME_UNKNOWN.

This layer never queries GitHub, never repeats a mutation and never rewrites the
original receipt.

Reconciliation is a separate HUMAN_OWNER-authorized, evidence-bound ceremony
that may produce exactly one of:

- RECONCILED_CONFIRMED_SUCCESS
- RECONCILED_CONFIRMED_TERMINAL_FAILURE
- STILL_OUTCOME_UNKNOWN

Even a reconciled terminal failure or confirmed no-effect state does not
authorize retry. Any new repository mutation attempt requires a completely new
authorization, effect key and execution attempt.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from atlasquant_aion_signed_github_mutation_adapter_outcome_v1 import (
    OUTCOME_SCHEMA,
    EXPECTED_POSTCONDITIONS,
    verify_mutation_outcome_receipt,
)


SCHEMA = "ATLASQUANT_AION_GITHUB_MUTATION_OUTCOME_RECONCILIATION_V1"
AUTH_SCHEMA = "ATLASQUANT_AION_GITHUB_MUTATION_RECONCILIATION_AUTHORIZATION_V1"
EVIDENCE_SCHEMA = "ATLASQUANT_AION_GITHUB_MUTATION_RECONCILIATION_EVIDENCE_V1"
RECONCILIATION_SCHEMA = "ATLASQUANT_AION_GITHUB_MUTATION_RECONCILIATION_RECORD_V1"
VERIFY_SCHEMA = "ATLASQUANT_AION_GITHUB_MUTATION_RECONCILIATION_VERIFY_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_GITHUB_MUTATION_RECONCILIATION_POLICY_V1"

RECONCILIATION_PURPOSE = "HUMAN_OWNER_EXPLICIT_GITHUB_MUTATION_OUTCOME_RECONCILIATION"
RECONCILIATION_MECHANISM = "ED25519_EXTERNAL_OWNER_REPOSITORY_MUTATION_KEY"

RECONCILIATION_DECISIONS = (
    "AUTHORIZE_GITHUB_MUTATION_RECONCILIATION",
    "DENY_GITHUB_MUTATION_RECONCILIATION",
)
RECONCILIATION_STATES = (
    "RECONCILED_CONFIRMED_SUCCESS",
    "RECONCILED_CONFIRMED_TERMINAL_FAILURE",
    "STILL_OUTCOME_UNKNOWN",
)
AUTHORITATIVE_EVIDENCE_CLASSES = (
    "GITHUB_PR_STATE_READBACK",
    "GITHUB_BRANCH_BASE_READBACK",
    "GITHUB_MAIN_COMMIT_GRAPH_READBACK",
    "GITHUB_MERGE_COMMIT_READBACK",
    "GITHUB_REPOSITORY_AUDIT_EVENT",
    "IMMUTABLE_REPOSITORY_OBSERVATION",
)
UNKNOWN_PRESERVING_CONDITIONS = (
    "EVIDENCE_MISSING",
    "EVIDENCE_INCOMPLETE",
    "EVIDENCE_STALE",
    "EVIDENCE_UNAUTHENTICATED",
    "EVIDENCE_SOURCE_NOT_ATTESTED",
    "REPOSITORY_IDENTITY_MISMATCH",
    "PR_NUMBER_MISMATCH",
    "MUTATION_MISMATCH",
    "EXECUTION_ATTEMPT_MISMATCH",
    "REQUEST_CORRELATION_MISMATCH",
    "IDEMPOTENCY_MISMATCH",
    "EFFECT_KEY_MISMATCH",
    "SEQUENCE_REGRESSION",
    "SUCCESS_AND_FAILURE_SIGNAL_CONFLICT",
    "POSTCONDITION_CONFLICT",
)
MAX_RECONCILIATION_AUTH_WINDOW_SECONDS = 120
MAX_EVIDENCE_AGE_SECONDS = 120

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,239}$")


def _clean(value: Any, limit: int = 1000) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256(value: Any) -> str:
    token = _clean(value, 90)
    return token if _DIGEST_RE.fullmatch(token) else ""


def _identity(value: Any, limit: int = 240) -> str:
    if type(value) is not str:
        return ""
    text = _clean(value, limit)
    if text != value or not _ID_RE.fullmatch(text):
        return ""
    return text


def _aware(value: Any, label: str) -> datetime:
    try:
        if isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception as exc:
        raise ValueError(f"{label} invalid") from exc
    if dt.tzinfo is None:
        raise ValueError(f"{label} timezone required")
    return dt.astimezone(timezone.utc)


def _evidence_classes(value: Sequence[Any] | None) -> list[str]:
    allowed = set(AUTHORITATIVE_EVIDENCE_CLASSES)
    out: list[str] = []
    for raw in list(value or []):
        token = _clean(raw, 120).upper()
        if token in allowed and token not in out:
            out.append(token)
    return sorted(out)


def build_reconciliation_authorization(
    outcome_receipt: Mapping[str, Any] | None,
    *,
    authorization_id: Any,
    decision: Any,
    owner_subject: Any,
    owner_binding_digest: Any,
    owner_key_fingerprint: Any,
    nonce_digest: Any,
    signed_authorization_digest: Any,
    verified_owner_signature: bool,
    verified_active_trust_root: bool,
    persistent_nonce_replay_guard_verified: bool,
    nonce_single_use_claimed: bool,
    issued_at: Any,
    expires_at: Any,
    now: Any,
) -> dict[str, Any]:
    """Build separate HUMAN_OWNER authorization for UNKNOWN reconciliation."""
    receipt = dict(outcome_receipt or {})
    blockers: list[str] = []

    receipt_check = verify_mutation_outcome_receipt(receipt)
    if receipt_check.get("valid") is not True:
        blockers.append("VALID_MUTATION_OUTCOME_RECEIPT_REQUIRED")
    if receipt.get("schema") != OUTCOME_SCHEMA:
        blockers.append("OUTCOME_RECEIPT_SCHEMA_MISMATCH")
    if receipt.get("outcome") != "OUTCOME_UNKNOWN":
        blockers.append("RECONCILIATION_ONLY_ALLOWED_FOR_OUTCOME_UNKNOWN")
    if receipt.get("receipt_immutable") is not True:
        blockers.append("IMMUTABLE_ORIGINAL_RECEIPT_REQUIRED")
    if receipt.get("original_receipt_mutable") is not False:
        blockers.append("ORIGINAL_RECEIPT_MUTABILITY_BOUNDARY_INVALID")
    if receipt.get("automatic_retry_allowed") is not False:
        blockers.append("ORIGINAL_RECEIPT_RETRY_BOUNDARY_INVALID")

    auth_id = _identity(authorization_id, 180)
    decision_name = _clean(decision, 100).upper()
    subject = _identity(owner_subject, 240)
    owner_digest = _sha256(owner_binding_digest)
    key_digest = _sha256(owner_key_fingerprint)
    nonce = _sha256(nonce_digest)
    supplied_signed_digest = _sha256(signed_authorization_digest)

    if not auth_id:
        blockers.append("RECONCILIATION_AUTHORIZATION_ID_REQUIRED")
    if decision_name not in RECONCILIATION_DECISIONS:
        blockers.append("RECONCILIATION_DECISION_INVALID")
    if not subject:
        blockers.append("OWNER_SUBJECT_REQUIRED")
    if not owner_digest:
        blockers.append("OWNER_BINDING_DIGEST_REQUIRED")
    if not key_digest:
        blockers.append("OWNER_KEY_FINGERPRINT_REQUIRED")
    if not nonce:
        blockers.append("RECONCILIATION_NONCE_DIGEST_REQUIRED")
    if not supplied_signed_digest:
        blockers.append("SIGNED_AUTHORIZATION_DIGEST_REQUIRED")
    if verified_owner_signature is not True:
        blockers.append("OWNER_RECONCILIATION_SIGNATURE_NOT_VERIFIED")
    if verified_active_trust_root is not True:
        blockers.append("ACTIVE_TRUST_ROOT_NOT_VERIFIED")
    if persistent_nonce_replay_guard_verified is not True:
        blockers.append("PERSISTENT_NONCE_REPLAY_GUARD_REQUIRED")
    if nonce_single_use_claimed is not True:
        blockers.append("NONCE_SINGLE_USE_CLAIM_REQUIRED")

    try:
        issued = _aware(issued_at, "issued_at")
        expires = _aware(expires_at, "expires_at")
        current = _aware(now, "now")
        if expires <= issued:
            blockers.append("RECONCILIATION_AUTH_EXPIRY_INVALID")
        if (
            expires - issued
        ).total_seconds() > MAX_RECONCILIATION_AUTH_WINDOW_SECONDS:
            blockers.append("RECONCILIATION_AUTH_WINDOW_TOO_LONG")
        if current < issued:
            blockers.append("RECONCILIATION_AUTH_FROM_FUTURE")
        if current > expires:
            blockers.append("RECONCILIATION_AUTH_EXPIRED")
    except ValueError:
        issued = None
        expires = None
        current = None
        blockers.append("RECONCILIATION_AUTH_TIME_INVALID")

    signed_material = {
        "authorization_id": auth_id,
        "purpose": RECONCILIATION_PURPOSE,
        "mechanism": RECONCILIATION_MECHANISM,
        "decision": decision_name,
        "owner_subject": subject,
        "owner_binding_digest": owner_digest,
        "owner_key_fingerprint": key_digest,
        "nonce_digest": nonce,
        "original_outcome_receipt_digest": _sha256(
            receipt.get("outcome_receipt_digest")
        ),
        "execution_attempt_id": receipt.get("execution_attempt_id"),
        "pr_number": receipt.get("pr_number"),
        "requested_mutation": receipt.get("requested_mutation"),
        "request_correlation_digest": _sha256(
            receipt.get("request_correlation_digest")
        ),
        "idempotency_key_digest": _sha256(
            receipt.get("idempotency_key_digest")
        ),
        "effect_key_digest": _sha256(receipt.get("effect_key_digest")),
        "issued_at": issued.isoformat() if issued else "",
        "expires_at": expires.isoformat() if expires else "",
    }
    expected_signed_digest = _digest(signed_material)
    if supplied_signed_digest and supplied_signed_digest != expected_signed_digest:
        blockers.append("SIGNED_AUTHORIZATION_DIGEST_MISMATCH")

    blockers = list(dict.fromkeys(blockers))
    approved = (
        not blockers
        and decision_name == "AUTHORIZE_GITHUB_MUTATION_RECONCILIATION"
    )
    denied = (
        not blockers
        and decision_name == "DENY_GITHUB_MUTATION_RECONCILIATION"
    )
    material = {
        **signed_material,
        "signed_authorization_digest": supplied_signed_digest,
        "verified_owner_signature": verified_owner_signature is True,
        "verified_active_trust_root": verified_active_trust_root is True,
        "persistent_nonce_replay_guard_verified": (
            persistent_nonce_replay_guard_verified is True
        ),
        "nonce_single_use_claimed": nonce_single_use_claimed is True,
        "verified_at": current.isoformat() if current else "",
    }

    return {
        "schema": AUTH_SCHEMA,
        "state": (
            "RECONCILIATION_AUTHORIZED"
            if approved
            else "RECONCILIATION_DENIED"
            if denied
            else "BLOCKED"
        ),
        "blockers": blockers,
        **material,
        "reconciliation_authorization_digest": (
            _digest(material) if not blockers else ""
        ),
        "reconciliation_authorized": approved,
        "reconciliation_denied": denied,
        "authorization_consumed": False,
        "authorization_reuse_allowed": False,
        "provider_query_authorized_by_this_module": False,
        "github_query_performed_by_this_module": False,
        "network_called_by_this_module": False,
        "retry_authorized": False,
        "new_attempt_authorized": False,
        "repository_mutation_performed": False,
        "executes_action": False,
    }


def build_authoritative_reconciliation_evidence(
    outcome_receipt: Mapping[str, Any] | None,
    reconciliation_authorization: Mapping[str, Any] | None,
    *,
    evidence_id: Any,
    evidence_classes: Sequence[Any] | None,
    evidence_source_digest: Any,
    evidence_set_digest: Any,
    repository_observation_digest: Any,
    pr_state_evidence_digest: Any,
    main_state_evidence_digest: Any,
    audit_evidence_digest: Any = "",
    repository_identity_match: bool,
    pr_number_match: bool,
    requested_mutation_match: bool,
    execution_attempt_id_match: bool,
    request_correlation_match: bool,
    idempotency_key_match: bool,
    effect_key_match: bool,
    evidence_source_attested: bool,
    evidence_schema_valid: bool,
    evidence_authenticity_verified: bool,
    evidence_freshness_verified: bool,
    evidence_sequence_monotonic: bool,
    independent_repository_readback_verified: bool,
    success_postcondition_verified: bool,
    authoritative_no_effect_verified: bool,
    authoritative_terminal_rejection_verified: bool,
    conflicting_evidence_present: bool,
    observed_at: Any,
    now: Any,
) -> dict[str, Any]:
    """Bind externally gathered repository evidence without querying GitHub."""
    receipt = dict(outcome_receipt or {})
    auth = dict(reconciliation_authorization or {})
    blockers: list[str] = []

    if verify_mutation_outcome_receipt(receipt).get("valid") is not True:
        blockers.append("VALID_MUTATION_OUTCOME_RECEIPT_REQUIRED")
    if receipt.get("outcome") != "OUTCOME_UNKNOWN":
        blockers.append("ORIGINAL_OUTCOME_MUST_BE_UNKNOWN")
    if auth.get("schema") != AUTH_SCHEMA:
        blockers.append("RECONCILIATION_AUTH_SCHEMA_MISMATCH")
    if auth.get("state") != "RECONCILIATION_AUTHORIZED":
        blockers.append("RECONCILIATION_AUTHORIZATION_REQUIRED")
    if auth.get("reconciliation_authorized") is not True:
        blockers.append("RECONCILIATION_AUTHORIZATION_FLAG_REQUIRED")
    if auth.get("authorization_consumed") is not False:
        blockers.append("RECONCILIATION_AUTH_ALREADY_CONSUMED")
    if _sha256(auth.get("original_outcome_receipt_digest")) != _sha256(
        receipt.get("outcome_receipt_digest")
    ):
        blockers.append("AUTHORIZATION_RECEIPT_BINDING_MISMATCH")

    eid = _identity(evidence_id, 180)
    classes = _evidence_classes(evidence_classes)
    source_digest = _sha256(evidence_source_digest)
    set_digest = _sha256(evidence_set_digest)
    repository_digest = _sha256(repository_observation_digest)
    pr_digest = _sha256(pr_state_evidence_digest)
    main_digest = _sha256(main_state_evidence_digest)
    audit_digest = _sha256(audit_evidence_digest) if audit_evidence_digest else ""

    if not eid:
        blockers.append("EVIDENCE_ID_REQUIRED")
    if not classes:
        blockers.append("AUTHORITATIVE_EVIDENCE_CLASS_REQUIRED")
    if not source_digest:
        blockers.append("EVIDENCE_SOURCE_DIGEST_REQUIRED")
    if not set_digest:
        blockers.append("EVIDENCE_SET_DIGEST_REQUIRED")
    if not repository_digest:
        blockers.append("REPOSITORY_OBSERVATION_DIGEST_REQUIRED")
    if not pr_digest:
        blockers.append("PR_STATE_EVIDENCE_DIGEST_REQUIRED")
    if not main_digest:
        blockers.append("MAIN_STATE_EVIDENCE_DIGEST_REQUIRED")

    for label, flag in (
        ("REPOSITORY_IDENTITY_MATCH_REQUIRED", repository_identity_match),
        ("PR_NUMBER_MATCH_REQUIRED", pr_number_match),
        ("REQUESTED_MUTATION_MATCH_REQUIRED", requested_mutation_match),
        ("EXECUTION_ATTEMPT_ID_MATCH_REQUIRED", execution_attempt_id_match),
        ("REQUEST_CORRELATION_MATCH_REQUIRED", request_correlation_match),
        ("IDEMPOTENCY_KEY_MATCH_REQUIRED", idempotency_key_match),
        ("EFFECT_KEY_MATCH_REQUIRED", effect_key_match),
        ("EVIDENCE_SOURCE_ATTESTATION_REQUIRED", evidence_source_attested),
        ("EVIDENCE_SCHEMA_VALIDATION_REQUIRED", evidence_schema_valid),
        ("EVIDENCE_AUTHENTICITY_REQUIRED", evidence_authenticity_verified),
        ("EVIDENCE_FRESHNESS_REQUIRED", evidence_freshness_verified),
        ("EVIDENCE_SEQUENCE_MONOTONIC_REQUIRED", evidence_sequence_monotonic),
        (
            "INDEPENDENT_REPOSITORY_READBACK_REQUIRED",
            independent_repository_readback_verified,
        ),
    ):
        if flag is not True:
            blockers.append(label)

    try:
        observed = _aware(observed_at, "observed_at")
        current = _aware(now, "now")
        age = (current - observed).total_seconds()
        if age < 0:
            blockers.append("RECONCILIATION_EVIDENCE_FROM_FUTURE")
        if age > MAX_EVIDENCE_AGE_SECONDS:
            blockers.append("RECONCILIATION_EVIDENCE_STALE")
    except ValueError:
        observed = None
        current = None
        blockers.append("RECONCILIATION_EVIDENCE_TIME_INVALID")

    success_signal = success_postcondition_verified is True
    failure_signal = (
        authoritative_no_effect_verified is True
        or authoritative_terminal_rejection_verified is True
    )
    inferred_conflict = success_signal and failure_signal
    conflict = conflicting_evidence_present is True or inferred_conflict

    blockers = list(dict.fromkeys(blockers))
    material = {
        "evidence_id": eid,
        "original_outcome_receipt_digest": _sha256(
            receipt.get("outcome_receipt_digest")
        ),
        "reconciliation_authorization_digest": _sha256(
            auth.get("reconciliation_authorization_digest")
        ),
        "execution_attempt_id": receipt.get("execution_attempt_id"),
        "pr_number": receipt.get("pr_number"),
        "requested_mutation": receipt.get("requested_mutation"),
        "expected_postcondition": receipt.get("expected_postcondition"),
        "request_correlation_digest": _sha256(
            receipt.get("request_correlation_digest")
        ),
        "idempotency_key_digest": _sha256(
            receipt.get("idempotency_key_digest")
        ),
        "effect_key_digest": _sha256(receipt.get("effect_key_digest")),
        "evidence_classes": classes,
        "evidence_source_digest": source_digest,
        "evidence_set_digest": set_digest,
        "repository_observation_digest": repository_digest,
        "pr_state_evidence_digest": pr_digest,
        "main_state_evidence_digest": main_digest,
        "audit_evidence_digest": audit_digest,
        "repository_identity_match": repository_identity_match is True,
        "pr_number_match": pr_number_match is True,
        "requested_mutation_match": requested_mutation_match is True,
        "execution_attempt_id_match": execution_attempt_id_match is True,
        "request_correlation_match": request_correlation_match is True,
        "idempotency_key_match": idempotency_key_match is True,
        "effect_key_match": effect_key_match is True,
        "evidence_source_attested": evidence_source_attested is True,
        "evidence_schema_valid": evidence_schema_valid is True,
        "evidence_authenticity_verified": evidence_authenticity_verified is True,
        "evidence_freshness_verified": evidence_freshness_verified is True,
        "evidence_sequence_monotonic": evidence_sequence_monotonic is True,
        "independent_repository_readback_verified": (
            independent_repository_readback_verified is True
        ),
        "success_postcondition_verified": success_signal,
        "authoritative_no_effect_verified": authoritative_no_effect_verified is True,
        "authoritative_terminal_rejection_verified": (
            authoritative_terminal_rejection_verified is True
        ),
        "conflicting_evidence_present": conflict,
        "observed_at": observed.isoformat() if observed else "",
        "verified_at": current.isoformat() if current else "",
    }

    return {
        "schema": EVIDENCE_SCHEMA,
        "state": (
            "AUTHORITATIVE_RECONCILIATION_EVIDENCE_ATTESTED"
            if not blockers
            else "BLOCKED"
        ),
        "blockers": blockers,
        **material,
        "reconciliation_evidence_digest": _digest(material) if not blockers else "",
        "evidence_queried_by_this_module": False,
        "github_queried_by_this_module": False,
        "network_called_by_this_module": False,
        "original_receipt_mutated": False,
        "retry_authorized": False,
        "new_attempt_authorized": False,
        "repository_mutation_performed": False,
        "executes_action": False,
    }


def build_outcome_reconciliation_record(
    outcome_receipt: Mapping[str, Any] | None,
    reconciliation_authorization: Mapping[str, Any] | None,
    reconciliation_evidence: Mapping[str, Any] | None,
    *,
    reconciliation_id: Any,
    evidence_complete: bool,
    observed_at: Any,
) -> dict[str, Any]:
    """Create append-only resolution without rewriting the primary receipt."""
    receipt = dict(outcome_receipt or {})
    auth = dict(reconciliation_authorization or {})
    evidence = dict(reconciliation_evidence or {})
    blockers: list[str] = []

    if verify_mutation_outcome_receipt(receipt).get("valid") is not True:
        blockers.append("VALID_MUTATION_OUTCOME_RECEIPT_REQUIRED")
    if receipt.get("outcome") != "OUTCOME_UNKNOWN":
        blockers.append("ORIGINAL_OUTCOME_MUST_BE_UNKNOWN")
    if receipt.get("receipt_immutable") is not True:
        blockers.append("ORIGINAL_RECEIPT_IMMUTABILITY_REQUIRED")

    if auth.get("schema") != AUTH_SCHEMA:
        blockers.append("RECONCILIATION_AUTH_SCHEMA_MISMATCH")
    if auth.get("state") != "RECONCILIATION_AUTHORIZED":
        blockers.append("RECONCILIATION_AUTHORIZATION_REQUIRED")
    if auth.get("reconciliation_authorized") is not True:
        blockers.append("RECONCILIATION_AUTHORIZATION_FLAG_REQUIRED")
    if auth.get("authorization_consumed") is not False:
        blockers.append("RECONCILIATION_AUTH_ALREADY_CONSUMED")

    if evidence.get("schema") != EVIDENCE_SCHEMA:
        blockers.append("RECONCILIATION_EVIDENCE_SCHEMA_MISMATCH")
    if evidence.get("state") != "AUTHORITATIVE_RECONCILIATION_EVIDENCE_ATTESTED":
        blockers.append("AUTHORITATIVE_RECONCILIATION_EVIDENCE_REQUIRED")

    receipt_digest = _sha256(receipt.get("outcome_receipt_digest"))
    if _sha256(auth.get("original_outcome_receipt_digest")) != receipt_digest:
        blockers.append("AUTHORIZATION_RECEIPT_BINDING_MISMATCH")
    if _sha256(evidence.get("original_outcome_receipt_digest")) != receipt_digest:
        blockers.append("EVIDENCE_RECEIPT_BINDING_MISMATCH")
    if _sha256(evidence.get("reconciliation_authorization_digest")) != _sha256(
        auth.get("reconciliation_authorization_digest")
    ):
        blockers.append("EVIDENCE_AUTHORIZATION_BINDING_MISMATCH")

    rid = _identity(reconciliation_id, 180)
    if not rid:
        blockers.append("RECONCILIATION_ID_REQUIRED")

    try:
        observed = _aware(observed_at, "observed_at")
    except ValueError:
        observed = None
        blockers.append("RECONCILIATION_OBSERVED_AT_INVALID")

    success = evidence.get("success_postcondition_verified") is True
    failure = (
        evidence.get("authoritative_no_effect_verified") is True
        or evidence.get("authoritative_terminal_rejection_verified") is True
    )
    conflict = evidence.get("conflicting_evidence_present") is True or (
        success and failure
    )

    if blockers:
        result_state = "STILL_OUTCOME_UNKNOWN"
    elif evidence_complete is not True:
        result_state = "STILL_OUTCOME_UNKNOWN"
    elif conflict:
        result_state = "STILL_OUTCOME_UNKNOWN"
    elif success and not failure:
        result_state = "RECONCILED_CONFIRMED_SUCCESS"
    elif failure and not success:
        result_state = "RECONCILED_CONFIRMED_TERMINAL_FAILURE"
    else:
        result_state = "STILL_OUTCOME_UNKNOWN"

    unknown_conditions: list[str] = []
    if evidence_complete is not True:
        unknown_conditions.append("EVIDENCE_INCOMPLETE")
    if conflict:
        unknown_conditions.append("SUCCESS_AND_FAILURE_SIGNAL_CONFLICT")
    if not success and not failure:
        unknown_conditions.append("EVIDENCE_INCOMPLETE")

    material = {
        "reconciliation_id": rid,
        "original_outcome_receipt_digest": receipt_digest,
        "reconciliation_authorization_digest": _sha256(
            auth.get("reconciliation_authorization_digest")
        ),
        "reconciliation_evidence_digest": _sha256(
            evidence.get("reconciliation_evidence_digest")
        ),
        "execution_attempt_id": receipt.get("execution_attempt_id"),
        "pr_number": receipt.get("pr_number"),
        "requested_mutation": receipt.get("requested_mutation"),
        "expected_postcondition": receipt.get("expected_postcondition"),
        "idempotency_key_digest": _sha256(
            receipt.get("idempotency_key_digest")
        ),
        "effect_key_digest": _sha256(receipt.get("effect_key_digest")),
        "reconciled_outcome": result_state,
        "evidence_complete": evidence_complete is True,
        "success_postcondition_verified": success,
        "authoritative_no_effect_verified": (
            evidence.get("authoritative_no_effect_verified") is True
        ),
        "authoritative_terminal_rejection_verified": (
            evidence.get("authoritative_terminal_rejection_verified") is True
        ),
        "conflicting_evidence_present": conflict,
        "unknown_preserving_conditions": sorted(set(unknown_conditions)),
        "observed_at": observed.isoformat() if observed else "",
    }

    record_valid = not blockers
    confirmed_no_effect = (
        record_valid
        and result_state == "RECONCILED_CONFIRMED_TERMINAL_FAILURE"
        and evidence.get("authoritative_no_effect_verified") is True
    )

    return {
        "schema": RECONCILIATION_SCHEMA,
        "state": "RECONCILIATION_RECORD_READY" if record_valid else "BLOCKED",
        "blockers": blockers,
        **material,
        "reconciliation_digest": _digest(material) if record_valid else "",
        "original_receipt_immutable": True,
        "original_receipt_mutated": False,
        "reconciliation_record_append_only": True,
        "reconciliation_is_retry": False,
        "repository_mutation_replayed": False,
        "automatic_retry_allowed": False,
        "retry_scheduled": False,
        "retry_performed": False,
        "new_attempt_authorized": False,
        "confirmed_no_effect": confirmed_no_effect,
        "new_attempt_may_be_considered_with_fresh_authorization": (
            confirmed_no_effect
        ),
        "fresh_owner_authorization_required_for_new_attempt": True,
        "new_effect_key_required_for_new_attempt": True,
        "new_execution_attempt_id_required": True,
        "authorization_consumed_by_this_module": False,
        "evidence_queried_by_this_module": False,
        "github_queried_by_this_module": False,
        "network_called_by_this_module": False,
        "repository_mutation_performed": False,
        "executes_action": False,
    }


def verify_outcome_reconciliation_record(
    record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw = dict(record or {})
    blockers: list[str] = []

    if raw.get("schema") != RECONCILIATION_SCHEMA:
        blockers.append("RECONCILIATION_SCHEMA_MISMATCH")
    if raw.get("state") != "RECONCILIATION_RECORD_READY":
        blockers.append("READY_RECONCILIATION_RECORD_REQUIRED")
    if raw.get("original_receipt_immutable") is not True:
        blockers.append("ORIGINAL_RECEIPT_IMMUTABILITY_REQUIRED")
    if raw.get("original_receipt_mutated") is not False:
        blockers.append("ORIGINAL_RECEIPT_MUST_NOT_BE_MUTATED")
    if raw.get("reconciliation_record_append_only") is not True:
        blockers.append("APPEND_ONLY_RECONCILIATION_REQUIRED")
    if raw.get("reconciliation_is_retry") is not False:
        blockers.append("RECONCILIATION_MUST_NOT_BE_RETRY")
    if raw.get("repository_mutation_replayed") is not False:
        blockers.append("REPOSITORY_MUTATION_MUST_NOT_BE_REPLAYED")
    if raw.get("automatic_retry_allowed") is not False:
        blockers.append("AUTOMATIC_RETRY_MUST_REMAIN_FALSE")
    if raw.get("new_attempt_authorized") is not False:
        blockers.append("NEW_ATTEMPT_MUST_REMAIN_UNAUTHORIZED")

    material = {
        key: raw.get(key)
        for key in (
            "reconciliation_id",
            "original_outcome_receipt_digest",
            "reconciliation_authorization_digest",
            "reconciliation_evidence_digest",
            "execution_attempt_id",
            "pr_number",
            "requested_mutation",
            "expected_postcondition",
            "idempotency_key_digest",
            "effect_key_digest",
            "reconciled_outcome",
            "evidence_complete",
            "success_postcondition_verified",
            "authoritative_no_effect_verified",
            "authoritative_terminal_rejection_verified",
            "conflicting_evidence_present",
            "unknown_preserving_conditions",
            "observed_at",
        )
    }
    supplied = _sha256(raw.get("reconciliation_digest"))
    expected = _digest(material)
    if not supplied or supplied != expected:
        blockers.append("RECONCILIATION_DIGEST_MISMATCH")

    outcome = _clean(raw.get("reconciled_outcome"), 120).upper()
    if outcome not in RECONCILIATION_STATES:
        blockers.append("RECONCILED_OUTCOME_INVALID")
    if outcome == "RECONCILED_CONFIRMED_SUCCESS":
        if raw.get("success_postcondition_verified") is not True:
            blockers.append("RECONCILED_SUCCESS_POSTCONDITION_REQUIRED")
        if raw.get("evidence_complete") is not True:
            blockers.append("RECONCILED_SUCCESS_COMPLETE_EVIDENCE_REQUIRED")
    elif outcome == "RECONCILED_CONFIRMED_TERMINAL_FAILURE":
        if not (
            raw.get("authoritative_no_effect_verified") is True
            or raw.get("authoritative_terminal_rejection_verified") is True
        ):
            blockers.append("RECONCILED_FAILURE_AUTHORITATIVE_EVIDENCE_REQUIRED")
        if raw.get("evidence_complete") is not True:
            blockers.append("RECONCILED_FAILURE_COMPLETE_EVIDENCE_REQUIRED")
    elif outcome == "STILL_OUTCOME_UNKNOWN":
        if raw.get("automatic_retry_allowed") is not False:
            blockers.append("STILL_UNKNOWN_RETRY_MUST_REMAIN_FALSE")

    for key in (
        "authorization_consumed_by_this_module",
        "evidence_queried_by_this_module",
        "github_queried_by_this_module",
        "network_called_by_this_module",
        "repository_mutation_performed",
        "executes_action",
    ):
        if raw.get(key) is not False:
            blockers.append("RECONCILIATION_UNSAFE_FIELD:" + key)

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": VERIFY_SCHEMA,
        "state": "VALID_RECONCILIATION_RECORD" if not blockers else "INVALID",
        "valid": not blockers,
        "blockers": blockers,
        "reconciled_outcome": outcome,
        "reconciliation_digest": supplied,
        "automatic_retry_allowed": False,
        "new_attempt_authorized": False,
        "repository_mutation_performed": False,
        "executes_action": False,
    }


def github_mutation_reconciliation_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "reconciliation_purpose": RECONCILIATION_PURPOSE,
        "reconciliation_mechanism": RECONCILIATION_MECHANISM,
        "reconciliation_states": list(RECONCILIATION_STATES),
        "authoritative_evidence_classes": list(AUTHORITATIVE_EVIDENCE_CLASSES),
        "unknown_preserving_conditions": list(UNKNOWN_PRESERVING_CONDITIONS),
        "reconciliation_only_for_outcome_unknown": True,
        "original_receipt_immutable": True,
        "reconciliation_record_append_only": True,
        "separate_owner_authorization_required": True,
        "owner_signature_required": True,
        "active_trust_root_required": True,
        "persistent_nonce_replay_guard_required": True,
        "single_use_reconciliation_nonce_required": True,
        "authorization_reuse_allowed": False,
        "authoritative_repository_evidence_required": True,
        "independent_repository_readback_required": True,
        "repository_identity_match_required": True,
        "pr_number_match_required": True,
        "requested_mutation_match_required": True,
        "execution_attempt_match_required": True,
        "request_correlation_match_required": True,
        "idempotency_match_required": True,
        "effect_key_match_required": True,
        "evidence_authenticity_required": True,
        "evidence_freshness_required": True,
        "evidence_sequence_monotonic_required": True,
        "conflicting_evidence_preserves_unknown": True,
        "incomplete_evidence_preserves_unknown": True,
        "stale_evidence_preserves_unknown": True,
        "unauthenticated_evidence_preserves_unknown": True,
        "reconciliation_is_retry": False,
        "repository_mutation_replayed": False,
        "automatic_retry_allowed": False,
        "new_attempt_authorized": False,
        "fresh_owner_authorization_required_for_new_attempt": True,
        "new_effect_key_required_for_new_attempt": True,
        "new_execution_attempt_id_required": True,
        "github_query_performed_by_this_module": False,
        "network_called_by_this_module": False,
        "repository_mutation_performed": False,
        "merge_executed": False,
        "retarget_executed": False,
        "draft_transition_executed": False,
        "branch_deleted": False,
        "deploy_executed": False,
        "worker_activation_allowed": False,
        "provider_activation_allowed": False,
        "production_persistence_activation_allowed": False,
        "external_action_executed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "AUTH_SCHEMA",
    "EVIDENCE_SCHEMA",
    "RECONCILIATION_SCHEMA",
    "VERIFY_SCHEMA",
    "POLICY_SCHEMA",
    "RECONCILIATION_PURPOSE",
    "RECONCILIATION_MECHANISM",
    "RECONCILIATION_DECISIONS",
    "RECONCILIATION_STATES",
    "AUTHORITATIVE_EVIDENCE_CLASSES",
    "UNKNOWN_PRESERVING_CONDITIONS",
    "MAX_RECONCILIATION_AUTH_WINDOW_SECONDS",
    "MAX_EVIDENCE_AGE_SECONDS",
    "build_reconciliation_authorization",
    "build_authoritative_reconciliation_evidence",
    "build_outcome_reconciliation_record",
    "verify_outcome_reconciliation_record",
    "github_mutation_reconciliation_policy",
]
