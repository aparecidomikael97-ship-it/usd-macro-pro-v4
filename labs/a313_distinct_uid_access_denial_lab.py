"""A313 LAB: real distinct Unix UIDs and OS-enforced SQLite file denial.

Only disposable A311 synthetic fixtures, two bounded sudo -u nobody commands
on GitHub-hosted Ubuntu. NO user creation, chown, service/Worker, deployment,
network, credentials, paid resource, real client data or production path.
A successful negative test is NOT a proof of operational writer exclusivity.
"""
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory

from labs.a311_process_isolated_sqlite_lab import (
    DB_NAME, SCHEMA as A311_SCHEMA, create_fixture, run_lab_request,
)
from labs.a312_os_principal_file_boundary_lab import (
    apply_fixture_private_modes, inspect_private_modes,
)

SCHEMA = "ATLASQUANT_AION_A313_DISTINCT_UID_ACCESS_DENIAL_LAB_V1"
LAB_P0_BLOCKERS = (
    "OPERATIONAL_SEPARATE_WRITER_UID_NOT_DEPLOYED",
    "OPERATIONAL_CLIENT_CANNOT_READ_OR_WRITE_NOT_ATTESTED",
    "WINDOWS_DACL_SID_NOT_AUDITED",
    "SQLITE_NATIVE_FD_VFS_WAL_SHM_NOT_AUTHENTICATED",
    "INDEPENDENT_INTENT_AND_COMMIT_ACK_CUSTODY_MISSING",
    "EXTERNAL_OWNER_PROVIDER_AUTHORITY_MISSING",
)
CHILD_READ_OPEN_SCRIPT = """
import errno, json, os, sqlite3, sys
from contextlib import closing
path, mode = sys.argv[1:]
out = {"uid": os.geteuid(), "pid": os.getpid(), "mode": mode,
       "read_open_denied": False, "write_open_denied": False,
       "directory_list_denied": False, "public_read_observed": False}
if mode == "restricted":
    for key, flags in (("read_open_denied", os.O_RDONLY),
                       ("write_open_denied", os.O_WRONLY)):
        try:
            fd = os.open(path, flags | getattr(os, "O_NOFOLLOW", 0))
        except PermissionError:
            out[key] = True
        else:
            os.close(fd)
    try:
        os.listdir(os.path.dirname(path))
    except PermissionError:
        out["directory_list_denied"] = True
elif mode == "public_read":
    # The control is OS-level file readability, not SQLite WAL/SHM
    # semantics. A read-only SQLite connection may fail when WAL
    # sidecars cannot be opened by an otherwise valid non-writer UID.
    with open(path, "rb") as handle:
        header = handle.read(16)
    out["public_header_length"] = len(header)
    out["public_read_observed"] = header == b"SQLite format 3\\x00"
else:
    raise ValueError("Unknown A313 LAB subtest")
print(json.dumps(out, sort_keys=True))
"""


def _base(status):
    return {
        "schema": SCHEMA, "status": status, "research_only": True,
        "synthetic_only": True, "real_two_uid_fixture_tested": False,
        "synthetic_other_uid_denied": False,
        "same_uid_caller_can_open_database": False,
        "public_read_control_passed": False,
        "windows_dacl_attested": False, "real_writer_account_deployed": False,
        "production_os_principal_isolation_proven": False,
        "exclusive_sqlite_writer_proven": False,
        "native_sqlite_fd_vfs_attested": False,
        "off_host_custody_proven": False,
        "independent_semantic_intent_ack_proven": False,
        "can_resume": False, "can_resend": False,
        "can_auto_retry": False, "can_authorize_real_effect": False,
        "automatic_retries": 0, "zero_auto_resend": True,
        "hard_no_go": True, "p0_homologated": 0,
        "no_worker_deploy_provider_operations": True,
        "new_paid_services": False,
        "blocking_requirements": list(LAB_P0_BLOCKERS),
    }


def _known_distinct_uid():
    """Never create accounts or grant extra privileges to the app itself."""
    if os.name != "posix" or not hasattr(os, "geteuid"):
        return None
    try:
        import pwd
        uid = pwd.getpwnam("nobody").pw_uid
    except (ImportError, KeyError, OSError):
        return None
    return uid if type(uid) is int and uid != os.geteuid() else None


def _run_existing_nobody(db_path, *, mode, timeout_seconds):
    if mode not in ("restricted", "public_read"):
        raise ValueError("invalid predefined test mode")
    sudo = shutil.which("sudo")
    if not sudo or _known_distinct_uid() is None:
        return None
    # Only sudo to an *existing, unprivileged* account in a disposable
    # runner. -n refuses interactive authentication; absolutely no shell.
    cmd = [
        sudo, "-n", "-u", "nobody", "--", sys.executable, "-c",
        CHILD_READ_OPEN_SCRIPT, str(db_path), mode,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              check=False, timeout=timeout_seconds)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0 or len(proc.stdout) > 2000:
        return None
    try:
        out = json.loads(proc.stdout)
    except (ValueError, TypeError):
        return None
    if (type(out) is not dict or type(out.get("pid")) is not int
            or type(out.get("uid")) is not int
            or out.get("mode") != mode
            or out["pid"] == os.getpid()
            or out["uid"] != _known_distinct_uid()):
        return None
    return out


def probe_real_different_uid_fixture(*, timeout_seconds=15):
    """One synthetic POSIX fixture; observe a genuine different UID denial.

    Never accepts an arbitrary path or command. On unsupported hosts returns
    UNTESTED, not a fake passing attestation. Strict CI must require proof.
    """
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 60:
        raise ValueError("timeout_seconds out of LAB bounds")
    result = _base("UNTESTED_DIFFERENT_UID")
    if os.name != "posix":
        result["status"] = "WINDOWS_DACL_SID_NOT_TESTED"
        return result
    if _known_distinct_uid() is None or shutil.which("sudo") is None:
        result["status"] = "DISTINCT_UID_LAB_RUNNER_UNAVAILABLE"
        return result
    # /tmp is a traversable POSIX parent; hosted-runner TMPDIR may
    # otherwise sit inside a runner-private directory unreadable by
    # nobody, invalidating the positive permission control.
    with TemporaryDirectory(prefix="a311-lab-a313-",
                            dir="/tmp" if os.name == "posix" else None) as directory:
        folder = create_fixture(directory)
        create = run_lab_request(folder, {
            "schema": A311_SCHEMA, "action": "CREATE_SYNTHETIC_CONVERSATION",
            "request_id": "a313-synthetic-fixture",
            "title": "A311 TEST A313 two UID synthetic",
        }, timeout_seconds=timeout_seconds)
        if create.get("status") != "LOCAL_ACKED":
            result["status"] = "FIXTURE_CREATE_FAILED"
            return result
        db_path = folder / DB_NAME
        if apply_fixture_private_modes(folder) is not True:
            result["status"] = "PRIVATE_FILE_MODES_NOT_SET"
            return result
        observed = inspect_private_modes(folder, db_path)
        result["posix_mode_metadata"] = observed
        if observed.get("mode_bits_private") is not True:
            result["status"] = "PRIVATE_FILE_MODES_NOT_OBSERVED"
            return result
        # Parent has same user identity as writer, yet must never be treated
        # as an actual operational AION client.
        with closing(sqlite3.connect("file:" + str(db_path) + "?mode=ro",
                                     uri=True, timeout=3)) as same_uid_db:
            parent_count = same_uid_db.execute(
                "SELECT COUNT(*) FROM conversations"
            ).fetchone()[0]
        result["same_uid_caller_can_open_database"] = parent_count == 1
        denied = _run_existing_nobody(
            db_path, mode="restricted", timeout_seconds=timeout_seconds
        )
        if denied is None:
            result["status"] = "DISTINCT_UID_PROBE_UNVERIFIABLE"
            return result
        result["different_uid_observed"] = denied["uid"] != os.geteuid()
        result["restricted_result"] = denied
        result["synthetic_other_uid_denied"] = (
            denied.get("read_open_denied") is True
            and denied.get("write_open_denied") is True
            and denied.get("directory_list_denied") is True
        )
        # Positive control: temporarily make THIS TEST FIXTURE publicly
        # readable, proving that nobody can execute Python and access SQLite.
        # No real data, permissions restored even if the child fails.
        try:
            folder.chmod(0o755)
            db_path.chmod(0o644)
            public = _run_existing_nobody(
                db_path, mode="public_read", timeout_seconds=timeout_seconds
            )
        finally:
            db_path.chmod(0o600)
            folder.chmod(0o700)
        result["public_read_control_passed"] = (
            public is not None and
            public.get("public_read_observed") is True and
            public.get("uid") == denied["uid"]
        )
        result["real_two_uid_fixture_tested"] = (
            result["different_uid_observed"]
            and result["public_read_control_passed"]
        )
        if (result["real_two_uid_fixture_tested"]
                and result["synthetic_other_uid_denied"]
                and result["same_uid_caller_can_open_database"]):
            result["status"] = "DIFFERENT_UID_FIXTURE_DENIAL_OBSERVED"
        else:
            result["status"] = "OS_PRINCIPAL_PROOF_INCOMPLETE"
    return result


def assess_operational_os_writer_readiness(*, observation):
    """Never promote a CI fixture UID to real custody/exclusive writer."""
    result = _base("HARD_NO_GO_OPERATIONAL_WRITER_NOT_ATTESTED")
    if type(observation) is not dict or observation.get("schema") != SCHEMA:
        result["blocking_requirements"].append("A313_OBSERVATION_INVALID")
    elif observation.get("synthetic_other_uid_denied") is True:
        result["synthetic_other_uid_denied"] = True
        result["real_two_uid_fixture_tested"] = (
            observation.get("real_two_uid_fixture_tested") is True
        )
    # No production OS user, SID/DACL, IPC identity, native FD, off-host
    # intent ledger or provider outcome can be attested by this host.
    return result


__all__ = [
    "SCHEMA", "LAB_P0_BLOCKERS", "probe_real_different_uid_fixture",
    "assess_operational_os_writer_readiness",
]
