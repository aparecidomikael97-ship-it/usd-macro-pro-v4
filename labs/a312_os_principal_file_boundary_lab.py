"""A312 LAB: observe OS file-mode limits for an isolated SQLite writer.

Real disposable SQLite, real subprocess with inherited OS principal.
A directory mode of 0700 and database 0600 DO NOT isolate another process
of the same OS user. No privilege escalation, user creation, resident worker,
provider, deployment, paid service, or operational authorization.
"""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory

from labs.a311_process_isolated_sqlite_lab import (
    DB_NAME, FIXTURE_MARKER, SCHEMA as A311_SCHEMA,
    create_fixture, fixture_root_valid, run_lab_request,
)

SCHEMA = "ATLASQUANT_AION_A312_OS_WRITER_PRINCIPAL_AUDIT_LAB_V1"
TEST_TITLE = "A312 TEST unauthorized second process changed title"
CHILD_SCRIPT = """
import json
import os
import sqlite3
import sys
from contextlib import closing
with closing(sqlite3.connect(sys.argv[1], timeout=5)) as db:
    cursor = db.execute(
        "UPDATE conversations SET title=? WHERE id=?",
        (sys.argv[3], sys.argv[2]),
    )
    affected = cursor.rowcount
    db.commit()
print(json.dumps({
    "pid": os.getpid(),
    "euid": os.geteuid() if hasattr(os, "geteuid") else None,
    "affected_rows": affected,
}))
"""
STATIC_BLOCKERS = (
    "NO_INDEPENDENT_WRITER_OS_PRINCIPAL",
    "NO_CLIENT_OS_ACCESS_DENIAL",
    "NO_NATIVE_SQLITE_VFS_FD_ATTESTATION",
    "NO_OFF_HOST_IMMUTABLE_CUSTODY",
    "NO_INDEPENDENT_ACK_OR_SEMANTIC_INTENT_PROOF",
)


def _base(status):
    return {
        "schema": SCHEMA,
        "status": status,
        "research_only": True,
        "synthetic_only": True,
        "distinct_process_observed": False,
        "separate_os_principal_attested": False,
        "same_principal_direct_file_write_observed": False,
        "posix_private_modes_observed": False,
        "windows_acl_audited": False,
        "os_writer_exclusivity_proven": False,
        "native_sqlite_vfs_fd_attested": False,
        "off_host_immutable_custody_attested": False,
        "semantic_exactly_once_attested": False,
        "real_external_ack_verified": False,
        "can_authorize_real_effect": False,
        "can_resume": False, "can_resend": False,
        "can_auto_retry": False, "automatic_retries": 0,
        "zero_auto_resend": True, "hard_no_go": True,
        "p0_homologated": 0, "no_worker_deploy_provider_orders": True,
        "new_paid_services": False,
        "blocking_requirements": list(STATIC_BLOCKERS),
    }


def inspect_private_modes(folder, database):
    """Report real POSIX mode/owner metadata; never call it OS isolation."""
    folder = Path(folder)
    database = Path(database)
    result = {
        "platform": os.name, "directory_mode": None,
        "db_mode": None, "directory_owner_uid": None,
        "db_owner_uid": None, "euid": None,
        "directory_is_real": False, "db_is_regular": False,
        "mode_bits_private": False,
        "identity_native_sqlite_fd_attested": False,
        "windows_dacl_checked": False,
    }
    if not fixture_root_valid(folder) or database != folder / DB_NAME:
        return result
    try:
        directory_meta = folder.lstat()
        db_meta = database.lstat()
    except OSError:
        return result
    result["directory_is_real"] = (
        stat.S_ISDIR(directory_meta.st_mode) and not folder.is_symlink()
    )
    result["db_is_regular"] = (
        stat.S_ISREG(db_meta.st_mode) and not database.is_symlink()
    )
    if os.name != "posix":
        # st_mode/chmod on Windows is NOT a proof about the DACL or token.
        return result
    result["directory_mode"] = oct(stat.S_IMODE(directory_meta.st_mode))
    result["db_mode"] = oct(stat.S_IMODE(db_meta.st_mode))
    result["directory_owner_uid"] = directory_meta.st_uid
    result["db_owner_uid"] = db_meta.st_uid
    result["euid"] = os.geteuid()
    result["mode_bits_private"] = (
        result["directory_is_real"]
        and result["db_is_regular"]
        and stat.S_IMODE(directory_meta.st_mode) == 0o700
        and stat.S_IMODE(db_meta.st_mode) == 0o600
        and directory_meta.st_uid == os.geteuid()
        and db_meta.st_uid == os.geteuid()
    )
    return result


def apply_fixture_private_modes(folder):
    """Best-effort permissions ONLY inside an A311 temporary fixture."""
    folder = Path(folder)
    if not fixture_root_valid(folder):
        raise ValueError("private-mode fixture not authenticated")
    db = folder / DB_NAME
    if not db.is_file() or db.is_symlink():
        raise ValueError("disposable SQLite fixture missing or symlinked")
    if os.name != "posix":
        return False
    # A312 explicitly does not chown or create another user.
    folder.chmod(0o700)
    for suffix in ("", "-wal", "-shm"):
        path = folder / (DB_NAME + suffix)
        if path.exists():
            if not path.is_file() or path.is_symlink():
                raise ValueError("non-regular SQLite fixture component")
            path.chmod(0o600)
    (folder / FIXTURE_MARKER).chmod(0o600)
    return True


def probe_same_principal_file_bypass(*, timeout_seconds=15):
    """Observe whether the calling OS principal can bypass A311 subprocess.

    Never takes a caller-supplied database path: the only target is a newly
    created disposable fixture. Spawns a bounded child with fixed SQL only.
    """
    if type(timeout_seconds) is not int or not (1 <= timeout_seconds <= 60):
        raise ValueError("invalid test timeout")
    result = _base("PROBE_INCOMPLETE")
    with TemporaryDirectory(prefix="a311-lab-a312-") as td:
        root = create_fixture(td)
        req = {
            "schema": A311_SCHEMA,
            "action": "CREATE_SYNTHETIC_CONVERSATION",
            "request_id": "a312-create",
            "title": "A311 TEST A312 disposable OS boundary",
        }
        created = run_lab_request(root, req, timeout_seconds=timeout_seconds)
        if created.get("status") != "LOCAL_ACKED":
            result["status"] = "FIXTURE_SETUP_NOT_CONFIRMED"
            return result
        cid = created["conversation_id"]
        db_path = root / DB_NAME
        try:
            posix_mode_requested = apply_fixture_private_modes(root)
        except (OSError, ValueError):
            result["status"] = "FIXTURE_PERMISSION_SETUP_FAILED"
            return result
        result["private_mode_requested_on_posix"] = posix_mode_requested
        before = inspect_private_modes(root, db_path)
        result["os_mode_observation"] = before
        result["posix_private_modes_observed"] = (
            before["mode_bits_private"] if os.name == "posix" else False
        )
        # Use another OS process under the *same* account. The parent never
        # has the store object, but does retain filesystem access.
        try:
            proc = subprocess.run(
                [sys.executable, "-c", CHILD_SCRIPT,
                 str(db_path), cid, TEST_TITLE],
                capture_output=True, text=True, check=False,
                timeout=timeout_seconds,
            )
            if proc.returncode != 0 or len(proc.stdout) > 2000:
                result["status"] = "SEPARATE_PROCESS_PROBE_DENIED_OR_FAILED"
                return result
            observed = json.loads(proc.stdout)
            if (type(observed) is not dict
                or type(observed.get("pid")) is not int
                or type(observed.get("affected_rows")) is not int
                or observed["pid"] == os.getpid()):
                result["status"] = "SUBPROCESS_EVIDENCE_INVALID"
                return result
        except (OSError, ValueError, subprocess.TimeoutExpired):
            result["status"] = "SEPARATE_PROCESS_PROBE_UNKNOWN"
            return result
        result["distinct_process_observed"] = True
        result["different_process_same_principal_observed"] = (
            os.name == "posix"
            and type(observed.get("euid")) is int
            and observed["euid"] == os.geteuid()
        )
        with closing(sqlite3.connect(str(db_path))) as reader:
            row = reader.execute(
                "SELECT title FROM conversations WHERE id=?", (cid,)
            ).fetchone()
        mutated = (
            observed["affected_rows"] == 1 and row is not None
            and row[0] == TEST_TITLE
        )
        result["same_principal_direct_file_write_observed"] = mutated
        result["status"] = (
            "SAME_ACCOUNT_WRITE_BYPASS_CONFIRMED"
            if mutated else "HOST_WRITE_BYPASS_NOT_CONFIRMED"
        )
        # It is a negative security result, not an operational write proof.
        result["client_can_direct_write_same_os_account"] = mutated
        result["separate_os_principal_attested"] = False
        return result


def assess_production_writer_boundary(*, observation):
    """Fail closed until independently enforced distinct OS credentials exist.

    A passed synthetic observation can never be upgraded into OS/P0 authority
    by renaming its keys or self-asserting a distinct user.
    """
    out = _base("NOT_READY_INDEPENDENT_PRINCIPAL_REQUIRED")
    if type(observation) is not dict or observation.get("schema") != SCHEMA:
        out["blocking_requirements"].append("OBSERVATION_MISSING_OR_WRONG_SCHEMA")
        return out
    if observation.get("same_principal_direct_file_write_observed") is True:
        out["blocking_requirements"].append("DIRECT_WRITER_BYPASS_OBSERVED")
    if observation.get("posix_private_modes_observed") is not True:
        out["blocking_requirements"].append(
            "POSIX_PRIVATE_MODE_UNPROVEN_OR_WINDOWS_DACL_NOT_ATTESTED"
        )
    # Observations on the same host cannot establish an independent trust
    # root, actual non-writer file-denial, writer-only ACL, or external ACK.
    out["observed_probe_status"] = observation.get("status")
    return out


__all__ = [
    "SCHEMA", "STATIC_BLOCKERS", "TEST_TITLE", "inspect_private_modes",
    "apply_fixture_private_modes", "probe_same_principal_file_bypass",
    "assess_production_writer_boundary",
]
