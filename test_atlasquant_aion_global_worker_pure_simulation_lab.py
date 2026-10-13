"""AION V16-A.49 — in-memory Global Worker transitions; NO authorization.

This is an explicitly NON-PRODUCTIVE LAB. Only state-transition helpers are
invoked: never call run_global_worker_once, the CAS writer or the executor.
Even a locally well-formed "ARMED" fixture is not authenticated HUMAN_OWNER
authorization or an independently witnessed current checkpoint.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch

from atlasquant_aion_core_intelligence.evidence import digest
from atlasquant_aion_global_worker import (
    MAX_JOBS,
    _claim_state,
    _default_state,
    _mutated,
    _normalize_inflight_tick,
    _release_state,
    govern_global_worker_plan,
)


NOW = datetime(2026, 10, 13, 21, 0, tzinfo=timezone.utc)
RUNNER = "a49-simulated-runner"
TOKEN = "A49_TEST_ONLY_INERT_TOKEN_NOT_AN_AUTHORITY"


def _local_fixture():
    """Construct a local scenario, NOT a staged/approved operational Worker."""
    return _mutated(
        _default_state(),
        state="ARMED",
        kill_switch=False,
        lease_seconds=600,
    )


def _inert_batch():
    return {
        "status": "SIMULATED_NO_EFFECT",
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "blocked": 0,
    }


class WorkerInMemorySimulationLabTests(TestCase):
    """Pure transitions stay entirely behind test-owned no-I/O sentinels."""

    def setUp(self):
        forbidden = (
            "atlasquant_aion_global_worker.requests.put",
            "atlasquant_aion_global_worker.requests.get",
            "atlasquant_aion_global_worker._persist_runtime_checkpoint_cas",
            "atlasquant_aion_global_worker.load_runtime_checkpoint",
            "atlasquant_aion_global_worker._execute_due_local_work_authorized",
            "atlasquant_aion_global_worker.run_global_worker_once",
        )
        self.guards = {}
        for target in forbidden:
            patcher = patch(
                target,
                side_effect=AssertionError("A49_INERT_LAB_FORBIDS_" + target),
            )
            self.guards[target] = patcher.start()
            self.addCleanup(patcher.stop)
        token_patcher = patch(
            "atlasquant_aion_global_worker.secrets.token_urlsafe",
            return_value=TOKEN,
        )
        self.token_mock = token_patcher.start()
        self.addCleanup(token_patcher.stop)

    def tearDown(self):
        for target, guard in self.guards.items():
            self.assert_not_called(guard, target)

    def assert_not_called(self, guard, target):
        self.assertEqual(
            guard.call_count, 0,
            "A49 simulation called a forbidden production surface: " + target,
        )

    def _claim(self, state=None, *, runner=RUNNER, now=NOW, work_intent=None):
        return _claim_state(
            _local_fixture() if state is None else state,
            runtime_id=runner,
            now=now,
            work_intent=work_intent,
        )

    def test_01_local_claim_is_copy_only_no_external_lease(self):
        before = _local_fixture()
        saved = deepcopy(before)
        claimed, lease = self._claim(before)
        self.assertEqual(before, saved)
        self.assertEqual(lease["state"], "CLAIMED")
        self.assertEqual(lease["fencing_token"], 1)
        self.assertEqual(lease["token"], TOKEN)
        self.assertEqual(claimed["inflight_tick"]["state"], "CLAIMED")
        self.assertNotEqual(claimed, before)

    def test_02_second_local_runner_cannot_claim_active_lease(self):
        first, _ = self._claim()
        unchanged = deepcopy(first)
        after, lease = self._claim(
            first, runner="a49-other-runner", now=NOW + timedelta(seconds=5),
        )
        self.assertEqual(lease["state"], "LEASE_HELD")
        self.assertEqual(lease["fencing_token"], 1)
        self.assertEqual(after, unchanged)

    def test_03_expired_local_lease_increments_fencing_counter(self):
        first, lease1 = self._claim()
        after, lease2 = self._claim(
            first, runner="a49-recovery-runner",
            now=NOW + timedelta(seconds=601),
        )
        self.assertEqual(lease1["fencing_token"], 1)
        self.assertEqual(lease2["fencing_token"], 2)
        self.assertTrue(lease2["reclaimed"])
        self.assertEqual(after["fencing_counter"], 2)
        self.assertEqual(after["stats"]["crash_recoveries"], 1)

    def test_04_same_owner_reentry_preserves_active_local_fence(self):
        first, lease1 = self._claim()
        second, lease2 = self._claim(first, now=NOW + timedelta(seconds=4))
        self.assertEqual(lease2["fencing_token"], lease1["fencing_token"])
        self.assertEqual(lease2["token"], lease1["token"])
        self.assertEqual(second["lease"]["owner"], RUNNER)

    def test_05_inert_release_clears_local_inflight_without_effect(self):
        claimed, lease = self._claim()
        final = _release_state(
            claimed, runtime_id=RUNNER,
            expected_lease_token=lease["token"],
            expected_fencing_token=lease["fencing_token"],
            now=NOW + timedelta(seconds=9),
            batch=_inert_batch(),
            final_status="SIMULATED_NO_EFFECT",
        )
        self.assertEqual(final["lease"]["owner"], "")
        self.assertEqual(final["inflight_tick"], {})
        self.assertEqual(final["stats"]["ticks"], 1)
        self.assertEqual(final["stats"]["processed"], 0)
        self.assertEqual(final["stats"]["succeeded"], 0)
        self.assertEqual(claimed["inflight_tick"]["state"], "CLAIMED")

    def test_06_wrong_lease_owner_token_or_fence_denied_by_local_transition(self):
        claimed, lease = self._claim()
        cases = (
            ({"runtime_id": "other-lab-runner"}, "GLOBAL_LEASE_OWNER_MISMATCH"),
            ({"expected_lease_token": "forged-test-token"}, "GLOBAL_LEASE_TOKEN_MISMATCH"),
            ({"expected_fencing_token": 2}, "GLOBAL_FENCING_TOKEN_MISMATCH"),
        )
        for updates, reason in cases:
            with self.subTest(reason=reason):
                kwargs = {
                    "runtime_id": RUNNER,
                    "expected_lease_token": lease["token"],
                    "expected_fencing_token": lease["fencing_token"],
                    "now": NOW + timedelta(seconds=1),
                    "batch": _inert_batch(),
                    "final_status": "SIMULATED_NO_EFFECT",
                }
                kwargs.update(updates)
                before = deepcopy(claimed)
                with self.assertRaisesRegex(ValueError, reason):
                    _release_state(claimed, **kwargs)
                self.assertEqual(claimed, before)

    def test_07_tampered_inflight_digest_rejected_even_locally(self):
        occurrence = {
            "schedule_id": "a49-local-only",
            "occurrence_key": "aa" * 32,
            "due_at": NOW.isoformat(),
            "capability": "ADMINISTRATION",
        }
        payload = {
            "as_of": NOW.isoformat(),
            "count": 1,
            "occurrences": [occurrence],
        }
        claimed, lease = self._claim(
            work_intent={**payload, "digest": digest(payload)},
        )
        self.assertEqual(lease["state"], "CLAIMED")
        self.assertEqual(claimed["inflight_tick"]["work_intent_count"], 1)
        tampered = deepcopy(claimed["inflight_tick"])
        tampered["work_intent_digest"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "invalid global inflight work digest"):
            _normalize_inflight_tick(tampered)
        self.assertEqual(claimed["inflight_tick"]["work_intent_digest"], digest(payload))

    def test_08_bounded_local_claim_rejects_oversized_occurrence_batch(self):
        with self.assertRaisesRegex(ValueError, "invalid global work intent occurrences"):
            self._claim(
                work_intent={
                    "count": MAX_JOBS + 1,
                    "occurrences": [{"simulated": True}] * (MAX_JOBS + 1),
                    "digest": "test-only-not-authority",
                    "as_of": NOW.isoformat(),
                },
            )

    def test_09_invalid_runtime_id_fails_closed_in_local_transition(self):
        for value in ("", "  ", True, 123):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self._claim(runner=value)

    def test_10_plan_governor_never_grants_local_authority(self):
        report = govern_global_worker_plan(
            [],
            trusted_context={
                "tenant_id": "a49-lab-tenant",
                "workspace_id": "a49-lab-workspace",
            },
        )
        for key in (
            "grants_permission", "executes_action", "starts_worker",
            "arms_worker", "authorizes_action",
        ):
            self.assertIs(report[key], False)
        self.assertNotIn("independent_witness_verified", report)

    def test_11_lab_token_never_serves_as_external_witness(self):
        claimed, lease = self._claim()
        self.assertEqual(lease["token"], TOKEN)
        self.assertEqual(claimed["lease"]["token"], TOKEN)
        self.assertNotIn("source_authenticity_verified", lease)
        self.assertNotIn("owner_identity_verified", lease)
        self.assertNotIn("independent_witness_verified", lease)


if __name__ == "__main__":
    import unittest
    unittest.main()
