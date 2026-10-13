"""AION V16-A.37: OFFLINE SHAPE CHECK ONLY; no external receipt trust.

A correctly shaped, context-matched, apparently signed payload remains
UNTRUSTED. This module has NO verifier, producer, network, callback, trust
root, signature validation, witness readback, grant or Outbox state update.
Never map its outputs to dispatch, reconciliation, retry or compensation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

SCHEMA = "ATLASQUANT_AION_EXTERNAL_EFFECT_CLAIM_V1_UNTRUSTED"
POSITIVE = "POSITIVE_COMMITTED"
NEGATIVE = "NEGATIVE_NO_EFFECT_FENCED"
_DOMAINS = {
    POSITIVE: "ATLASQUANT:AION:COMMITTED_EFFECT_CLAIM:V1:UNTRUSTED",
    NEGATIVE: "ATLASQUANT:AION:NO_EFFECT_FENCED_CLAIM:V1:UNTRUSTED",
}
_BINDING = (
    "owner_id", "tenant_id", "workspace_id", "host_id",
    "producer_issuer_id", "producer_account_id", "action_class",
    "intent_digest", "idempotency_key", "attempt", "epoch",
    "witness_sequence", "witness_head", "nonce",
)
_FIELDS = frozenset((
    "schema", "domain", "kind", "receipt_id", "issued_at",
    "claimed_signature",
    *_BINDING,
))
_EXTRA = {
    POSITIVE: "claimed_effect_ref",
    NEGATIVE: "claimed_terminal_fence_ref",
}
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HEX128 = re.compile(r"^[0-9a-f]{128}$")
_UTC_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

# Deliberately no enable flag / verifier injection / "trusted" result.
def _deny(reason: str, *, shape_matched: bool = False) -> dict[str, Any]:
    return {
        "schema": "ATLASQUANT_AION_EXTERNAL_RECEIPT_PRECHECK_V1",
        "status": "BLOCKED_EXTERNAL_PROOF_UNAVAILABLE" if shape_matched else "BLOCKED_INVALID_UNTRUSTED_CLAIM",
        "reason": reason,
        "shape_matched": shape_matched,
        "issuer_authenticated": False,
        "signature_verified": False,
        "current_external_witness_verified": False,
        "producer_commit_verified": False,
        "producer_terminal_no_effect_fence_verified": False,
        "external_action_authorized": False,
        "effect_ledger_authorized": False,
        "retry_authorized": False,
        "saga_advance_authorized": False,
    }


def inspect_untrusted_receipt_shape(
    untrusted_claim: Any, expected_local_binding: Any,
) -> dict[str, Any]:
    """Check bounded primitive syntax/context only, NEVER grant authority.

    expected_local_binding is NOT proof of trusted external enrollment. Matching
    it detects mistakes but cannot authenticate the issuer or witness. No
    references to untrusted object properties/methods are evaluated: only
    exact built-in dict/str/int/bool types and primitive equality are accepted.
    """
    if type(untrusted_claim) is not dict:
        return _deny("CLAIM_MUST_BE_PLAIN_DICT")
    if type(expected_local_binding) is not dict:
        return _deny("EXPECTED_MUST_BE_PLAIN_DICT")
    if any(type(key) is not str for key in expected_local_binding):
        return _deny("EXPECTED_KEY_NOT_STRING")
    if set(expected_local_binding) != set(_BINDING):
        return _deny("EXPECTED_BINDING_FIELDS_MISMATCH")
    # Inspect keys BEFORE dict.get: a foreign key whose hash collides
    # with "kind" might execute an attacker-controlled __eq__ otherwise.
    if any(type(key) is not str for key in untrusted_claim):
        return _deny("CLAIM_KEY_NOT_STRING")
    kind = untrusted_claim.get("kind")
    if type(kind) is not str or kind not in _DOMAINS:
        return _deny("INVALID_CLAIM_KIND")
    allowed = _FIELDS | {_EXTRA[kind]}
    if set(untrusted_claim) != allowed:
        return _deny("CLAIM_FIELDS_MISMATCH")
    if type(untrusted_claim["schema"]) is not str or type(untrusted_claim["domain"]) is not str:
        return _deny("UNTRUSTED_DOMAIN_TYPE")
    if untrusted_claim["schema"] != SCHEMA or untrusted_claim["domain"] != _DOMAINS[kind]:
        return _deny("UNTRUSTED_DOMAIN_MISMATCH")
    for field in _BINDING:
        observed, expected = untrusted_claim[field], expected_local_binding[field]
        if field in {"attempt", "epoch", "witness_sequence"}:
            if type(expected) is not int or expected < 1:
                return _deny("INVALID_EXPECTED_" + field.upper())
            if type(observed) is not int or observed < 1:
                return _deny("INVALID_CLAIM_" + field.upper())
        else:
            if type(expected) is not str or type(observed) is not str:
                return _deny("INVALID_BINDING_TYPE_" + field.upper())
            if len(expected) > 128 or len(observed) > 128:
                return _deny("BINDING_TOO_LONG_" + field.upper())
            if field in {"intent_digest", "witness_head"}:
                if not _HEX64.fullmatch(expected) or not _HEX64.fullmatch(observed):
                    return _deny("INVALID_DIGEST_" + field.upper())
            elif not _TOKEN.fullmatch(expected) or not _TOKEN.fullmatch(observed):
                return _deny("INVALID_BINDING_TOKEN_" + field.upper())
        if type(observed) is not type(expected) or observed != expected:
            return _deny("LOCAL_BINDING_MISMATCH_" + field.upper())
    for key in ("receipt_id", _EXTRA[kind]):
        value = untrusted_claim[key]
        if type(value) is not str or not _TOKEN.fullmatch(value):
            return _deny("INVALID_UNTRUSTED_IDENTIFIER_" + key.upper())
    signature = untrusted_claim["claimed_signature"]
    if type(signature) is not str or not _HEX128.fullmatch(signature):
        return _deny("INVALID_CLAIMED_SIGNATURE_SHAPE")
    issued_at = untrusted_claim["issued_at"]
    if type(issued_at) is not str or not _UTC_Z.fullmatch(issued_at):
        return _deny("INVALID_UTC_TIMESTAMP")
    try:
        parsed = datetime.strptime(issued_at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        if parsed.year < 2020:
            return _deny("INVALID_UTC_TIMESTAMP")
    except ValueError:
        return _deny("INVALID_UTC_TIMESTAMP")
    # Even a well-formed, matching, self-"signed" claim conveys NO approval.
    # No real issuer enrollment, signature verifier, producer fence or
    # independently authenticated current witness exists in this component.
    return _deny("INDEPENDENT_PRODUCER_AND_WITNESS_NOT_ENROLLED", shape_matched=True)
