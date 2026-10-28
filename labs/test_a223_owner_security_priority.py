"""A223: security-first research preference without signoff or real actions."""
from dataclasses import FrozenInstanceError
import copy
import json
import unittest

from labs.a220_synthetic_root_attack_boundaries import KMS_HSM, OFFLINE
from labs.a221_independent_evidence_blueprint import CONTROL_PROTOCOLS
from labs.a222_owner_acceptance_matrix import (
    SCHEMA as A222_SCHEMA, CRITERIA, ROLES,
    preflight_owner_acceptance_matrix,
)
from labs.a223_owner_security_priority import (
    SCHEMA, PRIORITY, SOURCE, preflight_owner_security_priority,
)


OWNER, TENANT, WORKSPACE = "synthetic-owner", "synthetic-tenant", "synthetic-workspace"
_UNSET = object()


def unfilled_a222():
    return {
        "schema": A222_SCHEMA,
        "owner_id": OWNER, "tenant_id": TENANT, "workspace_id": WORKSPACE,
        "decision_state": "AWAITING_OWNER_PRIORITIES",
        "owner_signoff_state": "NOT_REQUESTED", "selected_model": "NONE",
        "budget_approval_state": "NOT_REQUESTED", "external_p0_homologated": 0,
        "models_under_review": [OFFLINE, KMS_HSM],
        "criteria": [
            {"criterion_id": c, "priority_state": "UNRANKED",
             "offline_assessment": "NOT_ASSESSED", "kms_hsm_assessment": "NOT_ASSESSED",
             "owner_preference_state": "NOT_PROVIDED", "evidence_confidence": "NO_EXTERNAL_EVIDENCE"}
            for c in sorted(CRITERIA)
        ],
        "roles": [
            {"role_id": r, "assignment_state": "UNASSIGNED",
             "identity_proof_state": "NOT_OBTAINED", "contact_state": "NOT_CONTACTED",
             "authority_state": "NO_AUTHORITY_GRANTED"}
            for r in sorted(ROLES)
        ],
        "evidence_gates": [
            {"control_id": c, "review_state": "NOT_STARTED",
             "external_evidence_state": "NOT_OBTAINED", "acceptance_state": "NOT_REQUESTED"}
            for c in sorted(CONTROL_PROTOCOLS)
        ],
    }


def research_note(matrix=None):
    if matrix is None:
        matrix = unfilled_a222()
    base = preflight_owner_acceptance_matrix(
        matrix, expected_owner_id=OWNER, expected_tenant_id=TENANT,
        expected_workspace_id=WORKSPACE,
    )
    assert base.matrix_complete
    return {
        "schema": SCHEMA, "owner_id": OWNER,
        "tenant_id": TENANT, "workspace_id": WORKSPACE,
        "research_priority": PRIORITY,
        "preference_source": SOURCE,
        "preference_status": "NOTED_NOT_AUTHENTICATED",
        "a222_matrix_digest": base.draft_digest,
        "models_under_review": [OFFLINE, KMS_HSM],
        "research_controls": [
            {"control_id": c, "research_question_state": "OPEN",
             "external_evidence_state": "NOT_OBTAINED",
             "acceptance_state": "NOT_REQUESTED"}
            for c in sorted(CONTROL_PROTOCOLS)
        ],
        "decision_state": "BOTH_MODELS_UNDER_RESEARCH",
        "owner_signoff_state": "NOT_REQUESTED",
        "chosen_model": "NONE",
        "provider_selection_state": "NO_PROVIDER_SELECTED",
        "budget_approval_state": "NOT_REQUESTED",
        "external_p0_homologated": 0,
        "uncertain_resend_policy": "ZERO_AUTO_RESEND",
    }


class A223OwnerSecurityPriorityTests(unittest.TestCase):
    def check(self, note=_UNSET, matrix=None, **kwargs):
        if matrix is None:
            matrix = unfilled_a222()
        if note is _UNSET:
            note = research_note(matrix)
        args = {
            "a222_matrix": matrix,
            "expected_owner_id": OWNER,
            "expected_tenant_id": TENANT,
            "expected_workspace_id": WORKSPACE,
        }
        args.update(kwargs)
        return preflight_owner_security_priority(note, **args)

    def always_no_authority(self, r):
        self.assertFalse(r.identity_verified)
        self.assertFalse(r.owner_signoff_valid)
        self.assertFalse(r.independent_evidence_verified)
        self.assertFalse(r.root_model_selected)
        self.assertEqual(r.external_p0_homologated, 0)
        for flag in (
            "may_select_model", "may_commit_budget", "may_contact_provider",
            "may_provision", "may_generate_key", "may_sign", "may_connect",
            "may_confirm", "may_auto_resend",
        ):
            self.assertFalse(getattr(r, flag), flag)

    def denied(self, note, code, matrix=None, **kwargs):
        r = self.check(note, matrix=matrix, **kwargs)
        self.assertEqual(r.code, code)
        self.assertFalse(r.research_form_valid)
        self.assertFalse(r.conversational_security_priority_noted)
        self.assertEqual(r.research_digest, "")
        self.assertEqual(r.unresolved_controls, ())
        self.always_no_authority(r)

    def change(self, field, value, code):
        n = research_note()
        n[field] = value
        self.denied(n, code)

    def test_01_option_1_is_only_a_research_note(self):
        r = self.check()
        self.assertTrue(r.research_form_valid)
        self.assertTrue(r.conversational_security_priority_noted)
        self.assertEqual(r.code, "SECURITY_PRIORITY_NOTED_RESEARCH_ONLY_13_CONTROLS_OPEN_HARD_NO_GO")
        self.assertEqual(len(r.research_digest), 64)
        self.always_no_authority(r)

    def test_02_all_thirteen_security_questions_are_open(self):
        r = self.check()
        self.assertEqual(len(CONTROL_PROTOCOLS), 13)
        self.assertEqual(r.unresolved_controls, tuple(sorted(CONTROL_PROTOCOLS)))
        self.always_no_authority(r)

    def test_03_both_models_are_unselected(self):
        n = research_note()
        self.assertEqual(set(n["models_under_review"]), {OFFLINE, KMS_HSM})
        self.assertEqual(n["chosen_model"], "NONE")
        self.always_no_authority(self.check(n))

    def test_04_json_input_is_only_an_unverified_note(self):
        self.assertTrue(self.check(json.dumps(research_note())).research_form_valid)
        self.always_no_authority(self.check(json.dumps(research_note())))

    def test_05_array_order_does_not_change_digest(self):
        n = research_note()
        initial = self.check(n)
        n["models_under_review"].reverse()
        n["research_controls"].reverse()
        self.assertEqual(initial, self.check(n))

    def test_06_a222_matrix_order_does_not_change_digest(self):
        matrix = unfilled_a222()
        n = research_note(matrix)
        initial = self.check(n, matrix=matrix)
        for key in ("models_under_review", "criteria", "roles", "evidence_gates"):
            matrix[key].reverse()
        self.assertEqual(initial, self.check(n, matrix=matrix))

    def test_07_result_cannot_be_mutated_to_authorize(self):
        r = self.check()
        with self.assertRaises(FrozenInstanceError):
            r.may_provision = True
        with self.assertRaises(FrozenInstanceError):
            r.owner_signoff_valid = True

    def test_08_never_mutates_original_inputs(self):
        m, n = unfilled_a222(), research_note()
        m0, n0 = copy.deepcopy(m), copy.deepcopy(n)
        for _ in range(5):
            self.check(n, matrix=m)
        self.assertEqual(m, m0)
        self.assertEqual(n, n0)

    def test_09_extra_fields_rejected(self):
        n = research_note()
        n["host_approved"] = True
        self.denied(n, "PRIORITY_ENVELOPE_NOT_EXACT")

    def test_10_missing_fields_rejected(self):
        for key in ("schema", "a222_matrix_digest", "research_controls"):
            n = research_note()
            del n[key]
            self.denied(n, "PRIORITY_ENVELOPE_NOT_EXACT")

    def test_11_wrong_type_envelope_rejected(self):
        for n in (None, [], "[]", 1, False):
            code = "AMBIGUOUS_OR_OVERSIZED_PRIORITY_JSON" if type(n) is str else "PRIORITY_ENVELOPE_NOT_EXACT"
            self.denied(n, code)

    def test_12_schema_not_inflated(self):
        self.change("schema", "ATLASQUANT_TRUSTED_SIGNOFF", "PRIORITY_SCHEMA_UNSUPPORTED")

    def test_13_wrong_owner_rejected(self):
        self.change("owner_id", "someone-else", "PRIORITY_SCOPE_MISMATCH")

    def test_14_wrong_tenant_rejected(self):
        self.change("tenant_id", "other-tenant", "PRIORITY_SCOPE_MISMATCH")

    def test_15_wrong_workspace_rejected(self):
        self.change("workspace_id", "other-workspace", "PRIORITY_SCOPE_MISMATCH")

    def test_16_bad_expected_owner_rejected(self):
        self.denied(research_note(), "INVALID_EXPECTED_SCOPE", expected_owner_id="/")

    def test_17_nonstring_expected_tenant_rejected(self):
        self.denied(research_note(), "INVALID_EXPECTED_SCOPE", expected_tenant_id=True)

    def test_18_nonstring_expected_workspace_rejected(self):
        self.denied(research_note(), "INVALID_EXPECTED_SCOPE", expected_workspace_id=1)

    def test_19_nonstring_candidate_identity_rejected(self):
        self.change("owner_id", 7, "PRIORITY_SCOPE_MISMATCH")

    def test_20_other_owner_priorities_not_assumed(self):
        for fake in ("MINIMUM_COST", "RECOVERY_FIRST", "OPERATIONAL_EASE", None, 1):
            self.change("research_priority", fake, "UNRECOGNIZED_CONVERSATIONAL_PRIORITY")

    def test_21_conversation_not_cryptographic_identity_proof(self):
        for fake in ("OWNER_AUTHENTICATED", "SIGNED_BY_OWNER", "VERIFIED", None):
            self.change("preference_source", fake, "HOST_CANNOT_ASSERT_AUTHENTICATED_PREFERENCE")

    def test_22_preference_cannot_be_promoted(self):
        for fake in ("APPROVED", "SIGNED", "OWNER_VERIFIED", True):
            self.change("preference_status", fake, "PREFERENCE_NOT_OWNER_SIGNOFF")

    def test_23_no_decision_inferred_from_security_priority(self):
        self.change("decision_state", "APPROVED", "CUSTODY_DECISION_NOT_AUTHORIZED")

    def test_24_fake_signoff_rejected(self):
        self.change("owner_signoff_state", "SIGNED", "HOST_CANNOT_SIGN_FOR_OWNER")

    def test_25_offline_custody_not_auto_chosen(self):
        self.change("chosen_model", OFFLINE, "CUSTODY_MODEL_CHOICE_NOT_AUTHORIZED")

    def test_26_kms_hsm_custody_not_auto_chosen(self):
        self.change("chosen_model", KMS_HSM, "CUSTODY_MODEL_CHOICE_NOT_AUTHORIZED")

    def test_27_provider_selection_not_allowed(self):
        self.change("provider_selection_state", "VENDOR_APPROVED", "PROVIDER_SELECTION_NOT_AUTHORIZED")

    def test_28_budget_or_spend_cannot_be_approved(self):
        self.change("budget_approval_state", "APPROVED", "SPENDING_NOT_AUTHORIZED")

    def test_29_external_p0_stays_zero_with_bool_type_rejection(self):
        for fake in (1, 6, True, -1, "0"):
            self.change("external_p0_homologated", fake, "FALSE_EXTERNAL_P0_HOMOLOGATION")

    def test_30_zero_auto_resend_is_required(self):
        for fake in ("AUTO_RESEND", "RETRY_ON_TIMEOUT", False, None):
            self.change("uncertain_resend_policy", fake, "UNCERTAIN_MUST_FAIL_CLOSED")

    def test_31_all_two_models_stay_under_review(self):
        for fake in ([], [OFFLINE], [OFFLINE, OFFLINE], [OFFLINE, "HOST_KEY"], "NONE"):
            self.change("models_under_review", fake, "BOTH_UNSELECTED_MODELS_REQUIRED")

    def test_32_unhashable_models_rejected(self):
        self.change("models_under_review", [OFFLINE, []], "BOTH_UNSELECTED_MODELS_REQUIRED")

    def test_33_a222_not_approved_or_rescored(self):
        m = unfilled_a222()
        m["criteria"][0]["priority_state"] = "HIGH"
        self.denied(research_note(), "A222_UNFILLED_MATRIX_REQUIRED", matrix=m)

    def test_34_a222_signoff_cannot_be_injected(self):
        m = unfilled_a222()
        m["owner_signoff_state"] = "SIGNED"
        self.denied(research_note(), "A222_UNFILLED_MATRIX_REQUIRED", matrix=m)

    def test_35_a222_scope_drift_is_refused(self):
        m = unfilled_a222()
        m["tenant_id"] = "fake-tenant"
        self.denied(research_note(), "A222_UNFILLED_MATRIX_REQUIRED", matrix=m)

    def test_36_wrong_a222_digest_rejected(self):
        self.change("a222_matrix_digest", "0" * 64, "A222_MATRIX_DIGEST_MISMATCH")

    def test_37_malformed_a222_digest_rejected(self):
        for fake in ("not-a-digest", True, 12, "F" * 64):
            self.change("a222_matrix_digest", fake, "A222_MATRIX_DIGEST_MISMATCH")

    def test_38_missing_control_question_rejected(self):
        n = research_note()
        n["research_controls"].pop()
        self.denied(n, "SECURITY_CONTROL_QUESTIONS_INCOMPLETE")

    def test_39_bad_control_schema_rejected(self):
        n = research_note()
        n["research_controls"][0]["verified"] = True
        self.denied(n, "SECURITY_CONTROL_ENVELOPE_NOT_EXACT")

    def test_40_unknown_control_rejected(self):
        n = research_note()
        n["research_controls"][0]["control_id"] = "host_approved_key"
        self.denied(n, "UNKNOWN_SECURITY_CONTROL")

    def test_41_duplicate_control_rejected(self):
        n = research_note()
        n["research_controls"][1]["control_id"] = n["research_controls"][0]["control_id"]
        self.denied(n, "DUPLICATE_SECURITY_CONTROL")

    def test_42_host_cannot_claim_controls_passed(self):
        for key, fake in (
            ("research_question_state", "CLOSED"),
            ("external_evidence_state", "VERIFIED"),
            ("acceptance_state", "OWNER_SIGNED"),
        ):
            n = research_note()
            n["research_controls"][0][key] = fake
            self.denied(n, "UNVERIFIED_CONTROL_CANNOT_BE_PASSED")

    def test_43_json_duplicate_fields_rejected(self):
        raw = json.dumps(research_note())
        bad = raw.replace('"chosen_model": "NONE"', '"chosen_model": "NONE", "chosen_model": "OWNER_OFFLINE_ROOT"', 1)
        self.assertNotEqual(raw, bad)
        self.denied(bad, "AMBIGUOUS_OR_OVERSIZED_PRIORITY_JSON")

    def test_44_oversized_json_rejected(self):
        self.denied("{" + " " * 9000 + "}", "AMBIGUOUS_OR_OVERSIZED_PRIORITY_JSON")

    def test_45_different_valid_scope_changes_digest(self):
        base = self.check()
        matrix = unfilled_a222()
        matrix["workspace_id"] = "new-workspace"
        n = research_note()
        n["workspace_id"] = "new-workspace"
        a222 = preflight_owner_acceptance_matrix(
            matrix, expected_owner_id=OWNER, expected_tenant_id=TENANT,
            expected_workspace_id="new-workspace",
        )
        n["a222_matrix_digest"] = a222.draft_digest
        other = self.check(n, matrix=matrix, expected_workspace_id="new-workspace")
        self.assertTrue(other.research_form_valid)
        self.assertNotEqual(base.research_digest, other.research_digest)
        self.always_no_authority(other)


if __name__ == "__main__":
    unittest.main()
