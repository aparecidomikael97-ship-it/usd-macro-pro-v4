import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent
WORKFLOW=ROOT/".github"/"workflows"/"quality-tests.yml"

class QualityWorkflowCoverageTests(unittest.TestCase):
    def test_every_root_test_file_is_executed_by_quality_workflow(self):
        text=WORKFLOW.read_text(encoding="utf-8")
        listed=set(re.findall(r"(?m)^\s+(test_[A-Za-z0-9_]+\.py)\s*\\?$",text))
        discovered={p.name for p in ROOT.glob("test_*.py")}
        missing=sorted(discovered-listed)
        self.assertEqual(missing,[],f"Quality workflow omits test files: {missing}")


    def test_core_workflows_use_current_node24_action_generation(self):
        workflow_dir=ROOT/".github"/"workflows"
        names=("quality-tests.yml","autopilot-v107.yml","atlasquant-checkpoint.yml","coleta_automatica.yml","atlasquant-integration-gate.yml","atlasquant-source-parity.yml","atlasquant-ui-smoke.yml")
        joined="\n".join((workflow_dir/name).read_text(encoding="utf-8") for name in names)
        self.assertNotIn("actions/checkout@v4",joined)
        self.assertNotIn("actions/setup-python@v5",joined)
        self.assertNotIn("actions/upload-artifact@v4",joined)
        self.assertIn("actions/checkout@v7",joined)
        self.assertIn("actions/setup-python@v7",joined)
        self.assertIn("actions/upload-artifact@v7",joined)


    def test_production_observability_workflows_are_read_only_and_candidate_safe(self):
        workflow_dir=ROOT/".github"/"workflows"
        health=(workflow_dir/"production-health.yml").read_text(encoding="utf-8")
        browser=(workflow_dir/"production-browser-smoke.yml").read_text(encoding="utf-8")
        for name,src in (("production-health.yml",health),("production-browser-smoke.yml",browser)):
            with self.subTest(name=name):
                self.assertIn("permissions:\n  contents: read",src)
                self.assertNotIn("contents: write",src)
                self.assertNotIn("GITHUB_TOKEN_HISTORICO",src)
                self.assertNotIn("requests.put(",src)
        self.assertIn("branches: [main]",health)
        self.assertIn("branches: [main, atlasquant-integration]",browser)
        self.assertIn("actions/setup-python@v7",browser)
        self.assertIn("actions/upload-artifact@v7",browser)
        self.assertIn("Warm production service",browser)
        self.assertIn("$APP_URL/_stcore/health",browser)
        self.assertIn("for attempt in range(1, 6)",browser)
        self.assertIn("for render_attempt in range(1, 7)",browser)
        self.assertIn('page.on("console"',browser)
        self.assertIn('page.on("pageerror"',browser)
        self.assertIn('"http_attempts": http_attempts',browser)
        self.assertIn('"http_status_history": status_history',browser)
        self.assertIn("reload_response = page.reload",browser)
        self.assertIn("status = reload_response.status",browser)
        self.assertIn('"render_attempts": render_attempts',browser)
        self.assertIn('"page_errors": page_errors[-10:]',browser)
        self.assertIn('"horizontal_overflow_px": horizontal_overflow',browser)
        self.assertIn('document.documentElement.scrollWidth',browser)
        self.assertIn('if horizontal_overflow > 8:',browser)
        self.assertIn('page.reload(wait_until="domcontentloaded"',browser)
        self.assertIn("stMainBlockContainer",browser)
        self.assertIn("stTextInput",browser)
        self.assertIn('"AtlasQuant" in page_title',browser)
        self.assertIn('"AtlasQuant" in body_text',browser)
        self.assertIn("if not rendered:",browser)
        self.assertNotIn("body vazio/curto",browser)


    def test_integration_ui_smoke_is_local_read_only_and_mobile_aware(self):
        src=(ROOT/".github"/"workflows"/"atlasquant-ui-smoke.yml").read_text(encoding="utf-8")
        self.assertIn("atlasquant-integration",src)
        self.assertIn("atlasquant-release-final",src)
        self.assertIn("permissions:\n  contents: read",src)
        self.assertNotIn("contents: write",src)
        self.assertIn('ATLASQUANT_ENV: "LOCAL"',src)
        self.assertIn('ATLASQUANT_AUTH_REQUIRED: "false"',src)
        self.assertIn('ATLASQUANT_OFFLINE_SMOKE: "true"',src)
        self.assertIn('page.locator(".aq-hero").count()',src)
        self.assertIn('"ATLASQUANT" in body_text',src)
        self.assertIn('"Carregando dados macroeconômicos globais" in body_text',src)
        self.assertIn('"hero_count":hero_count',src)
        self.assertIn('"loading_macro":loading_macro',src)
        self.assertIn('"width":390',src)
        self.assertIn('"width":1440',src)
        self.assertIn("horizontal_overflow_px",src)
        self.assertIn("stException",src)
        self.assertIn("actions/upload-artifact@v7",src)
        self.assertNotIn("secrets.",src)



    def test_integration_gate_is_source_only_manual_and_current_main_based(self):
        src=(ROOT/".github"/"workflows"/"atlasquant-integration-gate.yml").read_text(encoding="utf-8")
        self.assertIn("branches: [atlasquant-integration]",src)
        self.assertIn("fetch-depth: 0",src)
        self.assertIn("git fetch origin main --prune",src)
        self.assertIn("merge-base",src)
        self.assertIn("origin/main...HEAD",src)
        self.assertIn("evaluate_integration_candidate",src)
        self.assertIn("actions/checkout@v7",src)
        self.assertIn("actions/setup-python@v7",src)
        self.assertIn("actions/upload-artifact@v7",src)
        self.assertNotIn("contents: write",src)
        self.assertNotIn("git merge",src)
        self.assertNotIn("git push",src)



    def test_runtime_source_parity_workflow_is_read_only_and_integration_based(self):
        src=(ROOT/".github"/"workflows"/"atlasquant-source-parity.yml").read_text(encoding="utf-8")
        self.assertIn("branches: [atlasquant-runtime, atlasquant-integration]",src)
        self.assertIn("permissions:\n  contents: read",src)
        self.assertIn("git fetch origin atlasquant-integration atlasquant-runtime --prune",src)
        self.assertIn('branch=="atlasquant-integration"',src)
        self.assertIn('branch=="atlasquant-runtime"',src)
        self.assertIn("compare_source_trees",src)
        self.assertIn("actions/checkout@v7",src)
        self.assertIn("actions/setup-python@v7",src)
        self.assertIn("actions/upload-artifact@v7",src)
        self.assertNotIn("contents: write",src)
        self.assertNotIn("git push",src)
        self.assertNotIn("update-ref",src)



if __name__=="__main__":
    unittest.main()
