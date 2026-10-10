"""Synthetic, offline Autopilot evidence guard checks; no remote API."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import unittest
from atlasquant_aion_v2_autopilot_evidence_guard import guarded_autopilot_evidence_write

def guarded(sink="shadow", result=None, write=None, group=None):
    group = group or uuid4().hex
    return guarded_autopilot_evidence_write(
        repo="synthetic/repo-" + group, branch="atlasquant-runtime",
        sink=sink, write=write if write is not None else lambda: result,
    )

class TestAutopilotUnknownQuarantine(unittest.TestCase):
    def test_unknown_sticky_no_second_writer(self):
        group=uuid4().hex
        calls=[]
        def writer():
            calls.append(1)
            return {"ok":False,"reason":"UNKNOWN_OUTCOME","reconciliation_required":True,
                    "safe_to_retry":False,"write_outcome":"UNKNOWN"}
        first=guarded(write=writer,group=group)
        second=guarded(write=writer,group=group)
        self.assertFalse(first["ok"])
        self.assertEqual(first["reason"],"PENDING_RECONCILIATION")
        self.assertEqual(second["reason"],"PENDING_RECONCILIATION")
        self.assertFalse(second["safe_to_retry"])
        self.assertEqual(len(calls),1)

    def test_later_already_present_cannot_erase_unknown(self):
        group=uuid4().hex
        calls=[]
        def writer():
            calls.append(len(calls))
            return ({"ok":False,"reason":"UNKNOWN_OUTCOME","reconciliation_required":True}
                    if len(calls)==1 else {"ok":True,"reason":"ALREADY_PRESENT"})
        guarded(group=group,write=writer)
        replay=guarded(group=group,write=writer)
        self.assertEqual(replay["reason"],"PENDING_RECONCILIATION")
        self.assertEqual(len(calls),1)

    def test_already_present_not_remote_success(self):
        result=guarded(result={"ok":True,"reason":"ALREADY_PRESENT","added":0})
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"],"REMOTE_ALREADY_PRESENT_UNVERIFIED")
        self.assertTrue(result["reconciliation_required"])

    def test_201_without_readback_rejected(self):
        result=guarded(result={"ok":True,"reason":"SAVED","added":3})
        self.assertEqual(result["reason"],"UNVERIFIED_SUCCESS")
        self.assertFalse(result["ok"])

    def test_verified_readback_not_independent_durability(self):
        result=guarded(result={"ok":True,"reason":"SAVED","verified":True,
                               "verification":"SAME_GITHUB_CONTENTS_ENDPOINT_READ_AFTER_WRITE",
                               "remote_durability_certified":False})
        self.assertTrue(result["ok"])
        self.assertFalse(result["remote_durability_certified"])

    def test_conflict_sticky(self):
        result=guarded(result={"ok":False,"reason":"CONFLICT","reconciliation_required":True})
        self.assertEqual(result["reason"],"PENDING_RECONCILIATION")
        self.assertFalse(result["safe_to_retry"])

    def test_exception_no_secret_leak(self):
        def fail():
            raise ValueError("Bearer SECRET_SYNTHETIC_NON_REAL")
        result=guarded(write=fail)
        self.assertEqual(result["error"],"ValueError")
        self.assertNotIn("SECRET",str(result))

    def test_invalid_sink_no_writer(self):
        calls=[]
        result=guarded(sink="unknown",write=lambda: calls.append(1))
        self.assertEqual(result["reason"],"INVALID_SINK_IDENTITY")
        self.assertEqual(calls,[])

    def test_separate_sink_does_not_mask_other(self):
        group=uuid4().hex
        guarded(sink="shadow",group=group,result={"ok":False,"reason":"UNKNOWN_OUTCOME"})
        other=guarded(sink="flight",group=group,result={"ok":True,"reason":"SAVED","verified":True})
        self.assertTrue(other["ok"])

    def test_parallel_no_replay(self):
        group=uuid4().hex
        calls=[]
        def writer():
            calls.append(1)
            return {"ok":False,"reason":"UNKNOWN_OUTCOME","reconciliation_required":True}
        with ThreadPoolExecutor(max_workers=12) as pool:
            responses=list(pool.map(lambda _:guarded(group=group,write=writer),range(30)))
        self.assertEqual(len(calls),1)
        self.assertTrue(all(r["reason"]=="PENDING_RECONCILIATION" for r in responses))

    def test_malformed_quarantined(self):
        result=guarded(result=None)
        self.assertEqual(result["error"],"MALFORMED_WRITER_RESULT")

    def test_no_release_api(self):
        import atlasquant_aion_v2_autopilot_evidence_guard as g
        self.assertEqual(g.__all__,["guarded_autopilot_evidence_write"])
        self.assertFalse(hasattr(g,"clear_quarantine"))

if __name__=="__main__":
    unittest.main()
