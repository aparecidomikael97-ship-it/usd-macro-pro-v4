"""A66 negative contract: local-only empty inflight cannot authorize clearing.

This test uses the historical INFLIGHT test's actual in-memory scheduler/Worker
fixture, but never runs a Worker, writes a remote checkpoint, or sends effects.
It does not stand in for independent F1/T1, F2, or producer attestation.
"""
import unittest
from copy import deepcopy

import test_atlasquant_aion_global_worker_inflight_resolution as fixture
from atlasquant_aion_core_intelligence.evidence import digest
from atlasquant_aion_global_worker import (
    _mutated,
    attach_global_worker_state,
    load_global_worker_state,
)
from atlasquant_aion_global_worker_inflight_reconciliation import (
    assess_global_inflight_reconciliation,
)
from atlasquant_aion_global_worker_inflight_resolution import (
    CONFIRMATION_PHRASE,
    stage_resolved_inflight_clear,
)


class EmptyInflightRequiresIndependentWitnessA66Tests(unittest.TestCase):
    def setUp(self):
        # Composition avoids importing legacy TestCase into this module's
        # unittest discovery. The fixture is unchanged and contains no I/O.
        self.fixture = fixture.GlobalInflightResolutionTests(
            methodName="test_confirmation_is_required_before_any_staging"
        )
        self.fixture.setUp()

    def _assert_diagnostic_and_no_staging(self, checkpoint):
        source = self.fixture.runtime(checkpoint, sha="local-only-a66")
        original = deepcopy(checkpoint)
        assessment = assess_global_inflight_reconciliation(
            source, now=fixture.AFTER_EXPIRY
        )
        self.assertEqual(
            assessment["status"], "UNVERIFIED_EMPTY_BATCH_REVIEW_REQUIRED"
        )
        self.assertEqual(assessment["terminal_proven"], 0)
        self.assertFalse(assessment["automatic_clear_allowed"])

        stage = stage_resolved_inflight_clear(
            self.fixture.access,
            source,
            confirmation=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=fixture.AFTER_EXPIRY,
        )
        self.assertEqual(stage["status"], "BLOCKED")
        self.assertEqual(stage["reason"], "INFLIGHT_RECONCILIATION_NOT_CLEARABLE")
        self.assertFalse(stage["requires_checkpoint_save"])
        self.assertFalse(stage["external_persisted"])
        self.assertFalse(stage["executes_action"])
        self.assertEqual(stage["checkpoint"], original)
        self.assertEqual(checkpoint, original)

    def test_01_real_local_empty_batch_is_still_not_independently_proven(self):
        claimed, intent = self.fixture.claim(self.fixture.arm({}))
        self.assertEqual(intent["count"], 0)
        self._assert_diagnostic_and_no_staging(claimed)

    def test_02_locally_relabelled_due_work_as_empty_cannot_clear_inflight(self):
        claimed, intent = self.fixture.claim(self.fixture.due_checkpoint())
        self.assertEqual(intent["count"], 1)
        state, status = load_global_worker_state(claimed)
        self.assertEqual(status["state"], "CONNECTED")
        inflight = deepcopy(state["inflight_tick"])
        self.assertEqual(inflight["work_intent_count"], 1)
        # Deliberately change only the local manifest and recompute the
        # self-contained Worker digest, without a current-head attestation.
        inflight["work_intent_count"] = 0
        inflight["work_occurrences"] = []
        # Also rewrite all self-contained digests/intent identifiers coherently.
        # This demonstrates why checksum validation alone is not custody.
        inflight["work_intent_digest"] = digest({
            "as_of": inflight["work_intent_as_of"],
            "count": 0,
            "occurrences": [],
        })
        inflight["intent_id"] = digest({
            "owner": inflight["owner"],
            "lease_token": inflight["lease_token"],
            "fencing_token": inflight["fencing_token"],
            "claimed_at": inflight["claimed_at"],
            "work_intent_digest": inflight["work_intent_digest"],
        })
        forged = attach_global_worker_state(
            claimed, _mutated(state, inflight_tick=inflight)
        )
        self._assert_diagnostic_and_no_staging(forged)

    def test_03_wrong_confirmation_still_denied(self):
        claimed, _ = self.fixture.claim(self.fixture.arm({}))
        result = stage_resolved_inflight_clear(
            self.fixture.access,
            self.fixture.runtime(claimed),
            confirmation=True,
            confirmation_phrase="fake-owner",
            now=fixture.AFTER_EXPIRY,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "EXACT_CONFIRMATION_PHRASE_REQUIRED")
        self.assertFalse(result["requires_checkpoint_save"])


if __name__ == "__main__":
    unittest.main()
