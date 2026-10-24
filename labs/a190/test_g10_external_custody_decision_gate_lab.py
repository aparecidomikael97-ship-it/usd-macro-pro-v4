"""A190 G10 documentary gate invariants: features/price never authorize effect."""
import unittest

from g10_external_custody_decision_gate_lab import (
    CANDIDATES, REQUIRED_EXTERNAL_PROOFS, assess, budget_preflight,
)


class G10ExternalCustodyDecisionGate(unittest.TestCase):
    def test_01_every_documented_candidate_still_hard_no_go(self):
        self.assertEqual(4, len(CANDIDATES))
        for name in CANDIDATES:
            with self.subTest(candidate=name):
                result = assess(name)
                self.assertEqual("HARD_NO_GO", result["decision"])
                self.assertEqual(0, result["p0_homologated"])
                self.assertFalse(result["effect_allowed"])
                self.assertFalse(result["owner_approval"])
        print("A190_G10_ALL_DOCUMENTED_OPTIONS=HARD_NO_GO_NO_PROVIDER_CHOSEN")

    def test_02_cloudflare_pitr_and_worker_admin_not_independent(self):
        blockers = assess("cloudflare_do_sqlite")["known_blockers"]
        self.assertIn("PITR_SUPPORTS_RESTORING_PRIOR_STATE", blockers)
        self.assertIn("ACCOUNT_WORKER_ADMIN_CAN_MODIFY_DATA", blockers)
        print("A190_G10_CLOUDFLARE_PITR_AND_ADMIN_BOUNDARY=RED_EXTERNAL_FLOOR_NOT_PROVEN")

    def test_03_dynamodb_conditional_write_not_real_effect(self):
        outcome = assess("aws_dynamodb_conditional")
        self.assertIn("CONDITIONAL_WRITE",
                      outcome["documented_capabilities_not_evidence"])
        self.assertEqual("NOT_PROVIDER_EFFECT_PROOF",
                         outcome["on_read_only_reservation"])
        self.assertFalse(outcome["effect_allowed"])
        print("A190_G10_DYNAMODB_CONDITIONAL_WRITE_NOT_VENDOR_EFFECT=DENY")

    def test_04_firestore_precondition_not_independent_owner(self):
        outcome = assess("google_firestore")
        self.assertIn("EXISTS_FALSE_PRECONDITION",
                      outcome["documented_capabilities_not_evidence"])
        self.assertIn(
            "ACCOUNT_ADMIN_CAN_CHANGE_OR_REMOVE_RECORDS",
            outcome["known_blockers"],
        )
        print("A190_G10_FIRESTORE_EXISTS_FALSE_NO_INDEPENDENT_ROOT=DENY")

    def test_05_supabase_free_pause_not_h0_floor(self):
        blockers = assess("supabase_free")["known_blockers"]
        self.assertIn("FREE_PROJECT_INACTIVITY_PAUSE", blockers)
        self.assertIn("FREE_NO_AUTOMATIC_BACKUPS_OR_UPTIME_SLA", blockers)
        print("A190_G10_SUPABASE_FREE_H0_AVAILABILITY=NOT_PROVEN")

    def test_06_all_fake_user_claims_still_cannot_upgrade_root(self):
        fake = {k: {
            "status": "ALL_PASS",
            "evidence_uri": "https://attacker.invalid/self-certified",
            "signed_by": "same_host_root",
        } for k in REQUIRED_EXTERNAL_PROOFS}
        outcome = assess("aws_dynamodb_conditional", fake)
        self.assertEqual(len(REQUIRED_EXTERNAL_PROOFS),
                         len(outcome["unverifiable_self_claims_present"]))
        self.assertEqual(0, outcome["externally_proven_gates"])
        self.assertEqual("HARD_NO_GO", outcome["decision"])
        print("A190_G10_FORGED_SELF_ATTESTED_ALL_EXTERNAL_GATES=NO_GO")

    def test_07_unknown_provider_and_unsupported_input_deny(self):
        outcome = assess("imaginary_vendor_with_best_marketing", {})
        self.assertEqual("HARD_NO_GO", outcome["decision"])
        self.assertEqual("UNRECOGNIZED_CANDIDATE", outcome["reason"])
        self.assertFalse(outcome["effect_allowed"])
        print("A190_G10_UNKNOWN_VENDOR=DENY")

    def test_08_no_price_or_fx_and_taxes_no_provisioning(self):
        result = budget_preflight(existing_brl=80, new_usd=5)
        self.assertEqual("UNKNOWN_DENY_PROVISIONING", result["status"])
        self.assertFalse(result["owner_approval"])
        print("A190_G10_UNKNOWN_FX_BILL_TAX=DENY_PROVISIONING")

    def test_09_over_budget_and_250_exception_not_automatic(self):
        over = budget_preflight(
            existing_brl="185", new_usd="5", effective_fx="6",
            tax_brl="3",
        )
        self.assertEqual("OVER_LIMIT_DENY_PROVISIONING", over["status"])
        self.assertEqual("218", over["estimated_total_brl"])
        self.assertFalse(over["owner_approval"])
        # Higher exceptional limit still needs express owner approval.
        under_exception = budget_preflight(
            existing_brl="185", new_usd="5", effective_fx="6",
            tax_brl="3", cap_brl="250",
        )
        self.assertEqual("WITHIN_ESTIMATE_STILL_NOT_AUTHORIZED",
                         under_exception["status"])
        self.assertFalse(under_exception["owner_approval"])
        print("A190_G10_R200_CAP_AND_R250_EXCEPTION=OWNER_APPROVAL_REQUIRED")

    def test_10_affordable_scenario_still_hard_no_go(self):
        result = assess("cloudflare_do_sqlite", cost={
            "existing_brl": "20", "new_usd": "0",
            "effective_fx": "5", "tax_brl": "0",
        })
        self.assertEqual("WITHIN_ESTIMATE_STILL_NOT_AUTHORIZED",
                         result["budget"]["status"])
        self.assertEqual("HARD_NO_GO", result["decision"])
        self.assertFalse(result["effect_allowed"])
        print("A190_G10_ZERO_COST_DOES_NOT_PROVE_INDEPENDENT_ROOT=DENY")

    def test_11_h0_and_ack_uncertainty_stay_fail_closed(self):
        for name in CANDIDATES:
            result = assess(name)
            self.assertEqual("DENY_NEW_EFFECT",
                             result["on_authority_unavailable"])
            self.assertEqual("UNCERTAIN_ZERO_AUTO_RESEND",
                             result["on_ack_uncertain"])
            self.assertFalse(result["auto_resend"])
        print("A190_G10_H0_AUTHORITY_ABSENT=DENY_AND_ZERO_AUTO_RESEND")

    def test_12_no_expensive_or_invalid_budget_arithmetic_bypass(self):
        for candidate in ("NaN", "-5", "Infinity", "", None, True):
            result = budget_preflight(
                existing_brl=candidate, new_usd="0", effective_fx="5",
                tax_brl="0",
            )
            self.assertEqual("UNKNOWN_DENY_PROVISIONING", result["status"])
        print("A190_G10_INVALID_FINOPS_INPUT=FAIL_CLOSED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
