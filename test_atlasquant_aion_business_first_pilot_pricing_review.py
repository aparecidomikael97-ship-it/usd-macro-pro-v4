import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_b2b_revenue_offer import (
    calculate_offer_economics,
)
from atlasquant_aion_business_first_pilot_pricing_review import (
    candidate_fit_review,
    first_pilot_policy,
    first_pilot_review_packet,
    pricing_pilot_review,
)


def _candidate():
    return candidate_fit_review(
        candidate_reference="pilot-001",
        segment="servicos locais",
        pain_fit_pct=90,
        recurring_fit_pct=85,
        decision_access_pct=80,
        data_readiness_pct=75,
        process_volume_fit_pct=85,
        implementation_readiness_pct=80,
        minimum_admin_fit_pct=70,
        contact_permission_state="OPT_IN",
    )


def _economics():
    return calculate_offer_economics(
        monthly_price_brl=800.0,
        estimated_monthly_cost_brl=240.0,
        implementation_fee_brl=600.0,
        estimated_implementation_cost_brl=200.0,
        minimum_margin_pct=40.0,
    )


def _pricing():
    return pricing_pilot_review(
        _economics(),
        proposed_pilot_monthly_price_brl=700.0,
        proposed_pilot_implementation_fee_brl=500.0,
    )


def _offer_ready():
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_B2B_REVENUE_OFFER_V1",
        "state": "READY_FOR_ADMIN_SALES_REVIEW",
        "readiness_digest": "a" * 64,
        "external_contact_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def _pilot_gates():
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_PILOT_GOVERNANCE_V1",
        "state": "PILOT_REVIEW_REQUIRED",
        "all_mandatory_gates_pass": True,
        "pilot_authorized": False,
        "runtime_activated": False,
        "executes_action": False,
    }


def _pilot_packet():
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_PILOT_REVIEW_PACKET_V1",
        "state": "HUMAN_PILOT_APPROVAL_REQUIRED",
        "charter_digest": "b" * 64,
        "human_approval_recorded": False,
        "pilot_authorized": False,
        "runtime_activation_approved": False,
        "executes_action": False,
    }


class BusinessFirstPilotPricingReviewTests(unittest.TestCase):
    def test_policy_keeps_every_real_action_blocked(self):
        row = first_pilot_policy()
        self.assertEqual(row["max_clients"], 1)
        self.assertEqual(row["max_duration_days"], 30)
        self.assertFalse(row["candidate_auto_selected"])
        self.assertFalse(row["price_auto_selected"])
        self.assertFalse(row["contact_authorized"])
        self.assertFalse(row["executes_action"])

    def test_candidate_fit_uses_admin_floor(self):
        row = _candidate()
        self.assertEqual(row["state"], "CANDIDATE_FIT_REVIEW_READY")
        self.assertGreaterEqual(row["weighted_fit_pct"], 70)
        self.assertTrue(row["contact_review_allowed"])
        self.assertFalse(row["candidate_selected"])

    def test_candidate_below_admin_floor_is_blocked(self):
        row = candidate_fit_review(
            candidate_reference="pilot-002",
            segment="servicos locais",
            pain_fit_pct=40,
            recurring_fit_pct=40,
            decision_access_pct=40,
            data_readiness_pct=40,
            process_volume_fit_pct=40,
            implementation_readiness_pct=40,
            minimum_admin_fit_pct=70,
            contact_permission_state="PERMITTED",
        )
        self.assertEqual(row["state"], "CANDIDATE_FIT_REVIEW_BLOCKED")
        self.assertIn("FIT_BELOW_ADMIN_FLOOR", row["blockers"])

    def test_do_not_contact_is_blocked(self):
        row = candidate_fit_review(
            candidate_reference="pilot-003",
            segment="servicos locais",
            pain_fit_pct=90,
            recurring_fit_pct=90,
            decision_access_pct=90,
            data_readiness_pct=90,
            process_volume_fit_pct=90,
            implementation_readiness_pct=90,
            minimum_admin_fit_pct=70,
            contact_permission_state="DO_NOT_CONTACT",
        )
        self.assertEqual(row["state"], "CANDIDATE_FIT_REVIEW_BLOCKED")
        self.assertIn("DO_NOT_CONTACT", row["blockers"])

    def test_pilot_price_must_stay_above_sustainable_floor(self):
        row = _pricing()
        self.assertEqual(row["state"], "PILOT_PRICING_REVIEW_READY")
        self.assertGreaterEqual(
            row["proposed_pilot_monthly_price_brl"],
            row["minimum_sustainable_monthly_price_brl"],
        )
        self.assertFalse(row["price_selected"])
        self.assertFalse(row["billing_authorized"])

    def test_pilot_price_below_floor_is_blocked(self):
        row = pricing_pilot_review(
            _economics(),
            proposed_pilot_monthly_price_brl=350.0,
            proposed_pilot_implementation_fee_brl=500.0,
        )
        self.assertEqual(row["state"], "PILOT_PRICING_REVIEW_BLOCKED")
        self.assertIn("PILOT_PRICE_BELOW_SUSTAINABLE_FLOOR", row["blockers"])

    def test_full_packet_only_reaches_admin_review(self):
        row = first_pilot_review_packet(
            candidate_review=_candidate(),
            pricing_review=_pricing(),
            offer_readiness=_offer_ready(),
            pilot_gate_review=_pilot_gates(),
            pilot_review_packet=_pilot_packet(),
            requested_by="mikael",
        )
        self.assertEqual(row["state"], "READY_FOR_ADMIN_FIRST_PILOT_REVIEW")
        self.assertEqual(row["candidate_reference"], "pilot-001")
        self.assertFalse(row["candidate_selected"])
        self.assertFalse(row["price_approved"])
        self.assertFalse(row["contact_authorized"])
        self.assertFalse(row["billing_authorized"])
        self.assertFalse(row["pilot_authorized"])
        self.assertFalse(row["runtime_authorized"])
        self.assertFalse(row["executes_action"])

    def test_missing_offer_readiness_blocks_packet(self):
        row = first_pilot_review_packet(
            candidate_review=_candidate(),
            pricing_review=_pricing(),
            offer_readiness={},
            pilot_gate_review=_pilot_gates(),
            pilot_review_packet=_pilot_packet(),
            requested_by="mikael",
        )
        self.assertEqual(row["state"], "FIRST_PILOT_REVIEW_BLOCKED")
        self.assertIn("offer_ready", row["blockers"])

    def test_admin_exposes_first_pilot_review_view(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("28 · Primeiro Piloto & Preco", source)
        self.assertIn("business_first_pilot_policy", source)

    def test_module_has_no_network_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_first_pilot_pricing_review.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for banned in (
            "requests",
            "urllib",
            "httpx",
            "socket",
            "subprocess",
            "github",
            "paramiko",
            "docker",
            "kubernetes",
        ):
            self.assertNotIn(banned, imported)


if __name__ == "__main__":
    unittest.main()
