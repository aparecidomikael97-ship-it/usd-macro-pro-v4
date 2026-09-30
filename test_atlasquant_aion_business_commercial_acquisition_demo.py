import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_commercial_acquisition_demo import (
    build_channel_plan,
    build_content_plan,
    build_contract_handoff,
    build_landing_page_brief,
    commercial_funnel_snapshot,
    outreach_draft,
    qualify_prospect,
)


class BusinessCommercialAcquisitionDemoTests(unittest.TestCase):
    def test_channel_plan_is_draft_only_and_has_no_auto_contact_or_spend(self):
        plan = build_channel_plan("Clínica")
        self.assertGreaterEqual(len(plan["channels"]), 4)
        self.assertFalse(plan["automatic_contact"])
        self.assertFalse(plan["automatic_publication"])
        self.assertFalse(plan["automatic_spend"])
        self.assertFalse(plan["executes_action"])

    def test_landing_brief_uses_diagnostic_cta_and_forbids_guarantees(self):
        result = build_landing_page_brief(
            segment="Clínica",
            offer_name="AION Atendimento & Conversão",
            primary_problem="Demora no atendimento e leads sem retorno.",
            package_summary="Diagnóstico, atendimento, follow-up, Radar e manutenção.",
        )
        self.assertEqual(result["state"], "DRAFT_READY")
        brief = result["brief"]
        self.assertEqual(brief["cta"], "Solicitar diagnóstico")
        self.assertIn("garantia de vendas", brief["prohibited_claims"])
        self.assertIn("cliente fictício apresentado como real", brief["prohibited_claims"])
        self.assertEqual(brief["publication_state"], "DRAFT_ONLY")
        self.assertFalse(result["automatic_publication"])
        self.assertFalse(result["executes_action"])

    def test_incomplete_landing_brief_fails_closed(self):
        result = build_landing_page_brief(
            segment="", offer_name="", primary_problem="", package_summary=""
        )
        self.assertEqual(result["state"], "INCOMPLETE")
        self.assertGreaterEqual(len(result["missing"]), 4)
        self.assertEqual(result["brief"], {})

    def test_prospect_qualification_is_review_only(self):
        prospect = qualify_prospect({
            "company_name": "Clínica Demo",
            "segment": "Clínica",
            "contact_permission_state": "OPT_IN_DEMO",
            "pain_fit": 90,
            "urgency": 80,
            "recurring_fit": 90,
            "decision_maker_access": 70,
            "data_readiness": 75,
        })
        self.assertEqual(prospect["state"], "QUALIFIED")
        self.assertGreaterEqual(prospect["score"], 75)
        self.assertTrue(prospect["contact_review_allowed"])
        self.assertFalse(prospect["automatic_contact"])
        self.assertFalse(prospect["automatic_send"])
        self.assertFalse(prospect["executes_action"])

    def test_do_not_contact_blocks_outreach_even_when_fit_is_good(self):
        prospect = qualify_prospect({
            "company_name": "Clínica Demo",
            "segment": "Clínica",
            "contact_permission_state": "DO_NOT_CONTACT",
            "pain_fit": 95,
            "urgency": 95,
            "recurring_fit": 95,
            "decision_maker_access": 90,
            "data_readiness": 90,
        })
        draft = outreach_draft(prospect)
        self.assertEqual(draft["state"], "BLOCKED_DO_NOT_CONTACT")
        self.assertEqual(draft["draft"], "")
        self.assertFalse(draft["sent"])
        self.assertFalse(draft["executes_action"])

    def test_outreach_is_only_a_draft_and_never_sent(self):
        prospect = qualify_prospect({
            "company_name": "Clínica Demo",
            "segment": "Clínica",
            "contact_permission_state": "PERMITTED_DEMO",
            "pain_fit": 85,
            "urgency": 70,
            "recurring_fit": 90,
            "decision_maker_access": 65,
            "data_readiness": 70,
        })
        draft = outreach_draft(prospect, sender_name="Mikael")
        self.assertEqual(draft["state"], "DRAFT_REVIEW_REQUIRED")
        self.assertIn("Mikael", draft["draft"])
        self.assertTrue(draft["requires_human_review"])
        self.assertFalse(draft["sent"])
        self.assertFalse(draft["automatic_send"])
        self.assertFalse(draft["executes_action"])

    def test_contract_handoff_never_signs_or_bills(self):
        handoff = build_contract_handoff(
            company_name="Clínica Demo",
            proposal_ready=True,
            scope_confirmed=True,
            privacy_terms_reviewed=True,
            sla_defined=True,
            commercial_terms_defined=True,
        )
        self.assertEqual(handoff["state"], "READY_FOR_SIGNATURE_REVIEW")
        self.assertEqual(handoff["contract_state"], "READY_FOR_SIGNATURE_REVIEW")
        self.assertFalse(handoff["contract_signed"])
        self.assertFalse(handoff["invoice_issued"])
        self.assertFalse(handoff["payment_collected"])
        self.assertEqual(
            handoff["client_portal_state"],
            "TO_PROVISION_AFTER_APPROVED_ONBOARDING",
        )
        self.assertFalse(handoff["runtime_activated"])
        self.assertFalse(handoff["executes_action"])

    def test_content_plan_requires_verification_for_case_study(self):
        no_case = build_content_plan(segment="Clínica", weeks=5, verified_case_available=False)
        self.assertFalse(any(x["content_type"] == "CASE_STUDY_VERIFIED_ONLY" for x in no_case["items"]))
        with_case = build_content_plan(segment="Clínica", weeks=5, verified_case_available=True)
        self.assertTrue(any(x["content_type"] == "CASE_STUDY_VERIFIED_ONLY" for x in with_case["items"]))
        self.assertFalse(with_case["automatic_publication"])
        self.assertTrue(with_case["approval_required_before_publish"])

    def test_funnel_demo_never_claims_real_contacts_contracts_or_payments(self):
        snap = commercial_funnel_snapshot({
            "PROSPECT": 30,
            "QUALIFIED": 12,
            "DIAGNOSTIC": 8,
            "PROPOSAL_DRAFT": 4,
            "CONTRACT_REVIEW": 2,
            "ONBOARDING_READY": 1,
        })
        self.assertEqual(snap["total_prospects"], 30)
        self.assertEqual(snap["real_contacts_sent"], 0)
        self.assertEqual(snap["real_contracts_signed"], 0)
        self.assertEqual(snap["real_payments_collected"], 0)
        self.assertEqual(snap["truth_state"], "DEMO_USER_INPUT")
        self.assertFalse(snap["executes_action"])

    def test_module_has_no_external_io_provider_or_ui_imports(self):
        source = Path("atlasquant_aion_business_commercial_acquisition_demo.py").read_text(encoding="utf-8")
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
