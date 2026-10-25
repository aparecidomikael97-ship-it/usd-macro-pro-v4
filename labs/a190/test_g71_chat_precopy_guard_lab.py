"""G71 RED-first: guard chat Message graphs before recursive dataclass copying.

Synthetic objects, temporary SQLite only. No provider/Worker/deploy.
"""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aion_chat.models import Message, Scope
from aion_chat.store import SQLiteChatStore

SCOPE = Scope("g71-owner", "g71-tenant", "g71-space")


class G71ChatPrecopyGuard(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="a190-g71-synthetic-")
        self.addCleanup(tmp.cleanup)
        self.store = SQLiteChatStore(Path(tmp.name) / "g71.sqlite3")
        self.addCleanup(self.store.close)
        self.db = self.store.db
        self.conversation = self.store.create_conversation(SCOPE, title="G71 fake")

    def deny(self, metadata, marker):
        original = Message(conversation_id=self.conversation.id, role="user",
                           content="public-synthetic", metadata=metadata)
        with self.assertRaisesRegex(ValueError, marker):
            self.store.append_message(SCOPE, original)
        self.assertFalse(self.db.in_transaction)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 0)
        self.assertEqual(self.store.get_conversation(
            SCOPE, self.conversation.id).message_count, 0)
        self.assertEqual(self.store.storage_health()["state"], "healthy")

    def test_01_direct_metadata_dict_cycle_is_stable_denial(self):
        cyclic = {}
        cyclic["loop"] = cyclic
        self.deny(cyclic, "G70_REDACT_CYCLE_DENY")
        print("G71_DICT_CYCLE_GREEN=DENY_AND_ROLLBACK")

    def test_02_indirect_tuple_list_cycle_is_stable_denial(self):
        cyclic = []
        cyclic.append((cyclic,))
        self.deny({"path": cyclic}, "G70_REDACT_CYCLE_DENY")
        print("G71_TUPLE_CYCLE_GREEN=DENY_AND_ROLLBACK")

    def test_03_hidden_sensitive_cycle_cannot_bypass_guard(self):
        cyclic = []
        cyclic.append(cyclic)
        self.deny({"password": cyclic, "note": "public"}, "G70_REDACT_CYCLE_DENY")
        print("G71_MASKED_CYCLE_GREEN=DENY_AND_ROLLBACK")

    def test_04_no_recursive_asdict_before_cycle_guard(self):
        cyclic = []
        cyclic.append(cyclic)
        with patch("aion_chat.store.asdict", side_effect=AssertionError(
                "recursive copy reached before G70 guard")):
            self.deny({"loop": cyclic}, "G70_REDACT_CYCLE_DENY")
        print("G71_PRECOPY_GREEN=GUARD_BEFORE_ASDICT")

    def test_05_shared_dag_expansion_refused_without_partial_write(self):
        tree = ["fake-leaf"]
        for _ in range(14):
            tree = [tree, tree]
        self.deny({"dag": tree}, "G70_REDACT_NODE_BUDGET_DENY")
        print("G71_DAG_GREEN=BOUNDED_EXPANSION")

    def test_06_normal_message_persists_redacted_without_input_mutation(self):
        metadata = {"password": "FAKE_G71_SECRET", "public": ["okay"]}
        original = Message(conversation_id=self.conversation.id, role="user",
                           content="hello", metadata=metadata)
        saved = self.store.append_message(SCOPE, original)
        self.assertEqual(saved.metadata["password"], "[REDACTED]")
        self.assertEqual(metadata["password"], "FAKE_G71_SECRET")
        self.assertEqual(self.store.get_message(
            SCOPE, self.conversation.id, saved.id).metadata["password"], "[REDACTED]")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 1)
        self.assertEqual(self.store.get_conversation(
            SCOPE, self.conversation.id).message_count, 1)
        print("G71_NORMAL_GREEN=REDACTED_PERSISTED")


if __name__ == "__main__":
    unittest.main()
