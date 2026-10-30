"""A314 LAB: kernel SO_PEERCRED, real distinct Linux UID and one-shot IPC.

No operational AION account, persistent Worker, provider, deployment or
customer database; tests exclusively use disposable A311 TEST fixtures.
"""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from labs.a311_process_isolated_sqlite_lab import create_fixture
from labs.a314_cross_uid_sqlite_socket_lab import (
    BLOCKERS, INVALID_REQUEST, REQUEST, SCHEMA,
    _clean_fixture, _expected_nobody, assess_operational_writer,
    probe_cross_uid_ipc_fixture, result_base,
)


class A314ActualCrossUIDIPCTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.observation = probe_cross_uid_ipc_fixture()

    def assert_no_real_authority(self, r):
        self.assertEqual(r["schema"], SCHEMA)
        self.assertTrue(r["research_only"])
        self.assertTrue(r["synthetic_fixture_only"])
        self.assertFalse(r["operational_writer_separate_uid_deployed"])
        self.assertFalse(r["production_client_file_denial_proven"])
        self.assertFalse(r["windows_sid_dacl_pipe_attested"])
        self.assertFalse(r["native_sqlite_vfs_fd_attested"])
        self.assertFalse(r["independent_ledger_and_provider_ack"])
        self.assertFalse(r["replay_intent_dedup_proven"])
        self.assertFalse(r["can_resume"])
        self.assertFalse(r["can_resend"])
        self.assertFalse(r["can_auto_retry"])
        self.assertFalse(r["can_authorize_real_effect"])
        self.assertEqual(r["automatic_retries"], 0)
        self.assertTrue(r["zero_auto_resend"])
        self.assertTrue(r["hard_no_go"])
        self.assertEqual(r["p0_homologated"], 0)
        self.assertTrue(r["no_worker_deploy_provider_operations"])
        self.assertFalse(r["new_paid_services"])
        self.assertTrue(set(BLOCKERS).issubset(set(r["blocking_requirements"])))

    def test_always_hard_no_go(self):
        self.assert_no_real_authority(self.observation)

    def test_ci_linux_must_prove_actual_cross_uid_socket(self):
        if os.environ.get("A314_REQUIRE_CROSS_UID_SOCKET") == "1":
            self.assertEqual(
                self.observation["status"],
                "LAB_CROSS_UID_IPC_AND_LIMITS_OBSERVED",
                "A314 Linux proof missing: " + repr(self.observation),
            )
            self.assertTrue(self.observation[
                "distinct_uid_ipc_local_write_observed"
            ])
        else:
            self.assert_no_real_authority(self.observation)

    @unittest.skipUnless(os.name == "posix", "Linux SO_PEERCRED only")
    def test_linux_kernel_peer_uid_denies_runner_uid(self):
        self._require_lab_proof()
        wrong = self.observation["wrong_uid_response"]
        p = wrong["ipc_response"]
        self.assertEqual(p["status"], "PEER_UID_DENIED")
        self.assertFalse(p["kernel_peer_uid_checked"])
        self.assertEqual(wrong["uid"], os.geteuid())
        self.assertEqual(p["kernel_peer_uid"], os.geteuid())
        self.assertFalse(p["db_handle_transmitted"])

    @unittest.skipUnless(os.name == "posix", "Linux SO_PEERCRED only")
    def test_real_other_uid_can_use_restricted_ipc(self):
        self._require_lab_proof()
        valid = self.observation["valid_uid_response"]
        peer = valid["ipc_response"]
        self.assertEqual(peer["status"], "SYNTHETIC_LOCAL_ACK")
        self.assertTrue(peer["kernel_peer_uid_checked"])
        self.assertEqual(valid["uid"], _expected_nobody())
        self.assertEqual(peer["kernel_peer_uid"], _expected_nobody())
        self.assertFalse(peer["db_handle_transmitted"])
        self.assertNotEqual(peer["server_pid"], valid["pid"])

    @unittest.skipUnless(os.name == "posix", "Linux SO_PEERCRED only")
    def test_restricted_client_cannot_open_db_directly(self):
        self._require_lab_proof()
        self.assertTrue(self.observation[
            "restricted_client_direct_file_access_denied"
        ])
        for result in (
            self.observation["invalid_action_response"],
            self.observation["valid_uid_response"],
            self.observation["replay_response"],
        ):
            self.assertTrue(result["read_denied"])
            self.assertTrue(result["write_denied"])
            self.assertTrue(result["listdir_denied"])

    @unittest.skipUnless(os.name == "posix", "Linux SO_PEERCRED only")
    def test_other_uid_cannot_send_undeclared_deploy_command(self):
        self._require_lab_proof()
        p = self.observation["invalid_action_response"]["ipc_response"]
        self.assertEqual(p["status"], "REQUEST_DENIED")
        self.assertTrue(p["kernel_peer_uid_checked"])
        self.assertFalse(p["can_authorize_real_effect"])

    @unittest.skipUnless(os.name == "posix", "Linux SO_PEERCRED only")
    def test_duplicate_request_id_still_lacks_semantic_dedup(self):
        self._require_lab_proof()
        r = self.observation
        self.assertEqual(r["local_conversation_count"], 2)
        self.assertTrue(r["same_request_id_created_two_rows"])
        self.assertEqual(
            r["replay_response"]["ipc_response"]["status"],
            "SYNTHETIC_LOCAL_ACK",
        )
        self.assertFalse(r["replay_intent_dedup_proven"])
        self.assertFalse(r["can_resend"])

    @unittest.skipUnless(os.name == "posix", "Linux SO_PEERCRED only")
    def test_same_uid_owner_is_still_a_file_bypass(self):
        self._require_lab_proof()
        self.assertTrue(self.observation[
            "same_host_owner_can_bypass_filesystem"
        ])
        self.assertFalse(self.observation[
            "production_client_file_denial_proven"
        ])

    @unittest.skipUnless(os.name == "nt", "Windows DACL requires native test")
    def test_windows_dacl_and_named_pipe_explicitly_unattested(self):
        self.assertEqual(
            self.observation["status"],
            "WINDOWS_OR_LINUX_CREDENTIAL_TEST_UNAVAILABLE",
        )
        self.assertFalse(
            self.observation["peer_uid_checked_via_linux_kernel"]
        )
        self.assert_no_real_authority(self.observation)

    def test_invalid_timeout_denied_before_running_fixture(self):
        for value in (None, 0, 1, -1, True, 31, "15", []):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    probe_cross_uid_ipc_fixture(timeout_seconds=value)

    def test_same_thread_claims_do_not_grant_authority(self):
        source = dict(self.observation)
        source.update({
            "status": "OPERATIONAL_READY",
            "production_client_file_denial_proven": True,
            "operational_writer_separate_uid_deployed": True,
            "native_sqlite_vfs_fd_attested": True,
            "independent_ledger_and_provider_ack": True,
            "replay_intent_dedup_proven": True,
            "hard_no_go": False,
            "can_resume": True, "can_resend": True,
            "can_authorize_real_effect": True,
            "p0_homologated": 6,
        })
        assessed = assess_operational_writer(report=source)
        self.assert_no_real_authority(assessed)
        self.assertEqual(
            assessed["status"], "HARD_NO_GO_NO_OPERATIONAL_WRITER"
        )

    def test_unknown_schema_not_accepted_for_readiness(self):
        assessed = assess_operational_writer(
            report={"schema": "unrelated", "p0_homologated": 6}
        )
        self.assertIn("MISSING_VERIFIABLE_LAB_REPORT",
                      assessed["blocking_requirements"])
        self.assert_no_real_authority(assessed)

    def test_untrusted_types_never_authorize(self):
        for data in (None, [], True, 1, "GO", {}):
            with self.subTest(value=repr(data)):
                assessed = assess_operational_writer(report=data)
                self.assert_no_real_authority(assessed)

    def test_default_contract_never_claims_real_release(self):
        self.assert_no_real_authority(result_base("UNKNOWN"))
        self.assertNotEqual(REQUEST["action"], "DEPLOY")
        self.assertEqual(INVALID_REQUEST["action"], "DEPLOY")

    def test_requires_a_marked_disposable_fixture(self):
        with TemporaryDirectory(prefix="a311-lab-a314-") as temp:
            self.assertIsNone(_clean_fixture(temp))
            private = Path(temp) / "a311-lab-a314-private"
            private.mkdir()
            create_fixture(private)
            if os.name == "posix":
                self.assertIsNotNone(_clean_fixture(temp))
            else:
                # This POSIX-only helper must never claim socket/UID
                # authentication on Windows merely because a marker exists.
                self.assertIsNone(_clean_fixture(temp))
            (private / ".a311-disposable-synthetic-only").unlink()
            self.assertIsNone(_clean_fixture(temp))

    def _require_lab_proof(self):
        if self.observation["status"] != "LAB_CROSS_UID_IPC_AND_LIMITS_OBSERVED":
            self.skipTest("not a Linux kernel peer-UID proof on this host")


if __name__ == "__main__":
    unittest.main()
