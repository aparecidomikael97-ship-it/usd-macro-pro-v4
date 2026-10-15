"""A83 LAB: a local re-digestable FAILED receipt is not producer no-effect proof.

Only synthetic offline checkpoints; no Worker, provider, writes, or keys.
This is a diagnostic truthfulness regression, not H0/F1/T1 enrollment.
"""
import unittest
from copy import deepcopy

import test_atlasquant_aion_inflight_untrusted_receipts_a58 as a58
from atlasquant_aion_global_worker_inflight_reconciliation import (
    assess_global_inflight_reconciliation,
)


class A83LocalFailedUntrustedProofTests(unittest.TestCase):
    def setUp(self):
        self.f = a58.A58LocalTerminalAuthorityDenialTests()
        self.f.setUp()

    def synthetic_failed(self):
        # Reuse actual A58 locally generated and re-digestable untrusted row.
        local = self.f.local_receipt_checkpoint()
        return self.f.locally_relabel_terminal(local, state="FAILED")

    def test_01_fake_local_failed_must_not_be_called_proven(self):
        checkpoint = self.synthetic_failed()
        before = deepcopy(checkpoint)
        result = assess_global_inflight_reconciliation(
            self.f.runtime(checkpoint), now=self.f.after_expiry)
        self.assertNotEqual(result["status"], "TERMINAL_EVIDENCE_READY_FOR_HUMAN_CLEAR")
        self.assertNotIn("PROVEN", result["occurrences"][0]["classification"])
        self.assertEqual(result["occurrences"][0]["classification"], "LOCAL_FAILED_UNVERIFIED")
        self.assertEqual(result["failed_proven"], 0)
        self.assertGreaterEqual(result["no_terminal_evidence"], 1)
        self.assertIs(result["automatic_clear_allowed"], False)
        self.assertIs(result["automatic_retry_allowed"], False)
        self.assertIs(result["executes_action"], False)
        self.assertEqual(checkpoint, before)

    def test_02_fake_failed_never_unlocks_human_clear_staging(self):
        checkpoint = self.synthetic_failed()
        before = deepcopy(checkpoint)
        stage = self.f.stage(checkpoint)
        self.assertEqual(stage["status"], "BLOCKED")
        self.assertFalse(stage["requires_checkpoint_save"])
        self.assertFalse(stage["executes_action"])
        self.assertFalse(stage["automatic_retry_allowed"])
        self.assertEqual(checkpoint, before)


if __name__ == "__main__":
    unittest.main()
