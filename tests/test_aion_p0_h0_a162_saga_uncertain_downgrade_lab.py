"""A162 RED-first: an UNKNOWN first effect cannot silently return to RUNNING.

Uses the actual Outbox, Saga, Budget and SQLiteChatStore fixture from #1403.
SQL rewrites are test-only adversarial corruptions, NEVER external sends.
"""
from __future__ import annotations

from datetime import timedelta
import unittest

from test_aion_p0_h0_saga_existing_first_intent_reentry_lab import (
    SagaExistingFirstIntentFenceLab, NOW,
)

LOCKED = "SAGA_UNCERTAIN_RECONCILIATION_LOCKED"
MARKERS = "SAGA_OUTBOX_PRIOR_DISPATCH_MARKERS_REQUIRES_RECONCILIATION"


class A162NoUncertainDowngradeLAB(unittest.TestCase):
    def setUp(self):
        fixture = SagaExistingFirstIntentFenceLab(
            "test_01_healthy_first_time_stage_remains_allowed_locally"
        )
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.f = fixture
        self.key = None

    def stage(self):
        out = self.f.stage_saga()
        self.key = out["outbox"]["idempotency_key"]
        self.assertEqual(self.f.box.effect_count(), 0)
        return out

    def rewrite_outbox(self, state, *, attempts=1, started="2026-10-21T17:00:01+00:00"):
        assert self.key is not None
        with self.f.db:
            self.f.db.execute(
                "UPDATE action_outbox SET state=?,attempts=?,dispatch_started_at=? "
                "WHERE idempotency_key=?",
                (state, attempts, started, self.key),
            )
        out = self.f.box.get(self.key)
        self.assertEqual(out["state"], state)
        self.assertEqual(out["local_integrity"], "MATCH")
        return out

    def first_unknown(self):
        self.stage()
        self.rewrite_outbox("UNCERTAIN")
        out = self.f.saga.sync_forward_outcome(
            "saga-first", "first", now=NOW + timedelta(seconds=2)
        )
        self.assertEqual(out["state"], "RECONCILIATION_REQUIRED")
        self.assertEqual(out["step_state"], "UNCERTAIN")
        self.assertEqual(self.f.saga.integrity_report("saga-first")["state"], "MATCH")
        return out

    def unchanged_on_denial(self, expected):
        before = tuple(self.f.db.iterdump())
        with self.assertRaisesRegex(PermissionError, expected):
            self.f.saga.sync_forward_outcome(
                "saga-first", "first", now=NOW + timedelta(seconds=3)
            )
        self.assertEqual(tuple(self.f.db.iterdump()), before)
        self.assertEqual(self.f.saga.integrity_report("saga-first")["state"], "MATCH")
        self.assertEqual(self.f.box.effect_count(), 0)

    def test_01_uncertain_then_local_pending_cannot_reopen_running(self):
        self.first_unknown()
        self.rewrite_outbox("PENDING")
        self.unchanged_on_denial(LOCKED)
        self.assertEqual(self.f.saga.get("saga-first")["state"], "RECONCILIATION_REQUIRED")

    def test_02_repeated_uncertain_sync_cannot_append_new_event(self):
        self.first_unknown()
        self.unchanged_on_denial(LOCKED)

    def test_03_uncertain_then_local_retry_cannot_reopen_running(self):
        self.first_unknown()
        self.rewrite_outbox("RETRY")
        self.unchanged_on_denial(LOCKED)

    def test_04_uncertain_then_claimed_cannot_reopen_running(self):
        self.first_unknown()
        self.rewrite_outbox("CLAIMED")
        self.unchanged_on_denial(LOCKED)

    def test_05_pending_with_dispatch_start_marker_denied_before_first_sync(self):
        self.stage()
        self.rewrite_outbox("PENDING", attempts=0)
        self.unchanged_on_denial(MARKERS)

    def test_06_pending_with_prior_attempt_counter_denied_before_first_sync(self):
        self.stage()
        self.rewrite_outbox("PENDING", attempts=1, started="")
        self.unchanged_on_denial(MARKERS)

    def test_07_clean_initial_pending_state_remains_locally_observable(self):
        self.stage()
        out = self.f.saga.sync_forward_outcome(
            "saga-first", "first", now=NOW + timedelta(seconds=2)
        )
        self.assertEqual(out["state"], "RUNNING")
        self.assertEqual(out["step_state"], "ENQUEUED")
        self.assertEqual(self.f.box.effect_count(), 0)
        self.assertEqual(self.f.saga.integrity_report("saga-first")["state"], "MATCH")

    def test_08_first_uncertain_sync_still_enters_reconciliation(self):
        self.first_unknown()
        self.assertEqual(self.f.saga.get("saga-first")["state"], "RECONCILIATION_REQUIRED")
        self.assertEqual(self.f.box.effect_count(), 0)


if __name__ == "__main__":
    unittest.main()
