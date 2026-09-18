import unittest

import pandas as pd

from autopilot_setup_audit_v114 import (
    aggregate_setup_performance,
    build_summary,
    sync_setup_audit,
)


NOW = pd.Timestamp("2026-09-17T16:30:00Z")


def scanner_with_fvg(status: str, score: float = 70.0) -> dict:
    return {
        "resultados": {
            "EUR/USD": {
                "tecnico": {
                    "ict": {
                        "amd": {"status": "AMD TESTE", "score": 40},
                        "fvg": {"status": status, "score": score},
                        "crt": {"status": "CRT TESTE", "score": 30},
                        "ote": {"status": "OTE TESTE", "score": 50},
                    },
                    "institutional": {
                        "displacement": {"status": "DISP TESTE", "score": 80},
                        "mss": {"status": "MSS TESTE", "score": 60},
                        "smt": {"status": "SMT TESTE", "score": 55},
                        "dealing_range": {"status": "DR TESTE", "score": 65},
                        "liquidity": {"status": "LIQ TESTE", "score": 75},
                        "session": {"status": "SESSION TESTE", "score": 90},
                        "pd_array": {"status": "PD TESTE", "score": 68},
                    },
                }
            }
        }
    }


def trade_row(*, trade_id="t1", status="WAIT_ENTRY", result="", realized_r=None) -> dict:
    return {
        "trade_id": trade_id,
        "signal_id": trade_id,
        "pair": "EUR/USD",
        "side": "BUY",
        "status": status,
        "result": result,
        "signal_time": "2026-09-17T16:15:00Z",
        "signal_candle_time": "2026-09-17T16:00:00Z",
        "score_master": 82.0,
        "quality": 78.0,
        "rank_index": 5.0,
        "h4": "CONFIRMA",
        "h1": "PULLBACK OK",
        "m15": "GATILHO",
        "ict_readiness": 80.0,
        "institutional_readiness": 84.0,
        "gate": "A",
        "gate_score": 88.0,
        "adr_used_pct": 50.0,
        "event_risk": "BAIXO",
        "technical_age_min": 5.0,
        "map_age_min": 3.0,
        "data_sufficient": True,
        "checklist_passed": True,
        "checklist_note": "ok",
        "created_at": "2026-09-17T16:16:00Z",
        "updated_at": "2026-09-17T16:16:00Z",
        "engine_version": "V11.2_PAPER_TRADING",
        "entry_time": None,
        "entry_price": None,
        "stop_price": None,
        "target_price": None,
        "risk_distance": None,
        "target_rr": 2.0,
        "exit_time": "2026-09-17T16:45:00Z" if status == "CLOSED" else None,
        "exit_price": 1.1 if status == "CLOSED" else None,
        "exit_reason": "TARGET" if result == "WIN" else "STOP" if result == "LOSS" else "",
        "realized_r": realized_r,
        "bars_held": 2 if status == "CLOSED" else None,
        "mfe_r": 2.0 if status == "CLOSED" else None,
        "mae_r": 0.4 if status == "CLOSED" else None,
        "ambiguous_touch": False,
    }


class SetupAuditV114Tests(unittest.TestCase):
    def test_new_trade_freezes_component_snapshot(self):
        trades = pd.DataFrame([trade_row()])
        audit = sync_setup_audit(trades, scanner_with_fvg("FVG ATIVO", 72), now=NOW)
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit.iloc[0]["fvg_status"], "FVG ATIVO")
        self.assertEqual(float(audit.iloc[0]["fvg_score"]), 72.0)
        self.assertEqual(audit.iloc[0]["mss_status"], "MSS TESTE")
        self.assertEqual(audit.iloc[0]["audit_capture_mode"], "FIRST_SEEN_V114")

    def test_existing_snapshot_is_not_overwritten_but_outcome_updates(self):
        first = sync_setup_audit(
            pd.DataFrame([trade_row()]),
            scanner_with_fvg("FVG ORIGINAL", 71),
            now=NOW,
        )
        closed = trade_row(status="CLOSED", result="WIN", realized_r=2.0)
        second = sync_setup_audit(
            pd.DataFrame([closed]),
            scanner_with_fvg("FVG MUDOU DEPOIS", 10),
            first,
            now=NOW + pd.Timedelta(minutes=30),
        )
        row = second.iloc[0]
        self.assertEqual(row["fvg_status"], "FVG ORIGINAL")
        self.assertEqual(float(row["fvg_score"]), 71.0)
        self.assertEqual(row["status"], "CLOSED")
        self.assertEqual(row["result"], "WIN")
        self.assertEqual(float(row["realized_r"]), 2.0)

    def test_aggregate_uses_only_closed_trades(self):
        rows = [
            trade_row(trade_id="w", status="CLOSED", result="WIN", realized_r=2.0),
            trade_row(trade_id="l", status="CLOSED", result="LOSS", realized_r=-1.0),
            trade_row(trade_id="o", status="OPEN", result="", realized_r=None),
        ]
        audit = sync_setup_audit(
            pd.DataFrame(rows),
            scanner_with_fvg("FVG ATIVO", 70),
            now=NOW,
        )
        perf = aggregate_setup_performance(audit)
        fvg = perf[(perf["component"] == "FVG") & (perf["state"] == "FVG ATIVO")].iloc[0]
        self.assertEqual(int(fvg["trades_closed"]), 2)
        self.assertEqual(int(fvg["wins"]), 1)
        self.assertEqual(int(fvg["losses"]), 1)
        self.assertEqual(float(fvg["win_rate_pct"]), 50.0)
        self.assertEqual(float(fvg["net_r"]), 1.0)
        self.assertEqual(float(fvg["avg_r"]), 0.5)
        self.assertEqual(float(fvg["profit_factor_r"]), 2.0)

    def test_duplicate_trade_id_remains_single_frozen_audit_row(self):
        duplicate=pd.DataFrame([trade_row(),trade_row()])
        audit=sync_setup_audit(duplicate,scanner_with_fvg("FVG ORIGINAL",71),now=NOW)
        self.assertEqual(len(audit),1)
        self.assertEqual(audit.iloc[0]["trade_id"],"t1")
        self.assertEqual(audit.iloc[0]["fvg_status"],"FVG ORIGINAL")

    def test_nonfinite_component_score_is_not_propagated(self):
        audit=sync_setup_audit(
            pd.DataFrame([trade_row()]),
            scanner_with_fvg("FVG ATIVO",float("nan")),
            now=NOW,
        )
        self.assertTrue(pd.isna(audit.iloc[0]["fvg_score"]))

    def test_summary_never_enables_execution_or_strategy_selection(self):
        audit=sync_setup_audit(pd.DataFrame([trade_row()]),scanner_with_fvg("FVG",70),now=NOW)
        summary=build_summary(audit,aggregate_setup_performance(audit),now=NOW)
        safety=summary["safety"]
        self.assertFalse(safety["real_orders"])
        self.assertFalse(safety["broker_connection"])
        self.assertFalse(safety["auto_strategy_selection"])
        self.assertFalse(safety["auto_gate_change"])

    def test_empty_is_safe(self):
        audit = sync_setup_audit(pd.DataFrame(), {}, pd.DataFrame(), now=NOW)
        perf = aggregate_setup_performance(audit)
        summary = build_summary(audit, perf, now=NOW)
        self.assertTrue(audit.empty)
        self.assertTrue(perf.empty)
        self.assertEqual(summary["audited_trades"], 0)
        self.assertEqual(summary["closed_trades"], 0)
        self.assertEqual(summary["sample_state"], "AGUARDANDO AMOSTRA")
        self.assertFalse(summary["safety"]["real_orders"])
        self.assertFalse(summary["safety"]["auto_strategy_selection"])


if __name__ == "__main__":
    unittest.main()
