"""A224: 50 guards for paper-only security proof challenges."""
from dataclasses import FrozenInstanceError, asdict
import copy
import json
import unittest

from labs.a220_synthetic_root_attack_boundaries import KMS_HSM, OFFLINE, SCENARIOS
from labs.a221_independent_evidence_blueprint import CONTROL_PROTOCOLS
from labs.a223_owner_security_priority import PRIORITY, preflight_owner_security_priority
from labs.a224_security_proof_test_catalog import (
    SCHEMA, EXPECTED_SAFE_BEHAVIOR, hypothetical_security_test_rows,
    preflight_security_test_catalog,
)
from labs.test_a223_owner_security_priority import (
    OWNER, TENANT, WORKSPACE, research_note, unfilled_a222,
)


def make_a224(a223=None, a222=None):
    if a222 is None:
        a222 = unfilled_a222()
    if a223 is None:
        a223 = research_note(a222)
    base = preflight_owner_security_priority(
        a223, a222_matrix=a222, expected_owner_id=OWNER,
        expected_tenant_id=TENANT, expected_workspace_id=WORKSPACE,
    )
    assert base.research_form_valid
    return {
        "schema": SCHEMA,
        "owner_id": OWNER, "tenant_id": TENANT, "workspace_id": WORKSPACE,
        "research_priority": PRIORITY,
        "a223_note_digest": base.research_digest,
        "plan_state": "HYPOTHETICAL_TESTS_NOT_EXECUTED",
        "owner_approval_state": "NOT_REQUESTED",
        "selected_model": "NONE",
        "provider_selection_state": "NO_PROVIDER_SELECTED",
        "budget_approval_state": "NOT_REQUESTED",
        "external_p0_homologated": 0,
        "uncertain_resend_policy": "ZERO_AUTO_RESEND",
        "models_under_review": [OFFLINE, KMS_HSM],
        "test_catalog": [asdict(r) for r in hypothetical_security_test_rows()],
    }


class A224SecurityProofCatalogTests(unittest.TestCase):
    def check(self, candidate=None, *, a223=None, a222=None, **kwargs):
        if a222 is None:
            a222 = unfilled_a222()
        if a223 is None:
            a223 = research_note(a222)
        if candidate is None:
            candidate = make_a224(a223, a222)
        args = {
            "a223_note": a223, "a222_matrix": a222,
            "expected_owner_id": OWNER, "expected_tenant_id": TENANT,
            "expected_workspace_id": WORKSPACE,
        }
        args.update(kwargs)
        return preflight_security_test_catalog(candidate, **args)

    def no_authority(self, result):
        self.assertFalse(result.owner_identity_verified)
        self.assertFalse(result.owner_signoff_valid)
        self.assertFalse(result.independent_tests_executed)
        self.assertFalse(result.independent_proof_accepted)
        self.assertFalse(result.custody_model_selected)
        self.assertEqual(result.external_p0_homologated, 0)
        for key in (
            "may_run_external_challenge", "may_contact_person", "may_select_model",
            "may_commit_budget", "may_provision", "may_generate_key",
            "may_sign", "may_connect", "may_confirm", "may_auto_resend",
        ):
            self.assertFalse(getattr(result, key), key)

    def denied(self, candidate, code, *, a223=None, a222=None, **kwargs):
        r = self.check(candidate, a223=a223, a222=a222, **kwargs)
        self.assertEqual(r.code, code)
        self.assertFalse(r.catalog_complete)
        self.assertFalse(r.security_priority_noted)
        self.assertEqual(r.catalog_digest, "")
        self.assertEqual(r.unexecuted_attacks, ())
        self.no_authority(r)

    def changed(self, key, value, code):
        n = make_a224()
        n[key] = value
        self.denied(n, code)

    def test_01_thirteen_unique_attacks_in_catalog(self):
        rows = hypothetical_security_test_rows()
        self.assertEqual(len(rows), 13)
        self.assertEqual({r.attack_id for r in rows}, set(SCENARIOS))

    def test_02_all_a221_controls_covered(self):
        self.assertEqual({r.control_id for r in hypothetical_security_test_rows()}, set(CONTROL_PROTOCOLS))

    def test_03_model_scope_exact_two_three_eight(self):
        rows = hypothetical_security_test_rows()
        self.assertEqual(sum(r.model_scope == "OFFLINE_ONLY" for r in rows), 2)
        self.assertEqual(sum(r.model_scope == "KMS_HSM_ONLY" for r in rows), 3)
        self.assertEqual(sum(r.model_scope == "BOTH" for r in rows), 8)

    def test_04_challenge_names_match_a221(self):
        for r in hypothetical_security_test_rows():
            self.assertEqual((r.nominal_source_role, r.challenge_kind), CONTROL_PROTOCOLS[r.control_id])

    def test_05_desired_behavior_exact_for_each_attack(self):
        self.assertEqual(set(EXPECTED_SAFE_BEHAVIOR), set(SCENARIOS))
        for r in hypothetical_security_test_rows():
            self.assertEqual(r.expected_safe_behavior, EXPECTED_SAFE_BEHAVIOR[r.attack_id])

    def test_06_frozen_specs_cannot_be_forged_passed(self):
        r = hypothetical_security_test_rows()[0]
        with self.assertRaises(FrozenInstanceError):
            r.execution_state = "PASSED"

    def test_07_every_spec_starts_unexecuted(self):
        for r in hypothetical_security_test_rows():
            self.assertEqual(r.execution_state, "NOT_EXECUTED")
            self.assertEqual(r.external_proof_state, "NOT_OBTAINED")
            self.assertEqual(r.independent_review_state, "UNASSIGNED")
            self.assertEqual(r.remediation_state, "NOT_STARTED")

    def test_08_valid_lab_plan_still_no_authority(self):
        r = self.check()
        self.assertTrue(r.catalog_complete)
        self.assertTrue(r.security_priority_noted)
        self.assertEqual(r.code, "13_HYPOTHETICAL_SECURITY_TESTS_DEFINED_NONE_EXECUTED_HARD_NO_GO")
        self.assertEqual(len(r.catalog_digest), 64)
        self.no_authority(r)

    def test_09_all_thirteen_attacks_remain_unexecuted(self):
        self.assertEqual(self.check().unexecuted_attacks, tuple(sorted(SCENARIOS)))

    def test_10_json_candidate_still_untrusted(self):
        r = self.check(json.dumps(make_a224()))
        self.assertTrue(r.catalog_complete)
        self.no_authority(r)

    def test_11_model_and_test_row_order_are_canonical(self):
        a = make_a224()
        first = self.check(a)
        a["models_under_review"].reverse()
        a["test_catalog"].reverse()
        self.assertEqual(first, self.check(a))

    def test_12_repeated_calls_do_not_change_inputs(self):
        matrix = unfilled_a222()
        note = research_note(matrix)
        candidate = make_a224(note, matrix)
        original = copy.deepcopy((matrix, note, candidate))
        for _ in range(5):
            self.assertTrue(self.check(candidate, a223=note, a222=matrix).catalog_complete)
        self.assertEqual((matrix, note, candidate), original)

    def test_13_result_is_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            self.check().may_run_external_challenge = True

    def test_14_extra_claim_rejected(self):
        n = make_a224()
        n["authorized_test_token"] = "signed"
        self.denied(n, "CATALOG_ENVELOPE_NOT_EXACT")

    def test_15_missing_required_top_level_field_rejected(self):
        for key in ("schema", "test_catalog", "a223_note_digest", "selected_model"):
            n = make_a224()
            del n[key]
            self.denied(n, "CATALOG_ENVELOPE_NOT_EXACT")

    def test_16_wrong_envelope_type_rejected(self):
        for bad in ({}, [], True, 0):
            self.denied(bad, "CATALOG_ENVELOPE_NOT_EXACT")

    def test_17_non_object_json_rejected(self):
        self.denied('"approved"', "AMBIGUOUS_OR_OVERSIZED_CATALOG_JSON")

    def test_18_wrong_schema_rejected(self):
        self.changed("schema", "TRUSTED_TEST_RESULT", "CATALOG_SCHEMA_UNSUPPORTED")

    def test_19_wrong_owner_rejected(self):
        self.changed("owner_id", "other", "CATALOG_SCOPE_MISMATCH")

    def test_20_wrong_tenant_rejected(self):
        self.changed("tenant_id", "other", "CATALOG_SCOPE_MISMATCH")

    def test_21_wrong_workspace_rejected(self):
        self.changed("workspace_id", "other", "CATALOG_SCOPE_MISMATCH")

    def test_22_invalid_expected_owner_rejected(self):
        self.denied(make_a224(), "INVALID_EXPECTED_SCOPE", expected_owner_id="bad / name")

    def test_23_nonstring_expected_tenant_rejected(self):
        self.denied(make_a224(), "INVALID_EXPECTED_SCOPE", expected_tenant_id=True)

    def test_24_nonstring_expected_workspace_rejected(self):
        self.denied(make_a224(), "INVALID_EXPECTED_SCOPE", expected_workspace_id=1)

    def test_25_nonstring_candidate_scope_rejected(self):
        self.changed("owner_id", False, "CATALOG_SCOPE_MISMATCH")

    def test_26_priority_cannot_change_to_cost_or_recovery(self):
        for x in ("LOWEST_COST", "RECOVERY_FIRST", "OPERATIONAL_EASE", 1):
            self.changed("research_priority", x, "SECURITY_FIRST_PRIORITY_REQUIRED")

    def test_27_plan_cannot_claim_execution(self):
        for x in ("ALL_TESTS_PASSED", "PROVED", "EXECUTED", True):
            self.changed("plan_state", x, "LAB_PLAN_CANNOT_ASSERT_TEST_EXECUTION")

    def test_28_owner_approval_cannot_be_asserted(self):
        self.changed("owner_approval_state", "SIGNED", "HOST_CANNOT_ASSERT_OWNER_APPROVAL")

    def test_29_offline_model_not_automatically_selected(self):
        self.changed("selected_model", OFFLINE, "CUSTODY_MODEL_NOT_SELECTED")

    def test_30_kms_model_not_automatically_selected(self):
        self.changed("selected_model", KMS_HSM, "CUSTODY_MODEL_NOT_SELECTED")

    def test_31_no_provider_selected(self):
        self.changed("provider_selection_state", "SELECTED", "PROVIDER_SELECTION_NOT_AUTHORIZED")

    def test_32_no_budget_approved(self):
        self.changed("budget_approval_state", "APPROVED", "SPENDING_NOT_AUTHORIZED")

    def test_33_fake_p0_denied_including_bool(self):
        for x in (1, 6, True, "0", -1):
            self.changed("external_p0_homologated", x, "FORGED_EXTERNAL_P0_HOMOLOGATION")

    def test_34_uncertain_always_zero_auto_resend(self):
        for x in ("RETRY", "AUTO_RESEND", None, False):
            self.changed("uncertain_resend_policy", x, "UNCERTAIN_MUST_FAIL_CLOSED")

    def test_35_both_models_required(self):
        for x in ([OFFLINE], [], [OFFLINE, OFFLINE], [OFFLINE, "HOST_MODEL"], "BOTH"):
            self.changed("models_under_review", x, "BOTH_MODELS_MUST_REMAIN_UNSELECTED")

    def test_36_unhashable_model_denied(self):
        self.changed("models_under_review", [OFFLINE, []], "BOTH_MODELS_MUST_REMAIN_UNSELECTED")

    def test_37_unfilled_a222_still_required(self):
        matrix = unfilled_a222()
        matrix["owner_signoff_state"] = "SIGNED"
        self.denied(make_a224(), "A223_UNVERIFIED_PRIORITY_REQUIRED", a223=research_note(), a222=matrix)

    def test_38_a223_verified_identity_forgery_rejected(self):
        note = research_note()
        note["preference_status"] = "SIGNED"
        self.denied(make_a224(), "A223_UNVERIFIED_PRIORITY_REQUIRED", a223=note)

    def test_39_a223_owner_scope_mismatch_rejected(self):
        note = research_note()
        note["tenant_id"] = "other-tenant"
        self.denied(make_a224(), "A223_UNVERIFIED_PRIORITY_REQUIRED", a223=note)

    def test_40_a223_digest_mismatch_rejected(self):
        self.changed("a223_note_digest", "0" * 64, "A223_LOCAL_DIGEST_MISMATCH")

    def test_41_a223_digest_bad_type_rejected(self):
        for x in (True, None, "f" * 63, "F" * 64):
            self.changed("a223_note_digest", x, "A223_LOCAL_DIGEST_MISMATCH")

    def test_42_missing_attack_row_rejected(self):
        n = make_a224()
        n["test_catalog"].pop()
        self.denied(n, "SECURITY_TEST_COVERAGE_INCOMPLETE")

    def test_43_wrong_row_type_rejected(self):
        n = make_a224()
        n["test_catalog"][0] = "approved"
        self.denied(n, "SECURITY_TEST_ENVELOPE_NOT_EXACT")

    def test_44_extra_probe_credentials_rejected(self):
        n = make_a224()
        n["test_catalog"][0]["credential"] = "host-provided"
        self.denied(n, "SECURITY_TEST_ENVELOPE_NOT_EXACT")

    def test_45_unknown_attack_rejected(self):
        n = make_a224()
        n["test_catalog"][0]["attack_id"] = "ROOT_TEST_PASSED"
        self.denied(n, "UNKNOWN_SECURITY_ATTACK")

    def test_46_duplicate_attack_rejected(self):
        n = make_a224()
        n["test_catalog"][1]["attack_id"] = n["test_catalog"][0]["attack_id"]
        self.denied(n, "DUPLICATE_SECURITY_ATTACK")

    def test_47_scope_protocol_source_behavior_cannot_be_misassigned(self):
        for field, val in (
            ("model_scope", "BOTH_WITHOUT_PROOF"),
            ("control_id", "kms_host_sign_denied"),
            ("nominal_source_role", "HOST_ADMIN"),
            ("challenge_kind", "SKIP_REAL_TEST"),
            ("expected_safe_behavior", "APPROVE_ANY_SIGNATURE"),
        ):
            n = make_a224()
            n["test_catalog"][0][field] = val
            self.denied(n, "A221_PROTOCOL_OR_MODEL_SCOPE_MISMATCH")

    def test_48_host_cannot_mark_execution_evidence_review_or_fix(self):
        for field, val in (
            ("execution_state", "PASSED"),
            ("external_proof_state", "VERIFIED"),
            ("independent_review_state", "APPROVED"),
            ("remediation_state", "COMPLETE"),
        ):
            n = make_a224()
            n["test_catalog"][0][field] = val
            self.denied(n, "UNEXECUTED_TEST_CANNOT_CLAIM_PROOF")

    def test_49_duplicate_json_key_and_oversized_payload_denied(self):
        raw = json.dumps(make_a224())
        forged = raw.replace('"selected_model": "NONE"', '"selected_model": "NONE", "selected_model": "OWNER_OFFLINE_ROOT"', 1)
        self.assertNotEqual(forged, raw)
        self.denied(forged, "AMBIGUOUS_OR_OVERSIZED_CATALOG_JSON")
        self.denied("{" + " " * 9000 + "}", "AMBIGUOUS_OR_OVERSIZED_CATALOG_JSON")

    def test_50_workspace_scope_changes_research_digest_only(self):
        from labs.a222_owner_acceptance_matrix import preflight_owner_acceptance_matrix
        matrix = unfilled_a222()
        note = research_note(matrix)
        candidate = make_a224(note, matrix)
        base = self.check(candidate, a223=note, a222=matrix)
        other_matrix = copy.deepcopy(matrix)
        other_matrix["workspace_id"] = "other-workspace"
        d222 = preflight_owner_acceptance_matrix(
            other_matrix, expected_owner_id=OWNER, expected_tenant_id=TENANT,
            expected_workspace_id="other-workspace",
        )
        other_note = copy.deepcopy(note)
        other_note["workspace_id"] = "other-workspace"
        other_note["a222_matrix_digest"] = d222.draft_digest
        d223 = preflight_owner_security_priority(
            other_note, a222_matrix=other_matrix,
            expected_owner_id=OWNER, expected_tenant_id=TENANT,
            expected_workspace_id="other-workspace",
        )
        other_catalog = copy.deepcopy(candidate)
        other_catalog["workspace_id"] = "other-workspace"
        other_catalog["a223_note_digest"] = d223.research_digest
        new = self.check(
            other_catalog, a223=other_note, a222=other_matrix,
            expected_workspace_id="other-workspace",
        )
        self.assertTrue(base.catalog_complete)
        self.assertTrue(new.catalog_complete)
        self.assertNotEqual(base.catalog_digest, new.catalog_digest)
        self.no_authority(new)


if __name__ == "__main__":
    unittest.main()
