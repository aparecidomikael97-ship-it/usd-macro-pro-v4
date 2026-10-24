"""A190 G13: offline bridge from signed semantic source to the REAL Outbox.

This file belongs exclusively to LAB. It never sends, reconciles, registers
actual effects, requests providers or grants permission. Issuer pins and
signatures here are SYNTHETIC, caller-supplied and NOT independent trust roots.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping

from aion_chat.models import Scope
from aion_chat.privacy import redact
from atlasquant_aion_execution_outbox import ExecutionOutbox
from g11_offline_conditional_cloud_adapter_contract_lab import (
    ContractDenied, original_subject,
)

_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
DOMAIN = b"A190:G13:SIGNED_SEMANTIC_OPERATION_V1\0"
DIGEST_SCHEMA = "A190_G13_OPERATION_V1"


def _token(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        raise ContractDenied("G13_INVALID_" + name)
    return value


def semantic_operation_digest(
    scope: Scope, *, business_event_id: str, action: str,
    aggregate_key: str, payload: Mapping[str, Any],
) -> str:
    """A LAB business-event identity bound to operation and redacted payload.

    The business_event_id must be independently sourced in real life. Redaction
    may coalesce different private values, so this local representation is not
    an authoritative business uniqueness oracle.
    """
    if not isinstance(scope, Scope):
        raise ContractDenied("G13_TRUSTED_SCOPE_REQUIRED")
    _token(business_event_id, "BUSINESS_EVENT_ID")
    _token(action, "ACTION")
    _token(aggregate_key, "AGGREGATE")
    if not isinstance(payload, Mapping):
        raise ContractDenied("G13_MAPPING_PAYLOAD_REQUIRED")
    safe = redact(dict(payload))
    material = {
        "schema": DIGEST_SCHEMA,
        "tenant": scope.tenant_id,
        "business_event_id": business_event_id,
        "action": action,
        "aggregate_key": aggregate_key,
        "redacted_payload": safe,
    }
    encoded = json.dumps(
        material, sort_keys=True, ensure_ascii=True,
        separators=(",", ":"), default=str,
    ).encode("ascii")
    return sha256(DOMAIN + encoded).hexdigest()


def stage_signed_semantic_lab(
    outbox: ExecutionOutbox, *, signed_event: Mapping[str, Any],
    caller_pin: bytes, claimed_request_ref: str,
    business_event_id: str, action: str, payload: Mapping[str, Any],
    aggregate_key: str, policy_version: str, authorization_ref: str,
    created_at: Any, valid_until: Any, now: int | None = None,
) -> dict[str, Any]:
    """Stage only. Cannot grant a send; never accepts an unsafe LAB Outbox.

    A verified synthetic event's semantic_digest supplies the stable intent
    reference, not claimed_request_ref, original_ref, or arbitrary request IDs.
    A forged caller pin still defeats issuer independence: HARD NO-GO.
    """
    if not isinstance(outbox, ExecutionOutbox):
        raise ContractDenied("G13_REAL_OUTBOX_REQUIRED")
    if getattr(outbox, "_synthetic_lab_callbacks_enabled", False):
        raise ContractDenied("G13_UNSAFE_LAB_OUTBOX_MUST_NOT_STAGE")
    _token(claimed_request_ref, "CLAIMED_REQUEST_REF")
    try:
        original = original_subject(signed_event, caller_pin, now=now)
    except (ValueError, TypeError) as exc:
        raise ContractDenied("G13_UNVERIFIED_SIGNED_ORIGIN") from exc

    subject = original["subject"]
    if subject["tenant"] != outbox.scope.tenant_id:
        raise ContractDenied("G13_ISSUER_TENANT_SCOPE_MISMATCH")
    expected = semantic_operation_digest(
        outbox.scope, business_event_id=business_event_id, action=action,
        aggregate_key=aggregate_key, payload=payload,
    )
    if subject["semantic_digest"] != expected:
        raise ContractDenied("G13_OPERATION_DIGEST_NOT_BOUND_TO_ORIGIN")

    # Real Outbox enforce-on-insert idempotency is scoped to intent_ref.
    # Use a stable, issuer-signed digest as that intent_ref; aliases vanish.
    stable_intent_ref = "semantic-" + expected
    staged = outbox.enqueue(
        intent_ref=stable_intent_ref,
        action=action, payload=payload, aggregate_key=aggregate_key,
        policy_version=policy_version, authorization_ref=authorization_ref,
        created_at=created_at, valid_until=valid_until,
    )
    return {
        **staged,
        "claimed_request_ref_lab_observation": claimed_request_ref,
        "native_semantic_reservation_id": original["native_id"],
        "semantic_event_key": stable_intent_ref,
        "lab_only": True,
        "external_root_verified": False,
        "provider_effect_verified": False,
        "execution_allowed": False,
        "permits_send": False,
        "security_decision": "HARD_NO_GO_SYNTHETIC_STAGING_ONLY",
    }


__all__ = [
    "DOMAIN", "DIGEST_SCHEMA", "semantic_operation_digest",
    "stage_signed_semantic_lab",
]
