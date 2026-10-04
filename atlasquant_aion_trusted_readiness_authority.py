"""AION V2.12: canonical trusted-readiness authority boundary.

This module deliberately implements *absence of authority*, not a trust root.
Caller-controlled payloads are ignored. No key, signature, verifier, network,
persistent store, provider or execution capability exists here.
"""
from __future__ import annotations

from typing import Any

SCHEMA = "ATLASQUANT_AION_TRUSTED_READINESS_AUTHORITY_V1"

BLOCKERS = (
    "TRUSTED_READINESS_AUTHORITY_UNAVAILABLE",
    "TRUST_ROOT_NOT_CONFIGURED",
    "SIGNATURE_VERIFICATION_UNAVAILABLE",
    "AUTHORITY_BINDING_NOT_CONFIGURED",
)


def trusted_readiness_authority_view(_payload: Any = None) -> dict[str, Any]:
    """Return the canonical fail-closed authority boundary.

    The argument is accepted only for compatibility/red-team injection tests and
    is intentionally never inspected. Until a separately authenticated trust
    root and authority-binding design exists, this function cannot return READY
    or grant execution authority.
    """
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "authority_available": False,
        "authority_verified": False,
        "authority_binding_configured": False,
        "trust_root_configured": False,
        "signature_verification_available": False,
        "origin_authenticated": False,
        "snapshot_signed": False,
        "execution_authority_granted": False,
        "execution_allowed": False,
        "executes_action": False,
        "reads_persistent_storage": False,
        "network_called": False,
        "creates_secret_or_key_material": False,
        "approval_implied": False,
        "blockers": list(BLOCKERS),
    }
