"""Adversarial synthetic-only localhost proof/readiness evaluator tests.

No Windows process, sockets, AppContainer profile, WFP filter or real probe.
"""
from __future__ import annotations

import copy
import inspect
import unittest

import atlasquant_aion_appcontainer_localhost_evidence_readiness_v1 as gate
from atlasquant_aion_windows_appcontainer_token_readonly_v1 import (
    evaluate_untrusted_token_readback,
)


def sample():
    profile = "AtlasQuantAIONProbe123456abcdef"
    token = evaluate_untrusted_token_readback(
        profile_name=profile, appcontainer_flag=True,
        sid_matches=True, capability_count=0, all_queries_succeeded=True,
    )
    return {
        "schema": gate.SCHEMA,
        "method": gate.METHOD,
        "probe_nonce": "ab"*32,
        "profile_name": profile,
        "expected_child_image_sha256": "sha256:"+"1"*64,
        "observed_child_image_sha256": "sha256:"+"1"*64,
        "token_readback": token,
        "normal_controls": {
            "before_nonce": "cd"*32,
            "after_nonce": "ef"*32,
            "before_reachable": True,
            "after_reachable": True,
            "before_witness_verified_independently": True,
            "after_witness_verified_independently": True,
        },
        "isolated_child": {
            "attempt_nonce": "ab"*32,
            "started": True,
            "completed": True,
            "connect_attempt_completed": True,
            "exit_code": 0,
            "connect_result": "OS_ACCESS_DENIED",
            "winsock_error_code": 10013,
            "stdout_nonce_correlated": True,
            "parent_received_probe_nonce": False,
            "token_checked_on_held_process_handle": True,
            "elapsed_ms": 700,
        },
        "cleanup": {
            "job_kill_on_close": True,
            "child_terminated": True,
            "process_handles_closed": True,
            "profile_deleted": True,
            "firewall_unchanged": True,
            "wfp_unchanged": True,
            "no_external_endpoint": True,
        },
    }


class ReadinessTests(unittest.TestCase):
    def verdict(self, obj):
        r=gate.review_untrusted_appcontainer_localhost_observation(obj)
        for name, value in gate.FALSE_GATES.items():
            self.assertIs(r[name],False,name)
        self.assertIs(r["physical_evidence_candidate_trusted"],False)
        self.assertIs(r["reference_data_only"],True)
        self.assertIs(r["single_ipv4_tcp_loopback_surface_only"],True)
        self.assertIs(r["separate_scoped_owner_approval_required"],True)
        self.assertIs(r["installer_authorized"],False)
        return r

    def test_complete_synthetic_receipt_is_still_untrusted(self):
        r=self.verdict(sample())
        self.assertEqual(r["state"],gate.CANDIDATE)
        self.assertFalse(r["network_deny_verified"])

    def test_cannot_prove_all_network_surfaces(self):
        r=self.verdict(sample())
        self.assertFalse(r["all_16_network_surfaces_verified"])
        self.assertFalse(r["physical_sandbox_12_of_12_verified"])

    def test_no_owner_pc_or_os_side_effect_in_pure_module(self):
        s=inspect.getsource(gate)
        for forbidden in ("ctypes.WinDLL(", "CreateAppContainerProfile(", "DeleteAppContainerProfile(",
                          "CreateProcessW(", "socket.socket(", "FwpmFilterAdd0(",
                          "subprocess.run(", "os.system(", "NCryptOpenKey("):
            self.assertNotIn(forbidden,s)
        self.verdict(sample())

    def test_non_mapping_observations_denied(self):
        for x in (None,False,True,[],{},123,"denied"):
            with self.subTest(x=x):
                self.assertEqual(self.verdict(x)["state"],"BLOCKED")

    def test_missing_or_extra_claims_denied(self):
        x=sample(); x["installer_authorized"]=True
        self.assertEqual(self.verdict(x)["reason"],"EXACT_OBSERVATION_SCHEMA_REQUIRED")
        for key in sample():
            x=sample(); x.pop(key)
            with self.subTest(key=key):
                self.assertEqual(self.verdict(x)["state"],"BLOCKED")

    def test_wrong_schema_and_method_denied(self):
        for key,value in (("schema","TRUSTED"),("method","WFP_CHILD_SCOPED_DYNAMIC_FILTERS"),
                          ("method","NORMAL_CI_CHILD_NOT_APPCONTAINER")):
            x=sample(); x[key]=value
            with self.subTest(key=key,value=value):
                self.assertEqual(self.verdict(x)["state"],"BLOCKED")

    def test_wrong_nonce_shape_denied(self):
        for value in (None,True,False,0,"A"*64,"0"*63,"g"*64,"ab"*33,["ab"*32]):
            x=sample(); x["probe_nonce"]=value
            with self.subTest(value=str(value)[:20]):
                self.assertEqual(self.verdict(x)["state"],"BLOCKED")

    def test_wrong_profile_name_denied(self):
        for value in ("AtlasQuantAIONProbe", "AtlasQuantAIONProbeABCDEF123456",
                      "AtlasQuantAIONProbe123456abcdef\\..","other123456abcdef",
                      "AtlasQuantAIONProbe12345","",False,None):
            x=sample(); x["profile_name"]=value
            with self.subTest(profile=str(value)):
                self.assertEqual(self.verdict(x)["state"],"BLOCKED")

    def test_image_hash_malformed_or_swapped_denied(self):
        for key in ("expected_child_image_sha256","observed_child_image_sha256"):
            for val in (None,True,"1"*64,"sha256:"+"G"*64,"sha256:"+"1"*63):
                x=sample(); x[key]=val
                with self.subTest(key=key,val=str(val)[:20]):
                    self.assertEqual(self.verdict(x)["reason"],"CHILD_IMAGE_DIGEST_INVALID")
        x=sample(); x["observed_child_image_sha256"]="sha256:"+"2"*64
        self.assertEqual(self.verdict(x)["reason"],"CHILD_IMAGE_MISMATCH_NOT_ATTESTATION")

    def test_bogus_token_schema_denied(self):
        x=sample(); x["token_readback"]["schema"]="EVIL"
        self.assertEqual(self.verdict(x)["state"],"BLOCKED")

    def test_missing_or_extra_token_field_denied(self):
        for key in sample()["token_readback"]:
            x=sample(); x["token_readback"].pop(key)
            with self.subTest(key=key):
                self.assertEqual(self.verdict(x)["reason"],"TOKEN_READBACK_SCHEMA_INVALID")
        x=sample(); x["token_readback"]["trusted_by_owner"]=True
        self.assertEqual(self.verdict(x)["state"],"BLOCKED")

    def test_normal_process_token_denied(self):
        x=sample()
        x["token_readback"]=evaluate_untrusted_token_readback(
            profile_name=x["profile_name"],appcontainer_flag=False,
            sid_matches=True,capability_count=0,all_queries_succeeded=True)
        self.assertEqual(self.verdict(x)["state"],"BLOCKED")

    def test_sid_mismatch_denied(self):
        x=sample(); x["token_readback"]=evaluate_untrusted_token_readback(
            profile_name=x["profile_name"],appcontainer_flag=True,
            sid_matches=False,capability_count=0,all_queries_succeeded=True)
        self.assertEqual(self.verdict(x)["state"],"BLOCKED")

    def test_extra_capability_denied(self):
        x=sample(); x["token_readback"]=evaluate_untrusted_token_readback(
            profile_name=x["profile_name"],appcontainer_flag=True,
            sid_matches=True,capability_count=1,all_queries_succeeded=True)
        self.assertEqual(self.verdict(x)["state"],"BLOCKED")

    def test_fake_physical_token_authority_denied(self):
        for key in ("physical_attestation_verified","real_host_identity_verified",
                    "process_handle_origin_verified","network_deny_verified",
                    "installer_authorized","build_authorized","deploy_authorized"):
            x=sample(); x["token_readback"][key]=True
            with self.subTest(flag=key):
                self.assertEqual(self.verdict(x)["state"],"BLOCKED")

    def test_boolean_zero_false_coercion_rejected_in_token(self):
        x=sample(); x["token_readback"]["capability_count"]=False
        self.assertEqual(self.verdict(x)["state"],"BLOCKED")

    def test_missing_or_extra_positive_controls_denied(self):
        for key in sample()["normal_controls"]:
            x=sample(); x["normal_controls"].pop(key)
            with self.subTest(key=key):
                self.assertEqual(self.verdict(x)["state"],"BLOCKED")
        x=sample(); x["normal_controls"]["network_deny_verified"]=True
        self.assertEqual(self.verdict(x)["state"],"BLOCKED")

    def test_missing_before_or_after_control_denied(self):
        for key in ("before_reachable","after_reachable",
                    "before_witness_verified_independently",
                    "after_witness_verified_independently"):
            x=sample(); x["normal_controls"][key]=False
            with self.subTest(key=key):
                self.assertEqual(self.verdict(x)["reason"],
                                 "POSITIVE_CONTROL_BEFORE_AFTER_REQUIRED")

    def test_boolean_coercions_rejected_in_controls(self):
        for key in ("before_reachable","after_reachable",
                    "before_witness_verified_independently",
                    "after_witness_verified_independently"):
            for val in (1,0,None,"true"):
                x=sample(); x["normal_controls"][key]=val
                with self.subTest(key=key,val=val):
                    self.assertEqual(self.verdict(x)["reason"],"CONTROL_BOOL_INVALID")

    def test_reused_control_challenges_denied(self):
        for a,b in (("before_nonce","after_nonce"),
                    ("before_nonce","probe_nonce"),
                    ("after_nonce","probe_nonce")):
            x=sample()
            if b=="probe_nonce":
                x["normal_controls"][a]=x["probe_nonce"]
            else:
                x["normal_controls"][a]=x["normal_controls"][b]
            with self.subTest(pair=(a,b)):
                self.assertEqual(self.verdict(x)["reason"],"REUSED_CONTROL_NONCE")

    def test_malformed_positive_control_nonce_denied(self):
        for k in ("before_nonce","after_nonce"):
            x=sample(); x["normal_controls"][k]="a"*65
            self.assertEqual(self.verdict(x)["reason"],"CONTROL_NONCE_INVALID")

    def test_missing_child_field_or_extra_authority_denied(self):
        for key in sample()["isolated_child"]:
            x=sample(); x["isolated_child"].pop(key)
            with self.subTest(key=key):
                self.assertEqual(self.verdict(x)["state"],"BLOCKED")
        x=sample(); x["isolated_child"]["physical_network_denial_verified"]=True
        self.assertEqual(self.verdict(x)["state"],"BLOCKED")

    def test_old_power_shell_timeout_stays_inconclusive(self):
        x=sample()
        x["isolated_child"]["completed"]=False
        x["isolated_child"]["connect_attempt_completed"]=False
        x["isolated_child"]["connect_result"]="TIMEOUT"
        x["isolated_child"]["elapsed_ms"]=8000
        self.assertEqual(self.verdict(x)["state"],"BLOCKED")

    def test_child_not_started_or_not_completed_denied(self):
        for key in ("started","completed","connect_attempt_completed",
                    "stdout_nonce_correlated","token_checked_on_held_process_handle"):
            x=sample(); x["isolated_child"][key]=False
            with self.subTest(key=key):
                self.assertEqual(self.verdict(x)["reason"],
                                 "STARTUP_TIMEOUT_OR_TOKEN_NOT_PROOF_OF_DENIAL")

    def test_reached_parent_listener_blocks(self):
        x=sample(); x["isolated_child"]["parent_received_probe_nonce"]=True
        self.assertEqual(self.verdict(x)["reason"],"PARENT_SAW_CHILD_NETWORK_ACCESS")

    def test_child_nonce_mismatch_blocks(self):
        x=sample(); x["isolated_child"]["attempt_nonce"]="ed"*32
        self.assertEqual(self.verdict(x)["reason"],"ISOLATED_NONCE_NOT_BOUND")

    def test_reported_connection_refused_not_network_deny(self):
        for result,error in (("OS_ACCESS_DENIED",10061),("NETWORK_ERROR",10013),
                             ("CONNECTED",0),("CONNECTION_REFUSED",10061),
                             ("TIMEOUT",None),("OS_ERROR",13)):
            with self.subTest(result=result,error=error):
                x=sample()
                x["isolated_child"]["connect_result"]=result
                x["isolated_child"]["winsock_error_code"]=error
                self.assertEqual(self.verdict(x)["state"],"BLOCKED")

    def test_unsupported_winerror_variant_denied(self):
        for value in (13,0,10035,10061,10060,-1,True,"10013",None):
            x=sample(); x["isolated_child"]["winsock_error_code"]=value
            with self.subTest(value=value):
                self.assertEqual(self.verdict(x)["state"],"BLOCKED")

    def test_failure_exit_is_not_network_deny(self):
        for value in (None,37,0xC0000022,True,"0",-1):
            x=sample(); x["isolated_child"]["exit_code"]=value
            with self.subTest(value=value):
                self.assertEqual(self.verdict(x)["state"],"BLOCKED")

    def test_probe_duration_bounds(self):
        for value in (-1,15001,None,True,"900",0.5):
            x=sample(); x["isolated_child"]["elapsed_ms"]=value
            with self.subTest(value=value):
                self.assertEqual(self.verdict(x)["reason"],"PROBE_DURATION_INVALID")

    def test_child_bool_types_strict(self):
        for key in ("started","completed","connect_attempt_completed",
                    "stdout_nonce_correlated","parent_received_probe_nonce",
                    "token_checked_on_held_process_handle"):
            x=sample(); x["isolated_child"][key]=1
            with self.subTest(key=key):
                self.assertEqual(self.verdict(x)["reason"],"CHILD_STATUS_BOOL_INVALID")

    def test_missing_cleanup_field_or_extra_flag_denied(self):
        for key in sample()["cleanup"]:
            x=sample(); x["cleanup"].pop(key)
            with self.subTest(key=key):
                self.assertEqual(self.verdict(x)["state"],"BLOCKED")
        x=sample(); x["cleanup"]["installer_authorized"]=True
        self.assertEqual(self.verdict(x)["state"],"BLOCKED")

    def test_failed_cleanup_blocked(self):
        for key in sample()["cleanup"]:
            x=sample(); x["cleanup"][key]=False
            with self.subTest(key=key):
                self.assertEqual(self.verdict(x)["reason"],
                                 "CLEANUP_OR_NO_HOST_CHANGE_NOT_CONFIRMED")

    def test_cleanup_boolean_coercion_blocked(self):
        for key in sample()["cleanup"]:
            x=sample(); x["cleanup"][key]=1
            with self.subTest(key=key):
                self.assertEqual(self.verdict(x)["reason"],"CLEANUP_BOOL_INVALID")

    def test_isolated_negative_on_one_surface_never_certifies_sixteen(self):
        x=sample()
        result=self.verdict(x)
        self.assertEqual(result["state"],gate.CANDIDATE)
        self.assertFalse(result["all_16_network_surfaces_verified"])

    def test_mutations_do_not_poison_sibling_observations(self):
        first=sample(); second=copy.deepcopy(first)
        first["isolated_child"]["connect_result"]="CONNECTED"
        self.assertEqual(self.verdict(first)["state"],"BLOCKED")
        self.assertEqual(self.verdict(second)["state"],gate.CANDIDATE)


if __name__=="__main__":
    unittest.main()
