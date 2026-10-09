"""Read-only CNG algorithm diagnostic category tests; CI only, no owner PC."""
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


class SilentCNGFailureCategoryTests(unittest.TestCase):
    def call(self, api):
        with patch.object(enum.sys, "platform", "win32"), patch.dict(
            os.environ, CI, clear=True,
        ), patch.object(enum, "_load_ncrypt", return_value=api):
            return enum.observe_silent_signature_algorithms_ci_only("cd"*32)

    def deny_auth(self, report):
        self.assertFalse(report["actual_no_ui_physically_verified"])
        self.assertFalse(report["private_key_enumerated"])
        self.assertFalse(report["private_key_opened"])
        self.assertFalse(report["private_key_created"])
        self.assertFalse(report["host_security_state_modified"])
        self.assertFalse(report["installer_authorized"])
        self.assertFalse(report["safe_to_resume"])

    def test_owner_case_shape_error_is_bounded_not_raw(self):
        out = self.call(FakeCNG(rows=[("INVALID\nNAME",5,0x10)]))
        self.assertEqual(out["reason"], "SILENT_ENUM_INVALID_RESULT")
        self.assertEqual(out["enumeration_failure_category"],
                         "ALGORITHM_NAME_SHAPE_INVALID")
        self.assertEqual(out["algorithm_name_count"],1)
        self.assertNotIn("INVALID",str(out))
        self.deny_auth(out)

    def test_class_error_is_discriminated(self):
        out = self.call(FakeCNG(rows=[("ECDSA_P256",3,0x10)]))
        self.assertEqual(out["enumeration_failure_category"],
                         "SIGNATURE_CLASS_MISMATCH")
        self.deny_auth(out)

    def test_signature_operation_error_is_discriminated(self):
        out = self.call(FakeCNG(rows=[("ECDSA_P256",5,0x4)]))
        self.assertEqual(out["enumeration_failure_category"],
                         "SIGNATURE_OPERATION_MISMATCH")
        self.deny_auth(out)

    def test_duplicate_algorithm_error_is_discriminated(self):
        out = self.call(FakeCNG(rows=[
            ("ECDSA_P256",5,0x10),("ECDSA_P256",5,0x10)]))
        self.assertEqual(out["enumeration_failure_category"],
                         "DUPLICATE_ALGORITHM_NAME")
        self.deny_auth(out)

    def test_excessive_count_does_not_dereference_and_discriminates(self):
        out = self.call(FakeCNG(too_many=True))
        self.assertEqual(out["reason"],"SILENT_ENUM_EXCESSIVE_COUNT")
        self.assertEqual(out["enumeration_failure_category"],
                         "EXCESSIVE_OR_MALFORMED_RECORD_COUNT")
        self.assertIsNone(out["algorithm_name_count"])
        self.deny_auth(out)

    def test_null_nonempty_algorithm_list_discriminated(self):
        out = self.call(FakeCNG(null_list=True))
        self.assertEqual(out["reason"],"SILENT_ENUM_NULL_LIST")
        self.assertEqual(out["enumeration_failure_category"],
                         "NULL_ALGORITHM_ARRAY")
        self.deny_auth(out)

    def test_unexpected_native_exception_discriminated_without_message(self):
        out = self.call(FakeCNG(fail_enum=True))
        self.assertEqual(out["enumeration_failure_category"],
                         "NATIVE_POINTER_OR_DECODING_EXCEPTION")
        self.assertNotIn("test enum exception",str(out))
        self.deny_auth(out)

    def test_valid_enumeration_has_no_failure_category(self):
        out = self.call(FakeCNG(rows=[("ECDSA_P256",5,0x10)]))
        self.assertEqual(out["state"],enum.CANDIDATE)
        self.assertIsNone(out["enumeration_failure_category"])
        self.assertEqual(out["algorithm_name_count"],1)
        self.deny_auth(out)

    def test_direct_record_shape_rejects_non_tuple_with_bounded_code(self):
        for bad in (["A",5,16], ("A",5), ("A",5,16,4), None):
            with self.subTest(bad=bad):
                with self.assertRaises(enum._AlgorithmShapeError) as exc:
                    enum._classify_names([bad])
                self.assertEqual(str(exc.exception),"RECORD_TUPLE_INVALID")

    def test_direct_record_boolean_rejects_bad_class_or_ops(self):
        for rec,code in [
            (("A",True,16),"SIGNATURE_CLASS_MISMATCH"),
            (("A",5,True),"SIGNATURE_OPERATION_MISMATCH"),
        ]:
            with self.subTest(code=code):
                with self.assertRaises(enum._AlgorithmShapeError) as exc:
                    enum._classify_names([rec])
                self.assertEqual(str(exc.exception),code)


if __name__ == "__main__":
    unittest.main()
