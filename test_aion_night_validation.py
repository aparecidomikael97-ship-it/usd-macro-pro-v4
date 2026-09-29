import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parent
MODULE_PATH = ROOT / "tools" / "aion_night_validation.py"
SPEC = importlib.util.spec_from_file_location("aion_night_validation", MODULE_PATH)
night = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = night
SPEC.loader.exec_module(night)


class AionNightValidationTests(unittest.TestCase):
    def test_quick_plan_is_fixed_local_and_skips_full_discover(self):
        steps = night.build_steps(full=False)
        names = [x.name for x in steps]
        self.assertEqual(
            names,
            ["critical_core", "adversarial_core", "compileall", "git_diff_check"],
        )
        flattened = " ".join(" ".join(x.command) for x in steps).lower()
        for banned in (
            "pip install",
            "npm install",
            "curl ",
            "wget ",
            "http://",
            "https://",
            "openai",
            "anthropic",
            "deploy",
            "git merge",
            "git push",
        ):
            self.assertNotIn(banned, flattened)

    def test_full_plan_includes_discover_and_real_adversarial_suites(self):
        steps = night.build_steps(full=True)
        by_name = {x.name: x for x in steps}
        self.assertIn("full_unittest_discover", by_name)
        adversarial = " ".join(by_name["adversarial_core"].command)
        self.assertIn("test_atlasquant_aion_security_adversarial", adversarial)
        self.assertIn("test_atlasquant_aion_hardening", adversarial)
        self.assertIn("test_atlasquant_aion_post_audit", adversarial)
        self.assertIn("test_atlasquant_aion_chaos_recovery", adversarial)
        self.assertIn("test_atlasquant_aion_core_independence", adversarial)
        self.assertIn("test_atlasquant_aion_global_worker_readiness", adversarial)
        self.assertIn("test_atlasquant_aion_global_worker_live_verification", adversarial)
        self.assertIn("test_atlasquant_aion_global_worker_supervision", adversarial)
        self.assertIn("test_atlasquant_aion_global_worker_recovery_closure", adversarial)
        self.assertIn("test_atlasquant_aion_global_worker_incident_reconciliation", adversarial)

    def test_report_fails_closed_if_any_step_is_not_pass(self):
        report = night.build_report(
            root=ROOT,
            full=True,
            results=[
                {"name": "a", "status": "PASS"},
                {"name": "b", "status": "FAIL"},
                {"name": "c", "status": "TIMEOUT"},
            ],
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["failed_steps"], ["b", "c"])
        self.assertEqual(report["cost_mode"], "ZERO_COST_DEFAULT")
        self.assertFalse(report["network_actions_performed"])
        self.assertFalse(report["deploy_performed"])
        self.assertFalse(report["real_trading_performed"])

    def test_report_path_cannot_escape_repository(self):
        with self.assertRaises(ValueError):
            night._resolve_report_path(ROOT, str(ROOT.parent / "outside.json"))
        inside = night._resolve_report_path(ROOT, "aion-night-validation-report.json")
        self.assertEqual(inside.parent, ROOT.resolve())

    def test_output_redaction_masks_common_secret_assignments(self):
        rendered = night._redact(
            "token=abc123 api_key:xyz password=hunter2 secret=value "
            "GITHUB_TOKEN_HISTORICO=gh-secret AUTHORIZATION_HEADER=bearer-secret"
        )
        for value in (
            "abc123",
            "xyz",
            "hunter2",
            "value",
            "gh-secret",
            "bearer-secret",
        ):
            self.assertNotIn(value, rendered)
        self.assertGreaterEqual(rendered.count("[REDACTED]"), 6)


if __name__ == "__main__":
    unittest.main()
