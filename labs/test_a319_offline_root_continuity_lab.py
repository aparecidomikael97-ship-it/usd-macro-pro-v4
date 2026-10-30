"""A319: fail-closed offline root rotation, real Ed25519, synthetic keys.

A successful signature check is never treated as evidence of an external
custodian, real authority or permission to resume/retry a real effect.
"""
import copy
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from labs.a317_detached_signed_intent_anchor_lab import encode, sha
from labs.a319_offline_root_continuity_lab import (
    SCHEMA, PREVIOUS_FIELDS, CANDIDATE_FIELDS,
    authorization_bytes, assess_offline_root_transition,
)


def pub(private):
    return private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()


class A319OfflineRootContinuityTests(unittest.TestCase):
    def setUp(self):
        self.old_signers = {
            "root-A-v4": Ed25519PrivateKey.generate(),
            "root-B-v4": Ed25519PrivateKey.generate(),
        }
        self.new_signers = {
            "root-A-v5": Ed25519PrivateKey.generate(),
            "root-B-v5": Ed25519PrivateKey.generate(),
        }
        self.old = {
            "schema": SCHEMA, "generation": 4,
            "roots": {k: pub(v) for k, v in self.old_signers.items()},
            "revoked_root_ids": [], "high_water_sequence": 10,
            "high_water_sha256": "a" * 64, "incident_epoch": 12,
        }
        self.old_digest = sha(encode(self.old))
        self.next = {
            **copy.deepcopy(self.old), "generation": 5,
            "roots": {k: pub(v) for k, v in self.new_signers.items()},
            "revoked_root_ids": sorted(self.old["roots"]),
            "previous_manifest_sha256": self.old_digest,
            "challenge_nonce": "c" * 64,
            "issued_at": 10000, "expires_at": 10100,
            "decision": "HOLD_ONLY",
        }
        self.resign()

    def resign(self):
        old_data = authorization_bytes(self.next, new_root=False)
        new_data = authorization_bytes(self.next, new_root=True)
        self.old_sig = {
            k: v.sign(old_data).hex() for k, v in self.old_signers.items()
        }
        self.new_sig = {
            k: v.sign(new_data).hex() for k, v in self.new_signers.items()
        }

    def assess(self, **kwargs):
        args = dict(
            previous_manifest=self.old, candidate_manifest=self.next,
            pinned_previous_digest=self.old_digest,
            old_root_signatures=self.old_sig,
            new_root_signatures=self.new_sig,
            expected_nonce="c" * 64, expected_incident_epoch=12,
            observed_clock_epoch=10050,
        )
        args.update(kwargs)
        return assess_offline_root_transition(**args)

    def assert_no_go(self, data):
        self.assertEqual(data["schema"], SCHEMA)
        self.assertTrue(data["research_only"])
        self.assertTrue(data["synthetic_only"])
        self.assertFalse(data["first_bootstrap_allowed"])
        self.assertFalse(data["out_of_band_reference_independently_authenticated"])
        self.assertFalse(data["old_root_custody_independently_attested"])
        self.assertFalse(data["new_root_custody_independently_attested"])
        self.assertFalse(data["revocation_source_independently_authenticated"])
        self.assertFalse(data["high_water_off_host_authenticated"])
        self.assertFalse(data["trusted_clock_attested"])
        self.assertFalse(data["real_provider_ack_attested"])
        self.assertFalse(data["independent_intent_custody_proven"])
        self.assertFalse(data["can_authorize_real_effect"])
        self.assertFalse(data["can_resume"])
        self.assertFalse(data["can_resend"])
        self.assertFalse(data["can_auto_retry"])
        self.assertEqual(data["automatic_retries"], 0)
        self.assertTrue(data["zero_auto_resend"])
        self.assertTrue(data["hard_no_go"])
        self.assertEqual(data["p0_homologated"], 0)
        self.assertTrue(data["no_worker_deploy_provider_orders"])
        self.assertFalse(data["new_paid_services"])

    def test_good_mathematical_rotation_cannot_create_external_custody(self):
        report = self.assess()
        self.assertEqual(
            report["status"], "LAB_MATH_CONTINUITY_VALID_NO_EXTERNAL_PIN"
        )
        self.assertEqual(report["old_valid_signatures"], 2)
        self.assertEqual(report["new_valid_signatures"], 2)
        self.assertTrue(report["mathematical_dual_quorum"])
        self.assert_no_go(report)

    def test_schema_is_strict_and_no_go_fields_can_be_injected(self):
        self.assertEqual(set(self.old), PREVIOUS_FIELDS)
        self.assertEqual(set(self.next), CANDIDATE_FIELDS)
        forged = dict(self.next, can_resume=True)
        response = self.assess(candidate_manifest=forged)
        self.assertIn("CANDIDATE_ROOT_MANIFEST_INVALID", response["issues"])
        self.assert_no_go(response)

    def test_first_bootstrap_without_old_pin_fails_closed(self):
        r = self.assess(previous_manifest=None, pinned_previous_digest=None)
        self.assertIn("PREVIOUS_ROOT_MANIFEST_INVALID_OR_UNTRUSTED", r["issues"])
        self.assert_no_go(r)

    def test_wrong_previously_pinned_digest_refused(self):
        r = self.assess(pinned_previous_digest="f" * 64)
        self.assertIn("PREVIOUS_PIN_OR_LINK_MISMATCH", r["issues"])
        self.assert_no_go(r)

    def test_candidate_cannot_replace_previous_digest_link(self):
        self.next["previous_manifest_sha256"] = "e" * 64
        self.resign()
        r = self.assess()
        self.assertIn("PREVIOUS_PIN_OR_LINK_MISMATCH", r["issues"])
        self.assert_no_go(r)

    def test_two_old_authorizers_are_both_required(self):
        r = self.assess(old_root_signatures={
            "root-A-v4": self.old_sig["root-A-v4"]
        })
        self.assertIn("OLD_EXACT_TWO_SIGNATURE_IDS_REQUIRED", r["issues"])
        self.assertIn("DUAL_QUORUM_NOT_MET", r["issues"])
        self.assert_no_go(r)

    def test_two_new_key_possessions_are_both_required(self):
        r = self.assess(new_root_signatures={
            "root-B-v5": self.new_sig["root-B-v5"]
        })
        self.assertIn("NEW_EXACT_TWO_SIGNATURE_IDS_REQUIRED", r["issues"])
        self.assert_no_go(r)

    def test_old_root_wrong_signature_is_rejected(self):
        fake = dict(self.old_sig, **{
            "root-A-v4": Ed25519PrivateKey.generate().sign(
                authorization_bytes(self.next, new_root=False)
            ).hex()
        })
        r = self.assess(old_root_signatures=fake)
        self.assertIn("OLD_SIGNATURE_UNVERIFIED", r["issues"])
        self.assert_no_go(r)

    def test_new_root_wrong_signature_is_rejected(self):
        fake = dict(self.new_sig)
        fake["root-A-v5"] = "0" * 128
        r = self.assess(new_root_signatures=fake)
        self.assertIn("NEW_SIGNATURE_UNVERIFIED", r["issues"])
        self.assert_no_go(r)

    def test_signature_domain_cannot_be_reused_between_roles(self):
        bad = {
            k: v.sign(authorization_bytes(self.next, new_root=False)).hex()
            for k, v in self.new_signers.items()
        }
        r = self.assess(new_root_signatures=bad)
        self.assertIn("NEW_SIGNATURE_UNVERIFIED", r["issues"])
        self.assert_no_go(r)

    def test_extra_unknown_old_signer_denied(self):
        r = self.assess(old_root_signatures=dict(
            self.old_sig, attacker="0" * 128
        ))
        self.assertIn("OLD_EXACT_TWO_SIGNATURE_IDS_REQUIRED", r["issues"])
        self.assert_no_go(r)

    def test_root_generation_replay_denied(self):
        self.next["generation"] = 4
        self.resign()
        r = self.assess()
        self.assertIn("ROOT_GENERATION_ROLLBACK_OR_GAP", r["issues"])
        self.assert_no_go(r)

    def test_root_generation_skip_denied(self):
        self.next["generation"] = 7
        self.resign()
        r = self.assess()
        self.assertIn("ROOT_GENERATION_ROLLBACK_OR_GAP", r["issues"])
        self.assert_no_go(r)

    def test_same_root_id_cannot_reappear_on_rotation(self):
        private = self.new_signers.pop("root-A-v5")
        self.new_signers["root-A-v4"] = private
        self.next["roots"] = {
            k: pub(v) for k, v in self.new_signers.items()
        }
        # Keep candidate structurally valid to isolate the cross-generation
        # root-ID reuse check; removing revocation remains a separate veto.
        self.next["revoked_root_ids"] = ["root-B-v4"]
        self.resign()
        r = self.assess()
        self.assertIn("ROOT_ID_REUSED_ON_ROTATION", r["issues"])
        self.assert_no_go(r)

    def test_same_public_key_cannot_reappear_with_new_name(self):
        self.new_signers["root-A-v5"] = self.old_signers["root-A-v4"]
        self.next["roots"] = {
            k: pub(v) for k, v in self.new_signers.items()
        }
        self.resign()
        r = self.assess()
        self.assertIn("ROOT_KEY_REUSED_ON_ROTATION", r["issues"])
        self.assert_no_go(r)

    def test_candidate_cannot_drop_required_revocations(self):
        self.next["revoked_root_ids"] = ["root-A-v4"]
        self.resign()
        r = self.assess()
        self.assertIn("REVOKED_ROOT_RESURRECTED_OR_NOT_REVOKED", r["issues"])
        self.assert_no_go(r)

    def test_older_revoked_root_ids_are_carried_forward(self):
        self.old["revoked_root_ids"] = ["pre-retired-A"]
        self.old_digest = sha(encode(self.old))
        self.next["previous_manifest_sha256"] = self.old_digest
        self.next["revoked_root_ids"] = sorted([
            "pre-retired-A", "root-A-v4", "root-B-v4"
        ])
        self.resign()
        r = self.assess()
        self.assertEqual(
            r["status"], "LAB_MATH_CONTINUITY_VALID_NO_EXTERNAL_PIN"
        )
        self.assert_no_go(r)

    def test_revoked_root_cannot_be_reintroduced_as_active(self):
        self.next["revoked_root_ids"] = ["root-A-v4", "root-B-v4",
                                         "root-A-v5"]
        self.resign()
        r = self.assess()
        self.assertIn("CANDIDATE_ROOT_MANIFEST_INVALID", r["issues"])
        self.assert_no_go(r)

    def test_local_high_water_sequence_rollback_is_denied(self):
        self.next["high_water_sequence"] = 9
        self.resign()
        r = self.assess()
        self.assertIn("HIGH_WATER_SEQUENCE_ROLLBACK", r["issues"])
        self.assert_no_go(r)

    def test_equal_high_water_with_changed_hash_is_denied(self):
        self.next["high_water_sha256"] = "d" * 64
        self.resign()
        r = self.assess()
        self.assertIn("HIGH_WATER_HASH_REPLACED", r["issues"])
        self.assert_no_go(r)

    def test_monotonic_high_water_claim_still_is_not_external_proof(self):
        self.next["high_water_sequence"] = 11
        self.next["high_water_sha256"] = "e" * 64
        self.resign()
        r = self.assess()
        self.assertTrue(r["mathematical_dual_quorum"])
        self.assertFalse(r["high_water_off_host_authenticated"])
        self.assert_no_go(r)

    def test_incident_epoch_reopen_not_accepted_without_authority(self):
        self.next["incident_epoch"] = 13
        self.resign()
        r = self.assess()
        self.assertIn("INCIDENT_EPOCH_ROLLBACK_OR_REOPEN", r["issues"])
        self.assert_no_go(r)

    def test_nonce_mismatch_is_denied(self):
        r = self.assess(expected_nonce="f" * 64)
        self.assertIn("CHALLENGE_NONCE_REPLAY_OR_MISMATCH", r["issues"])
        self.assert_no_go(r)

    def test_expired_rotation_is_denied(self):
        r = self.assess(observed_clock_epoch=10100)
        self.assertIn("ROTATION_STALE_OR_FUTURE", r["issues"])
        self.assert_no_go(r)

    def test_future_rotation_is_denied(self):
        r = self.assess(observed_clock_epoch=9999)
        self.assertIn("ROTATION_STALE_OR_FUTURE", r["issues"])
        self.assert_no_go(r)

    def test_too_long_validity_is_denied(self):
        self.next["expires_at"] = 11000
        self.resign()
        r = self.assess()
        self.assertIn("ROTATION_STALE_OR_FUTURE", r["issues"])
        self.assert_no_go(r)

    def test_invalid_schema_numbers_and_types_are_denied(self):
        for value in (True, 4.0, "4", None, -2):
            with self.subTest(value=repr(value)):
                bad = copy.deepcopy(self.next)
                bad["generation"] = value
                r = self.assess(candidate_manifest=bad)
                self.assertIn("CANDIDATE_ROOT_MANIFEST_INVALID", r["issues"])
                self.assert_no_go(r)

    def test_operational_decision_field_is_never_accepted(self):
        self.next["decision"] = "GO_DEPLOY"
        self.resign()
        r = self.assess()
        self.assertIn("CANDIDATE_ROOT_MANIFEST_INVALID", r["issues"])
        self.assert_no_go(r)

    def test_reused_root_key_within_candidate_fails_closed(self):
        self.next["roots"]["root-B-v5"] = self.next["roots"]["root-A-v5"]
        r = self.assess()
        self.assertIn("CANDIDATE_ROOT_MANIFEST_INVALID", r["issues"])
        self.assert_no_go(r)

    def test_untrusted_pinset_and_both_signers_can_be_reminted(self):
        """Key security counterexample: caller-controlled roots are not trust."""
        self.old_signers = {
            "evil-old-A": Ed25519PrivateKey.generate(),
            "evil-old-B": Ed25519PrivateKey.generate(),
        }
        self.new_signers = {
            "evil-new-A": Ed25519PrivateKey.generate(),
            "evil-new-B": Ed25519PrivateKey.generate(),
        }
        self.old["roots"] = {
            k: pub(v) for k, v in self.old_signers.items()
        }
        self.old_digest = sha(encode(self.old))
        self.next["roots"] = {
            k: pub(v) for k, v in self.new_signers.items()
        }
        self.next["revoked_root_ids"] = sorted(self.old["roots"])
        self.next["previous_manifest_sha256"] = self.old_digest
        self.resign()
        outcome = self.assess()
        self.assertEqual(
            outcome["status"], "LAB_MATH_CONTINUITY_VALID_NO_EXTERNAL_PIN"
        )
        self.assertTrue(outcome["mathematical_dual_quorum"])
        self.assertFalse(outcome["out_of_band_reference_independently_authenticated"])
        self.assert_no_go(outcome)

    def test_caller_can_alter_nonce_clock_and_head_and_remint(self):
        self.old["high_water_sequence"] = 0
        self.old["high_water_sha256"] = "0" * 64
        self.old_digest = sha(encode(self.old))
        self.next["previous_manifest_sha256"] = self.old_digest
        self.next["high_water_sequence"] = 0
        self.next["high_water_sha256"] = "0" * 64
        self.next["challenge_nonce"] = "e" * 64
        self.next["issued_at"] = 5000
        self.next["expires_at"] = 5100
        self.resign()
        r = self.assess(expected_nonce="e" * 64,
                        observed_clock_epoch=5050)
        self.assertTrue(r["mathematical_dual_quorum"])
        self.assertFalse(r["high_water_off_host_authenticated"])
        self.assertFalse(r["trusted_clock_attested"])
        self.assert_no_go(r)

    def test_duplicate_revoked_ids_and_unsorted_list_not_accepted(self):
        for item in (["root-A-v4", "root-A-v4"], ["root-B-v4", "root-A-v4"]):
            with self.subTest(item=item):
                forged = copy.deepcopy(self.next)
                forged["revoked_root_ids"] = item
                r = self.assess(candidate_manifest=forged)
                self.assertIn("CANDIDATE_ROOT_MANIFEST_INVALID", r["issues"])
                self.assert_no_go(r)


if __name__ == "__main__":
    unittest.main()
