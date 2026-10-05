"""AION B2B owner renewal decision request.

Pure/offline preparation for an explicit owner decision ceremony. This module
does not treat chat text as approval, does not verify a signature, does not
persist a decision, and does not execute renewal, expansion, pause, termination,
billing, repricing, quota/role/integration changes, customer contact, provider
calls, deploys, or production mutations.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping

from atlasquant_aion_b2b_owner_renewal_review import (
    SCHEMA as OWNER_REVIEW_SCHEMA,
)

SCHEMA = "ATLASQUANT_AION_B2B_OWNER_RENEWAL_DECISION_REQUEST_V1"

UNSAFE_PACKET_FIELDS = (
    "automatic_owner_choice",
    "automatic_renewal",
    "automatic_expansion",
    "automatic_package_change",
    "automatic_pause",
    "automatic_termination",
    "automatic_billing",
    "automatic_pricing_change",
    "automatic_quota_increase",
    "automatic_role_change",
    "automatic_integration_change",
    "automatic_customer_contact",
    "automatic_provisioning",
    "automatic_deploy",
    "provider_called",
    "crm_write",
    "production_mutation",
    "executes_action",
)

GENERIC_CHAT_CHOICES = {
    "ok",
    "okay",
    "sim",
    "vamos la",
    "vamos lá",
    "pode ir",
    "pode seguir",
    "aprovado",
    "approve",
    "yes",
}


def _text(value: Any, limit: int = 320) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(data.get("owner_id"), 120),
        "tenant_id": _text(data.get("tenant_id"), 120),
        "workspace_id": _text(data.get("workspace_id"), 120),
    }


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


def build_owner_renewal_decision_request(
    *,
    trusted_scope: Mapping[str, Any],
    owner_review_packet: Mapping[str, Any],
    requested_choice: Any,
    ceremony_id: Any,
    nonce: Any,
    issued_at: Any,
    expires_at: Any,
) -> dict[str, Any]:
    trusted = _scope(trusted_scope)
    packet = (
        dict(owner_review_packet)
        if isinstance(owner_review_packet, Mapping)
        else {}
    )
    blockers: list[str] = []

    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")
    if packet.get("schema") != OWNER_REVIEW_SCHEMA:
        blockers.append("OWNER_REVIEW_PACKET_SCHEMA_INVALID")
    if packet.get("state") != "REVIEWABLE":
        blockers.append("OWNER_REVIEW_PACKET_NOT_REVIEWABLE")
    if packet.get("decision") != "OWNER_REVIEW_REQUIRED":
        blockers.append("OWNER_REVIEW_PACKET_DECISION_BOUNDARY_INVALID")
    if packet.get("blockers"):
        blockers.append("OWNER_REVIEW_PACKET_HAS_BLOCKERS")
    if packet.get("owner_decision_required") is not True:
        blockers.append("OWNER_DECISION_BOUNDARY_MISSING")
    if packet.get("owner_only") is not True:
        blockers.append("OWNER_ONLY_BOUNDARY_MISSING")
    if packet.get("customer_visible") is not False:
        blockers.append("OWNER_REVIEW_PACKET_CUSTOMER_VISIBILITY_UNSAFE")

    if _scope(packet.get("scope")) != trusted or _scope(packet) != trusted:
        blockers.append("OWNER_REVIEW_PACKET_SCOPE_MISMATCH")

    customer_id = _text(packet.get("customer_id"), 120)
    pilot_id = _text(packet.get("pilot_id"), 120)
    package = _text(packet.get("package"), 40).upper()
    if not customer_id:
        blockers.append("CUSTOMER_ID_REQUIRED")
    if not pilot_id:
        blockers.append("PILOT_ID_REQUIRED")
    if not package:
        blockers.append("PACKAGE_REQUIRED")

    for field in (
        "evidence_digest",
        "cycle_evidence_digest",
        "contract_digest",
        "value_bound_conversion_digest",
    ):
        if not _text(packet.get(field), 180):
            blockers.append(field.upper() + "_REQUIRED")

    for key in UNSAFE_PACKET_FIELDS:
        if packet.get(key) is not False:
            blockers.append("OWNER_REVIEW_PACKET_UNSAFE_FIELD:" + key)

    allowed = [
        _text(item, 120)
        for item in list(packet.get("allowed_owner_choices") or [])[:20]
        if _text(item, 120)
    ]
    choice = _text(requested_choice, 120)
    if not choice:
        blockers.append("OWNER_RENEWAL_CHOICE_REQUIRED")
    if choice.casefold() in GENERIC_CHAT_CHOICES:
        blockers.append("GENERIC_CHAT_INSTRUCTION_NOT_ACCEPTED_AS_DECISION")
    if choice not in allowed:
        blockers.append("OWNER_RENEWAL_CHOICE_NOT_ALLOWED_BY_PACKET")

    ceremony = _text(ceremony_id, 160)
    request_nonce = _text(nonce, 240)
    issued = _text(issued_at, 96)
    expires = _text(expires_at, 96)
    if not ceremony:
        blockers.append("CEREMONY_ID_REQUIRED")
    if len(request_nonce) < 16:
        blockers.append("NONCE_INVALID")
    if not issued:
        blockers.append("ISSUED_AT_REQUIRED")
    if not expires:
        blockers.append("EXPIRES_AT_REQUIRED")

    request = {
        "purpose": "B2B_OWNER_RENEWAL_EXPLICIT_DECISION",
        "owner_id": trusted["owner_id"],
        "tenant_id": trusted["tenant_id"],
        "workspace_id": trusted["workspace_id"],
        "customer_id": customer_id,
        "pilot_id": pilot_id,
        "package": package,
        "review_type": _text(packet.get("review_type"), 120),
        "requested_choice": choice,
        "owner_review_packet_digest": _text(
            packet.get("evidence_digest"),
            180,
        ),
        "cycle_evidence_digest": _text(
            packet.get("cycle_evidence_digest"),
            180,
        ),
        "contract_digest": _text(packet.get("contract_digest"), 180),
        "value_bound_conversion_digest": _text(
            packet.get("value_bound_conversion_digest"),
            180,
        ),
        "ceremony_id": ceremony,
        "nonce": request_nonce,
        "issued_at": issued,
        "expires_at": expires,
    }
    request_digest = _digest(request)

    if blockers:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "request": {},
            "request_digest": "",
            "blockers": list(dict.fromkeys(blockers)),
            "owner_signature_required": True,
            "owner_signature_verified": False,
            "owner_decision_verified": False,
            "owner_decision_recorded": False,
            "decision_persisted": False,
            "generic_chat_instruction_accepted_as_decision": False,
            "renewal_authorized": False,
            "expansion_authorized": False,
            "pause_authorized": False,
            "termination_authorized": False,
            "billing_authorized": False,
            "pricing_change_authorized": False,
            "quota_change_authorized": False,
            "role_change_authorized": False,
            "integration_change_authorized": False,
            "customer_contact_authorized": False,
            "provisioning_authorized": False,
            "deploy_authorized": False,
            "provider_called": False,
            "crm_write_authorized": False,
            "production_mutation_authorized": False,
            "external_action_executed": False,
            "executes_action": False,
        }

    return {
        "schema": SCHEMA,
        "state": "READY_FOR_EXPLICIT_OWNER_SIGNATURE",
        "request": request,
        "request_digest": request_digest,
        "blockers": [],
        "owner_signature_required": True,
        "owner_signature_verified": False,
        "owner_decision_verified": False,
        "owner_decision_recorded": False,
        "decision_persisted": False,
        "requires_signature_verification_step": True,
        "requires_persistence_after_verification": True,
        "generic_chat_instruction_accepted_as_decision": False,
        "renewal_authorized": False,
        "expansion_authorized": False,
        "pause_authorized": False,
        "termination_authorized": False,
        "billing_authorized": False,
        "pricing_change_authorized": False,
        "quota_change_authorized": False,
        "role_change_authorized": False,
        "integration_change_authorized": False,
        "customer_contact_authorized": False,
        "provisioning_authorized": False,
        "deploy_authorized": False,
        "provider_called": False,
        "crm_write_authorized": False,
        "production_mutation_authorized": False,
        "external_action_executed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "GENERIC_CHAT_CHOICES",
    "build_owner_renewal_decision_request",
]
