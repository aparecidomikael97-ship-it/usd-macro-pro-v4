"""A334 LAB: preserve safe A201 missing-configuration denial semantics.

A known plain RuntimeConfig with missing token/repo is UNAVAILABLE. An
arbitrary config object is never inspected for these properties; any supplied
credentials still cannot authorize ENABLE. All transports are mocked.
"""
import unittest
from unittest.mock import Mock, patch

from atlasquant_aion_global_worker_activation import (
    activate_global_worker_feature_flag,
    write_repository_feature_flag_enabled,
)
from atlasquant_aion_memory import RuntimeConfig


class A334MissingConfigContractTests(unittest.TestCase):
    def test_exact_runtime_config_without_token_remains_unavailable(self):
        config = RuntimeConfig(token="", repo="owner/repo", branch="atlasquant-runtime")
        with patch(
            "atlasquant_aion_global_worker_activation.requests.post",
        ) as post, patch(
            "atlasquant_aion_global_worker_activation.requests.patch",
        ) as update:
            result = write_repository_feature_flag_enabled(config, "UNSET")
        post.assert_not_called()
        update.assert_not_called()
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["reason"], "Repository/token required for flag mutation.")
        self.assertFalse(result["modified"])
        self.assertFalse(result["feature_flag_modified"])
        self.assertFalse(result["independent_witness_verified"])

    def test_exact_runtime_config_without_repo_remains_unavailable(self):
        config = RuntimeConfig(token="synthetic-test-token", repo="", branch="atlasquant-runtime")
        with patch(
            "atlasquant_aion_global_worker_activation.requests.post",
        ) as post, patch(
            "atlasquant_aion_global_worker_activation.requests.patch",
        ) as update:
            result = write_repository_feature_flag_enabled(config, "DISABLED")
        post.assert_not_called()
        update.assert_not_called()
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertFalse(result["modified"])

    def test_hostile_non_runtime_config_properties_are_never_evaluated(self):
        class HostileConfig:
            @property
            def token(self):
                raise AssertionError("A334_UNTRUSTED_TOKEN_READ")
            @property
            def repo(self):
                raise AssertionError("A334_UNTRUSTED_REPO_READ")
        with patch(
            "atlasquant_aion_global_worker_activation.requests.post",
        ) as post, patch(
            "atlasquant_aion_global_worker_activation.requests.patch",
        ) as update:
            result = write_repository_feature_flag_enabled(
                HostileConfig(), "UNSET"
            )
        post.assert_not_called()
        update.assert_not_called()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "EXTERNAL_ENABLE_CUSTODY_NOT_HOMOLOGATED")

    def test_exact_runtime_config_with_hostile_token_bool_is_not_executed(self):
        class TrapToken:
            def __bool__(self):
                raise AssertionError("A334_TRAP_BOOL_MUST_NOT_BE_CALLED")
        config = RuntimeConfig(token=TrapToken(), repo="owner/repo", branch="atlasquant-runtime")
        with patch(
            "atlasquant_aion_global_worker_activation.requests.post",
        ) as post:
            result = write_repository_feature_flag_enabled(config, "UNSET")
        post.assert_not_called()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["modified"])

    def test_hostile_prior_state_str_is_not_evaluated(self):
        class HostilePriorState:
            def __str__(self):
                raise AssertionError("A334_TRAP_STR_MUST_NOT_BE_CALLED")
        with patch(
            "atlasquant_aion_global_worker_activation.requests.post",
        ) as post:
            result = write_repository_feature_flag_enabled(
                RuntimeConfig(token="synthetic", repo="owner/repo", branch="atlasquant-runtime"),
                HostilePriorState(),
            )
        post.assert_not_called()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["modified"])

    def test_activation_even_without_token_cannot_call_injected_writer(self):
        reader = Mock(side_effect=AssertionError("A334_RUNTIME_READER_FORBIDDEN"))
        writer = Mock(return_value={"status": "WRITE_ACCEPTED", "modified": True})
        config = RuntimeConfig(token="", repo="owner/repo", branch="atlasquant-runtime")
        result = activate_global_worker_feature_flag(
            access=None, runtime_result={}, approval={}, config=config,
            confirmation=True, runtime_reader=reader, flag_writer=writer,
        )
        reader.assert_not_called()
        writer.assert_not_called()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED")
        self.assertFalse(result["feature_flag_modified"])
        self.assertFalse(result["global_worker_executed"])


if __name__ == "__main__":
    unittest.main()
