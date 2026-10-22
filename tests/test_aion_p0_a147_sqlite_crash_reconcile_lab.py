"""A147 LAB crash boundaries: real SQLite, synthetic signatures and witness.

No external provider, order, send, deploy, Worker's execution, or real trust.
All synthetic witness stores are rollbackable. This is NOT P0 H0 homologation.
"""
import base64
from contextlib import closing
import os
from pathlib import Path
from unittest.mock import patch
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from aion_p0_a145_authenticated_checkpoint_lab import SignedCheckpoint, checkpoint_payload
from aion_p0_a145_checkpoint_verifier_lab import Checkpoint, canonical_history_digest
from aion_p0_a146_highwater_gate_lab import HighWater, SyntheticVolatileWitnessLAB
from aion_p0_a146_signed_highwater_lab import SignedHighWater, canonical_highwater_bytes
from aion_p0_a147_sqlite_crash_journal_lab import (
    DB_NAME, JournalUnavailable, SimulatedBeforeCommitCrash,
    SyntheticCrashJournalLAB,
)

ROOT = Path(__file__).resolve().parent.parent


def pub(private):
    return private.public_key().public_bytes(encoding=serialization.Encoding.Raw,
                                              format=serialization.PublicFormat.Raw)


class A147CrashReconciliationLAB(unittest.TestCase):
    def setUp(self):
        self.lab_env = patch.dict(os.environ, {"AION_LAB_MODE": "1"})
        self.lab_env.start()
        self.addCleanup(self.lab_env.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.local = self.root / "local_journal"
        self.local.mkdir()
        self.journal = SyntheticCrashJournalLAB.bootstrap_synthetic_lab(
            lab_dir=self.local, ledger_id="ledger-A"
        )
        self.cp_signer = Ed25519PrivateKey.generate()
        self.floor_signer = Ed25519PrivateKey.generate()
        self.cp_keys = {"checkpoint-key": pub(self.cp_signer)}
        self.floor_keys = {"highwater-key": pub(self.floor_signer)}
        self.floor_store = SyntheticVolatileWitnessLAB()
        self.floor_store.publish(self.anchor([]), expected_sequence=None)

    def anchor(self, events):
        return HighWater("ledger-A", len(events), canonical_history_digest(events))

    def cp(self, events):
        obj = Checkpoint("ledger-A", len(events), canonical_history_digest(events))
        signature = self.cp_signer.sign(checkpoint_payload(obj))
        return SignedCheckpoint(obj, "checkpoint-key",
                                base64.b64encode(signature).decode("ascii"))

    def floor(self, anchor):
        signature = self.floor_signer.sign(canonical_highwater_bytes(anchor))
        return SignedHighWater(anchor, "highwater-key",
                               base64.b64encode(signature).decode("ascii"))

    def floor_reader(self, ledger_id):
        return self.floor(self.floor_store.read(ledger_id))

    def reserve(self, intent="run_one"):
        return self.journal.reserve_local_uncertain(intent)

    def assess(self, *, events=None, cp=None, reader=None, cp_keys=None, floor_keys=None):
        events = self.journal.read_events() if events is None else events
        return self.journal.assess_restart(
            checkpoint_envelope=self.cp(events) if cp is None else cp,
            checkpoint_pinned_keys=self.cp_keys if cp_keys is None else cp_keys,
            highwater_pinned_keys=self.floor_keys if floor_keys is None else floor_keys,
            read_signed_highwater=self.floor_reader if reader is None else reader,
        )

    def witness_current(self):
        events = self.journal.read_events()
        anchor = self.anchor(events)
        old = self.floor_store.read("ledger-A")
        self.assertTrue(self.floor_store.publish(anchor, expected_sequence=old.sequence))
        return events

    def reopen(self):
        return SyntheticCrashJournalLAB(lab_dir=self.local, ledger_id="ledger-A")

    def assert_blocked(self, decision, contains=None):
        self.assertEqual(decision.verdict, "LAB_HARD_BLOCKED")
        self.assertFalse(decision.automatic_retry_allowed)
        self.assertFalse(decision.external_execution_allowed)
        if contains:
            self.assertIn(contains, decision.reason)

    def test_01_explicit_bootstrap_empty(self):
        self.assertEqual(self.journal.read_events(), [])

    def test_02_reopen_empty_does_not_auto_bootstrap(self):
        self.assertEqual(self.reopen().read_events(), [])

    def test_03_local_reservation_persists_across_restart(self):
        self.assertTrue(self.reserve())
        self.assertEqual(self.reopen().read_events(), [{"seq": 1, "intent": "run_one"}])

    def test_04_precommit_fault_rolls_back(self):
        with self.assertRaises(SimulatedBeforeCommitCrash):
            self.journal.reserve_local_uncertain("run_one", fault_before_commit=True)
        self.assertEqual(self.reopen().read_events(), [])

    def test_05_postcommit_before_witness_ack_blocks(self):
        self.assertTrue(self.reserve())
        self.assert_blocked(self.assess(), "unwitnessed_local_advance")

    def test_06_postcommit_and_witness_ack_still_quarantines(self):
        self.assertTrue(self.reserve())
        self.witness_current()
        dec = self.reopen().assess_restart(
            checkpoint_envelope=self.cp(self.journal.read_events()),
            checkpoint_pinned_keys=self.cp_keys,
            highwater_pinned_keys=self.floor_keys,
            read_signed_highwater=self.floor_reader,
        )
        self.assertEqual(dec.verdict, "LAB_QUARANTINE_MANUAL_REVIEW")
        self.assertEqual(dec.reason, "reserved_effect_unknown")
        self.assertFalse(dec.automatic_retry_allowed)
        self.assertFalse(dec.external_execution_allowed)

    def test_07_genesis_consistency_never_authorizes(self):
        dec = self.assess()
        self.assertEqual(dec.verdict, "LAB_QUARANTINE_MANUAL_REVIEW")
        self.assertEqual(dec.reason, "read_only_genesis_not_authorized")
        self.assertFalse(dec.external_execution_allowed)

    def test_08_duplicate_intent_no_second_write(self):
        self.assertTrue(self.reserve())
        self.assertFalse(self.reserve())
        self.assertEqual(len(self.reopen().read_events()), 1)

    def test_09_second_intent_blocked_while_first_uncertain(self):
        self.assertTrue(self.reserve())
        with self.assertRaisesRegex(JournalUnavailable, "unresolved_first_operation_blocks_new_intent"):
            self.reserve("run_two")
        self.assertEqual(self.reopen().read_events(),
                         [{"seq": 1, "intent": "run_one"}])

    def test_10_duplicate_after_process_reopen_denied(self):
        self.reserve()
        self.assertFalse(self.reopen().reserve_local_uncertain("run_one"))

    def test_11_witness_offline_blocks(self):
        self.reserve()
        self.floor_store.offline = True
        self.assert_blocked(self.assess(), "witness_unavailable")

    def test_12_missing_checkpoint_blocks(self):
        dec = self.journal.assess_restart(
            checkpoint_envelope=None,
            checkpoint_pinned_keys=self.cp_keys,
            highwater_pinned_keys=self.floor_keys,
            read_signed_highwater=self.floor_reader)
        self.assert_blocked(dec)

    def test_13_missing_pinned_checkpoint_key_blocks(self):
        self.assert_blocked(self.assess(cp_keys={}))

    def test_14_missing_pinned_floor_key_blocks(self):
        self.assert_blocked(self.assess(floor_keys={}), "missing_highwater_trust_anchor")

    def test_15_external_witness_ahead_of_local_old_history_blocks(self):
        self.reserve()
        self.witness_current()
        # Losing the local SQLite increment while the witness stays ahead.
        stale = self.root / "stale.sqlite"
        with closing(sqlite3.connect(stale)) as db:
            db.execute("CREATE TABLE dummy (x INTEGER)")
            db.commit()
        # Signed genesis vs newer high-water, even without simulating a DB swap.
        self.assert_blocked(self.assess(events=[], cp=self.cp([])), "history_sequence_mismatch")

    def test_16_signed_checkpoint_for_wrong_history_blocks(self):
        self.reserve()
        self.assert_blocked(self.assess(cp=self.cp([])), "history_sequence_mismatch")

    def test_17_floor_digest_tamper_blocks(self):
        self.reserve()
        self.witness_current()
        bad = SignedHighWater(HighWater("ledger-A", 1, "a"*64),
                              "highwater-key", self.floor(self.anchor(self.journal.read_events())).signature_b64)
        self.assert_blocked(self.assess(reader=lambda _: bad), "highwater_signature_mismatch")

    def test_18_forged_floor_signature_blocks(self):
        self.reserve()
        self.witness_current()
        genuine = self.floor(self.floor_store.read("ledger-A"))
        tampered = SignedHighWater(genuine.anchor, "highwater-key",
                                  base64.b64encode(b"0" * 64).decode("ascii"))
        self.assert_blocked(self.assess(reader=lambda _: tampered), "highwater_signature_mismatch")

    def test_19_deleted_sqlite_never_recreated(self):
        self.journal.path.unlink()
        with self.assertRaises(JournalUnavailable):
            self.reopen()
        self.assertFalse(self.journal.path.exists())

    def test_20_missing_sqlite_blocks_restart_assessment(self):
        self.journal.path.unlink()
        self.assert_blocked(self.assess(events=[]), "missing_or_linked_journal")

    def test_21_existing_bootstrap_forbidden(self):
        with self.assertRaisesRegex(JournalUnavailable, "existing_journal_bootstrap_forbidden"):
            SyntheticCrashJournalLAB.bootstrap_synthetic_lab(lab_dir=self.local, ledger_id="ledger-A")

    def test_22_policy_delete_no_silent_repair(self):
        with closing(sqlite3.connect(self.journal.path)) as db:
            db.execute("DELETE FROM ledger_meta")
            db.commit()
        with self.assertRaisesRegex(JournalUnavailable, "ledger_identity_or_policy_changed"):
            self.reopen()

    def test_23_schema_trigger_added_denies_reopen(self):
        with closing(sqlite3.connect(self.journal.path)) as db:
            db.execute("CREATE TRIGGER surprise AFTER INSERT ON events BEGIN SELECT 1; END")
            db.commit()
        with self.assertRaisesRegex(JournalUnavailable, "unexpected_schema_objects"):
            self.reopen()

    def test_24_foreign_application_id_denies_reopen(self):
        with closing(sqlite3.connect(self.journal.path)) as db:
            db.execute("PRAGMA application_id=1000")
            db.commit()
        with self.assertRaisesRegex(JournalUnavailable, "foreign_application_id"):
            self.reopen()

    def test_25_altered_intent_denies_historically_signed_receipt(self):
        self.reserve()
        self.witness_current()
        cp = self.cp(self.journal.read_events())
        with closing(sqlite3.connect(self.journal.path)) as db:
            db.execute("UPDATE events SET intent='tampered' WHERE seq=1")
            db.commit()
        self.assert_blocked(self.assess(cp=cp), "history_digest_mismatch")

    def test_26_duplicate_concurrent_writer_one_reservation_only(self):
        outcome = []
        def worker():
            try:
                outcome.append(self.reopen().reserve_local_uncertain("same_run"))
            except Exception as exc:
                outcome.append(type(exc).__name__)
        tasks = [threading.Thread(target=worker) for _ in range(2)]
        for task in tasks: task.start()
        for task in tasks: task.join()
        self.assertEqual(sorted(outcome), [False, True])
        self.assertEqual(len(self.reopen().read_events()), 1)

    def test_27_concurrent_distinct_writer_only_one_admitted(self):
        outcome = []
        def worker(intent):
            try:
                outcome.append("accepted" if self.reopen().reserve_local_uncertain(intent) else "duplicate")
            except JournalUnavailable as exc:
                outcome.append(str(exc))
        tasks = [threading.Thread(target=worker, args=(s,)) for s in ("run_a", "run_b")]
        for task in tasks: task.start()
        for task in tasks: task.join()
        self.assertEqual(sorted(outcome), ["accepted", "unresolved_first_operation_blocks_new_intent"])
        events = self.reopen().read_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["seq"], 1)

    def test_28_real_child_process_crash_after_commit_survives(self):
        code = (
            "import os; "
            "from aion_p0_a147_sqlite_crash_journal_lab import SyntheticCrashJournalLAB; "
            f"SyntheticCrashJournalLAB(lab_dir={str(self.local)!r},ledger_id='ledger-A')"
            ".reserve_local_uncertain('child_committed'); "
            "os._exit(37)"
        )
        result = subprocess.run([sys.executable, "-B", "-c", code],
                                cwd=ROOT, env=dict(os.environ), capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 37, result.stderr)
        self.assertEqual(self.reopen().read_events(), [{"seq":1,"intent":"child_committed"}])
        self.assert_blocked(self.assess(), "unwitnessed_local_advance")

    def test_29_real_child_process_crash_before_commit_rolls_back(self):
        code = (
            "import sqlite3,os; "
            f"db=sqlite3.connect({str(self.journal.path)!r}); "
            "db.execute('BEGIN IMMEDIATE'); "
            "db.execute(\"INSERT INTO events(seq,intent,state) VALUES (1,'child_uncommitted','RESERVED_UNCERTAIN')\"); "
            "os._exit(39)"
        )
        result = subprocess.run([sys.executable, "-B", "-c", code],
                                cwd=ROOT, env=dict(os.environ), capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 39, result.stderr)
        self.assertEqual(self.reopen().read_events(), [])

    def test_30_database_swap_old_snapshot_with_witness_ahead_blocks(self):
        old = self.root / "old_state.sqlite"
        shutil.copyfile(self.journal.path, old)  # no open DB connections
        self.reserve()
        self.witness_current()
        shutil.copyfile(old, self.journal.path)
        dec = self.assess()
        self.assert_blocked(dec, "signed_checkpoint_rollback")

    def test_31_negative_double_rollback_still_looks_consistent(self):
        old = self.root / "old_state.sqlite"
        shutil.copyfile(self.journal.path, old)
        self.reserve()
        self.witness_current()
        shutil.copyfile(old, self.journal.path)
        # NEGATIVE EVIDENCE: independently trusted high-water still absent.
        reset = SyntheticVolatileWitnessLAB()
        reset.publish(self.anchor([]), expected_sequence=None)
        decision = self.assess(reader=lambda ledger: self.floor(reset.read(ledger)))
        self.assertEqual(decision.verdict, "LAB_QUARANTINE_MANUAL_REVIEW")
        self.assertFalse(decision.external_execution_allowed)

    def test_32_bad_intent_rejected_before_write(self):
        with self.assertRaisesRegex(JournalUnavailable, "invalid_intent"):
            self.reserve("../escape")
        self.assertEqual(self.journal.read_events(), [])

    def test_33_without_lab_flag_fails_closed(self):
        with patch.dict(os.environ, {"AION_LAB_MODE": "0"}):
            with self.assertRaisesRegex(JournalUnavailable, "lab_mode_required"):
                self.reopen()

    def test_34_lost_client_ack_is_not_permission_to_resend(self):
        self.assertTrue(self.reserve("ack_lost"))
        # Client failed after a successful local commit; the restart sees intent.
        self.assertFalse(self.reopen().reserve_local_uncertain("ack_lost"))
        self.assert_blocked(self.assess(), "unwitnessed_local_advance")

    def test_35_witness_reader_error_converts_to_block(self):
        self.reserve()
        def fail(_):
            raise OSError("injected network failure (synthetic only)")
        self.assert_blocked(self.assess(reader=fail), "witness_read_failed")

    def test_36_policy_identity_changed_denies_open(self):
        with closing(sqlite3.connect(self.journal.path)) as db:
            db.execute("UPDATE ledger_meta SET ledger_id='ledger-B'")
            db.commit()
        with self.assertRaisesRegex(JournalUnavailable, "ledger_identity_or_policy_changed"):
            self.reopen()

    def test_37_not_a_real_provider_effect_proof(self):
        self.reserve()
        self.witness_current()
        decision = self.assess()
        self.assertEqual(decision.verdict, "LAB_QUARANTINE_MANUAL_REVIEW")
        self.assertEqual(decision.reason, "reserved_effect_unknown")
        self.assertFalse(decision.automatic_retry_allowed)

    def test_38_empty_restore_without_signed_checkpoint_denied(self):
        self.assert_blocked(self.journal.assess_restart(
            checkpoint_envelope=None, checkpoint_pinned_keys=self.cp_keys,
            highwater_pinned_keys=self.floor_keys,
            read_signed_highwater=self.floor_reader))

    def test_39_run_id_is_not_duplicated_if_witness_offline(self):
        self.reserve("only_once")
        self.floor_store.offline = True
        self.assertFalse(self.reopen().reserve_local_uncertain("only_once"))
        self.assertEqual(len(self.reopen().read_events()), 1)

    def test_40_reopen_with_foreign_ledger_identity_denied(self):
        with self.assertRaisesRegex(JournalUnavailable, "ledger_identity_or_policy_changed"):
            SyntheticCrashJournalLAB(lab_dir=self.local, ledger_id="ledger-B")


    def test_41_run_mode_disabled_after_open_denies_new_write(self):
        with patch.dict(os.environ, {"AION_LAB_MODE": "0"}):
            with self.assertRaisesRegex(JournalUnavailable, "lab_mode_required"):
                self.reserve()
        self.assertEqual(self.journal.read_events(), [])

    def test_42_run_mode_disabled_after_open_denies_read(self):
        with patch.dict(os.environ, {"AION_LAB_MODE": "0"}):
            with self.assertRaisesRegex(JournalUnavailable, "lab_mode_required"):
                self.journal.read_events()

    def test_43_unresolved_first_operation_blocks_second_after_reopen(self):
        self.assertTrue(self.reserve("first"))
        with self.assertRaisesRegex(JournalUnavailable, "unresolved_first_operation_blocks_new_intent"):
            self.reopen().reserve_local_uncertain("second")
        self.assertEqual(len(self.journal.read_events()), 1)

    def test_44_matching_signed_highwater_does_not_allow_new_intent(self):
        self.assertTrue(self.reserve("first"))
        self.witness_current()
        self.assertEqual(self.assess().verdict, "LAB_QUARANTINE_MANUAL_REVIEW")
        with self.assertRaisesRegex(JournalUnavailable, "unresolved_first_operation_blocks_new_intent"):
            self.reserve("second")

    def test_45_witness_offline_does_not_allow_new_intent(self):
        self.assertTrue(self.reserve("first"))
        self.floor_store.offline = True
        self.assert_blocked(self.assess())
        with self.assertRaisesRegex(JournalUnavailable, "unresolved_first_operation_blocks_new_intent"):
            self.reserve("second")

    def test_46_negative_deleted_database_explicit_rebootstrap_erases_local_history(self):
        # NEGATIVE EVIDENCE: synthetic genesis is not protected by independent
        # custody. A missing file can be manually re-created with the same ID.
        self.assertTrue(self.reserve("before_reset"))
        self.journal.path.unlink()
        fresh = SyntheticCrashJournalLAB.bootstrap_synthetic_lab(
            lab_dir=self.local, ledger_id="ledger-A"
        )
        self.assertEqual(fresh.read_events(), [])
        self.assertFalse(self.floor_store.offline)
        # The still-current high-water catches the loss; if the witness is also
        # reset or rolled back, A146's negative proof remains relevant.
        decision = fresh.assess_restart(
            checkpoint_envelope=self.cp([]),
            checkpoint_pinned_keys=self.cp_keys,
            highwater_pinned_keys=self.floor_keys,
            read_signed_highwater=self.floor_reader,
        )
        self.assertEqual(decision.verdict, "LAB_QUARANTINE_MANUAL_REVIEW")
        self.assertFalse(decision.external_execution_allowed)

    def test_47_precommit_crash_does_not_create_a_pending_reservation(self):
        with self.assertRaises(SimulatedBeforeCommitCrash):
            self.journal.reserve_local_uncertain("before_commit", fault_before_commit=True)
        self.assertTrue(self.reserve("later_allowed_synthetic"))
        self.assertEqual(self.reopen().read_events(), [{"seq":1,"intent":"later_allowed_synthetic"}])

    def test_48_extra_index_rejected_without_repair(self):
        with closing(sqlite3.connect(self.journal.path)) as db:
            db.execute("CREATE INDEX extra_state_index ON events(state)")
            db.commit()
        with self.assertRaisesRegex(JournalUnavailable, "unexpected_schema_objects"):
            self.reopen()

    def test_49_external_effect_remains_unproven_after_valid_commit(self):
        self.assertTrue(self.reserve("intent_no_provider"))
        self.witness_current()
        after_restart = self.reopen()
        outcome = after_restart.assess_restart(
            checkpoint_envelope=self.cp(after_restart.read_events()),
            checkpoint_pinned_keys=self.cp_keys,
            highwater_pinned_keys=self.floor_keys,
            read_signed_highwater=self.floor_reader,
        )
        self.assertEqual(outcome.reason, "reserved_effect_unknown")
        self.assertFalse(outcome.automatic_retry_allowed)

    def test_50_second_write_denial_is_transactional(self):
        self.assertTrue(self.reserve("first"))
        for attempt in range(3):
            with self.assertRaisesRegex(JournalUnavailable, "unresolved_first_operation_blocks_new_intent"):
                self.reserve("another_"+str(attempt))
        self.assertEqual(self.reopen().read_events(), [{"seq": 1, "intent": "first"}])

if __name__ == "__main__":
    unittest.main()
