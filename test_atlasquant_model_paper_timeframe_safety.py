import unittest
from unittest.mock import patch

import pandas as pd

import atlasquant_model_paper as model


NOW=pd.Timestamp("2026-09-21T09:00:00Z")


def checklist_ready():
    return {
        "pair":"EUR/USD",
        "side":"BUY",
        "all_checks_passed":True,
        "decision":{"state":"READY","hard_blocks":[],"soft_blocks":[]},
        "score_master":80.0,
        "quality":80.0,
        "rank_index":80.0,
        "h4":"🟢 CONFIRMA","h1":"🟢 PULLBACK OK","m15":"🔴 SEM GATILHO",
        "ict_readiness":80.0,
        "institutional_readiness":80.0,
        "gate":"A",
        "gate_score":80.0,
        "adr_used_pct":40.0,
        "event_risk":"NORMAL",
        "technical_age_min":1.0,
        "map_age_min":1.0,
        "data_sufficient":True,
        "data_quality_pct":100.0,
        "d1_regime":"ALTA",
        "w1_regime":"ALTA",
        "active_session":"London",
    }


def candidate(tf="H1",episode="e1"):
    return {
        "candidate_id":"c1",
        "episode_id":episode,
        "setup_id":"crt",
        "pair":"EUR/USD",
        "side":"BUY",
        "captured_at":"2026-09-21T08:20:00Z",
        "status":"🟢 CRT CONFIRMADO",
        "score":80.0,
        "research_candidate":True,
        "source_model":"CRT",
        "source_timeframe":tf,
        "evidence":{},
    }


def bars(freq="1h",periods=12,start="2026-09-20T21:00:00Z",base=1.10):
    times=pd.date_range(start,periods=periods,freq=freq)
    return [
        {
            "datetime":t.isoformat(),
            "open":base,
            "high":base+0.0010,
            "low":base-0.0010,
            "close":base+0.0001,
        }
        for t in times
    ]


class ModelPaperTimeframeSafetyTests(unittest.TestCase):
    def test_execution_frame_reads_exact_h1_cache_not_m15(self):
        scanner_pair={
            "tecnico":{
                "cache_v110":{
                    "m15":bars("15min",periods=12,start="2026-09-21T05:45:00Z",base=1.20),
                    "h1":bars("1h",periods=12,start="2026-09-20T21:00:00Z",base=1.10),
                }
            }
        }
        h1=model._execution_frame(scanner_pair,"H1")
        m15=model._execution_frame(scanner_pair,"M15")
        self.assertFalse(h1.empty)
        self.assertFalse(m15.empty)
        self.assertAlmostEqual(float(h1.iloc[-1]["open"]),1.10)
        self.assertAlmostEqual(float(m15.iloc[-1]["open"]),1.20)

    def test_h1_candidate_can_become_wait_entry_only_with_exact_h1_frame(self):
        h1=bars("1h",periods=12,start="2026-09-20T21:00:00Z",base=1.10)
        m15=bars("15min",periods=12,start="2026-09-21T05:45:00Z",base=1.20)
        scanner={"resultados":{"EUR/USD":{
            "h1_fetched_at":"2026-09-21T08:00:00Z",
            "m15_fetched_at":"2026-09-21T08:30:00Z",
            "tecnico":{
                "cache_v110":{"h1":h1,"m15":m15},
                "ict":{"setup_candidates":{"candidates":[candidate("H1")]}},
            },
        }}}
        with patch.object(model,"evaluate_pair_checklist",return_value=checklist_ready()) as check:
            ledger,summary=model.run_model_paper_cycle(
                {"pairs":[{"Par":"EUR/USD"}]},
                scanner,
                {"contexts":{"EUR/USD":{}}},
                now=NOW,
            )
        self.assertEqual(len(ledger),1)
        row=ledger.iloc[0]
        self.assertEqual(row["status"],"WAIT_ENTRY")
        self.assertEqual(row["execution_timeframe"],"H1")
        self.assertTrue(bool(row["timeframe_alignment_passed"]))
        self.assertEqual(row["timeframe_alignment_reason"],"SOURCE_EQUALS_EXECUTION")
        self.assertEqual(pd.Timestamp(row["signal_time"]),pd.Timestamp(h1[-1]["datetime"])+pd.Timedelta(hours=1))
        self.assertEqual(summary["pending_entries"],1)
        self.assertEqual(summary["blocked_timeframe"],0)
        self.assertFalse(summary["automatic_execution"])
        self.assertFalse(summary["real_orders_enabled"])
        self.assertEqual(check.call_args.kwargs["execution_timeframe"],"H1")

    def test_h1_candidate_with_missing_h1_frame_fails_closed_instead_of_using_m15(self):
        scanner={"resultados":{"EUR/USD":{
            "h1_fetched_at":"2026-09-21T08:00:00Z",
            "m15_fetched_at":"2026-09-21T08:30:00Z",
            "tecnico":{
                "cache_v110":{"m15":bars("15min",periods=20,base=1.20)},
                "ict":{"setup_candidates":{"candidates":[candidate("H1")]}},
            },
        }}}
        with patch.object(model,"evaluate_pair_checklist",return_value=checklist_ready()):
            ledger,summary=model.run_model_paper_cycle(
                {"pairs":[{"Par":"EUR/USD"}]},
                scanner,
                {"contexts":{"EUR/USD":{}}},
                now=NOW,
            )
        row=ledger.iloc[0]
        self.assertEqual(row["status"],"BLOCKED_DATA")
        self.assertFalse(bool(row["timeframe_alignment_passed"]))
        self.assertEqual(row["timeframe_alignment_reason"],"EXECUTION_FRAME_EMPTY:H1")
        self.assertEqual(summary["pending_entries"],0)
        self.assertEqual(summary["open_positions"],0)

    def test_unsupported_h4_candidate_remains_blocked_timeframe(self):
        with patch.object(model,"current_setup_candidates",return_value=[candidate("H4")]), \
             patch.object(model,"evaluate_pair_checklist",return_value=checklist_ready()):
            ledger,summary=model.run_model_paper_cycle(
                {"pairs":[{"Par":"EUR/USD"}]},
                {"resultados":{}},
                {"contexts":{}},
                now=NOW,
            )
        row=ledger.iloc[0]
        self.assertEqual(row["status"],"BLOCKED_TIMEFRAME")
        self.assertFalse(bool(row["timeframe_alignment_passed"]))
        self.assertEqual(row["timeframe_alignment_reason"],"EXECUTION_FRAME_NOT_AVAILABLE:H4")
        self.assertEqual(summary["blocked_timeframe"],1)

    def test_legacy_h1_wait_entry_uses_exact_h1_frame_not_m15_substitute(self):
        legacy=pd.DataFrame([{
            "trade_id":"e2","signal_id":"e2","episode_id":"e2","candidate_id":"c2",
            "pair":"EUR/USD","side":"BUY","setup_id":"crt",
            "setup_attribution":model.MODEL_ATTRIBUTION,
            "status":"WAIT_ENTRY","source_model":"CRT","source_timeframe":"H1",
            "signal_time":"2026-09-21T08:00:00Z","created_at":"2026-09-21T07:00:00Z",
            "updated_at":"2026-09-21T07:00:00Z",
        }])
        exact=bars("1h",periods=12,start="2026-09-20T23:00:00Z",base=1.10)
        with patch.object(model,"current_setup_candidates",return_value=[]), \
             patch.object(model,"_execution_frame",return_value=pd.DataFrame(exact).assign(
                 datetime=lambda d:pd.to_datetime(d["datetime"],utc=True)
             )) as frame:
            ledger,_=model.run_model_paper_cycle(
                {"pairs":[]},{"resultados":{"EUR/USD":{}}},{"contexts":{}},legacy,now=NOW
            )
        frame.assert_called_with({},"H1")
        self.assertEqual(ledger.iloc[0]["execution_timeframe"],"H1")
        self.assertNotEqual(ledger.iloc[0]["status"],"BLOCKED_TIMEFRAME")

    def test_summary_keeps_m15_and_h1_statistics_separate(self):
        ledger=pd.DataFrame([
            {"trade_id":"m1","source_timeframe":"M15","setup_id":"fvg","status":"CLOSED","result":"WIN","realized_r":2.0},
            {"trade_id":"h1","source_timeframe":"H1","setup_id":"crt","status":"BLOCKED_CONTEXT","result":"","realized_r":None},
            {"trade_id":"h2","source_timeframe":"H1","setup_id":"ote","status":"WAIT_ENTRY","result":"","realized_r":None},
        ])
        summary=model.summarize_model_paper(ledger)
        self.assertEqual(summary["by_timeframe"]["M15"]["closed"],1)
        self.assertEqual(summary["by_timeframe"]["M15"]["wins"],1)
        self.assertEqual(summary["by_timeframe"]["M15"]["net_r"],2.0)
        self.assertEqual(summary["by_timeframe"]["H1"]["blocked_context"],1)
        self.assertEqual(summary["by_timeframe"]["H1"]["pending"],1)


    def test_summary_explains_block_reasons_by_timeframe_and_setup(self):
        ledger=pd.DataFrame([
            {
                "trade_id":"h1","source_timeframe":"H1","setup_id":"crt",
                "status":"BLOCKED_CONTEXT","result":"","realized_r":None,
                "context_hard_blocks":"Contexto D1 ausente para execução H1 | Gate bloqueado",
                "context_soft_blocks":"ICT incompleto (40/100)",
                "timeframe_alignment_reason":"SOURCE_EQUALS_EXECUTION",
            },
            {
                "trade_id":"h2","source_timeframe":"H1","setup_id":"crt",
                "status":"BLOCKED_TIMEFRAME","result":"","realized_r":None,
                "context_hard_blocks":"",
                "context_soft_blocks":"",
                "timeframe_alignment_reason":"EXECUTION_FRAME_NOT_AVAILABLE:H4",
            },
        ])
        summary=model.summarize_model_paper(ledger)
        self.assertEqual(
            summary["by_timeframe"]["H1"]["hard_block_reasons"]["Contexto D1 ausente para execução H1"],1
        )
        self.assertEqual(summary["by_setup"]["crt"]["soft_block_reasons"]["ICT incompleto (40/100)"],1)
        self.assertEqual(
            summary["by_timeframe"]["H1"]["timeframe_block_reasons"]["EXECUTION_FRAME_NOT_AVAILABLE:H4"],1
        )
        self.assertFalse(summary["automatic_execution"])
        self.assertFalse(summary["real_orders_enabled"])



if __name__=="__main__":
    unittest.main()
