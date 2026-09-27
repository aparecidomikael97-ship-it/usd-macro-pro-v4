import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from atlasquant_aion_local_executor import (
    ALLOWED_KINDS,
    FORBIDDEN_KINDS,
    execute_local_tool,
    local_allowlist,
)
from atlasquant_aion_memory_layers import SCHEMA as MEMORY_SCHEMA
from atlasquant_aion_memory_layers import VERSION, default_memory_layers, remember

ROOT = Path(__file__).resolve().parent
NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)


def _memory(content, *, truth="CONFIRMED", valid_until=""):
    return remember(
        default_memory_layers(),
        layer="knowledge",
        content=content,
        origin="local-test",
        category="note",
        truth_state=truth,
        valid_until=valid_until,
        persona="trader",
    )


class AllowlistTests(unittest.TestCase):
    def test_allowlist_is_static_and_only_read_search_draft(self):
        catalog = local_allowlist()
        ids = [item["tool_id"] for item in catalog]
        self.assertEqual(ids, [
            "aion.memory.search",
            "aion.checkpoint.inspect",
            "aion.status.board",
            "aion.tasks.summary",
            "aion.missions.summary",
            "aion.durable_tasks.summary",
            "aion.approval.inbox",
            "aion.observability.summary",
            "aion.specialist.snapshot",
            "aion.secretary.brief",
        ])
        self.assertEqual({item["kind"] for item in catalog}, set(ALLOWED_KINDS))
        self.assertFalse({item["kind"] for item in catalog} & FORBIDDEN_KINDS)
        self.assertFalse(any("handler" in item for item in catalog))

    def test_source_has_no_process_eval_network_or_dynamic_import(self):
        text = (ROOT / "atlasquant_aion_local_executor.py").read_text(encoding="utf-8")
        for banned in (
            "import subprocess", "from subprocess", "eval(", "exec(", "__import__",
            "importlib", "import socket", "urllib", "import requests", "os.system", "Popen(",
        ):
            self.assertNotIn(banned, text)

    def test_unknown_and_forbidden_tools_fail_closed(self):
        for tool_id in (
            "os.system",
            "subprocess.run",
            "aion.checkpoint.prepare_save",
            "deploy_production",
            "real_trade",
            "merge_main",
            "",
        ):
            out = execute_local_tool(tool_id, {"command": "echo secret"})
            self.assertEqual(out["state"], "BLOCK", tool_id)
            self.assertEqual(out["blockers"], ["TOOL_NOT_ALLOWLISTED"])
            self.assertIsNone(out["result"])
            self.assertFalse(out["executes_external_action"])
            self.assertFalse(out["network_called"])
            self.assertFalse(out["subprocess_called"])
            self.assertFalse(out["real_trading_enabled"])
            self.assertFalse(out["writes_checkpoint"])
            self.assertFalse(out["publishes"])
            self.assertFalse(out["tool_output_is_authority"])


class LocalToolTests(unittest.TestCase):
    def test_memory_search_preserves_truth_and_downgrades_expired(self):
        fresh = _memory("Radar local sem ordem.")
        out = execute_local_tool("aion.memory.search", {
            "memory": fresh,
            "persona": "trader",
            "query": "aion",
            "command": "rm -rf /",
        })
        self.assertEqual(out["state"], "READY")
        self.assertEqual(out["kind"], "SEARCH")
        self.assertGreaterEqual(out["result"]["canonical_count"], 1)
        layered = out["result"]["layered"]
        self.assertEqual(layered[0]["truth_state"], "CONFIRMED")
        self.assertNotIn("rm -rf", str(out["result"]))

        expired = _memory(
            "Leitura vencida.",
            valid_until=(NOW - timedelta(days=1)).isoformat(),
        )
        hidden = execute_local_tool("aion.memory.search", {
            "memory": expired,
            "persona": "trader",
            "now": NOW,
        })
        self.assertEqual(hidden["result"]["layered"], [])
        stale = execute_local_tool("aion.memory.search", {
            "memory": expired,
            "persona": "trader",
            "now": NOW,
            "include_expired": True,
        })
        self.assertEqual(stale["result"]["layered"][0]["truth_state"], "UNKNOWN")
        self.assertEqual(stale["result"]["layered"][0]["status"], "EXPIRED")

    def test_memory_content_secrets_are_redacted_without_changing_truth(self):
        memory = _memory("password=hunter2 permanece confidencial")
        out = execute_local_tool("aion.memory.search", {"memory": memory, "persona": "trader"})
        content = out["result"]["layered"][0]["content"]
        self.assertNotIn("hunter2", content)
        self.assertIn("[REDACTED]", content)
        self.assertEqual(out["result"]["layered"][0]["truth_state"], "CONFIRMED")

    def test_checkpoint_inspect_does_not_echo_or_save_secrets(self):
        secret = "sk-" + ("a" * 24)
        out = execute_local_tool("aion.checkpoint.inspect", {
            "checkpoint": {
                "schema": MEMORY_SCHEMA,
                "version": VERSION,
                "api_key": secret,
                "client_secret": "super-secret-value",
            },
        })
        self.assertEqual(out["state"], "READY")
        self.assertEqual(out["kind"], "READ")
        rendered = str(out["result"])
        self.assertNotIn(secret, rendered)
        self.assertNotIn("super-secret-value", rendered)
        self.assertFalse(out["result"]["saved"])
        self.assertFalse(out["result"]["write_safe"])
        self.assertFalse(out["writes_checkpoint"])

    def test_status_board_stays_unknown_without_evidence(self):
        out = execute_local_tool("aion.status.board", {})
        self.assertEqual(out["kind"], "READ")
        states = {item["id"]: item["state"] for item in out["result"]["items"]}
        self.assertEqual(states["app_runtime"], "UNKNOWN")
        self.assertTrue(all(item["executes_action"] is False for item in out["result"]["items"]))

    def test_tasks_missions_durable_approval_and_observability_are_read_only(self):
        checkpoint = {
            "operating": {"tasks": [{
                "title": "Revisar fila",
                "domain": "secretary",
                "action": "read",
                "status": "WAITING_APPROVAL",
            }]},
            "continuity": {"missions": [{
                "title": "Mapear evidência",
                "domain": "research",
                "objective": "Ler fontes.",
                "status": "PLANNED",
            }]},
            "durable_tasks": {"records": []},
            "events": [{
                "event_type": "local.check",
                "message": "token=abc123secrettokenvalue",
                "severity": "WARNING",
                "truth_state": "CONFIRMED",
            }],
        }
        tasks = execute_local_tool("aion.tasks.summary", {"checkpoint": checkpoint})
        missions = execute_local_tool("aion.missions.summary", {"checkpoint": checkpoint})
        durable = execute_local_tool("aion.durable_tasks.summary", {"checkpoint": checkpoint})
        inbox = execute_local_tool("aion.approval.inbox", {"checkpoint": checkpoint})
        observed = execute_local_tool("aion.observability.summary", {"checkpoint": checkpoint})
        self.assertEqual(tasks["result"]["waiting_approval"], 1)
        self.assertFalse(tasks["result"]["executes_action"])
        self.assertEqual(missions["result"]["active"], 1)
        self.assertFalse(missions["result"]["executes_action"])
        self.assertEqual(durable["result"]["tasks"], 0)
        self.assertFalse(durable["result"]["automatic_resume_executes"])
        self.assertFalse(inbox["result"]["automatic_approval"])
        self.assertGreaterEqual(inbox["result"]["total"], 1)
        self.assertEqual(observed["result"]["by_truth"]["CONFIRMED"], 1)
        self.assertNotIn("abc123secrettokenvalue", str(observed["result"]))
        self.assertFalse(observed["result"]["remote_logging"])

    def test_specialist_snapshot_does_not_invent_evidence(self):
        out = execute_local_tool("aion.specialist.snapshot", {"specialist": "market"})
        self.assertEqual(out["kind"], "READ")
        self.assertFalse(out["result"]["network_called"])
        self.assertFalse(out["result"].get("provider_called", False))
        self.assertNotEqual(out["result"].get("truth_state"), "CONFIRMED")

    def test_secretary_brief_is_a_draft(self):
        out = execute_local_tool("aion.secretary.brief", {
            "market_context": {"summary": "sem confirmação"},
        })
        self.assertEqual(out["kind"], "DRAFT")
        self.assertEqual(out["result"]["market"]["truth_state"], "UNKNOWN")
        self.assertTrue(out["result"]["draft_only"])
        self.assertFalse(out["result"]["published"])
        self.assertFalse(out["publishes"])
        self.assertFalse(out["result"]["real_orders_enabled"])

    def test_large_results_are_bounded(self):
        memory = _memory("x" * 3000)
        out = execute_local_tool("aion.memory.search", {"memory": memory, "persona": "trader"})
        self.assertTrue(out["truncated"])
        self.assertLessEqual(len(out["result"]["layered"][0]["content"]), 500)
        self.assertEqual(out["result"]["layered"][0]["truth_state"], "CONFIRMED")


if __name__ == "__main__":
    unittest.main()
