"""A84 LAB RED: no untrusted positive assessor label may stage an inflight clear.

The fixture is an offline claimed checkpoint. There are no provider calls,
no real authority enrollment, and no Runtime CAS. This contract does not
assert that monkeypatching a trusted Python module is a real external attack.
"""
import inspect
import unittest
from copy import deepcopy
from unittest.mock import patch

import test_atlasquant_aion_global_worker_inflight_resolution as history
from atlasquant_aion_global_worker_inflight_resolution import (
    CONFIRMATION_PHRASE, stage_resolved_inflight_clear,
)


class A84IndependentInflightStagingGateTests(unittest.TestCase):
    def setUp(self):
        self.f = history.GlobalInflightResolutionTests(
            methodName="test_confirmation_is_required_before_any_staging")
        self.f.setUp()
        self.claimed, self.intent = self.f.claim(self.f.due_checkpoint())
        self.assertEqual(self.intent["count"], 1)
        self.runtime = self.f.runtime(self.claimed, sha="A84-SYNTHETIC-ONLY")
        self.original = deepcopy(self.claimed)

    def stage(self, assessment):
        # This intercepted value is an adversarial regression input, not
        # source custody, producer signature or terminal-effect proof.
        with patch(
            "atlasquant_aion_global_worker_inflight_resolution."
            "assess_global_inflight_reconciliation",
            return_value=assessment,
        ) as intercepted:
            result = stage_resolved_inflight_clear(
                self.f.access,
                self.runtime,
                confirmation=True,
                confirmation_phrase=CONFIRMATION_PHRASE,
                now=history.AFTER_EXPIRY,
            )
        intercepted.assert_called_once()
        return result

    def test_01_claimed_terminal_label_without_external_root_never_stages(self):
        for status in ("TERMINAL_EVIDENCE_READY_FOR_HUMAN_CLEAR",):
            with self.subTest(status=status):
                result = self.stage({
                    "status": status,
                    "terminal_proven": 1,
                    "reconciliation_digest": "A84-FORGED-LOCAL",
                    "automatic_clear_allowed": True,
                })
                self.assertEqual(result["status"], "BLOCKED")
                self.assertEqual(result["reason"], "INDEPENDENT_INFLIGHT_CLEAR_PROOF_NOT_ENROLLED")
                self.assertFalse(result["requires_checkpoint_save"])
                self.assertFalse(result["executes_action"])
                self.assertFalse(result["external_persisted"])
                self.assertFalse(result["automatic_retry_allowed"])
                self.assertEqual(result["checkpoint"], self.original)
                self.assertEqual(self.claimed, self.original)

    def test_02_patched_positive_label_never_invokes_checkpoint_mutation(self):
        result = self.stage({
            "status": "TERMINAL_EVIDENCE_READY_FOR_HUMAN_CLEAR",
            "terminal_proven": 1,
            "reconciliation_digest": "A84-FORGED-LOCAL",
            "automatic_clear_allowed": False,
        })
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["requires_checkpoint_save"])
        self.assertEqual(self.claimed, self.original)
        # A dormant positive constructor must not survive beneath a gate:
        # a future change to the assessor cannot revive the stale pathway.
        source = inspect.getsource(stage_resolved_inflight_clear)
        self.assertNotIn('"STAGED_CLEAR_READY"', source)
        self.assertNotIn("attach_global_worker_state(", source)

if __name__ == "__main__":
    unittest.main()
