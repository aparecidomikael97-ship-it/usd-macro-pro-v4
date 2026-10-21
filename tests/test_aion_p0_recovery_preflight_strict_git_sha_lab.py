"""RED-first: recovery preflight must require a valid Git blob SHA for CAS.

These tests call real recovery_preflight and restore_checkpoint_revision but
NEVER call GitHub or save. All state is local, synthetic and review-only.
"""
from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch
import unittest

from test_atlasquant_aion_recovery_traceability_gate import _current, _candidate
from atlasquant_aion_recovery import recovery_preflight, restore_checkpoint_revision
from atlasquant_aion_memory import RuntimeConfig


class RecoveryPreflightStrictSHAInvariants(unittest.TestCase):
    def setUp(self):
        self.current=_current()
        self.candidate=_candidate()

    def blocked_sha(self, bad):
        current=deepcopy(self.current)
        current["sha"]=bad
        out=recovery_preflight(current,deepcopy(self.candidate))
        self.assertFalse(out.get("allowed"),bad)
        self.assertIn("SHA",out.get("reason",""))
        self.assertFalse(out.get("executes_action",False))

    def test_01_true_current_blob_sha_preserves_review_eligibility(self):
        out=recovery_preflight(self.current,self.candidate)
        self.assertTrue(out["allowed"])
        self.assertEqual(out["expected_sha"],"b"*40)
        self.assertFalse(out["executes_action"])

    def test_02_empty_sha_denied(self):
        self.blocked_sha("")

    def test_03_non_hex_sha_denied(self):
        self.blocked_sha("not-a-github-blob")

    def test_04_short_hex_sha_denied(self):
        self.blocked_sha("abcdef0")

    def test_05_long_hex_sha_denied(self):
        self.blocked_sha("b"*41)

    def test_06_40_char_non_hex_sha_denied(self):
        self.blocked_sha("z"*40)

    def test_07_sha_with_newline_denied(self):
        self.blocked_sha("b"*40+"\n123")

    def test_08_sha_with_git_algo_prefix_denied_not_valid_contents_sha(self):
        self.blocked_sha("sha1:"+"b"*40)

    def test_09_numeric_sha_never_coerced_to_approved_cas(self):
        self.blocked_sha(1)

    def test_10_boolean_sha_never_coerced_to_approved_cas(self):
        self.blocked_sha(True)

    def test_11_valid_uppercase_hex_sha_still_eligible(self):
        curr=deepcopy(self.current)
        curr["sha"]="B"*40
        out=recovery_preflight(curr,self.candidate)
        self.assertTrue(out["allowed"])
        self.assertEqual(out["expected_sha"],"B"*40)

    def test_12_invalid_sha_blocks_restore_without_readback_or_write(self):
        curr=deepcopy(self.current)
        curr["sha"]="wrong-but-truthy"
        cfg=RuntimeConfig(token="unused",repo="owner/repo",branch="atlasquant-runtime")
        with patch("atlasquant_aion_recovery.load_checkpoint_revision") as read, patch(
            "atlasquant_aion_recovery.save_runtime_checkpoint"
        ) as write:
            result=restore_checkpoint_revision(self.candidate,curr,cfg,approved=True)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertIs(result["saved"],False)
        self.assertIs(result["verified"],False)
        read.assert_not_called()
        write.assert_not_called()

    def test_13_invalid_object_current_does_not_throw(self):
        result=recovery_preflight(4,self.candidate)
        self.assertFalse(result["allowed"])
        self.assertFalse(result.get("executes_action",False))

    def test_14_invalid_object_candidate_does_not_throw(self):
        result=recovery_preflight(self.current,4)
        self.assertFalse(result["allowed"])
        self.assertFalse(result.get("executes_action",False))

    def test_15_same_contents_still_denied(self):
        curr=deepcopy(self.current)
        cand=deepcopy(self.candidate)
        cand["checkpoint"]=deepcopy(curr["checkpoint"])
        from atlasquant_aion_memory import checkpoint_integrity_report,checkpoint_source_digest
        cand["integrity"]=checkpoint_integrity_report(cand["checkpoint"])
        cand["digest"]=checkpoint_source_digest(cand["checkpoint"])
        result=recovery_preflight(curr,cand)
        self.assertFalse(result["allowed"])

    def test_16_bad_claimed_digest_still_denied(self):
        cand=deepcopy(self.candidate)
        cand["digest"]="f"*16
        result=recovery_preflight(self.current,cand)
        self.assertFalse(result["allowed"])
        self.assertIn("digest",result["reason"])

    def test_17_restoration_rejects_bogus_cas_before_any_external_action(self):
        for value in ("not-hex","b"*39,"b"*41,False):
            current=deepcopy(self.current)
            current["sha"]=value
            with self.subTest(value=value),patch(
                "atlasquant_aion_recovery.load_checkpoint_revision"
            ) as read,patch("atlasquant_aion_recovery.save_runtime_checkpoint") as write:
                out=restore_checkpoint_revision(
                    self.candidate,current,
                    RuntimeConfig(token="unused",repo="owner/repo",branch="atlasquant-runtime"),
                    approved=True,
                )
                self.assertEqual(out["status"],"BLOCKED")
                read.assert_not_called()
                write.assert_not_called()


if __name__=="__main__":
    unittest.main()
