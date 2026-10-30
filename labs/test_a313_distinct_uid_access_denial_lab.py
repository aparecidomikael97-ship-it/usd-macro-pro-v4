"""A313 negative OS-principal identity tests. CI Ubuntu must prove real UID.

Windows deliberately does NOT infer SID/DACL behavior from Linux chmod.
All proof is limited to temporary CI SQLite and preexisting nobody account.
"""
import os
import unittest

from labs.a313_distinct_uid_access_denial_lab import (
    SCHEMA, LAB_P0_BLOCKERS, assess_operational_os_writer_readiness,
    probe_real_different_uid_fixture,
)


class A313RealDifferentUIDFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.observation = probe_real_different_uid_fixture()

    def assert_hard_no_go(self, value):
        self.assertEqual(value["schema"], SCHEMA)
        self.assertTrue(value["research_only"])
        self.assertTrue(value["synthetic_only"])
        self.assertFalse(value["windows_dacl_attested"])
        self.assertFalse(value["real_writer_account_deployed"])
        self.assertFalse(value["production_os_principal_isolation_proven"])
        self.assertFalse(value["exclusive_sqlite_writer_proven"])
        self.assertFalse(value["native_sqlite_fd_vfs_attested"])
        self.assertFalse(value["off_host_custody_proven"])
        self.assertFalse(value["independent_semantic_intent_ack_proven"])
        self.assertFalse(value["can_resume"])
        self.assertFalse(value["can_resend"])
        self.assertFalse(value["can_auto_retry"])
        self.assertFalse(value["can_authorize_real_effect"])
        self.assertEqual(value["automatic_retries"], 0)
        self.assertTrue(value["zero_auto_resend"])
        self.assertTrue(value["hard_no_go"])
        self.assertEqual(value["p0_homologated"], 0)
        self.assertFalse(value["new_paid_services"])
        self.assertTrue(value["no_worker_deploy_provider_operations"])

    def test_fixture_outcome_is_never_operational_proof(self):
        self.assert_hard_no_go(self.observation)

    def test_github_ubuntu_must_prove_distinct_uid_not_skip(self):
        if os.environ.get("A313_REQUIRE_DIFFERENT_UID") == "1":
            self.assertEqual(
                self.observation["status"],
                "DIFFERENT_UID_FIXTURE_DENIAL_OBSERVED",
                "CI Ubuntu must fail RED if sudo/nobody or Linux UID proof missing",
            )
            self.assertTrue(self.observation["real_two_uid_fixture_tested"])
            self.assertTrue(self.observation["synthetic_other_uid_denied"])
        else:
            self.assert_hard_no_go(self.observation)

    @unittest.skipUnless(os.name == "posix", "real UID tests are POSIX only")
    def test_restricted_directory_denies_other_uid_read_and_write(self):
        if self.observation["status"] != "DIFFERENT_UID_FIXTURE_DENIAL_OBSERVED":
            self.skipTest("different UID unavailable locally; CI enforces it")
        out = self.observation["restricted_result"]
        self.assertTrue(out["read_open_denied"])
        self.assertTrue(out["write_open_denied"])
        self.assertTrue(out["directory_list_denied"])
        self.assertEqual(out["mode"], "restricted")

    @unittest.skipUnless(os.name == "posix", "real UID tests are POSIX only")
    def test_successful_positive_control_disproves_fake_environment_failure(self):
        if self.observation["status"] != "DIFFERENT_UID_FIXTURE_DENIAL_OBSERVED":
            self.skipTest("different UID unavailable locally; CI enforces it")
        self.assertTrue(self.observation["public_read_control_passed"])
        self.assertTrue(self.observation["real_two_uid_fixture_tested"])
        self.assertTrue(self.observation["different_uid_observed"])

    @unittest.skipUnless(os.name == "posix", "real UID tests are POSIX only")
    def test_posix_observed_0700_0600_and_real_file_owner(self):
        if self.observation["status"] != "DIFFERENT_UID_FIXTURE_DENIAL_OBSERVED":
            self.skipTest("different UID unavailable locally; CI enforces it")
        m = self.observation["posix_mode_metadata"]
        self.assertTrue(m["mode_bits_private"])
        self.assertEqual(m["directory_mode"], "0o700")
        self.assertEqual(m["db_mode"], "0o600")
        self.assertEqual(m["db_owner_uid"], m["euid"])
        self.assertFalse(m["identity_native_sqlite_fd_attested"])

    @unittest.skipUnless(os.name == "posix", "real UID tests are POSIX only")
    def test_parent_same_writer_uid_still_can_open_database(self):
        if self.observation["status"] != "DIFFERENT_UID_FIXTURE_DENIAL_OBSERVED":
            self.skipTest("different UID unavailable locally; CI enforces it")
        self.assertTrue(self.observation["same_uid_caller_can_open_database"])
        self.assertFalse(
            self.observation["production_os_principal_isolation_proven"]
        )

    @unittest.skipUnless(os.name == "nt", "Windows DACL not tested on POSIX")
    def test_windows_is_explicitly_unattested_not_a_fake_pass(self):
        self.assertEqual(self.observation["status"],
                         "WINDOWS_DACL_SID_NOT_TESTED")
        self.assertFalse(self.observation["real_two_uid_fixture_tested"])
        self.assertFalse(self.observation["synthetic_other_uid_denied"])
        self.assertFalse(self.observation["windows_dacl_attested"])

    def test_no_account_is_created_or_operational_writer_started(self):
        self.assertFalse(self.observation["real_writer_account_deployed"])
        self.assertTrue(self.observation["no_worker_deploy_provider_operations"])
        self.assertFalse(self.observation["new_paid_services"])

    def test_assessment_is_always_hard_no_go(self):
        decision = assess_operational_os_writer_readiness(
            observation=self.observation
        )
        self.assertEqual(
            decision["status"], "HARD_NO_GO_OPERATIONAL_WRITER_NOT_ATTESTED"
        )
        self.assert_hard_no_go(decision)

    def test_spoofed_true_production_claims_never_promote(self):
        forged = dict(self.observation)
        forged.update({
            "real_writer_account_deployed": True,
            "production_os_principal_isolation_proven": True,
            "exclusive_sqlite_writer_proven": True,
            "native_sqlite_fd_vfs_attested": True,
            "off_host_custody_proven": True,
            "p0_homologated": 6,
            "hard_no_go": False,
            "can_resume": True,
            "can_resend": True,
            "can_authorize_real_effect": True,
        })
        decision = assess_operational_os_writer_readiness(observation=forged)
        self.assert_hard_no_go(decision)

    def test_wrong_schema_report_is_invalid(self):
        decision = assess_operational_os_writer_readiness(
            observation={"schema": "bogus", "p0_homologated": 6}
        )
        self.assertIn("A313_OBSERVATION_INVALID",
                      decision["blocking_requirements"])
        self.assert_hard_no_go(decision)

    def test_invalid_report_types_denied(self):
        for value in (None, [], 0, True, "privileged", {}):
            with self.subTest(input=repr(value)):
                decision = assess_operational_os_writer_readiness(
                    observation=value
                )
                self.assert_hard_no_go(decision)
                self.assertIn("A313_OBSERVATION_INVALID",
                              decision["blocking_requirements"])

    def test_no_static_p0_requirement_removed(self):
        decision = assess_operational_os_writer_readiness(
            observation=self.observation
        )
        self.assertTrue(set(LAB_P0_BLOCKERS).issubset(
            set(decision["blocking_requirements"])
        ))
        self.assertIn("WINDOWS_DACL_SID_NOT_AUDITED",
                      decision["blocking_requirements"])

    def test_bad_timeout_is_refused_without_subprocess(self):
        for value in (-1, 0, 61, None, True, "15", 1.5):
            with self.subTest(timeout=repr(value)):
                with self.assertRaises(ValueError):
                    probe_real_different_uid_fixture(
                        timeout_seconds=value
                    )

    def test_nonposix_does_not_self_certify(self):
        if os.name != "posix":
            self.assertFalse(self.observation["real_two_uid_fixture_tested"])
        self.assert_hard_no_go(self.observation)


if __name__ == "__main__":
    unittest.main()
