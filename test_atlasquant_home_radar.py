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

    def test_adr_is_described_without_calling_it_probability(self):
        row=home_rows_from_packs([_pack()])[0]
        self.assertIn("ADR 63%",row["movement"])
        self.assertNotIn("probabilidade",row["movement"].casefold())


if __name__=="__main__":
    unittest.main()
