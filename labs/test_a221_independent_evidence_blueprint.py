"""A221: 40 negative proof-plan tests; no external evidence is collected."""
from collections import Counter
from dataclasses import FrozenInstanceError
import copy
import json
import unittest

from labs.a220_synthetic_root_attack_boundaries import MODELS, OFFLINE, KMS_HSM, SCENARIOS
from labs.a221_independent_evidence_blueprint import (
    SCHEMA, CONTROL_PROTOCOLS, preflight_independent_evidence_blueprint,
)


OWNER = "synthetic-owner"
TENANT = "synthetic-tenant"
WORKSPACE = "synthetic-workspace"


def model_scope(control_id):
    domains = set()
    for eligible, control in SCENARIOS.values():
        if control == control_id:
            domains.update(eligible)
    if domains == MODELS:
        return "BOTH"
    if domains == {OFFLINE}:
        return "OFFLINE_ONLY"
    if domains == {KMS_HSM}:
        return "KMS_HSM_ONLY"
    raise AssertionError(control_id)


class A221UntrustedEvidenceBlueprintTests(unittest.TestCase):
    def proposal(self):
        return {
            "schema": SCHEMA,
            "owner_id": OWNER,
            "tenant_id": TENANT,
            "workspace_id": WORKSPACE,
            "design_state": "RESEARCH_BLUEPRINT_ONLY",
            "owner_approval_state": "NOT_REQUESTED",
            "provider_selection_state": "NO_PROVIDER_SELECTED",
            "external_p0_homologated": 0,
            "requirements": [
                {
                    "control_id": control_id,
                    "model_scope": model_scope(control_id),
                    "nominal_source_role": role,
                    "challenge_kind": kind,
                    "issuer_identity_state": "UNVERIFIED",
                    "reviewer_state": "UNASSIGNED",
                    "witness_state": "NOT_OBTAINED",
                    "challenge_state": "NOT_EXECUTED",
                    "evidence_state": "NOT_OBTAINED",
                    "contact_state": "NOT_CONTACTED",
                    "cost_state": "NOT_QUOTED",
                }
                for control_id, (role, kind) in CONTROL_PROTOCOLS.items()
            ],
        }

    def assess(self, candidate=None, **overrides):
        args = dict(
            expected_owner_id=OWNER,
            expected_tenant_id=TENANT,
            expected_workspace_id=WORKSPACE,
        )
        args.update(overrides)
        return preflight_independent_evidence_blueprint(
            self.proposal() if candidate is None else candidate, **args,
        )

    def safe(self, result):
        self.assertFalse(result.independent_root_verified)
        self.assertFalse(result.independent_witness_verified)
        self.assertFalse(result.owner_approval_valid)
        self.assertEqual(result.external_p0_homologated, 0)
        self.assertFalse(result.may_collect_evidence)
        self.assertFalse(result.may_contact_provider)
        self.assertFalse(result.may_run_external_challenge)
        self.assertFalse(result.may_provision)
        self.assertFalse(result.may_sign)
        self.assertFalse(result.may_connect)
        self.assertFalse(result.may_confirm)

    def denied(self, candidate, code, **overrides):
        result = self.assess(candidate, **overrides)
        self.assertEqual(result.code, code)
        self.assertFalse(result.blueprint_complete)
        self.assertFalse(result.a220_scenarios_covered)
        self.assertFalse(result.blueprint_digest)
        self.safe(result)

    def test_01_complete_blueprint_is_still_without_authority(self):
        r = self.assess()
        self.assertTrue(r.blueprint_complete)
        self.assertTrue(r.a220_scenarios_covered)
        self.assertEqual(r.code, "BLUEPRINT_SHAPE_COMPLETE_EXTERNAL_AUTHORITIES_AND_PROOFS_ABSENT")
        self.assertEqual(len(r.blueprint_digest), 64)
        self.safe(r)

    def test_02_valid_json_does_not_verify_externals(self):
        r = self.assess(json.dumps(self.proposal()))
        self.assertTrue(r.blueprint_complete)
        self.safe(r)

    def test_03_requirement_reorder_does_not_change_digest(self):
        p = self.proposal()
        first = self.assess(p)
        p["requirements"].reverse()
        self.assertEqual(first, self.assess(p))

    def test_04_frozen_results_cannot_grant_permission(self):
        r = self.assess()
        with self.assertRaises(FrozenInstanceError):
            r.may_collect_evidence = True
        with self.assertRaises(FrozenInstanceError):
            r.independent_root_verified = True

    def test_05_blueprint_covers_exact_a220_control_ids(self):
        controls = {c for _, c in SCENARIOS.values()}
        self.assertEqual(set(CONTROL_PROTOCOLS), controls)
        self.assertEqual(len(controls), 13)
        self.assertEqual({x["control_id"] for x in self.proposal()["requirements"]}, controls)

    def test_06_offline_kms_and_both_scope_counts(self):
        counts = Counter(r["model_scope"] for r in self.proposal()["requirements"])
        self.assertEqual(counts, {"OFFLINE_ONLY": 2, "KMS_HSM_ONLY": 3, "BOTH": 8})

    def test_07_nominal_source_roles_not_real_identified_parties(self):
        p = self.proposal()
        for r in p["requirements"]:
            self.assertTrue(r["nominal_source_role"])
            self.assertEqual(r["issuer_identity_state"], "UNVERIFIED")
            self.assertEqual(r["reviewer_state"], "UNASSIGNED")

    def test_08_all_challenges_still_unexecuted(self):
        for r in self.proposal()["requirements"]:
            self.assertEqual(r["challenge_state"], "NOT_EXECUTED")
            self.assertEqual(r["evidence_state"], "NOT_OBTAINED")

    def test_09_extra_trusted_flag_rejected(self):
        p = self.proposal()
        p["trusted"] = True
        self.denied(p, "BLUEPRINT_ENVELOPE_NOT_EXACT")

    def test_10_missing_top_level_keys_rejected(self):
        for field in ("owner_id", "requirements", "schema", "external_p0_homologated"):
            with self.subTest(field=field):
                p = self.proposal()
                del p[field]
                self.denied(p, "BLUEPRINT_ENVELOPE_NOT_EXACT")

    def test_11_wrong_schema_rejected(self):
        p = self.proposal()
        p["schema"] = "A221_ACTIVATED"
        self.denied(p, "BLUEPRINT_SCHEMA_UNSUPPORTED")

    def test_12_wrong_owner_rejected(self):
        p = self.proposal()
        p["owner_id"] = "intruder"
        self.denied(p, "BLUEPRINT_SCOPE_MISMATCH")

    def test_13_wrong_tenant_rejected(self):
        p = self.proposal()
        p["tenant_id"] = "intruder"
        self.denied(p, "BLUEPRINT_SCOPE_MISMATCH")

    def test_14_wrong_workspace_rejected(self):
        p = self.proposal()
        p["workspace_id"] = "intruder"
        self.denied(p, "BLUEPRINT_SCOPE_MISMATCH")

    def test_15_invalid_expected_scope_rejected(self):
        self.denied(self.proposal(), "INVALID_EXPECTED_SCOPE", expected_owner_id="invalid owner/")

    def test_16_untyped_expected_scope_rejected(self):
        self.denied(self.proposal(), "INVALID_EXPECTED_SCOPE", expected_workspace_id=True)

    def test_17_wrong_scope_types_rejected(self):
        p = self.proposal()
        p["tenant_id"] = 123
        self.denied(p, "BLUEPRINT_SCOPE_MISMATCH")

    def test_18_host_approved_design_rejected(self):
        p = self.proposal()
        p["design_state"] = "APPROVED"
        self.denied(p, "HOST_CANNOT_APPROVE_EVIDENCE_DESIGN")

    def test_19_false_owner_approval_rejected(self):
        p = self.proposal()
        p["owner_approval_state"] = "APPROVED_BY_HOST"
        self.denied(p, "HOST_CANNOT_ASSERT_OWNER_APPROVAL")

    def test_20_selected_provider_rejected(self):
        p = self.proposal()
        p["provider_selection_state"] = "AWS_CHOSEN_BY_HOST"
        self.denied(p, "PROVIDER_SELECTION_NOT_AUTHORIZED")

    def test_21_false_p0_rejected(self):
        for fake in (True, 1, 6, "0", -1):
            with self.subTest(fake=fake):
                p = self.proposal()
                p["external_p0_homologated"] = fake
                self.denied(p, "FALSE_EXTERNAL_P0_HOMOLOGATION")

    def test_22_missing_requirement_rejected(self):
        p = self.proposal()
        p["requirements"].pop()
        self.denied(p, "REQUIRED_PROOF_BLUEPRINT_INCOMPLETE")

    def test_23_wrong_requirements_container_rejected(self):
        p = self.proposal()
        p["requirements"] = {}
        self.denied(p, "REQUIRED_PROOF_BLUEPRINT_INCOMPLETE")

    def test_24_extra_requirement_and_missing_field_rejected(self):
        p = self.proposal()
        p["requirements"][0]["api_key"] = "DO_NOT_USE"
        self.denied(p, "EVIDENCE_REQUIREMENT_ENVELOPE_NOT_EXACT")
        q = self.proposal()
        del q["requirements"][0]["issuer_identity_state"]
        self.denied(q, "EVIDENCE_REQUIREMENT_ENVELOPE_NOT_EXACT")

    def test_25_private_key_or_receipt_blob_rejected(self):
        for field in ("private_key", "provider_receipt", "key_arn"):
            p = self.proposal()
            p["requirements"][0][field] = "HOST_CLAIM"
            self.denied(p, "EVIDENCE_REQUIREMENT_ENVELOPE_NOT_EXACT")

    def test_26_unknown_control_rejected(self):
        p = self.proposal()
        p["requirements"][0]["control_id"] = "HOST_CONTROL_PROVES_SECURITY"
        self.denied(p, "UNSUPPORTED_EVIDENCE_CONTROL")

    def test_27_unhashable_control_rejected(self):
        p = self.proposal()
        p["requirements"][0]["control_id"] = []
        self.denied(p, "UNSUPPORTED_EVIDENCE_CONTROL")

    def test_28_duplicate_control_rejected(self):
        p = self.proposal()
        p["requirements"][1]["control_id"] = p["requirements"][0]["control_id"]
        self.denied(p, "DUPLICATE_EVIDENCE_CONTROL")

    def test_29_model_scope_mismatch_rejected(self):
        p = self.proposal()
        p["requirements"][0]["model_scope"] = "BOTH"
        self.denied(p, "EVIDENCE_SCOPE_MISMATCH")

    def test_30_host_cannot_assign_itself_as_source_role(self):
        p = self.proposal()
        p["requirements"][0]["nominal_source_role"] = "HOST_SELF_WITNESS"
        self.denied(p, "EVIDENCE_SOURCE_ROLE_MISMATCH")

    def test_31_wrong_challenge_kind_rejected(self):
        p = self.proposal()
        p["requirements"][0]["challenge_kind"] = "NONE"
        self.denied(p, "EVIDENCE_CHALLENGE_KIND_MISMATCH")

    def test_32_verified_issuer_claim_rejected(self):
        p = self.proposal()
        p["requirements"][0]["issuer_identity_state"] = "VERIFIED"
        self.denied(p, "EVIDENCE_NOT_OBTAINED_OR_REVIEWED")

    def test_33_host_appointed_reviewer_rejected(self):
        p = self.proposal()
        p["requirements"][1]["reviewer_state"] = "OWNER_APPROVED"
        self.denied(p, "EVIDENCE_NOT_OBTAINED_OR_REVIEWED")

    def test_34_host_asserted_witness_rejected(self):
        p = self.proposal()
        p["requirements"][2]["witness_state"] = "SIGNED_BY_HOST"
        self.denied(p, "EVIDENCE_NOT_OBTAINED_OR_REVIEWED")

    def test_35_executed_external_challenge_claim_rejected(self):
        p = self.proposal()
        p["requirements"][3]["challenge_state"] = "PASSED"
        self.denied(p, "EVIDENCE_NOT_OBTAINED_OR_REVIEWED")

    def test_36_obtained_evidence_claim_rejected(self):
        p = self.proposal()
        p["requirements"][4]["evidence_state"] = "INDEPENDENTLY_VERIFIED"
        self.denied(p, "EVIDENCE_NOT_OBTAINED_OR_REVIEWED")

    def test_37_vendor_contact_or_budget_claim_rejected(self):
        for field, value in (("contact_state", "CONTACTED"), ("cost_state", "QUOTED")):
            with self.subTest(field=field):
                p = self.proposal()
                p["requirements"][5][field] = value
                self.denied(p, "EVIDENCE_NOT_OBTAINED_OR_REVIEWED")

    def test_38_unknown_credential_and_boolean_state_rejected(self):
        p = self.proposal()
        p["requirements"][6]["challenge_state"] = True
        self.denied(p, "EVIDENCE_NOT_OBTAINED_OR_REVIEWED")

    def test_39_duplicate_or_oversized_json_rejected(self):
        original = json.dumps(self.proposal())
        fake = original.replace(
            '"owner_approval_state": "NOT_REQUESTED"',
            '"owner_approval_state": "NOT_REQUESTED", "owner_approval_state": "APPROVED"', 1,
        )
        self.assertNotEqual(fake, original)
        self.denied(fake, "AMBIGUOUS_OR_OVERSIZED_BLUEPRINT_JSON")
        self.denied("{" + " " * 9000 + "}", "AMBIGUOUS_OR_OVERSIZED_BLUEPRINT_JSON")

    def test_40_repeat_is_deterministic_and_never_collects_evidence(self):
        p = self.proposal()
        snapshot = copy.deepcopy(p)
        first = self.assess(p)
        for _ in range(10):
            again = self.assess(p)
            self.assertEqual(again, first)
            self.safe(again)
        self.assertEqual(p, snapshot)
        changed = copy.deepcopy(p)
        changed["workspace_id"] = "other-workspace"
        other = self.assess(changed, expected_workspace_id="other-workspace")
        self.assertTrue(other.blueprint_complete)
        self.assertNotEqual(first.blueprint_digest, other.blueprint_digest)
        self.safe(other)


if __name__ == "__main__":
    unittest.main()
