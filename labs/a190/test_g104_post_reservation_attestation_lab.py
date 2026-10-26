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

    def test_12_post_commit_attestor_offline_spends_reservation_no_send(self):
        original = self.enroll_fixture()
        def missing_post(_challenge, _claimed):
            raise TimeoutError("G104_SYNTHETIC_POST_ACK_LOST")
        guard = self.make_guard(original, post_probe=missing_post)
        store, out, row = self.host(guard=guard)
        try:
            result, adapter = self.claim_and_send(out, row)
            self.assertEqual(result["state"], "UNCERTAIN")
            self.assertEqual(adapter.send_calls, 0)
            self.assertEqual(self.custody.snapshot()["count"], 1)
            self.assertEqual(self.remote_sequence["count"], 1)
        finally:
            store.close()
        print("G104_LOST_POST_ACK=SPENT_UNCERTAIN_ZERO_SEND")

    def test_13_validly_signed_wrong_effect_post_proof_denied(self):
        original = self.enroll_fixture()
        def wrong_effect(challenge, request):
            return self.proof_after(
                challenge, request, overrides={"effect_digest": "0" * 64},
            )
        guard = self.make_guard(original, post_probe=wrong_effect)
        self.assertFalse(guard(original))
        self.assertEqual(self.custody.snapshot()["count"], 1)
        print("G104_OTHER_EFFECT_POST_PROOF=DENIED")

    def test_14_wrong_post_commit_signer_denied(self):
        from labs.a190.test_g102_pinned_external_attestation_admission_lab import OTHER_PRIVATE
        original = self.enroll_fixture()
        def counterfeit(challenge, request):
            return self.proof_after(challenge, request, signer=OTHER_PRIVATE)
        guard = self.make_guard(original, post_probe=counterfeit)
        self.assertFalse(guard(original))
        self.assertEqual(self.custody.snapshot()["count"], 1)
        print("G104_UNPINNED_POST_SIGNER=DENIED")

    def test_15_replayed_post_challenge_denied(self):
        original = self.enroll_fixture()
        def old_challenge(_challenge, request):
            return self.proof_after("0" * 64, request)
        guard = self.make_guard(original, post_probe=old_challenge)
        self.assertFalse(guard(original))
        self.assertEqual(self.custody.snapshot()["count"], 1)
        print("G104_POST_PROOF_REPLAY=DENIED")

    def test_16_signed_wrong_sequence_denied(self):
        original = self.enroll_fixture()
        def wrong_sequence(challenge, request):
            return self.proof_after(
                challenge, request,
                overrides={"sequence": 2, "high_water": 2, "count": 2},
            )
        guard = self.make_guard(original, post_probe=wrong_sequence)
        self.assertFalse(guard(original))
        self.assertEqual(self.custody.snapshot()["count"], 1)
        print("G104_DIFFERENT_POST_ORDINAL=DENIED")

    def test_17_signed_other_idempotency_key_denied(self):
        original = self.enroll_fixture()
        def other_id(challenge, request):
            return self.proof_after(
                challenge, request, overrides={"idempotency_key": "0" * 64},
            )
        guard = self.make_guard(original, post_probe=other_id)
        self.assertFalse(guard(original))
        self.assertEqual(self.custody.snapshot()["count"], 1)
        print("G104_OTHER_REQUEST_POST_PROOF=DENIED")

    def test_18_missing_post_commit_attestation_callback_denies_enrollment(self):
        original = self.enroll_fixture()
        with self.assertRaisesRegex(
            TypeError, "G104_POST_COMMIT_ATTESTOR_REQUIRED",
        ):
            self.make_guard(original, post_probe=False)
        self.assertEqual(self.custody.snapshot()["count"], 0)
        print("G104_NO_POST_ATTESTOR=ENROLLMENT_DENIED")

    def test_19_signed_other_business_decision_denied(self):
        original = self.enroll_fixture()
        def other_decision(challenge, request):
            return self.proof_after(
                challenge, request, overrides={"decision_sha256": "0" * 64},
            )
        guard = self.make_guard(original, post_probe=other_decision)
        self.assertFalse(guard(original))
        self.assertEqual(self.custody.snapshot()["count"], 1)
        print("G104_OTHER_DECISION_POST_PROOF=DENIED")
