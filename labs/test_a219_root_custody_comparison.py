"""A219: 40 pure research-only comparison checks, no credentials or key APIs."""
from dataclasses import FrozenInstanceError
import copy
import json
import unittest

from labs.a219_root_custody_comparison import (
    SCHEMA, MODELS, THREAT_QUESTIONS,
    hypothetical_threat_comparison, preflight_root_custody_comparison,
)


OWNER = "synthetic-owner"
TENANT = "synthetic-tenant"
WORKSPACE = "synthetic-workspace"
OFFLINE = "OWNER_OFFLINE_ROOT"
KMS = "SEPARATE_DOMAIN_KMS_HSM"


class A219RootCustodyResearchTests(unittest.TestCase):
    def proposal(self):
        return {
            "schema": SCHEMA,
            "owner_id": OWNER,
            "tenant_id": TENANT,
            "workspace_id": WORKSPACE,
            "decision_state": "AWAITING_OWNER_COMPARISON_REVIEW",
            "owner_approval_state": "NOT_REQUESTED",
            "chosen_model": "NONE",
            "p0_external_homologated": 0,
            "models": [
                {
                    "model_id": model_id,
                    "identity_state": "UNVERIFIED",
                    "control_domain": "UNASSIGNED",
                    "key_material_state": "NOT_PROVISIONED",
                    "signing_policy_state": "NOT_REVIEWED",
                    "authorization_separation_state": "NOT_DEMONSTRATED",
                    "audit_state": "NOT_OBTAINED",
                    "revocation_state": "UNTESTED",
                    "recovery_state": "UNTESTED",
                    "availability_state": "UNTESTED",
                    "cost_state": "NOT_QUOTED",
                    "research_state": "HYPOTHETICAL_ONLY",
                }
                for model_id in (OFFLINE, KMS)
            ],
        }

    def assess(self, candidate=None, **overrides):
        args = dict(
            expected_owner_id=OWNER,
            expected_tenant_id=TENANT,
            expected_workspace_id=WORKSPACE,
        )
        args.update(overrides)
        return preflight_root_custody_comparison(
            self.proposal() if candidate is None else candidate, **args,
        )

    def denied(self, candidate, code, **overrides):
        result = self.assess(candidate, **overrides)
        self.assertEqual(result.code, code)
        self.assertFalse(result.comparison_complete)
        self.assertFalse(result.comparison_digest)
        self.assertFalse(result.independent_root_verified)
        self.assertFalse(result.owner_choice_approved)
        self.assertEqual(result.external_p0_homologated, 0)
        self.assertFalse(result.may_generate_or_import_key)
        self.assertFalse(result.may_sign)
        self.assertFalse(result.may_provision)
        self.assertFalse(result.may_connect)
        self.assertFalse(result.may_confirm)
        return result

    def test_01_baseline_never_grants_authority(self):
        r = self.assess()
        self.assertTrue(r.comparison_complete)
        self.assertEqual(r.code, "BOTH_MODELS_RESEARCHED_ALL_EXTERNAL_PROOFS_PENDING")
        self.assertEqual(len(r.comparison_digest), 64)
        self.assertEqual(r.external_p0_homologated, 0)
        self.assertFalse(r.independent_root_verified)
        self.assertFalse(r.owner_choice_approved)
        self.assertFalse(r.may_generate_or_import_key)
        self.assertFalse(r.may_sign)
        self.assertFalse(r.may_provision)
        self.assertFalse(r.may_connect)
        self.assertFalse(r.may_confirm)

    def test_02_string_json_is_still_research_only(self):
        r = self.assess(json.dumps(self.proposal()))
        self.assertTrue(r.comparison_complete)
        self.assertFalse(r.may_sign)

    def test_03_model_order_cannot_bias_hash_or_selection(self):
        p = self.proposal()
        a = self.assess(p)
        p["models"].reverse()
        b = self.assess(p)
        self.assertEqual(a, b)
        self.assertFalse(b.owner_choice_approved)

    def test_04_results_are_frozen(self):
        r = self.assess()
        with self.assertRaises(FrozenInstanceError):
            r.may_sign = True
        with self.assertRaises(FrozenInstanceError):
            r.independent_root_verified = True

    def test_05_every_hypothetical_scenario_is_unresolved(self):
        r = self.assess()
        self.assertEqual(r.unresolved_scenarios, tuple(sorted(THREAT_QUESTIONS)))
        self.assertEqual(len(r.unresolved_scenarios), 8)

    def test_06_all_scenario_questions_cover_both_models(self):
        for name in THREAT_QUESTIONS:
            with self.subTest(scenario=name):
                x = hypothetical_threat_comparison(name)
                self.assertEqual(x.scenario, name)
                self.assertTrue(x.offline_question.endswith("?"))
                self.assertTrue(x.kms_hsm_question.endswith("?"))
                self.assertNotEqual(x.offline_question, x.kms_hsm_question)
                self.assertEqual(x.evidence_state, "NOT_OBTAINED")
                self.assertFalse(x.may_activate)

    def test_07_unknown_scenarios_are_rejected(self):
        for x in ("", "SAFE", "PROVIDER_APPROVED", 123, None, True):
            with self.subTest(x=x):
                with self.assertRaises(ValueError):
                    hypothetical_threat_comparison(x)

    def test_08_scenario_result_cannot_claim_verified(self):
        r = hypothetical_threat_comparison("HOST_COMPROMISE")
        with self.assertRaises(FrozenInstanceError):
            r.evidence_state = "VERIFIED"

    def test_09_extra_approval_flag_is_rejected(self):
        p = self.proposal()
        p["independent_approval"] = True
        self.denied(p, "COMPARISON_ENVELOPE_NOT_EXACT")

    def test_10_missing_top_level_fields_are_rejected(self):
        for field in ("schema", "owner_id", "chosen_model", "models"):
            with self.subTest(field=field):
                p = self.proposal()
                p.pop(field)
                self.denied(p, "COMPARISON_ENVELOPE_NOT_EXACT")

    def test_11_unknown_schema_is_rejected(self):
        p = self.proposal()
        p["schema"] = "A219_ALREADY_TRUSTED"
        self.denied(p, "COMPARISON_SCHEMA_UNSUPPORTED")

    def test_12_owner_scope_mismatch_is_rejected(self):
        p = self.proposal()
        p["owner_id"] = "other-owner"
        self.denied(p, "COMPARISON_SCOPE_MISMATCH")

    def test_13_tenant_scope_mismatch_is_rejected(self):
        p = self.proposal()
        p["tenant_id"] = "other-tenant"
        self.denied(p, "COMPARISON_SCOPE_MISMATCH")

    def test_14_workspace_scope_mismatch_is_rejected(self):
        p = self.proposal()
        p["workspace_id"] = "other-workspace"
        self.denied(p, "COMPARISON_SCOPE_MISMATCH")

    def test_15_invalid_expected_scope_is_rejected(self):
        self.denied(self.proposal(), "INVALID_EXPECTED_SCOPE", expected_owner_id="bad scope/")

    def test_16_nonstring_expected_scope_is_rejected(self):
        self.denied(self.proposal(), "INVALID_EXPECTED_SCOPE", expected_tenant_id=123)

    def test_17_booleans_cannot_pass_as_scope(self):
        p = self.proposal()
        p["owner_id"] = True
        self.denied(p, "COMPARISON_SCOPE_MISMATCH")

    def test_18_premature_decision_is_rejected(self):
        p = self.proposal()
        p["decision_state"] = "APPROVED"
        self.denied(p, "PREMATURE_MODEL_DECISION")

    def test_19_host_claimed_owner_approval_is_rejected(self):
        p = self.proposal()
        p["owner_approval_state"] = "OWNER_APPROVED"
        self.denied(p, "HOST_ASSERTED_OWNER_APPROVAL")

    def test_20_offline_winner_selection_is_rejected(self):
        p = self.proposal()
        p["chosen_model"] = OFFLINE
        self.denied(p, "PREMATURE_ROOT_CUSTODY_SELECTION")

    def test_21_kms_winner_selection_is_rejected(self):
        p = self.proposal()
        p["chosen_model"] = KMS
        self.denied(p, "PREMATURE_ROOT_CUSTODY_SELECTION")

    def test_22_external_p0_claims_are_rejected(self):
        for fake in (1, 6, True, "0", -1):
            with self.subTest(fake=fake):
                p = self.proposal()
                p["p0_external_homologated"] = fake
                self.denied(p, "FORGED_EXTERNAL_P0_HOMOLOGATION")

    def test_23_missing_model_is_rejected(self):
        p = self.proposal()
        p["models"].pop()
        self.denied(p, "RESEARCH_MODELS_INCOMPLETE")

    def test_24_wrong_model_container_is_rejected(self):
        p = self.proposal()
        p["models"] = {}
        self.denied(p, "RESEARCH_MODELS_INCOMPLETE")

    def test_25_missing_model_field_is_rejected(self):
        p = self.proposal()
        p["models"][0].pop("audit_state")
        self.denied(p, "ROOT_MODEL_ENVELOPE_NOT_EXACT")

    def test_26_secret_material_field_is_rejected(self):
        p = self.proposal()
        p["models"][0]["private_key"] = "SHOULD_NOT_EXIST"
        self.denied(p, "ROOT_MODEL_ENVELOPE_NOT_EXACT")

    def test_27_cloud_credentials_field_is_rejected(self):
        p = self.proposal()
        p["models"][1]["cloud_access_token"] = "SHOULD_NOT_EXIST"
        self.denied(p, "ROOT_MODEL_ENVELOPE_NOT_EXACT")

    def test_28_vendor_selection_field_is_rejected(self):
        p = self.proposal()
        p["models"][1]["vendor"] = "host-selected"
        self.denied(p, "ROOT_MODEL_ENVELOPE_NOT_EXACT")

    def test_29_unknown_model_is_rejected(self):
        p = self.proposal()
        p["models"][1]["model_id"] = "HOST_ROOT"
        self.denied(p, "UNSUPPORTED_ROOT_MODEL")

    def test_30_duplicate_model_is_rejected(self):
        p = self.proposal()
        p["models"][1]["model_id"] = OFFLINE
        self.denied(p, "DUPLICATE_ROOT_MODEL")

    def test_31_claimed_identity_verification_is_rejected(self):
        p = self.proposal()
        p["models"][0]["identity_state"] = "VERIFIED"
        self.denied(p, "ROOT_RESEARCH_STATE_CANNOT_CLAIM_PROOF")

    def test_32_claimed_control_domain_is_rejected(self):
        p = self.proposal()
        p["models"][1]["control_domain"] = "independent-account"
        self.denied(p, "ROOT_RESEARCH_STATE_CANNOT_CLAIM_PROOF")

    def test_33_generated_key_claim_is_rejected(self):
        p = self.proposal()
        p["models"][0]["key_material_state"] = "KEY_CREATED"
        self.denied(p, "ROOT_RESEARCH_STATE_CANNOT_CLAIM_PROOF")

    def test_34_approved_signing_policy_is_rejected(self):
        p = self.proposal()
        p["models"][1]["signing_policy_state"] = "APPROVED"
        self.denied(p, "ROOT_RESEARCH_STATE_CANNOT_CLAIM_PROOF")

    def test_35_fake_separation_and_audit_are_rejected(self):
        for field in ("authorization_separation_state", "audit_state"):
            with self.subTest(field=field):
                p = self.proposal()
                p["models"][1][field] = "EXTERNALLY_VERIFIED"
                self.denied(p, "ROOT_RESEARCH_STATE_CANNOT_CLAIM_PROOF")

    def test_36_revocation_recovery_availability_cannot_be_self_tested(self):
        for field in ("revocation_state", "recovery_state", "availability_state"):
            with self.subTest(field=field):
                p = self.proposal()
                p["models"][0][field] = "TESTED_OK"
                self.denied(p, "ROOT_RESEARCH_STATE_CANNOT_CLAIM_PROOF")

    def test_37_cost_quote_or_activated_research_is_rejected(self):
        for field, value in (("cost_state", "QUOTED"), ("research_state", "IN_PRODUCTION")):
            with self.subTest(field=field):
                p = self.proposal()
                p["models"][1][field] = value
                self.denied(p, "ROOT_RESEARCH_STATE_CANNOT_CLAIM_PROOF")

    def test_38_duplicate_json_keys_are_rejected(self):
        plain = json.dumps(self.proposal())
        ambiguous = plain.replace(
            '"chosen_model": "NONE"',
            '"chosen_model": "NONE", "chosen_model": "OWNER_OFFLINE_ROOT"', 1,
        )
        self.assertNotEqual(plain, ambiguous)
        self.denied(ambiguous, "AMBIGUOUS_OR_OVERSIZED_COMPARISON_JSON")

    def test_39_oversized_json_and_non_dict_rejected(self):
        self.denied("{" + " " * 9000 + "}", "AMBIGUOUS_OR_OVERSIZED_COMPARISON_JSON")
        self.denied([], "COMPARISON_ENVELOPE_NOT_EXACT")

    def test_40_repeat_without_side_effects_or_authority(self):
        p = self.proposal()
        original = copy.deepcopy(p)
        first = self.assess(p)
        for _ in range(10):
            r = self.assess(p)
            self.assertEqual(r, first)
            self.assertEqual(r.external_p0_homologated, 0)
            self.assertFalse(r.may_sign)
            self.assertFalse(r.may_confirm)
        self.assertEqual(p, original)
        self.assertNotEqual(first.comparison_digest, "")
        changed = copy.deepcopy(p)
        changed["workspace_id"] = "other-workspace"
        r = self.assess(changed, expected_workspace_id="other-workspace")
        self.assertTrue(r.comparison_complete)
        self.assertNotEqual(r.comparison_digest, first.comparison_digest)


if __name__ == "__main__":
    unittest.main()
