"""A314 LAB: finite Unix socket writer across genuine different Linux UIDs.

This is an *ephemeral fixture-only* process with exactly one request per
instance, NOT a deployed/resident AION Worker. Client uses existing nobody UID
only on GitHub's disposable Ubuntu runner, no user creation, chown, network,
services, provider, live operation, external effect or new paid resources.

Linux SO_PEERCRED authenticates the connecting *UID*, not the user intent,
owner authorization, P0, native SQLite FD identity, or provider ACK.
"""
from contextlib import closing
import json
import os
from pathlib import Path
try:
    import pwd
except ImportError:  # Windows cannot provide Unix user databases.
    pwd = None
import socket
import sqlite3
import stat
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

from labs.a311_process_isolated_sqlite_lab import (
    DB_NAME, SCHEMA as A311_SCHEMA, create_fixture,
    execute_fixture_request, fixture_root_valid,
)
from labs.a312_os_principal_file_boundary_lab import apply_fixture_private_modes

SCHEMA = "ATLASQUANT_AION_A314_CROSS_UID_IPC_WRITER_LAB_V1"
SOCKET_NAME = "a314-synthetic.sock"
READY_NAME = ".a314-accept-ready"
REQUEST = {"schema": SCHEMA, "action": "CREATE_SYNTHETIC_ONLY",
           "request_id": "a314-fixed-test-request"}
INVALID_REQUEST = {"schema": SCHEMA, "action": "DEPLOY",
                   "request_id": "a314-fixed-test-request"}
TITLE = "A311 TEST A314 separate UID IPC"
CLIENT_SCRIPT = """
import json, os, socket, sys
socket_path, db_path, raw = sys.argv[1:]
result = {"uid": os.geteuid(), "pid": os.getpid(),
          "read_denied": False, "write_denied": False,
          "listdir_denied": False}
for key, flag in (("read_denied", os.O_RDONLY),
                  ("write_denied", os.O_WRONLY)):
    try:
        fd = os.open(db_path, flag)
    except PermissionError:
        result[key] = True
    else:
        os.close(fd)
try:
    os.listdir(os.path.dirname(db_path))
except PermissionError:
    result["listdir_denied"] = True
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
    client.settimeout(8)
    client.connect(socket_path)
    client.sendall(raw.encode("utf-8") + b"\\n")
    response = client.makefile("rb").readline(4097)
result["ipc_response"] = json.loads(response)
print(json.dumps(result, separators=(",", ":")))
"""
BLOCKERS = (
    "NO_OPERATIONAL_WRITER_ACCOUNT_OR_ACL_DEPLOYED",
    "NO_PRODUCTION_PEER_IDENTITY_AUTHORIZATION",
    "NO_EXCLUSIVE_SQLITE_VFS_FD_WAL_SHM_AUTHORITY",
    "NO_EXTERNAL_INTENT_DEDUP_OR_ROLLBACK_CUSTODY",
    "NO_PROVIDER_ACK_OR_OWNER_REVOCATION_PROOF",
    "NO_WINDOWS_NAMED_PIPE_SID_DACL_TEST",
)
MAX_BYTES = 4096


def result_base(status):
    return {
        "schema": SCHEMA, "status": status, "research_only": True,
        "synthetic_fixture_only": True,
        "peer_uid_checked_via_linux_kernel": False,
        "distinct_uid_ipc_local_write_observed": False,
        "restricted_client_direct_file_access_denied": False,
        "same_host_owner_can_bypass_filesystem": False,
        "replay_intent_dedup_proven": False,
        "operational_writer_separate_uid_deployed": False,
        "production_client_file_denial_proven": False,
        "windows_sid_dacl_pipe_attested": False,
        "native_sqlite_vfs_fd_attested": False,
        "independent_ledger_and_provider_ack": False,
        "can_resume": False, "can_resend": False,
        "can_auto_retry": False, "can_authorize_real_effect": False,
        "automatic_retries": 0, "zero_auto_resend": True,
        "hard_no_go": True, "p0_homologated": 0,
        "no_worker_deploy_provider_operations": True,
        "new_paid_services": False, "blocking_requirements": list(BLOCKERS),
    }


def _expected_nobody():
    if (os.name != "posix" or pwd is None
            or not hasattr(socket, "SO_PEERCRED")):
        return None
    try:
        uid = pwd.getpwnam("nobody").pw_uid
    except (KeyError, ImportError, OSError):
        return None
    return uid if type(uid) is int and uid != os.geteuid() else None


def _clean_fixture(root):
    root = Path(root)
    private = root / "a311-lab-a314-private"
    sock = root / SOCKET_NAME
    if (os.name != "posix" or not root.is_absolute()
            or not root.name.startswith("a311-lab-a314-")
            or not root.is_dir() or root.is_symlink()
            or not fixture_root_valid(private)
            or sock.is_symlink()):
        return None
    return private, sock


def _server_once(root):
    fixture = _clean_fixture(root)
    expected_uid = _expected_nobody()
    if fixture is None or expected_uid is None:
        return 2
    private, path = fixture
    os.umask(0o077)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.settimeout(12)
        server.bind(str(path))
        # The host directory is searchable by nobody; peer UID is checked
        # by the kernel, not by a client-supplied JSON identity claim.
        os.chmod(path, 0o666)
        server.listen(1)
        # The parent must not connect until the socket can be reached by
        # the restricted UID; socket pathname existence alone races chmod.
        (Path(root) / READY_NAME).write_text("ready\\n", encoding="utf-8")
        try:
            conn, _ = server.accept()
        except socket.timeout:
            return 3
        with conn:
            conn.settimeout(8)
            try:
                size = struct.calcsize("3i")
                pid, uid, gid = struct.unpack(
                    "3i", conn.getsockopt(socket.SOL_SOCKET,
                                           socket.SO_PEERCRED, size))
                raw = conn.makefile("rb").readline(MAX_BYTES + 1)
                if uid != expected_uid:
                    status, accepted = "PEER_UID_DENIED", False
                elif len(raw) > MAX_BYTES:
                    status, accepted = "REQUEST_TOO_LARGE", False
                else:
                    try:
                        req = json.loads(raw.decode("utf-8"))
                    except (ValueError, UnicodeError):
                        req = None
                    accepted = (type(req) is dict and req == REQUEST
                                and all(type(k) is str for k in req))
                    status = "REQUEST_DENIED"
                    if accepted:
                        a311_req = {
                            "schema": A311_SCHEMA,
                            "action": "CREATE_SYNTHETIC_CONVERSATION",
                            "request_id": REQUEST["request_id"],
                            "title": TITLE,
                        }
                        reply = execute_fixture_request(
                            private, json.dumps(a311_req).encode("utf-8")
                        )
                        status = ("SYNTHETIC_LOCAL_ACK"
                                  if reply.get("status") == "LOCAL_ACKED"
                                  else "LOCAL_WRITE_REFUSED")
                response = {
                    "schema": SCHEMA, "status": status,
                    "server_pid": os.getpid(), "peer_pid": pid,
                    "kernel_peer_uid": uid,
                    "kernel_peer_uid_checked": uid == expected_uid,
                    "db_handle_transmitted": False,
                    "can_authorize_real_effect": False,
                    "hard_no_go": True, "zero_auto_resend": True,
                    "p0_homologated": 0,
                }
                conn.sendall((json.dumps(response) + "\n").encode("utf-8"))
            except (OSError, ValueError, sqlite3.DatabaseError):
                return 4
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return 5
    return 0


def _client_exchange(root, request, *, other_uid, timeout=15):
    fixture = _clean_fixture(root)
    if fixture is None:
        return None
    private, path = fixture
    raw = json.dumps(request, separators=(",", ":"), allow_nan=False)
    if len(raw.encode("utf-8")) > MAX_BYTES:
        return None
    command = [sys.executable, "-c", CLIENT_SCRIPT,
               str(path), str(private / DB_NAME), raw]
    if other_uid:
        import shutil
        sudo = shutil.which("sudo")
        if not sudo:
            return None
        command = [sudo, "-n", "-u", "nobody", "--"] + command
    try:
        completed = subprocess.run(
            command, check=False, timeout=timeout, capture_output=True,
            text=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode or len(completed.stdout) > 3000:
        return None
    try:
        reply = json.loads(completed.stdout)
    except ValueError:
        return None
    return reply if type(reply) is dict else None


def _run_one_exchange(root, request, *, other_uid, timeout=15):
    """One temporary server process; always stop/reap; never auto retry."""
    fixture = _clean_fixture(root)
    if fixture is None:
        return None
    _, path = fixture
    ready = Path(root) / READY_NAME
    ready.unlink(missing_ok=True)
    try:
        server = subprocess.Popen(
            [sys.executable, "-u", "-m",
             "labs.a314_cross_uid_sqlite_socket_lab",
             "--serve-once", str(root)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except OSError:
        return None
    try:
        end = time.monotonic() + min(timeout, 10)
        while (not ready.exists() or not path.exists()) and server.poll() is None:
            if time.monotonic() >= end:
                return None
            time.sleep(0.02)
        if not ready.exists() or not path.exists() or server.poll() is not None:
            return None
        client = _client_exchange(root, request, other_uid=other_uid,
                                  timeout=timeout)
        try:
            stdout, stderr = server.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None
        if server.returncode != 0 or len(stdout) > 100 or len(stderr) > 2000:
            return None
        return client
    finally:
        if server.poll() is None:
            server.kill()
            server.communicate(timeout=5)
        if path.exists() and not path.is_symlink():
            path.unlink()
        ready.unlink(missing_ok=True)


def probe_cross_uid_ipc_fixture(*, timeout_seconds=15):
    if type(timeout_seconds) is not int or not 2 <= timeout_seconds <= 30:
        raise ValueError("A314 test timeout must be 2..30 sec")
    out = result_base("UNTESTED")
    if os.name != "posix" or _expected_nobody() is None:
        out["status"] = "WINDOWS_OR_LINUX_CREDENTIAL_TEST_UNAVAILABLE"
        return out
    import shutil
    if not shutil.which("sudo"):
        out["status"] = "CI_TEST_SUDO_UNAVAILABLE"
        return out
    # Only /tmp, an ephemeral local fixture. No privileged user is created.
    with TemporaryDirectory(prefix="a311-lab-a314-", dir="/tmp") as temp:
        root = Path(temp)
        private = root / "a311-lab-a314-private"
        private.mkdir(mode=0o700)
        create_fixture(private)
        root.chmod(0o711)
        try:
            invalid = _run_one_exchange(
                root, INVALID_REQUEST, other_uid=True,
                timeout=timeout_seconds)
            permitted = _run_one_exchange(
                root, REQUEST, other_uid=True, timeout=timeout_seconds)
            # The owner-UID negative probe follows the initial write so
            # the existing SQLite file can be opened in the client script.
            wrong = _run_one_exchange(
                root, REQUEST, other_uid=False, timeout=timeout_seconds)
            # Repeat the *same request_id* in a new process: this should
            # reveal missing off-host semantic-idempotency custody.
            replay = _run_one_exchange(
                root, REQUEST, other_uid=True, timeout=timeout_seconds)
            out["wrong_uid_response"] = wrong
            out["invalid_action_response"] = invalid
            out["valid_uid_response"] = permitted
            out["replay_response"] = replay
            if not all(type(p) is dict and
                       type(p.get("ipc_response")) is dict
                       for p in (wrong, invalid, permitted, replay)):
                out["status"] = "IPC_PROBE_INCOMPLETE"
                return out
            out["peer_uid_checked_via_linux_kernel"] = all([
                wrong["ipc_response"].get("status") == "PEER_UID_DENIED",
                wrong["ipc_response"].get("kernel_peer_uid_checked") is False,
                invalid["ipc_response"].get("status") == "REQUEST_DENIED",
                invalid["ipc_response"].get("kernel_peer_uid_checked") is True,
                permitted["ipc_response"].get("status") == "SYNTHETIC_LOCAL_ACK",
                permitted["ipc_response"].get("kernel_peer_uid_checked") is True,
                replay["ipc_response"].get("status") == "SYNTHETIC_LOCAL_ACK",
            ])
            out["restricted_client_direct_file_access_denied"] = all(
                p.get("read_denied") is True
                and p.get("write_denied") is True
                and p.get("listdir_denied") is True
                for p in (invalid, permitted, replay)
            )
            db = private / DB_NAME
            if not db.is_file():
                out["status"] = "SYNTHETIC_DB_NOT_CREATED"
                return out
            apply_fixture_private_modes(private)
            with closing(sqlite3.connect(str(db))) as reader:
                count = reader.execute(
                    "SELECT COUNT(*) FROM conversations"
                ).fetchone()[0]
            out["local_conversation_count"] = count
            out["distinct_uid_ipc_local_write_observed"] = (
                out["peer_uid_checked_via_linux_kernel"]
                and out["restricted_client_direct_file_access_denied"]
                and count == 2
            )
            out["same_request_id_created_two_rows"] = count == 2
            # The fixture owner (same UID as writer) can still bypass IPC.
            with closing(sqlite3.connect(str(db))) as same_uid:
                same_uid.execute(
                    "UPDATE conversations SET title=? WHERE title=?",
                    ("A311 TEST same-host-owner-bypass", TITLE),
                )
                same_uid.commit()
                bypassed = same_uid.execute(
                    "SELECT COUNT(*) FROM conversations WHERE title=?",
                    ("A311 TEST same-host-owner-bypass",)
                ).fetchone()[0]
            out["same_host_owner_can_bypass_filesystem"] = bypassed == 2
            out["status"] = (
                "LAB_CROSS_UID_IPC_AND_LIMITS_OBSERVED"
                if (out["distinct_uid_ipc_local_write_observed"]
                    and out["same_host_owner_can_bypass_filesystem"])
                else "OS_IPC_PROOF_INCOMPLETE"
            )
            return out
        finally:
            # Handles were closed; never restore host privileges outside
            # the isolated fixture. Parent mode for reliable CI cleanup.
            root.chmod(0o700)


def assess_operational_writer(*, report):
    out = result_base("HARD_NO_GO_NO_OPERATIONAL_WRITER")
    if type(report) is not dict or report.get("schema") != SCHEMA:
        out["blocking_requirements"].append("MISSING_VERIFIABLE_LAB_REPORT")
    elif report.get("distinct_uid_ipc_local_write_observed") is True:
        out["distinct_uid_ipc_local_write_observed"] = True
    # All claims of P0 ready, outside provider outcome, deployment remain
    # blocked. This local experiment is a negative architectural probe.
    return out


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if len(argv) != 2 or argv[0] != "--serve-once":
        return 2
    return _server_once(argv[1])


if __name__ == "__main__":
    sys.exit(main())
