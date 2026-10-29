"""A230: 50 adversarial tests for host-renamed controller labels (synthetic only)."""
from dataclasses import FrozenInstanceError
import copy
import json
import unittest

from labs.a229_common_control_domain_claims import (
    CONTROL_LABEL_FIELDS, preflight_common_control_claims,
)
from labs.a230_host_label_rewrite import SCHEMA, preflight_host_label_rewrite
from labs.test_a229_common_control_domain_claims import make_graph, upstream_for_a229
from labs.test_a223_owner_security_priority import OWNER, TENANT, WORKSPACE


def setup_case(*, baseline=None, context=None):
    if context is None:
        context = upstream_for_a229()
    a228, a227, items, _ = context
    a226, a225, a224, a223, a222 = items
    args = dict(
        a228_scenario=a228, a227_contract=a227, a226_claims=a226,
        a225_untrusted_claim=a225, a224_catalog=a224, a223_note=a223,
        a222_matrix=a222, expected_owner_id=OWNER,
        expected_tenant_id=TENANT, expected_workspace_id=WORKSPACE,
    )
    if baseline is None:
        baseline = make_graph(context=context)
    prior = preflight_common_control_claims(baseline, **args)
    assert prior.source_envelope_valid and not prior.external_evidence_accepted
    candidate = dict(
        schema=SCHEMA, owner_id=OWNER, tenant_id=TENANT,
        workspace_id=WORKSPACE,
        a229_reference_digest=prior.local_claim_digest,
        rewrite_state="HOST_CONTROLLED_RENAME_STUDY_ONLY",
        model_selection_state="NO_MODEL_SELECTED",
        owner_signoff_state="NOT_REQUESTED",
        source_contact_state="NOT_CONTACTED",
        claimed_gate_state="HARD_NO_GO",
        external_p0_homologated=0,
        uncertain_resend_policy="ZERO_AUTO_RESEND",
        rewritten_sources=copy.deepcopy(baseline["sources"]),
    )
    return baseline, candidate, args, context


def shared_baseline(field="claimed_controller_id", *, count=2, context=None):
    if context is None:
        context = upstream_for_a229()
    baseline = make_graph(context=context)
    for row in baseline["sources"][1:count]:
        row[field] = baseline["sources"][0][field]
    return baseline, context


class A230HostRenameTests(unittest.TestCase):
    def check(self, case=None, *, baseline=None, args=None, context=None, **overrides):
        if case is None:
            baseline, candidate, args, context = setup_case(
                baseline=baseline, context=context)
        else:
            baseline, candidate, args, context = case
        params = dict(args)
        params.update(overrides)
        return preflight_host_label_rewrite(candidate, a229_graph=baseline, **params)

    def no_authority(self, result):
        for field in (
            "actual_control_domains_independent", "actual_issuer_identities_verified",
            "external_evidence_accepted", "owner_signoff_valid",
            "provider_final_effect_verified", "may_accept_security_proof",
            "may_select_model", "may_contact_person", "may_run_external_challenge",
            "may_commit_budget", "may_provision", "may_generate_key",
            "may_sign", "may_connect", "may_confirm", "may_auto_resend",
        ):
            self.assertFalse(getattr(result, field), field)
        self.assertEqual(result.external_p0_homologated, 0)

    def denied(self, case, code, **kwargs):
        result = self.check(case, **kwargs)
        self.assertEqual(result.code, code)
        self.assertFalse(result.envelope_valid)
        self.assertFalse(result.untrusted_a229_bound)
        self.assertFalse(result.rewrite_graph_valid)
        self.assertEqual(result.local_claim_digest, "")
        self.assertEqual(result.disappeared_visible_pairs, 0)
        self.no_authority(result)

    def test_01_distinct_labels_do_not_prove_independence(self):
        r = self.check()
        self.assertTrue(r.rewrite_graph_valid)
        self.assertEqual(r.before_visible_pair_count, 0)
        self.assertEqual(r.after_visible_pair_count, 0)
        self.assertEqual(r.changed_label_cells, 0)
        self.assertEqual(r.code, "UNCHANGED_HOST_LABELS_STILL_NOT_INDEPENDENCE")
        self.no_authority(r)

    def test_02_visible_overlap_without_rewrite_not_approved(self):
        baseline, context = shared_baseline()
        r = self.check(baseline=baseline, context=context)
        self.assertEqual((r.before_visible_pair_count, r.after_visible_pair_count), (1, 1))
        self.no_authority(r)

    def test_03_one_pair_hidden_by_host_rename(self):
        baseline, context = shared_baseline()
        case = setup_case(baseline=baseline, context=context)
        case[1]["rewritten_sources"][1]["claimed_controller_id"] = "disguised-controller-1"
        r = self.check(case)
        self.assertEqual((r.before_visible_pair_count, r.after_visible_pair_count, r.disappeared_visible_pairs), (1, 0, 1))
        self.assertEqual(r.code, "RENAME_REMOVED_ALL_VISIBLE_OVERLAPS_NOT_INDEPENDENCE")
        self.no_authority(r)

    def test_04_all_66_visible_pairs_hidden_by_renaming(self):
        baseline, context = shared_baseline("claimed_ultimate_parent_id", count=12)
        case = setup_case(baseline=baseline, context=context)
        for i, node in enumerate(case[1]["rewritten_sources"]):
            node["claimed_ultimate_parent_id"] = f"disguised-parent-{i}"
        r = self.check(case)
        self.assertEqual((r.before_visible_pair_count, r.after_visible_pair_count, r.disappeared_visible_pairs), (66, 0, 66))
        self.assertEqual((r.changed_label_cells, r.changed_source_rows), (12, 12))
        self.no_authority(r)

    def test_05_partial_disguise_keeps_one_visible_pair(self):
        baseline, context = shared_baseline(count=3)
        case = setup_case(baseline=baseline, context=context)
        case[1]["rewritten_sources"][2]["claimed_controller_id"] = "unrelated-controller-2"
        r = self.check(case)
        self.assertEqual((r.before_visible_pair_count, r.after_visible_pair_count, r.disappeared_visible_pairs), (3, 1, 2))
        self.assertEqual(r.code, "RENAME_REMOVED_SOME_VISIBLE_OVERLAPS_NOT_INDEPENDENCE")
        self.no_authority(r)

    def test_06_rewritten_noncolliding_labels_still_no_proof(self):
        case = setup_case()
        case[1]["rewritten_sources"][0]["claimed_controller_id"] = "new-controller"
        r = self.check(case)
        self.assertEqual(r.disappeared_visible_pairs, 0)
        self.assertEqual(r.changed_label_cells, 1)
        self.assertEqual(r.code, "RENAMED_HOST_LABELS_STILL_NOT_INDEPENDENCE")
        self.no_authority(r)

    def test_07_hide_signing_principal(self):
        self._hide("claimed_signing_principal_id")

    def test_08_hide_audit_store(self):
        self._hide("claimed_audit_store_id")

    def test_09_hide_recovery_principal(self):
        self._hide("claimed_recovery_principal_id")

    def test_10_hide_ultimate_parent(self):
        self._hide("claimed_ultimate_parent_id")

    def _hide(self, field):
        baseline, context = shared_baseline(field)
        case = setup_case(baseline=baseline, context=context)
        case[1]["rewritten_sources"][1][field] = "disguised-independent"
        r = self.check(case)
        self.assertEqual(r.disappeared_visible_pairs, 1)
        self.no_authority(r)

    def test_11_cross_role_collision_can_be_hidden(self):
        baseline, context = shared_baseline()
        baseline["sources"][1]["claimed_controller_id"] = "controller-1"
        baseline["sources"][1]["claimed_recovery_principal_id"] = baseline["sources"][0]["claimed_controller_id"]
        case = setup_case(baseline=baseline, context=context)
        case[1]["rewritten_sources"][1]["claimed_recovery_principal_id"] = "disguised-recovery"
        r = self.check(case)
        self.assertEqual(r.disappeared_visible_pairs, 1)
        self.no_authority(r)

    def test_12_intra_source_collapse_can_be_hidden(self):
        case = setup_case()
        case[0]["sources"][0]["claimed_signing_principal_id"] = case[0]["sources"][0]["claimed_controller_id"]
        case = setup_case(baseline=case[0], context=case[3])
        case[1]["rewritten_sources"][0]["claimed_signing_principal_id"] = "masked-signing"
        r = self.check(case)
        self.assertEqual(r.disappeared_visible_pairs, 0)
        self.assertEqual(r.changed_label_cells, 1)
        self.no_authority(r)

    def test_13_source_row_order_does_not_change_local_digest(self):
        case = setup_case()
        a = self.check(case)
        case[1]["rewritten_sources"].reverse()
        b = self.check(case)
        self.assertEqual(a, b)

    def test_14_repeat_is_pure_without_mutating_inputs(self):
        case = setup_case()
        snapshot = copy.deepcopy(case[:3])
        for _ in range(3):
            self.no_authority(self.check(case))
        self.assertEqual(snapshot, case[:3])

    def test_15_immutable_result_cannot_be_promoted(self):
        r = self.check()
        with self.assertRaises(FrozenInstanceError):
            r.external_evidence_accepted = True

    def test_16_all_60_host_labels_can_be_renamed_without_trust(self):
        case = setup_case()
        for i, row in enumerate(case[1]["rewritten_sources"]):
            for j, field in enumerate(CONTROL_LABEL_FIELDS):
                row[field] = f"new-{i}-{j}"
        r = self.check(case)
        self.assertEqual((r.changed_label_cells, r.changed_source_rows), (60, 12))
        self.assertEqual(r.after_visible_pair_count, 0)
        self.no_authority(r)

    def test_17_renaming_can_introduce_new_overlap_without_trust(self):
        case = setup_case()
        case[1]["rewritten_sources"][1]["claimed_audit_store_id"] = "audit-0"
        r = self.check(case)
        self.assertEqual(r.after_visible_pair_count, 1)
        self.assertEqual(r.disappeared_visible_pairs, 0)
        self.no_authority(r)

    def test_18_json_never_certifies_and_size_limit_fails_closed(self):
        case = setup_case()
        payload = json.dumps(case[1])
        altered = (case[0], payload, case[2], case[3])
        r = self.check(altered)
        if len(payload.encode("utf-8")) > 8192:
            self.assertEqual(r.code, "AMBIGUOUS_OR_OVERSIZED_REWRITE_JSON")
        else:
            self.assertTrue(r.rewrite_graph_valid)
        self.no_authority(r)

    def test_19_untrusted_baseline_cannot_be_promoted(self):
        case = setup_case()
        case[0]["claimed_gate_state"] = "GO"
        self.denied(case, "A229_UNTRUSTED_BASELINE_REQUIRED")
        fresh = setup_case()
        serialized = (json.dumps(fresh[0]), fresh[1], fresh[2], fresh[3])
        self.denied(serialized, "A229_BASELINE_OBJECT_REQUIRED")

    def test_20_missing_top_field_rejected(self):
        case = setup_case()
        del case[1]["rewritten_sources"]
        self.denied(case, "REWRITE_ENVELOPE_NOT_EXACT")

    def test_21_extra_authority_flag_rejected(self):
        case = setup_case()
        case[1]["verified_independent"] = True
        self.denied(case, "REWRITE_ENVELOPE_NOT_EXACT")

    def test_22_wrong_envelope_types_rejected(self):
        case = setup_case()
        for bad in (None, False, [], "{}", 3):
            changed = (case[0], bad, case[2], case[3])
            self.no_authority(self.check(changed))

    def test_23_invalid_expected_owner_rejected(self):
        self.denied(setup_case(), "INVALID_EXPECTED_SCOPE", expected_owner_id="bad owner")

    def test_24_invalid_expected_tenant_rejected(self):
        self.denied(setup_case(), "INVALID_EXPECTED_SCOPE", expected_tenant_id=True)

    def test_25_invalid_expected_workspace_rejected(self):
        self.denied(setup_case(), "INVALID_EXPECTED_SCOPE", expected_workspace_id=0)

    def test_26_rewritten_rows_must_be_full_list(self):
        for bad in ([], None, tuple(), ["not-a-source"] * 12):
            case = setup_case()
            case[1]["rewritten_sources"] = bad
            self.no_authority(self.check(case))

    def test_27_source_identity_cannot_be_renamed(self):
        case = setup_case()
        case[1]["rewritten_sources"][0]["nominal_source_id"] = "renamed-source"
        self.denied(case, "REWRITE_CHANGED_SOURCE_IDENTITY_OR_PROVENANCE")

    def test_28_source_provenance_cannot_be_renamed(self):
        case = setup_case()
        case[1]["rewritten_sources"][0]["claim_origin"] = "INDEPENDENT_EXTERNAL"
        self.denied(case, "REWRITTEN_A229_GRAPH_INVALID")


# 22 individually named contract-mutation cases, in addition to the 28 above.
# These are independently executed unittest cases, not synthetic pass counters.
_MUTATIONS = (
    ("schema", "VERIFIED", "REWRITE_SCHEMA_UNSUPPORTED"),
    ("owner_id", "foreign", "REWRITE_SCOPE_MISMATCH"),
    ("tenant_id", "foreign", "REWRITE_SCOPE_MISMATCH"),
    ("workspace_id", "foreign", "REWRITE_SCOPE_MISMATCH"),
    ("rewrite_state", "AUDITED", "HOST_CANNOT_CLAIM_REAL_DEPENDENCY_AUDIT"),
    ("model_selection_state", "OFFLINE", "HOST_CANNOT_SELECT_ROOT_MODEL"),
    ("owner_signoff_state", "SIGNED", "HOST_CANNOT_CLAIM_OWNER_SIGNOFF"),
    ("source_contact_state", "CONTACTED", "HOST_CANNOT_CLAIM_EXTERNAL_CONTACT"),
    ("claimed_gate_state", "GO", "HOST_CANNOT_OVERRIDE_HARD_NO_GO"),
    ("uncertain_resend_policy", "AUTO_RESEND", "UNCERTAIN_ZERO_AUTO_RESEND_REQUIRED"),
    ("external_p0_homologated", 1, "FALSE_EXTERNAL_P0_CLAIM"),
    ("external_p0_homologated", True, "FALSE_EXTERNAL_P0_CLAIM"),
    ("external_p0_homologated", "0", "FALSE_EXTERNAL_P0_CLAIM"),
    ("external_p0_homologated", -1, "FALSE_EXTERNAL_P0_CLAIM"),
    ("a229_reference_digest", "0" * 64, "A229_LOCAL_REWRITE_BINDING_MISMATCH"),
    ("a229_reference_digest", True, "A229_LOCAL_REWRITE_BINDING_MISMATCH"),
    ("a229_reference_digest", "F" * 64, "A229_LOCAL_REWRITE_BINDING_MISMATCH"),
    ("owner_id", True, "REWRITE_SCOPE_MISMATCH"),
    ("tenant_id", None, "REWRITE_SCOPE_MISMATCH"),
    ("workspace_id", 0, "REWRITE_SCOPE_MISMATCH"),
    ("rewrite_state", True, "HOST_CANNOT_CLAIM_REAL_DEPENDENCY_AUDIT"),
    ("model_selection_state", True, "HOST_CANNOT_SELECT_ROOT_MODEL"),
)


def _mutation_test(field, bad, code):
    def run(self):
        case = setup_case()
        case[1][field] = bad
        self.denied(case, code)
    return run


for index, (field, value, expected_code) in enumerate(_MUTATIONS, start=29):
    setattr(A230HostRenameTests, f"test_{index:02d}_mutated_{field}", _mutation_test(field, value, expected_code))


if __name__ == "__main__":
    unittest.main()
