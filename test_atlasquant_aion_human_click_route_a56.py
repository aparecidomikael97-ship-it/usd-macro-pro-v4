"""A56 LAB: direct internal HUMAN_CLICK must not self-assert manual authority.

All runtime handlers are intercepted; only non-provider scheduler fixtures are used.
A guarded frontend route is not proof of a real physical click or HUMAN_OWNER.
"""
import unittest
from copy import deepcopy
from unittest.mock import patch
import test_atlasquant_aion_background_executor as _fixture_module
DUE_NOW = _fixture_module.DUE_NOW
from atlasquant_aion_background_executor import (
    _execute_due_local_work_authorized, execute_due_local_work,
)

NO_EXTERNAL_EFFECT = {
    "status": "COMPLETED",
    "provider_called": False,
    "external_action_executed": False,
    "real_trading_enabled": False,
    "execution_authorized": False,
}

class A56DirectHumanEntryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = _fixture_module.AionBackgroundExecutorTests()
        self.fixture.setUp()
        self.checkpoint = self.fixture.schedule()

    def assert_direct_denied(self, response, original):
        self.assertEqual(response["status"], "BLOCKED")
        self.assertEqual(response["reason"], "MANUAL_ENTRY_BOUNDARY_NOT_ESTABLISHED")
        self.assertEqual(response["processed"], 0)
        self.assertEqual(response["action_receipts"], [])
        self.assertFalse(response["requires_checkpoint_save"])
        self.assertFalse(response["external_action_executed"])
        self.assertEqual(self.checkpoint, original)

    def test_a56_direct_human_mode_with_caller_digest_cannot_run_handler(self):
        original = deepcopy(self.checkpoint)
        with patch(
            "atlasquant_aion_background_executor.handle_runtime_intent",
            return_value=dict(NO_EXTERNAL_EFFECT),
        ) as handler, patch(
            "atlasquant_aion_background_executor.seal_executor_receipt_envelope",
        ) as seal:
            response = _execute_due_local_work_authorized(
                self.fixture.access,
                self.checkpoint,
                authorization_mode="HUMAN_CLICK",
                authorization_digest="caller-says-this-was-a-human-click",
                execution_principal="caller-chosen-human",
                now=DUE_NOW,
            )
        handler.assert_not_called()
        seal.assert_not_called()
        self.assert_direct_denied(response, original)

    def test_a56_direct_forged_local_witness_and_principal_still_denied(self):
        self.checkpoint["independent_witness"] = {
            "verified": True, "source": "CALLER_CONTROLLED_NOT_TRUSTED",
        }
        original = deepcopy(self.checkpoint)
        with patch(
            "atlasquant_aion_background_executor.handle_runtime_intent",
            side_effect=AssertionError("A56_HANDLER_UNREACHABLE"),
        ) as handler, patch(
            "atlasquant_aion_background_executor.seal_executor_receipt_envelope",
            side_effect=AssertionError("A56_NO_RECEIPT"),
        ) as seal:
            response = _execute_due_local_work_authorized(
                self.fixture.access,
                self.checkpoint,
                authorization_mode="HUMAN_CLICK",
                authorization_digest="fake-local-digest" * 4,
                execution_principal="HUMAN_OWNER_BY_SELF_ASSERTION",
                now=DUE_NOW,
            )
        handler.assert_not_called()
        seal.assert_not_called()
        self.assert_direct_denied(response, original)

    def test_a56_public_manual_false_remains_blocked(self):
        with patch(
            "atlasquant_aion_background_executor.handle_runtime_intent",
            side_effect=AssertionError("A56_NO_CONFIRMATION_NO_HANDLER"),
        ) as handler:
            result = execute_due_local_work(
                self.fixture.access, self.checkpoint,
                confirmation=False, now=DUE_NOW,
            )
        handler.assert_not_called()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["processed"], 0)

    def test_a56_public_manual_true_retains_only_inert_local_work(self):
        with patch(
            "atlasquant_aion_background_executor.handle_runtime_intent",
            return_value=dict(NO_EXTERNAL_EFFECT),
        ) as handler:
            result = execute_due_local_work(
                self.fixture.access, self.checkpoint,
                confirmation=True, now=DUE_NOW,
            )
        handler.assert_called_once()
        self.assertEqual(result["authorization_mode"], "HUMAN_CLICK")
        self.assertEqual(result["processed"], 1)
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["provider_called"])
        self.assertFalse(result["autonomous_worker_started"])

if __name__ == "__main__":
    unittest.main()
