from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_aion_developer_command_policy import (
    SCHEMA,
    build_command_policy_contract,
)


def _runner():
    return {
        "schema": "ATLASQUANT_AION_DEVELOPER_RUNNER_CONTRACT_V1",
        "runner_contract_id": "DEVRUN-1",
        "state": "READY_FOR_RUNNER_DESIGN_REVIEW",
        "resource_budget": {
            "runtime_seconds": 900,
            "memory_mb": 2048,
            "output_bytes": 2_000_000,
            "max_commands": 24,
        },
        "command_plan": [
            {
                "step": "COMPILE_CHANGED_SCOPE",
                "executable": "python",
                "argv": ["-m", "compileall", "-q", "<AUTHORIZED_CHANGED_SCOPE>"],
                "shell": False,
                "cwd": "<ISOLATED_WORKTREE>",
                "network": False,
                "writes_repo": False,
                "writes_repository": False,
                "may_write_ephemeral_cache": True,
                "pycache_prefix": "<SANDBOX_EPHEMERAL_PYCACHE>",
            },
            {
                "step": "RUN_TARGETED_TESTS",
                "executable": "python",
                "argv": ["-m", "unittest", "-q", "<APPROVED_TEST_TARGETS>"],
                "shell": False,
                "cwd": "<ISOLATED_WORKTREE>",
                "network": False,
                "writes_repo": False,
            },
            {
                "step": "VERIFY_DIFF_CHECK",
                "executable": "git",
                "argv": ["diff", "--check"],
                "shell": False,
                "cwd": "<ISOLATED_WORKTREE>",
                "network": False,
                "writes_repo": False,
            },
        ],
        "command_plan_is_data_only": True,
        "shell_allowed": False,
        "network_allowed": False,
        "secrets_allowed": False,
        "repo_write_allowed": False,
        "blockers": [],
        "execution_authorized": False,
        "executor_attached": False,
        "commands_executed": False,
        "writes_files": False,
        "runs_tests": False,
        "network_called": False,
        "subprocess_called": False,
        "automatic_commit": False,
        "automatic_merge": False,
        "automatic_deploy": False,
        "production_change_allowed": False,
        "real_trading_enabled": False,
        "tool_output_is_authority": False,
    }


class AionDeveloperCommandPolicyTests(unittest.TestCase):
    def test_exact_plan_is_only_ready_for_executable_pinning_review(self):
        out = build_command_policy_contract(_runner())
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "READY_FOR_EXECUTABLE_PINNING_REVIEW")
        self.assertEqual(out["allowlist_policy"]["mode"], "EXACT_ARGV_TEMPLATES")
        self.assertFalse(out["allowlist_policy"]["shell_allowed"])
        self.assertFalse(out["allowlist_policy"]["network_allowed"])
        self.assertFalse(out["allowlist_policy"]["repo_write_allowed"])
        self.assertFalse(out["executable_pinning_verified"])
        self.assertFalse(out["os_sandbox_verified"])
        self.assertFalse(out["execution_authorized"])
        self.assertFalse(out["allowlist_policy"]["PATH_LOOKUP_ALLOWED"])
        self.assertTrue(out["allowlist_policy"]["ABSOLUTE_EXECUTABLE_REQUIRED"])
        self.assertTrue(out["allowlist_policy"]["EXECUTABLE_DIGEST_REQUIRED"])
        self.assertFalse(out["allowlist_policy"]["PARENT_ENV_INHERITANCE"])
        self.assertFalse(out["compile_step_executable"])
        self.assertEqual(
            out["validated_command_plan"][0]["pycache_prefix"],
            "<SANDBOX_EPHEMERAL_PYCACHE>",
        )

    def test_executable_substitution_is_blocked(self):
        runner = _runner()
        runner["command_plan"] = deepcopy(runner["command_plan"])
        runner["command_plan"][0]["executable"] = "/tmp/python"
        out = build_command_policy_contract(runner)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("EXECUTABLE_MISMATCH:COMPILE_CHANGED_SCOPE", out["blockers"])

    def test_argv_injection_or_template_drift_is_blocked(self):
        runner = _runner()
        runner["command_plan"] = deepcopy(runner["command_plan"])
        runner["command_plan"][1]["argv"] = [
            "-m", "unittest", "-q", "<APPROVED_TEST_TARGETS>", ";", "touch", "x"
        ]
        out = build_command_policy_contract(runner)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("ARGV_TEMPLATE_MISMATCH:RUN_TARGETED_TESTS", out["blockers"])
        self.assertIn("FORBIDDEN_ARG_SYNTAX:RUN_TARGETED_TESTS", out["blockers"])

    def test_shell_network_write_or_cwd_drift_is_blocked(self):
        runner = _runner()
        runner["command_plan"] = deepcopy(runner["command_plan"])
        runner["command_plan"][2]["shell"] = True
        runner["command_plan"][2]["network"] = True
        runner["command_plan"][2]["writes_repo"] = True
        runner["command_plan"][2]["cwd"] = "/tmp"
        out = build_command_policy_contract(runner)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("SHELL_MUST_BE_FALSE:VERIFY_DIFF_CHECK", out["blockers"])
        self.assertIn("NETWORK_MUST_BE_FALSE:VERIFY_DIFF_CHECK", out["blockers"])
        self.assertIn("REPO_WRITE_MUST_BE_FALSE:VERIFY_DIFF_CHECK", out["blockers"])
        self.assertIn("CWD_MUST_BE_ISOLATED_WORKTREE:VERIFY_DIFF_CHECK", out["blockers"])

    def test_step_injection_or_reordering_is_blocked(self):
        runner = _runner()
        runner["command_plan"] = deepcopy(runner["command_plan"])
        runner["command_plan"].insert(0, {
            "step": "EXTRA",
            "executable": "python",
            "argv": ["-c", "print(1)"],
            "shell": False,
            "cwd": "<ISOLATED_WORKTREE>",
            "network": False,
            "writes_repo": False,
        })
        out = build_command_policy_contract(runner)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("COMMAND_PLAN_LENGTH_MISMATCH", out["blockers"])
        self.assertIn("COMMAND_PLAN_ORDER_OR_STEP_SET_MISMATCH", out["blockers"])

    def test_caller_environment_overrides_are_blocked(self):
        out = build_command_policy_contract(
            _runner(),
            requested_environment={"CUSTOM": "1"},
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("CALLER_ENVIRONMENT_OVERRIDES_NOT_ALLOWED", out["blockers"])

    def test_secret_like_environment_key_is_blocked(self):
        out = build_command_policy_contract(
            _runner(),
            requested_environment={"API_KEY": "value"},
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("SECRET_LIKE_ENVIRONMENT_KEY_NOT_ALLOWED", out["blockers"])

    def test_budget_must_cover_plan(self):
        runner = _runner()
        runner["resource_budget"] = deepcopy(runner["resource_budget"])
        runner["resource_budget"]["max_commands"] = 2
        out = build_command_policy_contract(runner)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("COMMAND_PLAN_EXCEEDS_RESOURCE_BUDGET", out["blockers"])

    def test_test_execution_hazard_is_explicit(self):
        out = build_command_policy_contract(_runner())
        rendered = " ".join(out["hazards"])
        self.assertIn("repository Python code", rendered)
        self.assertIn("operating-system sandbox", rendered)
        self.assertIn("subprocesses", rendered)
        self.assertIn("PROVE_OS_SANDBOX_PROCESS_ISOLATION", out["required_before_future_execution"])

    def test_never_executes_or_authorizes(self):
        out = build_command_policy_contract(_runner())
        for key in (
            "execution_authorized",
            "executor_attached",
            "commands_executed",
            "writes_files",
            "runs_tests",
            "network_called",
            "subprocess_called",
            "automatic_commit",
            "automatic_merge",
            "automatic_deploy",
            "production_change_allowed",
            "real_trading_enabled",
            "tool_output_is_authority",
        ):
            self.assertFalse(out[key])


if __name__ == "__main__":
    unittest.main()
