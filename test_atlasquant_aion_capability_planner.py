from __future__ import annotations

import unittest

from atlasquant_aion_capability_planner import (
    capability_snapshot,
    plan_agentic_mission,
)


class AtlasQuantAionCapabilityPlannerTests(unittest.TestCase):
    def setUp(self):
        self.admin = {"role":"ADMIN"}

    def test_local_capabilities_are_available_without_executing(self):
        snap = capability_snapshot(access=self.admin)
        by_id = {x["id"]:x for x in snap["capabilities"]}
        self.assertEqual(by_id["memory_read"]["state"], "AVAILABLE_LOCAL")
        self.assertEqual(by_id["cognitive_plan"]["state"], "AVAILABLE_LOCAL")
        self.assertFalse(snap["automatic_execution"])
        self.assertFalse(snap["automatic_approval"])
        self.assertFalse(snap["real_orders_enabled"])

    def test_real_trading_is_blocked_even_when_flags_and_connector_claim_ready(self):
        snap = capability_snapshot(
            access=self.admin,
            feature_flags={"real_broker_execution":True},
            system_context={"integrations":{"broker_connected":True}},
        )
        by_id = {x["id"]:x for x in snap["capabilities"]}
        self.assertEqual(by_id["real_trade"]["state"], "BLOCKED")
        self.assertFalse(by_id["real_trade"]["executes_action"])

    def test_current_market_requires_fresh_confirmed_market_dependency(self):
        plan = plan_agentic_mission(
            "analise o forex agora",
            access=self.admin,
            system_context={"source_mesh":{"market_live_confirmed":False}},
        )
        market = [x for x in plan["stages"] if x["capability_id"]=="market_snapshot"][0]
        self.assertEqual(market["state"], "EVIDENCE_REQUIRED")
        self.assertEqual(plan["readiness"], "BLOCKED_OR_DEPENDENT")

    def test_confirmed_live_market_read_is_available_without_action_approval(self):
        plan = plan_agentic_mission(
            "analise o forex agora",
            access=self.admin,
            system_context={"source_mesh":{"market_live_confirmed":True}},
        )
        market = [x for x in plan["stages"] if x["capability_id"]=="market_snapshot"][0]
        self.assertEqual(market["state"], "AVAILABLE_LOCAL")
        self.assertFalse(market["requires_explicit_approval"])
        self.assertFalse(market["executes_action"])

    def test_deploy_plan_exposes_feature_and_approval_gate_without_action(self):
        plan = plan_agentic_mission(
            "corrigir a interface e fazer deploy no Render",
            access=self.admin,
            feature_flags={"production_deploy":False},
            system_context={"integrations":{"production_connected":True}},
        )
        deploy = [x for x in plan["stages"] if x["capability_id"]=="production_deploy"][0]
        self.assertEqual(deploy["state"], "FEATURE_DISABLED")
        self.assertTrue(deploy["requires_explicit_approval"])
        self.assertFalse(plan["executes_action"])

    def test_social_publish_plan_stops_at_feature_or_dependency_gate(self):
        plan = plan_agentic_mission(
            "criar e publicar vídeo no Instagram",
            access=self.admin,
            feature_flags={"social_publish":True},
            system_context={"integrations":{"social_connected":False}},
        )
        publish = [x for x in plan["stages"] if x["capability_id"]=="social_publish"][0]
        self.assertEqual(publish["state"], "EXTERNAL_DEPENDENCY")
        self.assertTrue(publish["requires_explicit_approval"])

    def test_checkpoint_write_needs_runtime_then_human_approval(self):
        no_runtime = plan_agentic_mission(
            "salvar checkpoint",
            access=self.admin,
            system_context={"runtime_checkpoint":{"status":"UNAVAILABLE"}},
        )
        write = [x for x in no_runtime["stages"] if x["capability_id"]=="checkpoint_write"][0]
        self.assertEqual(write["state"], "EXTERNAL_DEPENDENCY")

        with_runtime = plan_agentic_mission(
            "salvar checkpoint",
            access=self.admin,
            system_context={"runtime_checkpoint":{"status":"CONFIRMED"}},
        )
        write = [x for x in with_runtime["stages"] if x["capability_id"]=="checkpoint_write"][0]
        self.assertEqual(write["state"], "APPROVAL_REQUIRED")
        self.assertTrue(write["requires_explicit_approval"])


if __name__ == "__main__":
    unittest.main()
