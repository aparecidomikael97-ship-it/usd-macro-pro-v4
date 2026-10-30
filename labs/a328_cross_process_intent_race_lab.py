"""A328 LAB: real two-PID race on one A315 semantic intent.

Two short-lived Python child processes attempt exactly one synthetic local
write each against a brand-new marked SQLiteChatStore. They share an intent
but use distinct transport IDs. No provider/Worker/network/deploy/real data.
This does NOT prove independent writer custody, cross-host idempotency,
power-loss safety, native VFS/FD identity, or P0-5/P0-6 closure.
"""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore

SCHEMA = "ATLASQUANT_AION_A328_CROSS_PROCESS_SEMANTIC_RACE_LAB_V1"
SCOPE = Scope("a328-owner", "a328-tenant", "a328-workspace")
MARKER = ".a315-synthetic-only"
MARKER_CONTENT = "A315 DISPOSABLE SYNTHETIC LAB ONLY\n"
CHILD_BODY = "A315 TEST A328 two-process synthetic race"
INTENT = "a328-identical-intent"

CHILD = r"""
import json, os, sys, time
from pathlib import Path
from aion_chat.models import Message, Scope
from aion_chat.store import SQLiteChatStore, StorageUnavailableError

db, cid, intent, transport, ready, go = sys.argv[1:]
store = None
result = {"pid": os.getpid(), "status": "LAB_CHILD_ERROR",
          "hard_no_go": True, "p0_homologated": 0,
          "zero_auto_resend": True, "automatic_retries": 0}
try:
    store = SQLiteChatStore(
        db, strict_local_data_version=True,
        strict_private_write_helpers=True,
        strict_sql_authorizer=True, strict_semantic_intent=True,
    )
    Path(ready).write_text("ready", encoding="utf-8")
    deadline = time.monotonic() + 10
    while not Path(go).exists():
        if time.monotonic() > deadline:
            raise TimeoutError("A328 finite test barrier expired")
        time.sleep(0.01)
    r = store.append_message_once(
        Scope("a328-owner", "a328-tenant", "a328-workspace"),
        Message(cid, "user", "A315 TEST A328 two-process synthetic race",
                id=transport),
        intent_id=intent,
    )
    result.update({
        "status": r["status"], "hard_no_go": r["hard_no_go"],
        "p0_homologated": r["p0_homologated"],
        "zero_auto_resend": r["zero_auto_resend"],
        "automatic_retries": r["automatic_retries"],
    })
except StorageUnavailableError:
    result["status"] = "STORAGE_DENIED"
except Exception as exc:
    result["status"] = "LAB_CHILD_ERROR"
    result["error_type"] = type(exc).__name__
finally:
    if store is not None:
        try:
            store.close()
        except Exception:
            result["status"] = "LAB_CHILD_CLOSE_ERROR"
print(json.dumps(result, sort_keys=True), flush=True)
"""


def _base():
    return {
        "schema": SCHEMA, "research_only": True,
        "synthetic_fixture_only": True,
        "actual_distinct_processes_used": False,
        "strict_semantic_intent_enabled": True,
        "independent_writer_authority": False,
        "off_host_high_water_custody": False,
        "native_sqlite_vfs_fd_identity_verified": False,
        "operational_cross_host_exactly_once": False,
        "provider_effect_or_ack_verified": False,
        "power_loss_durability_proven": False,
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
        strict_private_write_helpers=True,
        strict_sql_authorizer=True,
        strict_semantic_intent=True,
    )


def _count(path, table):
    if table not in ("messages", "a315_local_intent_receipts"):
        raise ValueError("A328 only permits synthetic fixture tables")
    with closing(sqlite3.connect(str(path))) as conn:
        return conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]


def _quick_check(path):
    with closing(sqlite3.connect(str(path))) as conn:
        return conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"


def probe_two_process_same_intent(*, timeout_seconds=25):
    """Run two bounded child processes against the same temporary SQLite DB."""
    if type(timeout_seconds) is not int or not 5 <= timeout_seconds <= 40:
        raise ValueError("A328 timeout must be 5..40 seconds")
    out = _base()
    with TemporaryDirectory(prefix="a315-lab-a328-") as raw:
        folder = Path(raw)
        db = folder / "only-synthetic.sqlite"
        go = folder / "release-both-a328"
        if not folder.name.startswith("a315-lab-a328-") or db.exists():
            raise RuntimeError("A328 requires a new marked disposable fixture")
        (folder / MARKER).write_text(MARKER_CONTENT, encoding="utf-8")
        seed = _open(db)
        try:
            cid = seed.create_conversation(
                SCOPE, "A315 TEST A328 synthetic race"
            ).id
        finally:
            seed.close()
        children = []
        responses = []
        ready_files = [folder / "child-a-ready", folder / "child-b-ready"]
        try:
            for index, name in enumerate(("a328-transport-a", "a328-transport-b")):
                command = [
                    sys.executable, "-u", "-c", CHILD, str(db), cid, INTENT,
                    name, str(ready_files[index]), str(go),
                ]
                children.append(subprocess.Popen(
                    command, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True,
                ))
            deadline = time.monotonic() + min(timeout_seconds, 15)
            while (not all(p.exists() for p in ready_files)
                   and all(p.poll() is None for p in children)
                   and time.monotonic() < deadline):
                time.sleep(0.01)
            out["both_ready_at_release"] = all(
                item.exists() for item in ready_files
            )
            go.write_text("run", encoding="utf-8")
            for child in children:
                try:
                    stdout, stderr = child.communicate(timeout=timeout_seconds)
                    if (child.returncode != 0 or len(stdout) > 4000
                            or len(stderr) > 4000):
                        responses.append({
                            "status": "LAB_CHILD_EXIT_INVALID",
                            "returncode": child.returncode,
                        })
                    else:
                        parsed = json.loads(stdout)
                        responses.append(
                            parsed if type(parsed) is dict
                            else {"status": "LAB_CHILD_OUTPUT_INVALID"}
                        )
                except (subprocess.TimeoutExpired, ValueError):
                    responses.append({"status": "LAB_CHILD_TIMEOUT_OR_JSON_ERROR"})
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=5)

        out["child_reports"] = responses
        out["actual_distinct_processes_used"] = (
            len(responses) == 2
            and all(type(r.get("pid")) is int for r in responses)
            and responses[0]["pid"] != responses[1]["pid"]
        )
        statuses = [r.get("status") for r in responses]
        out["local_acked_count"] = statuses.count("LOCAL_ACKED_ONCE")
        out["local_duplicate_count"] = statuses.count("DUPLICATE_LOCAL_NO_EFFECT")
        out["local_denial_count"] = statuses.count("STORAGE_DENIED")
        out["child_error_count"] = sum(
            status not in (
                "LOCAL_ACKED_ONCE", "DUPLICATE_LOCAL_NO_EFFECT",
                "STORAGE_DENIED",
            ) for status in statuses
        )
        out["sqlite_quick_check_ok"] = _quick_check(db)
        out["message_count"] = _count(db, "messages")
        out["intent_receipt_count"] = _count(
            db, "a315_local_intent_receipts"
        )
        out["same_intent_single_local_effect_observed"] = (
            out["both_ready_at_release"]
            and out["actual_distinct_processes_used"]
            and out["child_error_count"] == 0
            and out["local_acked_count"] == 1
            and out["message_count"] == 1
            and out["intent_receipt_count"] == 1
            and out["sqlite_quick_check_ok"]
        )
        out["status"] = (
            "LAB_ONE_LOCAL_ACK_NO_OPERATIONAL_AUTHORITY"
            if out["same_intent_single_local_effect_observed"]
            else "LAB_CONCURRENT_WRITE_UNRESOLVED_HOLD"
        )
    return out


__all__ = [
    "SCHEMA", "probe_two_process_same_intent",
]
