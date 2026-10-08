"""Negative tests for AION network-deny evidence: no real sockets/network/policy."""
from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_aion_windows_network_deny_evidence_gate_v1 import (
    SCHEMA, METHODS, SURFACES, BLOCKED, UNTRUSTED_CANDIDATE,
    network_denial_plan, assess_untrusted_network_candidate,
)


class NetworkDenialGateTests(unittest.TestCase):
    def setUp(self):
        self.all_denied = [
            {
                "surface": s,
                "normal_control": "REACHABLE",
                "isolated_observation": "BLOCKED_BY_OS",
            }
            for s in SURFACES
        ]

    def check_closed(self, report, reason=None):
        self.assertEqual(report["state"], BLOCKED)
        if reason is not None:
            self.assertEqual(report["reason"], reason)
        for flag in (
            "physical_proof_verified", "network_deny_verified",
            "build_authorized", "package_install_authorized",
            "deploy_authorized",
        ):
            self.assertIs(report[flag], False, flag)

    def assess(self, observations=None, method=None, claims=None):
        return assess_untrusted_network_candidate(
            self.all_denied if observations is None else observations,
            method=METHODS[0] if method is None else method, claims=claims,
        )

    def test_plan_does_not_activate_real_windows_resources(self):
        p=network_denial_plan()
        self.assertEqual(p["state"],"READY_FOR_CONTROLLED_NETWORK_DENY_PROBE_DESIGN_REVIEW")
        self.assertEqual(p["schema"],SCHEMA)
        self.assertFalse(p["profile_created"])
        self.assertFalse(p["wfp_filter_added"])
        self.assertFalse(p["network_probe_executed"])
        self.assertFalse(p["network_deny_verified"])
        self.assertFalse(p["build_authorized"])

    def test_plan_requires_parent_physical_proof(self):
        p=network_denial_plan()
        self.assertEqual(p["required_parent_contract"],"WINDOWS_NETWORK_DENY_PHYSICAL_PROOF_REQUIRED")

    def test_plan_matrix_has_exact_unique_surfaces(self):
        p=network_denial_plan()
        self.assertEqual([x["surface"] for x in p["surfaces"]],list(SURFACES))
        self.assertEqual(len(SURFACES),16)
        self.assertEqual(len(set(SURFACES)),16)

    def test_ipv4_and_ipv6_loopback_included(self):
        for family in ("IPV4","IPV6"):
            self.assertIn("TCP_LOOPBACK_"+family,SURFACES)
            self.assertIn("UDP_LOOPBACK_"+family,SURFACES)

    def test_dns_both_protocols_and_families_included(self):
        for proto in ("TCP","UDP"):
            for family in ("IPV4","IPV6"):
                self.assertIn("DNS_"+proto+"_"+family,SURFACES)

    def test_proxy_and_named_pipe_bypass_included(self):
        for name in ("HTTP_CONNECT_PROXY","SOCKS_PROXY","REMOTE_SMB_NAMED_PIPE","INHERITED_SOCKET_HANDLE"):
            self.assertIn(name,SURFACES)

    def test_methods_are_only_review_candidates(self):
        self.assertEqual(METHODS,(
            "APPCONTAINER_NO_NETWORK_CAPABILITIES",
            "WFP_CHILD_SCOPED_DYNAMIC_FILTERS",
        ))

    def test_completed_self_report_is_not_real_proof(self):
        x=self.assess()
        self.assertEqual(x["state"],UNTRUSTED_CANDIDATE)
        self.assertTrue(x["structurally_complete"])
        self.assertEqual(x["surfaces_checked"],16)
        self.assertFalse(x["network_deny_verified"])
        self.assertFalse(x["physical_proof_verified"])
        self.assertFalse(x["build_authorized"])
        self.assertFalse(x["package_install_authorized"])

    def test_completed_self_report_wfp_also_not_real_proof(self):
        x=self.assess(method=METHODS[1])
        self.assertEqual(x["state"],UNTRUSTED_CANDIDATE)
        self.assertFalse(x["network_deny_verified"])

    def test_empty_observations_blocked(self):
        self.check_closed(self.assess(observations=[]),"EXACT_SURFACE_COVERAGE_REQUIRED")

    def test_missing_one_surface_blocked(self):
        self.check_closed(self.assess(observations=self.all_denied[:-1]),"EXACT_SURFACE_COVERAGE_REQUIRED")

    def test_extra_surface_blocked(self):
        self.check_closed(self.assess(observations=self.all_denied + self.all_denied[:1]),"EXACT_SURFACE_COVERAGE_REQUIRED")

    def test_duplicate_surface_blocked(self):
        data=deepcopy(self.all_denied)
        data[1]["surface"]=data[0]["surface"]
        self.check_closed(self.assess(observations=data),"DUPLICATE_OR_UNKNOWN_SURFACE")

    def test_unknown_surface_blocked(self):
        data=deepcopy(self.all_denied)
        data[1]["surface"]="TOKEN_SAYS_TRUST_ME"
        self.check_closed(self.assess(observations=data),"DUPLICATE_OR_UNKNOWN_SURFACE")

    def test_unknown_method_blocked(self):
        for method in ("LOW_INTEGRITY_ONLY","CREATE_RESTRICTED_TOKEN","FIREWALL_DISABLE","NONE", "",42,True):
            with self.subTest(method=method):
                self.check_closed(self.assess(method=method),"UNAPPROVED_NETWORK_ISOLATION_METHOD")

    def test_any_allowed_surface_blocks_all_methods(self):
        for method in METHODS:
            for index,surface in enumerate(SURFACES):
                with self.subTest(method=method,surface=surface):
                    data=deepcopy(self.all_denied)
                    data[index]["isolated_observation"]="ALLOWED"
                    result=self.assess(observations=data,method=method)
                    self.check_closed(result,"ANY_ALLOWED_ERROR_OR_UNMEASURED_TRAFFIC_FAILS_CLOSED")
                    self.assertIn(surface,result["failing_surfaces"])

    def test_any_unmeasured_surface_blocks(self):
        for status in ("ERROR","NOT_RUN"):
            for i,surface in enumerate(SURFACES):
                with self.subTest(status=status,surface=surface):
                    data=deepcopy(self.all_denied)
                    data[i]["isolated_observation"]=status
                    self.check_closed(self.assess(observations=data),"ANY_ALLOWED_ERROR_OR_UNMEASURED_TRAFFIC_FAILS_CLOSED")

    def test_unreachable_normal_control_not_proof(self):
        for status in ("NOT_RUN","FAILED"):
            with self.subTest(status=status):
                data=deepcopy(self.all_denied)
                data[3]["normal_control"]=status
                x=self.assess(observations=data)
                self.check_closed(x,"INDEPENDENT_REACHABILITY_CONTROLS_REQUIRED")
                self.assertIn(SURFACES[3],x["failing_surfaces"])

    def test_unknown_normal_control_status_blocked(self):
        data=deepcopy(self.all_denied)
        data[0]["normal_control"]="SKIPPED_BY_DESIGN"
        self.check_closed(self.assess(observations=data),"UNKNOWN_POSITIVE_CONTROL")

    def test_unknown_isolated_status_blocked(self):
        data=deepcopy(self.all_denied)
        data[0]["isolated_observation"]="ALMOST_BLOCKED"
        self.check_closed(self.assess(observations=data),"UNKNOWN_ISOLATED_OBSERVATION")

    def test_unknown_record_field_blocked(self):
        data=deepcopy(self.all_denied)
        data[0]["safe"]=True
        self.check_closed(self.assess(observations=data),"OBSERVATION_RECORD_SHAPE_INVALID")

    def test_missing_record_field_blocked(self):
        data=deepcopy(self.all_denied)
        del data[0]["normal_control"]
        self.check_closed(self.assess(observations=data),"OBSERVATION_RECORD_SHAPE_INVALID")

    def test_non_dict_record_blocked(self):
        data=deepcopy(self.all_denied)
        data[4]="UNTRUSTED"
        self.check_closed(self.assess(observations=data),"OBSERVATION_RECORD_SHAPE_INVALID")

    def test_scalar_in_place_of_matrix_blocked(self):
        for v in (None,True,{},123,"BLOCKED"*16):
            with self.subTest(value=v):
                self.check_closed(self.assess(observations=v),"EXACT_SURFACE_COVERAGE_REQUIRED")

    def test_claim_physical_proof_true_is_rejected(self):
        self.check_closed(self.assess(claims={"physical_proof_verified":True}),"SELF_ASSERTED_VERIFICATION_FORBIDDEN")

    def test_claim_network_deny_false_still_rejected(self):
        self.check_closed(self.assess(claims={"network_deny_verified":False}),"SELF_ASSERTED_VERIFICATION_FORBIDDEN")

    def test_claim_build_authorized_rejected(self):
        self.check_closed(self.assess(claims={"build_authorized":True}),"SELF_ASSERTED_VERIFICATION_FORBIDDEN")

    def test_claim_independently_verified_rejected(self):
        self.check_closed(self.assess(claims={"independently_verified":True}),"SELF_ASSERTED_VERIFICATION_FORBIDDEN")

    def test_claim_unknown_flag_rejected(self):
        self.check_closed(self.assess(claims={"owner_approval":"self-signed"}),"UNRECOGNIZED_CALLER_CLAIMS")

    def test_claims_non_dict_rejected(self):
        self.check_closed(self.assess(claims=["all good"]),"CALLER_CLAIMS_INVALID")

    def test_boolean_observation_rejected(self):
        data=deepcopy(self.all_denied)
        data[1]["normal_control"]=True
        self.check_closed(self.assess(observations=data),"UNKNOWN_POSITIVE_CONTROL")

    def test_boolean_surface_rejected(self):
        data=deepcopy(self.all_denied)
        data[1]["surface"]=True
        self.check_closed(self.assess(observations=data),"DUPLICATE_OR_UNKNOWN_SURFACE")

    def test_multiple_failures_all_reported_in_contract_order(self):
        data=deepcopy(self.all_denied)
        data[2]["isolated_observation"]="ALLOWED"
        data[15]["isolated_observation"]="ERROR"
        x=self.assess(observations=data)
        self.check_closed(x)
        self.assertEqual(x["failing_surfaces"],[SURFACES[2],SURFACES[15]])

    def test_order_of_candidate_records_does_not_change_result(self):
        a=self.assess()
        b=self.assess(observations=list(reversed(self.all_denied)))
        self.assertEqual(a,b)

    def test_input_records_are_not_mutated(self):
        data=deepcopy(self.all_denied)
        self.assess(observations=data)
        self.assertEqual(data,self.all_denied)

    def test_every_response_never_authorizes_deploy(self):
        for x in (
            network_denial_plan(),
            self.assess(),
            self.assess(observations=[]),
            self.assess(claims={"build_authorized":True}),
        ):
            self.assertFalse(x["deploy_authorized"])
            self.assertFalse(x["network_deny_verified"])
