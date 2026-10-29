"""A225: 50 no-authorization checks for forged host evidence claims."""
from dataclasses import FrozenInstanceError
import copy
import json
import unittest

from labs.a220_synthetic_root_attack_boundaries import KMS_HSM, OFFLINE, SCENARIOS
from labs.a221_independent_evidence_blueprint import CONTROL_PROTOCOLS
from labs.a224_security_proof_test_catalog import preflight_security_test_catalog
from labs.a225_untrusted_security_proof_rejection import (
    SCHEMA, FORGERY_TACTICS, preflight_untrusted_forged_security_proof,
)
from labs.test_a223_owner_security_priority import (
    OWNER, TENANT, WORKSPACE, research_note, unfilled_a222,
)
from labs.test_a224_security_proof_test_catalog import make_a224


_UNSET = object()
DEFAULT_ATTACK = "HOST_READS_OFFLINE_PRIVATE_MATERIAL"


def forged_note(*, model=OFFLINE, attack=DEFAULT_ATTACK,
                tactic="HOST_SELF_ATTESTED_PASS", a224=None, a223=None, a222=None):
    if a222 is None:
        a222 = unfilled_a222()
    if a223 is None:
        a223 = research_note(a222)
    if a224 is None:
        a224 = make_a224(a223, a222)
    check = preflight_security_test_catalog(
        a224, a223_note=a223, a222_matrix=a222,
        expected_owner_id=OWNER, expected_tenant_id=TENANT,
        expected_workspace_id=WORKSPACE,
    )
    assert check.catalog_complete
    _, control_id = SCENARIOS[attack]
    role, kind = CONTROL_PROTOCOLS[control_id]
    return {
        "schema": SCHEMA,
        "owner_id": OWNER, "tenant_id": TENANT, "workspace_id": WORKSPACE,
        "a224_catalog_digest": check.catalog_digest,
        "model_id": model, "attack_id": attack,
        "control_id": control_id, "challenge_kind": kind,
        "claimed_source_role": role, "forgery_tactic": tactic,
        "claim_origin": "HOST_CONTROLLED_UNTRUSTED",
        "claimed_execution_state": "HOST_CLAIMS_PASS_UNVERIFIED",
        "claimed_evidence_digest": "a" * 64,
        "claimed_witness_digest": "b" * 64,
        "issuer_identity_state": "UNVERIFIED",
        "external_proof_state": "NOT_OBTAINED",
        "independent_review_state": "UNASSIGNED",
        "owner_approval_state": "NOT_REQUESTED",
        "provider_receipt_state": "NOT_OBTAINED",
        "external_p0_homologated": 0,
        "uncertain_resend_policy": "ZERO_AUTO_RESEND",
    }


class A225UntrustedForgedEvidenceTests(unittest.TestCase):
    def check(self, candidate=_UNSET, *, a224=None, a223=None, a222=None, **kwargs):
        if a222 is None:
            a222 = unfilled_a222()
        if a223 is None:
            a223 = research_note(a222)
        if a224 is None:
            a224 = make_a224(a223, a222)
        if candidate is _UNSET:
            candidate = forged_note(a224=a224, a223=a223, a222=a222)
        args = {
            "a224_catalog": a224, "a223_note": a223,
            "a222_matrix": a222, "expected_owner_id": OWNER,
            "expected_tenant_id": TENANT,
            "expected_workspace_id": WORKSPACE,
        }
        args.update(kwargs)
        return preflight_untrusted_forged_security_proof(candidate, **args)

    def no_authority(self, r):
        self.assertFalse(r.owner_identity_verified)
        self.assertFalse(r.independent_issuer_verified)
        self.assertFalse(r.independent_witness_verified)
        self.assertFalse(r.external_proof_accepted)
        self.assertFalse(r.owner_signoff_valid)
        self.assertFalse(r.provider_final_effect_verified)
        self.assertEqual(r.external_p0_homologated, 0)
        for field in (
            "may_accept_security_proof", "may_select_model", "may_contact_person",
            "may_run_external_challenge", "may_commit_budget", "may_provision",
            "may_generate_key", "may_sign", "may_connect", "may_confirm",
            "may_auto_resend",
        ):
            self.assertFalse(getattr(r, field), field)

    def denied(self, candidate, code, *, a224=None, a223=None, a222=None, **kwargs):
        r = self.check(candidate, a224=a224, a223=a223, a222=a222, **kwargs)
        self.assertFalse(r.local_shape_matches_research_catalog)
        self.assertFalse(r.hostile_tactic_identified)
        self.assertEqual(r.code, code)
        self.assertEqual(r.untrusted_claim_digest, "")
        self.assertEqual(r.scenario, "")
        self.no_authority(r)

    def changed(self, name, value, code):
        claim = forged_note()
        claim[name] = value
        self.denied(claim, code)

    def test_01_host_claim_matches_catalog_but_never_proves_it(self):
        r = self.check()
        self.assertTrue(r.local_shape_matches_research_catalog)
        self.assertTrue(r.hostile_tactic_identified)
        self.assertEqual(r.code, "HOST_FORGED_PROOF_LOCALLY_WELL_FORMED_BUT_NO_EXTERNAL_PROOF_HARD_NO_GO")
        self.assertEqual(len(r.untrusted_claim_digest), 64)
        self.no_authority(r)

    def test_02_all_eight_tactics_only_host_claims(self):
        self.assertEqual(len(FORGERY_TACTICS), 8)
        for tactic in sorted(FORGERY_TACTICS):
            r = self.check(forged_note(tactic=tactic))
            self.assertTrue(r.local_shape_matches_research_catalog, tactic)
            self.assertEqual(r.forgery_tactic, tactic)
            self.no_authority(r)

    def test_03_all_13_attacks_with_valid_model_stay_unproven(self):
        for attack, (models, _) in SCENARIOS.items():
            model = sorted(models)[0]
            r = self.check(forged_note(model=model, attack=attack))
            self.assertEqual(r.scenario, attack)
            self.no_authority(r)

    def test_04_all_21_valid_model_attack_pairs_never_grant(self):
        pairs = [(attack, model) for attack, (models, _) in SCENARIOS.items() for model in models]
        self.assertEqual(len(pairs), 21)
        for attack, model in pairs:
            r = self.check(forged_note(model=model, attack=attack))
            self.assertTrue(r.local_shape_matches_research_catalog)
            self.no_authority(r)

    def test_05_168_combinations_all_remain_untrusted(self):
        count = 0
        for attack, (models, _) in SCENARIOS.items():
            for model in models:
                for tactic in FORGERY_TACTICS:
                    r = self.check(forged_note(model=model, attack=attack, tactic=tactic))
                    self.assertTrue(r.local_shape_matches_research_catalog)
                    self.no_authority(r)
                    count += 1
        self.assertEqual(count, 168)

    def test_06_forged_owner_approval_cannot_raise_authority(self):
        self.no_authority(self.check(forged_note(tactic="FORGED_OWNER_SIGNOFF")))

    def test_07_fake_witness_cannot_raise_authority(self):
        self.no_authority(self.check(forged_note(tactic="FAKE_INDEPENDENT_WITNESS")))

    def test_08_fake_provider_receipt_cannot_confirm_broker_effect(self):
        self.no_authority(self.check(forged_note(tactic="FAKE_PROVIDER_FINAL_RECEIPT")))

    def test_09_replayed_digest_cannot_verify_identity(self):
        self.no_authority(self.check(forged_note(tactic="REPLAYED_EVIDENCE_DIGEST")))

    def test_10_outage_pressure_cannot_enable_resend(self):
        self.no_authority(self.check(forged_note(tactic="OUTAGE_RETRY_PRESSURE")))

    def test_11_self_attested_kms_denial_not_independent(self):
        r = self.check(forged_note(model=KMS_HSM, attack="HOST_INVOKES_KMS_SIGN", tactic="KMS_POLICY_SCREENSHOT_CLAIM"))
        self.no_authority(r)

    def test_12_self_attested_offline_custody_not_independent(self):
        r = self.check(forged_note(tactic="OFFLINE_CUSTODIAN_SCREENSHOT_CLAIM"))
        self.no_authority(r)

    def test_13_json_copy_does_not_improve_proof(self):
        r = self.check(json.dumps(forged_note()))
        self.assertTrue(r.local_shape_matches_research_catalog)
        self.no_authority(r)

    def test_14_repeat_no_mutation_or_authority(self):
        claim, matrix = forged_note(), unfilled_a222()
        note = research_note(matrix)
        catalog = make_a224(note, matrix)
        snapshot = copy.deepcopy((claim, matrix, note, catalog))
        for _ in range(5):
            self.no_authority(self.check(claim, a222=matrix, a223=note, a224=catalog))
        self.assertEqual((claim, matrix, note, catalog), snapshot)

    def test_15_result_immutable_to_approval(self):
        with self.assertRaises(FrozenInstanceError):
            self.check().may_accept_security_proof = True

    def test_16_extra_field_rejected(self):
        n = forged_note()
        n["owner_signature_valid"] = True
        self.denied(n, "FORGED_PROOF_ENVELOPE_NOT_EXACT")

    def test_17_missing_required_fields_rejected(self):
        for field in ("schema", "model_id", "a224_catalog_digest", "claimed_witness_digest"):
            n = forged_note()
            del n[field]
            self.denied(n, "FORGED_PROOF_ENVELOPE_NOT_EXACT")

    def test_18_non_dict_candidates_rejected(self):
        for bad in (None, [], True, 5, {}):
            self.denied(bad, "FORGED_PROOF_ENVELOPE_NOT_EXACT")

    def test_19_non_object_json_rejected(self):
        self.denied('"PASS"', "AMBIGUOUS_OR_OVERSIZED_FORGED_PROOF_JSON")

    def test_20_wrong_schema_rejected(self):
        self.changed("schema", "REAL_EVIDENCE_ACCEPTED", "FORGED_PROOF_SCHEMA_UNSUPPORTED")

    def test_21_other_owner_scope_rejected(self):
        self.changed("owner_id", "other", "FORGED_PROOF_SCOPE_MISMATCH")

    def test_22_other_tenant_scope_rejected(self):
        self.changed("tenant_id", "other", "FORGED_PROOF_SCOPE_MISMATCH")

    def test_23_other_workspace_scope_rejected(self):
        self.changed("workspace_id", "other", "FORGED_PROOF_SCOPE_MISMATCH")

    def test_24_expected_owner_scope_invalid_rejected(self):
        self.denied(forged_note(), "INVALID_EXPECTED_SCOPE", expected_owner_id="a/b")

    def test_25_expected_tenant_scope_nonstr_rejected(self):
        self.denied(forged_note(), "INVALID_EXPECTED_SCOPE", expected_tenant_id=True)

    def test_26_expected_workspace_nonstr_rejected(self):
        self.denied(forged_note(), "INVALID_EXPECTED_SCOPE", expected_workspace_id=1)

    def test_27_boolean_candidate_scope_rejected(self):
        self.changed("owner_id", True, "FORGED_PROOF_SCOPE_MISMATCH")

    def test_28_unknown_model_rejected(self):
        for x in ("HOST_ROOT", None, 1, False):
            self.changed("model_id", x, "UNKNOWN_CUSTODY_MODEL")

    def test_29_unknown_attack_rejected(self):
        for x in ("ROOT_SAFE", None, 4):
            self.changed("attack_id", x, "UNKNOWN_FORGED_PROOF_SCENARIO")

    def test_30_offline_attack_with_kms_model_rejected(self):
        self.changed("model_id", KMS_HSM, "ATTACK_AND_MODEL_INCOMPATIBLE")

    def test_31_kms_attack_with_offline_model_rejected(self):
        n = forged_note(model=KMS_HSM, attack="HOST_INVOKES_KMS_SIGN")
        n["model_id"] = OFFLINE
        self.denied(n, "ATTACK_AND_MODEL_INCOMPATIBLE")

    def test_32_wrong_control_id_rejected(self):
        self.changed("control_id", "kms_host_sign_denied", "CLAIMED_SECURITY_CONTROL_MISMATCH")

    def test_33_wrong_source_role_rejected(self):
        self.changed("claimed_source_role", "HOST_CEO", "CLAIMED_SOURCE_ROLE_OR_CHALLENGE_MISMATCH")

    def test_34_wrong_challenge_rejected(self):
        self.changed("challenge_kind", "SKIP_EXTERNAL_TEST", "CLAIMED_SOURCE_ROLE_OR_CHALLENGE_MISMATCH")

    def test_35_unknown_tactic_rejected(self):
        for x in ("TRUSTED_REAL_PROOF", None, 4):
            self.changed("forgery_tactic", x, "UNSUPPORTED_FORGERY_TACTIC")

    def test_36_origin_cannot_claim_external_attestation(self):
        self.changed("claim_origin", "INDEPENDENT_ATTESTED", "HOST_CLAIM_CANNOT_BECOME_EXTERNAL_PROOF")

    def test_37_claimed_pass_is_not_actual_execution(self):
        self.changed("claimed_execution_state", "TEST_PASSED_VERIFIED", "HOST_CLAIM_CANNOT_BECOME_EXTERNAL_PROOF")

    def test_38_claimed_issuer_identity_unverified(self):
        self.changed("issuer_identity_state", "VERIFIED", "HOST_CLAIM_CANNOT_BECOME_EXTERNAL_PROOF")

    def test_39_external_proof_cannot_be_marked_accepted(self):
        self.changed("external_proof_state", "OBTAINED", "HOST_CLAIM_CANNOT_BECOME_EXTERNAL_PROOF")

    def test_40_reviewer_cannot_be_assigned_by_host(self):
        self.changed("independent_review_state", "APPROVED", "HOST_CLAIM_CANNOT_BECOME_EXTERNAL_PROOF")

    def test_41_owner_signoff_cannot_be_forged(self):
        self.changed("owner_approval_state", "SIGNED", "HOST_CLAIM_CANNOT_BECOME_EXTERNAL_PROOF")

    def test_42_broker_receipt_cannot_be_forged(self):
        self.changed("provider_receipt_state", "FINAL_CONFIRMED", "HOST_CLAIM_CANNOT_BECOME_EXTERNAL_PROOF")

    def test_43_uncertain_auto_resend_cannot_be_enabled(self):
        self.changed("uncertain_resend_policy", "AUTO_RESEND", "HOST_CLAIM_CANNOT_BECOME_EXTERNAL_PROOF")

    def test_44_external_p0_cannot_be_self_certified(self):
        for val in (1, 6, True, -1, "0"):
            self.changed("external_p0_homologated", val, "FORGED_EXTERNAL_P0_HOMOLOGATION")

    def test_45_fake_hashes_must_be_well_shaped_but_never_authoritative(self):
        for field in ("claimed_evidence_digest", "claimed_witness_digest"):
            for val in ("X" * 64, "f" * 63, None, True):
                self.changed(field, val, "INVALID_UNTRUSTED_DIGEST")

    def test_46_wrong_a224_digest_cannot_be_substituted(self):
        self.changed("a224_catalog_digest", "0" * 64, "A224_LOCAL_CATALOG_DIGEST_MISMATCH")

    def test_47_malformed_a224_digest_rejected(self):
        for val in ("1", "F" * 64, None, True):
            self.changed("a224_catalog_digest", val, "A224_LOCAL_CATALOG_DIGEST_MISMATCH")

    def test_48_mutated_a224_plan_not_acceptable(self):
        catalog = make_a224()
        catalog["test_catalog"][0]["execution_state"] = "PASSED"
        self.denied(forged_note(), "A224_UNEXECUTED_TEST_CATALOG_REQUIRED", a224=catalog)

    def test_49_corrupted_a223_or_a222_cannot_make_evidence(self):
        note = research_note()
        note["preference_source"] = "SIGNED_BY_OWNER"
        self.denied(forged_note(), "A224_UNEXECUTED_TEST_CATALOG_REQUIRED", a223=note, a224=make_a224())
        matrix = unfilled_a222()
        matrix["owner_signoff_state"] = "SIGNED"
        self.denied(forged_note(), "A224_UNEXECUTED_TEST_CATALOG_REQUIRED", a223=research_note(), a222=matrix, a224=make_a224())

    def test_50_duplicate_json_and_oversized_payload_fail_closed(self):
        raw = json.dumps(forged_note())
        dup = raw.replace(
            '"owner_id": "synthetic-owner"',
            '"owner_id": "synthetic-owner", "owner_id": "forged-owner"', 1,
        )
        self.assertNotEqual(dup, raw)
        self.denied(dup, "AMBIGUOUS_OR_OVERSIZED_FORGED_PROOF_JSON")
        self.denied("{" + " " * 9000 + "}", "AMBIGUOUS_OR_OVERSIZED_FORGED_PROOF_JSON")


if __name__ == "__main__":
    unittest.main()
