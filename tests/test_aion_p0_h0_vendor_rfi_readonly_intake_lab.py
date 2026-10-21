"""LAB: 34-question vendor support reply ledger never unlocks AION.

Adversarial fixture variants are synthetic. A reply status is for follow-up,
not producer or custodial attestation and not an authorization to send.
"""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from aion_p0_h0_vendor_rfi_readonly_intake_gate import (  # noqa:E402
    LEDGER,TEMPLATE,audit,IntakeError,
)


class VendorRFIReadOnlyIntakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record=json.loads(LEDGER.read_text(encoding="utf-8"))
        cls.doc=TEMPLATE.read_text(encoding="utf-8")

    def verify(self,mod=None,document=None):
        d=deepcopy(self.record)
        if mod is not None:
            mod(d)
        return audit(d,self.doc if document is None else document)

    def fails(self,mod,reason):
        with self.assertRaisesRegex(IntakeError,reason):
            self.verify(mod)

    def test_01_all_34_real_draft_questions_are_pending(self):
        x=self.verify()
        self.assertEqual(x["questions"],34)
        self.assertEqual(x["pending"],34)
        self.assertEqual(x["by_group"],{
            "AWS_DYNAMODB_ALTERNATIVE":8,
            "CLOUDFLARE_DO_CUSTODIAN":12,
            "ONESIGNAL_SMS_PRODUCER":14,
        })
        self.assertEqual(x["verdict"],"HARD_NO_GO_EXTERNAL_EVIDENCE_MISSING")

    def test_02_no_dispatch_worker_or_automatic_retry_from_draft(self):
        x=self.verify()
        self.assertFalse(x["technical_submission_performed"])
        self.assertFalse(x["external_proof_authenticated"])
        self.assertFalse(x["worker_allowed"])
        self.assertFalse(x["automatic_resend_allowed"])
        self.assertEqual(x["homologated_p0_count"],0)

    def test_03_remove_first_vendor_question_denied(self):
        self.fails(lambda d:d["answers"].pop(0),"QUESTION_COUNT")

    def test_04_duplicated_question_denied(self):
        self.fails(lambda d:d["answers"][1].__setitem__("id","P-01"),"DUPLICATE_QUESTION")

    def test_05_cross_role_question_relabel_denied(self):
        self.fails(lambda d:d["answers"][0].__setitem__("subject","CLOUDFLARE_DO_CUSTODIAN"),"QUESTION_ID_OUT_OF_RANGE")

    def test_06_question_not_present_in_letter_denied(self):
        with self.assertRaisesRegex(IntakeError,"UNDOCUMENTED_QUESTION"):
            self.verify(document=self.doc.replace("**P-07.","**P-XX."))

    def test_07_unsupported_outcome_flag_must_not_claim_response_is_verified(self):
        self.fails(lambda d:d["answers"][0].__setitem__("verified_by_independent_reviewer",True),"MINTED_UNVERIFIED_AUTHORITY")

    def test_08_untrusted_vendor_public_key_is_not_attestation(self):
        self.fails(lambda d:d["answers"][0].__setitem__("independently_authenticated_evidence",True),"MINTED_UNVERIFIED_AUTHORITY")

    def test_09_promote_first_response_to_dispatch_denied(self):
        self.fails(lambda d:d["answers"][0].__setitem__("claim_of_production_authority",True),"MINTED_UNVERIFIED_AUTHORITY")

    def test_10_fabricated_vendor_reply_without_reference_denied(self):
        self.fails(lambda d:d["answers"][0].__setitem__("response_state","ANSWERED_UNVERIFIED"),"PRIVATE_REFERENCE_REQUIRED")

    def test_11_vague_vendor_reply_with_date_but_no_reference_denied(self):
        def mod(d):
            d["answers"][0]["response_state"]="NEEDS_CLARIFICATION"
            d["answers"][0]["response_observed_at"]="2026-10-21"
        self.fails(mod,"PRIVATE_REFERENCE_REQUIRED")

    def test_12_candidate_reply_reference_still_never_grants_worker(self):
        def mod(d):
            d["answers"][0].update({
                "response_state":"ANSWERED_UNVERIFIED",
                "response_observed_at":"2026-10-21",
                "vendor_response_reference":"PRIVATE_RECORD:onesignal-engineering-response-ticket-reviewed-later",
            })
        result=self.verify(mod)
        self.assertEqual(result["pending"],33)
        self.assertEqual(result["vendor_answer_candidates_unverified"],1)
        self.assertFalse(result["external_proof_authenticated"])
        self.assertFalse(result["worker_allowed"])

    def test_13_email_address_or_raw_private_correspondence_not_embedded_in_github(self):
        def mod(d):
            d["answers"][0].update({
                "response_state":"ANSWERED_UNVERIFIED",
                "response_observed_at":"2026-10-21",
                "vendor_response_reference":"PRIVATE_RECORD:agent@example.com",
            })
        self.fails(mod,"PRIVATE_REFERENCE_REQUIRED")

    def test_14_user_tries_to_enable_retry_after_timeout_denied(self):
        self.fails(lambda d:d["governance"].__setitem__("auto_resend_enabled",True),"UNVERIFIED_PRODUCTION_AUTHORITY")

    def test_15_provider_unsigned_receipt_not_enough(self):
        self.fails(lambda d:d["governance"].__setitem__("provider_effect_receipt_authenticated",True),"UNVERIFIED_PRODUCTION_AUTHORITY")

    def test_16_local_no_effect_is_not_a_terminal_fence(self):
        self.fails(lambda d:d["governance"].__setitem__("terminal_no_effect_fenced",True),"UNVERIFIED_PRODUCTION_AUTHORITY")

    def test_17_custodian_not_verified_merely_by_cloud_account_name(self):
        self.fails(lambda d:d["governance"].__setitem__("independent_latest_head_witness_verified",True),"UNVERIFIED_PRODUCTION_AUTHORITY")

    def test_18_critical_h0_question_cannot_lose_gate_link(self):
        self.fails(lambda d:d["answers"][8].__setitem__("related_h0_producer_gate_classes",[]),"UNMAPPED_H0_BARRIER")

    def test_19_private_customer_phone_number_not_part_of_public_answer(self):
        def mod(d):
            d["answers"][0]["response_state"]="NOT_SUPPORTED"
            d["answers"][0]["response_observed_at"]="2026-10-21"
            d["answers"][0]["vendor_response_reference"]="PRIVATE_RECORD:5511999999999@example.com"
        self.fails(mod,"PRIVATE_REFERENCE_REQUIRED")

    def test_20_unsent_rfi_cannot_claim_dispatched_after_private_email(self):
        self.fails(lambda d:d.__setitem__("rfi_delivery_status","SENT_TO_VENDOR"),"FALSE_COMMUNICATION")

    def test_21_owner_challenge_not_authenticated_by_draft(self):
        self.fails(lambda d:d["governance"].__setitem__("owner_consent_authenticated",True),"UNVERIFIED_PRODUCTION_AUTHORITY")

    def test_22_85_quality_failures_still_open(self):
        self.fails(lambda d:d["governance"].__setitem__("quality_historical_85_waived",True),"UNVERIFIED_PRODUCTION_AUTHORITY")

    def test_23_any_claim_of_homologated_p0_denied(self):
        self.fails(lambda d:d["governance"].__setitem__("homologated_p0_count",1),"UNVERIFIED_PRODUCTION_AUTHORITY")

    def test_24_zero_spend_must_not_be_pretended_approved_purchase(self):
        self.fails(lambda d:d["governance"].__setitem__("approved_spend_brl",250),"UNVERIFIED_PRODUCTION_AUTHORITY")

    def test_25_no_unsent_disclosure_in_email_doc_denied(self):
        with self.assertRaisesRegex(IntakeError,"UNSENT_DISCLOSURE"):
            self.verify(document=self.doc.replace("(NOT SENT)","(DRAFT)"))

    def test_26_source_sha_binding_is_immutable(self):
        self.fails(lambda d:d.__setitem__("source_sha","0"*40),"SOURCE_PR_CHANGED")


if __name__=="__main__":
    unittest.main()
