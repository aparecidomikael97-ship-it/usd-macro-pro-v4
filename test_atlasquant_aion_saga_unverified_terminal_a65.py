"""A65 LAB: local terminal-looking Outbox statuses are not no-effect proof.

The Saga is local SQLite, with no independent producer/fence or actual dispatch.
These tests don't simulate authoritative no-effect receipts or real clients.
"""
import tempfile
import unittest

import test_atlasquant_aion_execution_saga as fixture


class A65UnverifiedTerminalStateTests(unittest.TestCase):
    def setUp(self):
        self.fx = fixture.ExecutionSagaTests()
        self.fx.setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store, self.outbox, self.budget, self.saga = self.fx._components(self.tmp.name)
        self.fx._create(self.saga)
        self.item = self.fx._enqueue_forward(self.saga)["outbox"]
        self.key = self.item["idempotency_key"]
        self.assertEqual(self.saga.integrity_report("saga-1")["state"], "MATCH")

    def _snapshot(self):
        sg = self.saga.get("saga-1")
        return (sg["state"],
                tuple((row["step_key"], row["state"], row["effect_ref"], row["last_error"])
                      for row in sg["steps"]),
                self.saga.integrity_report("saga-1")["events"],
                self.outbox.effect_count())

    def _set_outbox(self, state, error):
        with self.saga.db:
            self.saga.db.execute(
                "UPDATE action_outbox SET state=?,last_error=? WHERE idempotency_key=?",
                (state, error, self.key),
            )
        self.assertEqual(self.saga.integrity_report("saga-1")["state"], "MATCH")

    def _deny_terminal(self):
        before = self._snapshot()
        with self.assertRaisesRegex(
            PermissionError, "INDEPENDENT_PRODUCER_NO_EFFECT_FENCE_NOT_ENROLLED"
        ):
            self.saga.sync_forward_outcome("saga-1", "one", now=fixture.NOW)
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_01_local_revoked_cannot_claim_terminal_failed(self):
        self._set_outbox("REVOKED", "AUTHORITY_REVOKED")
        self._deny_terminal()

    def test_02_local_blocked_reapproval_cannot_claim_terminal_failed(self):
        self._set_outbox("BLOCKED_REAPPROVAL", "AUTHORITY_EXPIRED")
        self._deny_terminal()

    def test_03_local_revoked_from_fake_authorization_callback_is_not_proof(self):
        self._set_outbox("REVOKED", "ACTOR_MISMATCH")
        self._deny_terminal()

    def test_04_blocked_producer_stays_nonterminal_without_external_send(self):
        self._set_outbox("BLOCKED_PRODUCER", "INDEPENDENT_PRODUCER_NOT_ENROLLED")
        out = self.saga.sync_forward_outcome("saga-1", "one", now=fixture.NOW)
        self.assertEqual(out["state"], "PRODUCER_ENROLLMENT_REQUIRED")
        self.assertFalse(out["executes_action"])
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_05_uncertain_is_diagnostic_only_not_no_effect_claim(self):
        self._set_outbox("UNCERTAIN", "SEND_RESULT_UNKNOWN:synthetic")
        out = self.saga.sync_forward_outcome("saga-1", "one", now=fixture.NOW)
        self.assertEqual(out["state"], "RECONCILIATION_REQUIRED")
        self.assertFalse(out["executes_action"])
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_06_forged_confirmed_remains_producer_denied(self):
        self._set_outbox("CONFIRMED", "A65_FORGED_LOCAL_POSITIVE")
        before = self._snapshot()
        with self.assertRaisesRegex(PermissionError, "INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED"):
            self.saga.sync_forward_outcome("saga-1", "one", now=fixture.NOW)
        self.assertEqual(self._snapshot(), before)

    def test_07_local_failed_retains_independent_fence_denial(self):
        self._set_outbox("FAILED", "A65_UNVERIFIED_NO_EFFECT")
        self._deny_terminal()


if __name__ == "__main__":
    unittest.main()
