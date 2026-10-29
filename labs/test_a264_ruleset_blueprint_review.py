"""A264: ensure an admin-facing policy cannot silently weaken main freeze."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from labs.a264_ruleset_blueprint_review import (
    BLUEPRINT_PATH, NO_GO, SCHEMA, review_blueprint, review_repository,
)
from labs.a263_main_policy_readonly import assess_policy_snapshot


ROOT = Path(__file__).resolve().parent.parent
PROPOSAL = json.loads((ROOT / BLUEPRINT_PATH).read_text("utf-8"))
OWNERS = (ROOT / ".github/CODEOWNERS").read_text("utf-8")
QUALITY = (ROOT / ".github/workflows/quality-tests.yml").read_text("utf-8")


def _analyze(payload=None, *, owners=OWNERS, quality=QUALITY):
    return review_blueprint(
        PROPOSAL if payload is None else payload,
        codeowners_text=owners, quality_text=quality,
    )


class A264AdminBlueprintContractTests(unittest.TestCase):
    def assert_no_authority(self, data):
        self.assertEqual(data["schema"], SCHEMA)
        self.assertEqual(data["status"], NO_GO)
        self.assertEqual(data["p0_homologated"], 0)
        for key in (
            "authorizes_send", "permits_merge", "permits_worker",
            "permits_deploy", "admin_ruleset_applied_verified",
            "main_protection_applied_verified",
            "independent_human_reviewer_confirmed",
            "quality_context_verified_in_required_checks_ui",
        ):
            self.assertIs(data[key], False)

    def test_01_actual_git_repo_proposal_is_structurally_valid_only(self):
        result = review_repository(ROOT)
        self.assert_no_authority(result)
        self.assertTrue(result["proposal_structure_valid"])
        self.assertEqual(result["proposal_issues"], [])
        self.assertEqual(result["required_quality_context_candidate"], "test")
        self.assertEqual(result["github_actions_integration_id_candidate"], 15368)

    def test_02_current_main_still_not_protected_by_proposal_file(self):
        result = assess_policy_snapshot({
            "name": "main",
            "commit": {"sha": "5744b2b7b17c84331e6f27c569064993ff587782"},
            "protected": False,
            "protection": {
                "required_status_checks": {
                    "enforcement_level": "off",
                    "contexts": [], "checks": [],
                },
            },
        }, [])
        self.assertFalse(result["main_protected_visible"])
        self.assertFalse(result["permits_merge"])
        self.assertFalse(_analyze()["admin_ruleset_applied_verified"])

    def test_03_bypass_actor_cannot_be_added(self):
        policy = copy.deepcopy(PROPOSAL)
        policy["bypass_actors"] = [{
            "actor_type": "RepositoryRole", "actor_id": 5,
            "bypass_mode": "always",
        }]
        result = _analyze(policy)
        self.assert_no_authority(result)
        self.assertFalse(result["proposal_structure_valid"])
        self.assertIn("BYPASS_ACTORS_NOT_EMPTY", result["proposal_issues"])

    def test_04_downgrading_enforcement_fails(self):
        for level in ("disabled", "evaluate", "green", True):
            with self.subTest(level=level):
                policy = copy.deepcopy(PROPOSAL)
                policy["enforcement"] = level
                result = _analyze(policy)
                self.assertFalse(result["proposal_structure_valid"])
                self.assert_no_authority(result)

    def test_05_only_main_must_be_targeted(self):
        for include, exclude in (
            (["~ALL"], []),
            (["refs/heads/dev"], []),
            (["refs/heads/main"], ["refs/heads/main"]),
        ):
            with self.subTest(includes=include):
                p = copy.deepcopy(PROPOSAL)
                p["conditions"]["ref_name"] = {
                    "include": include, "exclude": exclude,
                }
                result = _analyze(p)
                self.assertFalse(result["proposal_structure_valid"])
                self.assertIn("MAIN_TARGET_NOT_EXACT", result["proposal_issues"])

    def test_06_deleting_branch_and_force_push_must_be_vetoed(self):
        for type_name in ("deletion", "non_fast_forward"):
            with self.subTest(rule=type_name):
                p = copy.deepcopy(PROPOSAL)
                p["rules"] = [
                    rule for rule in p["rules"] if rule["type"] != type_name
                ]
                self.assertFalse(_analyze(p)["proposal_structure_valid"])

    def test_07_independent_approval_count_cannot_be_zero(self):
        p = copy.deepcopy(PROPOSAL)
        rule = next(r for r in p["rules"] if r["type"] == "pull_request")
        rule["parameters"]["required_approving_review_count"] = 0
        result = _analyze(p)
        self.assert_no_authority(result)
        self.assertIn(
            "PR_APPROVAL_OR_INDEPENDENT_REVIEW_WEAKENED",
            result["proposal_issues"],
        )

    def test_08_stale_last_push_and_codeowner_checks_cannot_be_disabled(self):
        for key in (
            "dismiss_stale_reviews_on_push", "require_code_owner_review",
            "require_last_push_approval", "required_review_thread_resolution",
        ):
            with self.subTest(key=key):
                p = copy.deepcopy(PROPOSAL)
                next(r for r in p["rules"] if r["type"] == "pull_request")[
                    "parameters"
                ][key] = False
                self.assertFalse(_analyze(p)["proposal_structure_valid"])

    def test_09_required_status_checks_pin_actual_quality_job_and_app(self):
        for key, changed in (
            ("strict_required_status_checks_policy", False),
            ("required_status_checks", []),
            ("required_status_checks", [{"context": "fake-green"}]),
            ("required_status_checks", [{"context": "test", "integration_id": 7}]),
        ):
            with self.subTest(key=key, changed=str(changed)):
                p = copy.deepcopy(PROPOSAL)
                next(r for r in p["rules"] if r["type"] == "required_status_checks")[
                    "parameters"
                ][key] = changed
                result = _analyze(p)
                self.assert_no_authority(result)
                self.assertIn(
                    "REQUIRED_QUALITY_TEST_NOT_PINNED",
                    result["proposal_issues"],
                )

    def test_10_missing_quality_job_or_main_pr_trigger_cannot_be_approved(self):
        variations = (
            QUALITY.replace("  test:\n", "  other:\n"),
            QUALITY.replace("branches: [main]", "branches: [sandbox]"),
            "",
        )
        for item in variations:
            with self.subTest(variant=item[:20]):
                self.assertFalse(_analyze(quality=item)["proposal_structure_valid"])

    def test_11_removing_codeowner_workflow_or_file_ownership_is_detected(self):
        for content in (
            OWNERS.replace("/.github/workflows/ @aparecidomikael97-ship-it", ""),
            OWNERS.replace("/.github/CODEOWNERS @aparecidomikael97-ship-it", ""),
            "",
        ):
            with self.subTest(content=content[:22]):
                self.assertFalse(_analyze(owners=content)["proposal_structure_valid"])

    def test_12_extra_trusted_or_deploy_claims_do_not_masquerade_as_rules(self):
        p = copy.deepcopy(PROPOSAL)
        p["p0_homologated"] = 6
        p["release_approved"] = True
        result = _analyze(p)
        self.assert_no_authority(result)
        self.assertFalse(result["proposal_structure_valid"])

    def test_13_even_an_ideal_synthetic_ruleset_does_not_authorize_deploy(self):
        result = _analyze()
        self.assertTrue(result["proposal_structure_valid"])
        self.assert_no_authority(result)

    def test_14_cli_on_actual_source_exits_three_not_release_green(self):
        cmd = subprocess.run(
            [sys.executable, "-B", "-m", "labs.a264_ruleset_blueprint_review",
             "--source-root", str(ROOT)],
            cwd=ROOT, capture_output=True, text=True, timeout=25,
        )
        self.assertEqual(cmd.returncode, 3, (cmd.stdout, cmd.stderr))
        obj = json.loads(cmd.stdout)
        self.assertTrue(obj["proposal_structure_valid"])
        self.assert_no_authority(obj)

    def test_15_unrecognized_schema_and_invalid_input_fail_closed(self):
        for bad in (None, [], "active", {}, {"name": PROPOSAL["name"]}):
            with self.subTest(type=type(bad).__name__):
                result = review_blueprint(
                    bad, codeowners_text=OWNERS, quality_text=QUALITY,
                )
                self.assertFalse(result["proposal_structure_valid"])
                self.assert_no_authority(result)


if __name__ == "__main__":
    unittest.main()
