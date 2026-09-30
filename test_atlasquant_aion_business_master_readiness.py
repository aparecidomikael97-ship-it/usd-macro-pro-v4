import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_master_readiness import (
    DEMO_GATES,
    LIVE_GATES,
    PILOT_GATES,
    default_demo_evidence,
    master_readiness_snapshot,
    pilot_review_packet,
    status_rows,
)


class BusinessMasterReadinessTests(unittest.TestCase):
    def test_default_demo_is_complete_but_pilot_and_live_are_blocked(self):
        snapshot = master_readiness_snapshot(default_demo_evidence())
        self.assertEqual(snapshot["demo"]["state"], "DEMO_READY")
        self.assertTrue(snapshot["demo"]["complete"])
        self.assertEqual(snapshot["demo"]["passed_count"], len(DEMO_GATES))
        self.assertEqual(snapshot["pilot"]["state"], "PILOT_BLOCKED")
        self.assertFalse(snapshot["pilot"]["complete"])
        self.assertEqual(snapshot["live"]["state"], "RUNTIME_OFF")
        self.assertFalse(snapshot["live"]["complete"])
        self.assertFalse(snapshot["pilot_authorized"])
        self.assertFalse(snapshot["live_runtime_authorized"])
        self.assertFalse(snapshot["runtime_activated"])
        self.assertFalse(snapshot["external_actions_enabled"])
        self.assertFalse(snapshot["payment_enabled"])
        self.assertFalse(snapshot["publication_enabled"])
        self.assertFalse(snapshot["executes_action"])

    def test_string_true_does_not_pass_gate(self):
        evidence = default_demo_evidence()
        evidence["demo_ui_ready"] = "true"
        snapshot = master_readiness_snapshot(evidence)
        self.assertFalse(snapshot["demo"]["complete"])
        self.assertIn("demo_ui_ready", snapshot["demo"]["missing"])

    def test_pilot_can_be_reviewable_but_never_authorized_automatically(self):
        evidence = default_demo_evidence()
        for gate in PILOT_GATES:
            evidence[gate] = True
        snapshot = master_readiness_snapshot(evidence)
        self.assertEqual(snapshot["pilot"]["state"], "PILOT_REVIEW_REQUIRED")
        self.assertTrue(snapshot["pilot"]["complete"])
        self.assertFalse(snapshot["pilot_authorized"])
        packet = pilot_review_packet(
            snapshot,
            requested_by="Mikael",
            pilot_scope="Piloto fechado com uma empresa fictícia/controlada.",
        )
        self.assertEqual(packet["state"], "PILOT_REVIEW_REQUIRED")
        self.assertTrue(packet["eligible_for_human_review"])
        self.assertFalse(packet["pilot_authorized"])
        self.assertFalse(packet["runtime_activation_approved"])
        self.assertFalse(packet["external_contact_authorized"])
        self.assertFalse(packet["contract_signature_authorized"])
        self.assertFalse(packet["payment_authorized"])
        self.assertFalse(packet["publication_authorized"])
        self.assertFalse(packet["executes_action"])

    def test_live_gates_do_not_activate_runtime(self):
        evidence = default_demo_evidence()
        for gate in LIVE_GATES:
            evidence[gate] = True
        snapshot = master_readiness_snapshot(evidence)
        self.assertEqual(snapshot["live"]["state"], "LIVE_REVIEW_REQUIRED")
        self.assertTrue(snapshot["live"]["complete"])
        self.assertFalse(snapshot["live_runtime_authorized"])
        self.assertFalse(snapshot["runtime_activated"])

    def test_status_rows_have_demo_pilot_live(self):
        rows = status_rows(master_readiness_snapshot(default_demo_evidence()))
        self.assertEqual([row["layer"] for row in rows], ["DEMO", "PILOT", "LIVE"])
        self.assertEqual(rows[0]["progress_pct"], 100.0)
        self.assertIn("Runtime permanece OFF", rows[2]["next_step"])

    def test_module_has_no_external_io_provider_or_ui_imports(self):
        source = Path("atlasquant_aion_business_master_readiness.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for banned in ("requests", "urllib", "httpx", "socket", "subprocess", "openai", "streamlit"):
            self.assertNotIn(banned, imported)


if __name__ == "__main__":
    unittest.main()
