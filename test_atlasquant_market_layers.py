import unittest

from atlasquant_market_layers import (
    LAYER_ORDER,
    beginner_layer_summary,
    build_market_layers,
    geopolitical_layer,
    macro_layer,
    micro_fundamentals_layer,
    technical_flow_layer,
)


def pack(**overrides):
    base={
        "pair":"EUR/USD",
        "side":"SELL",
        "direction":"🔴 VENDA EUR/USD",
        "macro_diff":-18.0,
        "quality":82,
        "data_ready":{"sufficient":True,"score":90},
        "h4":"🔴 confirma venda",
        "h1":"🔴 confirma venda",
        "m15":"🟡 aguardando gatilho",
        "gate":"B",
        "ict_read":72,
        "inst_read":84,
        "hard_blocks":[],
        "soft_blocks":["M15 ainda não confirmou gatilho"],
    }
    base.update(overrides)
    return base


def news_state():
    article={
        "title":"Geopolitical tensions escalate after military attack and new sanctions",
        "source":"Reuters",
        "weighted_impact":-0.35,
        "recency_factor":1.0,
        "source_factor":1.15,
        "independence_factor":1.0,
    }
    return {
        "currencies":{
            "EUR":{"articles":[article]},
            "USD":{"articles":[{**article,"weighted_impact":0.20}]},
        }
    }


class AtlasQuantMarketLayersTests(unittest.TestCase):
    def test_contract_has_exact_four_layers(self):
        out=build_market_layers(pack(),news_state=news_state(),macro_context={"fed":{"tom":"Restritivo","forca":0.4}})
        self.assertEqual(tuple(x["id"] for x in out["layers"]),LAYER_ORDER)
        self.assertEqual(len(out["layers"]),4)
        self.assertFalse(out["probability"])
        self.assertFalse(out["changes_score_mestre"])
        self.assertFalse(out["changes_gate"])
        self.assertFalse(out["changes_weights"])
        self.assertFalse(out["real_orders_enabled"])
        self.assertFalse(out["automatic_execution"])
        self.assertIn("consensus",out)
        self.assertTrue(out["consensus"]["advisory_only"])
        self.assertFalse(out["consensus"]["changes_gate"])

    def test_macro_uses_existing_relative_strength_not_probability(self):
        out=macro_layer(pack(),macro_context={"fed":{"tom":"Restritivo","forca":0.4},"event":{"disponivel":True,"evento":"PCE","impacto":"ALTO"}})
        self.assertTrue(out["available"])
        self.assertEqual(out["direction"],"VENDA")
        self.assertLess(out["balance"],0)
        self.assertTrue(any("Fed" in x for x in out["reasons"]))
        self.assertTrue(any("PCE" in x for x in out["risks"]))
        self.assertFalse(out["probability"])
        self.assertFalse(out["decision_effect"])

    def test_geopolitics_requires_actual_geo_stories(self):
        empty=geopolitical_layer("EUR/USD",{"currencies":{"EUR":{"articles":[]},"USD":{"articles":[]}}})
        self.assertFalse(empty["available"])
        self.assertEqual(empty["direction"],"INDISPONÍVEL")
        self.assertEqual(empty["quality"],0)

        out=geopolitical_layer("EUR/USD",news_state())
        self.assertTrue(out["available"])
        self.assertTrue(out["reasons"])
        self.assertIn(out["direction"],{"COMPRA","VENDA","NEUTRO"})
        self.assertLessEqual(abs(out["balance"]),100)
        self.assertFalse(out["probability"])

    def test_non_geopolitical_macro_headline_does_not_fake_geo_signal(self):
        state={"currencies":{
            "EUR":{"articles":[{"title":"Euro area CPI inflation slows","weighted_impact":-0.2}]},
            "USD":{"articles":[{"title":"US payroll growth beats expectations","weighted_impact":0.3}]},
        }}
        out=geopolitical_layer("EUR/USD",state)
        self.assertFalse(out["available"])
        self.assertEqual(out["direction"],"INDISPONÍVEL")

    def test_micro_is_explicitly_unavailable_for_fx_without_inputs(self):
        out=micro_fundamentals_layer("EUR/USD",None)
        self.assertFalse(out["available"])
        self.assertEqual(out["direction"],"INDISPONÍVEL")
        self.assertIn("não inventa",out["detail"])

    def test_micro_can_accept_future_index_constituent_inputs(self):
        state={
            "WIN":{
                "components":[
                    {"name":"Vale","impact":60,"quality":90,"weight":0.35,"reason":"ADR/minério favoráveis"},
                    {"name":"Petrobras","impact":40,"quality":80,"weight":0.30,"reason":"petróleo favorável"},
                    {"name":"Bancos","impact":-20,"quality":75,"weight":0.35,"reason":"juros locais pressionam"},
                ],
                "risks":["Notícia corporativa pode alterar a contribuição."],
            }
        }
        out=micro_fundamentals_layer("WIN",state)
        self.assertTrue(out["available"])
        self.assertGreater(out["balance"],0)
        self.assertEqual(out["direction"],"COMPRA")
        self.assertTrue(any("Vale" in x for x in out["reasons"]))

    def test_technical_fails_closed_when_data_is_stale_or_insufficient(self):
        out=technical_flow_layer(pack(data_ready={"sufficient":False,"score":20}))
        self.assertFalse(out["available"])
        self.assertEqual(out["direction"],"INDISPONÍVEL")
        self.assertTrue(any("insuficientes" in x.casefold() for x in out["risks"]))

    def test_technical_uses_top_down_and_readiness_when_data_valid(self):
        out=technical_flow_layer(pack())
        self.assertTrue(out["available"])
        self.assertLess(out["balance"],0)
        self.assertEqual(out["direction"],"VENDA")
        text=" ".join(out["reasons"])
        self.assertIn("H4",text)
        self.assertIn("ICT readiness",text)
        self.assertIn("Fluxo institucional",text)

    def test_missing_micro_does_not_become_fake_neutral_confidence(self):
        out=build_market_layers(pack(),news_state=news_state())
        micro=next(x for x in out["layers"] if x["id"]=="micro")
        self.assertFalse(micro["available"])
        self.assertIn("micro",out["missing_layers"])
        self.assertEqual(out["available_layers"],3)

    def test_composite_only_renormalizes_available_evidence(self):
        no_geo=build_market_layers(pack(),news_state={"currencies":{}})
        self.assertEqual(no_geo["available_layers"],2)
        self.assertEqual(set(no_geo["missing_layers"]),{"geopolitics","micro"})
        self.assertIn(no_geo["research_direction"],{"COMPRA","VENDA","NEUTRO"})
        self.assertFalse(no_geo["probability"])

    def test_beginner_summary_is_plain_language(self):
        result=build_market_layers(pack(),news_state=news_state())
        text=beginner_layer_summary(result)
        self.assertTrue(text)
        self.assertNotIn("probabilidade",text.casefold())


if __name__=="__main__":
    unittest.main()