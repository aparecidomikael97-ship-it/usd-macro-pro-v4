import unittest

from atlasquant_aion_tenant_evidence_binding import (
    EVIDENCE_KINDS,
    build_evidence_record,
    validate_evidence_record,
)

S1 = "sha256:" + ("1" * 64)
S2 = "sha256:" + ("2" * 64)

class TenantEvidenceBindingTests(unittest.TestCase):
    def test_all_required_kinds_build_and_validate(self):
        for kind in EVIDENCE_KINDS:
            row = build_evidence_record(
                kind,
                subject_digest=S1,
                result_digest=S2,
                test_count=10,
            )
            checked = validate_evidence_record(row, expected_kind=kind)
            self.assertTrue(checked["valid"])
            self.assertFalse(checked["authority"])
            self.assertTrue(row["digest"].startswith("sha256:"))

    def test_subject_tamper_is_detected(self):
        row = build_evidence_record(
            "ACL_STORE", subject_digest=S1, result_digest=S2, test_count=3
        )

        row["subject_digest"] = "sha256:" + ("3" * 64)
        checked = validate_evidence_record(row, expected_kind="ACL_STORE")
        self.assertFalse(checked["valid"])
        self.assertIn("EVIDENCE_DIGEST_MISMATCH", checked["reasons"])

    def test_result_tamper_is_detected(self):
        row = build_evidence_record(
            "TENANT_E2E", subject_digest=S1, result_digest=S2, test_count=5
        )
        row["result_digest"] = "sha256:" + ("4" * 64)
        checked = validate_evidence_record(row, expected_kind="TENANT_E2E")
        self.assertFalse(checked["valid"])
        self.assertIn("EVIDENCE_DIGEST_MISMATCH", checked["reasons"])

    def test_kind_swap_is_detected(self):
        row = build_evidence_record(
            "BACKUP_RESTORE", subject_digest=S1, result_digest=S2, test_count=4
        )
        checked = validate_evidence_record(row, expected_kind="REVOCATION_REPLAY")
        self.assertFalse(checked["valid"])
        self.assertIn("KIND_MISMATCH", checked["reasons"])

    def test_authority_escalation_is_detected(self):
        row = build_evidence_record(
            "DURABLE_STORE", subject_digest=S1, result_digest=S2, test_count=6
        )
        row["authority"] = True
        checked = validate_evidence_record(row, expected_kind="DURABLE_STORE")
        self.assertFalse(checked["valid"])
        self.assertIn("AUTHORITY_FORBIDDEN", checked["reasons"])

    def test_zero_test_count_is_rejected(self):
        with self.assertRaises(ValueError):
            build_evidence_record(
                "IDENTITY_REGISTRY",
                subject_digest=S1,
                result_digest=S2,
                test_count=0,
            )

    def test_fail_status_can_be_integrity_valid_but_not_a_pass(self):
        row = build_evidence_record(
            "TENANT_E2E",
            subject_digest=S1,
            result_digest=S2,
            test_count=2,
            status="FAIL",
        )
        checked = validate_evidence_record(row, expected_kind="TENANT_E2E")
        self.assertTrue(checked["valid"])
        self.assertEqual(checked["status"], "FAIL")

if __name__ == "__main__":
    unittest.main()
