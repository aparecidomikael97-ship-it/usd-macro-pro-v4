import unittest

from atlasquant_flight_recorder_panel import (
    decision_fingerprint, record_from_pack, append_unique, recorder_summary, prepare_flight_capture, hydrate_persistent_records, recorder_visual_state,
)


class AtlasQuantFlightRecorderPanelTests(unittest.TestCase):
    def base(self):
        return {
            "pair":"EUR/USD","side":"BUY","direction":"🟢 COMPRA EUR/USD",
            "state":"🟡 AGUARDAR GATILHO","priority":80,"score":76,"quality":82,
            "gate":"WAIT","m15":"AGUARDAR","h1":"CONFIRMA","h4":"CONFIRMA",
            "event":"NORMAL","reason":"macro favorece EUR","next_action":"Aguardar M15",
            "target":"PDH 1.1000","hard_blocks":[],"soft_blocks":[],"positives":["H1 confirma"],
            "executable":False,"data_ready":{"sufficient":True,"score":90},
        }

    def test_fingerprint_is_stable(self):
        p=self.base()
        self.assertEqual(decision_fingerprint(p,"v1"),decision_fingerprint(dict(p),"v1"))

    def test_state_change_changes_fingerprint(self):
        p=self.base(); q=self.base(); q["m15"]="CONFIRMADO"
        self.assertNotEqual(decision_fingerprint(p,"v1"),decision_fingerprint(q,"v1"))

    def test_non_executable_is_recorded_as_blocked(self):
        r=record_from_pack(self.base(),"v1")
        self.assertEqual(r["record_type"],"BLOCKED")

    def test_executable_ready_is_decision(self):
        p=self.base(); p["executable"]=True; p["state"]="🟢 EXECUTÁVEL"
        r=record_from_pack(p,"v1")
        self.assertEqual(r["record_type"],"DECISION")
        self.assertEqual(r["side"],"BUY")

    def test_insufficient_data_never_becomes_decision(self):
        p=self.base(); p["executable"]=True; p["data_ready"]["sufficient"]=False
        r=record_from_pack(p,"v1")
        self.assertEqual(r["record_type"],"BLOCKED")

    def test_append_unique_prevents_duplicate_state(self):
        r=record_from_pack(self.base(),"v1")
        rows,added=append_unique([],r)
        self.assertTrue(added)
        rows2,added2=append_unique(rows,r)
        self.assertFalse(added2)
        self.assertEqual(len(rows2),1)

    def test_summary_separates_decisions_and_blocks(self):
        a=record_from_pack(self.base(),"v1")
        p=self.base(); p["executable"]=True
        b=record_from_pack(p,"v1")
        s=recorder_summary([a,b])
        self.assertEqual(s["records"],2)
        self.assertEqual(s["decisions"],1)
        self.assertEqual(s["blocked"],1)

    def test_prepare_capture_is_mode_agnostic(self):
        cap=prepare_flight_capture([],self.base(),"v1")
        self.assertTrue(cap["added"])
        self.assertEqual(cap["summary"]["records"],1)

    def test_prepare_capture_deduplicates_existing_state(self):
        first=prepare_flight_capture([],self.base(),"v1")
        second=prepare_flight_capture(first["rows"],self.base(),"v1")
        self.assertFalse(second["added"])
        self.assertEqual(second["summary"]["records"],1)

    def test_hydrate_persistent_records_merges_remote_and_session(self):
        remote=record_from_pack(self.base(),"v1")
        changed=self.base(); changed["m15"]="CONFIRMADO"
        session=record_from_pack(changed,"v1")
        rows=hydrate_persistent_records([session],[remote])
        self.assertEqual(len(rows),2)

    def test_hydrate_persistent_records_deduplicates(self):
        row=record_from_pack(self.base(),"v1")
        rows=hydrate_persistent_records([row],[row])
        self.assertEqual(len(rows),1)

    def test_hydrate_prefers_remote_order_then_session(self):
        remote=record_from_pack(self.base(),"v1")
        changed=self.base(); changed["m15"]="CONFIRMADO"
        session=record_from_pack(changed,"v1")
        rows=hydrate_persistent_records([session],[remote])
        self.assertEqual(rows[0]["_fingerprint"],remote["_fingerprint"])
        self.assertEqual(rows[1]["_fingerprint"],session["_fingerprint"])


    def test_recorder_visual_state_is_audit_only_and_fail_safe(self):
        self.assertEqual(recorder_visual_state({"records":0})["label"],"SEM REGISTROS")
        self.assertEqual(recorder_visual_state({"records":3},{"ok":True})["label"],"REGISTRO PERSISTIDO")
        self.assertEqual(recorder_visual_state({"records":3},{"ok":False,"reason":"SAVE_ERROR"})["label"],"SESSÃO PRESERVADA")
        self.assertEqual(recorder_visual_state({"records":"bad"})["label"],"REVISAR")



if __name__=="__main__":
    unittest.main()
