import unittest
from unittest.mock import patch, Mock
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

    def test_autopilot_freezes_model_specific_setup_candidates_without_execution(self):
        from pathlib import Path
        text = Path("autopilot_v107.py").read_text(encoding="utf-8")
        self.assertIn("build_setup_candidates",text)
        self.assertIn('setup_candidates',text)
        candidate_source=Path("atlasquant_setup_candidates.py").read_text(encoding="utf-8")
        self.assertIn('"automatic_paper_entry":False',candidate_source)
        self.assertIn('"real_orders_enabled":False',candidate_source)
        self.assertIn('"setup_inference_from_outcome":False',candidate_source)

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


    def test_github_write_retries_transient_409_with_fresh_sha(self):
        get1=Mock(status_code=200); get1.json.return_value={"sha":"oldsha"}
        get2=Mock(status_code=200); get2.json.return_value={"sha":"newsha"}
        put1=Mock(status_code=409)
        put2=Mock(status_code=200)
        put2.raise_for_status.return_value=None
        with patch.object(a,"TOKEN","token"), patch.object(a,"REPO","owner/repo"), patch.object(a,"BRANCH","atlasquant-runtime"), \
             patch.object(a.requests,"get",side_effect=[get1,get2]) as get_call, \
             patch.object(a.requests,"put",side_effect=[put1,put2]) as put_call, \
             patch.object(a.time,"sleep") as sleep_call:
            ok,err=a.gh_put_bytes("dados/teste.json",b"{}","teste")
        self.assertTrue(ok)
        self.assertEqual(err,"")
        self.assertEqual(get_call.call_count,2)
        self.assertEqual(put_call.call_count,2)
        self.assertEqual(put_call.call_args_list[0].kwargs["json"]["sha"],"oldsha")
        self.assertEqual(put_call.call_args_list[1].kwargs["json"]["sha"],"newsha")
        sleep_call.assert_called_once()

    def test_github_write_does_not_retry_non_conflict_failure(self):
        get1=Mock(status_code=200); get1.json.return_value={"sha":"sha"}
        put1=Mock(status_code=500)
        put1.raise_for_status.side_effect=RuntimeError("server down")
        with patch.object(a,"TOKEN","token"), patch.object(a,"REPO","owner/repo"), patch.object(a,"BRANCH","atlasquant-runtime"), \
             patch.object(a.requests,"get",return_value=get1), patch.object(a.requests,"put",return_value=put1) as put_call, \
             patch.object(a.time,"sleep") as sleep_call:
            ok,err=a.gh_put_bytes("dados/teste.json",b"{}","teste")
        self.assertFalse(ok)
        self.assertIn("server down",err)
        self.assertEqual(put_call.call_count,1)
        sleep_call.assert_not_called()


    def test_home_snapshot_payload_is_compact_and_fail_closed(self):
        now=pd.Timestamp("2026-09-18T12:00:00Z")
        inputs={
            "generated_at":"2026-09-18T11:59:00Z",
            "fast_boot":{"ranking":[{"Código":"USD"}]},
        }
        packs=[{"pair":"EUR/USD","direction":"VENDA"}]
        scanner={"resultados":{"EUR/USD":{}}}
        master={"contexts":{"EUR/USD":{}}}
        out=a.build_home_snapshot_payload(inputs,packs,scanner,master,{"stories":[1]},now=now)
        self.assertEqual(out["schema"],"ATLASQUANT_HOME_SNAPSHOT_V1")
        self.assertEqual(out["generated_at"],inputs["generated_at"])
        self.assertEqual(len(out["packs"]),1)
        self.assertEqual(out["runtime"]["scanner_pairs"],1)
        self.assertEqual(out["runtime"]["market_map_pairs"],1)
        self.assertTrue(out["runtime"]["news_available"])
        self.assertFalse(out["safety"]["real_orders"])
        self.assertFalse(out["safety"]["automatic_execution"])
        self.assertFalse(out["safety"]["automatic_gate_change"])
        self.assertFalse(out["safety"]["automatic_weight_change"])
        self.assertFalse(out["safety"]["automatic_promotion"])

    def test_home_snapshot_drops_non_mapping_pack_rows(self):
        now=pd.Timestamp("2026-09-18T12:00:00Z")
        out=a.build_home_snapshot_payload({},[{"pair":"EUR/USD"},None,"bad"],{}, {}, {},now=now)
        self.assertEqual(out["packs"],[{"pair":"EUR/USD"}])
        self.assertFalse(out["safety"]["real_orders"])


    def test_home_snapshot_can_carry_signal_lifecycle_without_enabling_orders(self):
        now=pd.Timestamp("2026-09-18T12:00:00Z")
        lifecycle={"schema":"ATLASQUANT_SIGNAL_LIFECYCLE_V1","pairs":{"EUR/USD":{"status_code":"CONFIRMED"}}}
        out=a.build_home_snapshot_payload(
            {},[{"pair":"EUR/USD"}],{}, {}, {},
            signal_lifecycle=lifecycle,now=now,
        )
        self.assertEqual(out["signal_lifecycle"],lifecycle)
        self.assertFalse(out["safety"]["real_orders"])
        self.assertFalse(out["safety"]["automatic_execution"])

    def test_autopilot_persists_signal_lifecycle_before_home_snapshot(self):
        from pathlib import Path
        src=Path("autopilot_v107.py").read_text(encoding="utf-8")
        lifecycle=src.index("advance_signal_lifecycle(")
        persist=src.index("gh_put_json(\n                SIGNAL_LIFECYCLE_PATH",lifecycle)
        annotate=src.index("annotate_packs_with_lifecycle(",persist)
        home=src.index("build_home_snapshot_payload(",annotate)
        self.assertLess(lifecycle,persist)
        self.assertLess(persist,annotate)
        self.assertLess(annotate,home)
        self.assertIn('"real_orders":False',src[lifecycle:home])

    def test_home_snapshot_path_is_dedicated_runtime_artifact(self):
        self.assertEqual(a.HOME_SNAPSHOT_PATH,"dados/atlasquant_home_snapshot_v1.json")

    def test_research_timeframe_cache_reuses_collected_data_only(self):
        from pathlib import Path
        src=Path("atlasquant_research_timeframes.py").read_text(encoding="utf-8")
        auto=Path("autopilot_v107.py").read_text(encoding="utf-8")
        self.assertNotIn("td_fetch(",src)
        self.assertNotIn("requests.",src)
        self.assertIn('RESEARCH_TF_CACHE_PATH = "dados/atlasquant_research_timeframes_v1.json"',auto)
        self.assertIn("build_research_timeframe_cache(",auto)
        self.assertIn('"provider_calls_added":False',auto)
        self.assertIn('"real_orders":False',auto)
        self.assertIn('"automatic_execution":False',auto)



if __name__=="__main__":
    unittest.main()
