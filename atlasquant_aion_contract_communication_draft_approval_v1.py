"""AION Contract + Communication Draft & Approval V1.

Pure drafting/approval-packet contracts for owner-reviewed contracts, email and
WhatsApp communication.

This module does NOT:
- sign or finalize a legal contract;
- resolve a real email address or phone number;
- send email or WhatsApp;
- call Gmail/WhatsApp/provider/network APIs;
- approve its own draft;
- convert APPROVED into execution authority;
- persist CRM/customer records;
- write memory/checkpoints;
- deploy.

Design rule:
DRAFT_READY != APPROVED != EXECUTION_AUTHORIZED != SENT/SIGNED.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from atlasquant_aion_advisor_decision_support_v1 import (
    ASSESSMENT_SCHEMA as ADVISOR_ASSESSMENT_SCHEMA,
    verify_advisory_assessment,
)


SCHEMA = "ATLASQUANT_AION_CONTRACT_COMMUNICATION_DRAFT_APPROVAL_V1"
CONTRACT_SCHEMA = "ATLASQUANT_AION_CONTRACT_DRAFT_V1"
COMMUNICATION_SCHEMA = "ATLASQUANT_AION_COMMUNICATION_DRAFT_V1"
APPROVAL_PACKET_SCHEMA = "ATLASQUANT_AION_DRAFT_APPROVAL_PACKET_V1"
VERIFY_SCHEMA = "ATLASQUANT_AION_DRAFT_APPROVAL_PACKET_VERIFY_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_CONTRACT_COMMUNICATION_POLICY_V1"

CHANNELS = ("EMAIL", "WHATSAPP")
APPROVAL_ACTIONS = (
    "SEND_EMAIL",
    "SEND_WHATSAPP",
    "EXPORT_CONTRACT_FOR_SIGNATURE_REVIEW",
)
CLAUSE_SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
CLAUSE_STATES = ("UNCHANGED", "PROPOSED", "REVISED")

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ALLOWED_RECIPIENT_PREFIXES = (
    "contact://",
    "crm://",
    "recipient://",
    "tenant-contact://",
)
_FORBIDDEN_METADATA_KEYS = frozenset({
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
    "smtp_password",
    "whatsapp_token",
    "gmail_token",
    "phone_number",
    "email_address",
})


def _clean(value: Any, limit: int = 5000) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _identity(value: Any, limit: int = 320) -> str:
    if type(value) is not str:
        return ""
    if not value or len(value) > limit or "\x00" in value:
        return ""
    if " ".join(value.split()) != value:
        return ""
    return value


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


def _refs(value: Any, *, limit: int = 80) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in list(value)[: limit * 2]:
        token = _identity(raw, 400)
        if token and token not in out:
            out.append(token)
        if len(out) >= limit:
            break
    return out


def _contains_forbidden_metadata(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = _clean(key, 120).casefold()
            if normalized in _FORBIDDEN_METADATA_KEYS:
                return True
            if _contains_forbidden_metadata(item):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_forbidden_metadata(item) for item in value)
    return False


def _recipient_ref(value: Any) -> str:
    ref = _identity(value, 320)
    if not ref:
        return ""
    if not any(ref.startswith(prefix) for prefix in _ALLOWED_RECIPIENT_PREFIXES):
        return ""
    if "@" in ref:
        return ""
    return ref


def _verify_advisor(
    advisor_assessment: Mapping[str, Any] | None,
) -> tuple[str, list[str], list[str]]:
    if not advisor_assessment:
        return "", [], []

    raw = dict(advisor_assessment)
    blockers: list[str] = []
    risk_ids: list[str] = []
    if raw.get("schema") != ADVISOR_ASSESSMENT_SCHEMA:
        blockers.append("ADVISOR_ASSESSMENT_SCHEMA_MISMATCH")
        return "", blockers, risk_ids

    verified = verify_advisory_assessment(raw)
    if verified.get("valid") is not True:
        blockers.append("ADVISOR_ASSESSMENT_INVALID")
        return "", blockers, risk_ids
    if raw.get("state") not in {
        "READY_FOR_HUMAN_REVIEW",
        "RISK_REVIEW_REQUIRED",
    }:
        blockers.append("ADVISOR_ASSESSMENT_NOT_REVIEWABLE")
        return "", blockers, risk_ids

    digest = _sha256(raw.get("assessment_digest"))
    if not digest:
        blockers.append("ADVISOR_ASSESSMENT_DIGEST_REQUIRED")

    for risk in list(raw.get("risks") or []):
        if not isinstance(risk, Mapping):
            continue
        rid = _identity(risk.get("risk_id"), 120)
        if rid and rid not in risk_ids:
            risk_ids.append(rid)
    return digest, blockers, risk_ids


def _contract_material(contract: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(contract)
    raw.pop("contract_digest", None)
    return raw


def _communication_material(draft: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(draft)
    raw.pop("draft_digest", None)
    return raw


def _approval_material(packet: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(packet)
    raw.pop("approval_packet_digest", None)
    return raw


def build_contract_draft(
    *,
    contract_id: Any,
    title: Any,
    party_refs: Sequence[Any] | None,
    clauses: Sequence[Mapping[str, Any]] | None,
    source_refs: Sequence[Any] | None,
    advisor_assessment: Mapping[str, Any] | None = None,
    jurisdiction_ref: Any = "",
    version_label: Any = "DRAFT_V1",
) -> dict[str, Any]:
    """Build a non-final contract draft for owner/professional review."""
    blockers: list[str] = []

    cid = _identity(contract_id, 160)
    title_text = _clean(title, 320)
    parties = _refs(party_refs, limit=20)
    sources = _refs(source_refs, limit=80)
    jurisdiction = _identity(jurisdiction_ref, 320)
    version = _identity(version_label, 120)

    if not cid:
        blockers.append("CONTRACT_ID_REQUIRED")
    if not title_text:
        blockers.append("CONTRACT_TITLE_REQUIRED")
    if len(parties) < 2:
        blockers.append("AT_LEAST_TWO_PARTY_REFS_REQUIRED")
    if not sources:
        blockers.append("CONTRACT_SOURCE_REFS_REQUIRED")
    if not version:
        blockers.append("VERSION_LABEL_REQUIRED")

    advisor_digest, advisor_blockers, advisor_risk_ids = _verify_advisor(
        advisor_assessment
    )
    blockers.extend(advisor_blockers)

    clause_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(list(clauses or []), start=1):
        if not isinstance(raw, Mapping):
            blockers.append(f"CLAUSE_INVALID:{index}")
            continue

        clause_id = _identity(raw.get("clause_id"), 120)
        heading = _clean(raw.get("heading"), 240)
        body = _clean(raw.get("body"), 10000)
        summary = _clean(raw.get("summary"), 1600)
        source_ref = _identity(raw.get("source_ref"), 400)
        state = _clean(raw.get("state") or "PROPOSED", 40).upper()
        severity = _clean(raw.get("risk_severity") or "LOW", 40).upper()
        risk_refs = _refs(raw.get("advisor_risk_refs"), limit=20)

        if not clause_id:
            blockers.append(f"CLAUSE_ID_REQUIRED:{index}")
        elif clause_id in seen:
            blockers.append(f"DUPLICATE_CLAUSE_ID:{clause_id}")
        else:
            seen.add(clause_id)
        if not heading:
            blockers.append(f"CLAUSE_HEADING_REQUIRED:{index}")
        if not body:
            blockers.append(f"CLAUSE_BODY_REQUIRED:{index}")
        if not summary:
            blockers.append(f"CLAUSE_SUMMARY_REQUIRED:{index}")
        if not source_ref:
            blockers.append(f"CLAUSE_SOURCE_REF_REQUIRED:{index}")
        if state not in CLAUSE_STATES:
            blockers.append(f"CLAUSE_STATE_INVALID:{clause_id or index}")
        if severity not in CLAUSE_SEVERITIES:
            blockers.append(f"CLAUSE_RISK_SEVERITY_INVALID:{clause_id or index}")
        if severity in {"HIGH", "CRITICAL"}:
            if not advisor_digest:
                blockers.append(
                    f"HIGH_RISK_CLAUSE_REQUIRES_ADVISOR:{clause_id or index}"
                )
            if not risk_refs:
                blockers.append(
                    f"HIGH_RISK_CLAUSE_REQUIRES_RISK_REF:{clause_id or index}"
                )
            unknown_refs = [rid for rid in risk_refs if rid not in advisor_risk_ids]
            if unknown_refs:
                blockers.append(
                    f"CLAUSE_ADVISOR_RISK_REF_UNKNOWN:{clause_id or index}"
                )

        clause_rows.append(
            {
                "clause_id": clause_id,
                "heading": heading,
                "body": body,
                "body_digest": _text_digest(body),
                "summary": summary,
                "source_ref": source_ref,
                "state": state,
                "risk_severity": severity,
                "advisor_risk_refs": risk_refs,
                "legal_conclusion": False,
            }
        )

    if not clause_rows:
        blockers.append("CONTRACT_CLAUSES_REQUIRED")

    if _contains_forbidden_metadata(
        {
            "party_refs": parties,
            "source_refs": sources,
            "jurisdiction_ref": jurisdiction,
        }
    ):
        blockers.append("FORBIDDEN_SECRET_METADATA")

    blockers = list(dict.fromkeys(blockers))
    contract: dict[str, Any] = {
        "schema": CONTRACT_SCHEMA,
        "state": "DRAFT_READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        "contract_id": cid,
        "title": title_text,
        "version_label": version,
        "party_refs": parties,
        "source_refs": sources,
        "jurisdiction_ref": jurisdiction,
        "clauses": clause_rows,
        "clause_count": len(clause_rows),
        "advisor_assessment_digest": advisor_digest,
        "legal_review_required": True,
        "professional_review_required_for_high_risk": True,
        "contract_is_final_legal_document": False,
        "legal_advice_issued": False,
        "binding_commitment_created": False,
        "contract_signed": False,
        "signature_requested": False,
        "signature_collected": False,
        "publication_ready": False,
        "customer_sent": False,
        "provider_called": False,
        "network_called": False,
        "crm_written": False,
        "memory_written": False,
        "checkpoint_written": False,
        "external_action_executed": False,
        "executes_action": False,
        "contract_digest": "",
    }
    contract["contract_digest"] = _digest(_contract_material(contract))
    return contract


def build_communication_draft(
    *,
    channel: Any,
    recipient_ref: Any,
    body: Any,
    subject: Any = "",
    attachment_refs: Sequence[Any] | None = None,
    related_contract_digest: Any = "",
    related_proposal_digest: Any = "",
    conversation_ref: Any = "",
) -> dict[str, Any]:
    """Build email/WhatsApp content using logical recipient refs only."""
    blockers: list[str] = []

    channel_name = _clean(channel, 40).upper()
    if channel_name not in CHANNELS:
        blockers.append("COMMUNICATION_CHANNEL_INVALID")

    recipient = _recipient_ref(recipient_ref)
    if not recipient:
        blockers.append("LOGICAL_RECIPIENT_REF_REQUIRED")

    body_text = _clean(body, 8000)
    subject_text = _clean(subject, 500)
    if not body_text:
        blockers.append("MESSAGE_BODY_REQUIRED")
    if channel_name == "EMAIL" and not subject_text:
        blockers.append("EMAIL_SUBJECT_REQUIRED")
    if channel_name == "WHATSAPP":
        subject_text = ""

    attachments = _refs(attachment_refs, limit=20)
    contract_digest = (
        _sha256(related_contract_digest)
        if related_contract_digest not in (None, "")
        else ""
    )
    proposal_digest = (
        _sha256(related_proposal_digest)
        if related_proposal_digest not in (None, "")
        else ""
    )
    if related_contract_digest and not contract_digest:
        blockers.append("RELATED_CONTRACT_DIGEST_INVALID")
    if related_proposal_digest and not proposal_digest:
        blockers.append("RELATED_PROPOSAL_DIGEST_INVALID")

    conversation = _identity(conversation_ref, 320)
    if _contains_forbidden_metadata(
        {
            "recipient_ref": recipient,
            "attachment_refs": attachments,
            "conversation_ref": conversation,
        }
    ):
        blockers.append("FORBIDDEN_SECRET_METADATA")

    blockers = list(dict.fromkeys(blockers))
    draft: dict[str, Any] = {
        "schema": COMMUNICATION_SCHEMA,
        "state": "DRAFT_READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        "channel": channel_name,
        "recipient_ref": recipient,
        "subject": subject_text,
        "body": body_text,
        "body_digest": _text_digest(body_text),
        "attachment_refs": attachments,
        "related_contract_digest": contract_digest,
        "related_proposal_digest": proposal_digest,
        "conversation_ref": conversation,
        "recipient_address_resolved": False,
        "recipient_phone_resolved": False,
        "approval_required": True,
        "approved": False,
        "execution_authorized": False,
        "message_sent": False,
        "delivery_confirmed": False,
        "provider_called": False,
        "network_called": False,
        "crm_written": False,
        "memory_written": False,
        "external_action_executed": False,
        "executes_action": False,
        "draft_digest": "",
    }
    draft["draft_digest"] = _digest(_communication_material(draft))
    return draft


def build_human_approval_packet(
    draft: Mapping[str, Any] | None,
    *,
    action: Any,
    owner_binding_digest: Any,
    reason: Any,
) -> dict[str, Any]:
    """Prepare a subject-bound approval request; never records approval."""
    raw = dict(draft or {})
    blockers: list[str] = []

    action_name = _clean(action, 80).upper()
    if action_name not in APPROVAL_ACTIONS:
        blockers.append("APPROVAL_ACTION_INVALID")

    owner_digest = _sha256(owner_binding_digest)
    if not owner_digest:
        blockers.append("OWNER_BINDING_DIGEST_REQUIRED")

    reason_text = _clean(reason, 1000)
    if not reason_text:
        blockers.append("APPROVAL_REASON_REQUIRED")

    subject_type = ""
    subject_digest = ""
    if raw.get("schema") == COMMUNICATION_SCHEMA:
        if raw.get("state") != "DRAFT_READY" or raw.get("blockers"):
            blockers.append("READY_COMMUNICATION_DRAFT_REQUIRED")
        subject_type = "COMMUNICATION"
        subject_digest = _sha256(raw.get("draft_digest"))
        expected_action = (
            "SEND_EMAIL"
            if raw.get("channel") == "EMAIL"
            else "SEND_WHATSAPP"
            if raw.get("channel") == "WHATSAPP"
            else ""
        )
        if action_name != expected_action:
            blockers.append("COMMUNICATION_ACTION_MISMATCH")
    elif raw.get("schema") == CONTRACT_SCHEMA:
        if raw.get("state") != "DRAFT_READY" or raw.get("blockers"):
            blockers.append("READY_CONTRACT_DRAFT_REQUIRED")
        subject_type = "CONTRACT"
        subject_digest = _sha256(raw.get("contract_digest"))
        if action_name != "EXPORT_CONTRACT_FOR_SIGNATURE_REVIEW":
            blockers.append("CONTRACT_ACTION_MISMATCH")
    else:
        blockers.append("SUPPORTED_DRAFT_SCHEMA_REQUIRED")

    if not subject_digest:
        blockers.append("SUBJECT_DIGEST_REQUIRED")

    blockers = list(dict.fromkeys(blockers))
    packet: dict[str, Any] = {
        "schema": APPROVAL_PACKET_SCHEMA,
        "state": "PENDING_HUMAN_APPROVAL" if not blockers else "BLOCKED",
        "blockers": blockers,
        "approval_gate_action": "EXTERNAL_CHANGE",
        "requested_action": action_name,
        "subject_type": subject_type,
        "subject_digest": subject_digest,
        "owner_binding_digest": owner_digest,
        "reason": reason_text,
        "approval_required": True,
        "approved": False,
        "rejected": False,
        "approval_decision_recorded": False,
        "approval_receipt_verified": False,
        "execution_authorized": False,
        "approval_is_execution": False,
        "recipient_address_resolved": False,
        "recipient_phone_resolved": False,
        "contract_signed": False,
        "message_sent": False,
        "provider_called": False,
        "network_called": False,
        "crm_written": False,
        "external_action_executed": False,
        "executes_action": False,
        "approval_packet_digest": "",
    }
    packet["approval_packet_digest"] = _digest(_approval_material(packet))
    return packet


def verify_human_approval_packet(
    packet: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw = dict(packet or {})
    blockers: list[str] = []

    if raw.get("schema") != APPROVAL_PACKET_SCHEMA:
        blockers.append("APPROVAL_PACKET_SCHEMA_MISMATCH")

    supplied = _sha256(raw.get("approval_packet_digest"))
    expected = _digest(_approval_material(raw))
    if not supplied or supplied != expected:
        blockers.append("APPROVAL_PACKET_DIGEST_MISMATCH")

    if raw.get("state") != "PENDING_HUMAN_APPROVAL" or raw.get("blockers"):
        blockers.append("PENDING_HUMAN_APPROVAL_PACKET_REQUIRED")
    if raw.get("approval_gate_action") != "EXTERNAL_CHANGE":
        blockers.append("APPROVAL_GATE_ACTION_MISMATCH")
    if raw.get("requested_action") not in APPROVAL_ACTIONS:
        blockers.append("REQUESTED_ACTION_INVALID")
    if not _sha256(raw.get("subject_digest")):
        blockers.append("SUBJECT_DIGEST_INVALID")
    if not _sha256(raw.get("owner_binding_digest")):
        blockers.append("OWNER_BINDING_DIGEST_INVALID")

    if raw.get("approval_required") is not True:
        blockers.append("APPROVAL_REQUIRED_FLAG_MISSING")
    for key in (
        "approved",
        "rejected",
        "approval_decision_recorded",
        "approval_receipt_verified",
        "execution_authorized",
        "approval_is_execution",
        "recipient_address_resolved",
        "recipient_phone_resolved",
        "contract_signed",
        "message_sent",
        "provider_called",
        "network_called",
        "crm_written",
        "external_action_executed",
        "executes_action",
    ):
        if raw.get(key) is not False:
            blockers.append("APPROVAL_BOUNDARY_INVALID:" + key)

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": VERIFY_SCHEMA,
        "state": "VALID" if not blockers else "INVALID",
        "valid": not blockers,
        "blockers": blockers,
        "approval_packet_digest": supplied,
        "executes_action": False,
    }


def contract_communication_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "channels": list(CHANNELS),
        "approval_actions": list(APPROVAL_ACTIONS),
        "logical_recipient_refs_only": True,
        "raw_email_address_in_control_plane": False,
        "raw_phone_number_in_control_plane": False,
        "contract_draft_supported": True,
        "clause_summary_supported": True,
        "advisor_risk_binding_supported": True,
        "high_risk_clause_requires_advisor": True,
        "contract_is_final_legal_document": False,
        "legal_advice_authority": False,
        "legal_review_required": True,
        "contract_signing_authority": False,
        "signature_collection_authority": False,
        "email_send_authority": False,
        "whatsapp_send_authority": False,
        "approval_gate_action": "EXTERNAL_CHANGE",
        "approval_required_before_external_send": True,
        "approval_is_execution": False,
        "approved": False,
        "execution_authorized": False,
        "contract_signed": False,
        "message_sent": False,
        "provider_called": False,
        "network_called": False,
        "crm_written": False,
        "memory_written": False,
        "worker_armed": False,
        "deploy_executed": False,
        "core_checkpoint_write": False,
        "external_action_executed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "CONTRACT_SCHEMA",
    "COMMUNICATION_SCHEMA",
    "APPROVAL_PACKET_SCHEMA",
    "VERIFY_SCHEMA",
    "POLICY_SCHEMA",
    "CHANNELS",
    "APPROVAL_ACTIONS",
    "CLAUSE_SEVERITIES",
    "CLAUSE_STATES",
    "build_contract_draft",
    "build_communication_draft",
    "build_human_approval_packet",
    "verify_human_approval_packet",
    "contract_communication_policy",
]
