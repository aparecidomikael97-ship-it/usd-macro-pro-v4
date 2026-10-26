"""G124 LAB-only composition of G120 owner proof and G119 provider claim.

This is a bridge regression for two formerly sibling Draft histories.
A valid synthetic owner approval may reserve ONE first attempt, but a
synthetic provider statement cannot prove a real effect, authorize retry,
or convert the witness reservation to real provider confirmation.
All keys and roots here are host-controlled fixtures. No live SEND.
"""
from hashlib import sha256

from labs.a190.test_g119_provider_evidence_separate_root_lab import (
    G119ProviderStatementTests,
)


class G124OwnerProviderCompositionTests(G119ProviderStatementTests):
    def test_24_original_owner_proof_then_witness_then_provider_claim_stays_unknown(self):
        # The G120 guard requires a separately signed, event-bound owner
        # enrollment BEFORE its G114 witness first-reservation action.
        guard = self.guard_for()
        self.assertTrue(guard(self.original_row))
        status = self.client.status(self.business_event_id)
        self.assertEqual(status["status"], "RESERVED")
        self.assertEqual(status["count"], 1)
        self.assertEqual(status["sequence"], 1)

        # A third synthetic key can prove only integrity of a test claim.
        # Even EXECUTED cannot mean a real provider executed an effect.
        verifier = self.verifier(floor=1)
        statement = self.sign(verifier.challenge(), claim="EXECUTED")
        assessed = verifier.inspect_statement(statement)
        self.assertTrue(assessed.signed_statement)
        self.assertEqual(assessed.provider_claim, "EXECUTED")
        self.assert_no_operational_permission(assessed)

        # Once spent, the same first-attempt guard cannot reopen admission.
        self.assertFalse(guard(self.original_row))
        self.assertEqual(self.client.status(self.business_event_id)["count"], 1)
        print("G124_OWNER_APPROVED_ONE_RESERVATION_PROVIDER_EXECUTED_STILL_UNKNOWN")

    def test_25_missing_owner_proof_cannot_be_repaired_by_provider_statement(self):
        # This test witness is enrolled, but no original owner proof exists.
        with self.assertRaisesRegex(ValueError, "G120_OWNER_ENROLLMENT_"):
            self.guard_for(owner_receipt={})
        self.assertEqual(self.client.status(self.business_event_id)["count"], 0)

        verifier = self.verifier(floor=0)
        claimed = verifier.inspect_statement(
            self.sign(verifier.challenge(), claim="EXECUTED")
        )
        self.assertEqual(
            claimed.disposition, "G119_WITNESS_RESERVATION_NOT_VERIFIED"
        )
        self.assert_no_operational_permission(claimed)
        print("G124_NO_OWNER_PROOF_PROVIDER_CLAIM_CANNOT_AUTHORIZE")

    def test_26_reenrolled_business_identity_cannot_borrow_owner_or_provider_claim(self):
        # The same machine can create an additional witness enrollment,
        # but the existing signed owner proof is bound to one event_id.
        invented = sha256(b"g124-reenrollment-same-original").hexdigest()
        self.assertEqual(
            self.client.enroll_synthetic_only(
                **{**self.enrollment, "event_id": invented}
            ), "ENROLLED",
        )
        with self.assertRaisesRegex(
            ValueError, "G120_OWNER_ENROLLMENT_EVENT_MISMATCH"
        ):
            self.guard_for(event=invented)
        self.assertEqual(self.client.status(invented)["count"], 0)

        # A provider-like statement is still scoped to the ORIGINAL event,
        # and without its reservation it cannot bootstrap a new admission.
        verifier = self.verifier(floor=0)
        assessed = verifier.inspect_statement(
            self.sign(verifier.challenge(), claim="EXECUTED")
        )
        self.assert_no_operational_permission(assessed)
        self.assertEqual(self.client.status(invented)["count"], 0)
        print("G124_NEW_EVENT_REENROLLMENT_ZERO_RESERVATION_NO_PROVIDER_GO")


if __name__ == "__main__":
    import unittest
    unittest.main()
