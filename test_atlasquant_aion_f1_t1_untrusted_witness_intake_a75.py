"""A75 negative-only witness intake matrix; all evidence is fictional.

No keys or signatures are generated or verified. No GitHub API, network,
persistent nonce registry, local filesystem, Windows TPM or Worker is used.
"""
import unittest
from copy import deepcopy

from atlasquant_aion_f1_t1_untrusted_witness_intake_a75 import (
    SCHEMA, inspect_untrusted_witness_claim,
)

NOW = "2026-10-14T17:00:00Z"
SCOPE = {
    "repo_id": 1366962269,
    "owner_id": 328188988,
    "branch": "atlasquant-runtime",
    "path": "dados/aion/checkpoint_master.json",
    "tenant_id": "synthetic-lab-tenant",
    "workspace_id": "synthetic-lab-workspace",
}
CLAIM = {
    **SCOPE,
    "schema": SCHEMA,
    "head_sha": "a" * 40,
    "checkpoint_blob_sha": "b" * 40,
    "checkpoint_digest": "c" * 64,
    "epoch": 3,
    "sequence": 7,
    "previous_sequence": 6,
    "previous_head_sha": "d" * 40,
    "nonce": "LAB_SYNTHETIC_NONCE_123456789",
    "issued_at": "2026-10-14T16:59:30Z",
    "expires_at": "2026-10-14T17:02:30Z",
    "witness_issuer": "synthetic-external-witness",
    "key_id": "synthetic-key-id",
    "signature_b64": "NOT_A_VERIFIED_CRYPTOGRAPHIC_SIGNATURE",
}
SNAPSHOT = {"head_sha": "a" * 40, "checkpoint_blob_sha": "b" * 40}


def assess(claim=None, *, scope=None, snap=None, watermark=None, now=NOW):
    return inspect_untrusted_witness_claim(
        deepcopy(CLAIM) if claim is None else claim,
        expected_scope=deepcopy(SCOPE) if scope is None else scope,
        now_ts=now,
        observed_snapshot=deepcopy(SNAPSHOT) if snap is None else snap,
        locally_known_high_water=watermark,
    )


class A75SourceWitnessIntakeHardStopTests(unittest.TestCase):
    def assert_denied(self, result):
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "INDEPENDENT_SOURCE_WITNESS_NOT_ENROLLED")
        self.assertIn("INDEPENDENT_SOURCE_WITNESS_NOT_ENROLLED", result["blockers"])
        self.assertIn("EXTERNAL_CUSTODY_AND_FRESHNESS_UNPROVEN", result["blockers"])
        for field in (
            "claim_signature_verified", "external_custody_verified",
            "fresh_github_head_independently_verified",
            "monotonic_high_water_independently_verified",
            "replay_prevented_independently", "source_authenticity_verified",
            "independent_witness_verified", "external_activation_allowed",
            "worker_execution_allowed", "runtime_modified", "network_called",
        ):
            self.assertIs(result[field], False, field)

    def test_01_perfectly_consistent_claim_is_still_never_authority(self):
        before = deepcopy(CLAIM)
        result = assess()
        self.assert_denied(result)
        self.assertIs(result["local_format_consistent"], True)
        self.assertEqual(CLAIM, before)

    def test_02_forged_verified_flags_and_unknown_keys_rejected(self):
        for field in ("independent_witness_verified", "signature_verified", "source_authenticity_verified", "external_activation_allowed"):
            with self.subTest(field=field):
                c = deepcopy(CLAIM)
                c[field] = True
                r = assess(c)
                self.assert_denied(r)
                self.assertIn("WITNESS_CLAIM_SHAPE_MISMATCH", r["blockers"])

    def test_03_foreign_repo_owner_branch_path_tenant_workspace_denied(self):
        mutations = {
            "repo_id": 1366962270, "owner_id": 328188989,
            "branch": "main", "path": "outro/checkpoint.json",
            "tenant_id": "tenant-outro", "workspace_id": "workspace-outro",
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                c = deepcopy(CLAIM)
                c[field] = value
                r = assess(c)
                self.assert_denied(r)
                self.assertIn("WITNESS_SCOPE_MISMATCH:" + field, r["blockers"])

    def test_04_current_head_and_blob_mismatch_denied(self):
        for field in ("head_sha", "checkpoint_blob_sha"):
            with self.subTest(field=field):
                c = deepcopy(CLAIM)
                c[field] = "e" * 40
                r = assess(c)
                self.assert_denied(r)
                self.assertIn("WITNESS_SNAPSHOT_MISMATCH:" + field, r["blockers"])

    def test_05_replay_or_rollback_detected_by_given_local_mark(self):
        for watermark in (7, 8, 900):
            with self.subTest(watermark=watermark):
                r = assess(watermark=watermark)
                self.assert_denied(r)
                self.assertIn("LOCAL_REPLAY_OR_ROLLBACK_SUSPECTED", r["blockers"])

    def test_06_even_higher_sequence_than_caller_mark_never_enrolls(self):
        r = assess(watermark=6)
        self.assert_denied(r)
        self.assertIs(r["local_format_consistent"], True)

    def test_07_missing_or_boolean_sequence_never_counted(self):
        for value in (True, False, 0, -1, None, "7", {}, 2**70):
            with self.subTest(value=str(value)):
                c = deepcopy(CLAIM)
                c["sequence"] = value
                r = assess(c)
                self.assert_denied(r)
                self.assertIn("WITNESS_SEQUENCE_INVALID:sequence", r["blockers"])

    def test_08_sequence_gap_and_bad_predecessor_blocked(self):
        c = deepcopy(CLAIM)
        c["previous_sequence"] = 4
        self.assertIn("WITNESS_SEQUENCE_GAP_OR_ROLLBACK", assess(c)["blockers"])
        c = deepcopy(CLAIM)
        c["previous_head_sha"] = "GENESIS"
        self.assertIn("WITNESS_PREVIOUS_HEAD_INVALID", assess(c)["blockers"])

    def test_09_forged_time_future_stale_expired_rejected(self):
        cases = [
            ("2026-10-14T17:10:00Z", "2026-10-14T17:12:00Z"),
            ("2026-10-14T16:30:00Z", "2026-10-14T17:02:30Z"),
            ("2026-10-14T16:00:00Z", "2026-10-14T16:05:00Z"),
        ]
        for issued, expires in cases:
            with self.subTest(issued=issued):
                c = deepcopy(CLAIM)
                c["issued_at"], c["expires_at"] = issued, expires
                r = assess(c)
                self.assert_denied(r)
                self.assertTrue(any("WITNESS_" in x and ("TIME" in x or "EXPIRED" in x or "WINDOW" in x) for x in r["blockers"]))
        self.assertIn("CLOCK_INVALID", assess(now="invalid")["blockers"])

    def test_10_missing_self_signed_and_unreadable_claims_do_not_authorize(self):
        c = deepcopy(CLAIM)
        del c["signature_b64"]
        self.assertIn("WITNESS_CLAIM_SHAPE_MISMATCH", assess(c)["blockers"])
        self.assert_denied(assess(None))
        self.assert_denied(assess("fake-receipt-string"))

    def test_11_wrong_expected_scope_cannot_be_trusted(self):
        self.assertIn("EXPECTED_SCOPE_INCOMPLETE_OR_UNTRUSTED", assess(scope={"repo_id": 1})["blockers"])
        self.assert_denied(assess(scope=deepcopy(CLAIM)))

    def test_12_identity_numeric_bool_is_invalid(self):
        for field in ("repo_id", "owner_id"):
            with self.subTest(field=field):
                c = deepcopy(CLAIM)
                c[field] = True
                r = assess(c)
                self.assert_denied(r)
                self.assertIn("WITNESS_ID_INVALID:" + field, r["blockers"])


if __name__ == "__main__":
    unittest.main()
