"""Windows CI-only negative probe: pinned signed image + suspended held process.

The negative path exclusively: create pinned runner Python with CREATE_SUSPENDED,
check actual held-process image path, held file SHA256 and a CI test Ed25519
signature, query token (normal -> rejected), and terminate WITHOUT resume.

The source executable is opened for read while denying new write/delete shares.
This DOES NOT prove global TOCTOU prevention against preexisting writer handles,
alternate paths/reparse points or kernel image-section internals; not a real
host/owner trust root. Never installs AION or runs on the owner's computer.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import time
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_windows_appcontainer_token_readonly_v1 import inspect_windows_process_handle
from atlasquant_aion_windows_signed_binary_ci_negative_intent_v1 import (
    SCHEMA, OPERATION, CANDIDATE, canonical_intent, check_signed_ci_negative_intent,
)


def _ci_allowed() -> bool:
    return (
        sys.platform == "win32"
        and os.getenv("GITHUB_ACTIONS") == "true"
        and os.getenv("GITHUB_EVENT_NAME") == "pull_request"
        and os.getenv("RUNNER_OS") == "Windows"
        and bool(os.getenv("GITHUB_RUN_ID"))
    )


def _result_template() -> dict[str, Any]:
    return {
        "schema": "AION_WINDOWS_PINNED_SUSPENDED_IMAGE_NEGATIVE_CI_V1",
        "running_on_windows_pr_ci": False,
        "image_handle_opened_deny_write_delete_shares": False,
        "file_identity_pre_post_stable": False,
        "file_digest_pre_post_stable": False,
        "test_intent_signed_with_ephemeral_ci_key": False,
        "signed_intent_candidate_untrusted": False,
        "child_created_suspended": False,
        "job_kill_on_close_set": False,
        "child_assigned_to_job": False,
        "actual_suspended_image_matches_signed_path": False,
        "normal_token_rejected": False,
        "child_never_resumed": False,
        "child_terminated": False,
        "canary_absent": False,
        "file_handle_closed": False,
        "process_handle_closed": False,
        "thread_handle_closed": False,
        "job_handle_closed": False,
        "scratch_removed": False,
        "network_probe_executed": False,
        "profile_created": False,
        "firewall_modified": False,
        "physical_attestation_verified": False,
        "real_owner_authorized": False,
        "safe_to_resume": False,
        "installer_authorized": False,
        "build_authorized": False,
        "deploy_authorized": False,
        "state": "BLOCKED",
    }


def run_ci_negative_signed_pinned_process() -> dict[str, Any]:
    result = _result_template()
    if not _ci_allowed():
        result["reason"] = "WINDOWS_GITHUB_PR_CI_ONLY"
        return result

    import ctypes
    from ctypes import wintypes as W
    import ntpath

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)

    class FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", W.DWORD), ("dwHighDateTime", W.DWORD)]

    class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", W.DWORD), ("ftCreationTime", FILETIME),
            ("ftLastAccessTime", FILETIME), ("ftLastWriteTime", FILETIME),
            ("dwVolumeSerialNumber", W.DWORD),
            ("nFileSizeHigh", W.DWORD), ("nFileSizeLow", W.DWORD),
            ("nNumberOfLinks", W.DWORD), ("nFileIndexHigh", W.DWORD),
            ("nFileIndexLow", W.DWORD),
        ]

    class SI(ctypes.Structure):
        _fields_ = [
            ("cb", W.DWORD), ("lpReserved", W.LPWSTR),
            ("lpDesktop", W.LPWSTR), ("lpTitle", W.LPWSTR),
            ("dwX", W.DWORD), ("dwY", W.DWORD), ("dwXSize", W.DWORD),
            ("dwYSize", W.DWORD), ("dwXCountChars", W.DWORD),
            ("dwYCountChars", W.DWORD), ("dwFillAttribute", W.DWORD),
            ("dwFlags", W.DWORD), ("wShowWindow", W.WORD),
            ("cbReserved2", W.WORD), ("lpReserved2", ctypes.c_void_p),
            ("hStdInput", W.HANDLE), ("hStdOutput", W.HANDLE),
            ("hStdError", W.HANDLE),
        ]

    class PI(ctypes.Structure):
        _fields_ = [
            ("hProcess", W.HANDLE), ("hThread", W.HANDLE),
            ("dwProcessId", W.DWORD), ("dwThreadId", W.DWORD),
        ]

    class BASIC(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", W.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", W.DWORD), ("Affinity", ctypes.c_size_t),
            ("PriorityClass", W.DWORD), ("SchedulingClass", W.DWORD),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_uint64)
            for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
            )
        ]

    class LIMITS(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BASIC), ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel.CreateFileW.argtypes = [
        W.LPCWSTR, W.DWORD, W.DWORD, ctypes.c_void_p,
        W.DWORD, W.DWORD, W.HANDLE,
    ]
    kernel.CreateFileW.restype = W.HANDLE
    kernel.GetFileInformationByHandle.argtypes = [
        W.HANDLE, ctypes.POINTER(BY_HANDLE_FILE_INFORMATION),
    ]
    kernel.GetFileInformationByHandle.restype = W.BOOL
    kernel.SetFilePointerEx.argtypes = [
        W.HANDLE, ctypes.c_int64, ctypes.c_void_p, W.DWORD,
    ]
    kernel.SetFilePointerEx.restype = W.BOOL
    kernel.ReadFile.argtypes = [
        W.HANDLE, ctypes.c_void_p, W.DWORD,
        ctypes.POINTER(W.DWORD), ctypes.c_void_p,
    ]
    kernel.ReadFile.restype = W.BOOL
    kernel.QueryFullProcessImageNameW.argtypes = [
        W.HANDLE, W.DWORD, W.LPWSTR, ctypes.POINTER(W.DWORD),
    ]
    kernel.QueryFullProcessImageNameW.restype = W.BOOL
    kernel.CreateProcessW.argtypes = [
        W.LPCWSTR, W.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
        W.BOOL, W.DWORD, ctypes.c_void_p, W.LPCWSTR,
        ctypes.POINTER(SI), ctypes.POINTER(PI),
    ]
    kernel.CreateProcessW.restype = W.BOOL
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, W.LPCWSTR]
    kernel.CreateJobObjectW.restype = W.HANDLE
    kernel.SetInformationJobObject.argtypes = [
        W.HANDLE, ctypes.c_int, ctypes.c_void_p, W.DWORD,
    ]
    kernel.SetInformationJobObject.restype = W.BOOL
    kernel.AssignProcessToJobObject.argtypes = [W.HANDLE, W.HANDLE]
    kernel.AssignProcessToJobObject.restype = W.BOOL
    kernel.TerminateProcess.argtypes = [W.HANDLE, W.UINT]
    kernel.TerminateProcess.restype = W.BOOL
    kernel.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
    kernel.WaitForSingleObject.restype = W.DWORD
    kernel.CloseHandle.argtypes = [W.HANDLE]
    kernel.CloseHandle.restype = W.BOOL

    def file_identity(h: int) -> tuple[int, ...] | None:
        info = BY_HANDLE_FILE_INFORMATION()
        if not kernel.GetFileInformationByHandle(h, ctypes.byref(info)):
            return None
        return (
            info.dwVolumeSerialNumber, info.nFileIndexHigh, info.nFileIndexLow,
            info.nFileSizeHigh, info.nFileSizeLow, info.ftLastWriteTime.dwHighDateTime,
            info.ftLastWriteTime.dwLowDateTime,
        )

    def hash_held_image(h: int) -> str | None:
        if not kernel.SetFilePointerEx(h, 0, None, 0):
            return None
        digest = sha256()
        buff = ctypes.create_string_buffer(65536)
        actual = W.DWORD()
        for _ in range(8192):
            if not kernel.ReadFile(
                h, buff, len(buff), ctypes.byref(actual), None,
            ):
                return None
            if actual.value == 0:
                return digest.hexdigest()
            digest.update(buff.raw[:actual.value])
        return None

    result["running_on_windows_pr_ci"] = True
    executable = str(Path(sys.executable).resolve())
    file_handle = None
    job = None
    proc = PI()
    scratch_path = None
    try:
        with tempfile.TemporaryDirectory(prefix="AION_CI_PINNED_NEGATIVE_") as scratch:
            scratch_path = Path(scratch)
            canary = scratch_path / "canary_must_not_exist.txt"
            try:
                raw_handle = kernel.CreateFileW(
                    executable, 0x80000000, 0x00000001, None, 3, 0x08000000, None,
                )
                if raw_handle == ctypes.c_void_p(-1).value or not raw_handle:
                    result["reason"] = "OPEN_PINNED_IMAGE_READ_WITH_DENY_WRITE_DELETE_SHARE_FAILED"
                else:
                    file_handle = raw_handle
                    result["image_handle_opened_deny_write_delete_shares"] = True
                    before_id = file_identity(file_handle)
                    before_hash = hash_held_image(file_handle)
                    if before_id is None or before_hash is None:
                        result["reason"] = "PRELAUNCH_FILE_ID_OR_DIGEST_FAILED"
                    else:
                        current_time = int(time.time())
                        manifest = {
                            "schema": SCHEMA, "operation": OPERATION,
                            "nonce": secrets.token_hex(16),
                            "image_path": ntpath.normpath(executable),
                            "image_sha256": before_hash,
                            "issued_at": current_time,
                            "expires_at": current_time + 60,
                            "expected_token_verdict": "TOKEN_NOT_APPCONTAINER",
                        }
                        # EPHEMERAL cryptographic test fixture, NOT owner root.
                        ephemeral_key = Ed25519PrivateKey.generate()
                        signature = ephemeral_key.sign(canonical_intent(manifest))
                        public_key = ephemeral_key.public_key().public_bytes(
                            encoding=serialization.Encoding.Raw,
                            format=serialization.PublicFormat.Raw,
                        )
                        result["test_intent_signed_with_ephemeral_ci_key"] = True

                        job = kernel.CreateJobObjectW(None, None)
                        if not job:
                            result["reason"] = "CREATE_JOB_FAILED"
                        else:
                            limits = LIMITS()
                            limits.BasicLimitInformation.LimitFlags = 0x2000
                            result["job_kill_on_close_set"] = bool(
                                kernel.SetInformationJobObject(
                                    job, 9, ctypes.byref(limits),
                                    ctypes.sizeof(limits),
                                )
                            )
                            if not result["job_kill_on_close_set"]:
                                result["reason"] = "SET_JOB_LIMIT_FAILED"
                            else:
                                canary_command = (
                                    "import pathlib,sys;"
                                    "pathlib.Path(sys.argv[1]).write_text('EXECUTED')"
                                )
                                cmd = ctypes.create_unicode_buffer(
                                    '"' + executable + '" -I -B -S -c "' +
                                    canary_command + '" "' + str(canary) + '"'
                                )
                                startup = SI()
                                startup.cb = ctypes.sizeof(startup)
                                # Always suspended; no code path resumes it.
                                envvals = {
                                    "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
                                    "WINDIR": os.environ.get("WINDIR", r"C:\Windows"),
                                    "TEMP": scratch, "TMP": scratch,
                                    "PYTHONNOUSERSITE": "1",
                                    "PYTHONDONTWRITEBYTECODE": "1",
                                }
                                envbuf = ctypes.create_unicode_buffer(
                                    "\0".join(
                                        k + "=" + v for k, v in sorted(envvals.items())
                                    ) + "\0\0"
                                )
                                result["child_created_suspended"] = bool(
                                    kernel.CreateProcessW(
                                        executable, cmd, None, None, False,
                                        0x4 | 0x08000000 | 0x400,
                                        ctypes.cast(envbuf, ctypes.c_void_p), scratch,
                                        ctypes.byref(startup), ctypes.byref(proc),
                                    )
                                )
                                if not result["child_created_suspended"]:
                                    result["reason"] = "CREATE_SUSPENDED_PINNED_IMAGE_FAILED"
                                else:
                                    result["child_never_resumed"] = True
                                    result["child_assigned_to_job"] = bool(
                                        kernel.AssignProcessToJobObject(
                                            job, proc.hProcess,
                                        )
                                    )
                                    if not result["child_assigned_to_job"]:
                                        result["reason"] = "ASSIGN_SUSPENDED_CHILD_JOB_FAILED"
                                    else:
                                        buffer = ctypes.create_unicode_buffer(32768)
                                        char_len = W.DWORD(len(buffer))
                                        readback = bool(
                                            kernel.QueryFullProcessImageNameW(
                                                proc.hProcess, 0,
                                                buffer, ctypes.byref(char_len),
                                            )
                                        )
                                        image_path = (
                                            buffer.value if readback else None
                                        )
                                        after_id = file_identity(file_handle)
                                        after_hash = hash_held_image(file_handle)
                                        result["file_identity_pre_post_stable"] = (
                                            before_id is not None and before_id == after_id
                                        )
                                        result["file_digest_pre_post_stable"] = (
                                            before_hash is not None and before_hash == after_hash
                                        )
                                        verdict = check_signed_ci_negative_intent(
                                            manifest, signature, public_key,
                                            observed_image_path=image_path,
                                            observed_image_sha256=after_hash,
                                            now=int(time.time()),
                                        )
                                        result["signed_intent_candidate_untrusted"] = (
                                            verdict["state"] == CANDIDATE
                                        )
                                        result["actual_suspended_image_matches_signed_path"] = (
                                            readback and verdict["state"] == CANDIDATE
                                        )
                                        token = inspect_windows_process_handle(
                                            int(proc.hProcess),
                                            "AtlasQuantAIONProbe5cee68653592",
                                        )
                                        result["normal_token_rejected"] = (
                                            token["reason"] == "TOKEN_NOT_APPCONTAINER"
                                        )
                                        if not all((
                                            result["file_identity_pre_post_stable"],
                                            result["file_digest_pre_post_stable"],
                                            result["signed_intent_candidate_untrusted"],
                                            result["normal_token_rejected"],
                                        )):
                                            result["reason"] = "SIGNED_FILE_ID_OR_TOKEN_MISMATCH"
            finally:
                if proc.hProcess:
                    terminated = bool(kernel.TerminateProcess(proc.hProcess, 1))
                    observed_exit = (
                        kernel.WaitForSingleObject(proc.hProcess, 5000) == 0
                    )
                    result["child_terminated"] = terminated and observed_exit
                if proc.hThread:
                    result["thread_handle_closed"] = bool(
                        kernel.CloseHandle(proc.hThread)
                    )
                if proc.hProcess:
                    result["process_handle_closed"] = bool(
                        kernel.CloseHandle(proc.hProcess)
                    )
                if job:
                    result["job_handle_closed"] = bool(kernel.CloseHandle(job))
                    job = None
                if file_handle:
                    result["file_handle_closed"] = bool(
                        kernel.CloseHandle(file_handle)
                    )
                    file_handle = None
                result["canary_absent"] = not canary.exists()
    finally:
        if job:
            kernel.CloseHandle(job)
        if file_handle:
            kernel.CloseHandle(file_handle)
        result["scratch_removed"] = (
            scratch_path is not None and not scratch_path.exists()
        )
    negative_requirements = (
        "running_on_windows_pr_ci",
        "image_handle_opened_deny_write_delete_shares",
        "file_identity_pre_post_stable",
        "file_digest_pre_post_stable",
        "test_intent_signed_with_ephemeral_ci_key",
        "signed_intent_candidate_untrusted",
        "child_created_suspended",
        "job_kill_on_close_set",
        "child_assigned_to_job",
        "actual_suspended_image_matches_signed_path",
        "normal_token_rejected",
        "child_never_resumed",
        "child_terminated",
        "canary_absent",
        "file_handle_closed",
        "process_handle_closed",
        "thread_handle_closed",
        "job_handle_closed",
        "scratch_removed",
    )
    if all(result[k] for k in negative_requirements):
        result["state"] = "SIGNED_PINNED_NORMAL_CHILD_QUARANTINED_CI_ONLY"
        result["reason"] = "NEGATIVE_CI_MEASUREMENT_NOT_OWNER_HOST_PROOF"
    else:
        result.setdefault("reason", "INCOMPLETE_NEGATIVE_PINNING_PROBE")
    return result


if __name__ == "__main__":
    if not _ci_allowed():
        raise SystemExit("CI ONLY: no local owner-PC or production execution")
    report = run_ci_negative_signed_pinned_process()
    print(json.dumps(report, sort_keys=True))
    if report["state"] != "SIGNED_PINNED_NORMAL_CHILD_QUARANTINED_CI_ONLY":
        raise SystemExit(1)
