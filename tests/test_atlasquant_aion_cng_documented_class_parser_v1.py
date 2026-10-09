"""No-owner-device tests for documented NCryptAlgorithmName.dwClass values."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import atlasquant_aion_native_cng_silent_signature_algorithm_enum_v1 as enum
from test_atlasquant_aion_native_cng_silent_signature_algorithm_enum_v1 import FakeCNG

CI = {
    "GITHUB_ACTIONS": "true",
    "GITHUB_EVENT_NAME": "pull_request",
    "RUNNER_OS": "Windows",
    "GITHUB_REPOSITORY": "aparecidomikael97-ship-it/usd-macro-pro-v4",
}


class DocumentedCNGClassesTests(unittest.TestCase):
    def probe(self, records):
        fake = FakeCNG(rows=records)
        with patch.object(enum.sys, "platform", "win32"), patch.dict(
            os.environ, CI, clear=True,
        ), patch.object(enum, "_load_ncrypt", return_value=fake):
            actual = enum.observe_silent_signature_algorithms_ci_only("a9" * 32)
        return actual, fake

    def still_denies_everything(self, out):
        self.assertFalse(out["owner_pc_execution_authorized_by_code"])
        self.assertFalse(out["actual_no_ui_physically_verified"])
        for key in (
            "tpm_presence_verified", "tpm_ed25519_key_custody_verified",
            "p256_tpm_key_custody_verified", "algorithm_provisionability_verified",
            "key_nonexportability_verified", "private_key_created",
            "private_key_opened", "private_key_enumerated",
            "private_key_enrolled", "host_security_state_modified",
            "physical_attestation_verified", "network_deny_verified",
            "collector_launch_authorized", "installer_authorized",
            "build_authorized", "deploy_authorized", "safe_to_resume",
        ):
            self.assertIs(out[key], False, key)

    def test_standard_interface_constants_are_exactly_three_documented(self):
        self.assertEqual(enum.DOCUMENTED_NCRYPT_CLASSES, frozenset({3, 4, 5}))

    def test_asymmetric_interface_class_can_have_signature_operation(self):
        out, fake = self.probe([("RSA", 3, 0x14), ("ECDSA_P256", 5, 0x10)])
        self.assertEqual(out["state"], enum.CANDIDATE, out)
        self.assertEqual(out["target_algorithm_names"], {
            "ECDSA_P256": "LISTED", "ED25519": "NOT_LISTED"})
        self.assertEqual([a[0] for a in fake.calls],
                         ["open", "enum", "free_buffer", "free_provider"])
        self.still_denies_everything(out)

    def test_documented_secret_agreement_interface_with_signature_bit_is_parsed_only(self):
        out, fake = self.probe([("OTHER_SIGNER", 4, 0x18)])
        self.assertEqual(out["state"], enum.CANDIDATE)
        self.assertEqual(out["target_algorithm_names"], {
            "ECDSA_P256": "NOT_LISTED", "ED25519": "NOT_LISTED"})
        self.still_denies_everything(out)

    def test_signature_interface_class_is_also_accepted(self):
        out, fake = self.probe([("ED25519", 5, 0x10)])
        self.assertEqual(out["state"], enum.CANDIDATE)
        self.assertEqual(out["target_algorithm_names"]["ED25519"], "LISTED")
        self.still_denies_everything(out)

    def test_all_three_documented_classes_mixed_in_one_result(self):
        out, fake = self.probe([
            ("RSA",3,0x14), ("SOME_ALG",4,0x18),
            ("ECDSA_P256",5,0x10), ("ED25519",5,0x10),
            ("ECDSA",3,0x10)])
        self.assertEqual(out["state"], enum.CANDIDATE)
        self.assertEqual(out["algorithm_name_count"],5)
        self.assertIsNone(out["enumeration_failure_category"])
        self.still_denies_everything(out)

    def test_unknown_class_still_blocks(self):
        for klass in (0,1,2,6,7,0xFFFFFFFF,False,True):
            with self.subTest(klass=klass):
                with self.assertRaises(enum._AlgorithmShapeError) as err:
                    enum._classify_names([("ECDSA_P256",klass,0x10)])
                self.assertEqual(str(err.exception),
                                 "UNRECOGNIZED_NCRYPT_ALGORITHM_CLASS")

    def test_mandatory_signature_operation_remains_checked_for_every_class(self):
        for klass in (3,4,5):
            for ops in (0,0x4,0x8,0xC,True):
                with self.subTest(klass=klass,ops=ops):
                    with self.assertRaises(enum._AlgorithmShapeError) as err:
                        enum._classify_names([("RSA",klass,ops)])
                    self.assertEqual(str(err.exception),
                                     "SIGNATURE_OPERATION_MISMATCH")

    def test_raw_algorithm_names_still_not_disclosed(self):
        out, fake = self.probe([("COMPANY_SECRET_PROVIDER_SIGNER",3,0x10)])
        self.assertNotIn("COMPANY_SECRET_PROVIDER_SIGNER",str(out))
        self.still_denies_everything(out)

    def test_silent_flag_required_and_no_retry_zero_flags(self):
        out, fake = self.probe([("RSA",3,0x14)])
        enumeration_calls=[c for c in fake.calls if c[0]=="enum"]
        self.assertEqual(enumeration_calls, [
            ("enum",0x1234,enum.SIGNATURE_OPERATION,enum.NCRYPT_SILENT_FLAG)])
        self.still_denies_everything(out)

    def test_duplicate_algorithm_blocks_regardless_of_class(self):
        out, fake = self.probe([("RSA",3,0x14),("RSA",5,0x10)])
        self.assertEqual(out["reason"],"SILENT_ENUM_INVALID_RESULT")
        self.assertEqual(out["enumeration_failure_category"],
                         "DUPLICATE_ALGORITHM_NAME")
        self.still_denies_everything(out)


if __name__ == "__main__":
    unittest.main()
