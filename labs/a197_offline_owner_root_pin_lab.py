"""A197 OFFLINE authority root-manifest PIN exercise (LAB, not an identity service).

Pin the entire public Ed25519 root registry manifest byte canonically to an
expected digest, then run the REAL signed authority verification with a REAL
SQLite nonce registry. This shows why signer self-attestation is insufficient.

CRITICAL: both trust manifest and expected PIN are inputs. If an attacker
controls BOTH, this proves nothing about HUMAN_OWNER provenance. Results
remain LOCAL_ONLY, never operationally authoritative. Do not use as production
owner enrollment or as a replacement for an independent custodian.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from typing import Any

from atlasquant_aion_authority_verifier import verify_authority_statement
from atlasquant_aion_trust_root import TrustRootRegistry

SCHEMA = "AION_A197_OFFLINE_PUBLIC_ROOT_PIN_PROOF_LAB_V1"
EXPECTED_FIELDS = frozenset({"schema", "roots", "revoked_key_ids"})


def canonical_manifest_digest(manifest: Any) -> str:
    """Canonical sha256 of the complete, strictly shaped public manifest."""
    if not isinstance(manifest, Mapping) or set(manifest) != EXPECTED_FIELDS:
        raise ValueError("canonical root manifest shape required")
    # Verify actual Ed25519 public keys, periods, statuses and revocations.
    TrustRootRegistry.from_mapping(manifest)
    raw = json.dumps(
        dict(manifest), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "reason": reason,
        "local_manifest_pin_matched": False,
        "local_signature_verified": False,
        "external_owner_provenance_verified": False,
        "independent_root_custody_verified": False,
        "independent_anti_rollback_verified": False,
        "human_owner_enrollment_verified": False,
        "execution_allowed": False,
        "approval_implied": False,
        "provider_called": False,
        "p0_homologated": 0,
        "hard_no_go": True,
    }


def assess_pinned_authority_locally(
    *,
    manifest: object,
    expected_manifest_sha256: object,
    statement: object,
    signature_b64: object,
    nonce_registry: object,
    now_ts: object,
    expected_binding: object,
) -> dict[str, Any]:
    """Illustrative narrow verifier, not a production authority or root.

    expected_manifest_sha256 is genuinely helpful ONLY when configured by a
    separately controlled authority that callers cannot rewrite; this module
    cannot establish that independent custody and NEVER claims it did.
    """
    if (
        not isinstance(expected_manifest_sha256, str)
        or len(expected_manifest_sha256) != 64
        or any(x not in "0123456789abcdef" for x in expected_manifest_sha256)
    ):
        return _blocked("TRUSTED_PIN_NOT_CONFIGURED")
    try:
        digest = canonical_manifest_digest(manifest)
    except (ValueError, TypeError, UnicodeError, OverflowError):
        return _blocked("MANIFEST_INVALID")
    if not hmac.compare_digest(digest, expected_manifest_sha256):
        return _blocked("MANIFEST_PIN_MISMATCH")

    # Gate on complete manifest (including revocation status), not just the
    # current public key, before consuming nonce or reading the signature.
    try:
        registry = TrustRootRegistry.from_mapping(manifest)
        result = verify_authority_statement(
            statement, signature_b64=signature_b64,
            trust_roots=registry, nonce_registry=nonce_registry,
            now_ts=now_ts, expected_binding=expected_binding,
        )
    except Exception:
        return _blocked("LOCAL_VERIFICATION_UNAVAILABLE")
    if result.get("state") != "VERIFIED" or result.get("signature_verified") is not True:
        out = _blocked("LOCAL_SIGNATURE_OR_REPLAY_DENIED")
        out["local_manifest_pin_matched"] = True
        return out

    # Even cryptographic verification under a matching caller-supplied pin
    # cannot attest to independent HUMAN_OWNER custody, nor allow an action.
    return {
        "schema": SCHEMA,
        "state": "LOCAL_SIGNATURE_VALID_NOT_OWNER_HOMOLOGATION",
        "reason": "LOCAL_PIN_AND_SIGNATURE_MATCH_ONLY",
        "local_manifest_pin_matched": True,
        "local_signature_verified": True,
        "external_owner_provenance_verified": False,
        "independent_root_custody_verified": False,
        "independent_anti_rollback_verified": False,
        "human_owner_enrollment_verified": False,
        "execution_allowed": False,
        "approval_implied": False,
        "provider_called": False,
        "p0_homologated": 0,
        "hard_no_go": True,
    }
