"""AION CNG silent signing-algorithm enumeration — CI ONLY, fail-closed.

Uses documented NCryptEnumAlgorithms (NCRYPT_SIGNATURE_OPERATION and
NCRYPT_SILENT_FLAG) instead of the rejected NCryptIsAlgSupported mode
or potentially interactive dwFlags=0. Enumerates *algorithm names*,
NEVER keys; it does not prove TPM/key custody or authorize installation.

Do not execute on owner's physical Windows without separate approved scope.
The CI-only environment check is not a secure identity or host attestation.
"""
from __future__ import annotations

import ctypes
import os
import re
import sys
from typing import Any

from atlasquant_aion_windows_native_cng_ksp_readonly_capability_v1 import (
    PROVIDER, NCRYPT_SILENT_FLAG, _load_ncrypt,
)
from atlasquant_aion_native_cng_status_diagnostic_v2 import decode_status

SCHEMA = "AION_CNG_SILENT_SIGNATURE_ALGORITHM_ENUM_CI_V1"
CANDIDATE = "SILENT_SIGNATURE_ALGORITHMS_LISTED_UNTRUSTED"
SIGNATURE_OPERATION = 0x00000010
MAX_ALG_COUNT = 64
TARGET_NAMES = ("ECDSA_P256", "ED25519")
_ALLOWED_NAME = re.compile(r"[A-Za-z0-9_.-]{1,128}\Z")
_NONCE = re.compile(r"[0-9a-f]{64}\Z")


class NCryptAlgorithmName(ctypes.Structure):
    _fields_ = [
        ("pszName", ctypes.c_wchar_p),
        ("dwClass", ctypes.c_uint32),
        ("dwAlgOperations", ctypes.c_uint32),
        ("dwFlags", ctypes.c_uint32),
    ]


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "BLOCKED", "reason": reason,
        "provider_name": PROVIDER,
        "requested_operation": "NCRYPT_SIGNATURE_OPERATION",
        "query_flags": "NCRYPT_SILENT_FLAG",
        "provider_open_status": None,
        "enumeration_status": None,
        "buffer_free_status": None,
        "provider_free_status": None,
        "algorithm_name_count": None,
        "target_algorithm_names": {x: "NOT_QUERIED" for x in TARGET_NAMES},
        "provider_handle_released": False,
        "result_buffer_released": False,
        "provider_ui_suppression_requested": True,
        "actual_no_ui_physically_verified": False,
        "owner_pc_execution_authorized_by_code": False,
        "independently_attested_provider_identity": False,
        "tpm_presence_verified": False,
        "tpm_ed25519_key_custody_verified": False,
        "p256_tpm_key_custody_verified": False,
        "algorithm_provisionability_verified": False,
        "key_nonexportability_verified": False,
        "private_key_created": False,
        "private_key_opened": False,
        "private_key_enumerated": False,
        "private_key_enrolled": False,
        "host_security_state_modified": False,
        "physical_attestation_verified": False,
        "network_deny_verified": False,
        "collector_launch_authorized": False,
        "installer_authorized": False,
        "build_authorized": False,
        "deploy_authorized": False,
        "safe_to_resume": False,
    }


def _ci_only() -> bool:
    """Safety convenience guard only. Environment variables are spoofable."""
    return (
        sys.platform == "win32"
        and os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_EVENT_NAME") == "pull_request"
        and os.environ.get("RUNNER_OS") == "Windows"
        and os.environ.get("GITHUB_REPOSITORY")
        == "aparecidomikael97-ship-it/usd-macro-pro-v4"
    )


def _classify_names(
    records: list[tuple[Any, Any, Any]],
) -> dict[str, str]:
    """Validate small, well-formed signature-only result; expose targets only."""
    if not isinstance(records, list) or len(records) > MAX_ALG_COUNT:
        raise ValueError("ENUM_COUNT_INVALID")
    names: set[str] = set()
    for name, alg_class, alg_operations in records:
        if (type(name) is not str or not _ALLOWED_NAME.fullmatch(name)
            or type(alg_class) is not int or type(alg_operations) is not int
            or alg_class != 5
            or not alg_operations & SIGNATURE_OPERATION
            or name in names):
            raise ValueError("ENUM_RECORD_MALFORMED")
        names.add(name)
    return {x: ("LISTED" if x in names else "NOT_LISTED") for x in TARGET_NAMES}


def observe_silent_signature_algorithms_ci_only(challenge_nonce: str) -> dict[str, Any]:
    if type(challenge_nonce) is not str or not _NONCE.fullmatch(challenge_nonce):
        return _base("CHALLENGE_REQUIRED")
    if not _ci_only():
        return _base("DISPOSABLE_GITHUB_WINDOWS_PR_CI_REQUIRED")
    out = _base("")
    try:
        api = _load_ncrypt()
        api.NCryptEnumAlgorithms.argtypes = (
            ctypes.c_void_p, ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.POINTER(NCryptAlgorithmName)),
            ctypes.c_uint32,
        )
        api.NCryptEnumAlgorithms.restype = ctypes.c_long
        api.NCryptFreeBuffer.argtypes = (ctypes.c_void_p,)
        api.NCryptFreeBuffer.restype = ctypes.c_long
    except (OSError, TypeError, AttributeError):
        return _base("NCRYPT_API_UNAVAILABLE")
    provider = ctypes.c_void_p()
    try:
        open_rc = api.NCryptOpenStorageProvider(
            ctypes.byref(provider), PROVIDER, 0)
        out["provider_open_status"] = decode_status(open_rc)
    except (OSError, TypeError, ValueError):
        return _base("PROVIDER_OPEN_EXCEPTION")
    if out["provider_open_status"]["classification"] != "ADVERTISED":
        out["reason"] = "PROVIDER_OPEN_FAILED"
        return out
    if not provider.value:
        out["reason"] = "PROVIDER_NULL_HANDLE"
        return out
    count = ctypes.c_uint32()
    alg_ptr = ctypes.POINTER(NCryptAlgorithmName)()
    try:
        try:
            status = api.NCryptEnumAlgorithms(
                provider, SIGNATURE_OPERATION,
                ctypes.byref(count), ctypes.byref(alg_ptr),
                NCRYPT_SILENT_FLAG,
            )
            out["enumeration_status"] = decode_status(status)
            if out["enumeration_status"]["classification"] != "ADVERTISED":
                out["reason"] = "SILENT_ENUM_FAILED"
            elif count.value > MAX_ALG_COUNT:
                out["reason"] = "SILENT_ENUM_EXCESSIVE_COUNT"
            elif count.value and not bool(alg_ptr):
                out["reason"] = "SILENT_ENUM_NULL_LIST"
            else:
                rows = [
                    (alg_ptr[i].pszName, int(alg_ptr[i].dwClass),
                     int(alg_ptr[i].dwAlgOperations))
                    for i in range(count.value)
                ]
                out["target_algorithm_names"] = _classify_names(rows)
                out["algorithm_name_count"] = count.value
        except (OSError, TypeError, ValueError, IndexError):
            out["reason"] = "SILENT_ENUM_INVALID_RESULT"
        finally:
            if bool(alg_ptr):
                try:
                    freed = api.NCryptFreeBuffer(ctypes.cast(alg_ptr, ctypes.c_void_p))
                    out["buffer_free_status"] = decode_status(freed)
                    out["result_buffer_released"] = (
                        out["buffer_free_status"]["classification"] == "ADVERTISED")
                except (OSError, TypeError, ValueError):
                    out["reason"] = "ALGORITHM_BUFFER_RELEASE_EXCEPTION"
            else:
                out["result_buffer_released"] = True
    finally:
        try:
            freed = api.NCryptFreeObject(provider)
            out["provider_free_status"] = decode_status(freed)
            out["provider_handle_released"] = (
                out["provider_free_status"]["classification"] == "ADVERTISED")
        except (OSError, TypeError, ValueError):
            out["reason"] = "PROVIDER_RELEASE_EXCEPTION"
    if not (out["provider_handle_released"] and out["result_buffer_released"]):
        out["reason"] = "RELEASE_UNCONFIRMED"
        return out
    if out["reason"]:
        return out
    out["state"] = CANDIDATE
    return out


__all__ = [
    "SCHEMA", "CANDIDATE", "SIGNATURE_OPERATION",
    "observe_silent_signature_algorithms_ci_only",
]
