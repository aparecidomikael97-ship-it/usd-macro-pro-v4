"""NCrypt status-only diagnostic V2 (CI-only; no owner PC execution).

Extends #1100's same three read-only native functions by retaining exact
SECURITY_STATUS error codes (bounded sanitized 32-bit hexadecimal). No key
creation/enumeration, no registry writes, no TPM-attestation claims.
The native probe MUST NOT run on a user's device without new explicit
permission after code review. CI Windows runs on disposable GitHub runner.
"""
from __future__ import annotations

import ctypes
import re
import sys
from typing import Any

from atlasquant_aion_windows_native_cng_ksp_readonly_capability_v1 import (
    PROVIDER, ALGORITHMS, NCRYPT_SILENT_FLAG, _load_ncrypt,
)

SCHEMA = "AION_NATIVE_PLATFORM_KSP_STATUS_DIAGNOSTIC_V2"
MAX_STATUS = (1 << 32) - 1
_NONCE = re.compile(r"[0-9a-f]{64}\Z")
_ERRORS = {
    0x00000000: ("ADVERTISED", "SUCCESS"),
    0x80090029: ("NOT_SUPPORTED", "NTE_NOT_SUPPORTED"),
    0x80090009: ("INCONCLUSIVE", "NTE_BAD_FLAGS"),
    0x80090026: ("INCONCLUSIVE", "NTE_INVALID_HANDLE"),
    0x80090027: ("INCONCLUSIVE", "NTE_INVALID_PARAMETER"),
    0x80090022: ("INCONCLUSIVE", "NTE_SILENT_CONTEXT"),
    0x8009002E: ("INCONCLUSIVE", "NTE_UI_REQUIRED"),
    0x80090010: ("INCONCLUSIVE", "NTE_PERM"),
    0x80090020: ("INCONCLUSIVE", "NTE_FAIL"),
    0x80090008: ("INCONCLUSIVE", "NTE_BAD_ALGID"),
    0x8009002D: ("INCONCLUSIVE", "NTE_INTERNAL_ERROR"),
    0x80090030: ("INCONCLUSIVE", "NTE_DEVICE_NOT_READY"),
}


def decode_status(raw: Any) -> dict[str, str | None]:
    """Treat signed/unsigned Windows LONG the same. Never imply support."""
    if type(raw) is not int or not -(1 << 31) <= raw <= MAX_STATUS:
        return {
            "status_hex": None,
            "classification": "INCONCLUSIVE",
            "reason": "MALFORMED_NATIVE_STATUS",
        }
    unsigned = raw & MAX_STATUS
    classification, reason = _ERRORS.get(
        unsigned, ("INCONCLUSIVE", "UNKNOWN_NATIVE_STATUS"))
    return {
        "status_hex": "0x%08X" % unsigned,
        "classification": classification,
        "reason": reason,
    }


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "reason": reason,
        "provider_name": PROVIDER,
        "provider_opened": False,
        "handle_release_confirmed": False,
        "open_status": None,
        "free_status": None,
        "algorithm_statuses": {alg: None for alg in ALGORITHMS},
        "tpm_present_verified": False,
        "native_provider_identity_attested": False,
        "tpm_ed25519_key_custody_verified": False,
        "p256_tpm_key_custody_verified": False,
        "key_provisionability_verified": False,
        "key_nonexportability_verified": False,
        "private_key_created": False,
        "private_key_opened": False,
        "private_key_enrolled": False,
        "system_security_state_modified": False,
        "network_deny_verified": False,
        "physical_attestation_verified": False,
        "installer_authorized": False,
        "build_authorized": False,
        "deploy_authorized": False,
        "safe_to_resume": False,
    }


def probe_native_platform_provider_status_codes_readonly(challenge_nonce: str) -> dict[str, Any]:
    """Same native API scope as #1100, with diagnostic status codes added."""
    if sys.platform != "win32":
        return _base("WINDOWS_REQUIRED")
    if type(challenge_nonce) is not str or not _NONCE.fullmatch(challenge_nonce):
        return _base("CHALLENGE_REQUIRED")
    try:
        api = _load_ncrypt()
    except (OSError, AttributeError, TypeError):
        return _base("SYSTEM_NCRYPT_UNAVAILABLE")
    h = ctypes.c_void_p()
    out = _base("")
    try:
        rc = api.NCryptOpenStorageProvider(ctypes.byref(h), PROVIDER, 0)
        out["open_status"] = decode_status(rc)
    except (OSError, TypeError, ValueError):
        return _base("PROVIDER_OPEN_EXCEPTION")
    if out["open_status"]["classification"] != "ADVERTISED":
        out["reason"] = "PROVIDER_OPEN_FAILED"
        return out
    if not h.value:
        out["reason"] = "PROVIDER_OPEN_NULL_HANDLE"
        return out
    out["provider_opened"] = True
    try:
        for alg in ALGORITHMS:
            try:
                rc = api.NCryptIsAlgSupported(h, alg, NCRYPT_SILENT_FLAG)
            except (OSError, TypeError, ValueError):
                out["reason"] = "QUERY_EXCEPTION"
                break
            out["algorithm_statuses"][alg] = decode_status(rc)
    finally:
        try:
            free_rc = api.NCryptFreeObject(h)
            out["free_status"] = decode_status(free_rc)
            out["handle_release_confirmed"] = (
                out["free_status"]["classification"] == "ADVERTISED")
        except (OSError, TypeError, ValueError):
            out["reason"] = "HANDLE_RELEASE_EXCEPTION"
    if not out["handle_release_confirmed"]:
        out["state"] = "BLOCKED"
        out["reason"] = "HANDLE_RELEASE_UNCONFIRMED"
        return out
    if out["reason"]:
        return out
    if any(out["algorithm_statuses"][a]["classification"] == "INCONCLUSIVE"
           for a in ALGORITHMS):
        out["reason"] = "NATIVE_ALGORITHM_STATUS_INCONCLUSIVE"
        return out
    out["state"] = "READONLY_NATIVE_STATUS_DIAGNOSTIC_UNTRUSTED"
    return out


__all__ = [
    "SCHEMA", "decode_status", "probe_native_platform_provider_status_codes_readonly",
]
