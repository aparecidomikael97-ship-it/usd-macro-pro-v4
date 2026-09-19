import unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import autopilot_v107 as a

class AutopilotRecoveryV1075Tests(unittest.TestCase):
    def test_daily_budget_is_conservative(self):
        self.assertLessEqual(a.AUTOPILOT_DAILY_CALL_BUDGET, 500)

    def test_nonpriority_frequencies_reduce_daily_usage(self):
        self.assertGreaterEqual(a.M15_EVERY_MIN, 50)
        self.assertGreaterEqual(a.H1_EVERY_MIN, 110)
        self.assertGreaterEqual(a.H4_EVERY_MIN, 230)

    def test_priority_still_checks_m15_faster(self):
        self.assertLess(a.PRIORITY_M15_EVERY_MIN, a.M15_EVERY_MIN)

    def test_workflow_creates_streamlit_secrets(self):
        wf = Path(".github/workflows/autopilot-v107.yml").read_text(encoding="utf-8")
        self.assertIn("Create Streamlit secrets for headless app", wf)
        self.assertIn(".streamlit/secrets.toml", wf)
        self.assertIn("GITHUB_TOKEN_HISTORICO", wf)

    def test_market_reopens_sunday_21utc(self):
        self.assertFalse(a.forex_market_likely_open(pd.Timestamp("2026-09-20T20:59:59Z")))
        self.assertTrue(a.forex_market_likely_open(pd.Timestamp("2026-09-20T21:00:00Z")))

    def test_status_recovers_to_ready_with_fresh_market_data(self):
        now=pd.Timestamp("2026-09-21T12:00:00Z")
        scanner={"resultados":{p:{"m15_fetched_at":(now-pd.Timedelta(minutes=15)).isoformat()} for p in a.PAIR_ORDER}}
        master={"contexts":{p:{"updated_at":(now-pd.Timedelta(minutes=15)).isoformat()} for p in a.PAIR_ORDER}}
        with patch("autopilot_v107.utcnow",return_value=now):
            status=a.status_summary(True,"ok",{},scanner,master,{},pd.DataFrame(),[],0,{})
        self.assertTrue(status["forex_market_open"])
        self.assertTrue(status["scanner_ready"])
        self.assertTrue(status["market_map_ready"])
        self.assertEqual(status["operational_readiness"],"READY")
        self.assertTrue(status["healthy"])

    def test_status_fails_closed_after_reopen_if_scanner_stale(self):
        now=pd.Timestamp("2026-09-21T12:00:00Z")
        stale=(now-pd.Timedelta(minutes=61)).isoformat()
        scanner={"resultados":{p:{"m15_fetched_at":stale} for p in a.PAIR_ORDER}}
        master={"contexts":{p:{"updated_at":stale} for p in a.PAIR_ORDER}}
        with patch("autopilot_v107.utcnow",return_value=now):
            status=a.status_summary(True,"ok",{},scanner,master,{},pd.DataFrame(),[],0,{})
        self.assertTrue(status["forex_market_open"])
        self.assertFalse(status["scanner_ready"])
        self.assertFalse(status["market_map_ready"])
        self.assertEqual(status["operational_readiness"],"DEGRADED")
        self.assertFalse(status["healthy"])

    def test_workflow_runs_full_paper_and_setup_audit_chain(self):
        wf=Path(".github/workflows/autopilot-v107.yml").read_text(encoding="utf-8")
        self.assertIn("python autopilot_setup_audit_v114.py",wf)

    def test_workflow_revalidates_when_runtime_engine_files_change(self):
        wf=Path(".github/workflows/autopilot-v107.yml").read_text(encoding="utf-8")
        for name in (
            "autopilot_v107.py","autopilot_paper_v112.py",
            "autopilot_setup_audit_v114.py","autopilot_quota_guard_v111.py",
            "paper_trading_v112.py","paper_friction_v116.py",
        ):
            with self.subTest(name=name):
                self.assertIn(name,wf)


    def test_runner_reports_429_message(self):
        src = Path("autopilot_v107.py").read_text(encoding="utf-8")
        self.assertIn("HTTP 429:", src)

if __name__ == "__main__":
    unittest.main()
