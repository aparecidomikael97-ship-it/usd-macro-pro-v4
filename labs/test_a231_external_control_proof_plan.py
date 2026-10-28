"""A231: 50 fail-closed tests for 60 unexecuted external-control proof requests."""
from dataclasses import FrozenInstanceError
import copy
import json
import unittest

from labs.a227_independence_acceptance_contract import INDEPENDENCE_REQUIREMENTS
from labs.a231_external_control_proof_plan import (
    CHALLENGE_KINDS, SCHEMA, preflight_external_control_proof_plan,
)
from labs.a230_host_label_rewrite import preflight_host_label_rewrite
from labs.test_a230_host_label_rewrite import setup_case
from labs.test_a223_owner_security_priority import OWNER, TENANT, WORKSPACE


def make_plan(context=None):
    if context is None:
        context = setup_case()
    baseline, rewrite, args, _ = context
    earlier = preflight_host_label_rewrite(rewrite, a229_graph=baseline, **args)
    assert earlier.rewrite_graph_valid and not earlier.external_evidence_accepted
    rows = []
    for rid in INDEPENDENCE_REQUIREMENTS:
        for domain, kind in CHALLENGE_KINDS.items():
            rows.append(dict(
                requirement_id=rid, control_domain=domain, challenge_kind=kind,
                challenge_nonce_state="NOT_ISSUED",
                issuer_identity_state="NOT_VERIFIED",
                independent_witness_state="NOT_VERIFIED",
                external_acquisition_state="NOT_REQUESTED",
                evidence_state="NOT_OBTAINED", reviewer_state="NOT_ASSIGNED",
            ))
    return dict(
        schema=SCHEMA, owner_id=OWNER, tenant_id=TENANT, workspace_id=WORKSPACE,
        a230_local_claim_digest=earlier.local_claim_digest,
        plan_state="HOST_WRITTEN_UNEXECUTED_PLAN_ONLY",
        owner_signoff_state="NOT_REQUESTED", model_selection_state="NO_MODEL_SELECTED",
        source_contact_state="NOT_CONTACTED", claimed_gate_state="HARD_NO_GO",
        external_p0_homologated=0, uncertain_resend_policy="ZERO_AUTO_RESEND",
        challenges=rows,
    )


class A231ExternalControlProofPlanTests(unittest.TestCase):
    def check(self, candidate=None, *, context=None, **overrides):
        if context is None:
            context = setup_case()
        if candidate is None:
            candidate = make_plan(context)
        baseline, rewrite, args, _ = context
        params = dict(args)
        params.update(overrides)
        return preflight_external_control_proof_plan(
            candidate, a230_rewrite=rewrite, a229_graph=baseline, **params,
        )

    def no_authority(self, r):
        self.assertEqual((r.external_challenges_executed, r.real_control_domains_independently_verified), (0, 0))
        self.assertEqual(r.external_p0_homologated, 0)
        for name in (
            "actual_issuer_identity_verified", "actual_control_domains_independent",
            "external_evidence_accepted", "owner_signoff_valid",
            "provider_final_effect_verified", "may_accept_security_proof",
            "may_select_model", "may_contact_person", "may_run_external_challenge",
            "may_commit_budget", "may_provision", "may_generate_key",
            "may_sign", "may_connect", "may_confirm", "may_auto_resend",
        ):
            self.assertFalse(getattr(r, name), name)

    def denied(self, candidate, code, *, context=None, **overrides):
        r = self.check(candidate, context=context, **overrides)
        self.assertEqual(r.code, code)
        self.assertFalse(r.plan_shape_complete)
        self.assertFalse(r.untrusted_a230_bound)
        self.assertEqual(r.planned_challenges, 0)
        self.assertEqual(r.local_plan_digest, "")
        self.no_authority(r)

    def mutate_top(self, field, value, code):
        plan = make_plan()
        plan[field] = value
        self.denied(plan, code)

    def mutate_row(self, field, value, code):
        plan = make_plan()
        plan["challenges"][0][field] = value
        self.denied(plan, code)

    def test_01_complete_plan_still_has_zero_external_proofs(self):
        r = self.check()
        self.assertTrue(r.plan_shape_complete)
        self.assertEqual(r.planned_challenges, 60)
        self.assertEqual(r.code, "SIXTY_EXTERNAL_PROOFS_NOT_OBTAINED")
        self.no_authority(r)

    def test_02_plan_digest_canonical_independent_of_row_order(self):
        plan = make_plan()
        a = self.check(plan)
        plan["challenges"].reverse()
        self.assertEqual(self.check(plan), a)

    def test_03_rewrite_changes_plan_binding_without_external_authority(self):
        context = setup_case()
        a = self.check(make_plan(context), context=context)
        other = setup_case()
        other[1]["rewritten_sources"][0]["claimed_controller_id"] = "renamed-controller"
        b = self.check(make_plan(other), context=other)
        self.assertNotEqual(a.local_plan_digest, b.local_plan_digest)
        self.no_authority(a)
        self.no_authority(b)

    def test_04_oversized_serialized_plan_denied(self):
        plan = make_plan()
        payload = json.dumps(plan)
        self.assertGreater(len(payload.encode("utf-8")), 8192)
        self.denied(payload, "AMBIGUOUS_OR_OVERSIZED_PROOF_PLAN_JSON")

    def test_05_repeat_readonly_no_input_mutation(self):
        context = setup_case()
        plan = make_plan(context)
        before = copy.deepcopy(plan)
        for _ in range(3):
            self.no_authority(self.check(plan, context=context))
        self.assertEqual(plan, before)

    def test_06_frozen_output_cannot_upgrade_status(self):
        with self.assertRaises(FrozenInstanceError):
            self.check().external_evidence_accepted = True

    def test_07_a230_digest_mismatch_after_rewrite(self):
        context = setup_case()
        plan = make_plan(context)
        context[1]["rewritten_sources"][0]["claimed_controller_id"] = "other-label"
        self.denied(plan, "A230_LOCAL_PLAN_BINDING_MISMATCH", context=context)

    def test_08_upstream_a230_go_state_rejected(self):
        context = setup_case()
        plan = make_plan(context)
        context[1]["claimed_gate_state"] = "GO"
        self.denied(plan, "A230_BLOCKED_UNTRUSTED_PLAN_REQUIRED", context=context)

    def test_09_a230_serialized_still_not_valid_input(self):
        context = setup_case()
        plan = make_plan(context)
        context = (context[0], json.dumps(context[1]), context[2], context[3])
        self.denied(plan, "A230_UNTRUSTED_RESEARCH_INPUTS_REQUIRED", context=context)

    def test_10_a229_serialized_still_not_valid_input(self):
        context = setup_case()
        plan = make_plan(context)
        context = (json.dumps(context[0]), context[1], context[2], context[3])
        self.denied(plan, "A230_UNTRUSTED_RESEARCH_INPUTS_REQUIRED", context=context)

    def test_11_extra_authority_top_field_rejected(self):
        self.mutate_top("independence_verified", True, "PROOF_PLAN_ENVELOPE_NOT_EXACT")

    def test_12_missing_required_top_field_rejected(self):
        plan = make_plan()
        del plan["challenges"]
        self.denied(plan, "PROOF_PLAN_ENVELOPE_NOT_EXACT")

    def test_13_unknown_schema_rejected(self):
        self.mutate_top("schema", "VERIFIED", "PROOF_PLAN_SCHEMA_UNSUPPORTED")

    def test_14_foreign_owner_scope_rejected(self):
        self.mutate_top("owner_id", "foreign", "PROOF_PLAN_SCOPE_MISMATCH")

    def test_15_foreign_tenant_scope_rejected(self):
        self.mutate_top("tenant_id", "foreign", "PROOF_PLAN_SCOPE_MISMATCH")

    def test_16_foreign_workspace_scope_rejected(self):
        self.mutate_top("workspace_id", "foreign", "PROOF_PLAN_SCOPE_MISMATCH")

    def test_17_invalid_expected_owner_scope_rejected(self):
        self.denied(make_plan(), "INVALID_EXPECTED_SCOPE", expected_owner_id="bad scope")

    def test_18_boolean_expected_tenant_rejected(self):
        self.denied(make_plan(), "INVALID_EXPECTED_SCOPE", expected_tenant_id=True)

    def test_19_host_selected_model_rejected(self):
        self.mutate_top("model_selection_state", "KMS", "HOST_CANNOT_SELECT_MODEL")

    def test_20_host_requested_owner_signoff_rejected(self):
        self.mutate_top("owner_signoff_state", "SIGNED", "HOST_CANNOT_ASSERT_OWNER_SIGNOFF")

    def test_21_boolean_false_p0_rejected(self):
        self.mutate_top("external_p0_homologated", True, "FALSE_EXTERNAL_P0_HOMOLOGATION")

    def test_22_json_duplicate_key_rejected(self):
        # Fail closed independently of JSON size; duplicate keys cannot grant.
        self.denied('{"schema":"X","schema":"Y"}', "AMBIGUOUS_OR_OVERSIZED_PROOF_PLAN_JSON")

    def test_23_missing_row_rejected(self):
        plan = make_plan()
        plan["challenges"].pop()
        self.denied(plan, "SIXTY_UNEXECUTED_CHALLENGES_REQUIRED")

    def test_24_extra_row_rejected(self):
        plan = make_plan()
        plan["challenges"].append(copy.deepcopy(plan["challenges"][0]))
        self.denied(plan, "SIXTY_UNEXECUTED_CHALLENGES_REQUIRED")

    def test_25_wrong_rows_container_rejected(self):
        plan = make_plan()
        plan["challenges"] = tuple(plan["challenges"])
        self.denied(plan, "SIXTY_UNEXECUTED_CHALLENGES_REQUIRED")

    def test_26_nonobject_row_rejected(self):
        self.mutate_row("test_flag", True, "PROOF_CHALLENGE_ROW_NOT_EXACT")
        plan = make_plan()
        plan["challenges"][0] = "not-proof"
        self.denied(plan, "PROOF_CHALLENGE_ROW_NOT_EXACT")

    def test_27_extra_reviewer_credential_rejected(self):
        self.mutate_row("private_key", "DO_NOT_STORE", "PROOF_CHALLENGE_ROW_NOT_EXACT")

    def test_28_missing_challenge_field_rejected(self):
        plan = make_plan()
        del plan["challenges"][0]["challenge_nonce_state"]
        self.denied(plan, "PROOF_CHALLENGE_ROW_NOT_EXACT")

    def test_29_unknown_requirement_id_rejected(self):
        self.mutate_row("requirement_id", "not-a-requirement", "UNKNOWN_INDEPENDENCE_REQUIREMENT")

    def test_30_unknown_control_domain_rejected(self):
        self.mutate_row("control_domain", "unknown", "UNKNOWN_CONTROL_DOMAIN")

    def test_31_duplicate_cell_rejected(self):
        plan = make_plan()
        plan["challenges"][1] = copy.deepcopy(plan["challenges"][0])
        self.denied(plan, "DUPLICATE_CONTROL_PROOF_CHALLENGE")

    def test_32_wrong_kind_rejected(self):
        self.mutate_row("challenge_kind", "FAKE_ATTESTATION", "CONTROL_DOMAIN_CHALLENGE_KIND_MISMATCH")

    def test_33_60_distinct_research_cells_exact(self):
        plan = make_plan()
        pairs = {(x["requirement_id"], x["control_domain"]) for x in plan["challenges"]}
        self.assertEqual(len(pairs), 60)
        self.assertEqual(pairs, {(a, b) for a in INDEPENDENCE_REQUIREMENTS for b in CHALLENGE_KINDS})
        self.no_authority(self.check(plan))

    def test_34_each_control_domain_has_twelve_unexecuted_challenges(self):
        plan = make_plan()
        for domain in CHALLENGE_KINDS:
            selected = [x for x in plan["challenges"] if x["control_domain"] == domain]
            self.assertEqual(len(selected), 12)
            self.assertTrue(all(x["evidence_state"] == "NOT_OBTAINED" for x in selected))

    def test_35_no_real_nonce_or_witness_identity_is_issued(self):
        plan = make_plan()
        self.assertTrue(all(x["challenge_nonce_state"] == "NOT_ISSUED" and
                            x["independent_witness_state"] == "NOT_VERIFIED"
                            for x in plan["challenges"]))
        self.no_authority(self.check(plan))

    def test_36_invalid_plan_never_emits_anchoring_digest(self):
        plan = make_plan()
        plan["challenges"][0]["issuer_identity_state"] = "VERIFIED"
        self.denied(plan, "HOST_CANNOT_ASSERT_EXTERNAL_CHALLENGE_PROOF_OR_REVIEW")

    def test_37_reordered_fields_and_rows_still_canonical(self):
        plan = make_plan()
        same = dict(reversed(list(plan.items())))
        same["challenges"] = [dict(reversed(list(x.items()))) for x in plan["challenges"][::-1]]
        self.assertEqual(self.check(plan), self.check(same))

    def test_38_plan_does_not_mutate_upstream_rewrite(self):
        context = setup_case()
        prior = copy.deepcopy(context[:2])
        self.check(make_plan(context), context=context)
        self.assertEqual(context[:2], prior)

    def test_39_changed_nominal_identity_in_a230_still_rejected(self):
        context = setup_case()
        plan = make_plan(context)
        context[1]["rewritten_sources"][0]["nominal_source_id"] = "fake-id"
        self.denied(plan, "A230_BLOCKED_UNTRUSTED_PLAN_REQUIRED", context=context)

    def test_40_host_can_supply_perfect_checklist_but_no_proof(self):
        r = self.check(make_plan())
        self.assertEqual(r.planned_challenges, 60)
        self.assertEqual(r.real_control_domains_independently_verified, 0)
        self.no_authority(r)


_BAD_STATES = (
    ("challenge_nonce_state", "ISSUED"),
    ("issuer_identity_state", "VERIFIED"),
    ("independent_witness_state", "VERIFIED"),
    ("external_acquisition_state", "CONTACTED"),
    ("evidence_state", "OBTAINED"),
    ("reviewer_state", "ASSIGNED"),
    ("evidence_state", True),
    ("external_acquisition_state", None),
    ("issuer_identity_state", 1),
    ("challenge_nonce_state", "a-fake-nonce"),
)


def _make_adversarial_case(field, value):
    def exercise(self):
        self.mutate_row(field, value, "HOST_CANNOT_ASSERT_EXTERNAL_CHALLENGE_PROOF_OR_REVIEW")
    return exercise


for index, (field, invalid) in enumerate(_BAD_STATES, start=41):
    setattr(
        A231ExternalControlProofPlanTests,
        f"test_{index:02d}_untrusted_{field}",
        _make_adversarial_case(field, invalid),
    )


if __name__ == "__main__":
    unittest.main()
