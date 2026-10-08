"""Windows GitHub-runner native read-only preflight tests. No owner device."""
import copy
import os
import unittest
from unittest.mock import patch

from atlasquant_aion_windows_native_readonly_preflight_v1 import (
    SCHEMA, OBSERVED, REVIEW_READY, BLOCKED, GUARD_REQUIRED, FIELDS,
    capture_ci_windows_native_observation, assess_ci_native_preflight,
    native_preflight_policy, _digest,
)

D = lambda v: "sha256:" + v * 64

class WindowsNativeReadOnlyPreflightV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.challenge = D("a")
        cls.policy = D("b")
        cls.source = D("c")
        cls.observation = capture_ci_windows_native_observation(
            challenge_digest=cls.challenge, policy_digest=cls.policy,
            verifier_source_digest=cls.source,
        )

    def review(self, observation=None, *, challenge=None, policy=None, source=None):
        return assess_ci_native_preflight(
            self.observation if observation is None else observation,
            expected_challenge_digest=self.challenge if challenge is None else challenge,
            expected_policy_digest=self.policy if policy is None else policy,
            expected_verifier_source_digest=self.source if source is None else source,
        )

    def altered(self, **changes):
        d = copy.deepcopy(self.observation)
        d.update(changes)
        return d

    def reseal(self, o):
        o["observation_digest"] = _digest({k: o.get(k) for k in FIELDS})
        return o

    def test_actual_ci_native_token_sid_acl_and_executable_are_observed(self):
        o = self.observation
        self.assertEqual(o["state"], OBSERVED)
        self.assertEqual(o["ci_platform"], "win32")
        self.assertEqual(o["ci_runner_os"], "Windows")
        self.assertEqual(o["observation_scope"], "EPHEMERAL_GITHUB_RUNNER_ONLY")
        self.assertTrue(o["process_image_exists"])
        self.assertTrue(o["runner_temp_within_policy"])
        self.assertGreater(o["boot_uptime_milliseconds"], 0)
        for field in ("token_user_sid_digest", "scratch_directory_owner_sid_digest",
                      "scratch_directory_acl_sddl_digest", "process_image_sha256"):
            self.assertTrue(o[field].startswith("sha256:"), field)
        self.assertFalse(o["human_owner_sid_verified"])
        self.assertFalse(o["aion_binary_or_signer_verified"])

    def test_native_review_shape_passes_without_trust(self):
        r = self.review()
        self.assertEqual(r["state"], REVIEW_READY, r)
        self.assertTrue(r["shape_verified_untrusted"])
        self.assertFalse(r["owner_device_or_aion_verified"])
        self.assertFalse(r["independent_attestation_trusted"])
        self.assertFalse(r["actual_reboot_proven"])
        self.assertFalse(r["aion_health_trusted"])

    def test_raw_sid_sddl_hostname_or_registry_content_not_returned(self):
        o = self.observation
        self.assertFalse(any(key in o for key in (
            "sid", "owner_sid", "sddl", "hostname", "username", "full_path",
            "startup_command", "startup_registry_value", "aion_binary_path",
            "raw_token", "windows_account",
        )))

    def test_missing_observation_blocks(self):
        self.assertEqual(self.review({})["state"], BLOCKED)
        self.assertEqual(self.review(None)["state"], REVIEW_READY)  # helper default
        self.assertEqual(assess_ci_native_preflight(
            None, expected_challenge_digest=self.challenge,
            expected_policy_digest=self.policy,
            expected_verifier_source_digest=self.source,
        )["state"], BLOCKED)

    def test_wrong_challenge_blocks_replay(self):
        self.assertEqual(self.review(challenge=D("d"))["state"], BLOCKED)

    def test_changed_challenge_and_reseal_still_blocks_expected(self):
        x = self.reseal(self.altered(challenge_digest=D("f")))
        self.assertEqual(self.review(x)["state"], BLOCKED)

    def test_changed_policy_blocks(self):
        self.assertEqual(self.review(policy=D("e"))["state"], BLOCKED)

    def test_changed_verifier_source_blocks(self):
        self.assertEqual(self.review(source=D("e"))["state"], BLOCKED)

    def test_tampered_owner_sid_digest_blocks(self):
        x = self.altered(token_user_sid_digest=D("e"))
        self.assertIn("OBSERVATION_DIGEST_MISMATCH", self.review(x)["blockers"])

    def test_missing_sid_and_resealed_evidence_blocks(self):
        x = self.reseal(self.altered(token_user_sid_digest=""))
        self.assertEqual(self.review(x)["state"], BLOCKED)

    def test_sddl_missing_and_resealed_blocks(self):
        x = self.reseal(self.altered(scratch_directory_acl_sddl_digest=""))
        self.assertEqual(self.review(x)["state"], BLOCKED)

    def test_empty_python_binary_hash_blocks(self):
        x = self.reseal(self.altered(process_image_sha256=""))
        self.assertEqual(self.review(x)["state"], BLOCKED)

    def test_missing_process_image_blocks(self):
        x = self.reseal(self.altered(process_image_exists=False))
        self.assertEqual(self.review(x)["state"], BLOCKED)

    def test_runner_temp_scope_mismatch_blocks(self):
        x = self.reseal(self.altered(runner_temp_within_policy=False))
        self.assertEqual(self.review(x)["state"], BLOCKED)

    def test_boot_uptime_is_not_reboot_proof(self):
        x = self.reseal(self.altered(boot_uptime_milliseconds=0))
        self.assertEqual(self.review(x)["state"], BLOCKED)
        r = self.review()
        self.assertFalse(r["actual_reboot_proven"])

    def test_boot_uptime_boolean_is_invalid(self):
        x = self.reseal(self.altered(boot_uptime_milliseconds=True))
        self.assertEqual(self.review(x)["state"], BLOCKED)

    def test_native_dacl_presence_is_not_effective_acl_proof(self):
        x = self.reseal(self.altered(scratch_directory_dacl_present="yes"))
        self.assertEqual(self.review(x)["state"], BLOCKED)
        self.assertFalse(self.observation["aion_owner_acl_verified"])

    def test_scratch_directory_owner_comparison_is_boolean(self):
        x = self.reseal(self.altered(token_matches_scratch_owner="true"))
        self.assertEqual(self.review(x)["state"], BLOCKED)

    def test_wrong_platform_blocks_even_when_resealed(self):
        x = self.reseal(self.altered(ci_platform="linux"))
        self.assertEqual(self.review(x)["state"], BLOCKED)

    def test_owner_device_scope_spoof_blocks(self):
        x = self.reseal(self.altered(observation_scope="HUMAN_OWNER_PC"))
        self.assertEqual(self.review(x)["state"], BLOCKED)

    def test_ci_run_key_status_is_only_visibility_not_valid_install(self):
        self.assertIn(self.observation["startup_run_key_status"],
                      ("ACCESSIBLE", "ABSENT", "DENIED"))
        self.assertIn(self.observation["aion_run_entry_status"],
                      ("ABSENT", "DENIED", "UNKNOWN", "PRESENT_UNVERIFIED"))
        self.assertFalse(self.observation["aion_startup_entry_verified"])

    def test_fake_startup_verified_promotion_blocks(self):
        x = self.altered(aion_startup_entry_verified=True)
        self.assertEqual(self.review(x)["state"], BLOCKED)

    def test_fake_owner_sid_verified_promotion_blocks(self):
        x = self.altered(human_owner_sid_verified=True)
        self.assertEqual(self.review(x)["state"], BLOCKED)

    def test_fake_health_or_installed_claim_blocks(self):
        for flag in ("aion_installed", "runtime_trusted_healthy",
                     "aion_runtime_health_verified", "trusted_attestation_issued",
                     "production_write_executed", "owner_pc_accessed"):
            self.assertEqual(self.review(self.altered(**{flag: True}))["state"],
                             BLOCKED, flag)

    def test_nonsha_policy_rejected(self):
        self.assertEqual(self.review(policy="sha256:"+"g"*64)["state"], BLOCKED)

    def test_guard_blocks_without_actions_context(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaisesRegex(RuntimeError, GUARD_REQUIRED):
                capture_ci_windows_native_observation(
                    challenge_digest=self.challenge, policy_digest=self.policy,
                    verifier_source_digest=self.source,
                )

    def test_guard_blocks_without_test_switch(self):
        with patch.dict(os.environ, {"AION_NATIVE_READONLY_PREFLIGHT": "0"}):
            with self.assertRaisesRegex(RuntimeError, GUARD_REQUIRED):
                capture_ci_windows_native_observation(
                    challenge_digest=self.challenge, policy_digest=self.policy,
                    verifier_source_digest=self.source,
                )

    def test_guard_blocks_non_pr_trigger(self):
        with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_dispatch"}):
            with self.assertRaisesRegex(RuntimeError, GUARD_REQUIRED):
                capture_ci_windows_native_observation(
                    challenge_digest=self.challenge, policy_digest=self.policy,
                    verifier_source_digest=self.source,
                )

    def test_guard_blocks_missing_runner_temp(self):
        with patch.dict(os.environ, {"RUNNER_TEMP": ""}):
            with self.assertRaisesRegex(RuntimeError, GUARD_REQUIRED):
                capture_ci_windows_native_observation(
                    challenge_digest=self.challenge, policy_digest=self.policy,
                    verifier_source_digest=self.source,
                )

    def test_policy_has_no_privileged_or_install_side_effect(self):
        p = native_preflight_policy()
        self.assertTrue(p["test_only"])
        self.assertTrue(p["native_windows_readonly_api_calls"])
        for key in ("physical_ci_disk_writes_performed", "owner_pc_read_or_written",
                    "human_owner_sid_verified", "aion_installed", "aion_binary_or_signer_verified",
                    "aion_startup_entry_verified", "aion_owner_acl_verified",
                    "independent_attestor_authenticated", "trusted_evidence_issued",
                    "owner_auth_consumed", "install_token_consumed",
                    "registry_modified", "acl_modified", "startup_modified",
                    "service_created", "package_installed", "deploy_executed",
                    "worker_activated"):
            self.assertFalse(p[key], key)

if __name__ == "__main__":
    unittest.main()
