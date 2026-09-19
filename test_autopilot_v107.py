import unittest
from unittest.mock import patch
import pandas as pd

import autopilot_v107 as a

class AutopilotV107Tests(unittest.TestCase):
    def test_market_schedule(self):
        sat = pd.Timestamp("2026-09-12T15:00:00Z")
        mon = pd.Timestamp("2026-09-14T15:00:00Z")
        self.assertFalse(a.forex_market_likely_open(sat))
        self.assertTrue(a.forex_market_likely_open(mon))


    def test_minutes_since_future_and_invalid_fail_closed(self):
        now=pd.Timestamp("2026-09-18T12:00:00Z")
        with patch.object(a,"utcnow",return_value=now):
            self.assertIsNone(a.minutes_since("2026-09-18T12:05:00Z"))
            self.assertIsNone(a.minutes_since("not-a-time"))
            self.assertIsNone(a.minutes_since(None))
            self.assertAlmostEqual(a.minutes_since("2026-09-18T11:30:00Z"),30.0)

    def test_status_summary_exact_60_minutes_is_stale(self):
        now=pd.Timestamp("2026-09-18T12:00:00Z")
        ts=(now-pd.Timedelta(minutes=60)).isoformat()
        scanner={"resultados":{p:{"m15_fetched_at":ts} for p in a.PAIR_ORDER}}
        master={"contexts":{p:{"updated_at":ts} for p in a.PAIR_ORDER}}
        with patch.object(a,"utcnow",return_value=now), patch.object(a,"forex_market_likely_open",return_value=True):
            status=a.status_summary(True,"ok",{},scanner,master,{},pd.DataFrame(),[],0,{})
        self.assertEqual(status["scanner_fresh"],0)
        self.assertEqual(status["market_map_fresh"],0)
        self.assertFalse(status["healthy"])

    def test_status_summary_future_evidence_is_not_fresh(self):
        now=pd.Timestamp("2026-09-18T12:00:00Z")
        ts=(now+pd.Timedelta(minutes=5)).isoformat()
        scanner={"resultados":{p:{"m15_fetched_at":ts} for p in a.PAIR_ORDER}}
        master={"contexts":{p:{"updated_at":ts} for p in a.PAIR_ORDER}}
        with patch.object(a,"utcnow",return_value=now), patch.object(a,"forex_market_likely_open",return_value=True):
            status=a.status_summary(True,"ok",{},scanner,master,{},pd.DataFrame(),[],0,{})
        self.assertEqual(status["scanner_fresh"],0)
        self.assertEqual(status["market_map_fresh"],0)
        self.assertFalse(status["healthy"])

    def test_macro_side(self):
        self.assertEqual(a.macro_side("COMPRA USD/CHF"), "BUY")
        self.assertEqual(a.macro_side("VENDA EUR/USD"), "SELL")
        self.assertEqual(a.macro_side("AGUARDAR"), "WAIT")

    def test_directional_return(self):
        self.assertAlmostEqual(a.directional_return("BUY",100,101),1.0)
        self.assertAlmostEqual(a.directional_return("SELL",100,99),1.0)

    def test_exact_horizon_close_uses_candle_close_time(self):
        frame=pd.DataFrame({
            "datetime":pd.to_datetime(["2026-09-14T17:45:00Z","2026-09-14T18:00:00Z"]),
            "open":[1,1],"high":[1,1],"low":[1,1],"close":[1.1,1.2]
        })
        target=pd.Timestamp("2026-09-14T18:00:00Z")
        # 17:45 candle closes exactly at 18:00 and must be used.
        self.assertAlmostEqual(a.exact_horizon_close(frame,target),1.1)

    def test_news_side(self):
        self.assertEqual(a.news_side(2.1),"BUY")
        self.assertEqual(a.news_side(-2.1),"SELL")
        self.assertEqual(a.news_side(1.9),"NEUTRAL")

    def test_validation_schema_has_timing_integrity(self):
        for c in ("signal_frozen_at","m15_candle_time","entry_time","auto_managed"):
            self.assertIn(c,a.VALIDATION_COLS)


    def test_market_closed_does_not_look_open_near_weekend_boundaries(self):
        fri_after_close = pd.Timestamp("2026-09-18T21:01:00Z")
        sun_before_open = pd.Timestamp("2026-09-20T20:59:00Z")
        sun_open = pd.Timestamp("2026-09-20T21:00:00Z")
        self.assertFalse(a.forex_market_likely_open(fri_after_close))
        self.assertFalse(a.forex_market_likely_open(sun_before_open))
        self.assertTrue(a.forex_market_likely_open(sun_open))

    def test_runtime_branch_is_never_a_code_branch(self):
        self.assertNotIn(a.BRANCH, {"main","atlasquant-dev"})

    def test_autopilot_source_keeps_real_execution_out_of_decision_evidence(self):
        from pathlib import Path
        text = Path("autopilot_v107.py").read_text(encoding="utf-8")
        self.assertIn('"real_orders":False', text)
        self.assertIn('"automatic_gate_change":False', text)
        self.assertIn('"automatic_promotion":False', text)

    def test_autopilot_persists_shadow_and_flight_evidence(self):
        from pathlib import Path
        text = Path("autopilot_v107.py").read_text(encoding="utf-8")
        self.assertIn("persist_shadow_samples", text)
        self.assertIn("persist_records", text)
        self.assertIn("build_pair_intelligence_packs", text)

    def test_shadow_failure_does_not_prevent_flight_persistence(self):
        packs=[{"pair":"EUR/USD"}]
        with patch.object(a,"build_shadow_batch",side_effect=RuntimeError("shadow down")), \
             patch.object(a,"persist_records",return_value={"ok":True,"added":1,"records":1,"reason":"SAVED","error":""}) as flight, \
             patch.object(a,"record_from_pack",return_value={"decision_id":"d1"}):
            shadow,flight_status,errors=a.persist_decision_evidence(
                packs,engine_version="test",repo="o/r",branch="atlasquant-runtime",token="t"
            )
        self.assertFalse(shadow["ok"])
        self.assertEqual(shadow["reason"],"SHADOW_EXCEPTION")
        self.assertTrue(flight_status["ok"])
        self.assertEqual(flight.call_count,1)
        self.assertEqual(len(errors),1)

    def test_flight_failure_preserves_successful_shadow_status(self):
        packs=[{"pair":"EUR/USD"}]
        with patch.object(a,"build_shadow_batch",return_value=[{"sample_id":"s1"}]), \
             patch.object(a,"persist_shadow_samples",return_value={"ok":True,"added":1,"samples":1,"reason":"SAVED","error":""}), \
             patch.object(a,"record_from_pack",side_effect=RuntimeError("flight down")):
            shadow,flight_status,errors=a.persist_decision_evidence(
                packs,engine_version="test",repo="o/r",branch="atlasquant-runtime",token="t"
            )
        self.assertTrue(shadow["ok"])
        self.assertFalse(flight_status["ok"])
        self.assertEqual(flight_status["reason"],"FLIGHT_EXCEPTION")
        self.assertEqual(len(errors),1)

    def test_shadow_returned_failure_is_visible_and_flight_still_runs(self):
        packs=[{"pair":"EUR/USD"}]
        with patch.object(a,"build_shadow_batch",return_value=[{"sample_id":"s1"}]), \
             patch.object(a,"persist_shadow_samples",return_value={"ok":False,"added":0,"samples":0,"reason":"CORRUPT_REMOTE","error":""}), \
             patch.object(a,"record_from_pack",return_value={"decision_id":"d1"}), \
             patch.object(a,"persist_records",return_value={"ok":True,"added":1,"records":1,"reason":"SAVED","error":""}) as flight:
            shadow,flight_status,errors=a.persist_decision_evidence(
                packs,engine_version="test",repo="o/r",branch="atlasquant-runtime",token="t"
            )
        self.assertFalse(shadow["ok"])
        self.assertTrue(flight_status["ok"])
        self.assertEqual(flight.call_count,1)
        self.assertTrue(any("CORRUPT_REMOTE" in x for x in errors))

    def test_flight_returned_failure_is_visible_without_erasing_shadow(self):
        packs=[{"pair":"EUR/USD"}]
        with patch.object(a,"build_shadow_batch",return_value=[{"sample_id":"s1"}]), \
             patch.object(a,"persist_shadow_samples",return_value={"ok":True,"added":1,"samples":1,"reason":"SAVED","error":""}), \
             patch.object(a,"record_from_pack",return_value={"decision_id":"d1"}), \
             patch.object(a,"persist_records",return_value={"ok":False,"added":0,"records":0,"reason":"NOT_CONFIGURED","error":""}):
            shadow,flight_status,errors=a.persist_decision_evidence(
                packs,engine_version="test",repo="o/r",branch="atlasquant-runtime",token=""
            )
        self.assertTrue(shadow["ok"])
        self.assertFalse(flight_status["ok"])
        self.assertTrue(any("NOT_CONFIGURED" in x for x in errors))

    def test_empty_evidence_batch_is_safe_and_observable(self):
        with patch.object(a,"build_shadow_batch",return_value=[]), \
             patch.object(a,"persist_shadow_samples",return_value={"ok":True,"added":0,"samples":0,"reason":"ALREADY_PRESENT","error":""}) as shadow, \
             patch.object(a,"persist_records",return_value={"ok":True,"added":0,"records":0,"reason":"ALREADY_PRESENT","error":""}) as flight:
            shadow_status,flight_status,errors=a.persist_decision_evidence(
                [],engine_version="test",repo="o/r",branch="atlasquant-runtime",token="t"
            )
        self.assertTrue(shadow_status["ok"])
        self.assertTrue(flight_status["ok"])
        self.assertEqual(errors,[])
        shadow.assert_called_once()
        flight.assert_called_once_with([],repo="o/r",branch="atlasquant-runtime",token="t")

    def test_main_has_autopilot_serialization_imports(self):
        from pathlib import Path
        text = Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertIn("import base64", text[:2500])
        self.assertIn("import json", text[:2500])


    def test_operational_readiness_requires_both_scanner_and_market_map(self):
        now=pd.Timestamp("2026-09-18T12:00:00Z")
        fresh=(now-pd.Timedelta(minutes=10)).isoformat()
        stale=(now-pd.Timedelta(minutes=61)).isoformat()
        scanner={"resultados":{p:{"m15_fetched_at":fresh} for p in a.PAIR_ORDER}}
        master={"contexts":{p:{"updated_at":stale} for p in a.PAIR_ORDER}}
        with patch.object(a,"utcnow",return_value=now), patch.object(a,"forex_market_likely_open",return_value=True):
            status=a.status_summary(True,"ok",{},scanner,master,{},pd.DataFrame(),[],0,{})
        self.assertTrue(status["scanner_ready"])
        self.assertFalse(status["market_map_ready"])
        self.assertEqual(status["operational_readiness"],"DEGRADED")

    def test_operational_readiness_ready_when_both_layers_are_fresh(self):
        now=pd.Timestamp("2026-09-18T12:00:00Z")
        fresh=(now-pd.Timedelta(minutes=10)).isoformat()
        scanner={"resultados":{p:{"m15_fetched_at":fresh} for p in a.PAIR_ORDER}}
        master={"contexts":{p:{"updated_at":fresh} for p in a.PAIR_ORDER}}
        with patch.object(a,"utcnow",return_value=now), patch.object(a,"forex_market_likely_open",return_value=True):
            status=a.status_summary(True,"ok",{},scanner,master,{},pd.DataFrame(),[],0,{})
        self.assertTrue(status["scanner_ready"])
        self.assertTrue(status["market_map_ready"])
        self.assertEqual(status["operational_readiness"],"READY")


    def test_market_closed_has_explicit_non_ready_state(self):
        now=pd.Timestamp("2026-09-19T12:00:00Z")
        scanner={"resultados":{}}
        master={"contexts":{}}
        with patch.object(a,"utcnow",return_value=now), patch.object(a,"forex_market_likely_open",return_value=False):
            status=a.status_summary(True,"ok",{},scanner,master,{},pd.DataFrame(),[],0,{})
        self.assertFalse(status["forex_market_open"])
        self.assertFalse(status["scanner_ready"])
        self.assertFalse(status["market_map_ready"])
        self.assertEqual(status["operational_readiness"],"MARKET_CLOSED")
        self.assertTrue(status["healthy"])


if __name__=="__main__":
    unittest.main()
