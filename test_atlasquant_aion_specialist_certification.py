"""Specialist router, domain isolation and certification gate."""
import unittest

from atlasquant_aion_core_intelligence.context import Context, Domain
from atlasquant_aion_core_intelligence.registry import Registry
from atlasquant_aion_core_intelligence.router import route
from atlasquant_aion_memory_layers import recall, remember
from atlasquant_aion_specialist_certification import (
    assess_specialist_certification,
    specialist_readiness_matrix,
)
from atlasquant_aion_specialist_router import (
    evaluate_specialist_request,
    present_domain_evidence,
    route_specialist,
)


def _context(domain):
    return Context("tenant-a", "workspace-a", "human-a", "task-a", domain, "ADMIN")


def _proof(**updates):
    payload = {
        "version": "1",
        "evidence_verified": True,
        "routing": {
            "correct_specialist_selected": True,
            "ambiguous_not_silently_selected": True,
        },
        "isolation": {
            "memory_separated": True,
            "evidence_separated": True,
            "automatic_cross_domain_access": False,
        },
        "permissions": {
            "scope_escalated": False,
            "role_escalated": False,
            "undeclared_tool": False,
        },
        "truth": {
            "unknown_promoted": False,
            "stale_promoted": False,
            "conflict_resolved_silently": False,
            "incomplete_promoted": False,
        },
        "safety": {
            "real_trading_enabled": False,
            "payment_executed": False,
            "publication_executed": False,
            "deploy_executed": False,
            "external_side_effects": False,
        },
        "tests": {
            "state": "PASS",
            "passed": True,
            "suite": "test_atlasquant_aion_specialist_certification.py",
            "fingerprint": "a" * 64,
            "provenance": "local-specialist-suite",
            "version": "1",
            "sha": "a7aa014deb5fb8c3c1732b71d0718a0f7e5f246f",
            "refs": ["docs/aion/AION_SPECIALIST_CERTIFICATION_V1.md"],
        },
    }
    payload.update(updates)
    return payload


class SpecialistRouterTests(unittest.TestCase):
    def test_trader_business_and_investments_select_their_experts(self):
        cases = (
            ("TRADER", "TRADER_EXPERT", "AION Trader Expert"),
            ("BUSINESS", "BUSINESS_EXPERT", "AION Business Expert"),
            ("INVESTMENTS", "INVESTMENT_EXPERT", "AION Investment Expert"),
            ("AION/CORE", "AION_CORE", "AION"),
        )
        for domain, profile_id, name in cases:
            with self.subTest(domain=domain):
                selected = route_specialist(domain=domain)
                self.assertEqual(selected["status"], "SELECTED")
                self.assertEqual(selected["specialist"], profile_id)
                self.assertEqual(selected["display_name"], name)
                self.assertFalse(selected["runtime_capability_available"])
                self.assertEqual(selected["certification_state"], "NOT_CERTIFIED")
                self.assertFalse(selected["tool_called"])
                self.assertFalse(selected["permissions_expanded"])
                self.assertFalse(selected["activates_specialist"])

    def test_workspace_aliases_follow_the_same_profiles(self):
        self.assertEqual(route_specialist(workspace="atlasquant")["specialist"], "TRADER_EXPERT")
        self.assertEqual(route_specialist(workspace="business")["specialist"], "BUSINESS_EXPERT")
        self.assertEqual(route_specialist(workspace="investments")["specialist"], "INVESTMENT_EXPERT")
        self.assertEqual(route_specialist(workspace="central")["specialist"], "AION_CORE")

    def test_ambiguous_context_does_not_select_a_specialist(self):
        selected = route_specialist(intent="analisar trader e business")
        self.assertEqual(selected["status"], "CLARIFICATION_REQUIRED")
        self.assertIsNone(selected["specialist"])
        self.assertGreaterEqual(len(selected["candidates"]), 2)
        self.assertFalse(selected["silent_fallback"])

    def test_unknown_domain_is_denied_safe(self):
        selected = route_specialist(domain="CRYPTO_DESK")
        self.assertEqual(selected["status"], "UNKNOWN")
        self.assertEqual(selected["reason"], "DENIED_SAFE")
        self.assertIsNone(selected["specialist"])

    def test_missing_specialist_is_degraded_safe_without_fallback(self):
        selected = route_specialist(domain="TRADER", requested_specialist="LAB_EXPERT")
        self.assertEqual(selected["status"], "DEGRADED_SAFE")
        self.assertEqual(selected["reason"], "SPECIALIST_NOT_REGISTERED")
        self.assertIsNone(selected["specialist"])
        self.assertNotEqual(selected["specialist"], "TRADER_EXPERT")

    def test_future_runtime_stays_disabled_and_profiles_stay_uncertified(self):
        registry = Registry(checkpoint_connected=False)
        for name in ("TRADER_FUTURE", "BUSINESS_FUTURE", "INVESTMENTS_FUTURE"):
            row = registry.get(name)
            self.assertFalse(row["available"])
            self.assertTrue(row["domain_recognized"])
            self.assertTrue(row["specialist_profile_registered"])
            self.assertFalse(row["runtime_capability_available"])
            self.assertFalse(row["specialist_certified"])
            self.assertEqual(row["certification_state"], "NOT_CERTIFIED")
        future = route("estado do sistema", _context(Domain.TRADER), registry)
        self.assertEqual(future.status, "UNAVAILABLE")
        self.assertEqual(future.reason, "FUTURE_CONTEXT_DISABLED")

    def test_core_does_not_inherit_physical_authority(self):
        selected = route_specialist(domain="CORE", parent_roles=["ADMIN"])
        self.assertEqual(selected["specialist"], "AION_CORE")
        self.assertFalse(selected["inherits_physical_authority"])
        self.assertIn("real_trade", selected["denied_actions"])
        decision = evaluate_specialist_request(selected, requested_actions=["real_trade", "payment"])
        self.assertEqual(decision["granted_actions"], [])
        self.assertFalse(decision["permissions_expanded"])


class DomainIsolationTests(unittest.TestCase):
    def _memory(self, domain, content, truth="UNKNOWN"):
        return remember(
            None,
            layer="working",
            content=content,
            origin="specialist-test",
            category="analysis",
            truth_state=truth,
            domain=domain,
            persona="operator",
        )

    def test_trader_memory_is_invisible_to_business(self):
        memory = self._memory("TRADER", "EURUSD reading is unknown")
        self.assertEqual(recall(memory, domain="BUSINESS", persona="operator"), [])
        self.assertEqual(len(recall(memory, domain="TRADER", persona="operator")), 1)

    def test_business_memory_is_invisible_to_investments(self):
        memory = self._memory("BUSINESS", "Commercial draft only")
        self.assertEqual(recall(memory, domain="INVESTMENTS", persona="operator"), [])
        self.assertEqual(len(recall(memory, domain="BUSINESS", persona="operator")), 1)

    def test_explicit_core_cross_domain_does_not_promote_unknown_evidence(self):
        memory = self._memory("TRADER", "No confirmed quote", truth="UNKNOWN")
        hidden = recall(memory, domain="BUSINESS", persona="operator")
        self.assertEqual(hidden, [])
        visible = recall(
            memory,
            persona="operator",
            accessor_profile="AION_CORE",
            explicit_domains=["TRADER"],
        )
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0]["truth_state"], "UNKNOWN")
        self.assertFalse(visible[0]["used_as_current_fact"])
        self.assertFalse(visible[0]["promoted"])
        self.assertFalse(visible[0]["automatic_cross_domain_access"])
        foreign = present_domain_evidence(
            {"domain": "TRADER", "truth_state": "UNKNOWN", "claim": "quote"},
            target_domain="BUSINESS",
            accessor_profile="AION_CORE",
        )
        self.assertTrue(foreign["explicit_cross_domain"])
        self.assertFalse(foreign["promoted"])
        self.assertFalse(foreign["used_as_current_fact"])
        self.assertEqual(foreign["truth_state"], "UNKNOWN")
        mismatched = present_domain_evidence(
            {"domain": "TRADER", "truth_state": "UNKNOWN"},
            target_domain="BUSINESS",
        )
        self.assertFalse(mismatched["visible"])
        self.assertFalse(mismatched["promoted"])

    def test_persona_isolation_remains_intact(self):
        memory = remember(
            None,
            layer="working",
            content="developer note",
            origin="specialist-test",
            category="task",
            persona="developer",
        )
        self.assertEqual(recall(memory, persona="trader"), [])
        self.assertEqual(len(recall(memory, persona="developer")), 1)
        self.assertEqual(recall(memory), [])

    def test_role_and_tool_escalation_are_blocked(self):
        business = route_specialist(domain="BUSINESS", parent_roles=["USER"], parent_scopes=["draft.read"])
        roles = evaluate_specialist_request(business, requested_roles=["ADMIN"], requested_scopes=["payments.write"])
        self.assertEqual(roles["granted_roles"], [])
        self.assertIn("ADMIN", roles["blocked_roles"])
        self.assertEqual(roles["granted_scopes"], [])
        self.assertFalse(roles["role_escalated"])
        self.assertFalse(roles["scope_escalated"])
        self.assertFalse(roles["permissions_expanded"])
        trader = route_specialist(domain="TRADER", parent_tools=["aion.memory.search"])
        tools = evaluate_specialist_request(trader, requested_tools=["real_trade", "undeclared.publisher"])
        self.assertEqual(tools["granted_tools"], [])
        self.assertFalse(tools["tool_escalated"])
        self.assertTrue(tools["tool_escalation_blocked"])

    def test_safety_flags_stay_false_for_every_selected_profile(self):
        for domain in ("TRADER", "BUSINESS", "INVESTMENTS", "CORE"):
            selected = route_specialist(domain=domain)
            self.assertFalse(selected["real_trading_enabled"])
            self.assertFalse(selected["payment_executed"])
            self.assertFalse(selected["publication_executed"])
            self.assertFalse(selected["external_action_executed"])
            self.assertFalse(selected["deploy_executed"])
            self.assertNotIn("real_trade", selected["allowed_tools"])


class SpecialistCertificationTests(unittest.TestCase):
    def test_truth_failures_do_not_certify(self):
        cases = {
            "unknown_promoted": "UNKNOWN",
            "stale_promoted": "STALE",
            "conflict_resolved_silently": "CONFLICT",
            "incomplete_promoted": "INCOMPLETE",
        }
        for key, label in cases.items():
            with self.subTest(truth=label):
                payload = _proof()
                payload["truth"] = dict(payload["truth"])
                payload["truth"][key] = True
                result = assess_specialist_certification("TRADER", payload, human_review_approved=True)
                self.assertEqual(result["dimensions"]["truth"], "FAIL")
                self.assertNotEqual(result["state"], "CERTIFIED")
                self.assertFalse(result["activates_specialist"])

    def test_real_boolean_review_certifies_and_lookalikes_do_not(self):
        certified = assess_specialist_certification("TRADER", _proof(), human_review_approved=True)
        self.assertEqual(certified["state"], "CERTIFIED")
        self.assertTrue(certified["human_review_approved"])
        self.assertFalse(certified["activates_specialist"])
        self.assertFalse(certified["tool_called"])
        self.assertFalse(certified["permissions_expanded"])
        self.assertFalse(certified["real_trading_enabled"])
        for lookalike in ("true", "yes", "approved", 1, None, "True"):
            with self.subTest(review=lookalike):
                result = assess_specialist_certification("TRADER", _proof(), human_review_approved=lookalike)
                self.assertNotEqual(result["state"], "CERTIFIED")
                self.assertFalse(result["human_review_approved"])

    def test_tested_without_human_review_is_not_certified(self):
        result = assess_specialist_certification("BUSINESS", _proof(), human_review_approved=False)
        self.assertEqual(result["state"], "TESTED")
        self.assertFalse(result["human_review_approved"])
        self.assertFalse(result["activates_specialist"])

    def test_certified_result_does_not_enable_future_runtime(self):
        before = Registry(checkpoint_connected=False).get("INVESTMENTS_FUTURE")
        result = assess_specialist_certification("INVESTMENTS", _proof(), human_review_approved=True)
        after = Registry(checkpoint_connected=False).get("INVESTMENTS_FUTURE")
        self.assertEqual(result["state"], "CERTIFIED")
        self.assertFalse(before["available"])
        self.assertFalse(after["available"])
        self.assertFalse(after["specialist_certified"])
        self.assertFalse(result["runtime_activated"])

    def test_missing_evidence_is_not_pass_and_one_gap_blocks_readiness(self):
        empty = specialist_readiness_matrix()
        for specialist in ("TRADER", "BUSINESS", "INVESTMENTS"):
            row = empty["specialists"][specialist]
            self.assertEqual(row["routing"], "NOT_EVIDENCED")
            self.assertEqual(row["state"], "NOT_CERTIFIED")
        self.assertEqual(empty["aggregate"], "NOT_READY")
        self.assertFalse(empty["masks_uncertified_specialist"])
        partial = specialist_readiness_matrix({
            "TRADER": {**_proof(), "human_review_approved": True},
            "BUSINESS": {**_proof(), "human_review_approved": True},
        })
        self.assertEqual(partial["specialists"]["TRADER"]["state"], "CERTIFIED")
        self.assertEqual(partial["specialists"]["BUSINESS"]["state"], "CERTIFIED")
        self.assertEqual(partial["specialists"]["INVESTMENTS"]["state"], "NOT_CERTIFIED")
        self.assertEqual(partial["specialists"]["INVESTMENTS"]["routing"], "NOT_EVIDENCED")
        self.assertEqual(partial["aggregate"], "NOT_READY")
        complete = specialist_readiness_matrix({
            "TRADER": {**_proof(), "human_review_approved": True},
            "BUSINESS": {**_proof(), "human_review_approved": True},
            "INVESTMENTS": {**_proof(), "human_review_approved": True},
        })
        self.assertEqual(complete["aggregate"], "READY")
        self.assertTrue(all(complete["specialists"][name]["state"] == "CERTIFIED" for name in ("TRADER", "BUSINESS", "INVESTMENTS")))


if __name__ == "__main__":
    unittest.main()
