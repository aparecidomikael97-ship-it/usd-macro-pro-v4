import unittest
import pandas as pd

from atlasquant_pair_matrix_core import (
    PAIR_MATRIX_PAIRS,
    build_pair_matrix,
    resolve_pair_usd_context,
)


class AtlasQuantCentralPairMatrixTests(unittest.TestCase):
    def ranking(self):
        return pd.DataFrame([
            {"Código":"USD","Pontuação_Final":70},
            {"Código":"EUR","Pontuação_Final":55},
            {"Código":"GBP","Pontuação_Final":60},
            {"Código":"AUD","Pontuação_Final":48},
            {"Código":"NZD","Pontuação_Final":46},
            {"Código":"JPY","Pontuação_Final":40},
            {"Código":"CHF","Pontuação_Final":44},
            {"Código":"CAD","Pontuação_Final":50},
        ])

    def context(self,**overrides):
        data=dict(
            usd_base=68,
            surprise_adjusted_usd=70,
            surprise_adjustment=2,
            fomc_score=80,
            fomc_active=True,
            fomc_post_release_active=False,
            next_event={"disponivel":True,"evento":"FOMC","dias":2},
        )
        data.update(overrides)
        return resolve_pair_usd_context(**data)

    @staticmethod
    def confluence(base,quote,diff,usd,adjustment,fed_tone,ranking):
        return {
            "score_confluencia":80 if abs(diff)>=6 else 50,
            "qualidade_confluencia":85,
            "nivel":"ALTA" if abs(diff)>=12 else "MODERADA",
        }

    def test_fomc_blend_is_shared_and_bounded(self):
        ctx=self.context()
        self.assertEqual(ctx["fomc_weight"],0.25)
        self.assertAlmostEqual(ctx["usd_for_pairs"],72.5)
        self.assertTrue(ctx["fomc_integrated"])

    def test_post_release_prevents_double_counting(self):
        ctx=self.context(fomc_post_release_active=True)
        self.assertEqual(ctx["fomc_weight"],0.0)
        self.assertEqual(ctx["usd_for_pairs"],70.0)
        self.assertFalse(ctx["fomc_integrated"])

    def test_non_fomc_event_does_not_blend(self):
        ctx=self.context(next_event={"disponivel":True,"evento":"CPI","dias":1})
        self.assertEqual(ctx["fomc_weight"],0.0)
        self.assertEqual(ctx["usd_for_pairs"],70.0)

    def test_valid_inputs_build_exactly_seven_unique_pairs(self):
        out=build_pair_matrix(
            ranking=self.ranking(),
            usd_context=self.context(),
            fed_tone="Hawkish",
            confluence_fn=self.confluence,
        )
        self.assertTrue(out["ready"])
        self.assertEqual(out["pairs_built"],7)
        self.assertEqual(set(out["matrix"]["Par"]),set(PAIR_MATRIX_PAIRS))
        self.assertEqual(list(out["matrix"]["Ranking"]),list(range(1,8)))
        self.assertFalse(out["trading_side_effects"])

    def test_missing_currency_fails_closed_without_fake_matrix(self):
        ranking=self.ranking()
        ranking=ranking[ranking["Código"]!="JPY"].copy()
        out=build_pair_matrix(
            ranking=ranking,
            usd_context=self.context(),
            fed_tone="Neutro",
            confluence_fn=self.confluence,
        )
        self.assertFalse(out["ready"])
        self.assertIn("JPY",out["missing_codes"])
        self.assertTrue(out["matrix"].empty)

    def test_invalid_confluence_fails_closed(self):
        def invalid(*args,**kwargs):
            return {"score_confluencia":float("nan"),"qualidade_confluencia":90,"nivel":"ALTA"}
        out=build_pair_matrix(
            ranking=self.ranking(),
            usd_context=self.context(),
            fed_tone="Neutro",
            confluence_fn=invalid,
        )
        self.assertFalse(out["ready"])
        self.assertTrue(out["matrix"].empty)
        self.assertIn("confluência inválida",out["reason"])

    def test_neutral_or_low_quality_never_becomes_direction(self):
        def low(*args,**kwargs):
            return {"score_confluencia":90,"qualidade_confluencia":40,"nivel":"ALTA"}
        out=build_pair_matrix(
            ranking=self.ranking(),
            usd_context=self.context(),
            fed_tone="Neutro",
            confluence_fn=low,
        )
        self.assertTrue(out["ready"])
        self.assertTrue(all("AGUARDAR" in x for x in out["matrix"]["Direção"]))


if __name__=="__main__":
    unittest.main()
