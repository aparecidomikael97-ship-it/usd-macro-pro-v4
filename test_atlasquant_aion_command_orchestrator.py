import unittest
from pathlib import Path
from unittest.mock import Mock

import atlasquant_aion_command_orchestrator as command
from atlasquant_aion_command_orchestrator import (
    SAFE_KINDS,
    command_catalog,
    orchestrate_local_command,
    plan_local_command,
)
from atlasquant_aion_memory import default_checkpoint


ROOT = Path(__file__).resolve().parent
ADMIN = {"role": "ADMIN", "session": {"username": "mikael", "role": "ADMIN"}}


class CatalogTests(unittest.TestCase):
    def test_catalog_is_exactly_the_eleven_safe_local_tools(self):
        catalog = command_catalog()
        self.assertEqual(len(catalog), 11)
        self.assertTrue(all(item["kind"] in SAFE_KINDS for item in catalog))
        ids = {item["tool_id"] for item in catalog}
        self.assertNotIn("aion.checkpoint.prepare_save", ids)

    def test_source_has_no_external_or_dynamic_execution(self):
        source = (ROOT / "atlasquant_aion_command_orchestrator.py").read_text(encoding="utf-8")
        for banned in (
            "import subprocess", "from subprocess", "eval(", "exec(", "__import__",
            "importlib", "import socket", "urllib", "import requests", "os.system", "Popen(",
        ):
            self.assertNotIn(banned, source)


class PlanningTests(unittest.TestCase):
    def test_memory_continuity_question_selects_canonical_search(self):
        out = plan_local_command("AION, onde paramos no sistema?")
        self.assertEqual(out["state"], "READY")
        self.assertEqual(out["tool_id"], "aion.memory.search")
        self.assertEqual(out["kind"], "SEARCH")
        self.assertFalse(out["executes_tool"])

    def test_status_and_specialist_questions_are_deterministic(self):
        status = plan_local_command("como está o sistema?")
        studio = plan_local_command("como está o Studio?")
        self.assertEqual(status["tool_id"], "aion.status.read")
        self.assertEqual(studio["tool_id"], "aion.specialists.snapshot")

    def test_sensitive_action_is_blocked_before_executor(self):
        for question in (
            "faça o deploy agora",
            "publique isso no Instagram",
            "salve o checkpoint",
            "mostre meu token de API",
            "execute trade real",
        ):
            out = plan_local_command(question)
            self.assertEqual(out["state"], "BLOCKED_INTENT", question)
            self.assertEqual(out["tool_id"], "")
            self.assertFalse(out["executes_tool"])

    def test_unmatched_question_does_not_guess_a_tool(self):
        out = plan_local_command("explique isso com cuidado")
        self.assertEqual(out["state"], "NO_MATCH")
        self.assertEqual(out["tool_id"], "")


class ExecutionTests(unittest.TestCase):
    def test_preview_never_invokes_executor(self):
        spy = Mock()
        original = command.execute_local_tool
        command.execute_local_tool = spy
        try:
            out = orchestrate_local_command("resumo de tarefas", execute=False)
        finally:
            command.execute_local_tool = original
        self.assertEqual(out["state"], "PLANNED")
        self.assertFalse(out["executor_invoked"])
        self.assertFalse(out["handler_executed"])
        spy.assert_not_called()

    def test_sensitive_intent_never_invokes_executor_even_when_execute_true(self):
        spy = Mock()
        original = command.execute_local_tool
        command.execute_local_tool = spy
        try:
            out = orchestrate_local_command("publique isso agora", execute=True)
        finally:
            command.execute_local_tool = original
        self.assertEqual(out["state"], "BLOCKED_INTENT")
        self.assertFalse(out["executor_invoked"])
        self.assertFalse(out["external_action_executed"])
        spy.assert_not_called()

    def test_safe_command_delegates_with_approval_false(self):
        spy = Mock(return_value={
            "state": "SUCCESS",
            "result": {"total": 3, "active": 2, "waiting_approval": 1, "blocked": 0},
            "preflight": {"state": "READY_FOR_EXECUTOR", "blockers": []},
            "security": {"external_side_effects": False},
            "external_action_executed": False,
            "real_orders_enabled": False,
        })
        original = command.execute_local_tool
        command.execute_local_tool = spy
        try:
            out = orchestrate_local_command(
                "resumo de tarefas",
                execute=True,
                runtime_context={"checkpoint": default_checkpoint()},
                access=ADMIN,
                authenticated_admin=True,
            )
        finally:
            command.execute_local_tool = original
        self.assertEqual(out["state"], "SUCCESS")
        self.assertTrue(out["executor_invoked"])
        self.assertTrue(out["handler_executed"])
        self.assertIn("Tarefas locais", out["summary"])
        kwargs = spy.call_args.kwargs
        self.assertFalse(kwargs["approved"])
        self.assertTrue(kwargs["authenticated_admin"])
        self.assertFalse(out["external_action_executed"])
        self.assertFalse(out["real_orders_enabled"])

    def test_real_executor_still_uses_tool_hub_preflight(self):
        out = orchestrate_local_command(
            "resumo de tarefas",
            execute=True,
            runtime_context={"checkpoint": default_checkpoint()},
            access=ADMIN,
            source_kind="EXTERNAL_AI",
            authenticated_admin=False,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertTrue(out["executor_invoked"])
        self.assertFalse(out["handler_executed"])
        result = out["tool_result"]
        self.assertIn("SOURCE_HAS_NO_COMMAND_AUTHORITY", result["preflight"]["blockers"])
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["real_orders_enabled"])

    def test_real_admin_read_executes_without_external_effect(self):
        out = orchestrate_local_command(
            "resumo de tarefas",
            execute=True,
            runtime_context={"checkpoint": default_checkpoint()},
            access=ADMIN,
            source_kind="ADMIN",
            authenticated_admin=True,
        )
        self.assertEqual(out["state"], "SUCCESS")
        self.assertTrue(out["handler_executed"])
        result = out["tool_result"]
        self.assertFalse(result["security"]["network_called"])
        self.assertFalse(result["security"]["connector_called"])
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["real_orders_enabled"])


if __name__ == "__main__":
    unittest.main()
