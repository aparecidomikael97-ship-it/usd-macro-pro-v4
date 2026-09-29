import unittest
from datetime import datetime, timezone

from atlasquant_aion_business_brain import (
    ACTIVATION_SEQUENCE,
    BUSINESS_ENGINES,
    DEPRECATED_PRIMARY_FRONTS,
    ENGINE_IDS,
    REINVESTMENT_TARGETS,
    business_strategy_checkpoint,
    brain_snapshot,
    experiment_plan,
    external_action_preflight,
    trend_freshness,
)
from atlasquant_aion_memory import ensure_operating_checkpoint, update_business_checkpoint


class AtlasQuantAionBusinessBrainTests(unittest.TestCase):
    def setUp(self):
        self.admin = {"allowed": True, "role": "ADMIN", "username": "admin.test"}

    def _opportunity(self, **extra):
        row = {
            "engine_id": "automation_b2b",
            "title": "Automação para clínica",
            "summary": "Atendimento, agenda e follow-up.",
            "source": "research:test",
            "truth_state": "CONFIRMED",
            "status": "READY",
            "revenue_score": 90,
            "recurrence_score": 95,
            "readiness_score": 80,
            "urgency_score": 70,
            "customer_ref": "CLIENT-001",
            "next_action": "Preparar proposta.",
            "evidence_observed_at": "2026-09-20T12:00:00+00:00",
        }
        row.update(extra)
        return row

    def test_exactly_five_official_revenue_engines(self):
        self.assertEqual(len(BUSINESS_ENGINES), 5)
        self.assertEqual(
            ENGINE_IDS,
            (
                "automation_b2b",
                "micro_saas",
                "international_ai",
                "revenue_ops",
                "digital_products",
            ),
        )
        self.assertEqual([item["rank"] for item in BUSINESS_ENGINES], [1, 2, 3, 4, 5])

    def test_legacy_fronts_are_explicitly_disabled(self):
        legacy = set(DEPRECATED_PRIMARY_FRONTS)
        for expected in ("dropshipping", "afiliados", "tiktok_shop", "mercado_livre"):
            self.assertIn(expected, legacy)
        for engine in ENGINE_IDS:
            self.assertNotIn(engine, legacy)

    def test_business_purpose_and_activation_sequence_are_checkpoint_contract(self):
        strategy = business_strategy_checkpoint()
        self.assertIn("reinvestir", strategy["purpose"].casefold())
        self.assertEqual(strategy["activation_sequence"], ACTIVATION_SEQUENCE)
        self.assertEqual(
            ACTIVATION_SEQUENCE,
            (
                "aion_core_stable",
                "nucleo_stable",
                "interface_stable",
                "business_controlled_activation",
            ),
        )
        self.assertEqual(
            REINVESTMENT_TARGETS,
            ("aion", "nucleo", "interface", "infrastructure"),
        )
        self.assertTrue(strategy["activation_requires_human_approval"])

    def test_external_actions_never_execute_inside_contract(self):
        blocked = external_action_preflight(
            "send_customer_message",
            self.admin,
            approved=False,
            connector_ready=True,
        )
        self.assertFalse(blocked["allowed"])
        self.assertFalse(blocked["executes_action"])
        eligible = external_action_preflight(
            "send_customer_message",
            self.admin,
            approved=True,
            connector_ready=True,
        )
        self.assertTrue(eligible["allowed"])
        self.assertFalse(eligible["executes_action"])

    def test_trend_evidence_expires_and_experiment_stays_non_executing(self):
        fresh = trend_freshness(
            self._opportunity(),
            now=datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc),
        )
        self.assertTrue(fresh["fresh"])
        stale = trend_freshness(
            self._opportunity(evidence_observed_at="2026-07-01T12:00:00+00:00"),
            now=datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc),
        )
        self.assertFalse(stale["fresh"])
        plan = experiment_plan(
            self._opportunity(external_action="send_customer_message"),
            hypothesis="A automação reduz tempo de resposta.",
            success_metric="20% mais leads respondidos",
            max_cost=100,
            max_days=7,
        )
        self.assertTrue(plan["requires_approval"])
        self.assertFalse(plan["executes_experiment"])

    def test_checkpoint_persists_business_brain_and_strategy(self):
        base = ensure_operating_checkpoint({})
        self.assertEqual(base["business"]["strategy"], business_strategy_checkpoint())
        updated = update_business_checkpoint(
            base,
            opportunities=[self._opportunity()],
            dirty=True,
        )
        self.assertEqual(len(updated["business"]["opportunities"]), 1)
        self.assertTrue(updated["business"]["opportunities_digest"])
        self.assertEqual(updated["business"]["strategy"], business_strategy_checkpoint())
        self.assertTrue(updated["business"]["strategy_digest"])

        snapshot = brain_snapshot(updated["business"]["opportunities"])
        self.assertEqual(snapshot["active_engines"], 5)
        self.assertEqual(snapshot["queue"]["total"], 1)
        self.assertTrue(snapshot["contract"]["trend_radar"])
        self.assertTrue(snapshot["contract"]["experiment_mode"])


if __name__ == "__main__":
    unittest.main()
