"""Synthetic fail-closed tests for AION journal continuity, no external calls."""
from __future__ import annotations
import ast
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from atlasquant_aion_event_journal import overlay_journal,continuity_summary
ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,10,9,18,0,tzinfo=timezone.utc)

def reported(state="CONTINUOUS_24H",flag=True):
    return {
      "continuity":{"state":state,"continuous_24h_confirmed":flag,
                    "heartbeat_count":48,"coverage_minutes":1440},
      "digest":"SYNTHETIC_FAKE","owner_approved":True,
      "remote_durability_certified":True,"independent_origin_verified":True,
    }

class JournalSafetyTests(unittest.TestCase):
    def test_forged_history_never_certifies(self):
        r=overlay_journal({},reported())
        self.assertFalse(r["continuous_runtime_confirmed"])
        self.assertTrue(r["background_24h_continuity_candidate"])

    def test_state_labeled_unverified(self):
        r=overlay_journal({},reported())
        self.assertEqual(r["background_watch_state"],"UNVERIFIED_REMOTE_HISTORY")
        self.assertEqual(r["reported_background_watch_state"],"CONTINUOUS_24H")

    def test_forged_owner_and_digest_cannot_bypass(self):
        r=overlay_journal({"continuous_runtime_confirmed":True},reported())
        self.assertFalse(r["continuous_runtime_confirmed"])
        self.assertFalse(r["independent_runtime_history_verified"])

    def test_no_journal_is_not_confirmed(self):
        r=overlay_journal({},None)
        self.assertFalse(r["continuous_runtime_confirmed"])
        self.assertEqual(r["background_watch_state"],"UNKNOWN")

    def test_building_evidence_is_not_confirmed(self):
        r=overlay_journal({},reported("BUILDING_EVIDENCE",False))
        self.assertFalse(r["continuous_runtime_confirmed"])
        self.assertFalse(r["background_24h_continuity_candidate"])

    def test_heartbeat_claim_without_samples_is_not_proof(self):
        r=overlay_journal({},reported())
        self.assertFalse(r["continuous_runtime_confirmed"])

    def test_real_dense_candidate_is_still_not_durable_attestation(self):
        samples=[{"observed_at":(NOW-timedelta(hours=24)+timedelta(minutes=30*i)).isoformat(),
                  "source_state":"FRESH"} for i in range(49)]
        metrics=continuity_summary(samples,now=NOW)
        self.assertTrue(metrics["continuous_24h_confirmed"])
        r=overlay_journal({},{"continuity":metrics,"heartbeats":samples})
        self.assertFalse(r["continuous_runtime_confirmed"])

    def test_autopilot_source_hard_denies_confirmation_in_both_states(self):
        tree=ast.parse((ROOT/"autopilot_v107.py").read_text(encoding="utf-8"))
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="main")
        dictionaries=[]
        for n in ast.walk(main):
            if isinstance(n,ast.Dict):
                fields={k.value:v for k,v in zip(n.keys,n.values)
                        if isinstance(k,ast.Constant) and isinstance(k.value,str)}
                if "continuous_24h_confirmed" in fields:
                    dictionaries.append(fields)
        self.assertEqual(len(dictionaries),2)
        self.assertTrue(all(isinstance(x["continuous_24h_confirmed"],ast.Constant)
                            and x["continuous_24h_confirmed"].value is False
                            for x in dictionaries))

    def test_advisory_candidate_is_preserved(self):
        source=(ROOT/"autopilot_v107.py").read_text("utf-8")
        self.assertIn('"continuity_candidate_24h":bool(',source)
        self.assertIn('"independent_history_verified":False',source)

    def test_overlay_never_enables_external_notifications(self):
        r=overlay_journal({},reported())
        self.assertFalse(r["external_delivery_allowed"])
        self.assertFalse(r["automatic_notification_sent"])

if __name__=="__main__":
    unittest.main()
