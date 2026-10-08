"""AION AppContainer process token SID/capability readback — read-only V1.

The caller must ALREADY hold a Windows process handle with query rights.
No profile registration, process creation, networking, ACL edits, WFP/Firewall,
SID disclosure, registry writes or AION installation occur in this module.

A matching SID/zero capabilities only becomes an UNTRUSTED CANDIDATE:
the supplied process handle and expected name are NOT an authenticated
owner-host or independently signed physical attestation.
"""
from __future__ import annotations

import re
import sys
from typing import Any

SCHEMA = "AION_WINDOWS_APPCONTAINER_TOKEN_READONLY_V1"
MATCH_CANDIDATE = "NATIVE_TOKEN_IDENTITY_CANDIDATE_UNTRUSTED"
NOT_READY = "NOT_VERIFIED"
PROFILE_RE = re.compile(r"^AtlasQuantAIONProbe[0-9a-f]{12}$")
TOKEN_QUERY = 0x0008
TOKEN_IS_APPCONTAINER = 29
TOKEN_CAPABILITIES = 30
TOKEN_APPCONTAINER_SID = 31
MAX_TOKEN_QUERY_BYTES = 65536
SID_LENGTH = 8


def _report(reason: str, *, state: str = NOT_READY, capacity: int | None = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": state,
        "reason": reason,
        "capability_count": capacity,
        "physical_attestation_verified": False,
        "real_host_identity_verified": False,
        "process_handle_origin_verified": False,
        "network_deny_verified": False,
        "installer_authorized": False,
        "build_authorized": False,
        "deploy_authorized": False,
    }


def evaluate_untrusted_token_readback(
    *,
    profile_name: Any,
    appcontainer_flag: Any,
    sid_matches: Any,
    capability_count: Any,
    all_queries_succeeded: Any,
) -> dict[str, Any]:
    """Pure decision over untrusted readings; never grant any authority."""
    if type(profile_name) is not str or PROFILE_RE.fullmatch(profile_name) is None:
        return _report("PROFILE_NAME_NOT_SCOPED_TO_EPHEMERAL_AION_PROBE")
    if any(type(x) is not bool for x in (appcontainer_flag, sid_matches, all_queries_succeeded)):
        return _report("TOKEN_BOOL_OBSERVATION_INVALID")
    if type(capability_count) is not int or not (0 <= capability_count <= 4096):
        return _report("TOKEN_CAPABILITY_COUNT_INVALID")
    if not all_queries_succeeded:
        return _report("TOKEN_READBACK_INCOMPLETE")
    if not appcontainer_flag:
        return _report("TOKEN_NOT_APPCONTAINER", capacity=capability_count)
    if not sid_matches:
        return _report("TOKEN_SID_DOES_NOT_MATCH_EXPECTED_PROFILE", capacity=capability_count)
    if capability_count != 0:
        return _report("TOKEN_HAS_NETWORK_OR_OTHER_CAPABILITIES", capacity=capability_count)
    return _report(
        "MATCHING_SID_AND_ZERO_CAPABILITIES_STILL_REQUIRE_INDEPENDENT_ATTESTATION",
        state=MATCH_CANDIDATE,
        capacity=0,
    )


def inspect_windows_process_handle(process_handle: Any, expected_profile_name: Any) -> dict[str, Any]:
    """Read a held process handle; NEVER resolve an untrusted PID to a handle.

    The handle must come from a future trusted CREATE_SUSPENDED launcher before
    it resumes the exact intended child. This V1 cannot establish that fact.
    """
    if type(expected_profile_name) is not str or PROFILE_RE.fullmatch(expected_profile_name) is None:
        return _report("PROFILE_NAME_NOT_SCOPED_TO_EPHEMERAL_AION_PROBE")
    if sys.platform != "win32":
        return _report("UNSUPPORTED_PLATFORM")
    if type(process_handle) is not int or process_handle == 0:
        return _report("PROCESS_HANDLE_REQUIRED")

    import ctypes
    from ctypes import wintypes as W

    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    userenv = ctypes.WinDLL("userenv", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)

    adv.OpenProcessToken.argtypes = [W.HANDLE, W.DWORD, ctypes.POINTER(W.HANDLE)]
    adv.OpenProcessToken.restype = W.BOOL
    adv.GetTokenInformation.argtypes = [
        W.HANDLE, ctypes.c_int, ctypes.c_void_p, W.DWORD, ctypes.POINTER(W.DWORD),
    ]
    adv.GetTokenInformation.restype = W.BOOL
    adv.EqualSid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    adv.EqualSid.restype = W.BOOL
    adv.FreeSid.argtypes = [ctypes.c_void_p]
    adv.FreeSid.restype = ctypes.c_void_p
    userenv.DeriveAppContainerSidFromAppContainerName.argtypes = [
        W.LPCWSTR, ctypes.POINTER(ctypes.c_void_p),
    ]
    userenv.DeriveAppContainerSidFromAppContainerName.restype = ctypes.c_long
    kernel.CloseHandle.argtypes = [W.HANDLE]
    kernel.CloseHandle.restype = W.BOOL

    def read_token_blob(token: W.HANDLE, info_class: int) -> ctypes.Array[ctypes.c_char] | None:
        needed = W.DWORD(0)
        adv.GetTokenInformation(token, info_class, None, 0, ctypes.byref(needed))
        if not (4 <= needed.value <= MAX_TOKEN_QUERY_BYTES):
            return None
        buffer = ctypes.create_string_buffer(needed.value)
        returned = W.DWORD(0)
        if not adv.GetTokenInformation(
            token, info_class, buffer, needed.value, ctypes.byref(returned),
        ):
            return None
        if returned.value < 4 or returned.value > needed.value:
            return None
        return buffer

    token = W.HANDLE()
    expected_sid = ctypes.c_void_p()
    try:
        if not adv.OpenProcessToken(
            W.HANDLE(process_handle), TOKEN_QUERY, ctypes.byref(token),
        ):
            return _report("OPEN_PROCESS_TOKEN_FAILED")

        is_app = W.DWORD()
        returned_size = W.DWORD()
        if not adv.GetTokenInformation(
            token, TOKEN_IS_APPCONTAINER, ctypes.byref(is_app),
            ctypes.sizeof(is_app), ctypes.byref(returned_size),
        ):
            return _report("TOKEN_IS_APPCONTAINER_QUERY_FAILED")
        if returned_size.value != ctypes.sizeof(is_app):
            return _report("TOKEN_IS_APPCONTAINER_SIZE_MISMATCH")
        if is_app.value != 1:
            return _report("TOKEN_NOT_APPCONTAINER")

        capabilities = read_token_blob(token, TOKEN_CAPABILITIES)
        if capabilities is None:
            return _report("TOKEN_CAPABILITIES_QUERY_FAILED")
        count = int.from_bytes(capabilities.raw[:4], "little")
        if count > 4096:
            return _report("TOKEN_CAPABILITY_COUNT_INVALID")
        if count != 0:
            return _report("TOKEN_HAS_NETWORK_OR_OTHER_CAPABILITIES", capacity=count)

        sid_record = read_token_blob(token, TOKEN_APPCONTAINER_SID)
        if sid_record is None or ctypes.sizeof(ctypes.c_void_p) > len(sid_record):
            return _report("TOKEN_APPCONTAINER_SID_QUERY_FAILED")
        child_sid = ctypes.cast(sid_record, ctypes.POINTER(ctypes.c_void_p))[0]
        if not child_sid:
            return _report("TOKEN_APPCONTAINER_SID_MISSING")
        hresult = userenv.DeriveAppContainerSidFromAppContainerName(
            expected_profile_name, ctypes.byref(expected_sid),
        )
        if hresult != 0 or not expected_sid:
            return _report("EXPECTED_PROFILE_SID_DERIVATION_FAILED")
        match = bool(adv.EqualSid(child_sid, expected_sid))
        return evaluate_untrusted_token_readback(
            profile_name=expected_profile_name,
            appcontainer_flag=True,
            sid_matches=match,
            capability_count=count,
            all_queries_succeeded=True,
        )
    except (AttributeError, OSError, ValueError, TypeError):
        return _report("NATIVE_WIN32_READBACK_UNAVAILABLE")
    finally:
        if expected_sid:
            adv.FreeSid(expected_sid)
        if token:
            kernel.CloseHandle(token)


if __name__ == "__main__":
    # Deliberately no CLI to inspect arbitrary PIDs or launch processes.
    # Only a future trusted launcher can supply the handle.
    raise SystemExit("This is a read-only library, not an owner-PC probe command.")
