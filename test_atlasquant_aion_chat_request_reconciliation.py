"""Security inversions of PR #1197: real SQLite, no duplicated browser turn."""
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from aion_chat.models import Scope
from aion_chat.staged_store import OperationScopedSQLiteChatStore
from aion_chat.store import SQLiteChatStore, StorageUnavailableError
from atlasquant_aion_chat_product_ui import (
    bind_product_conversation,
    staged_product_session,
    submit_product_turn,
)
from atlasquant_aion_memory import default_checkpoint


def access():
    return {
        "allowed": True, "mode": "AUTHENTICATED", "role": "ADMIN",
        "session": {
            "username": "test-owner", "role": "ADMIN",
            "permissions": ["app:read", "aion:admin", "aion:checkpoint"],
            "credential_fingerprint": "test-browser-session-credential",
        },
    }


class DurableRequestReplayRegression(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "chat.sqlite3"
        self.scope = Scope("test-owner", "tenant-a", "workspace-a")
        self.auth = access()
        self.context = {"checkpoint": default_checkpoint()}
        # Reject attempted socket connects even if a new code path sneaks in.
        self.addCleanup(patch.stopall)
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection"):
            p = patch(target, side_effect=AssertionError("network forbidden in audit"))
            p.start()

    def _session(self, store, cid=""):
        state = staged_product_session({}, self.auth, self.scope)
        if cid:
            bind_product_conversation(
                state, self.auth, self.scope, store, self.context, cid
            )
        return state

    def _send(self, store, state, rid):
        return submit_product_turn(
            state,
            {
                "conversation_id": state["conversation_id"],
                "request_id": rid,
                "message": "status geral",
                "attachments": [],
            },
            self.auth, self.scope, store, self.context,
        )

    def test_identical_request_after_session_reset_keeps_two_messages(self):
        first = OperationScopedSQLiteChatStore(self.path)
        state1 = self._session(first)
        self.assertEqual(
            self._send(first, state1, "same-browser-request")["state"],
            "CONFIRMED_AND_PERSISTED",
        )
        cid = state1["conversation_id"]
        self.assertEqual(first.get_conversation(self.scope, cid).message_count, 2)
        first.close()

        # Session state is lost. Read the SAME existing conversation with a
        # fresh connection-free handle and browser session. No new user intent.
        reopened = OperationScopedSQLiteChatStore(self.path)
        self.addCleanup(reopened.close)
        state2 = self._session(reopened, cid)
        self.assertEqual(state2["requests"], set())
        again = self._send(reopened, state2, "same-browser-request")
        self.assertEqual(again["state"], "LOCAL_PAIR_RECONCILED")
        self.assertEqual(reopened.get_conversation(self.scope, cid).message_count, 2)
        pairs = reopened.list_messages(self.scope, cid).items
        self.assertEqual([p.role for p in pairs], ["user", "assistant"])
        self.assertFalse(again["message_write_attempted"])
        self.assertFalse(again["retry_authorized"])
        self.assertFalse(again["execution_authorized"])

    def test_postcommit_close_error_reconciles_without_duplicate(self):
        class NativeWithInjectedCloseFailure(SQLiteChatStore):
            armed = True

            def append_message(self, scope, message):
                # We only simulate failure AFTER a real committed assistant write.
                result = super().append_message(scope, message)
                if message.role == "assistant" and type(self).armed:
                    self._synthetic_close_failure = True
                return result

            def close(self):
                super().close()
                if getattr(self, "_synthetic_close_failure", False) and type(self).armed:
                    type(self).armed = False
                    raise RuntimeError("synthetic postcommit connection-close failure")

        with patch("aion_chat.staged_store.SQLiteChatStore", NativeWithInjectedCloseFailure):
            first = OperationScopedSQLiteChatStore(self.path)
            state1 = self._session(first)
            # The close fails after COMMIT, so caller cannot receive a success.
            with self.assertRaises(StorageUnavailableError):
                self._send(first, state1, "postcommit-request")
            cid = state1["conversation_id"]
            self.assertNotIn("postcommit-request", state1["requests"])
            self.assertEqual(first.storage_health()["state"], "failed")
            first.close()

        independent = OperationScopedSQLiteChatStore(self.path)
        self.addCleanup(independent.close)
        # Both messages are in SQLite even though caller saw an error.
        self.assertEqual(independent.get_conversation(self.scope, cid).message_count, 2)
        state2 = self._session(independent, cid)
        again = self._send(independent, state2, "postcommit-request")
        self.assertEqual(again["state"], "LOCAL_PAIR_RECONCILED")
        self.assertEqual(independent.get_conversation(self.scope, cid).message_count, 2)


if __name__ == "__main__":
    unittest.main()

