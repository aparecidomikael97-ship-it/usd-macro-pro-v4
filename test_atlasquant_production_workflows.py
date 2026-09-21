import unittest
from pathlib import Path


class AtlasQuantProductionWorkflowContractTests(unittest.TestCase):
    def test_health_workflow_remains_read_only_and_checks_both_endpoints(self):
        text=Path(".github/workflows/production-health.yml").read_text(encoding="utf-8")
        self.assertIn("branches: [main]",text)
        self.assertIn("contents: read",text)
        self.assertNotIn("contents: write",text)
        self.assertIn('/_stcore/health',text)
        self.assertIn('$APP_URL/',text)
        self.assertIn('test "$code" = "200"',text)

    def test_browser_smoke_keeps_fast_home_and_safety_contract(self):
        text=Path(".github/workflows/production-browser-smoke.yml").read_text(encoding="utf-8")
        self.assertIn("branches: [main, atlasquant-integration]",text)
        self.assertIn("contents: read",text)
        self.assertNotIn("contents: write",text)
        self.assertIn("ATLASQUANT_HOME_SNAPSHOT_V1",text)
        self.assertIn('age <= 120',text)
        self.assertIn('get("real_orders") is False',text)
        self.assertIn('get("automatic_execution") is False',text)
        self.assertIn('"desktop"',text)
        self.assertIn('"mobile"',text)
        self.assertIn('"Pixel 7"',text)
        self.assertIn("MARKET INTELLIGENCE PLATFORM",text)
        self.assertIn("Safety Core monitorado",text)


    def test_app_deploy_marker_has_explicit_environment_fallbacks(self):
        src=Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertIn('os.getenv("RENDER_GIT_COMMIT","")',src)
        self.assertIn('os.getenv("ATLASQUANT_DEPLOY_COMMIT","")',src)
        self.assertIn('os.getenv("GIT_COMMIT","")',src)
        self.assertIn('id="atlasquant-deploy-marker"',src)
        self.assertIn('["git","rev-parse","HEAD"]',src)
        self.assertIn('re.fullmatch(r"[0-9a-fA-F]{40}",candidate)',src)

    def test_browser_smoke_separates_deploy_identity_from_latency_failure(self):
        text=Path(".github/workflows/production-browser-smoke.yml").read_text(encoding="utf-8")
        self.assertIn("deploy_identity_ok",text)
        self.assertIn("source_build == expected_build",text)
        self.assertIn("atlasquant-source-build-marker",text)
        self.assertIn("deploy_identity_ok and auth_inputs < 1 and measured_ui_ms is not None and measured_ui_ms > 30000",text)
        self.assertIn("measured_ui_ms_excluding_deploy_wait",text)
        self.assertIn("Do not attribute Render deployment wait",text)

    def test_browser_smoke_defines_identity_before_reporting_it(self):
        text=Path(".github/workflows/production-browser-smoke.yml").read_text(encoding="utf-8")
        assign=text.index("deploy_identity_ok = bool(source_build and source_build == expected_build)")
        report=text.index('"deploy_identity_ok": deploy_identity_ok')
        self.assertLess(assign,report)
        self.assertIn("measured_ui_ms_excluding_deploy_wait",text)
        self.assertIn("meaningful_ms) - int(deploy_wait_ms",text)

    def test_browser_smoke_uses_source_bundle_identity_when_git_metadata_is_missing(self):
        text=Path(".github/workflows/production-browser-smoke.yml").read_text(encoding="utf-8")
        self.assertIn("short_source_fingerprint",text)
        self.assertIn("expected_source_build",text)
        self.assertIn("atlasquant-source-build-marker",text)
        self.assertIn("deploy_seen_builds",text)
        self.assertIn("source_build != expected_build",text)
        self.assertIn("uses: actions/checkout@v7",text)

    def test_app_exposes_source_bundle_marker_before_fast_home_can_stop(self):
        src=Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        marker=src.index('id="atlasquant-source-build-marker"')
        fast=src.index("load_home_snapshot(",marker)
        self.assertLess(marker,fast)


    def test_browser_smoke_exposes_checkout_modules_to_tmp_runner(self):
        text=Path(".github/workflows/production-browser-smoke.yml").read_text(encoding="utf-8")
        self.assertIn('PYTHONPATH="$GITHUB_WORKSPACE',text)
        self.assertIn("python /tmp/atlasquant_browser_smoke.py",text)
        self.assertIn("from atlasquant_build_identity import short_source_fingerprint",text)



if __name__=="__main__":
    unittest.main()
