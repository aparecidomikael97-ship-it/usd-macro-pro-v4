"""A227: fifty synthetic fail-closed tests; absolutely no live evidence."""
from dataclasses import FrozenInstanceError
import copy
import json
import unittest

from labs.a226_claimed_source_independence import preflight_claimed_source_independence
from labs.a227_independence_acceptance_contract import (
    SCHEMA, INDEPENDENCE_REQUIREMENTS, preflight_independent_source_contract,
)
from labs.test_a223_owner_security_priority import (
    OWNER, TENANT, WORKSPACE, research_note, unfilled_a222,
)
from labs.test_a224_security_proof_test_catalog import make_a224
from labs.test_a225_untrusted_security_proof_rejection import forged_note
from labs.test_a226_claimed_source_independence import make_sources


_UNSET = object()


def upstream():
    a222 = unfilled_a222()
    a223 = research_note(a222)
    a224 = make_a224(a223, a222)
    a225 = forged_note(a224=a224, a223=a223, a222=a222)
    a226 = make_sources(a225=a225, a224=a224, a223=a223, a222=a222)
    return a226, a225, a224, a223, a222


def make_contract(*, upstream_items=None):
    a226, a225, a224, a223, a222 = upstream_items or upstream()
    prior = preflight_claimed_source_independence(
        a226, a225_untrusted_claim=a225, a224_catalog=a224,
        a223_note=a223, a222_matrix=a222,
        expected_owner_id=OWNER, expected_tenant_id=TENANT,
        expected_workspace_id=WORKSPACE,
    )
    assert prior.two_source_envelope_valid and not prior.obvious_claimed_shared_control
    rows = []
    for rid, (proof, boundary, challenge) in INDEPENDENCE_REQUIREMENTS.items():
        rows.append({
            "requirement_id": rid, "proof_kind": proof,
            "trust_boundary": boundary, "negative_challenge": challenge,
            "external_evidence_state": "NOT_OBTAINED",
            "independent_identity_state": "NOT_VERIFIED",
            "test_state": "NOT_EXECUTED", "reviewer_state": "UNASSIGNED",
        })
    return {
        "schema": SCHEMA,
        "owner_id": OWNER, "tenant_id": TENANT, "workspace_id": WORKSPACE,
        "a226_claims_digest": prior.local_comparison_digest,
        "design_state": "RESEARCH_REQUIREMENTS_ONLY",
        "owner_signoff_state": "NOT_REQUESTED",
        "provider_selection_state": "NO_PROVIDER_SELECTED",
        "source_contact_state": "NOT_CONTACTED",
        "external_p0_homologated": 0,
        "uncertain_resend_policy": "ZERO_AUTO_RESEND",
        "requirements": rows,
    }


class A227IndependenceAcceptanceContractTests(unittest.TestCase):
    def check(self, candidate=_UNSET, *, upstream_items=None, **kwargs):
        items = upstream_items or upstream()
        if candidate is _UNSET:
            candidate = make_contract(upstream_items=items)
        a226, a225, a224, a223, a222 = items
        params = {
            "a226_claims": a226, "a225_untrusted_claim": a225,
            "a224_catalog": a224, "a223_note": a223, "a222_matrix": a222,
            "expected_owner_id": OWNER, "expected_tenant_id": TENANT,
            "expected_workspace_id": WORKSPACE,
        }
        params.update(kwargs)
        return preflight_independent_source_contract(candidate, **params)

    def no_authority(self, r):
        self.assertFalse(r.actual_issuer_identity_verified)
        self.assertFalse(r.actual_domain_independence_verified)
        self.assertFalse(r.actual_external_challenges_executed)
        self.assertFalse(r.external_evidence_accepted)
        self.assertFalse(r.owner_signoff_valid)
        self.assertFalse(r.provider_final_effect_verified)
        self.assertEqual(r.external_p0_homologated, 0)
        for flag in (
            "may_accept_security_proof", "may_select_model", "may_contact_person",
            "may_run_external_challenge", "may_commit_budget", "may_provision",
            "may_generate_key", "may_sign", "may_connect", "may_confirm",
            "may_auto_resend",
        ):
            self.assertFalse(getattr(r, flag), flag)

    def denied(self, candidate, code, **kwargs):
        r = self.check(candidate, **kwargs)
        self.assertFalse(r.contract_shape_complete)
        self.assertFalse(r.untrusted_a226_claims_bound)
        self.assertEqual(r.requirements_count, 0)
        self.assertEqual(r.contract_digest, "")
        self.assertEqual(r.code, code)
        self.no_authority(r)

    def change_top(self, field, value, code):
        n = make_contract()
        n[field] = value
        self.denied(n, code)

    def change_row(self, field, value, code):
        n = make_contract()
        n["requirements"][0][field] = value
        self.denied(n, code)

    def test_01_valid_research_contract_is_not_external_proof(self):
        r = self.check()
        self.assertTrue(r.contract_shape_complete)
        self.assertTrue(r.untrusted_a226_claims_bound)
        self.assertEqual(r.requirements_count, 12)
        self.assertEqual(r.code, "CONTRACT_SHAPE_COMPLETE_EXTERNAL_INDEPENDENCE_UNVERIFIED")
        self.assertEqual(len(r.contract_digest), 64)
        self.no_authority(r)

    def test_02_requirements_order_canonical(self):
        n = make_contract()
        r = self.check(n)
        n["requirements"].reverse()
        self.assertEqual(r, self.check(n))

    def test_03_json_research_contract_still_unverified(self):
        r = self.check(json.dumps(make_contract()))
        self.assertTrue(r.contract_shape_complete)
        self.no_authority(r)

    def test_04_binding_changes_digest_when_prior_claims_change(self):
        first = self.check()
        items = upstream()
        items[0]["source_a"]["claimed_audit_store_id"] += "-changed"
        new = make_contract(upstream_items=items)
        r = self.check(new, upstream_items=items)
        self.assertNotEqual(first.contract_digest, r.contract_digest)
        self.no_authority(r)

    def test_05_frozen_result_cannot_be_promoted(self):
        with self.assertRaises(FrozenInstanceError):
            self.check().external_evidence_accepted = True

    def test_06_pure_repeat_does_not_mutate_candidate(self):
        n = make_contract()
        before = copy.deepcopy(n)
        for _ in range(3):
            self.no_authority(self.check(n))
        self.assertEqual(before, n)

    def test_07_all_twelve_distinct_acceptance_requirements(self):
        self.assertEqual(len(INDEPENDENCE_REQUIREMENTS), 12)
        self.assertEqual(len(set(INDEPENDENCE_REQUIREMENTS)), 12)
        self.assertEqual(set(INDEPENDENCE_REQUIREMENTS), {
            row["requirement_id"] for row in make_contract()["requirements"]
        })

    def test_08_all_rows_are_unobtained(self):
        for row in make_contract()["requirements"]:
            self.assertEqual(row["external_evidence_state"], "NOT_OBTAINED")
            self.assertEqual(row["independent_identity_state"], "NOT_VERIFIED")

    def test_09_no_challenge_or_reviewer_assigned(self):
        for row in make_contract()["requirements"]:
            self.assertEqual(row["test_state"], "NOT_EXECUTED")
            self.assertEqual(row["reviewer_state"], "UNASSIGNED")

    def test_10_a226_cross_scope_is_not_acceptable(self):
        items = upstream()
        n = make_contract(upstream_items=items)
        items[0]["owner_id"] = "different-owner"
        self.denied(n, "A226_UNTRUSTED_CLAIMS_REQUIRED", upstream_items=items)

    def test_11_invalid_top_level_shapes(self):
        for obj in (None, {}, [], True, 1):
            self.denied(obj, "CONTRACT_ENVELOPE_NOT_EXACT")

    def test_12_extra_authority_field_rejected(self):
        n = make_contract()
        n["verified"] = True
        self.denied(n, "CONTRACT_ENVELOPE_NOT_EXACT")

    def test_13_missing_top_field_rejected(self):
        for field in ("schema", "requirements", "a226_claims_digest"):
            n = make_contract()
            del n[field]
            self.denied(n, "CONTRACT_ENVELOPE_NOT_EXACT")

    def test_14_unknown_schema_rejected(self):
        self.change_top("schema", "VERIFIED", "CONTRACT_SCHEMA_UNSUPPORTED")

    def test_15_foreign_owner_scope_rejected(self):
        self.change_top("owner_id", "other", "CONTRACT_SCOPE_MISMATCH")

    def test_16_foreign_tenant_scope_rejected(self):
        self.change_top("tenant_id", "other", "CONTRACT_SCOPE_MISMATCH")

    def test_17_foreign_workspace_scope_rejected(self):
        self.change_top("workspace_id", "other", "CONTRACT_SCOPE_MISMATCH")

    def test_18_invalid_expected_owner_scope(self):
        self.denied(make_contract(), "INVALID_EXPECTED_SCOPE", expected_owner_id="bad owner")

    def test_19_invalid_expected_tenant_scope(self):
        self.denied(make_contract(), "INVALID_EXPECTED_SCOPE", expected_tenant_id=True)

    def test_20_invalid_expected_workspace_scope(self):
        self.denied(make_contract(), "INVALID_EXPECTED_SCOPE", expected_workspace_id=1)

    def test_21_boolean_scope_does_not_equal_string(self):
        self.change_top("owner_id", True, "CONTRACT_SCOPE_MISMATCH")

    def test_22_host_cannot_self_certify_contract(self):
        self.change_top("design_state", "APPROVED", "HOST_CANNOT_SELF_CERTIFY_CONTRACT")

    def test_23_host_cannot_claim_owner_signoff(self):
        self.change_top("owner_signoff_state", "SIGNED", "HOST_CANNOT_ASSERT_OWNER_SIGNOFF")

    def test_24_no_vendor_selection_authorized(self):
        self.change_top("provider_selection_state", "SELECTED", "VENDOR_SELECTION_NOT_AUTHORIZED")

    def test_25_no_source_contact_authorized(self):
        self.change_top("source_contact_state", "CONTACTED", "EXTERNAL_CONTACT_NOT_AUTHORIZED")

    def test_26_no_uncertain_retry_even_in_contract(self):
        self.change_top("uncertain_resend_policy", "AUTO_RESEND", "UNCERTAIN_MUST_FAIL_CLOSED")

    def test_27_false_p0_homologation_rejected(self):
        for bad in (True, 1, 6, "0", -1):
            self.change_top("external_p0_homologated", bad, "FALSE_EXTERNAL_P0_CLAIM")

    def test_28_a226_invalid_source_shape_rejected(self):
        items = upstream()
        n = make_contract(upstream_items=items)
        items[0]["source_a"] = "not-a-source"
        self.denied(n, "A226_UNTRUSTED_CLAIMS_REQUIRED", upstream_items=items)

    def test_29_shared_controller_blocks_contract(self):
        items = upstream()
        n = make_contract(upstream_items=items)
        items[0]["source_b"]["claimed_controller_id"] = items[0]["source_a"]["claimed_controller_id"]
        self.denied(n, "A226_NOMINAL_CONFLICT_MUST_BE_RESOLVED", upstream_items=items)

    def test_30_shared_signer_blocks_contract(self):
        items = upstream()
        n = make_contract(upstream_items=items)
        items[0]["source_b"]["claimed_signing_principal_id"] = items[0]["source_a"]["claimed_signing_principal_id"]
        self.denied(n, "A226_NOMINAL_CONFLICT_MUST_BE_RESOLVED", upstream_items=items)

    def test_31_shared_audit_store_blocks_contract(self):
        items = upstream()
        n = make_contract(upstream_items=items)
        items[0]["source_b"]["claimed_audit_store_id"] = items[0]["source_a"]["claimed_audit_store_id"]
        self.denied(n, "A226_NOMINAL_CONFLICT_MUST_BE_RESOLVED", upstream_items=items)

    def test_32_disagreeing_source_hashes_blocks_contract(self):
        items = upstream()
        n = make_contract(upstream_items=items)
        items[0]["source_b"]["claim_digest"] = "d" * 64
        self.denied(n, "A226_NOMINAL_CONFLICT_MUST_BE_RESOLVED", upstream_items=items)

    def test_33_forged_a226_digest_rejected(self):
        self.change_top("a226_claims_digest", "0" * 64, "A226_LOCAL_CLAIM_BINDING_MISMATCH")

    def test_34_malformed_a226_digest_rejected(self):
        for bad in (True, "F" * 64, "a" * 63, None):
            self.change_top("a226_claims_digest", bad, "A226_LOCAL_CLAIM_BINDING_MISMATCH")

    def test_35_promoted_a225_claim_is_not_accepted(self):
        items = upstream()
        n = make_contract(upstream_items=items)
        items[1]["external_proof_state"] = "VERIFIED"
        self.denied(n, "A226_UNTRUSTED_CLAIMS_REQUIRED", upstream_items=items)

    def test_36_fake_a224_execution_does_not_count(self):
        items = upstream()
        n = make_contract(upstream_items=items)
        items[2]["test_catalog"][0]["execution_state"] = "PASSED"
        self.denied(n, "A226_UNTRUSTED_CLAIMS_REQUIRED", upstream_items=items)

    def test_37_duplicate_requirement_rejected(self):
        n = make_contract()
        n["requirements"][1] = copy.deepcopy(n["requirements"][0])
        self.denied(n, "DUPLICATE_INDEPENDENCE_REQUIREMENT")

    def test_38_missing_requirement_rejected(self):
        n = make_contract()
        n["requirements"].pop()
        self.denied(n, "INDEPENDENCE_REQUIREMENTS_INCOMPLETE")

    def test_39_extra_requirement_rejected(self):
        n = make_contract()
        n["requirements"].append(copy.deepcopy(n["requirements"][0]))
        self.denied(n, "INDEPENDENCE_REQUIREMENTS_INCOMPLETE")

    def test_40_requirement_nonobject_rejected(self):
        n = make_contract()
        n["requirements"][0] = "certified"
        self.denied(n, "INDEPENDENCE_REQUIREMENT_ENVELOPE_NOT_EXACT")

    def test_41_extra_requirement_field_rejected(self):
        self.change_row("host_verified", True, "INDEPENDENCE_REQUIREMENT_ENVELOPE_NOT_EXACT")

    def test_42_missing_requirement_field_rejected(self):
        n = make_contract()
        del n["requirements"][0]["trust_boundary"]
        self.denied(n, "INDEPENDENCE_REQUIREMENT_ENVELOPE_NOT_EXACT")

    def test_43_unknown_requirement_id_rejected(self):
        self.change_row("requirement_id", "host_says_pass", "UNKNOWN_INDEPENDENCE_REQUIREMENT")

    def test_44_changed_proof_kind_rejected(self):
        self.change_row("proof_kind", "HOST_SIGNATURE", "INDEPENDENCE_PROOF_PROTOCOL_MISMATCH")

    def test_45_changed_trust_boundary_rejected(self):
        self.change_row("trust_boundary", "SAME_HOST", "INDEPENDENCE_PROOF_PROTOCOL_MISMATCH")

    def test_46_changed_negative_challenge_rejected(self):
        self.change_row("negative_challenge", "NONE", "INDEPENDENCE_PROOF_PROTOCOL_MISMATCH")

    def test_47_host_claims_evidence_obtained_rejected(self):
        self.change_row("external_evidence_state", "OBTAINED", "HOST_CANNOT_PROMOTE_REQUIREMENT_TO_EXTERNAL_PROOF")

    def test_48_host_claims_identity_verified_rejected(self):
        self.change_row("independent_identity_state", "VERIFIED", "HOST_CANNOT_PROMOTE_REQUIREMENT_TO_EXTERNAL_PROOF")

    def test_49_host_claims_challenge_executed_rejected(self):
        self.change_row("test_state", "PASSED", "HOST_CANNOT_PROMOTE_REQUIREMENT_TO_EXTERNAL_PROOF")

    def test_50_host_claims_reviewer_assigned_rejected(self):
        self.change_row("reviewer_state", "OWNER", "HOST_CANNOT_PROMOTE_REQUIREMENT_TO_EXTERNAL_PROOF")


if __name__ == "__main__":
    unittest.main()
