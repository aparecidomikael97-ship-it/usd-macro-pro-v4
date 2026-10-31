"""A329 LAB: COMMIT happened, ACK was lost, and another PID was already open.

Only freshly created A315 synthetic SQLite fixtures are used. The second
process opens before the first process' real SQLite COMMIT/ACK fault and then
tries the same intent. This is a bounded cross-PID *local* experiment; it
does not authorize external replay, recovery, Worker, provider or P0 closure.
"""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from unittest import mock

from aion_chat.models import Message, Scope
from aion_chat.store import (
    SQLiteChatStore, StorageUnavailableError,
    StoreCommitOutcomeUncertainError,
)
from labs.a291_chat_write_gate_commit_fence_lab import SyntheticAckLossConnection

SCHEMA = "ATLASQUANT_AION_A329_CONCURRENT_UNKNOWN_COMMIT_LAB_V1"
SCOPE = Scope("a329-owner", "a329-tenant", "a329-workspace")
INTENT = "a329-uncertain-same-intent"
BODY = "A315 TEST A329 synthetic uncertain COMMIT"
MARKER = ".a315-synthetic-only"
MARKER_CONTENT = "A315 DISPOSABLE SYNTHETIC LAB ONLY\n"

CHILD = r"""
import json, os, sys, time
from pathlib import Path
from aion_chat.models import Message, Scope
from aion_chat.store import SQLiteChatStore, StorageUnavailableError

db, cid, ready, go = sys.argv[1:]
store = None
out = {"pid": os.getpid(), "status": "LAB_CHILD_ERROR",
       "hard_no_go": True, "zero_auto_resend": True,
       "p0_homologated": 0, "automatic_retries": 0}
try:
    store = SQLiteChatStore(
        db, strict_local_data_version=True,
        strict_private_write_helpers=True, strict_sql_authorizer=True,
        strict_semantic_intent=True,
    )
    Path(ready).write_text("ready", encoding="utf-8")
    deadline = time.monotonic() + 12
    while not Path(go).exists():
        if time.monotonic() > deadline:
            raise TimeoutError("A329 bounded barrier expired")
        time.sleep(0.01)
    result = store.append_message_once(
        Scope("a329-owner", "a329-tenant", "a329-workspace"),
        Message(cid, "user", "A315 TEST A329 synthetic uncertain COMMIT",
                id="a329-other-process-transport"),
        intent_id="a329-uncertain-same-intent",
    )
    out.update({
        "status": result["status"],
        "hard_no_go": result["hard_no_go"],
        "zero_auto_resend": result["zero_auto_resend"],
        "p0_homologated": result["p0_homologated"],
        "automatic_retries": result["automatic_retries"],
    })
except StorageUnavailableError:
    out["status"] = "STORAGE_DENIED"
except Exception as exc:
    out["status"] = "LAB_CHILD_ERROR"
    out["error_type"] = type(exc).__name__
finally:
    if store is not None:
        try:
            store.close()
        except Exception:
            out["status"] = "LAB_CHILD_CLOSE_ERROR"
print(json.dumps(out, sort_keys=True), flush=True)
"""


def _base():
    return {
        "schema": SCHEMA, "research_only": True,
        "synthetic_only": True, "real_native_sqlite_commit": True,
        "two_distinct_processes": False,
        "synthetic_ack_loss_only": True,
        "off_host_ledger_authenticated": False,
        "external_provider_ack_authenticated": False,
        "independent_writer_or_file_custody": False,
        "native_fd_vfs_wal_identity_attested": False,
        "power_loss_survival_proven": False,
        "cross_host_semantic_exactly_once_proven": False,
        "can_resume": False, "can_resend": False,
        "can_auto_retry": False, "can_authorize_real_effect": False,
        "automatic_retries": 0, "zero_auto_resend": True,
        "hard_no_go": True, "p0_homologated": 0,
        "no_worker_deploy_provider_orders": True,
        "new_paid_services": False,
    }


def _open(path):
    return SQLiteChatStore(
        path, strict_local_data_version=True,
        strict_private_write_helpers=True, strict_sql_authorizer=True,
        strict_semantic_intent=True,
    )


def _count(path, table):
    if table not in ("messages", "a315_local_intent_receipts"):
        raise ValueError("A329 only permits synthetic receipt/message tables")
    with closing(sqlite3.connect(str(path))) as db:
        return db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]


def _quick_check(path):
    with closing(sqlite3.connect(str(path))) as db:
        return db.execute("PRAGMA quick_check").fetchone()[0] == "ok"


def probe_unknown_commit_with_preconnected_rival(*, timeout_seconds=25):
    """Observe genuine SQLite COMMIT + lost ACK and preconnected rival PID."""
    if type(timeout_seconds) is not int or not 5 <= timeout_seconds <= 40:
        raise ValueError("A329 timeout must be 5..40")
    out = _base()
    with TemporaryDirectory(prefix="a315-lab-a329-") as raw:
        folder = Path(raw)
        path = folder / "only-synthetic.sqlite"
        ready = folder / "rival-connection-open"
        go = folder / "rival-may-attempt"
        if not folder.name.startswith("a315-lab-a329-") or path.exists():
            raise RuntimeError("A329 demands a fresh marked lab fixture")
        (folder / MARKER).write_text(MARKER_CONTENT, encoding="utf-8")
        setup = _open(path)
        try:
            cid = setup.create_conversation(
                SCOPE, "A315 TEST A329 synthetic COMMIT race"
            ).id
        finally:
            setup.close()

        raw_connect = sqlite3.connect

        def synthetic_connect(*args, **kwargs):
            return raw_connect(
                *args, **kwargs, factory=SyntheticAckLossConnection
            )

        with mock.patch(
            "aion_chat.store.sqlite3.connect", side_effect=synthetic_connect
        ):
            writer = _open(path)
        child = None
        try:
            child = subprocess.Popen(
                [
                    sys.executable, "-u", "-c", CHILD,
                    str(path), cid, str(ready), str(go),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True,
            )
            deadline = time.monotonic() + min(timeout_seconds, 15)
            while (not ready.exists() and child.poll() is None
                   and time.monotonic() < deadline):
                time.sleep(0.01)
            out["other_process_open_before_fault"] = (
                ready.exists() and child.poll() is None
            )
            out["parent_pid_distinct"] = child.pid is not None
            if not out["other_process_open_before_fault"]:
                out["status"] = "LAB_RIVAL_OPEN_NOT_VERIFIED_HOLD"
                go.write_text("abort", encoding="utf-8")
            else:
                writer.db.fault_once = "after"
                try:
                    writer.append_message_once(
                        SCOPE,
                        Message(cid, "user", BODY,
                                id="a329-parent-transport"),
                        intent_id=INTENT,
                    )
                    out["parent_fault_status"] = "UNEXPECTED_ACK"
                except StoreCommitOutcomeUncertainError:
                    out["parent_fault_status"] = "COMMIT_OUTCOME_UNKNOWN"
                except StorageUnavailableError:
                    out["parent_fault_status"] = "STORAGE_DENIED"
                out["parent_pending_marker_before_release"] = (
                    writer._message_commit_marker.exists()
                )
                out["parent_health_reason"] = writer._health_reason
                out["parent_retry_denied"] = False
                try:
                    writer.append_message_once(
                        SCOPE,
                        Message(cid, "user", BODY,
                                id="a329-parent-forbidden-retry"),
                        intent_id=INTENT,
                    )
                except StorageUnavailableError:
                    out["parent_retry_denied"] = True
                go.write_text("attempt", encoding="utf-8")
            try:
                stdout, stderr = child.communicate(timeout=timeout_seconds)
                if child.returncode or len(stdout) > 4000 or len(stderr) > 4000:
                    out["rival_report"] = {"status": "LAB_CHILD_EXIT_INVALID"}
                else:
                    parsed = json.loads(stdout)
                    out["rival_report"] = (
                        parsed if type(parsed) is dict
                        else {"status": "LAB_CHILD_OUTPUT_INVALID"}
                    )
            except (subprocess.TimeoutExpired, ValueError):
                out["rival_report"] = {"status": "LAB_CHILD_TIMEOUT_OR_JSON_ERROR"}
        finally:
            if child is not None:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=5)
            writer.close()

        out["final_message_count"] = _count(path, "messages")
        out["final_intent_receipt_count"] = _count(
            path, "a315_local_intent_receipts"
        )
        out["sqlite_integrity_ok"] = _quick_check(path)
        out["pending_marker_persisted"] = (
            Path(str(path) + ".aion-message-commit-pending").exists()
        )
        out["fresh_strict_open_denied"] = False
        try:
            fresh = _open(path)
        except StorageUnavailableError:
            out["fresh_strict_open_denied"] = True
        else:
            fresh.close()

        child_data = out.get("rival_report", {})
        out["two_distinct_processes"] = (
            type(child_data.get("pid")) is int
            and out["parent_pid_distinct"]
        )
        out["rival_did_not_reack"] = (
            child_data.get("status") in (
                "STORAGE_DENIED", "DUPLICATE_LOCAL_NO_EFFECT"
            )
        )
        out["unknown_commit_quarantined_locally"] = all((
            out["other_process_open_before_fault"],
            out["two_distinct_processes"],
            out.get("parent_fault_status") == "COMMIT_OUTCOME_UNKNOWN",
            out.get("parent_health_reason")
                == "COMMIT_OUTCOME_UNKNOWN_ZERO_AUTO_RETRY",
            out.get("parent_pending_marker_before_release") is True,
            out.get("parent_retry_denied") is True,
            out["pending_marker_persisted"],
            out["fresh_strict_open_denied"],
            out["rival_did_not_reack"],
            out["final_message_count"] == 1,
            out["final_intent_receipt_count"] == 1,
            out["sqlite_integrity_ok"],
        ))
        out["status"] = (
            "LAB_UNKNOWN_COMMIT_HOLD_WITH_PRECONNECTED_RIVAL"
            if out["unknown_commit_quarantined_locally"]
            else "LAB_UNKNOWN_COMMIT_RACE_UNRESOLVED_HOLD"
        )
    return out


__all__ = [
    "SCHEMA", "probe_unknown_commit_with_preconnected_rival",
]
