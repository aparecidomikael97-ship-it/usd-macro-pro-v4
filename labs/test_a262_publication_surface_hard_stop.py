"""A262: enforce draft hard-stop ordering and inventory real publish routes."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from labs.a262_publication_surface_hard_stop import (
    GUARD_NAME, NO_GO, SCHEMA, SURFACES,
    inspect_publication_surfaces, inspect_repository,
)


ROOT = Path(__file__).resolve().parent.parent
HOOK = ".github/workflows/render-deploy-control.yml"
RENDER = "render.yaml"


def _sources():
    return {path: (ROOT / path).read_bytes() for path in SURFACES}


def _changed(path, before, after):
    files = _sources()
    old = files[path]
    assert old.count(before) == 1, (path, old.count(before))
    files[path] = old.replace(before, after)
    return files


def _no_go(test, result):
    test.assertEqual(result["schema"], SCHEMA)
    test.assertEqual(result["status"], NO_GO)
    test.assertEqual(result["p0_homologated"], 0)
    for key in ("independently_attested_pipeline", "permits_merge",
                "permits_deploy", "permits_worker", "authorizes_send"):
        test.assertIs(result[key], False)


class A262ReleaseRouteHardStopTests(unittest.TestCase):
    def test_01_current_draft_hook_has_a_hard_stop_before_any_post(self):
        result = inspect_repository(ROOT)
        _no_go(self, result)
        self.assertEqual(result["surface_count"], len(SURFACES))
        self.assertTrue(result["all_sources_present"])
        self.assertTrue(result["github"]["recognized"])
        self.assertTrue(result["github_draft_hard_stop_present"])
        self.assertEqual(result["github"]["webhook_paths"], 1)
        self.assertEqual(result["github"]["guarded_in_draft"], 1)
        self.assertTrue(result["github"]["details"][0]["draft_hard_stop_precedes_hook"])

    def test_02_real_dispatch_and_main_reconcile_trigger_both_mapped(self):
        result = inspect_repository(ROOT)
        _no_go(self, result)
        self.assertTrue(result["github"]["manual_dispatch"])
        self.assertTrue(result["github"]["main_reconcile_push"])
        self.assertTrue(result["reconcile_trigger_observed"])
        self.assertIn("MAIN_RECONCILE_TRIGGER_PRESENT", result["findings"])
        self.assertIn("GITHUB_MANUAL_DISPATCH_PRESENT", result["findings"])

    def test_03_draft_has_stop_but_render_remains_unbound_to_artifact(self):
        result = inspect_repository(ROOT)
        _no_go(self, result)
        self.assertTrue(result["github_draft_hard_stop_present"])
        self.assertTrue(result["render_source_build_observed"])
        self.assertTrue(result["render_auto_deploy_off_configured"])
        self.assertIn("RENDER_SOURCE_BUILD_NOT_A260_ARTIFACT", result["findings"])
        self.assertIn("RENDER_MANUAL_UI_OR_EXTERNAL_HOOK_NOT_VERIFIABLE_FROM_REPO",
                      result["findings"])

    def test_04_removing_early_guard_is_detected_without_positive_status(self):
        data = _changed(HOOK, b"exit 2", b"echo 'green'")
        result = inspect_publication_surfaces(data)
        _no_go(self, result)
        self.assertFalse(result["github_draft_hard_stop_present"])
        self.assertIn("UNGUARDED_OR_UNKNOWN_GITHUB_DEPLOY_HOOK", result["findings"])

    def test_05_exit_zero_is_not_a_safety_gate(self):
        data = _changed(HOOK, b"exit 2", b"exit 0")
        result = inspect_publication_surfaces(data)
        _no_go(self, result)
        self.assertEqual(result["github"]["guarded_in_draft"], 0)

    def test_06_if_always_on_webhook_bypasses_failed_guard(self):
        data = _changed(
            HOOK,
            b"      - name: Trigger Render deploy\n",
            b"      - name: Trigger Render deploy\n        if: ${{ always() }}\n",
        )
        result = inspect_publication_surfaces(data)
        _no_go(self, result)
        self.assertEqual(result["github"]["webhook_paths"], 1)
        self.assertFalse(result["github_draft_hard_stop_present"])

    def test_07_continue_on_error_on_guard_is_detected(self):
        data = _changed(
            HOOK,
            b"      - name: " + GUARD_NAME.encode() + b"\n",
            b"      - name: " + GUARD_NAME.encode() +
                b"\n        continue-on-error: true\n",
        )
        result = inspect_publication_surfaces(data)
        _no_go(self, result)
        self.assertFalse(result["github_draft_hard_stop_present"])

    def test_08_second_publish_job_without_guard_is_detected(self):
        extra = (
            "\n  bypass:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: curl -fsS -X POST \"$RENDER_DEPLOY_HOOK_URL\"\n"
        ).encode()
        data = _sources()
        data[HOOK] += extra
        result = inspect_publication_surfaces(data)
        _no_go(self, result)
        self.assertEqual(result["github"]["webhook_paths"], 2)
        self.assertEqual(result["github"]["guarded_in_draft"], 1)
        self.assertFalse(result["github_draft_hard_stop_present"])

    def test_09_duplicate_yaml_keys_cannot_override_our_guard(self):
        data = _sources()
        data[HOOK] += b"\njobs: {}\n"
        result = inspect_publication_surfaces(data)
        _no_go(self, result)
        self.assertFalse(result["github"]["recognized"])
        self.assertFalse(result["github_draft_hard_stop_present"])

    def test_10_render_auto_deploy_on_cannot_authorize_anything(self):
        data = _changed(RENDER, b"autoDeployTrigger: off",
                        b"autoDeployTrigger: on")
        result = inspect_publication_surfaces(data)
        _no_go(self, result)
        self.assertFalse(result["render_auto_deploy_off_configured"])
        self.assertTrue(result["render_source_build_observed"])

    def test_11_fake_a260_command_in_render_source_is_not_provenance(self):
        data = _changed(
            RENDER, b"pip install -r requirements.txt",
            b"python -m labs.a260_offline_runtime_bundle && pip install -r requirements.txt",
        )
        result = inspect_publication_surfaces(data)
        _no_go(self, result)
        self.assertFalse(result["render_source_build_observed"])

    def test_12_postdeploy_smoke_and_backup_do_not_authorize_deploy(self):
        result = inspect_repository(ROOT)
        _no_go(self, result)
        self.assertTrue(result["after_deploy_probes_observed"])
        self.assertTrue(result["source_backup_only_observed"])
        self.assertTrue(result["release_readiness_only_observed"])
        self.assertIn("WHOLE_SOURCE_ZIP_IS_BACKUP_NOT_RUNTIME_ALLOWLIST",
                      result["findings"])
        self.assertIn("POST_DEPLOY_PROBES_AND_READINESS_ARE_NOT_P0_AUTHORITY",
                      result["findings"])

    def test_13_missing_source_and_unsafe_root_fail_closed(self):
        with TemporaryDirectory(prefix="a262-missing-") as raw:
            result = inspect_repository(Path(raw))
            _no_go(self, result)
            self.assertFalse(result["all_sources_present"])
            self.assertFalse(result["github_draft_hard_stop_present"])
            self.assertFalse(result["render_source_build_observed"])

    def test_14_unsafe_yaml_tags_are_not_executed(self):
        with TemporaryDirectory(prefix="a262-yaml-") as raw:
            marker = Path(raw) / "would-write.txt"
            payload = (
                "!!python/object/apply:builtins.open\n"
                f"- {str(marker)!r}\n"
                "- w\n"
            ).encode()
            data = _sources()
            data[HOOK] = payload
            result = inspect_publication_surfaces(data)
            _no_go(self, result)
            self.assertFalse(result["github"]["recognized"])
            self.assertFalse(marker.exists())

    def test_15_cli_status_is_nonzero_even_for_workflow_with_hard_stop(self):
        p = subprocess.run(
            [sys.executable, "-B", "-m",
             "labs.a262_publication_surface_hard_stop",
             "--source-root", str(ROOT)],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(p.returncode, 2, (p.stdout, p.stderr))
        result = json.loads(p.stdout)
        _no_go(self, result)
        self.assertTrue(result["github_draft_hard_stop_present"])

    def test_16_all_concurrent_audits_are_still_no_go(self):
        data = _sources()
        with ThreadPoolExecutor(max_workers=8) as pool:
            values = list(pool.map(lambda _: inspect_publication_surfaces(data),
                                   range(50)))
        self.assertEqual(len(values), 50)
        for value in values:
            _no_go(self, value)

    @unittest.expectedFailure
    def test_17_red_render_source_deploy_is_not_bound_to_a262_draft_gate(self):
        # A262 only changes the draft GitHub Actions workflow. Direct Render UI,
        # alternative hooks and the actual source-build remain outside that gate.
        current_render = (ROOT / RENDER).read_text(encoding="utf-8")
        self.assertIn("a262_publication_surface_hard_stop", current_render)


if __name__ == "__main__":
    unittest.main()
