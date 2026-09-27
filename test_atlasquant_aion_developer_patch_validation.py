from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_aion_developer_builder_sandbox import structural_builder_sandbox_request
from atlasquant_aion_developer_manifest import bind_builder_request_lineage
from atlasquant_aion_developer_patch_validation import SCHEMA, validate_patch
from atlasquant_aion_developer_sandbox_preflight import build_sandbox_preflight


def _request():
    return structural_builder_sandbox_request(
        branch="cursor/safe",
        baseline_ref="main@a",
        candidate_ref="cursor/safe@b",
        requested_files=("module.py", "test_module.py", "requirements.txt"),
        candidate_tests=("test_module.py",),
    )


def _preflight(request=None):
    return build_sandbox_preflight(
        request or _request(),
        environment_kind="ISOLATED_WORKTREE",
        environment_id="sandbox-001",
        isolated_worktree=True,
        repository_root_bound=True,
        network_disabled=True,
        secrets_mounted=False,
        command_policy="ALLOWLIST_ONLY",
    )


def _validate(patch, request=None, preflight=None, **kwargs):
    request = request or _request()
    return validate_patch(
        request,
        preflight or _preflight(request),
        patch,
        baseline_ref=kwargs.get("baseline_ref", "main@a"),
        candidate_ref=kwargs.get("candidate_ref", "cursor/safe@b"),
    )


class AionDeveloperPatchValidationTests(unittest.TestCase):
    def test_safe_in_scope_patch_is_only_ready_for_human_review(self):
        patch = (
            "diff --git a/module.py b/module.py\n"
            "index 111..222 100644\n"
            "--- a/module.py\n"
            "+++ b/module.py\n"
            "@@ -1 +1 @@\n"
            "-VALUE = 1\n"
            "+VALUE = 2\n"
        )
        out = _validate(patch)
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "READY_FOR_PATCH_REVIEW")
        self.assertEqual(out["file_count"], 1)
        self.assertEqual(out["files"][0]["path"], "module.py")
        self.assertFalse(out["revision_binding"]["revision_content_verified"])
        self.assertTrue(out["content_binding_requires_external_verification"])
        self.assertTrue(out["human_patch_review_required"])
        self.assertFalse(out["patch_applied"])
        self.assertFalse(out["execution_authorized"])
        self.assertFalse(out["writes_files"])

    def test_out_of_scope_and_traversal_paths_fail_closed(self):
        patch = (
            "diff --git a/outside.py b/outside.py\n"
            "--- a/outside.py\n+++ b/outside.py\n"
            "@@ -1 +1 @@\n-x=1\n+x=2\n"
        )
        out = _validate(patch)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PATCH_PATH_OUTSIDE_AUTHORIZED_SCOPE", out["blockers"])

        traversal = (
            "diff --git a/../outside.py b/../outside.py\n"
            "--- a/../outside.py\n+++ b/../outside.py\n"
            "@@ -1 +1 @@\n-x=1\n+x=2\n"
        )
        with self.assertRaises(ValueError):
            _validate(traversal)

    def test_create_delete_rename_mode_and_binary_are_blocked(self):
        cases = [
            (
                "diff --git a/module.py b/module.py\nnew file mode 100644\n"
                "--- /dev/null\n+++ b/module.py\n@@ -0,0 +1 @@\n+x=1\n",
                "NEW_FILE_NOT_ALLOWED",
            ),
            (
                "diff --git a/module.py b/module.py\ndeleted file mode 100644\n"
                "--- a/module.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-x=1\n",
                "DELETE_FILE_NOT_ALLOWED",
            ),
            (
                "diff --git a/module.py b/test_module.py\n"
                "similarity index 100%\nrename from module.py\nrename to test_module.py\n",
                "RENAME_OR_COPY_NOT_ALLOWED",
            ),
            (
                "diff --git a/module.py b/module.py\nold mode 100644\nnew mode 100755\n",
                "FILE_MODE_CHANGE_NOT_ALLOWED",
            ),
            (
                "diff --git a/module.py b/module.py\nGIT binary patch\nliteral 1\nA\n",
                "BINARY_PATCH_NOT_ALLOWED",
            ),
        ]
        for patch, blocker in cases:
            with self.subTest(blocker=blocker):
                out = _validate(patch)
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn(blocker, out["blockers"])

    def test_test_deletion_or_weakening_is_blocked(self):
        patch = (
            "diff --git a/test_module.py b/test_module.py\n"
            "--- a/test_module.py\n+++ b/test_module.py\n"
            "@@ -1,2 +1 @@\n-def test_guard():\n-    assert guard()\n+pass\n"
        )
        out = _validate(patch)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("TEST_DELETION_OR_WEAKENING_NOT_ALLOWED", out["blockers"])

    def test_dependency_and_release_surfaces_require_separate_review(self):
        dep = (
            "diff --git a/requirements.txt b/requirements.txt\n"
            "--- a/requirements.txt\n+++ b/requirements.txt\n"
            "@@ -1 +1 @@\n-a==1\n+a==2\n"
        )
        self.assertIn(
            "DEPENDENCY_CHANGE_REQUIRES_SEPARATE_REVIEW",
            _validate(dep)["blockers"],
        )
        rel = (
            "diff --git a/docs/release/NOTES.md b/docs/release/NOTES.md\n"
            "--- a/docs/release/NOTES.md\n+++ b/docs/release/NOTES.md\n"
            "@@ -1 +1 @@\n-old\n+new\n"
        )
        self.assertIn(
            "RELEASE_SURFACE_REQUIRES_SEPARATE_REVIEW",
            _validate(rel)["blockers"],
        )

    def test_secret_like_addition_is_blocked_without_echoing_secret(self):
        secret = "super-secret-value"
        patch = (
            "diff --git a/module.py b/module.py\n"
            "--- a/module.py\n+++ b/module.py\n"
            "@@ -1 +1 @@\n-x=1\n+api_key=" + secret + "\n"
        )
        out = _validate(patch)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("SECRET_LIKE_ADDITION_NOT_ALLOWED", out["blockers"])
        self.assertNotIn(secret, str(out))
        self.assertFalse(out["patch_text_included"])

    def test_lineage_and_revision_refs_are_bound(self):
        preflight = _preflight()
        preflight["builder_request_id"] = "OTHER"
        with self.assertRaises(ValueError):
            _validate("diff --git a/module.py b/module.py\n", preflight=preflight)
        with self.assertRaises(ValueError):
            _validate(
                "diff --git a/module.py b/module.py\n",
                candidate_ref="cursor/other@b",
            )

    def test_canonical_path_collision_is_blocked(self):
        request = _request()
        request["scope"] = deepcopy(request["scope"])
        request["scope"]["requested_files"] = ["module.py", "Ｍodule.py"]
        request["scope"]["authorized_files"] = ["module.py", "Ｍodule.py"]
        request = bind_builder_request_lineage(request)
        patch = (
            "diff --git a/module.py b/module.py\n--- a/module.py\n+++ b/module.py\n"
            "@@ -1 +1 @@\n-a=1\n+a=2\n"
            "diff --git a/Ｍodule.py b/Ｍodule.py\n--- a/Ｍodule.py\n+++ b/Ｍodule.py\n"
            "@@ -1 +1 @@\n-b=1\n+b=2\n"
        )
        out = _validate(patch, request=request, preflight=_preflight(request))
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("CANONICAL_PATH_COLLISION", out["blockers"])

    def test_patch_budget_fails_closed(self):
        patch = (
            "diff --git a/module.py b/module.py\n--- a/module.py\n+++ b/module.py\n"
            "@@ -1 +1 @@\n"
            + "".join("+x=1\n" for _ in range(1001))
        )
        out = _validate(patch)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PER_FILE_CHANGE_BUDGET_EXCEEDED", out["blockers"])

    def test_validator_never_executes_or_writes(self):
        patch = (
            "diff --git a/module.py b/module.py\n--- a/module.py\n+++ b/module.py\n"
            "@@ -1 +1 @@\n-x=1\n+x=2\n"
        )
        out = _validate(patch)
        for key in (
            "patch_applied", "execution_authorized", "executor_attached",
            "commands_executed", "writes_files", "runs_tests", "network_called",
            "subprocess_called", "automatic_commit", "automatic_merge",
            "automatic_deploy", "production_change_allowed",
            "real_trading_enabled", "tool_output_is_authority",
        ):
            self.assertFalse(out[key])


if __name__ == "__main__":
    unittest.main()
