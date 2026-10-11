"""Disposable scoped SQLite tests for pending model user turn staging.

No provider, external network, production database, host PC or paid API.
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_chat_pending_model_turn_v1 import (
    STATE, SCHEMA, UNTRUSTED_FLAGS, stage_pending_model_user_turn,
)
from atlasquant_aion_chat_surface import MAX_MESSAGE_CHARS


def access(username="owner", *, role="ADMIN", allowed=True, mode="AUTHENTICATED"):
    return {
        "allowed": allowed, "mode": mode, "role": role,
        "session": {
            "role": role, "username": username,
            "credential_fingerprint": "fixture-fingerprint",
            "permissions": ["app:read", "aion:admin"],
        },
    }


class StageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "staging.db"
        self.store = SQLiteChatStore(self.path)
        self.scope = Scope("owner", "tenant1", "workspace1")
        self.conversation = self.store.create_conversation(self.scope, "AION")
        self.cid = self.conversation.id

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def stage(self, **overrides):
        opts = {
            "store": self.store, "scope": self.scope, "access": access(),
            "conversation_id": self.cid, "request_id": "request0001",
            "message": "Me explique um conceito econômico",
        }
        opts.update(overrides)
        receipt = stage_pending_model_user_turn(
            opts["store"], opts["scope"], opts["access"],
            conversation_id=opts["conversation_id"],
            request_id=opts["request_id"], message=opts["message"],
        )
        self.assertEqual(receipt["schema"], SCHEMA)
        for field, value in UNTRUSTED_FLAGS.items():
            self.assertIs(receipt[field], value, field)
        self.assertFalse(receipt["trusted_host_store_provenance_attested"])
        self.assertFalse(receipt["external_model_path_activated"])
        return receipt

    def test_stages_actual_persisted_user_message(self):
        receipt = self.stage()
        self.assertEqual(receipt["state"], STATE)
        m = self.store.get_message(self.scope, self.cid, receipt["message_id"])
        self.assertEqual(m.role, "user")
        self.assertEqual(m.content, "Me explique um conceito econômico")
        self.assertEqual(m.metadata["approval_state"], "PENDING")
        self.assertIs(m.metadata["model_invocation_authorized"], False)
        self.assertEqual(self.store.get_conversation(self.scope, self.cid).message_count, 1)
        self.assertNotIn(m.content, str(receipt))
        self.assertEqual(len(receipt["message_sha256"]), 64)

    def test_repeated_request_is_idempotent(self):
        r1 = self.stage()
        r2 = self.stage()
        self.assertEqual(r2["state"], "IDEMPOTENT_STAGED")
        self.assertEqual(r1["message_id"], r2["message_id"])
        self.assertEqual(self.store.get_conversation(self.scope, self.cid).message_count, 1)

    def test_reused_request_id_with_new_text_fails_closed(self):
        self.stage()
        with self.assertRaisesRegex(ValueError, "different message"):
            self.stage(message="conteúdo alterado")
        self.assertEqual(self.store.get_conversation(self.scope, self.cid).message_count, 1)

    def test_different_request_id_writes_new_user_turn(self):
        r1 = self.stage()
        r2 = self.stage(request_id="request0002")
        self.assertNotEqual(r1["message_id"], r2["message_id"])
        self.assertEqual(self.store.get_conversation(self.scope, self.cid).message_count, 2)

    def test_two_conversations_have_independent_ids(self):
        r1 = self.stage()
        cid2 = self.store.create_conversation(self.scope, "B").id
        r2 = self.stage(conversation_id=cid2)
        self.assertNotEqual(r1["message_id"], r2["message_id"])
        with self.assertRaises(LookupError):
            self.store.get_message(self.scope, cid2, r1["message_id"])

    def test_reopen_store_preserves_idempotency(self):
        first = self.stage()
        self.store.db.close()
        self.store = SQLiteChatStore(self.path)
        again = self.stage()
        self.assertEqual(again["state"], "IDEMPOTENT_STAGED")
        self.assertEqual(first["request_digest"], again["request_digest"])
        self.assertEqual(self.store.get_conversation(self.scope, self.cid).message_count, 1)

    def test_disabled_login_is_rejected_without_write(self):
        for bad in (access(allowed=False), access(mode="PREVIEW"),
                    access(role="USER"), access(username="other")):
            with self.subTest(bad=bad):
                with self.assertRaises(PermissionError):
                    self.stage(access=bad)
        self.assertEqual(self.store.get_conversation(self.scope, self.cid).message_count, 0)

    def test_missing_permission_and_fingerprint_fail(self):
        a = access(); a["session"]["permissions"] = []
        with self.assertRaises(PermissionError):
            self.stage(access=a)
        a = access(); a["session"]["credential_fingerprint"] = ""
        with self.assertRaises(PermissionError):
            self.stage(access=a)
        self.assertEqual(self.store.get_conversation(self.scope, self.cid).message_count, 0)

    def test_untrusted_scope_is_rejected(self):
        with self.assertRaises(TypeError):
            self.stage(scope={"owner_id":"owner"})
        with self.assertRaises(PermissionError):
            self.stage(scope=Scope("someone", "tenant1", "workspace1"))
        with self.assertRaises(LookupError):
            self.stage(scope=Scope("owner", "tenant2", "workspace1"))

    def test_invalid_conversation_is_rejected(self):
        for cid in (None, False, "", "x"*121):
            with self.subTest(cid=cid):
                with self.assertRaises(ValueError):
                    self.stage(conversation_id=cid)
        with self.assertRaises(LookupError):
            self.stage(conversation_id="unknown-conversation")
        self.assertEqual(self.store.get_conversation(self.scope, self.cid).message_count, 0)

    def test_archived_conversation_is_rejected(self):
        self.store.archive_conversation(self.scope, self.cid)
        with self.assertRaises(ValueError):
            self.stage()

    def test_invalid_request_id_rejected(self):
        for req in (None, False, "", "short", "x"*81, "with space",
                    "/../../etc/passwd", "🔥"*8):
            with self.subTest(req=req):
                with self.assertRaises(ValueError):
                    self.stage(request_id=req)
        self.assertEqual(self.store.get_conversation(self.scope, self.cid).message_count, 0)

    def test_nonstring_empty_and_overlong_message_rejected(self):
        for msg in (None, b"hello", False, {}, "", " \n ", "a"*(MAX_MESSAGE_CHARS+1)):
            with self.subTest(value=type(msg).__name__):
                with self.assertRaises(ValueError):
                    self.stage(message=msg)
        self.assertEqual(self.store.get_conversation(self.scope, self.cid).message_count, 0)

    def test_sensitive_text_not_eligible_for_external_model_staging(self):
        for msg in ("minha senha é 123", "cartão de crédito 123",
                    "API key: secret", "meu CPF", "token de acesso"):
            with self.subTest(value=msg[:9]):
                with self.assertRaisesRegex(ValueError, "sensitive"):
                    self.stage(message=msg)
        self.assertEqual(self.store.get_conversation(self.scope, self.cid).message_count, 0)

    def test_full_message_is_preserved_without_trim(self):
        msg = " Explique inflação\nCom exemplo local "
        receipt = self.stage(message=msg)
        stored = self.store.get_message(self.scope, self.cid, receipt["message_id"])
        self.assertEqual(stored.content, msg)

    def test_user_message_at_exact_bound(self):
        self.stage(message="x"*MAX_MESSAGE_CHARS)
        self.assertEqual(self.store.get_conversation(self.scope, self.cid).message_count, 1)

    def test_bogus_client_flags_are_not_parameters(self):
        with self.assertRaises(TypeError):
            stage_pending_model_user_turn(
                self.store, self.scope, access(),
                conversation_id=self.cid,
                request_id="request0001",
                message="olá", approved=True,
            )
        self.assertEqual(self.store.get_conversation(self.scope, self.cid).message_count, 0)

    def test_no_provider_calls_when_staging(self):
        import requests
        with patch.object(requests.sessions.Session, "request",
                          side_effect=AssertionError("NETWORK FORBIDDEN")):
            self.stage()
        self.assertEqual(self.store.get_conversation(self.scope, self.cid).message_count, 1)

    def test_no_model_output_or_assistant_message(self):
        self.stage()
        page = self.store.list_messages(self.scope, self.cid)
        self.assertEqual(len(page.items), 1)
        self.assertEqual(page.items[0].role, "user")
        self.assertEqual(page.items[0].metadata["approval_state"], "PENDING")
        self.assertIs(page.items[0].metadata["model_invocation_authorized"], False)

    def test_failed_store_write_does_not_claim_success(self):
        class FailWrite:
            def __init__(self, original): self.original=original
            def get_conversation(self, *args): return self.original.get_conversation(*args)
            def get_message(self, *args): return self.original.get_message(*args)
            def append_message(self, *args): raise RuntimeError("DISK_FULL")
        with self.assertRaises((RuntimeError, LookupError)):
            self.stage(store=FailWrite(self.store))
        self.assertEqual(self.store.get_conversation(self.scope, self.cid).message_count, 0)

    def test_uncertain_response_after_actual_commit_reconciles(self):
        class LostResponse:
            def __init__(self, original): self.original=original
            def get_conversation(self, *args): return self.original.get_conversation(*args)
            def get_message(self, *args): return self.original.get_message(*args)
            def append_message(self, *args):
                self.original.append_message(*args)
                raise TimeoutError("response lost after commit")
        receipt = self.stage(store=LostResponse(self.store))
        self.assertEqual(receipt["state"], "IDEMPOTENT_STAGED")
        self.assertEqual(self.store.get_conversation(self.scope, self.cid).message_count, 1)

    def test_replay_after_uncertain_write_with_changed_content_is_blocked(self):
        self.stage()
        with self.assertRaisesRegex(ValueError, "different message"):
            self.stage(message="texto diferente")
        self.assertEqual(self.store.get_conversation(self.scope, self.cid).message_count, 1)

    def test_does_not_modify_login_or_grant_owner_privilege(self):
        a = access()
        original = {**a, "session":dict(a["session"])}
        self.stage(access=a)
        self.assertEqual(a, original)
        r = self.stage()
        self.assertFalse(r["owner_signature_verified"])
        self.assertFalse(r["model_invocation_authorized"])


if __name__ == "__main__":
    unittest.main()
