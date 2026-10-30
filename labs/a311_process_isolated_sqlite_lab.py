"""A311: disposable one-request-per-process SQLite boundary, LAB ONLY.

A separate Python *test subprocess* owns SQLiteChatStore; the parent only
receives JSON results, never a live connection. This does not grant OS-level
file isolation, independent credentials, off-host provenance or P0-6 closure.
No resident Worker, real provider, deployment, transfer or outbound effects.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import mock

from aion_chat.models import Message, Scope
from aion_chat.store import (
    SQLiteChatStore, StorageUnavailableError, StoreCommitOutcomeUncertainError,
)
from labs.a291_chat_write_gate_commit_fence_lab import SyntheticAckLossConnection

SCHEMA = "ATLASQUANT_AION_A311_DISPOSABLE_PROCESS_BOUNDARY_LAB_V1"
FIXTURE_MARKER = ".a311-disposable-synthetic-only"
FIXTURE_CONTENT = "A311 DISPOSABLE LAB ONLY; NO REAL DATA\n"
DB_NAME = "a311-only-synthetic.db"
MAX_REQUEST_BYTES = 4096
MAX_MESSAGES_RETURNED = 20
SCOPE = Scope("a311-fixture-owner", "a311-fixture-tenant",
              "a311-fixture-workspace")
ACTIONS = frozenset({
    "CREATE_SYNTHETIC_CONVERSATION", "APPEND_SYNTHETIC_MESSAGE",
    "READ_SYNTHETIC_MESSAGES", "READ_SYNTHETIC_HEALTH",
})
IDENTIFIER = re.compile(r"[A-Za-z0-9._-]{1,80}\Z")
HEX_ID = re.compile(r"[0-9a-f]{32}\Z")
FIELDS = {
    "CREATE_SYNTHETIC_CONVERSATION": frozenset(
        {"schema", "action", "request_id", "title"}),
    "APPEND_SYNTHETIC_MESSAGE": frozenset(
        {"schema", "action", "request_id", "conversation_id",
         "message_id", "intent_id", "content"}),
    "READ_SYNTHETIC_MESSAGES": frozenset(
        {"schema", "action", "request_id", "conversation_id"}),
    "READ_SYNTHETIC_HEALTH": frozenset(
        {"schema", "action", "request_id"}),
}


def base_response(status, *, request_id=None, **extra):
    return {
        "schema": SCHEMA, "status": status, "request_id": request_id,
        "research_only": True, "child_pid": os.getpid(),
        "sqlite_handle_not_returned": True,
        "independent_os_storage_isolation": False,
        "independent_authority_proven": False,
        "native_sqlite_fd_attested": False,
        "off_host_intent_ledger_proven": False,
        "semantic_exactly_once_proven": False,
        "can_authorize_real_effect": False, "can_resume": False,
        "can_resend": False, "automatic_retries": 0,
        "zero_auto_resend": True, "hard_no_go": True,
        "p0_homologated": 0, "new_paid_services": False,
        "no_worker_deploy_provider_calls": True, **extra,
    }


def fixture_root_valid(folder):
    try:
        path = Path(folder)
        if not path.is_absolute() or not path.name.startswith("a311-lab-"):
            return False
        if path.is_symlink() or not path.is_dir():
            return False
        marker = path / FIXTURE_MARKER
        if marker.is_symlink() or not marker.is_file():
            return False
        return marker.read_text(encoding="utf-8") == FIXTURE_CONTENT
    except (OSError, TypeError, ValueError):
        return False


def create_fixture(directory):
    """Fixture creation is explicit in the tests, never a production path."""
    path = Path(directory)
    if (not path.is_absolute() or not path.name.startswith("a311-lab-")
            or path.is_symlink() or not path.is_dir()):
        raise ValueError("A311 requires a disposable a311-lab- directory")
    marker = path / FIXTURE_MARKER
    with marker.open("x", encoding="utf-8") as handle:
        handle.write(FIXTURE_CONTENT)
    return path


def _valid_request(req):
    if type(req) is not dict:
        return False
    action = req.get("action")
    if type(action) is not str or action not in ACTIONS:
        return False
    if set(req) != FIELDS[action] or req.get("schema") != SCHEMA:
        return False
    request_id = req.get("request_id")
    if type(request_id) is not str or not IDENTIFIER.fullmatch(request_id):
        return False
    if action == "CREATE_SYNTHETIC_CONVERSATION":
        title = req["title"]
        return (type(title) is str and 1 <= len(title) <= 100
                and title.startswith("A311 TEST "))
    if action == "APPEND_SYNTHETIC_MESSAGE":
        return (
            type(req["conversation_id"]) is str
            and HEX_ID.fullmatch(req["conversation_id"]) is not None
            and type(req["message_id"]) is str
            and IDENTIFIER.fullmatch(req["message_id"]) is not None
            and type(req["intent_id"]) is str
            and IDENTIFIER.fullmatch(req["intent_id"]) is not None
            and type(req["content"]) is str
            and 1 <= len(req["content"]) <= 512
            and req["content"].startswith("A311 TEST ")
        )
    if action == "READ_SYNTHETIC_MESSAGES":
        return (type(req["conversation_id"]) is str
                and HEX_ID.fullmatch(req["conversation_id"]) is not None)
    return True


def _no_duplicate_json_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("repeated JSON key")
        result[key] = value
    return result


def execute_fixture_request(folder, raw, *, inject_ack_after_commit=False):
    """Run once inside child; never run a customer/operational command."""
    if not fixture_root_valid(folder):
        return base_response("FIXTURE_REFUSED")
    if type(raw) is not bytes or len(raw) > MAX_REQUEST_BYTES:
        return base_response("MALFORMED_REQUEST")
    try:
        req = json.loads(raw.decode("utf-8"),
                         object_pairs_hook=_no_duplicate_json_keys)
    except (ValueError, TypeError, UnicodeError):
        return base_response("MALFORMED_REQUEST")
    if not _valid_request(req):
        return base_response("REQUEST_DENIED")
    action = req["action"]
    request_id = req["request_id"]
    if inject_ack_after_commit and action != "APPEND_SYNTHETIC_MESSAGE":
        return base_response("FAULT_INJECTION_RESTRICTED", request_id=request_id)
    db_path = Path(folder) / DB_NAME
    store = None
    try:
        if inject_ack_after_commit:
            # Test-only subclass simulates COMMIT applied, ACK not received.
            actual_connect = sqlite3.connect

            def synthetic_connect(*args, **kwargs):
                return actual_connect(*args, **kwargs,
                                      factory=SyntheticAckLossConnection)
            with mock.patch("aion_chat.store.sqlite3.connect",
                            side_effect=synthetic_connect):
                store = SQLiteChatStore(
                    db_path, strict_local_data_version=True,
                    strict_private_write_helpers=True,
                    strict_sql_authorizer=True,
                )
        else:
            store = SQLiteChatStore(
                db_path, strict_local_data_version=True,
                strict_private_write_helpers=True,
                strict_sql_authorizer=True,
            )
        if action == "CREATE_SYNTHETIC_CONVERSATION":
            conv = store.create_conversation(SCOPE, req["title"])
            return base_response("LOCAL_ACKED", request_id=request_id,
                                 conversation_id=conv.id)
        if action == "APPEND_SYNTHETIC_MESSAGE":
            msg = Message(
                req["conversation_id"], "user", req["content"],
                id=req["message_id"],
                metadata={"a311_synthetic_intent_id": req["intent_id"]},
            )
            if inject_ack_after_commit:
                store.db.fault_once = "after"
            recorded = store.append_message(SCOPE, msg)
            return base_response("LOCAL_ACKED", request_id=request_id,
                                 message_id=recorded.id,
                                 message_sequence=recorded.sequence)
        if action == "READ_SYNTHETIC_MESSAGES":
            page = store.list_messages(SCOPE, req["conversation_id"],
                                       page_size=MAX_MESSAGES_RETURNED)
            return base_response("READ_ONLY_RESULT", request_id=request_id,
                                 message_ids=[item.id for item in page.items],
                                 message_sequences=[
                                     item.sequence for item in page.items
                                 ],
                                 has_more=page.next_cursor is not None)
        if action == "READ_SYNTHETIC_HEALTH":
            result = store.storage_health(deep=True)
            return base_response("READ_ONLY_RESULT", request_id=request_id,
                                 local_health=result["state"],
                                 strict_authorizer=store._strict_sql_authorizer)
        return base_response("REQUEST_DENIED", request_id=request_id)
    except StoreCommitOutcomeUncertainError:
        # The one test message may already be committed. NO RETRY OR REOPEN.
        return base_response("ACK_UNKNOWN_QUARANTINE", request_id=request_id)
    except sqlite3.IntegrityError:
        return base_response("DUPLICATE_OR_CONSTRAINT_DENIED",
                             request_id=request_id)
    except (StorageUnavailableError, sqlite3.DatabaseError, LookupError):
        return base_response("LOCAL_STORE_QUARANTINED_OR_DENIED",
                             request_id=request_id)
    except (TypeError, ValueError, AttributeError, OSError):
        return base_response("LOCAL_REQUEST_FAILED_CLOSED",
                             request_id=request_id)
    finally:
        if store is not None:
            store.close()


def run_lab_request(folder, request, *, inject_ack_after_commit=False,
                    timeout_seconds=15):
    """One subprocess per request. No persistent daemon, no retry loop."""
    if (type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 60):
        raise ValueError("timeout_seconds must be 1..60")
    try:
        raw = json.dumps(request, allow_nan=False,
                         separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return base_response("MALFORMED_REQUEST")
    if len(raw) > MAX_REQUEST_BYTES:
        return base_response("MALFORMED_REQUEST")
    argv = [sys.executable, "-u", "-m",
            "labs.a311_process_isolated_sqlite_lab", "--fixture-child",
            str(folder)]
    if inject_ack_after_commit:
        argv.append("--inject-ack-loss")
    try:
        completed = subprocess.run(
            argv, input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout_seconds, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return base_response("IPC_UNKNOWN_QUARANTINE")
    if completed.returncode != 0 or len(completed.stdout) > MAX_REQUEST_BYTES:
        return base_response("CHILD_EXIT_UNTRUSTED")
    try:
        value = json.loads(completed.stdout.decode("utf-8"))
    except (ValueError, UnicodeError):
        return base_response("CHILD_REPLY_INVALID")
    if (type(value) is not dict or value.get("schema") != SCHEMA
            or value.get("zero_auto_resend") is not True
            or value.get("hard_no_go") is not True
            or value.get("p0_homologated") != 0
            or value.get("can_authorize_real_effect") is not False):
        return base_response("CHILD_REPLY_UNTRUSTED")
    return value


def _child_main(folder, *, inject_ack_loss):
    # Process isolation is not filesystem ACL isolation; caller could forge
    # the marker and open/overwrite the DB. Tests show this counterexample.
    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    result = execute_fixture_request(
        folder, raw, inject_ack_after_commit=inject_ack_loss,
    )
    sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")
    sys.stdout.flush()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="A311 disposable LAB only")
    parser.add_argument("--fixture-child")
    parser.add_argument("--inject-ack-loss", action="store_true")
    opts = parser.parse_args(argv)
    if not opts.fixture_child:
        return 2
    return _child_main(opts.fixture_child,
                       inject_ack_loss=opts.inject_ack_loss)


if __name__ == "__main__":
    sys.exit(main())
