import unittest
from unittest.mock import patch
import pandas as pd
import paper_trading_v112 as p

class PaperTradingV112SafetyTests(unittest.TestCase):
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

    def test_same_bar_stop_and_target_is_conservative_loss(self):
        frame=pd.DataFrame([{"datetime":"2026-09-18T10:00:00Z","open":1.0,"high":1.3,"low":0.7,"close":1.0}])
        row=pd.Series({"status":"OPEN","entry_time":"2026-09-18T10:00:00Z","entry_price":1.0,"stop_price":0.9,"target_price":1.2,"risk_distance":0.1,"side":"BUY"})
        out=p._close_open(row,frame.assign(datetime=pd.to_datetime(frame["datetime"],utc=True)),now=self.now)
        self.assertEqual(out["status"],"CLOSED")
        self.assertEqual(out["result"],"LOSS")
        self.assertEqual(out["exit_reason"],"STOP_AND_TARGET_SAME_CANDLE")
        self.assertTrue(out["ambiguous_touch"])

    def test_module_has_no_live_broker_execution_contract(self):
        self.assertNotIn("broker", {x.lower() for x in dir(p) if callable(getattr(p,x,None))})
        self.assertEqual(p.ACTIVE_STATUSES,{"WAIT_ENTRY","OPEN"})

if __name__=="__main__":
    unittest.main()
