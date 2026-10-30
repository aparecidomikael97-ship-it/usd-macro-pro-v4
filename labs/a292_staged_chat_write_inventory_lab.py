"""A292 LAB: exact staged-chat write inventory and real COMMIT-ACK matrix.

Static AST catches unexpected SQLiteChatStore self.db DML and changes to the
six known business-writing pathways; native synthetic ACK loss checks each
existing writer. The scanner is bounded and syntactic, NOT a general proof
of no dynamic SQL, host custody, native VFS/FD identity, or provider effects.
"""
import ast
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
from tempfile import TemporaryDirectory
from unittest import mock

from aion_chat.models import (
    Attachment, ContextSummary, ConversationCheckpoint, Message, Scope,
)
from aion_chat.store import (
    FAILED, HEALTHY, SQLiteChatStore,
    StorageUnavailableError, StoreCommitOutcomeUncertainError,
)
from labs.a291_chat_write_gate_commit_fence_lab import SyntheticAckLossConnection

SCHEMA = "ATLASQUANT_AION_STAGED_CHAT_WRITE_INVENTORY_LAB_V1"
SOURCE = Path(__file__).resolve().parents[1] / "aion_chat" / "store.py"
SCOPE = Scope("owner-a292", "tenant-a292", "workspace-a292")
WRITE_ENTRYPOINTS = frozenset((
    "create_conversation", "append_message", "archive_conversation",
    "add_attachment_metadata", "save_checkpoint", "save_context_summary",
))
LAB_ONLY_ENTRYPOINTS = frozenset(("append_message_once",))
DIRECT_FENCED = frozenset((
    "create_conversation", "append_message", "append_message_once",
))
TRANSACTION_FENCED = WRITE_ENTRYPOINTS - DIRECT_FENCED
DIRECT_DML = {
    # A315 creates an opt-in-only local receipt schema on startup; this
    # maintenance DDL must remain visible to the static inventory.
    "__init__": ("CREATE",),
    "_update": ("UPDATE",),
    "_save_record": ("INSERT",),
    "create_conversation": ("INSERT",),
    "append_message": ("INSERT",),
    # A315 opt-in: one real message INSERT and one local intent receipt
    # INSERT inside the *same* fenced SQLite COMMIT.
    "append_message_once": ("INSERT", "INSERT"),
}
HELPERS_WITH_RAW_DML = frozenset(("_update", "_save_record"))
SENSITIVE_SQL = frozenset((
    "INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "DROP",
    "ALTER", "ATTACH", "DETACH",
))
FAULTS = frozenset(("before", "after"))


def _base():
    return {
        "schema": SCHEMA,
        "research_only": True,
        "real_native_sqlite": True,
        "no_provider_worker_deploy_orders": True,
        "zero_auto_resend": True,
        "can_authorize_send": False,
        "p0_homologated": 0,
        "independent_owner_proof": False,
        "native_fd_authenticated": False,
        "off_host_rollback_witness": False,
        "complete_path_proof": False,
    }


def _first_sql_token(expression, bindings):
    if isinstance(expression, ast.Constant) and type(expression.value) is str:
        match = re.match(r"\s*([a-zA-Z]+)", expression.value)
        return match.group(1).upper() if match else "UNKNOWN"
    if isinstance(expression, ast.JoinedStr):
        if expression.values and isinstance(expression.values[0], ast.Constant):
            return _first_sql_token(expression.values[0], bindings)
    if isinstance(expression, ast.Name):
        value = bindings.get(expression.id)
        return _first_sql_token(value, {}) if value is not None else "UNKNOWN"
    if isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Add):
        return _first_sql_token(expression.left, bindings)
    return "UNKNOWN"


def _self_db_call(call):
    if not isinstance(call, ast.Call):
        return None
    target = call.func
    if not isinstance(target, ast.Attribute):
        return None
    receiver = target.value
    if not isinstance(receiver, ast.Attribute):
        return None
    if (
        not isinstance(receiver.value, ast.Name)
        or receiver.value.id != "self"
        or receiver.attr != "db"
    ):
        return None
    return target.attr


def inspect_store_writers(*, source=None):
    """Fail closed on unexpected direct DML, commit sink or fence removal.

    This inventory deliberately says nothing about calls through OTHER
    connection variables, dynamic SQL outside the SQLiteChatStore class,
    OS-level restore writes, or malicious Python callers of helper methods.
    """
    if source is None:
        source = SOURCE.read_text(encoding="utf-8")
    if type(source) is not str or len(source) > 200_000:
        raise ValueError("invalid bounded source")
    result = _base()
    result.update({
        "static_only": True, "source_bytes": len(source.encode("utf-8")),
        "write_entrypoints": sorted(WRITE_ENTRYPOINTS),
        "lab_only_entrypoints": sorted(LAB_ONLY_ENTRYPOINTS),
        "unguarded_private_helpers": sorted(HELPERS_WITH_RAW_DML),
        "separate_maintenance_scope": [
            "__init__", "backup_to", "restore_from_backup",
            "wal_checkpoint", "_wal_checkpoint_under_lifecycle_lock",
        ],
        "direct_dml_by_method": {},
        "issues": [],
    })
    try:
        tree = ast.parse(source)
    except SyntaxError:
        result["issues"].append("SOURCE_SYNTAX_INVALID")
        result["valid_contract"] = False
        return result
    stores = [
        node for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "SQLiteChatStore"
    ]
    if len(stores) != 1:
        result["issues"].append("SQLITE_CHAT_STORE_CLASS_NOT_UNIQUE")
        result["valid_contract"] = False
        return result
    methods = {
        node.name: node for node in stores[0].body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    issues = result["issues"]
    dml = {}
    commits = []
    scripts = []
    backups = []
    for name, method in methods.items():
        bound = {}
        for node in ast.walk(method):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if (
                isinstance(target, ast.Name)
                and isinstance(node.value, ast.Constant)
                and type(node.value.value) is str
            ):
                bound[target.id] = node.value
            elif isinstance(target, ast.Tuple) and isinstance(
                node.value, ast.Tuple
            ):
                for key, value in zip(target.elts, node.value.elts):
                    if (
                        isinstance(key, ast.Name)
                        and isinstance(value, ast.Constant)
                        and type(value.value) is str
                    ):
                        bound[key.id] = value
        ops = []
        for node in ast.walk(method):
            call_type = _self_db_call(node)
            if call_type == "execute":
                sql_op = (
                    _first_sql_token(node.args[0], bound)
                    if node.args else "UNKNOWN"
                )
                if sql_op in SENSITIVE_SQL:
                    ops.append(sql_op)
                elif sql_op == "UNKNOWN":
                    issues.append("UNRESOLVED_SQL:" + name)
            elif call_type == "commit":
                commits.append(name)
            elif call_type == "executescript":
                scripts.append(name)
            elif call_type == "backup":
                backups.append(name)
        if ops:
            dml[name] = tuple(sorted(ops))
    result["direct_dml_by_method"] = {
        method: list(values) for method, values in sorted(dml.items())
    }
    if dml != DIRECT_DML:
        issues.append("DIRECT_DML_METHOD_SET_OR_SQL_CHANGED")
    if sorted(commits) != ["_commit_fenced_chat_write"]:
        issues.append("UNEXPECTED_DIRECT_COMMIT_SINK")
    if sorted(scripts) != ["__init__"]:
        issues.append("UNEXPECTED_SCHEMA_SCRIPT_SINK")
    if sorted(backups) != ["backup_to"]:
        issues.append("UNEXPECTED_BACKUP_SINK")
    for name in WRITE_ENTRYPOINTS | LAB_ONLY_ENTRYPOINTS:
        method = methods.get(name)
        if method is None:
            issues.append("MISSING_WRITER:" + name)
            continue
        decorated = any(
            isinstance(d, ast.Name) and d.id == "_local_commit_gate"
            for d in method.decorator_list
        )
        calls = {
            node.func.attr for node in ast.walk(method)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
        }
        if not decorated:
            issues.append("WRITER_MISSING_LOCAL_LOCK:" + name)
        required = (
            "_commit_fenced_chat_write"
            if name in DIRECT_FENCED else "_fenced_chat_transaction"
        )
        if required not in calls:
            issues.append("WRITER_MISSING_COMMIT_FENCE:" + name)
    for helper in HELPERS_WITH_RAW_DML:
        if helper not in methods:
            issues.append("RAW_HELPER_MISSING:" + helper)
    result["issues"] = sorted(set(issues))
    result["valid_contract"] = not result["issues"]
    return result


def _open_ack_connection(path):
    original_connect = sqlite3.connect

    def factory_connect(*args, **kwargs):
        return original_connect(
            *args, **kwargs, factory=SyntheticAckLossConnection
        )

    with mock.patch(
        "aion_chat.store.sqlite3.connect", side_effect=factory_connect
    ):
        return SQLiteChatStore(path, strict_local_data_version=True)


def _synthetic_attachment(cid):
    digest = "a" * 64
    return Attachment(
        cid, "a292.txt", "text/plain", 1, digest, digest + ".blob"
    )


def _prepare_writer(store, writer):
    if writer == "create_conversation":
        return None, lambda: store.create_conversation(SCOPE, "faulted")
    conv = store.create_conversation(SCOPE, "seed")
    if writer == "append_message":
        msg = Message(
            conv.id, "user", "faulted", id="a292-faulted-message"
        )
        return conv.id, lambda: store.append_message(SCOPE, msg)
    if writer == "archive_conversation":
        return conv.id, lambda: store.archive_conversation(SCOPE, conv.id)
    if writer == "add_attachment_metadata":
        a = _synthetic_attachment(conv.id)
        return conv.id, lambda: store.add_attachment_metadata(SCOPE, a)
    if writer in ("save_checkpoint", "save_context_summary"):
        msg = store.append_message(
            SCOPE, Message(conv.id, "user", "seed", id="a292-seed-message")
        )
        if writer == "save_checkpoint":
            cp = ConversationCheckpoint(conv.id, msg.sequence)
            return conv.id, lambda: store.save_checkpoint(SCOPE, cp)
        summary = ContextSummary(
            conv.id, msg.sequence, "seed summary",
            source_message_ids=[msg.id],
        )
        return conv.id, lambda: store.save_context_summary(SCOPE, summary)
    raise ValueError("unsupported writer")


def _external_effect_count(path, writer, cid):
    with closing(sqlite3.connect(str(path))) as db:
        if writer == "create_conversation":
            sql, args = "SELECT COUNT(*) FROM conversations", ()
        elif writer == "append_message":
            sql, args = "SELECT COUNT(*) FROM messages WHERE cid=?", (cid,)
        elif writer == "archive_conversation":
            sql, args = (
                "SELECT COUNT(*) FROM conversations WHERE id=? AND archived=1",
                (cid,),
            )
        else:
            kind = {
                "add_attachment_metadata": "attachment",
                "save_checkpoint": "checkpoint",
                "save_context_summary": "summary",
            }[writer]
            sql, args = (
                "SELECT COUNT(*) FROM records WHERE cid=? AND kind=?",
                (cid, kind),
            )
        return db.execute(sql, args).fetchone()[0]


def probe_one_writer_ack_boundary(*, writer="append_message", phase="after"):
    if type(writer) is not str or writer not in WRITE_ENTRYPOINTS:
        raise ValueError("unsupported staged-chat writer")
    if type(phase) is not str or phase not in FAULTS:
        raise ValueError("invalid synthetic COMMIT phase")
    result = _base()
    with TemporaryDirectory(prefix="a292-writer-") as raw:
        path = Path(raw) / "staging.db"
        store = _open_ack_connection(path)
        try:
            cid, invoke = _prepare_writer(store, writer)
            before = _external_effect_count(path, writer, cid)
            store.db.fault_once = phase
            uncertain = False
            try:
                invoke()
            except StoreCommitOutcomeUncertainError:
                uncertain = True
            after = _external_effect_count(path, writer, cid)
            failed = (
                store._health_state == FAILED
                and store._health_reason == (
                    "COMMIT_OUTCOME_UNKNOWN_ZERO_AUTO_RETRY"
                )
            )
            marker = store._message_commit_marker.exists()
            denied_retry = False
            try:
                invoke()
            except StorageUnavailableError:
                denied_retry = True
            after_retry = _external_effect_count(path, writer, cid)
            result.update({
                "writer": writer,
                "synthetic_phase": phase,
                "baseline_effect_count": before,
                "first_effect_count": after,
                "uncertain_error_raised": uncertain,
                "health_failed_sticky": failed,
                "pending_marker_persisted": marker,
                "automatic_retry_denied": denied_retry,
                "effect_count_after_denied_retry": after_retry,
            })
        finally:
            store.close()
        try:
            reopened = SQLiteChatStore(path)
        except StorageUnavailableError:
            result["restart_refused_pending_marker"] = True
        else:
            reopened.close()
            result["restart_refused_pending_marker"] = False
    return result


def probe_real_raw_helper_bypasses():
    """Honest negative: Python helper methods are NOT independent boundaries."""
    result = _base()
    with TemporaryDirectory(prefix="a292-helper-") as raw:
        path = Path(raw) / "staging.db"
        store = SQLiteChatStore(path, strict_local_data_version=True)
        try:
            conv = store.create_conversation(SCOPE, "original")
            msg = store.append_message(
                SCOPE, Message(
                    conv.id, "user", "seed", id="a292-helper-seed"
                )
            )
            c = store.get_conversation(SCOPE, conv.id)
            c.title = "direct-helper-update"
            store._update(c)
            store.db.commit()
            checkpoint = ConversationCheckpoint(conv.id, msg.sequence)
            store._save_record(SCOPE, "checkpoint", checkpoint, msg.sequence)
            store.db.commit()
            direct_title = store.get_conversation(SCOPE, conv.id).title
            latest = store.get_latest_checkpoint(SCOPE, conv.id)
            health = store.storage_health(deep=True)
            result.update({
                "raw_update_helper_changed_title": (
                    direct_title == "direct-helper-update"
                ),
                "raw_save_record_helper_inserted_checkpoint": (
                    latest is not None and latest.id == checkpoint.id
                ),
                "pending_commit_marker_absent": not (
                    store._message_commit_marker.exists()
                ),
                "strict_local_health_still_green": (
                    health["state"] == HEALTHY
                ),
                "unrestricted_same_process_helper_access": True,
            })
        finally:
            store.close()
    return result


def probe_all_six_normal_writers():
    """Observe actual pre-COMMIT marker publication on all six writers."""
    result = _base()
    with TemporaryDirectory(prefix="a292-normal-six-") as raw:
        path = Path(raw) / "staging.db"
        store = SQLiteChatStore(path, strict_local_data_version=True)
        try:
            original = store._publish_message_commit_marker
            with mock.patch.object(
                store, "_publish_message_commit_marker", wraps=original
            ) as marker_spy:
                conv = store.create_conversation(SCOPE, "all six")
                msg = store.append_message(
                    SCOPE, Message(
                        conv.id, "user", "seed", id="a292-six-normal-msg"
                    )
                )
                attachment = _synthetic_attachment(conv.id)
                store.add_attachment_metadata(SCOPE, attachment)
                checkpoint = ConversationCheckpoint(conv.id, msg.sequence)
                store.save_checkpoint(SCOPE, checkpoint)
                summary = ContextSummary(
                    conv.id, msg.sequence, "normal summary",
                    source_message_ids=[msg.id],
                )
                store.save_context_summary(SCOPE, summary)
                store.archive_conversation(SCOPE, conv.id)
                publishes = marker_spy.call_count
            with closing(sqlite3.connect(str(path))) as external:
                recs = external.execute(
                    "SELECT kind, COUNT(*) FROM records GROUP BY kind"
                ).fetchall()
                rows = external.execute(
                    "SELECT COUNT(*) FROM messages WHERE cid=?",
                    (conv.id,),
                ).fetchone()[0]
                archive = external.execute(
                    "SELECT archived FROM conversations WHERE id=?",
                    (conv.id,),
                ).fetchone()[0]
            result.update({
                "six_distinct_writers_executed": True,
                "local_commit_markers_published": publishes,
                "message_count": rows,
                "record_kinds": {
                    str(name): int(count) for name, count in recs
                },
                "archived": bool(archive),
                "pending_marker_absent_after_acks": not (
                    store._message_commit_marker.exists()
                ),
                "health_healthy_after_ack": (
                    store.storage_health(deep=True)["state"] == HEALTHY
                ),
            })
        finally:
            store.close()
    return result


__all__ = [
    "SCHEMA", "SOURCE", "SCOPE", "WRITE_ENTRYPOINTS", "LAB_ONLY_ENTRYPOINTS",
    "DIRECT_FENCED",
    "TRANSACTION_FENCED", "DIRECT_DML", "HELPERS_WITH_RAW_DML",
    "inspect_store_writers", "probe_one_writer_ack_boundary",
    "probe_real_raw_helper_bypasses", "probe_all_six_normal_writers",
]
