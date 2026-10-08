"""AION Windows host-anchor READ-ONLY registry readiness observation.

Safety scope: this NEVER creates/edits/installs an anchor, never validates OS
ACL/TPM/secure boot, and never gives host pins to a trusted verifier. Shape
readback alone is NEVER a proof of Windows-protected trust or real owner
identity. Windows CI can exercise the negative-only native registry path.

Required HKLM path is FIXED, not supplied by a caller.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from typing import Any, Mapping

SCHEMA = "AION_WINDOWS_HOST_ANCHOR_READONLY_INVENTORY_V1"
CANDIDATE = "READ_ONLY_ANCHOR_SHAPE_OBSERVED_UNTRUSTED"
BLOCKED = "BLOCKED"
ANCHOR_SCHEMA = "AION_HOST_COLLECTOR_TRUST_ANCHOR_V1"
FIXED_HKLM_PATH = r"SOFTWARE\AtlasQuant\AION\TrustedHostPolicyV1"
READ_VALUES = (
    "AnchorSchema", "PolicyAuthorityPublicKey",
    "OwnerRegistryRootPublicKey", "PolicySnapshotDigest", "PolicyEpoch",
)
_DOMAIN = b"ATLASQUANT:AION:WINDOWS_HOST_ANCHOR_READONLY:V1\x00"
_SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
_NONCE = re.compile(r"[0-9a-f]{64}\Z")
MAX_EPOCH = 2**63 - 1


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": BLOCKED, "reason": reason,
        "native_registry_read_completed": False,
        "anchor_schema_and_types_valid": False,
        "fixed_machine_scope_used": False,
        "anchor_snapshot_observation_digest": None,
        "policy_epoch_observed": None,
        "source_path_was_user_controlled": False,
        "host_anchor_is_protected": False,
        "registry_acl_verified": False,
        "trusted_installer_identity_verified": False,
        "independent_host_policy_origin_verified": False,
        "hardware_antirollback_verified": False,
        "tpm_binding_verified": False,
        "owner_identity_verified": False,
        "physical_attestation_verified": False,
        "network_deny_verified": False,
        "safe_to_resume": False,
        "collector_launch_authorized": False,
        "installer_authorized": False,
        "build_authorized": False,
        "deploy_authorized": False,
        "trust_store_modified": False,
        "system_registry_modified": False,
    }


def _strict_values(
    values: Mapping[str, tuple[Any, int]], *,
    reg_binary: int, reg_sz: int, reg_qword: int,
) -> dict[str, Any]:
    """Return only sanitized observed hashes; never treat as root-of-trust."""
    if type(values) is not dict or set(values) != set(READ_VALUES):
        raise ValueError("ANCHOR_VALUES_INCOMPLETE_OR_EXTRA")
    for name in READ_VALUES:
        item = values[name]
        if type(item) is not tuple or len(item) != 2 or type(item[1]) is not int:
            raise ValueError("ANCHOR_VALUE_OR_TYPE_INVALID")
    schema, typ = values["AnchorSchema"]
    if type(schema) is not str or typ != reg_sz or schema != ANCHOR_SCHEMA:
        raise ValueError("ANCHOR_SCHEMA_INVALID")
    keys = []
    for name in ("PolicyAuthorityPublicKey", "OwnerRegistryRootPublicKey"):
        raw, typ = values[name]
        if typ != reg_binary or type(raw) is not bytes or len(raw) != 32:
            raise ValueError("ANCHOR_PUBLIC_KEY_INVALID")
        if raw == b"\x00" * 32:
            raise ValueError("ANCHOR_ZERO_KEY_REJECTED")
        keys.append(raw)
    if keys[0] == keys[1]:
        raise ValueError("ANCHOR_SIGNER_ROLE_COLLISION")
    digest, typ = values["PolicySnapshotDigest"]
    if typ != reg_sz or type(digest) is not str or not _SHA.fullmatch(digest):
        raise ValueError("ANCHOR_POLICY_DIGEST_INVALID")
    epoch, typ = values["PolicyEpoch"]
    if typ != reg_qword or type(epoch) is not int or not 1 <= epoch <= MAX_EPOCH:
        raise ValueError("ANCHOR_EPOCH_INVALID")
    canonical = json.dumps(
        {
            "schema": schema,
            "policy_authority_public_key_sha256": _sha(keys[0]),
            "owner_registry_root_public_key_sha256": _sha(keys[1]),
            "policy_snapshot_digest": digest,
            "policy_epoch": epoch,
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")
    return {
        "anchor_snapshot_observation_digest": _sha(_DOMAIN + canonical),
        "policy_epoch_observed": epoch,
    }


def observe_owner_windows_host_anchor_readonly(
    challenge_nonce: str,
) -> dict[str, Any]:
    """HKLM readback via winreg, exact fixed 64-bit registry view.

    A fresh 256-bit nonce only correlates a diagnostic observation. It does
    NOT authenticate the caller, Windows registry integrity or hardware.
    """
    if sys.platform != "win32":
        return _blocked("WINDOWS_REQUIRED")
    if type(challenge_nonce) is not str or not _NONCE.fullmatch(challenge_nonce):
        return _blocked("EXPLICIT_256_BIT_CHALLENGE_REQUIRED")
    try:
        import winreg
    except ImportError:
        return _blocked("WINDOWS_REGISTRY_API_UNAVAILABLE")

    try:
        # Fixed machine hive and fixed full 64-bit view. No fallback to HKCU,
        # no caller-selected key, no create/write/delete behavior.
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            FIXED_HKLM_PATH,
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as anchor:
            count = winreg.QueryInfoKey(anchor)[1]
            if type(count) is not int or count != len(READ_VALUES):
                return _blocked("ANCHOR_VALUE_COUNT_INVALID")
            values = {
                name: winreg.QueryValueEx(anchor, name)
                for name in READ_VALUES
            }
        validated = _strict_values(
            values, reg_binary=winreg.REG_BINARY,
            reg_sz=winreg.REG_SZ, reg_qword=winreg.REG_QWORD,
        )
    except FileNotFoundError:
        return _blocked("HOST_ANCHOR_ABSENT")
    except PermissionError:
        return _blocked("HOST_ANCHOR_READ_DENIED")
    except OSError:
        return _blocked("HOST_ANCHOR_READ_ERROR")
    except (TypeError, ValueError):
        return _blocked("HOST_ANCHOR_SHAPE_INVALID")

    return {
        **_blocked(""),
        "state": CANDIDATE, "reason": "",
        "native_registry_read_completed": True,
        "anchor_schema_and_types_valid": True,
        "fixed_machine_scope_used": True,
        "anchor_snapshot_observation_digest": validated[
            "anchor_snapshot_observation_digest"],
        "policy_epoch_observed": validated["policy_epoch_observed"],
        "challenge_binding_digest": _sha(
            _DOMAIN + bytes.fromhex(challenge_nonce)
            + bytes.fromhex(
                validated["anchor_snapshot_observation_digest"][7:]
            )
        ),
    }


__all__ = [
    "SCHEMA", "CANDIDATE", "ANCHOR_SCHEMA", "FIXED_HKLM_PATH",
    "READ_VALUES", "observe_owner_windows_host_anchor_readonly",
]
