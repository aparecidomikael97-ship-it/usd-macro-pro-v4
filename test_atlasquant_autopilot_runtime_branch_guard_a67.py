"""A67: negative test of the actual scheduled Autopilot import boundary.

One subprocess per env combination ensures module globals are reinitialized.
No GitHub token, provider key, network call, runtime PUT, Worker, trade or deploy.
The shared runtime resolver retains its legacy/custom branch compatibility;
only this specifically privileged scheduled writer must be pinned.
"""
import os
import subprocess
import sys
import unittest


IMPORT_CODE = """
import socket
def deny_network(*args, **kwargs):
    raise AssertionError("A67_NETWORK_FORBIDDEN")
socket.socket.connect = deny_network
socket.socket.connect_ex = deny_network
import autopilot_v107
print("SELECTED_RUNTIME_BRANCH=" + autopilot_v107.BRANCH)
"""


class AutopilotPinnedDataBranchA67Tests(unittest.TestCase):
    def check(self, *, explicit, legacy):
        env = os.environ.copy()
        env.update({
            "GITHUB_DATA_BRANCH": explicit,
            "GITHUB_BRANCH_HISTORICO": legacy,
            "GITHUB_TOKEN_HISTORICO": "",
            "GITHUB_TOKEN": "",
            "CHAVE_FRED": "",
            "CHAVE_TWELVE_DATA": "",
            "CHAVE_NEWSAPI": "",
            "CHAVE_EODHD": "",
        })
        return subprocess.run(
            [sys.executable, "-c", IMPORT_CODE],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            env=env,
            capture_output=True,
            text=True,
            timeout=35,
            check=False,
        )

    def assert_pinned(self, explicit, legacy):
        result = self.check(explicit=explicit, legacy=legacy)
        self.assertEqual(result.returncode, 0, result.stderr[-1400:])
        self.assertIn("SELECTED_RUNTIME_BRANCH=atlasquant-runtime", result.stdout)

    def assert_denied(self, explicit, legacy):
        result = self.check(explicit=explicit, legacy=legacy)
        self.assertNotEqual(result.returncode, 0, result.stdout[-800:])
        self.assertIn("AUTOPILOT_RUNTIME_BRANCH_NOT_APPROVED", result.stderr)
        self.assertNotIn("A67_NETWORK_FORBIDDEN", result.stderr)

    def test_01_production_writer_still_uses_dedicated_runtime_branch(self):
        self.assert_pinned("atlasquant-runtime", "atlasquant-runtime")

    def test_02_release_code_branch_is_never_an_autopilot_data_sink(self):
        self.assert_denied("atlasquant-final-release-prep", "atlasquant-runtime")

    def test_03_arbitrary_non_code_branch_name_cannot_redirect_writer(self):
        self.assert_denied("feature/unsafe-output", "atlasquant-runtime")

    def test_04_legacy_env_cannot_redirect_to_integration_code_branch(self):
        self.assert_denied("", "atlasquant-integration")

    def test_05_legacy_main_alias_is_still_redirected_to_runtime(self):
        # Retain historical migration semantics: the resolver maps main
        # to atlasquant-runtime; the actual writer remains pinned.
        self.assert_pinned("main", "main")


if __name__ == "__main__":
    unittest.main()
