import ast
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import atlasquant_aion_contract_auditor as auditor
import atlasquant_aion_local_executor as executor
from atlasquant_aion_contract_auditor import (
    LOCAL_CONTRACT,
    WRITE_CONTRACT,
    audit_allowlist_rows,
    audit_aion_local_contracts,
    audit_command_rules,
    audit_handler_map,
    audit_tool_rows,
    format_audit_report,
    local_security_violations,
    main,
)
from atlasquant_aion_tool_hub import DEFAULT_TOOLS, default_tool_hub


ROOT = Path(__file__).resolve().parent


def _tools():
    return [dict(item) for item in DEFAULT_TOOLS]


class LiveAuditTests(unittest.TestCase):
    def test_live_contracts_pass_without_authority(self):
        report = audit_aion_local_contracts()
        self.assertEqual(report["schema"], auditor.SCHEMA)
        self.assertEqual(report["state"], "PASS", format_audit_report(report))
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["findings"], [])
        self.assertGreaterEqual(report["checks_total"], 17)
        self.assertIn("atlasquant_aion_local_traceability.py", report["workflow_summary"]["critical_modules"])
        self.assertIn("test_atlasquant_aion_local_traceability.py", report["workflow_summary"]["critical_tests"])
        self.assertEqual(report["passed"], report["checks_total"])
        self.assertEqual(report["registry_summary"]["tools"], 12)
        self.assertEqual(report["registry_summary"]["local_tools"], 11)
        self.assertEqual(report["handler_summary"]["handlers"], 11)
        self.assertFalse(report["handler_summary"]["write_handler"])
        self.assertFalse(report["executes_action"])
        self.assertFalse(report["external_action_executed"])
        self.assertFalse(report["real_orders_enabled"])
        self.assertFalse(report["tool_output_is_authority"])
        self.assertEqual(report["orchestration_summary"]["max_bundle_tools"], 3)

    def test_cli_prints_pass_and_check_count(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main([])
        text = buffer.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("AION Local Contract Audit", text)
        self.assertIn("\nPASS\n", text)
        self.assertIn("0 failures", text)
        self.assertNotIn(_sentinel(), text)

    def test_auditor_source_has_no_network_or_process_calls(self):
        tree = ast.parse((ROOT / "atlasquant_aion_contract_auditor.py").read_text(encoding="utf-8"))
        banned = {"eval", "exec", "__import__", "getattr", "system", "Popen"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
                self.assertNotIn(name, banned)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(alias.name.split(".", 1)[0], {"socket", "requests", "urllib", "subprocess"})


class MutationTests(unittest.TestCase):
    def test_write_added_to_allowlist_fails(self):
        allow = list(executor.local_allowlist()) + [{
            "tool_id": WRITE_CONTRACT[0], "kind": "WRITE", "label": "save",
        }]
        findings = audit_allowlist_rows(allow, _tools())
        self.assertTrue(any(row["invariant_id"] == "allowlist.write" for row in findings))

    def test_removed_handler_fails(self):
        handlers = dict(executor._HANDLERS)
        handlers.pop("aion.status.read")
        findings = audit_handler_map(handlers, executor.local_allowlist(), _tools())
        self.assertTrue(findings)
        self.assertTrue(any(row["invariant_id"] == "handlers.missing" for row in findings))

    def test_changed_kind_fails(self):
        tools = _tools()
        for item in tools:
            if item["tool_id"] == "aion.status.read":
                item["kind"] = "PUBLISH"
        findings = audit_tool_rows(tools)
        self.assertTrue(any(row["invariant_id"] == "registry.local_kind" for row in findings))

    def test_unexpected_connector_fails(self):
        tools = _tools()
        for item in tools:
            if item["tool_id"] == "aion.memory.search":
                item["connector_id"] = "market-feed"
        findings = audit_tool_rows(tools)
        self.assertTrue(any(row["invariant_id"] == "registry.local_connector" for row in findings))

    def test_external_side_effect_on_local_tool_fails(self):
        tools = _tools()
        for item in tools:
            if item["tool_id"] == "aion.events.summary":
                item["external_side_effects"] = True
        findings = audit_tool_rows(tools)
        self.assertTrue(any(row["invariant_id"] == "registry.local_side_effect" for row in findings))

    def test_duplicate_tool_id_fails(self):
        tools = _tools()
        tools.append(dict(tools[0]))
        findings = audit_tool_rows(tools)
        self.assertTrue(any(row["invariant_id"] == "registry.duplicate_id" for row in findings))

    def test_rule_pointing_at_missing_tool_fails(self):
        rules = tuple(auditor.command._RULES) + (("aion.missing.tool", ("faz algo",)),)
        findings = audit_command_rules(
            rules, _tools(), executor.local_allowlist(), executor._HANDLERS,
        )
        self.assertTrue(any(row["invariant_id"] == "rules.unbound" for row in findings))

    def test_envelope_network_called_fails(self):
        violations = local_security_violations({
            "security": {
                "sanitized": True, "network_called": True, "connector_called": False,
                "external_side_effects": False, "permissions_expanded": False,
                "secrets_included": False,
            },
            "executes_action": False, "external_action_executed": False,
            "real_orders_enabled": False, "tool_output_is_authority": False,
            "provenance": {"local_only": True},
        })
        self.assertIn("network_called=True", violations)

    def test_tool_output_authority_fails(self):
        violations = local_security_violations({
            "security": {
                "sanitized": True, "network_called": False, "connector_called": False,
                "external_side_effects": False, "permissions_expanded": False,
                "secrets_included": False,
            },
            "executes_action": False, "external_action_executed": False,
            "real_orders_enabled": False, "tool_output_is_authority": True,
            "provenance": {"local_only": True},
        })
        self.assertTrue(any(item.startswith("tool_output_is_authority=") for item in violations))

    def test_handler_for_forbidden_kind_fails(self):
        tools = _tools()
        for item in tools:
            if item["tool_id"] == "aion.tasks.summary":
                item["kind"] = "FINANCIAL"
        findings = audit_handler_map(dict(executor._HANDLERS), executor.local_allowlist(), tools)
        self.assertTrue(any(row["invariant_id"] == "handlers.forbidden_kind" for row in findings))

    def test_traceability_is_part_of_the_static_contract(self):
        self.assertIn("atlasquant_aion_local_traceability.py", auditor.STATIC_MODULES)
        self.assertEqual(set(auditor.SOURCE_CATALOG), {row[0] for row in LOCAL_CONTRACT})

    def test_live_hub_matches_the_closed_contract(self):
        hub = {item["tool_id"]: item for item in default_tool_hub()["tools"]}
        self.assertEqual(set(hub), {row[0] for row in LOCAL_CONTRACT} | {WRITE_CONTRACT[0]})
        self.assertEqual(hub[WRITE_CONTRACT[0]]["kind"], "WRITE")
        self.assertNotIn(WRITE_CONTRACT[0], executor._HANDLERS)


def _sentinel() -> str:
    return "contract-auditor-sentinel"


if __name__ == "__main__":
    unittest.main()
