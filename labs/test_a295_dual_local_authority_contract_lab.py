"""A295 LAB regressions: intent identity contract with two SAME-HOST signers."""
import time
import unittest

from labs.a295_dual_local_authority_contract_lab import (
    ACTION, ENVELOPE_FIELDS, SCHEMA, LocalDualSignerContract,
    intent_digest, validate_intent, probe_dual_contract_tamper_replay,
    probe_partial_signer_failure, probe_same_host_reset_bootstrap,
    probe_untrusted_approval_flag,
)


class A295QuorumIntentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = probe_dual_contract_tamper_replay()

    def test_two_local_pids_ack_bound_intent(self):
        self.assertTrue(self.data["first_quorum_accepted"])
        self.assertTrue(self.data["first_quorum_verified"])
        self.assertTrue(self.data["second_quorum_accepted"])
        self.assertTrue(self.data["second_quorum_verified"])

    def test_missing_second_approval_denied_before_any_signature(self):
        self.assertTrue(self.data["single_approval_denied"])

    def test_same_envelope_cannot_be_replayed_same_epoch(self):
        self.assertTrue(self.data["replayed_intent_denied"])
        self.assertTrue(self.data["nonce_reuse_denied"])
        self.assertTrue(self.data["semantic_duplicate_denied"])

    def test_intent_and_chain_tampering_denied(self):
        self.assertTrue(self.data["changed_payload_denied"])
        self.assertTrue(self.data["wrong_parent_denied"])
        self.assertTrue(self.data["old_receipt_stale"])

    def test_expired_approval_is_denied(self):
        self.assertTrue(self.data["expired_intent_denied"])

    def test_dual_local_quorum_never_homologates_p0(self):
        self.assertFalse(self.data["independent_real_owner_verified"])
        self.assertFalse(self.data["externally_durable_authority_epoch"])
        self.assertFalse(self.data["public_key_identity_attested"])
        self.assertFalse(self.data["can_authorize_real_effect"])
        self.assertEqual(self.data["p0_homologated"], 0)
        self.assertTrue(self.data["hard_no_go"])


class A295PartialSignatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = probe_partial_signer_failure()

    def test_partially_signed_outcome_is_unknown_and_denied(self):
        self.assertTrue(self.data["first_partial_denied"])
        self.assertTrue(self.data["owner_side_effect_may_have_occurred"])
        self.assertTrue(self.data["no_known_rollback_of_owner_signature"])

    def test_quorum_failure_sticky_zero_auto_resend(self):
        self.assertTrue(self.data["further_requests_sticky_denied"])
        self.assertTrue(self.data["zero_auto_resend"])


class A295HostCompromiseNegativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reset = probe_same_host_reset_bootstrap()
        cls.flags = probe_untrusted_approval_flag()

    def test_rebootstrap_reapproves_identical_intent_and_semantic_effect(self):
        self.assertTrue(self.reset["original_simulated_quorum_accepted"])
        self.assertTrue(self.reset["same_intent_reaccepted_after_host_reset"])
        self.assertTrue(self.reset["newly_reset_signers_approve_duplicate"])
        self.assertTrue(self.reset["old_and_new_receipts_differ"])
        self.assertTrue(self.reset["host_reset_breaks_independent_authority"])

    def test_old_receipt_cannot_cross_new_ephemeral_keys(self):
        self.assertTrue(self.reset["new_keys_reject_old_receipt"])

    def test_untrusted_local_boolean_cannot_prove_owner_consent(self):
        self.assertTrue(self.flags["structural_envelope_valid"])
        self.assertTrue(self.flags["fake_owner_scope_accepted_by_local_flags"])
        self.assertTrue(self.flags["fake_owner_verifies_with_same_host_children"])
        self.assertTrue(self.flags["real_owner_identity_not_authenticated"])


class A295SchemaAndInputTests(unittest.TestCase):
    def setUp(self):
        self.pair = LocalDualSignerContract()
        self.intent = self.pair.make_intent(
            payload_digest="a" * 64, history_digest="b" * 64
        )

    def tearDown(self):
        self.pair.close()

    def test_exact_schema_and_hash_stability(self):
        self.assertEqual(frozenset(self.intent), ENVELOPE_FIELDS)
        self.assertEqual(self.intent["schema"], SCHEMA)
        self.assertEqual(self.intent["action"], ACTION)
        self.assertTrue(validate_intent(self.intent))
        self.assertEqual(intent_digest(self.intent), intent_digest(dict(self.intent)))
        self.assertEqual(len(intent_digest(self.intent)), 64)

    def test_extra_or_missing_intent_field_fails_closed(self):
        for bad in (
            dict(self.intent, unexpected=True),
            {k: v for k, v in self.intent.items() if k != "intent_id"},
        ):
            with self.subTest(keys=frozenset(bad)):
                with self.assertRaises(ValueError):
                    validate_intent(bad)

    def test_digest_nonce_epoch_sequence_and_scope_validation(self):
        mutations = [
            {"payload_digest": "a"},
            {"history_digest": "g" * 64},
            {"nonce": "oops"},
            {"epoch": True},
            {"sequence": True},
            {"sequence": 0},
            {"scope": {"owner_id": "owner"}},
            {"scope": dict(self.intent["scope"], owner_id="")},
            {"action": "SEND_LIVE_ORDER"},
            {"previous_head": "bad"},
        ]
        for mutation in mutations:
            with self.subTest(mutation=repr(mutation)):
                with self.assertRaises(ValueError):
                    validate_intent(dict(self.intent, **mutation))

    def test_expiry_now_and_max_window(self):
        for when in (int(time.time()) - 1, int(time.time()) + 3600):
            with self.subTest(expires_at=when):
                with self.assertRaises(ValueError):
                    validate_intent(dict(self.intent, expires_at=when))

    def test_none_or_integer_approval_flags_are_denied(self):
        for owner,custodian in ((1, True), (True, 1), (None, True)):
            with self.subTest(owner=owner, custodian=custodian):
                outcome = self.pair.approve(
                    self.intent,
                    owner_approved=owner, custodian_approved=custodian,
                )
                self.assertFalse(outcome["ok"])
                self.assertEqual(outcome["reason"], "APPROVAL_FLAG_INVALID")

    def test_no_default_approval_or_production_action(self):
        response = self.pair.approve(self.intent)
        self.assertFalse(response["ok"])
        self.assertEqual(response["reason"], "SIMULATED_DUAL_APPROVAL_MISSING")

    def test_epoch_identity_is_local_and_invalid_input_is_rejected(self):
        for bad in ("", "not-hex", "g" * 32, 1):
            with self.subTest(epoch=bad):
                with self.assertRaises(ValueError):
                    LocalDualSignerContract(epoch=bad)


if __name__ == "__main__":
    unittest.main()
