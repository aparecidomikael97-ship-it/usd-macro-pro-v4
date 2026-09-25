import base64
import json
import unittest
from unittest.mock import MagicMock, patch

from atlasquant_aion_memory import (
    RuntimeConfig,
    checkpoint_integrity_report,
    default_checkpoint,
)
from atlasquant_aion_recovery import (
    list_checkpoint_revisions,
    load_checkpoint_revision,
    recovery_preflight,
    restore_checkpoint_revision,
)


class AtlasQuantAionRecoveryTests(unittest.TestCase):
    def cfg(self):
        return RuntimeConfig(
            token="token-test",
            repo="owner/repo",
            branch="atlasquant-runtime",
        )

    def candidate(self, *, revision="abcdef1234567890abcdef1234567890abcdef12"):
        cp=default_checkpoint()
        cp["aion"]["priority"]="recovery candidate"
        return {
            "status":"CONFIRMED",
            "revision":revision,
            "checkpoint":cp,
            "integrity":checkpoint_integrity_report(cp),
        }

    def current(self, *, mismatch=False):
        cp=default_checkpoint()
        integrity=checkpoint_integrity_report(cp)
        if mismatch:
            cp["studio"]["digest"]="tampered"
            integrity=checkpoint_integrity_report(cp)
        return {
            "status":"CONFIRMED",
            "sha":"0123456789abcdef0123456789abcdef01234567",
            "checkpoint":cp,
            "integrity":integrity,
        }

    def test_history_list_is_read_only_and_filters_invalid_revisions(self):
        response=MagicMock()
        response.raise_for_status.return_value=None
        response.json.return_value=[
            {
                "sha":"abcdef1234567890abcdef1234567890abcdef12",
                "commit":{
                    "message":"AION checkpoint",
                    "author":{"date":"2026-09-24T22:00:00Z"},
                },
            },
            {"sha":"not-a-sha","commit":{"message":"invalid"}},
        ]
        with patch("atlasquant_aion_recovery.requests.get",return_value=response) as get:
            result=list_checkpoint_revisions(self.cfg(),limit=12)
        self.assertEqual(result["status"],"CONFIRMED")
        self.assertEqual(result["count"],1)
        self.assertFalse(result["executes_action"])
        self.assertEqual(
            result["items"][0]["revision"],
            "abcdef1234567890abcdef1234567890abcdef12",
        )
        self.assertEqual(get.call_args.kwargs["params"]["path"],"dados/aion/checkpoint_master.json")

    def test_history_refuses_code_branch_before_network(self):
        cfg=RuntimeConfig(token="x",repo="owner/repo",branch="main")
        with patch("atlasquant_aion_recovery.requests.get") as get:
            result=list_checkpoint_revisions(cfg)
        self.assertEqual(result["status"],"BLOCKED")
        get.assert_not_called()

    def test_revision_load_verifies_checkpoint_integrity(self):
        cp=default_checkpoint()
        raw=json.dumps(cp).encode("utf-8")
        response=MagicMock()
        response.raise_for_status.return_value=None
        response.json.return_value={"content":base64.b64encode(raw).decode("ascii")}
        revision="abcdef1234567890abcdef1234567890abcdef12"
        with patch("atlasquant_aion_recovery.requests.get",return_value=response):
            result=load_checkpoint_revision(revision,self.cfg())
        self.assertEqual(result["status"],"CONFIRMED")
        self.assertEqual(result["integrity"]["state"],"CONFIRMED")
        self.assertFalse(result["executes_action"])

    def test_recovery_can_repair_current_mismatch_using_clean_candidate(self):
        preflight=recovery_preflight(
            self.current(mismatch=True),
            self.candidate(),
        )
        self.assertTrue(preflight["allowed"])
        self.assertEqual(preflight["candidate_integrity"],"CONFIRMED")
        self.assertTrue(preflight["expected_sha"])

    def test_recovery_blocks_tampered_candidate(self):
        candidate=self.candidate()
        candidate["checkpoint"]["business"]["digest"]="wrong"
        candidate["integrity"]=checkpoint_integrity_report(candidate["checkpoint"])
        preflight=recovery_preflight(self.current(),candidate)
        self.assertFalse(preflight["allowed"])
        self.assertEqual(preflight["candidate_integrity"],"MISMATCH")

    def test_recovery_blocks_same_effective_checkpoint(self):
        current=self.current()
        candidate={
            "status":"CONFIRMED",
            "revision":"abcdef1234567890abcdef1234567890abcdef12",
            "checkpoint":current["checkpoint"],
            "integrity":checkpoint_integrity_report(current["checkpoint"]),
        }
        preflight=recovery_preflight(current,candidate)
        self.assertFalse(preflight["allowed"])
        self.assertIn("same effective",preflight["reason"])

    def test_restore_requires_explicit_approval_before_write(self):
        with patch("atlasquant_aion_recovery.save_runtime_checkpoint") as save:
            result=restore_checkpoint_revision(
                self.candidate(),
                self.current(),
                self.cfg(),
                approved=False,
            )
        self.assertEqual(result["status"],"BLOCKED")
        save.assert_not_called()

    def test_restore_writes_conditionally_and_records_audit_event(self):
        captured={}
        def fake_save(checkpoint,config,**kwargs):
            captured["checkpoint"]=checkpoint
            captured["expected_sha"]=kwargs.get("expected_sha")
            return {
                "status":"CONFIRMED",
                "saved":True,
                "verified":True,
                "checkpoint":checkpoint,
                "sha":"newsha",
            }

        current=self.current(mismatch=True)
        with patch("atlasquant_aion_recovery.save_runtime_checkpoint",side_effect=fake_save):
            result=restore_checkpoint_revision(
                self.candidate(),
                current,
                self.cfg(),
                approved=True,
            )
        self.assertTrue(result["saved"])
        self.assertTrue(result["verified"])
        self.assertFalse(result["automatic_restore"])
        self.assertEqual(captured["expected_sha"],current["sha"])
        events=captured["checkpoint"]["operating"]["events"]
        self.assertTrue(any(x["event_type"]=="checkpoint_recovery_restored" for x in events))
        self.assertTrue(any(x["severity"]=="WARNING" for x in events))


if __name__=="__main__":
    unittest.main()
