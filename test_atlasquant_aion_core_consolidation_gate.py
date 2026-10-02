import unittest
from datetime import datetime, timezone

from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_consolidation_gate import (
    consolidate_runtime_knowledge,
    consolidation_policy,
)

NOW = datetime(2026, 10, 2, 9, 30, tzinfo=timezone.utc)


def _row(ref, *, claim="build", contradicts=False, observed_at=None):
    return {
        "claim": claim,
        "truth_state": "CONFIRMED",
        "source": "runtime",
        "source_ref": ref,
        "time_sensitive": observed_at is not None,
        "observed_at": observed_at or NOW.isoformat(),
        "supports_claim": not contradicts,
        "contradicts_claim": contradicts,
    }


class AionCoreConsolidationGateTests(unittest.TestCase):
    def test_policy_keeps_all_automatic_authority_disabled(self):
        policy = consolidation_policy()
        self.assertTrue(policy["runtime_validation_required"])
        self.assertTrue(policy["provenance_required"])
        self.assertTrue(policy["trust_assessment_required"])
        self.assertTrue(policy["memory_access_policy_required"])
        self.assertFalse(policy["automatic_memory_write"])
        self.assertFalse(policy["automatic_memory_promotion"])
        self.assertFalse(policy["automatic_checkpoint_stage"])
        self.assertFalse(policy["execution_authority"])

    def test_single_source_stays_candidate_but_is_review_ready(self):
        result = consolidate_runtime_knowledge(
            tenant_id="tenant:test",
            runtime_domain=Domain.ADMIN,
            rows=[_row("runtime-build:a")],
            now=NOW,
        )
        self.assertEqual(result["status"], "CONSOLIDATED")
        self.assertTrue(result["checkpoint_review_ready"])
        self.assertEqual(len(result["memory_candidates"]), 1)
        candidate = result["memory_candidates"][0]
        self.assertEqual(candidate["trust_status"], "WEAKLY_SUPPORTED")
        self.assertEqual(candidate["recommended_state"], "CANDIDATE")
        self.assertEqual(candidate["memory_candidate"]["state"], "CANDIDATE")
        self.assertFalse(candidate["memory_written"])
        self.assertTrue(candidate["provenance_ids"])
        self.assertTrue(candidate["evidence_ids"])

    def test_two_independent_sources_recommend_validation_without_promoting(self):
        result = consolidate_runtime_knowledge(
            tenant_id="tenant:test",
            runtime_domain=Domain.ADMIN,
            rows=[
                _row("runtime-build:a"),
                _row("runtime-build:b"),
            ],
            now=NOW,
        )
        self.assertEqual(result["status"], "CONSOLIDATED")
        candidate = result["memory_candidates"][0]
        self.assertEqual(candidate["trust_status"], "SUPPORTED")
        self.assertEqual(candidate["recommended_state"], "VALIDATED")
        self.assertEqual(candidate["memory_candidate"]["state"], "CANDIDATE")
        self.assertTrue(candidate["promotion_requires_explicit_review"])
        self.assertFalse(result["memory_auto_promotion"])

    def test_independent_conflict_blocks_review_readiness(self):
        result = consolidate_runtime_knowledge(
            tenant_id="tenant:test",
            runtime_domain=Domain.ADMIN,
            rows=[
                _row("runtime-build:support"),
                _row("runtime-build:conflict", contradicts=True),
            ],
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checkpoint_review_ready"])
        candidate = result["memory_candidates"][0]
        self.assertEqual(candidate["trust_status"], "CONFLICTING")
        self.assertEqual(candidate["recommended_state"], "CONFLICTING")
        self.assertTrue(
            any(x.startswith("TRUST_CONFLICTING:") for x in result["blockers"])
        )

    def test_realtime_stale_evidence_blocks_review_readiness(self):
        result = consolidate_runtime_knowledge(
            tenant_id="tenant:test",
            runtime_domain=Domain.ADMIN,
            rows=[
                _row(
                    "runtime-build:old",
                    observed_at="2026-09-29T09:00:00+00:00",
                )
            ],
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        candidate = result["memory_candidates"][0]
        self.assertEqual(candidate["trust_status"], "STALE_EVIDENCE")
        self.assertEqual(candidate["recommended_state"], "STALE")

    def test_missing_provenance_reference_blocks_entire_consolidation(self):
        result = consolidate_runtime_knowledge(
            tenant_id="tenant:test",
            runtime_domain=Domain.ADMIN,
            rows=[{
                "claim": "build",
                "truth_state": "CONFIRMED",
                "source": "runtime",
                "source_ref": "",
            }],
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("NIGHTSHIFT_VALIDATION_BLOCKED", result["blockers"])
        self.assertEqual(result["memory_candidates"], [])
        self.assertFalse(result["checkpoint_review_ready"])

    def test_domain_memory_candidate_is_bound_to_same_tenant_and_domain(self):
        result = consolidate_runtime_knowledge(
            tenant_id="tenant:alpha",
            runtime_domain=Domain.BUSINESS,
            rows=[_row("business:metric:1", claim="revenue-evidence")],
            now=NOW,
        )
        candidate = result["memory_candidates"][0]
        memory = candidate["memory_candidate"]
        self.assertEqual(memory["tenant_id"], "tenant:alpha")
        self.assertEqual(memory["domain_id"], "NEGOCIOS")
        self.assertEqual(memory["layer"], "DOMAIN")
        self.assertTrue(candidate["memory_access"]["allowed"])

    def test_digest_is_deterministic_for_same_inputs(self):
        rows = [_row("runtime-build:a"), _row("runtime-build:b")]
        first = consolidate_runtime_knowledge(
            tenant_id="tenant:test",
            runtime_domain=Domain.ADMIN,
            rows=rows,
            now=NOW,
        )
        second = consolidate_runtime_knowledge(
            tenant_id="tenant:test",
            runtime_domain=Domain.ADMIN,
            rows=rows,
            now=NOW,
        )
        self.assertEqual(
            first["consolidation_digest"],
            second["consolidation_digest"],
        )
        self.assertEqual(first["memory_candidates"], second["memory_candidates"])

    def test_no_execution_or_external_persistence_is_authorized(self):
        result = consolidate_runtime_knowledge(
            tenant_id="tenant:test",
            runtime_domain=Domain.ADMIN,
            rows=[_row("runtime-build:a")],
            now=NOW,
        )
        self.assertFalse(result["checkpoint_auto_stage"])
        self.assertFalse(result["memory_auto_write"])
        self.assertFalse(result["memory_auto_promotion"])
        self.assertFalse(result["external_persisted"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["external_action_executed"])


if __name__ == "__main__":
    unittest.main()
