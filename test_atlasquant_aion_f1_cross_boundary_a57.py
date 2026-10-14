"""A57: test REAL AION entrypoints against self-asserted independent authority.
This is a negative-only LAB regression suite; not witness enrollment.
"""
from copy import deepcopy
import unittest
from unittest.mock import patch
import test_atlasquant_aion_global_worker as global_fixtures
import test_atlasquant_aion_background_executor as executor_fixtures
from atlasquant_aion_background_executor import (
    _execute_due_local_work_authorized, execute_due_local_work,
)
from atlasquant_aion_global_worker import run_global_worker_once
from atlasquant_aion_global_worker_activation import (
    write_repository_feature_flag_enabled,
)
from atlasquant_aion_global_worker_readiness import runtime_posture


class F1RealEntrypointDenialTests(unittest.TestCase):
    def setUp(self):
        self.global_fixture = global_fixtures.AionGlobalDurableWorkerTests()
        self.global_fixture.setUp()
        self.local_fixture = executor_fixtures.AionBackgroundExecutorTests()
        self.local_fixture.setUp()

    def run_unenrolled_worker(self, checkpoint, **claims):
        loaded = {"status": "CONFIRMED", "checkpoint": checkpoint,
                  "sha": "a57-fake-local-sha", **claims}
        with patch(
            "atlasquant_aion_global_worker.load_runtime_checkpoint",
            return_value=loaded,
        ) as read, patch(
            "atlasquant_aion_global_worker._persist_runtime_checkpoint_cas",
            side_effect=AssertionError("A57_NO_CAS_WITHOUT_WITNESS"),
        ) as cas, patch(
            "atlasquant_aion_global_worker._execute_due_local_work_authorized",
            side_effect=AssertionError("A57_NO_EXECUTOR_WITHOUT_WITNESS"),
        ) as execute:
            result = run_global_worker_once(
                config=global_fixtures._config(),
                runtime_id="a57-f1-denial",
                feature_enabled=True,
                now=global_fixtures.TICK,
            )
        read.assert_called_once()
        cas.assert_not_called()
        execute.assert_not_called()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "INDEPENDENT_SOURCE_WITNESS_NOT_ENROLLED")
        self.assertEqual(result["processed"], 0)
        self.assertFalse(result["external_action_executed"])

    def test_01_readiness_pass_is_not_source_authorization(self):
        checkpoint = self.global_fixture.armed_checkpoint()
        original = deepcopy(checkpoint)
        posture = runtime_posture(
            {"status": "CONFIRMED", "sha": "a57-github-sha", "checkpoint": checkpoint},
            global_fixtures._config(),
        )
        self.assertEqual(posture["state"], "PASS")
        self.run_unenrolled_worker(checkpoint)
        self.assertEqual(checkpoint, original)

    def test_02_forged_witness_fields_on_loaded_result_denied(self):
        checkpoint = self.global_fixture.armed_checkpoint()
        self.run_unenrolled_worker(
            checkpoint, independent_witness_verified=True,
            independent_owner_authorized=True,
            witness_head={"verified": True, "seq": 999, "digest": "f" * 64},
            producer_receipt={"state": "COMMITTED_EFFECT", "verified": True},
        )

    def test_03_direct_flag_writer_cannot_make_post_patch(self):
        with patch(
            "atlasquant_aion_global_worker_activation.requests.post",
            side_effect=AssertionError("A57_NO_POST"),
        ) as post, patch(
            "atlasquant_aion_global_worker_activation.requests.patch",
            side_effect=AssertionError("A57_NO_PATCH"),
        ) as patch_request:
            result = write_repository_feature_flag_enabled(
                global_fixtures._config(), "DISABLED",
            )
        post.assert_not_called()
        patch_request.assert_not_called()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED")
        self.assertFalse(result["feature_flag_modified"])

    def test_04_forged_internal_manual_digest_cannot_issue_receipt(self):
        checkpoint = self.local_fixture.schedule()
        checkpoint["independent_witness"] = {"verified": True, "owner": "self-claimed"}
        original = deepcopy(checkpoint)
        with patch(
            "atlasquant_aion_background_executor.handle_runtime_intent",
            side_effect=AssertionError("A57_HANDLER_UNREACHABLE"),
        ) as handler, patch(
            "atlasquant_aion_background_executor.seal_executor_receipt_envelope",
            side_effect=AssertionError("A57_RECEIPT_UNREACHABLE"),
        ) as seal:
            result = _execute_due_local_work_authorized(
                self.local_fixture.access, checkpoint,
                authorization_mode="HUMAN_CLICK",
                authorization_digest="self-declared-click",
                execution_principal="HUMAN_OWNER_BY_CALLER",
                now=executor_fixtures.DUE_NOW,
            )
        handler.assert_not_called()
        seal.assert_not_called()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "MANUAL_ENTRY_BOUNDARY_NOT_ESTABLISHED")
        self.assertFalse(result["requires_checkpoint_save"])
        self.assertEqual(checkpoint, original)

    def test_05_public_manual_boolean_allows_only_inert_local_action(self):
        checkpoint = self.local_fixture.schedule()
        checkpoint["independent_witness"] = {"verified": True, "owner": "self-claimed"}
        with patch(
            "atlasquant_aion_background_executor.handle_runtime_intent",
            return_value={
                "status": "COMPLETED", "provider_called": False,
                "external_action_executed": False,
                "real_trading_enabled": False, "execution_authorized": False,
            },
        ) as handler:
            result = execute_due_local_work(
                self.local_fixture.access, checkpoint,
                confirmation=True, now=executor_fixtures.DUE_NOW,
            )
        handler.assert_called_once()
        self.assertEqual(result["authorization_mode"], "HUMAN_CLICK")
        self.assertEqual(result["processed"], 1)
        self.assertFalse(result["action_receipts_are_authority"])
        self.assertFalse(result["external_persisted"])
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["provider_called"])
        self.assertFalse(result["autonomous_worker_started"])
        # NOT proof of a physical click: confirmation comes from the caller.

    def test_06_feature_off_never_reads_runtime(self):
        with patch(
            "atlasquant_aion_global_worker.load_runtime_checkpoint",
            side_effect=AssertionError("A57_NO_READ_WHEN_DISABLED"),
        ) as read:
            result = run_global_worker_once(
                config=global_fixtures._config(),
                runtime_id="a57-feature-off",
                feature_enabled=False,
                now=global_fixtures.TICK,
            )
        read.assert_not_called()
        self.assertEqual(result["status"], "FEATURE_DISABLED")
        self.assertFalse(result["network_called"])
        self.assertEqual(result["processed"], 0)


if __name__ == "__main__":
    unittest.main()
