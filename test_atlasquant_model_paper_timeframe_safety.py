import unittest
from unittest.mock import patch

import pandas as pd

import atlasquant_model_paper as model


NOW=pd.Timestamp("2026-09-21T09:00:00Z")


def checklist_ready():
    return {
        "all_checks_passed":True,
        "decision":{"state":"READY","hard_blocks":[],"soft_blocks":[]},
        "score_master":80.0,
        "quality":80.0,
        "rank_index":80.0,
        "h4":"ALTA","h1":"ALTA","m15":"ALTA",
        "ict_readiness":80.0,
        "institutional_readiness":80.0,
        "gate":"A",
        "gate_score":80.0,
        "adr_used_pct":40.0,
        "event_risk":"BAIXO",
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
        "captured_at":"2026-09-21T08:00:00Z",
        "status":"🟢 CRT CONFIRMADO",
        "score":80.0,
        "research_candidate":True,
        "source_model":"CRT",
        "source_timeframe":tf,
        "evidence":{},
    }


class ModelPaperTimeframeSafetyTests(unittest.TestCase):
    def test_h1_candidate_never_executes_on_m15_frame(self):
        with patch.object(model,"current_setup_candidates",return_value=[candidate("H1")]),              patch.object(model,"evaluate_pair_checklist",return_value=checklist_ready()),              patch.object(model,"_m15",return_value=pd.DataFrame()):
            ledger,summary=model.run_model_paper_cycle(
                {"pairs":[{"Par":"EUR/USD"}]},
                {"resultados":{}},
                {"contexts":{}},
                now=NOW,
            )
        self.assertEqual(len(ledger),1)
        row=ledger.iloc[0]
        self.assertEqual(row["status"],"BLOCKED_TIMEFRAME")
        self.assertFalse(bool(row["timeframe_alignment_passed"]))
        self.assertEqual(row["timeframe_alignment_reason"],"EXECUTION_FRAME_NOT_AVAILABLE:H1")
        self.assertEqual(summary["blocked_timeframe"],1)
        self.assertEqual(summary["pending_entries"],0)
        self.assertEqual(summary["open_positions"],0)
        self.assertFalse(summary["automatic_execution"])
        self.assertFalse(summary["real_orders_enabled"])

    def test_legacy_h1_wait_entry_is_quarantined_before_m15_fill(self):
        legacy=pd.DataFrame([{
            "trade_id":"e2","signal_id":"e2","episode_id":"e2","candidate_id":"c2",
            "pair":"EUR/USD","side":"BUY","setup_id":"crt",
            "setup_attribution":model.MODEL_ATTRIBUTION,
            "status":"WAIT_ENTRY","source_model":"CRT","source_timeframe":"H1",
            "signal_time":"2026-09-21T08:00:00Z","created_at":"2026-09-21T08:00:00Z",
            "updated_at":"2026-09-21T08:00:00Z",
        }])
        with patch.object(model,"current_setup_candidates",return_value=[]),              patch.object(model,"_m15") as m15:
            ledger,summary=model.run_model_paper_cycle(
                {"pairs":[]},{"resultados":{}},{"contexts":{}},legacy,now=NOW
            )
        self.assertEqual(ledger.iloc[0]["status"],"BLOCKED_TIMEFRAME")
        self.assertFalse(bool(ledger.iloc[0]["timeframe_alignment_passed"]))
        self.assertEqual(summary["pending_entries"],0)
        m15.assert_not_called()


if __name__=="__main__":
    unittest.main()
