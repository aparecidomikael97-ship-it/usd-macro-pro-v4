import unittest

from atlasquant_aion_model_router import (
    budget_decision,
    classify_complexity,
    normalize_budget,
    privacy_sensitive,
    route_intelligence,
    set_budget_policy,
)


class AtlasQuantAionModelRouterTests(unittest.TestCase):
    def test_complexity_classifier_is_deterministic(self):
        self.assertEqual(classify_complexity("resuma o status"),"LOW")
        self.assertEqual(classify_complexity("corrigir falha de segurança na arquitetura"),"HIGH")
        self.assertEqual(classify_complexity("analise este tema"),"NORMAL")

    def test_sensitive_content_stays_local(self):
        self.assertTrue(privacy_sensitive("minha senha é abc"))
        route=route_intelligence(
            "verifique este token secreto",
            provider_state="EXTERNAL_READY",
            external_feature_enabled=True,
            budget={"allow_paid":True,"monthly_limit_usd":10},
            estimated_request_cost_usd=1,
            request_approved=True,
        )
        self.assertEqual(route["lane"],"LOCAL_DETERMINISTIC")
        self.assertTrue(route["privacy_sensitive"])
        self.assertFalse(route["executes_provider_call"])

    def test_zero_cost_default_blocks_paid_external_route(self):
        budget=normalize_budget({})
        decision=budget_decision(budget,0.10,request_approved=True)
        self.assertFalse(decision["allowed"])
        route=route_intelligence(
            "análise complexa de arquitetura",
            provider_state="EXTERNAL_READY",
            external_feature_enabled=True,
            budget=budget,
            estimated_request_cost_usd=0.10,
            request_approved=True,
        )
        self.assertEqual(route["lane"],"LOCAL_DETERMINISTIC")

    def test_external_route_requires_feature_provider_budget_and_request_approval(self):
        budget={"allow_paid":True,"monthly_limit_usd":10,"spent_usd":1}
        blocked=route_intelligence(
            "arquitetura complexa",
            provider_state="EXTERNAL_READY",
            external_feature_enabled=True,
            budget=budget,
            estimated_request_cost_usd=2,
            request_approved=False,
        )
        self.assertEqual(blocked["lane"],"LOCAL_DETERMINISTIC")
        allowed=route_intelligence(
            "arquitetura complexa",
            provider_state="EXTERNAL_READY",
            external_feature_enabled=True,
            budget=budget,
            estimated_request_cost_usd=2,
            request_approved=True,
        )
        self.assertEqual(allowed["lane"],"EXTERNAL_REASONING")
        self.assertFalse(allowed["executes_billing"])

    def test_budget_never_exceeds_monthly_remaining(self):
        budget={"allow_paid":True,"monthly_limit_usd":5,"spent_usd":4.5}
        decision=budget_decision(budget,1,request_approved=True)
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["budget"]["remaining_usd"],0.5)

    def test_set_budget_policy_only_changes_checkpoint_copy(self):
        original={"aion":{"real_trading":False}}
        changed=set_budget_policy(
            original,
            monthly_limit_usd=20,
            allow_paid=True,
            approved_by="admin",
            approved_at="2026-09-23T21:00:00-04:00",
        )
        self.assertNotIn("model_budget",original["aion"])
        self.assertTrue(changed["aion"]["model_budget"]["allow_paid"])
        self.assertEqual(changed["aion"]["model_budget"]["monthly_limit_usd"],20)
        self.assertFalse(changed["aion"]["real_trading"])


if __name__=="__main__":
    unittest.main()
