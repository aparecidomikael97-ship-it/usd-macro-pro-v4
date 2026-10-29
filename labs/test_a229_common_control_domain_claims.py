"""A229: 50 synthetic checks of shared authority labels; never trust them."""
from dataclasses import FrozenInstanceError
import copy
import json
import unittest

from labs.a227_independence_acceptance_contract import INDEPENDENCE_REQUIREMENTS
from labs.a228_partial_evidence_failure_matrix import preflight_partial_independence_failures
from labs.a229_common_control_domain_claims import (
    SCHEMA, CONTROL_LABEL_FIELDS, preflight_common_control_claims,
)
from labs.test_a223_owner_security_priority import OWNER, TENANT, WORKSPACE
from labs.test_a228_partial_evidence_failure_matrix import (
    make_matrix, preflight_inputs,
)


_UNSET = object()


def upstream_for_a229():
    a227, items, a227_digest = preflight_inputs()
    context = (a227, items, a227_digest)
    a228 = make_matrix(context=context)
    a226, a225, a224, a223, a222 = items
    result = preflight_partial_independence_failures(
        a228, a227_contract=a227, a226_claims=a226,
        a225_untrusted_claim=a225, a224_catalog=a224,
        a223_note=a223, a222_matrix=a222,
        expected_owner_id=OWNER, expected_tenant_id=TENANT,
        expected_workspace_id=WORKSPACE,
    )
    assert result.scenario_shape_complete and not result.external_evidence_accepted
    return a228, a227, items, result.synthetic_scenario_digest


def make_graph(*, context=None):
    if context is None:
        context = upstream_for_a229()
    a228, a227, items, a228_digest = context
    sources = []
    for index, rid in enumerate(INDEPENDENCE_REQUIREMENTS):
        sources.append({
            "requirement_id": rid, "nominal_source_id": f"nominal-source-{index}",
            "claimed_controller_id": f"controller-{index}",
            "claimed_ultimate_parent_id": f"parent-{index}",
            "claimed_signing_principal_id": f"signer-{index}",
            "claimed_audit_store_id": f"audit-{index}",
            "claimed_recovery_principal_id": f"recovery-{index}",
            "claim_origin": "HOST_SUPPLIED_UNVERIFIED",
            "issuer_identity_state": "NOT_VERIFIED",
            "dependency_audit_state": "NOT_OBTAINED",
        })
    return {
        "schema": SCHEMA, "owner_id": OWNER, "tenant_id": TENANT,
        "workspace_id": WORKSPACE, "a228_scenario_digest": a228_digest,
        "study_state": "HOST_DEPENDENCY_LABEL_STUDY_ONLY",
        "model_selection_state": "NO_MODEL_SELECTED",
        "owner_signoff_state": "NOT_REQUESTED",
        "source_contact_state": "NOT_CONTACTED",
        "claimed_gate_state": "HARD_NO_GO",
        "external_p0_homologated": 0,
        "uncertain_resend_policy": "ZERO_AUTO_RESEND",
        "sources": sources,
    }


class A229CommonControlClaimTests(unittest.TestCase):
    def check(self, candidate=_UNSET, *, context=None, **kwargs):
        if context is None:
            context = upstream_for_a229()
        if candidate is _UNSET:
            candidate = make_graph(context=context)
        a228, a227, items, _ = context
        a226, a225, a224, a223, a222 = items
        params = {
            "a228_scenario": a228, "a227_contract": a227,
            "a226_claims": a226, "a225_untrusted_claim": a225,
            "a224_catalog": a224, "a223_note": a223, "a222_matrix": a222,
            "expected_owner_id": OWNER, "expected_tenant_id": TENANT,
            "expected_workspace_id": WORKSPACE,
        }
        params.update(kwargs)
        return preflight_common_control_claims(candidate, **params)

    def no_authority(self, r):
        for field in (
            "actual_control_domains_independent", "actual_issuer_identities_verified",
            "external_evidence_accepted", "owner_signoff_valid",
            "provider_final_effect_verified", "may_accept_security_proof",
            "may_select_model", "may_contact_person", "may_run_external_challenge",
            "may_commit_budget", "may_provision", "may_generate_key", "may_sign",
            "may_connect", "may_confirm", "may_auto_resend",
        ):
            self.assertFalse(getattr(r, field), field)
        self.assertEqual(r.external_p0_homologated, 0)

    def denied(self, candidate, code, *, context=None, **kwargs):
        r = self.check(candidate, context=context, **kwargs)
        self.assertFalse(r.source_envelope_valid)
        self.assertFalse(r.untrusted_a228_scenario_bound)
        self.assertFalse(r.nominal_sources_distinct)
        self.assertEqual(r.pairwise_overlap_count, 0)
        self.assertEqual(r.same_field_pair_counts, (0, 0, 0, 0, 0))
        self.assertEqual(r.cross_role_overlap_pairs, 0)
        self.assertEqual(r.intra_source_role_collapses, 0)
        self.assertEqual(r.affected_requirements, ())
        self.assertEqual(r.local_claim_digest, "")
        self.assertEqual(r.code, code)
        self.no_authority(r)

    def change_top(self, key, value, code):
        g = make_graph()
        g[key] = value
        self.denied(g, code)

    def change_source(self, key, value, code):
        g = make_graph()
        g["sources"][0][key] = value
        self.denied(g, code)

    def overlap(self, field, *, i=0, j=1):
        g = make_graph()
        g["sources"][j][field] = g["sources"][i][field]
        return self.check(g)

    def test_01_all_different_host_labels_are_not_real_independence(self):
        r = self.check()
        self.assertTrue(r.source_envelope_valid)
        self.assertTrue(r.nominal_sources_distinct)
        self.assertEqual(r.pairwise_overlap_count, 0)
        self.assertEqual(r.intra_source_role_collapses, 0)
        self.assertEqual(r.affected_requirements, ())
        self.assertEqual(r.code, "DISTINCT_HOST_LABELS_STILL_NOT_INDEPENDENCE_PROOF")
        self.no_authority(r)

    def test_02_shared_controller_detected(self):
        r = self.overlap("claimed_controller_id")
        self.assertEqual(r.pairwise_overlap_count, 1)
        self.assertEqual(r.same_field_pair_counts[0], 1)
        self.assertEqual(len(r.affected_requirements), 2)
        self.no_authority(r)

    def test_03_shared_ultimate_parent_detected(self):
        r = self.overlap("claimed_ultimate_parent_id")
        self.assertEqual(r.same_field_pair_counts[1], 1)
        self.no_authority(r)

    def test_04_shared_signing_principal_detected(self):
        r = self.overlap("claimed_signing_principal_id")
        self.assertEqual(r.same_field_pair_counts[2], 1)
        self.no_authority(r)

    def test_05_shared_audit_store_detected(self):
        r = self.overlap("claimed_audit_store_id")
        self.assertEqual(r.same_field_pair_counts[3], 1)
        self.no_authority(r)

    def test_06_shared_recovery_path_detected(self):
        r = self.overlap("claimed_recovery_principal_id")
        self.assertEqual(r.same_field_pair_counts[4], 1)
        self.no_authority(r)

    def test_07_five_shared_domains_are_one_affected_pair(self):
        g = make_graph()
        for field in CONTROL_LABEL_FIELDS:
            g["sources"][1][field] = g["sources"][0][field]
        r = self.check(g)
        self.assertEqual(r.pairwise_overlap_count, 1)
        self.assertEqual(r.same_field_pair_counts, (1, 1, 1, 1, 1))
        self.no_authority(r)

    def test_08_intra_source_controller_signer_collapse(self):
        g = make_graph()
        g["sources"][0]["claimed_signing_principal_id"] = g["sources"][0]["claimed_controller_id"]
        r = self.check(g)
        self.assertEqual(r.intra_source_role_collapses, 1)
        self.assertEqual(r.pairwise_overlap_count, 0)
        self.assertEqual(r.affected_requirements, (g["sources"][0]["requirement_id"],))
        self.no_authority(r)

    def test_09_cross_role_overlap_detected(self):
        g = make_graph()
        g["sources"][1]["claimed_recovery_principal_id"] = g["sources"][0]["claimed_controller_id"]
        r = self.check(g)
        self.assertEqual(r.pairwise_overlap_count, 1)
        self.assertEqual(r.cross_role_overlap_pairs, 1)
        self.assertEqual(r.same_field_pair_counts, (0, 0, 0, 0, 0))
        self.no_authority(r)

    def test_10_three_sources_same_parent_create_three_pairs(self):
        g = make_graph()
        for index in (1, 2):
            g["sources"][index]["claimed_ultimate_parent_id"] = g["sources"][0]["claimed_ultimate_parent_id"]
        r = self.check(g)
        self.assertEqual(r.pairwise_overlap_count, 3)
        self.assertEqual(r.same_field_pair_counts[1], 3)
        self.assertEqual(len(r.affected_requirements), 3)
        self.no_authority(r)

    def test_11_all_twelve_share_a_parent_sixty_six_pairs(self):
        g = make_graph()
        for row in g["sources"][1:]:
            row["claimed_ultimate_parent_id"] = g["sources"][0]["claimed_ultimate_parent_id"]
        r = self.check(g)
        self.assertEqual(r.pairwise_overlap_count, 66)
        self.assertEqual(r.same_field_pair_counts, (0, 66, 0, 0, 0))
        self.assertEqual(len(r.affected_requirements), 12)
        self.no_authority(r)

    def test_12_all_five_domains_shared_still_sixty_six_pairs(self):
        g = make_graph()
        for row in g["sources"][1:]:
            for field in CONTROL_LABEL_FIELDS:
                row[field] = g["sources"][0][field]
        r = self.check(g)
        self.assertEqual(r.pairwise_overlap_count, 66)
        self.assertEqual(r.same_field_pair_counts, (66, 66, 66, 66, 66))
        self.no_authority(r)

    def test_13_reversed_rows_have_same_local_digest(self):
        g = make_graph()
        a = self.check(g)
        g["sources"].reverse()
        self.assertEqual(a, self.check(g))

    def test_14_changing_label_changes_only_local_digest(self):
        g = make_graph()
        a = self.check(g)
        g["sources"][0]["claimed_controller_id"] += "-new"
        b = self.check(g)
        self.assertNotEqual(a.local_claim_digest, b.local_claim_digest)
        self.no_authority(a)
        self.no_authority(b)

    def test_15_json_claims_still_untrusted(self):
        r = self.check(json.dumps(make_graph()))
        self.assertTrue(r.source_envelope_valid)
        self.no_authority(r)

    def test_16_pure_repeat_never_mutates_input(self):
        g = make_graph()
        before = copy.deepcopy(g)
        for _ in range(3):
            self.no_authority(self.check(g))
        self.assertEqual(before, g)

    def test_17_frozen_outcome_cannot_become_authority(self):
        with self.assertRaises(FrozenInstanceError):
            self.check().external_evidence_accepted = True

    def test_18_all_330_cross_source_same_field_collisions(self):
        context = upstream_for_a229()
        template = make_graph(context=context)
        count = 0
        for i in range(12):
            for j in range(i + 1, 12):
                for field in CONTROL_LABEL_FIELDS:
                    with self.subTest(i=i, j=j, field=field):
                        g = dict(template)
                        g["sources"] = [dict(s) for s in template["sources"]]
                        g["sources"][j][field] = g["sources"][i][field]
                        r = self.check(g, context=context)
                        self.assertTrue(r.source_envelope_valid)
                        self.assertEqual(r.pairwise_overlap_count, 1)
                        self.assertEqual(len(r.affected_requirements), 2)
                        self.no_authority(r)
                        count += 1
        self.assertEqual(count, 330)

    def test_19_nonobject_top_rejected(self):
        for bad in (None, {}, [], True, 2):
            self.denied(bad, "COMMON_CONTROL_ENVELOPE_NOT_EXACT")

    def test_20_extra_top_field_rejected(self):
        g = make_graph()
        g["is_independent"] = True
        self.denied(g, "COMMON_CONTROL_ENVELOPE_NOT_EXACT")

    def test_21_missing_top_field_rejected(self):
        for field in ("schema", "sources", "a228_scenario_digest"):
            g = make_graph()
            del g[field]
            self.denied(g, "COMMON_CONTROL_ENVELOPE_NOT_EXACT")

    def test_22_unknown_schema_rejected(self):
        self.change_top("schema", "VERIFIED", "COMMON_CONTROL_SCHEMA_UNSUPPORTED")

    def test_23_wrong_owner_rejected(self):
        self.change_top("owner_id", "other", "COMMON_CONTROL_SCOPE_MISMATCH")

    def test_24_wrong_tenant_rejected(self):
        self.change_top("tenant_id", "other", "COMMON_CONTROL_SCOPE_MISMATCH")

    def test_25_wrong_workspace_rejected(self):
        self.change_top("workspace_id", "other", "COMMON_CONTROL_SCOPE_MISMATCH")

    def test_26_invalid_expected_owner_rejected(self):
        self.denied(make_graph(), "INVALID_EXPECTED_SCOPE", expected_owner_id="bad owner")

    def test_27_invalid_expected_tenant_rejected(self):
        self.denied(make_graph(), "INVALID_EXPECTED_SCOPE", expected_tenant_id=True)

    def test_28_invalid_expected_workspace_rejected(self):
        self.denied(make_graph(), "INVALID_EXPECTED_SCOPE", expected_workspace_id=7)

    def test_29_boolean_owner_not_equal_string(self):
        self.change_top("owner_id", True, "COMMON_CONTROL_SCOPE_MISMATCH")

    def test_30_host_cannot_claim_real_dependency_audit(self):
        self.change_top("study_state", "AUDITED", "HOST_CANNOT_ASSERT_REAL_DEPENDENCY_AUDIT")

    def test_31_host_cannot_choose_root_model(self):
        self.change_top("model_selection_state", "OFFLINE", "NO_MODEL_CHOICE_FROM_HOST_LABELS")

    def test_32_host_cannot_assert_owner_signoff(self):
        self.change_top("owner_signoff_state", "SIGNED", "HOST_CANNOT_ASSERT_OWNER_SIGNOFF")

    def test_33_host_cannot_claim_external_contact(self):
        self.change_top("source_contact_state", "CONTACTED", "EXTERNAL_CONTACT_NOT_AUTHORIZED")

    def test_34_host_cannot_override_hard_no_go(self):
        self.change_top("claimed_gate_state", "GO", "HOST_CANNOT_OVERRIDE_HARD_NO_GO")

    def test_35_fake_external_p0_rejected(self):
        for bad in (True, 1, 6, "0", -1):
            self.change_top("external_p0_homologated", bad, "FALSE_EXTERNAL_P0_CLAIM")

    def test_36_auto_resend_denied(self):
        self.change_top("uncertain_resend_policy", "AUTO_RESEND", "UNCERTAIN_MUST_FAIL_CLOSED")

    def test_37_invalid_a228_scenario_cannot_anchor_graph(self):
        context = upstream_for_a229()
        g = make_graph(context=context)
        context[0]["claimed_gate_state"] = "GO"
        self.denied(g, "A228_BLOCKED_SYNTHETIC_SCENARIO_REQUIRED", context=context)

    def test_38_invalid_a227_contract_cannot_anchor_graph(self):
        context = upstream_for_a229()
        g = make_graph(context=context)
        context[1]["owner_signoff_state"] = "SIGNED"
        self.denied(g, "A228_BLOCKED_SYNTHETIC_SCENARIO_REQUIRED", context=context)

    def test_39_fake_a228_scenario_digest_rejected(self):
        self.change_top("a228_scenario_digest", "0" * 64, "A228_LOCAL_SCENARIO_BINDING_MISMATCH")

    def test_40_malformed_scenario_digest_rejected(self):
        for bad in (True, None, "f" * 63, "F" * 64):
            self.change_top("a228_scenario_digest", bad, "A228_LOCAL_SCENARIO_BINDING_MISMATCH")

    def test_41_missing_source_row_rejected(self):
        g = make_graph()
        g["sources"].pop()
        self.denied(g, "TWELVE_CONTROL_SOURCE_CLAIMS_REQUIRED")

    def test_42_extra_source_row_rejected(self):
        g = make_graph()
        g["sources"].append(copy.deepcopy(g["sources"][0]))
        self.denied(g, "TWELVE_CONTROL_SOURCE_CLAIMS_REQUIRED")

    def test_43_sources_must_be_list(self):
        g = make_graph()
        g["sources"] = tuple(g["sources"])
        self.denied(g, "TWELVE_CONTROL_SOURCE_CLAIMS_REQUIRED")

    def test_44_source_row_must_be_object(self):
        g = make_graph()
        g["sources"][0] = "verified"
        self.denied(g, "CONTROL_SOURCE_ROW_NOT_EXACT")

    def test_45_extra_or_missing_row_field_rejected(self):
        self.change_source("real_independence", True, "CONTROL_SOURCE_ROW_NOT_EXACT")
        g = make_graph()
        del g["sources"][0]["claimed_audit_store_id"]
        self.denied(g, "CONTROL_SOURCE_ROW_NOT_EXACT")

    def test_46_unknown_requirement_rejected(self):
        self.change_source("requirement_id", "host_override", "UNKNOWN_CONTROL_REQUIREMENT")

    def test_47_duplicate_requirement_rejected(self):
        g = make_graph()
        g["sources"][1]["requirement_id"] = g["sources"][0]["requirement_id"]
        self.denied(g, "DUPLICATE_CONTROL_REQUIREMENT")

    def test_48_duplicate_nominal_source_rejected(self):
        g = make_graph()
        g["sources"][1]["nominal_source_id"] = g["sources"][0]["nominal_source_id"]
        self.denied(g, "DUPLICATE_NOMINAL_SOURCE_LABEL")

    def test_49_invalid_host_label_rejected(self):
        for bad in ("", "slash/path", True, None, 123):
            self.change_source("claimed_controller_id", bad, "INVALID_HOST_CONTROL_LABEL")

    def test_50_host_cannot_promote_claimed_authority(self):
        self.change_source("claim_origin", "INDEPENDENT_EXTERNAL", "HOST_CANNOT_CLAIM_INDEPENDENT_CONTROL_ORIGIN")
        self.change_source("issuer_identity_state", "VERIFIED", "HOST_CANNOT_PROMOTE_CONTROL_LABELS_TO_PROOF")
        self.change_source("dependency_audit_state", "OBTAINED", "HOST_CANNOT_PROMOTE_CONTROL_LABELS_TO_PROOF")


if __name__ == "__main__":
    unittest.main()
