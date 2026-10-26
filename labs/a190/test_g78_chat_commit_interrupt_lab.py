"""G78 RED specification: COMMIT BaseException must quarantine chat SQLite.

Host-run only: do not run in the Codex Windows sandbox. These tests use local
temporary SQLite files and synthetic connection faults; no network or paid API.
Target baseline: G77 300df9eff7948a14ac1f5b56d9ebd760ef2f66d1.
RED status requires an external host run; this file alone is not validation.
"""
import unittest

from aion_chat.models import Scope
from aion_chat.store import StorageUnavailableError
from labs.a190 import test_g33_chat_ambiguous_commit_lab as g33


SCOPE = Scope("g78-owner", "g78-tenant", "g78-workspace")


class InterruptCommitFault(g33.CommitFault):
    """Retain the exact primary fault, optionally faulting after physical close."""

    def __init__(self, real, *, after, primary, close_error=None):
        super().__init__(real, after=after)
        self.primary = primary
        self.close_error = close_error

    def commit(self):
        self.commit_count += 1
        if self.after:
            self.real.commit()
        raise self.primary

    def close(self):
        # Physically close first so precommit effects are discarded and the
        # synthetic secondary exception cannot leak a SQLite handle or lock.
        super().close()
        if self.close_error is not None:
            raise self.close_error


class G78ChatCommitInterrupt(unittest.TestCase):
    # Reuse only fixture lifecycle methods. Inheriting G33 would collect its
    # unrelated tests as well as these focused G78 cases.
    setUp = g33.G33ChatCommitAmbiguity.setUp
    restore_if_healthy = g33.G33ChatCommitAmbiguity.restore_if_healthy
    reopen = g33.G33ChatCommitAmbiguity.reopen

    def assert_commit_quarantined(self, *, after, primary, close_error=None):
        proxy = InterruptCommitFault(
            self.original, after=after, primary=primary, close_error=close_error
        )
        # Construction/schema setup has already completed on the real handle.
        self.store.db = proxy
        with self.assertRaises(BaseException) as captured:
            self.store.create_conversation(SCOPE, "g78-committed-candidate")

        # Catch BaseException deliberately so a leaked secondary SystemExit
        # becomes an identity assertion failure instead of exiting the runner.
        self.assertIs(captured.exception, primary)
        self.assertEqual(proxy.commit_count, 1)
        self.assertEqual(proxy.rollback_count, 0)
        self.assertEqual(proxy.close_count, 1)
        self.assertIsNone(self.store.db)
        self.assertEqual(self.store.storage_health()["state"], "failed")
        with self.assertRaises(StorageUnavailableError):
            self.store.require_healthy()
        with self.assertRaises(StorageUnavailableError):
            self.store.create_conversation(SCOPE, "g78-must-not-retry")
        self.assertEqual(proxy.commit_count, 1)
        self.assertEqual(proxy.rollback_count, 0)
        self.assertEqual(proxy.close_count, 1)
        self.assertTrue(any(
            "COMMIT_OUTCOME_UNCERTAIN" in note
            for note in getattr(primary, "__notes__", [])
        ))

        with self.reopen() as fresh:
            rows = fresh.list_conversations(SCOPE).items
            self.assertEqual(len(rows), 1 if after else 0)
            if after:
                self.assertEqual(rows[0].title, "g78-committed-candidate")

    def test_01_keyboard_interrupt_before_commit(self):
        self.assert_commit_quarantined(
            after=False, primary=KeyboardInterrupt("G78_COMMIT_BEFORE")
        )

    def test_02_keyboard_interrupt_after_commit(self):
        self.assert_commit_quarantined(
            after=True, primary=KeyboardInterrupt("G78_COMMIT_AFTER")
        )

    def test_03_system_exit_before_commit(self):
        self.assert_commit_quarantined(
            after=False, primary=SystemExit("G78_COMMIT_BEFORE")
        )

    def test_04_system_exit_after_commit(self):
        self.assert_commit_quarantined(
            after=True, primary=SystemExit("G78_COMMIT_AFTER")
        )

    def test_05_secondary_close_system_exit_before_commit(self):
        self.assert_commit_quarantined(
            after=False, primary=KeyboardInterrupt("G78_PRIMARY_COMMIT"),
            close_error=SystemExit("G78_SECONDARY_CLOSE"),
        )

    def test_06_secondary_close_system_exit_after_commit(self):
        # OSError reaches quarantine already on G77, independently exposing
        # whether close's BaseException masks the original COMMIT error.
        self.assert_commit_quarantined(
            after=True, primary=OSError("G78_PRIMARY_COMMIT"),
            close_error=SystemExit("G78_SECONDARY_CLOSE"),
        )

    def test_07_oserror_before_commit_control(self):
        self.assert_commit_quarantined(
            after=False, primary=OSError("G78_COMMIT_BEFORE_CONTROL")
        )

    def test_08_oserror_after_commit_control(self):
        self.assert_commit_quarantined(
            after=True, primary=OSError("G78_COMMIT_AFTER_CONTROL")
        )


if __name__ == "__main__":
    unittest.main()
