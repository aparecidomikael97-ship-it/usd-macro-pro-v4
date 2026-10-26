"""G77 synthetic COMMIT interruption regression; no external effects."""
import unittest
from datetime import timedelta

from labs.a190.test_g33_outbox_ambiguous_commit_lab import (
    AmbiguousCommit, G33OutboxCommitAmbiguity, NOW, SCOPE, WORKER,
)
from aion_chat.store import StorageUnavailableError


class InterruptCommit(AmbiguousCommit):
    def __init__(self, real, *, after, error, close_error=None):
        super().__init__(real, after=after)
        self.error = error
        self.close_error = close_error

    def commit(self):
        self.commits += 1
        # Installed only after claim: this must be the pre-witness reservation.
        row = self.real.execute(
            "SELECT state,last_error FROM action_outbox"
        ).fetchone()
        assert tuple(row) == ("UNCERTAIN", "FIRST_ATTEMPT_WITNESS_PENDING")
        if self.after:
            self.real.commit()
        raise self.error

    def close(self):
        super().close()
        if self.close_error is not None:
            raise self.close_error


class G77CommitInterruptQuarantine(unittest.TestCase):
    # Reuse the existing isolated SQLite fixture without inheriting its tests.
    setUp = G33OutboxCommitAmbiguity.setUp
    restore_if_healthy = G33OutboxCommitAmbiguity.restore_if_healthy
    stage = G33OutboxCommitAmbiguity.stage
    reopened = G33OutboxCommitAmbiguity.reopened

    def check_interrupt(self, error, *, after=True, close_error=None):
        key = self.stage()["idempotency_key"]
        self.outbox.claim_next(WORKER, now=NOW, lease_seconds=60)
        witness_calls = []
        self.outbox._synthetic_lab_callbacks_enabled = True
        self.outbox._first_attempt_guard = lambda intent: witness_calls.append(intent) or True
        proxy = InterruptCommit(self.original, after=after, error=error,
                                close_error=close_error)
        self.outbox.db = self.store.db = proxy
        decision = self.outbox.get(key)["decision"]
        with self.assertRaises(type(error)) as caught:
            self.outbox.dispatch_claimed(
                key, worker_id=WORKER, now=NOW + timedelta(seconds=1),
                adapter=self.trap,
                authorize=lambda _: {
                    "allowed": True, "actor_id": SCOPE.owner_id,
                    "policy_version": decision["policy_version"],
                    "authorization_ref": decision["authorization_ref"],
                },
            )
        self.assertIs(caught.exception, error)
        self.assertEqual(witness_calls, [])
        self.assertEqual(self.trap.lookups, 0)
        self.assertEqual(proxy.commits, 1)
        self.assertEqual(proxy.rollbacks, 0)
        self.assertEqual(proxy.closes, 1)
        self.assertIsNone(self.outbox.db)
        self.assertIsNone(self.store.db)
        self.assertEqual(self.store.storage_health()["state"], "failed")
        self.assertTrue(any("COMMIT_OUTCOME_UNCERTAIN" in note
                            for note in getattr(error, "__notes__", [])))
        with self.assertRaises(StorageUnavailableError):
            self.stage("quarantined")
        with self.reopened() as (_, outbox):
            self.assertEqual(outbox.get(key)["state"],
                             "UNCERTAIN" if after else "CLAIMED")
            self.assertEqual(outbox.effect_count(), 0)
            if after:
                expired = NOW + timedelta(minutes=2)
                outbox.release_expired_claims(now=expired)
                self.assertIsNone(outbox.claim_next("g77-other", now=expired))
                self.assertEqual(outbox.get(key)["state"], "UNCERTAIN")

    def test_postcommit_keyboard_interrupt(self):
        self.check_interrupt(KeyboardInterrupt("g77-retained"))

    def test_postcommit_system_exit(self):
        self.check_interrupt(SystemExit("g77-retained"))

    def test_precommit_keyboard_interrupt(self):
        self.check_interrupt(KeyboardInterrupt("g77-before"), after=False)

    def test_precommit_system_exit(self):
        self.check_interrupt(SystemExit("g77-before"), after=False)

    def test_close_interrupt_preserves_original(self):
        self.check_interrupt(KeyboardInterrupt("g77-primary"),
                             close_error=SystemExit("g77-secondary"))

    def test_ordinary_postcommit_failure(self):
        self.check_interrupt(OSError("g77-ordinary"))

    def test_ordinary_precommit_failure(self):
        self.check_interrupt(OSError("g77-ordinary"), after=False)


if __name__ == "__main__":
    unittest.main()
