"""A232: 50 adversarial checks of historical 6-P0 crosswalk, no GO."""
from dataclasses import FrozenInstanceError
import copy
import json
import unittest

from labs.a231_external_control_proof_plan import preflight_external_control_proof_plan
from labs.a232_six_p0_evidence_crosswalk import (
    SCHEMA, P0_DEFINITIONS, preflight_six_p0_crosswalk,
)
from labs.test_a231_external_control_proof_plan import make_plan
from labs.test_a230_host_label_rewrite import setup_case
from labs.test_a223_owner_security_priority import OWNER, TENANT, WORKSPACE


def make_matrix(*, context=None, plan=None):
    if context is None:
        context = setup_case()
    baseline, rewrite, args, _ = context
    if plan is None:
        plan = make_plan(context)
    previous = preflight_external_control_proof_plan(
        plan, a230_rewrite=rewrite, a229_graph=baseline, **args)
    assert previous.plan_shape_complete and not previous.external_evidence_accepted
    gates = []
    for pid, (missing, requirements, extra) in P0_DEFINITIONS.items():
        gates.append(dict(
            p0_id=pid, missing_primary_evidence=missing,
            supporting_a231_requirements=list(requirements),
            missing_nonchecklist_gates=list(extra),
            external_evidence_state="NOT_OBTAINED",
            native_evidence_state="NOT_PROVEN",
            independent_review_state="NOT_DONE",
            acceptance_state="HARD_NO_GO",
        ))
    matrix = dict(
        schema=SCHEMA, owner_id=OWNER, tenant_id=TENANT,
        workspace_id=WORKSPACE, a231_plan_digest=previous.local_plan_digest,
        matrix_state="RESEARCH_CROSSWALK_ONLY",
        owner_signoff_state="NOT_REQUESTED",
        source_contact_state="NOT_CONTACTED",
        claimed_gate_state="HARD_NO_GO", external_p0_homologated=0,
        uncertain_resend_policy="ZERO_AUTO_RESEND", p0_gates=gates,
    )
    return matrix, plan, context


class A232SixP0CrosswalkTests(unittest.TestCase):
    def check(self, bundle=None, **overrides):
        if bundle is None:
            bundle = make_matrix()
        matrix, plan, context = bundle
        baseline, rewrite, args, _ = context
        params = dict(args)
        params.update(overrides)
        return preflight_six_p0_crosswalk(
            matrix, a231_plan=plan, a230_rewrite=rewrite,
            a229_graph=baseline, **params,
        )

    def no_authority(self, result):
        self.assertFalse(result.native_sqlite_read_proven)
        self.assertFalse(result.native_sqlite_write_proven)
        self.assertFalse(result.independent_owner_verified)
        self.assertFalse(result.independent_provider_receipt_verified)
        self.assertFalse(result.external_evidence_accepted)
        self.assertFalse(result.owner_signoff_valid)
        self.assertFalse(result.provider_final_effect_verified)
        self.assertEqual(result.external_p0_homologated, 0)
        self.assertEqual(result.p0_gates_homologated, 0)
        for field in (
            "may_accept_security_proof", "may_select_model", "may_contact_person",
            "may_run_external_challenge", "may_commit_budget", "may_provision",
            "may_generate_key", "may_sign", "may_connect", "may_confirm",
            "may_auto_resend",
        ):
            self.assertFalse(getattr(result, field), field)

    def denied(self, bundle, code, **kwargs):
        result = self.check(bundle, **kwargs)
        self.assertEqual(result.code, code)
        self.assertFalse(result.shape_complete)
        self.assertFalse(result.untrusted_a231_bound)
        self.assertEqual(result.p0_gates_documented, 0)
        self.assertEqual(result.supporting_challenge_cells, ())
        self.assertEqual(result.local_matrix_digest, "")
        self.no_authority(result)

    def mutate_top(self, field, value, code):
        bundle = make_matrix()
        bundle[0][field] = value
        self.denied(bundle, code)

    def mutate_gate(self, field, value, code, index=0):
        bundle = make_matrix()
        bundle[0]["p0_gates"][index][field] = value
        self.denied(bundle, code)

    def test_01_six_open_gates_cannot_auto_homologate(self):
        r = self.check()
        self.assertTrue(r.shape_complete)
        self.assertEqual(r.p0_gates_documented, 6)
        self.assertEqual(r.p0_gates_homologated, 0)
        self.assertEqual(r.code, "SIX_P0_MAPPED_ZERO_INDEPENDENT_PROOFS_AND_NATIVE_GATES_OPEN")
        self.no_authority(r)

    def test_02_mapped_cells_by_p0(self):
        r = self.check()
        self.assertEqual(r.supporting_challenge_cells, (35, 30, 30, 30, 0, 10))
        self.assertEqual(r.unmapped_challenge_cells, 0)
        self.no_authority(r)

    def test_03_native_sqlite_read_never_claimed_by_60_external_checks(self):
        self.assertEqual(P0_DEFINITIONS["P0-5"][1], ())
        self.assertIn("ATOMIC_NATIVE_SQLITE_READ_HANDLE", P0_DEFINITIONS["P0-5"][2])
        self.no_authority(self.check())

    def test_04_native_sqlite_write_still_needs_commit_recovery(self):
        self.assertIn("POST_COMMIT_OUTCOME_RECONCILIATION", P0_DEFINITIONS["P0-6"][2])
        self.no_authority(self.check())

    def test_05_owner_enrollment_not_in_a231_proofs(self):
        self.assertIn("REAL_OWNER_ENROLLMENT", P0_DEFINITIONS["P0-1"][2])
        self.no_authority(self.check())

    def test_06_provider_reconciliation_still_external(self):
        self.assertIn("INDEPENDENT_PROVIDER_RECONCILIATION", P0_DEFINITIONS["P0-2"][2])
        self.no_authority(self.check())

    def test_07_business_event_identity_still_missing(self):
        self.assertIn("AUTHENTIC_BUSINESS_EVENT_IDENTITY", P0_DEFINITIONS["P0-3"][2])
        self.no_authority(self.check())

    def test_08_h0_independent_witness_still_missing(self):
        self.assertIn("INDEPENDENT_MONOTONIC_WITNESS", P0_DEFINITIONS["P0-4"][2])
        self.no_authority(self.check())

    def test_09_reordering_six_rows_keeps_canonical_digest(self):
        bundle = make_matrix()
        a = self.check(bundle)
        bundle[0]["p0_gates"].reverse()
        self.assertEqual(a, self.check(bundle))

    def test_10_all_60_a231_challenges_still_unexecuted(self):
        bundle = make_matrix()
        self.assertEqual(len(bundle[1]["challenges"]), 60)
        self.assertTrue(all(x["evidence_state"] == "NOT_OBTAINED" for x in bundle[1]["challenges"]))
        self.no_authority(self.check(bundle))

    def test_11_a231_forged_witness_rejected(self):
        bundle = make_matrix()
        bundle[1]["challenges"][0]["independent_witness_state"] = "VERIFIED"
        self.denied(bundle, "A231_BLOCKED_UNEXECUTED_PROOF_PLAN_REQUIRED")

    def test_12_a231_fake_reviewer_rejected(self):
        bundle = make_matrix()
        bundle[1]["challenges"][0]["reviewer_state"] = "DONE"
        self.denied(bundle, "A231_BLOCKED_UNEXECUTED_PROOF_PLAN_REQUIRED")

    def test_13_a231_digest_mismatch_rejected(self):
        self.mutate_top("a231_plan_digest", "0"*64, "A231_LOCAL_MATRIX_BINDING_MISMATCH")

    def test_14_a231_plan_changed_after_binding_rejected(self):
        bundle = make_matrix()
        bundle[1]["challenges"].reverse()
        # Row ordering is canonicalized and must NOT create a false mismatch.
        self.assertTrue(self.check(bundle).shape_complete)
        bundle[1]["owner_signoff_state"] = "SIGNED"
        self.denied(bundle, "A231_BLOCKED_UNEXECUTED_PROOF_PLAN_REQUIRED")

    def test_15_p0_ids_must_be_exact_set(self):
        self.assertEqual(set(P0_DEFINITIONS), {f"P0-{i}" for i in range(1, 7)})
        self.no_authority(self.check())

    def test_16_duplicate_p0_rejected(self):
        bundle = make_matrix()
        bundle[0]["p0_gates"][1]["p0_id"] = "P0-1"
        self.denied(bundle, "DUPLICATE_P0_GATE")

    def test_17_missing_p0_rejected(self):
        bundle = make_matrix()
        bundle[0]["p0_gates"].pop()
        self.denied(bundle, "SIX_P0_GATES_REQUIRED")

    def test_18_extra_p0_rejected(self):
        bundle = make_matrix()
        bundle[0]["p0_gates"].append(copy.deepcopy(bundle[0]["p0_gates"][0]))
        self.denied(bundle, "SIX_P0_GATES_REQUIRED")

    def test_19_unknown_p0_rejected(self):
        self.mutate_gate("p0_id", "P0-7", "UNKNOWN_P0_GATE")

    def test_20_external_native_gate_substitution_rejected(self):
        self.mutate_gate("missing_nonchecklist_gates", [], "P0_EVIDENCE_CROSSWALK_MISMATCH", index=4)

    def test_21_fake_read_success_rejected(self):
        self.mutate_gate("native_evidence_state", "PROVEN", "HOST_CANNOT_ASSERT_P0_EVIDENCE_OR_ACCEPTANCE", index=4)

    def test_22_fake_write_success_rejected(self):
        self.mutate_gate("native_evidence_state", "PROVEN", "HOST_CANNOT_ASSERT_P0_EVIDENCE_OR_ACCEPTANCE", index=5)

    def test_23_acceptance_go_rejected(self):
        self.mutate_gate("acceptance_state", "GO", "HOST_CANNOT_ASSERT_P0_EVIDENCE_OR_ACCEPTANCE")

    def test_24_external_receipt_claim_rejected(self):
        self.mutate_gate("external_evidence_state", "OBTAINED", "HOST_CANNOT_ASSERT_P0_EVIDENCE_OR_ACCEPTANCE", index=1)

    def test_25_p0_reviewer_claim_rejected(self):
        self.mutate_gate("independent_review_state", "DONE", "HOST_CANNOT_ASSERT_P0_EVIDENCE_OR_ACCEPTANCE")

    def test_26_no_input_mutation(self):
        bundle = make_matrix()
        copy_prior = copy.deepcopy(bundle)
        for _ in range(3):
            self.no_authority(self.check(bundle))
        self.assertEqual(bundle, copy_prior)

    def test_27_immutable_result_cannot_upgrade(self):
        with self.assertRaises(FrozenInstanceError):
            self.check().p0_gates_homologated = 6

    def test_28_huge_json_string_fails_closed(self):
        bundle = make_matrix()
        payload = json.dumps(bundle[0])
        if len(payload.encode("utf-8")) > 8192:
            self.denied((payload, bundle[1], bundle[2]), "AMBIGUOUS_OR_OVERSIZED_P0_MATRIX_JSON")
        else:
            self.no_authority(self.check((payload, bundle[1], bundle[2])))


_MUTATIONS = (
    ("schema", "VERIFIED", "P0_MATRIX_SCHEMA_UNSUPPORTED"),
    ("owner_id", "foreign", "P0_MATRIX_SCOPE_MISMATCH"),
    ("tenant_id", "foreign", "P0_MATRIX_SCOPE_MISMATCH"),
    ("workspace_id", "foreign", "P0_MATRIX_SCOPE_MISMATCH"),
    ("matrix_state", "GO", "HOST_CANNOT_HOMOLOGATE_P0_MATRIX"),
    ("owner_signoff_state", "SIGNED", "HOST_CANNOT_ASSERT_OWNER_SIGNOFF"),
    ("source_contact_state", "CONTACTED", "HOST_CANNOT_CLAIM_SOURCE_CONTACT"),
    ("claimed_gate_state", "GO", "HOST_CANNOT_OVERRIDE_HARD_NO_GO"),
    ("uncertain_resend_policy", "AUTO_RESEND", "UNCERTAIN_ZERO_AUTO_RESEND_REQUIRED"),
    ("external_p0_homologated", 1, "FALSE_EXTERNAL_P0_HOMOLOGATION"),
    ("external_p0_homologated", 6, "FALSE_EXTERNAL_P0_HOMOLOGATION"),
    ("external_p0_homologated", True, "FALSE_EXTERNAL_P0_HOMOLOGATION"),
    ("external_p0_homologated", "0", "FALSE_EXTERNAL_P0_HOMOLOGATION"),
    ("a231_plan_digest", "F"*64, "A231_LOCAL_MATRIX_BINDING_MISMATCH"),
    ("a231_plan_digest", None, "A231_LOCAL_MATRIX_BINDING_MISMATCH"),
    ("a231_plan_digest", True, "A231_LOCAL_MATRIX_BINDING_MISMATCH"),
    ("owner_id", True, "P0_MATRIX_SCOPE_MISMATCH"),
    ("tenant_id", None, "P0_MATRIX_SCOPE_MISMATCH"),
    ("workspace_id", 2, "P0_MATRIX_SCOPE_MISMATCH"),
    ("matrix_state", True, "HOST_CANNOT_HOMOLOGATE_P0_MATRIX"),
    ("claimed_gate_state", True, "HOST_CANNOT_OVERRIDE_HARD_NO_GO"),
    ("uncertain_resend_policy", False, "UNCERTAIN_ZERO_AUTO_RESEND_REQUIRED"),
)


def _mutation_test(field, bad, code):
    def case(self):
        self.mutate_top(field, bad, code)
    return case


for i, (field, value, code) in enumerate(_MUTATIONS, start=29):
    setattr(A232SixP0CrosswalkTests, f"test_{i:02d}_untrusted_{field}",
            _mutation_test(field, value, code))


if __name__ == "__main__":
    unittest.main()
