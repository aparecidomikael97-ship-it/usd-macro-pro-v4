import unittest
import pandas as pd
from ict_execution_v108 import detect_crt, detect_amd, detect_fvg
from atlasquant_setup_candidates import build_setup_candidates, candidate_rows

class ICTExecutionV108Tests(unittest.TestCase):
    def _df(self, rows, freq="h"):
        d=pd.DataFrame(rows,columns=["open","high","low","close"])
        d["datetime"]=pd.date_range("2026-09-14",periods=len(d),freq=freq,tz="UTC")
        return d[["datetime","open","high","low","close"]]

    def test_bullish_crt(self):
        d=self._df([(1.00,1.10,.90,1.02),(1.02,1.05,.88,.96),(.96,1.08,.95,1.06)])
        x=detect_crt(d,"BUY")
        self.assertIn("CONFIRMADO",x["status"])
        self.assertEqual(x["raid_side"],"SSL")

    def test_amd_detects_manipulation_or_distribution(self):
        rows=[(1.00,1.02,.98,1.00)]*8
        rows += [(1.00,1.01,.96,.99),(0.99,1.02,.98,1.01),(1.01,1.04,1.00,1.03),(1.03,1.06,1.02,1.05)]
        x=detect_amd(self._df(rows,"15min"),"BUY")
        self.assertGreaterEqual(x["score"],70)

    def test_fvg(self):
        d=self._df([(1,1.01,.99,1),(1,1.02,.995,1.015),(1.03,1.04,1.025,1.035)],"15min")
        x=detect_fvg(d,"BUY")
        self.assertGreaterEqual(x["score"],65)


    def test_model_specific_candidates_are_explicit_and_do_not_create_trades(self):
        pack=build_setup_candidates(
            pair="EUR/USD",
            side="BUY",
            captured_at="2026-09-20T12:00:00Z",
            ict_snapshot={
                "crt":{"status":"🟢 CRT CONFIRMADO","score":100,"phase":"DISTRIBUIÇÃO"},
                "ote":{"status":"🟢 DENTRO DO OTE","score":90,"retracement_pct":70.5},
                "amd":{"status":"🟢 AMD / PO3 EM DISTRIBUIÇÃO","score":100,"phase":"DISTRIBUIÇÃO"},
                "fvg":{"status":"🟢 FVG EM TESTE","score":90,"zone_low":1.1,"zone_high":1.2},
            },
        )
        self.assertEqual(pack["candidate_count"],4)
        self.assertEqual(
            {x["setup_id"] for x in pack["candidates"]},
            {"crt","ote","amd-po3","fvg"},
        )
        self.assertFalse(pack["setup_inference_from_outcome"])
        self.assertFalse(pack["automatic_paper_entry"])
        self.assertFalse(pack["automatic_execution"])
        for row in pack["candidates"]:
            self.assertEqual(row["setup_attribution"],"SOURCE_MODEL_EXPLICIT")
            self.assertFalse(row["paper_trade_created"])
            self.assertFalse(row["real_orders_enabled"])

    def test_yellow_or_waiting_model_states_are_not_research_candidates(self):
        pack=build_setup_candidates(
            pair="EUR/USD",
            side="BUY",
            captured_at="2026-09-20T12:00:00Z",
            ict_snapshot={
                "crt":{"status":"🟡 MANIPULAÇÃO DETECTADA","score":70,"phase":"MANIPULAÇÃO"},
                "ote":{"status":"🟡 PRÓXIMO DO OTE","score":65},
                "amd":{"status":"🟡 AMD EM MANIPULAÇÃO","score":70,"phase":"MANIPULAÇÃO"},
                "fvg":{"status":"🟡 FVG PRESENTE","score":65},
            },
        )
        self.assertEqual(pack["candidate_count"],0)
        self.assertEqual(candidate_rows(pack),[])
        self.assertEqual(len(pack["models"]),4)

    def test_episode_id_stays_stable_when_only_capture_time_or_price_changes(self):
        a=build_setup_candidates(
            pair="EUR/USD",side="BUY",captured_at="2026-09-20T12:00:00Z",
            ict_snapshot={"fvg":{
                "status":"🟢 FVG EM TESTE","score":90,
                "zone_low":1.10,"zone_high":1.11,"price":1.105,
            }},
        )
        b=build_setup_candidates(
            pair="EUR/USD",side="BUY",captured_at="2026-09-20T12:30:00Z",
            ict_snapshot={"fvg":{
                "status":"🟢 FVG EM TESTE","score":92,
                "zone_low":1.10,"zone_high":1.11,"price":1.108,
            }},
        )
        self.assertNotEqual(a["candidates"][0]["candidate_id"],b["candidates"][0]["candidate_id"])
        self.assertEqual(a["candidates"][0]["episode_id"],b["candidates"][0]["episode_id"])

    def test_candidate_id_is_deterministic_for_same_point_in_time_evidence(self):
        args={
            "pair":"EUR/USD",
            "side":"BUY",
            "captured_at":"2026-09-20T12:00:00Z",
            "ict_snapshot":{"fvg":{"status":"🟢 FVG EM TESTE","score":90,"zone_low":1.1,"zone_high":1.2}},
        }
        a=build_setup_candidates(**args)
        b=build_setup_candidates(**args)
        self.assertEqual(a["candidates"][0]["candidate_id"],b["candidates"][0]["candidate_id"])

    def test_wait_side_never_becomes_candidate_even_if_component_status_is_green(self):
        pack=build_setup_candidates(
            pair="EUR/USD",
            side="WAIT",
            captured_at="2026-09-20T12:00:00Z",
            ict_snapshot={"fvg":{"status":"🟢 FVG EM TESTE","score":90}},
        )
        self.assertEqual(pack["candidate_count"],0)

if __name__=="__main__": unittest.main()
