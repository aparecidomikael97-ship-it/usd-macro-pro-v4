import os
import unittest
from unittest.mock import patch

from atlasquant_runtime_store import (
    DEFAULT_RUNTIME_BRANCH,
    evaluate_runtime_branch,
    is_code_branch,
    require_runtime_branch,
    resolve_runtime_branch,
    runtime_branch_from_env,
)


class AtlasQuantRuntimeStoreTests(unittest.TestCase):
    def test_default_is_dedicated_runtime_branch(self):
        self.assertEqual(resolve_runtime_branch(), DEFAULT_RUNTIME_BRANCH)

    def test_explicit_data_branch_wins(self):
        self.assertEqual(
            resolve_runtime_branch("custom-runtime", "main"),
            "custom-runtime",
        )

    def test_explicit_main_is_redirected(self):
        self.assertEqual(
            resolve_runtime_branch("main", "history-data"),
            DEFAULT_RUNTIME_BRANCH,
        )

    def test_explicit_dev_is_redirected(self):
        self.assertEqual(
            resolve_runtime_branch("atlasquant-dev", "history-data"),
            DEFAULT_RUNTIME_BRANCH,
        )

    def test_legacy_main_is_migrated_away_from_code_branch(self):
        self.assertEqual(
            resolve_runtime_branch(None, "main"),
            DEFAULT_RUNTIME_BRANCH,
        )

    def test_legacy_dev_is_migrated_away_from_code_branch(self):
        self.assertEqual(
            resolve_runtime_branch(None, "atlasquant-dev"),
            DEFAULT_RUNTIME_BRANCH,
        )

    def test_legacy_custom_runtime_branch_is_preserved(self):
        self.assertEqual(
            resolve_runtime_branch(None, "history-data"),
            "history-data",
        )

    def test_code_branch_detection(self):
        self.assertTrue(is_code_branch("main"))
        self.assertTrue(is_code_branch("atlasquant-dev"))
        self.assertFalse(is_code_branch(DEFAULT_RUNTIME_BRANCH))

    def test_policy_rejects_runtime_writes_to_main(self):
        p=evaluate_runtime_branch("main")
        self.assertFalse(p.safe_for_runtime_writes)

    def test_require_runtime_branch_fails_closed(self):
        with self.assertRaises(ValueError):
            require_runtime_branch("atlasquant-dev")

    def test_env_prefers_new_setting(self):
        with patch.dict(os.environ, {
            "GITHUB_DATA_BRANCH":"runtime-x",
            "GITHUB_BRANCH_HISTORICO":"main",
        }, clear=True):
            self.assertEqual(runtime_branch_from_env(), "runtime-x")


if __name__=="__main__":
    unittest.main()
