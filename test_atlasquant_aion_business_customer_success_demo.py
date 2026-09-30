import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_customer_success_demo import (
    PRIORITIES,
    customer_health,
    expansion_opportunity,
    normalize_customer_signals,
    renewal_readiness,
    sla_ticket,
    success_plan,
)


def _healthy(**updates):
    data = {
        "company_name": "Clínica Horizonte Demo",
        "usage_pct": 85,
        "goals_progress_pct": 80,
        "satisfaction_score": 4.5,
        "days_since_last_activity": 2,
        "open_tickets": 0,
        "critical_incidents": 0,
        "onboarding_complete": True,
        "monthly_review_done": True,
        "payment_state": "CURRENT",
        "renewal_days": 45,
    }
    data.update(updates)
    return data


class BusinessCustomerSuccessDemoTests(unittest.TestCase):
    def test_signals_are_demo_only_and_bounded(self):
        row = normalize_customer_signals(_healthy())
        self.assertEqual(row["truth_state"], "DEMO_USER_INPUT")
        self.assertFalse(row["real_client_verified"])
        self.assertGreater(row["coverage_pct"], 80)
        bad = normalize_customer_signals(_healthy(usage_pct=101, satisfaction_score=6))
        self.assertIsNone(bad["usage_pct"])
        self.assertIsNone(bad["satisfaction_score"])

    def test_healthy_customer_is_not_automatically_upsold(self):
        health = customer_health(_healthy())
        self.assertEqual(health["state"], "HEALTHY")
        self.assertGreaterEqual(health["health_score"], 80)
        self.assertFalse(health["churn_risk"])
        opportunity = expansion_opportunity(health)
        self.assertEqual(opportunity["state"], "EXPANSION_REVIEW_AVAILABLE")
        self.assertTrue(opportunity["eligible_for_human_review"])
        self.assertFalse(opportunity["automatic_upsell"])
        self.assertFalse(opportunity["executes_action"])

    def test_at_risk_customer_prioritizes_success_before_expansion(self):
        health = customer_health(_healthy(
            usage_pct=10,
            goals_progress_pct=15,
            satisfaction_score=2,
            days_since_last_activity=45,
            critical_incidents=1,
            onboarding_complete=False,
        ))
        self.assertIn(health["state"], {"CRITICAL", "AT_RISK"})
        self.assertTrue(health["churn_risk"])
        plan = success_plan(health)
        self.assertGreaterEqual(len(plan["actions"]), 4)
        opportunity = expansion_opportunity(health)
        self.assertEqual(opportunity["state"], "NO_UPSELL_NOW")
        self.assertFalse(opportunity["eligible_for_human_review"])

    def test_sla_ticket_is_demo_only_and_detects_breach(self):
        p1 = sla_ticket(title="Falha crítica demo", priority="P1", age_hours=2)
        self.assertEqual(p1["target_hours"], PRIORITIES["P1"]["target_hours"])
        self.assertEqual(p1["sla_state"], "BREACHED_DEMO")
        self.assertFalse(p1["sent_to_support"])
        self.assertFalse(p1["external_write"])
        self.assertFalse(p1["executes_action"])
        normal = sla_ticket(title="Dúvida", priority="P3", age_hours=2)
        self.assertEqual(normal["sla_state"], "WITHIN_TARGET_DEMO")

    def test_success_plan_is_review_only(self):
        plan = success_plan(customer_health(_healthy(monthly_review_done=False)))
        self.assertEqual(plan["state"], "PLAN_READY")
        self.assertTrue(any(item["source"] == "REVIEW_PENDING" for item in plan["actions"]))
        self.assertTrue(all(item["status"] == "PENDING_REVIEW" for item in plan["actions"]))
        self.assertFalse(plan["executes_action"])

    def test_renewal_window_does_not_authorize_renewal(self):
        health = customer_health(_healthy(renewal_days=30))
        renewal = renewal_readiness(health)
        self.assertEqual(renewal["state"], "REVIEW_REQUIRED")
        self.assertTrue(renewal["review_window"])
        self.assertFalse(renewal["renewal_authorized"])
        self.assertFalse(renewal["automatic_renewal"])
        self.assertFalse(renewal["executes_action"])

    def test_unknown_renewal_days_fail_closed(self):
        renewal = renewal_readiness(customer_health(_healthy(renewal_days=None)))
        self.assertEqual(renewal["state"], "UNKNOWN")
        self.assertFalse(renewal["review_window"])
        self.assertFalse(renewal["renewal_authorized"])

    def test_module_has_no_external_io_or_provider_imports(self):
        source = Path("atlasquant_aion_business_customer_success_demo.py").read_text(encoding="utf-8")
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
