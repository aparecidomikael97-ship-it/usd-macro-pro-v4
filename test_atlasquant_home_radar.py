import unittest

from atlasquant_home_radar import (
    home_rows_from_packs,
    home_summary,
    voice_script_for_row,
)
from atlasquant_session_profiles import (
    extract_session_bucket,
    prioritize_rows_for_session,
    session_bucket_from_timestamp,
    session_profile_match,
    session_profile_summary,
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

    def test_session_timestamp_classification_is_dst_aware_in_new_york(self):
        self.assertEqual(session_bucket_from_timestamp("2026-09-20T01:00:00Z"),"ASIA")
        self.assertEqual(session_bucket_from_timestamp("2026-09-20T07:00:00Z"),"LONDON")
        self.assertEqual(session_bucket_from_timestamp("2026-09-20T13:00:00Z"),"NEW_YORK")
        self.assertEqual(session_bucket_from_timestamp("2026-09-20T18:00:00Z"),"AFTER_NEW_YORK")

    def test_radar_preserves_session_from_pack_and_profile_only_reorders(self):
        asia=_pack(pair="AUD/USD",priority=70)
        asia["active_session"]="Ásia"
        ny=_pack(pair="EUR/USD",priority=90)
        ny["active_session"]="Nova York"
        rows=home_rows_from_packs([ny,asia])
        prioritized=prioritize_rows_for_session(rows,"Noite/madrugada · Ásia + Londres")
        self.assertEqual(prioritized[0]["pair"],"AUD/USD")
        self.assertEqual(prioritized[0]["session_match"],"MATCH")
        self.assertEqual(prioritized[1]["session_match"],"OUTSIDE")
        self.assertEqual(len(prioritized),2)

    def test_unknown_session_is_not_hidden_or_fake_matched(self):
        rows=home_rows_from_packs([_pack()])
        self.assertEqual(extract_session_bucket(rows[0]),"UNKNOWN")
        prioritized=prioritize_rows_for_session(rows,"Dia · Nova York + continuidade")
        self.assertEqual(len(prioritized),1)
        self.assertEqual(prioritized[0]["session_match"],"UNKNOWN")
        summary=session_profile_summary(prioritized,"Dia · Nova York + continuidade")
        self.assertEqual(summary["unknown"],1)
        self.assertFalse(summary["real_orders_enabled"])

    def test_session_profile_does_not_change_trade_direction(self):
        rows=home_rows_from_packs([_pack(direction="🔴 VENDA")])
        before=rows[0]["action"]
        after=prioritize_rows_for_session(rows,"Noite/madrugada · Ásia + Londres")[0]
        self.assertEqual(before,"VENDA")
        self.assertEqual(after["action"],"VENDA")
        self.assertEqual(session_profile_match("NEW_YORK","Noite/madrugada · Ásia + Londres"),"OUTSIDE")

    def test_voice_explains_reason_risk_and_no_order(self):
        row=home_rows_from_packs([_pack()])[0]
        script=voice_script_for_row(row).casefold()
        self.assertIn("análise do eur/usd",script)
        self.assertIn("próximo passo",script)
        self.assertIn("sessão",script)
        self.assertIn("não é garantia",script)
        self.assertIn("nem ordem para corretora",script)

    def test_home_voice_reuses_fixed_neural_renderer(self):
        import inspect
        import atlasquant_home_radar as home
        source=inspect.getsource(home.render_browser_voice)
        self.assertIn("render_neural_voice_player",source)
        self.assertNotIn("browser_speech_html",source)
        self.assertNotIn("SpeechSynthesisUtterance",source)

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