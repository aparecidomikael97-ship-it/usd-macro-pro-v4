"""No authority even for a fully separated *claimed* H0 topology."""
from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_aion_p0_h0_authority_graph_lab import (
    SCHEMA, REQUIRED_ROLES, AUTHORITY_FALSE, PERMANENT_BLOCKERS,
    inspect_authority_graph_lab as inspect,
)


def proposal():
    roles = {}
    for i, role in enumerate(sorted(REQUIRED_ROLES), 1):
        roles[role] = {
            "security_domain_id": f"security-domain-{i:02}",
            "cloud_account_id": f"cloud-account-{i:02}",
            "organization_id": f"organization-{i:02}",
            "signer_fingerprint_sha256": format(i, "064x"),
            "admin_controllers": [f"admin-root-{i:02}"],
            "recovery_controllers": [f"recovery-root-{i:02}"],
            "deployment_controllers": [f"deploy-root-{i:02}"],
            "billing_controllers": [f"billing-root-{i:02}"],
        }
    return {"schema": SCHEMA, "roles": roles, "delegations": []}


class P0H0AuthorityGraphLabTests(unittest.TestCase):
    def check(self, packet, expected=None, consistent=None):
        out = inspect(packet)
        self.assertEqual(out["state"], "HARD_NO_GO")
        self.assertIs(out["allowed"], False)
        self.assertIs(out["simulation_only"], True)
        self.assertEqual(out["blockers"], PERMANENT_BLOCKERS)
        for flag in AUTHORITY_FALSE:
            self.assertIs(out[flag], False, flag)
        if expected:
            self.assertIn(expected, out["findings"])
        if consistent is not None:
            self.assertIs(out["claimed_topology_consistent_lab"], consistent)
        return out

    def test_01_distinct_claimed_roots_still_hard_no_go(self):
        result = self.check(proposal(), consistent=True)
        self.assertEqual(result["findings"], ())

    def test_02_all_role_names_mandatory(self):
        p = proposal(); del p["roles"]["head_issuer"]
        self.check(p, "ROLE_SET_INVALID", False)

    def test_03_unknown_role_rejected(self):
        p = proposal(); p["roles"]["emergency_operator"] = {}
        self.check(p, "ROLE_SET_INVALID", False)

    def test_04_missing_role_field_rejected(self):
        p = proposal(); del p["roles"]["executor"]["recovery_controllers"]
        self.check(p, "ROLE_SHAPE_INVALID:executor", False)

    def test_05_extra_administration_claim_rejected(self):
        p = proposal(); p["roles"]["executor"]["separation_verified"] = True
        self.check(p, "ROLE_SHAPE_INVALID:executor", False)

    def test_06_self_attested_verified_flag_rejected(self):
        p = proposal(); p["independent_issuer_verified"] = True
        self.check(p, "PROPOSAL_SCHEMA_OR_SHAPE_INVALID", False)

    def test_07_unknown_schema_rejected(self):
        p = proposal(); p["schema"] = "OTHER_SCHEMA"
        self.check(p, "PROPOSAL_SCHEMA_OR_SHAPE_INVALID", False)

    def test_08_schema_object_cannot_trick_eq(self):
        class Tricky:
            def __eq__(self, other): return True
        p = proposal(); p["schema"] = Tricky()
        self.check(p, "PROPOSAL_SCHEMA_OR_SHAPE_INVALID", False)

    def test_09_plain_dict_only(self):
        class TrickyDict(dict):
            def __getitem__(self, key): raise RuntimeError("executed")
        self.check(TrickyDict(proposal()), "PROPOSAL_SCHEMA_OR_SHAPE_INVALID", False)

    def test_10_shared_org_detected(self):
        p = proposal()
        p["roles"]["executor"]["organization_id"] = p["roles"]["readback_witness"]["organization_id"]
        self.check(p, "SHARED_CLAIMED_ROOT_OR_KEY:organization_id", False)

    def test_11_shared_cloud_account_detected(self):
        p = proposal()
        p["roles"]["executor"]["cloud_account_id"] = p["roles"]["nonce_custodian"]["cloud_account_id"]
        self.check(p, "SHARED_CLAIMED_ROOT_OR_KEY:cloud_account_id", False)

    def test_12_shared_security_domain_detected(self):
        p = proposal()
        p["roles"]["executor"]["security_domain_id"] = p["roles"]["reservation_signer"]["security_domain_id"]
        self.check(p, "SHARED_CLAIMED_ROOT_OR_KEY:security_domain_id", False)

    def test_13_shared_signer_fingerprint_detected(self):
        p = proposal()
        p["roles"]["executor"]["signer_fingerprint_sha256"] = p["roles"]["head_issuer"]["signer_fingerprint_sha256"]
        self.check(p, "SHARED_CLAIMED_ROOT_OR_KEY:signer_fingerprint_sha256", False)

    def test_14_same_person_direct_controller_rejected(self):
        p = proposal()
        p["roles"]["executor"]["admin_controllers"] = p["roles"]["readback_witness"]["admin_controllers"]
        self.check(p, "SHARED_DIRECT_OR_TRANSITIVE_CONTROL:executor:readback_witness", False)

    def test_15_same_recovery_root_rejected(self):
        p = proposal()
        p["roles"]["executor"]["recovery_controllers"] = p["roles"]["nonce_custodian"]["recovery_controllers"]
        self.check(p, "SHARED_DIRECT_OR_TRANSITIVE_CONTROL:executor:nonce_custodian", False)

    def test_16_shared_deployment_root_rejected(self):
        p = proposal()
        p["roles"]["executor"]["deployment_controllers"] = p["roles"]["head_issuer"]["deployment_controllers"]
        self.check(p, "SHARED_DIRECT_OR_TRANSITIVE_CONTROL:executor:head_issuer", False)

    def test_17_cross_field_admin_to_recovery_rejected(self):
        p = proposal()
        p["roles"]["readback_witness"]["recovery_controllers"] = p["roles"]["head_issuer"]["admin_controllers"]
        self.check(p, "SHARED_DIRECT_OR_TRANSITIVE_CONTROL:head_issuer:readback_witness", False)

    def test_18_transitive_common_root_detected(self):
        p = proposal()
        p["delegations"] = [
            {"controller": "ultimate-root-0001", "controlled": p["roles"]["executor"]["admin_controllers"][0]},
            {"controller": "ultimate-root-0001", "controlled": p["roles"]["head_issuer"]["recovery_controllers"][0]},
        ]
        self.check(p, "SHARED_DIRECT_OR_TRANSITIVE_CONTROL:executor:head_issuer", False)

    def test_19_three_level_transitive_common_root_detected(self):
        p = proposal()
        p["delegations"] = [
            {"controller": "master-root-0001", "controlled": "middle-root-0001"},
            {"controller": "middle-root-0001", "controlled": p["roles"]["executor"]["admin_controllers"][0]},
            {"controller": "master-root-0001", "controlled": p["roles"]["nonce_custodian"]["recovery_controllers"][0]},
        ]
        self.check(p, "SHARED_DIRECT_OR_TRANSITIVE_CONTROL:executor:nonce_custodian", False)

    def test_20_cycle_rejected(self):
        p = proposal()
        p["delegations"] = [
            {"controller": "controller-root-0001", "controlled": "controller-root-0002"},
            {"controller": "controller-root-0002", "controlled": "controller-root-0001"},
        ]
        self.check(p, "CONTROL_DELEGATION_CYCLE", False)

    def test_21_self_edge_rejected(self):
        p = proposal()
        p["delegations"] = [{"controller": "same-controller-01", "controlled": "same-controller-01"}]
        self.check(p, "DELEGATION_EDGE_INVALID", False)

    def test_22_edge_with_extra_verified_field_rejected(self):
        p = proposal()
        p["delegations"] = [{"controller": "controller-root-0001", "controlled": "controller-root-0002", "verified": True}]
        self.check(p, "DELEGATION_EDGE_INVALID", False)

    def test_23_delegation_limit_bounded(self):
        p = proposal()
        p["delegations"] = [
            {"controller": f"controller-root-{i:04}", "controlled": f"controlled-root-{i:04}"}
            for i in range(129)
        ]
        self.check(p, "DELEGATIONS_SHAPE_OR_LIMIT_INVALID", False)

    def test_24_delegation_not_plain_list_rejected(self):
        p = proposal(); p["delegations"] = tuple()
        self.check(p, "DELEGATIONS_SHAPE_OR_LIMIT_INVALID", False)

    def test_25_bare_boolean_controller_rejected(self):
        p = proposal(); p["roles"]["executor"]["admin_controllers"] = [True]
        self.check(p, "ROLE_CONTROLLERS_INVALID:executor:admin_controllers", False)

    def test_26_duplicate_controller_claim_rejected(self):
        p = proposal(); p["roles"]["executor"]["admin_controllers"] = ["same-root-0001", "same-root-0001"]
        self.check(p, "ROLE_CONTROLLERS_INVALID:executor:admin_controllers", False)

    def test_27_empty_controllers_rejected(self):
        p = proposal(); p["roles"]["executor"]["recovery_controllers"] = []
        self.check(p, "ROLE_CONTROLLERS_INVALID:executor:recovery_controllers", False)

    def test_28_huge_controller_list_rejected(self):
        p = proposal(); p["roles"]["executor"]["deployment_controllers"] = [f"root-node-{i:04}" for i in range(17)]
        self.check(p, "ROLE_CONTROLLERS_INVALID:executor:deployment_controllers", False)

    def test_29_noncanonical_key_hex_rejected(self):
        p = proposal(); p["roles"]["executor"]["signer_fingerprint_sha256"] = "G"*64
        self.check(p, "SIGNER_FINGERPRINT_INVALID:executor", False)

    def test_30_malformed_account_identifier_rejected(self):
        p = proposal(); p["roles"]["executor"]["cloud_account_id"] = "!invalid"
        self.check(p, "ROLE_IDENTIFIER_INVALID:executor:cloud_account_id", False)

    def test_31_non_plain_role_dict_rejected(self):
        p = proposal()
        class TrickyDict(dict):
            def __getitem__(self, key): raise RuntimeError("executed")
        p["roles"]["executor"] = TrickyDict(p["roles"]["executor"])
        self.check(p, "ROLE_SHAPE_INVALID:executor", False)

    def test_32_non_plain_role_name_rejected(self):
        p = proposal(); p["roles"][1] = p["roles"].pop("executor")
        self.check(p, "ROLE_SET_INVALID", False)

    def test_33_non_plain_edge_mapping_rejected(self):
        p = proposal()
        class TrickyDict(dict):
            def __getitem__(self, key): raise RuntimeError("executed")
        p["delegations"] = [TrickyDict({"controller":"controller-root-01", "controlled":"controlled-root-01"})]
        self.check(p, "DELEGATION_EDGE_INVALID", False)

    def test_34_wrong_edge_types_rejected(self):
        p = proposal(); p["delegations"] = [{"controller": 1, "controlled": "controlled-root-01"}]
        self.check(p, "DELEGATION_EDGE_INVALID", False)

    def test_35_unreported_controls_cannot_be_distinguished(self):
        a = self.check(proposal(), consistent=True)
        b = self.check(deepcopy(proposal()), consistent=True)
        self.assertEqual(a, b)
        self.assertIs(a["administrative_independence_authenticated"], False)

    def test_36_no_delegate_graph_does_not_claim_nonce_custody(self):
        a = self.check(proposal(), consistent=True)
        self.assertIs(a["external_nonce_custody_authenticated"], False)
        self.assertIs(a["first_external_effect_allowed"], False)
        self.assertIs(a["automatic_retry_allowed"], False)

    def test_37_shared_billing_control_detected(self):
        p = proposal()
        p["roles"]["executor"]["billing_controllers"] = p["roles"]["readback_witness"]["billing_controllers"]
        self.check(p, "SHARED_DIRECT_OR_TRANSITIVE_CONTROL:executor:readback_witness", False)

    def test_38_billing_root_can_control_recovery_transitively(self):
        p = proposal()
        p["delegations"] = [{
            "controller": p["roles"]["executor"]["billing_controllers"][0],
            "controlled": p["roles"]["nonce_custodian"]["recovery_controllers"][0],
        }]
        self.check(p, "SHARED_DIRECT_OR_TRANSITIVE_CONTROL:executor:nonce_custodian", False)


if __name__ == "__main__":
    unittest.main()
