import unittest
from unittest.mock import patch
import pandas as pd
import paper_trading_v112 as p
import atlasquant_model_paper as mp

class PaperTradingV112SafetyTests(unittest.TestCase):
    def _bars(self,start="2026-09-17T08:00:00Z",n=40,base=1.1000):
        rows=[]
        ts=pd.Timestamp(start)
        price=base
        for i in range(n):
            o=price; cl=o+0.00005
            rows.append({
                "datetime":(ts+pd.Timedelta(minutes=15*i)).isoformat(),
                "open":o,"high":o+0.00030,"low":o-0.00030,"close":cl,
            })
            price=cl
        return rows

    def _state(self,now,bars=None,m15_status="🟢 GATILHO",adr=45.0):
        bars=bars or self._bars()
        last_dt=pd.Timestamp(bars[-1]["datetime"])
        inputs={"pairs":[{
            "Par":"EUR/USD","Direção":"🟢 COMPRA EUR/USD",
            "Score final":90.0,"Qualidade":90.0,"Índice ranking":90.0,
        }]}
        scanner={"resultados":{"EUR/USD":{
            "m15_fetched_at":last_dt.isoformat(),
            "tecnico":{
                "disponivel":True,"dados_disponiveis":True,
                "h4":{"status":"🟢 CONFIRMA"},"h1":{"status":"🟢 PULLBACK OK"},
                "m15":{"status":m15_status},
                "ict":{"readiness":82.0},"institutional":{"readiness":84.0},
                "cache_v110":{"m15":bars},
            },
        }}}
        master={"contexts":{"EUR/USD":{
            "updated_at":now.isoformat(),"readiness_grade":"READY","readiness_score":78.0,
            "adr_used_pct":adr,"event_risk":"NORMAL",
        }}}
        return inputs,scanner,master
    def setUp(self):
        self.now=pd.Timestamp("2026-09-18T12:00:00Z")
        self.input={"Score final":100,"Qualidade":100,"Índice ranking":100,"Direção":"COMPRA"}
        self.tec={"dados_disponiveis":True,"h4":{"status":"OK"},"h1":{"status":"OK"},"m15":{"status":"OK"},"ict":{"readiness":100},"institutional":{"readiness":100}}
        self.map={"updated_at":self.now.isoformat(),"readiness_grade":"READY","readiness_score":100,"adr_used_pct":20,"event_risk":"BAIXO"}

    def test_stale_technical_fails_closed(self):
        scanner={"m15_fetched_at":(self.now-pd.Timedelta(minutes=76)).isoformat(),"tecnico":self.tec}
        with patch("paper_trading_v112.evaluate_decision_integrity",return_value={"executable":True,"hard_blocks":[],"soft_blocks":[]}):
            chk=p.evaluate_pair_checklist("EUR/USD",self.input,scanner,self.map,now=self.now)
        self.assertFalse(chk["data_sufficient"])
        self.assertFalse(chk["all_checks_passed"])

    def test_stale_market_map_fails_closed(self):
        scanner={"m15_fetched_at":self.now.isoformat(),"tecnico":self.tec}
        old={**self.map,"updated_at":(self.now-pd.Timedelta(minutes=76)).isoformat()}
        with patch("paper_trading_v112.evaluate_decision_integrity",return_value={"executable":True,"hard_blocks":[],"soft_blocks":[]}):
            chk=p.evaluate_pair_checklist("EUR/USD",self.input,scanner,old,now=self.now)
        self.assertFalse(chk["data_sufficient"])
        self.assertFalse(chk["all_checks_passed"])

    def test_future_dated_technical_evidence_fails_closed(self):
        scanner={"m15_fetched_at":(self.now+pd.Timedelta(minutes=5)).isoformat(),"tecnico":self.tec}
        with patch("paper_trading_v112.evaluate_decision_integrity",return_value={"executable":True,"hard_blocks":[],"soft_blocks":[]}):
            chk=p.evaluate_pair_checklist("EUR/USD",self.input,scanner,self.map,now=self.now)
        self.assertIsNone(chk["technical_age_min"])
        self.assertFalse(chk["data_sufficient"])
        self.assertFalse(chk["all_checks_passed"])

    def test_future_dated_market_map_fails_closed(self):
        scanner={"m15_fetched_at":self.now.isoformat(),"tecnico":self.tec}
        future={**self.map,"updated_at":(self.now+pd.Timedelta(minutes=5)).isoformat()}
        with patch("paper_trading_v112.evaluate_decision_integrity",return_value={"executable":True,"hard_blocks":[],"soft_blocks":[]}):
            chk=p.evaluate_pair_checklist("EUR/USD",self.input,scanner,future,now=self.now)
        self.assertIsNone(chk["map_age_min"])
        self.assertFalse(chk["data_sufficient"])
        self.assertFalse(chk["all_checks_passed"])

    def test_hard_or_soft_block_prevents_paper_signal(self):
        scanner={"m15_fetched_at":self.now.isoformat(),"tecnico":self.tec}
        for decision in ({"executable":True,"hard_blocks":["X"],"soft_blocks":[]},{"executable":True,"hard_blocks":[],"soft_blocks":["Y"]},{"executable":False,"hard_blocks":[],"soft_blocks":[]}):
            with self.subTest(decision=decision), patch("paper_trading_v112.evaluate_decision_integrity",return_value=decision):
                chk=p.evaluate_pair_checklist("EUR/USD",self.input,scanner,self.map,now=self.now)
                self.assertFalse(chk["all_checks_passed"])

    def test_normalize_m15_deduplicates_and_rejects_bad_geometry(self):
        rows=[
          {"datetime":"2026-09-18T10:00:00Z","open":1.0,"high":1.2,"low":0.9,"close":1.1},
          {"datetime":"2026-09-18T10:00:00Z","open":1.1,"high":1.3,"low":1.0,"close":1.2},
          {"datetime":"2026-09-18T10:15:00Z","open":1.0,"high":0.9,"low":0.8,"close":1.1},
        ]
        d=p.normalize_m15(rows)
        self.assertEqual(len(d),1)
        self.assertAlmostEqual(float(d.iloc[0]["open"]),1.1)

    def test_wait_entry_is_first_bar_after_signal_and_atr_uses_prior_bars(self):
        times=pd.date_range("2026-09-18T08:00:00Z",periods=12,freq="15min")
        frame=pd.DataFrame([{"datetime":t,"open":1.10,"high":1.11,"low":1.09,"close":1.10} for t in times])
        chk={"all_checks_passed":True,"pair":"EUR/USD","side":"BUY","score_master":100,"quality":100,"rank_index":1,"h4":"OK","h1":"OK","m15":"OK","ict_readiness":100,"institutional_readiness":100,"gate":"READY","gate_score":100,"adr_used_pct":20,"event_risk":"BAIXO","technical_age_min":0,"map_age_min":0,"data_sufficient":True}
        row=p._make_wait_entry(chk,frame.iloc[:9],now=self.now)
        out=p._fill_entry(pd.Series(row),frame,now=self.now)
        self.assertEqual(out["status"],"OPEN")
        self.assertEqual(pd.Timestamp(out["entry_time"]),times[9])
        self.assertAlmostEqual(float(out["entry_price"]),1.10)

    def test_setup_attribution_is_only_explicit_and_preserves_point_in_time_context(self):
        scanner={"m15_fetched_at":self.now.isoformat(),"tecnico":self.tec}
        input_row={**self.input,"setup_id":"FVG"}
        market={
            **self.map,
            "d1":{"structure":{"regime":"TENDÊNCIA"}},
            "w1":{"structure":{"regime":"EXPANSÃO"}},
            "killzone":{"active":{"name":"London Killzone"}},
        }
        with patch("paper_trading_v112.evaluate_decision_integrity",return_value={"executable":True,"hard_blocks":[],"soft_blocks":[]}):
            chk=p.evaluate_pair_checklist("EUR/USD",input_row,scanner,market,now=self.now)
        self.assertEqual(chk["setup_id"],"fvg")
        self.assertEqual(chk["setup_attribution"],"EXPLICIT_INPUT")
        self.assertEqual(chk["d1_regime"],"TENDÊNCIA")
        self.assertEqual(chk["w1_regime"],"EXPANSÃO")
        self.assertEqual(chk["active_session"],"London Killzone")
        self.assertEqual(chk["data_quality_pct"],100.0)

        frame=pd.DataFrame(self._bars(start="2026-09-18T08:00:00Z",n=12))
        frame["datetime"]=pd.to_datetime(frame["datetime"],utc=True)
        row=p._make_wait_entry(chk,frame,now=self.now)
        self.assertEqual(row["setup_id"],"fvg")
        self.assertEqual(row["setup_attribution"],"EXPLICIT_INPUT")
        self.assertEqual(row["active_session"],"London Killzone")

    def test_missing_setup_never_gets_inferred_from_ict_state(self):
        scanner={"m15_fetched_at":self.now.isoformat(),"tecnico":{
            **self.tec,
            "ict":{"readiness":100,"fvg":{"status":"FVG ATIVO","score":100}},
        }}
        with patch("paper_trading_v112.evaluate_decision_integrity",return_value={"executable":True,"hard_blocks":[],"soft_blocks":[]}):
            chk=p.evaluate_pair_checklist("EUR/USD",self.input,scanner,self.map,now=self.now)
        self.assertEqual(chk["setup_id"],"")
        self.assertEqual(chk["setup_attribution"],"UNATTRIBUTED")

    def _model_scanner(self,candidates,bars=None):
        bars=bars or self._bars(start="2026-09-20T07:00:00Z",n=20)
        return {"resultados":{"EUR/USD":{
            "m15_fetched_at":bars[-1]["datetime"],
            "tecnico":{
                "dados_disponiveis":True,
                "cache_v110":{"m15":bars},
                "ict":{"setup_candidates":{"candidates":candidates}},
            },
        }}}

    def _model_checklist(self,setup_id,passed=True):
        return {
            "pair":"EUR/USD","side":"BUY","setup_id":setup_id,
            "setup_attribution":"EXPLICIT_INPUT",
            "all_checks_passed":passed,
            "decision":{
                "state":"EXECUTABLE" if passed else "BLOCKED",
                "hard_blocks":[] if passed else ["EVENT_RISK"],
                "soft_blocks":[],
            },
            "score_master":90.0,"quality":90.0,"rank_index":1.0,
            "h4":"OK","h1":"OK","m15":"OK",
            "ict_readiness":90.0,"institutional_readiness":90.0,
            "gate":"READY","gate_score":90.0,"adr_used_pct":30.0,
            "event_risk":"NORMAL" if passed else "ALTO",
            "technical_age_min":0.0,"map_age_min":0.0,
            "data_sufficient":True,"data_quality_pct":95.0,
            "d1_regime":"TREND","w1_regime":"EXPANSION",
            "active_session":"London",
        }

    def test_model_paper_allows_two_setups_on_same_pair_without_cross_labeling(self):
        candidates=[
            {
                "candidate_id":"c-fvg","episode_id":"e-fvg","setup_id":"fvg",
                "source_model":"FVG","source_timeframe":"M15","pair":"EUR/USD",
                "side":"BUY","captured_at":"2026-09-20T12:00:00Z",
                "status":"🟢 FVG EM TESTE","score":90,
                "research_candidate":True,"evidence":{"zone_low":1.1,"zone_high":1.11},
            },
            {
                "candidate_id":"c-ote","episode_id":"e-ote","setup_id":"ote",
                "source_model":"OTE","source_timeframe":"M15","pair":"EUR/USD",
                "side":"BUY","captured_at":"2026-09-20T12:00:00Z",
                "status":"🟢 DENTRO DO OTE","score":88,
                "research_candidate":True,"evidence":{"zone_low":1.09,"zone_high":1.11},
            },
        ]
        scanner=self._model_scanner(candidates)
        inputs={"pairs":[{"Par":"EUR/USD","Direção":"COMPRA","Score final":90,"Qualidade":90,"Índice ranking":1}]}
        master={"contexts":{"EUR/USD":{}}}
        def checklist(pair,row,scanner_pair,map_ctx,now=None):
            return self._model_checklist(row.get("setup_id"),True)
        with patch("atlasquant_model_paper.evaluate_pair_checklist",side_effect=checklist):
            ledger,cycle=mp.run_model_paper_cycle(inputs,scanner,master,now=pd.Timestamp("2026-09-20T12:05:00Z"))
        self.assertEqual(len(ledger),2)
        self.assertEqual(set(ledger["setup_id"].astype(str)),{"fvg","ote"})
        self.assertEqual(set(ledger["setup_attribution"].astype(str)),{"SOURCE_MODEL_EXPLICIT"})
        self.assertEqual(set(ledger["status"].astype(str)),{"WAIT_ENTRY"})
        self.assertEqual(cycle["new_qualified"],2)
        self.assertFalse(cycle["setup_inference_used"])

    def test_model_paper_records_blocked_candidate_instead_of_hiding_it(self):
        candidate={
            "candidate_id":"c-fvg","episode_id":"e-fvg","setup_id":"fvg",
            "source_model":"FVG","source_timeframe":"M15","pair":"EUR/USD",
            "side":"BUY","captured_at":"2026-09-20T12:00:00Z",
            "status":"🟢 FVG EM TESTE","score":90,
            "research_candidate":True,"evidence":{"zone_low":1.1,"zone_high":1.11},
        }
        scanner=self._model_scanner([candidate])
        inputs={"pairs":[{"Par":"EUR/USD","Direção":"COMPRA"}]}
        with patch("atlasquant_model_paper.evaluate_pair_checklist",return_value=self._model_checklist("fvg",False)):
            ledger,cycle=mp.run_model_paper_cycle(inputs,scanner,{"contexts":{"EUR/USD":{}}},now=pd.Timestamp("2026-09-20T12:05:00Z"))
        self.assertEqual(len(ledger),1)
        self.assertEqual(ledger.iloc[0]["status"],"BLOCKED_CONTEXT")
        self.assertIn("EVENT_RISK",str(ledger.iloc[0]["context_hard_blocks"]))
        self.assertEqual(cycle["new_blocked"],1)
        self.assertEqual(cycle["closed_trades"],0)

    def test_model_paper_deduplicates_repeated_scan_by_episode_id(self):
        candidate={
            "candidate_id":"snapshot-1","episode_id":"same-episode","setup_id":"fvg",
            "source_model":"FVG","source_timeframe":"M15","pair":"EUR/USD",
            "side":"BUY","captured_at":"2026-09-20T12:00:00Z",
            "status":"🟢 FVG EM TESTE","score":90,
            "research_candidate":True,"evidence":{"zone_low":1.1,"zone_high":1.11},
        }
        scanner=self._model_scanner([candidate])
        inputs={"pairs":[{"Par":"EUR/USD","Direção":"COMPRA"}]}
        with patch("atlasquant_model_paper.evaluate_pair_checklist",return_value=self._model_checklist("fvg",False)):
            first,_=mp.run_model_paper_cycle(inputs,scanner,{"contexts":{"EUR/USD":{}}},now=pd.Timestamp("2026-09-20T12:05:00Z"))
            repeated=dict(candidate)
            repeated["candidate_id"]="snapshot-2"
            repeated["captured_at"]="2026-09-20T12:30:00Z"
            second,cycle=mp.run_model_paper_cycle(
                inputs,self._model_scanner([repeated]),{"contexts":{"EUR/USD":{}}},
                first,now=pd.Timestamp("2026-09-20T12:35:00Z"),
            )
        self.assertEqual(len(second),1)
        self.assertEqual(cycle["new_candidates_observed"],0)

    def test_same_bar_stop_and_target_is_conservative_loss(self):
        frame=pd.DataFrame([{"datetime":"2026-09-18T10:00:00Z","open":1.0,"high":1.3,"low":0.7,"close":1.0}])
        row=pd.Series({"status":"OPEN","entry_time":"2026-09-18T10:00:00Z","entry_price":1.0,"stop_price":0.9,"target_price":1.2,"risk_distance":0.1,"side":"BUY"})
        out=p._close_open(row,frame.assign(datetime=pd.to_datetime(frame["datetime"],utc=True)),now=self.now)
        self.assertEqual(out["status"],"CLOSED")
        self.assertEqual(out["result"],"LOSS")
        self.assertEqual(out["exit_reason"],"STOP_AND_TARGET_SAME_CANDLE")
        self.assertTrue(out["ambiguous_touch"])


    def test_nonfinite_realized_r_does_not_contaminate_paper_summary(self):
        rows=[
            {"trade_id":"good","pair":"EUR/USD","status":"CLOSED","result":"WIN","realized_r":2.0},
            {"trade_id":"nan","pair":"EUR/USD","status":"CLOSED","result":"WIN","realized_r":float("nan")},
            {"trade_id":"inf","pair":"GBP/USD","status":"CLOSED","result":"WIN","realized_r":float("inf")},
            {"trade_id":"ninf","pair":"GBP/USD","status":"CLOSED","result":"LOSS","realized_r":float("-inf")},
        ]
        summary=p.summarize_paper_trades(pd.DataFrame(rows))
        self.assertEqual(summary["net_r"],2.0)
        self.assertEqual(summary["avg_r"],2.0)
        self.assertEqual(summary["by_pair"]["EUR/USD"]["net_r"],2.0)
        self.assertEqual(summary["by_pair"]["GBP/USD"]["net_r"],0.0)

    def test_summary_by_setup_uses_explicit_tags_only(self):
        rows=[
            {
                "trade_id":"tagged","pair":"EUR/USD","setup_id":"fvg",
                "setup_attribution":"EXPLICIT_INPUT","status":"CLOSED",
                "result":"WIN","realized_r":2.0,
            },
            {
                "trade_id":"untagged","pair":"GBP/USD","setup_id":"",
                "setup_attribution":"UNATTRIBUTED","status":"CLOSED",
                "result":"LOSS","realized_r":-1.0,
            },
        ]
        summary=p.summarize_paper_trades(pd.DataFrame(rows))
        self.assertIn("fvg",summary["by_setup"])
        self.assertEqual(summary["by_setup"]["fvg"]["trades"],1)
        self.assertTrue(summary["by_setup"]["fvg"]["explicit_attribution_only"])
        self.assertFalse(summary["setup_attribution_inferred"])

    def test_untrusted_setup_label_does_not_enter_by_setup_summary(self):
        rows=[{
            "trade_id":"legacy","pair":"EUR/USD","setup_id":"fvg",
            "setup_attribution":"", "status":"CLOSED",
            "result":"WIN","realized_r":2.0,
        }]
        summary=p.summarize_paper_trades(pd.DataFrame(rows))
        self.assertEqual(summary["by_setup"],{})
        self.assertFalse(summary["setup_attribution_inferred"])

    def test_module_has_no_live_broker_execution_contract(self):
        self.assertNotIn("broker", {x.lower() for x in dir(p) if callable(getattr(p,x,None))})
        self.assertEqual(p.ACTIVE_STATUSES,{"WAIT_ENTRY","OPEN"})

    def test_checklist_only_passes_when_everything_is_clear(self):
        now=pd.Timestamp("2026-09-17T18:00:00Z")
        bars=self._bars(start="2026-09-17T08:15:00Z",n=39)
        inputs,scanner,master=self._state(now,bars=bars)
        row=inputs["pairs"][0]
        sp=scanner["resultados"]["EUR/USD"]
        mp=master["contexts"]["EUR/USD"]
        chk=p.evaluate_pair_checklist("EUR/USD",row,sp,mp,now=now)
        self.assertTrue(chk["all_checks_passed"])
        self.assertTrue(chk["decision"]["executable"])
        self.assertEqual(chk["decision"]["hard_blocks"],[])
        self.assertEqual(chk["decision"]["soft_blocks"],[])

    def test_missing_m15_trigger_blocks_paper_entry(self):
        now=pd.Timestamp("2026-09-17T18:00:00Z")
        bars=self._bars(start="2026-09-17T08:15:00Z",n=39)
        inputs,scanner,master=self._state(now,bars=bars,m15_status="🔴 SEM GATILHO")
        trades,cycle=p.run_paper_cycle(inputs,scanner,master,now=now)
        self.assertTrue(trades.empty)
        self.assertEqual(cycle["pending_created"],0)
        self.assertFalse(cycle["checklists"]["EUR/USD"]["passed"])

    def test_signal_waits_next_m15_then_opens_and_closes_at_target(self):
        now1=pd.Timestamp("2026-09-17T18:00:00Z")
        bars1=self._bars(start="2026-09-17T08:15:00Z",n=39)
        inputs,scanner1,master1=self._state(now1,bars=bars1)
        trades1,cycle1=p.run_paper_cycle(inputs,scanner1,master1,now=now1)
        self.assertEqual(len(trades1),1)
        self.assertEqual(trades1.iloc[0]["status"],"WAIT_ENTRY")
        self.assertEqual(cycle1["pending_created"],1)

        signal_time=pd.Timestamp(trades1.iloc[0]["signal_time"])
        last_close=float(bars1[-1]["close"])
        next_bar={
            "datetime":signal_time.isoformat(),"open":last_close,
            "high":last_close+0.00020,"low":last_close-0.00020,"close":last_close+0.00002,
        }
        bars2=bars1+[next_bar]
        now2=signal_time+pd.Timedelta(minutes=20)
        inputs,scanner2,master2=self._state(now2,bars=bars2)
        trades2,cycle2=p.run_paper_cycle(inputs,scanner2,master2,trades1,now=now2)
        self.assertEqual(len(trades2),1)
        self.assertEqual(trades2.iloc[0]["status"],"OPEN")
        self.assertAlmostEqual(float(trades2.iloc[0]["entry_price"]),last_close,places=8)
        self.assertEqual(cycle2["entries_opened"],1)

        target=float(trades2.iloc[0]["target_price"])
        stop=float(trades2.iloc[0]["stop_price"])
        entry=float(trades2.iloc[0]["entry_price"])
        future={
            "datetime":(signal_time+pd.Timedelta(minutes=15)).isoformat(),
            "open":entry,"high":target+0.00001,
            "low":max(stop+0.00001,entry-0.00005),"close":target,
        }
        bars3=bars2+[future]
        now3=signal_time+pd.Timedelta(minutes=40)
        inputs,scanner3,master3=self._state(now3,bars=bars3)
        trades3,cycle3=p.run_paper_cycle(inputs,scanner3,master3,trades2,now=now3)
        self.assertEqual(len(trades3),1)
        self.assertEqual(trades3.iloc[0]["status"],"CLOSED")
        self.assertEqual(trades3.iloc[0]["result"],"WIN")
        self.assertAlmostEqual(float(trades3.iloc[0]["realized_r"]),2.0,places=6)
        self.assertEqual(cycle3["trades_closed"],1)

    def test_high_adr_soft_block_prevents_simulation(self):
        now=pd.Timestamp("2026-09-17T18:00:00Z")
        bars=self._bars(start="2026-09-17T08:15:00Z",n=39)
        inputs,scanner,master=self._state(now,bars=bars,adr=90.0)
        trades,cycle=p.run_paper_cycle(inputs,scanner,master,now=now)
        self.assertTrue(trades.empty)
        self.assertFalse(cycle["checklists"]["EUR/USD"]["passed"])
        self.assertTrue(cycle["checklists"]["EUR/USD"]["soft_blocks"])



if __name__=="__main__":
    unittest.main()
