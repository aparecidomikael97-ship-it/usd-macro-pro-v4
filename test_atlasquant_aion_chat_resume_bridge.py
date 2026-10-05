from pathlib import Path
import tempfile
import unittest

from aion_chat.context import compact_conversation
from aion_chat.models import Message, Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_chat_history_bridge import execute_and_persist_readonly
from atlasquant_aion_chat_resume_bridge import (
    SCHEMA,
    VERIFY_SCHEMA,
    prepare_resume_context,
    verify_resume_context,
)
from atlasquant_aion_memory import default_checkpoint


ROOT = Path(__file__).resolve().parent
ADMIN_ACCESS = {
    "role": "ADMIN",
    "session": {"username": "mikael", "role": "ADMIN"},
}
ADMIN_CONTEXT = {
    "role": "ADMIN",
    "persona": "admin",
    "experience_mode": "ADVANCED",
    "domain_hint": "admin",
}


class ResumeContextTests(unittest.TestCase):
    def setUp(self):
        self.scope = Scope("mikael", "tenant-a", "workspace-a")

    def _store(self, root):
        return SQLiteChatStore(Path(root) / "chat.sqlite3")

    def _persist_verified_turn(self, store, cid, turn_index=1):
        return execute_and_persist_readonly(
            store,
            self.scope,
            "status geral",
            context=ADMIN_CONTEXT,
            runtime_context={"checkpoint": default_checkpoint()},
            access=ADMIN_ACCESS,
            authenticated_admin=True,
            conversation_id=cid,
            turn_index=turn_index,
        )

    def test_verified_history_can_be_reopened_as_resume_context(self):
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(raw)
            conv = store.create_conversation(self.scope, "AION principal")
            persisted = self._persist_verified_turn(store, conv.id)
            self.assertEqual(persisted["state"], "CONFIRMED_AND_PERSISTED")

            out = prepare_resume_context(store, self.scope, conv.id)
            self.assertEqual(out["schema"], SCHEMA)
            self.assertEqual(out["state"], "READY")
            self.assertEqual(out["message_count"], 2)
            self.assertEqual(len(out["context"]["recent"]), 2)
            self.assertEqual(
                [row["role"] for row in out["context"]["recent"]],
                ["user", "assistant"],
            )
            self.assertTrue(out["identity_binding_complete"])
            self.assertTrue(out["context_digest"])
            self.assertIsNone(out["checkpoint_id"])
            self.assertIsNone(out["summary_id"])
            self.assertFalse(out["automatic_compaction"])
            self.assertFalse(out["automatic_checkpoint_write"])
            self.assertFalse(out["core_checkpoint_write"])
            self.assertFalse(out["automatic_memory_promotion"])
            self.assertFalse(out["provider_called"])
            self.assertFalse(out["network_called"])
            self.assertFalse(out["tool_executed"])
            self.assertFalse(out["external_action_executed"])
            store.close()

            reopened = self._store(raw)
            again = prepare_resume_context(reopened, self.scope, conv.id)
            self.assertEqual(out["context_digest"], again["context_digest"])
            self.assertEqual(out["identity_binding_digest"], again["identity_binding_digest"])
            reopened.close()

    def test_resume_context_preserves_multiline_history(self):
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(raw)
            conv = store.create_conversation(self.scope)
            message = "status geral\n  segunda linha\n\tbloco indentado"
            persisted = execute_and_persist_readonly(
                store,
                self.scope,
                message,
                context=ADMIN_CONTEXT,
                runtime_context={"checkpoint": default_checkpoint()},
                access=ADMIN_ACCESS,
                authenticated_admin=True,
                conversation_id=conv.id,
                turn_index=22,
            )
            self.assertEqual(
                persisted["state"],
                "CONFIRMED_AND_PERSISTED",
            )
            out = prepare_resume_context(store, self.scope, conv.id)
            self.assertEqual(out["state"], "READY")
            self.assertEqual(
                out["context"]["recent"][0]["content"],
                message,
            )
            store.close()

    def test_prepare_is_read_only_and_does_not_create_checkpoint(self):
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(raw)
            conv = store.create_conversation(self.scope)
            store.append_message(self.scope, Message(conv.id, "user", "olá"))
            before = store.get_conversation(self.scope, conv.id)
            self.assertIsNone(store.get_latest_checkpoint(self.scope, conv.id))
            self.assertIsNone(store.get_latest_summary(self.scope, conv.id))

            first = prepare_resume_context(store, self.scope, conv.id)
            second = prepare_resume_context(store, self.scope, conv.id)
            after = store.get_conversation(self.scope, conv.id)

            self.assertEqual(first["context_digest"], second["context_digest"])
            self.assertEqual(before.message_count, after.message_count)
            self.assertEqual(before.latest_checkpoint, after.latest_checkpoint)
            self.assertIsNone(store.get_latest_checkpoint(self.scope, conv.id))
            self.assertIsNone(store.get_latest_summary(self.scope, conv.id))
            store.close()

    def test_new_message_makes_prior_resume_envelope_stale(self):
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(raw)
            conv = store.create_conversation(self.scope)
            store.append_message(self.scope, Message(conv.id, "user", "primeira"))
            prepared = prepare_resume_context(store, self.scope, conv.id)
            current = verify_resume_context(store, self.scope, prepared)
            self.assertEqual(current["schema"], VERIFY_SCHEMA)
            self.assertEqual(current["state"], "CURRENT")
            self.assertTrue(current["current"])

            store.append_message(self.scope, Message(conv.id, "user", "segunda"))
            stale = verify_resume_context(store, self.scope, prepared)
            self.assertFalse(stale["current"])
            self.assertEqual(stale["state"], "STALE_OR_INVALID")
            self.assertIn("MESSAGE_COUNT_STALE", stale["blockers"])
            self.assertIn("CONTEXT_STALE_OR_TAMPERED", stale["blockers"])
            store.close()

    def test_context_tamper_is_detected(self):
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(raw)
            conv = store.create_conversation(self.scope)
            store.append_message(self.scope, Message(conv.id, "user", "original"))
            prepared = prepare_resume_context(store, self.scope, conv.id)
            prepared["context"]["recent"][0]["content"] = "forjado"
            checked = verify_resume_context(store, self.scope, prepared)
            self.assertFalse(checked["current"])
            self.assertIn("CONTEXT_DIGEST_MISMATCH", checked["blockers"])
            self.assertIn("CONTEXT_STALE_OR_TAMPERED", checked["blockers"])
            store.close()

    def test_query_is_fingerprinted_not_stored_as_request_field(self):
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(raw)
            conv = store.create_conversation(self.scope)
            for text in ("macro antigo", "mensagem recente"):
                store.append_message(self.scope, Message(conv.id, "user", text))
            out = prepare_resume_context(
                store,
                self.scope,
                conv.id,
                query="macro",
            )
            self.assertTrue(out["query_fingerprint"])
            self.assertFalse(out["query_stored"])
            self.assertNotIn("query", out)
            valid = verify_resume_context(
                store,
                self.scope,
                out,
                query="macro",
            )
            self.assertTrue(valid["current"])
            wrong = verify_resume_context(
                store,
                self.scope,
                out,
                query="outra busca",
            )
            self.assertFalse(wrong["current"])
            self.assertIn("QUERY_FINGERPRINT_MISMATCH", wrong["blockers"])
            store.close()

    def test_cross_scope_resume_is_unavailable(self):
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(raw)
            conv = store.create_conversation(self.scope)
            other = Scope("mikael", "tenant-b", "workspace-a")
            with self.assertRaises(LookupError):
                prepare_resume_context(store, other, conv.id)
            store.close()

    def test_explicit_existing_chat_checkpoint_is_reported_but_not_modified(self):
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(raw)
            conv = store.create_conversation(self.scope)
            store.append_message(
                self.scope,
                Message(
                    conv.id,
                    "user",
                    "decisão",
                    metadata={
                        "memory_events": [{
                            "kind": "pending",
                            "key": "review",
                            "value": "revisar",
                        }]
                    },
                ),
            )
            checkpoint, summary = compact_conversation(
                store,
                self.scope,
                conv.id,
            )
            out = prepare_resume_context(store, self.scope, conv.id)
            self.assertEqual(out["checkpoint_id"], checkpoint.id)
            self.assertEqual(out["summary_id"], summary.id)
            self.assertFalse(out["automatic_compaction"])
            self.assertFalse(out["automatic_checkpoint_write"])
            self.assertEqual(
                store.get_latest_checkpoint(self.scope, conv.id).id,
                checkpoint.id,
            )
            self.assertEqual(
                store.get_latest_summary(self.scope, conv.id).id,
                summary.id,
            )
            store.close()

    def test_small_context_budget_surfaces_rehydration_instead_of_deleting_history(self):
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(raw)
            conv = store.create_conversation(self.scope)
            for index in range(20):
                store.append_message(
                    self.scope,
                    Message(
                        conv.id,
                        "user",
                        f"mensagem-{index} " + ("x" * 1000),
                    ),
                )
            out = prepare_resume_context(
                store,
                self.scope,
                conv.id,
                budget_bytes=2048,
                recent_count=20,
            )
            self.assertEqual(out["state"], "REHYDRATION_REQUIRED")
            self.assertTrue(out["context"]["requires_rehydration"])
            self.assertEqual(
                store.get_conversation(self.scope, conv.id).message_count,
                20,
            )
            store.close()

    def test_bounds_fail_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(raw)
            conv = store.create_conversation(self.scope)
            with self.assertRaises(ValueError):
                prepare_resume_context(
                    store,
                    self.scope,
                    conv.id,
                    budget_bytes=511,
                )
            with self.assertRaises(ValueError):
                prepare_resume_context(
                    store,
                    self.scope,
                    conv.id,
                    recent_count=201,
                )
            with self.assertRaises(ValueError):
                prepare_resume_context(
                    store,
                    self.scope,
                    conv.id,
                    retrieval_count=0,
                )
            store.close()


class SourceBoundaryTests(unittest.TestCase):
    def test_resume_bridge_has_no_write_compact_network_provider_or_executor_path(self):
        source = (
            ROOT / "atlasquant_aion_chat_resume_bridge.py"
        ).read_text(encoding="utf-8")
        for banned in (
            "compact_conversation",
            "append_message",
            "save_checkpoint",
            "save_context_summary",
            "execute_readonly_golden_path",
            "execute_and_persist_readonly",
            "import requests",
            "import subprocess",
            "from subprocess",
            "urllib.request",
            "socket.",
            "os.system",
            "Popen(",
            "open(",
            ".write(",
        ):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
