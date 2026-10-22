"""A174 LAB — local reservation persistence is not external custody proof."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from aion_chat.uncertain_reservation_lab import (
    LocalWriteReservationLab, ReservationDenied, ReservationJournalUnavailable,
)


RID = "intent_20261022_abcdefghijklmnop"
HASH_A = "a" * 64
HASH_B = "b" * 64


class UncertainWriteJournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "reservation.sqlite3"

    def journal(self):
        return LocalWriteReservationLab(self.path)

    def test_01_same_request_never_authorizes_duplicate_effect(self):
        journal = self.journal()
        self.assertEqual(journal.reserve(RID, HASH_A)["state"], "PENDING")
        with self.assertRaisesRegex(ReservationDenied, "ALREADY_RESERVED_DENIED"):
            journal.reserve(RID, HASH_A)
        self.assertEqual(journal.status(RID)["state"], "PENDING")
        print("A174_REPLAY_SAME_ID=DENIED")

    def test_02_same_id_other_payload_is_denied(self):
        journal = self.journal()
        journal.reserve(RID, HASH_A)
        with self.assertRaisesRegex(ReservationDenied, "PAYLOAD_MISMATCH_DENIED"):
            journal.reserve(RID, HASH_B)
        self.assertEqual(journal.status(RID)["payload_sha256"], HASH_A)

    def test_03_restart_in_new_process_blocks_reserved_intent(self):
        self.journal().reserve(RID, HASH_A)
        script = (
            "import sys; from aion_chat.uncertain_reservation_lab "
            "import LocalWriteReservationLab, ReservationDenied; "
            "j=LocalWriteReservationLab(sys.argv[1]); "
            "rid=sys.argv[2]; digest=sys.argv[3]; "
            "exec('try:\\n j.reserve(rid,digest)\\nexcept ReservationDenied as e:"
            "\\n print(str(e))\\n sys.exit(0)\\n'); sys.exit(4)"
        )
        outcome = subprocess.run(
            [sys.executable, "-B", "-c", script, str(self.path), RID, HASH_A],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(outcome.returncode, 0, outcome.stdout + outcome.stderr)
        self.assertIn("ALREADY_RESERVED_DENIED", outcome.stdout)
        print("A174_NEW_PROCESS_REPLAY=DENIED_LOCAL_JOURNAL_PRESENT")

    def test_04_abrupt_exit_after_reservation_remains_pending(self):
        script = (
            "import os,sys; from aion_chat.uncertain_reservation_lab "
            "import LocalWriteReservationLab; "
            "LocalWriteReservationLab(sys.argv[1]).reserve(sys.argv[2],sys.argv[3]); "
            "os._exit(37)"
        )
        outcome = subprocess.run(
            [sys.executable, "-B", "-c", script, str(self.path), RID, HASH_A],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(outcome.returncode, 37, outcome.stderr)
        journal = self.journal()
        self.assertEqual(journal.status(RID)["state"], "PENDING")
        with self.assertRaisesRegex(ReservationDenied, "ALREADY_RESERVED_DENIED"):
            journal.reserve(RID, HASH_A)
        print("A174_ABRUPT_EXIT=PENDING_SURVIVED_LOCAL_RESTART")

    def test_05_ambiguous_result_remains_blocked_after_restart(self):
        journal = self.journal()
        journal.reserve(RID, HASH_A)
        self.assertEqual(journal.mark_unknown(RID)["state"], "UNKNOWN")
        self.assertEqual(journal.mark_unknown(RID)["state"], "UNKNOWN")
        restarted = self.journal()
        self.assertEqual(restarted.status(RID)["state"], "UNKNOWN")
        with self.assertRaisesRegex(ReservationDenied, "ALREADY_RESERVED_DENIED"):
            restarted.reserve(RID, HASH_A)
        print("A174_UNKNOWN_RESTART=DENIED")

    def test_06_two_handles_race_for_same_request_only_one_reserves(self):
        first, second = self.journal(), self.journal()

        def attempt(journal):
            try:
                journal.reserve(RID, HASH_A)
                return "RESERVED"
            except ReservationDenied as exc:
                self.assertEqual(str(exc), "ALREADY_RESERVED_DENIED")
                return "DENIED"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, (first, second)))
        self.assertCountEqual(results, ["RESERVED", "DENIED"])
        self.assertEqual(self.journal().status(RID)["state"], "PENDING")

    def test_07_missing_local_journal_after_rollback_is_a_known_bypass(self):
        journal = self.journal()
        journal.reserve(RID, HASH_A)
        self.path.unlink()  # temporary LAB file only; no user data or providers
        new_journal = self.journal()
        accepted = new_journal.reserve(RID, HASH_A)
        self.assertEqual(accepted["state"], "PENDING")
        print("A174_LOCAL_JOURNAL_DELETION=REPLAY_ACCEPTED_NOT_ATTESTED")

    def test_08_corrupt_existing_journal_does_not_silently_recreate(self):
        self.journal().reserve(RID, HASH_A)
        self.path.write_bytes(b"NOT_A_SQLITE_DATABASE")
        with self.assertRaises(ReservationJournalUnavailable):
            self.journal()

    def test_09_symlink_journal_and_parent_alias_denied(self):
        target = self.root / "actual.sqlite3"
        LocalWriteReservationLab(target)
        alias = self.root / "alias.sqlite3"
        try:
            alias.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("OS symlink creation unavailable")
        with self.assertRaisesRegex(
                ReservationJournalUnavailable, "JOURNAL_NOT_REGULAR_FILE"):
            LocalWriteReservationLab(alias)
        parent_alias = self.root / "parent-alias"
        try:
            parent_alias.symlink_to(self.root, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("OS directory symlink creation unavailable")
        with self.assertRaisesRegex(
                ReservationJournalUnavailable, "JOURNAL_PARENT_ALIAS_DENIED"):
            LocalWriteReservationLab(parent_alias / "new.sqlite3")

    def test_10_invalid_ids_and_hashes_denied(self):
        journal = self.journal()
        with self.assertRaisesRegex(ReservationDenied, "INVALID_REQUEST_ID"):
            journal.reserve("../bad", HASH_A)
        with self.assertRaisesRegex(ReservationDenied, "INVALID_PAYLOAD_SHA256"):
            journal.reserve(RID, "not a SHA")
        self.assertIsNone(journal.status(RID))


if __name__ == "__main__":
    unittest.main()
