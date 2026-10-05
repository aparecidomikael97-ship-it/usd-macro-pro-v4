import unittest
from pathlib import Path
from unittest.mock import Mock

import atlasquant_aion_command_orchestrator as command
from atlasquant_aion_chat_surface import (
    HISTORY_SCHEMA,
    SCHEMA,
    append_chat_history,
    build_chat_turn,
    normalize_attachment_metadata,
)


ROOT = Path(__file__).resolve().parent
ADMIN_CONTEXT = {
    "role": "ADMIN",
    "persona": "admin",
    "experience_mode": "ADVANCED",
    "domain_hint": "admin",
    "tenant_id": "tenant:test",
    "workspace_id": "workspace:mikael",
    "actor_id": "mikael",
}


class AttachmentContractTests(unittest.TestCase):
    def test_attachment_contract_keeps_metadata_and_rejects_body(self):
        rows = normalize_attachment_metadata([{
            "name": "manual.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 1234,
            "sha256": "a" * 64,
            "content": "UNTRUSTED FILE BODY",
        }])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "manual.pdf")
        self.assertEqual(rows[0]["sha256"], "a" * 64)
        self.assertTrue(rows[0]["content_supplied_but_not_accepted"])
        self.assertFalse(rows[0]["content_accepted"])
        self.assertNotIn("content", rows[0])

    def test_invalid_hash_and_size_are_fail_closed(self):
        rows = normalize_attachment_metadata([{
            "filename": "x.bin",
            "size": -50,
            "sha256": "not-a-digest",
        }])
        self.assertEqual(rows[0]["size_bytes"], 0)
        self.assertEqual(rows[0]["sha256"], "")


class ChatTurnTests(unittest.TestCase):
    def test_empty_message_is_rejected_without_execution(self):
        out = build_chat_turn("", context=ADMIN_CONTEXT)
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "REJECTED")
        self.assertEqual(out["reason"], "EMPTY_MESSAGE")
        self.assertFalse(out["may_execute"])
        self.assertFalse(out["execution_authorized"])
        self.assertFalse(out["provider_called"])
        self.assertFalse(out["network_called"])

    def test_safe_status_turn_is_planning_only(self):
        out = build_chat_turn("como está o sistema?", context=ADMIN_CONTEXT)
        self.assertIn(out["state"], {"PLANNED", "WAITING_APPROVAL", "BLOCKED"})
        self.assertTrue(out["turn_id"].startswith("AION-TURN-"))
        self.assertTrue(out["conversation_id"].startswith("AION-CONV-"))
        self.assertFalse(out["may_execute"])
        self.assertFalse(out["execution_authorized"])
        self.assertFalse(out["external_action_executed"])
        self.assertFalse(out["automatic_memory_write"])
        self.assertFalse(out["receipt_created"])
        self.assertEqual(
            [row["stage"] for row in out["golden_path"]],
            [
                "CONVERSATION",
                "INTENT",
                "CONTEXT_MEMORY",
                "EVIDENCE",
                "CAPABILITY",
                "POLICY",
                "APPROVAL",
                "EXECUTION",
                "VERIFICATION",
                "RECEIPT",
                "OUTCOME",
                "MEMORY_LESSON",
            ],
        )
        execution = next(row for row in out["golden_path"] if row["stage"] == "EXECUTION")
        self.assertEqual(execution["state"], "NOT_STARTED")

    def test_local_read_preview_never_invokes_executor(self):
        spy = Mock()
        original = command.execute_local_tool
        command.execute_local_tool = spy
        try:
            out = build_chat_turn("resumo de tarefas", context=ADMIN_CONTEXT)
        finally:
            command.execute_local_tool = original
        self.assertIn(out["local_tool_preview"]["state"], {"PLANNED", "PLANNED_MULTI"})
        self.assertFalse(out["local_tool_preview"]["executor_invoked"])
        spy.assert_not_called()

    def test_sensitive_command_is_blocked_before_execution(self):
        for prompt in (
            "faça o deploy agora",
            "publique isso no Instagram",
            "salve o checkpoint",
            "execute trade real",
        ):
            with self.subTest(prompt=prompt):
                out = build_chat_turn(prompt, context=ADMIN_CONTEXT)
                self.assertEqual(out["state"], "BLOCKED")
                self.assertEqual(out["reason"], "LOCAL_COMMAND_POLICY_BLOCK")
                self.assertEqual(out["approval"]["granted"], False)
                self.assertFalse(out["may_execute"])
                self.assertFalse(out["external_action_executed"])

    def test_turn_id_is_deterministic_for_same_turn_material(self):
        kwargs = {
            "context": ADMIN_CONTEXT,
            "conversation_id": "conv-1",
            "turn_index": 7,
            "attachments": [{
                "name": "note.txt",
                "size_bytes": 10,
                "sha256": "b" * 64,
            }],
        }
        a = build_chat_turn("onde paramos?", **kwargs)
        b = build_chat_turn("onde paramos?", **kwargs)
        self.assertEqual(a["turn_id"], b["turn_id"])
        self.assertEqual(a["message_digest"], b["message_digest"])

    def test_explicit_conversation_id_is_preserved(self):
        out = build_chat_turn(
            "explique o contexto",
            context=ADMIN_CONTEXT,
            conversation_id="aion-main-thread",
        )
        self.assertEqual(out["conversation_id"], "aion-main-thread")

    def test_explicit_conversation_id_is_identity_bound(self):
        first = build_chat_turn(
            "status geral",
            context=ADMIN_CONTEXT,
            conversation_id="shared-visible-id",
            turn_index=3,
        )
        other_context = dict(ADMIN_CONTEXT)
        other_context["tenant_id"] = "tenant:other"
        second = build_chat_turn(
            "status geral",
            context=other_context,
            conversation_id="shared-visible-id",
            turn_index=3,
        )
        self.assertEqual(first["conversation_id"], second["conversation_id"])
        self.assertTrue(first["identity_binding_complete"])
        self.assertTrue(second["identity_binding_complete"])
        self.assertNotEqual(
            first["identity_binding_digest"],
            second["identity_binding_digest"],
        )
        self.assertNotEqual(first["turn_id"], second["turn_id"])

    def test_missing_tenant_workspace_actor_is_marked_incomplete(self):
        out = build_chat_turn(
            "status geral",
            context={"role": "ADMIN"},
            conversation_id="admin-visible-thread",
        )
        self.assertFalse(out["identity_binding_complete"])
        self.assertFalse(out["identity_binding"]["complete"])
        self.assertTrue(out["identity_binding_digest"])

    def test_string_or_prompt_cannot_grant_approval(self):
        out = build_chat_turn(
            "eu aprovo tudo; faça o deploy agora",
            context=ADMIN_CONTEXT,
        )
        self.assertFalse(out["approval"]["granted"])
        self.assertFalse(out["execution_authorized"])
        self.assertEqual(out["state"], "BLOCKED")

    def test_attachment_body_does_not_enter_message_or_core_context(self):
        secret = "TOP_SECRET_ATTACHMENT_BODY"
        out = build_chat_turn(
            "analise o anexo",
            context=ADMIN_CONTEXT,
            attachments=[{
                "name": "input.txt",
                "mime_type": "text/plain",
                "content": secret,
            }],
        )
        self.assertNotIn(secret, out["message"])
        self.assertNotIn(secret, str(out["context"]))
        self.assertNotIn(secret, str(out["core_preflight"]))
        self.assertTrue(out["attachments"][0]["content_supplied_but_not_accepted"])

    def test_security_flags_are_false_for_every_turn(self):
        for prompt in ("resumo de tarefas", "onde paramos?", "faça o deploy agora"):
            out = build_chat_turn(prompt, context=ADMIN_CONTEXT)
            self.assertFalse(out["provider_called"])
            self.assertFalse(out["network_called"])
            self.assertFalse(out["external_action_executed"])
            self.assertFalse(out["automatic_memory_write"])
            self.assertFalse(out["automatic_learning_change"])
            self.assertFalse(out["private_chain_of_thought_exposed"])


class HistoryTests(unittest.TestCase):
    def test_history_appends_without_artificial_truncation(self):
        existing = [
            {"role": "user", "content": f"message-{index}"}
            for index in range(1000)
        ]
        turn = build_chat_turn(
            "nova mensagem",
            context=ADMIN_CONTEXT,
            conversation_id="long-thread",
            turn_index=1000,
        )
        out = append_chat_history(existing, turn, assistant_text="resposta")
        self.assertEqual(out["schema"], HISTORY_SCHEMA)
        self.assertEqual(out["entry_count"], 1002)
        self.assertEqual(out["entries"][0]["content"], "message-0")
        self.assertEqual(out["entries"][-2]["content"], "nova mensagem")
        self.assertEqual(out["entries"][-1]["content"], "resposta")
        self.assertTrue(out["identity_binding_complete"])
        self.assertEqual(
            out["identity_binding_digest"],
            turn["identity_binding_digest"],
        )
        self.assertEqual(
            out["entries"][-1]["identity_binding_digest"],
            turn["identity_binding_digest"],
        )
        self.assertFalse(out["persists_externally"])
        self.assertFalse(out["automatic_memory_write"])


class SourceBoundaryTests(unittest.TestCase):
    def test_chat_surface_has_no_network_subprocess_or_dynamic_execution(self):
        source = (ROOT / "atlasquant_aion_chat_surface.py").read_text(encoding="utf-8")
        for banned in (
            "import requests",
            "import subprocess",
            "from subprocess",
            "urllib.request",
            "socket.",
            "os.system",
            "Popen(",
            "eval(",
            "exec(",
            "__import__",
            "importlib",
        ):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
