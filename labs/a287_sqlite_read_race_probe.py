"""A287 LAB: deterministic strict SQLiteChatStore read-guard interleavings.

Native disposable SQLite with two real connections and controlled monkeypatch
scheduling. This is a negative characterization plus an isolated candidate
post-read check, NOT a modification of production store behavior. No external
providers, Worker, orders, network, trusted FD, off-host witness or P0 closure.
"""
from contextlib import closing, nullcontext
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from unittest import mock

from aion_chat.models import Message, Scope
from aion_chat.store import FAILED, HEALTHY, SQLiteChatStore, StorageUnavailableError

SCHEMA = "ATLASQUANT_AION_SQLITE_READ_CHECK_TOCTOU_LAB_V1"
SCOPE = Scope("owner-a287", "tenant-a287", "workspace-a287")
ENDPOINTS = frozenset((
    "get_conversation", "list_conversations", "get_message",
    "list_messages", "get_latest_summary", "retrieve_messages",
))


def _foreign_commit(path, cid, title):
    """Commit from a real *other* native SQLite handle, same DB path."""
    with closing(sqlite3.connect(str(path))) as external:
        row = external.execute(
            "SELECT data FROM conversations WHERE id=?", (cid,)
        ).fetchone()
        if row is None:
            raise LookupError("synthetic conversation disappeared")
        obj = json.loads(row[0])
        obj["title"] = title
        external.execute(
            "UPDATE conversations SET title=?, data=? WHERE id=?",
            (title, json.dumps(obj), cid),
        )
        external.commit()


def postcheck_read_candidate(store, read_fn):
    """LAB-only second local counter check; not an atomic security proof."""
    store._require_open()
    try:
        result = read_fn()
    except Exception:
        # If a competing commit happened during a read that itself failed,
        # prioritize the local fail-closed storage veto over a plain not-found.
        store._require_open()
        raise
    store._require_open()
    return result


def probe_reader_interleaving(
    *, endpoint="get_conversation", postcheck=False, integrated_guard=False
):
    """Inject a second-handle COMMIT after the existing early store check.

    For getters that call _scope directly, inject after _scope's check.
    For getters that call get_conversation as their early guard, inject after
    that get_conversation returns but before the endpoint's own SELECT.
    The deterministic monkeypatch is a test scheduler, not an attack API.
    """
    if type(endpoint) is not str or endpoint not in ENDPOINTS:
        raise ValueError("unsupported research endpoint")
    if type(postcheck) is not bool:
        raise TypeError("postcheck must be bool")
    if type(integrated_guard) is not bool:
        raise TypeError("integrated_guard must be bool")
    with TemporaryDirectory(prefix="a287-read-") as raw:
        path = Path(raw) / "staging.db"
        store = SQLiteChatStore(path, strict_local_data_version=True)
        try:
            c = store.create_conversation(SCOPE, "original")
            msg = store.append_message(
                SCOPE, Message(c.id, "user", "hello a287", id="a287-message")
            )
            inode_before = (path.stat().st_dev, path.stat().st_ino)
            original_version = store._read_local_data_version()
            injected = False

            def inject():
                nonlocal injected
                if not injected:
                    _foreign_commit(path, c.id, "foreign-committed")
                    injected = True

            actions = {
                "get_conversation": lambda: store.get_conversation(SCOPE, c.id),
                "list_conversations": lambda: store.list_conversations(SCOPE),
                "get_message": lambda: store.get_message(SCOPE, c.id, msg.id),
                "list_messages": lambda: store.list_messages(SCOPE, c.id),
                "get_latest_summary": lambda: store.get_latest_summary(SCOPE, c.id),
                "retrieve_messages": lambda: store.retrieve_messages(
                    SCOPE, c.id, "hello", before_sequence=2
                ),
            }
            if endpoint in {"get_conversation", "list_conversations"}:
                original = store._scope

                def interpose(scope):
                    result = original(scope)
                    inject()
                    return result

                target = "_scope"
            else:
                original = store.get_conversation

                def interpose(scope, cid):
                    result = original(scope, cid)
                    inject()
                    return result

                target = "get_conversation"

            status = "NOT_RUN"
            result = None
            # A288: explicitly keep the A287 *historical* pre-only
            # negative control. It disables just the new post-read method
            # inside this synthetic LAB harness; NEVER normal runtime.
            legacy_pre_only = (
                not integrated_guard and not postcheck
                and hasattr(store, "_post_read_data_version_guard")
            )
            guard_context = (
                mock.patch.object(store, "_post_read_data_version_guard",
                                  return_value=None)
                if legacy_pre_only else nullcontext()
            )
            with guard_context:
                with mock.patch.object(store, target, side_effect=interpose):
                    try:
                        result = (
                            postcheck_read_candidate(store, actions[endpoint])
                            if postcheck else actions[endpoint]()
                        )
                        status = "RETURNED"
                    except StorageUnavailableError:
                        status = "DENIED_AFTER_EXTERNAL_COMMIT"

            # A no-postcheck read finished while its *store status* was still
            # healthy; this is not proof the returned data is trustworthy.
            state_before_followup = store._health_state
            version_after = store._read_local_data_version()
            health = store.storage_health(deep=True)
            with closing(sqlite3.connect(str(path))) as auditor:
                quick_check = auditor.execute("PRAGMA quick_check").fetchone()[0]
            return {
                "schema": SCHEMA,
                "endpoint": endpoint,
                "postcheck_lab_candidate": postcheck,
                "integrated_store_postcheck": integrated_guard,
                "status": status,
                "injected_external_commit": injected,
                "same_path_inode": inode_before == (
                    path.stat().st_dev, path.stat().st_ino
                ),
                "quick_check_ok": quick_check == "ok",
                "counter_changed": original_version != version_after,
                "store_health_before_followup": state_before_followup,
                "store_health_after_followup": health["state"],
                "store_reason_after_followup": health["reason"],
                "returned_foreign_title": (
                    result.title == "foreign-committed"
                    if status == "RETURNED" and endpoint == "get_conversation"
                    else (
                        len(result.items) == 1
                        and result.items[0].title == "foreign-committed"
                        if status == "RETURNED" and endpoint == "list_conversations"
                        else False
                    )
                ),
                "native_fd_authenticated": False,
                "off_host_rollback_witness": False,
                "antirollback_proven": False,
                "p0_homologated": 0,
                "authorizes_send": False,
                "zero_auto_resend": True,
                "no_worker_orders_network": True,
            }
        finally:
            store.close()


def probe_last_moment_postcheck_gap():
    """External writer commits *after* the candidate's final local check.

    This last-moment scheduler illustrates why postcheck narrows the gap but
    cannot offer atomic external-history or delivery authorization.
    """
    with TemporaryDirectory(prefix="a287-last-") as raw:
        path = Path(raw) / "staging.db"
        store = SQLiteChatStore(path, strict_local_data_version=True)
        try:
            c = store.create_conversation(SCOPE, "original")
            original_guard = store._require_open
            checks = 0
            injected = False

            def delayed_guard():
                nonlocal checks, injected
                original_guard()
                checks += 1
                # Candidate precheck, internal _scope check, candidate postcheck.
                if checks == 3:
                    _foreign_commit(path, c.id, "after-final-check")
                    injected = True

            # Preserve the A287 pre-integration last-moment proof after
            # A288 adds a separate internal read check.
            guard_context = (
                mock.patch.object(store, "_post_read_data_version_guard",
                                  return_value=None)
                if hasattr(store, "_post_read_data_version_guard")
                else nullcontext()
            )
            with guard_context:
                with mock.patch.object(store, "_require_open", side_effect=delayed_guard):
                    result = postcheck_read_candidate(
                        store, lambda: store.get_conversation(SCOPE, c.id)
                    )
            healthy_before_followup = store._health_state == HEALTHY
            followup = store.storage_health(deep=True)
            return {
                "schema": SCHEMA,
                "checks": checks,
                "injected_after_final_check": injected,
                "read_returned": result.id == c.id,
                "returned_original_title": result.title == "original",
                "temporarily_healthy_after_return": healthy_before_followup,
                "later_health_denies": (
                    followup["state"] == FAILED
                    and followup["reason"] == "LOCAL_DATA_VERSION_CHANGED"
                ),
                "atomic_proof": False,
                "p0_homologated": 0,
                "authorizes_send": False,
            }
        finally:
            store.close()


__all__ = [
    "SCHEMA", "ENDPOINTS", "postcheck_read_candidate",
    "probe_reader_interleaving", "probe_last_moment_postcheck_gap",
]
