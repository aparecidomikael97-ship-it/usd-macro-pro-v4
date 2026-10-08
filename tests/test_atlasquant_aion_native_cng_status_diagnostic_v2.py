"""CI-only synthetic/native error-code diagnostics for CNG KSP V2."""
from __future__ import annotations

import secrets
import sys
import unittest
from unittest.mock import patch

import atlasquant_aion_native_cng_status_diagnostic_v2 as diagnostic
from test_atlasquant_aion_windows_native_cng_ksp_readonly_capability_v1 import FakeNCrypt


class NativeCNGStatusDiagnosticTests(unittest.TestCase):
    def probe(self, fake):
        with patch.object(diagnostic.sys, "platform", "win32"), patch.object(
            diagnostic, "_load_ncrypt", return_value=fake
        ):
            return diagnostic.probe_native_platform_provider_status_codes_readonly(
                "b2" * 32)

    def forever_denied(self, report):
        for name in (
            "tpm_present_verified", "native_provider_identity_attested",
            "tpm_ed25519_key_custody_verified",
            "p256_tpm_key_custody_verified", "key_provisionability_verified",
            "key_nonexportability_verified", "private_key_created",
            "private_key_opened", "private_key_enrolled",
            "system_security_state_modified", "network_deny_verified",
            "physical_attestation_verified", "installer_authorized",
            "build_authorized", "deploy_authorized", "safe_to_resume",
        ):
            self.assertIs(report[name], False, name)

    def test_decode_unsigned_and_signed_not_supported(self):
        for raw in (0x80090029, 0x80090029 - 2**32):
            result = diagnostic.decode_status(raw)
            self.assertEqual(result, {
                "status_hex": "0x80090029",
                "classification": "NOT_SUPPORTED",
                "reason": "NTE_NOT_SUPPORTED",
            })

    def test_decode_success_only_classification_advertised(self):
        result = diagnostic.decode_status(0)
        self.assertEqual(result["classification"], "ADVERTISED")
        self.assertEqual(result["reason"], "SUCCESS")

    def test_known_error_codes_remain_inconclusive(self):
        known = {
            0x80090009: "NTE_BAD_FLAGS",
            0x80090026: "NTE_INVALID_HANDLE",
            0x80090027: "NTE_INVALID_PARAMETER",
            0x80090022: "NTE_SILENT_CONTEXT",
            0x8009002E: "NTE_UI_REQUIRED",
            0x80090010: "NTE_PERM",
            0x80090020: "NTE_FAIL",
            0x80090008: "NTE_BAD_ALGID",
            0x8009002D: "NTE_INTERNAL_ERROR",
            0x80090030: "NTE_DEVICE_NOT_READY",
        }
        for code, name in known.items():
            with self.subTest(name=name):
                actual = diagnostic.decode_status(code)
                self.assertEqual(actual["classification"], "INCONCLUSIVE")
                self.assertEqual(actual["reason"], name)
                self.assertEqual(actual["status_hex"], f"0x{code:08X}")

    def test_unknown_error_code_kept_inconclusive(self):
        actual = diagnostic.decode_status(0x80099999)
        self.assertEqual(actual["reason"], "UNKNOWN_NATIVE_STATUS")
        self.assertEqual(actual["classification"], "INCONCLUSIVE")

    def test_invalid_status_types_never_accepted(self):
        for value in (None, "0", True, False, 1.1, {}, -2**40, 2**40):
            with self.subTest(value=value):
                actual = diagnostic.decode_status(value)
                self.assertEqual(actual["reason"], "MALFORMED_NATIVE_STATUS")
                self.assertIsNone(actual["status_hex"])

    def test_matching_original_api_scope_and_cleanup(self):
        fake = FakeNCrypt(algorithm_status={"ECDSA_P256": 0, "ED25519": 0x80090029})
        result = self.probe(fake)
        self.assertEqual(
            result["state"], "READONLY_NATIVE_STATUS_DIAGNOSTIC_UNTRUSTED")
        self.assertEqual(fake.open_calls, [(diagnostic.PROVIDER, 0)])
        self.assertEqual(
            [(name,flags) for _,name,flags in fake.alg_calls],
            [("ECDSA_P256", diagnostic.NCRYPT_SILENT_FLAG),
             ("ED25519", diagnostic.NCRYPT_SILENT_FLAG)])
        self.assertEqual(fake.free_calls, [fake.handle])
        self.assertTrue(result["handle_release_confirmed"])
        self.assertEqual(result["algorithm_statuses"]["ED25519"]["reason"], "NTE_NOT_SUPPORTED")
        self.forever_denied(result)

    def test_both_advertised_still_no_tpm_or_key_proof(self):
        result = self.probe(FakeNCrypt(
            algorithm_status={"ECDSA_P256": 0, "ED25519": 0}))
        self.assertEqual(result["state"], "READONLY_NATIVE_STATUS_DIAGNOSTIC_UNTRUSTED")
        self.forever_denied(result)

    def test_both_bad_flags_observed_not_misreported_unsupported(self):
        result = self.probe(FakeNCrypt(algorithm_status={
            "ECDSA_P256": 0x80090009, "ED25519": 0x80090009}))
        self.assertEqual(result["reason"], "NATIVE_ALGORITHM_STATUS_INCONCLUSIVE")
        self.assertEqual(result["algorithm_statuses"]["ECDSA_P256"]["reason"], "NTE_BAD_FLAGS")
        self.assertTrue(result["handle_release_confirmed"])
        self.forever_denied(result)

    def test_invalid_handle_observed_not_misreported_unsupported(self):
        result = self.probe(FakeNCrypt(algorithm_status={
            "ECDSA_P256": 0x80090026, "ED25519": 0x80090026}))
        self.assertEqual(result["algorithm_statuses"]["ED25519"]["reason"], "NTE_INVALID_HANDLE")
        self.assertEqual(result["state"], "BLOCKED")
        self.forever_denied(result)

    def test_open_error_status_recorded_no_query(self):
        fake = FakeNCrypt(open_status=0x80090010)
        result = self.probe(fake)
        self.assertEqual(result["open_status"]["reason"], "NTE_PERM")
        self.assertEqual(result["reason"], "PROVIDER_OPEN_FAILED")
        self.assertFalse(fake.alg_calls)
        self.assertFalse(fake.free_calls)
        self.forever_denied(result)

    def test_open_success_null_handle_denied(self):
        result = self.probe(FakeNCrypt(handle=0))
        self.assertEqual(result["reason"], "PROVIDER_OPEN_NULL_HANDLE")
        self.forever_denied(result)

    def test_query_exception_still_frees_handle(self):
        fake = FakeNCrypt(alg_error=OSError("synthetic"))
        result = self.probe(fake)
        self.assertEqual(result["reason"], "QUERY_EXCEPTION")
        self.assertEqual(fake.free_calls, [fake.handle])
        self.forever_denied(result)

    def test_free_failure_overrides_algorithm_advertisement(self):
        fake = FakeNCrypt(free_status=0x80090026)
        result = self.probe(fake)
        self.assertEqual(result["free_status"]["reason"], "NTE_INVALID_HANDLE")
        self.assertFalse(result["handle_release_confirmed"])
        self.assertEqual(result["reason"], "HANDLE_RELEASE_UNCONFIRMED")
        self.forever_denied(result)

    def test_free_exception_also_blocks(self):
        result = self.probe(FakeNCrypt(free_error=OSError("synthetic")))
        self.assertEqual(result["reason"], "HANDLE_RELEASE_UNCONFIRMED")
        self.forever_denied(result)

    def test_invalid_nonce_does_not_load_provider(self):
        with patch.object(diagnostic.sys, "platform", "win32"), patch.object(
            diagnostic, "_load_ncrypt"
        ) as loader:
            result = diagnostic.probe_native_platform_provider_status_codes_readonly(
                "xyz")
        self.assertEqual(result["reason"], "CHALLENGE_REQUIRED")
        loader.assert_not_called()

    def test_wrong_os_does_not_load_provider(self):
        with patch.object(diagnostic.sys, "platform", "linux"), patch.object(
            diagnostic, "_load_ncrypt"
        ) as loader:
            result = diagnostic.probe_native_platform_provider_status_codes_readonly(
                "a1"*32)
        self.assertEqual(result["reason"], "WINDOWS_REQUIRED")
        loader.assert_not_called()

    def test_native_windows_runner_is_always_non_authoritative(self):
        if sys.platform != "win32":
            self.skipTest("native read-only CNG probe only on Windows CI")
        actual = diagnostic.probe_native_platform_provider_status_codes_readonly(
            secrets.token_hex(32))
        self.assertIn(actual["state"], (
            "BLOCKED", "READONLY_NATIVE_STATUS_DIAGNOSTIC_UNTRUSTED"))
        self.forever_denied(actual)


if __name__ == "__main__":
    unittest.main()
