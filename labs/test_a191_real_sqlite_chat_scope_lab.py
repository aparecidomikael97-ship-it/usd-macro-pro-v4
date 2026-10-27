"""A191 / G143 REAL SQLiteChatStore scoped persistence adversarial regression LAB.

Exercise existing AION local-chat SQLite storage, rather than invented paper
claims. No network, no provider, no customer data, no approval, no Worker.

EXPECTED RED FINDING is intentionally reproduced as a passing regression:
Scope dataclass is NOT a server-authenticated identity; a caller able to forge
the exact tuple can read a conversation. This is a missing trust boundary,
NOT authorization to open a production system. No actual cross-user identities
or real providers are used.
"""
from pathlib import Path
import tempfile
import unittest

from aion_chat.attachments import ingest_attachment
from aion_chat.models import (
    ConversationCheckpoint,
    ContextSummary,
    Message,
    Scope,
)
from aion_chat.service import ChatService
from aion_chat.store import SQLiteChatStore


class A191ChatSQLiteScopeLab(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "aion-chat.sqlite3"
        self.store = SQLiteChatStore(self.db_path)
        self.addCleanup(self._close_if_open)

        self.a = Scope("owner-a", "tenant-a", "trader")
        self.other_tenant = Scope("owner-a", "tenant-b", "trader")
        self.other_workspace = Scope("owner-a", "tenant-a", "investimentos")
        self.other_owner = Scope("owner-b", "tenant-a", "trader")
        self.scopes = [self.other_tenant, self.other_workspace, self.other_owner]

        self.conv = self.store.create_conversation(
            self.a, "SOLE_OWNER_SECRET_MARKER_SCOPE_A",
        )
        self.msg = self.store.append_message(
            self.a,
            Message(self.conv.id, "user", "SO_MARKET_PRIVATE_MARKER_SCOPE_A"),
        )

    def _close_if_open(self):
        self.store.close()

    def _assert_not_visible(self, scope, conversation_id=None):
        cid = conversation_id or self.conv.id
        with self.assertRaises(LookupError):
            self.store.get_conversation(scope, cid)

    def test_local_scope_owner_can_reopen_own_conversation(self):
        got = self.store.get_conversation(self.a, self.conv.id)
        self.assertEqual(got.id, self.conv.id)
        self.assertEqual(got.message_count, 1)

    def test_foreign_tenant_get_is_denied(self):
        self._assert_not_visible(self.other_tenant)

    def test_foreign_workspace_get_is_denied(self):
        self._assert_not_visible(self.other_workspace)

    def test_foreign_owner_get_is_denied(self):
        self._assert_not_visible(self.other_owner)

    def test_list_conversations_only_same_scope(self):
        for scope in self.scopes:
            with self.subTest(scope=scope):
                self.assertEqual(
                    self.store.list_conversations(scope).items, [],
                )

    def test_search_conversations_does_not_reveal_foreign_title_or_content(self):
        for scope in self.scopes:
            with self.subTest(scope=scope):
                for term in ("SOLE_OWNER_SECRET", "SO_MARKET_PRIVATE"):
                    self.assertEqual(
                        self.store.search_conversations(scope, term).items, [],
                    )

    def test_archiving_foreign_conversation_is_denied_and_does_not_mutate(self):
        for scope in self.scopes:
            with self.subTest(scope=scope):
                with self.assertRaises(LookupError):
                    self.store.archive_conversation(scope, self.conv.id)
                self.assertFalse(
                    self.store.get_conversation(self.a, self.conv.id).archived,
                )

    def test_foreign_append_is_denied_and_does_not_mutate(self):
        for scope in self.scopes:
            with self.subTest(scope=scope):
                with self.assertRaises(LookupError):
                    self.store.append_message(
                        scope,
                        Message(self.conv.id, "user", "injected by foreign scope"),
                    )
                self.assertEqual(
                    self.store.get_conversation(self.a, self.conv.id).message_count,
                    1,
                )

    def test_foreign_history_and_exact_message_denied(self):
        for scope in self.scopes:
            with self.subTest(scope=scope):
                with self.assertRaises(LookupError):
                    self.store.list_messages(scope, self.conv.id)
                with self.assertRaises(LookupError):
                    self.store.get_message(scope, self.conv.id, self.msg.id)

    def test_foreign_attachment_metadata_and_file_retrieval_denied(self):
        att = ingest_attachment(
            self.store, self.a, self.conv.id, self.root / "attachments",
            "private.txt", b"LOCAL_SYNTHETIC_ONLY",
        )
        for scope in self.scopes:
            with self.subTest(scope=scope):
                with self.assertRaises(LookupError):
                    self.store.get_attachment(scope, self.conv.id, att.id)
                with self.assertRaises(LookupError):
                    ingest_attachment(
                        self.store, scope, self.conv.id,
                        self.root / "attachments",
                        "foreign.txt", b"NOT_SAVED",
                    )
        self.assertEqual(
            self.store.get_attachment(self.a, self.conv.id, att.id).id,
            att.id,
        )

    def test_foreign_checkpoint_reads_and_writes_denied(self):
        cp = ConversationCheckpoint(self.conv.id, 1, confirmed_facts={
            "private": "SCOPE_A_ONLY",
        })
        self.store.save_checkpoint(self.a, cp)
        for scope in self.scopes:
            with self.subTest(scope=scope):
                with self.assertRaises(LookupError):
                    self.store.get_latest_checkpoint(scope, self.conv.id)
                with self.assertRaises(LookupError):
                    self.store.save_checkpoint(
                        scope,
                        ConversationCheckpoint(self.conv.id, 1),
                    )

    def test_foreign_context_summary_reads_and_writes_denied(self):
        summary = ContextSummary(
            self.conv.id, 1, "PRIVATE_SUMMARY_A", [self.msg.id],
        )
        self.store.save_context_summary(self.a, summary)
        for scope in self.scopes:
            with self.subTest(scope=scope):
                with self.assertRaises(LookupError):
                    self.store.get_latest_summary(scope, self.conv.id)
                with self.assertRaises(LookupError):
                    self.store.save_context_summary(
                        scope,
                        ContextSummary(self.conv.id, 1, "INJECTED", []),
                    )

    def test_foreign_retrieval_denied(self):
        for scope in self.scopes:
            with self.subTest(scope=scope):
                with self.assertRaises(LookupError):
                    self.store.retrieve_messages(
                        scope,
                        self.conv.id,
                        "SO_MARKET_PRIVATE",
                        before_sequence=3,
                    )

    def test_chat_service_cannot_send_to_foreign_conversation(self):
        for scope in self.scopes:
            with self.subTest(scope=scope):
                service = ChatService(
                    self.store, scope, self.root / "attachments",
                )
                with self.assertRaises(LookupError):
                    service.send(self.conv.id, "foreign text", action="query")
        self.assertEqual(
            self.store.get_conversation(self.a, self.conv.id).message_count,
            1,
        )

    def test_scope_cursors_cannot_cross_tenants_or_workspaces(self):
        self.store.create_conversation(self.a, "ANOTHER_A_CONVERSATION")
        cursor = self.store.list_conversations(self.a, page_size=1).next_cursor
        self.assertTrue(cursor)
        for scope in self.scopes:
            with self.subTest(scope=scope):
                with self.assertRaises(ValueError):
                    self.store.list_conversations(
                        scope, cursor=cursor, page_size=1,
                    )

    def test_history_cursor_cannot_cross_tenants_or_workspaces(self):
        self.store.append_message(
            self.a, Message(self.conv.id, "assistant", "second"),
        )
        cursor = self.store.list_messages(
            self.a, self.conv.id, page_size=1,
        ).next_cursor
        self.assertTrue(cursor)
        for scope in self.scopes:
            with self.subTest(scope=scope):
                # Conversation ownership is tested before cursor decoding.
                with self.assertRaises(LookupError):
                    self.store.list_messages(
                        scope, self.conv.id, cursor=cursor, page_size=1,
                    )

    def test_scope_is_not_authentication_expected_red_finding(self):
        # A plain dataclass is forgeable: the SAME exact tuple works, as expected.
        # This RED finding MUST remain visible. Nothing here proves real ID/ACL.
        supplied_by_untrusted_caller = Scope(
            self.a.owner_id, self.a.tenant_id, self.a.workspace_id,
        )
        result = self.store.get_conversation(
            supplied_by_untrusted_caller, self.conv.id,
        )
        self.assertEqual(result.id, self.conv.id)
        print(
            "A191_SCOPE_FORGERY=UNAUTHENTICATED_SCOPE_ACCEPTED_"
            "NEEDS_TRUSTED_ENTRYPOINT_AND_REAL_ACL_RED",
            flush=True,
        )

    def test_scoped_reads_still_isolate_after_local_restart(self):
        self.store.close()
        self.store = SQLiteChatStore(self.db_path)
        self.assertEqual(
            self.store.get_message(
                self.a, self.conv.id, self.msg.id,
            ).content,
            "SO_MARKET_PRIVATE_MARKER_SCOPE_A",
        )
        for scope in self.scopes:
            with self.subTest(scope=scope):
                self._assert_not_visible(scope)
                self.assertEqual(self.store.list_conversations(scope).items, [])

    def test_verified_backup_and_restore_preserve_scoped_reads_but_not_external_epoch(self):
        backup = self.root / "backup.sqlite3"
        report = self.store.backup_to(backup)
        self.assertEqual(report["state"], "BACKUP_VERIFIED")
        restored_path = self.root / "restore.sqlite3"
        restored = SQLiteChatStore.restore_from_backup(
            backup, restored_path,
        )
        self.assertEqual(restored["state"], "RESTORE_VERIFIED")
        second = SQLiteChatStore(restored_path)
        try:
            self.assertEqual(
                second.get_conversation(self.a, self.conv.id).id,
                self.conv.id,
            )
            for scope in self.scopes:
                with self.subTest(scope=scope):
                    with self.assertRaises(LookupError):
                        second.get_conversation(scope, self.conv.id)
        finally:
            second.close()
        # IMPORTANT: this local backup is NOT a witness against rollback.
        print(
            "A191_BACKUP_RESTORE=LOCAL_SCOPE_ISOLATION_ONLY_"
            "NO_INDEPENDENT_ANTI_ROLLBACK_RED",
            flush=True,
        )

    def test_invalid_scope_does_not_read_data(self):
        for raw in (
            None, "", {}, ("owner-a", "tenant-a", "trader"),
        ):
            with self.subTest(raw=raw):
                with self.assertRaises((TypeError, ValueError)):
                    self.store.get_conversation(raw, self.conv.id)

    def test_no_cross_scope_mutations_in_history(self):
        self.store.create_conversation(self.other_tenant, "TENANT_B_OWN")
        self.store.create_conversation(self.other_workspace, "INVESTMENT_OWN")
        self.store.create_conversation(self.other_owner, "OTHER_OWNER_OWN")
        for scope in (self.a, *self.scopes):
            found = self.store.list_conversations(scope).items
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].tenant_id, scope.tenant_id)
            self.assertEqual(found[0].workspace_id, scope.workspace_id)
            self.assertEqual(found[0].owner_id, scope.owner_id)


if __name__ == "__main__":
    unittest.main()
