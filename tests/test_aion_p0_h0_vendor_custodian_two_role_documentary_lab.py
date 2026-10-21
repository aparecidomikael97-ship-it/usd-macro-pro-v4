"""Adversarial documentary assessment tests: none can authorize real effects."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import json
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from aion_p0_h0_vendor_custodian_documentary_gate import (  # noqa:E402
    PATH, audit, DocumentaryGateError
)


class TwoRoleH0VendorCustodianDocumentaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=json.loads(PATH.read_text(encoding="utf-8"))

    def check(self,change=None):
        x=deepcopy(self.base)
        if change is not None:
            change(x)
        return audit(x)

    def denied(self,func,reason):
        with self.assertRaisesRegex(DocumentaryGateError,reason):
            self.check(func)

    def test_01_complete_two_role_6_pair_inventory_never_goes_live(self):
        result=self.check()
        self.assertEqual((result["provider_count"],result["custodian_count"],result["pair_count"]),(3,2,6))
        self.assertEqual(result["verdict"],"HARD_NO_GO_EXTERNAL_EVIDENCE_MISSING")
        for k in ("actual_external_trust_verified","effect_or_absence_proven","worker_allowed","automatic_resend_allowed"):
            self.assertIs(result[k],False)
        self.assertEqual(result["homologated_p0_count"],0)

    def test_02_provider_authority_false_not_solely_identity_value(self):
        self.denied(lambda x:x["provider_candidates"][0].__setitem__("independent_enrollment_verified",True),"UNVERIFIED")

    def test_03_custodian_authority_false_not_solely_cloud_product_name(self):
        self.denied(lambda x:x["custodian_candidates"][0].__setitem__("independent_enrollment_verified",True),"UNVERIFIED")

    def test_04_fake_provider_receipt_does_not_open_gate(self):
        self.denied(lambda x:x["provider_candidates"][1].__setitem__("authenticated_external_receipt_verified",True),"UNVERIFIED")

    def test_05_fake_terminal_no_effect_fence_cannot_be_passed(self):
        self.denied(lambda x:x["provider_candidates"][0].__setitem__("terminal_no_effect_verified",True),"UNVERIFIED")

    def test_06_user_account_tested_false_required_without_creds(self):
        self.denied(lambda x:x["custodian_candidates"][1].__setitem__("actual_account_tested",True),"UNVERIFIED")

    def test_07_no_external_send_under_documentary_research(self):
        self.denied(lambda x:x["global_governance"].__setitem__("approved_merchant_or_sms_send",True),"UNVERIFIED")

    def test_08_no_automatic_resend_under_any_provider(self):
        self.denied(lambda x:x["global_governance"].__setitem__("automatic_resend_enabled",True),"UNVERIFIED")

    def test_09_no_worker_enrollment_by_paper_review(self):
        self.denied(lambda x:x["global_governance"].__setitem__("worker_enabled",True),"UNVERIFIED")

    def test_10_no_spend_claim_without_explicit_authorization(self):
        self.denied(lambda x:x["global_governance"].__setitem__("new_spend_authorized_brl",10),"UNAUTHORIZED_SPEND")

    def test_11_one_signal_dedupe_duration_is_not_infinite(self):
        self.denied(lambda x:x["provider_candidates"][0]["documented_capabilities"].__setitem__("dedupe_duration_days",999999),"ONESIGNAL_DEDUPE_SCOPE")

    def test_12_one_signal_sms_create_dedupe_is_not_terminal_no_effect(self):
        self.denied(lambda x:x["cross_role_gate"].__setitem__("client_dedupe_not_equal_to_terminal_no_effect",False),"EXTERNAL_FENCE_PRETENDED")

    def test_13_twilio_classic_dedupe_token_cannot_be_invented(self):
        self.denied(lambda x:x["provider_candidates"][1]["documented_capabilities"].__setitem__("dedupe_key","operationId"),"TWILIO_CLASSIC_DEDUPE")

    def test_14_twilio_bulk_operation_id_is_not_dedupe(self):
        self.denied(lambda x:x["provider_candidates"][2]["documented_capabilities"].__setitem__("client_create_idempotency","TRUE"),"OPERATION_ID_CONFUSED")

    def test_15_timeout_empty_list_or_404_never_fences_future_effect(self):
        self.denied(lambda x:x["cross_role_gate"].__setitem__("no_evidence_from_timeout_404_or_empty_list",False),"EXTERNAL_FENCE_PRETENDED")

    def test_16_cloudflare_free_tier_not_price_promise(self):
        self.denied(lambda x:x["custodian_candidates"][0]["cost_evidence"].__setitem__("amount_brl_monthly",0),"UNVERIFIED_COST")

    def test_17_aws_dynamodb_free_tier_not_price_promise(self):
        self.denied(lambda x:x["custodian_candidates"][1]["cost_evidence"].__setitem__("amount_brl_monthly",0),"UNVERIFIED_COST")

    def test_18_same_root_for_producer_and_custodian_not_independent(self):
        self.denied(lambda x:x["cross_role_gate"].__setitem__("local_executor_cannot_administer_both_roots",False),"EXTERNAL_FENCE_PRETENDED")

    def test_19_unverified_high_water_latest_cannot_be_true(self):
        self.denied(lambda x:x["cross_role_gate"].__setitem__("highwater_must_be_authenticated_from_external_independent_source",False),"EXTERNAL_FENCE_PRETENDED")

    def test_20_unknown_first_attempt_is_not_retryable(self):
        self.denied(lambda x:x["cross_role_gate"].__setitem__("when_lost_first_response","RETRY"),"FIRST_ATTEMPT_UNSAFE_RESEND")

    def test_21_missing_one_combination_is_rejected(self):
        self.denied(lambda x:x["non_go_pairs"].pop(),"PAIR_COVERAGE_MISSING")

    def test_22_relabelled_one_pair_as_go_is_rejected(self):
        self.denied(lambda x:x["non_go_pairs"][0].__setitem__("can_dispatch",True),"PAIR_UNVERIFIED_AUTHORIZATION")

    def test_23_fake_verified_credential_same_row_rejected(self):
        self.denied(lambda x:x["custodian_candidates"][0].__setitem__("approved_for_effects",True),"UNVERIFIED")

    def test_24_documentary_shortlist_is_not_pilot_approval(self):
        self.denied(lambda x:x["shortlist_for_documentary_RFI_only"].__setitem__("status","APPROVED_PILOT"),"SHORTLIST_MISTAKEN_FOR_APPROVAL")

    def test_25_wrong_undocumented_provider_or_endpoint_rejected(self):
        self.denied(lambda x:x["provider_candidates"][1].__setitem__("id","TWILIO_CONVERSATIONS"),"PROVIDER_ENDPOINTS_CHANGED")

    def test_26_absence_of_official_sources_rejected(self):
        self.denied(lambda x:x["provider_candidates"][2].__setitem__("official_references",[]),"UNSUPPORTED_DOCUMENT_REFERENCE")

    def test_27_claiming_one_homologated_p0_rejected(self):
        self.denied(lambda x:x["global_governance"].__setitem__("homologated_p0_count",1),"P0_PREMATURE_HOMOLOGATION")

    def test_28_remove_external_fence_requirement_rejected(self):
        self.denied(lambda x:x["cross_role_gate"].__setitem__("provider_terminal_no_effect_requires_enforced_future_effect_fence",False),"EXTERNAL_FENCE_PRETENDED")


if __name__=="__main__":
    unittest.main()
