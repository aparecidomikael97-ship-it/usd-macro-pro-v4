"""Synthetic owner-scoped read-only native CNG enumeration validation.

No real owner machine or mutable host resources in CI.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

import atlasquant_aion_owner_silent_cng_algorithm_observation_v1 as owner
import atlasquant_aion_native_cng_silent_signature_algorithm_enum_v1 as enum
from test_atlasquant_aion_native_cng_silent_signature_algorithm_enum_v1 import FakeCNG


class OwnerScopedSilentCNGTests(unittest.TestCase):
    def invoke(self, *, auth=True, scope=owner.PHYSICAL_SCOPE,
               nonce="a3" * 32, device="win32", api=None):
        api = api if api is not None else FakeCNG()
        # Deliberately remove GitHub CI flags: owner pathway MUST NOT spoof CI.
        with patch.object(owner.sys, "platform", device), patch.dict(
            os.environ, {}, clear=True,
        ), patch.object(enum, "_load_ncrypt", return_value=api) as load:
            result = owner.observe_owner_silent_signature_algorithms_readonly(
                nonce,
                explicit_owner_authorization_for_this_probe=auth,
                authorized_device_scope=scope,
            )
        return result, api, load

    def assert_never_authorizes(self, result):
        self.assertIs(result["provider_ui_suppression_requested"], True)
        for key in (
            "actual_no_ui_physically_verified",
            "owner_pc_execution_authorized_by_code",
            "independently_attested_provider_identity",
            "tpm_presence_verified",
            "tpm_ed25519_key_custody_verified",
            "p256_tpm_key_custody_verified",
            "algorithm_provisionability_verified",
            "key_nonexportability_verified",
            "private_key_created", "private_key_opened",
            "private_key_enumerated", "private_key_enrolled",
            "host_security_state_modified",
            "physical_attestation_verified", "network_deny_verified",
            "collector_launch_authorized",
            "installer_authorized", "build_authorized",
            "deploy_authorized", "safe_to_resume",
        ):
            self.assertIs(result[key], False, key)

    def test_exact_owner_scope_allows_same_native_core_without_ci_spoof(self):
        result, api, loader = self.invoke()
        self.assertEqual(result["state"], enum.CANDIDATE, result)
        self.assertEqual(api.calls, [
            ("open", enum.PROVIDER, 0),
            ("enum", 0x1234, enum.SIGNATURE_OPERATION, enum.NCRYPT_SILENT_FLAG),
            ("free_buffer", True),
            ("free_provider", 0x1234),
        ])
        self.assertEqual(result["target_algorithm_names"], {
            "ECDSA_P256": "LISTED", "ED25519": "LISTED",
        })
        self.assertTrue(result["provider_handle_released"])
        self.assertTrue(result["result_buffer_released"])
        loader.assert_called_once()
        self.assert_never_authorizes(result)

    def test_no_approval_blocks_before_native_load(self):
        result, api, load = self.invoke(auth=False)
        self.assertEqual(result["reason"], "EXPLICIT_OWNER_SCOPED_READONLY_AUTHORIZATION_REQUIRED")
        load.assert_not_called()
        self.assertFalse(api.calls)
        self.assert_never_authorizes(result)

    def test_invalid_scope_blocks_before_native_load(self):
        for scope in ("", "OWNER", "INSTALL", "TRUST", "AUTO_APPROVE", None, True):
            with self.subTest(scope=scope):
                result, api, load = self.invoke(scope=scope)
                self.assertEqual(result["state"], "BLOCKED")
                load.assert_not_called()
                self.assert_never_authorizes(result)

    def test_none_or_truthy_non_boolean_approval_is_denied(self):
        for auth in (None, 1, "true", "yes", "sim", [], {}):
            with self.subTest(auth=auth):
                result, api, load = self.invoke(auth=auth)
                self.assertEqual(result["state"], "BLOCKED")
                load.assert_not_called()
                self.assert_never_authorizes(result)

    def test_invalid_nonce_fails_before_provider_load(self):
        for nonce in (None, "f"*63, "G"*64, "f"*66, "", True, 1):
            with self.subTest(nonce=nonce):
                result, api, load = self.invoke(nonce=nonce)
                self.assertEqual(result["reason"], "EXPLICIT_256_BIT_CHALLENGE_REQUIRED")
                load.assert_not_called()
                self.assert_never_authorizes(result)

    def test_non_windows_always_denied(self):
        result, api, load = self.invoke(device="linux")
        self.assertEqual(result["reason"], "WINDOWS_REQUIRED")
        load.assert_not_called()
        self.assert_never_authorizes(result)

    def test_original_ci_wrapper_stays_guarded_on_owner(self):
        with patch.object(enum.sys, "platform", "win32"), patch.dict(
            os.environ, {}, clear=True,
        ), patch.object(enum, "_load_ncrypt") as loading:
            result = enum.observe_silent_signature_algorithms_ci_only("ab"*32)
        self.assertEqual(result["reason"], "DISPOSABLE_GITHUB_WINDOWS_PR_CI_REQUIRED")
        loading.assert_not_called()
        self.assert_never_authorizes(result)

    def test_bad_flags_never_retries_with_zero_flags(self):
        result, api, loader = self.invoke(api=FakeCNG(enum_status=0x80090009))
        self.assertEqual(result["reason"], "SILENT_ENUM_FAILED")
        self.assertEqual(result["enumeration_status"]["reason"], "NTE_BAD_FLAGS")
        self.assertEqual([a for a in api.calls if a[0] == "enum"], [
            ("enum", 0x1234, enum.SIGNATURE_OPERATION, enum.NCRYPT_SILENT_FLAG),
        ])
        self.assertTrue(result["provider_handle_released"])
        self.assert_never_authorizes(result)

    def test_provider_not_ready_fails_closed(self):
        result, api, _ = self.invoke(api=FakeCNG(open_status=0x80090030))
        self.assertEqual(result["reason"], "PROVIDER_OPEN_FAILED")
        self.assertFalse(any(a[0] == "enum" for a in api.calls))
        self.assert_never_authorizes(result)

    def test_invalid_signature_interface_fails_closed(self):
        result, api, _ = self.invoke(api=FakeCNG(rows=[("ED25519", 3, 0x10)]))
        self.assertEqual(result["reason"], "SILENT_ENUM_INVALID_RESULT")
        self.assertTrue(result["provider_handle_released"])
        self.assert_never_authorizes(result)

    def test_malformed_name_fails_closed(self):
        result, api, _ = self.invoke(api=FakeCNG(rows=[("bad\nname", 5, 0x10)]))
        self.assertEqual(result["reason"], "SILENT_ENUM_INVALID_RESULT")
        self.assert_never_authorizes(result)

    def test_excessive_count_never_read_as_algorithms(self):
        result, api, _ = self.invoke(api=FakeCNG(too_many=True))
        self.assertEqual(result["reason"], "SILENT_ENUM_EXCESSIVE_COUNT")
        self.assertEqual(result["target_algorithm_names"], {
            "ECDSA_P256": "NOT_QUERIED", "ED25519": "NOT_QUERIED",
        })
        self.assert_never_authorizes(result)

    def test_provider_cleanup_required(self):
        result, api, _ = self.invoke(api=FakeCNG(free_provider_status=0x80090026))
        self.assertEqual(result["reason"], "RELEASE_UNCONFIRMED")
        self.assert_never_authorizes(result)

    def test_buffer_cleanup_required(self):
        result, api, _ = self.invoke(api=FakeCNG(free_buffer_status=0x80090027))
        self.assertEqual(result["reason"], "RELEASE_UNCONFIRMED")
        self.assert_never_authorizes(result)

    def test_none_listed_still_not_hardware_proof(self):
        result, api, _ = self.invoke(api=FakeCNG(rows=[("RSA", 5, 0x10)]))
        self.assertEqual(result["state"], enum.CANDIDATE)
        self.assertEqual(result["target_algorithm_names"], {
            "ECDSA_P256": "NOT_LISTED", "ED25519": "NOT_LISTED",
        })
        self.assert_never_authorizes(result)

    def test_no_private_key_operations_in_owner_wrapper(self):
        result, api, _ = self.invoke()
        self.assertFalse(any("key" in action for action, *_ in api.calls))
        self.assert_never_authorizes(result)


if __name__ == "__main__":
    unittest.main()
