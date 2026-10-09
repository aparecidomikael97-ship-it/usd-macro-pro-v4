"""Fail-closed synthetic and disposable Windows NCryptEnumAlgorithms checks."""
from __future__ import annotations

import ctypes
import os
import secrets
import sys
import unittest
from unittest.mock import patch

import atlasquant_aion_native_cng_silent_signature_algorithm_enum_v1 as silent


CI = {
    "GITHUB_ACTIONS": "true",
    "GITHUB_EVENT_NAME": "pull_request",
    "RUNNER_OS": "Windows",
    "GITHUB_REPOSITORY": "aparecidomikael97-ship-it/usd-macro-pro-v4",
}


class Fn:
    def __init__(self, f):
        self.f = f
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        return self.f(*args)


class FakeCNG:
    def __init__(self, rows=None, *, open_status=0, enum_status=0,
                 free_buffer_status=0, free_provider_status=0,
                 too_many=False, null_list=False, fail_enum=False):
        self.rows = rows if rows is not None else [
            ("ECDSA_P256", 5, 0x10), ("ED25519", 5, 0x10),
        ]
        self.open_status = open_status
        self.enum_status = enum_status
        self.free_buffer_status = free_buffer_status
        self.free_provider_status = free_provider_status
        self.too_many = too_many
        self.null_list = null_list
        self.fail_enum = fail_enum
        self.calls = []
        self.array = None
        self.NCryptOpenStorageProvider = Fn(self.open)
        self.NCryptEnumAlgorithms = Fn(self.enumerate)
        self.NCryptFreeBuffer = Fn(self.free_buffer)
        self.NCryptFreeObject = Fn(self.free_provider)

    def open(self, pointer, name, flags):
        self.calls.append(("open", name, flags))
        if self.open_status == 0:
            ctypes.cast(pointer, ctypes.POINTER(ctypes.c_void_p))[0] = 0x1234
        return self.open_status

    def enumerate(self, handle, kind, countptr, listptr, flags):
        self.calls.append(("enum", handle.value, kind, flags))
        if self.fail_enum:
            raise OSError("test enum exception")
        if self.enum_status == 0:
            ctypes.cast(countptr, ctypes.POINTER(ctypes.c_uint32))[0] = (
                65 if self.too_many else len(self.rows))
            if self.rows and not self.null_list:
                self.array = (silent.NCryptAlgorithmName * len(self.rows))(
                    *(silent.NCryptAlgorithmName(a, b, c, 0)
                      for a, b, c in self.rows)
                )
                ctypes.cast(listptr, ctypes.POINTER(
                    ctypes.POINTER(silent.NCryptAlgorithmName)))[0] = (
                        ctypes.cast(self.array, ctypes.POINTER(silent.NCryptAlgorithmName))
                    )
        return self.enum_status

    def free_buffer(self, pointer):
        self.calls.append(("free_buffer", bool(pointer.value)))
        return self.free_buffer_status

    def free_provider(self, handle):
        self.calls.append(("free_provider", handle.value))
        return self.free_provider_status


class NativeCNGSilentEnumTests(unittest.TestCase):
    def probe(self, api=None, env=None, platform="win32", nonce="ba"*32):
        if api is None:
            api = FakeCNG()
        if env is None:
            env = CI
        with patch.object(silent.sys, "platform", platform), patch.dict(
            os.environ, env, clear=True
        ), patch.object(silent, "_load_ncrypt", return_value=api) as loader:
            result = silent.observe_silent_signature_algorithms_ci_only(nonce)
        return result, api, loader

    def deny_trust(self, out):
        self.assertTrue(out["provider_ui_suppression_requested"])
        for x in (
            "actual_no_ui_physically_verified",
            "owner_pc_execution_authorized_by_code",
            "independently_attested_provider_identity",
            "tpm_presence_verified", "tpm_ed25519_key_custody_verified",
            "p256_tpm_key_custody_verified",
            "algorithm_provisionability_verified",
            "key_nonexportability_verified",
            "private_key_created", "private_key_opened",
            "private_key_enumerated", "private_key_enrolled",
            "host_security_state_modified",
            "physical_attestation_verified", "network_deny_verified",
            "collector_launch_authorized", "installer_authorized",
            "build_authorized", "deploy_authorized", "safe_to_resume",
        ):
            self.assertIs(out[x], False, x)

    def test_fixed_provider_signature_filter_silent_flag_and_cleanup(self):
        out, api, loader = self.probe()
        self.assertEqual(out["state"], silent.CANDIDATE, out)
        self.assertEqual(api.calls, [
            ("open", silent.PROVIDER, 0),
            ("enum", 0x1234, silent.SIGNATURE_OPERATION, silent.NCRYPT_SILENT_FLAG),
            ("free_buffer", True),
            ("free_provider", 0x1234),
        ])
        self.assertEqual(out["target_algorithm_names"], {
            "ECDSA_P256": "LISTED", "ED25519": "LISTED"})
        self.assertTrue(out["result_buffer_released"])
        self.assertTrue(out["provider_handle_released"])
        loader.assert_called_once()
        self.deny_trust(out)

    def test_not_listed_does_not_claim_global_algorithm_absence(self):
        out, api, _ = self.probe(FakeCNG(rows=[("RSA", 5, 0x10)]))
        self.assertEqual(out["state"], silent.CANDIDATE)
        self.assertEqual(out["target_algorithm_names"], {
            "ECDSA_P256": "NOT_LISTED", "ED25519": "NOT_LISTED"})
        self.deny_trust(out)

    def test_empty_algorithm_list_is_well_formed_non_authoritative(self):
        out, api, _ = self.probe(FakeCNG(rows=[]))
        self.assertEqual(out["state"], silent.CANDIDATE)
        self.assertEqual(out["algorithm_name_count"], 0)
        self.assertEqual([c[0] for c in api.calls],
                         ["open", "enum", "free_provider"])
        self.deny_trust(out)

    def test_no_hidden_signature_keys_enumeration(self):
        out, api, _ = self.probe()
        self.assertFalse(any("key" in name for name, *_ in api.calls))
        self.deny_trust(out)

    def test_unrecognized_algorithms_not_disclosed(self):
        out, api, _ = self.probe(FakeCNG(
            rows=[("INTERNAL_PROVIDER_ALG", 5, 0x10)]))
        self.assertNotIn("INTERNAL_PROVIDER_ALG", repr(out))
        self.deny_trust(out)

    def test_bad_flags_reports_inconclusive_and_frees_handle(self):
        out, api, _ = self.probe(FakeCNG(enum_status=0x80090009))
        self.assertEqual(out["reason"], "SILENT_ENUM_FAILED")
        self.assertEqual(out["enumeration_status"]["reason"], "NTE_BAD_FLAGS")
        self.assertEqual(api.calls[-1], ("free_provider", 0x1234))
        self.deny_trust(out)

    def test_provider_not_ready_does_not_enumerate(self):
        out, api, _ = self.probe(FakeCNG(open_status=0x80090030))
        self.assertEqual(out["reason"], "PROVIDER_OPEN_FAILED")
        self.assertEqual(out["provider_open_status"]["reason"], "NTE_DEVICE_NOT_READY")
        self.assertEqual([c[0] for c in api.calls], ["open"])
        self.deny_trust(out)

    def test_enum_exception_releases_provider(self):
        out, api, _ = self.probe(FakeCNG(fail_enum=True))
        self.assertEqual(out["reason"], "SILENT_ENUM_INVALID_RESULT")
        self.assertEqual(api.calls[-1][0], "free_provider")
        self.deny_trust(out)

    def test_excessive_count_does_not_dereference_and_releases_buffer(self):
        out, api, _ = self.probe(FakeCNG(too_many=True))
        self.assertEqual(out["reason"], "SILENT_ENUM_EXCESSIVE_COUNT")
        self.assertEqual([c[0] for c in api.calls][-2:],
                         ["free_buffer", "free_provider"])
        self.deny_trust(out)

    def test_null_list_for_nonzero_count_blocks(self):
        out, api, _ = self.probe(FakeCNG(null_list=True))
        self.assertEqual(out["reason"], "SILENT_ENUM_NULL_LIST")
        self.assertEqual([c[0] for c in api.calls][-1], "free_provider")
        self.deny_trust(out)

    def test_zero_flags_not_supported_as_physical_fallback(self):
        # Hard-coded to silent flag; no retry with zero flags even on error.
        out, api, _ = self.probe(FakeCNG(enum_status=0x80090009))
        self.assertEqual(len([c for c in api.calls if c[0] == "enum"]), 1)
        self.assertEqual(api.calls[1][-1], silent.NCRYPT_SILENT_FLAG)
        self.deny_trust(out)

    def test_invalid_signature_class_blocks(self):
        out, api, _ = self.probe(FakeCNG(rows=[("ED25519", 3, 0x10)]))
        self.assertEqual(out["reason"], "SILENT_ENUM_INVALID_RESULT")
        self.deny_trust(out)

    def test_duplicate_algorithm_name_blocks(self):
        out, api, _ = self.probe(FakeCNG(rows=[
            ("ECDSA_P256", 5, 0x10), ("ECDSA_P256", 5, 0x10)
        ]))
        self.assertEqual(out["reason"], "SILENT_ENUM_INVALID_RESULT")
        self.deny_trust(out)

    def test_nonsignature_operations_block(self):
        out, api, _ = self.probe(FakeCNG(rows=[
            ("ECDSA_P256", 5, 0x4)
        ]))
        self.assertEqual(out["reason"], "SILENT_ENUM_INVALID_RESULT")
        self.deny_trust(out)

    def test_malformed_algorithm_name_blocks(self):
        out, api, _ = self.probe(FakeCNG(rows=[
            ("INJECTED\nALGORITHM", 5, 0x10)
        ]))
        self.assertEqual(out["reason"], "SILENT_ENUM_INVALID_RESULT")
        self.deny_trust(out)

    def test_provider_buffer_free_failure_blocks(self):
        out, api, _ = self.probe(FakeCNG(free_buffer_status=0x80090027))
        self.assertEqual(out["reason"], "RELEASE_UNCONFIRMED")
        self.assertEqual(api.calls[-1][0], "free_provider")
        self.deny_trust(out)

    def test_provider_handle_free_failure_blocks(self):
        out, api, _ = self.probe(FakeCNG(free_provider_status=0x80090026))
        self.assertEqual(out["reason"], "RELEASE_UNCONFIRMED")
        self.deny_trust(out)

    def test_no_owner_or_wrong_git_environment_loads_api(self):
        for e in (
            {}, {"GITHUB_ACTIONS": "true"},
            {**CI, "GITHUB_EVENT_NAME": "push"},
            {**CI, "RUNNER_OS": "Linux"},
            {**CI, "GITHUB_REPOSITORY": "attacker/wrong"},
        ):
            with self.subTest(env=e):
                out, api, loader = self.probe(env=e)
                self.assertEqual(out["state"], "BLOCKED")
                loader.assert_not_called()
                self.deny_trust(out)

    def test_nonwindows_blocks(self):
        out, api, loader = self.probe(platform="linux")
        self.assertEqual(out["reason"], "DISPOSABLE_GITHUB_WINDOWS_PR_CI_REQUIRED")
        loader.assert_not_called()
        self.deny_trust(out)

    def test_invalid_challenge_blocks_before_api(self):
        for bad in (None, "", "a"*63, "Z"*64, True, 17):
            with self.subTest(bad=bad):
                out, api, loader = self.probe(nonce=bad)
                self.assertEqual(out["reason"], "CHALLENGE_REQUIRED")
                loader.assert_not_called()
                self.deny_trust(out)

    def test_name_validator_rejects_outside_shape(self):
        for records in (
            [(None, 5, 0x10)], [("A", True, 0x10)],
            [("A", 5, False)], [("A", 5, 0x4)],
            [("A", 5, 0x10)] * 65,
        ):
            with self.subTest(records=records):
                with self.assertRaises(ValueError):
                    silent._classify_names(records)

    def test_native_disposable_windows_runner_only(self):
        if not silent._ci_only():
            self.skipTest("native check only on actual GitHub Windows runner")
        out = silent.observe_silent_signature_algorithms_ci_only(
            secrets.token_hex(32))
        self.assertIn(out["state"], ("BLOCKED", silent.CANDIDATE))
        self.deny_trust(out)


if __name__ == "__main__":
    unittest.main()
