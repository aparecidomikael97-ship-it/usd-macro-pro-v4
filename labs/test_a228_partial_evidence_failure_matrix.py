"""A228: 50 tests, including all 4,095 nonempty synthetic failure subsets."""
from dataclasses import FrozenInstanceError
import copy
import json
import unittest

from labs.a227_independence_acceptance_contract import (
    INDEPENDENCE_REQUIREMENTS, preflight_independent_source_contract,
)
from labs.a228_partial_evidence_failure_matrix import (
    SCHEMA, CLAIMED_PASS, SIMULATED_FAILURE,
    preflight_partial_independence_failures,
)
from labs.test_a223_owner_security_priority import OWNER, TENANT, WORKSPACE
from labs.test_a227_independence_acceptance_contract import make_contract, upstream


_UNSET = object()


def preflight_inputs():
    items = upstream()
    contract = make_contract(upstream_items=items)
    a226, a225, a224, a223, a222 = items
    p = preflight_independent_source_contract(
        contract, a226_claims=a226, a225_untrusted_claim=a225,
        a224_catalog=a224, a223_note=a223, a222_matrix=a222,
        expected_owner_id=OWNER, expected_tenant_id=TENANT,
        expected_workspace_id=WORKSPACE,
    )
    assert p.contract_shape_complete and not p.external_evidence_accepted
    return contract, items, p.contract_digest


def make_matrix(*, failed_ids=None, context=None):
    if context is None:
        context = preflight_inputs()
    contract, items, contract_digest = context
    if failed_ids is None:
        failed_ids = {"issuer_trust_anchor"}
    failures = set(failed_ids)
    rows = []
    for rid, (_, _, negative_challenge) in INDEPENDENCE_REQUIREMENTS.items():
        failed = rid in failures
        rows.append({
            "requirement_id": rid,
            "simulated_outcome": SIMULATED_FAILURE if failed else CLAIMED_PASS,
            "negative_challenge": negative_challenge if failed else "NONE",
            "claim_origin": "HOST_SIMULATED_UNTRUSTED",
            "external_evidence_state": "NOT_OBTAINED",
            "independent_verification_state": "NOT_VERIFIED",
        })
    return {
        "schema": SCHEMA, "owner_id": OWNER, "tenant_id": TENANT,
        "workspace_id": WORKSPACE, "a227_contract_digest": contract_digest,
        "study_state": "SYNTHETIC_FAILURE_CAMPAIGN_ONLY",
        "model_selection_state": "NO_MODEL_SELECTED",
        "owner_signoff_state": "NOT_REQUESTED",
        "source_contact_state": "NOT_CONTACTED",
        "claimed_gate_state": "HARD_NO_GO",
        "external_p0_homologated": 0,
        "uncertain_resend_policy": "ZERO_AUTO_RESEND",
        "outcomes": rows,
    }


class A228PartialIndependenceFailureTests(unittest.TestCase):
    def check(self, candidate=_UNSET, *, context=None, **kwargs):
        if context is None:
            context = preflight_inputs()
        contract, items, _ = context
        if candidate is _UNSET:
            candidate = make_matrix(context=context)
        a226, a225, a224, a223, a222 = items
        params = {
            "a227_contract": contract, "a226_claims": a226,
            "a225_untrusted_claim": a225, "a224_catalog": a224,
            "a223_note": a223, "a222_matrix": a222,
            "expected_owner_id": OWNER, "expected_tenant_id": TENANT,
            "expected_workspace_id": WORKSPACE,
        }
        params.update(kwargs)
        return preflight_partial_independence_failures(candidate, **params)

    def no_authority(self, r):
        self.assertEqual(r.independent_passes_verified, 0)
        for name in (
            "actual_independent_source_verified", "external_evidence_accepted",
            "owner_signoff_valid", "provider_final_effect_verified",
            "may_accept_security_proof", "may_select_model", "may_contact_person",
            "may_run_external_challenge", "may_commit_budget", "may_provision",
            "may_generate_key", "may_sign", "may_connect", "may_confirm",
            "may_auto_resend",
        ):
            self.assertFalse(getattr(r, name), name)
        self.assertEqual(r.external_p0_homologated, 0)

    def denied(self, candidate, code, *, context=None, **kwargs):
        r = self.check(candidate, context=context, **kwargs)
        self.assertFalse(r.scenario_shape_complete)
        self.assertFalse(r.untrusted_a227_contract_bound)
        self.assertEqual(r.simulated_failures, 0)
        self.assertEqual(r.host_claimed_passes, 0)
        self.assertEqual(r.synthetic_scenario_digest, "")
        self.assertEqual(r.code, code)
        self.no_authority(r)

    def change_top(self, field, value, code):
        n = make_matrix()
        n[field] = value
        self.denied(n, code)

    def change_row(self, field, value, code):
        n = make_matrix()
        n["outcomes"][0][field] = value
        self.denied(n, code)

    def test_01_one_failure_blocks_eleven_claimed_passes(self):
        r = self.check()
        self.assertTrue(r.scenario_shape_complete)
        self.assertTrue(r.untrusted_a227_contract_bound)
        self.assertEqual((r.simulated_failures, r.host_claimed_passes), (1, 11))
        self.assertEqual(r.code, "SIMULATED_FAILURES_BLOCK_ALL_HOST_CLAIMED_PASSES")
        self.assertEqual(len(r.synthetic_scenario_digest), 64)
        self.no_authority(r)

    def test_02_all_twelve_fail_still_blocked(self):
        r = self.check(make_matrix(failed_ids=INDEPENDENCE_REQUIREMENTS))
        self.assertEqual((r.simulated_failures, r.host_claimed_passes), (12, 0))
        self.no_authority(r)

    def test_03_each_individual_control_failure_blocks(self):
        for rid in INDEPENDENCE_REQUIREMENTS:
            with self.subTest(rid=rid):
                r = self.check(make_matrix(failed_ids={rid}))
                self.assertTrue(r.scenario_shape_complete)
                self.assertEqual(r.simulated_failures, 1)
                self.no_authority(r)

    def test_04_two_failed_requirements_block_ten_claims(self):
        ids = list(INDEPENDENCE_REQUIREMENTS)
        r = self.check(make_matrix(failed_ids=set(ids[:2])))
        self.assertEqual((r.simulated_failures, r.host_claimed_passes), (2, 10))
        self.no_authority(r)

    def test_05_negative_challenge_cannot_be_swapped(self):
        self.change_row("negative_challenge", "FAKE", "NEGATIVE_CHALLENGE_MISMATCH")

    def test_06_eleven_failures_one_host_pass_blocks(self):
        ids = list(INDEPENDENCE_REQUIREMENTS)
        r = self.check(make_matrix(failed_ids=set(ids[:-1])))
        self.assertEqual((r.simulated_failures, r.host_claimed_passes), (11, 1))
        self.no_authority(r)

    def test_07_zero_failures_does_not_certify_anything(self):
        self.denied(make_matrix(failed_ids=set()), "ZERO_FAILURES_DO_NOT_PROVE_INDEPENDENCE")

    def test_08_swapped_rows_have_same_digest(self):
        n = make_matrix()
        initial = self.check(n)
        n["outcomes"].reverse()
        self.assertEqual(initial, self.check(n))

    def test_09_json_representation_still_untrusted(self):
        r = self.check(json.dumps(make_matrix()))
        self.assertTrue(r.scenario_shape_complete)
        self.no_authority(r)

    def test_10_changed_failure_subset_changes_digest(self):
        ids = list(INDEPENDENCE_REQUIREMENTS)
        self.assertNotEqual(
            self.check(make_matrix(failed_ids={ids[0]})).synthetic_scenario_digest,
            self.check(make_matrix(failed_ids={ids[1]})).synthetic_scenario_digest,
        )

    def test_11_pure_repeat_does_not_mutate_scenario(self):
        n = make_matrix()
        original = copy.deepcopy(n)
        for _ in range(3):
            self.no_authority(self.check(n))
        self.assertEqual(original, n)

    def test_12_frozen_output_rejects_authority_mutation(self):
        with self.assertRaises(FrozenInstanceError):
            self.check().external_evidence_accepted = True

    def test_13_all_4095_nonempty_subsets_fail_closed(self):
        ids = list(INDEPENDENCE_REQUIREMENTS)
        context = preflight_inputs()
        template = make_matrix(context=context)
        for mask in range(1, 1 << len(ids)):
            n = dict(template)
            n["outcomes"] = [
                {
                    **row,
                    "simulated_outcome": SIMULATED_FAILURE if mask & (1 << index) else CLAIMED_PASS,
                    "negative_challenge": INDEPENDENCE_REQUIREMENTS[row["requirement_id"]][2]
                    if mask & (1 << index) else "NONE",
                }
                for index, row in enumerate(template["outcomes"])
            ]
            r = self.check(n, context=context)
            self.assertTrue(r.scenario_shape_complete, mask)
            self.assertEqual(r.simulated_failures, mask.bit_count(), mask)
            self.assertEqual(r.host_claimed_passes, 12 - mask.bit_count(), mask)
            self.assertFalse(r.external_evidence_accepted, mask)
            self.assertFalse(r.may_confirm, mask)
            self.assertFalse(r.may_auto_resend, mask)

    def test_14_all_outputs_have_zero_verified_passes(self):
        ids = list(INDEPENDENCE_REQUIREMENTS)
        for failed in (set(ids[:1]), set(ids[::2]), set(ids)):
            self.no_authority(self.check(make_matrix(failed_ids=failed)))

    def test_15_malformed_top_level_rejected(self):
        for obj in (None, {}, [], True, 3):
            self.denied(obj, "FAILURE_MATRIX_ENVELOPE_NOT_EXACT")

    def test_16_extra_top_level_authority_rejected(self):
        n = make_matrix()
        n["allow_execute"] = True
        self.denied(n, "FAILURE_MATRIX_ENVELOPE_NOT_EXACT")

    def test_17_missing_top_level_field_rejected(self):
        for key in ("schema", "outcomes", "a227_contract_digest"):
            n = make_matrix()
            del n[key]
            self.denied(n, "FAILURE_MATRIX_ENVELOPE_NOT_EXACT")

    def test_18_schema_cannot_be_promoted(self):
        self.change_top("schema", "VERIFIED_REAL_WORLD", "FAILURE_MATRIX_SCHEMA_UNSUPPORTED")

    def test_19_other_owner_rejected(self):
        self.change_top("owner_id", "other", "FAILURE_MATRIX_SCOPE_MISMATCH")

    def test_20_other_tenant_rejected(self):
        self.change_top("tenant_id", "other", "FAILURE_MATRIX_SCOPE_MISMATCH")

    def test_21_other_workspace_rejected(self):
        self.change_top("workspace_id", "other", "FAILURE_MATRIX_SCOPE_MISMATCH")

    def test_22_invalid_expected_owner_rejected(self):
        self.denied(make_matrix(), "INVALID_EXPECTED_SCOPE", expected_owner_id="bad owner")

    def test_23_invalid_expected_tenant_rejected(self):
        self.denied(make_matrix(), "INVALID_EXPECTED_SCOPE", expected_tenant_id=True)

    def test_24_invalid_expected_workspace_rejected(self):
        self.denied(make_matrix(), "INVALID_EXPECTED_SCOPE", expected_workspace_id=1)

    def test_25_boolean_owner_scope_rejected(self):
        self.change_top("owner_id", True, "FAILURE_MATRIX_SCOPE_MISMATCH")

    def test_26_host_cannot_claim_actual_campaign(self):
        self.change_top("study_state", "REAL_WORLD_COMPLETE", "CANNOT_SELF_CERTIFY_REAL_TEST")

    def test_27_model_cannot_be_selected_from_failure_results(self):
        self.change_top("model_selection_state", "KMS_HSM", "CANNOT_SELECT_MODEL_IN_LAB")

    def test_28_no_owner_signoff_claim(self):
        self.change_top("owner_signoff_state", "APPROVED", "HOST_CANNOT_ASSERT_OWNER_SIGNOFF")

    def test_29_no_source_contact_claim(self):
        self.change_top("source_contact_state", "CONTACTED", "EXTERNAL_CONTACT_NOT_AUTHORIZED")

    def test_30_host_cannot_override_hard_no_go(self):
        self.change_top("claimed_gate_state", "GO", "HOST_CANNOT_OVERRIDE_HARD_NO_GO")

    def test_31_auto_resend_is_not_permitted(self):
        self.change_top("uncertain_resend_policy", "AUTO_RESEND", "UNCERTAIN_MUST_FAIL_CLOSED")

    def test_32_false_p0_claims_denied(self):
        for bad in (True, 1, 6, -1, "0"):
            self.change_top("external_p0_homologated", bad, "FALSE_EXTERNAL_P0_CLAIM")

    def test_33_invalid_a227_contract_cannot_anchor_scenario(self):
        context = preflight_inputs()
        n = make_matrix(context=context)
        context[0]["owner_signoff_state"] = "SIGNED"
        self.denied(n, "A227_UNVERIFIED_CONTRACT_REQUIRED", context=context)

    def test_34_invalid_a226_sources_cannot_anchor_scenario(self):
        context = preflight_inputs()
        n = make_matrix(context=context)
        context[1][0]["source_a"] = "fake"
        self.denied(n, "A227_UNVERIFIED_CONTRACT_REQUIRED", context=context)

    def test_35_foreign_a227_scope_cannot_anchor_scenario(self):
        context = preflight_inputs()
        n = make_matrix(context=context)
        context[0]["tenant_id"] = "other-tenant"
        self.denied(n, "A227_UNVERIFIED_CONTRACT_REQUIRED", context=context)

    def test_36_fake_a227_external_proof_cannot_anchor_scenario(self):
        context = preflight_inputs()
        n = make_matrix(context=context)
        context[0]["requirements"][0]["external_evidence_state"] = "VERIFIED"
        self.denied(n, "A227_UNVERIFIED_CONTRACT_REQUIRED", context=context)

    def test_37_forged_a227_digest_denied(self):
        self.change_top("a227_contract_digest", "0" * 64, "A227_LOCAL_CONTRACT_BINDING_MISMATCH")

    def test_38_malformed_a227_digest_denied(self):
        for value in (True, None, "a" * 63, "F" * 64):
            self.change_top("a227_contract_digest", value, "A227_LOCAL_CONTRACT_BINDING_MISMATCH")

    def test_39_missing_outcome_row_denied(self):
        n = make_matrix()
        n["outcomes"].pop()
        self.denied(n, "TWELVE_OUTCOMES_REQUIRED")

    def test_40_extra_outcome_row_denied(self):
        n = make_matrix()
        n["outcomes"].append(copy.deepcopy(n["outcomes"][0]))
        self.denied(n, "TWELVE_OUTCOMES_REQUIRED")

    def test_41_tuple_not_list_denied(self):
        n = make_matrix()
        n["outcomes"] = tuple(n["outcomes"])
        self.denied(n, "TWELVE_OUTCOMES_REQUIRED")

    def test_42_duplicate_outcome_id_denied(self):
        n = make_matrix()
        n["outcomes"][1] = copy.deepcopy(n["outcomes"][0])
        self.denied(n, "OUTCOME_REQUIREMENT_DUPLICATE")

    def test_43_unknown_outcome_id_denied(self):
        self.change_row("requirement_id", "host_claim_pass", "OUTCOME_REQUIREMENT_UNKNOWN")

    def test_44_nonobject_row_denied(self):
        n = make_matrix()
        n["outcomes"][0] = "verified"
        self.denied(n, "OUTCOME_ROW_ENVELOPE_NOT_EXACT")

    def test_45_extra_row_field_denied(self):
        self.change_row("verified", True, "OUTCOME_ROW_ENVELOPE_NOT_EXACT")

    def test_46_missing_row_field_denied(self):
        n = make_matrix()
        del n["outcomes"][0]["negative_challenge"]
        self.denied(n, "OUTCOME_ROW_ENVELOPE_NOT_EXACT")

    def test_47_host_claims_independent_origin_denied(self):
        self.change_row("claim_origin", "EXTERNAL_TRUSTED", "HOST_OUTCOME_CANNOT_CLAIM_INDEPENDENT_ORIGIN")

    def test_48_host_claims_real_evidence_denied(self):
        self.change_row("external_evidence_state", "OBTAINED", "HOST_OUTCOME_CANNOT_PROMOTE_EXTERNAL_PROOF")

    def test_49_host_claims_verified_independence_denied(self):
        self.change_row("independent_verification_state", "VERIFIED", "HOST_OUTCOME_CANNOT_PROMOTE_EXTERNAL_PROOF")

    def test_50_host_claims_real_success_denied(self):
        self.change_row("simulated_outcome", "VERIFIED_PASS", "OUTCOME_CANNOT_CLAIM_VERIFIED_SUCCESS")


if __name__ == "__main__":
    unittest.main()
