from __future__ import annotations
import unittest

from atlasquant_aion_digital_twin import (
    new_digital_twin, record_twin_observation, digital_twin_summary,
)


class AtlasQuantAionDigitalTwinTests(unittest.TestCase):
    def _twin(self):
        return new_digital_twin(
            "Mudança segura",
            baseline_ref="main@abc",
            candidate_ref="branch@def",
            scope=["atlasquant_aion_admin.py"],
            dependencies=["checkpoint:v12"],
            expected_impacts=["development-ui"],
            rollback_plan="Reverter commit candidato.",
            created_at="2026-09-25T18:00:00+00:00",
        )

    def test_twin_is_simulation_only(self):
        twin=self._twin()
        self.assertTrue(twin["simulation_only"])
        self.assertFalse(twin["production_touched"])
        self.assertFalse(twin["automatic_action"])

    def test_observation_requires_evidence_and_uncertainty_for_ready_state(self):
        twin=self._twin()
        twin=record_twin_observation(
            twin,area="tests",claim="Suite verde",impact="HIGH",
            baseline_value="2040 tests",candidate_value="2050 tests",
            uncertainty_pct=0,evidence_refs=["ci:123"],
        )
        self.assertEqual(twin["state"],"READY_FOR_EVALUATION")
        self.assertFalse(twin["production_touched"])

    def test_missing_evidence_keeps_twin_incomplete(self):
        twin=self._twin()
        twin=record_twin_observation(
            twin,area="tests",claim="Suposta melhora",impact="HIGH",
            uncertainty_pct=10,evidence_refs=[],
        )
        self.assertEqual(twin["state"],"EVIDENCE_INCOMPLETE")

    def test_critical_blocker_blocks_twin(self):
        twin=self._twin()
        twin=record_twin_observation(
            twin,area="security",claim="Regressão crítica",impact="CRITICAL",
            uncertainty_pct=0,evidence_refs=["test:security"],critical_blocker=True,
        )
        self.assertEqual(twin["state"],"BLOCKED")
        self.assertEqual(digital_twin_summary([twin])["blocked"],1)


if __name__=="__main__":
    unittest.main()
