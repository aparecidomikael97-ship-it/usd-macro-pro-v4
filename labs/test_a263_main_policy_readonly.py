"""A263 main protection facts: synthetic offline negatives and live GET invariants."""
from unittest import mock
from tempfile import TemporaryDirectory
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from labs.a263_main_policy_readonly import (
    BASE_URL, NO_GO, REPO, SCHEMA, assess_policy_snapshot, observe_live_policy,
)


SHA = "5744b2b7b17c84331e6f27c569064993ff587782"


def branch(*, protected=False, checks=(), enforcement="off"):
    return {
        "name": "main",
        "commit": {"sha": SHA},
        "protected": protected,
        "protection": {"enabled": protected, "required_status_checks": {
            "enforcement_level": enforcement,
            "contexts": list(checks),
            "checks": [{"context": x} for x in checks],
        }},
    }


def assert_nogo(test, record):
    test.assertEqual(record["schema"], SCHEMA)
    test.assertEqual(record["status"], NO_GO)
    test.assertEqual(record["p0_homologated"], 0)
    for key in ("admin_protection_details_verified", "required_pr_review_verified",
                "bypass_users_verified", "render_permissions_verified",
                "authorizes_send", "permits_merge", "permits_worker",
                "permits_deploy", "release_approved"):
        test.assertIs(record[key], False)


class FakeHttpResponse:
    def __init__(self, body):
        self.status = 200
        self._body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def read(self, size):
        return self._body[:size]


class A263MainProtectionTests(unittest.TestCase):
    def test_01_actual_oct29_main_snapshot_unprotected_and_rulesets_empty(self):
        result = assess_policy_snapshot(branch(), [])
        assert_nogo(self, result)
        self.assertTrue(result["main_response_valid"])
        self.assertEqual(result["main_sha"], SHA)
        self.assertFalse(result["main_protected_visible"])
        self.assertFalse(result["required_checks_visible"])
        self.assertEqual(result["active_repo_rulesets_visible"], 0)
        self.assertIn("MAIN_PROTECTION_NOT_OBSERVED", result["issues"])
        self.assertIn("REQUIRED_CHECKS_NOT_VISIBLE_AS_ENFORCED", result["issues"])
        self.assertIn("NO_ACTIVE_REPOSITORY_RULESET_OBSERVED", result["issues"])

    def test_02_codeowners_and_green_quality_are_not_enforcement(self):
        item = branch()
        item["quality_passed"] = True
        item["codeowners_present"] = True
        result = assess_policy_snapshot(item, [])
        assert_nogo(self, result)
        self.assertFalse(result["main_protected_visible"])

    def test_03_fake_boolean_protected_with_no_required_checks_still_denied(self):
        result = assess_policy_snapshot(branch(protected=True), [])
        assert_nogo(self, result)
        self.assertTrue(result["main_protected_visible"])
        self.assertFalse(result["required_checks_visible"])

    def test_04_checks_visible_but_no_admin_review_or_ruleset_still_denied(self):
        result = assess_policy_snapshot(
            branch(protected=True, checks=("Quality tests",), enforcement="on"),
            [],
        )
        assert_nogo(self, result)
        self.assertTrue(result["required_checks_visible"])
        self.assertIn("ADMIN_REQUIRED_REVIEWS_AND_BYPASS_UNVERIFIED", result["issues"])

    def test_05_active_ruleset_cannot_override_unprotected_branch(self):
        rules = [{"id": 123, "enforcement": "active", "name": "looks secure"}]
        result = assess_policy_snapshot(branch(protected=False), rules)
        assert_nogo(self, result)
        self.assertEqual(result["active_repo_rulesets_visible"], 1)
        self.assertFalse(result["main_protected_visible"])

    def test_06_even_all_local_flags_cannot_authorize_merge_or_deploy(self):
        item = branch(protected=True, checks=("Quality tests",), enforcement="on")
        item["required_reviews"] = 2
        item["approved"] = True
        item["allow_merge"] = True
        item["trusted"] = True
        result = assess_policy_snapshot(item, [{
            "id": 1, "enforcement": "active", "protected": True,
            "bypass_actors": [], "required_status_checks": ["Quality tests"],
        }])
        assert_nogo(self, result)
        self.assertTrue(result["main_protected_visible"])
        self.assertTrue(result["required_checks_visible"])

    def test_07_response_for_wrong_branch_is_not_accepted(self):
        item = branch(protected=True, checks=("Quality tests",), enforcement="on")
        item["name"] = "not-main"
        result = assess_policy_snapshot(item, [])
        assert_nogo(self, result)
        self.assertFalse(result["main_response_valid"])

    def test_08_sha_malformed_or_missing_does_not_prove_branch(self):
        for sha in (None, "main", "a" * 39, "a" * 41, True, ""):
            with self.subTest(sha=sha):
                item = branch(protected=True)
                item["commit"]["sha"] = sha
                result = assess_policy_snapshot(item, [])
                assert_nogo(self, result)
                self.assertFalse(result["main_response_valid"])

    def test_09_malformed_branch_or_rulesets_response_fails_closed(self):
        for response in (None, [], {}, "trusted", {"protected": True}):
            with self.subTest(response=str(response)):
                result = assess_policy_snapshot(response, {"trusted": True})
                assert_nogo(self, result)
                self.assertFalse(result["main_response_valid"])
                self.assertFalse(result["rulesets_collection_valid"])

    def test_10_inactive_ruleset_does_not_prove_enforcement(self):
        result = assess_policy_snapshot(
            branch(protected=False),
            [{"id": 2, "enforcement": "disabled"},
             {"id": 3, "enforcement": "evaluate"}],
        )
        assert_nogo(self, result)
        self.assertEqual(result["active_repo_rulesets_visible"], 0)

    def test_11_only_get_requests_to_exact_two_repository_endpoints(self):
        requests = []
        def fake_urlopen(req, timeout):
            requests.append((req.get_method(), req.full_url, timeout))
            return FakeHttpResponse(
                branch() if req.full_url.endswith("/branches/main") else []
            )
        with mock.patch("labs.a263_main_policy_readonly.urlopen",
                        side_effect=fake_urlopen), mock.patch.dict(
                            os.environ, {"GITHUB_TOKEN": "dummy-secret"}, clear=False
                        ):
            result = observe_live_policy(timeout=3)
        assert_nogo(self, result)
        self.assertEqual([x[0] for x in requests], ["GET", "GET"])
        self.assertEqual(requests[0][1], BASE_URL + "/branches/main")
        self.assertEqual(requests[1][1], BASE_URL + "/rulesets?includes_parents=true")
        self.assertEqual(result["source"], "GITHUB_READ_ONLY_GET_TWO_ENDPOINTS_UNVERIFIED_ADMIN")
        self.assertNotIn("dummy-secret", json.dumps(result))

    def test_12_timeout_invalid_is_rejected(self):
        for timeout in (0, -1, None, "fast", True, 31):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                observe_live_policy(timeout=timeout)

    def test_13_cli_without_live_flag_always_fails_closed_no_network(self):
        p = subprocess.run(
            [sys.executable, "-B", "-m", "labs.a263_main_policy_readonly"],
            cwd=Path(__file__).resolve().parent.parent,
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(p.returncode, 3)
        report = json.loads(p.stdout)
        self.assertEqual(report["p0_homologated"], 0)
        self.assertFalse(report["permits_merge"])
        self.assertFalse(report["permits_deploy"])
        self.assertIn("GITHUB_POLICY_READ_FAILED_CLOSED", report["issues"])

    def test_14_unreadable_live_git_returns_safe_refusal(self):
        with mock.patch("labs.a263_main_policy_readonly.urlopen",
                        side_effect=OSError("fail")):
            # Main never turns an exception into release permission.
            from labs.a263_main_policy_readonly import main
            with mock.patch("sys.argv", ["a263", "--live"]), mock.patch(
                "builtins.print"
            ) as capture:
                self.assertEqual(main(), 3)
                report = json.loads(capture.call_args.args[0])
                self.assertIs(report["permits_deploy"], False)
                self.assertEqual(report["p0_homologated"], 0)

    def test_15_branch_protection_403_remains_unknown_not_green(self):
        # The current integration cannot read /branches/main/protection.
        # The public branch response is enough to observe false, but not
        # to verify all admin-required reviews or bypass permissions.
        result = assess_policy_snapshot(branch(protected=False), [])
        assert_nogo(self, result)
        self.assertFalse(result["admin_protection_details_verified"])


if __name__ == "__main__":
    unittest.main()
