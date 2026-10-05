from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_chat_product_bridge import (
    CREATE_SCHEMA,
    RESUME_SCHEMA,
    SCHEMA,
    TURN_SCHEMA,
    create_product_conversation,
    execute_product_read_turn,
    resume_product_conversation,
    validate_product_binding,
)
from atlasquant_aion_memory import default_checkpoint


ROOT = Path(__file__).resolve().parent


def authenticated_access(username="mikael", *, permissions=None):
    return {
        "allowed": True,
        "mode": "AUTHENTICATED",
        "reason": "OK",
        "role": "ADMIN",
        "session": {
            "username": username,
            "role": "ADMIN",
            "permissions": list(
                permissions
                if permissions is not None
                else ["app:read", "aion:admin", "aion:checkpoint"]
            ),
            "credential_fingerprint": "credential-fingerprint-test",
            "authenticated_at": 1.0,
            "last_seen": 1.0,
        },
    }


class ProductBindingTests(unittest.TestCase):
    def setUp(self):
        self.scope = Scope("mikael", "tenant-a", "workspace-a")

    def test_authenticated_admin_scope_binds(self):
        out = validate_product_binding(
            authenticated_access(),
            self.scope,
        )
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "BOUND")
        self.assertTrue(out["bound"])
        self.assertTrue(out["authenticated"])
        self.assertTrue(out["permissions_verified"])
        self.assertFalse(out["grants_authority"])
        self.assertFalse(out["executes_action"])

    def test_preview_and_open_modes_are_rejected(self):
        for mode in ("PREVIEW", "OPEN"):
            access = authenticated_access()
            access["mode"] = mode
            with self.subTest(mode=mode):
                out = validate_product_binding(access, self.scope)
                self.assertFalse(out["bound"])
                self.assertIn(
                    "AUTHENTICATED_MODE_REQUIRED",
                    out["blockers"],
                )

    def test_scope_owner_must_match_authenticated_username(self):
        out = validate_product_binding(
            authenticated_access("other-user"),
            self.scope,
        )
        self.assertFalse(out["bound"])
        self.assertIn("SCOPE_OWNER_MISMATCH", out["blockers"])

    def test_missing_fingerprint_or_permission_fails_closed(self):
        no_fingerprint = authenticated_access()
        no_fingerprint["session"]["credential_fingerprint"] = ""
        out = validate_product_binding(no_fingerprint, self.scope)
        self.assertFalse(out["bound"])
        self.assertIn(
            "CREDENTIAL_FINGERPRINT_REQUIRED",
            out["blockers"],
        )

        missing_permission = authenticated_access(
            permissions=["app:read"],
        )
        out = validate_product_binding(missing_permission, self.scope)
        self.assertFalse(out["bound"])
        self.assertIn(
            "MISSING_PERMISSION:aion:admin",
            out["blockers"],
        )

    def test_non_admin_role_fails_closed(self):
        access = authenticated_access()
        access["role"] = "USER"
        access["session"]["role"] = "USER"
        out = validate_product_binding(access, self.scope)
        self.assertFalse(out["bound"])
        self.assertIn("ADMIN_ROLE_REQUIRED", out["blockers"])


class ProductCompositionTests(unittest.TestCase):
    def setUp(self):
        self.scope = Scope("mikael", "tenant-a", "workspace-a")
        self.access = authenticated_access()

    def _store(self, root):
        return SQLiteChatStore(Path(root) / "chat.sqlite3")

    def test_explicit_create_then_verified_read_then_resume(self):
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(raw)

            created = create_product_conversation(
                store,
                self.scope,
                self.access,
                title="Conversa principal",
            )
            self.assertEqual(created["schema"], CREATE_SCHEMA)
            self.assertEqual(created["state"], "CREATED")
            self.assertFalse(created["automatic_creation"])
            self.assertFalse(created["external_action_executed"])

            cid = created["conversation_id"]
            turn = execute_product_read_turn(
                store,
                self.scope,
                self.access,
                "status geral\n  com detalhes",
                conversation_id=cid,
                runtime_context={"checkpoint": default_checkpoint()},
                turn_index=1,
            )
            self.assertEqual(turn["schema"], TURN_SCHEMA)
            self.assertEqual(
                turn["state"],
                "CONFIRMED_AND_PERSISTED",
            )
            self.assertFalse(turn["provider_called"])
            self.assertFalse(turn["network_called"])
            self.assertFalse(turn["external_action_executed"])
            self.assertFalse(turn["memory_promoted"])
            self.assertEqual(
                turn["result"]["golden_result"]["turn"]["message"],
                "status geral\n  com detalhes",
            )

            resume = resume_product_conversation(
                store,
                self.scope,
                self.access,
                cid,
            )
            self.assertEqual(resume["schema"], RESUME_SCHEMA)
            self.assertEqual(resume["state"], "READY")
            self.assertEqual(resume["resume"]["message_count"], 2)
            self.assertEqual(
                resume["resume"]["context"]["recent"][0]["content"],
                "status geral\n  com detalhes",
            )
            self.assertFalse(resume["automatic_checkpoint_write"])
            self.assertFalse(resume["memory_promoted"])
            store.close()

    def test_sensitive_command_is_not_persisted(self):
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(raw)
            created = create_product_conversation(
                store,
                self.scope,
                self.access,
            )
            cid = created["conversation_id"]
            out = execute_product_read_turn(
                store,
                self.scope,
                self.access,
                "faça o deploy agora",
                conversation_id=cid,
                runtime_context={"checkpoint": default_checkpoint()},
                turn_index=2,
            )
            self.assertEqual(out["state"], "NOT_PERSISTED")
            self.assertFalse(out["external_action_executed"])
            self.assertEqual(
                store.get_conversation(self.scope, cid).message_count,
                0,
            )
            store.close()

    def test_wrong_scope_cannot_reopen_or_execute_conversation(self):
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(raw)
            created = create_product_conversation(
                store,
                self.scope,
                self.access,
            )
            cid = created["conversation_id"]
            other_scope = Scope("mikael", "tenant-b", "workspace-a")

            with self.assertRaises(LookupError):
                resume_product_conversation(
                    store,
                    other_scope,
                    self.access,
                    cid,
                )
            with self.assertRaises(LookupError):
                execute_product_read_turn(
                    store,
                    other_scope,
                    self.access,
                    "status geral",
                    conversation_id=cid,
                    runtime_context={"checkpoint": default_checkpoint()},
                )
            store.close()

    def test_mismatched_owner_is_rejected_before_store_call(self):
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(raw)
            other_scope = Scope(
                "other-user",
                "tenant-a",
                "workspace-a",
            )
            with self.assertRaises(PermissionError):
                create_product_conversation(
                    store,
                    other_scope,
                    self.access,
                )
            self.assertEqual(
                store.list_conversations(self.scope).items,
                [],
            )
            store.close()

    def test_runtime_context_is_required_for_execution(self):
        with tempfile.TemporaryDirectory() as raw:
            store = self._store(raw)
            created = create_product_conversation(
                store,
                self.scope,
                self.access,
            )
            with self.assertRaises(TypeError):
                execute_product_read_turn(
                    store,
                    self.scope,
                    self.access,
                    "status geral",
                    conversation_id=created["conversation_id"],
                    runtime_context=None,
                )
            store.close()


class SourceBoundaryTests(unittest.TestCase):
    def test_product_bridge_has_no_hidden_storage_network_provider_or_scope_default(self):
        source = (
            ROOT / "atlasquant_aion_chat_product_bridge.py"
        ).read_text(encoding="utf-8")
        for banned in (
            "SQLiteChatStore(",
            "Path(",
            "tempfile",
            "default_checkpoint(",
            "Scope(",
            "import requests",
            "import subprocess",
            "from subprocess",
            "urllib.request",
            "socket.",
            "os.system",
            "Popen(",
            "compact_conversation",
            "save_checkpoint",
            "save_context_summary",
        ):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
