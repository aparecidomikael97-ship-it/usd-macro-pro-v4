"""AION Outbound Execution Authorization + Durable Dispatch V1.

Pure contracts for the two gates that must exist after an approved outbound
bridge and before any provider call:

1. fresh single-use HUMAN_OWNER execution-intent verification;
2. durable dispatch record candidate, bound to a sealed payload attestation.

No cryptographic signature is verified here; a future trusted verifier supplies
that attestation. No nonce is persisted here. No durable dispatch record is
written here. No provider is called.

A positive state never means an email/WhatsApp/contract export happened.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_approval_outbound_dispatch_bridge_v1 import (
    BRIDGE_SCHEMA,
    verify_outbound_dispatch_bridge,
)


SCHEMA = "ATLASQUANT_AION_OUTBOUND_EXECUTION_AUTH_DURABLE_DISPATCH_V1"
AUTH_SCHEMA = "ATLASQUANT_AION_FRESH_OUTBOUND_EXECUTION_AUTHORIZATION_V1"
AUTH_PERSISTENCE_SCHEMA = "ATLASQUANT_AION_OUTBOUND_EXECUTION_AUTH_PERSISTENCE_ATTESTATION_V1"
PAYLOAD_ATTESTATION_SCHEMA = "ATLASQUANT_AION_OUTBOUND_SEALED_PAYLOAD_ATTESTATION_V1"
DISPATCH_SCHEMA = "ATLASQUANT_AION_OUTBOUND_DURABLE_DISPATCH_RECORD_CANDIDATE_V1"
VERIFY_SCHEMA = "ATLASQUANT_AION_OUTBOUND_DURABLE_DISPATCH_VERIFY_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_OUTBOUND_EXECUTION_DISPATCH_POLICY_V1"

PURPOSE = "HUMAN_OWNER_EXPLICIT_OUTBOUND_EXTERNAL_EFFECT_EXECUTION"
MECHANISM = "ED25519_EXTERNAL_OWNER_EXECUTION_KEY"
DECISIONS = ("AUTHORIZE_OUTBOUND_EXECUTION", "DENY_OUTBOUND_EXECUTION")
MAX_AUTHORIZATION_WINDOW_SECONDS = 120
MAX_PAYLOAD_ATTESTATION_AGE_SECONDS = 30

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,239}$")


def _clean(value: Any, limit: int = 1000) -> str:
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


def _auth_material(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(row)
    raw.pop("authorization_digest", None)
    return raw


def _payload_material(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(row)
    raw.pop("payload_attestation_digest", None)
    return raw


def _dispatch_material(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(row)
    raw.pop("dispatch_candidate_digest", None)
    return raw


def build_fresh_outbound_execution_authorization(
    bridge: Mapping[str, Any] | None,
    *,
    authorization_id: Any,
    decision: Any,
    mechanism: Any,
    owner_binding_digest: Any,
    owner_key_fingerprint: Any,
    signed_request_digest: Any,
    authorization_nonce_digest: Any,
    verified_owner_signature: bool,
    verified_active_trust_root: bool,
    persistent_nonce_replay_guard_verified: bool,
    nonce_single_use_claimed: bool,
    issued_at: Any,
    expires_at: Any,
    now: Any,
) -> dict[str, Any]:
    """Represent a fresh owner execution-intent verification."""
    bridge_row = dict(bridge or {})
    blockers: list[str] = []

    bridge_check = verify_outbound_dispatch_bridge(bridge_row)
    if bridge_check.get("valid") is not True:
        blockers.append("VALID_OUTBOUND_BRIDGE_REQUIRED")

    auth_id = _identity(authorization_id, 160)
    if not auth_id:
        blockers.append("AUTHORIZATION_ID_REQUIRED")

    decision_name = _clean(decision, 80).upper()
    if decision_name not in DECISIONS:
        blockers.append("EXECUTION_DECISION_INVALID")

    mechanism_name = _clean(mechanism, 100).upper()
    if mechanism_name != MECHANISM:
        blockers.append("EXECUTION_MECHANISM_INVALID")

    owner_digest = _sha256(owner_binding_digest)
    key_fingerprint = _sha256(owner_key_fingerprint)
    request_digest = _sha256(signed_request_digest)
    nonce_digest = _sha256(authorization_nonce_digest)
    if not owner_digest:
        blockers.append("OWNER_BINDING_DIGEST_REQUIRED")
    if not key_fingerprint:
        blockers.append("OWNER_KEY_FINGERPRINT_REQUIRED")
    if not request_digest:
        blockers.append("SIGNED_REQUEST_DIGEST_REQUIRED")
    if not nonce_digest:
        blockers.append("AUTHORIZATION_NONCE_DIGEST_REQUIRED")

    if owner_digest and owner_digest != _sha256(
        bridge_row.get("owner_binding_digest")
    ):
        blockers.append("OWNER_BINDING_BRIDGE_MISMATCH")
    if verified_owner_signature is not True:
        blockers.append("OWNER_EXECUTION_SIGNATURE_NOT_VERIFIED")
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
            blockers.append("AUTHORIZATION_EXPIRY_INVALID")
        if (expires - issued).total_seconds() > MAX_AUTHORIZATION_WINDOW_SECONDS:
            blockers.append("AUTHORIZATION_WINDOW_TOO_LONG")
        if current < issued:
            blockers.append("AUTHORIZATION_FROM_FUTURE")
        if current > expires:
            blockers.append("AUTHORIZATION_EXPIRED")
    except ValueError:
        issued = None
        expires = None
        current = None
        blockers.append("AUTHORIZATION_TIME_INVALID")

    blockers = list(dict.fromkeys(blockers))
    material = {
        "authorization_id": auth_id,
        "purpose": PURPOSE,
        "mechanism": mechanism_name,
        "decision": decision_name,
        "bridge_digest": _sha256(bridge_row.get("bridge_digest")),
        "subject_digest": _sha256(bridge_row.get("subject_digest")),
        "requested_action": _clean(
            bridge_row.get("requested_action"), 80
        ).upper(),
        "owner_binding_digest": owner_digest,
        "owner_key_fingerprint": key_fingerprint,
        "signed_request_digest": request_digest,
        "authorization_nonce_digest": nonce_digest,
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
    positive = not blockers and decision_name == "AUTHORIZE_OUTBOUND_EXECUTION"
    denied = not blockers and decision_name == "DENY_OUTBOUND_EXECUTION"

    return {
        "schema": AUTH_SCHEMA,
        "state": (
            "FRESH_EXECUTION_INTENT_VERIFIED"
            if positive
            else "EXECUTION_DENIED"
            if denied
            else "BLOCKED"
        ),
        "blockers": blockers,
        **material,
        "authorization_digest": _digest(material) if not blockers else "",
        "fresh_execution_intent_verified": positive,
        "execution_intent_denied": denied,
        "authorization_persisted": False,
        "persistence_attested": False,
        "authorization_consumed": False,
        "execution_command_generated": False,
        "dispatch_record_written": False,
        "execution_authorized": False,
        "provider_called": False,
        "network_called": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def build_authorization_persistence_attestation(
    authorization: Mapping[str, Any] | None,
    *,
    persisted_record_digest: Any,
    writer_attestation_digest: Any,
    persisted_at: Any,
    read_after_write_verified: bool,
    atomic_write_or_cas_verified: bool,
    writer_identity_verified: bool,
    now: Any,
) -> dict[str, Any]:
    """Represent external proof that fresh authorization was durably stored."""
    auth = dict(authorization or {})
    blockers: list[str] = []

    if auth.get("schema") != AUTH_SCHEMA:
        blockers.append("AUTHORIZATION_SCHEMA_MISMATCH")
    if auth.get("state") != "FRESH_EXECUTION_INTENT_VERIFIED":
        blockers.append("FRESH_EXECUTION_INTENT_REQUIRED")
    if auth.get("fresh_execution_intent_verified") is not True:
        blockers.append("FRESH_EXECUTION_INTENT_FLAG_REQUIRED")
    if auth.get("authorization_consumed") is not False:
        blockers.append("AUTHORIZATION_ALREADY_CONSUMED")

    auth_digest = _sha256(auth.get("authorization_digest"))
    record_digest = _sha256(persisted_record_digest)
    writer_digest = _sha256(writer_attestation_digest)
    if not auth_digest:
        blockers.append("AUTHORIZATION_DIGEST_REQUIRED")
    if not record_digest:
        blockers.append("PERSISTED_RECORD_DIGEST_REQUIRED")
    if not writer_digest:
        blockers.append("WRITER_ATTESTATION_DIGEST_REQUIRED")
    if read_after_write_verified is not True:
        blockers.append("READ_AFTER_WRITE_VERIFICATION_REQUIRED")
    if atomic_write_or_cas_verified is not True:
        blockers.append("ATOMIC_WRITE_OR_CAS_REQUIRED")
    if writer_identity_verified is not True:
        blockers.append("WRITER_IDENTITY_VERIFICATION_REQUIRED")

    try:
        persisted = _aware(persisted_at, "persisted_at")
        current = _aware(now, "now")
        issued = _aware(auth.get("issued_at"), "authorization_issued_at")
        expires = _aware(auth.get("expires_at"), "authorization_expires_at")
        if persisted < issued:
            blockers.append("AUTHORIZATION_PERSISTED_BEFORE_ISSUE")
        if persisted > expires:
            blockers.append("AUTHORIZATION_PERSISTED_AFTER_EXPIRY")
        if current < persisted:
            blockers.append("PERSISTENCE_ATTESTATION_FROM_FUTURE")
        if current > expires:
            blockers.append("AUTHORIZATION_EXPIRED_AFTER_PERSISTENCE")
    except ValueError:
        persisted = None
        blockers.append("AUTHORIZATION_PERSISTENCE_TIME_INVALID")

    blockers = list(dict.fromkeys(blockers))
    material = {
        "authorization_digest": auth_digest,
        "persisted_record_digest": record_digest,
        "writer_attestation_digest": writer_digest,
        "persisted_at": persisted.isoformat() if persisted else "",
        "read_after_write_verified": read_after_write_verified is True,
        "atomic_write_or_cas_verified": atomic_write_or_cas_verified is True,
        "writer_identity_verified": writer_identity_verified is True,
    }
    return {
        "schema": AUTH_PERSISTENCE_SCHEMA,
        "state": "PERSISTED_AUTHORIZATION_ATTESTED" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "persistence_attestation_digest": _digest(material) if not blockers else "",
        "authorization_persisted_by_this_module": False,
        "authorization_consumed": False,
        "dispatch_record_written": False,
        "provider_called": False,
        "network_called": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def build_sealed_payload_attestation(
    bridge: Mapping[str, Any] | None,
    authorization: Mapping[str, Any] | None,
    authorization_persistence: Mapping[str, Any] | None,
    *,
    payload_digest: Any,
    payload_schema_ref: Any,
    recipient_resolution_digest: Any,
    endpoint_reference_digest: Any,
    credential_reference_digest: Any,
    request_headers_policy_digest: Any,
    transport_policy_digest: Any,
    timeout_policy_digest: Any,
    verified_by_trusted_adapter: bool,
    checked_at: Any,
    now: Any,
) -> dict[str, Any]:
    """Bind opaque digests for a future wire payload without exposing secrets."""
    bridge_row = dict(bridge or {})
    auth = dict(authorization or {})
    persistence = dict(authorization_persistence or {})
    blockers: list[str] = []

    if verify_outbound_dispatch_bridge(bridge_row).get("valid") is not True:
        blockers.append("VALID_OUTBOUND_BRIDGE_REQUIRED")
    if auth.get("schema") != AUTH_SCHEMA:
        blockers.append("AUTHORIZATION_SCHEMA_MISMATCH")
    if auth.get("state") != "FRESH_EXECUTION_INTENT_VERIFIED":
        blockers.append("FRESH_EXECUTION_INTENT_REQUIRED")
    if auth.get("fresh_execution_intent_verified") is not True:
        blockers.append("FRESH_EXECUTION_INTENT_FLAG_REQUIRED")
    if auth.get("authorization_consumed") is not False:
        blockers.append("AUTHORIZATION_ALREADY_CONSUMED")
    if _sha256(auth.get("bridge_digest")) != _sha256(
        bridge_row.get("bridge_digest")
    ):
        blockers.append("AUTHORIZATION_BRIDGE_DIGEST_MISMATCH")

    if persistence.get("schema") != AUTH_PERSISTENCE_SCHEMA:
        blockers.append("AUTHORIZATION_PERSISTENCE_SCHEMA_MISMATCH")
    if persistence.get("state") != "PERSISTED_AUTHORIZATION_ATTESTED":
        blockers.append("PERSISTED_AUTHORIZATION_ATTESTATION_REQUIRED")
    if _sha256(persistence.get("authorization_digest")) != _sha256(
        auth.get("authorization_digest")
    ):
        blockers.append("PERSISTED_AUTHORIZATION_DIGEST_MISMATCH")
    if not _sha256(persistence.get("persistence_attestation_digest")):
        blockers.append("AUTHORIZATION_PERSISTENCE_ATTESTATION_DIGEST_REQUIRED")

    payload = _sha256(payload_digest)
    recipient = _sha256(recipient_resolution_digest)
    endpoint = _sha256(endpoint_reference_digest)
    credential = _sha256(credential_reference_digest)
    headers = _sha256(request_headers_policy_digest)
    transport = _sha256(transport_policy_digest)
    timeout = _sha256(timeout_policy_digest)
    schema_ref = _identity(payload_schema_ref, 320)

    for label, value in (
        ("PAYLOAD_DIGEST_REQUIRED", payload),
        ("RECIPIENT_RESOLUTION_DIGEST_REQUIRED", recipient),
        ("ENDPOINT_REFERENCE_DIGEST_REQUIRED", endpoint),
        ("CREDENTIAL_REFERENCE_DIGEST_REQUIRED", credential),
        ("REQUEST_HEADERS_POLICY_DIGEST_REQUIRED", headers),
        ("TRANSPORT_POLICY_DIGEST_REQUIRED", transport),
        ("TIMEOUT_POLICY_DIGEST_REQUIRED", timeout),
    ):
        if not value:
            blockers.append(label)
    if not schema_ref:
        blockers.append("PAYLOAD_SCHEMA_REF_REQUIRED")
    if verified_by_trusted_adapter is not True:
        blockers.append("TRUSTED_ADAPTER_PAYLOAD_VERIFICATION_REQUIRED")

    try:
        checked = _aware(checked_at, "checked_at")
        current = _aware(now, "now")
        age = (current - checked).total_seconds()
        if age < 0:
            blockers.append("PAYLOAD_ATTESTATION_FROM_FUTURE")
        if age > MAX_PAYLOAD_ATTESTATION_AGE_SECONDS:
            blockers.append("PAYLOAD_ATTESTATION_STALE")
        auth_expiry = _aware(auth.get("expires_at"), "authorization_expires_at")
        if current > auth_expiry:
            blockers.append("AUTHORIZATION_EXPIRED_BEFORE_PAYLOAD_ATTESTATION")
    except ValueError:
        checked = None
        current = None
        blockers.append("PAYLOAD_ATTESTATION_TIME_INVALID")

    blockers = list(dict.fromkeys(blockers))
    material = {
        "bridge_digest": _sha256(bridge_row.get("bridge_digest")),
        "authorization_digest": _sha256(auth.get("authorization_digest")),
        "authorization_persistence_attestation_digest": _sha256(
            persistence.get("persistence_attestation_digest")
        ),
        "subject_digest": _sha256(bridge_row.get("subject_digest")),
        "requested_action": _clean(
            bridge_row.get("requested_action"), 80
        ).upper(),
        "adapter_manifest_digest": _sha256(
            bridge_row.get("adapter_manifest_digest")
        ),
        "payload_digest": payload,
        "payload_schema_ref": schema_ref,
        "recipient_resolution_digest": recipient,
        "endpoint_reference_digest": endpoint,
        "credential_reference_digest": credential,
        "request_headers_policy_digest": headers,
        "transport_policy_digest": transport,
        "timeout_policy_digest": timeout,
        "verified_by_trusted_adapter": verified_by_trusted_adapter is True,
        "checked_at": checked.isoformat() if checked else "",
    }
    return {
        "schema": PAYLOAD_ATTESTATION_SCHEMA,
        "state": "SEALED_PAYLOAD_ATTESTED" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "payload_attestation_digest": _digest(material) if not blockers else "",
        "raw_recipient_included": False,
        "raw_endpoint_included": False,
        "raw_credential_included": False,
        "raw_payload_included": False,
        "authorization_consumed": False,
        "dispatch_record_written": False,
        "provider_called": False,
        "network_called": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def build_durable_dispatch_record_candidate(
    bridge: Mapping[str, Any] | None,
    authorization: Mapping[str, Any] | None,
    authorization_persistence: Mapping[str, Any] | None,
    payload_attestation: Mapping[str, Any] | None,
    *,
    execution_id: Any,
    task_id: Any,
    step_id: Any,
    lease_identity_digest: Any,
    observability_trace_id: Any,
    recorded_at: Any,
) -> dict[str, Any]:
    """Prepare exact durable-record material. Does not write the record."""
    bridge_row = dict(bridge or {})
    auth = dict(authorization or {})
    persistence = dict(authorization_persistence or {})
    payload = dict(payload_attestation or {})
    blockers: list[str] = []

    if verify_outbound_dispatch_bridge(bridge_row).get("valid") is not True:
        blockers.append("VALID_OUTBOUND_BRIDGE_REQUIRED")
    if auth.get("schema") != AUTH_SCHEMA:
        blockers.append("AUTHORIZATION_SCHEMA_MISMATCH")
    if auth.get("state") != "FRESH_EXECUTION_INTENT_VERIFIED":
        blockers.append("FRESH_EXECUTION_INTENT_REQUIRED")
    if auth.get("fresh_execution_intent_verified") is not True:
        blockers.append("FRESH_EXECUTION_INTENT_FLAG_REQUIRED")
    if auth.get("authorization_persisted") is not False:
        blockers.append("AUTHORIZATION_OBJECT_MUST_NOT_SELF_CLAIM_PERSISTENCE")
    if auth.get("authorization_consumed") is not False:
        blockers.append("AUTHORIZATION_ALREADY_CONSUMED")

    if persistence.get("schema") != AUTH_PERSISTENCE_SCHEMA:
        blockers.append("AUTHORIZATION_PERSISTENCE_SCHEMA_MISMATCH")
    if persistence.get("state") != "PERSISTED_AUTHORIZATION_ATTESTED":
        blockers.append("PERSISTED_AUTHORIZATION_ATTESTATION_REQUIRED")
    if _sha256(persistence.get("authorization_digest")) != _sha256(
        auth.get("authorization_digest")
    ):
        blockers.append("PERSISTED_AUTHORIZATION_DIGEST_MISMATCH")
    if persistence.get("authorization_consumed") is not False:
        blockers.append("PERSISTED_AUTHORIZATION_ALREADY_CONSUMED")

    if payload.get("schema") != PAYLOAD_ATTESTATION_SCHEMA:
        blockers.append("PAYLOAD_ATTESTATION_SCHEMA_MISMATCH")
    if payload.get("state") != "SEALED_PAYLOAD_ATTESTED":
        blockers.append("SEALED_PAYLOAD_ATTESTATION_REQUIRED")
    if payload.get("verified_by_trusted_adapter") is not True:
        blockers.append("TRUSTED_ADAPTER_PAYLOAD_VERIFICATION_REQUIRED")

    bridge_digest = _sha256(bridge_row.get("bridge_digest"))
    auth_digest = _sha256(auth.get("authorization_digest"))
    persistence_attestation_digest = _sha256(
        persistence.get("persistence_attestation_digest")
    )
    payload_attestation_digest = _sha256(
        payload.get("payload_attestation_digest")
    )
    if _sha256(auth.get("bridge_digest")) != bridge_digest:
        blockers.append("AUTHORIZATION_BRIDGE_DIGEST_MISMATCH")
    if _sha256(payload.get("bridge_digest")) != bridge_digest:
        blockers.append("PAYLOAD_BRIDGE_DIGEST_MISMATCH")
    if _sha256(payload.get("authorization_digest")) != auth_digest:
        blockers.append("PAYLOAD_AUTHORIZATION_DIGEST_MISMATCH")
    if _sha256(payload.get("authorization_persistence_attestation_digest")) != (
        persistence_attestation_digest
    ):
        blockers.append("PAYLOAD_AUTHORIZATION_PERSISTENCE_DIGEST_MISMATCH")
    if _sha256(payload.get("subject_digest")) != _sha256(
        bridge_row.get("subject_digest")
    ):
        blockers.append("PAYLOAD_SUBJECT_DIGEST_MISMATCH")
    if _sha256(payload.get("adapter_manifest_digest")) != _sha256(
        bridge_row.get("adapter_manifest_digest")
    ):
        blockers.append("PAYLOAD_ADAPTER_DIGEST_MISMATCH")

    exe = _identity(execution_id, 160)
    task = _identity(task_id, 160)
    step = _identity(step_id, 160)
    trace = _identity(observability_trace_id, 200)
    lease = _sha256(lease_identity_digest)
    for label, value in (
        ("EXECUTION_ID_REQUIRED", exe),
        ("TASK_ID_REQUIRED", task),
        ("STEP_ID_REQUIRED", step),
        ("OBSERVABILITY_TRACE_ID_REQUIRED", trace),
        ("LEASE_IDENTITY_DIGEST_REQUIRED", lease),
    ):
        if not value:
            blockers.append(label)

    try:
        recorded = _aware(recorded_at, "recorded_at")
        auth_expiry = _aware(auth.get("expires_at"), "authorization_expires_at")
        if recorded > auth_expiry:
            blockers.append("AUTHORIZATION_EXPIRED_BEFORE_DISPATCH_RECORD")
        checked = _aware(payload.get("checked_at"), "payload_checked_at")
        age = (recorded - checked).total_seconds()
        if age < 0:
            blockers.append("DISPATCH_RECORD_BEFORE_PAYLOAD_ATTESTATION")
        if age > MAX_PAYLOAD_ATTESTATION_AGE_SECONDS:
            blockers.append("PAYLOAD_ATTESTATION_STALE_AT_DISPATCH")
    except ValueError:
        recorded = None
        blockers.append("DISPATCH_RECORD_TIME_INVALID")

    blockers = list(dict.fromkeys(blockers))
    candidate: dict[str, Any] = {
        "schema": DISPATCH_SCHEMA,
        "state": (
            "READY_FOR_DURABLE_DISPATCH_RECORD_WRITE"
            if not blockers
            else "BLOCKED"
        ),
        "blockers": blockers,
        "mode": "EXTERNAL_EFFECT",
        "pre_record_state_required": "LEASED",
        "post_record_state": "DISPATCH_RECORDED",
        "execution_id": exe,
        "task_id": task,
        "step_id": step,
        "bridge_digest": bridge_digest,
        "authorization_digest": auth_digest,
        "authorization_persistence_attestation_digest": (
            persistence_attestation_digest
        ),
        "payload_attestation_digest": payload_attestation_digest,
        "subject_digest": _sha256(bridge_row.get("subject_digest")),
        "approval_packet_digest": _sha256(
            bridge_row.get("approval_packet_digest")
        ),
        "approval_evidence_digest": _sha256(
            bridge_row.get("approval_evidence_digest")
        ),
        "adapter_manifest_digest": _sha256(
            bridge_row.get("adapter_manifest_digest")
        ),
        "requested_action": _clean(
            bridge_row.get("requested_action"), 80
        ).upper(),
        "idempotency_key_digest": _sha256(
            bridge_row.get("idempotency_key_digest")
        ),
        "effect_key_digest": _sha256(bridge_row.get("effect_key_digest")),
        "payload_digest": _sha256(payload.get("payload_digest")),
        "recipient_resolution_digest": _sha256(
            payload.get("recipient_resolution_digest")
        ),
        "endpoint_reference_digest": _sha256(
            payload.get("endpoint_reference_digest")
        ),
        "credential_reference_digest": _sha256(
            payload.get("credential_reference_digest")
        ),
        "request_headers_policy_digest": _sha256(
            payload.get("request_headers_policy_digest")
        ),
        "transport_policy_digest": _sha256(
            payload.get("transport_policy_digest")
        ),
        "timeout_policy_digest": _sha256(
            payload.get("timeout_policy_digest")
        ),
        "lease_identity_digest": lease,
        "observability_trace_id": trace,
        "dispatch_recorded_at_candidate": (
            recorded.isoformat() if recorded else ""
        ),
        "post_record_crash_becomes_outcome_unknown": True,
        "post_record_timeout_becomes_outcome_unknown": True,
        "post_record_ambiguous_ack_becomes_outcome_unknown": True,
        "outcome_unknown_automatic_retry_allowed": False,
        "outcome_unknown_requires_explicit_reconciliation": True,
        "outcome_receipt_required": True,
        "authorization_persistence_attestation_required": True,
        "authorization_consumption_required_atomically_with_write": True,
        "durable_store_write_required": True,
        "dispatch_record_written": False,
        "authorization_consumed": False,
        "provider_call_allowed_after_this_module": False,
        "provider_called": False,
        "network_called": False,
        "message_sent": False,
        "contract_exported": False,
        "signature_requested": False,
        "external_action_executed": False,
        "executes_action": False,
        "dispatch_candidate_digest": "",
    }
    candidate["dispatch_candidate_digest"] = (
        _digest(_dispatch_material(candidate)) if not blockers else ""
    )
    return candidate


def verify_durable_dispatch_record_candidate(
    candidate: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw = dict(candidate or {})
    blockers: list[str] = []

    if raw.get("schema") != DISPATCH_SCHEMA:
        blockers.append("DISPATCH_SCHEMA_MISMATCH")
    if raw.get("state") != "READY_FOR_DURABLE_DISPATCH_RECORD_WRITE":
        blockers.append("DISPATCH_CANDIDATE_NOT_READY")

    supplied = _sha256(raw.get("dispatch_candidate_digest"))
    expected = _digest(_dispatch_material(raw))
    if not supplied or supplied != expected:
        blockers.append("DISPATCH_CANDIDATE_DIGEST_MISMATCH")

    for key in (
        "post_record_crash_becomes_outcome_unknown",
        "post_record_timeout_becomes_outcome_unknown",
        "post_record_ambiguous_ack_becomes_outcome_unknown",
        "outcome_unknown_requires_explicit_reconciliation",
        "outcome_receipt_required",
        "authorization_persistence_attestation_required",
        "authorization_consumption_required_atomically_with_write",
        "durable_store_write_required",
    ):
        if raw.get(key) is not True:
            blockers.append("DURABLE_GUARD_MISSING:" + key)

    for key in (
        "outcome_unknown_automatic_retry_allowed",
        "dispatch_record_written",
        "authorization_consumed",
        "provider_call_allowed_after_this_module",
        "provider_called",
        "network_called",
        "message_sent",
        "contract_exported",
        "signature_requested",
        "external_action_executed",
        "executes_action",
    ):
        if raw.get(key) is not False:
            blockers.append("DISPATCH_BOUNDARY_INVALID:" + key)

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": VERIFY_SCHEMA,
        "state": "VALID" if not blockers else "INVALID",
        "valid": not blockers,
        "blockers": blockers,
        "dispatch_candidate_digest": supplied,
        "executes_action": False,
    }


def outbound_execution_dispatch_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "fresh_execution_intent_required": True,
        "execution_mechanism": MECHANISM,
        "authorization_max_window_seconds": MAX_AUTHORIZATION_WINDOW_SECONDS,
        "persistent_nonce_replay_guard_required": True,
        "single_use_nonce_required": True,
        "authorization_must_match_exact_bridge_digest": True,
        "authorization_is_provider_call": False,
        "authorization_persistence_separate": True,
        "authorization_persistence_attestation_required": True,
        "sealed_payload_attestation_required": True,
        "sealed_payload_max_age_seconds": MAX_PAYLOAD_ATTESTATION_AGE_SECONDS,
        "raw_recipient_in_control_plane": False,
        "raw_endpoint_in_control_plane": False,
        "raw_credential_in_control_plane": False,
        "raw_payload_in_control_plane": False,
        "durable_dispatch_write_before_external_effect": True,
        "authorization_consumption_atomic_with_dispatch_write": True,
        "post_record_ambiguity_becomes_outcome_unknown": True,
        "outcome_unknown_automatic_retry_allowed": False,
        "outcome_unknown_requires_explicit_reconciliation": True,
        "outcome_receipt_required": True,
        "authorization_persisted": False,
        "authorization_consumed": False,
        "dispatch_record_written": False,
        "provider_called": False,
        "network_called": False,
        "message_sent": False,
        "contract_exported": False,
        "signature_requested": False,
        "worker_armed": False,
        "deploy_executed": False,
        "core_checkpoint_write": False,
        "external_action_executed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "AUTH_SCHEMA",
    "AUTH_PERSISTENCE_SCHEMA",
    "PAYLOAD_ATTESTATION_SCHEMA",
    "DISPATCH_SCHEMA",
    "VERIFY_SCHEMA",
    "POLICY_SCHEMA",
    "PURPOSE",
    "MECHANISM",
    "DECISIONS",
    "MAX_AUTHORIZATION_WINDOW_SECONDS",
    "MAX_PAYLOAD_ATTESTATION_AGE_SECONDS",
    "build_fresh_outbound_execution_authorization",
    "build_authorization_persistence_attestation",
    "build_sealed_payload_attestation",
    "build_durable_dispatch_record_candidate",
    "verify_durable_dispatch_record_candidate",
    "outbound_execution_dispatch_policy",
]
