"""A331 LAB: recovery regression for A51/A56 local executor admission fences.

No external provider, trade, deployment or worker is used. All runtime Core
handlers are intercepted. Route sentinels are NOT proof of physical HUMAN_OWNER.
"""
import unittest
from copy import deepcopy
from unittest.mock import patch

from atlasquant_aion_background_executor import (
    _execute_due_local_work_authorized,
    execute_due_local_work,
)
import test_atlasquant_aion_background_executor as fixture_module

NO_EFFECT = {
    "status": "COMPLETED",
    "provider_called": False,
    "external_action_executed": False,
    "real_trading_enabled": False,
    "execution_authorized": False,
}


class A331DirectExecutorAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.AionBackgroundExecutorTests()
        self.fixture.setUp()
        self.checkpoint = self.fixture.schedule()
        self.before = deepcopy(self.checkpoint)

    def assert_denied_without_effect(self, result, expected_reason):
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], expected_reason)
        self.assertEqual(result["processed"], 0)
        self.assertEqual(result["action_receipts"], [])
        self.assertFalse(result["requires_checkpoint_save"])
        self.assertFalse(result["provider_called"])
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["autonomous_worker_started"])
        self.assertFalse(result["independent_witness_verified"])
        self.assertEqual(result["checkpoint"], self.before)
        self.assertEqual(self.checkpoint, self.before)

    def test_direct_global_worker_digest_cannot_reach_handler(self):
        with patch(
            "atlasquant_aion_background_executor.handle_runtime_intent",
            return_value=dict(NO_EFFECT),
        ) as handler, patch(
            "atlasquant_aion_background_executor.seal_executor_receipt_envelope",
        ) as receipt:
            result = _execute_due_local_work_authorized(
                self.fixture.access, self.checkpoint,
                authorization_mode="GLOBAL_WORKER",
                authorization_digest="caller-self-asserted-not-authority",
                now=fixture_module.DUE_NOW,
            )
        handler.assert_not_called()
        receipt.assert_not_called()
        self.assert_denied_without_effect(
            result, "INDEPENDENT_AUTONOMOUS_AUTHORITY_NOT_ENROLLED"
        )

    def test_direct_armed_worker_forged_checkpoint_witness_is_denied(self):
        self.checkpoint["independent_witness"] = {
            "verified": True, "source": "CALLER_CONTROLLED"
        }
        self.before = deepcopy(self.checkpoint)
        with patch(
            "atlasquant_aion_background_executor.handle_runtime_intent",
            return_value=dict(NO_EFFECT),
        ) as handler, patch(
            "atlasquant_aion_background_executor.seal_executor_receipt_envelope",
        ) as receipt:
            result = _execute_due_local_work_authorized(
                self.fixture.access, self.checkpoint,
                authorization_mode="ARMED_WORKER",
                authorization_digest="fabricated-digest",
                execution_principal="forged-worker",
                now=fixture_module.DUE_NOW,
            )
        handler.assert_not_called()
        receipt.assert_not_called()
        self.assert_denied_without_effect(
            result, "INDEPENDENT_AUTONOMOUS_AUTHORITY_NOT_ENROLLED"
        )

    def test_direct_human_click_with_caller_digest_is_denied(self):
        with patch(
            "atlasquant_aion_background_executor.handle_runtime_intent",
            return_value=dict(NO_EFFECT),
        ) as handler, patch(
            "atlasquant_aion_background_executor.seal_executor_receipt_envelope",
        ) as receipt:
            result = _execute_due_local_work_authorized(
                self.fixture.access, self.checkpoint,
                authorization_mode="HUMAN_CLICK",
                authorization_digest="a-string-cannot-prove-human-presence",
                execution_principal="self-asserted-owner",
                now=fixture_module.DUE_NOW,
            )
        handler.assert_not_called()
        receipt.assert_not_called()
        self.assert_denied_without_effect(
            result, "MANUAL_ENTRY_BOUNDARY_NOT_ESTABLISHED"
        )

    def test_direct_human_click_with_local_fake_owner_witness_is_denied(self):
        self.checkpoint["human_owner_witness"] = {
            "verified": True, "owner": "self-asserted", "nonce": "fake"
        }
        self.before = deepcopy(self.checkpoint)
        with patch(
            "atlasquant_aion_background_executor.handle_runtime_intent",
            return_value=dict(NO_EFFECT),
        ) as handler, patch(
            "atlasquant_aion_background_executor.seal_executor_receipt_envelope",
        ) as receipt:
            result = _execute_due_local_work_authorized(
                self.fixture.access, self.checkpoint,
                authorization_mode="HUMAN_CLICK",
                authorization_digest="local-claim",
                execution_principal="HUMAN_OWNER_BY_CALLER",
                now=fixture_module.DUE_NOW,
            )
        handler.assert_not_called()
        receipt.assert_not_called()
        self.assert_denied_without_effect(
            result, "MANUAL_ENTRY_BOUNDARY_NOT_ESTABLISHED"
        )

    def test_public_frontdoor_without_confirmation_remains_blocked(self):
        with patch(
            "atlasquant_aion_background_executor.handle_runtime_intent",
            return_value=dict(NO_EFFECT),
        ) as handler:
            result = execute_due_local_work(
                self.fixture.access, self.checkpoint,
                confirmation=False, now=fixture_module.DUE_NOW,
            )
        handler.assert_not_called()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "EXPLICIT_HUMAN_CONFIRMATION_REQUIRED")
        self.assertEqual(result["processed"], 0)

    def test_public_frontdoor_keeps_inert_manual_read_draft_path(self):
        with patch(
            "atlasquant_aion_background_executor.handle_runtime_intent",
            return_value=dict(NO_EFFECT),
        ) as handler:
            result = execute_due_local_work(
                self.fixture.access, self.checkpoint,
                confirmation=True, now=fixture_module.DUE_NOW,
            )
        handler.assert_called_once()
        self.assertEqual(result["authorization_mode"], "HUMAN_CLICK")
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["succeeded"], 1)
        self.assertFalse(result["provider_called"])
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["autonomous_worker_started"])


if __name__ == "__main__":
    unittest.main()
