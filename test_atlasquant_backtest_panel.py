import inspect
import unittest
import pandas as pd

from atlasquant_backtest_panel import (
    read_csv_bytes,
    normalize_tradingview_candles,
    normalize_signal_sheet,
    signal_template_csv,
    candles_template_csv,
    render_operational_backtest_panel,
    load_tradingview_fvg_pine_asset,
    load_tradingview_ote_pine_asset,
    load_tradingview_crt_pine_asset,
    load_tradingview_amd_pine_asset,
    backtest_result_status,
)


class BacktestPanelTests(unittest.TestCase):
    def test_tradingview_time_alias_is_normalized(self):
        raw=pd.DataFrame({
            "time":["2026-09-15T00:00:00Z"],
            "open":[1.1],"high":[1.2],"low":[1.0],"close":[1.15],
        })
        out=normalize_tradingview_candles(raw)
        self.assertEqual(list(out.columns),["datetime","open","high","low","close"])
        self.assertEqual(len(out),1)

    def test_portuguese_candle_aliases_are_normalized(self):
        raw=pd.DataFrame({
            "data":["2026-09-15T00:00:00Z"],
            "abertura":[1.1],"máxima":[1.2],"mínima":[1.0],"fechamento":[1.15],
        })
        out=normalize_tradingview_candles(raw)
        self.assertEqual(len(out),1)
        self.assertAlmostEqual(out.iloc[0]["close"],1.15)

    def test_signal_sheet_accepts_portuguese_aliases(self):
        raw=pd.DataFrame({
            "data_hora":["2026-09-15T00:00:00Z"],
            "par":["EUR/USD"],
            "operacional":["OB+CHOCH"],
            "sessão":["Londres"],
            "direção":["COMPRA"],
            "entrada":[1.10],"sl":[1.09],"alvo":[1.12],
        })
        out=normalize_signal_sheet(raw)
        self.assertEqual(out.iloc[0]["side"],"BUY")
        self.assertEqual(out.iloc[0]["setup"],"OB+CHOCH")
        self.assertEqual(out.iloc[0]["pair"],"EUR/USD")

    def test_default_pair_fills_missing_pair(self):
        raw=pd.DataFrame({
            "signal_time":["2026-09-15T00:00:00Z"],
            "side":["SELL"],"entry":[1.10],"stop":[1.11],"target":[1.08],
        })
        out=normalize_signal_sheet(raw,default_pair="GBP/USD")
        self.assertEqual(out.iloc[0]["pair"],"GBP/USD")

    def test_missing_required_signal_columns_fails_closed(self):
        raw=pd.DataFrame({"side":["BUY"],"entry":[1.1]})
        out=normalize_signal_sheet(raw,default_pair="EUR/USD")
        self.assertTrue(out.empty)

    def test_templates_have_only_headers(self):
        self.assertEqual(signal_template_csv().count("\n"),1)
        self.assertIn("signal_time",signal_template_csv())
        self.assertEqual(candles_template_csv().count("\n"),1)
        self.assertIn("datetime",candles_template_csv())

    def test_signal_sheet_preserves_optional_point_in_time_context(self):
        raw=pd.DataFrame({
            "signal_time":["2026-09-15T00:00:00Z"],
            "pair":["EUR/USD"],
            "side":["BUY"],
            "entry":[1.10],
            "stop":[1.09],
            "target":[1.12],
            "macro_alignment":[1],
            "technical_confirmation":[True],
            "liquidity_confirmation":[True],
            "regime_fit":[True],
            "regime":["TREND"],
            "known_high_impact_event":[False],
            "data_quality_pct":[96],
            "plan_followed":[True],
            "event_label":["CPI"],
            "event_impact":["HIGH"],
        })
        out=normalize_signal_sheet(raw)
        self.assertEqual(out.iloc[0]["macro_alignment"],1)
        self.assertTrue(out.iloc[0]["technical_confirmation"])
        self.assertEqual(out.iloc[0]["regime"],"TREND")
        self.assertEqual(out.iloc[0]["event_label"],"CPI")

    def test_signal_template_exposes_diagnostic_columns(self):
        template=signal_template_csv()
        for field in (
            "macro_alignment","technical_confirmation","liquidity_confirmation",
            "regime_fit","known_high_impact_event","data_quality_pct","plan_followed",
            "event_time","event_label","event_impact",
        ):
            self.assertIn(field,template)

    def test_panel_exposes_automatic_replay(self):
        source=inspect.getsource(render_operational_backtest_panel)
        self.assertIn("Rodar backtest automático",source)
        self.assertIn("single_position_per_pair=True",source)
        self.assertIn("generate_bos_choch_ob_signals",source)

    def test_panel_exposes_separate_fvg_replay(self):
        source=inspect.getsource(render_operational_backtest_panel)
        self.assertIn("Rodar backtest FVG",source)
        self.assertIn("generate_fvg_signals",source)
        self.assertIn('key_suffix="fvg"',source)

    def test_fvg_pine_loader_returns_content(self):
        text=load_tradingview_fvg_pine_asset()
        self.assertIn("AtlasQuant FVG Research V1",text)
        self.assertIn("strategy.entry",text)

    def test_panel_exposes_separate_ote_replay(self):
        source=inspect.getsource(render_operational_backtest_panel)
        self.assertIn("Rodar backtest OTE",source)
        self.assertIn("generate_ote_signals",source)
        self.assertIn('key_suffix="ote"',source)

    def test_ote_pine_loader_returns_content(self):
        text=load_tradingview_ote_pine_asset()
        self.assertIn("AtlasQuant OTE Research V1",text)
        self.assertIn("strategy.entry",text)

    def test_panel_exposes_separate_crt_replay(self):
        source=inspect.getsource(render_operational_backtest_panel)
        self.assertIn("Rodar backtest CRT",source)
        self.assertIn("generate_crt_signals",source)
        self.assertIn('key_suffix="crt"',source)

    def test_crt_pine_loader_returns_content(self):
        text=load_tradingview_crt_pine_asset()
        self.assertIn("AtlasQuant CRT Research V1",text)
        self.assertIn("strategy.entry",text)

    def test_panel_exposes_separate_amd_replay(self):
        source=inspect.getsource(render_operational_backtest_panel)
        self.assertIn("Rodar backtest AMD",source)
        self.assertIn("generate_amd_signals",source)
        self.assertIn('key_suffix="amd"',source)

    def test_amd_pine_loader_returns_content(self):
        text=load_tradingview_amd_pine_asset()
        self.assertIn("AtlasQuant AMD Power of Three Research V1",text)
        self.assertIn("strategy.entry",text)

    def test_panel_exposes_five_strategy_comparator(self):
        source=inspect.getsource(render_operational_backtest_panel)
        self.assertIn("Comparar os 5 operacionais",source)
        self.assertIn("run_strategy_suite",source)
        self.assertIn("comparison_frame",source)
        self.assertIn("observed_expectancy_rank",source)

    def test_panel_exposes_temporal_stability_for_comparator(self):
        source=inspect.getsource(render_operational_backtest_panel)
        self.assertIn("Estabilidade temporal",source)
        self.assertIn("temporal_stability_report",source)
        self.assertIn("Blocos temporais",source)
        self.assertIn("Baixar estabilidade",source)

    def test_panel_exposes_walk_forward_diagnostics(self):
        source=inspect.getsource(render_operational_backtest_panel)
        self.assertIn("Walk-forward — treino anterior × teste futuro",source)
        self.assertIn("walk_forward_report",source)
        self.assertIn("Janelas OOS",source)
        self.assertIn("Baixar walk-forward",source)

    def test_panel_exposes_cost_and_slippage_sensitivity(self):
        source=inspect.getsource(render_operational_backtest_panel)
        self.assertIn("Slippage adverso por trade (R)",source)
        self.assertIn("Sensibilidade a custos e slippage",source)
        self.assertIn("friction_sensitivity_report",source)
        self.assertIn("Baixar custos/slippage",source)
        self.assertIn("slippage_r=float(slippage_r)",source)

    def test_panel_exposes_segmented_friction_and_parameter_robustness(self):
        source=inspect.getsource(render_operational_backtest_panel)
        self.assertIn("Ver custos/slippage por sessão e par",source)
        self.assertIn("friction_breakdown",source)
        self.assertIn("Robustez de parâmetros pré-definidos",source)
        self.assertIn("parameter_robustness_report",source)
        self.assertIn("não procura nem escolhe automaticamente o melhor parâmetro",source)
        self.assertIn("Baixar robustez de parâmetros",source)

    def test_panel_exposes_consolidated_evidence_report(self):
        source=inspect.getsource(render_operational_backtest_panel)
        self.assertIn("Relatório consolidado de evidências",source)
        self.assertIn("consolidated_evidence_frame",source)
        self.assertIn("build_evidence_bundle",source)
        self.assertIn("Baixar relatório de evidências",source)
        self.assertIn("Baixar resumo de evidências",source)
        self.assertIn("não qualidade do setup",source)

    def test_panel_exposes_reproducible_snapshot_and_diff(self):
        source=inspect.getsource(render_operational_backtest_panel)
        self.assertIn("Snapshot reproduzível do Backtest",source)
        self.assertIn("build_backtest_snapshot",source)
        self.assertIn("Baixar snapshot reproduzível",source)
        self.assertIn("Comparar dois snapshots salvos",source)
        self.assertIn("compare_backtest_snapshots",source)
        self.assertIn("Baixar diff dos snapshots",source)

    def test_panel_exposes_local_snapshot_history(self):
        source=inspect.getsource(render_operational_backtest_panel)
        self.assertIn("Histórico local de snapshots",source)
        self.assertIn("save_snapshot_local",source)
        self.assertIn("load_snapshot_history",source)
        self.assertIn("Linha do tempo",source)
        self.assertIn("Mudanças entre execuções consecutivas",source)
        self.assertIn("Baixar histórico de snapshots",source)
        self.assertIn("Restaurar histórico exportado",source)
        self.assertIn("Validar e restaurar histórico ZIP",source)
        self.assertIn("inspect_history_archive",source)
        self.assertIn("restore_history_archive",source)
        self.assertIn("fora de dados/",source)

    def test_csv_bytes_read_utf8(self):
        raw=b"time,open,high,low,close\n2026-09-15T00:00:00Z,1,2,0.5,1.5\n"
        out=read_csv_bytes(raw)
        self.assertEqual(len(out),1)
        self.assertIn("time",out.columns)


    def test_panel_exposes_gain_loss_diagnosis_and_passport(self):
        source=inspect.getsource(render_operational_backtest_panel)
        module_source=inspect.getsource(__import__("atlasquant_backtest_panel"))
        self.assertIn("backtest_intelligence_bundle",module_source)
        self.assertIn("Por que deu gain ou loss?",module_source)
        self.assertIn("Passaporte do Operacional",module_source)
        self.assertIn("atlasquant_last_backtest_intelligence",module_source)
        self.assertIn("não inventa uma causa",module_source)

    def test_backtest_status_is_descriptive_not_trade_authorization(self):
        self.assertEqual(backtest_result_status({"trades":0})["label"],"SEM AMOSTRA")
        self.assertEqual(backtest_result_status({"trades":10,"net_r":4,"max_drawdown_r":1})["label"],"AMOSTRA POSITIVA")
        self.assertEqual(backtest_result_status({"trades":10,"net_r":-1,"max_drawdown_r":3})["label"],"AMOSTRA NEGATIVA")
        source=inspect.getsource(backtest_result_status)
        self.assertNotIn("EXECUTÁVEL",source)
        self.assertNotIn("BUY",source)
        self.assertNotIn("SELL",source)



if __name__=="__main__":
    unittest.main()
