"""Adversarial CI tests, including one real 127.0.0.1 parent/child control."""
from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_aion_windows_loopback_observer_classifier_v1 import (
    SCHEMA, RESULT_SCHEMA, ENDPOINT, PROTOCOL, TOKEN_MODE,
    POTENTIAL_OS_DENY_ERROR_CODES, classify_localhost_receipt,
)
from atlasquant_aion_windows_loopback_ci_collector_v1 import (
    run_ci_localhost_observation,
)


def fixture():
    return {
        "schema": SCHEMA,
        "probe_run_id": "ab" * 16,
        "endpoint": ENDPOINT,
        "protocol": PROTOCOL,
        "port": 32000,
        "normal_control_reachable": True,
        "server_received_child_nonce": True,
        "child_started": True,
        "child_completed": True,
        "child_exit_code": 0,
        "child_reported_status": "CONNECTED",
        "child_reported_error_code": None,
        "child_nonce_matches": True,
        "child_token_mode": TOKEN_MODE,
        "elapsed_ms": 80,
    }


class LocalhostObserverSecurityTests(unittest.TestCase):
    def classify(self, changes=None):
        value=fixture()
        if changes:
            value.update(changes)
        return classify_localhost_receipt(value)

    def no_auth(self, result):
        self.assertEqual(result["schema"], RESULT_SCHEMA)
        for field in (
            "physical_network_denial_verified",
            "all_network_surfaces_verified",
            "appcontainer_token_verified",
            "installer_authorized",
            "build_authorized",
            "deployment_authorized",
        ):
            self.assertIs(result[field], False, field)

    def test_live_ci_normal_child_connection_witness(self):
        receipt, classified=run_ci_localhost_observation()
        self.assertEqual(receipt["endpoint"], "127.0.0.1")
        self.assertEqual(receipt["protocol"], "TCP_IPV4_LOOPBACK_ONLY")
        self.assertTrue(receipt["normal_control_reachable"])
        self.assertTrue(receipt["child_started"])
        self.assertTrue(receipt["child_completed"])
        self.assertEqual(receipt["child_exit_code"], 0)
        self.assertTrue(receipt["child_nonce_matches"])
        self.assertTrue(receipt["server_received_child_nonce"])
        self.assertEqual(receipt["child_reported_status"], "CONNECTED")
        self.assertEqual(classified["state"], "NETWORK_ACCESS_OBSERVED")
        self.no_auth(classified)

    def test_synthetic_success_witness_never_authorizes(self):
        result=self.classify()
        self.assertEqual(result["state"], "NETWORK_ACCESS_OBSERVED")
        self.no_auth(result)

    def test_deny_claim_while_server_saw_child_is_contradictory(self):
        result=self.classify({
            "child_reported_status": "OS_ERROR",
            "child_reported_error_code": 10013,
        })
        self.assertEqual(result["state"], "CONTRADICTORY")
        self.no_auth(result)

    def test_success_claim_without_server_witness_is_contradictory(self):
        result=self.classify({"server_received_child_nonce": False})
        self.assertEqual(result["state"], "CONTRADICTORY")
        self.no_auth(result)

    def test_access_denied_no_server_hit_is_untrusted_candidate(self):
        for code in sorted(POTENTIAL_OS_DENY_ERROR_CODES):
            with self.subTest(code=code):
                result=self.classify({
                    "server_received_child_nonce": False,
                    "child_reported_status": "OS_ERROR",
                    "child_reported_error_code": code,
                })
                self.assertEqual(result["state"], "UNTRUSTED_DENIAL_CANDIDATE")
                self.assertTrue(result["candidate_os_access_denial"])
                self.no_auth(result)

    def test_access_denied_no_parent_positive_control_inconclusive(self):
        result=self.classify({
            "normal_control_reachable": False,
            "server_received_child_nonce": False,
            "child_reported_status": "OS_ERROR",
            "child_reported_error_code": 10013,
        })
        self.assertEqual(result["state"], "INCONCLUSIVE")
        self.assertFalse(result["candidate_os_access_denial"])
        self.no_auth(result)

    def test_connection_refused_not_os_policy_deny(self):
        for code in (111, 10061, 10060, 110, 101, 10051):
            with self.subTest(code=code):
                result=self.classify({
                    "server_received_child_nonce": False,
                    "child_reported_status": "OS_ERROR",
                    "child_reported_error_code": code,
                })
                self.assertEqual(result["state"], "INCONCLUSIVE")
                self.no_auth(result)

    def test_process_timeout_is_never_deny_proof(self):
        result=self.classify({
            "server_received_child_nonce": False,
            "child_completed": False,
            "child_exit_code": None,
            "child_reported_status": "TIMEOUT",
            "child_nonce_matches": False,
        })
        self.assertEqual(result["state"], "INCONCLUSIVE")
        self.assertEqual(result["reason"], "CHILD_STARTUP_OR_TIMEOUT_NOT_NETWORK_DENIAL")
        self.no_auth(result)

    def test_even_completed_timeout_label_not_proof(self):
        result=self.classify({
            "server_received_child_nonce": False,
            "child_reported_status": "TIMEOUT",
        })
        self.assertEqual(result["state"], "INCONCLUSIVE")
        self.no_auth(result)

    def test_process_launch_failure_not_deny_proof(self):
        result=self.classify({
            "server_received_child_nonce": False,
            "child_started": False,
            "child_completed": False,
            "child_exit_code": None,
            "child_nonce_matches": False,
            "child_reported_status": "START_ERROR",
        })
        self.assertEqual(result["state"], "INCONCLUSIVE")
        self.no_auth(result)

    def test_nonzero_child_exit_is_not_network_deny(self):
        result=self.classify({
            "server_received_child_nonce": False,
            "child_reported_status": "OS_ERROR",
            "child_reported_error_code": 10013,
            "child_exit_code": 0xc0000022,
        })
        self.assertEqual(result["state"], "INCONCLUSIVE")
        self.assertFalse(result["candidate_os_access_denial"])
        self.no_auth(result)

    def test_challenge_mismatch_invalid(self):
        result=self.classify({"child_nonce_matches": False})
        self.assertEqual(result["state"], "INVALID")
        self.no_auth(result)

    def test_missing_normal_positive_control_inconclusive(self):
        result=self.classify({"normal_control_reachable": False})
        self.assertEqual(result["state"], "INCONCLUSIVE")
        self.no_auth(result)

    def test_untrusted_claim_boolean_rejected_as_extra_field(self):
        original=fixture()
        original["physical_network_denial_verified"]=True
        result=classify_localhost_receipt(original)
        self.assertEqual(result["state"], "INVALID")
        self.no_auth(result)

    def test_untrusted_claim_false_still_extra_field(self):
        original=fixture()
        original["physical_network_denial_verified"]=False
        result=classify_localhost_receipt(original)
        self.assertEqual(result["state"], "INVALID")
        self.no_auth(result)

    def test_child_appcontainer_claim_rejected(self):
        result=self.classify({"child_token_mode": "APPCONTAINER_VERIFIED_BY_CHILD"})
        self.assertEqual(result["state"], "INVALID")
        self.no_auth(result)

    def test_fake_external_ip_and_ipv6_rejected(self):
        for endpoint, proto in (
            ("8.8.8.8", PROTOCOL),
            ("localhost", PROTOCOL),
            ("::1", "TCP_IPV6"),
            ("127.0.0.1", "UDP_IPV4"),
        ):
            with self.subTest(endpoint=endpoint,proto=proto):
                result=self.classify({"endpoint": endpoint, "protocol": proto})
                self.assertEqual(result["state"], "INVALID")
                self.no_auth(result)

    def test_bad_port_types_rejected(self):
        for port in (None,True,False,"32000",0,80,65536,-1):
            with self.subTest(port=port):
                result=self.classify({"port":port})
                self.assertEqual(result["state"], "INVALID")
                self.no_auth(result)

    def test_bad_elapsed_window_rejected(self):
        for elapsed in (-1,15001,None,True,1.5,"40"):
            with self.subTest(elapsed=elapsed):
                result=self.classify({"elapsed_ms":elapsed})
                self.assertEqual(result["state"], "INVALID")
                self.no_auth(result)

    def test_bad_run_nonce_rejected(self):
        for token in (None,True,"short","x"*32,"AB"*16,"0"*33):
            with self.subTest(token=token):
                result=self.classify({"probe_run_id": token})
                self.assertEqual(result["state"], "INVALID")
                self.no_auth(result)

    def test_wrong_schema_rejected(self):
        self.assertEqual(self.classify({"schema":"OLD"})["state"],"INVALID")

    def test_missing_field_rejected(self):
        value=fixture();del value["child_exit_code"]
        self.assertEqual(classify_localhost_receipt(value)["state"],"INVALID")

    def test_unknown_field_rejected(self):
        value=fixture();value["admin_override"]=True
        self.assertEqual(classify_localhost_receipt(value)["state"],"INVALID")

    def test_nonmapping_inputs_rejected(self):
        for x in (None,True,0,[],(),"valid"):
            with self.subTest(x=x):
                result=classify_localhost_receipt(x)
                self.assertEqual(result["state"],"INVALID")
                self.no_auth(result)

    def test_boolean_observation_values_must_be_exact_bool(self):
        for key in (
            "normal_control_reachable", "server_received_child_nonce",
            "child_started", "child_completed", "child_nonce_matches",
        ):
            with self.subTest(key=key):
                result=self.classify({key:1})
                self.assertEqual(result["state"],"INVALID")
                self.no_auth(result)

    def test_child_status_unknown_or_unhashable_rejected(self):
        for status in (None,True,[],{},33,"ALLOWED_BY_OWNER"):
            with self.subTest(status=str(status)):
                result=self.classify({"child_reported_status":status})
                self.assertEqual(result["state"],"INVALID")
                self.no_auth(result)

    def test_error_code_wrong_type_rejected(self):
        for error in (True,False,"10013",[],{},-1,0x100000000):
            with self.subTest(error=str(error)):
                result=self.classify({"child_reported_error_code":error})
                self.assertEqual(result["state"],"INVALID")
                self.no_auth(result)

    def test_exit_code_wrong_type_rejected(self):
        for code in (True,False,"0",[],{},-1,0x100000000):
            with self.subTest(code=str(code)):
                result=self.classify({"child_exit_code":code})
                self.assertEqual(result["state"],"INVALID")
                self.no_auth(result)

    def test_started_but_not_completed_inconclusive(self):
        result=self.classify({"child_completed":False})
        self.assertEqual(result["state"],"INCONCLUSIVE")
        self.no_auth(result)

    def test_normal_child_does_not_promote_16_surface_network_denial(self):
        receipt,_=run_ci_localhost_observation()
        self.assertEqual(receipt["child_token_mode"],TOKEN_MODE)
        result=classify_localhost_receipt(receipt)
        self.assertFalse(result["all_network_surfaces_verified"])
        self.assertFalse(result["appcontainer_token_verified"])
        self.assertFalse(result["physical_network_denial_verified"])

    def test_receipt_not_mutated_by_verifier(self):
        before=fixture()
        after=deepcopy(before)
        classify_localhost_receipt(before)
        self.assertEqual(before,after)

    def test_every_conclusion_keeps_build_install_deploy_blocked(self):
        variants=(
            {}, {"server_received_child_nonce":False},
            {"server_received_child_nonce":False,"child_reported_status":"OS_ERROR","child_reported_error_code":10013},
            {"child_completed":False},
            {"child_nonce_matches":False},
            {"normal_control_reachable":False},
            {"child_exit_code":37},
        )
        for variant in variants:
            with self.subTest(variant=variant):
                self.no_auth(self.classify(variant))
