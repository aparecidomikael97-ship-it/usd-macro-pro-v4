"""Windows CI-only suspended-child *negative* quarantine probe V1.

A tiny Python canary child is created with CREATE_SUSPENDED, assigned to a new
kill-on-close Windows Job Object, and checked via the previously reviewed
read-only AppContainer token inspector. As the child is a NORMAL CI process,
it MUST be rejected and TERMINATED WITHOUT ANY ResumeThread call.

Only GitHub-hosted PR CI is an intended caller. No AppContainer creation,
network operation, AION code execution, install, ACL, firewall or registry edit.
The env check is a safety interlock, NOT an authenticated CI trust anchor.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

from atlasquant_aion_windows_appcontainer_token_readonly_v1 import (
    inspect_windows_process_handle,
)
from atlasquant_aion_windows_suspended_child_quarantine_contract_v1 import (
    SCHEMA, FIELDS, classify_quarantine_observation,
)

TEST_PROFILE = "AtlasQuantAIONProbe5cee68653592"
CANARY_PAYLOAD = "AION_CHILD_SHOULD_NEVER_START"
CANARY_CODE = (
    "import pathlib,sys;"
    "pathlib.Path(sys.argv[1]).write_text('AION_CHILD_SHOULD_NEVER_START',encoding='ascii')"
)


def _ci_allowed() -> bool:
    return (
        sys.platform == "win32"
        and os.getenv("GITHUB_ACTIONS") == "true"
        and os.getenv("GITHUB_EVENT_NAME") == "pull_request"
        and os.getenv("RUNNER_OS") == "Windows"
        and bool(os.getenv("GITHUB_RUN_ID"))
    )


def _fresh_observation() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "running_on_pr_ci": False,
        "child_created_suspended": False,
        "job_kill_on_close": False,
        "child_attached_to_job": False,
        "child_never_resumed": False,
        "token_reason": "NOT_QUERIED",
        "token_state": "NOT_VERIFIED",
        "token_physical_attestation_verified": False,
        "token_process_handle_origin_verified": False,
        "token_network_deny_verified": False,
        "termination_requested": False,
        "child_exit_observed": False,
        "canary_absent": False,
        "job_handle_closed": False,
        "child_handle_closed": False,
        "thread_handle_closed": False,
    }


def run_ci_suspended_child_negative_probe() -> dict[str, Any]:
    """Run a deliberately rejected Windows-native suspended canary process."""
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "runner_only": True,
        "appcontainer_profile_created": False,
        "network_socket_opened": False,
        "firewall_or_wfp_changed": False,
        "production_binary_executed": False,
        "environment_inherited": False,
        "host_independently_attested": False,
    }
    observation = _fresh_observation()
    result["observation"] = observation
    if not _ci_allowed():
        result["classification"] = classify_quarantine_observation(observation)
        return result

    import ctypes
    from ctypes import wintypes as W

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)

    class STARTUPINFO(ctypes.Structure):
        _fields_ = [
            ("cb", W.DWORD), ("lpReserved", W.LPWSTR),
            ("lpDesktop", W.LPWSTR), ("lpTitle", W.LPWSTR),
            ("dwX", W.DWORD), ("dwY", W.DWORD),
            ("dwXSize", W.DWORD), ("dwYSize", W.DWORD),
            ("dwXCountChars", W.DWORD), ("dwYCountChars", W.DWORD),
            ("dwFillAttribute", W.DWORD), ("dwFlags", W.DWORD),
            ("wShowWindow", W.WORD), ("cbReserved2", W.WORD),
            ("lpReserved2", ctypes.c_void_p),
            ("hStdInput", W.HANDLE), ("hStdOutput", W.HANDLE),
            ("hStdError", W.HANDLE),
        ]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("hProcess", W.HANDLE), ("hThread", W.HANDLE),
            ("dwProcessId", W.DWORD), ("dwThreadId", W.DWORD),
        ]

    class BASIC_LIMITS(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", W.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", W.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", W.DWORD),
            ("SchedulingClass", W.DWORD),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_uint64)
            for name in (
                "ReadOperationCount", "WriteOperationCount",
                "OtherOperationCount", "ReadTransferCount",
                "WriteTransferCount", "OtherTransferCount",
            )
        ]

    class EXTENDED_LIMITS(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BASIC_LIMITS),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, W.LPCWSTR]
    kernel.CreateJobObjectW.restype = W.HANDLE
    kernel.SetInformationJobObject.argtypes = [
        W.HANDLE, ctypes.c_int, ctypes.c_void_p, W.DWORD,
    ]
    kernel.SetInformationJobObject.restype = W.BOOL
    kernel.AssignProcessToJobObject.argtypes = [W.HANDLE, W.HANDLE]
    kernel.AssignProcessToJobObject.restype = W.BOOL
    kernel.CreateProcessW.argtypes = [
        W.LPCWSTR, W.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
        W.BOOL, W.DWORD, ctypes.c_void_p, W.LPCWSTR,
        ctypes.POINTER(STARTUPINFO),
        ctypes.POINTER(PROCESS_INFORMATION),
    ]
    kernel.CreateProcessW.restype = W.BOOL
    kernel.TerminateProcess.argtypes = [W.HANDLE, W.UINT]
    kernel.TerminateProcess.restype = W.BOOL
    kernel.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
    kernel.WaitForSingleObject.restype = W.DWORD
    kernel.CloseHandle.argtypes = [W.HANDLE]
    kernel.CloseHandle.restype = W.BOOL

    observation["running_on_pr_ci"] = True
    job = None
    process = PROCESS_INFORMATION()
    try:
        with tempfile.TemporaryDirectory(prefix="AION_CI_SUSPENDED_QUARANTINE_") as scratch:
            root = Path(scratch)
            canary = root / "unauthorized_execution_canary.txt"
            try:
                job = kernel.CreateJobObjectW(None, None)
                if not job:
                    result["failure_stage"] = "CREATE_JOB_OBJECT"
                else:
                    limits = EXTENDED_LIMITS()
                    limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
                    observation["job_kill_on_close"] = bool(
                        kernel.SetInformationJobObject(
                            job, 9, ctypes.byref(limits), ctypes.sizeof(limits),
                        )
                    )
                    if not observation["job_kill_on_close"]:
                        result["failure_stage"] = "SET_KILL_ON_CLOSE"
                    else:
                        executable = str(Path(sys.executable).resolve())
                        # The child is a pinned runner Python executable; the
                        # canary only touches a new disposable temp directory.
                        line = ctypes.create_unicode_buffer(
                            '"' + executable + '" -I -B -S -c "' + CANARY_CODE
                            + '" "' + str(canary) + '"'
                        )
                        startup = STARTUPINFO()
                        startup.cb = ctypes.sizeof(startup)
                        # Exactly controlled environment: no parent PATH,
                        # GitHub tokens or user Python startup configuration.
                        envvars = {
                            "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
                            "WINDIR": os.environ.get("WINDIR", r"C:\Windows"),
                            "TEMP": scratch, "TMP": scratch,
                            "PYTHONNOUSERSITE": "1",
                            "PYTHONDONTWRITEBYTECODE": "1",
                        }
                        env = ctypes.create_unicode_buffer(
                            "\0".join(k + "=" + v for k, v in sorted(envvars.items()))
                            + "\0\0"
                        )
                        flags = 0x00000004 | 0x08000000 | 0x00000400  # SUSPENDED, NO_WINDOW, UNICODE_ENV
                        observation["child_created_suspended"] = bool(
                            kernel.CreateProcessW(
                                executable, line, None, None, False,
                                flags, ctypes.cast(env, ctypes.c_void_p),
                                scratch, ctypes.byref(startup), ctypes.byref(process),
                            )
                        )
                        if not observation["child_created_suspended"]:
                            result["failure_stage"] = "CREATE_SUSPENDED_CHILD"
                        else:
                            # No ResumeThread, ever. Normal CI process must be
                            # denied before any chance of canary execution.
                            observation["child_never_resumed"] = True
                            observation["child_attached_to_job"] = bool(
                                kernel.AssignProcessToJobObject(job, process.hProcess)
                            )
                            if not observation["child_attached_to_job"]:
                                result["failure_stage"] = "ASSIGN_JOB"
                            else:
                                token_result = inspect_windows_process_handle(
                                    int(process.hProcess), TEST_PROFILE
                                )
                                observation["token_reason"] = token_result["reason"]
                                observation["token_state"] = token_result["state"]
                                observation["token_physical_attestation_verified"] = (
                                    token_result["physical_attestation_verified"]
                                )
                                observation["token_process_handle_origin_verified"] = (
                                    token_result["process_handle_origin_verified"]
                                )
                                observation["token_network_deny_verified"] = (
                                    token_result["network_deny_verified"]
                                )
                                if token_result["reason"] != "TOKEN_NOT_APPCONTAINER":
                                    result["failure_stage"] = "UNEXPECTED_TOKEN_IDENTITY"
            finally:
                # Always terminate, even if job assignment or inspection fails.
                if process.hProcess:
                    observation["termination_requested"] = bool(
                        kernel.TerminateProcess(process.hProcess, 1)
                    )
                    observation["child_exit_observed"] = (
                        kernel.WaitForSingleObject(process.hProcess, 5000) == 0
                    )
                if job:
                    observation["job_handle_closed"] = bool(kernel.CloseHandle(job))
                    job = None
                if process.hThread:
                    observation["thread_handle_closed"] = bool(
                        kernel.CloseHandle(process.hThread)
                    )
                if process.hProcess:
                    observation["child_handle_closed"] = bool(
                        kernel.CloseHandle(process.hProcess)
                    )
                observation["canary_absent"] = not canary.exists()
    finally:
        if job:
            kernel.CloseHandle(job)
    result["classification"] = classify_quarantine_observation(observation)
    result["scope"] = "EPHEMERAL_WINDOWS_CI_NEGATIVE_CHILD_ONLY"
    return result


if __name__ == "__main__":
    if not _ci_allowed():
        raise SystemExit("CI-ONLY: Windows GitHub PR runner required, no local execution")
    report = run_ci_suspended_child_negative_probe()
    print(json.dumps(report, sort_keys=True))
    if report["classification"]["state"] != "NORMAL_CHILD_QUARANTINED_AND_TERMINATED":
        raise SystemExit(1)
