"""A58 RED: locally digest-sealed terminal rows are NOT independent producer proof.

Regression against real AION inflight reconciliation and clear-staging paths.
No provider/network calls, no runtime writes and no positive owner enrollment.
RED assertions must remain RED until a fail-closed boundary is validated.
"""
import unittest
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

import test_atlasquant_aion_global_worker_inflight_reconciliation as rf
from atlasquant_aion_background_executor import (
    EXECUTOR_NAMESPACE, _bundle_digest, execute_due_local_work,
    _execute_due_local_work_authorized,
)
from atlasquant_aion_global_worker_inflight_reconciliation import assess_global_inflight_reconciliation
from atlasquant_aion_global_worker_inflight_resolution import (
    CONFIRMATION_PHRASE as CLEAR_PHRASE, stage_resolved_inflight_clear,
)


class A58LocalTerminalAuthorityDenialTests(unittest.TestCase):
    def setUp(self):
        self.f = rf.GlobalInflightReconciliationTests()
        self.f.setUp()
        self.claimed, self.intent = self.f.claimed(self.f.due_checkpoint())
        self.assertEqual(self.intent["count"], 1)
        self.after_expiry = rf.TICK + timedelta(minutes=20)

    def runtime(self, checkpoint):
        return self.f.runtime(checkpoint)

    def stage(self, checkpoint):
        return stage_resolved_inflight_clear(
            self.f.access, self.runtime(checkpoint),
            confirmation=True, confirmation_phrase=CLEAR_PHRASE,
            now=self.after_expiry,
        )

    def local_receipt_checkpoint(self):
        # Only a safe inert LOCAL simulation, with the handler intercepted.
        with patch(
            "atlasquant_aion_background_executor.handle_runtime_intent",
            return_value={
                "status": "COMPLETED",
                "provider_called": False,
                "external_action_executed": False,
                "real_trading_enabled": False,
                "execution_authorized": False,
            },
        ) as handler:
            result = execute_due_local_work(
                self.f.access, self.claimed,
                confirmation=True, now=rf.TICK,
            )
        handler.assert_called_once()
        self.assertEqual(result["processed"], 1)
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["external_persisted"])
        self.assertFalse(result["action_receipts_are_authority"])
        return result["checkpoint"]

    def locally_relabel_terminal(self, checkpoint, state=None, unsafe=False):
        result = deepcopy(checkpoint)
        raw = result[EXECUTOR_NAMESPACE]
        self.assertEqual(len(raw["receipts"]), 1)
        receipt = raw["receipts"][0]
        self.assertEqual(receipt["authorization_mode"], "HUMAN_CLICK")
        receipt["authorization_mode"] = "GLOBAL_WORKER"
        if state is not None:
            receipt["state"] = state
        if unsafe:
            receipt["external_action_executed"] = True
        # This is only a locally computed digest, NOT a producer signature.
        raw["digest"] = _bundle_digest(raw)
        return result

    def assert_no_clear(self, checkpoint):
        before = deepcopy(checkpoint)
        assessment = assess_global_inflight_reconciliation(
            self.runtime(checkpoint), now=self.after_expiry,
        )
        result = self.stage(checkpoint)
        self.assertNotEqual(
            assessment["status"], "TERMINAL_EVIDENCE_READY_FOR_HUMAN_CLEAR",
            "Local digest is not independently witnessed terminal authority",
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["requires_checkpoint_save"])
        self.assertFalse(result["executes_action"])
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertEqual(checkpoint, before)

    def test_a58_no_receipt_must_remain_ambiguous_and_unclearable(self):
        self.assert_no_clear(self.claimed)

    def test_a58_blocked_autonomous_kernel_never_creates_terminal_receipt(self):
        before = deepcopy(self.claimed)
        with patch(
            "atlasquant_aion_background_executor.handle_runtime_intent",
            side_effect=AssertionError("A58_NO_HANDLER"),
        ) as handler:
            executed = _execute_due_local_work_authorized(
                self.f.access, self.claimed,
                authorization_mode="GLOBAL_WORKER",
                authorization_digest="local-not-authority",
                now=rf.TICK,
            )
        handler.assert_not_called()
        self.assertEqual(executed["status"], "BLOCKED")
        self.assertEqual(executed["reason"], "INDEPENDENT_AUTONOMOUS_AUTHORITY_NOT_ENROLLED")
        self.assertEqual(executed["action_receipts"], [])
        self.assertEqual(self.claimed, before)
        self.assert_no_clear(executed["checkpoint"])

    def test_a58_local_human_receipt_cannot_clear_global_inflight(self):
        self.assert_no_clear(self.local_receipt_checkpoint())

    def test_a58_locally_relabelled_succeeded_receipt_must_not_unlock_clear(self):
        checkpoint = self.locally_relabel_terminal(self.local_receipt_checkpoint())
        self.assert_no_clear(checkpoint)

    def test_a58_locally_relabelled_blocked_receipt_must_not_unlock_clear(self):
        checkpoint = self.locally_relabel_terminal(
            self.local_receipt_checkpoint(), state="BLOCKED",
        )
        self.assert_no_clear(checkpoint)

    def test_a58_unsafe_local_terminal_must_be_rejected_even_if_redigested(self):
        checkpoint = self.locally_relabel_terminal(
            self.local_receipt_checkpoint(), unsafe=True,
        )
        assessment = assess_global_inflight_reconciliation(
            self.runtime(checkpoint), now=self.after_expiry,
        )
        self.assertEqual(assessment["status"], "BLOCKED_UNSAFE_EVIDENCE")
        self.assertEqual(self.stage(checkpoint)["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
