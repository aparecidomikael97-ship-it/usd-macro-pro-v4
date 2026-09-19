import tempfile
import unittest
from pathlib import Path

from atlasquant_dev_preflight import (
    build_dev_readiness_manifest,
    readiness_manifest_json,
    run_dev_preflight,
)


class DevPreReleaseReadinessTests(unittest.TestCase):
    def test_current_dev_tree_passes_static_preflight(self):
        report=run_dev_preflight()
        self.assertEqual(report["status"],"DEV_PREFLIGHT_OK")
        self.assertEqual(report["failed"],0)
        self.assertTrue(report["manual_runtime_activation_required"])
        self.assertFalse(report["runtime_promotion_performed"])
        names={x["name"] for x in report["checks"]}
        self.assertIn("backtest_ui_integrated",names)
        self.assertIn("backtest_panel_offline",names)
        self.assertIn("runtime_branch_policy",names)
        self.assertIn("tradingview_python_static_parity",names)
        self.assertIn("private_access_gate_integrated",names)
        self.assertIn("role_portal_integrated",names)
        self.assertIn("platform_center_integrated",names)
        self.assertIn("sales_center_integrated",names)
        self.assertIn("account_registry_non_destructive",names)
        self.assertIn("commercial_launch_fail_closed",names)
        self.assertIn("account_change_audit_safe",names)
        self.assertIn("source_integration_gate_manual",names)
        self.assertIn("runtime_source_parity_observational",names)
        self.assertIn("production_observability_read_only",names)
        self.assertIn("commercial_security_evidence_bounded",names)
        self.assertIn("source_checkpoint_excludes_runtime_evidence",names)
        self.assertIn("production_observability_read_only",names)

    def test_missing_tree_is_blocked_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            report=run_dev_preflight(
                root=Path(td),
                parity_report={"status":"OK","passed":1,"failed":0},
            )
        self.assertEqual(report["status"],"DEV_PREFLIGHT_BLOCKED")
        self.assertGreater(report["failed"],0)
        self.assertIn("required_files",report["blockers"])

    def test_green_ci_manifest_stays_pending_runtime_activation(self):
        preflight={
            "status":"DEV_PREFLIGHT_OK",
            "passed":6,
            "failed":0,
        }
        manifest=build_dev_readiness_manifest(
            preflight,
            dev_sha="abc123",
            quality_run_id=123,
            tests_total=645,
            tests_failed=0,
            compile_ok=True,
        )
        self.assertEqual(
            manifest["status"],
            "DEV_VALIDATED_PENDING_RUNTIME_ACTIVATION",
        )
        self.assertTrue(manifest["quality_ok"])
        self.assertTrue(manifest["manual_runtime_activation_required"])
        self.assertTrue(manifest["runtime_health_check_pending"])
        self.assertFalse(manifest["runtime_promotion_performed"])

    def test_failed_ci_blocks_manifest(self):
        preflight={"status":"DEV_PREFLIGHT_OK","passed":6,"failed":0}
        manifest=build_dev_readiness_manifest(
            preflight,
            dev_sha="abc123",
            quality_run_id=123,
            tests_total=645,
            tests_failed=1,
            compile_ok=True,
        )
        self.assertEqual(manifest["status"],"DEV_BLOCKED")
        self.assertIn("QUALITY_TEST_FAILURES",manifest["blockers"])

    def test_manifest_json_keeps_manual_activation_contract(self):
        manifest=build_dev_readiness_manifest(
            {"status":"DEV_PREFLIGHT_OK","passed":6,"failed":0},
            dev_sha="abc123",
            quality_run_id=123,
            tests_total=1,
            tests_failed=0,
            compile_ok=True,
        )
        raw=readiness_manifest_json(manifest)
        self.assertIn('"manual_runtime_activation_required": true',raw)
        self.assertIn('"runtime_promotion_performed": false',raw)


    def test_readiness_manifest_rejects_corrupt_test_counts(self):
        pre={"status":"DEV_PREFLIGHT_OK","passed":7,"failed":0}
        for total,failed in ((float("nan"),0),(float("inf"),0),(-1,0),(10,float("inf")),(10,-1),(10,11),(True,0)):
            with self.subTest(total=total,failed=failed):
                out=build_dev_readiness_manifest(pre,dev_sha="abc",quality_run_id="1",tests_total=total,tests_failed=failed,compile_ok=True)
                self.assertEqual(out["status"],"DEV_BLOCKED")
                self.assertIn("INVALID_TEST_EVIDENCE",out["blockers"])
                self.assertFalse(out["runtime_promotion_performed"])


if __name__=="__main__":
    unittest.main()
