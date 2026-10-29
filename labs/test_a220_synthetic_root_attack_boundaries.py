"""A220: 40 adversarial tests of untrusted hypothetical access boundaries."""
from dataclasses import FrozenInstanceError
import copy
import json
import unittest

from labs.a220_synthetic_root_attack_boundaries import (
    SCHEMA, OFFLINE, KMS_HSM, MODELS, SCENARIOS,
    simulate_untrusted_root_attack,
)


OWNER = "synthetic-owner"
TENANT = "synthetic-tenant"
WORKSPACE = "synthetic-workspace"
CONTROLS = (
    "offline_private_material_outside_host",
    "offline_custodian_unreachable_by_host",
    "kms_host_sign_denied",
    "kms_host_policy_write_denied",
    "kms_host_role_assumption_denied",
    "approval_outside_host",
    "signer_admin_approver_roles_separate",
    "nonce_checkpoint_outside_host",
    "revocation_checkpoint_outside_host",
    "audit_witness_outside_host",
    "outage_fails_closed_no_resend",
    "provider_receipt_not_substituted_by_root_signature",
    "scope_isolated",
)


class A220SyntheticRootHostAttackTests(unittest.TestCase):
    def proposal(self, model=OFFLINE, attack="HOST_READS_OFFLINE_PRIVATE_MATERIAL"):
        return {
            "schema": SCHEMA,
            "owner_id": OWNER,
            "tenant_id": TENANT,
            "workspace_id": WORKSPACE,
            "model_id": model,
            "attack_id": attack,
            "attacker_origin": "HOST_CONTROLLED",
            "assumptions_state": "FICTIONAL_UNVERIFIED_ONLY",
            "owner_approval_state": "NOT_REQUESTED",
            "external_p0_homologated": 0,
            "controls": {k: True for k in CONTROLS},
        }

    def assess(self, candidate=None, **overrides):
        args = dict(
            expected_owner_id=OWNER,
            expected_tenant_id=TENANT,
            expected_workspace_id=WORKSPACE,
        )
        args.update(overrides)
        return simulate_untrusted_root_attack(
            self.proposal() if candidate is None else candidate, **args,
        )

    def no_authority(self, result):
        self.assertFalse(result.independently_verified)
        self.assertFalse(result.owner_approval_valid)
        self.assertEqual(result.external_p0_homologated, 0)
        self.assertFalse(result.may_generate_key)
        self.assertFalse(result.may_sign)
        self.assertFalse(result.may_provision)
        self.assertFalse(result.may_connect)
        self.assertFalse(result.may_confirm)
        self.assertFalse(result.may_auto_resend)

    def denied(self, candidate, code, **overrides):
        r = self.assess(candidate, **overrides)
        self.assertEqual(r.code, code)
        self.assertFalse(r.scenario_applicable)
        self.assertFalse(r.assumption_says_blocked)
        self.assertFalse(r.synthetic_gap_detected)
        self.assertFalse(r.attacked_control)
        self.assertFalse(r.assumption_digest)
        self.no_authority(r)
        return r

    def gap(self, candidate, field):
        candidate["controls"][field] = False
        r = self.assess(candidate)
        self.assertEqual(r.code, "SYNTHETIC_ATTACK_REVEALS_ASSUMED_CONTROL_GAP")
        self.assertTrue(r.scenario_applicable)
        self.assertTrue(r.synthetic_gap_detected)
        self.assertFalse(r.assumption_says_blocked)
        self.assertEqual(r.attacked_control, field)
        self.no_authority(r)
        return r

    def test_01_offline_control_only_assumed(self):
        r = self.assess()
        self.assertTrue(r.scenario_applicable)
        self.assertTrue(r.assumption_says_blocked)
        self.assertFalse(r.synthetic_gap_detected)
        self.assertEqual(r.code, "SYNTHETIC_ASSUMPTION_BLOCKS_SCENARIO_NOT_PROOF")
        self.assertEqual(r.attacked_control, "offline_private_material_outside_host")
        self.assertEqual(len(r.assumption_digest), 64)
        self.no_authority(r)

    def test_02_all_applicable_scenarios_have_only_hypothetical_blocks(self):
        for attack, (models, control) in SCENARIOS.items():
            for model in models:
                with self.subTest(attack=attack, model=model):
                    r = self.assess(self.proposal(model, attack))
                    self.assertEqual(r.attacked_control, control)
                    self.assertTrue(r.assumption_says_blocked)
                    self.no_authority(r)

    def test_03_each_missing_control_creates_synthetic_gap(self):
        for attack, (models, control) in SCENARIOS.items():
            for model in models:
                with self.subTest(attack=attack, model=model):
                    self.gap(self.proposal(model, attack), control)

    def test_04_frozen_output_rejects_trust_promotion(self):
        r = self.assess()
        with self.assertRaises(FrozenInstanceError):
            r.may_sign = True
        with self.assertRaises(FrozenInstanceError):
            r.independently_verified = True

    def test_05_json_input_also_never_gains_authority(self):
        r = self.assess(json.dumps(self.proposal()))
        self.assertTrue(r.scenario_applicable)
        self.no_authority(r)

    def test_06_offline_material_exposure_gap(self):
        self.gap(self.proposal(), "offline_private_material_outside_host")

    def test_07_offline_custodian_impersonation_gap(self):
        self.gap(
            self.proposal(OFFLINE, "HOST_IMPERSONATES_OFFLINE_CUSTODIAN"),
            "offline_custodian_unreachable_by_host",
        )

    def test_08_kms_direct_sign_gap(self):
        self.gap(
            self.proposal(KMS_HSM, "HOST_INVOKES_KMS_SIGN"),
            "kms_host_sign_denied",
        )

    def test_09_kms_admin_policy_mutation_gap(self):
        self.gap(
            self.proposal(KMS_HSM, "HOST_CHANGES_KMS_KEY_POLICY"),
            "kms_host_policy_write_denied",
        )

    def test_10_kms_assume_role_gap(self):
        self.gap(
            self.proposal(KMS_HSM, "HOST_ASSUMES_SIGNER_ROLE"),
            "kms_host_role_assumption_denied",
        )

    def test_11_owner_approval_forgery_gap_on_both_models(self):
        for model in MODELS:
            self.gap(self.proposal(model, "HOST_FORGES_OWNER_APPROVAL"), "approval_outside_host")

    def test_12_signer_admin_collusion_gap_on_both_models(self):
        for model in MODELS:
            self.gap(
                self.proposal(model, "ADMIN_SIGNER_APPROVER_COLLUSION"),
                "signer_admin_approver_roles_separate",
            )

    def test_13_nonce_replay_gap_on_both_models(self):
        for model in MODELS:
            self.gap(
                self.proposal(model, "HOST_REPLAYS_OLD_NONCE"),
                "nonce_checkpoint_outside_host",
            )

    def test_14_revocation_replay_gap_on_both_models(self):
        for model in MODELS:
            self.gap(
                self.proposal(model, "HOST_REUSES_REVOKED_ROOT"),
                "revocation_checkpoint_outside_host",
            )

    def test_15_host_audit_erasure_gap_on_both_models(self):
        for model in MODELS:
            self.gap(
                self.proposal(model, "HOST_ERASES_AUDIT_TRAIL"),
                "audit_witness_outside_host",
            )

    def test_16_uncertain_outage_must_not_auto_resend(self):
        for model in MODELS:
            r = self.gap(
                self.proposal(model, "OUTAGE_FORCES_AUTOMATIC_RESEND"),
                "outage_fails_closed_no_resend",
            )
            self.assertFalse(r.may_auto_resend)

    def test_17_root_signature_not_proof_of_broker_effect(self):
        for model in MODELS:
            self.gap(
                self.proposal(model, "ROOT_SIGNATURE_FORGES_BROKER_EFFECT"),
                "provider_receipt_not_substituted_by_root_signature",
            )

    def test_18_cross_tenant_scope_isolation_gap(self):
        for model in MODELS:
            self.gap(
                self.proposal(model, "HOST_SUBSTITUTES_OTHER_TENANT"),
                "scope_isolated",
            )

    def test_19_untrusted_extra_authorization_is_rejected(self):
        p = self.proposal()
        p["approved"] = True
        self.denied(p, "ATTACK_ENVELOPE_NOT_EXACT")

    def test_20_missing_envelope_key_is_rejected(self):
        for key in ("schema", "model_id", "attack_id", "controls"):
            with self.subTest(key=key):
                p = self.proposal()
                p.pop(key)
                self.denied(p, "ATTACK_ENVELOPE_NOT_EXACT")

    def test_21_unknown_schema_is_rejected(self):
        p = self.proposal()
        p["schema"] = "FULLY_TRUSTED"
        self.denied(p, "ATTACK_SCHEMA_UNSUPPORTED")

    def test_22_wrong_owner_scope_is_rejected(self):
        p = self.proposal()
        p["owner_id"] = "other-owner"
        self.denied(p, "SYNTHETIC_SCOPE_MISMATCH")

    def test_23_wrong_tenant_scope_is_rejected(self):
        p = self.proposal()
        p["tenant_id"] = "other-tenant"
        self.denied(p, "SYNTHETIC_SCOPE_MISMATCH")

    def test_24_wrong_workspace_scope_is_rejected(self):
        p = self.proposal()
        p["workspace_id"] = "other-workspace"
        self.denied(p, "SYNTHETIC_SCOPE_MISMATCH")

    def test_25_untrusted_expected_scope_rejected(self):
        self.denied(self.proposal(), "INVALID_EXPECTED_SCOPE", expected_owner_id="not valid/")

    def test_26_expected_scope_types_rejected(self):
        self.denied(self.proposal(), "INVALID_EXPECTED_SCOPE", expected_workspace_id=True)

    def test_27_unknown_root_model_rejected(self):
        p = self.proposal()
        p["model_id"] = "HOST_ROOT"
        self.denied(p, "UNKNOWN_ROOT_MODEL")

    def test_28_unhashable_and_boolean_models_rejected(self):
        for model in ([], {}, False, None):
            with self.subTest(model=model):
                p = self.proposal()
                p["model_id"] = model
                self.denied(p, "UNKNOWN_ROOT_MODEL")

    def test_29_unknown_attack_rejected(self):
        p = self.proposal()
        p["attack_id"] = "HOST_ALREADY_TRUSTED"
        self.denied(p, "UNKNOWN_ATTACK_SCENARIO")

    def test_30_unknown_attack_unhashable_rejected(self):
        p = self.proposal()
        p["attack_id"] = []
        self.denied(p, "UNKNOWN_ATTACK_SCENARIO")

    def test_31_inapplicable_model_scenario_rejected(self):
        p = self.proposal(OFFLINE, "HOST_INVOKES_KMS_SIGN")
        self.denied(p, "SCENARIO_ROOT_MODEL_MISMATCH")
        q = self.proposal(KMS_HSM, "HOST_READS_OFFLINE_PRIVATE_MATERIAL")
        self.denied(q, "SCENARIO_ROOT_MODEL_MISMATCH")

    def test_32_non_host_origin_cannot_claim_real_proof(self):
        p = self.proposal()
        p["attacker_origin"] = "EXTERNAL_INDEPENDENT"
        self.denied(p, "ATTACKER_ORIGIN_NOT_HOST_BOUND")

    def test_33_assumptions_cannot_claim_real_enforcement(self):
        p = self.proposal()
        p["assumptions_state"] = "PROVEN_IN_CLOUD"
        self.denied(p, "UNTRUSTED_ASSUMPTIONS_CANNOT_BECOME_FACT")

    def test_34_owner_approval_claim_rejected(self):
        p = self.proposal()
        p["owner_approval_state"] = "APPROVED"
        self.denied(p, "HOST_ASSERTED_OWNER_APPROVAL")

    def test_35_false_external_p0_claim_rejected(self):
        for fake in (True, 1, 6, "0", -1):
            with self.subTest(fake=fake):
                p = self.proposal()
                p["external_p0_homologated"] = fake
                self.denied(p, "FALSE_EXTERNAL_P0_CLAIM")

    def test_36_malformed_controls_matrix_rejected(self):
        for controls in (None, [], {}, "true"):
            with self.subTest(controls=controls):
                p = self.proposal()
                p["controls"] = controls
                self.denied(p, "SYNTHETIC_CONTROL_MATRIX_NOT_EXACT")

    def test_37_extra_credential_or_missing_control_rejected(self):
        for key, value in (("api_token", "SECRET"), ("kms_key_arn", "arn:synthetic")):
            p = self.proposal()
            p["controls"][key] = value
            self.denied(p, "SYNTHETIC_CONTROL_MATRIX_NOT_EXACT")
        p = self.proposal()
        del p["controls"]["kms_host_sign_denied"]
        self.denied(p, "SYNTHETIC_CONTROL_MATRIX_NOT_EXACT")

    def test_38_non_boolean_controls_cannot_pretend_true(self):
        for bad in (1, "true", None, [], {}):
            with self.subTest(bad=bad):
                p = self.proposal()
                p["controls"]["offline_private_material_outside_host"] = bad
                self.denied(p, "SYNTHETIC_CONTROL_MUST_BE_BOOLEAN")

    def test_39_duplicate_or_oversized_json_rejected(self):
        raw = json.dumps(self.proposal())
        duplicate = raw.replace(
            '"owner_approval_state": "NOT_REQUESTED"',
            '"owner_approval_state": "NOT_REQUESTED", "owner_approval_state": "APPROVED"', 1,
        )
        self.assertNotEqual(duplicate, raw)
        self.denied(duplicate, "AMBIGUOUS_OR_OVERSIZED_ATTACK_JSON")
        self.denied('{' + ' ' * 9000 + '}', "AMBIGUOUS_OR_OVERSIZED_ATTACK_JSON")

    def test_40_replay_and_digests_remain_only_local_assumptions(self):
        p = self.proposal()
        snapshot = copy.deepcopy(p)
        first = self.assess(p)
        for _ in range(10):
            again = self.assess(p)
            self.assertEqual(first, again)
            self.no_authority(again)
        self.assertEqual(p, snapshot)
        self.assertNotEqual(first.assumption_digest, "")
        changed = copy.deepcopy(p)
        changed["controls"]["offline_private_material_outside_host"] = False
        self.assertNotEqual(first.assumption_digest, self.assess(changed).assumption_digest)
        different_scope = copy.deepcopy(p)
        different_scope["workspace_id"] = "other-workspace"
        scoped = self.assess(different_scope, expected_workspace_id="other-workspace")
        self.assertNotEqual(first.assumption_digest, scoped.assumption_digest)
        self.no_authority(scoped)


if __name__ == "__main__":
    unittest.main()
