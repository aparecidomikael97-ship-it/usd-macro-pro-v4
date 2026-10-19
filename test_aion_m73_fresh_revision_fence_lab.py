"""M73 adversarial LAB-only contracts. Synthetic source; NO operational grants.

Golden expected outcomes are written before CI. The direct M71 RED remains
unmodified and must not be described as repaired by these adapter tests.
"""
import unittest
from copy import deepcopy
from datetime import timedelta

from aion_m73_freshness_fence_lab import diagnose_fresh_gate_lab
from atlasquant_aion_global_worker_incident_reconciliation import (
    reconcile_global_worker_incident_center,
)
from atlasquant_aion_global_worker_reactivation_gate import (
    READY_STATUS,
    assess_post_incident_reactivation_gate,
)
from test_atlasquant_aion_global_worker_reactivation_gate import (
    NOW, _post_incident_runtime, _safe_reconciled_snapshot, _readiness, _safe_flag,
)


class M73RevisionFenceLabTests(unittest.TestCase):
    def setUp(self):
        self.runtime, self.incident = _post_incident_runtime()
        self.readiness, self.flag = _readiness(), _safe_flag()
        self.original_gate = assess_post_incident_reactivation_gate(
            self.runtime, _safe_reconciled_snapshot(self.runtime),
            self.readiness, self.flag, now=NOW
        )
        self.assertEqual(self.original_gate["status"], READY_STATUS)
        self.shape_only = {
            "post_incident_gate_required": True,
            "post_incident_closure_ledger_digest":
                self.original_gate["closure_ledger_digest"],
            "post_incident_latest_closure_record_id":
                self.original_gate["latest_closure_record_id"],
        }
        self.original_runtime = deepcopy(self.runtime)
        self.original_flag = deepcopy(self.flag)

    def obs(self, *, revision=7, instant=NOW, snapshot=None, source="LAB_SIMULATION"):
        if snapshot is None:
            snapshot = _safe_reconciled_snapshot(self.runtime)
        return {
            "source": source, "revision": revision,
            "observed_at": instant.isoformat(),
            "incident_snapshot": deepcopy(snapshot),
        }

    def evaluate(self, observations, *, now=NOW, issued_revision=7,
                 issued_source="LAB_SIMULATION", original_gate=None):
        rows = iter([deepcopy(x) for x in observations])
        def reader():
            return next(rows)
        result = diagnose_fresh_gate_lab(
            self.runtime, self.readiness, self.flag, self.shape_only,
            original_gate if original_gate is not None else self.original_gate,
            issued_revision=issued_revision, issued_source=issued_source,
            observation_reader=reader, now=now,
        )
        self.assertIs(result["authorization_issued"], False)
        self.assertIs(result["reactivation_authorized"], False)
        self.assertIs(result["feature_flag_modified"], False)
        self.assertIs(result["global_worker_executed"], False)
        self.assertIs(result["executes_action"], False)
        self.assertEqual(self.runtime, self.original_runtime)
        self.assertEqual(self.flag, self.original_flag)
        return result

    def checked(self, expected, observations, **kw):
        result = self.evaluate(observations, **kw)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["reason"], expected)

    def incident_snapshot(self, when, *, new_incident=False):
        incident = deepcopy(self.incident)
        incident["generated_at"] = when.isoformat()
        if new_incident:
            incident["evidence_digest"] = "e" * 64
        return reconcile_global_worker_incident_center(
            {}, incident, self.runtime, now=when
        )

    def test_m73_01_coherent_diagnostic_never_authorizes(self):
        one = self.obs()
        result = self.evaluate([one, one])
        self.assertEqual(result["state"], "DIAGNOSTIC_COHERENT_ONLY")
        self.assertEqual(result["reason"], "NO_ACTIVATION_AUTHORITY_OR_ATOMIC_FENCE")

    def test_m73_02_reopened_revision_blocks_replayed_ready_gate(self):
        when = NOW + timedelta(seconds=10)
        reopened = self.incident_snapshot(when)
        self.assertEqual(
            reopened["global_worker_reconciliation"]["state"], "REOPENED"
        )
        one = self.obs(revision=8, instant=when, snapshot=reopened)
        self.checked("M73_REVISION_CHANGED_AFTER_GATE", [one, one], now=when)

    def test_m73_03_reopened_even_if_revision_claim_unchanged_blocks(self):
        when = NOW + timedelta(seconds=10)
        reopened = self.incident_snapshot(when)
        one = self.obs(revision=7, instant=when, snapshot=reopened)
        self.checked("M73_CURRENT_INCIDENT_BLOCKED", [one, one], now=when)

    def test_m73_04_new_distinct_incident_blocks(self):
        when = NOW + timedelta(seconds=10)
        snap = self.incident_snapshot(when, new_incident=True)
        self.assertEqual(
            snap["global_worker_reconciliation"]["state"],
            "NEW_INCIDENT_AFTER_CLOSURE",
        )
        one = self.obs(revision=7, instant=when, snapshot=snap)
        self.checked("M73_CURRENT_INCIDENT_BLOCKED", [one, one], now=when)

    def test_m73_05_missing_reader_blocks(self):
        result = diagnose_fresh_gate_lab(
            self.runtime, self.readiness, self.flag, self.shape_only,
            self.original_gate, issued_revision=7,
            issued_source="LAB_SIMULATION", observation_reader=None, now=NOW
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["reason"], "M73_SOURCE_UNAVAILABLE")
        self.assertFalse(result["authorization_issued"])

    def test_m73_06_source_read_error_blocks(self):
        def bad_reader():
            raise OSError("LAB_SIMULATED_UNAVAILABLE")
        result = diagnose_fresh_gate_lab(
            self.runtime, self.readiness, self.flag, self.shape_only,
            self.original_gate, issued_revision=7,
            issued_source="LAB_SIMULATION", observation_reader=bad_reader, now=NOW
        )
        self.assertEqual(result["reason"], "M73_SOURCE_READ_FAILED")
        self.assertEqual(result["state"], "BLOCKED")

    def test_m73_07_old_observation_blocks_within_gate_ttl(self):
        old = self.obs()
        self.checked(
            "M73_OBSERVATION_STALE", [old, old],
            now=NOW + timedelta(seconds=6)
        )

    def test_m73_08_future_observation_blocks(self):
        future = self.obs(instant=NOW + timedelta(seconds=1))
        self.checked("M73_OBSERVATION_FROM_FUTURE", [future, future])

    def test_m73_09_revision_rollback_blocks(self):
        one = self.obs(revision=6)
        self.checked("M73_REVISION_ROLLBACK", [one, one])

    def test_m73_10_revision_change_between_reads_blocks(self):
        a, b = self.obs(revision=7), self.obs(revision=8)
        self.checked("M73_TOCTOU_OBSERVATION_CHANGED", [a, b])

    def test_m73_11_snapshot_change_between_reads_blocks(self):
        a, b = self.obs(), self.obs()
        b["incident_snapshot"]["global_worker_reconciliation"]["current_outcome"] = "TAMPERED"
        self.checked("M73_TOCTOU_OBSERVATION_CHANGED", [a, b])

    def test_m73_12_missing_snapshot_blocks(self):
        one = self.obs()
        one["incident_snapshot"] = None
        self.checked("M73_SNAPSHOT_UNAVAILABLE", [one, one])

    def test_m73_13_source_claim_changes_blocks(self):
        one = self.obs(source="OTHER_SOURCE")
        self.checked("M73_SOURCE_CHANGED", [one, one])

    def test_m73_14_tampered_legacy_gate_blocks(self):
        gate = deepcopy(self.original_gate)
        gate["activation_plan_allowed"] = False
        one = self.obs()
        self.checked(
            "M73_OLD_GATE_INTEGRITY_MISMATCH", [one, one],
            original_gate=gate
        )

    def test_m73_15_clock_missing_timezone_blocks(self):
        now_naive = NOW.replace(tzinfo=None)
        one = self.obs()
        self.checked("M73_CLOCK_INVALID", [one, one], now=now_naive)

    def test_m73_16_unconfirmed_reconciliation_blocks(self):
        one = self.obs()
        one["incident_snapshot"]["global_worker_reconciliation"]["fail_open"] = True
        self.checked("M73_CURRENT_INCIDENT_BLOCKED", [one, one])

    def test_m73_17_reconciliation_timestamp_conflict_blocks(self):
        one = self.obs()
        one["observed_at"] = (NOW + timedelta(seconds=1)).isoformat()
        self.checked(
            "M73_OBSERVATION_FROM_FUTURE", [one, one], now=NOW
        )

    def test_m73_18_snapshot_timestamp_conflict_blocks(self):
        one = self.obs()
        one["incident_snapshot"]["global_worker_reconciliation"]["reconciled_at"] = (
            NOW - timedelta(seconds=1)
        ).isoformat()
        self.checked("M73_RECONCILIATION_TIME_MISMATCH", [one, one])


if __name__ == "__main__":
    unittest.main()
