import unittest

from atlasquant_home_radar import (
    home_rows_from_packs,
    home_summary,
    voice_script_for_row,
)


def _pack(
    pair="EUR/USD",
    direction="🟢 COMPRA",
    *,
    sufficient=True,
    state="🟢 CONTEXTO VÁLIDO",
    gate="A",
    priority=82,
    quality=76,
    data_score=88,
):
    return {
        "pair":pair,
        "direction":direction,
        "state":state,
        "priority":priority,
        "quality":quality,
        "data_ready":{"sufficient":sufficient,"score":data_score},
        "strength":{"base_score":72,"quote_score":48,"difference":24},
        "h4":"🟢 confirma compra",
        "h1":"🟢 confirma compra",
        "m15":"🟡 aguardando gatilho",
        "gate":gate,
        "event":"NORMAL",
        "news_align":"base favorecida",
        "adr":63,
        "reason":"EUR está mais forte que USD e a estrutura maior está alinhada.",
        "next_action":"Esperar gatilho válido no M15.",
        "blockers":["M15 ainda aguarda gatilho"],
        "target":"BSL",
        "w1":"🟢 altista",
        "d1":"🟢 altista",
        "pd_zone":"DISCOUNT",
        "sweep_type":"SSL",
        "sweep_level":"PDL",
        "ict_read":74,
        "inst_read":81,
        "up":["H4 confirma compra"],
        "down":["evento contrário"],
        "positives":["estrutura coerente"],
        "hard_blocks":[],
        "soft_blocks":["M15 ainda aguarda gatilho"],
    }


class AtlasQuantHomeRadarTests(unittest.TestCase):
    def test_valid_buy_remains_analysis_buy(self):
        rows=home_rows_from_packs([_pack()])
        self.assertEqual(rows[0]["bias"],"COMPRA")
        self.assertEqual(rows[0]["action"],"COMPRA")
        self.assertTrue(rows[0]["data_ready"])

    def test_stale_or_insufficient_data_fails_closed(self):
        rows=home_rows_from_packs([_pack(sufficient=False,data_score=20)])
        self.assertEqual(rows[0]["bias"],"COMPRA")
        self.assertEqual(rows[0]["action"],"NÃO OPERAR")

    def test_wait_state_never_becomes_trade_direction(self):
        rows=home_rows_from_packs([_pack(direction="⚪ AGUARDAR",state="⚪ AGUARDAR",gate="WAIT")])
        self.assertEqual(rows[0]["bias"],"NEUTRO")
        self.assertEqual(rows[0]["action"],"NÃO OPERAR")

    def test_rows_are_sorted_by_actionable_priority(self):
        packs=[
            _pack(pair="EUR/USD",priority=60),
            _pack(pair="GBP/USD",priority=90,sufficient=False),
            _pack(pair="AUD/USD",priority=85),
        ]
        rows=home_rows_from_packs(packs)
        self.assertEqual(rows[0]["pair"],"AUD/USD")
        self.assertEqual(rows[-1]["pair"],"GBP/USD")

    def test_summary_is_conservative(self):
        rows=home_rows_from_packs([
            _pack(pair="EUR/USD"),
            _pack(pair="GBP/USD",direction="🔴 VENDA"),
            _pack(pair="AUD/USD",sufficient=False),
        ])
        summary=home_summary(rows)
        self.assertEqual(summary["total"],3)
        self.assertEqual(summary["actionable"],2)
        self.assertEqual(summary["blocked"],1)

    def test_voice_explains_reason_risk_and_no_order(self):
        row=home_rows_from_packs([_pack()])[0]
        script=voice_script_for_row(row).casefold()
        self.assertIn("análise do eur/usd",script)
        self.assertIn("próximo passo",script)
        self.assertIn("não é garantia",script)
        self.assertIn("nem ordem para corretora",script)

    def test_research_consensus_is_visible_but_does_not_override_action(self):
        rows=home_rows_from_packs([_pack()],macro_context={"fed":{"tom":"Neutro","forca":0}})
        row=rows[0]
        self.assertEqual(row["action"],"COMPRA")
        self.assertIn("research_state",row)
        self.assertGreaterEqual(row["research_layers"],2)
        self.assertIsInstance(row["research_blockers"],list)

    def test_structured_macro_metadata_reaches_home_row(self):
        macro_context={
            "currencies":{
                "EUR":{
                    "rates":{"score":40,"quality":90,"fresh":True},
                    "inflation":{"score":45,"quality":90,"fresh":True},
                    "growth":{"score":42,"quality":90,"fresh":True},
                },
                "USD":{
                    "rates":{"score":75,"quality":90,"fresh":True},
                    "inflation":{"score":68,"quality":90,"fresh":True},
                    "growth":{"score":60,"quality":90,"fresh":True},
                },
            }
        }
        row=home_rows_from_packs([_pack()],macro_context=macro_context)[0]
        self.assertEqual(row["macro_research_mode"],"structured")
        self.assertEqual(row["macro_research_direction"],"VENDA")
        self.assertGreater(row["macro_research_coverage"],40)
        self.assertEqual(row["action"],"COMPRA")

    def test_geopolitical_news_can_reach_research_layers_without_becoming_order(self):
        article={
            "title":"Geopolitical tensions escalate after attack and sanctions",
            "source":"Reuters","weighted_impact":-0.2,
            "recency_factor":1.0,"source_factor":1.0,"independence_factor":1.0,
        }
        news={"currencies":{"EUR":{"articles":[article]},"USD":{"articles":[article]}}}
        row=home_rows_from_packs([_pack()],news_state=news)[0]
        self.assertGreaterEqual(row["research_layers"],3)
        self.assertEqual(row["action"],"COMPRA")

    def test_structured_geopolitical_metadata_reaches_home_without_overriding_action(self):
        news={"geopolitical_events":[{
            "event_id":"GEO-RADAR",
            "title":"New sanctions and shipping disruption",
            "category":"sanctions",
            "source":"Verified wire",
            "quality":90,
            "severity":"high",
            "duration":"medium",
            "currency_impacts":{"EUR":-50,"USD":20},
        }]}
        row=home_rows_from_packs([_pack()],news_state=news)[0]
        self.assertEqual(row["geo_research_direction"],"VENDA")
        self.assertEqual(row["geo_research_severity"],"ALTO")
        self.assertGreater(row["geo_research_coverage"],0)
        self.assertTrue(row["geo_research_events"])
        self.assertIn("trade",row["geo_research_channels"])
        self.assertEqual(row["action"],"COMPRA")

    def test_adr_is_described_without_calling_it_probability(self):
        row=home_rows_from_packs([_pack()])[0]
        self.assertIn("ADR 63%",row["movement"])
        self.assertNotIn("probabilidade",row["movement"].casefold())


if __name__=="__main__":
    unittest.main()


class AtlasQuantHomeVoiceContextTests(unittest.TestCase):
    def test_home_row_preserves_advanced_voice_context(self):
        row=home_rows_from_packs([_pack()])[0]
        self.assertEqual(row["w1"],"🟢 altista")
        self.assertEqual(row["d1"],"🟢 altista")
        self.assertEqual(row["pd_zone"],"DISCOUNT")
        self.assertEqual(row["sweep_type"],"SSL")
        self.assertEqual(row["ict_read"],74)
        self.assertEqual(row["inst_read"],81)
        self.assertIn("H4 confirma compra",row["up"])
        self.assertIn("M15 ainda aguarda gatilho",row["soft_blocks"])