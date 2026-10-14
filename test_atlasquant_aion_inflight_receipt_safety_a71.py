"""A71: missing local evidence safety flags must classify as unsafe.

This suite cannot enroll F1/T1, a producer, a trusted clock or an owner.
All receipts/checkpoints are synthetic and read-only. Real Global Worker stays OFF.
"""
import unittest
from copy import deepcopy

import test_atlasquant_aion_inflight_untrusted_receipts_a58 as a58
from atlasquant_aion_background_executor import EXECUTOR_NAMESPACE, _bundle_digest
from atlasquant_aion_global_worker_inflight_reconciliation import (
    _receipt_is_safe, assess_global_inflight_reconciliation,
)

SAFETY_FLAGS = (
    "provider_called", "external_action_executed",
    "real_trading_enabled", "execution_authorized",
)


class A71ReceiptCompletenessSecurityTests(unittest.TestCase):
    def test_01_explicit_false_flags_are_necessary_for_safe_claim(self):
        self.assertTrue(_receipt_is_safe({key: False for key in SAFETY_FLAGS}))
        for omitted in SAFETY_FLAGS:
            with self.subTest(omitted=omitted):
                receipt = {key: False for key in SAFETY_FLAGS if key != omitted}
                self.assertFalse(
                    _receipt_is_safe(receipt),
                    "an absent flag must not be silently interpreted as False",
                )

    def test_02_non_bool_or_true_flags_are_unsafe(self):
        for field in SAFETY_FLAGS:
            for value in (True, None, "false", 0, [], {}):
                with self.subTest(field=field, value=repr(value)):
                    receipt = {key: False for key in SAFETY_FLAGS}
                    receipt[field] = value
                    self.assertFalse(_receipt_is_safe(receipt))

    def test_03_digested_local_receipt_missing_flag_must_escalate(self):
        fixture = a58.A58LocalTerminalAuthorityDenialTests()
        fixture.setUp()
        for omitted in SAFETY_FLAGS:
            with self.subTest(omitted=omitted):
                checkpoint = fixture.locally_relabel_terminal(
                    fixture.local_receipt_checkpoint(), state="SUCCEEDED",
                )
                before = deepcopy(checkpoint)
                raw = checkpoint[EXECUTOR_NAMESPACE]
                del raw["receipts"][0][omitted]
                raw["digest"] = _bundle_digest(raw)
                before = deepcopy(checkpoint)
                assessment = assess_global_inflight_reconciliation(
                    fixture.runtime(checkpoint), now=fixture.after_expiry,
                )
                self.assertEqual(
                    assessment["status"], "BLOCKED_UNSAFE_EVIDENCE",
                    "locally recomputed digest is no independent receipt custody",
                )
                self.assertTrue(assessment["unsafe_evidence"])
                self.assertEqual(
                    assessment["occurrences"][0]["classification"],
                    "LOCAL_TERMINAL_UNVERIFIED",
                )
                self.assertEqual(fixture.stage(checkpoint)["status"], "BLOCKED")
                self.assertEqual(checkpoint, before)

    def test_04_local_receipt_with_false_flags_still_never_clears(self):
        fixture = a58.A58LocalTerminalAuthorityDenialTests()
        fixture.setUp()
        checkpoint = fixture.locally_relabel_terminal(
            fixture.local_receipt_checkpoint(), state="BLOCKED",
        )
        result = assess_global_inflight_reconciliation(
            fixture.runtime(checkpoint), now=fixture.after_expiry,
        )
        self.assertEqual(result["status"], "UNVERIFIED_TERMINAL_EVIDENCE_REVIEW_REQUIRED")
        self.assertFalse(result["unsafe_evidence"])
        self.assertEqual(fixture.stage(checkpoint)["status"], "BLOCKED")
        self.assertFalse(result["automatic_clear_allowed"])
        self.assertFalse(result["automatic_retry_allowed"])


if __name__ == "__main__":
    unittest.main()
