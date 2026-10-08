"""AION signed owner proof -> internal navigation composition (offline-only draft).

This thin adapter composes the #1079 cryptographic verifier with the #1078
same-session navigation bridge. It does not authenticate the browser or
provision an owner key; ONLY a separately trusted host may construct its
policy from server-held, independently authenticated bindings.

A positive result is NOT a desktop action, live page-transition proof,
biometric authentication, purchase, deploy, or general tool authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, MutableMapping

from atlasquant_aion_trusted_owner_host_crypto_proof_v1 import (
    SQLiteOwnerNonceRegistry, verify_host_owner_proof,
)
from atlasquant_aion_owner_host_entry_navigation_bridge_v1 import (
    prepare_owner_host_entry, route_owner_text_navigation,
)

SCHEMA = "AION_OWNER_PROOF_INTERNAL_NAVIGATION_COMPOSITION_V1"


@dataclass(frozen=True)
class TrustedOwnerHostPolicy:
    """Trusted HOST-SIDE inputs only; never hydrate from client JSON or cookies.

    The caller MUST independently verify the real authenticated ADMIN session,
    session/device binding digests and enrolled owner key. This container
    does not, by itself, make a process or configuration trusted.
    """
    pinned_owner_public_key: bytes
    expected_pinned_key_fingerprint: str
    expected_session_binding_digest: str
    expected_device_binding_digest: str
    expected_issuer: str
    expected_audience: str
    device: str
    nonce_registry: SQLiteOwnerNonceRegistry


def _blocked(reason: str, *, proof_reason: str = "") -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "reason": reason,
        "proof_reason": proof_reason,
        "owner_ready": False,
        "navigation_requested": False,
        "navigation_confirmed": False,
        "external_action_authorized": False,
        "execution_confirmed": False,
        "trusted_host_attached": False,
    }


def _verify(
    access: Mapping[str, Any] | None,
    payload: Mapping[str, Any] | None,
    signature_b64: str,
    *,
    policy: TrustedOwnerHostPolicy,
    now_epoch: int,
) -> tuple[Mapping[str, Any] | None, str]:
    if not isinstance(policy, TrustedOwnerHostPolicy):
        return None, "TRUSTED_HOST_POLICY_REQUIRED"
    if policy.device not in ("DESKTOP", "MOBILE"):
        return None, "TRUSTED_DEVICE_REQUIRED"
    if not isinstance(policy.nonce_registry, SQLiteOwnerNonceRegistry):
        return None, "DURABLE_REPLAY_STORE_REQUIRED"
    # The verifier checks expected issuer, audience, key, signed canonical bytes,
    # authenticated session binding and durable nonce consumption, in that order.
    verified = verify_host_owner_proof(
        access, payload, signature_b64,
        pinned_owner_public_key=policy.pinned_owner_public_key,
        expected_pinned_key_fingerprint=policy.expected_pinned_key_fingerprint,
        expected_session_binding_digest=policy.expected_session_binding_digest,
        expected_device_binding_digest=policy.expected_device_binding_digest,
        expected_issuer=policy.expected_issuer,
        expected_audience=policy.expected_audience,
        now_epoch=now_epoch,
        nonce_registry=policy.nonce_registry,
    )
    if verified.get("state") != "CRYPTO_PROOF_VERIFIED_FOR_TRUSTED_HOST_REVIEW":
        return None, str(verified.get("reason") or "OWNER_PROOF_REJECTED")
    assertion = verified.get("owner_assertion")
    if not isinstance(assertion, Mapping) or assertion.get("verified") is not True:
        return None, "OWNER_ASSERTION_UNAVAILABLE"
    # Assertion stays internal to this call, never returned to UI as authority.
    return assertion, ""


def plan_verified_owner_greeting(
    access: Mapping[str, Any] | None,
    payload: Mapping[str, Any] | None,
    signature_b64: str,
    *,
    policy: TrustedOwnerHostPolicy,
    now_epoch: int,
    now: datetime | None = None,
    timezone_name: str | None = None,
) -> dict[str, Any]:
    """Prepare display-only greeting after a ONE-TIME signed owner proof.

    A separate fresh proof is required for a later navigation request. There
    is no persistent authorization session or automatic device pairing here.
    """
    assertion, reason = _verify(
        access, payload, signature_b64, policy=policy, now_epoch=now_epoch,
    )
    if assertion is None:
        return _blocked("SIGNED_OWNER_PROOF_REQUIRED", proof_reason=reason)
    result = prepare_owner_host_entry(
        access, assertion, trusted_host_owner=True,
        now=now, timezone_name=timezone_name,
    )
    if result.get("state") != "OWNER_ENTRY_READY":
        return _blocked("OWNER_GREETING_NOT_READY")
    return {
        **result,
        "schema": SCHEMA,
        "proof_consumed": True,
        "navigation_confirmed": False,
        "trusted_host_attached": False,  # host/UI binding not performed here
    }


def request_verified_owner_navigation(
    session_state: MutableMapping[str, Any],
    access: Mapping[str, Any] | None,
    payload: Mapping[str, Any] | None,
    signature_b64: str,
    *,
    policy: TrustedOwnerHostPolicy,
    now_epoch: int,
    text: str,
) -> dict[str, Any]:
    """Request strictly internal navigation only after fresh owner signature.

    The host passes a trusted session state and a policy it created itself;
    policy.device is never selected by client input. This requests but does
    not confirm a page transition. No external-app path is offered.
    """
    if not isinstance(session_state, MutableMapping):
        return _blocked("TRUSTED_SESSION_STATE_REQUIRED")
    if type(text) is not str or not 1 <= len(text) <= 160:
        return _blocked("FRESH_SINGLE_TEXT_COMMAND_REQUIRED")
    assertion, reason = _verify(
        access, payload, signature_b64, policy=policy, now_epoch=now_epoch,
    )
    if assertion is None:
        return _blocked("SIGNED_OWNER_PROOF_REQUIRED", proof_reason=reason)
    result = route_owner_text_navigation(
        session_state, access, assertion,
        trusted_host_owner=True,
        text=text, device=policy.device,
    )
    if result.get("state") != "INTERNAL_NAVIGATION_REQUESTED":
        return _blocked(str(result.get("reason") or "NAVIGATION_REJECTED"))
    return {
        **result,
        "schema": SCHEMA,
        "proof_consumed": True,
        "navigation_confirmed": False,
        "trusted_host_attached": False,
    }


__all__ = [
    "SCHEMA", "TrustedOwnerHostPolicy", "plan_verified_owner_greeting",
    "request_verified_owner_navigation",
]
