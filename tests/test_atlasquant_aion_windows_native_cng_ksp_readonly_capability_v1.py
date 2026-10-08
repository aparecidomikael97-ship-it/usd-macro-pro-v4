"""Native CNG KSP read-only capability checks and synthetic adversarial errors."""
from __future__ import annotations

import ctypes
import secrets
import sys
import unittest
from unittest.mock import patch

import atlasquant_aion_windows_native_cng_ksp_readonly_capability_v1 as cng


class FakeNCrypt:
    def __init__(self, *, open_status=0, algorithm_status=None,
                 handle=0x414243, free_status=0, open_error=None,
                 alg_error=None, free_error=None):
        self.open_status = open_status
        self.algorithm_status = (
            {"ECDSA_P256": 0, "ED25519": cng.NTE_NOT_SUPPORTED}
            if algorithm_status is None else algorithm_status
        )
        self.handle = handle
        self.free_status = free_status
        self.open_error = open_error
        self.alg_error = alg_error
        self.free_error = free_error
        self.open_calls = []
        self.alg_calls = []
        self.free_calls = []

    def NCryptOpenStorageProvider(self, pointer, name, flags):
        self.open_calls.append((name, flags))
        if self.open_error is not None:
            raise self.open_error
        if self.open_status == 0:
            ctypes.cast(pointer, ctypes.POINTER(ctypes.c_void_p))[0] = self.handle
        return self.open_status

    def NCryptIsAlgSupported(self, handle, name, flags):
        self.alg_calls.append((handle.value, name, flags))
        if self.alg_error is not None:
            raise self.alg_error
        return self.algorithm_status[name]

    def NCryptFreeObject(self, handle):
        self.free_calls.append(handle.value)
        if self.free_error is not None:
            raise self.free_error
        return self.free_status


class PlatformKSPReadOnlyTests(unittest.TestCase):
    def probe(self, api=None, challenge=None):
        api = FakeNCrypt() if api is None else api
        challenge = "af" * 32 if challenge is None else challenge
        with patch.object(cng.sys, "platform", "win32"), patch.object(
            cng, "_load_ncrypt", return_value=api
        ):
            return cng.probe_platform_ksp_algorithm_support_readonly(challenge)

    def assert_never_authorizes(self, report):
        for k in (
            "native_provider_identity_attested",
            "tpm_hardware_present_verified",
            "tpm_ownership_verified",
            "tpm_ed25519_key_custody_verified",
            "p256_tpm_key_custody_verified",
            "algorithm_provisionability_verified",
            "key_nonexportability_verified",
            "private_key_created", "private_key_opened",
            "private_key_enrolled",
            "collector_binary_measured",
            "anchor_independently_protected",
            "antirollback_verified", "physical_attestation_verified",
            "network_deny_verified", "collector_launch_authorized",
            "installer_authorized", "build_authorized",
            "deploy_authorized", "safe_to_resume",
            "host_security_state_modified",
        ):
            self.assertIs(report[k], False, k)

    def test_fixed_provider_and_two_fixed_algorithms_only(self):
        fake = FakeNCrypt()
        report = self.probe(fake)
        self.assertEqual(report["state"], cng.CANDIDATE, report)
        self.assertEqual(fake.open_calls, [(cng.PROVIDER, 0)])
        self.assertEqual(fake.alg_calls, [
            (fake.handle, "ECDSA_P256", cng.NCRYPT_SILENT_FLAG),
            (fake.handle, "ED25519", cng.NCRYPT_SILENT_FLAG),
        ])
        self.assertEqual(fake.free_calls, [fake.handle])
        self.assertIs(report["provider_handle_released"], True)
        self.assert_never_authorizes(report)

    def test_success_only_means_advertised_not_hardware_proof(self):
        fake = FakeNCrypt(algorithm_status={"ECDSA_P256": 0, "ED25519": 0})
        report = self.probe(fake)
        self.assertEqual(report["algorithm_advertisements"], {
            "ECDSA_P256": "ADVERTISED", "ED25519": "ADVERTISED"})
        self.assert_never_authorizes(report)

    def test_not_supported_is_explicitly_negative(self):
        fake = FakeNCrypt(algorithm_status={
            "ECDSA_P256": -2146893783,  # 0x80090029 represented as signed LONG
            "ED25519": cng.NTE_NOT_SUPPORTED,
        })
        report = self.probe(fake)
        self.assertEqual(report["state"], cng.CANDIDATE)
        self.assertEqual(report["algorithm_advertisements"], {
            "ECDSA_P256": "NOT_SUPPORTED", "ED25519": "NOT_SUPPORTED"})
        self.assert_never_authorizes(report)

    def test_other_status_inconclusive_and_blocks(self):
        fake = FakeNCrypt(algorithm_status={"ECDSA_P256": 0, "ED25519": 0x80090027})
        report = self.probe(fake)
        self.assertEqual(report["state"], "BLOCKED")
        self.assertEqual(report["reason"], "ALGORITHM_QUERY_INCONCLUSIVE")
        self.assertEqual(fake.free_calls, [fake.handle])
        self.assert_never_authorizes(report)

    def test_error_during_algorithm_query_frees_handle(self):
        fake = FakeNCrypt(alg_error=OSError("mock query fail"))
        report = self.probe(fake)
        self.assertEqual(report["reason"], "ALGORITHM_QUERY_EXCEPTION")
        self.assertEqual(fake.free_calls, [fake.handle])
        self.assert_never_authorizes(report)

    def test_open_failure_does_not_query_or_free_null_handle(self):
        fake = FakeNCrypt(open_status=0x80090029)
        report = self.probe(fake)
        self.assertEqual(report["reason"], "PROVIDER_UNAVAILABLE_OR_ERROR")
        self.assertFalse(fake.alg_calls)
        self.assertFalse(fake.free_calls)
        self.assert_never_authorizes(report)

    def test_open_exception_fails_closed(self):
        fake = FakeNCrypt(open_error=OSError("mock open error"))
        report = self.probe(fake)
        self.assertEqual(report["reason"], "PROVIDER_OPEN_CALL_FAILED")
        self.assertFalse(fake.alg_calls)
        self.assert_never_authorizes(report)

    def test_success_with_null_handle_does_not_assert_provider(self):
        fake = FakeNCrypt(handle=0)
        report = self.probe(fake)
        self.assertEqual(report["reason"], "PROVIDER_OPEN_RETURNED_NULL_HANDLE")
        self.assert_never_authorizes(report)

    def test_free_failure_blocks_even_if_algorithms_are_advertised(self):
        fake = FakeNCrypt(free_status=0x80090026)
        report = self.probe(fake)
        self.assertEqual(report["reason"], "PROVIDER_HANDLE_RELEASE_UNCONFIRMED")
        self.assertEqual(report["state"], "BLOCKED")
        self.assert_never_authorizes(report)

    def test_free_exception_blocks_even_if_query_succeeds(self):
        fake = FakeNCrypt(free_error=OSError("mock free fail"))
        report = self.probe(fake)
        self.assertEqual(report["reason"], "PROVIDER_HANDLE_RELEASE_UNCONFIRMED")
        self.assert_never_authorizes(report)

    def test_nonce_changes_binding_not_trust(self):
        a = self.probe(FakeNCrypt(), "aa"*32)
        b = self.probe(FakeNCrypt(), "ab"*32)
        self.assertNotEqual(a["challenge_binding_digest"], b["challenge_binding_digest"])
        self.assertEqual(a["algorithm_advertisements"], b["algorithm_advertisements"])
        self.assert_never_authorizes(a)
        self.assert_never_authorizes(b)

    def test_invalid_nonce_rejected_before_native_api(self):
        for nonce in ("", "a"*63, "A"*64, "aa"*33, 12, None, True):
            with self.subTest(nonce=nonce):
                with patch.object(cng.sys, "platform", "win32"), patch.object(
                    cng, "_load_ncrypt"
                ) as loading:
                    report = cng.probe_platform_ksp_algorithm_support_readonly(nonce)
                self.assertEqual(report["reason"], "EXPLICIT_256_BIT_CHALLENGE_REQUIRED")
                loading.assert_not_called()
                self.assert_never_authorizes(report)

    def test_non_windows_rejected_before_native(self):
        with patch.object(cng.sys, "platform", "linux"), patch.object(
            cng, "_load_ncrypt"
        ) as loading:
            report = cng.probe_platform_ksp_algorithm_support_readonly("aa"*32)
        self.assertEqual(report["reason"], "WINDOWS_REQUIRED")
        loading.assert_not_called()

    def test_native_load_failure_rejected(self):
        with patch.object(cng.sys, "platform", "win32"), patch.object(
            cng, "_load_ncrypt", side_effect=OSError("ncrypt unavailable")
        ):
            report = cng.probe_platform_ksp_algorithm_support_readonly("aa"*32)
        self.assertEqual(report["reason"], "NCRYPT_API_UNAVAILABLE")
        self.assert_never_authorizes(report)

    def test_status_non_int_not_silent_success(self):
        for status in (None, True, "0", b"0", object()):
            with self.subTest(status=repr(status)):
                self.assertEqual(cng._status(status), "INCONCLUSIVE")

    def test_status_signed_windows_long_normalized(self):
        self.assertEqual(cng._status(0), "ADVERTISED")
        self.assertEqual(cng._status(cng.NTE_NOT_SUPPORTED), "NOT_SUPPORTED")
        self.assertEqual(cng._status(cng.NTE_NOT_SUPPORTED - 2**32),
                         "NOT_SUPPORTED")

    def test_native_windows_ci_probe_never_claims_device_security(self):
        if sys.platform != "win32":
            self.skipTest("native CNG probe only on Windows GitHub CI")
        report = cng.probe_platform_ksp_algorithm_support_readonly(
            secrets.token_hex(32))
        self.assertIn(report["state"], ("BLOCKED", cng.CANDIDATE))
        self.assert_never_authorizes(report)
        if report["state"] == cng.CANDIDATE:
            self.assertEqual(set(report["algorithm_advertisements"]), set(cng.ALGORITHMS))
            self.assertTrue(report["provider_handle_released"])


if __name__ == "__main__":
    unittest.main()
