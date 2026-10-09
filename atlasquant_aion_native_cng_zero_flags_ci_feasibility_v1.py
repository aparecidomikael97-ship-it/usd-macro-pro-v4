"""AION native CNG zero-flags variant — DISPOSABLE GITHUB CI ONLY.

This module is NOT cleared to run on a human owner's PC. Contrary to
NCRYPT_SILENT_FLAG, passing dwFlags=0 to NCryptIsAlgSupported does NOT
contractually suppress user interface. Therefore successful CI results
cannot authorize interactive or unattended physical Windows usage.

Only three native functions (provider open, algorithm status, free). Zero
key operations, registry access, installation or TPM mutation.
"""
from __future__ import annotations

import os
import re
import sys
from typing import Any

from atlasquant_aion_windows_native_cng_ksp_readonly_capability_v1 import (
    _load_ncrypt, PROVIDER, ALGORITHMS,
)
from atlasquant_aion_native_cng_status_diagnostic_v2 import decode_status

SCHEMA = "AION_PLATFORM_KSP_ZERO_FLAGS_CI_FEASIBILITY_V1"
STATUS = "ZERO_FLAGS_DISPOSABLE_CI_OBSERVATION_UNTRUSTED"
ZERO_FLAGS = 0
_NONCE = re.compile(r"[0-9a-f]{64}\Z")


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "reason": reason,
        "query_flags": ZERO_FLAGS,
        "provider": PROVIDER,
        "open_status": None,
        "algorithm_statuses": {k: None for k in ALGORITHMS},
        "free_status": None,
        "provider_opened": False,
        "provider_handle_released": False,
        "native_execution_attempted": False,
        "zero_flags_may_allow_provider_ui": True,
        "ui_suppression_verified": False,
        "owner_pc_execution_authorized_by_code": False,
        "physical_host_safety_verified": False,
        "tpm_key_custody_verified": False,
        "private_key_created": False,
        "private_key_opened": False,
        "private_key_enrolled": False,
        "host_security_state_modified": False,
        "installer_authorized": False,
        "build_authorized": False,
        "deploy_authorized": False,
        "safe_to_resume": False,
    }


def _github_ci_only() -> bool:
    """Convenience CI gate, NOT identity attestation; environment is spoofable."""
    return (
        sys.platform == "win32"
        and os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_EVENT_NAME") == "pull_request"
        and os.environ.get("RUNNER_OS") == "Windows"
        and os.environ.get("GITHUB_REPOSITORY")
        == "aparecidomikael97-ship-it/usd-macro-pro-v4"
    )


def probe_zero_flags_ci_feasibility_only(challenge_nonce: str) -> dict[str, Any]:
    """Never run from Desktop Commander on owner computer.

    May run on an isolated/disposable CI runner. A provider can show UI
    because flags=0; CI job timeout is a **resource guard**, not a proof
    that no UI was shown or that owner execution is safe.
    """
    if type(challenge_nonce) is not str or not _NONCE.fullmatch(challenge_nonce):
        return _blocked("CHALLENGE_REQUIRED")
    if not _github_ci_only():
        return _blocked("DISPOSABLE_GITHUB_WINDOWS_PR_CI_REQUIRED")
    import ctypes
    result = _blocked("")
    try:
        api = _load_ncrypt()
    except (OSError, AttributeError, TypeError):
        return _blocked("SYSTEM_NCRYPT_UNAVAILABLE")
    handle = ctypes.c_void_p()
    result["native_execution_attempted"] = True
    try:
        raw = api.NCryptOpenStorageProvider(
            ctypes.byref(handle), PROVIDER, 0)
        result["open_status"] = decode_status(raw)
    except (OSError, ValueError, TypeError):
        result["reason"] = "PROVIDER_OPEN_EXCEPTION"
        return result
    if result["open_status"]["classification"] != "ADVERTISED":
        result["reason"] = "PROVIDER_OPEN_FAILED"
        return result
    if not handle.value:
        result["reason"] = "PROVIDER_OPEN_NULL_HANDLE"
        return result
    result["provider_opened"] = True
    try:
        for alg in ALGORITHMS:
            try:
                raw = api.NCryptIsAlgSupported(handle, alg, ZERO_FLAGS)
            except (OSError, ValueError, TypeError):
                result["reason"] = "ALGORITHM_QUERY_EXCEPTION"
                break
            result["algorithm_statuses"][alg] = decode_status(raw)
    finally:
        try:
            result["free_status"] = decode_status(api.NCryptFreeObject(handle))
            result["provider_handle_released"] = (
                result["free_status"]["classification"] == "ADVERTISED"
            )
        except (OSError, ValueError, TypeError):
            result["reason"] = "PROVIDER_HANDLE_RELEASE_EXCEPTION"
    if not result["provider_handle_released"]:
        result["reason"] = "PROVIDER_HANDLE_RELEASE_UNCONFIRMED"
        return result
    if result["reason"]:
        return result
    if any(
        result["algorithm_statuses"][alg]["classification"] == "INCONCLUSIVE"
        for alg in ALGORITHMS
    ):
        result["reason"] = "ALGORITHM_STATUS_INCONCLUSIVE"
        return result
    result["state"] = STATUS
    return result


__all__ = ("SCHEMA", "STATUS", "ZERO_FLAGS", "probe_zero_flags_ci_feasibility_only")
