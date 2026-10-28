"""A218: 30 vendor-neutral source-decision tests. No API/provider/key calls."""
from dataclasses import FrozenInstanceError
import copy
import json
import unittest

from labs.a218_source_portfolio_preflight import (
    SCHEMA, preflight_source_portfolio,
)


OWNER = "synthetic-owner"
TENANT = "synthetic-tenant"
WORKSPACE = "synthetic-workspace"
OPTIONS = [
    ("ROOT", "OWNER_OFFLINE_ROOT"),
    ("ROOT", "SEPARATE_DOMAIN_HSM"),
    ("PROVIDER", "PROVIDER_SIGNED_FINAL_RECEIPT"),
    ("PROVIDER", "PROVIDER_AUTHORITATIVE_QUERY"),
    ("WITNESS", "INDEPENDENT_APPEND_ONLY_LOG"),
    ("WITNESS", "OFFHOST_CHECKPOINT_FLOOR"),
]


class A218ResearchOnlySourcePortfolioTests(unittest.TestCase):
    def proposal(self):
        return {
            "schema": SCHEMA,
            "owner_id": OWNER,
            "tenant_id": TENANT,
            "workspace_id": WORKSPACE,
            "decision_state": "AWAITING_OWNER_SOURCE_CHOICE",
            "owner_approval_state": "NOT_REQUESTED",
            "selected_option_ids": [],
            "p0_external_homologated": 0,
            "candidates": [
                {
                    "role": role,
                    "option": option,
                    "source_id": f"research-opt-{i}",
                    "control_domain": "UNASSIGNED",
                    "evidence_state": "NOT_OBTAINED",
                    "contact_state": "NOT_CONTACTED",
                    "estimated_cost_state": "NOT_QUOTED",
                    "status": "RESEARCH_ONLY",
                }
                for i, (role, option) in enumerate(OPTIONS, 1)
            ],
        }

    def assess(self, proposal=None, **overrides):
        args = {
            "expected_owner_id": OWNER,
            "expected_tenant_id": TENANT,
            "expected_workspace_id": WORKSPACE,
        }
        args.update(overrides)
        return preflight_source_portfolio(
            self.proposal() if proposal is None else proposal, **args,
        )

    def denied(self, proposal, code, **overrides):
        result = self.assess(proposal, **overrides)
        self.assertEqual(result.code, code)
        self.assertFalse(result.catalog_complete)
        self.assertFalse(result.independent_root_verified)
        self.assertFalse(result.owner_decision_approved)
        self.assertEqual(result.external_p0_homologated, 0)
        self.assertFalse(result.may_provision)
        self.assertFalse(result.may_connect)
        self.assertFalse(result.may_confirm)
        return result

    def test_01_complete_catalog_is_only_research(self):
        result = self.assess()
        self.assertTrue(result.catalog_complete)
        self.assertEqual(
            result.code, "CANDIDATE_OPTIONS_COMPLETE_OWNER_AND_EXTERNAL_PROOF_PENDING",
        )
        self.assertEqual(len(result.catalog_digest), 64)
        self.assertFalse(result.independent_root_verified)
        self.assertFalse(result.owner_decision_approved)
        self.assertEqual(result.external_p0_homologated, 0)
        self.assertFalse(result.may_provision)
        self.assertFalse(result.may_connect)
        self.assertFalse(result.may_confirm)

    def test_02_valid_json_catalog_remains_non_authoritative(self):
        result = self.assess(json.dumps(self.proposal()))
        self.assertTrue(result.catalog_complete)
        self.assertFalse(result.may_connect)

    def test_03_result_is_frozen_against_trust_promotion(self):
        result = self.assess()
        with self.assertRaises(FrozenInstanceError):
            result.may_provision = True
        with self.assertRaises(FrozenInstanceError):
            result.independent_root_verified = True

    def test_04_extra_verified_flag_cannot_activate(self):
        p = self.proposal()
        p["independently_verified"] = True
        self.denied(p, "PORTFOLIO_ENVELOPE_NOT_EXACT")

    def test_05_missing_portfolio_keys_rejected(self):
        for field in ("owner_id", "decision_state", "p0_external_homologated", "candidates"):
            with self.subTest(field=field):
                p = self.proposal()
                p.pop(field)
                self.denied(p, "PORTFOLIO_ENVELOPE_NOT_EXACT")

    def test_06_unknown_schema_rejected(self):
        p = self.proposal()
        p["schema"] = "HOST_APPROVED"
        self.denied(p, "PORTFOLIO_SCHEMA_UNSUPPORTED")

    def test_07_owner_scope_collision_rejected(self):
        p = self.proposal()
        p["owner_id"] = "intruder"
        self.denied(p, "OWNER_SCOPE_MISMATCH")

    def test_08_tenant_and_workspace_swap_rejected(self):
        for field in ("tenant_id", "workspace_id"):
            p = self.proposal()
            p[field] = "other"
            self.denied(p, "OWNER_SCOPE_MISMATCH")

    def test_09_untrusted_owner_expectation_rejected(self):
        self.denied(
            self.proposal(), "INVALID_EXPECTED_OWNER_SCOPE",
            expected_owner_id="with spaces /",
        )

    def test_10_host_cannot_set_decision_approved(self):
        p = self.proposal()
        p["decision_state"] = "APPROVED"
        self.denied(p, "PREMATURE_SOURCE_DECISION")

    def test_11_host_cannot_assert_owner_approval(self):
        p = self.proposal()
        p["owner_approval_state"] = "OWNER_APPROVED"
        self.denied(p, "OWNER_APPROVAL_NOT_ESTABLISHED")

    def test_12_host_cannot_choose_root_provider_or_witness(self):
        p = self.proposal()
        p["selected_option_ids"] = ["research-opt-1"]
        self.denied(p, "SOURCE_SELECTION_PREMATURE")

    def test_13_selected_options_must_be_empty_real_list(self):
        p = self.proposal()
        p["selected_option_ids"] = ""
        self.denied(p, "SOURCE_SELECTION_PREMATURE")

    def test_14_p0_homologated_cannot_be_forged(self):
        for fake in (1, 6, True, "0", -1):
            with self.subTest(fake=fake):
                p = self.proposal()
                p["p0_external_homologated"] = fake
                self.denied(p, "FALSE_EXTERNAL_P0_HOMOLOGATION")

    def test_15_missing_source_option_rejected(self):
        p = self.proposal()
        p["candidates"].pop()
        self.denied(p, "SOURCE_OPTIONS_INCOMPLETE")

    def test_16_wrong_candidate_container_rejected(self):
        p = self.proposal()
        p["candidates"] = {}
        self.denied(p, "SOURCE_OPTIONS_INCOMPLETE")

    def test_17_extra_credentials_field_rejected(self):
        p = self.proposal()
        p["candidates"][0]["api_key"] = "DO_NOT_USE_CREDENTIALS"
        self.denied(p, "SOURCE_CANDIDATE_ENVELOPE_NOT_EXACT")

    def test_18_missing_candidate_field_rejected(self):
        p = self.proposal()
        p["candidates"][0].pop("status")
        self.denied(p, "SOURCE_CANDIDATE_ENVELOPE_NOT_EXACT")

    def test_19_unknown_vendor_option_rejected(self):
        p = self.proposal()
        p["candidates"][0]["option"] = "MAGICAL_HOST_ROOT"
        self.denied(p, "UNSUPPORTED_RESEARCH_OPTION")

    def test_20_role_option_mismatch_rejected(self):
        p = self.proposal()
        p["candidates"][0]["role"] = "PROVIDER"
        self.denied(p, "SOURCE_ROLE_OPTION_MISMATCH")

    def test_21_invalid_candidate_identifier_rejected(self):
        p = self.proposal()
        p["candidates"][0]["source_id"] = "fake id with spaces"
        self.denied(p, "INVALID_SOURCE_CANDIDATE_ID")

    def test_22_duplicate_candidate_id_rejected(self):
        p = self.proposal()
        p["candidates"][1]["source_id"] = p["candidates"][0]["source_id"]
        self.denied(p, "DUPLICATED_SOURCE_OPTION_OR_ID")

    def test_23_duplicate_option_rejected(self):
        p = self.proposal()
        p["candidates"][1]["option"] = p["candidates"][0]["option"]
        self.denied(p, "DUPLICATED_SOURCE_OPTION_OR_ID")

    def test_24_unapproved_control_domain_rejected(self):
        p = self.proposal()
        p["candidates"][0]["control_domain"] = "user-picked-service"
        self.denied(p, "PREMATURE_CONTROL_DOMAIN_SELECTION")

    def test_25_unverified_external_evidence_cannot_be_self_claimed_verified(self):
        p = self.proposal()
        p["candidates"][2]["evidence_state"] = "INDEPENDENTLY_VERIFIED"
        self.denied(p, "EXTERNAL_EVIDENCE_UNVERIFIED")

    def test_26_contacting_external_party_not_authorized(self):
        p = self.proposal()
        p["candidates"][2]["contact_state"] = "CONTACTED"
        self.denied(p, "EXTERNAL_COORDINATION_NOT_AUTHORIZED")

    def test_27_price_quote_cannot_be_marked_without_user_scope(self):
        p = self.proposal()
        p["candidates"][3]["estimated_cost_state"] = "QUOTED"
        self.denied(p, "FINANCIAL_COMMITMENT_NOT_AUTHORIZED")

    def test_28_candidate_cannot_upgrade_itself_to_trusted(self):
        p = self.proposal()
        p["candidates"][4]["status"] = "TRUSTED"
        self.denied(p, "SOURCE_CANDIDATE_PREMATURELY_TRUSTED")

    def test_29_duplicate_json_keys_rejected_before_host_collapse(self):
        p = json.dumps(self.proposal())
        ambiguous = p.replace(
            '"decision_state": "AWAITING_OWNER_SOURCE_CHOICE"',
            '"decision_state": "AWAITING_OWNER_SOURCE_CHOICE", "decision_state": "APPROVED"',
            1,
        )
        self.assertNotEqual(ambiguous, p)
        self.denied(ambiguous, "AMBIGUOUS_OR_OVERSIZED_PORTFOLIO_JSON")

    def test_30_repeat_without_mutation_cannot_change_external_state(self):
        original = self.proposal()
        snapshot = copy.deepcopy(original)
        first = self.assess(original)
        for _ in range(10):
            result = self.assess(original)
            self.assertEqual(first, result)
            self.assertFalse(result.may_confirm)
            self.assertEqual(result.external_p0_homologated, 0)
        self.assertEqual(snapshot, original)


if __name__ == "__main__":
    unittest.main()
