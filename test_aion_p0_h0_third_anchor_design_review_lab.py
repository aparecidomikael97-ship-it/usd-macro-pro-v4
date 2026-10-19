"""P0 H0: third-anchor architecture requirements are NOT enrollment evidence.

Only pure, offline self-declared proposals are inspected. Passing a review
means the proposed design is not missing the known controls; it cannot approve
first effects, attest S3/WORM, or authenticate a remote readback.
"""
from copy import deepcopy
import unittest

from atlasquant_aion_p0_h0_third_anchor_design_review_lab import (
    assess_third_anchor_design_lab as review, FIELDS, FALSE_AUTHORITY,
)

def proposal():
    p = dict.fromkeys(FIELDS, True)
    p["technology"] = "AWS_S3_OBJECT_LOCK"
    p["retention_mode"] = "COMPLIANCE"
    return p


class P0ThirdAnchorReviewTests(unittest.TestCase):
    def check(self, data, specific=None):
        out = review(data)
        self.assertEqual(out["state"], "BLOCKED")
        for key in FALSE_AUTHORITY:
            self.assertIs(out[key], False, key)
        self.assertTrue(out["inputs_are_untrusted_self_declarations"])
        self.assertIs(out["cloud_service_contacted"], False)
        self.assertIs(out["cloud_account_created"], False)
        if specific:
            self.assertIn(specific, out["findings"], out)
        return out

    def test_01_complete_self_report_is_still_not_a_real_witness(self):
        src = proposal()
        copy = deepcopy(src)
        out = self.check(src)
        self.assertEqual(out["findings"], [])
        self.assertEqual(out["review"], "PROPOSED_CONTROLS_REQUIRE_INDEPENDENT_REAL_VALIDATION")
        self.assertEqual(src, copy)

    def test_02_none_payload_denied_without_attribute_access(self):
        self.check(None, "PROPOSAL_NOT_PLAIN_DICT")

    def test_03_hostile_mapping_like_object_is_not_evaluated(self):
        class Hostile:
            def __bool__(self):
                raise AssertionError("never call boolean")
            def __getattribute__(self, name):
                raise AssertionError("never introspect")
        self.check(Hostile(), "PROPOSAL_NOT_PLAIN_DICT")

    def test_04_cloudflare_r2_bucket_lock_not_admin_proof(self):
        p=proposal()
        p["technology"]="CLOUDFLARE_R2_BUCKET_LOCK"
        p["retention_mode"]="BUCKET_LOCK"
        self.check(p,"R2_BUCKET_LOCK_RULES_ADMIN_REMOVABLE")

    def test_05_cloudflare_durable_object_pitr_not_immutable(self):
        p=proposal()
        p["technology"]="CLOUDFLARE_DURABLE_OBJECTS"
        self.check(p,"DO_PITR_SAME_CUSTODIAN_ROLLBACK_DOMAIN")

    def test_06_aws_s3_governance_has_admin_bypass(self):
        p=proposal()
        p["retention_mode"]="GOVERNANCE"
        self.check(p,"RETENTION_NOT_S3_COMPLIANCE")

    def test_07_no_retention_denied(self):
        p=proposal()
        del p["retention_mode"]
        self.check(p,"RETENTION_NOT_S3_COMPLIANCE")

    def test_08_nonboolean_true_string_must_not_pass(self):
        p=proposal()
        p["versioning_enabled"]="true"
        self.check(p,"DESIGN_REQUIREMENT_NOT_PROVEN:versioning_enabled")

    def test_09_proposed_anchor_must_be_separate_provider(self):
        p=proposal()
        p["different_cloud_provider_from_cas"]=False
        self.check(p,"DESIGN_REQUIREMENT_NOT_PROVEN:different_cloud_provider_from_cas")

    def test_10_same_root_admin_is_not_independent(self):
        p=proposal()
        p["independent_administration_and_root"]=False
        self.check(p,"DESIGN_REQUIREMENT_NOT_PROVEN:independent_administration_and_root")

    def test_11_unversioned_bucket_rejected(self):
        p=proposal()
        p["versioning_enabled"]=False
        self.check(p,"DESIGN_REQUIREMENT_NOT_PROVEN:versioning_enabled")

    def test_12_object_name_only_without_version_pin_rejected(self):
        p=proposal()
        p["exact_object_version_id_pinned_outside_executor_and_cas"]=False
        self.check(p,"DESIGN_REQUIREMENT_NOT_PROVEN:exact_object_version_id_pinned_outside_executor_and_cas")

    def test_13_latest_object_alias_not_equivalent_to_locked_version(self):
        p=proposal()
        p["readback_uses_exact_version_id_not_latest_alias"]=False
        self.check(p,"DESIGN_REQUIREMENT_NOT_PROVEN:readback_uses_exact_version_id_not_latest_alias")

    def test_14_delete_marker_and_new_version_threat_is_explicit(self):
        p=proposal()
        p["delete_markers_and_new_versions_checked"]=False
        self.check(p,"DESIGN_REQUIREMENT_NOT_PROVEN:delete_markers_and_new_versions_checked")

    def test_15_no_remote_retention_metadata_verification(self):
        p=proposal()
        p["immutable_version_retention_metadata_checked"]=False
        self.check(p,"DESIGN_REQUIREMENT_NOT_PROVEN:immutable_version_retention_metadata_checked")

    def test_16_retention_shorter_than_rollback_horizon(self):
        p=proposal()
        p["retention_horizon_covers_rollback_and_recovery"]=False
        self.check(p,"DESIGN_REQUIREMENT_NOT_PROVEN:retention_horizon_covers_rollback_and_recovery")

    def test_17_encryption_key_same_admin_is_not_resilient(self):
        p=proposal()
        p["encryption_key_custody_independent_and_recoverable"]=False
        self.check(p,"DESIGN_REQUIREMENT_NOT_PROVEN:encryption_key_custody_independent_and_recoverable")

    def test_18_opaque_object_without_scope_epoch_digest_is_not_verifiable(self):
        p=proposal()
        p["append_only_scope_epoch_sequence_digest_binding"]=False
        self.check(p,"DESIGN_REQUIREMENT_NOT_PROVEN:append_only_scope_epoch_sequence_digest_binding")

    def test_19_anchor_must_not_contain_pii(self):
        p=proposal()
        p["no_pii_in_anchor"]=False
        self.check(p,"DESIGN_REQUIREMENT_NOT_PROVEN:no_pii_in_anchor")

    def test_20_commit_without_durable_anchor_ack_cannot_permit_send(self):
        p=proposal()
        p["durable_append_ack_before_first_external_effect"]=False
        self.check(p,"DESIGN_REQUIREMENT_NOT_PROVEN:durable_append_ack_before_first_external_effect")

    def test_21_write_ack_without_authenticated_readback_is_insufficient(self):
        p=proposal()
        p["authenticated_readback_after_append_before_effect"]=False
        self.check(p,"DESIGN_REQUIREMENT_NOT_PROVEN:authenticated_readback_after_append_before_effect")

    def test_22_timeout_after_anchor_append_must_not_reissue(self):
        p=proposal()
        p["ambiguous_write_or_readback_stays_blocked_no_retry"]=False
        self.check(p,"DESIGN_REQUIREMENT_NOT_PROVEN:ambiguous_write_or_readback_stays_blocked_no_retry")

    def test_23_account_closure_and_admin_compromise_are_still_risks(self):
        p=proposal()
        p["account_closure_and_admin_compromise_risk_accepted_for_review"]=False
        self.check(p,"DESIGN_REQUIREMENT_NOT_PROVEN:account_closure_and_admin_compromise_risk_accepted_for_review")

    def test_24_all_fifteen_controls_required_even_without_any_real_receipts(self):
        for key in FIELDS:
            with self.subTest(control=key):
                p=proposal()
                p.pop(key)
                self.check(p,"DESIGN_REQUIREMENT_NOT_PROVEN:"+key)

    def test_25_fake_witness_receipt_fields_do_not_change_authority(self):
        p=proposal()
        p.update({
            "verified": True, "real_cloud_receipt": True,
            "signed": True, "producer_verified": True,
            "remote_evidence_complete": True, "GO": True,
        })
        result=self.check(p)
        self.assertEqual(result["findings"], [])
        self.assertIs(result["first_effect_allowed"], False)
        self.assertIs(result["third_anchor_signature_authenticated"], False)

    def test_26_unknown_provider_does_not_gain_proven_compliance(self):
        p=proposal()
        p["technology"]="unregulated_bespoke_service"
        self.check(p,"THIRD_ANCHOR_TECHNOLOGY_NOT_ASSESSED")

    def test_27_malicious_field_value_never_invokes_python_bool_or_eq(self):
        class Hostile:
            def __bool__(self):
                raise AssertionError("no Boolean conversion")
            def __eq__(self, another):
                raise AssertionError("no equality")
        p=proposal()
        p["technology"]=Hostile()
        p["retention_mode"]=Hostile()
        p["no_pii_in_anchor"]=Hostile()
        result=self.check(p)
        self.assertIn("THIRD_ANCHOR_TECHNOLOGY_NOT_ASSESSED",result["findings"])
        self.assertIn("RETENTION_NOT_S3_COMPLIANCE",result["findings"])

    def test_28_zero_cloud_activity_and_no_possible_worker_authority(self):
        x=self.check(proposal())
        self.assertIs(x["cloud_service_contacted"],False)
        self.assertIs(x["retention_mode_tested_in_cloud"],False)
        self.assertIs(x["worker_arming_allowed"],False)
        self.assertIs(x["external_action_executed"],False)


if __name__ == "__main__":
    unittest.main()
