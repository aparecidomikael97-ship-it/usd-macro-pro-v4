"""AION Windows native read-only verifier preflight V1.

CI-hosted Windows observation ONLY. No installation, local owner-PC access,
Registry modification, ACL change, startup change, process launch or reboot.
A Windows runner's identity is NOT the HUMAN_OWNER identity. Raw SID, SDDL,
host name, Registry value and filesystem path are never returned.

Native OS readings are neither authenticated attestations nor proof of an
AION package, startup registration, reboot, continuous operation, or health.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import winreg
from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_WINDOWS_NATIVE_READONLY_PREFLIGHT_V1"
OBSERVED = "CI_WINDOWS_NATIVE_OBSERVATION_SHAPE_READY_UNTRUSTED"
REVIEW_READY = "READY_FOR_NATIVE_WINDOWS_READONLY_SECURITY_REVIEW"
BLOCKED = "BLOCKED"
GUARD_REQUIRED = "WINDOWS_HOSTED_PR_RUNNER_REQUIRED"
FIELDS = (
    "schema", "challenge_digest", "policy_digest", "verifier_source_digest",
    "token_user_sid_digest", "scratch_directory_owner_sid_digest",
    "scratch_directory_acl_sddl_digest", "scratch_directory_dacl_present",
    "token_matches_scratch_owner", "process_image_sha256",
    "process_image_exists", "runner_temp_within_policy",
    "boot_uptime_milliseconds", "startup_run_key_status",
    "aion_run_entry_status", "ci_platform", "ci_runner_os",
    "observation_scope",
)
POLICY = {
    "schema": SCHEMA,
    "test_only": True,
    "ephemeral_github_windows_runner_only": True,
    "native_windows_readonly_api_calls": True,
    "real_windows_sid_and_scratch_acl_read": True,
    "physical_ci_disk_writes_performed": False,
    "owner_pc_read_or_written": False,
    "human_owner_sid_verified": False,
    "aion_installed": False,
    "aion_binary_or_signer_verified": False,
    "aion_startup_entry_verified": False,
    "aion_owner_acl_verified": False,
    "aion_process_running_verified": False,
    "real_boot_transition_proven": False,
    "actual_reboot_performed": False,
    "aion_runtime_health_verified": False,
    "independent_attestor_authenticated": False,
    "trusted_evidence_issued": False,
    "owner_auth_consumed": False,
    "install_token_consumed": False,
    "registry_modified": False,
    "acl_modified": False,
    "startup_modified": False,
    "service_created": False,
    "package_installed": False,
    "deploy_executed": False,
    "worker_activated": False,
}

def _digest(v: Any) -> str:
    return "sha256:" + sha256(json.dumps(
        v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")).hexdigest()

def _sha(v: Any) -> bool:
    return (type(v) is str and len(v) == 71
            and v.startswith("sha256:") and all(x in "0123456789abcdef" for x in v[7:]))

def _hash_secret(value: str, kind: str) -> str:
    # A digest is still a potentially correlatable pseudonymous identifier.
    # It MUST NOT be uploaded to public logs or interpreted as anonymization.
    return _digest({"scope": "ci-only", "kind": kind, "value": value})

def _runner_guard() -> Path:
    if (
        os.name != "nt" or sys.platform != "win32"
        or os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("RUNNER_OS") != "Windows"
        or os.environ.get("GITHUB_EVENT_NAME") != "pull_request"
        or os.environ.get("AION_NATIVE_READONLY_PREFLIGHT") != "1"
    ):
        raise RuntimeError(GUARD_REQUIRED)
    raw = os.environ.get("RUNNER_TEMP", "")
    if not raw:
        raise RuntimeError(GUARD_REQUIRED)
    path = Path(raw)
    if not path.is_dir() or path.is_symlink():
        raise RuntimeError(GUARD_REQUIRED)
    return path.resolve(strict=True)

def _winlibs() -> tuple[Any, Any]:
    return (ctypes.WinDLL("kernel32", use_last_error=True),
            ctypes.WinDLL("advapi32", use_last_error=True))

def _sid_to_string(adv: Any, kernel: Any, sid: Any) -> str:
    p = wintypes.LPWSTR()
    convert = adv.ConvertSidToStringSidW
    convert.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    convert.restype = wintypes.BOOL
    if not convert(sid, ctypes.byref(p)) or not p.value:
        raise OSError(ctypes.get_last_error(), "ConvertSidToStringSidW failed")
    release = kernel.LocalFree
    release.argtypes = [ctypes.c_void_p]
    release.restype = ctypes.c_void_p
    try:
        return str(p.value)
    finally:
        release(ctypes.cast(p, ctypes.c_void_p))

def _token_sid(adv: Any, kernel: Any) -> str:
    # TOKEN_QUERY=0x0008; TokenUser=1; process handle is a pseudo handle.
    get_process = kernel.GetCurrentProcess
    get_process.argtypes = []
    get_process.restype = wintypes.HANDLE
    open_token = adv.OpenProcessToken
    open_token.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)
    ]
    open_token.restype = wintypes.BOOL
    token = wintypes.HANDLE()
    if not open_token(get_process(), 0x0008, ctypes.byref(token)):
        raise OSError(ctypes.get_last_error(), "OpenProcessToken failed")
    close_handle = kernel.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    try:
        get_info = adv.GetTokenInformation
        get_info.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        get_info.restype = wintypes.BOOL
        size = wintypes.DWORD(0)
        get_info(token, 1, None, 0, ctypes.byref(size))
        if size.value < ctypes.sizeof(ctypes.c_void_p):
            raise OSError(ctypes.get_last_error(), "TokenUser size invalid")
        buf = ctypes.create_string_buffer(size.value)
        if not get_info(token, 1, buf, size.value, ctypes.byref(size)):
            raise OSError(ctypes.get_last_error(), "GetTokenInformation failed")
        class SID_AND_ATTRIBUTES(ctypes.Structure):
            _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]
        entry = ctypes.cast(buf, ctypes.POINTER(SID_AND_ATTRIBUTES)).contents
        return _sid_to_string(adv, kernel, entry.Sid)
    finally:
        close_handle(token)

def _scratch_security(path: Path, adv: Any, kernel: Any) -> tuple[str, str, bool]:
    """Read owner and DACL of RUNNER_TEMP; do not modify Windows ACLs."""
    query = adv.GetNamedSecurityInfoW
    query.argtypes = [
        wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    query.restype = wintypes.DWORD
    owner, group, dacl, sacl, desc = (ctypes.c_void_p() for _ in range(5))
    code = query(
        str(path), 1, 0x00000001 | 0x00000004,
        ctypes.byref(owner), ctypes.byref(group),
        ctypes.byref(dacl), ctypes.byref(sacl), ctypes.byref(desc),
    )
    if code != 0 or not owner.value or not desc.value:
        if desc.value:
            kernel.LocalFree(ctypes.c_void_p(desc.value))
        raise OSError(code, "GetNamedSecurityInfoW owner/DACL read failed")
    release = kernel.LocalFree
    release.argtypes = [ctypes.c_void_p]
    release.restype = ctypes.c_void_p
    try:
        owner_sid = _sid_to_string(adv, kernel, owner)
        converter = adv.ConvertSecurityDescriptorToStringSecurityDescriptorW
        converter.argtypes = [
            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
            ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(wintypes.ULONG),
        ]
        converter.restype = wintypes.BOOL
        sddl = wintypes.LPWSTR()
        length = wintypes.ULONG(0)
        if not converter(
            desc, 1, 0x00000001 | 0x00000004,
            ctypes.byref(sddl), ctypes.byref(length),
        ) or not sddl.value:
            raise OSError(ctypes.get_last_error(), "SDDL read conversion failed")
        try:
            return owner_sid, str(sddl.value), bool(dacl.value)
        finally:
            release(ctypes.cast(sddl, ctypes.c_void_p))
    finally:
        release(desc)

def _uptime_ms(kernel: Any) -> int:
    tick = kernel.GetTickCount64
    tick.argtypes = []
    tick.restype = ctypes.c_ulonglong
    return int(tick())

def _startup_readonly_visibility() -> tuple[str, str]:
    """Only existence/status of HKCU Run and AION value; no value contents."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_READ,
        ) as key:
            try:
                winreg.QueryValueEx(key, "AtlasQuantAION")
            except FileNotFoundError:
                return ("ACCESSIBLE", "ABSENT")
            except PermissionError:
                return ("ACCESSIBLE", "DENIED")
            return ("ACCESSIBLE", "PRESENT_UNVERIFIED")
    except FileNotFoundError:
        return ("ABSENT", "ABSENT")
    except PermissionError:
        return ("DENIED", "UNKNOWN")

def capture_ci_windows_native_observation(
    *, challenge_digest: str, policy_digest: str, verifier_source_digest: str,
) -> dict[str, Any]:
    """Native-read-only CI observation with explicit NO TRUST/NO OWNER scope."""
    base = _runner_guard()
    if not all(_sha(v) for v in (
        challenge_digest, policy_digest, verifier_source_digest,
    )):
        raise ValueError("DIGESTS_REQUIRED")
    kernel, adv = _winlibs()
    token_sid = _token_sid(adv, kernel)
    owner_sid, sddl, dacl_present = _scratch_security(base, adv, kernel)
    image = Path(sys.executable)
    if not image.is_file() or image.is_symlink():
        raise RuntimeError("RUNNER_PYTHON_IMAGE_INVALID")
    startup, aion_entry = _startup_readonly_visibility()
    data = {
        "schema": SCHEMA,
        "challenge_digest": challenge_digest,
        "policy_digest": policy_digest,
        "verifier_source_digest": verifier_source_digest,
        "token_user_sid_digest": _hash_secret(token_sid, "ci-token-sid"),
        "scratch_directory_owner_sid_digest": _hash_secret(owner_sid, "ci-scratch-owner"),
        "scratch_directory_acl_sddl_digest": _hash_secret(sddl, "ci-scratch-sddl"),
        "scratch_directory_dacl_present": dacl_present,
        "token_matches_scratch_owner": token_sid == owner_sid,
        "process_image_sha256": "sha256:" + sha256(image.read_bytes()).hexdigest(),
        "process_image_exists": True,
        "runner_temp_within_policy": True,
        "boot_uptime_milliseconds": _uptime_ms(kernel),
        "startup_run_key_status": startup,
        "aion_run_entry_status": aion_entry,
        "ci_platform": "win32",
        "ci_runner_os": "Windows",
        "observation_scope": "EPHEMERAL_GITHUB_RUNNER_ONLY",
    }
    return {
        **data,
        "observation_digest": _digest(data),
        "state": OBSERVED,
        "blockers": [],
        **{k: False for k in (
            "human_owner_sid_verified", "aion_binary_or_signer_verified",
            "aion_owner_acl_verified", "aion_startup_entry_verified",
            "aion_process_running_verified", "real_boot_transition_proven",
            "aion_runtime_health_verified", "trusted_attestation_issued",
            "aion_installed", "owner_pc_accessed", "production_write_executed",
            "runtime_trusted_healthy",
        )},
    }

def assess_ci_native_preflight(
    observation: Mapping[str, Any] | None, *,
    expected_challenge_digest: str, expected_policy_digest: str,
    expected_verifier_source_digest: str,
) -> dict[str, Any]:
    """Shape-only review. No observed data may claim owner/installer trust."""
    o = dict(observation) if isinstance(observation, Mapping) else {}
    errors: list[str] = []
    expected_keys = set(FIELDS) | {
        "observation_digest", "state", "blockers",
        "human_owner_sid_verified", "aion_binary_or_signer_verified",
        "aion_owner_acl_verified", "aion_startup_entry_verified",
        "aion_process_running_verified", "real_boot_transition_proven",
        "aion_runtime_health_verified", "trusted_attestation_issued",
        "aion_installed", "owner_pc_accessed", "production_write_executed",
        "runtime_trusted_healthy",
    }
    if set(o) - expected_keys:
        errors.append("UNEXPECTED_OBSERVATION_FIELDS")
    if expected_keys - set(o):
        errors.append("MISSING_REQUIRED_OBSERVATION_FIELDS")
    if o.get("schema") != SCHEMA or o.get("state") != OBSERVED:
        errors.append("NATIVE_OBSERVATION_REQUIRED")
    if not all(_sha(x) for x in (
        expected_challenge_digest, expected_policy_digest,
        expected_verifier_source_digest,
    )):
        errors.append("EXPECTED_DIGEST_INVALID")
    for expected, key in (
        (expected_challenge_digest, "challenge_digest"),
        (expected_policy_digest, "policy_digest"),
        (expected_verifier_source_digest, "verifier_source_digest"),
    ):
        if o.get(key) != expected:
            errors.append("BINDING_MISMATCH:" + key)
    if o.get("observation_digest") != _digest({key: o.get(key) for key in FIELDS}):
        errors.append("OBSERVATION_DIGEST_MISMATCH")
    for field in (
        "token_user_sid_digest", "scratch_directory_owner_sid_digest",
        "scratch_directory_acl_sddl_digest", "process_image_sha256",
    ):
        if not _sha(o.get(field)):
            errors.append("NATIVE_DIGEST_INVALID:" + field)
    if type(o.get("boot_uptime_milliseconds")) is not int or o["boot_uptime_milliseconds"] <= 0:
        errors.append("NATIVE_UPTIME_INVALID")
    if o.get("process_image_exists") is not True or o.get("runner_temp_within_policy") is not True:
        errors.append("RUNNER_SCOPING_INVALID")
    if o.get("ci_platform") != "win32" or o.get("ci_runner_os") != "Windows":
        errors.append("WINDOWS_RUNNER_REQUIRED")
    if o.get("observation_scope") != "EPHEMERAL_GITHUB_RUNNER_ONLY":
        errors.append("OBSERVATION_SCOPE_INVALID")
    if o.get("startup_run_key_status") not in ("ACCESSIBLE", "ABSENT", "DENIED"):
        errors.append("STARTUP_HKCU_READ_STATUS_INVALID")
    if o.get("aion_run_entry_status") not in ("ABSENT", "DENIED", "UNKNOWN", "PRESENT_UNVERIFIED"):
        errors.append("STARTUP_AION_READ_STATUS_INVALID")
    if type(o.get("scratch_directory_dacl_present")) is not bool:
        errors.append("DACL_OBSERVATION_INVALID")
    if type(o.get("token_matches_scratch_owner")) is not bool:
        errors.append("OWNER_MATCH_OBSERVATION_INVALID")
    for flag in (
        "human_owner_sid_verified", "aion_binary_or_signer_verified",
        "aion_owner_acl_verified", "aion_startup_entry_verified",
        "aion_process_running_verified", "real_boot_transition_proven",
        "aion_runtime_health_verified", "trusted_attestation_issued",
        "aion_installed", "owner_pc_accessed", "production_write_executed",
        "runtime_trusted_healthy",
    ):
        if o.get(flag) is not False:
            errors.append("FORBIDDEN_TRUST_PROMOTION:" + flag)
    errors = list(dict.fromkeys(errors))
    material = {
        "observation_digest": o.get("observation_digest", ""),
        "expected_challenge_digest": expected_challenge_digest,
        "expected_policy_digest": expected_policy_digest,
        "expected_verifier_source_digest": expected_verifier_source_digest,
        "review_state": REVIEW_READY if not errors else BLOCKED,
    }
    return {
        "schema": SCHEMA,
        "state": REVIEW_READY if not errors else BLOCKED,
        "blockers": errors,
        "review_digest": _digest(material) if not errors else "",
        "shape_verified_untrusted": not errors,
        "ci_runner_os_observed": not errors,
        "windows_native_api_observation_tested": not errors,
        "read_only_scope": True,
        "owner_device_or_aion_verified": False,
        "independent_attestation_trusted": False,
        "actual_reboot_proven": False,
        "aion_health_trusted": False,
        "installation_authorized": False,
        "deploy_authorized": False,
    }

def native_preflight_policy() -> dict[str, Any]:
    return dict(POLICY)

__all__ = [
    "SCHEMA", "OBSERVED", "REVIEW_READY", "BLOCKED", "GUARD_REQUIRED",
    "FIELDS", "capture_ci_windows_native_observation", "assess_ci_native_preflight",
    "native_preflight_policy", "_digest",
]
