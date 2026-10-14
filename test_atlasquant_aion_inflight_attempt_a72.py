"""A72: locally re-digested malformed executor attempts never crash assessor.

Synthetic checkpoint/receipt-only redteam: zero network, producer, persistence,
Global Worker execution, F1/T1 attestation or actual owner approval.
"""
import unittest
from copy import deepcopy

import test_atlasquant_aion_inflight_untrusted_receipts_a58 as a58
from atlasquant_aion_background_executor import EXECUTOR_NAMESPACE, _bundle_digest
from atlasquant_aion_global_worker_inflight_reconciliation import (
    assess_global_inflight_reconciliation,
)

class A72MalformedAttemptDenialTests(unittest.TestCase):
    def setUp(self):
        self.f = a58.A58LocalTerminalAuthorityDenialTests()
        self.f.setUp()

    def _tampered(self, *, value, missing=False):
        chk = self.f.locally_relabel_terminal(
            self.f.local_receipt_checkpoint(), state="SUCCEEDED",
        )
        raw = chk[EXECUTOR_NAMESPACE]
        row = raw["receipts"][0]
        if missing:
            del row["attempt"]
        else:
            row["attempt"] = value
        raw["digest"] = _bundle_digest(raw)
        return chk

    def _assert_fail_closed(self, chk):
        prior = deepcopy(chk)
        result = assess_global_inflight_reconciliation(
            self.f.runtime(chk), now=self.f.after_expiry,
        )
        self.assertEqual(result["status"], "BLOCKED_UNSAFE_EVIDENCE")
        self.assertIs(result["unsafe_evidence"], True)
        self.assertFalse(result["automatic_clear_allowed"])
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertFalse(result["executes_action"])
        self.assertEqual(self.f.stage(chk)["status"], "BLOCKED")
        self.assertEqual(chk, prior)

    def test_01_malformed_string_and_container_cannot_throw_or_clear(self):
        for value in ("nan", "2.5", "missing", {}, [], None):
            with self.subTest(value=repr(value)):
                self._assert_fail_closed(self._tampered(value=value))

    def test_02_bool_zero_negative_and_unbounded_count_are_rejected(self):
        for value in (False, True, 0, -1, 1_000_001, 10**100):
            with self.subTest(value=repr(value)):
                self._assert_fail_closed(self._tampered(value=value))

    def test_03_missing_attempt_is_unsafe_not_implicit_zero(self):
        self._assert_fail_closed(self._tampered(value=None, missing=True))

    def test_04_valid_original_attempt_stays_local_unverified(self):
        chk = self.f.locally_relabel_terminal(
            self.f.local_receipt_checkpoint(), state="SUCCEEDED",
        )
        result = assess_global_inflight_reconciliation(
            self.f.runtime(chk), now=self.f.after_expiry,
        )
        self.assertEqual(result["status"], "UNVERIFIED_TERMINAL_EVIDENCE_REVIEW_REQUIRED")
        self.assertIs(result["unsafe_evidence"], False)
        self.assertEqual(self.f.stage(chk)["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
