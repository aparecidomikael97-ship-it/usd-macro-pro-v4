"""P0 H0 provider evidence crosswalk negative and provenance regressions.

All fixture evidence is synthetic for negative testing; positive result means
only the INVENTORY is structurally correct, never an external authorization.
"""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from aion_p0_h0_provider_32_crosswalk_audit import (  # noqa: E402
    CrosswalkError, audit, load,
)


class Provider32CurrentQualityCrosswalkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proposal,cls.current,cls.historical=load()

    def check(self,proposal=None,current=None,historical=None):
        return audit(
            deepcopy(self.proposal if proposal is None else proposal),
            deepcopy(self.current if current is None else current),
            deepcopy(self.historical if historical is None else historical),
        )

    def test_01_exact_32_matches_6895_current_run(self):
        result=self.check()
        self.assertEqual(result["matched_32_provider_errors"],32)
        self.assertEqual(result["current_quality_tests"],6895)
        self.assertEqual(result["historical_quality_tests"],6562)
        self.assertEqual(result["verdict"],"HARD_NO_GO_EXTERNAL_EVIDENCE_MISSING")
        self.assertFalse(result["worker_allowed"])
        self.assertFalse(result["automatic_resend_allowed"])

    def test_02_all_three_external_gate_categories_are_preserved(self):
        self.assertEqual(self.check()["gates"],{
            "PRE_ADAPTER_PRODUCER_ENROLLMENT":23,
            "CAUSAL_COMMITTED_EFFECT_RECEIPT":8,
            "TERMINAL_NO_EFFECT_FENCE":1,
        })

    def test_03_deleted_case_cannot_be_passed_over(self):
        case=deepcopy(self.proposal)
        case["cases"].pop()
        with self.assertRaisesRegex(CrosswalkError,"ONE_TO_ONE"):
            self.check(proposal=case)

    def test_04_duplicate_case_cannot_be_passed_over(self):
        case=deepcopy(self.proposal)
        case["cases"].append(case["cases"][0])
        with self.assertRaisesRegex(CrosswalkError,"ONE_TO_ONE"):
            self.check(proposal=case)

    def test_05_current_exception_change_requires_review(self):
        current=deepcopy(self.current)
        t=next(x for x in current["entries"] if x["family"]=="INDEPENDENT_PRODUCER_GATE")
        t["observed_exception"]="PermissionError: SOMETHING_ELSE"
        with self.assertRaisesRegex(CrosswalkError,"CASE_OR_PROOF_DRIFT"):
            self.check(current=current)

    def test_06_observed_old_gate_tampered_cannot_be_accepted(self):
        corrupt=deepcopy(self.historical)
        corrupt["cases"][0]["observed_gate"]="CAUSAL_COMMITTED_EFFECT_RECEIPT"
        with self.assertRaisesRegex(CrosswalkError,"CASE_OR_PROOF_DRIFT"):
            self.check(historical=corrupt)

    def test_07_current_source_sha_cannot_be_swapped(self):
        proposed=deepcopy(self.proposal)
        proposed["sources"]["current_quality_sha"]="0"*40
        with self.assertRaisesRegex(CrosswalkError,"PROVENANCE_MISMATCH"):
            self.check(proposal=proposed)

    def test_08_current_quality_test_count_cannot_be_replaced_by_old(self):
        proposed=deepcopy(self.proposal)
        proposed["sources"]["verified_current_quality_tests"]=6562
        with self.assertRaisesRegex(CrosswalkError,"PROVENANCE_MISMATCH"):
            self.check(proposal=proposed)

    def test_09_claim_of_enrolled_external_producer_denied(self):
        proposed=deepcopy(self.proposal)
        proposed["authority"]["producer_enrolled_independently"]=True
        with self.assertRaisesRegex(CrosswalkError,"UNVERIFIED_AUTHORITY"):
            self.check(proposal=proposed)

    def test_10_fake_successful_provider_receipt_cannot_promote_authority(self):
        proposed=deepcopy(self.proposal)
        proposed["authority"]["external_receipt_authenticated"]=True
        with self.assertRaisesRegex(CrosswalkError,"UNVERIFIED_AUTHORITY"):
            self.check(proposal=proposed)

    def test_11_claim_of_no_effect_fence_denied(self):
        proposed=deepcopy(self.proposal)
        proposed["authority"]["external_no_effect_fence_verified"]=True
        with self.assertRaisesRegex(CrosswalkError,"UNVERIFIED_AUTHORITY"):
            self.check(proposal=proposed)

    def test_12_twilio_classic_cannot_be_relabelled_go(self):
        proposed=deepcopy(self.proposal)
        proposed["provider_assessment"]["status"]="GO"
        with self.assertRaisesRegex(CrosswalkError,"VENDOR_NO_GO"):
            self.check(proposal=proposed)

    def test_13_twilio_conversations_cannot_be_confused_with_classic_message_post(self):
        proposed=deepcopy(self.proposal)
        proposed["provider_assessment"]["endpoint"]="Twilio Conversations/Orchestrator"
        with self.assertRaisesRegex(CrosswalkError,"VENDOR_NO_GO"):
            self.check(proposal=proposed)

    def test_14_404_list_timeout_cannot_be_negative_fence(self):
        proposed=deepcopy(self.proposal)
        terminal=next(x for x in proposed["gate_requirements"] if x["gate"]=="TERMINAL_NO_EFFECT_FENCE")
        terminal["cannot_substitute"]=["synthetic_receipt"]
        with self.assertRaisesRegex(CrosswalkError,"FALSE_NEGATIVE"):
            self.check(proposal=proposed)

    def test_15_allowing_automatic_resend_denied_even_if_matrix_still_red(self):
        proposed=deepcopy(self.proposal)
        proposed["authority"]["automatic_resend_allowed"]=True
        with self.assertRaisesRegex(CrosswalkError,"UNVERIFIED_AUTHORITY"):
            self.check(proposal=proposed)

    def test_16_all_evidence_still_incomplete_and_no_p0_homologated(self):
        result=self.check()
        self.assertFalse(result["evidence_complete"])
        self.assertFalse(result["identity_independently_enrolled"])
        self.assertFalse(result["provider_receipt_authentic"])
        self.assertFalse(result["terminal_no_effect_fenced"])
        self.assertEqual(result["homologated_p0_count"],0)


if __name__=="__main__":
    unittest.main()
