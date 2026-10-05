from pathlib import Path
import unittest

from aion_chat.attachments import ingest_attachment
from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_chat_golden_path import execute_readonly_golden_path
from atlasquant_aion_chat_history_bridge import (
    SCHEMA,
    execute_and_persist_readonly,
    persist_verified_read_result,
    trusted_context_for_scope,
    validate_verified_read_result,
)
from atlasquant_aion_memory import default_checkpoint


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


class FailAssistantOnceStore:
    def __init__(self, inner):
        self.inner = inner
        self.fail = True

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def append_message(self, scope, message):
        if message.role == "assistant" and self.fail:
            self.fail = False
            raise RuntimeError("simulated assistant write failure")
        return self.inner.append_message(scope, message)


class ChatHistoryBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self._testMethodName)
        # unittest temp location is supplied explicitly per test via helper instead.
        self.scope = Scope("mikael", "tenant-a", "workspace-a")

    def _store(self, temp_dir):
        return SQLiteChatStore(temp_dir / "chat.sqlite3")

    def _golden(self, cid, *, scope=None, turn_index=1):
        scope = scope or self.scope
        context = trusted_context_for_scope(scope, ADMIN_CONTEXT)
        return execute_readonly_golden_path(
            "status geral",
            context=context,
            runtime_context={"checkpoint": default_checkpoint()},
            access=ADMIN_ACCESS,
            authenticated_admin=True,
            conversation_id=cid,
            turn_index=turn_index,
        )

    def test_trusted_context_identity_comes_from_scope(self):
        out = trusted_context_for_scope(self.scope, ADMIN_CONTEXT)
        self.assertEqual(out["tenant_id"], "tenant-a")
        self.assertEqual(out["workspace_id"], "workspace-a")
        self.assertEqual(out["actor_id"], "mikael")
        self.assertEqual(out["role"], "ADMIN")

    def test_trusted_context_rejects_identity_override(self):
        with self.assertRaisesRegex(ValueError, "crosses trusted scope"):
            trusted_context_for_scope(
                self.scope,
                {**ADMIN_CONTEXT, "tenant_id": "tenant-b"},
            )

    def test_verified_result_persists_and_reopens(self):
        import tempfile
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = self._store(root)
            conv = store.create_conversation(self.scope, "AION principal")
            result = self._golden(conv.id)
            persisted = persist_verified_read_result(store, self.scope, result)
            self.assertEqual(persisted["schema"], SCHEMA)
            self.assertEqual(persisted["state"], "PERSISTED")
            self.assertTrue(persisted["local_history_persisted"])
            self.assertFalse(persisted["persisted_externally"])
            self.assertFalse(persisted["checkpoint_written"])
            self.assertFalse(persisted["memory_promoted"])
            self.assertFalse(persisted["external_action_executed"])
            self.assertIsNone(store.get_latest_checkpoint(self.scope, conv.id))
            store.close()

            reopened = self._store(root)
            rows = reopened.list_messages(
                self.scope,
                conv.id,
                page_size=20,
            ).items
            self.assertEqual([row.role for row in rows], ["user", "assistant"])
            self.assertEqual(rows[0].metadata["turn_id"], result["turn_id"])
            self.assertEqual(
                rows[1].metadata["receipt_id"],
                result["receipt"]["receipt_id"],
            )
            self.assertEqual(rows[1].truth_state, "UNKNOWN")
            self.assertTrue(rows[1].provenance["local_only"])
            self.assertFalse(rows[1].provenance["grants_authority"])
            reopened.close()

    def test_full_execute_and_persist_path_is_idempotent(self):
        import tempfile
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(Path(raw))
            conv = store.create_conversation(self.scope)
            kwargs = dict(
                context=ADMIN_CONTEXT,
                runtime_context={"checkpoint": default_checkpoint()},
                access=ADMIN_ACCESS,
                authenticated_admin=True,
                conversation_id=conv.id,
                turn_index=7,
            )
            first = execute_and_persist_readonly(
                store,
                self.scope,
                "status geral",
                **kwargs,
            )
            second = execute_and_persist_readonly(
                store,
                self.scope,
                "status geral",
                **kwargs,
            )
            self.assertEqual(first["state"], "CONFIRMED_AND_PERSISTED")
            self.assertEqual(first["persistence"]["state"], "PERSISTED")
            self.assertEqual(second["state"], "CONFIRMED_AND_PERSISTED")
            self.assertEqual(second["persistence"]["state"], "IDEMPOTENT")
            rows = store.list_messages(self.scope, conv.id, page_size=20).items
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0].id, first["persistence"]["user_message_id"])
            self.assertEqual(rows[1].id, first["persistence"]["assistant_message_id"])
            store.close()

    def test_result_from_other_scope_is_rejected_before_write(self):
        import tempfile
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(Path(raw))
            conv = store.create_conversation(self.scope)
            result = self._golden(conv.id)
            other = Scope("mikael", "tenant-b", "workspace-a")
            validation = validate_verified_read_result(other, result)
            self.assertFalse(validation["valid"])
            self.assertIn(
                "RESULT_IDENTITY_BINDING_MISMATCH",
                validation["blockers"],
            )
            with self.assertRaises(ValueError):
                persist_verified_read_result(store, other, result)
            self.assertEqual(
                store.get_conversation(self.scope, conv.id).message_count,
                0,
            )
            store.close()

    def test_tampered_receipt_is_rejected_before_write(self):
        import tempfile
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(Path(raw))
            conv = store.create_conversation(self.scope)
            result = self._golden(conv.id)
            result["receipt"]["tool_ids"] = ["aion.tasks.summary"]
            validation = validate_verified_read_result(self.scope, result)
            self.assertFalse(validation["valid"])
            self.assertIn("RECEIPT_DIGEST_INVALID", validation["blockers"])
            with self.assertRaises(ValueError):
                persist_verified_read_result(store, self.scope, result)
            self.assertEqual(
                store.get_conversation(self.scope, conv.id).message_count,
                0,
            )
            store.close()

    def test_partial_assistant_failure_is_explicit_and_retryable(self):
        import tempfile
        with tempfile.TemporaryDirectory() as raw:
            inner = self._store(Path(raw))
            conv = inner.create_conversation(self.scope)
            result = self._golden(conv.id, turn_index=9)
            flaky = FailAssistantOnceStore(inner)

            first = persist_verified_read_result(flaky, self.scope, result)
            self.assertEqual(
                first["state"],
                "PARTIAL_PERSISTENCE_RETRY_REQUIRED",
            )
            self.assertTrue(first["user_persisted"])
            self.assertFalse(first["assistant_persisted"])
            self.assertEqual(
                inner.get_conversation(self.scope, conv.id).message_count,
                1,
            )

            second = persist_verified_read_result(flaky, self.scope, result)
            self.assertEqual(second["state"], "PERSISTED")
            self.assertTrue(second["user_persisted"])
            self.assertTrue(second["assistant_persisted"])
            self.assertEqual(
                inner.get_conversation(self.scope, conv.id).message_count,
                2,
            )

            third = persist_verified_read_result(flaky, self.scope, result)
            self.assertEqual(third["state"], "IDEMPOTENT")
            self.assertEqual(
                inner.get_conversation(self.scope, conv.id).message_count,
                2,
            )
            inner.close()

    def test_attachment_metadata_is_bound_to_turn_and_persisted(self):
        import tempfile
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = self._store(root)
            conv = store.create_conversation(self.scope)
            attachment = ingest_attachment(
                store,
                self.scope,
                conv.id,
                root / "attachments",
                "report.txt",
                b"safe report",
            )
            out = execute_and_persist_readonly(
                store,
                self.scope,
                "status geral",
                context=ADMIN_CONTEXT,
                runtime_context={"checkpoint": default_checkpoint()},
                access=ADMIN_ACCESS,
                authenticated_admin=True,
                attachment_ids=[attachment.id],
                conversation_id=conv.id,
                turn_index=11,
            )
            self.assertEqual(out["state"], "CONFIRMED_AND_PERSISTED")
            turn_attachments = out["golden_result"]["turn"]["attachments"]
            self.assertEqual(len(turn_attachments), 1)
            self.assertEqual(turn_attachments[0]["name"], "report.txt")
            self.assertEqual(turn_attachments[0]["sha256"], attachment.digest)
            rows = store.list_messages(self.scope, conv.id, page_size=20).items
            self.assertEqual(rows[0].attachments, [attachment.id])
            store.close()

    def test_unbound_attachment_cannot_be_added_after_execution(self):
        import tempfile
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = self._store(root)
            conv = store.create_conversation(self.scope)
            result = self._golden(conv.id, turn_index=12)
            attachment = ingest_attachment(
                store,
                self.scope,
                conv.id,
                root / "attachments",
                "late.txt",
                b"late attachment",
            )
            with self.assertRaisesRegex(ValueError, "attachment metadata"):
                persist_verified_read_result(
                    store,
                    self.scope,
                    result,
                    attachment_ids=[attachment.id],
                )
            self.assertEqual(
                store.get_conversation(self.scope, conv.id).message_count,
                0,
            )
            store.close()

    def test_duplicate_attachment_id_is_rejected_before_execution(self):
        import tempfile
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = self._store(root)
            conv = store.create_conversation(self.scope)
            attachment = ingest_attachment(
                store,
                self.scope,
                conv.id,
                root / "attachments",
                "dup.txt",
                b"dup",
            )
            with self.assertRaisesRegex(ValueError, "duplicate attachment"):
                execute_and_persist_readonly(
                    store,
                    self.scope,
                    "status geral",
                    context=ADMIN_CONTEXT,
                    runtime_context={"checkpoint": default_checkpoint()},
                    access=ADMIN_ACCESS,
                    authenticated_admin=True,
                    attachment_ids=[attachment.id, attachment.id],
                    conversation_id=conv.id,
                    turn_index=13,
                )
            self.assertEqual(
                store.get_conversation(self.scope, conv.id).message_count,
                0,
            )
            store.close()

    def test_blocked_golden_path_is_never_persisted(self):
        import tempfile
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(Path(raw))
            conv = store.create_conversation(self.scope)
            out = execute_and_persist_readonly(
                store,
                self.scope,
                "faça o deploy agora",
                context=ADMIN_CONTEXT,
                runtime_context={"checkpoint": default_checkpoint()},
                access=ADMIN_ACCESS,
                authenticated_admin=True,
                conversation_id=conv.id,
                turn_index=1,
            )
            self.assertEqual(out["state"], "NOT_PERSISTED")
            self.assertFalse(out["local_history_persisted"])
            self.assertEqual(
                store.get_conversation(self.scope, conv.id).message_count,
                0,
            )
            store.close()

    def test_multiline_user_message_persists_exact_formatting(self):
        import tempfile
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(Path(raw))
            conv = store.create_conversation(self.scope)
            message = "status geral\n  segunda linha\n\tbloco indentado"
            out = execute_and_persist_readonly(
                store,
                self.scope,
                message,
                context=ADMIN_CONTEXT,
                runtime_context={"checkpoint": default_checkpoint()},
                access=ADMIN_ACCESS,
                authenticated_admin=True,
                conversation_id=conv.id,
                turn_index=21,
            )
            self.assertEqual(out["state"], "CONFIRMED_AND_PERSISTED")
            self.assertEqual(
                out["golden_result"]["turn"]["message"],
                message,
            )
            self.assertEqual(
                out["golden_result"]["turn"]["canonical_message"],
                "status geral segunda linha bloco indentado",
            )
            rows = store.list_messages(
                self.scope,
                conv.id,
                page_size=20,
            ).items
            self.assertEqual(rows[0].content, message)
            store.close()

            reopened = self._store(Path(raw))
            rows = reopened.list_messages(
                self.scope,
                conv.id,
                page_size=20,
            ).items
            self.assertEqual(rows[0].content, message)
            reopened.close()

    def test_sensitive_text_is_redacted_by_existing_store(self):
        import tempfile
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(Path(raw))
            conv = store.create_conversation(self.scope)
            out = execute_and_persist_readonly(
                store,
                self.scope,
                "status geral senha=abc123",
                context=ADMIN_CONTEXT,
                runtime_context={"checkpoint": default_checkpoint()},
                access=ADMIN_ACCESS,
                authenticated_admin=True,
                conversation_id=conv.id,
                turn_index=3,
            )
            self.assertEqual(out["state"], "CONFIRMED_AND_PERSISTED")
            rows = store.list_messages(self.scope, conv.id, page_size=20).items
            self.assertNotIn("abc123", rows[0].content)
            self.assertIn("[REDACTED]", rows[0].content)
            store.close()


if __name__ == "__main__":
    unittest.main()
