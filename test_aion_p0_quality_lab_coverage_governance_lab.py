"""LAB-only fail-closed Quality root-test coverage governance.

Do not modify the canonical Quality selection or waive the legacy coverage FAIL.
A missing root test can be LAB-only only if it has an executable step on this
branch's dedicated, read-only matrix CI. No product capabilities are unlocked.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUALITY = ROOT / ".github" / "workflows" / "quality-tests.yml"
DEDICATED = ROOT / ".github" / "workflows" / "aion-p0-quality-lab-coverage-governance.yml"
LEGACY = ROOT / "test_quality_workflow_coverage.py"
LAB_ONLY = (
    "test_aion_m71_execution_fresh_source_denial_lab",
    "test_aion_p0_h0_boundary_drift_mutations_lab",
    "test_aion_p0_h0_custody_two_domain_model_lab",
    "test_aion_p0_h0_iam_finops_preflight_lab",
    "test_aion_p0_h0_sqlite_startup_observer_lab",
    "test_aion_p0_h0_third_anchor_design_review_lab",
    "test_aion_p0_m71_original_stale_gate_safety_negative_lab",
    "test_aion_p0_original_six_evidence_matrix_lab",
    "test_aion_p0_original_sqlite_compat_concurrency_restore_lab",
    "test_aion_p0_quality_85_causal_inventory_lab",
    "test_aion_p0_sqlite_authority_budget_owner_thread_lab",
    "test_aion_p0_sqlite_chat_store_owner_thread_lab",
    "test_aion_p0_sqlite_execution_restore_hardstop_lab",
    "test_aion_p0_sqlite_nested_transaction_denial_lab",
    "test_aion_p0_sqlite_owner_thread_denial_lab",
    "test_aion_p0_sqlite_saga_owner_thread_lab",
    "test_aion_p0_staged_host_sqlite_cleanup_lab",
    "test_aion_p0_outbox_saga_internal_state_lab",
    "test_aion_p0_outbox_saga_cas_retry_recovery_lab",
    "test_aion_p0_outbox_saga_historical_reconcile_cas_lab",
    "test_aion_p0_budget_saga_trust_boundary_lab",
    "test_aion_p0_quality_lab_coverage_governance_lab",
)


class AIONP0QualityLabCoverageGovernanceTests(unittest.TestCase):
    def test_no_unclassified_root_test_file(self):
        quality = QUALITY.read_text(encoding="utf-8")
        listed = set(re.findall(r"(?m)^\s+(test_[A-Za-z0-9_]+\.py)\s*\\?$", quality))
        discovered = {p.name for p in ROOT.glob("test_*.py")}
        omitted = discovered - listed
        expected = {module + ".py" for module in LAB_ONLY}
        self.assertEqual(len(LAB_ONLY), len(set(LAB_ONLY)), "duplicate LAB audit module")
        self.assertEqual(omitted, expected,
                         "No implicit exclusions; update both audit and CI after any change")
        self.assertFalse(expected & listed, "LAB file included twice")

    def test_every_omitted_module_has_real_unittest_step(self):
        content = DEDICATED.read_text(encoding="utf-8")
        executed = re.findall(
            r"(?m)^\s+run:\s+python -B -m unittest -v (test_[A-Za-z0-9_]+)\s*$",
            content,
        )
        self.assertEqual(set(executed), set(LAB_ONLY),
                         "Each LAB module requires a literal executable unittest step")
        self.assertEqual(len(executed), len(LAB_ONLY),
                         "Duplicate, absent or unrecognized CI step")

    def test_runner_is_read_only_two_os_and_branch_scoped(self):
        content = DEDICATED.read_text(encoding="utf-8")
        self.assertIn("on:\n  push:\n    branches: [lab/aion-p0-quality-governance-20261019]", content)
        self.assertIn("permissions:\n  contents: read", content)
        self.assertIn("os: [ubuntu-latest, windows-latest]", content)
        self.assertIn("persist-credentials: false", content)
        self.assertIn("actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", content)
        self.assertIn("actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97", content)
        for forbidden in ("contents: write", "id-token: write", "secrets.",
                          "deploy", "workflow_run:", "schedule:", "curl "):
            self.assertNotIn(forbidden, content,
                             "LAB runner must not mutate systems or invoke external providers")

    def test_legacy_quality_coverage_red_remains_untouched(self):
        legacy = LEGACY.read_text(encoding="utf-8")
        self.assertIn("def test_every_root_test_file_is_executed_by_quality_workflow", legacy)
        self.assertIn("self.assertEqual(missing,[],", legacy)
        self.assertNotIn("@unittest.skip", legacy)
        self.assertNotIn("xfail", legacy)
        self.assertIn("python -m unittest -q", QUALITY.read_text(encoding="utf-8"))

    def test_no_external_producer_enrollment_disguised_as_coverage(self):
        outbox = (ROOT / "atlasquant_aion_execution_outbox.py").read_text(encoding="utf-8")
        saga = (ROOT / "atlasquant_aion_execution_saga.py").read_text(encoding="utf-8")
        self.assertIn("INDEPENDENT_PRODUCER_NOT_ENROLLED", outbox)
        self.assertIn("INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED", saga)
        self.assertIn("INDEPENDENT_PRODUCER_NO_EFFECT_FENCE_NOT_ENROLLED", saga)


if __name__ == "__main__":
    unittest.main()
