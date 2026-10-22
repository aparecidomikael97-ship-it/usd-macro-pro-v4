"""A152 adversarial evidence-decision tests. NO external trust or execution."""
from copy import deepcopy
from datetime import date
from pathlib import Path
import unittest

from tools.aion_p0_a152_external_evidence_decision_gate import (
    A152EvidenceError, EXPECTED_PRODUCER_ERRORS, ROOT, SOURCE_PATHS,
    audit_documentary_sources, load_readonly_sources,
)

AS_OF = date(2026, 10, 22)


class A152ExternalEvidenceDecisionLAB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = load_readonly_sources(ROOT)

    def setUp(self):
        self.sources = deepcopy(self.baseline)

    def assess(self):
        return audit_documentary_sources(self.sources, as_of=AS_OF)

    def test_01_real_source_set_valid_but_never_grants_go(self):
        r = self.assess()
        self.assertEqual(r["decision"], "HARD_NO_GO_EXTERNAL_CUSTODY_AND_PRODUCER_EVIDENCE_MISSING")
        self.assertEqual(r["authority"]["homologated_p0_count"], 0)
        self.assertFalse(any(v for k,v in r["authority"].items() if isinstance(v,bool)))

    def test_02_historical_quality_is_51_fail_and_34_error(self):
        q=self.assess()["historical_quality_baseline_only"]
        self.assertEqual((q["tests"],q["fail"],q["error"]),(6895,51,34))
        self.assertTrue(q["not_claimed_as_latest_ci"])

    def test_03_current_external_provider_crosswalk_is_23_8_1(self):
        r=self.assess()
        self.assertEqual(r["source_integrity"]["provider_issues_open"],32)
        self.assertEqual(r["source_integrity"]["producer_gate_breakdown"],
                         dict(sorted(EXPECTED_PRODUCER_ERRORS.items())))

    def test_04_unsent_rfi_pending_34(self):
        r=self.assess()["source_integrity"]
        self.assertEqual(r["RFI_questions"],34)
        self.assertEqual(r["RFI_unanswered"],34)
        self.assertEqual(r["RFI_answer_claims_unverified"],0)

    def test_05_vendor_pairs_are_documentary_only(self):
        self.assertEqual(self.assess()["source_integrity"]["documentary_vendor_pairs"],6)

    def test_06_unknown_financial_quotes_cannot_be_converted_to_zero(self):
        r=self.assess()["finops"]
        self.assertTrue(r["unpriced"])
        self.assertIsNone(r["projected_monthly_brl_UNVERIFIED_INPUTS"])
        self.assertIn("NO_COMPLETE_COST_PROJECTION",r["issues"])

    def test_07_200_brl_is_global_cap_not_spending_approval(self):
        r=self.assess()
        self.assertEqual(r["finops"]["global_cap_brl"],"200.00")
        self.assertEqual(r["authority"]["new_spend_authorized_brl"],0)
        self.assertFalse(r["authority"]["actual_cost_verified"])

    def test_08_e0_through_e5_all_explicitly_missing(self):
        r=self.assess()
        self.assertEqual(set(r["evidence_gates"]),
                         {"E0_FINANCE","E1_IAM_IDENTITY","E2_IMMUTABLE_ANCHOR",
                          "E3_MONOTONIC_WITNESS","E4_CRASH_RECOVERY",
                          "E5_FULL_H0_SIGNOFF"})
        self.assertTrue(all(v.startswith("MISSING_") for v in r["evidence_gates"].values()))

    def test_09_zero_auto_resend_even_if_documents_coherent(self):
        self.assertIs(self.assess()["authority"]["automatic_resend_allowed"],False)

    def test_10_worker_never_armed(self):
        self.assertIs(self.assess()["authority"]["worker_allowed"],False)

    def test_11_real_owner_consent_cannot_be_inferred_from_documents(self):
        self.assertIs(self.assess()["authority"]["real_HUMAN_OWNER_consent_verified"],False)

    def test_12_provider_no_effect_not_inferred_from_twilio_documentation(self):
        self.assertFalse(self.assess()["authority"]["producer_effect_or_terminal_no_effect_authenticated"])

    def test_13_missing_named_source_fails_closed(self):
        self.sources.pop("finops")
        with self.assertRaisesRegex(A152EvidenceError,"A152_SOURCE_SET_INVALID"):
            self.assess()

    def test_14_extra_document_fake_external_proof_source_fails_closed(self):
        self.sources["real_provider_receipt"]={"verified":True}
        with self.assertRaisesRegex(A152EvidenceError,"A152_SOURCE_SET_INVALID"):
            self.assess()

    def test_15_malformed_quality_baseline_fails_closed(self):
        self.sources["quality"]["baseline"]["fail"]=0
        with self.assertRaisesRegex(A152EvidenceError,"QUALITY_RED_BASELINE_CHANGED"):
            self.assess()

    def test_16_quality_85_case_ledger_missing_entry_fails_closed(self):
        self.sources["quality"]["entries"].pop()
        with self.assertRaisesRegex(A152EvidenceError,"QUALITY_RED_LEDGER_MISMATCH"):
            self.assess()

    def test_17_quality_provenance_sha_changed_fails_closed(self):
        self.sources["quality"]["baseline"]["head_sha"]="a"*40
        with self.assertRaisesRegex(A152EvidenceError,"QUALITY_BASELINE_SHA_MISMATCH"):
            self.assess()

    def test_18_rfi_independent_evidence_claim_rejected(self):
        self.sources["rfi"]["answers"][0]["independently_authenticated_evidence"]=True
        with self.assertRaisesRegex(A152EvidenceError,"EXISTING_DOCUMENTARY_GATE_REJECTED"):
            self.assess()

    def test_19_unsent_rfi_falsely_marked_sent_rejected(self):
        self.sources["rfi"]["rfi_delivery_status"]="SENT"
        with self.assertRaisesRegex(A152EvidenceError,"EXISTING_DOCUMENTARY_GATE_REJECTED"):
            self.assess()

    def test_20_vendor_custodian_account_forged_enrolled_rejected(self):
        self.sources["roles"]["global_governance"]["custodian_account_provisioned"]=True
        with self.assertRaisesRegex(A152EvidenceError,"EXISTING_DOCUMENTARY_GATE_REJECTED"):
            self.assess()

    def test_21_vendor_pair_false_real_authorization_rejected(self):
        self.sources["roles"]["non_go_pairs"][0]["can_dispatch"]=True
        with self.assertRaisesRegex(A152EvidenceError,"EXISTING_DOCUMENTARY_GATE_REJECTED"):
            self.assess()

    def test_22_crosswalk_producer_receipt_claim_rejected(self):
        self.sources["crosswalk"]["authority"]["external_receipt_authenticated"]=True
        with self.assertRaisesRegex(A152EvidenceError,"EXISTING_DOCUMENTARY_GATE_REJECTED"):
            self.assess()

    def test_23_crosswalk_drop_one_case_fails_closed(self):
        self.sources["crosswalk"]["cases"].pop()
        with self.assertRaisesRegex(A152EvidenceError,"EXISTING_DOCUMENTARY_GATE_REJECTED"):
            self.assess()

    def test_24_financial_cap_increased_to_250_is_fiscal_defect_not_authority(self):
        self.sources["finops"]["global_cap_brl"]="250"
        r=self.assess()
        self.assertIn("GLOBAL_CAP_CHANGE_NOT_AUTHORIZED",r["finops"]["issues"])
        self.assertEqual(r["finops"]["global_cap_brl"],"200.00")
        self.assertFalse(r["authority"]["actual_cost_verified"])

    def test_25_quote_is_31_days_stale_not_validated(self):
        self.sources["finops"]["regional_aws_quote_date"]="2026-09-21"
        self.assertIn("AWS_QUOTE_FRESH_EVIDENCE_MISSING",self.assess()["finops"]["issues"])

    def test_26_claimed_review_controls_true_do_not_prove_cloud_iam(self):
        controls=self.sources["finops"]["proposed_controls"]
        for k in controls:
            controls[k]=True
        r=self.assess()
        self.assertFalse(r["authority"]["independent_D1_D2_custody_verified"])

    def test_27_synthetic_accurate_cost_math_cannot_prove_current_spend(self):
        p=self.sources["finops"]
        p["regional_aws_quote_date"]="2026-10-21"
        p["usd_brl_observed_date"]="2026-10-21"
        prices={
            "s3_standard_gb_month_usd":"0.03",
            "s3_put_per_1000_usd":"0.005",
            "s3_get_per_1000_usd":"0.0004",
            "kms_key_month_usd":"1",
            "kms_per_10000_usd":"0.001",
            "audit_logging_monthly_usd":"0",
            "other_cloud_monthly_usd":"0",
            "usd_brl_stress_rate":"6",
            "existing_ecosystem_monthly_brl":"80",
            "tax_fx_uncertainty_fraction":"0.30",
        }
        p["quotes"].update(prices)
        p["workload"].update({
            "anchors_per_day":10,
            "retention_days":90,
            "versions_per_anchor":1,
            "bytes_per_version":1024,
            "s3_puts_per_anchor":1,
            "s3_gets_per_anchor":2,
            "kms_calls_per_anchor":1,
            "cloudflare_account_requests_per_day":200,
            "cloudflare_account_gbs_per_day":1,
            "cloudflare_account_rows_read_per_day":500,
            "cloudflare_account_rows_written_per_day":300,
            "cloudflare_account_sqlite_gb":0.01,
            "workers_account_requests_per_day":200,
        })
        p["proposed_controls"].update({k:True for k in p["proposed_controls"]})
        r=self.assess()
        self.assertFalse(r["finops"]["unpriced"])
        self.assertIsNotNone(r["finops"]["projected_monthly_brl_UNVERIFIED_INPUTS"])
        self.assertFalse(r["authority"]["actual_cost_verified"])
        self.assertFalse(r["authority"]["first_effect_allowed"])

    def test_28_unverified_vendor_support_answer_still_not_proof(self):
        row=self.sources["rfi"]["answers"][0]
        row.update({"response_state":"ANSWERED_UNVERIFIED",
                    "response_observed_at":"2026-10-22",
                    "vendor_response_reference":"PRIVATE_RECORD:synthetic",
                    "verified_by_independent_reviewer":False,
                    "independently_authenticated_evidence":False,
                    "claim_of_production_authority":False,
                    "open_item":True})
        r=self.assess()
        self.assertEqual(r["source_integrity"]["RFI_unanswered"],33)
        self.assertEqual(r["source_integrity"]["RFI_answer_claims_unverified"],1)
        self.assertFalse(r["authority"]["provider_enrolled"])

    def test_29_wrong_date_type_denied(self):
        with self.assertRaisesRegex(A152EvidenceError,"AS_OF_INVALID"):
            audit_documentary_sources(self.sources,as_of="2026-10-22")

    def test_30_invalid_claimed_provider_source_shape_denied(self):
        self.sources["roles"]["provider_candidates"]={}
        with self.assertRaisesRegex(A152EvidenceError,"EXISTING_DOCUMENTARY_GATE_REJECTED"):
            self.assess()


if __name__ == "__main__":
    unittest.main()
