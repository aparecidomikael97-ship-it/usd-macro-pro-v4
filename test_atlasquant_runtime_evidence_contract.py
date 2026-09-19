from pathlib import Path
import unittest

from atlasquant_shadow_capture import build_shadow_batch, hydrate_shadow_samples
from atlasquant_flight_recorder_panel import (
    append_unique,
    decision_fingerprint,
    hydrate_persistent_records,
    prepare_flight_capture,
    recorder_summary,
)
from atlasquant_runtime_store import require_runtime_branch, resolve_runtime_branch


PAIRS=("EUR/USD","GBP/USD","AUD/USD","NZD/USD","USD/JPY","USD/CAD","USD/CHF")


def pack(pair,side="BUY",state="OBS",executable=False):
    return {
        "pair":pair,"side":side,"state":state,"executable":executable,
        "priority":50,"score":80,"quality":90,
        "data_ready":{"score":100,"sufficient":True},
        "gate":"WAIT","m15":"NO_TRIGGER","h1":"OK","h4":"OK",
        "event":"NORMAL","hard_blocks":[],"soft_blocks":[],
        "direction":side,"reason":"contract","next_action":"wait","target":"—",
        "timestamp":"2026-09-19T09:00:00Z",
    }


class RuntimeEvidenceContractTests(unittest.TestCase):
    def test_runtime_branch_policy_redirects_code_branches(self):
        self.assertEqual(resolve_runtime_branch("main",""),"atlasquant-runtime")
        self.assertEqual(resolve_runtime_branch("atlasquant-dev",""),"atlasquant-runtime")
        self.assertEqual(require_runtime_branch("atlasquant-runtime"),"atlasquant-runtime")
        with self.assertRaises(ValueError):
            require_runtime_branch("main")

    def test_flight_fingerprint_is_stable_for_identical_state(self):
        p=pack("EUR/USD")
        self.assertEqual(decision_fingerprint(p,"V"),decision_fingerprint(dict(p),"V"))

    def test_flight_fingerprint_changes_when_decision_changes(self):
        a=pack("EUR/USD",side="BUY")
        b=pack("EUR/USD",side="SELL")
        self.assertNotEqual(decision_fingerprint(a,"V"),decision_fingerprint(b,"V"))

    def test_flight_capture_deduplicates_same_state(self):
        first=prepare_flight_capture([],pack("EUR/USD"),"V")
        second=prepare_flight_capture(first["rows"],pack("EUR/USD"),"V")
        self.assertTrue(first["added"])
        self.assertFalse(second["added"])
        self.assertEqual(len(second["rows"]),1)

    def test_flight_hydration_deduplicates_remote_and_session(self):
        rec=prepare_flight_capture([],pack("EUR/USD"),"V")["current"]
        rows=hydrate_persistent_records([rec],[rec])
        self.assertEqual(len(rows),1)

    def test_flight_summary_counts_decision_and_blocked(self):
        blocked=prepare_flight_capture([],pack("EUR/USD"),"V")["current"]
        decision=prepare_flight_capture([],pack("GBP/USD",executable=True),"V")["current"]
        s=recorder_summary([blocked,decision])
        self.assertEqual(s,{"records":2,"decisions":1,"blocked":1})

    def test_shadow_builds_exactly_one_sample_per_major_pair(self):
        rows=build_shadow_batch([pack(p) for p in PAIRS],champion_version="V")
        self.assertEqual(len(rows),7)
        self.assertEqual({x["champion"]["pair"] for x in rows},set(PAIRS))
        self.assertEqual({x["challenger"]["pair"] for x in rows},set(PAIRS))

    def test_shadow_hydration_deduplicates_same_sample(self):
        row=build_shadow_batch([pack("EUR/USD")],champion_version="V")[0]
        rows=hydrate_shadow_samples([row],[row])
        self.assertEqual(len(rows),1)

    def test_all_seven_pairs_generate_unique_flight_fingerprints(self):
        rows=[prepare_flight_capture([],pack(p),"V")["current"] for p in PAIRS]
        fps=[x["_fingerprint"] for x in rows]
        self.assertEqual(len(fps),7)
        self.assertEqual(len(set(fps)),7)
        self.assertEqual({x["asset"] for x in rows},set(PAIRS))

    def test_all_seven_pairs_remain_blocked_when_not_executable(self):
        rows=[prepare_flight_capture([],pack(p,executable=False),"V")["current"] for p in PAIRS]
        self.assertTrue(all(x["record_type"]=="BLOCKED" for x in rows))
        self.assertTrue(all(x["outcome"]=="BLOCKED" for x in rows))

    def test_shadow_pair_identity_and_direction_match(self):
        rows=build_shadow_batch([pack(p) for p in PAIRS],champion_version="V")
        self.assertTrue(all(x["pair_match"] for x in rows))
        self.assertTrue(all(x["side_match"] for x in rows))
        self.assertTrue(all(not x["opposite_direction"] for x in rows))
        self.assertTrue(all(not x["critical_mismatch"] for x in rows))

    def test_shadow_never_turns_challenger_into_live_execution(self):
        rows=build_shadow_batch([pack(p,executable=False) for p in PAIRS],champion_version="V")
        self.assertTrue(all(not x["challenger"]["executable"] for x in rows))

    def test_executable_champion_cannot_make_strict_challenger_execute_without_all_gates(self):
        p=pack("EUR/USD",executable=True)
        p["score"]=90
        p["quality"]=95
        p["data_ready"]={"score":95,"sufficient":True}
        p["macro_diff"]=10
        p["h4"]="ALINHADO"
        p["h1"]="ALINHADO"
        p["m15"]="NO_TRIGGER"
        row=build_shadow_batch([p],champion_version="V")[0]
        self.assertTrue(row["champion"]["executable"])
        self.assertFalse(row["challenger"]["executable"])
        self.assertFalse(row["execution_match"])
        self.assertTrue(row["critical_mismatch"])

    def test_strict_challenger_can_only_observe_when_every_gate_passes(self):
        p=pack("EUR/USD",executable=True)
        p.update({"score":90,"quality":95,"macro_diff":10,"h4":"ALINHADO","h1":"ALINHADO","m15":"GATILHO"})
        p["data_ready"]={"score":95,"sufficient":True}
        row=build_shadow_batch([p],champion_version="V")[0]
        self.assertTrue(row["challenger"]["executable"])
        self.assertTrue(row["execution_match"])
        self.assertFalse(row["critical_mismatch"])

    def test_repeated_seven_pair_batch_is_idempotent_in_memory(self):
        records=[]
        for p in PAIRS:
            current=prepare_flight_capture([],pack(p),"V")["current"]
            records,added=append_unique(records,current)
            self.assertTrue(added)
        for p in PAIRS:
            current=prepare_flight_capture([],pack(p),"V")["current"]
            records,added=append_unique(records,current)
            self.assertFalse(added)
        self.assertEqual(len(records),7)

        samples=build_shadow_batch([pack(p) for p in PAIRS],champion_version="V")
        hydrated=hydrate_shadow_samples(samples,samples)
        self.assertEqual(len(hydrated),7)

    def test_append_unique_rejects_duplicate_fingerprint(self):
        rec=prepare_flight_capture([],pack("USD/JPY"),"V")["current"]
        rows,added=append_unique([rec],rec)
        self.assertFalse(added)
        self.assertEqual(len(rows),1)


    def test_validation_ui_surfaces_runtime_provenance_without_live_claim(self):
        source=Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertIn("Proveniência da validação: dados persistidos de runtime",source)
        self.assertIn("_aq_runtime_source",source)
        self.assertIn("_aq_quota_source",source)
        self.assertIn("runtime persistido indisponível; revisão permanece conservadora",source)
        self.assertNotIn("Proveniência da validação: dados ao vivo",source)


if __name__=="__main__":
    unittest.main()
