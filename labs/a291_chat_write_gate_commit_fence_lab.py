"""A291 LAB: cooperative write-authorizer composition with real chat COMMIT fence.

Uses the actual SQLiteChatStore and its A247/A250/A251 commit marker, with
real native SQLite and a synthetic Connection subclass that loses an ACK
before/after COMMIT. No providers, Worker, outbound effect, deployment,
native-FD identity attestation or P0 homologation.
"""
from contextlib import closing, contextmanager
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import threading
from unittest import mock

from aion_chat.models import Message, Scope
from aion_chat.store import (
    FAILED, HEALTHY, SQLiteChatStore, StorageUnavailableError,
    StoreCommitOutcomeUncertainError,
)
from labs.a290_sqlite_local_write_gate_lab import WRITE_ACTIONS

SCHEMA = "ATLASQUANT_AION_CHAT_WRITE_GATE_COMMIT_FENCE_LAB_V1"
SCOPE = Scope("owner-a291", "tenant-a291", "workspace-a291")
FAULTS = frozenset(("before", "after"))


class SyntheticAckLossConnection(sqlite3.Connection):
    """Real SQLite COMMIT plus synthetic application ACK loss."""

    fault_once = None

    def commit(self):
        if getattr(self, "fault_once", None) == "before":
            self.fault_once = None
            raise sqlite3.OperationalError("A291 synthetic COMMIT rejected before call")
        result = super().commit()
        if getattr(self, "fault_once", None) == "after":
            self.fault_once = None
            raise sqlite3.OperationalError("A291 synthetic ACK lost after COMMIT")
        return result


class LocalChatCommitWriteGate:
    """Cooperative facade, not a host-resistant access boundary.

    A new callback is installed after each authorized store method so cached
    statements cannot retain an expired grant, as characterized by A289/A290.
    The original SQLiteChatStore's pre-COMMIT marker remains responsible for
    uncertain outcomes. No independent off-host trust is introduced.
    """

    def __init__(self, path, *, ack_loss_connection=False):
        if type(ack_loss_connection) is not bool:
            raise TypeError("ack_loss_connection must be bool")
        self.path = Path(path)
        self._lock = threading.RLock()
        self._grant = False
        self._closed = False
        self._update_checks = 0
        if ack_loss_connection:
            original_connect = sqlite3.connect

            def synthetic_connect(*args, **kwargs):
                return original_connect(
                    *args, **kwargs, factory=SyntheticAckLossConnection
                )

            with mock.patch(
                "aion_chat.store.sqlite3.connect", side_effect=synthetic_connect
            ):
                self._store = SQLiteChatStore(
                    self.path, strict_local_data_version=True
                )
        else:
            self._store = SQLiteChatStore(
                self.path, strict_local_data_version=True
            )
        self._store.db.set_authorizer(self._authorize)

    def _authorize(self, action, arg1, arg2, db_name, trigger):
        if action == sqlite3.SQLITE_UPDATE:
            self._update_checks += 1
        if action in WRITE_ACTIONS and not self._grant:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    def _require_open(self):
        if self._closed:
            raise StorageUnavailableError("A291 LAB facade closed")

    @contextmanager
    def _authorized_store_method(self):
        self._require_open()
        with self._lock:
            if self._grant:
                raise StorageUnavailableError("A291 nested write grant denied")
            self._grant = True
            try:
                yield
            finally:
                self._grant = False
                # Re-install after EACH attempt including a lost ACK, ensuring
                # the prepared statement cache does not preserve a grant.
                if self._store.db is not None:
                    try:
                        self._store.db.set_authorizer(self._authorize)
                    except sqlite3.DatabaseError as exc:
                        self._store._health_state = FAILED
                        self._store._health_reason = (
                            "A291_LOCAL_AUTHORIZER_REARM_UNCERTAIN"
                        )
                        raise StorageUnavailableError(
                            "A291 local authorizer rearm uncertain"
                        ) from exc

    def create_conversation(self, title):
        with self._authorized_store_method():
            return self._store.create_conversation(SCOPE, title)

    def append_message(self, message):
        with self._authorized_store_method():
            return self._store.append_message(SCOPE, message)

    def get_conversation(self, cid):
        self._require_open()
        return self._store.get_conversation(SCOPE, cid)

    def list_messages(self, cid):
        self._require_open()
        return self._store.list_messages(SCOPE, cid)

    def storage_health(self):
        self._require_open()
        return self._store.storage_health(deep=True)

    def trigger_ack_loss_once(self, when):
        if type(when) is not str or when not in FAULTS:
            raise ValueError("unsupported synthetic ACK-loss phase")
        self._require_open()
        if not isinstance(self._store.db, SyntheticAckLossConnection):
            raise RuntimeError("synthetic ACK-loss connection not configured")
        self._store.db.fault_once = when

    def direct_raw_update_denied(self, cid):
        """Negative check: a caller attempts a raw same-handle mutation."""
        self._require_open()
        self._store.db.execute(
            "UPDATE conversations SET title=? WHERE id=?",
            ("raw-unauthorized", cid),
        )
        self._store.db.commit()

    @property
    def pending_marker_exists(self):
        return self._store._message_commit_marker.exists()

    def close(self):
        if not self._closed:
            self._store.close()
            self._closed = True


def _base():
    return {
        "schema": SCHEMA,
        "research_only": True,
        "native_sqlite": True,
        "real_staging_store": True,
        "zero_auto_resend": True,
        "no_provider_worker_deploy_orders": True,
        "no_external_effect_or_real_receipt": True,
        "can_authorize_send": False,
        "p0_homologated": 0,
        "independent_owner_proof": False,
        "native_fd_authenticated": False,
        "off_host_rollback_floor": False,
    }


def _external_message_count(path, cid):
    with closing(sqlite3.connect(str(path))) as other:
        return other.execute(
            "SELECT COUNT(*) FROM messages WHERE cid=?", (cid,)
        ).fetchone()[0]


def probe_normal_fenced_gate():
    result = _base()
    with TemporaryDirectory(prefix="a291-normal-") as raw:
        path = Path(raw) / "staging.db"
        gate = LocalChatCommitWriteGate(path)
        try:
            conv = gate.create_conversation("normal")
            msg = gate.append_message(
                Message(conv.id, "user", "normal", id="a291-normal-msg")
            )
            denied = False
            try:
                gate.direct_raw_update_denied(conv.id)
            except sqlite3.DatabaseError:
                denied = True
                gate._store.db.rollback()
            result.update({
                "message_sequence": msg.sequence,
                "external_read_count": _external_message_count(path, conv.id),
                "store_healthy": gate.storage_health()["state"] == HEALTHY,
                "direct_raw_write_denied": denied,
                "pending_marker_after_ack": gate.pending_marker_exists,
                "update_authorizer_checks": gate._update_checks,
                "cached_sql_authorizer_rearmed": True,
            })
        finally:
            gate.close()
    return result


def probe_commit_ack_loss(*, phase="after"):
    if type(phase) is not str or phase not in FAULTS:
        raise ValueError("invalid synthetic COMMIT phase")
    result = _base()
    with TemporaryDirectory(prefix="a291-uncertain-") as raw:
        path = Path(raw) / "staging.db"
        gate = LocalChatCommitWriteGate(path, ack_loss_connection=True)
        try:
            conv = gate.create_conversation("uncertain")
            msg = Message(
                conv.id, "user", "potentially-committed",
                id="a291-uncertain-msg"
            )
            gate.trigger_ack_loss_once(phase)
            uncertain = False
            try:
                gate.append_message(msg)
            except StoreCommitOutcomeUncertainError:
                uncertain = True
            persisted = _external_message_count(path, conv.id)
            marker = gate.pending_marker_exists
            reason_at_commit_failure = gate._store._health_reason
            health = gate.storage_health()
            retry_denied = False
            try:
                gate.append_message(msg)
            except StorageUnavailableError:
                retry_denied = True
            after_retry = _external_message_count(path, conv.id)
            result.update({
                "synthetic_phase": phase,
                "uncertain_error_raised": uncertain,
                "committed_count_visible_externally": persisted,
                "pending_commit_marker_persists": marker,
                "health_failed_sticky": (
                    health["state"] == FAILED
                    and reason_at_commit_failure
                    == "COMMIT_OUTCOME_UNKNOWN_ZERO_AUTO_RETRY"
                    and health["reason"]
                    == "MESSAGE_COMMIT_PENDING_ZERO_AUTO_RETRY"
                ),
                "initial_uncertain_reason": reason_at_commit_failure,
                "health_after_marker_reason": health["reason"],
                "retry_denied": retry_denied,
                "message_count_after_denied_retry": after_retry,
                "rearm_after_unknown_commit": not gate._grant,
            })
        finally:
            gate.close()
        reopen_denied = False
        try:
            reopened = SQLiteChatStore(path)
        except StorageUnavailableError:
            reopen_denied = True
        else:
            reopened.close()
        result["restart_denied_by_local_marker"] = reopen_denied
    return result


def probe_raw_same_handle_authorizer_uninstall():
    """Demonstrates that this facade is NOT a host security boundary."""
    result = _base()
    with TemporaryDirectory(prefix="a291-uninstall-") as raw:
        path = Path(raw) / "staging.db"
        gate = LocalChatCommitWriteGate(path)
        try:
            conv = gate.create_conversation("before")
            row = gate._store.db.execute(
                "SELECT data FROM conversations WHERE id=?", (conv.id,)
            ).fetchone()
            edited = json.loads(row[0])
            edited["title"] = "same-handle-bypass"
            gate._store.db.set_authorizer(None)
            gate._store.db.execute(
                "UPDATE conversations SET title=?, data=? WHERE id=?",
                (edited["title"], json.dumps(edited), conv.id),
            )
            gate._store.db.commit()
            result.update({
                "authorizer_uninstalled_by_same_process": True,
                "write_bypassed_local_gate": (
                    gate.get_conversation(conv.id).title
                    == "same-handle-bypass"
                ),
                "same_handle_data_version_cannot_attest": (
                    gate.storage_health()["state"] == HEALTHY
                ),
                "no_independent_capability": True,
            })
        finally:
            gate.close()
    return result


__all__ = [
    "SCHEMA", "FAULTS", "SyntheticAckLossConnection",
    "LocalChatCommitWriteGate", "probe_normal_fenced_gate",
    "probe_commit_ack_loss", "probe_raw_same_handle_authorizer_uninstall",
]
