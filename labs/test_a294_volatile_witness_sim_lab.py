"""A294 LAB tests: volatile same-host witness and hostile snapshot replacement."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from labs.a294_volatile_witness_sim_lab import (
    GENESIS, SCHEMA, VolatileWitnessClient, sqlite_semantic_digest,
    probe_witness_catches_closed_store_rollback,
    probe_sequence_and_receipt_tampering,
    probe_witness_reset_and_bootstrap_bypass, volatile_witness,
)
from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore


class A294WitnessRollbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = probe_witness_catches_closed_store_rollback()

    def test_anchor_accepts_latest_committed_snapshot(self):
        self.assertTrue(self.data["anchored"])
        self.assertTrue(self.data["prior_snapshot_verified"])

    def test_signed_witness_rejects_old_valid_sqlite_history(self):
        self.assertTrue(self.data["different_digest_after_host_rollback"])
        self.assertTrue(self.data["post_rollback_witness_denied"])

    def test_local_strict_sqlite_still_passes_rollback(self):
        self.assertTrue(self.data["local_strict_reopen_still_healthy"])
        self.assertTrue(self.data["local_messages_lost"])

    def test_simulated_witness_not_homologation(self):
        self.assertFalse(self.data["trusted_external_signer"])
        self.assertFalse(self.data["host_resistant_rollback_witness"])
        self.assertFalse(self.data["native_fd_authenticated"])
        self.assertEqual(self.data["p0_homologated"], 0)


class A294WitnessChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = probe_sequence_and_receipt_tampering()

    def test_initial_chain_and_second_explicit_anchor(self):
        self.assertTrue(self.data["first_anchor_accepted"])
        self.assertTrue(self.data["second_chain_anchor_accepted"])
        self.assertTrue(self.data["latest_receipt_verified"])

    def test_no_auto_replay_or_wrong_parent_accepted(self):
        self.assertTrue(self.data["replay_denied"])
        self.assertTrue(self.data["wrong_parent_denied"])
        self.assertTrue(self.data["new_history_requires_new_anchor"])

    def test_tampered_or_stale_receipt_fails_closed(self):
        self.assertTrue(self.data["forged_receipt_denied"])
        self.assertTrue(self.data["old_receipt_no_longer_current"])


class A294ResetNegativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = probe_witness_reset_and_bootstrap_bypass()

    def test_witness_process_failure_refuses_verification(self):
        self.assertTrue(self.data["initial_anchor"])
        self.assertTrue(self.data["killed_witness_denied"])

    def test_empty_witness_loses_previous_anchored_history(self):
        self.assertTrue(self.data["new_empty_witness_denied_old_receipt"])

    def test_untrusted_bootstrap_accepts_host_rollback(self):
        self.assertTrue(self.data["unsafe_reset_can_reanchor_old_history"])
        self.assertTrue(self.data["same_host_witness_is_not_trusted_custody"])


class A294WitnessProtocolTests(unittest.TestCase):
    def test_invalid_request_and_invalid_sequence_fail_closed(self):
        with volatile_witness() as witness:
            missing = witness.call(
                "verify", digest="a" * 64, receipt={}
            )
            invalid = witness.call(
                "anchor", seq=1, digest="not-a-hash", previous=GENESIS
            )
            out_of_order = witness.call(
                "anchor", seq=2, digest="a" * 64, previous=GENESIS
            )
            unsupported = witness.call("please-send-live-orders")
            self.assertEqual(missing["reason"], "WITNESS_UNINITIALIZED")
            self.assertEqual(invalid["reason"], "INVALID_ANCHOR")
            self.assertEqual(
                out_of_order["reason"], "NON_MONOTONIC_SEQUENCE"
            )
            self.assertEqual(
                unsupported["reason"], "UNSUPPORTED_OPERATION"
            )

    def test_client_denies_when_witness_no_longer_running(self):
        witness = VolatileWitnessClient()
        try:
            self.assertTrue(witness.active)
            witness._child.kill()
            witness._child.wait(timeout=5)
            self.assertFalse(witness.active)
            self.assertEqual(
                witness.call("verify", digest="b" * 64, receipt={})["reason"],
                "WITNESS_UNAVAILABLE",
            )
        finally:
            witness.close()

    def test_digest_stable_without_write_and_changes_with_row(self):
        with TemporaryDirectory(prefix="a294-digest-") as raw:
            path = Path(raw) / "chat.db"
            scope = Scope("o", "t", "w")
            store = SQLiteChatStore(path, strict_local_data_version=True)
            try:
                first = sqlite_semantic_digest(path)
                again = sqlite_semantic_digest(path)
                self.assertEqual(first, again)
                self.assertEqual(len(first), 64)
                store.create_conversation(scope, "synthetic")
                changed = sqlite_semantic_digest(path)
                self.assertNotEqual(first, changed)
            finally:
                store.close()

    def test_missing_database_is_not_silently_created(self):
        with TemporaryDirectory(prefix="a294-missing-") as raw:
            path = Path(raw) / "missing.db"
            with self.assertRaises(FileNotFoundError):
                sqlite_semantic_digest(path)
            self.assertFalse(path.exists())

    def test_strict_lab_meta_and_no_authorization(self):
        data = self.data if hasattr(self, "data") else probe_witness_catches_closed_store_rollback()
        self.assertEqual(data["schema"], SCHEMA)
        self.assertTrue(data["research_only"])
        self.assertTrue(data["disposable_sqlite_only"])
        self.assertTrue(data["same_host_not_independent"])
        self.assertTrue(data["volatile_no_durable_custody"])
        self.assertFalse(data["can_authorize_send"])
        self.assertTrue(data["provider_worker_deploy_orders_disabled"])
        self.assertTrue(data["zero_auto_resend"])
        self.assertEqual(data["p0_homologated"], 0)


if __name__ == "__main__":
    unittest.main()
