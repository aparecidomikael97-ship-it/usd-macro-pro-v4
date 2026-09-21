import os
import unittest
from unittest.mock import Mock, patch
from io import StringIO
from contextlib import redirect_stdout

import pandas as pd

import autopilot_news_nowcast_v1 as news_runner
import autopilot_setup_audit_v114 as audit_runner
from autopilot_setup_audit_v114 import (
    aggregate_setup_performance,
    build_summary,
    sync_setup_audit,
    _audit_cycle,
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


def market_map_context(*, d1_regime="TENDÊNCIA ALTISTA", session="London Killzone") -> dict:
    return {
        "contexts":{
            "EUR/USD":{
                "d1":{"structure":{"regime":d1_regime}},
                "w1":{"structure":{"regime":"EXPANSÃO"}},
                "killzone":{"active":{"name":session} if session else None},
                "premium_discount":{"zone":"DESCONTO"},
                "latest_sweep":{"type":"SSL"},
            }
        }
    }


def trade_row(*, trade_id="t1", status="WAIT_ENTRY", result="", realized_r=None, setup_id="", setup_attribution="UNATTRIBUTED", d1_regime="", active_session="", data_quality_pct=100.0) -> dict:
    return {
        "trade_id": trade_id,
        "signal_id": trade_id,
        "pair": "EUR/USD",
        "side": "BUY",
        "setup_id":setup_id,
        "setup_attribution":setup_attribution,
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
        "data_quality_pct":data_quality_pct,
        "d1_regime":d1_regime,
        "w1_regime":"",
        "active_session":active_session,
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


    def test_new_trade_freezes_regime_and_session_context(self):
        audit=sync_setup_audit(
            pd.DataFrame([trade_row()]),
            scanner_with_fvg("FVG ATIVO",72),
            market_map=market_map_context(),
            now=NOW,
        )
        row=audit.iloc[0]
        self.assertEqual(row["d1_regime"],"TENDÊNCIA ALTISTA")
        self.assertEqual(row["w1_regime"],"EXPANSÃO")
        self.assertEqual(row["active_session"],"London Killzone")
        self.assertEqual(row["premium_discount_zone"],"DESCONTO")
        self.assertEqual(row["latest_sweep_type"],"SSL")

    def test_explicit_setup_and_original_session_context_are_frozen(self):
        trade=trade_row(
            setup_id="fvg",
            setup_attribution="EXPLICIT_INPUT",
            d1_regime="REGIME NO SINAL",
            active_session="Asia",
            data_quality_pct=100,
        )
        audit=sync_setup_audit(
            pd.DataFrame([trade]),
            scanner_with_fvg("FVG ATIVO",72),
            market_map=market_map_context(d1_regime="REGIME DEPOIS",session="London"),
            now=NOW,
        )
        row=audit.iloc[0]
        self.assertEqual(row["setup_id"],"fvg")
        self.assertEqual(row["setup_attribution"],"EXPLICIT_INPUT")
        self.assertEqual(row["d1_regime"],"REGIME NO SINAL")
        self.assertEqual(row["active_session"],"Asia")
        self.assertEqual(float(row["data_quality_pct"]),100.0)

    def test_regime_context_is_frozen_after_first_seen(self):
        first=sync_setup_audit(
            pd.DataFrame([trade_row()]),
            scanner_with_fvg("FVG ORIGINAL",71),
            market_map=market_map_context(d1_regime="TENDÊNCIA ALTISTA"),
            now=NOW,
        )
        second=sync_setup_audit(
            pd.DataFrame([trade_row(status="CLOSED",result="WIN",realized_r=2.0)]),
            scanner_with_fvg("FVG ALTERADO",10),
            first,
            market_map=market_map_context(d1_regime="TENDÊNCIA BAIXISTA",session="New York AM"),
            now=NOW+pd.Timedelta(minutes=30),
        )
        row=second.iloc[0]
        self.assertEqual(row["d1_regime"],"TENDÊNCIA ALTISTA")
        self.assertEqual(row["active_session"],"London Killzone")

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


    def test_nonfinite_realized_r_is_excluded_from_performance_and_summary(self):
        for bad in (float("nan"),float("inf"),float("-inf")):
            with self.subTest(realized_r=bad):
                audit=sync_setup_audit(
                    pd.DataFrame([trade_row(status="CLOSED",result="WIN",realized_r=bad)]),
                    scanner_with_fvg("FVG ATIVO",70),
                    now=NOW,
                )
                perf=aggregate_setup_performance(audit)
                summary=build_summary(audit,perf,now=NOW)
                self.assertTrue(perf.empty)
                self.assertEqual(summary["closed_trades"],0)
                self.assertEqual(summary["net_r"],0.0)

    def test_summary_counts_only_explicit_setup_tags_without_inference(self):
        rows=[
            trade_row(
                trade_id="tagged",status="CLOSED",result="WIN",realized_r=2.0,
                setup_id="fvg",setup_attribution="EXPLICIT_INPUT",
            ),
            trade_row(
                trade_id="plain",status="CLOSED",result="LOSS",realized_r=-1.0,
            ),
        ]
        audit=sync_setup_audit(pd.DataFrame(rows),scanner_with_fvg("FVG",70),now=NOW)
        summary=build_summary(audit,aggregate_setup_performance(audit),now=NOW)
        self.assertEqual(summary["explicit_setup_trades"],1)
        self.assertEqual(summary["explicit_setup_closed_trades"],1)
        self.assertFalse(summary["setup_attribution_inferred"])

    def test_untrusted_setup_id_is_not_counted_as_explicit(self):
        row=trade_row(
            status="CLOSED",result="WIN",realized_r=2.0,
            setup_id="fvg",setup_attribution="",
        )
        audit=sync_setup_audit(pd.DataFrame([row]),scanner_with_fvg("FVG",70),now=NOW)
        summary=build_summary(audit,aggregate_setup_performance(audit),now=NOW)
        self.assertEqual(summary["explicit_setup_trades"],0)
        self.assertEqual(summary["explicit_setup_closed_trades"],0)
        self.assertFalse(summary["setup_attribution_inferred"])

    def test_summary_never_enables_execution_or_strategy_selection(self):
        audit=sync_setup_audit(pd.DataFrame([trade_row()]),scanner_with_fvg("FVG",70),now=NOW)
        summary=build_summary(audit,aggregate_setup_performance(audit),now=NOW)
        safety=summary["safety"]
        self.assertFalse(safety["real_orders"])
        self.assertFalse(safety["broker_connection"])
        self.assertFalse(safety["auto_strategy_selection"])
        self.assertFalse(safety["auto_gate_change"])


    def test_paper_blockers_are_descriptive_and_never_change_thresholds(self):
        status={"paper_trading_v112":{"last_cycle":{"checklists":{
            "EUR/USD":{"passed":False,"state":"🟡 DIREÇÃO CONFIRMADA — AGUARDAR EXECUÇÃO","hard_blocks":[],"soft_blocks":["ICT incompleto (42/100)","M15 ainda não confirmou gatilho"]},
            "USD/JPY":{"passed":False,"state":"⚪ EM OBSERVAÇÃO","hard_blocks":["Gate bloqueado"],"soft_blocks":["M15 ainda não confirmou gatilho"]},
        }}}}
        summary=build_summary(pd.DataFrame(),pd.DataFrame(),now=NOW,status=status)
        blockers=summary["paper_blockers"]
        self.assertEqual(blockers["pairs_evaluated"],2)
        self.assertEqual(blockers["checklists_passed"],0)
        self.assertEqual(blockers["soft_block_counts"]["M15 ainda não confirmou gatilho"],2)
        self.assertEqual(blockers["hard_block_counts"]["Gate bloqueado"],1)
        self.assertTrue(blockers["diagnostic_only"])
        self.assertFalse(blockers["thresholds_changed"])
        self.assertFalse(summary["safety"]["real_orders"])
        self.assertFalse(summary["safety"]["auto_gate_change"])

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


    def test_main_runs_news_nowcast_sidecar_and_preserves_core_return_code(self):
        with patch.object(audit_runner.paper_runner,"main",return_value=7) as paper, \
             patch.object(audit_runner,"_audit_cycle",return_value=(True,{"audited_trades":0},[])) as audit, \
             patch.object(audit_runner.news_nowcast_runner,"_news_nowcast_cycle",return_value=(True,{"runtime_state":"THROTTLED"},[])) as news:
            out=StringIO()
            with redirect_stdout(out):
                rc=audit_runner.main()
        self.assertEqual(rc,7)
        paper.assert_called_once()
        audit.assert_called_once()
        news.assert_called_once()
        self.assertIn("news_nowcast_v1",out.getvalue())

    def test_news_nowcast_provider_throttle_is_six_hours_by_default(self):
        now=pd.Timestamp("2026-09-20T18:00:00Z")
        self.assertFalse(news_runner.should_fetch_provider(
            {"last_success_at":"2026-09-20T13:00:01Z"},now=now
        ))
        self.assertTrue(news_runner.should_fetch_provider(
            {"last_success_at":"2026-09-20T11:59:59Z"},now=now
        ))
        self.assertTrue(news_runner.should_fetch_provider({},now=now))

    def test_news_provider_paginates_once_when_first_page_is_full(self):
        first=Mock()
        first.status_code=200
        first.raise_for_status.return_value=None
        first.json.return_value=[
            {"type":f"Event {i}","date":"2026-09-01 12:00:00","country":"US"}
            for i in range(1000)
        ]
        second=Mock()
        second.status_code=200
        second.raise_for_status.return_value=None
        second.json.return_value=[
            {"type":"Tail Event","date":"2026-09-02 12:00:00","country":"US"}
        ]
        with patch.object(news_runner.requests,"get",side_effect=[first,second]) as get:
            rows,status=news_runner.fetch_eodhd_events(
                "token",start_date="2026-06-01",end_date="2026-09-30"
            )
        self.assertTrue(status["ok"])
        self.assertTrue(status["paginated"])
        self.assertEqual(status["requests"],2)
        self.assertEqual(len(rows),1001)
        self.assertEqual(get.call_args_list[0].kwargs["params"]["offset"],0)
        self.assertEqual(get.call_args_list[1].kwargs["params"]["offset"],1000)

    def test_news_provider_fails_closed_when_two_pages_are_full(self):
        page=Mock()
        page.status_code=200
        page.raise_for_status.return_value=None
        page.json.return_value=[
            {"type":f"Event {i}","date":"2026-09-01 12:00:00","country":"US"}
            for i in range(1000)
        ]
        page2=Mock()
        page2.status_code=200
        page2.raise_for_status.return_value=None
        page2.json.return_value=[
            {"type":f"Tail {i}","date":"2026-09-02 12:00:00","country":"US"}
            for i in range(1000)
        ]
        with patch.object(news_runner.requests,"get",side_effect=[page,page2]):
            rows,status=news_runner.fetch_eodhd_events(
                "token",start_date="2026-01-01",end_date="2026-09-30"
            )
        self.assertFalse(status["ok"])
        self.assertEqual(status["reason"],"TRUNCATED_PROVIDER_DATA")
        self.assertEqual(rows,[])

    def test_news_nowcast_missing_optional_provider_fails_closed_without_core_failure(self):
        json_writes=[]
        with patch.dict(os.environ,{"CHAVE_EODHD":""},clear=False), \
             patch.object(news_runner.base,"gh_get_csv",return_value=(pd.DataFrame(),"")), \
             patch.object(news_runner.base,"gh_get_json",side_effect=[({},""),({},"")]), \
             patch.object(news_runner.base,"gh_put_json",side_effect=lambda path,obj,message:(json_writes.append((path,obj)) or (True,""))), \
             patch.object(news_runner.base,"utcnow",return_value=pd.Timestamp("2026-09-20T18:00:00Z")):
            ok,summary,errors=news_runner._news_nowcast_cycle()
        self.assertTrue(ok)
        self.assertEqual(errors,[])
        self.assertEqual(summary["runtime_state"],"NOT_CONFIGURED")
        self.assertFalse(summary["safety"]["real_orders"])
        self.assertFalse(summary["safety"]["market_reaction_predicted"])
        self.assertTrue(any(path==news_runner.SUMMARY_PATH for path,_ in json_writes))

    def test_status_write_failure_is_visible_in_stdout_even_when_status_cannot_persist(self):
        with patch("autopilot_setup_audit_v114.base.gh_get_csv",return_value=(pd.DataFrame(),"")), \
             patch("autopilot_setup_audit_v114.base.gh_get_json",side_effect=[({},""),({},""),({},"")]), \
             patch("autopilot_setup_audit_v114.base.gh_put_csv",return_value=(True,"")), \
             patch("autopilot_setup_audit_v114.base.gh_put_json",side_effect=[(True,""),(False,"remote unavailable")]), \
             patch("autopilot_setup_audit_v114.base.utcnow",return_value=NOW):
            out=StringIO()
            with redirect_stdout(out):
                ok,summary,errors=_audit_cycle()
        self.assertFalse(ok)
        self.assertTrue(any("Salvar status setup audit" in x for x in errors))
        self.assertIn("[setup-audit][status-write-failed]",out.getvalue())
        self.assertIn("remote unavailable",out.getvalue())


if __name__ == "__main__":
    unittest.main()
