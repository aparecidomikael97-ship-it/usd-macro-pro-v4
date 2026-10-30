"""A322 LAB: deterministic public genesis card, 2-copy digest checks, costs.

All references are invented here. A matching pair of synthetic copies
is NOT proof of two external custodians or an immutable high-water.
"""
import copy
import unittest

from labs.a317_detached_signed_intent_anchor_lab import encode, sha
from labs.a319_offline_root_continuity_lab import SCHEMA as A319_SCHEMA
from labs.a322_genesis_out_of_band_handoff_lab import (
    SCHEMA, CARD_FIELDS, COPY_FIELDS, GENESIS_PROFILE,
    generate_genesis_card, verify_declared_genesis_handoff,
    assess_low_cost_custody_profile,
)


class A322GenesisPinHandoffTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {
            "schema": A319_SCHEMA,
            "generation": 3,
            "roots": {
                "fixture-root-A": "1" * 64,
                "fixture-root-B": "2" * 64,
            },
            "revoked_root_ids": [],
            "high_water_sequence": 7,
            "high_water_sha256": "a" * 64,
            "incident_epoch": 4,
        }
        self.card = generate_genesis_card(
            public_manifest=self.manifest,
            ceremony_id="a322-synthetic-genesis",
        )
        self.copies = self.make_copies()

    def make_copies(self):
        card_sha = sha(encode(self.card))
        return [
            {
                "card_sha256": card_sha,
                "copy_id": "copy-A",
                "claimed_custodian_id": "human-A",
                "claimed_admin_domain": "admin-domain-A",
                "claimed_account_id": "account-A",
                "claimed_device_id": "device-A",
                "claimed_recovery_domain": "recovery-A",
                "claimed_delivery_channel": "manual-channel-A",
                "claimed_retained_at": 1000,
                "decision": "OBSERVED_ONLY",
            },
            {
                "card_sha256": card_sha,
                "copy_id": "copy-B",
                "claimed_custodian_id": "human-B",
                "claimed_admin_domain": "admin-domain-B",
                "claimed_account_id": "account-B",
                "claimed_device_id": "device-B",
                "claimed_recovery_domain": "recovery-B",
                "claimed_delivery_channel": "manual-channel-B",
                "claimed_retained_at": 1001,
                "decision": "OBSERVED_ONLY",
            },
        ]

    def run_handoff(self, **extra):
        options = {
            "public_manifest": self.manifest,
            "genesis_card": self.card,
            "custody_copies": self.copies,
        }
        options.update(extra)
        return verify_declared_genesis_handoff(**options)

    def assert_never_authorize(self, value):
        self.assertEqual(value["schema"], SCHEMA)
        self.assertTrue(value["research_only"])
        self.assertTrue(value["synthetic_only"])
        self.assertFalse(value["bootstrap_independently_authenticated"])
        self.assertFalse(value["actual_custodian_identities_authenticated"])
        self.assertFalse(value["actual_admin_domain_separation_verified"])
        self.assertFalse(value["out_of_band_delivery_verified"])
        self.assertFalse(value["off_host_immutable_high_water_verified"])
        self.assertFalse(value["real_external_source_consulted"])
        self.assertFalse(value["external_provider_ack_verified"])
        self.assertFalse(value["automatic_effect_reconciliation_verified"])
        self.assertFalse(value["can_authorize_real_effect"])
        self.assertFalse(value["can_resume"])
        self.assertFalse(value["can_resend"])
        self.assertFalse(value["can_auto_retry"])
        self.assertEqual(value["automatic_retries"], 0)
        self.assertTrue(value["zero_auto_resend"])
        self.assertTrue(value["hard_no_go"])
        self.assertEqual(value["p0_homologated"], 0)
        self.assertTrue(value["no_worker_deploy_provider_orders"])
        self.assertFalse(value["new_paid_services"])

    def assert_veto(self, value, issue):
        self.assertEqual(value["status"], "LAB_GENESIS_HANDOFF_VETO")
        self.assertIn(issue, value["issues"])
        self.assert_never_authorize(value)

    def test_public_card_is_deterministic_and_never_pinned_as_trust(self):
        fresh = generate_genesis_card(
            public_manifest=self.manifest,
            ceremony_id="a322-synthetic-genesis",
        )
        self.assertEqual(self.card, fresh)
        self.assertEqual(set(self.card), CARD_FIELDS)
        self.assertEqual(self.card["manifest_sha256"], sha(encode(self.manifest)))
        self.assertEqual(self.card["decision"], "HOLD_ONLY")

    def test_public_card_has_full_hash_and_short_manual_fingerprint(self):
        digest = self.card["manifest_sha256"]
        self.assertEqual(len(digest), 64)
        self.assertEqual(len(self.card["fingerprint"].split("-")), 8)
        self.assertEqual(self.card["fingerprint"].replace("-", ""), digest[:32])

    def test_two_claimed_copies_match_without_independent_custody(self):
        result = self.run_handoff()
        self.assertEqual(result["status"], "LAB_HANDOFF_COPIES_MATCH_UNATTESTED")
        self.assertEqual(result["matched_copies"], 2)
        self.assertTrue(result["two_claimed_separate_custody_paths_consistent"])
        self.assertTrue(result["full_manifest_digest_compared"])
        self.assert_never_authorize(result)

    def test_copy_schema_is_strict(self):
        for c in self.copies:
            self.assertEqual(set(c), COPY_FIELDS)

    def test_one_copy_does_not_count_as_two(self):
        self.assert_veto(
            self.run_handoff(custody_copies=self.copies[:1]),
            "TWO_CUSTODY_COPIES_REQUIRED",
        )

    def test_three_copies_are_not_a_valid_two_custodian_ceremony(self):
        copies = self.copies + [copy.deepcopy(self.copies[0])]
        self.assert_veto(
            self.run_handoff(custody_copies=copies),
            "TWO_CUSTODY_COPIES_REQUIRED",
        )

    def test_missing_card_is_denied(self):
        self.assert_veto(
            self.run_handoff(genesis_card=None), "GENESIS_CARD_NOT_CANONICAL"
        )

    def test_unknown_card_field_is_denied(self):
        card = dict(self.card, operational_ready=True)
        self.assert_veto(
            self.run_handoff(genesis_card=card), "GENESIS_CARD_NOT_CANONICAL"
        )

    def test_wrong_card_decision_is_denied(self):
        card = dict(self.card, decision="GO_DEPLOY")
        self.assert_veto(
            self.run_handoff(genesis_card=card), "GENESIS_CARD_NOT_CANONICAL"
        )

    def test_short_display_fingerprint_tamper_is_denied(self):
        card = dict(self.card, fingerprint="0" * 32)
        self.assert_veto(
            self.run_handoff(genesis_card=card), "GENESIS_CARD_NOT_CANONICAL"
        )

    def test_public_manifest_tampered_but_old_card_is_rejected(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["high_water_sequence"] = 0
        result = self.run_handoff(public_manifest=manifest)
        self.assert_veto(result, "CARD_NOT_BOUND_TO_CURRENT_MANIFEST")

    def test_new_root_key_requires_new_card_even_if_root_names_match(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["roots"]["fixture-root-A"] = "f" * 64
        self.assert_veto(
            self.run_handoff(public_manifest=manifest),
            "CARD_NOT_BOUND_TO_CURRENT_MANIFEST",
        )

    def test_fake_local_card_hash_is_detected(self):
        copies = copy.deepcopy(self.copies)
        copies[0]["card_sha256"] = "f" * 64
        self.assert_veto(
            self.run_handoff(custody_copies=copies),
            "RETAINED_COPY_DIGEST_MISMATCH",
        )

    def test_both_copies_of_wrong_card_are_not_a_proof(self):
        copies = copy.deepcopy(self.copies)
        for item in copies:
            item["card_sha256"] = "0" * 64
        self.assert_veto(
            self.run_handoff(custody_copies=copies),
            "RETAINED_COPY_DIGEST_MISMATCH",
        )

    def test_two_copies_from_same_administrator_are_refused(self):
        copies = copy.deepcopy(self.copies)
        copies[1]["claimed_admin_domain"] = copies[0]["claimed_admin_domain"]
        self.assert_veto(
            self.run_handoff(custody_copies=copies),
            "ADMIN_DOMAIN_REUSED",
        )

    def test_two_accounts_with_same_recovery_owner_are_refused(self):
        copies = copy.deepcopy(self.copies)
        copies[1]["claimed_recovery_domain"] = copies[0]["claimed_recovery_domain"]
        self.assert_veto(
            self.run_handoff(custody_copies=copies),
            "RECOVERY_DOMAIN_REUSED",
        )

    def test_two_copies_from_same_login_are_refused(self):
        copies = copy.deepcopy(self.copies)
        copies[1]["claimed_account_id"] = copies[0]["claimed_account_id"]
        self.assert_veto(
            self.run_handoff(custody_copies=copies),
            "ACCOUNT_ID_REUSED",
        )

    def test_same_device_is_not_separate_custody(self):
        copies = copy.deepcopy(self.copies)
        copies[1]["claimed_device_id"] = copies[0]["claimed_device_id"]
        self.assert_veto(
            self.run_handoff(custody_copies=copies),
            "DEVICE_ID_REUSED",
        )

    def test_same_delivery_channel_is_not_separate_custody(self):
        copies = copy.deepcopy(self.copies)
        copies[1]["claimed_delivery_channel"] = copies[0]["claimed_delivery_channel"]
        self.assert_veto(
            self.run_handoff(custody_copies=copies),
            "DELIVERY_CHANNEL_REUSED",
        )

    def test_duplicate_copy_identifier_is_refused(self):
        copies = copy.deepcopy(self.copies)
        copies[1]["copy_id"] = copies[0]["copy_id"]
        self.assert_veto(self.run_handoff(custody_copies=copies), "COPY_ID_REUSED")

    def test_duplicate_custodian_identity_is_refused(self):
        copies = copy.deepcopy(self.copies)
        copies[1]["claimed_custodian_id"] = copies[0]["claimed_custodian_id"]
        self.assert_veto(self.run_handoff(custody_copies=copies), "CUSTODIAN_ID_REUSED")

    def test_copy_can_never_insert_go_fields(self):
        copies = copy.deepcopy(self.copies)
        copies[1]["can_resend"] = True
        self.assert_veto(
            self.run_handoff(custody_copies=copies),
            "CUSTODY_COPY_SHAPE_INVALID",
        )

    def test_copy_go_decision_refused(self):
        copies = copy.deepcopy(self.copies)
        copies[1]["decision"] = "GO"
        self.assert_veto(
            self.run_handoff(custody_copies=copies),
            "CUSTODY_COPY_SHAPE_INVALID",
        )

    def test_bad_timestamp_type_is_refused(self):
        copies = copy.deepcopy(self.copies)
        copies[1]["claimed_retained_at"] = True
        self.assert_veto(
            self.run_handoff(custody_copies=copies),
            "CUSTODY_COPY_SHAPE_INVALID",
        )

    def test_manifest_not_public_or_noncanonical_is_refused(self):
        for item in (None, [], {}, "root", dict(self.manifest, private_key="secret")):
            with self.subTest(value=repr(item)):
                self.assert_veto(
                    self.run_handoff(public_manifest=item),
                    "ROOT_MANIFEST_NOT_CANONICAL",
                )

    def test_generator_refuses_bad_id_and_nonpublic_manifest(self):
        for item in (None, True, {}, "", "a b", "x" * 81):
            with self.subTest(value=repr(item)):
                with self.assertRaises(ValueError):
                    generate_genesis_card(
                        public_manifest=self.manifest, ceremony_id=item,
                    )
        with self.assertRaises(ValueError):
            generate_genesis_card(
                public_manifest=dict(self.manifest, secret_key="x"),
                ceremony_id="synthetic",
            )

    def test_attacker_can_remint_manifest_card_and_both_local_copies(self):
        """Main negative: all math passes, but no actual external custody."""
        self.manifest["high_water_sequence"] = 0
        self.manifest["high_water_sha256"] = "0" * 64
        self.manifest["roots"] = {
            "fictional-new-A": "e" * 64,
            "fictional-new-B": "d" * 64,
        }
        self.card = generate_genesis_card(
            public_manifest=self.manifest,
            ceremony_id="attacker-synthetic-root",
        )
        self.copies = self.make_copies()
        observed = self.run_handoff()
        self.assertEqual(
            observed["status"], "LAB_HANDOFF_COPIES_MATCH_UNATTESTED"
        )
        self.assertTrue(observed["two_claimed_separate_custody_paths_consistent"])
        self.assertFalse(observed["bootstrap_independently_authenticated"])
        self.assert_never_authorize(observed)

    def test_manual_two_custodians_profile_no_required_vendor_fee(self):
        report = assess_low_cost_custody_profile(
            "two_human_offline_custodians"
        )
        self.assertEqual(
            report["status"], "LAB_PRACTICAL_OFFLINE_PILOT_NO_AUTOMATION"
        )
        self.assertIs(report["recurring_vendor_required_by_design"], False)
        self.assertTrue(report["recommended_now"])
        self.assertFalse(report["can_support_unattended_effect_approval"])
        self.assert_never_authorize(report)

    def test_managed_append_only_option_requires_review_not_assumed_free(self):
        report = assess_low_cost_custody_profile(
            "two_separately_administered_append_only_witnesses"
        )
        self.assertEqual(
            report["status"], "LAB_ARCHITECTURE_CANDIDATE_NOT_PROVISIONED"
        )
        self.assertIsNone(report["recurring_vendor_required_by_design"])
        self.assertFalse(report["recommended_now"])
        self.assertFalse(report["can_support_unattended_effect_approval"])
        self.assert_never_authorize(report)

    def test_single_owner_cloud_and_local_is_not_external_independence(self):
        report = assess_low_cost_custody_profile(
            "same_owner_cloud_or_local_copies"
        )
        self.assertEqual(
            report["status"], "LAB_SHARED_CONTROL_FAILURE_DOMAIN_VETO"
        )
        self.assertIn(
            "SAME_OWNER_CAN_REPLACE_PIN_AND_HISTORY", report["issues"]
        )
        self.assert_never_authorize(report)

    def test_unknown_profile_never_creates_configuration(self):
        for value in ("", "cloud", None, 0, True, {}):
            with self.subTest(profile=repr(value)):
                report = assess_low_cost_custody_profile(value)
                self.assertEqual(report["status"], "LAB_PROFILE_UNKNOWN_VETO")
                self.assertFalse(report["recommended_now"])
                self.assert_never_authorize(report)

    def test_strategy_catalog_is_bounded_and_no_automatic_go(self):
        self.assertEqual(len(GENESIS_PROFILE), 3)
        for profile in GENESIS_PROFILE:
            with self.subTest(profile=profile):
                self.assert_never_authorize(
                    assess_low_cost_custody_profile(profile)
                )


if __name__ == "__main__":
    unittest.main()
