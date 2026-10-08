"""AION CI-only: rooted key registry -> exact signed owner internal UI command.

This is a safe preflight *composition*, not a host trust anchor, sign-in,
enrollment, session binding implementation, browser endpoint, or real action.
The caller MUST obtain all HostEvidence from independent trusted host sources
and protect the minimum registry epoch against rollback. Never construct
HostEvidence directly from untrusted browser/client JSON.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Any, Mapping, MutableMapping

from atlasquant_aion_owner_signed_key_registry_preflight_v1 import (
    verify_owner_registry_for_host_review,
)
from atlasquant_aion_owner_proof_navigation_composition_v1 import (
    TrustedOwnerHostPolicy,
)
from atlasquant_aion_owner_signed_intent_guard_v1 import (
    request_intent_bound_navigation, plan_intent_bound_greeting,
)
from atlasquant_aion_trusted_owner_host_crypto_proof_v1 import (
    SQLiteOwnerNonceRegistry,
)

SCHEMA = "AION_ROOTED_OWNER_SIGNED_UI_PREFLIGHT_V1"

# Only these same-session navigation fields are allowed out of the private
# staging state. A future route adding a new write must be security-reviewed.
_NAV_PENDING_KEYS = frozenset({
    "atlasquant_central_choice",
    "atlasquant_guided_revalidation_request",
    "aion_admin_workspace_jump",
})
_EXPECTED_KEYS_BY_TARGET = {
    "central": frozenset({"atlasquant_central_choice"}),
    "trader": frozenset({"atlasquant_central_choice", "atlasquant_guided_revalidation_request"}),
    "investimentos": frozenset({"atlasquant_central_choice", "atlasquant_guided_revalidation_request"}),
    "aion": frozenset({"atlasquant_central_choice", "atlasquant_guided_revalidation_request"}),
    "negocios": frozenset({
        "atlasquant_central_choice", "atlasquant_guided_revalidation_request",
        "aion_admin_workspace_jump",
    }),
}


def _stage_navigation(
    session_state: dict[str, Any],
) -> tuple[dict[str, Any] | None, str]:
    """Use a minimal routing snapshot. No references to unrelated session data."""
    try:
        mode = session_state.get("atlasquant_experience_mode", "")
    except Exception:
        return None, "SESSION_SNAPSHOT_UNAVAILABLE"
    if type(mode) is not str or len(mode) > 80:
        return None, "SESSION_NAV_MODE_INVALID"
    # This is a *private* dict, never the real browser/Streamlit session.
    return {"atlasquant_experience_mode": mode}, ""


def _commit_allowed_navigation(
    session_state: dict[str, Any],
    staged: dict[str, Any],
    target: Any,
) -> str:
    """Apply only expected keys after a fully successful signed route.

    V1 intentionally requires a plain dict; Streamlit's mutable proxy must
    NOT be sent here until a separately trusted host supplies its own atomic,
    authenticated commit transaction.
    """
    expected = _EXPECTED_KEYS_BY_TARGET.get(target)
    if expected is None:
        return "UNRECOGNIZED_SIGNED_NAVIGATION_TARGET"
    actual = set(staged) - {"atlasquant_experience_mode"}
    if actual != expected or not actual.issubset(_NAV_PENDING_KEYS):
        return "UNREVIEWED_ROUTE_STATE_MUTATION"
    if staged.get("atlasquant_central_choice") != target:
        # "central" is the only special root target; the resolver uses
        # an internal string constant for its visible label.
        if target != "central" or staged.get("atlasquant_central_choice") != "central_root":
            return "NAVIGATION_STATE_TARGET_MISMATCH"
    try:
        values = {key: staged[key] for key in expected}
        # dict.update with controlled str keys and validated mapping. All
        # actual session mutations occur AFTER proof+intent verification.
        session_state.update(values)
    except Exception:
        return "HOST_SESSION_NAV_COMMIT_FAILED"
    return ""



@dataclass(frozen=True)
class HostEvidence:
    """Parameters established independently by an authenticated host.

    A dataclass is NOT a security primitive: passing attacker-controlled
    values would defeat all of the trust promises made by this composition.
    """
    pinned_root_public_key: bytes
    pinned_root_fingerprint: str
    registry_id: str
    owner_subject: str
    host_issuer: str
    device_id: str
    device_binding_digest: str
    minimum_registry_epoch: int
    session_binding_digest: str
    audience: str
    device_kind: str
    nonce_registry: SQLiteOwnerNonceRegistry


def _blocked(reason: str, registry_reason: str = "") -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "BLOCKED",
        "reason": reason, "registry_reason": registry_reason,
        "owner_ready": False, "navigation_requested": False,
        "navigation_confirmed": False, "greeting_spoken": False,
        "microphone_active": False, "signed_intent_bound": False,
        "root_signed_registry_verified": False,
        "owner_key_resolved": False, "device_enrolled": False,
        "external_action_authorized": False, "execution_confirmed": False,
        "host_attached": False, "production_authorized": False,
    }


def _digest(data: bytes) -> str:
    return "sha256:" + sha256(data).hexdigest()


def _derive_policy(
    registry_raw: bytes,
    registry_root_signature_b64: str,
    owner_payload: Mapping[str, Any] | None,
    *,
    host: HostEvidence,
    now_epoch: int,
) -> tuple[TrustedOwnerHostPolicy | None, Mapping[str, Any] | None, str, str]:
    """Resolve only registry-signed current owner key, never a client pin."""
    if not isinstance(host, HostEvidence):
        return None, None, "HOST_EVIDENCE_REQUIRED", ""
    if host.device_kind not in ("DESKTOP", "MOBILE"):
        return None, None, "HOST_DEVICE_KIND_REQUIRED", ""
    if not isinstance(host.nonce_registry, SQLiteOwnerNonceRegistry):
        return None, None, "HOST_DURABLE_NONCE_STORE_REQUIRED", ""

    # Explicit trust in host-supplied expected values remains an external gap.
    registry = verify_owner_registry_for_host_review(
        registry_raw, registry_root_signature_b64,
        pinned_root_public_key=host.pinned_root_public_key,
        expected_root_fingerprint=host.pinned_root_fingerprint,
        expected_registry_id=host.registry_id,
        expected_owner_subject=host.owner_subject,
        expected_host_issuer=host.host_issuer,
        expected_device_id=host.device_id,
        expected_device_binding_digest=host.device_binding_digest,
        minimum_epoch=host.minimum_registry_epoch,
        now_epoch=now_epoch,
    )
    if registry.get("state") != "SIGNED_REGISTRY_VERIFIED_FOR_HOST_REVIEW":
        return None, None, "ROOT_SIGNED_REGISTRY_REQUIRED", str(
            registry.get("reason") or "REGISTRY_FAILED"
        )
    # The host only derives its owner pin from the verified signed registry.
    # Matching the signed owner proof's subject/issuer/device to independently
    # anchored registry and host values happens before any proof nonce burn.
    if (
        not isinstance(owner_payload, Mapping)
        or owner_payload.get("subject") != host.owner_subject
        or owner_payload.get("issuer") != host.host_issuer
        or owner_payload.get("audience") != host.audience
        or owner_payload.get("device_binding_digest") != host.device_binding_digest
        or owner_payload.get("session_binding_digest") != host.session_binding_digest
        or owner_payload.get("key_fingerprint") != registry["owner_key_fingerprint"]
    ):
        return None, None, "OWNER_PROOF_NOT_BOUND_TO_ROOTED_REGISTRY", ""

    key = registry["resolved_owner_public_key"]
    if type(key) is not bytes or _digest(key) != registry["owner_key_fingerprint"]:
        return None, None, "REGISTRY_OWNER_KEY_INVALID", ""
    policy = TrustedOwnerHostPolicy(
        pinned_owner_public_key=key,
        expected_pinned_key_fingerprint=registry["owner_key_fingerprint"],
        expected_session_binding_digest=host.session_binding_digest,
        expected_device_binding_digest=host.device_binding_digest,
        expected_issuer=host.host_issuer,
        expected_audience=host.audience,
        device=host.device_kind,
        nonce_registry=host.nonce_registry,
    )
    # Do not return the registry's owner key to untrusted UI consumers.
    return policy, registry, "", ""


def request_rooted_owner_navigation(
    session_state: MutableMapping[str, Any],
    access: Mapping[str, Any] | None,
    registry_raw: bytes,
    registry_root_signature_b64: str,
    owner_payload: Mapping[str, Any] | None,
    owner_signature_b64: str,
    intent: Mapping[str, Any] | None,
    intent_signature_b64: str,
    *,
    host: HostEvidence,
    now_epoch: int,
    text: str,
) -> dict[str, Any]:
    """Checks rooted key/device + exact signed command BEFORE navigation."""
    # Prototype safe boundary: refuse Streamlit/mutable proxy writes directly.
    # A real trusted host must implement a separate, protected commit adapter.
    if type(session_state) is not dict:
        return _blocked("HOST_SESSION_PLAIN_DICT_REQUIRED")
    if type(text) is not str or not 1 <= len(text) <= 160:
        return _blocked("EXACT_SINGLE_COMMAND_REQUIRED")
    staged, snapshot_reason = _stage_navigation(session_state)
    if staged is None:
        return _blocked(snapshot_reason)
    policy, registry, reason, registry_reason = _derive_policy(
        registry_raw, registry_root_signature_b64, owner_payload,
        host=host, now_epoch=now_epoch,
    )
    if policy is None:
        return _blocked(reason, registry_reason)
    try:
        result = request_intent_bound_navigation(
            staged, access, owner_payload, owner_signature_b64,
            intent, intent_signature_b64,
            policy=policy, now_epoch=now_epoch, text=text,
        )
    except Exception:
        # The proof nonce may have been consumed (fail closed), but the real
        # session_state remains unchanged. No error/secret reflected to client.
        return _blocked("STAGED_OWNER_NAVIGATION_FAILED")
    if result.get("state") != "INTERNAL_NAVIGATION_REQUESTED":
        return _blocked("SIGNED_OWNER_INTENT_OR_NAVIGATION_REJECTED")
    commit_reason = _commit_allowed_navigation(
        session_state, staged, result.get("target"),
    )
    if commit_reason:
        return _blocked(commit_reason)
    return {
        **result, "schema": SCHEMA,
        "root_signed_registry_verified": True,
        "owner_key_resolved": True,
        "device_enrolled": True,
        "registry_epoch": registry["registry_epoch"],
        "registry_digest": registry["registry_digest"],
        "owner_key_id": registry["owner_key_id"],
        "navigation_confirmed": False,
        "external_action_authorized": False, "execution_confirmed": False,
        "host_attached": False, "production_authorized": False,
    }


def plan_rooted_owner_greeting(
    access: Mapping[str, Any] | None,
    registry_raw: bytes,
    registry_root_signature_b64: str,
    owner_payload: Mapping[str, Any] | None,
    owner_signature_b64: str,
    intent: Mapping[str, Any] | None,
    intent_signature_b64: str,
    *,
    host: HostEvidence,
    now_epoch: int,
    now: datetime | None = None,
    timezone_name: str | None = None,
) -> dict[str, Any]:
    """Signed display-only greeting: never starts listener or reads PC info."""
    policy, registry, reason, registry_reason = _derive_policy(
        registry_raw, registry_root_signature_b64, owner_payload,
        host=host, now_epoch=now_epoch,
    )
    if policy is None:
        return _blocked(reason, registry_reason)
    result = plan_intent_bound_greeting(
        access, owner_payload, owner_signature_b64,
        intent, intent_signature_b64,
        policy=policy, now_epoch=now_epoch,
        now=now, timezone_name=timezone_name,
    )
    if result.get("state") != "OWNER_ENTRY_READY":
        return _blocked("SIGNED_OWNER_INTENT_OR_GREETING_REJECTED")
    return {
        **result, "schema": SCHEMA,
        "root_signed_registry_verified": True,
        "owner_key_resolved": True,
        "device_enrolled": True,
        "registry_epoch": registry["registry_epoch"],
        "registry_digest": registry["registry_digest"],
        "owner_key_id": registry["owner_key_id"],
        "greeting_spoken": False, "microphone_active": False,
        "external_action_authorized": False, "execution_confirmed": False,
        "host_attached": False, "production_authorized": False,
    }


__all__ = [
    "SCHEMA", "HostEvidence", "request_rooted_owner_navigation",
    "plan_rooted_owner_greeting",
]
