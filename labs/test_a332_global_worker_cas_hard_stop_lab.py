"""A332 LAB: Global Worker frontdoor and direct CAS writer stay hard-stopped.

Revalidate historic A47/A48 containment against the current A331 stack.
No runtime network, provider, worker, credentials or productive writes are used.
"""
import unittest
from unittest.mock import MagicMock, patch

from atlasquant_aion_global_worker import (
    _persist_runtime_checkpoint_cas,
    run_global_worker_once,
)
from atlasquant_aion_memory import ensure_operating_checkpoint
import test_atlasquant_aion_global_worker as worker_fixtures


class A332GlobalWorkerCasHardStopTests(unittest.TestCase):
    def setUp(self):
        self.fixture = worker_fixtures.AionGlobalDurableWorkerTests()
        self.fixture.setUp()

    def assert_denied(self, result):
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "INDEPENDENT_SOURCE_WITNESS_NOT_ENROLLED")
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["independent_witness_verified"])
        self.assertFalse(result["owner_identity_verified"])

    def test_feature_disabled_keeps_no_network_or_execution(self):
        with patch(
            "atlasquant_aion_global_worker.load_runtime_checkpoint",
        ) as load, patch(
            "atlasquant_aion_global_worker._persist_runtime_checkpoint_cas",
        ) as persist, patch(
            "atlasquant_aion_global_worker._execute_due_local_work_authorized",
        ) as execute:
            result = run_global_worker_once(
                config=worker_fixtures._config(), runtime_id="a332-flag-off",
                feature_enabled=False, now=worker_fixtures.TICK,
            )
        load.assert_not_called()
        persist.assert_not_called()
        execute.assert_not_called()
        self.assertEqual(result["status"], "FEATURE_DISABLED")
        self.assertFalse(result["network_called"])

    def test_enabled_direct_frontdoor_does_not_read_or_claim_checkpoint(self):
        with patch(
            "atlasquant_aion_global_worker.load_runtime_checkpoint",
        ) as load, patch(
            "atlasquant_aion_global_worker._persist_runtime_checkpoint_cas",
        ) as persist, patch(
            "atlasquant_aion_global_worker._execute_due_local_work_authorized",
        ) as execute:
            result = run_global_worker_once(
                config=worker_fixtures._config(), runtime_id="a332-true-flag",
                feature_enabled=True, now=worker_fixtures.TICK,
            )
        load.assert_not_called()
        persist.assert_not_called()
        execute.assert_not_called()
        self.assert_denied(result)
        self.assertEqual(result["processed"], 0)
        self.assertFalse(result["network_called"])
        self.assertFalse(result["automatic_runtime_checkpoint_persistence"])

    def test_enabled_environment_flag_cannot_read_runtime(self):
        with patch(
            "atlasquant_aion_global_worker.global_worker_feature_enabled",
            return_value=True,
        ), patch(
            "atlasquant_aion_global_worker.load_runtime_checkpoint",
        ) as load, patch(
            "atlasquant_aion_global_worker._persist_runtime_checkpoint_cas",
        ) as persist:
            result = run_global_worker_once(
                config=worker_fixtures._config(), runtime_id="a332-env-on", now=worker_fixtures.TICK,
            )
        load.assert_not_called()
        persist.assert_not_called()
        self.assert_denied(result)
        self.assertFalse(result["network_called"])

    def test_hostile_config_boolean_not_evaluated_before_denial(self):
        class HostileConfig:
            def __bool__(self):
                raise AssertionError("A332_UNTRUSTED_CONFIG_BOOL_CALLED")
        with patch(
            "atlasquant_aion_global_worker.load_runtime_checkpoint",
        ) as load:
            result = run_global_worker_once(
                config=HostileConfig(), runtime_id="a332-hostile",
                feature_enabled=True, now=worker_fixtures.TICK,
            )
        load.assert_not_called()
        self.assert_denied(result)
        self.assertFalse(result["network_called"])

    def test_direct_writer_with_fake_local_witness_never_puts(self):
        checkpoint = ensure_operating_checkpoint(self.fixture.armed_checkpoint())
        checkpoint["independent_witness"] = {
            "verified": True, "owner": "self-asserted", "source": "LOCAL_FAKE"
        }
        with patch(
            "atlasquant_aion_global_worker.requests.put",
            return_value=MagicMock(status_code=409),
        ) as put, patch(
            "atlasquant_aion_global_worker.load_runtime_checkpoint",
        ) as readback:
            result = _persist_runtime_checkpoint_cas(
                checkpoint, worker_fixtures._config(), expected_sha="caller-sha",
                operation="claim global lease",
            )
        put.assert_not_called()
        readback.assert_not_called()
        self.assert_denied(result)
        self.assertFalse(result["saved"])
        self.assertFalse(result["verified"])
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertFalse(result["network_called"])

    def test_direct_writer_never_reads_hostile_branch_property(self):
        class HostileConfig:
            @property
            def branch(self):
                raise AssertionError("A332_UNTRUSTED_BRANCH_READ")
        with patch(
            "atlasquant_aion_global_worker.requests.put",
        ) as put:
            result = _persist_runtime_checkpoint_cas(
                {}, HostileConfig(), expected_sha="caller-sha",
                operation="claim global lease",
            )
        put.assert_not_called()
        self.assert_denied(result)
        self.assertFalse(result["network_called"])

    def test_missing_cas_sha_does_not_change_unenrolled_denial(self):
        with patch(
            "atlasquant_aion_global_worker.requests.put",
        ) as put:
            result = _persist_runtime_checkpoint_cas(
                {}, worker_fixtures._config(), expected_sha="", operation="claim global lease",
            )
        put.assert_not_called()
        self.assert_denied(result)
        self.assertFalse(result["network_called"])


if __name__ == "__main__":
    unittest.main()
