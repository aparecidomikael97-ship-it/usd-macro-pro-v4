"""G104 RED-first: a signed reservation must be witnessed AFTER commitment.

G102 can accept a correctly signed but locally produced reservation following a
valid preflight attestation, even if the separate 'external' observer never
records that effect. This is a synthetic negative proof, not an independent
custodian or production send authority.
"""
from labs.a190.test_g102_pinned_external_attestation_admission_lab import (
    G102PinnedExternalAdmission,
)


class G104PostReservationAdversarial(G102PinnedExternalAdmission):
    def test_11_local_signed_reservation_without_remote_commit_denied(self):
        original = self.enroll_fixture()
        # Current G102 accepts this real synthetic local reservation signed
        # with the pinned A181 fixture key. The synthetic out-of-band counter
        # is deliberately *not* advanced, creating a split view.
        guard = self.make_guard(original, reserve=self.custody.reserve)
        self.assertFalse(
            guard(original),
            "G104_UNMET: signed preflight alone does not authenticate "
            "that the subsequent reservation reached the external ledger",
        )
        # If reservation happened before the new postflight denial, never
        # auto-retry or claim it was rolled back: local custody is spent.
        self.assertEqual(self.custody.snapshot()["count"], 1)
        self.assertEqual(self.remote_sequence["count"], 0)
        print("G104_UNATTESTED_POST_RESERVATION=DENIED_NO_SEND")
