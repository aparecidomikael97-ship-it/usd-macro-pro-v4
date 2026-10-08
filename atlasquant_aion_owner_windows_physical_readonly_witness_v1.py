"""AION owner-Windows read-only physical-process observation V1.

Non-privileged LOCAL readback only. No child, AppContainer profile, network,
WFP/Firewall, registry, ACL, package install or execution permission.
Explicit CLI opt-in is a scope fence, NOT owner authentication.
The resulting facts are NOT independently attested or production trusted.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as W
from hashlib import sha256
import json
import ntpath
import os
import re
import sys
import time
from typing import Any

SCHEMA = "AION_OWNER_WINDOWS_PHYSICAL_READONLY_WITNESS_V1"
STATE = "PHYSICAL_READONLY_OBSERVATION_UNTRUSTED"
NONCE = re.compile(r"[0-9a-f]{64}\Z")
OPT_IN = "--owner-authorized-physical-readonly"
DWORD_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
OPEN_EXISTING = 3
TOKEN_QUERY = 0x0008


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "BLOCKED", "reason": reason,
        "evidence_collected": False, "signature_trusted": False,
        "physical_attestation_verified": False, "network_deny_verified": False,
        "safe_to_resume": False, "installer_authorized": False,
        "build_authorized": False, "deploy_authorized": False,
    }


def _source_guard(argv: list[str], *, platform: str) -> bool:
    return (platform == "win32" and len(argv) == 3
            and argv[1] == OPT_IN and bool(NONCE.fullmatch(argv[2])))


def collect_readonly_witness(nonce: str) -> dict[str, Any]:
    """Observe only the current diagnostic Python process and its executable.

    Caller must supply a 32-byte challenge from a separate host controller.
    Neither that controller nor the collector is authenticated by this code.
    """
    if sys.platform != "win32" or type(nonce) is not str or not NONCE.fullmatch(nonce):
        return _blocked("WINDOWS_AND_EXPLICIT_HOST_CHALLENGE_REQUIRED")
    from ctypes import byref, POINTER

    class FILETIME(ctypes.Structure):
        _fields_ = [("low", W.DWORD), ("high", W.DWORD)]

    class FILE_INFO(ctypes.Structure):
        _fields_ = [
            ("attributes", W.DWORD), ("created", FILETIME), ("accessed", FILETIME),
            ("modified", FILETIME), ("volume", W.DWORD),
            ("size_high", W.DWORD), ("size_low", W.DWORD),
            ("links", W.DWORD), ("index_high", W.DWORD), ("index_low", W.DWORD),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel.CreateFileW.argtypes = [
        W.LPCWSTR, W.DWORD, W.DWORD, ctypes.c_void_p,
        W.DWORD, W.DWORD, W.HANDLE,
    ]
    kernel.CreateFileW.restype = W.HANDLE
    kernel.GetFileInformationByHandle.argtypes = [W.HANDLE, POINTER(FILE_INFO)]
    kernel.GetFileInformationByHandle.restype = W.BOOL
    kernel.SetFilePointerEx.argtypes = [
        W.HANDLE, ctypes.c_int64, ctypes.c_void_p, W.DWORD,
    ]
    kernel.SetFilePointerEx.restype = W.BOOL
    kernel.ReadFile.argtypes = [
        W.HANDLE, ctypes.c_void_p, W.DWORD, POINTER(W.DWORD), ctypes.c_void_p,
    ]
    kernel.ReadFile.restype = W.BOOL
    kernel.GetCurrentProcess.restype = W.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [
        W.HANDLE, W.DWORD, W.LPWSTR, POINTER(W.DWORD),
    ]
    kernel.QueryFullProcessImageNameW.restype = W.BOOL
    kernel.CloseHandle.argtypes = [W.HANDLE]
    kernel.CloseHandle.restype = W.BOOL
    advapi.OpenProcessToken.argtypes = [W.HANDLE, W.DWORD, POINTER(W.HANDLE)]
    advapi.OpenProcessToken.restype = W.BOOL
    advapi.GetTokenInformation.argtypes = [
        W.HANDLE, W.DWORD, ctypes.c_void_p, W.DWORD, POINTER(W.DWORD),
    ]
    advapi.GetTokenInformation.restype = W.BOOL
    advapi.IsTokenRestricted.argtypes = [W.HANDLE]
    advapi.IsTokenRestricted.restype = W.BOOL

    held = None
    token = W.HANDLE()
    closed_file = False
    closed_token = False
    try:
        executable = sys.executable
        held = kernel.CreateFileW(
            executable, DWORD_READ, FILE_SHARE_READ, None, OPEN_EXISTING, 0, None,
        )
        if not held or held == ctypes.c_void_p(-1).value:
            return _blocked("HELD_READ_ONLY_IMAGE_OPEN_FAILED")

        def identity():
            info = FILE_INFO()
            if not kernel.GetFileInformationByHandle(held, byref(info)):
                raise OSError("FILE_IDENTITY_READ_FAILED")
            return (
                info.volume, info.index_high, info.index_low,
                info.size_high, info.size_low, info.modified.high,
                info.modified.low,
            )

        def held_digest():
            if not kernel.SetFilePointerEx(held, 0, None, 0):
                raise OSError("FILE_REWIND_FAILED")
            digest = sha256()
            buffer = ctypes.create_string_buffer(65536)
            count = W.DWORD()
            for _ in range(8192):
                if not kernel.ReadFile(
                    held, buffer, len(buffer), byref(count), None,
                ):
                    raise OSError("FILE_READ_FAILED")
                if count.value == 0:
                    return digest.hexdigest()
                digest.update(buffer.raw[:count.value])
            raise OSError("FILE_TOO_LARGE_FOR_BOUNDED_READ")

        before_identity = identity()
        before_digest = held_digest()
        actual_path = ctypes.create_unicode_buffer(32768)
        size = W.DWORD(len(actual_path))
        current = kernel.GetCurrentProcess()
        if not kernel.QueryFullProcessImageNameW(
            current, 0, actual_path, byref(size),
        ):
            return _blocked("PROCESS_IMAGE_READBACK_FAILED")
        path_matches = ntpath.normcase(ntpath.normpath(actual_path.value)) == (
            ntpath.normcase(ntpath.normpath(executable))
        )
        if not advapi.OpenProcessToken(current, TOKEN_QUERY, byref(token)):
            return _blocked("PROCESS_TOKEN_OPEN_FAILED")
        app_container = W.DWORD()
        needed = W.DWORD()
        token_ok = bool(advapi.GetTokenInformation(
            token, 29, byref(app_container),
            ctypes.sizeof(app_container), byref(needed),
        ))
        restricted = bool(advapi.IsTokenRestricted(token))
        after_digest = held_digest()
        after_identity = identity()
        ok = (
            path_matches and token_ok and before_digest == after_digest
            and before_identity == after_identity
        )
        result = {
            "schema": SCHEMA,
            "state": STATE if ok else "BLOCKED",
            "reason": "" if ok else "IMAGE_OR_TOKEN_READBACK_MISMATCH",
            "challenge_digest": sha256(
                b"ATLASQUANT:AION:PHYSICAL_READONLY_WITNESS:V1\x00"
                + bytes.fromhex(nonce)
            ).hexdigest(),
            "observed_at_epoch": int(time.time()),
            "held_image_file_share_read_only": True,
            "image_path_matches_current_process": path_matches,
            "image_sha256": before_digest,
            "image_size_bytes": ((before_identity[3] << 32) | before_identity[4]),
            "file_identity_stable": before_identity == after_identity,
            "digest_pre_post_stable": before_digest == after_digest,
            "native_token_readback": token_ok,
            "token_is_appcontainer": bool(app_container.value) if token_ok else None,
            "token_is_restricted": restricted,
            "physical_owner_process_not_launched": True,
            "network_probe_executed": False,
            "child_created": False,
            "profile_created": False,
            "firewall_modified": False,
            "signed_by_enrolled_collector": False,
            "independent_collector_verified": False,
            "evidence_collected": ok,
            "signature_trusted": False,
            "physical_attestation_verified": False,
            "network_deny_verified": False,
            "safe_to_resume": False,
            "installer_authorized": False,
            "build_authorized": False,
            "deploy_authorized": False,
        }
        return result
    except (OSError, ValueError, OverflowError):
        return _blocked("NATIVE_READ_ONLY_OBSERVATION_FAILED")
    finally:
        if token:
            closed_token = bool(kernel.CloseHandle(token))
        if held and held != ctypes.c_void_p(-1).value:
            closed_file = bool(kernel.CloseHandle(held))
        # CloseHandle is always reached; do not treat this runner as an
        # independently trusted source of handle-closure attestation.
        _ = (closed_file, closed_token)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if not _source_guard(argv, platform=sys.platform):
        print(json.dumps(_blocked("EXPLICIT_WINDOWS_HOST_SCOPE_REQUIRED"),
                         sort_keys=True))
        return 2
    observation = collect_readonly_witness(argv[2])
    print(json.dumps(observation, sort_keys=True))
    return 0 if observation["state"] == STATE else 1


if __name__ == "__main__":
    raise SystemExit(main())
