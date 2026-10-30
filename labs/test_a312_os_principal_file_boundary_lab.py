"""A312 LAB: real second-process OS identity and SQLite file-mode gaps."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from labs.a311_process_isolated_sqlite_lab import (
    DB_NAME, SCHEMA as A311_SCHEMA, create_fixture, run_lab_request,
)
from labs.a312_os_principal_file_boundary_lab import (
    SCHEMA, STATIC_BLOCKERS, TEST_TITLE, apply_fixture_private_modes,
    assess_production_writer_boundary, inspect_private_modes,
    probe_same_principal_file_bypass,
)


class A312RealOSBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Execute real process boundary once, avoid repeated subprocess churn.
        cls.observation = probe_same_principal_file_bypass()

    def assert_never_authorizes(self, result):
        self.assertEqual(result["schema"], SCHEMA)
        self.assertTrue(result["research_only"])
        self.assertTrue(result["synthetic_only"] if "synthetic_only" in result else True)
        self.assertFalse(result["separate_os_principal_attested"])
        self.assertFalse(result["os_writer_exclusivity_proven"])
        self.assertFalse(result["native_sqlite_vfs_fd_attested"])
        self.assertFalse(result["off_host_immutable_custody_attested"])
        self.assertFalse(result["semantic_exactly_once_attested"])
        self.assertFalse(result["real_external_ack_verified"])
        self.assertFalse(result["can_authorize_real_effect"])
        self.assertFalse(result["can_resume"])
        self.assertFalse(result["can_resend"])
        self.assertFalse(result["can_auto_retry"])
        self.assertEqual(result["automatic_retries"], 0)
        self.assertTrue(result["hard_no_go"])
        self.assertTrue(result["zero_auto_resend"])
        self.assertFalse(result["new_paid_services"])
        self.assertTrue(result["no_worker_deploy_provider_orders"])
        self.assertEqual(result["p0_homologated"], 0)

    def test_observed_second_real_os_process_can_write(self):
        data = self.observation
        self.assertEqual(data["status"], "SAME_ACCOUNT_WRITE_BYPASS_CONFIRMED")
        self.assertTrue(data["distinct_process_observed"])
        self.assertTrue(data["same_principal_direct_file_write_observed"])
        self.assertTrue(data["client_can_direct_write_same_os_account"])
        self.assert_never_authorizes(data)

    def test_posix_mode_0700_and_db_0600_not_sufficient(self):
        data = self.observation
        self.assertEqual(
            data["posix_private_modes_observed"], os.name == "posix"
        )
        self.assertTrue(data["same_principal_direct_file_write_observed"])
        if os.name == "posix":
            self.assertTrue(data["different_process_same_principal_observed"])
            self.assertEqual(data["os_mode_observation"]["directory_mode"], "0o700")
            self.assertEqual(data["os_mode_observation"]["db_mode"], "0o600")
        else:
            self.assertIsNone(data["os_mode_observation"]["db_mode"])
            self.assertFalse(data["windows_acl_audited"])
        self.assert_never_authorizes(data)

    def test_probe_not_a_real_separate_user_privilege_test(self):
        data = self.observation
        self.assertFalse(data["separate_os_principal_attested"])
        self.assertFalse(data["os_writer_exclusivity_proven"])
        self.assertIn("NO_INDEPENDENT_WRITER_OS_PRINCIPAL",
                      data["blocking_requirements"])

    def test_readiness_with_real_bypass_is_held(self):
        assessment = assess_production_writer_boundary(
            observation=self.observation
        )
        self.assertEqual(
            assessment["status"], "NOT_READY_INDEPENDENT_PRINCIPAL_REQUIRED"
        )
        self.assertIn("DIRECT_WRITER_BYPASS_OBSERVED",
                      assessment["blocking_requirements"])
        self.assert_never_authorizes(assessment)

    def test_spoofed_external_os_attestation_still_denied(self):
        forged = dict(self.observation,
                      separate_os_principal_attested=True,
                      os_writer_exclusivity_proven=True,
                      native_sqlite_vfs_fd_attested=True,
                      off_host_immutable_custody_attested=True,
                      p0_homologated=6,
                      can_authorize_real_effect=True)
        out = assess_production_writer_boundary(observation=forged)
        self.assert_never_authorizes(out)
        self.assertIn("DIRECT_WRITER_BYPASS_OBSERVED",
                      out["blocking_requirements"])

    def test_wrong_schema_is_refused(self):
        out = assess_production_writer_boundary(
            observation={"schema": "ATTACK", "can_resume": True}
        )
        self.assertIn("OBSERVATION_MISSING_OR_WRONG_SCHEMA",
                      out["blocking_requirements"])
        self.assert_never_authorizes(out)

    def test_invalid_observation_types_are_refused(self):
        for poison in (None, [], True, "authorized", 0, {}):
            with self.subTest(poison=repr(poison)):
                out = assess_production_writer_boundary(observation=poison)
                self.assert_never_authorizes(out)
                self.assertIn("OBSERVATION_MISSING_OR_WRONG_SCHEMA",
                              out["blocking_requirements"])

    def test_minimum_requirements_do_not_disappear(self):
        out = assess_production_writer_boundary(
            observation=self.observation
        )
        self.assertTrue(set(STATIC_BLOCKERS).issubset(
            set(out["blocking_requirements"])
        ))
        self.assertIn("NO_OFF_HOST_IMMUTABLE_CUSTODY",
                      out["blocking_requirements"])
        self.assert_never_authorizes(out)

    def test_posix_file_mode_is_metadata_not_native_sqlite_fd(self):
        obs = self.observation["os_mode_observation"]
        self.assertFalse(obs["identity_native_sqlite_fd_attested"])
        self.assertFalse(obs["windows_dacl_checked"])
        self.assert_never_authorizes(self.observation)

    def test_invalid_timeout_is_denied_before_fixture_creation(self):
        for bad in (None, True, -1, 0, 61, "15"):
            with self.subTest(value=repr(bad)):
                with self.assertRaises(ValueError):
                    probe_same_principal_file_bypass(timeout_seconds=bad)

    def test_a312_does_not_run_resident_service_or_provider(self):
        data = self.observation
        self.assertTrue(data["no_worker_deploy_provider_orders"])
        self.assertEqual(data["new_paid_services"], False)
        self.assert_never_authorizes(data)


class A312FilesystemMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="a311-lab-a312-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = create_fixture(self.temp.name)

    def build_synthetic_db(self):
        result = run_lab_request(self.root, {
            "schema": A311_SCHEMA,
            "action": "CREATE_SYNTHETIC_CONVERSATION",
            "request_id": "a312-test-setup",
            "title": "A311 TEST A312 isolated fixture",
        })
        self.assertEqual(result["status"], "LOCAL_ACKED", result)
        return self.root / DB_NAME

    def test_nonexistent_db_cannot_claim_private_mode(self):
        report = inspect_private_modes(self.root, self.root / DB_NAME)
        self.assertFalse(report["mode_bits_private"])
        self.assertFalse(report["db_is_regular"])
        self.assertFalse(report["identity_native_sqlite_fd_attested"])

    def test_wrong_db_path_never_accepted(self):
        self.build_synthetic_db()
        report = inspect_private_modes(self.root,
                                       self.root / "someone-elses.db")
        self.assertFalse(report["mode_bits_private"])
        self.assertFalse(report["db_is_regular"])

    def test_fixture_does_not_allow_permission_changes_without_db(self):
        with self.assertRaises(ValueError):
            apply_fixture_private_modes(self.root)

    def test_unmarked_fixture_cannot_be_prepared(self):
        self.build_synthetic_db()
        (self.root / ".a311-disposable-synthetic-only").unlink()
        with self.assertRaises(ValueError):
            apply_fixture_private_modes(self.root)

    def test_actual_posix_modes_are_observed_not_self_asserted(self):
        db = self.build_synthetic_db()
        altered = apply_fixture_private_modes(self.root)
        report = inspect_private_modes(self.root, db)
        if os.name == "posix":
            self.assertTrue(altered)
            self.assertTrue(report["mode_bits_private"])
            self.assertEqual(report["euid"],
                             report["db_owner_uid"])
            self.assertEqual(report["directory_mode"], "0o700")
            self.assertEqual(report["db_mode"], "0o600")
        else:
            self.assertFalse(altered)
            self.assertFalse(report["mode_bits_private"])
            self.assertIsNone(report["euid"])
            self.assertFalse(report["windows_dacl_checked"])

    @unittest.skipUnless(os.name == "posix", "POSIX permission modes only")
    def test_world_readable_directory_is_not_private(self):
        db = self.build_synthetic_db()
        apply_fixture_private_modes(self.root)
        self.root.chmod(0o755)
        report = inspect_private_modes(self.root, db)
        self.assertFalse(report["mode_bits_private"])
        self.assertEqual(report["directory_mode"], "0o755")

    @unittest.skipUnless(os.name == "posix", "POSIX permission modes only")
    def test_world_readable_database_is_not_private(self):
        db = self.build_synthetic_db()
        apply_fixture_private_modes(self.root)
        db.chmod(0o644)
        report = inspect_private_modes(self.root, db)
        self.assertFalse(report["mode_bits_private"])
        self.assertEqual(report["db_mode"], "0o644")

    @unittest.skipUnless(os.name == "posix", "POSIX symlink probe only")
    def test_symlinked_db_is_not_mistaken_for_private_file(self):
        db = self.build_synthetic_db()
        apply_fixture_private_modes(self.root)
        other = self.root / "not-the-opened-file.db"
        db.rename(other)
        try:
            db.symlink_to(other)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(str(exc))
        report = inspect_private_modes(self.root, db)
        self.assertFalse(report["db_is_regular"])
        self.assertFalse(report["mode_bits_private"])


if __name__ == "__main__":
    unittest.main()
