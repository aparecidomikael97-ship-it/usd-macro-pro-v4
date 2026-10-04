import unittest

from atlasquant_master_market import build_executive_market_snapshot


class ExecutiveMasterMarketTests(unittest.TestCase):
    def test_snapshot_keeps_28_forex_pairs_and_separate_markets(self):
        snapshot = build_executive_market_snapshot()
        self.assertEqual(snapshot["forex"]["monitored"], 28)
        self.assertEqual(snapshot["forex"]["top"], [])
        self.assertEqual(len({row["pair"] for row in snapshot["forex"]["population"]}), 28)
        self.assertTrue(all(row["asset_class"] == "INDEX" for row in snapshot["indices"]))
        self.assertTrue(all(row["asset_class"] == "CRYPTO" for row in snapshot["cryptos"]))
        self.assertEqual(snapshot["dxy"]["symbol"], "DXY")

    def test_absent_domains_and_dxy_remain_unconfirmed(self):
        snapshot = build_executive_market_snapshot()
        domains = {row["Domínio"]: row for row in snapshot["domains"]}
        self.assertEqual(domains["Geopolítica"]["Estado"], "SEM DADOS")
        self.assertEqual(domains["Sentimento"]["Fonte"], "FONTE AUSENTE")
        self.assertEqual(snapshot["dxy"]["state"], "SEM LEITURA AO VIVO")
        self.assertIsNone(snapshot["dxy"]["score"])
        self.assertEqual(snapshot["event"]["pre_news"], "BLOQUEADO")

    def test_only_current_explicit_authorization_is_released_for_study(self):
        rows = [
            {
                "Par": "EUR/USD",
                "Estado": "🟢 EXECUTÁVEL",
                "Autorização": "✅ AUTORIZADA PELO ESTADO ATUAL",
                "Status temporal": "ATUAL",
            },
            {
                "Par": "GBP/USD",
                "Estado": "🟢 EXECUTÁVEL",
                "Autorização": "✅ AUTORIZADA PELO ESTADO ATUAL",
                "Status temporal": "EXPIRADA — REVALIDAR",
            },
            {
                "Par": "USD/JPY",
                "Estado": "🔴 CONFLITO",
                "Autorização": "⛔ NÃO AUTORIZADA",
                "Status temporal": "ATUAL",
            },
        ]
        snapshot = build_executive_market_snapshot(master_rows=rows)
        released = snapshot["opportunities"]["released_for_study"]
        blocked = snapshot["opportunities"]["blocked"]
        self.assertEqual([row["Par"] for row in released], ["EUR/USD"])
        self.assertEqual({row["Par"] for row in blocked}, {"GBP/USD", "USD/JPY"})
        self.assertEqual(snapshot["alignment"]["divergent_pairs"], ["USD/JPY"])
        self.assertFalse(snapshot["real_orders_enabled"])
        self.assertFalse(snapshot["automatic_execution"])

    def test_event_requires_provenance_and_source_fallback_is_visible(self):
        snapshot = build_executive_market_snapshot(
            macro_context={
                "trend": 61,
                "event": {
                    "disponivel": True,
                    "nome": "CPI",
                    "data": "2026-10-01",
                },
            },
            source_status={
                "FRED": "✅ Dados válidos",
                "News": "⚠️ Fallback parcial",
                "Flow": {"status": "offline"},
            },
        )
        self.assertEqual(snapshot["event"]["state"], "CONFIRMADO")
        self.assertEqual(snapshot["event"]["title"], "CPI")
        self.assertEqual(snapshot["event"]["pre_news"], "REVISAR")
        self.assertEqual(snapshot["fallback_count"], 1)
        self.assertEqual(snapshot["unavailable_source_count"], 1)
        states = {row["Fonte"]: row["Estado"] for row in snapshot["sources"]}
        self.assertEqual(states["FRED"], "CONFIRMADA")
        self.assertEqual(states["News"], "FALLBACK")


if __name__ == "__main__":
    unittest.main()
