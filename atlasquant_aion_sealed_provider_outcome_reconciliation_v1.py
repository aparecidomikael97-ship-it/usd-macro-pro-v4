"""AION Sealed Provider Call + Outcome Receipt + Reconciliation V1.

Pure, non-executing contracts for the final outbound safety boundary.

This module begins only after a durable-dispatch candidate already exists.
It defines:
1. attestation that DISPATCH_RECORDED was durably committed and the fresh
   execution authorization was consumed atomically;
2. an exact sealed single-call boundary;
3. immutable outcome classification;
4. separate evidence-bound reconciliation for OUTCOME_UNKNOWN.

It never writes the durable store, opens network transport, resolves secrets,
calls a provider, sends a message, exports/signs a contract, retries an effect,
or mutates an original receipt.

Outcome truth is intentionally narrow:
- CONFIRMED_SUCCESS
- CONFIRMED_TERMINAL_FAILURE
- OUTCOME_UNKNOWN

Silence, timeout, reset, crash, malformed acknowledgements or incomplete
evidence never become inferred success or inferred terminal failure.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from atlasquant_aion_outbound_execution_authorization_durable_dispatch_v1 import (
    DISPATCH_SCHEMA as DISPATCH_CANDIDATE_SCHEMA,
    verify_durable_dispatch_record_candidate,
)


SCHEMA = "ATLASQUANT_AION_SEALED_PROVIDER_OUTCOME_RECONCILIATION_V1"
DISPATCH_WRITE_ATTESTATION_SCHEMA = (
    "ATLASQUANT_AION_OUTBOUND_DISPATCH_WRITE_ATTESTATION_V1"
)
PROVIDER_RUNTIME_ATTESTATION_SCHEMA = (
    "ATLASQUANT_AION_OUTBOUND_PROVIDER_RUNTIME_ATTESTATION_V1"
)
CALL_BOUNDARY_SCHEMA = "ATLASQUANT_AION_OUTBOUND_SEALED_PROVIDER_CALL_BOUNDARY_V1"
OUTCOME_RECEIPT_SCHEMA = "ATLASQUANT_AION_OUTBOUND_OUTCOME_RECEIPT_V1"
RECONCILIATION_AUTH_SCHEMA = (
    "ATLASQUANT_AION_OUTBOUND_RECONCILIATION_AUTHORIZATION_V1"
)
RECONCILIATION_SCHEMA = "ATLASQUANT_AION_OUTBOUND_OUTCOME_RECONCILIATION_V1"
VERIFY_SCHEMA = "ATLASQUANT_AION_OUTBOUND_OUTCOME_CHAIN_VERIFY_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_OUTBOUND_OUTCOME_CHAIN_POLICY_V1"

OUTCOME_STATES = (
    "CONFIRMED_SUCCESS",
    "CONFIRMED_TERMINAL_FAILURE",
    "OUTCOME_UNKNOWN",
)
RECONCILIATION_STATES = (
    "RECONCILED_CONFIRMED_SUCCESS",
    "RECONCILED_CONFIRMED_TERMINAL_FAILURE",
    "STILL_OUTCOME_UNKNOWN",
)
AMBIGUITY_TRIGGERS = (
    "TIMEOUT_AFTER_DISPATCH",
    "CONNECTION_RESET_AFTER_DISPATCH",
    "PROCESS_CRASH_AFTER_DISPATCH",
    "MISSING_PROVIDER_ACK",
    "MALFORMED_PROVIDER_ACK",
    "AMBIGUOUS_PROVIDER_ACK",
    "RESPONSE_CORRELATION_MISMATCH",
    "RESPONSE_IDENTITY_MISMATCH",
    "RESPONSE_SCHEMA_MISMATCH",
    "RESPONSE_AUTHENTICITY_UNVERIFIED",
    "DUPLICATE_PROVIDER_RESPONSE_CONFLICT",
    "LATE_RESPONSE_WITHOUT_RECONCILIATION_CONTEXT",
    "EFFECT_CONFIRMATION_EVIDENCE_INCOMPLETE",
)
AUTHORITATIVE_EVIDENCE_CLASSES = (
    "PROVIDER_AUTHORITATIVE_OPERATION_STATUS",
    "PROVIDER_AUTHORITATIVE_REQUEST_LOOKUP",
    "PROVIDER_SIGNED_EVENT_OR_RECEIPT",
    "EFFECT_SIDE_AUTHORITATIVE_READBACK",
    "IMMUTABLE_DOWNSTREAM_AUDIT_RECORD",
)
RECONCILIATION_PURPOSE = "HUMAN_OWNER_EXPLICIT_OUTCOME_RECONCILIATION"
RECONCILIATION_MECHANISM = "ED25519_EXTERNAL_OWNER_EXECUTION_KEY"
RECONCILIATION_DECISIONS = (
    "AUTHORIZE_OUTCOME_RECONCILIATION",
    "DENY_OUTCOME_RECONCILIATION",
)
MAX_RUNTIME_ATTESTATION_AGE_SECONDS = 30
MAX_RECONCILIATION_AUTH_WINDOW_SECONDS = 120

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,239}$")


def _clean(value: Any, limit: int = 1600) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _identity(value: Any, limit: int = 240) -> str:
    if type(value) is not str:
        return ""
    text = _clean(value, limit)
    if text != value or not _ID_RE.fullmatch(text):
        return ""
    return text


def _sha256(value: Any) -> str:
    token = _clean(value, 90)
    return token if _SHA256_RE.fullmatch(token) else ""


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


def _digest_material(row: Mapping[str, Any], digest_field: str) -> dict[str, Any]:
    raw = dict(row)
    raw.pop(digest_field, None)
    return raw


def _string_list(value: Any, *, allowed: Sequence[str], limit: int = 20) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for item in value:
        token = _clean(item, 120).upper()
        if token in allowed and token not in out:
            out.append(token)
        if len(out) >= limit:
            break
    return out


def build_dispatch_write_attestation(
    candidate: Mapping[str, Any] | None,
    *,
    durable_dispatch_record_digest: Any,
    store_writer_attestation_digest: Any,
    persisted_state: Any,
    lease_ownership_verified: bool,
    lease_not_expired: bool,
    idempotency_reservation_verified: bool,
    effect_key_reservation_verified: bool,
    authorization_consumed_atomically: bool,
    read_after_write_verified: bool,
    writer_identity_verified: bool,
    persisted_at: Any,
) -> dict[str, Any]:
    """Represent proof of a future durable DISPATCH_RECORDED write."""
    row = dict(candidate or {})
    blockers: list[str] = []

    check = verify_durable_dispatch_record_candidate(row)
    if check.get("valid") is not True:
        blockers.append("VALID_DURABLE_DISPATCH_CANDIDATE_REQUIRED")

    record_digest = _sha256(durable_dispatch_record_digest)
    writer_digest = _sha256(store_writer_attestation_digest)
    state = _clean(persisted_state, 80).upper()
    if not record_digest:
        blockers.append("DURABLE_DISPATCH_RECORD_DIGEST_REQUIRED")
    if not writer_digest:
        blockers.append("STORE_WRITER_ATTESTATION_DIGEST_REQUIRED")
    if state != "DISPATCH_RECORDED":
        blockers.append("PERSISTED_STATE_MUST_BE_DISPATCH_RECORDED")
    if lease_ownership_verified is not True:
        blockers.append("LEASE_OWNERSHIP_VERIFICATION_REQUIRED")
    if lease_not_expired is not True:
        blockers.append("LEASE_FRESHNESS_VERIFICATION_REQUIRED")
    if idempotency_reservation_verified is not True:
        blockers.append("IDEMPOTENCY_RESERVATION_VERIFICATION_REQUIRED")
    if effect_key_reservation_verified is not True:
        blockers.append("EFFECT_KEY_RESERVATION_VERIFICATION_REQUIRED")
    if authorization_consumed_atomically is not True:
        blockers.append("AUTHORIZATION_ATOMIC_CONSUMPTION_REQUIRED")
    if read_after_write_verified is not True:
        blockers.append("DISPATCH_READ_AFTER_WRITE_REQUIRED")
    if writer_identity_verified is not True:
        blockers.append("DISPATCH_WRITER_IDENTITY_REQUIRED")

    try:
        persisted = _aware(persisted_at, "persisted_at")
        candidate_at = _aware(
            row.get("dispatch_recorded_at_candidate"),
            "dispatch_recorded_at_candidate",
        )
        if persisted < candidate_at:
            blockers.append("DISPATCH_PERSISTED_BEFORE_CANDIDATE_TIME")
    except ValueError:
        persisted = None
        blockers.append("DISPATCH_PERSISTENCE_TIME_INVALID")

    blockers = list(dict.fromkeys(blockers))
    material = {
        "execution_id": _clean(row.get("execution_id"), 160),
        "dispatch_candidate_digest": _sha256(
            row.get("dispatch_candidate_digest")
        ),
        "durable_dispatch_record_digest": record_digest,
        "store_writer_attestation_digest": writer_digest,
        "persisted_state": state,
        "lease_identity_digest": _sha256(row.get("lease_identity_digest")),
        "idempotency_key_digest": _sha256(row.get("idempotency_key_digest")),
        "effect_key_digest": _sha256(row.get("effect_key_digest")),
        "authorization_digest": _sha256(row.get("authorization_digest")),
        "payload_attestation_digest": _sha256(
            row.get("payload_attestation_digest")
        ),
        "lease_ownership_verified": lease_ownership_verified is True,
        "lease_not_expired": lease_not_expired is True,
        "idempotency_reservation_verified": (
            idempotency_reservation_verified is True
        ),
        "effect_key_reservation_verified": effect_key_reservation_verified is True,
        "authorization_consumed_atomically": (
            authorization_consumed_atomically is True
        ),
        "read_after_write_verified": read_after_write_verified is True,
        "writer_identity_verified": writer_identity_verified is True,
        "persisted_at": persisted.isoformat() if persisted else "",
    }
    return {
        "schema": DISPATCH_WRITE_ATTESTATION_SCHEMA,
        "state": "DISPATCH_RECORDED_ATTESTED" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "dispatch_write_attestation_digest": (
            _digest(material) if not blockers else ""
        ),
        "dispatch_written_by_this_module": False,
        "authorization_consumed_by_this_module": False,
        "provider_called": False,
        "network_called": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def build_provider_runtime_attestation(
    candidate: Mapping[str, Any] | None,
    *,
    provider_identity_ref: Any,
    runtime_build_digest: Any,
    adapter_manifest_digest: Any,
    endpoint_reference_digest: Any,
    credential_reference_digest: Any,
    signed_runtime_verified: bool,
    endpoint_allowlist_verified: bool,
    credential_scope_verified: bool,
    credential_not_expired: bool,
    redirect_disabled_or_bounded: bool,
    timeout_policy_verified: bool,
    transport_policy_verified: bool,
    checked_at: Any,
    now: Any,
) -> dict[str, Any]:
    """Describe the future trusted outbound runtime without exposing secrets."""
    row = dict(candidate or {})
    blockers: list[str] = []

    if verify_durable_dispatch_record_candidate(row).get("valid") is not True:
        blockers.append("VALID_DURABLE_DISPATCH_CANDIDATE_REQUIRED")

    provider = _identity(provider_identity_ref, 240)
    runtime_digest = _sha256(runtime_build_digest)
    adapter_digest = _sha256(adapter_manifest_digest)
    endpoint_digest = _sha256(endpoint_reference_digest)
    credential_digest = _sha256(credential_reference_digest)

    if not provider:
        blockers.append("PROVIDER_IDENTITY_REF_REQUIRED")
    if not runtime_digest:
        blockers.append("RUNTIME_BUILD_DIGEST_REQUIRED")
    if not adapter_digest:
        blockers.append("ADAPTER_MANIFEST_DIGEST_REQUIRED")
    if not endpoint_digest:
        blockers.append("ENDPOINT_REFERENCE_DIGEST_REQUIRED")
    if not credential_digest:
        blockers.append("CREDENTIAL_REFERENCE_DIGEST_REQUIRED")

    if adapter_digest and adapter_digest != _sha256(
        row.get("adapter_manifest_digest")
    ):
        blockers.append("ADAPTER_MANIFEST_DIGEST_MISMATCH")
    if endpoint_digest and endpoint_digest != _sha256(
        row.get("endpoint_reference_digest")
    ):
        blockers.append("ENDPOINT_REFERENCE_DIGEST_MISMATCH")
    if credential_digest and credential_digest != _sha256(
        row.get("credential_reference_digest")
    ):
        blockers.append("CREDENTIAL_REFERENCE_DIGEST_MISMATCH")

    for label, flag in (
        ("SIGNED_RUNTIME_VERIFICATION_REQUIRED", signed_runtime_verified),
        ("ENDPOINT_ALLOWLIST_VERIFICATION_REQUIRED", endpoint_allowlist_verified),
        ("CREDENTIAL_SCOPE_VERIFICATION_REQUIRED", credential_scope_verified),
        ("CREDENTIAL_FRESHNESS_VERIFICATION_REQUIRED", credential_not_expired),
        ("REDIRECT_POLICY_VERIFICATION_REQUIRED", redirect_disabled_or_bounded),
        ("TIMEOUT_POLICY_VERIFICATION_REQUIRED", timeout_policy_verified),
        ("TRANSPORT_POLICY_VERIFICATION_REQUIRED", transport_policy_verified),
    ):
        if flag is not True:
            blockers.append(label)

    try:
        checked = _aware(checked_at, "checked_at")
        current = _aware(now, "now")
        age = (current - checked).total_seconds()
        if age < 0:
            blockers.append("RUNTIME_ATTESTATION_FROM_FUTURE")
        if age > MAX_RUNTIME_ATTESTATION_AGE_SECONDS:
            blockers.append("RUNTIME_ATTESTATION_STALE")
    except ValueError:
        checked = None
        blockers.append("RUNTIME_ATTESTATION_TIME_INVALID")

    blockers = list(dict.fromkeys(blockers))
    material = {
        "provider_identity_ref": provider,
        "runtime_build_digest": runtime_digest,
        "adapter_manifest_digest": adapter_digest,
        "endpoint_reference_digest": endpoint_digest,
        "credential_reference_digest": credential_digest,
        "signed_runtime_verified": signed_runtime_verified is True,
        "endpoint_allowlist_verified": endpoint_allowlist_verified is True,
        "credential_scope_verified": credential_scope_verified is True,
        "credential_not_expired": credential_not_expired is True,
        "redirect_disabled_or_bounded": redirect_disabled_or_bounded is True,
        "timeout_policy_verified": timeout_policy_verified is True,
        "transport_policy_verified": transport_policy_verified is True,
        "checked_at": checked.isoformat() if checked else "",
    }
    return {
        "schema": PROVIDER_RUNTIME_ATTESTATION_SCHEMA,
        "state": "PROVIDER_RUNTIME_ATTESTED" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "runtime_attestation_digest": _digest(material) if not blockers else "",
        "raw_endpoint_included": False,
        "raw_credential_included": False,
        "secret_material_included": False,
        "provider_called": False,
        "network_called": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def build_sealed_provider_call_boundary(
    candidate: Mapping[str, Any] | None,
    dispatch_attestation: Mapping[str, Any] | None,
    runtime_attestation: Mapping[str, Any] | None,
    *,
    call_attempt_id: Any,
    provider_request_correlation_digest: Any,
) -> dict[str, Any]:
    """Seal the exact one-call attempt. Does not perform the call."""
    row = dict(candidate or {})
    dispatch = dict(dispatch_attestation or {})
    runtime = dict(runtime_attestation or {})
    blockers: list[str] = []

    if verify_durable_dispatch_record_candidate(row).get("valid") is not True:
        blockers.append("VALID_DURABLE_DISPATCH_CANDIDATE_REQUIRED")

    if dispatch.get("schema") != DISPATCH_WRITE_ATTESTATION_SCHEMA:
        blockers.append("DISPATCH_WRITE_ATTESTATION_SCHEMA_MISMATCH")
    if dispatch.get("state") != "DISPATCH_RECORDED_ATTESTED":
        blockers.append("DISPATCH_RECORDED_ATTESTATION_REQUIRED")
    if dispatch.get("authorization_consumed_atomically") is not True:
        blockers.append("AUTHORIZATION_MUST_BE_CONSUMED_AT_DISPATCH_WRITE")
    if _sha256(dispatch.get("dispatch_candidate_digest")) != _sha256(
        row.get("dispatch_candidate_digest")
    ):
        blockers.append("DISPATCH_CANDIDATE_BINDING_MISMATCH")

    if runtime.get("schema") != PROVIDER_RUNTIME_ATTESTATION_SCHEMA:
        blockers.append("PROVIDER_RUNTIME_ATTESTATION_SCHEMA_MISMATCH")
    if runtime.get("state") != "PROVIDER_RUNTIME_ATTESTED":
        blockers.append("PROVIDER_RUNTIME_ATTESTATION_REQUIRED")
    if _sha256(runtime.get("adapter_manifest_digest")) != _sha256(
        row.get("adapter_manifest_digest")
    ):
        blockers.append("RUNTIME_ADAPTER_BINDING_MISMATCH")
    if _sha256(runtime.get("endpoint_reference_digest")) != _sha256(
        row.get("endpoint_reference_digest")
    ):
        blockers.append("RUNTIME_ENDPOINT_BINDING_MISMATCH")
    if _sha256(runtime.get("credential_reference_digest")) != _sha256(
        row.get("credential_reference_digest")
    ):
        blockers.append("RUNTIME_CREDENTIAL_BINDING_MISMATCH")

    attempt = _identity(call_attempt_id, 180)
    correlation = _sha256(provider_request_correlation_digest)
    if not attempt:
        blockers.append("CALL_ATTEMPT_ID_REQUIRED")
    if not correlation:
        blockers.append("PROVIDER_REQUEST_CORRELATION_DIGEST_REQUIRED")

    blockers = list(dict.fromkeys(blockers))
    material = {
        "call_attempt_id": attempt,
        "execution_id": _clean(row.get("execution_id"), 160),
        "observability_trace_id": _clean(
            row.get("observability_trace_id"), 200
        ),
        "durable_dispatch_record_digest": _sha256(
            dispatch.get("durable_dispatch_record_digest")
        ),
        "dispatch_write_attestation_digest": _sha256(
            dispatch.get("dispatch_write_attestation_digest")
        ),
        "provider_runtime_attestation_digest": _sha256(
            runtime.get("runtime_attestation_digest")
        ),
        "provider_identity_ref": _clean(
            runtime.get("provider_identity_ref"), 240
        ),
        "runtime_build_digest": _sha256(runtime.get("runtime_build_digest")),
        "adapter_manifest_digest": _sha256(row.get("adapter_manifest_digest")),
        "subject_digest": _sha256(row.get("subject_digest")),
        "requested_action": _clean(row.get("requested_action"), 80).upper(),
        "payload_digest": _sha256(row.get("payload_digest")),
        "recipient_resolution_digest": _sha256(
            row.get("recipient_resolution_digest")
        ),
        "endpoint_reference_digest": _sha256(
            row.get("endpoint_reference_digest")
        ),
        "credential_reference_digest": _sha256(
            row.get("credential_reference_digest")
        ),
        "request_headers_policy_digest": _sha256(
            row.get("request_headers_policy_digest")
        ),
        "transport_policy_digest": _sha256(
            row.get("transport_policy_digest")
        ),
        "timeout_policy_digest": _sha256(row.get("timeout_policy_digest")),
        "idempotency_key_digest": _sha256(row.get("idempotency_key_digest")),
        "effect_key_digest": _sha256(row.get("effect_key_digest")),
        "provider_request_correlation_digest": correlation,
    }
    return {
        "schema": CALL_BOUNDARY_SCHEMA,
        "state": "SEALED_SINGLE_CALL_READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "call_boundary_digest": _digest(material) if not blockers else "",
        "exactly_one_call_attempt_allowed": True,
        "provider_switch_allowed": False,
        "endpoint_switch_allowed": False,
        "credential_switch_allowed": False,
        "payload_mutation_allowed": False,
        "capability_expansion_allowed": False,
        "scope_expansion_allowed": False,
        "provider_called": False,
        "network_called": False,
        "call_attempt_started": False,
        "outcome_receipt_created": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def build_outcome_receipt(
    call_boundary: Mapping[str, Any] | None,
    *,
    requested_outcome: Any,
    provider_response_evidence_digest: Any = "",
    observed_at: Any,
    ambiguity_triggers: Sequence[Any] | None = None,
    provider_identity_match: bool = False,
    runtime_build_match: bool = False,
    execution_id_match: bool = False,
    trace_id_match: bool = False,
    provider_request_correlation_match: bool = False,
    idempotency_key_match: bool = False,
    effect_key_match: bool = False,
    response_schema_valid: bool = False,
    response_authenticity_verified: bool = False,
    provider_success_semantics_attested: bool = False,
    effect_confirmation_complete: bool = False,
    expected_postcondition_match: bool = False,
    provider_terminal_failure_semantics_attested: bool = False,
    no_effect_or_terminal_rejection_evidence_complete: bool = False,
) -> dict[str, Any]:
    """Classify observed evidence. Ambiguity always wins and becomes UNKNOWN."""
    boundary = dict(call_boundary or {})
    blockers: list[str] = []

    if boundary.get("schema") != CALL_BOUNDARY_SCHEMA:
        blockers.append("CALL_BOUNDARY_SCHEMA_MISMATCH")
    if boundary.get("state") != "SEALED_SINGLE_CALL_READY":
        blockers.append("SEALED_SINGLE_CALL_BOUNDARY_REQUIRED")

    requested = _clean(requested_outcome, 80).upper()
    if requested not in OUTCOME_STATES:
        blockers.append("OUTCOME_STATE_INVALID")

    evidence_digest = _sha256(provider_response_evidence_digest)
    ambiguity = _string_list(
        ambiguity_triggers,
        allowed=AMBIGUITY_TRIGGERS,
        limit=20,
    )

    try:
        observed = _aware(observed_at, "observed_at")
    except ValueError:
        observed = None
        blockers.append("OUTCOME_OBSERVED_AT_INVALID")

    success_requirements = all((
        provider_identity_match is True,
        runtime_build_match is True,
        execution_id_match is True,
        trace_id_match is True,
        provider_request_correlation_match is True,
        idempotency_key_match is True,
        effect_key_match is True,
        response_schema_valid is True,
        response_authenticity_verified is True,
        provider_success_semantics_attested is True,
        effect_confirmation_complete is True,
        expected_postcondition_match is True,
        bool(evidence_digest),
    ))
    failure_requirements = all((
        provider_identity_match is True,
        execution_id_match is True,
        provider_request_correlation_match is True,
        response_schema_valid is True,
        response_authenticity_verified is True,
        provider_terminal_failure_semantics_attested is True,
        no_effect_or_terminal_rejection_evidence_complete is True,
        bool(evidence_digest),
    ))

    if blockers:
        final_outcome = "OUTCOME_UNKNOWN"
    elif ambiguity:
        final_outcome = "OUTCOME_UNKNOWN"
    elif requested == "CONFIRMED_SUCCESS" and success_requirements:
        final_outcome = "CONFIRMED_SUCCESS"
    elif requested == "CONFIRMED_TERMINAL_FAILURE" and failure_requirements:
        final_outcome = "CONFIRMED_TERMINAL_FAILURE"
    elif requested == "OUTCOME_UNKNOWN":
        final_outcome = "OUTCOME_UNKNOWN"
    else:
        final_outcome = "OUTCOME_UNKNOWN"
        ambiguity.append("EFFECT_CONFIRMATION_EVIDENCE_INCOMPLETE")

    ambiguity = list(dict.fromkeys(ambiguity))
    material = {
        "call_boundary_digest": _sha256(boundary.get("call_boundary_digest")),
        "call_attempt_id": _clean(boundary.get("call_attempt_id"), 180),
        "execution_id": _clean(boundary.get("execution_id"), 160),
        "observability_trace_id": _clean(
            boundary.get("observability_trace_id"), 200
        ),
        "durable_dispatch_record_digest": _sha256(
            boundary.get("durable_dispatch_record_digest")
        ),
        "provider_identity_ref": _clean(
            boundary.get("provider_identity_ref"), 240
        ),
        "runtime_build_digest": _sha256(boundary.get("runtime_build_digest")),
        "subject_digest": _sha256(boundary.get("subject_digest")),
        "requested_action": _clean(
            boundary.get("requested_action"), 80
        ).upper(),
        "payload_digest": _sha256(boundary.get("payload_digest")),
        "idempotency_key_digest": _sha256(
            boundary.get("idempotency_key_digest")
        ),
        "effect_key_digest": _sha256(boundary.get("effect_key_digest")),
        "provider_request_correlation_digest": _sha256(
            boundary.get("provider_request_correlation_digest")
        ),
        "provider_response_evidence_digest": evidence_digest,
        "requested_outcome": requested,
        "outcome_state": final_outcome,
        "ambiguity_triggers": ambiguity,
        "observed_at": observed.isoformat() if observed else "",
        "provider_identity_match": provider_identity_match is True,
        "runtime_build_match": runtime_build_match is True,
        "execution_id_match": execution_id_match is True,
        "trace_id_match": trace_id_match is True,
        "provider_request_correlation_match": (
            provider_request_correlation_match is True
        ),
        "idempotency_key_match": idempotency_key_match is True,
        "effect_key_match": effect_key_match is True,
        "response_schema_valid": response_schema_valid is True,
        "response_authenticity_verified": (
            response_authenticity_verified is True
        ),
        "provider_success_semantics_attested": (
            provider_success_semantics_attested is True
        ),
        "effect_confirmation_complete": effect_confirmation_complete is True,
        "expected_postcondition_match": expected_postcondition_match is True,
        "provider_terminal_failure_semantics_attested": (
            provider_terminal_failure_semantics_attested is True
        ),
        "no_effect_or_terminal_rejection_evidence_complete": (
            no_effect_or_terminal_rejection_evidence_complete is True
        ),
    }

    receipt_valid = not blockers
    return {
        "schema": OUTCOME_RECEIPT_SCHEMA,
        "state": "OUTCOME_RECEIPT_READY" if receipt_valid else "BLOCKED",
        "blockers": blockers,
        **material,
        "outcome_receipt_digest": _digest(material) if receipt_valid else "",
        "receipt_is_append_only": True,
        "receipt_is_immutable": True,
        "success_inferred_from_silence": False,
        "failure_inferred_from_silence": False,
        "outcome_unknown_automatic_retry_allowed": False,
        "outcome_unknown_requires_separate_reconciliation": True,
        "new_attempt_requires_fresh_authorization": True,
        "original_receipt_mutable": False,
        "receipt_persisted_by_this_module": False,
        "provider_called_by_this_module": False,
        "network_called_by_this_module": False,
        "retry_executed": False,
        "external_action_executed_by_this_module": False,
        "executes_action": False,
    }


def build_reconciliation_authorization(
    outcome_receipt: Mapping[str, Any] | None,
    *,
    authorization_id: Any,
    decision: Any,
    owner_binding_digest: Any,
    owner_key_fingerprint: Any,
    signed_request_digest: Any,
    nonce_digest: Any,
    verified_owner_signature: bool,
    verified_active_trust_root: bool,
    persistent_nonce_replay_guard_verified: bool,
    nonce_single_use_claimed: bool,
    issued_at: Any,
    expires_at: Any,
    now: Any,
) -> dict[str, Any]:
    """Represent separate HUMAN_OWNER authorization for UNKNOWN reconciliation."""
    receipt = dict(outcome_receipt or {})
    blockers: list[str] = []

    if receipt.get("schema") != OUTCOME_RECEIPT_SCHEMA:
        blockers.append("OUTCOME_RECEIPT_SCHEMA_MISMATCH")
    if receipt.get("state") != "OUTCOME_RECEIPT_READY":
        blockers.append("VALID_OUTCOME_RECEIPT_REQUIRED")
    if receipt.get("outcome_state") != "OUTCOME_UNKNOWN":
        blockers.append("RECONCILIATION_ONLY_ALLOWED_FOR_OUTCOME_UNKNOWN")

    auth_id = _identity(authorization_id, 160)
    decision_name = _clean(decision, 80).upper()
    owner_digest = _sha256(owner_binding_digest)
    key_digest = _sha256(owner_key_fingerprint)
    request_digest = _sha256(signed_request_digest)
    nonce = _sha256(nonce_digest)

    if not auth_id:
        blockers.append("RECONCILIATION_AUTHORIZATION_ID_REQUIRED")
    if decision_name not in RECONCILIATION_DECISIONS:
        blockers.append("RECONCILIATION_DECISION_INVALID")
    if not owner_digest:
        blockers.append("OWNER_BINDING_DIGEST_REQUIRED")
    if not key_digest:
        blockers.append("OWNER_KEY_FINGERPRINT_REQUIRED")
    if not request_digest:
        blockers.append("SIGNED_REQUEST_DIGEST_REQUIRED")
    if not nonce:
        blockers.append("RECONCILIATION_NONCE_DIGEST_REQUIRED")
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

    blockers = list(dict.fromkeys(blockers))
    material = {
        "authorization_id": auth_id,
        "purpose": RECONCILIATION_PURPOSE,
        "mechanism": RECONCILIATION_MECHANISM,
        "decision": decision_name,
        "original_outcome_receipt_digest": _sha256(
            receipt.get("outcome_receipt_digest")
        ),
        "execution_id": _clean(receipt.get("execution_id"), 160),
        "owner_binding_digest": owner_digest,
        "owner_key_fingerprint": key_digest,
        "signed_request_digest": request_digest,
        "nonce_digest": nonce,
        "verified_owner_signature": verified_owner_signature is True,
        "verified_active_trust_root": verified_active_trust_root is True,
        "persistent_nonce_replay_guard_verified": (
            persistent_nonce_replay_guard_verified is True
        ),
        "nonce_single_use_claimed": nonce_single_use_claimed is True,
        "issued_at": issued.isoformat() if issued else "",
        "expires_at": expires.isoformat() if expires else "",
        "verified_at": current.isoformat() if current else "",
    }
    approved = (
        not blockers
        and decision_name == "AUTHORIZE_OUTCOME_RECONCILIATION"
    )
    denied = (
        not blockers
        and decision_name == "DENY_OUTCOME_RECONCILIATION"
    )
    return {
        "schema": RECONCILIATION_AUTH_SCHEMA,
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
        "provider_query_authorized_by_this_module": False,
        "retry_authorized": False,
        "new_attempt_authorized": False,
        "provider_called": False,
        "network_called": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def build_outcome_reconciliation(
    outcome_receipt: Mapping[str, Any] | None,
    reconciliation_authorization: Mapping[str, Any] | None,
    *,
    reconciliation_id: Any,
    evidence_class: Any,
    evidence_source_digest: Any,
    evidence_record_digest: Any,
    provider_identity_match: bool,
    execution_id_match: bool,
    trace_id_match: bool,
    provider_request_correlation_match: bool,
    idempotency_key_match: bool,
    effect_key_match: bool,
    evidence_source_attested: bool,
    evidence_schema_valid: bool,
    evidence_authenticity_verified: bool,
    evidence_freshness_verified: bool,
    evidence_sequence_monotonic: bool,
    success_evidence_complete: bool,
    expected_postcondition_match: bool,
    terminal_failure_or_no_effect_evidence_complete: bool,
    conflicting_evidence_present: bool,
    observed_at: Any,
) -> dict[str, Any]:
    """Append a separate reconciliation record. Never rewrites the receipt."""
    receipt = dict(outcome_receipt or {})
    auth = dict(reconciliation_authorization or {})
    blockers: list[str] = []

    if receipt.get("schema") != OUTCOME_RECEIPT_SCHEMA:
        blockers.append("OUTCOME_RECEIPT_SCHEMA_MISMATCH")
    if receipt.get("state") != "OUTCOME_RECEIPT_READY":
        blockers.append("VALID_OUTCOME_RECEIPT_REQUIRED")
    if receipt.get("outcome_state") != "OUTCOME_UNKNOWN":
        blockers.append("ORIGINAL_OUTCOME_MUST_BE_UNKNOWN")

    if auth.get("schema") != RECONCILIATION_AUTH_SCHEMA:
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
        blockers.append("RECONCILIATION_AUTH_RECEIPT_BINDING_MISMATCH")

    rid = _identity(reconciliation_id, 180)
    evidence_kind = _clean(evidence_class, 100).upper()
    source_digest = _sha256(evidence_source_digest)
    record_digest = _sha256(evidence_record_digest)
    if not rid:
        blockers.append("RECONCILIATION_ID_REQUIRED")
    if evidence_kind not in AUTHORITATIVE_EVIDENCE_CLASSES:
        blockers.append("AUTHORITATIVE_EVIDENCE_CLASS_REQUIRED")
    if not source_digest:
        blockers.append("EVIDENCE_SOURCE_DIGEST_REQUIRED")
    if not record_digest:
        blockers.append("EVIDENCE_RECORD_DIGEST_REQUIRED")

    try:
        observed = _aware(observed_at, "observed_at")
    except ValueError:
        observed = None
        blockers.append("RECONCILIATION_OBSERVED_AT_INVALID")

    core_matches = all((
        provider_identity_match is True,
        execution_id_match is True,
        trace_id_match is True,
        provider_request_correlation_match is True,
        idempotency_key_match is True,
        effect_key_match is True,
        evidence_source_attested is True,
        evidence_schema_valid is True,
        evidence_authenticity_verified is True,
        evidence_freshness_verified is True,
        evidence_sequence_monotonic is True,
    ))

    if blockers:
        result_state = "STILL_OUTCOME_UNKNOWN"
    elif conflicting_evidence_present:
        result_state = "STILL_OUTCOME_UNKNOWN"
    elif (
        core_matches
        and success_evidence_complete is True
        and expected_postcondition_match is True
        and terminal_failure_or_no_effect_evidence_complete is not True
    ):
        result_state = "RECONCILED_CONFIRMED_SUCCESS"
    elif (
        core_matches
        and terminal_failure_or_no_effect_evidence_complete is True
        and success_evidence_complete is not True
    ):
        result_state = "RECONCILED_CONFIRMED_TERMINAL_FAILURE"
    else:
        result_state = "STILL_OUTCOME_UNKNOWN"

    material = {
        "reconciliation_id": rid,
        "original_outcome_receipt_digest": _sha256(
            receipt.get("outcome_receipt_digest")
        ),
        "reconciliation_authorization_digest": _sha256(
            auth.get("reconciliation_authorization_digest")
        ),
        "execution_id": _clean(receipt.get("execution_id"), 160),
        "observability_trace_id": _clean(
            receipt.get("observability_trace_id"), 200
        ),
        "provider_request_correlation_digest": _sha256(
            receipt.get("provider_request_correlation_digest")
        ),
        "idempotency_key_digest": _sha256(
            receipt.get("idempotency_key_digest")
        ),
        "effect_key_digest": _sha256(receipt.get("effect_key_digest")),
        "evidence_class": evidence_kind,
        "evidence_source_digest": source_digest,
        "evidence_record_digest": record_digest,
        "provider_identity_match": provider_identity_match is True,
        "execution_id_match": execution_id_match is True,
        "trace_id_match": trace_id_match is True,
        "provider_request_correlation_match": (
            provider_request_correlation_match is True
        ),
        "idempotency_key_match": idempotency_key_match is True,
        "effect_key_match": effect_key_match is True,
        "evidence_source_attested": evidence_source_attested is True,
        "evidence_schema_valid": evidence_schema_valid is True,
        "evidence_authenticity_verified": (
            evidence_authenticity_verified is True
        ),
        "evidence_freshness_verified": evidence_freshness_verified is True,
        "evidence_sequence_monotonic": evidence_sequence_monotonic is True,
        "success_evidence_complete": success_evidence_complete is True,
        "expected_postcondition_match": expected_postcondition_match is True,
        "terminal_failure_or_no_effect_evidence_complete": (
            terminal_failure_or_no_effect_evidence_complete is True
        ),
        "conflicting_evidence_present": conflicting_evidence_present is True,
        "reconciled_outcome_state": result_state,
        "observed_at": observed.isoformat() if observed else "",
    }
    return {
        "schema": RECONCILIATION_SCHEMA,
        "state": "RECONCILIATION_RECORD_READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "reconciliation_digest": _digest(material) if not blockers else "",
        "original_receipt_immutable": True,
        "original_receipt_mutated": False,
        "reconciliation_is_retry": False,
        "external_effect_replayed": False,
        "automatic_retry_allowed": False,
        "new_attempt_authorized": False,
        "new_attempt_requires_confirmed_no_effect": True,
        "new_attempt_requires_fresh_owner_authorization": True,
        "new_attempt_requires_new_durable_dispatch": True,
        "authorization_consumed_by_this_module": False,
        "provider_called_by_this_module": False,
        "network_called_by_this_module": False,
        "external_action_executed_by_this_module": False,
        "executes_action": False,
    }


def _verification_material(
    raw: Mapping[str, Any],
    schema: str,
) -> tuple[str, dict[str, Any], str, tuple[str, ...], tuple[str, ...]]:
    specs = {
        DISPATCH_WRITE_ATTESTATION_SCHEMA: (
            "dispatch_write_attestation_digest",
            "DISPATCH_RECORDED_ATTESTED",
            (
                "execution_id",
                "dispatch_candidate_digest",
                "durable_dispatch_record_digest",
                "store_writer_attestation_digest",
                "persisted_state",
                "lease_identity_digest",
                "idempotency_key_digest",
                "effect_key_digest",
                "authorization_digest",
                "payload_attestation_digest",
                "lease_ownership_verified",
                "lease_not_expired",
                "idempotency_reservation_verified",
                "effect_key_reservation_verified",
                "authorization_consumed_atomically",
                "read_after_write_verified",
                "writer_identity_verified",
                "persisted_at",
            ),
            (
                "lease_ownership_verified",
                "lease_not_expired",
                "idempotency_reservation_verified",
                "effect_key_reservation_verified",
                "authorization_consumed_atomically",
                "read_after_write_verified",
                "writer_identity_verified",
            ),
            (
                "dispatch_written_by_this_module",
                "authorization_consumed_by_this_module",
                "provider_called",
                "network_called",
                "external_action_executed",
                "executes_action",
            ),
        ),
        PROVIDER_RUNTIME_ATTESTATION_SCHEMA: (
            "runtime_attestation_digest",
            "PROVIDER_RUNTIME_ATTESTED",
            (
                "provider_identity_ref",
                "runtime_build_digest",
                "adapter_manifest_digest",
                "endpoint_reference_digest",
                "credential_reference_digest",
                "signed_runtime_verified",
                "endpoint_allowlist_verified",
                "credential_scope_verified",
                "credential_not_expired",
                "redirect_disabled_or_bounded",
                "timeout_policy_verified",
                "transport_policy_verified",
                "checked_at",
            ),
            (
                "signed_runtime_verified",
                "endpoint_allowlist_verified",
                "credential_scope_verified",
                "credential_not_expired",
                "redirect_disabled_or_bounded",
                "timeout_policy_verified",
                "transport_policy_verified",
            ),
            (
                "raw_endpoint_included",
                "raw_credential_included",
                "secret_material_included",
                "provider_called",
                "network_called",
                "external_action_executed",
                "executes_action",
            ),
        ),
        CALL_BOUNDARY_SCHEMA: (
            "call_boundary_digest",
            "SEALED_SINGLE_CALL_READY",
            (
                "call_attempt_id",
                "execution_id",
                "observability_trace_id",
                "durable_dispatch_record_digest",
                "dispatch_write_attestation_digest",
                "provider_runtime_attestation_digest",
                "provider_identity_ref",
                "runtime_build_digest",
                "adapter_manifest_digest",
                "subject_digest",
                "requested_action",
                "payload_digest",
                "recipient_resolution_digest",
                "endpoint_reference_digest",
                "credential_reference_digest",
                "request_headers_policy_digest",
                "transport_policy_digest",
                "timeout_policy_digest",
                "idempotency_key_digest",
                "effect_key_digest",
                "provider_request_correlation_digest",
            ),
            ("exactly_one_call_attempt_allowed",),
            (
                "provider_switch_allowed",
                "endpoint_switch_allowed",
                "credential_switch_allowed",
                "payload_mutation_allowed",
                "capability_expansion_allowed",
                "scope_expansion_allowed",
                "provider_called",
                "network_called",
                "call_attempt_started",
                "outcome_receipt_created",
                "external_action_executed",
                "executes_action",
            ),
        ),
        OUTCOME_RECEIPT_SCHEMA: (
            "outcome_receipt_digest",
            "OUTCOME_RECEIPT_READY",
            (
                "call_boundary_digest",
                "call_attempt_id",
                "execution_id",
                "observability_trace_id",
                "durable_dispatch_record_digest",
                "provider_identity_ref",
                "runtime_build_digest",
                "subject_digest",
                "requested_action",
                "payload_digest",
                "idempotency_key_digest",
                "effect_key_digest",
                "provider_request_correlation_digest",
                "provider_response_evidence_digest",
                "requested_outcome",
                "outcome_state",
                "ambiguity_triggers",
                "observed_at",
                "provider_identity_match",
                "runtime_build_match",
                "execution_id_match",
                "trace_id_match",
                "provider_request_correlation_match",
                "idempotency_key_match",
                "effect_key_match",
                "response_schema_valid",
                "response_authenticity_verified",
                "provider_success_semantics_attested",
                "effect_confirmation_complete",
                "expected_postcondition_match",
                "provider_terminal_failure_semantics_attested",
                "no_effect_or_terminal_rejection_evidence_complete",
            ),
            (
                "receipt_is_append_only",
                "receipt_is_immutable",
                "outcome_unknown_requires_separate_reconciliation",
                "new_attempt_requires_fresh_authorization",
            ),
            (
                "success_inferred_from_silence",
                "failure_inferred_from_silence",
                "outcome_unknown_automatic_retry_allowed",
                "original_receipt_mutable",
                "receipt_persisted_by_this_module",
                "provider_called_by_this_module",
                "network_called_by_this_module",
                "retry_executed",
                "external_action_executed_by_this_module",
                "executes_action",
            ),
        ),
        RECONCILIATION_AUTH_SCHEMA: (
            "reconciliation_authorization_digest",
            "RECONCILIATION_AUTHORIZED",
            (
                "authorization_id",
                "purpose",
                "mechanism",
                "decision",
                "original_outcome_receipt_digest",
                "execution_id",
                "owner_binding_digest",
                "owner_key_fingerprint",
                "signed_request_digest",
                "nonce_digest",
                "verified_owner_signature",
                "verified_active_trust_root",
                "persistent_nonce_replay_guard_verified",
                "nonce_single_use_claimed",
                "issued_at",
                "expires_at",
                "verified_at",
            ),
            (
                "reconciliation_authorized",
                "verified_owner_signature",
                "verified_active_trust_root",
                "persistent_nonce_replay_guard_verified",
                "nonce_single_use_claimed",
            ),
            (
                "reconciliation_denied",
                "authorization_consumed",
                "provider_query_authorized_by_this_module",
                "retry_authorized",
                "new_attempt_authorized",
                "provider_called",
                "network_called",
                "external_action_executed",
                "executes_action",
            ),
        ),
        RECONCILIATION_SCHEMA: (
            "reconciliation_digest",
            "RECONCILIATION_RECORD_READY",
            (
                "reconciliation_id",
                "original_outcome_receipt_digest",
                "reconciliation_authorization_digest",
                "execution_id",
                "observability_trace_id",
                "provider_request_correlation_digest",
                "idempotency_key_digest",
                "effect_key_digest",
                "evidence_class",
                "evidence_source_digest",
                "evidence_record_digest",
                "provider_identity_match",
                "execution_id_match",
                "trace_id_match",
                "provider_request_correlation_match",
                "idempotency_key_match",
                "effect_key_match",
                "evidence_source_attested",
                "evidence_schema_valid",
                "evidence_authenticity_verified",
                "evidence_freshness_verified",
                "evidence_sequence_monotonic",
                "success_evidence_complete",
                "expected_postcondition_match",
                "terminal_failure_or_no_effect_evidence_complete",
                "conflicting_evidence_present",
                "reconciled_outcome_state",
                "observed_at",
            ),
            (
                "original_receipt_immutable",
                "new_attempt_requires_confirmed_no_effect",
                "new_attempt_requires_fresh_owner_authorization",
                "new_attempt_requires_new_durable_dispatch",
            ),
            (
                "original_receipt_mutated",
                "reconciliation_is_retry",
                "external_effect_replayed",
                "automatic_retry_allowed",
                "new_attempt_authorized",
                "authorization_consumed_by_this_module",
                "provider_called_by_this_module",
                "network_called_by_this_module",
                "external_action_executed_by_this_module",
                "executes_action",
            ),
        ),
    }
    spec = specs.get(schema)
    if spec is None:
        return "", {}, "", (), ()
    digest_field, expected_state, fields, required_true, required_false = spec
    return (
        digest_field,
        {key: raw.get(key) for key in fields},
        expected_state,
        required_true,
        required_false,
    )


def verify_outcome_chain_record(
    record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw = dict(record or {})
    blockers: list[str] = []
    schema = raw.get("schema")

    (
        digest_field,
        material,
        expected_state,
        required_true,
        required_false,
    ) = _verification_material(raw, schema)

    if not digest_field:
        return {
            "schema": VERIFY_SCHEMA,
            "state": "INVALID",
            "valid": False,
            "blockers": ["UNSUPPORTED_RECORD_SCHEMA"],
            "executes_action": False,
        }

    if raw.get("state") != expected_state:
        blockers.append("RECORD_STATE_INVALID")

    supplied = _sha256(raw.get(digest_field))
    expected = _digest(material)
    if not supplied or supplied != expected:
        blockers.append("RECORD_DIGEST_MISMATCH")

    for key in required_true:
        if raw.get(key) is not True:
            blockers.append("REQUIRED_RECORD_GUARD_MISSING:" + key)

    for key in required_false:
        if raw.get(key) is not False:
            blockers.append("RECORD_BOUNDARY_INVALID:" + key)

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": VERIFY_SCHEMA,
        "state": "VALID" if not blockers else "INVALID",
        "valid": not blockers,
        "blockers": blockers,
        "record_schema": schema,
        "record_digest": supplied,
        "executes_action": False,
    }


def outcome_chain_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "durable_dispatch_record_required_before_call": True,
        "authorization_consumed_atomically_before_call": True,
        "provider_runtime_attestation_required": True,
        "sealed_exact_single_call_required": True,
        "provider_switch_after_dispatch_allowed": False,
        "endpoint_switch_after_dispatch_allowed": False,
        "credential_switch_after_dispatch_allowed": False,
        "payload_mutation_after_dispatch_allowed": False,
        "capability_expansion_after_dispatch_allowed": False,
        "outcome_states": list(OUTCOME_STATES),
        "success_requires_complete_positive_evidence": True,
        "terminal_failure_requires_authoritative_evidence": True,
        "silence_is_success": False,
        "silence_is_terminal_failure": False,
        "ambiguity_always_outcome_unknown": True,
        "outcome_receipt_append_only": True,
        "outcome_receipt_immutable": True,
        "outcome_unknown_automatic_retry_allowed": False,
        "outcome_unknown_requires_separate_reconciliation": True,
        "reconciliation_requires_separate_owner_authorization": True,
        "reconciliation_original_receipt_immutable": True,
        "reconciliation_is_retry": False,
        "conflicting_evidence_preserves_unknown": True,
        "incomplete_evidence_preserves_unknown": True,
        "new_attempt_requires_confirmed_no_effect": True,
        "new_attempt_requires_fresh_owner_authorization": True,
        "new_attempt_requires_new_durable_dispatch": True,
        "dispatch_written_by_this_module": False,
        "authorization_consumed_by_this_module": False,
        "provider_called": False,
        "network_called": False,
        "message_sent": False,
        "contract_exported": False,
        "signature_requested": False,
        "retry_executed": False,
        "worker_armed": False,
        "deploy_executed": False,
        "core_checkpoint_write": False,
        "external_action_executed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "DISPATCH_WRITE_ATTESTATION_SCHEMA",
    "PROVIDER_RUNTIME_ATTESTATION_SCHEMA",
    "CALL_BOUNDARY_SCHEMA",
    "OUTCOME_RECEIPT_SCHEMA",
    "RECONCILIATION_AUTH_SCHEMA",
    "RECONCILIATION_SCHEMA",
    "VERIFY_SCHEMA",
    "POLICY_SCHEMA",
    "OUTCOME_STATES",
    "RECONCILIATION_STATES",
    "AMBIGUITY_TRIGGERS",
    "AUTHORITATIVE_EVIDENCE_CLASSES",
    "RECONCILIATION_PURPOSE",
    "RECONCILIATION_MECHANISM",
    "RECONCILIATION_DECISIONS",
    "build_dispatch_write_attestation",
    "build_provider_runtime_attestation",
    "build_sealed_provider_call_boundary",
    "build_outcome_receipt",
    "build_reconciliation_authorization",
    "build_outcome_reconciliation",
    "verify_outcome_chain_record",
    "outcome_chain_policy",
]
