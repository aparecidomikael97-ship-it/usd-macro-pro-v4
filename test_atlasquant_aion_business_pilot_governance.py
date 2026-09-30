import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_pilot_governance import (
    MANDATORY_GATES,
    STOP_REASONS,
    build_pilot_charter,
    define_stop_conditions,
    define_success_criteria,
    pilot_gate_review,
    pilot_posture,
    pilot_review_packet,
)


class BusinessPilotGovernanceTests(unittest.TestCase):
    def _charter(self):
        return build_pilot_charter(
            client_reference="client-demo-001",
            segment="Clínica",
            package_label="Atendimento & Conversão",
            workflow_name="Atendimento inicial + follow-up controlado",
            channels=["WhatsApp Business"],
            duration_days=14,
            human_operators=["Mikael"],
            support_owner="Mikael",
            daily_external_action_cap=0,
            allow_external_messages=False,
            allow_publication=False,
            allow_payments=False,
        )

    def _success(self):
        return define_success_criteria(
            metric_names=["tempo_resposta", "leads_qualificados", "proximos_passos"],
            minimum_sample_size=30,
            review_cadence_days=7,
        )

    def _stop(self):
        return define_stop_conditions(
            reasons=list(STOP_REASONS),
            immediate_stop_on_unexpected_external_action=True,
        )

    def _gates(self):
        return {name: True for name in MANDATORY_GATES}

    def test_charter_is_one_client_one_workflow_bounded_and_runtime_off(self):
        row = self._charter()
        self.assertEqual(row["state"], "DRAFT_CHARTER")
        self.assertEqual(row["charter"]["client_count"], 1)
        self.assertEqual(row["charter"]["workflow_count"], 1)
        self.assertEqual(row["charter"]["duration_days"], 14)
        self.assertEqual(row["charter"]["daily_external_action_cap"], 0)
        self.assertFalse(row["charter"]["allow_external_messages"])
        self.assertFalse(row["charter"]["allow_publication"])
        self.assertFalse(row["charter"]["allow_payments"])
        self.assertEqual(row["charter"]["runtime_state"], "OFF")
        self.assertFalse(row["pilot_authorized"])
        self.assertFalse(row["runtime_activated"])
        self.assertFalse(row["executes_action"])

    def test_charter_blocks_external_capability_in_v1(self):
        row = build_pilot_charter(
            client_reference="client-demo-001",
            segment="Clínica",
            package_label="Atendimento & Conversão",
            workflow_name="Follow-up",
            channels=["WhatsApp Business"],
            duration_days=14,
            human_operators=["Mikael"],
            support_owner="Mikael",
            daily_external_action_cap=1,
            allow_external_messages=True,
            allow_publication=False,
            allow_payments=False,
        )
        self.assertEqual(row["state"], "BLOCKED")
        self.assertFalse(row["external_capabilities_off"])
        self.assertFalse(row["pilot_authorized"])

    def test_success_criteria_require_sample_and_never_guarantee_financial_result(self):
        row = self._success()
        self.assertEqual(row["state"], "DEFINED")
        self.assertGreaterEqual(row["minimum_sample_size"], 20)
        self.assertFalse(row["financial_guarantee"])
        self.assertFalse(row["automatic_success_claim"])
        bad = define_success_criteria(
            metric_names=["x"], minimum_sample_size=5, review_cadence_days=7
        )
        self.assertEqual(bad["state"], "INCOMPLETE")

    def test_stop_conditions_require_privacy_incident_and_unexpected_action(self):
        row = self._stop()
        self.assertEqual(row["state"], "DEFINED")
        self.assertTrue(row["human_escalation_required"])
        self.assertFalse(row["automatic_runtime_shutdown_available_now"])
        incomplete = define_stop_conditions(
            reasons=["CLIENT_REQUEST"],
            immediate_stop_on_unexpected_external_action=True,
        )
        self.assertEqual(incomplete["state"], "INCOMPLETE")

    def test_all_gates_only_create_review_required_never_authorization(self):
        review = pilot_gate_review(
            self._charter(), self._gates(), self._success(), self._stop()
        )
        self.assertEqual(review["state"], "PILOT_REVIEW_REQUIRED")
        self.assertTrue(review["all_mandatory_gates_pass"])
        self.assertEqual(review["failed_gates"], [])
        self.assertFalse(review["pilot_authorized"])
        self.assertFalse(review["pilot_started"])
        self.assertFalse(review["runtime_activated"])
        self.assertFalse(review["external_actions_authorized"])
        self.assertFalse(review["payment_authorized"])
        self.assertFalse(review["publication_authorized"])

    def test_missing_gate_fails_closed(self):
        gates = self._gates()
        gates["rollback_ready"] = False
        review = pilot_gate_review(
            self._charter(), gates, self._success(), self._stop()
        )
        self.assertEqual(review["state"], "BLOCKED")
        self.assertIn("rollback_ready", review["failed_gates"])
        self.assertFalse(review["all_mandatory_gates_pass"])

    def test_review_packet_requires_explicit_human_approval_later(self):
        review = pilot_gate_review(
            self._charter(), self._gates(), self._success(), self._stop()
        )
        packet = pilot_review_packet(
            self._charter(), review, requested_by="Mikael"
        )
        self.assertEqual(packet["state"], "HUMAN_PILOT_APPROVAL_REQUIRED")
        self.assertEqual(packet["approval_scope"], "BUSINESS_BOUNDED_PILOT_ONLY")
        self.assertTrue(packet["approval_must_name_client"])
        self.assertTrue(packet["approval_must_name_workflow"])
        self.assertTrue(packet["approval_must_name_duration"])
        self.assertFalse(packet["human_approval_recorded"])
        self.assertFalse(packet["pilot_authorized"])
        self.assertFalse(packet["runtime_activation_approved"])
        self.assertFalse(packet["external_actions_authorized"])

    def test_posture_keeps_runtime_off_even_when_review_packet_is_ready(self):
        charter = self._charter()
        review = pilot_gate_review(
            charter, self._gates(), self._success(), self._stop()
        )
        packet = pilot_review_packet(charter, review, requested_by="Mikael")
        posture = pilot_posture(charter, review, packet)
        self.assertEqual(posture["state"], "AWAITING_EXPLICIT_HUMAN_APPROVAL")
        self.assertTrue(posture["demo_complete_is_not_pilot_approval"])
        self.assertTrue(posture["pilot_review_is_not_pilot_approval"])
        self.assertEqual(posture["runtime_state"], "OFF")
        self.assertFalse(posture["pilot_authorized"])
        self.assertFalse(posture["executes_action"])

    def test_module_has_no_external_io_provider_or_ui_imports(self):
        source = Path("atlasquant_aion_business_pilot_governance.py").read_text(encoding="utf-8")
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
