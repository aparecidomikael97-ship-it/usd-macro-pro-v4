"""CI-only CNG zero-flags red-team and user-interaction risk contract."""
from __future__ import annotations

import os
import secrets
import sys
import unittest
from unittest.mock import patch

import atlasquant_aion_native_cng_zero_flags_ci_feasibility_v1 as z
from test_atlasquant_aion_windows_native_cng_ksp_readonly_capability_v1 import FakeNCrypt


CI_ENV = {
    "GITHUB_ACTIONS": "true",
    "GITHUB_EVENT_NAME": "pull_request",
    "RUNNER_OS": "Windows",
    "GITHUB_REPOSITORY": "aparecidomikael97-ship-it/usd-macro-pro-v4",
}


class ZeroFlagsCIOnlyTests(unittest.TestCase):
    def run_fake(self, fake=None, env=None, osname="win32", nonce=None):
        if fake is None:
            fake = FakeNCrypt()
        if env is None:
            env = CI_ENV
        if nonce is None:
            nonce = "bd" * 32
        with patch.object(z.sys, "platform", osname), patch.dict(
            os.environ, env, clear=True
        ), patch.object(z, "_load_ncrypt", return_value=fake) as loader:
            result = z.probe_zero_flags_ci_feasibility_only(nonce)
        return result, fake, loader

    def all_false(self, result):
        self.assertIs(result["zero_flags_may_allow_provider_ui"], True)
        for key in (
            "ui_suppression_verified", "owner_pc_execution_authorized_by_code",
            "physical_host_safety_verified", "tpm_key_custody_verified",
            "private_key_created", "private_key_opened",
            "private_key_enrolled", "host_security_state_modified",
            "installer_authorized", "build_authorized",
            "deploy_authorized", "safe_to_resume",
        ):
            self.assertIs(result[key], False, key)

    def test_ci_mock_requests_exact_zero_flags_two_algorithms(self):
        result, fake, loader = self.run_fake()
        self.assertEqual(result["state"], z.STATUS)
        self.assertEqual(fake.open_calls, [(z.PROVIDER, 0)])
        self.assertEqual([(name,flags) for _,name,flags in fake.alg_calls], [
            ("ECDSA_P256", 0), ("ED25519", 0),
        ])
        self.assertEqual(fake.free_calls, [fake.handle])
        self.assertIs(result["provider_handle_released"], True)
        loader.assert_called_once()
        self.all_false(result)

    def test_even_both_advertised_remains_untrusted(self):
        result, _, _ = self.run_fake(FakeNCrypt(
            algorithm_status={"ECDSA_P256": 0, "ED25519": 0}))
        self.assertEqual(result["state"], z.STATUS)
        self.all_false(result)

    def test_owner_machine_environment_never_triggers_call(self):
        result, fake, loader = self.run_fake(env={})
        self.assertEqual(result["reason"], "DISPOSABLE_GITHUB_WINDOWS_PR_CI_REQUIRED")
        self.assertFalse(result["native_execution_attempted"])
        self.assertFalse(fake.open_calls)
        loader.assert_not_called()
        self.all_false(result)

    def test_action_var_missing_blocks(self):
        env = dict(CI_ENV)
        env.pop("GITHUB_ACTIONS")
        result, fake, loader = self.run_fake(env=env)
        self.assertEqual(result["state"], "BLOCKED")
        loader.assert_not_called()

    def test_wrong_event_blocks(self):
        env = dict(CI_ENV)
        env["GITHUB_EVENT_NAME"] = "workflow_dispatch"
        result, _, loader = self.run_fake(env=env)
        self.assertEqual(result["reason"], "DISPOSABLE_GITHUB_WINDOWS_PR_CI_REQUIRED")
        loader.assert_not_called()

    def test_push_event_blocks(self):
        env = dict(CI_ENV)
        env["GITHUB_EVENT_NAME"] = "push"
        result, _, loader = self.run_fake(env=env)
        self.assertEqual(result["state"], "BLOCKED")
        loader.assert_not_called()

    def test_wrong_repo_blocks(self):
        env = dict(CI_ENV)
        env["GITHUB_REPOSITORY"] = "attacker/host"
        result, _, loader = self.run_fake(env=env)
        self.assertEqual(result["reason"], "DISPOSABLE_GITHUB_WINDOWS_PR_CI_REQUIRED")
        loader.assert_not_called()

    def test_wrong_runner_os_blocks(self):
        env = dict(CI_ENV)
        env["RUNNER_OS"] = "Linux"
        result, _, loader = self.run_fake(env=env)
        self.assertEqual(result["state"], "BLOCKED")
        loader.assert_not_called()

    def test_native_nonwindows_blocks(self):
        result, _, loader = self.run_fake(osname="linux")
        self.assertEqual(result["state"], "BLOCKED")
        loader.assert_not_called()

    def test_invalid_nonce_does_not_load_native(self):
        for bad in ("", "1"*63, "G"*64, None, 0, "de"*33, True):
            with self.subTest(bad=bad):
                result, _, loader = self.run_fake(nonce=bad)
                self.assertEqual(result["reason"], "CHALLENGE_REQUIRED")
                loader.assert_not_called()
                self.all_false(result)

    def test_open_not_ready_blocks(self):
        result, fake, _ = self.run_fake(FakeNCrypt(open_status=0x80090030))
        self.assertEqual(result["reason"], "PROVIDER_OPEN_FAILED")
        self.assertEqual(result["open_status"]["reason"], "NTE_DEVICE_NOT_READY")
        self.assertFalse(fake.alg_calls)
        self.assertFalse(fake.free_calls)
        self.all_false(result)

    def test_query_bad_flags_still_inconclusive_even_zero_flags(self):
        result, fake, _ = self.run_fake(FakeNCrypt(algorithm_status={
            "ECDSA_P256": 0x80090009, "ED25519": 0x80090009}))
        self.assertEqual(result["reason"], "ALGORITHM_STATUS_INCONCLUSIVE")
        self.assertEqual(result["algorithm_statuses"]["ECDSA_P256"]["reason"],
                         "NTE_BAD_FLAGS")
        self.assertEqual(fake.free_calls, [fake.handle])
        self.all_false(result)

    def test_not_supported_is_not_tpm_absence(self):
        result, _, _ = self.run_fake(FakeNCrypt(algorithm_status={
            "ECDSA_P256": 0, "ED25519": 0x80090029}))
        self.assertEqual(result["state"], z.STATUS)
        self.assertEqual(
            result["algorithm_statuses"]["ED25519"]["classification"], "NOT_SUPPORTED")
        self.all_false(result)

    def test_invalid_handle_is_not_algorithm_absence(self):
        result, fake, _ = self.run_fake(FakeNCrypt(algorithm_status={
            "ECDSA_P256": 0x80090026, "ED25519": 0x80090026}))
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(fake.free_calls, [fake.handle])
        self.all_false(result)

    def test_open_exception_blocks(self):
        result, fake, _ = self.run_fake(FakeNCrypt(open_error=OSError("mock")))
        self.assertEqual(result["reason"], "PROVIDER_OPEN_EXCEPTION")
        self.assertFalse(fake.alg_calls)
        self.all_false(result)

    def test_null_open_handle_blocks(self):
        result, fake, _ = self.run_fake(FakeNCrypt(handle=0))
        self.assertEqual(result["reason"], "PROVIDER_OPEN_NULL_HANDLE")
        self.assertFalse(fake.free_calls)
        self.all_false(result)

    def test_native_query_exception_frees_handle(self):
        result, fake, _ = self.run_fake(FakeNCrypt(alg_error=OSError("mock")))
        self.assertEqual(result["reason"], "ALGORITHM_QUERY_EXCEPTION")
        self.assertEqual(fake.free_calls, [fake.handle])
        self.all_false(result)

    def test_native_free_error_blocks(self):
        result, fake, _ = self.run_fake(FakeNCrypt(free_status=0x80090026))
        self.assertEqual(result["reason"], "PROVIDER_HANDLE_RELEASE_UNCONFIRMED")
        self.assertIs(result["provider_handle_released"], False)
        self.all_false(result)

    def test_native_free_exception_blocks(self):
        result, fake, _ = self.run_fake(FakeNCrypt(free_error=OSError("mock")))
        self.assertEqual(result["reason"], "PROVIDER_HANDLE_RELEASE_UNCONFIRMED")
        self.all_false(result)

    def test_status_fields_immutable_trust_floor_on_normal_case(self):
        result, _, _ = self.run_fake()
        for value in (result["open_status"], result["free_status"],
                      *result["algorithm_statuses"].values()):
            self.assertRegex(value["status_hex"], "^0x[0-9A-F]{8}$")
        self.all_false(result)

    def test_ci_environment_is_not_identity_attestation(self):
        result, _, _ = self.run_fake()
        # Set by our mocked process env, not proof of hosting or identity.
        self.assertIs(result["owner_pc_execution_authorized_by_code"], False)
        self.assertIs(result["ui_suppression_verified"], False)
        self.all_false(result)

    def test_real_windows_ci_run_may_be_blocked_but_never_authorizes(self):
        if sys.platform != "win32" or not z._github_ci_only():
            self.skipTest("requires Windows GitHub pull-request runner")
        report = z.probe_zero_flags_ci_feasibility_only(secrets.token_hex(32))
        self.assertIn(report["state"], ("BLOCKED", z.STATUS))
        self.all_false(report)


if __name__ == "__main__":
    unittest.main()
