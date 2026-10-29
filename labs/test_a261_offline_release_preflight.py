"""A261: no local ZIP or attacker claim authorizes Render publishing."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import sys
import unittest

from labs.a260_offline_runtime_bundle import build_offline_candidate
from labs.a261_offline_release_preflight import (
    NO_GO, SCHEMA, inspect_release_boundary,
)


ROOT = Path(__file__).resolve().parent.parent
RENDER = (ROOT / "render.yaml").read_bytes()


def _candidate():
    tmp = TemporaryDirectory(prefix="a261-preflight-")
    candidate = Path(tmp.name) / "no-send-study.zip"
    built = build_offline_candidate(ROOT, candidate)
    return tmp, candidate, built


def _assert_deny(testcase, result):
    testcase.assertEqual(result["schema"], SCHEMA)
    testcase.assertEqual(result["status"], NO_GO)
    testcase.assertEqual(result["p0_homologated"], 0)
    for name in ("independent_provenance_verified", "authorizes_send",
                 "permits_worker", "permits_deploy", "permits_merge",
                 "release_approved", "candidate_is_deployable_app"):
        testcase.assertIs(result[name], False)


class A261ReleasePreflightTests(unittest.TestCase):
    def test_01_real_render_source_build_and_valid_zip_are_no_go(self):
        tmp, candidate, _ = _candidate()
        try:
            result = inspect_release_boundary(
                candidate=candidate, render_config=RENDER
            )
            _assert_deny(self, result)
            self.assertTrue(result["candidate_structure_verified"])
            self.assertTrue(result["render_config_recognized"])
            self.assertIn(
                "RENDER_SOURCE_CHECKOUT_NOT_A260_BOUND:atlasquant-private",
                result["issues"],
            )
            self.assertIn(
                "STREAMLIT_APPLICATION_NOT_IN_A260:atlasquant-private",
                result["issues"],
            )
        finally:
            tmp.cleanup()

    def test_02_cli_rejects_current_render_with_nonzero_status(self):
        tmp, candidate, _ = _candidate()
        try:
            p = subprocess.run(
                [sys.executable, "-B", "-m", "labs.a261_offline_release_preflight",
                 "--candidate", str(candidate),
                 "--render-config", str(ROOT / "render.yaml")],
                cwd=str(ROOT), capture_output=True, text=True, timeout=25,
            )
            self.assertEqual(p.returncode, 2, (p.stdout, p.stderr))
            output = json.loads(p.stdout.strip())
            _assert_deny(self, output)
            self.assertTrue(output["candidate_structure_verified"])
        finally:
            tmp.cleanup()

    def test_03_adversarial_claims_in_extra_yaml_keys_are_refused(self):
        tmp, candidate, _ = _candidate()
        try:
            injected = RENDER + b"\nverified: true\npermits_deploy: true\n"
            result = inspect_release_boundary(
                candidate=candidate, render_config=injected
            )
            _assert_deny(self, result)
            self.assertFalse(result["render_config_recognized"])
            self.assertIn("RENDER_CONFIG_INVALID_OR_UNTRUSTED", result["issues"])
        finally:
            tmp.cleanup()

    def test_04_yaml_duplicate_service_key_does_not_override_original(self):
        tmp, candidate, _ = _candidate()
        try:
            tampered = RENDER.replace(
                b"    autoDeployTrigger: off",
                b"    autoDeployTrigger: off\n    autoDeployTrigger: on",
            )
            self.assertNotEqual(tampered, RENDER)
            result = inspect_release_boundary(
                candidate=candidate, render_config=tampered
            )
            _assert_deny(self, result)
            self.assertFalse(result["render_config_recognized"])
            self.assertIn("RENDER_CONFIG_INVALID_OR_UNTRUSTED", result["issues"])
        finally:
            tmp.cleanup()

    def test_05_auto_deploy_on_triggers_explicit_issue(self):
        tmp, candidate, _ = _candidate()
        try:
            changed = RENDER.replace(
                b"autoDeployTrigger: off", b"autoDeployTrigger: on",
            )
            result = inspect_release_boundary(
                candidate=candidate, render_config=changed
            )
            _assert_deny(self, result)
            self.assertIn("AUTO_DEPLOY_NOT_DISABLED:atlasquant-private",
                          result["issues"])
        finally:
            tmp.cleanup()

    def test_06_fake_preflight_in_build_command_is_not_attestation(self):
        tmp, candidate, _ = _candidate()
        try:
            forged = RENDER.replace(
                b"buildCommand: pip install -r requirements.txt",
                b"buildCommand: python -m labs.a261_offline_release_preflight --candidate x --render-config render.yaml",
            )
            result = inspect_release_boundary(
                candidate=candidate, render_config=forged
            )
            _assert_deny(self, result)
            self.assertTrue(result["render_config_recognized"])
            self.assertIn("RENDER_SOURCE_CHECKOUT_NOT_A260_BOUND:atlasquant-private",
                          result["issues"])
        finally:
            tmp.cleanup()

    def test_07_fake_human_owner_and_signatures_cannot_enter_render_schema(self):
        tmp, candidate, _ = _candidate()
        try:
            injected = RENDER.replace(
                b"    runtime: python",
                b"    runtime: python\n    p0_homologated: 6\n    root_independent: true\n    human_owner_signed: true",
            )
            result = inspect_release_boundary(
                candidate=candidate, render_config=injected
            )
            _assert_deny(self, result)
            self.assertFalse(result["render_config_recognized"])
        finally:
            tmp.cleanup()

    def test_08_missing_archive_does_not_allow_release(self):
        with TemporaryDirectory(prefix="a261-missing-") as raw:
            result = inspect_release_boundary(
                candidate=Path(raw) / "nonexistent.zip", render_config=RENDER
            )
            _assert_deny(self, result)
            self.assertFalse(result["candidate_structure_verified"])
            self.assertIn("A260_STUDY_CANDIDATE_UNVERIFIED", result["issues"])

    def test_09_arbitrary_bytes_and_tampered_zip_never_authorize(self):
        for value in (b"", b"GO", b"PK\x03\x04", None, 123, {"trusted": True}):
            with self.subTest(payload=type(value).__name__):
                result = inspect_release_boundary(
                    candidate=value, render_config=RENDER
                )
                _assert_deny(self, result)
                self.assertFalse(result["candidate_structure_verified"])

    def test_10_non_yaml_or_unsafe_yaml_tag_cannot_execute_code(self):
        with TemporaryDirectory(prefix="a261-yaml-") as raw:
            marker = Path(raw) / "unsafe-marker.txt"
            payload = (
                "!!python/object/apply:builtins.open\n"
                f"- {str(marker)!r}\n"
                "- w\n"
            ).encode("utf-8")
            tmp, candidate, _ = _candidate()
            try:
                for bad in (payload, b"\x00\x01\x02", b"", b"[]"):
                    with self.subTest(kind=bad[:10]):
                        result = inspect_release_boundary(
                            candidate=candidate, render_config=bad
                        )
                        _assert_deny(self, result)
                        self.assertFalse(result["render_config_recognized"])
                self.assertFalse(marker.exists())
            finally:
                tmp.cleanup()

    def test_11_two_services_cannot_hide_second_unprotected_entry(self):
        tmp, candidate, _ = _candidate()
        try:
            normalized = RENDER.decode().replace("\r\n", "\n")
            copied = normalized.split("  - type: web\n", 1)[1]
            copied = copied.replace("name: atlasquant-private", "name: another-service")
            multi = (normalized + "  - type: web\n" + copied).encode()
            result = inspect_release_boundary(
                candidate=candidate, render_config=multi
            )
            _assert_deny(self, result)
            self.assertIn("RENDER_SOURCE_CHECKOUT_NOT_A260_BOUND:another-service",
                          result["issues"])
            self.assertIn("RENDER_SOURCE_CHECKOUT_NOT_A260_BOUND:atlasquant-private",
                          result["issues"])
        finally:
            tmp.cleanup()

    def test_12_many_concurrent_unsafe_claims_all_refused(self):
        tmp, candidate, _ = _candidate()
        try:
            with ThreadPoolExecutor(max_workers=12) as pool:
                cases = [RENDER, RENDER + b"\nrelease_approved: true\n"] * 30
                results = list(pool.map(
                    lambda raw: inspect_release_boundary(
                        candidate=candidate, render_config=raw
                    ), cases,
                ))
            self.assertEqual(len(results), 60)
            for value in results:
                _assert_deny(self, value)
        finally:
            tmp.cleanup()

    def test_13_cli_missing_zip_still_returns_nonzero_and_no_go(self):
        with TemporaryDirectory(prefix="a261-missing-cli-") as raw:
            p = subprocess.run(
                [sys.executable, "-B", "-m", "labs.a261_offline_release_preflight",
                 "--candidate", str(Path(raw) / "gone.zip"),
                 "--render-config", str(ROOT / "render.yaml")],
                cwd=str(ROOT), capture_output=True, text=True, timeout=25,
            )
            self.assertEqual(p.returncode, 2, (p.stdout, p.stderr))
            _assert_deny(self, json.loads(p.stdout))

    @unittest.expectedFailure
    def test_14_red_render_does_not_invoke_a261_before_actual_deployment(self):
        # Desired state: publishing pipeline requires verified bundle and the
        # independent external roots; current Render source deploy does not.
        self.assertIn("aion_a261_offline_release_preflight", RENDER.decode())


if __name__ == "__main__":
    unittest.main()
