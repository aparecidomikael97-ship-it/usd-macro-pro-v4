"""Fail-closed Windows suspended child quarantine negative-case tests."""
from __future__ import annotations

from copy import deepcopy
import inspect
import os
import sys
import unittest
from unittest.mock import patch

from atlasquant_aion_windows_suspended_child_quarantine_contract_v1 import (
    SCHEMA, FIELDS, BLOCKED, SUCCESS_NEGATIVE,
    classify_quarantine_observation,
)
from atlasquant_aion_windows_suspended_child_quarantine_ci_v1 import (
    _ci_allowed, _fresh_observation, run_ci_suspended_child_negative_probe,
)


def fixture():
    record = _fresh_observation()
    for field in (
        "running_on_pr_ci",
        "child_created_suspended",
        "job_kill_on_close",
        "child_attached_to_job",
        "child_never_resumed",
        "termination_requested",
        "child_exit_observed",
        "canary_absent",
        "job_handle_closed",
        "child_handle_closed",
        "thread_handle_closed",
    ):
        record[field] = True
    record["token_reason"] = "TOKEN_NOT_APPCONTAINER"
    record["token_state"] = "NOT_VERIFIED"
    return record


class SuspendedChildQuarantineTests(unittest.TestCase):
    def assert_not_authorized(self, output):
        self.assertIs(output["appcontainer_identity_verified"], False)
        self.assertIs(output["network_deny_verified"], False)
        self.assertIs(output["physical_sandbox_verified"], False)
        self.assertIs(output["independent_attestation_verified"], False)
        self.assertIs(output["installer_authorized"], False)
        self.assertIs(output["build_authorized"], False)
        self.assertIs(output["deploy_authorized"], False)
        self.assertIs(output["safe_to_resume_appcontainer"], False)

    def test_positive_synthetic_negative_case_does_not_authorize(self):
        result = classify_quarantine_observation(fixture())
        self.assertEqual(result["state"], SUCCESS_NEGATIVE)
        self.assertTrue(result["normal_child_negative_case_passed"])
        self.assert_not_authorized(result)

    def test_empty_observation_blocked(self):
        out = classify_quarantine_observation({})
        self.assertEqual(out["state"], BLOCKED)
        self.assert_not_authorized(out)

    def test_non_exact_inputs_blocked(self):
        for value in (None, [], tuple(), True, 0, "OK"):
            with self.subTest(value=value):
                out = classify_quarantine_observation(value)
                self.assertEqual(out["state"], BLOCKED)
                self.assert_not_authorized(out)

    def test_added_install_claim_rejected(self):
        data = fixture()
        data["installer_authorized"] = True
        self.assertEqual(
            classify_quarantine_observation(data)["reason"],
            "EXACT_OBSERVATION_FIELDS_REQUIRED",
        )

    def test_added_network_deny_claim_rejected(self):
        data = fixture()
        data["network_deny_verified"] = True
        self.assertEqual(
            classify_quarantine_observation(data)["state"],
            BLOCKED,
        )

    def test_missing_fields_rejected(self):
        for field in FIELDS:
            with self.subTest(field=field):
                data = fixture()
                del data[field]
                self.assertEqual(
                    classify_quarantine_observation(data)["state"], BLOCKED,
                )

    def test_wrong_schema_blocked(self):
        data = fixture()
        data["schema"] = "OLD"
        self.assertEqual(
            classify_quarantine_observation(data)["reason"], "SCHEMA_MISMATCH",
        )

    def test_all_required_true_fail_closed_when_missing(self):
        positive_required = (
            "running_on_pr_ci",
            "child_created_suspended",
            "job_kill_on_close",
            "child_attached_to_job",
            "child_never_resumed",
            "termination_requested",
            "child_exit_observed",
            "canary_absent",
            "job_handle_closed",
            "child_handle_closed",
            "thread_handle_closed",
        )
        for field in positive_required:
            with self.subTest(field=field):
                data = fixture()
                data[field] = False
                out = classify_quarantine_observation(data)
                self.assertEqual(out["reason"], "QUARANTINE_OBSERVATION_INCOMPLETE")
                self.assert_not_authorized(out)

    def test_booleans_cannot_be_ints_or_strings(self):
        for field in FIELDS - {"schema", "token_reason", "token_state"}:
            for value in (0, 1, "true", [], None):
                with self.subTest(field=field, value=str(value)):
                    data = fixture()
                    data[field] = value
                    out = classify_quarantine_observation(data)
                    self.assertEqual(out["reason"], "BOOLEAN_FIELD_INVALID")

    def test_token_reason_must_be_exact_negative(self):
        for value in (
            "", None, True, [],
            "MATCHING_SID_AND_ZERO_CAPABILITIES_STILL_REQUIRE_INDEPENDENT_ATTESTATION",
            "TOKEN_APPCONTAINER_SID_MISSING",
            "TOKEN_CAPABILITIES_QUERY_FAILED",
            "UNEXPECTED", "TOKEN_IS_APPCONTAINER_QUERY_FAILED",
        ):
            with self.subTest(value=str(value)):
                data = fixture()
                data["token_reason"] = value
                self.assertEqual(classify_quarantine_observation(data)["state"], BLOCKED)

    def test_token_state_must_not_be_candidate(self):
        data = fixture()
        data["token_state"] = "NATIVE_TOKEN_IDENTITY_CANDIDATE_UNTRUSTED"
        out = classify_quarantine_observation(data)
        self.assertEqual(out["reason"], "REJECTED_NORMAL_PROCESS_TOKEN_EXPECTED")
        self.assert_not_authorized(out)

    def test_raw_attestation_claim_true_is_rejected(self):
        for field in (
            "token_physical_attestation_verified",
            "token_process_handle_origin_verified",
            "token_network_deny_verified",
        ):
            with self.subTest(field=field):
                data = fixture()
                data[field] = True
                out = classify_quarantine_observation(data)
                self.assertEqual(out["reason"], "UNTRUSTED_ATTESTATION_CLAIM")

    def test_all_claims_false_still_not_real_proof(self):
        out = classify_quarantine_observation(fixture())
        self.assertEqual(out["state"], SUCCESS_NEGATIVE)
        self.assert_not_authorized(out)

    def test_input_record_never_mutated(self):
        data = fixture()
        expected = deepcopy(data)
        classify_quarantine_observation(data)
        self.assertEqual(data, expected)

    def test_result_field_set_does_not_expose_process_identifiers(self):
        result = classify_quarantine_observation(fixture())
        self.assertEqual(
            set(result),
            {
                "schema", "state", "reason", "normal_child_negative_case_passed",
                "appcontainer_identity_verified", "network_deny_verified",
                "physical_sandbox_verified", "independent_attestation_verified",
                "installer_authorized", "build_authorized", "deploy_authorized",
                "safe_to_resume_appcontainer",
            },
        )
        self.assertNotIn("process_id", result)
        self.assertNotIn("sid", result)

    def test_fresh_observation_is_locked_by_default(self):
        output = classify_quarantine_observation(_fresh_observation())
        self.assertEqual(output["state"], BLOCKED)
        self.assert_not_authorized(output)

    def test_ci_guard_denies_windows_owner_computer_unless_pr_env(self):
        with patch.dict(
            os.environ, {
                "GITHUB_ACTIONS": "false",
                "GITHUB_EVENT_NAME": "local",
                "RUNNER_OS": "Windows",
                "GITHUB_RUN_ID": "",
            },
        ):
            self.assertFalse(_ci_allowed())

    def test_no_owner_pc_execution_when_ci_guard_rejects(self):
        with patch(
            "atlasquant_aion_windows_suspended_child_quarantine_ci_v1._ci_allowed",
            return_value=False,
        ):
            report = run_ci_suspended_child_negative_probe()
        self.assertFalse(report["observation"]["running_on_pr_ci"])
        self.assertFalse(report["observation"]["child_created_suspended"])
        self.assertEqual(report["classification"]["state"], BLOCKED)
        self.assert_not_authorized(report["classification"])

    def test_no_process_resume_api_in_native_launcher(self):
        source = inspect.getsource(run_ci_suspended_child_negative_probe)
        # Never resume ANY child, even a forged AppContainer-positive token.
        self.assertNotIn("ResumeThread", source)
        self.assertNotIn("NtResumeProcess", source)
        self.assertNotIn("CreateAppContainerProfile(", source)
        self.assertNotIn("FwpmFilterAdd0(", source)

    def test_no_network_imports_in_native_launcher(self):
        import ast
        from pathlib import Path
        import atlasquant_aion_windows_suspended_child_quarantine_ci_v1 as mod
        tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertNotIn("socket", [x.name for x in node.names])
                self.assertNotIn("requests", [x.name for x in node.names])

    def test_real_windows_ci_suspended_normal_child_blocked_and_cleaned(self):
        if sys.platform != "win32" or not _ci_allowed():
            self.skipTest("Runs ONLY on Windows GitHub PR CI")
        report = run_ci_suspended_child_negative_probe()
        observation = report["observation"]
        self.assertEqual(set(observation), FIELDS)
        self.assertEqual(report["classification"]["state"], SUCCESS_NEGATIVE, report)
        self.assertEqual(observation["token_reason"], "TOKEN_NOT_APPCONTAINER")
        self.assertTrue(observation["child_created_suspended"])
        self.assertTrue(observation["job_kill_on_close"])
        self.assertTrue(observation["child_attached_to_job"])
        self.assertTrue(observation["child_exit_observed"])
        self.assertTrue(observation["canary_absent"])
        self.assertTrue(observation["job_handle_closed"])
        self.assertTrue(observation["child_handle_closed"])
        self.assertTrue(observation["thread_handle_closed"])
        self.assertFalse(report["appcontainer_profile_created"])
        self.assertFalse(report["network_socket_opened"])
        self.assertFalse(report["firewall_or_wfp_changed"])
        self.assertFalse(report["production_binary_executed"])
        self.assertFalse(report["environment_inherited"])
        self.assert_not_authorized(report["classification"])

    def test_fake_claim_synthetic_case_cannot_approve_resume(self):
        data = fixture()
        result = classify_quarantine_observation(data)
        self.assertFalse(result["safe_to_resume_appcontainer"])
        self.assertFalse(result["physical_sandbox_verified"])
        self.assertFalse(result["appcontainer_identity_verified"])

    def test_report_still_not_credible_host_attestation(self):
        data = fixture()
        result = classify_quarantine_observation(data)
        self.assertFalse(result["independent_attestation_verified"])

    def test_no_hardcoded_installation_keys_accepted(self):
        with self.assertRaises(TypeError):
            classify_quarantine_observation(fixture(), installer_authorized=True)
