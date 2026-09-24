import unittest

from atlasquant_aion_core import (
    RISKY_EXTERNAL_FEATURES,
    all_confirmed,
    cost_guard,
    feature_flag_snapshot,
    guardian_decision,
    mission_plan,
    route_context,
    truth_record,
)


class AtlasQuantAionCoreTests(unittest.TestCase):
    def test_router_separates_primary_admin_domains(self):
        cases = {
            "publique um vídeo no Instagram": "studio",
            "pesquise produto no Mercado Livre e margem": "business",
            "rode um backtest no laboratório": "laboratory",
            "qual nossa agenda e pendências": "secretary",
            "corrija a interface e abra um pull request": "development",
            "crie um cupom de 7 dias grátis": "promotions",
            "como está o radar forex": "trading",
        }
        for text, expected in cases.items():
            self.assertEqual(route_context(text)["domain"], expected)

    def test_truth_record_never_promotes_value_without_evidence(self):
        unknown = truth_record("pronto")
        confirmed = truth_record("pronto", source="test", confirmed=True)
        self.assertEqual(unknown["kind"], "UNKNOWN")
        self.assertEqual(confirmed["kind"], "CONFIRMED")
        self.assertFalse(all_confirmed([unknown]))
        self.assertTrue(all_confirmed([confirmed]))

    def test_zero_cost_guard_blocks_positive_cost_without_approval(self):
        self.assertTrue(cost_guard(0)["allowed"])
        self.assertFalse(cost_guard(20)["allowed"])
        self.assertTrue(cost_guard(20, approved=True)["allowed"])

    def test_feature_flags_are_off_by_default(self):
        flags = feature_flag_snapshot()
        self.assertEqual(flags, RISKY_EXTERNAL_FEATURES)
        self.assertTrue(all(value is False for value in flags.values()))

    def test_guardian_denies_unknown_and_real_trading_even_for_admin(self):
        admin = {"role": "ADMIN"}
        self.assertFalse(guardian_decision("something_new", admin)["allowed"])
        result = guardian_decision(
            "real_trade",
            admin,
            approved=True,
            feature_flags={"real_broker_execution": True},
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["risk"], "REAL_TRADING")

    def test_guardian_requires_admin_and_explicit_approval_for_sensitive_actions(self):
        user = {"role": "USER"}
        admin = {"role": "ADMIN"}
        self.assertFalse(guardian_decision("save_checkpoint", user, approved=True)["allowed"])
        self.assertFalse(guardian_decision("save_checkpoint", admin, approved=False)["allowed"])
        self.assertTrue(guardian_decision("save_checkpoint", admin, approved=True)["allowed"])

    def test_external_publish_is_double_locked_by_flag_and_approval(self):
        admin = {"role": "ADMIN"}
        self.assertFalse(guardian_decision("publish_social", admin, approved=True)["allowed"])
        self.assertFalse(
            guardian_decision(
                "publish_social",
                admin,
                approved=False,
                feature_flags={"social_publish": True},
            )["allowed"]
        )
        self.assertTrue(
            guardian_decision(
                "publish_social",
                admin,
                approved=True,
                feature_flags={"social_publish": True},
            )["allowed"]
        )

    def test_mission_plan_is_non_executing_and_checkpoint_oriented(self):
        plan = mission_plan("corrigir interface do administrador")
        self.assertEqual(plan["domain"], "development")
        self.assertEqual(plan["status"], "PLANNED")
        self.assertFalse(plan["executes_action"])
        self.assertIn("Sandbox/branch de feature", " ".join(plan["steps"]))


if __name__ == "__main__":
    unittest.main()
