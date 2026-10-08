"""AION Approval Decision + Outbound Dispatch Bridge V1.

Pure, non-executing boundary between an owner-approved draft and a future
outbound adapter.

This module does NOT:
- approve a draft;
- authenticate a human itself;
- send email or WhatsApp;
- resolve real recipients;
- sign/export a contract;
- select/load credentials;
- call a provider;
- open the network;
- write a durable dispatch record;
- consume an approval;
- mark execution authorized.

Security invariants:
1. exact approved subject digest must still match the current draft;
2. approval packet digest must match the human decision evidence;
3. owner identity/binding must match across packet and decision evidence;
4. approval must be fresh, authenticated and unconsumed;
5. provider capability is least-privilege and logical only;
6. any post-approval draft mutation blocks dispatch;
7. positive result means READY_FOR_EXECUTION_AUTHORIZATION_REVIEW only.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_contract_communication_draft_approval_v1 import (
    APPROVAL_PACKET_SCHEMA,
    COMMUNICATION_SCHEMA,
    CONTRACT_SCHEMA,
    verify_human_approval_packet,
)


SCHEMA = "ATLASQUANT_AION_APPROVAL_OUTBOUND_DISPATCH_BRIDGE_V1"
APPROVAL_EVIDENCE_SCHEMA = "ATLASQUANT_AION_HUMAN_APPROVAL_DECISION_EVIDENCE_V1"
ADAPTER_MANIFEST_SCHEMA = "ATLASQUANT_AION_OUTBOUND_ADAPTER_MANIFEST_V1"
BRIDGE_SCHEMA = "ATLASQUANT_AION_OUTBOUND_DISPATCH_BRIDGE_V1"
VERIFY_SCHEMA = "ATLASQUANT_AION_OUTBOUND_DISPATCH_BRIDGE_VERIFY_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_OUTBOUND_DISPATCH_POLICY_V1"

OUTBOUND_ACTIONS = (
    "SEND_EMAIL",
    "SEND_WHATSAPP",
    "EXPORT_CONTRACT_FOR_SIGNATURE_REVIEW",
)
ADAPTER_KINDS = (
    "EMAIL_PROVIDER",
    "WHATSAPP_PROVIDER",
    "CONTRACT_EXPORT_ADAPTER",
)
ACTION_TO_ADAPTER_KIND = {
    "SEND_EMAIL": "EMAIL_PROVIDER",
    "SEND_WHATSAPP": "WHATSAPP_PROVIDER",
    "EXPORT_CONTRACT_FOR_SIGNATURE_REVIEW": "CONTRACT_EXPORT_ADAPTER",
}
MAX_APPROVAL_AGE_SECONDS = 300
MAX_BRIDGE_WINDOW_SECONDS = 60

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,239}$")

_FORBIDDEN_KEYS = frozenset({
    "password",
    "passwd",
    "senha",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "secret",
    "client_secret",
    "private_key",
    "cookie",
    "authorization",
    "bearer",
    "credential",
    "smtp_password",
    "whatsapp_token",
    "gmail_token",
    "email_address",
    "phone_number",
    "endpoint_url",
    "url",
    "uri",
    "headers",
    "payload_raw",
    "raw_payload",
})


def _clean(value: Any, limit: int = 4000) -> str:
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


def _text_digest(value: Any) -> str:
    return "sha256:" + sha256(_clean(value, 20000).encode("utf-8")).hexdigest()


def _sha256(value: Any) -> str:
    token = _clean(value, 90)
    return token if _SHA256_RE.fullmatch(token) else ""


def _identity(value: Any, limit: int = 240) -> str:
    if type(value) is not str:
        return ""
    if not value or len(value) > limit or "\x00" in value:
        return ""
    if " ".join(value.split()) != value:
        return ""
    if not _ID_RE.fullmatch(value):
        return ""
    return value


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


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if _clean(key, 120).casefold() in _FORBIDDEN_KEYS:
                return True
            if _contains_forbidden(item):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_forbidden(item) for item in value)
    return False


def _communication_material(draft: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(draft)
    raw.pop("draft_digest", None)
    return raw


def _contract_material(draft: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(draft)
    raw.pop("contract_digest", None)
    return raw


def current_subject_digest(draft: Mapping[str, Any] | None) -> str:
    """Rebuild the exact draft digest instead of trusting its stored digest."""
    raw = dict(draft or {})
    if raw.get("schema") == COMMUNICATION_SCHEMA:
        return _digest(_communication_material(raw))
    if raw.get("schema") == CONTRACT_SCHEMA:
        return _digest(_contract_material(raw))
    return ""


def _stored_subject_digest(draft: Mapping[str, Any]) -> str:
    if draft.get("schema") == COMMUNICATION_SCHEMA:
        return _sha256(draft.get("draft_digest"))
    if draft.get("schema") == CONTRACT_SCHEMA:
        return _sha256(draft.get("contract_digest"))
    return ""


def _expected_action(draft: Mapping[str, Any]) -> str:
    if draft.get("schema") == COMMUNICATION_SCHEMA:
        channel = _clean(draft.get("channel"), 40).upper()
        if channel == "EMAIL":
            return "SEND_EMAIL"
        if channel == "WHATSAPP":
            return "SEND_WHATSAPP"
    elif draft.get("schema") == CONTRACT_SCHEMA:
        return "EXPORT_CONTRACT_FOR_SIGNATURE_REVIEW"
    return ""


def _subject_kind(draft: Mapping[str, Any]) -> str:
    if draft.get("schema") == COMMUNICATION_SCHEMA:
        return "COMMUNICATION"
    if draft.get("schema") == CONTRACT_SCHEMA:
        return "CONTRACT"
    return ""


def build_approval_decision_evidence(
    *,
    approval_packet: Mapping[str, Any] | None,
    approval_id: Any,
    approval_version: Any,
    decision: Any,
    human_principal_ref: Any,
    human_principal_binding_digest: Any,
    owner_binding_digest: Any,
    authenticated_receipt_digest: Any,
    approval_packet_digest: Any,
    subject_digest: Any,
    requested_action: Any,
    decided_at: Any,
    expires_at: Any,
    authenticated_human_receipt_verified: bool,
    owner_session_or_signature_verified: bool,
    approval_consumed: bool = False,
) -> dict[str, Any]:
    """Represent evidence emitted by a future trusted ApprovalGate adapter."""
    packet = dict(approval_packet or {})
    blockers: list[str] = []

    packet_check = verify_human_approval_packet(packet)
    if packet_check.get("valid") is not True:
        blockers.append("VALID_APPROVAL_PACKET_REQUIRED")

    aid = _identity(approval_id, 160)
    if not aid:
        blockers.append("APPROVAL_ID_REQUIRED")

    try:
        version = int(approval_version)
        if version < 2:
            blockers.append("APPROVAL_VERSION_MUST_REFLECT_DECISION")
    except Exception:
        version = 0
        blockers.append("APPROVAL_VERSION_INVALID")

    decision_name = _clean(decision, 30).upper()
    if decision_name not in {"APPROVED", "REJECTED"}:
        blockers.append("APPROVAL_DECISION_INVALID")

    principal = _identity(human_principal_ref, 240)
    principal_digest = _sha256(human_principal_binding_digest)
    owner_digest = _sha256(owner_binding_digest)
    receipt_digest = _sha256(authenticated_receipt_digest)
    packet_digest = _sha256(approval_packet_digest)
    approved_subject_digest = _sha256(subject_digest)
    action_name = _clean(requested_action, 80).upper()

    if not principal:
        blockers.append("HUMAN_PRINCIPAL_REF_REQUIRED")
    if not principal_digest:
        blockers.append("HUMAN_PRINCIPAL_BINDING_DIGEST_REQUIRED")
    if not owner_digest:
        blockers.append("OWNER_BINDING_DIGEST_REQUIRED")
    if not receipt_digest:
        blockers.append("AUTHENTICATED_RECEIPT_DIGEST_REQUIRED")
    if not packet_digest:
        blockers.append("APPROVAL_PACKET_DIGEST_REQUIRED")
    if not approved_subject_digest:
        blockers.append("SUBJECT_DIGEST_REQUIRED")
    if action_name not in OUTBOUND_ACTIONS:
        blockers.append("REQUESTED_ACTION_INVALID")

    if packet_digest and packet_digest != _sha256(
        packet.get("approval_packet_digest")
    ):
        blockers.append("APPROVAL_PACKET_DIGEST_MISMATCH")
    if approved_subject_digest and approved_subject_digest != _sha256(
        packet.get("subject_digest")
    ):
        blockers.append("APPROVED_SUBJECT_DIGEST_MISMATCH")
    if owner_digest and owner_digest != _sha256(
        packet.get("owner_binding_digest")
    ):
        blockers.append("OWNER_BINDING_MISMATCH")
    if action_name and action_name != _clean(
        packet.get("requested_action"), 80
    ).upper():
        blockers.append("APPROVAL_ACTION_MISMATCH")

    if authenticated_human_receipt_verified is not True:
        blockers.append("AUTHENTICATED_HUMAN_RECEIPT_REQUIRED")
    if owner_session_or_signature_verified is not True:
        blockers.append("OWNER_SESSION_OR_SIGNATURE_VERIFICATION_REQUIRED")

    try:
        decided = _aware(decided_at, "decided_at")
        expires = _aware(expires_at, "expires_at")
        if expires <= decided:
            blockers.append("APPROVAL_EXPIRY_INVALID")
        window = (expires - decided).total_seconds()
        if window > MAX_APPROVAL_AGE_SECONDS:
            blockers.append("APPROVAL_WINDOW_TOO_LONG")
    except ValueError:
        decided = None
        expires = None
        blockers.append("APPROVAL_TIME_INVALID")

    blockers = list(dict.fromkeys(blockers))
    material = {
        "approval_id": aid,
        "approval_version": version,
        "decision": decision_name,
        "human_principal_ref": principal,
        "human_principal_binding_digest": principal_digest,
        "owner_binding_digest": owner_digest,
        "authenticated_receipt_digest": receipt_digest,
        "approval_packet_digest": packet_digest,
        "subject_digest": approved_subject_digest,
        "requested_action": action_name,
        "decided_at": decided.isoformat() if decided else "",
        "expires_at": expires.isoformat() if expires else "",
        "authenticated_human_receipt_verified": (
            authenticated_human_receipt_verified is True
        ),
        "owner_session_or_signature_verified": (
            owner_session_or_signature_verified is True
        ),
        "approval_consumed": bool(approval_consumed),
    }
    return {
        "schema": APPROVAL_EVIDENCE_SCHEMA,
        "state": (
            "APPROVED_EVIDENCE_READY"
            if not blockers and decision_name == "APPROVED"
            else "REJECTED_EVIDENCE_READY"
            if not blockers and decision_name == "REJECTED"
            else "BLOCKED"
        ),
        "blockers": blockers,
        **material,
        "evidence_digest": _digest(material) if not blockers else "",
        "approval_is_execution_authorization": False,
        "execution_authorized": False,
        "approval_consumed_by_this_module": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def build_outbound_adapter_manifest(
    *,
    adapter_id: Any,
    adapter_kind: Any,
    version: Any,
    binary_or_build_digest: Any,
    logical_capabilities: Any,
    signed_manifest_verified: bool,
) -> dict[str, Any]:
    """Describe a future adapter without endpoint/credential material."""
    blockers: list[str] = []
    aid = _identity(adapter_id, 160)
    kind = _clean(adapter_kind, 80).upper()
    ver = _identity(version, 80)
    build_digest = _sha256(binary_or_build_digest)

    if not aid:
        blockers.append("ADAPTER_ID_REQUIRED")
    if kind not in ADAPTER_KINDS:
        blockers.append("ADAPTER_KIND_INVALID")
    if not ver:
        blockers.append("ADAPTER_VERSION_REQUIRED")
    if not build_digest:
        blockers.append("ADAPTER_BUILD_DIGEST_REQUIRED")

    caps: list[str] = []
    if isinstance(logical_capabilities, (list, tuple)):
        for raw in logical_capabilities:
            cap = _clean(raw, 80).upper()
            if cap in OUTBOUND_ACTIONS and cap not in caps:
                caps.append(cap)
    if not caps:
        blockers.append("ADAPTER_LOGICAL_CAPABILITY_REQUIRED")
    if signed_manifest_verified is not True:
        blockers.append("SIGNED_ADAPTER_MANIFEST_REQUIRED")

    blockers = list(dict.fromkeys(blockers))
    material = {
        "adapter_id": aid,
        "adapter_kind": kind,
        "version": ver,
        "binary_or_build_digest": build_digest,
        "logical_capabilities": caps,
        "signed_manifest_verified": signed_manifest_verified is True,
    }
    return {
        "schema": ADAPTER_MANIFEST_SCHEMA,
        "state": "READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "manifest_digest": _digest(material) if not blockers else "",
        "endpoint_resolved": False,
        "credentials_loaded": False,
        "provider_selected_dynamically": False,
        "network_called": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def build_outbound_dispatch_bridge(
    draft: Mapping[str, Any] | None,
    approval_packet: Mapping[str, Any] | None,
    approval_evidence: Mapping[str, Any] | None,
    adapter_manifest: Mapping[str, Any] | None,
    *,
    bridge_id: Any,
    idempotency_key_digest: Any,
    effect_key_digest: Any,
    now: Any,
) -> dict[str, Any]:
    """Bind exact approved draft to exact adapter capability. Never dispatches."""
    d = dict(draft or {})
    packet = dict(approval_packet or {})
    evidence = dict(approval_evidence or {})
    adapter = dict(adapter_manifest or {})
    blockers: list[str] = []

    subject_kind = _subject_kind(d)
    action = _expected_action(d)
    stored_digest = _stored_subject_digest(d)
    rebuilt_digest = current_subject_digest(d)

    if not subject_kind or not action:
        blockers.append("SUPPORTED_DRAFT_REQUIRED")
    if d.get("state") != "DRAFT_READY" or d.get("blockers"):
        blockers.append("READY_DRAFT_REQUIRED")
    if not stored_digest or not rebuilt_digest:
        blockers.append("DRAFT_DIGEST_REQUIRED")
    elif stored_digest != rebuilt_digest:
        blockers.append("DRAFT_MUTATED_AFTER_DIGEST")

    packet_check = verify_human_approval_packet(packet)
    if packet_check.get("valid") is not True:
        blockers.append("VALID_APPROVAL_PACKET_REQUIRED")
    if _clean(packet.get("subject_type"), 40).upper() != subject_kind:
        blockers.append("APPROVAL_PACKET_SUBJECT_TYPE_MISMATCH")
    if _clean(packet.get("requested_action"), 80).upper() != action:
        blockers.append("APPROVAL_PACKET_ACTION_MISMATCH")
    if _sha256(packet.get("subject_digest")) != rebuilt_digest:
        blockers.append("APPROVAL_PACKET_SUBJECT_DIGEST_MISMATCH")

    if evidence.get("schema") != APPROVAL_EVIDENCE_SCHEMA:
        blockers.append("APPROVAL_EVIDENCE_SCHEMA_MISMATCH")
    if evidence.get("state") != "APPROVED_EVIDENCE_READY":
        blockers.append("APPROVED_DECISION_EVIDENCE_REQUIRED")
    if evidence.get("decision") != "APPROVED":
        blockers.append("APPROVAL_DECISION_MUST_BE_APPROVED")
    if evidence.get("authenticated_human_receipt_verified") is not True:
        blockers.append("HUMAN_RECEIPT_NOT_VERIFIED")
    if evidence.get("owner_session_or_signature_verified") is not True:
        blockers.append("OWNER_IDENTITY_NOT_VERIFIED")
    if evidence.get("approval_consumed") is not False:
        blockers.append("APPROVAL_ALREADY_CONSUMED")
    if evidence.get("approval_is_execution_authorization") is not False:
        blockers.append("APPROVAL_EXECUTION_BOUNDARY_INVALID")
    if evidence.get("execution_authorized") is not False:
        blockers.append("APPROVAL_MUST_NOT_PREAUTHORIZE_EXECUTION")

    if _sha256(evidence.get("subject_digest")) != rebuilt_digest:
        blockers.append("APPROVAL_EVIDENCE_SUBJECT_DIGEST_MISMATCH")
    if _sha256(evidence.get("approval_packet_digest")) != _sha256(
        packet.get("approval_packet_digest")
    ):
        blockers.append("APPROVAL_EVIDENCE_PACKET_DIGEST_MISMATCH")
    if _sha256(evidence.get("owner_binding_digest")) != _sha256(
        packet.get("owner_binding_digest")
    ):
        blockers.append("APPROVAL_OWNER_BINDING_MISMATCH")
    if _clean(evidence.get("requested_action"), 80).upper() != action:
        blockers.append("APPROVAL_EVIDENCE_ACTION_MISMATCH")

    try:
        current = _aware(now, "now")
        decided = _aware(evidence.get("decided_at"), "decided_at")
        expires = _aware(evidence.get("expires_at"), "expires_at")
        if current < decided:
            blockers.append("APPROVAL_DECISION_FROM_FUTURE")
        if current > expires:
            blockers.append("APPROVAL_EXPIRED")
        if (current - decided).total_seconds() > MAX_APPROVAL_AGE_SECONDS:
            blockers.append("APPROVAL_TOO_OLD")
    except ValueError:
        current = None
        blockers.append("APPROVAL_TIME_INVALID")

    if adapter.get("schema") != ADAPTER_MANIFEST_SCHEMA:
        blockers.append("ADAPTER_MANIFEST_SCHEMA_MISMATCH")
    if adapter.get("state") != "READY" or adapter.get("blockers"):
        blockers.append("READY_ADAPTER_MANIFEST_REQUIRED")
    expected_kind = ACTION_TO_ADAPTER_KIND.get(action)
    if adapter.get("adapter_kind") != expected_kind:
        blockers.append("ADAPTER_KIND_ACTION_MISMATCH")
    if action not in list(adapter.get("logical_capabilities") or []):
        blockers.append("ADAPTER_CAPABILITY_MISSING")
    if adapter.get("signed_manifest_verified") is not True:
        blockers.append("ADAPTER_MANIFEST_NOT_VERIFIED")

    bridge = _identity(bridge_id, 160)
    idem = _sha256(idempotency_key_digest)
    effect = _sha256(effect_key_digest)
    if not bridge:
        blockers.append("BRIDGE_ID_REQUIRED")
    if not idem:
        blockers.append("IDEMPOTENCY_KEY_DIGEST_REQUIRED")
    if not effect:
        blockers.append("EFFECT_KEY_DIGEST_REQUIRED")
    if idem and effect and idem == effect:
        blockers.append("IDEMPOTENCY_AND_EFFECT_KEYS_MUST_DIFFER")

    if _contains_forbidden(d) or _contains_forbidden(packet) or _contains_forbidden(
        evidence
    ) or _contains_forbidden(adapter):
        blockers.append("FORBIDDEN_SECRET_OR_ENDPOINT_MATERIAL")

    blockers = list(dict.fromkeys(blockers))
    material = {
        "bridge_id": bridge,
        "subject_type": subject_kind,
        "subject_digest": rebuilt_digest,
        "approval_packet_digest": _sha256(packet.get("approval_packet_digest")),
        "approval_evidence_digest": _sha256(evidence.get("evidence_digest")),
        "approval_id": _clean(evidence.get("approval_id"), 160),
        "owner_binding_digest": _sha256(evidence.get("owner_binding_digest")),
        "authenticated_receipt_digest": _sha256(
            evidence.get("authenticated_receipt_digest")
        ),
        "requested_action": action,
        "adapter_id": _clean(adapter.get("adapter_id"), 160),
        "adapter_kind": _clean(adapter.get("adapter_kind"), 80),
        "adapter_manifest_digest": _sha256(adapter.get("manifest_digest")),
        "idempotency_key_digest": idem,
        "effect_key_digest": effect,
        "checked_at": current.isoformat() if current else "",
    }
    bridge_digest = _digest(material) if not blockers else ""

    return {
        "schema": BRIDGE_SCHEMA,
        "state": (
            "READY_FOR_EXECUTION_AUTHORIZATION_REVIEW"
            if not blockers
            else "BLOCKED"
        ),
        "blockers": blockers,
        **material,
        "bridge_digest": bridge_digest,
        "approved_subject_immutable": not blockers,
        "draft_rebuild_match": bool(not blockers and stored_digest == rebuilt_digest),
        "fresh_approval_verified": not blockers,
        "adapter_capability_verified": not blockers,
        "single_use_execution_authorization_still_required": True,
        "durable_dispatch_record_still_required": True,
        "pre_dispatch_revalidation_still_required": True,
        "outcome_receipt_still_required": True,
        "approval_consumed": False,
        "execution_authorization_issued": False,
        "execution_authorized": False,
        "dispatch_record_written": False,
        "recipient_resolved": False,
        "endpoint_resolved": False,
        "credentials_loaded": False,
        "payload_materialized": False,
        "provider_called": False,
        "network_called": False,
        "message_sent": False,
        "contract_exported": False,
        "signature_requested": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def verify_outbound_dispatch_bridge(
    bridge: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw = dict(bridge or {})
    blockers: list[str] = []

    if raw.get("schema") != BRIDGE_SCHEMA:
        blockers.append("BRIDGE_SCHEMA_MISMATCH")
    if raw.get("state") != "READY_FOR_EXECUTION_AUTHORIZATION_REVIEW":
        blockers.append("BRIDGE_NOT_READY")

    material = {
        key: raw.get(key)
        for key in (
            "bridge_id",
            "subject_type",
            "subject_digest",
            "approval_packet_digest",
            "approval_evidence_digest",
            "approval_id",
            "owner_binding_digest",
            "authenticated_receipt_digest",
            "requested_action",
            "adapter_id",
            "adapter_kind",
            "adapter_manifest_digest",
            "idempotency_key_digest",
            "effect_key_digest",
            "checked_at",
        )
    }
    expected = _digest(material)
    supplied = _sha256(raw.get("bridge_digest"))
    if not supplied or supplied != expected:
        blockers.append("BRIDGE_DIGEST_MISMATCH")

    required_true = (
        "approved_subject_immutable",
        "draft_rebuild_match",
        "fresh_approval_verified",
        "adapter_capability_verified",
        "single_use_execution_authorization_still_required",
        "durable_dispatch_record_still_required",
        "pre_dispatch_revalidation_still_required",
        "outcome_receipt_still_required",
    )
    for key in required_true:
        if raw.get(key) is not True:
            blockers.append("REQUIRED_BRIDGE_GUARD_MISSING:" + key)

    required_false = (
        "approval_consumed",
        "execution_authorization_issued",
        "execution_authorized",
        "dispatch_record_written",
        "recipient_resolved",
        "endpoint_resolved",
        "credentials_loaded",
        "payload_materialized",
        "provider_called",
        "network_called",
        "message_sent",
        "contract_exported",
        "signature_requested",
        "external_action_executed",
        "executes_action",
    )
    for key in required_false:
        if raw.get(key) is not False:
            blockers.append("BRIDGE_EXECUTION_BOUNDARY_INVALID:" + key)

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": VERIFY_SCHEMA,
        "state": "VALID" if not blockers else "INVALID",
        "valid": not blockers,
        "blockers": blockers,
        "bridge_digest": supplied,
        "executes_action": False,
    }


def outbound_dispatch_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "exact_approved_subject_digest_required": True,
        "post_approval_mutation_blocks": True,
        "authenticated_human_receipt_required": True,
        "owner_session_or_signature_verification_required": True,
        "approval_freshness_required": True,
        "approval_single_use_required": True,
        "approval_is_execution_authorization": False,
        "adapter_signed_manifest_required": True,
        "adapter_exact_action_capability_required": True,
        "dynamic_provider_switch_after_approval": False,
        "raw_recipient_in_control_plane": False,
        "endpoint_in_control_plane": False,
        "credential_material_in_control_plane": False,
        "idempotency_key_digest_required": True,
        "effect_key_digest_required": True,
        "fresh_execution_authorization_still_required": True,
        "durable_dispatch_record_still_required": True,
        "pre_dispatch_revalidation_still_required": True,
        "outcome_receipt_still_required": True,
        "approval_consumed": False,
        "execution_authorization_issued": False,
        "execution_authorized": False,
        "dispatch_record_written": False,
        "recipient_resolved": False,
        "endpoint_resolved": False,
        "credentials_loaded": False,
        "payload_materialized": False,
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
    "APPROVAL_EVIDENCE_SCHEMA",
    "ADAPTER_MANIFEST_SCHEMA",
    "BRIDGE_SCHEMA",
    "VERIFY_SCHEMA",
    "POLICY_SCHEMA",
    "OUTBOUND_ACTIONS",
    "ADAPTER_KINDS",
    "ACTION_TO_ADAPTER_KIND",
    "MAX_APPROVAL_AGE_SECONDS",
    "MAX_BRIDGE_WINDOW_SECONDS",
    "current_subject_digest",
    "build_approval_decision_evidence",
    "build_outbound_adapter_manifest",
    "build_outbound_dispatch_bridge",
    "verify_outbound_dispatch_bridge",
    "outbound_dispatch_policy",
]
