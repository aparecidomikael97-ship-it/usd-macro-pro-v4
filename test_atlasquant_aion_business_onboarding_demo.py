import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_onboarding_demo import (
    ACCESS_CATEGORIES,
    PHASES,
    build_implementation_plan,
    go_live_review_packet,
    minimum_access_plan,
    onboarding_intake,
    onboarding_status,
)


class BusinessOnboardingDemoTests(unittest.TestCase):
    def _intake(self):
        return onboarding_intake(
            company_name="Clínica Horizonte Demo",
            package_label="Atendimento & Conversão",
            business_owner="Responsável Demo",
            business_goal="Reduzir demora e organizar follow-up.",
            requested_channels=["WhatsApp", "Instagram"],
            requested_integrations=["calendar", "crm"],
        )

    def test_intake_requires_core_scope_fields_and_never_accepts_real_credentials(self):
        ready = self._intake()
        self.assertEqual(ready["state"], "READY_FOR_PLANNING")
        self.assertFalse(ready["real_credentials_supplied"])
        self.assertFalse(ready["runtime_activated"])
        self.assertFalse(ready["executes_action"])
        blocked = onboarding_intake(
            company_name="",
            package_label="",
            business_owner="",
            business_goal="",
        )
        self.assertEqual(blocked["state"], "INCOMPLETE")
        self.assertEqual(set(blocked["missing"]), {
            "company_name", "package_label", "business_owner", "business_goal",
        })

    def test_access_plan_is_least_privilege_and_has_no_secret_values(self):
        plan = minimum_access_plan(
            self._intake(),
            {"whatsapp_business": True, "calendar": True, "payments": False},
        )
        self.assertEqual(plan["state"], "PLAN_READY")
        self.assertEqual(plan["principle"], "LEAST_PRIVILEGE")
        self.assertEqual(len(plan["items"]), len(ACCESS_CATEGORIES))
        whatsapp = next(x for x in plan["items"] if x["category"] == "whatsapp_business")
        payment = next(x for x in plan["items"] if x["category"] == "payments")
        self.assertEqual(whatsapp["access_level"], "MINIMUM_REQUIRED")
        self.assertTrue(whatsapp["approval_required"])
        self.assertIsNone(whatsapp["credential_value"])
        self.assertEqual(payment["access_level"], "NONE")
        self.assertFalse(plan["stores_secret"])
        self.assertFalse(plan["external_connection_performed"])

    def test_implementation_plan_is_sandbox_first_and_has_six_phases(self):
        intake = self._intake()
        access = minimum_access_plan(intake, {"calendar": True})
        result = build_implementation_plan(intake, access)
        self.assertEqual(result["state"], "PLAN_READY")
        self.assertEqual(len(result["plan"]["phases"]), len(PHASES))
        self.assertTrue(result["plan"]["sandbox_first"])
        self.assertTrue(result["plan"]["human_approval_before_live"])
        self.assertFalse(result["plan"]["live_runtime_authorized"])
        self.assertFalse(result["plan"]["real_credentials_present"])
        self.assertTrue(result["plan_digest"])
        self.assertFalse(result["runtime_activated"])
        self.assertFalse(result["external_write"])
        self.assertFalse(result["executes_action"])

    def test_status_can_complete_demo_but_never_authorize_live_runtime(self):
        intake = self._intake()
        plan = build_implementation_plan(intake, minimum_access_plan(intake, {}))
        partial = onboarding_status(plan, ["ESCOPO", "SANDBOX"])
        self.assertEqual(partial["state"], "IN_PROGRESS")
        self.assertFalse(partial["eligible_for_live_review"])
        complete = onboarding_status(plan, list(PHASES))
        self.assertEqual(complete["state"], "DEMO_COMPLETE")
        self.assertTrue(complete["eligible_for_live_review"])
        self.assertEqual(complete["progress_pct"], 100.0)
        self.assertFalse(complete["live_runtime_authorized"])
        self.assertFalse(complete["runtime_activated"])

    def test_go_live_packet_only_requests_separate_human_review(self):
        intake = self._intake()
        plan = build_implementation_plan(intake, minimum_access_plan(intake, {}))
        status = onboarding_status(plan, list(PHASES))
        packet = go_live_review_packet(plan, status)
        self.assertEqual(packet["state"], "LIVE_REVIEW_REQUIRED")
        self.assertTrue(packet["eligible_for_human_review"])
        self.assertEqual(packet["approval_scope"], "BUSINESS_LIVE_RUNTIME_ONLY")
        self.assertFalse(packet["human_approval_recorded"])
        self.assertFalse(packet["runtime_activation_approved"])
        self.assertFalse(packet["runtime_activated"])
        self.assertFalse(packet["external_actions_authorized"])
        self.assertFalse(packet["payment_authorized"])
        self.assertFalse(packet["publication_authorized"])
        self.assertFalse(packet["executes_action"])

    def test_incomplete_plan_cannot_request_live_review(self):
        blocked = build_implementation_plan({"state": "INCOMPLETE"}, {"state": "PLAN_READY"})
        status = onboarding_status(blocked, list(PHASES))
        packet = go_live_review_packet(blocked, status)
        self.assertEqual(packet["state"], "BLOCKED")
        self.assertFalse(packet["eligible_for_human_review"])
        self.assertFalse(packet["runtime_activation_approved"])

    def test_module_has_no_external_io_or_provider_imports(self):
        source = Path("atlasquant_aion_business_onboarding_demo.py").read_text(encoding="utf-8")
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
