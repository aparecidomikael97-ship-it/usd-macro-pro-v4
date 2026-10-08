"""Native Windows CNG KSP algorithm capability READ-ONLY observation V1.

CI/diagnostic only. Do not run on HUMAN_OWNER Windows until separately
approved. Opens exactly Microsoft's Platform Crypto Provider; requests
algorithm support for two fixed identifiers, then frees provider handle.
No key enumerate/open/create/import/export/sign, no TPM attestation, ACL,
registry, network, installation or host security-state modification.

NCryptIsAlgSupported SUCCESS is an *algorithm advertisement* by a selected
provider, NOT hardware identity, a provisionable non-exportable key, TPM
key possession, private-key custody, or a ready Ed25519 AION signing root.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import re
import sys
from typing import Any

SCHEMA = "AION_WINDOWS_NATIVE_PLATFORM_KSP_CAPABILITY_READONLY_V1"
CANDIDATE = "PLATFORM_KSP_ALGORITHM_ADVERTISEMENT_UNTRUSTED"
PROVIDER = "Microsoft Platform Crypto Provider"
ALGORITHMS = ("ECDSA_P256", "ED25519")
NCRYPT_SILENT_FLAG = 0x40
NTE_NOT_SUPPORTED = 0x80090029
_DOMAIN = b"ATLASQUANT:AION:WINDOWS_CNG_READONLY_OBSERVATION:V1\x00"
_NONCE = re.compile(r"[0-9a-f]{64}\Z")
_ALLOWED_STATES = {"ADVERTISED", "NOT_SUPPORTED", "INCONCLUSIVE"}


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "BLOCKED", "reason": reason,
        "provider_name": PROVIDER,
        "provider_opened": False,
        "provider_handle_released": False,
        "algorithm_advertisements": {name: "NOT_QUERIED" for name in ALGORITHMS},
        "native_provider_identity_attested": False,
        "tpm_hardware_present_verified": False,
        "tpm_ownership_verified": False,
        "tpm_ed25519_key_custody_verified": False,
        "p256_tpm_key_custody_verified": False,
        "algorithm_provisionability_verified": False,
        "key_nonexportability_verified": False,
        "private_key_created": False,
        "private_key_opened": False,
        "private_key_enrolled": False,
        "collector_binary_measured": False,
        "anchor_independently_protected": False,
        "antirollback_verified": False,
        "physical_attestation_verified": False,
        "network_deny_verified": False,
        "collector_launch_authorized": False,
        "installer_authorized": False,
        "build_authorized": False,
        "deploy_authorized": False,
        "safe_to_resume": False,
        "host_security_state_modified": False,
    }


def _status(status: Any) -> str:
    """Allow only the documented two status meanings; others inconclusive."""
    if type(status) is not int or not -(2**31) <= status < 2**32:
        return "INCONCLUSIVE"
    raw = status & 0xFFFFFFFF
    if raw == 0:
        return "ADVERTISED"
    if raw == NTE_NOT_SUPPORTED:
        return "NOT_SUPPORTED"
    return "INCONCLUSIVE"


def _load_ncrypt() -> Any:
    """Local trusted-system DLL name, no caller-supplied path or provider."""
    # LOAD_LIBRARY_SEARCH_SYSTEM32 avoids user-controlled DLL search paths.
    dll = ctypes.WinDLL("ncrypt.dll", winmode=0x00000800)
    dll.NCryptOpenStorageProvider.argtypes = (
        ctypes.POINTER(ctypes.c_void_p), ctypes.c_wchar_p, ctypes.c_uint32)
    dll.NCryptOpenStorageProvider.restype = ctypes.c_long
    dll.NCryptIsAlgSupported.argtypes = (
        ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32)
    dll.NCryptIsAlgSupported.restype = ctypes.c_long
    dll.NCryptFreeObject.argtypes = (ctypes.c_void_p,)
    dll.NCryptFreeObject.restype = ctypes.c_long
    return dll


def probe_platform_ksp_algorithm_support_readonly(challenge_nonce: str) -> dict[str, Any]:
    """One bounded provider session; zero key operations and no disk writes."""
    if sys.platform != "win32":
        return _base("WINDOWS_REQUIRED")
    if type(challenge_nonce) is not str or not _NONCE.fullmatch(challenge_nonce):
        return _base("EXPLICIT_256_BIT_CHALLENGE_REQUIRED")
    try:
        api = _load_ncrypt()
    except (OSError, AttributeError, TypeError):
        return _base("NCRYPT_API_UNAVAILABLE")
    provider_handle = ctypes.c_void_p()
    try:
        opened_status = api.NCryptOpenStorageProvider(
            ctypes.byref(provider_handle), PROVIDER, 0)
    except (OSError, ValueError, TypeError):
        return _base("PROVIDER_OPEN_CALL_FAILED")
    if _status(opened_status) != "ADVERTISED":
        return _base("PROVIDER_UNAVAILABLE_OR_ERROR")
    if not provider_handle.value:
        return _base("PROVIDER_OPEN_RETURNED_NULL_HANDLE")
    observed = _base("")
    observed["provider_opened"] = True
    try:
        # Request no UI. Fixed algorithms only; no NCryptEnumerateKeys,
        # NCryptCreatePersistedKey, NCryptOpenKey or private-key operations.
        for name in ALGORITHMS:
            try:
                s = api.NCryptIsAlgSupported(
                    provider_handle, name, NCRYPT_SILENT_FLAG)
            except (OSError, ValueError, TypeError):
                observed["reason"] = "ALGORITHM_QUERY_EXCEPTION"
                break
            observed["algorithm_advertisements"][name] = _status(s)
    finally:
        try:
            freed = api.NCryptFreeObject(provider_handle)
            observed["provider_handle_released"] = (_status(freed) == "ADVERTISED")
        except (OSError, ValueError, TypeError):
            observed["provider_handle_released"] = False
    if not observed["provider_handle_released"]:
        observed["reason"] = "PROVIDER_HANDLE_RELEASE_UNCONFIRMED"
        return observed
    if observed["reason"]:
        return observed
    if any(observed["algorithm_advertisements"][alg] not in _ALLOWED_STATES
           for alg in ALGORITHMS):
        observed["reason"] = "ALGORITHM_QUERY_RESULT_INVALID"
        return observed
    if any(observed["algorithm_advertisements"][alg] == "INCONCLUSIVE"
           for alg in ALGORITHMS):
        observed["reason"] = "ALGORITHM_QUERY_INCONCLUSIVE"
        return observed
    observed["state"] = CANDIDATE
    sanitized = json.dumps(
        observed["algorithm_advertisements"],
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")
    observed["challenge_binding_digest"] = _digest(
        _DOMAIN + bytes.fromhex(challenge_nonce) + sanitized)
    return observed


__all__ = [
    "SCHEMA", "CANDIDATE", "PROVIDER", "ALGORITHMS", "NTE_NOT_SUPPORTED",
    "probe_platform_ksp_algorithm_support_readonly",
]
