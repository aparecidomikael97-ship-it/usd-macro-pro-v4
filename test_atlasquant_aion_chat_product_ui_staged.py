from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_chat_product_ui import (
    bind_product_conversation,
    staged_product_session,
    submit_product_turn,
    validate_product_ui_injection,
    view_product_data,
)
from atlasquant_aion_memory import default_checkpoint


ROOT = Path(__file__).resolve().parent


def authenticated_access(username="mikael"):
    return {
        "allowed": True,
        "mode": "AUTHENTICATED",
        "reason": "OK",
        "role": "ADMIN",
        "session": {
            "username": username,
            "role": "ADMIN",
            "permissions": [
                "app:read",
                "aion:admin",
                "aion:checkpoint",
            ],
            "credential_fingerprint": "credential-fingerprint-staged-ui",
            "authenticated_at": 1.0,
            "last_seen": 1.0,
        },
    }


class StagedProductUiContinuityTests(unittest.TestCase):
    def setUp(self):
        self.scope = Scope("mikael", "tenant-a", "workspace-a")
        self.access = authenticated_access()
        self.runtime_context = {"checkpoint": default_checkpoint()}

    def _store(self, root):
        return SQLiteChatStore(Path(root) / "aion-chat-staged.sqlite3")

    @staticmethod
    def _event(state, request_id, message="status geral", attachments=None):
        return {
            "conversation_id": state.get("conversation_id") or "",
            "request_id": request_id,
            "message": message,
            "attachments": list(attachments or []),
        }

    def test_persist_close_reopen_and_continue_from_same_point(self):
        with tempfile.TemporaryDirectory() as raw:
            session = {}
            store = self._store(raw)
            state = staged_product_session(session, self.access, self.scope)

            first = submit_product_turn(
                state,
                self._event(state, "request-1"),
                self.access,
                self.scope,
                store,
                self.runtime_context,
            )
            self.assertEqual(first["state"], "CONFIRMED_AND_PERSISTED")
            self.assertTrue(first["continued_from_durable_history"])
            self.assertEqual(first["prior_message_count"], 0)
            self.assertEqual(first["current_message_count"], 2)
            cid = state["conversation_id"]

            before_close = view_product_data(
                state,
                self.access,
                self.scope,
                store,
                self.runtime_context,
            )
            self.assertTrue(before_close["product_mode"])
            self.assertTrue(before_close["durable_history"])
            self.assertEqual(before_close["total"], 2)
            self.assertEqual(
                [row["role"] for row in before_close["entries"]],
                ["user", "assistant"],
            )
            self.assertEqual(before_close["entries"][0]["content"], "status geral")
            store.close()

            # Simulate a new UI session + a newly opened store handle. The host
            # explicitly supplies the known conversation id; nothing is inferred.
            reopened_store = self._store(raw)
            new_session = {}
            reopened_state = staged_product_session(
                new_session,
                self.access,
                self.scope,
            )
            reopened = bind_product_conversation(
                reopened_state,
                self.access,
                self.scope,
                reopened_store,
                self.runtime_context,
                cid,
            )
            self.assertEqual(reopened["state"], "REOPENED")
            self.assertEqual(
                reopened["resume"]["resume"]["message_count"],
                2,
            )

            restored = view_product_data(
                reopened_state,
                self.access,
                self.scope,
                reopened_store,
                self.runtime_context,
            )
            self.assertEqual(restored["total"], 2)
            self.assertEqual(
                restored["entries"][0]["content"],
                "status geral",
            )

            second = submit_product_turn(
                reopened_state,
                self._event(reopened_state, "request-2"),
                self.access,
                self.scope,
                reopened_store,
                self.runtime_context,
            )
            self.assertEqual(second["state"], "CONFIRMED_AND_PERSISTED")
            self.assertEqual(second["prior_message_count"], 2)
            self.assertEqual(second["current_message_count"], 4)
            self.assertTrue(second["resume_context_digest"])

            final = view_product_data(
                reopened_state,
                self.access,
                self.scope,
                reopened_store,
                self.runtime_context,
            )
            self.assertEqual(final["total"], 4)
            self.assertEqual(len(final["entries"]), 4)
            reopened_store.close()

    def test_sensitive_turn_is_not_persisted(self):
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(raw)
            state = staged_product_session({}, self.access, self.scope)
            out = submit_product_turn(
                state,
                self._event(
                    state,
                    "sensitive-1",
                    message="faça deploy agora",
                ),
                self.access,
                self.scope,
                store,
                self.runtime_context,
            )
            self.assertEqual(out["state"], "NOT_PERSISTED")
            self.assertFalse(out["external_action_executed"])
            self.assertEqual(
                store.get_conversation(
                    self.scope,
                    state["conversation_id"],
                ).message_count,
                0,
            )
            self.assertIn("não persistido", state["notice"].lower())
            store.close()

    def test_attachment_metadata_cannot_activate_durable_ingest(self):
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(raw)
            state = staged_product_session({}, self.access, self.scope)
            with self.assertRaisesRegex(ValueError, "Anexos duráveis"):
                submit_product_turn(
                    state,
                    self._event(
                        state,
                        "attachment-1",
                        attachments=[{
                            "filename": "ref.png",
                            "mime_type": "image/png",
                            "size_bytes": 10,
                        }],
                    ),
                    self.access,
                    self.scope,
                    store,
                    self.runtime_context,
                )
            self.assertEqual(
                store.list_conversations(self.scope).items,
                [],
            )
            store.close()

    def test_same_browser_request_id_is_idempotent_in_staged_session(self):
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(raw)
            state = staged_product_session({}, self.access, self.scope)
            event = self._event(state, "same-request")
            first = submit_product_turn(
                state,
                event,
                self.access,
                self.scope,
                store,
                self.runtime_context,
            )
            self.assertEqual(first["state"], "CONFIRMED_AND_PERSISTED")
            event["conversation_id"] = state["conversation_id"]
            second = submit_product_turn(
                state,
                event,
                self.access,
                self.scope,
                store,
                self.runtime_context,
            )
            self.assertEqual(second["state"], "IDEMPOTENT_REQUEST")
            self.assertEqual(
                store.get_conversation(
                    self.scope,
                    state["conversation_id"],
                ).message_count,
                2,
            )
            store.close()

    def test_cross_scope_reopen_fails_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(raw)
            state = staged_product_session({}, self.access, self.scope)
            submit_product_turn(
                state,
                self._event(state, "scope-1"),
                self.access,
                self.scope,
                store,
                self.runtime_context,
            )
            cid = state["conversation_id"]
            other = Scope("mikael", "tenant-b", "workspace-a")
            other_state = staged_product_session({}, self.access, other)
            with self.assertRaises(LookupError):
                bind_product_conversation(
                    other_state,
                    self.access,
                    other,
                    store,
                    self.runtime_context,
                    cid,
                )
            self.assertEqual(other_state["conversation_id"], "")
            store.close()


class StagedProductUiBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.scope = Scope("mikael", "tenant-a", "workspace-a")
        self.access = authenticated_access()
        self.runtime_context = {"checkpoint": default_checkpoint()}

    def test_injection_is_explicit_and_does_not_activate_production_store(self):
        with tempfile.TemporaryDirectory() as raw:
            store = SQLiteChatStore(Path(raw) / "chat.sqlite3")
            out = validate_product_ui_injection(
                self.access,
                self.scope,
                store,
                self.runtime_context,
            )
            self.assertEqual(out["state"], "BOUND_STAGED")
            self.assertTrue(out["scope_injected"])
            self.assertTrue(out["store_injected"])
            self.assertTrue(out["runtime_context_injected"])
            self.assertFalse(out["store_created_here"])
            self.assertFalse(out["scope_inferred"])
            self.assertFalse(out["runtime_context_inferred"])
            self.assertFalse(out["production_store_activated"])
            self.assertFalse(out["grants_authority"])
            store.close()

    def test_missing_runtime_context_fails_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            store = SQLiteChatStore(Path(raw) / "chat.sqlite3")
            with self.assertRaises(TypeError):
                validate_product_ui_injection(
                    self.access,
                    self.scope,
                    store,
                    None,
                )
            store.close()

    def test_staged_safe_turn_has_no_network_provider_or_subprocess(self):
        with tempfile.TemporaryDirectory() as raw:
            store = SQLiteChatStore(Path(raw) / "chat.sqlite3")
            state = staged_product_session({}, self.access, self.scope)
            attempts = []

            def forbidden(*args, **kwargs):
                attempts.append((args, kwargs))
                raise AssertionError("external side effect attempted")

            with (
                patch("requests.sessions.Session.request", side_effect=forbidden),
                patch.object(socket, "socket", side_effect=forbidden),
                patch.object(subprocess, "Popen", side_effect=forbidden),
                patch.object(os, "system", side_effect=forbidden),
            ):
                out = submit_product_turn(
                    state,
                    {
                        "conversation_id": "",
                        "request_id": "no-network-1",
                        "message": "status geral",
                        "attachments": [],
                    },
                    self.access,
                    self.scope,
                    store,
                    self.runtime_context,
                )
            self.assertEqual(out["state"], "CONFIRMED_AND_PERSISTED")
            self.assertEqual(attempts, [])
            self.assertFalse(out["provider_called"])
            self.assertFalse(out["network_called"])
            self.assertFalse(out["external_action_executed"])
            store.close()

    def test_adapter_source_has_no_hidden_store_scope_runtime_or_provider(self):
        source = (
            ROOT / "atlasquant_aion_chat_product_ui.py"
        ).read_text(encoding="utf-8")
        for banned in (
            "SQLiteChatStore(",
            "default_checkpoint(",
            "Scope(",
            "import requests",
            "import subprocess",
            "import socket",
            "urllib.request",
            "os.system",
        ):
            self.assertNotIn(banned, source)

    def test_workspace_and_reference_ui_require_complete_injection(self):
        workspace = (
            ROOT / "atlasquant_aion_chat_workspace_ui.py"
        ).read_text(encoding="utf-8")
        reference = (
            ROOT / "atlasquant_reference_ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "staged product mode requires Scope + store + runtime_context",
            workspace,
        )
        self.assertIn(
            "aion_chat_binding requires scope + store + runtime_context",
            reference,
        )
        self.assertIn("product_conversation_id", workspace)
        self.assertIn('"conversation_id", ""', reference)


if __name__ == "__main__":
    unittest.main()
