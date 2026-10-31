"""A333 LAB: reject injected Global Worker enable writer without owner custody.

Actual owner ceremony and data-provider transports are NOT tested or provisioned.
Only local synthetic tickets, mock callables, and denied network sockets exist.
"""
import unittest
from copy import deepcopy
from unittest.mock import Mock, patch

from atlasquant_aion_global_worker_activation import (
    DEACTIVATION_PHRASE,
    activate_global_worker_feature_flag,
    deactivate_global_worker_feature_flag,
    force_disable_repository_feature_flag,
    write_repository_feature_flag_enabled,
)
import test_atlasquant_aion_global_worker_activation as fixture_module


class A333ActivationInjectedWriterDenialTests(unittest.TestCase):
    def assert_authority_denied(self, result):
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["reason"], "INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED"
        )
        self.assertFalse(result["feature_flag_modified"])
        self.assertFalse(result["global_worker_executed"])
        self.assertFalse(result["independent_witness_verified"])
        self.assertFalse(result["runtime_checkpoint_modified"])

    def test_local_valid_ticket_cannot_activate_via_injected_writer(self):
        fixture = fixture_module.GlobalWorkerActivationCeremonyTests()
        fixture.setUp()
        ticket = fixture.approval()
        original = deepcopy(fixture.runtime)
        runtime_reader = Mock(return_value=deepcopy(fixture.runtime))
        flag_reader = Mock(side_effect=[
            fixture_module._safe_flag("UNSET"),
            {"status": "CONFIRMED", "state": "ENABLED"},
        ])
        writer = Mock(return_value={"status": "WRITE_ACCEPTED", "modified": True})
        disabler = Mock()
        with patch(
            "requests.sessions.Session.request",
            side_effect=AssertionError("A333_EXTERNAL_NETWORK_DENIED"),
        ):
            result = activate_global_worker_feature_flag(
                fixture.access, fixture.runtime, ticket,
                fixture_module._config(),
                confirmation=True,
                runtime_reader=runtime_reader,
                flag_reader=flag_reader,
                flag_writer=writer,
                flag_disabler=disabler,
                now=fixture_module.NOW,
            )
        runtime_reader.assert_not_called()
        flag_reader.assert_not_called()
        writer.assert_not_called()
        disabler.assert_not_called()
        self.assertEqual(fixture.runtime, original)
        self.assert_authority_denied(result)

    def test_forged_owner_marker_cannot_reach_injected_runtime_reader(self):
        runtime_reader = Mock(
            side_effect=AssertionError("A333_RUNTIME_READER_MUST_NOT_RUN")
        )
        writer = Mock(return_value={"status": "WRITE_ACCEPTED", "modified": True})
        with patch(
            "requests.sessions.Session.request",
            side_effect=AssertionError("A333_NO_EXTERNAL_NETWORK"),
        ):
            result = activate_global_worker_feature_flag(
                access=None,
                runtime_result={"status": "CONFIRMED", "independent_witness": {"verified": True}},
                approval={"owner": "self-asserted", "feature_flag_state_at_plan": "UNSET"},
                config=object(),
                confirmation=True,
                runtime_reader=runtime_reader,
                flag_writer=writer,
                now=fixture_module.NOW,
            )
        runtime_reader.assert_not_called()
        writer.assert_not_called()
        self.assert_authority_denied(result)

    def test_direct_enable_writer_does_not_read_hostile_repo_property(self):
        class HostileConfig:
            @property
            def repo(self):
                raise AssertionError("A333_CONFIG_REPO_PROPERTY_READ")
            @property
            def token(self):
                raise AssertionError("A333_CONFIG_TOKEN_PROPERTY_READ")
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
        self.assertEqual(
            result["reason"], "EXTERNAL_ENABLE_CUSTODY_NOT_HOMOLOGATED"
        )
        self.assertFalse(result["modified"])
        self.assertFalse(result["independent_witness_verified"])

    def test_default_enable_writer_remains_denied_before_http(self):
        with patch(
            "atlasquant_aion_global_worker_activation.requests.post",
        ) as post, patch(
            "atlasquant_aion_global_worker_activation.requests.patch",
        ) as update:
            for state in ("UNSET", "DISABLED"):
                result = write_repository_feature_flag_enabled(
                    fixture_module._config(), state
                )
                self.assertEqual(result["status"], "BLOCKED")
                self.assertEqual(
                    result["reason"], "EXTERNAL_ENABLE_CUSTODY_NOT_HOMOLOGATED"
                )
                self.assertEqual(result["previous_state"], state)
                self.assertFalse(result["modified"])
        post.assert_not_called()
        update.assert_not_called()

    def test_missing_final_confirmation_still_denies_before_reads(self):
        reader = Mock()
        writer = Mock()
        result = activate_global_worker_feature_flag(
            None, {}, None, object(),
            confirmation=False, runtime_reader=reader, flag_writer=writer,
        )
        reader.assert_not_called()
        writer.assert_not_called()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "FINAL_EXPLICIT_CONFIRMATION_REQUIRED")

    def test_safety_disable_still_writes_only_disabled_value(self):
        response = Mock(status_code=204)
        with patch(
            "atlasquant_aion_global_worker_activation.requests.patch",
            return_value=response,
        ) as update, patch(
            "atlasquant_aion_global_worker_activation.requests.post",
        ) as create:
            result = force_disable_repository_feature_flag(
                fixture_module._config()
            )
        update.assert_called_once()
        create.assert_not_called()
        self.assertEqual(update.call_args.kwargs["json"]["value"], "0")
        self.assertEqual(result["status"], "DISABLED")

    def test_authenticated_deactivation_path_still_works_with_mock_writer(self):
        fixture = fixture_module.GlobalWorkerActivationCeremonyTests()
        fixture.setUp()
        reader = Mock(side_effect=[
            {"status": "CONFIRMED", "state": "ENABLED"},
            fixture_module._safe_flag("DISABLED"),
        ])
        disabler = Mock(return_value={"status": "DISABLED", "modified": True})
        with patch(
            "requests.sessions.Session.request",
            side_effect=AssertionError("A333_DEACTIVATION_NETWORK_DENIED"),
        ):
            result = deactivate_global_worker_feature_flag(
                fixture.access, fixture_module._config(),
                confirmation=True, confirmation_phrase=DEACTIVATION_PHRASE,
                flag_reader=reader, flag_disabler=disabler,
            )
        disabler.assert_called_once()
        self.assertEqual(result["status"], "DISABLED")
        self.assertFalse(result["global_worker_executed"])


if __name__ == "__main__":
    unittest.main()
