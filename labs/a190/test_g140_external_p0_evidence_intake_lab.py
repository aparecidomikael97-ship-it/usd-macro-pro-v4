"""G140 tests: candidate artifacts are NEVER independent proof by themselves.

All verdicts intentionally HARD_NO_GO; even a perfectly populated dossier
with external-sounding strings cannot close P0 without independently
adjudicated custody/enrollment/native SQLite/provider evidence.
"""
from copy import deepcopy
from hashlib import sha256
import unittest

from labs.a190.g140_external_p0_evidence_intake_lab import (
    SCHEMA, RED_G122_IDS, evaluate_p0_external_evidence_lab,
)


HEAD = "3609e423228812f4e096391a71cd339b088af51c"


def evidence(*, source="independent_external_claimed", result="pass_claimed"):
    return {
        "schema": SCHEMA,
        "repository_commit": HEAD,
        "evidence": [
            {
                "case_id": case,
                "claimed_result": result,
                "source_kind": source,
                "source_identifier": "claimed-provider-domain:case-"+str(i),
                "artifact_sha256": sha256(case.encode()).hexdigest(),
                "independence_claimed": True,
                "reviewer_claimed": "claimed-human-reviewer-NOT-VERIFIED",
            }
            for i, case in enumerate(RED_G122_IDS)
        ],
    }


class G140ExternalP0EvidenceIntakeAntiGreenwashTests(unittest.TestCase):
    def assert_no_go(self, dossier, *, expected_status=None):
        result = evaluate_p0_external_evidence_lab(dossier)
        if expected_status is not None:
            self.assertEqual(result.status, expected_status)
        self.assertIn("NO_GO", result.status)
        self.assertIs(result.externally_verified, False)
        self.assertEqual(result.p0_homologated, 0)
        self.assertEqual(result.p0_total, 6)
        self.assertIs(result.allows_worker, False)
        self.assertIs(result.allows_provider_send, False)
        self.assertIs(result.allows_retry, False)
        return result

    def test_01_none_or_empty_documents_fail_closed(self):
        for value in (None, False, [], {}, "", 1):
            with self.subTest(value=value):
                self.assert_no_go(value, expected_status="DENY_INVALID_DOSSIER_HARD_NO_GO")

    def test_02_full_five_claimed_pass_from_claimed_external_still_not_go(self):
        decision = self.assert_no_go(
            evidence(),
            expected_status="EXTERNAL_CLAIMS_REQUIRE_INDEPENDENT_ADJUDICATION_HARD_NO_GO",
        )
        self.assertTrue(decision.requires_independent_review)
        print("G140_FIVE_CLAIMED_EXTERNAL_GREEN=REVIEW_REQUIRED_HARD_NO_GO_ZERO_P0")

    def test_03_synthetic_lab_claims_never_external(self):
        self.assert_no_go(
            evidence(source="synthetic_lab"),
            expected_status="DENY_SELF_ATTESTED_EVIDENCE_HARD_NO_GO",
        )

    def test_04_same_host_ci_and_self_attested_claims_never_authority(self):
        for source in ("same_host", "ci_fixture", "self_attested"):
            with self.subTest(source=source):
                self.assert_no_go(
                    evidence(source=source),
                    expected_status="DENY_SELF_ATTESTED_EVIDENCE_HARD_NO_GO",
                )
        print("G140_G125_GREEN_AND_G139_LOCAL_KEYS=NOT_EXTERNAL_P0_EVIDENCE")

    def test_05_one_synthetic_row_poison_prevents_greenwashing_aggregate(self):
        manifest = evidence()
        manifest["evidence"][2]["source_kind"] = "ci_fixture"
        self.assert_no_go(
            manifest,
            expected_status="DENY_SELF_ATTESTED_EVIDENCE_HARD_NO_GO",
        )

    def test_06_missing_one_actual_g122_requirement_denied(self):
        manifest = evidence()
        manifest["evidence"].pop()
        self.assert_no_go(
            manifest,
            expected_status="DENY_INCOMPLETE_G122_HARD_NO_GO",
        )

    def test_07_duplicate_actual_requirement_rejected(self):
        manifest = evidence()
        manifest["evidence"][1]["case_id"] = manifest["evidence"][0]["case_id"]
        self.assert_no_go(
            manifest,
            expected_status="DENY_INVALID_DOSSIER_HARD_NO_GO",
        )

    def test_08_invented_or_removed_g122_assertion_rejected(self):
        manifest = evidence()
        manifest["evidence"][1]["case_id"] = "test_new_fictional_p0_certified"
        self.assert_no_go(
            manifest,
            expected_status="DENY_INVALID_DOSSIER_HARD_NO_GO",
        )

    def test_09_unrecognized_evidence_source_must_not_be_auto_trusted(self):
        manifest = evidence()
        manifest["evidence"][0]["source_kind"] = "validated_on_github"
        self.assert_no_go(manifest)

    def test_10_deceptive_claimed_result_status_not_a_trust_flag(self):
        manifest = evidence()
        manifest["evidence"][0]["claimed_result"] = "external_p0_homologated"
        self.assert_no_go(manifest)

    def test_11_unmet_canonical_requirements_remain_denied(self):
        self.assert_no_go(
            evidence(result="unmet"),
            expected_status="DENY_G122_STILL_UNMET_HARD_NO_GO",
        )
        print("G140_REAL_G122_RED=REMAINS_RED_WITH_NO_PASS_RECLASSIFICATION")

    def test_12_not_tested_requirements_remain_denied(self):
        self.assert_no_go(
            evidence(result="not_tested"),
            expected_status="DENY_G122_STILL_UNMET_HARD_NO_GO",
        )

    def test_13_claimed_external_cert_and_sha256_cannot_verify_provenance(self):
        manifest = evidence()
        for row in manifest["evidence"]:
            row["reviewer_claimed"] = "independent-security-auditor-claimed"
            row["source_identifier"] = "https://fake-but-well-formed-claim.invalid/proof"
            row["artifact_sha256"] = "0" * 64
        result = self.assert_no_go(
            manifest,
            expected_status="EXTERNAL_CLAIMS_REQUIRE_INDEPENDENT_ADJUDICATION_HARD_NO_GO",
        )
        self.assertIn("file_hash_does_not_prove_independence", result.checks)

    def test_14_changed_commit_or_additional_fields_rejected(self):
        manifest = evidence()
        manifest["repository_commit"] = "not-a-real-commit"
        self.assert_no_go(manifest)
        another = evidence()
        another["claimed_p0_closed"] = 6
        self.assert_no_go(another)

    def test_15_boolean_vs_string_and_malformed_hash_rejected(self):
        for field, bad in (("independence_claimed", 1),
                           ("artifact_sha256", "pass"),
                           ("source_identifier", ""),
                           ("reviewer_claimed", "<script>"),
                           ("claimed_result", True)):
            with self.subTest(field=field):
                manifest = evidence()
                manifest["evidence"][0][field] = bad
                self.assert_no_go(manifest)

    def test_16_missing_payload_field_and_injected_approval_rejected(self):
        manifest = evidence()
        manifest["evidence"][0].pop("artifact_sha256")
        self.assert_no_go(manifest)
        manifest2 = evidence()
        manifest2["evidence"][0]["grants_authority"] = True
        self.assert_no_go(manifest2)

    def test_17_exact_test_names_guard_real_unmasked_g122(self):
        from lab_a183_external_requirements_red import (
            ExternalRequirementsRed, LiveNativeRollbackRequirementsRed,
        )
        from unittest import TestLoader
        actual = set(TestLoader().getTestCaseNames(ExternalRequirementsRed)) | set(
            TestLoader().getTestCaseNames(LiveNativeRollbackRequirementsRed))
        self.assertEqual(set(RED_G122_IDS), actual)
        self.assert_no_go(evidence(result="unmet"))
        print("G140_FIVE_G122_CANONICAL_TEST_NAMES=UNCHANGED_AND_UNMASKED")

    def test_18_order_of_evidence_rows_does_not_change_security_decision(self):
        manifest = evidence()
        manifest["evidence"].reverse()
        self.assert_no_go(
            manifest,
            expected_status="EXTERNAL_CLAIMS_REQUIRE_INDEPENDENT_ADJUDICATION_HARD_NO_GO",
        )

    def test_19_local_override_fields_cannot_grant_worker_or_send(self):
        manifest = evidence()
        for extra in ("worker_enabled", "send_authorized", "p0_homologated"):
            modified = deepcopy(manifest)
            modified[extra] = True
            self.assert_no_go(modified)
        self.assert_no_go(evidence())
        print("G140_SELF_ATTESTED_READY_FLAG_CANNOT_ENABLE_SEND_OR_WORKER")


if __name__ == "__main__":
    unittest.main(verbosity=2)
