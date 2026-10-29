"""A226: 50 checks that two agreeing host witnesses still lack authority."""
from dataclasses import FrozenInstanceError
import copy
import json
import unittest

from labs.a225_untrusted_security_proof_rejection import preflight_untrusted_forged_security_proof
from labs.a226_claimed_source_independence import (
    SCHEMA, preflight_claimed_source_independence,
)
from labs.test_a223_owner_security_priority import (
    OWNER, TENANT, WORKSPACE, research_note, unfilled_a222,
)
from labs.test_a224_security_proof_test_catalog import make_a224
from labs.test_a225_untrusted_security_proof_rejection import forged_note


_UNSET = object()


def make_sources(*, a225=None, a224=None, a223=None, a222=None):
    if a222 is None:
        a222 = unfilled_a222()
    if a223 is None:
        a223 = research_note(a222)
    if a224 is None:
        a224 = make_a224(a223, a222)
    if a225 is None:
        a225 = forged_note(a224=a224, a223=a223, a222=a222)
    base = preflight_untrusted_forged_security_proof(
        a225, a224_catalog=a224, a223_note=a223,
        a222_matrix=a222, expected_owner_id=OWNER,
        expected_tenant_id=TENANT, expected_workspace_id=WORKSPACE,
    )
    assert base.local_shape_matches_research_catalog

    def source(id_, controller, signer, audit):
        return {
            "source_id": id_, "claimed_controller_id": controller,
            "claimed_signing_principal_id": signer,
            "claimed_audit_store_id": audit,
            "claim_digest": "c" * 64,
            "claim_origin": "HOST_SUPPLIED_UNVERIFIED",
            "claim_result_state": "HOST_CLAIMS_PASSED",
            "issuer_identity_state": "NOT_VERIFIED",
            "trust_domain_proof_state": "NOT_OBTAINED",
            "independent_receipt_state": "NOT_OBTAINED",
        }

    return {
        "schema": SCHEMA,
        "owner_id": OWNER, "tenant_id": TENANT, "workspace_id": WORKSPACE,
        "a225_untrusted_claim_digest": base.untrusted_claim_digest,
        "study_state": "TWO_HOST_CONTROLLED_CLAIMS_ONLY",
        "owner_approval_state": "NOT_REQUESTED",
        "provider_receipt_state": "NOT_OBTAINED",
        "external_p0_homologated": 0,
        "uncertain_resend_policy": "ZERO_AUTO_RESEND",
        "source_a": source("observer-a", "controller-a", "signer-a", "audit-a"),
        "source_b": source("observer-b", "controller-b", "signer-b", "audit-b"),
    }


class A226ClaimedIndependenceTests(unittest.TestCase):
    def check(self, candidate=_UNSET, *, a225=None, a224=None, a223=None, a222=None, **kwargs):
        if a222 is None:
            a222 = unfilled_a222()
        if a223 is None:
            a223 = research_note(a222)
        if a224 is None:
            a224 = make_a224(a223, a222)
        if a225 is None:
            a225 = forged_note(a224=a224, a223=a223, a222=a222)
        if candidate is _UNSET:
            candidate = make_sources(a225=a225, a224=a224, a223=a223, a222=a222)
        params = {
            "a225_untrusted_claim": a225, "a224_catalog": a224,
            "a223_note": a223, "a222_matrix": a222,
            "expected_owner_id": OWNER, "expected_tenant_id": TENANT,
            "expected_workspace_id": WORKSPACE,
        }
        params.update(kwargs)
        return preflight_claimed_source_independence(candidate, **params)

    def no_authority(self, r):
        for field in (
            "actual_independent_issuers_verified", "actual_domain_separation_verified",
            "owner_anchor_verified", "independent_evidence_accepted",
            "owner_signoff_valid", "provider_final_effect_verified",
            "may_accept_security_proof", "may_select_model", "may_contact_person",
            "may_run_external_challenge", "may_commit_budget", "may_provision",
            "may_generate_key", "may_sign", "may_connect", "may_confirm",
            "may_auto_resend",
        ):
            self.assertFalse(getattr(r, field), field)
        self.assertEqual(r.external_p0_homologated, 0)

    def denied(self, candidate, code, **kwargs):
        r = self.check(candidate, **kwargs)
        self.assertFalse(r.two_source_envelope_valid)
        self.assertFalse(r.locally_coherent_claims)
        self.assertEqual(r.code, code)
        self.assertEqual(r.local_comparison_digest, "")
        self.no_authority(r)

    def changed(self, name, value, code):
        n = make_sources()
        n[name] = value
        self.denied(n, code)

    def changed_source(self, source, name, value, code):
        n = make_sources()
        n[source][name] = value
        self.denied(n, code)

    def test_01_coherent_separate_labels_are_not_independence_proof(self):
        r = self.check()
        self.assertTrue(r.two_source_envelope_valid)
        self.assertTrue(r.locally_coherent_claims)
        self.assertFalse(r.obvious_claimed_shared_control)
        self.assertEqual(r.code, "TWO_COHERENT_DISTINCT_HOST_LABELS_INDEPENDENCE_UNPROVEN")
        self.assertEqual(len(r.local_comparison_digest), 64)
        self.no_authority(r)

    def test_02_claimed_same_controller_exposes_overlap_not_proof(self):
        n = make_sources()
        n["source_b"]["claimed_controller_id"] = n["source_a"]["claimed_controller_id"]
        r = self.check(n)
        self.assertTrue(r.repeated_claimed_controller)
        self.assertTrue(r.obvious_claimed_shared_control)
        self.assertEqual(r.code, "EXPLICIT_SHARED_HOST_LABELS_NOT_INDEPENDENT")
        self.no_authority(r)

    def test_03_same_signer_exposes_overlap(self):
        n = make_sources()
        n["source_b"]["claimed_signing_principal_id"] = n["source_a"]["claimed_signing_principal_id"]
        r = self.check(n)
        self.assertTrue(r.repeated_claimed_signing_principal)
        self.no_authority(r)

    def test_04_same_audit_store_exposes_overlap(self):
        n = make_sources()
        n["source_b"]["claimed_audit_store_id"] = n["source_a"]["claimed_audit_store_id"]
        r = self.check(n)
        self.assertTrue(r.repeated_claimed_audit_store)
        self.no_authority(r)

    def test_05_all_three_claimed_domains_same_still_no_trust(self):
        n = make_sources()
        for field in ("claimed_controller_id", "claimed_signing_principal_id", "claimed_audit_store_id"):
            n["source_b"][field] = n["source_a"][field]
        r = self.check(n)
        self.assertTrue(r.obvious_claimed_shared_control)
        self.assertTrue(r.repeated_claimed_controller)
        self.assertTrue(r.repeated_claimed_signing_principal)
        self.assertTrue(r.repeated_claimed_audit_store)
        self.no_authority(r)

    def test_06_all_nominal_domains_different_remain_untrusted(self):
        n = make_sources()
        for source in ("source_a", "source_b"):
            for key in ("claimed_controller_id", "claimed_signing_principal_id", "claimed_audit_store_id"):
                n[source][key] += "-different"
        self.no_authority(self.check(n))

    def test_07_consistent_fake_digests_do_not_verify_issuers(self):
        n = make_sources()
        n["source_a"]["claim_digest"] = "f" * 64
        n["source_b"]["claim_digest"] = "f" * 64
        self.assertTrue(self.check(n).locally_coherent_claims)
        self.no_authority(self.check(n))

    def test_08_disagreeing_claims_are_not_independent_proof(self):
        n = make_sources()
        n["source_b"]["claim_digest"] = "d" * 64
        r = self.check(n)
        self.assertTrue(r.two_source_envelope_valid)
        self.assertFalse(r.locally_coherent_claims)
        self.assertEqual(r.code, "HOST_CLAIMS_DISAGREE_NO_INDEPENDENT_PROOF")
        self.no_authority(r)

    def test_09_disagreement_and_shared_controller_are_both_untrusted(self):
        n = make_sources()
        n["source_b"]["claimed_controller_id"] = n["source_a"]["claimed_controller_id"]
        n["source_b"]["claim_digest"] = "d" * 64
        r = self.check(n)
        self.assertFalse(r.locally_coherent_claims)
        self.assertTrue(r.repeated_claimed_controller)
        self.no_authority(r)

    def test_10_swapped_source_slots_are_order_canonical(self):
        n = make_sources()
        first = self.check(n)
        n["source_a"], n["source_b"] = n["source_b"], n["source_a"]
        self.assertEqual(first, self.check(n))

    def test_11_json_input_same_but_not_authenticated(self):
        r = self.check(json.dumps(make_sources()))
        self.assertTrue(r.two_source_envelope_valid)
        self.no_authority(r)

    def test_12_digest_matches_only_local_text(self):
        n = make_sources()
        a = self.check(n)
        n["source_a"]["claimed_audit_store_id"] += "-new"
        b = self.check(n)
        self.assertNotEqual(a.local_comparison_digest, b.local_comparison_digest)
        self.no_authority(a)
        self.no_authority(b)

    def test_13_repeated_runs_do_not_mutate_inputs(self):
        n = make_sources()
        before = copy.deepcopy(n)
        for _ in range(5):
            self.no_authority(self.check(n))
        self.assertEqual(before, n)

    def test_14_frozen_output_rejects_authority_mutation(self):
        with self.assertRaises(FrozenInstanceError):
            self.check().independent_evidence_accepted = True

    def test_15_malformed_top_level_envelope_rejected(self):
        for n in (None, {}, [], True, 9):
            self.denied(n, "SOURCE_CLAIMS_ENVELOPE_NOT_EXACT")

    def test_16_extra_top_level_authority_rejected(self):
        n = make_sources()
        n["host_verified"] = True
        self.denied(n, "SOURCE_CLAIMS_ENVELOPE_NOT_EXACT")

    def test_17_missing_top_level_field_rejected(self):
        for key in ("schema", "source_a", "source_b", "a225_untrusted_claim_digest"):
            n = make_sources()
            del n[key]
            self.denied(n, "SOURCE_CLAIMS_ENVELOPE_NOT_EXACT")

    def test_18_json_nonobject_rejected(self):
        self.denied('"approved"', "AMBIGUOUS_OR_OVERSIZED_SOURCE_CLAIMS_JSON")

    def test_19_wrong_schema_rejected(self):
        self.changed("schema", "INDEPENDENCE_VERIFIED", "SOURCE_CLAIMS_SCHEMA_UNSUPPORTED")

    def test_20_other_owner_scope_rejected(self):
        self.changed("owner_id", "other", "SOURCE_CLAIMS_SCOPE_MISMATCH")

    def test_21_other_tenant_scope_rejected(self):
        self.changed("tenant_id", "other", "SOURCE_CLAIMS_SCOPE_MISMATCH")

    def test_22_other_workspace_scope_rejected(self):
        self.changed("workspace_id", "other", "SOURCE_CLAIMS_SCOPE_MISMATCH")

    def test_23_invalid_expected_owner_rejected(self):
        self.denied(make_sources(), "INVALID_EXPECTED_SCOPE", expected_owner_id="bad / name")

    def test_24_invalid_expected_tenant_type_rejected(self):
        self.denied(make_sources(), "INVALID_EXPECTED_SCOPE", expected_tenant_id=True)

    def test_25_invalid_expected_workspace_type_rejected(self):
        self.denied(make_sources(), "INVALID_EXPECTED_SCOPE", expected_workspace_id=1)

    def test_26_candidate_scope_bool_rejected(self):
        self.changed("owner_id", True, "SOURCE_CLAIMS_SCOPE_MISMATCH")

    def test_27_host_cannot_claim_independence_verified(self):
        self.changed("study_state", "TWO_REAL_INDEPENDENT_SOURCES", "HOST_CANNOT_SELF_CERTIFY_INDEPENDENCE")

    def test_28_host_cannot_claim_owner_signoff(self):
        self.changed("owner_approval_state", "SIGNED", "HOST_CANNOT_ASSERT_OWNER_SIGNOFF")

    def test_29_provider_receipt_still_not_obtained(self):
        self.changed("provider_receipt_state", "CONFIRMED", "HOST_CANNOT_FORGE_PROVIDER_RECEIPT")

    def test_30_false_external_p0_denied_including_bool(self):
        for fake in (True, 1, 6, -1, "0"):
            self.changed("external_p0_homologated", fake, "FALSE_EXTERNAL_P0_CLAIM")

    def test_31_no_auto_resend_even_in_a_claim_of_outage(self):
        self.changed("uncertain_resend_policy", "AUTO_RESEND", "UNCERTAIN_MUST_FAIL_CLOSED")

    def test_32_bad_source_shapes_rejected(self):
        for key in ("source_a", "source_b"):
            n = make_sources()
            n[key] = "signed"
            self.denied(n, "SOURCE_DESCRIPTION_NOT_EXACT")

    def test_33_unknown_source_field_rejected(self):
        self.changed_source("source_a", "test_passed", True, "SOURCE_DESCRIPTION_NOT_EXACT")

    def test_34_missing_source_field_rejected(self):
        n = make_sources()
        del n["source_a"]["claimed_controller_id"]
        self.denied(n, "SOURCE_DESCRIPTION_NOT_EXACT")

    def test_35_bad_source_ids_rejected(self):
        for field in ("source_id", "claimed_controller_id", "claimed_signing_principal_id", "claimed_audit_store_id"):
            for bad in ("", "slash/path", True):
                self.changed_source("source_a", field, bad, "INVALID_HOST_CLAIMED_SOURCE_IDENTITY")

    def test_36_bad_source_b_identity_rejected(self):
        self.changed_source("source_b", "claimed_controller_id", 0, "INVALID_HOST_CLAIMED_SOURCE_IDENTITY")

    def test_37_bad_untrusted_source_digest_rejected(self):
        for bad in ("a" * 63, "G" * 64, True, None):
            self.changed_source("source_a", "claim_digest", bad, "INVALID_UNTRUSTED_SOURCE_DIGEST")

    def test_38_both_source_hashes_are_only_syntax(self):
        n = make_sources()
        n["source_a"]["claim_digest"] = "0" * 64
        n["source_b"]["claim_digest"] = "0" * 64
        r = self.check(n)
        self.assertTrue(r.locally_coherent_claims)
        self.no_authority(r)

    def test_39_host_claim_origin_cannot_be_promoted(self):
        self.changed_source("source_a", "claim_origin", "INDEPENDENT_EXTERNAL", "HOST_CANNOT_ELEVATE_NOMINAL_SOURCE_TO_AUTHORITY")

    def test_40_claim_result_cannot_become_verified(self):
        self.changed_source("source_b", "claim_result_state", "VERIFIED_PASS", "HOST_CANNOT_ELEVATE_NOMINAL_SOURCE_TO_AUTHORITY")

    def test_41_issuer_identity_cannot_be_self_verified(self):
        self.changed_source("source_b", "issuer_identity_state", "VERIFIED", "HOST_CANNOT_ELEVATE_NOMINAL_SOURCE_TO_AUTHORITY")

    def test_42_domain_independence_cannot_be_self_proved(self):
        self.changed_source("source_a", "trust_domain_proof_state", "INDEPENDENT", "HOST_CANNOT_ELEVATE_NOMINAL_SOURCE_TO_AUTHORITY")

    def test_43_independent_receipt_cannot_be_self_obtained(self):
        self.changed_source("source_b", "independent_receipt_state", "SIGNED", "HOST_CANNOT_ELEVATE_NOMINAL_SOURCE_TO_AUTHORITY")

    def test_44_same_nominal_source_id_rejected(self):
        n = make_sources()
        n["source_b"]["source_id"] = n["source_a"]["source_id"]
        self.denied(n, "DUPLICATE_NOMINAL_SOURCE_ID")

    def test_45_wrong_a225_digest_rejected(self):
        self.changed("a225_untrusted_claim_digest", "0" * 64, "A225_UNTRUSTED_CLAIM_DIGEST_MISMATCH")

    def test_46_bad_a225_digest_type_rejected(self):
        for bad in (True, "f" * 63, "F" * 64, None):
            self.changed("a225_untrusted_claim_digest", bad, "A225_UNTRUSTED_CLAIM_DIGEST_MISMATCH")

    def test_47_a225_untrusted_claim_cannot_be_promoted_to_valid_proof(self):
        claim = forged_note()
        claim["external_proof_state"] = "VERIFIED"
        self.denied(make_sources(), "A225_UNTRUSTED_CLAIM_REQUIRED", a225=claim)

    def test_48_a224_executed_claim_not_acceptable(self):
        catalog = make_a224()
        catalog["test_catalog"][0]["execution_state"] = "PASSED"
        self.denied(make_sources(), "A225_UNTRUSTED_CLAIM_REQUIRED", a224=catalog, a225=forged_note())

    def test_49_duplicate_json_and_oversized_payload_denied(self):
        raw = json.dumps(make_sources())
        forged = raw.replace(
            '"owner_id": "synthetic-owner"',
            '"owner_id": "synthetic-owner", "owner_id": "fake"', 1,
        )
        self.assertNotEqual(raw, forged)
        self.denied(forged, "AMBIGUOUS_OR_OVERSIZED_SOURCE_CLAIMS_JSON")
        self.denied("{" + " " * 9000 + "}", "AMBIGUOUS_OR_OVERSIZED_SOURCE_CLAIMS_JSON")

    def test_50_rebound_valid_host_claim_changes_local_digest_only(self):
        n = make_sources()
        initial = self.check(n)
        claim = forged_note()
        claim["claimed_witness_digest"] = "e" * 64
        a224 = make_a224()
        a223 = research_note()
        a222 = unfilled_a222()
        new_a225 = preflight_untrusted_forged_security_proof(
            claim, a224_catalog=a224, a223_note=a223, a222_matrix=a222,
            expected_owner_id=OWNER, expected_tenant_id=TENANT,
            expected_workspace_id=WORKSPACE,
        )
        self.assertTrue(new_a225.local_shape_matches_research_catalog)
        n["a225_untrusted_claim_digest"] = new_a225.untrusted_claim_digest
        rebound = self.check(n, a225=claim, a224=a224, a223=a223, a222=a222)
        self.assertTrue(rebound.two_source_envelope_valid)
        self.assertNotEqual(initial.local_comparison_digest, rebound.local_comparison_digest)
        self.no_authority(rebound)


if __name__ == "__main__":
    unittest.main()
