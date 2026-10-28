"""A222: 40 checks that a research matrix cannot impersonate its owner."""
from dataclasses import FrozenInstanceError
import copy
import json
import unittest

from labs.a220_synthetic_root_attack_boundaries import OFFLINE, KMS_HSM
from labs.a221_independent_evidence_blueprint import CONTROL_PROTOCOLS
from labs.a222_owner_acceptance_matrix import (
    SCHEMA, CRITERIA, ROLES, preflight_owner_acceptance_matrix,
)


OWNER = "synthetic-owner"
TENANT = "synthetic-tenant"
WORKSPACE = "synthetic-workspace"


class A222OwnerMatrixResearchOnlyTests(unittest.TestCase):
    def proposal(self):
        return {
            "schema": SCHEMA,
            "owner_id": OWNER,
            "tenant_id": TENANT,
            "workspace_id": WORKSPACE,
            "decision_state": "AWAITING_OWNER_PRIORITIES",
            "owner_signoff_state": "NOT_REQUESTED",
            "selected_model": "NONE",
            "budget_approval_state": "NOT_REQUESTED",
            "external_p0_homologated": 0,
            "models_under_review": [OFFLINE, KMS_HSM],
            "criteria": [
                {
                    "criterion_id": ident,
                    "priority_state": "UNRANKED",
                    "offline_assessment": "NOT_ASSESSED",
                    "kms_hsm_assessment": "NOT_ASSESSED",
                    "owner_preference_state": "NOT_PROVIDED",
                    "evidence_confidence": "NO_EXTERNAL_EVIDENCE",
                }
                for ident in sorted(CRITERIA)
            ],
            "roles": [
                {
                    "role_id": ident,
                    "assignment_state": "UNASSIGNED",
                    "identity_proof_state": "NOT_OBTAINED",
                    "contact_state": "NOT_CONTACTED",
                    "authority_state": "NO_AUTHORITY_GRANTED",
                }
                for ident in sorted(ROLES)
            ],
            "evidence_gates": [
                {
                    "control_id": ident,
                    "review_state": "NOT_STARTED",
                    "external_evidence_state": "NOT_OBTAINED",
                    "acceptance_state": "NOT_REQUESTED",
                }
                for ident in sorted(CONTROL_PROTOCOLS)
            ],
        }

    def assess(self, candidate=None, **overrides):
        args = dict(
            expected_owner_id=OWNER,
            expected_tenant_id=TENANT,
            expected_workspace_id=WORKSPACE,
        )
        args.update(overrides)
        return preflight_owner_acceptance_matrix(
            self.proposal() if candidate is None else candidate, **args,
        )

    def no_authority(self, r):
        self.assertFalse(r.owner_preferences_recorded)
        self.assertFalse(r.responsibilities_assigned)
        self.assertFalse(r.external_proof_accepted)
        self.assertFalse(r.owner_signoff_valid)
        self.assertEqual(r.external_p0_homologated, 0)
        self.assertFalse(r.may_select_model)
        self.assertFalse(r.may_commit_budget)
        self.assertFalse(r.may_contact_provider)
        self.assertFalse(r.may_provision)
        self.assertFalse(r.may_sign)
        self.assertFalse(r.may_connect)
        self.assertFalse(r.may_confirm)

    def denied(self, candidate, code, **overrides):
        r = self.assess(candidate, **overrides)
        self.assertEqual(r.code, code)
        self.assertFalse(r.matrix_complete)
        self.assertFalse(r.draft_digest)
        self.assertEqual(r.unresolved_criteria, ())
        self.no_authority(r)

    def test_01_complete_matrix_is_still_unapproved(self):
        r = self.assess()
        self.assertTrue(r.matrix_complete)
        self.assertEqual(r.code, "OWNER_MATRIX_FORM_COMPLETE_ALL_DECISIONS_AND_P0_PROOFS_PENDING")
        self.assertEqual(len(r.draft_digest), 64)
        self.assertEqual(r.unresolved_criteria, tuple(sorted(CRITERIA)))
        self.no_authority(r)

    def test_02_json_is_only_an_unfilled_form(self):
        r = self.assess(json.dumps(self.proposal()))
        self.assertTrue(r.matrix_complete)
        self.no_authority(r)

    def test_03_order_does_not_choose_a_preference(self):
        p = self.proposal()
        first = self.assess(p)
        for field in ("models_under_review", "criteria", "roles", "evidence_gates"):
            p[field].reverse()
        self.assertEqual(first, self.assess(p))
        self.no_authority(first)

    def test_04_result_is_frozen_against_forged_signoff(self):
        r = self.assess()
        with self.assertRaises(FrozenInstanceError):
            r.owner_signoff_valid = True
        with self.assertRaises(FrozenInstanceError):
            r.may_commit_budget = True

    def test_05_research_questions_cover_all_eight_priorities(self):
        self.assertEqual(len(CRITERIA), 8)
        self.assertEqual({x["criterion_id"] for x in self.proposal()["criteria"]}, CRITERIA)

    def test_06_roles_unassigned_and_gate_count(self):
        p = self.proposal()
        self.assertEqual(len(ROLES), 7)
        self.assertEqual({x["role_id"] for x in p["roles"]}, ROLES)
        self.assertEqual(len(p["evidence_gates"]), 13)
        self.assertTrue(all(x["assignment_state"] == "UNASSIGNED" for x in p["roles"]))

    def test_07_no_scores_or_receipts_are_present(self):
        p = self.proposal()
        for c in p["criteria"]:
            self.assertEqual(c["priority_state"], "UNRANKED")
            self.assertEqual(c["offline_assessment"], "NOT_ASSESSED")
            self.assertEqual(c["kms_hsm_assessment"], "NOT_ASSESSED")
            self.assertEqual(c["owner_preference_state"], "NOT_PROVIDED")
        for g in p["evidence_gates"]:
            self.assertEqual(g["external_evidence_state"], "NOT_OBTAINED")

    def test_08_top_level_extra_claim_is_rejected(self):
        p = self.proposal()
        p["automatically_approved"] = True
        self.denied(p, "OWNER_MATRIX_ENVELOPE_NOT_EXACT")

    def test_09_missing_top_level_fields_rejected(self):
        for field in ("schema", "owner_id", "criteria", "evidence_gates"):
            p = self.proposal()
            del p[field]
            self.denied(p, "OWNER_MATRIX_ENVELOPE_NOT_EXACT")

    def test_10_wrong_schema_rejected(self):
        p = self.proposal()
        p["schema"] = "A222_TRUSTED"
        self.denied(p, "OWNER_MATRIX_SCHEMA_UNSUPPORTED")

    def test_11_wrong_owner_rejected(self):
        p = self.proposal()
        p["owner_id"] = "other-owner"
        self.denied(p, "OWNER_MATRIX_SCOPE_MISMATCH")

    def test_12_wrong_tenant_rejected(self):
        p = self.proposal()
        p["tenant_id"] = "other-tenant"
        self.denied(p, "OWNER_MATRIX_SCOPE_MISMATCH")

    def test_13_wrong_workspace_rejected(self):
        p = self.proposal()
        p["workspace_id"] = "other-workspace"
        self.denied(p, "OWNER_MATRIX_SCOPE_MISMATCH")

    def test_14_invalid_expected_owner_scope_rejected(self):
        self.denied(self.proposal(), "INVALID_EXPECTED_SCOPE", expected_owner_id="not valid /")

    def test_15_nonstring_expected_scope_rejected(self):
        self.denied(self.proposal(), "INVALID_EXPECTED_SCOPE", expected_workspace_id=True)

    def test_16_nonstring_candidate_scope_rejected(self):
        p = self.proposal()
        p["tenant_id"] = True
        self.denied(p, "OWNER_MATRIX_SCOPE_MISMATCH")

    def test_17_self_decision_rejected(self):
        p = self.proposal()
        p["decision_state"] = "APPROVED"
        self.denied(p, "OWNER_DECISION_CANNOT_BE_SELF_ASSERTED")

    def test_18_fake_owner_signature_rejected(self):
        p = self.proposal()
        p["owner_signoff_state"] = "SIGNED"
        self.denied(p, "HOST_CANNOT_SIGN_FOR_OWNER")

    def test_19_fake_offline_selection_rejected(self):
        p = self.proposal()
        p["selected_model"] = OFFLINE
        self.denied(p, "NO_CUSTODY_MODEL_AUTHORIZED")

    def test_20_fake_kms_selection_rejected(self):
        p = self.proposal()
        p["selected_model"] = KMS_HSM
        self.denied(p, "NO_CUSTODY_MODEL_AUTHORIZED")

    def test_21_budget_approval_claim_rejected(self):
        p = self.proposal()
        p["budget_approval_state"] = "APPROVED"
        self.denied(p, "BUDGET_COMMITMENT_NOT_AUTHORIZED")

    def test_22_false_p0_homologation_rejected(self):
        for fake in (1, 6, True, "0", -1):
            p = self.proposal()
            p["external_p0_homologated"] = fake
            self.denied(p, "FORGED_EXTERNAL_P0_HOMOLOGATION")

    def test_23_missing_or_extra_model_rejected(self):
        for wrong in ([], [OFFLINE], [OFFLINE, OFFLINE], [OFFLINE, "HOST_ROOT"]):
            p = self.proposal()
            p["models_under_review"] = wrong
            self.denied(p, "BOTH_RESEARCH_MODELS_REQUIRED")

    def test_24_unhashable_model_rejected(self):
        p = self.proposal()
        p["models_under_review"] = [OFFLINE, []]
        self.denied(p, "BOTH_RESEARCH_MODELS_REQUIRED")

    def test_25_missing_criterion_rejected(self):
        p = self.proposal()
        p["criteria"].pop()
        self.denied(p, "OWNER_CRITERIA_INCOMPLETE")

    def test_26_malformed_criterion_envelope_rejected(self):
        p = self.proposal()
        p["criteria"][0]["owner_approved_score"] = 999
        self.denied(p, "OWNER_CRITERION_ENVELOPE_NOT_EXACT")

    def test_27_unknown_criterion_rejected(self):
        p = self.proposal()
        p["criteria"][0]["criterion_id"] = "MAXIMUM_PROFIT"
        self.denied(p, "UNKNOWN_OWNER_CRITERION")

    def test_28_duplicate_criterion_rejected(self):
        p = self.proposal()
        p["criteria"][1]["criterion_id"] = p["criteria"][0]["criterion_id"]
        self.denied(p, "DUPLICATE_OWNER_CRITERION")

    def test_29_fake_criterion_priority_and_rating_rejected(self):
        for field, value in (
            ("priority_state", "HIGH"),
            ("offline_assessment", "BEST"),
            ("kms_hsm_assessment", "SAFE"),
            ("owner_preference_state", OFFLINE),
            ("evidence_confidence", "VERIFIED"),
        ):
            p = self.proposal()
            p["criteria"][0][field] = value
            self.denied(p, "HOST_ASSIGNED_OWNER_PRIORITY_OR_SCORE")

    def test_30_missing_responsibility_rejected(self):
        p = self.proposal()
        p["roles"].pop()
        self.denied(p, "OWNER_RESPONSIBILITY_ROLES_INCOMPLETE")

    def test_31_bad_responsibility_envelope_rejected(self):
        p = self.proposal()
        p["roles"][0]["person_name"] = "HOST_INVENTED"
        self.denied(p, "RESPONSIBILITY_ENVELOPE_NOT_EXACT")

    def test_32_unknown_and_duplicate_roles_rejected(self):
        p = self.proposal()
        p["roles"][0]["role_id"] = "HOST_ADMIN_APPROVER"
        self.denied(p, "UNKNOWN_RESPONSIBILITY_ROLE")
        q = self.proposal()
        q["roles"][1]["role_id"] = q["roles"][0]["role_id"]
        self.denied(q, "DUPLICATE_RESPONSIBILITY_ROLE")

    def test_33_unapproved_assignment_identity_contact_authority_rejected(self):
        for field, value in (
            ("assignment_state", "ASSIGNED"),
            ("identity_proof_state", "VERIFIED"),
            ("contact_state", "CONTACTED"),
            ("authority_state", "GRANTED"),
        ):
            p = self.proposal()
            p["roles"][0][field] = value
            self.denied(p, "UNAPPROVED_ROLE_ASSIGNMENT")

    def test_34_missing_evidence_gate_rejected(self):
        p = self.proposal()
        p["evidence_gates"].pop()
        self.denied(p, "EXTERNAL_EVIDENCE_GATES_INCOMPLETE")

    def test_35_bad_gate_envelope_and_credential_rejected(self):
        p = self.proposal()
        p["evidence_gates"][0]["receipt_blob"] = "HOST_CLAIM"
        self.denied(p, "EVIDENCE_GATE_ENVELOPE_NOT_EXACT")

    def test_36_unknown_or_duplicate_gate_rejected(self):
        p = self.proposal()
        p["evidence_gates"][0]["control_id"] = "BROKER_ALREADY_CONFIRMED"
        self.denied(p, "UNKNOWN_A221_EVIDENCE_GATE")
        q = self.proposal()
        q["evidence_gates"][1]["control_id"] = q["evidence_gates"][0]["control_id"]
        self.denied(q, "DUPLICATE_EVIDENCE_GATE")

    def test_37_host_cannot_accept_gate_or_proof(self):
        for field, value in (
            ("review_state", "PASSED"),
            ("external_evidence_state", "VERIFIED"),
            ("acceptance_state", "SIGNED"),
        ):
            p = self.proposal()
            p["evidence_gates"][0][field] = value
            self.denied(p, "UNREVIEWED_PROOF_CANNOT_BE_ACCEPTED")

    def test_38_wrong_types_and_structures_rejected(self):
        p = self.proposal()
        p["criteria"][0]["priority_state"] = True
        self.denied(p, "HOST_ASSIGNED_OWNER_PRIORITY_OR_SCORE")
        q = self.proposal()
        q["roles"] = {}
        self.denied(q, "OWNER_RESPONSIBILITY_ROLES_INCOMPLETE")
        k = self.proposal()
        k["evidence_gates"] = "signed"
        self.denied(k, "EXTERNAL_EVIDENCE_GATES_INCOMPLETE")

    def test_39_duplicate_and_oversized_json_rejected(self):
        raw = json.dumps(self.proposal())
        fake = raw.replace(
            '"selected_model": "NONE"',
            '"selected_model": "NONE", "selected_model": "SEPARATE_DOMAIN_KMS_HSM"', 1,
        )
        self.assertNotEqual(fake, raw)
        self.denied(fake, "AMBIGUOUS_OR_OVERSIZED_OWNER_MATRIX_JSON")
        self.denied("{" + " " * 9000 + "}", "AMBIGUOUS_OR_OVERSIZED_OWNER_MATRIX_JSON")

    def test_40_repeat_is_read_only_and_digest_scope_bound(self):
        p = self.proposal()
        snapshot = copy.deepcopy(p)
        first = self.assess(p)
        for _ in range(10):
            again = self.assess(p)
            self.assertEqual(first, again)
            self.no_authority(again)
        self.assertEqual(p, snapshot)
        changed = copy.deepcopy(p)
        changed["workspace_id"] = "other-workspace"
        other = self.assess(changed, expected_workspace_id="other-workspace")
        self.assertTrue(other.matrix_complete)
        self.assertNotEqual(first.draft_digest, other.draft_digest)
        self.no_authority(other)


if __name__ == "__main__":
    unittest.main()
