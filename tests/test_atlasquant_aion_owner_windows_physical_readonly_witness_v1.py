"""Security tests for AION owner-Windows read-only witness."""
from __future__ import annotations

import ast
import inspect
import secrets
import sys
import unittest
from unittest.mock import patch

import atlasquant_aion_owner_windows_physical_readonly_witness_v1 as witness


class ReadonlyPhysicalWitnessTests(unittest.TestCase):
    def test_explicit_scope_required(self):
        cases = [
            [], ["probe.py"], ["probe.py", "--owner-authorized-physical-readonly"],
            ["probe.py", "--owner-authorized-physical-readonly", "g" * 64],
            ["probe.py", "--owner-authorized-physical-readonly", "0" * 32],
            ["probe.py", "--owner-authorized-physical-readonly", "0" * 64, "--install"],
            ["probe.py", "--install", "0" * 64],
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertFalse(witness._source_guard(case, platform="win32"))
        self.assertFalse(witness._source_guard(
            ["probe.py", witness.OPT_IN, "0" * 64], platform="linux"))
        self.assertTrue(witness._source_guard(
            ["probe.py", witness.OPT_IN, "0" * 64], platform="win32"))

    def test_missing_nonce_is_blocked(self):
        result = witness.collect_readonly_witness("missing")
        self.assertEqual(result["state"], "BLOCKED")
        self.assertFalse(result["installer_authorized"])

    def test_no_platform_cannot_collect(self):
        with patch.object(witness.sys, "platform", "linux"):
            result = witness.collect_readonly_witness("a" * 64)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertFalse(result["physical_attestation_verified"])

    def test_result_never_grants_authority(self):
        for nonce in ("", "a" * 63, "A" * 64, "..", "z" * 64):
            result = witness.collect_readonly_witness(nonce)
            for key in (
                "signature_trusted", "physical_attestation_verified",
                "network_deny_verified", "safe_to_resume",
                "installer_authorized", "build_authorized", "deploy_authorized",
            ):
                self.assertIs(result[key], False, key)

    def test_source_contains_no_creation_network_or_resume_primitives(self):
        tree = ast.parse(inspect.getsource(witness))
        forbidden_imports = {
            "subprocess", "socket", "http", "urllib", "requests",
            "winreg", "shutil", "tempfile",
        }
        forbidden_calls = {
            "CreateProcessW", "ResumeThread", "NtResumeProcess",
            "CreateAppContainerProfile", "DeleteAppContainerProfile",
            "FwpmFilterAdd0", "FwpmFilterDeleteById0",
            "SetTokenInformation", "CreateRestrictedToken",
            "CreateJobObjectW", "AssignProcessToJobObject",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(alias.name.split(".")[0], forbidden_imports)
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn((node.module or "").split(".")[0], forbidden_imports)
            if isinstance(node, ast.Attribute):
                self.assertNotIn(node.attr, forbidden_calls)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, forbidden_calls)
        source = inspect.getsource(witness)
        for fragment in (
            '"installer_authorized": False',
            '"physical_attestation_verified": False',
            '"network_deny_verified": False',
            '"child_created": False',
            '"signed_by_enrolled_collector": False',
        ):
            self.assertIn(fragment, source)

    def test_windows_runner_native_readonly_probe(self):
        if sys.platform != "win32":
            self.skipTest("native Windows-only readback")
        result = witness.collect_readonly_witness(secrets.token_hex(32))
        self.assertEqual(result["state"], witness.STATE, result)
        for key in (
            "held_image_file_share_read_only",
            "image_path_matches_current_process",
            "file_identity_stable",
            "digest_pre_post_stable",
            "native_token_readback",
        ):
            self.assertIs(result[key], True, key)
        self.assertEqual(len(result["image_sha256"]), 64)
        self.assertGreater(result["image_size_bytes"], 0)
        for key in (
            "signed_by_enrolled_collector",
            "independent_collector_verified", "physical_attestation_verified",
            "network_probe_executed", "network_deny_verified", "child_created",
            "profile_created", "firewall_modified",
            "safe_to_resume", "installer_authorized",
            "build_authorized", "deploy_authorized",
        ):
            self.assertIs(result[key], False, key)


if __name__ == "__main__":
    unittest.main()
