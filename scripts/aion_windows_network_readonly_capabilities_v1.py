"""Read-only AION Windows network-isolation capability inventory.

NO AppContainer profile, WFP filter, Windows Firewall rule or network socket.
Only:
- derive/FreeSid of a throwaway AppContainer SID (no profile registration);
- WFP engine open/close with documented RPC authentication values.
Reports sanitized API status, NOT an isolation/network-denial attestation.
"""
from __future__ import annotations

import json
import sys


def inventory() -> dict[str, object]:
    report: dict[str, object] = {
        "schema": "AION_WINDOWS_NETWORK_READ_ONLY_API_INVENTORY_V1",
        "state": "UNSUPPORTED_PLATFORM" if sys.platform != "win32" else "READ_ONLY_CAPABILITY_INVENTORY",
        "profile_created": False,
        "wfp_filter_added": False,
        "firewall_rule_modified": False,
        "loopback_exemption_modified": False,
        "socket_test_executed": False,
        "network_deny_verified": False,
        "physical_sandbox_verified": False,
        "install_authorized": False,
    }
    if sys.platform != "win32":
        return report

    import ctypes
    from ctypes import wintypes

    try:
        userenv = ctypes.WinDLL("userenv", use_last_error=True)
        advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        derive = userenv.DeriveAppContainerSidFromAppContainerName
        derive.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)]
        derive.restype = ctypes.c_long
        free_sid = advapi.FreeSid
        free_sid.argtypes = [ctypes.c_void_p]
        free_sid.restype = ctypes.c_void_p

        derived_sid = ctypes.c_void_p()
        try:
            code = derive(
                "AtlasQuantAIONCapabilityReadOnlyInventory",
                ctypes.byref(derived_sid),
            )
            report["appcontainer_sid_derivation_success"] = code == 0 and bool(derived_sid)
            report["appcontainer_sid_derivation_hresult"] = f"0x{code & 0xffffffff:08x}"
        finally:
            if derived_sid:
                free_sid(derived_sid)
    except (AttributeError, OSError, ValueError) as exc:
        report["appcontainer_sid_derivation_success"] = False
        report["appcontainer_failure_category"] = type(exc).__name__

    try:
        fwp = ctypes.WinDLL("fwpuclnt", use_last_error=True)
        open_session = fwp.FwpmEngineOpen0
        open_session.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p,
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
        ]
        open_session.restype = wintypes.DWORD
        close_session = fwp.FwpmEngineClose0
        close_session.argtypes = [ctypes.c_void_p]
        close_session.restype = wintypes.DWORD

        # RPC_C_AUTHN_WINNT=10, documented for FwpmEngineOpen0.
        # No session object -> no filters, no policy objects are created.
        handle = ctypes.c_void_p()
        try:
            status = open_session(None, 10, None, None, ctypes.byref(handle))
            report["wfp_session_open_success"] = status == 0 and bool(handle)
            report["wfp_open_code"] = int(status)
        finally:
            if handle:
                report["wfp_session_close_success"] = close_session(handle) == 0
    except (AttributeError, OSError, ValueError) as exc:
        report["wfp_session_open_success"] = False
        report["wfp_failure_category"] = type(exc).__name__
    return report


if __name__ == "__main__":
    print(json.dumps(inventory(), sort_keys=True))
