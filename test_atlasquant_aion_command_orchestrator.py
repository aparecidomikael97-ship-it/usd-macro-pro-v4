import unittest
from pathlib import Path
from unittest.mock import Mock

import atlasquant_aion_command_orchestrator as command
from atlasquant_aion_command_orchestrator import (
    BUNDLE_SAFE_KINDS,
    MAX_BUNDLE_TOOLS,
    SAFE_KINDS,
    command_catalog,
    orchestrate_local_command,
    plan_local_bundle,
    plan_local_command,
)
from atlasquant_aion_local_traceability import local_contract_fingerprint
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

    def test_compound_read_question_builds_bounded_bundle(self):
        out = plan_local_bundle("AION, onde paramos e o que falta?")
        self.assertEqual(out["state"], "READY_MULTI")
        self.assertEqual(out["selected_count"], 2)
        self.assertEqual(out["tool_ids"], ["aion.memory.search", "aion.tasks.summary"])
        self.assertLessEqual(out["selected_count"], MAX_BUNDLE_TOOLS)
        self.assertTrue(all(kind in BUNDLE_SAFE_KINDS for kind in out["kinds"]))
        self.assertFalse(out["executes_tools"])

    def test_bundle_never_includes_draft(self):
        out = plan_local_bundle("briefing executivo e resumo de tarefas")
        self.assertNotIn("DRAFT", out.get("kinds", []))
        self.assertTrue(out["excluded_draft_from_bundle"])

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

    def test_memory_match_uses_word_boundaries_not_substrings(self):
        for question in ("deslembrado", "lembranca", "uma deslembrada qualquer"):
            single = plan_local_command(question)
            bundle = plan_local_bundle(question)
            self.assertEqual(single["state"], "NO_MATCH", question)
            self.assertNotIn("aion.memory.search", bundle.get("tool_ids", []), question)

        positive = plan_local_command("você lembra onde paramos?")
        self.assertEqual(positive["state"], "READY")
        self.assertEqual(positive["tool_id"], "aion.memory.search")

    def test_additional_sensitive_phrases_are_explicitly_blocked(self):
        for question in (
            "cobrar cliente agora",
            "fazer pagamento",
            "enviar ordem real",
            "publicação imediata",
        ):
            single = plan_local_command(question)
            bundle = plan_local_bundle(question)
            self.assertEqual(single["state"], "BLOCKED_INTENT", question)
            self.assertEqual(bundle["state"], "BLOCKED_INTENT", question)
            self.assertEqual(single["tool_id"], "")
            self.assertEqual(bundle["selected_count"], 0)

    def test_unmatched_question_does_not_guess_a_tool(self):
        out = plan_local_command("explique isso com cuidado")
        self.assertEqual(out["state"], "NO_MATCH")
        self.assertEqual(out["tool_id"], "")


class ExecutionTests(unittest.TestCase):
    def test_single_preview_never_invokes_executor(self):
        spy = Mock()
        original = command.execute_local_tool
        command.execute_local_tool = spy
        try:
            out = orchestrate_local_command("resumo de tarefas", execute=False)
        finally:
            command.execute_local_tool = original
        self.assertEqual(out["state"], "PLANNED")
        self.assertEqual(out["mode"], "SINGLE")
        self.assertFalse(out["executor_invoked"])
        self.assertFalse(out["handler_executed"])
        spy.assert_not_called()

    def test_multi_preview_never_invokes_executor(self):
        spy = Mock()
        original = command.execute_local_tool
        command.execute_local_tool = spy
        try:
            out = orchestrate_local_command("onde paramos e o que falta?", execute=False)
        finally:
            command.execute_local_tool = original
        self.assertEqual(out["state"], "PLANNED_MULTI")
        self.assertEqual(out["mode"], "MULTI_READ")
        self.assertEqual(out["tool_ids"], ["aion.memory.search", "aion.tasks.summary"])
        self.assertFalse(out["executor_invoked"])
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

    def test_safe_single_command_delegates_with_approval_false(self):
        spy = Mock(return_value={
            "state": "SUCCESS",
            "tool_id": "aion.tasks.summary",
            "workspace_id": "administration",
            "kind": "READ",
            "contract_fingerprint": local_contract_fingerprint(),
            "request_id": "single-test",
            "result": {"total": 3, "active": 2, "waiting_approval": 1, "blocked": 0},
            "truth": {"status": "UNKNOWN", "freshness": "UNVERIFIED"},
            "preflight": {"state": "READY_FOR_EXECUTOR", "blockers": []},
            "provenance": {
                "source_module": "atlasquant_aion_local_executor",
                "source_function": "_test",
                "input_scope": "local",
                "local_only": True,
            },
            "security": {
                "network_called": False,
                "connector_called": False,
                "external_side_effects": False,
                "permissions_expanded": False,
                "secrets_included": False,
            },
            "executes_action": False,
            "external_action_executed": False,
            "real_orders_enabled": False,
            "tool_output_is_authority": False,
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
        self.assertEqual(out["mode"], "SINGLE")
        self.assertTrue(out["executor_invoked"])
        self.assertTrue(out["handler_executed"])
        self.assertEqual(out["handlers_executed"], 1)
        kwargs = spy.call_args.kwargs
        self.assertFalse(kwargs["approved"])
        self.assertTrue(kwargs["authenticated_admin"])
        self.assertFalse(out["external_action_executed"])
        self.assertFalse(out["real_orders_enabled"])

    def test_multi_read_executes_sequentially_with_individual_preflights(self):
        def ok(tool_id, **kwargs):
            return {
                "state": "SUCCESS",
                "tool_id": tool_id,
                "workspace_id": "central",
                "kind": "SEARCH" if tool_id == "aion.memory.search" else "READ",
                "contract_fingerprint": local_contract_fingerprint(),
                "request_id": str(kwargs.get("request_id") or ""),
                "result": {"canonical_count": 1} if tool_id == "aion.memory.search" else {
                    "total": 2, "active": 1, "waiting_approval": 0, "blocked": 0
                },
                "truth": {"status": "UNKNOWN", "freshness": "UNVERIFIED"},
                "preflight": {"state": "READY_FOR_EXECUTOR", "blockers": []},
                "provenance": {
                    "source_module": "atlasquant_aion_local_executor",
                    "source_function": "_test",
                    "input_scope": "local",
                    "local_only": True,
                },
                "security": {
                    "network_called": False,
                    "connector_called": False,
                    "external_side_effects": False,
                    "permissions_expanded": False,
                    "secrets_included": False,
                },
                "executes_action": False,
                "external_action_executed": False,
                "real_orders_enabled": False,
                "tool_output_is_authority": False,
            }
        spy = Mock(side_effect=ok)
        original = command.execute_local_tool
        command.execute_local_tool = spy
        try:
            out = orchestrate_local_command(
                "onde paramos e o que falta?",
                execute=True,
                runtime_context={"checkpoint": default_checkpoint()},
                access=ADMIN,
                authenticated_admin=True,
            )
        finally:
            command.execute_local_tool = original
        self.assertEqual(out["state"], "SUCCESS")
        self.assertEqual(out["mode"], "MULTI_READ")
        self.assertEqual(out["handlers_executed"], 2)
        self.assertEqual(spy.call_count, 2)
        self.assertEqual(
            [call.args[0] for call in spy.call_args_list],
            ["aion.memory.search", "aion.tasks.summary"],
        )
        self.assertTrue(all(call.kwargs["approved"] is False for call in spy.call_args_list))
        self.assertFalse(out["stopped_early"])
        self.assertEqual(out["traceability"]["record_count"], 2)
        self.assertEqual(len(out["traceability"]["execution_refs"]), 2)
        self.assertFalse(out["traceability"]["tool_output_is_authority"])

    def test_multi_read_blocks_mixed_contract_fingerprints(self):
        calls = {"n": 0}

        def mixed(tool_id, **kwargs):
            calls["n"] += 1
            return {
                "state": "SUCCESS",
                "tool_id": tool_id,
                "workspace_id": "central",
                "kind": "SEARCH" if tool_id == "aion.memory.search" else "READ",
                "contract_fingerprint": "AION-LCL-" + (("A" if calls["n"] == 1 else "B") * 16),
                "request_id": str(kwargs.get("request_id") or ""),
                "result": {"truth_state": "UNKNOWN"},
                "truth": {"status": "UNKNOWN", "freshness": "UNVERIFIED"},
                "preflight": {"state": "READY_FOR_EXECUTOR", "blockers": []},
                "provenance": {
                    "source_module": "atlasquant_aion_local_executor",
                    "source_function": "_test",
                    "input_scope": "local",
                    "local_only": True,
                },
                "security": {
                    "network_called": False,
                    "connector_called": False,
                    "external_side_effects": False,
                    "permissions_expanded": False,
                    "secrets_included": False,
                },
                "executes_action": False,
                "external_action_executed": False,
                "real_orders_enabled": False,
                "tool_output_is_authority": False,
            }

        spy = Mock(side_effect=mixed)
        original = command.execute_local_tool
        command.execute_local_tool = spy
        try:
            out = orchestrate_local_command(
                "onde paramos e o que falta?",
                execute=True,
                runtime_context={"checkpoint": default_checkpoint()},
                access=ADMIN,
                authenticated_admin=True,
            )
        finally:
            command.execute_local_tool = original
        self.assertEqual(out["state"], "SECURITY_BLOCK")
        self.assertEqual(out["traceability"]["state"], "SECURITY_BLOCK")
        self.assertFalse(out["traceability"]["contract_consistent"])
        self.assertFalse(out["executive_response"]["safe_to_display"])

    def test_multi_read_stops_on_first_blocked_preflight(self):
        blocked = {
            "state": "BLOCKED",
            "tool_id": "aion.tasks.summary",
            "workspace_id": "administration",
            "kind": "READ",
            "contract_fingerprint": local_contract_fingerprint(),
            "request_id": "blocked-test",
            "result": None,
            "truth": {"status": "UNKNOWN", "freshness": "UNVERIFIED"},
            "preflight": {"state": "BLOCK", "blockers": ["GUARDIAN_DENIED"]},
            "provenance": {
                "source_module": "atlasquant_aion_local_executor",
                "source_function": "",
                "input_scope": "local",
                "local_only": True,
            },
            "security": {
                "network_called": False,
                "connector_called": False,
                "external_side_effects": False,
                "permissions_expanded": False,
                "secrets_included": False,
            },
            "executes_action": False,
            "external_action_executed": False,
            "real_orders_enabled": False,
            "tool_output_is_authority": False,
        }
        spy = Mock(return_value=blocked)
        original = command.execute_local_tool
        command.execute_local_tool = spy
        try:
            out = orchestrate_local_command(
                "resumo de tarefas e aprovações pendentes",
                execute=True,
                runtime_context={"checkpoint": default_checkpoint()},
                access=ADMIN,
                authenticated_admin=True,
            )
        finally:
            command.execute_local_tool = original
        self.assertEqual(out["state"], "BLOCKED")
        self.assertEqual(out["mode"], "MULTI_READ")
        self.assertEqual(spy.call_count, 1)
        self.assertEqual(out["handlers_executed"], 0)
        self.assertTrue(out["stopped_early"])

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


    def test_string_false_execute_does_not_invoke_executor(self):
        spy = Mock()
        original = command.execute_local_tool
        command.execute_local_tool = spy
        try:
            out = orchestrate_local_command("resumo de tarefas", execute="false")
        finally:
            command.execute_local_tool = original
        self.assertEqual(out["state"], "PLANNED")
        self.assertFalse(out["execution_requested"])
        self.assertFalse(out["executor_invoked"])
        spy.assert_not_called()

    def test_string_false_authenticated_admin_is_not_forwarded_as_true(self):
        spy = Mock(return_value={
            "state": "BLOCKED",
            "tool_id": "aion.tasks.summary",
            "workspace_id": "administration",
            "kind": "READ",
            "contract_fingerprint": local_contract_fingerprint(),
            "request_id": "exact-bool-admin",
            "result": None,
            "truth": {"status": "UNKNOWN", "freshness": "UNVERIFIED"},
            "preflight": {"state": "BLOCK", "blockers": ["ADMIN_REQUIRED"]},
            "provenance": {
                "source_module": "atlasquant_aion_local_executor",
                "source_function": "_test",
                "input_scope": "local",
                "local_only": True,
            },
            "security": {
                "network_called": False,
                "connector_called": False,
                "external_side_effects": False,
                "permissions_expanded": False,
                "secrets_included": False,
            },
            "executes_action": False,
            "external_action_executed": False,
            "real_orders_enabled": False,
            "tool_output_is_authority": False,
        })
        original = command.execute_local_tool
        command.execute_local_tool = spy
        try:
            out = orchestrate_local_command(
                "resumo de tarefas",
                execute=True,
                runtime_context={"checkpoint": default_checkpoint()},
                access=ADMIN,
                authenticated_admin="false",
            )
        finally:
            command.execute_local_tool = original
        self.assertTrue(out["executor_invoked"])
        self.assertFalse(spy.call_args.kwargs["authenticated_admin"])



if __name__ == "__main__":
    unittest.main()
