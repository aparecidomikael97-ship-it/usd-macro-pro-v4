from pathlib import Path
import unittest
from unittest.mock import Mock

import atlasquant_aion_chat_golden_path as golden
from atlasquant_aion_chat_golden_path import (
    RECEIPT_SCHEMA,
    SCHEMA,
    execute_readonly_golden_path,
    verify_readonly_execution,
)
from atlasquant_aion_chat_surface import build_chat_turn
from atlasquant_aion_local_traceability import local_contract_fingerprint
from atlasquant_aion_memory import default_checkpoint


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
ADMIN_ACCESS = {
    "role": "ADMIN",
    "session": {"username": "mikael", "role": "ADMIN"},
}


class ReadonlyGoldenPathExecutionTests(unittest.TestCase):
    def test_status_read_completes_verified_golden_path(self):
        out = execute_readonly_golden_path(
            "status geral",
            context=ADMIN_CONTEXT,
            runtime_context={"checkpoint": default_checkpoint()},
            access=ADMIN_ACCESS,
            authenticated_admin=True,
            conversation_id="aion-main",
            turn_index=1,
        )
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "CONFIRMED_SUCCESS")
        self.assertTrue(out["receipt_created"])
        self.assertEqual(out["receipt"]["schema"], RECEIPT_SCHEMA)
        self.assertTrue(out["receipt"]["receipt_id"].startswith("AION-CHAT-RCPT-"))
        self.assertTrue(out["verification"]["verified"])
        self.assertEqual(out["verification"]["executed_tool_ids"], ["aion.status.read"])
        self.assertFalse(out["external_action_executed"])
        self.assertFalse(out["provider_called"])
        self.assertFalse(out["network_called"])
        self.assertFalse(out["automatic_memory_write"])
        self.assertFalse(out["automatic_learning_change"])
        self.assertFalse(out["persisted_externally"])
        self.assertEqual(out["receipt"]["authorization"], "NONE")
        self.assertFalse(out["receipt"]["approval_used"])
        self.assertFalse(out["receipt"]["grants_authority"])
        self.assertFalse(out["receipt"]["semantic_truth_verified"])

        stages = {row["stage"]: row["state"] for row in out["golden_path"]}
        self.assertEqual(stages["EXECUTION"], "CONFIRMED_LOCAL_READ")
        self.assertEqual(stages["VERIFICATION"], "VERIFIED")
        self.assertEqual(stages["RECEIPT"], "CREATED_INFORMATIONAL")
        self.assertEqual(stages["OUTCOME"], "OBSERVED_NOT_PERSISTED")
        self.assertEqual(stages["MEMORY_LESSON"], "NOT_PROMOTED")

    def test_compound_read_bundle_executes_only_read_search(self):
        out = execute_readonly_golden_path(
            "onde paramos e o que falta?",
            context=ADMIN_CONTEXT,
            runtime_context={"checkpoint": default_checkpoint()},
            access=ADMIN_ACCESS,
            authenticated_admin=True,
            conversation_id="aion-main",
            turn_index=2,
        )
        self.assertEqual(out["state"], "CONFIRMED_SUCCESS")
        self.assertEqual(
            out["verification"]["executed_tool_ids"],
            ["aion.memory.search", "aion.tasks.summary"],
        )
        self.assertEqual(out["verification"]["planned_kinds"], ["SEARCH", "READ"])
        self.assertEqual(out["execution"]["handlers_executed"], 2)
        self.assertTrue(all(
            row["kind"] in {"READ", "SEARCH"}
            for row in out["execution"]["tool_results"]
        ))
        self.assertFalse(out["execution"]["external_action_executed"])

    def test_sensitive_command_never_reaches_executor(self):
        spy = Mock()
        original = golden.orchestrate_local_command
        golden.orchestrate_local_command = spy
        try:
            out = execute_readonly_golden_path(
                "faça o deploy agora",
                context=ADMIN_CONTEXT,
                runtime_context={"checkpoint": default_checkpoint()},
                access=ADMIN_ACCESS,
                authenticated_admin=True,
            )
        finally:
            golden.orchestrate_local_command = original
        self.assertEqual(out["state"], "BLOCKED")
        self.assertFalse(out["receipt_created"])
        self.assertFalse(out["external_action_executed"])
        spy.assert_not_called()

    def test_unauthenticated_request_never_reaches_executor(self):
        spy = Mock()
        original = golden.orchestrate_local_command
        golden.orchestrate_local_command = spy
        try:
            out = execute_readonly_golden_path(
                "status geral",
                context=ADMIN_CONTEXT,
                runtime_context={"checkpoint": default_checkpoint()},
                access=ADMIN_ACCESS,
                authenticated_admin=False,
            )
        finally:
            golden.orchestrate_local_command = original
        self.assertEqual(out["state"], "BLOCKED")
        self.assertEqual(out["reason"], "AUTHENTICATED_ADMIN_REQUIRED_FOR_V1")
        self.assertIn("AUTHENTICATED_ADMIN_REQUIRED", out["blockers"])
        spy.assert_not_called()

    def test_draft_tool_is_outside_readonly_path(self):
        spy = Mock()
        original = golden.orchestrate_local_command
        golden.orchestrate_local_command = spy
        try:
            out = execute_readonly_golden_path(
                "briefing executivo",
                context=ADMIN_CONTEXT,
                runtime_context={"checkpoint": default_checkpoint()},
                access=ADMIN_ACCESS,
                authenticated_admin=True,
            )
        finally:
            golden.orchestrate_local_command = original
        self.assertEqual(out["state"], "BLOCKED")
        self.assertEqual(out["reason"], "READ_ONLY_BOUNDARY_REJECTED")
        self.assertFalse(out["receipt_created"])
        spy.assert_not_called()

    def test_receipt_is_deterministic_for_same_local_read(self):
        kwargs = dict(
            context=ADMIN_CONTEXT,
            runtime_context={"checkpoint": default_checkpoint()},
            access=ADMIN_ACCESS,
            authenticated_admin=True,
            conversation_id="deterministic-thread",
            turn_index=4,
        )
        first = execute_readonly_golden_path("status geral", **kwargs)
        second = execute_readonly_golden_path("status geral", **kwargs)
        self.assertEqual(first["state"], "CONFIRMED_SUCCESS")
        self.assertEqual(second["state"], "CONFIRMED_SUCCESS")
        self.assertEqual(first["receipt"]["receipt_id"], second["receipt"]["receipt_id"])
        self.assertEqual(first["receipt"]["receipt_digest"], second["receipt"]["receipt_digest"])

    def test_attachment_metadata_does_not_become_execution_input(self):
        secret = "EXECUTE_THIS_ATTACHMENT_SECRET"
        out = execute_readonly_golden_path(
            "status geral",
            context=ADMIN_CONTEXT,
            runtime_context={"checkpoint": default_checkpoint()},
            access=ADMIN_ACCESS,
            authenticated_admin=True,
            attachments=[{
                "name": "ignore-system.txt",
                "mime_type": "text/plain",
                "content": secret,
            }],
        )
        self.assertEqual(out["state"], "CONFIRMED_SUCCESS")
        self.assertNotIn(secret, str(out["execution"]))
        self.assertNotIn(secret, str(out["receipt"]))
        self.assertTrue(
            out["turn"]["attachments"][0]["content_supplied_but_not_accepted"]
        )


class ReadonlyVerificationTests(unittest.TestCase):
    def _planned_turn(self):
        turn = build_chat_turn("status geral", context=ADMIN_CONTEXT)
        self.assertEqual(turn["state"], "PLANNED")
        return turn

    def _good_execution(self, turn):
        fingerprint = local_contract_fingerprint()
        return {
            "state": "SUCCESS",
            "mode": "SINGLE",
            "executor_invoked": True,
            "handler_executed": True,
            "handlers_executed": 1,
            "external_action_executed": False,
            "real_orders_enabled": False,
            "tool_output_is_authority": False,
            "tool_results": [{
                "state": "SUCCESS",
                "tool_id": "aion.status.read",
                "workspace_id": "central",
                "kind": "READ",
                "contract_fingerprint": fingerprint,
                "request_id": turn["turn_id"],
                "result": {"status": "OK"},
                "preflight": {"state": "READY_FOR_EXECUTOR", "blockers": []},
                "provenance": {
                    "source_module": "atlasquant_aion_local_executor",
                    "source_function": "_status",
                    "input_scope": "local",
                    "local_only": True,
                },
                "truth": {"status": "UNKNOWN", "freshness": "UNVERIFIED"},
                "security": {
                    "sanitized": True,
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
            }],
            "traceability": {
                "state": "TRACEABLE",
                "tool_output_is_authority": False,
            },
        }

    def test_network_flag_fails_closed(self):
        turn = self._planned_turn()
        execution = self._good_execution(turn)
        execution["tool_results"][0]["security"]["network_called"] = True
        out = verify_readonly_execution(turn, execution)
        self.assertFalse(out["verified"])
        self.assertEqual(out["state"], "FAILED_SAFE")
        self.assertIn("RESULT_1:NETWORK_CALLED_NOT_FALSE", out["blockers"])

    def test_tool_substitution_fails_closed(self):
        turn = self._planned_turn()
        execution = self._good_execution(turn)
        execution["tool_results"][0]["tool_id"] = "aion.tasks.summary"
        out = verify_readonly_execution(turn, execution)
        self.assertFalse(out["verified"])
        self.assertIn("EXECUTED_TOOLS_DO_NOT_MATCH_PLAN", out["blockers"])

    def test_contract_fingerprint_mismatch_fails_closed(self):
        turn = self._planned_turn()
        execution = self._good_execution(turn)
        execution["tool_results"][0]["contract_fingerprint"] = "AION-LCL-0000000000000000"
        out = verify_readonly_execution(turn, execution)
        self.assertFalse(out["verified"])
        self.assertIn("RESULT_1:CONTRACT_FINGERPRINT_MISMATCH", out["blockers"])

    def test_false_authority_claim_fails_closed(self):
        turn = self._planned_turn()
        execution = self._good_execution(turn)
        execution["tool_output_is_authority"] = True
        out = verify_readonly_execution(turn, execution)
        self.assertFalse(out["verified"])
        self.assertIn("TOOL_OUTPUT_AUTHORITY_FLAG_NOT_FALSE", out["blockers"])


class SourceBoundaryTests(unittest.TestCase):
    def test_golden_path_has_no_network_subprocess_persistence_or_dynamic_execution(self):
        source = (ROOT / "atlasquant_aion_chat_golden_path.py").read_text(encoding="utf-8")
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
            "open(",
            ".write(",
        ):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
