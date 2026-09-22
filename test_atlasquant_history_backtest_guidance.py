import unittest
import pandas as pd

from atlasquant_history_backtest_guidance import (
    backtest_help_model,
    history_change_summary,
    history_chart_frame,
    history_help_model,
    prepare_history,
)


class AtlasQuantHistoryBacktestGuidanceTests(unittest.TestCase):
    def frame(self):
        return pd.DataFrame([
            {"Código":"USD","Pontuação_Final":60,"Pontuação_Macro":58,"Influência_Fed":2,"data":"2026-09-20"},
            {"Código":"EUR","Pontuação_Final":55,"Pontuação_Macro":55,"Influência_Fed":0,"data":"2026-09-20"},
            {"Código":"USD","Pontuação_Final":64,"Pontuação_Macro":61,"Influência_Fed":3,"data":"2026-09-21"},
            {"Código":"EUR","Pontuação_Final":52,"Pontuação_Macro":52,"Influência_Fed":0,"data":"2026-09-21"},
        ])

    def test_history_summary_compares_latest_to_previous_per_currency(self):
        out=history_change_summary(self.frame())
        usd=out[out["Moeda"]=="USD"].iloc[0]
        eur=out[out["Moeda"]=="EUR"].iloc[0]
        self.assertEqual(usd["Mudança"],4.0)
        self.assertEqual(usd["Leitura"],"FORTALECEU")
        self.assertEqual(eur["Mudança"],-3.0)
        self.assertEqual(eur["Leitura"],"ENFRAQUECEU")

    def test_history_missing_columns_fails_closed(self):
        bad=pd.DataFrame([{"foo":1}])
        self.assertTrue(prepare_history(bad).empty)
        self.assertTrue(history_change_summary(bad).empty)

    def test_history_filter_does_not_invent_rows(self):
        out=history_chart_frame(self.frame(),currencies=["USD"],days=7)
        self.assertEqual(set(out["Código"]),{"USD"})
        self.assertEqual(len(out),2)

    def test_history_help_explicitly_separates_history_from_backtest(self):
        model=history_help_model()
        self.assertIn("Não é Backtest",model["not_this"])
        self.assertFalse(model["trading_side_effects"])

    def test_backtest_help_teaches_risk_metrics_and_sample_limits(self):
        model=backtest_help_model()
        joined=" ".join(
            [x[0]+" "+x[1] for x in model["steps"]]
            + list(model["questions"])
            + [model["video_script"]]
            + list(model["warnings"])
        ).casefold()
        for term in ("taxa de acerto","expectativa em r","drawdown","mfe","mae","custos","slippage","amostra"):
            with self.subTest(term=term):
                self.assertIn(term,joined)
        self.assertIn("não garante resultado futuro",joined)
        self.assertFalse(model["automatic_promotion"])
        self.assertFalse(model["trading_side_effects"])


if __name__=="__main__":
    unittest.main()
