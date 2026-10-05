"""AION V2.13 Control Plane bridge.

Builds a canonical authority view only by executing the real cryptographic
verifier. It never trusts a pre-computed caller boolean such as
authority_verified=True.
"""
from __future__ import annotations

from typing import Any, Mapping

from atlasquant_aion_authority_verifier import verify_authority_statement
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry

SCHEMA = "ATLASQUANT_AION_TRUSTED_AUTHORITY_VIEW_V1"


def verify_and_build_trusted_authority_view(
    statement: Any,
    *,
    signature_b64: str,
    trust_roots: TrustRootRegistry,
    nonce_registry: PersistentNonceRegistry,
    now_ts: str,
    expected_binding: Mapping[str, str],
) -> dict[str, Any]:
    verification = verify_authority_statement(
        statement,
        signature_b64=signature_b64,
        trust_roots=trust_roots,
        nonce_registry=nonce_registry,
        now_ts=now_ts,
        expected_binding=expected_binding,
    )
    verified = verification["state"] == "VERIFIED" and verification["authority_verified"] is True
    return {
        "schema": SCHEMA,
        "state": "VERIFIED" if verified else "BLOCKED",
        "blockers": list(verification["blockers"]),
        "authority_available": verified,
        "authority_verified": verified,
        "authority_binding_configured": verification.get("binding_verified", False),
        "trust_root_configured": verification.get("trust_root_configured", False),
        "signature_verification_available": True,
        "signature_verified": verification.get("signature_verified", False),
        "origin_authenticated": verified,
        "snapshot_signed": False,
        "execution_authority_granted": verification.get("execution_authority_granted", False) if verified else False,
        "execution_allowed": False,
        "approval_implied": False,
        "executes_action": False,
        "network_called": False,
        "private_key_used": False,
        "verification": verification,
    }
