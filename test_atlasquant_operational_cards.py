import unittest

from pair_intelligence_v110 import atlasquant_operational_card


class AtlasQuantOperationalCardsTests(unittest.TestCase):
    def test_green_requires_executable_and_ready(self):
        row = atlasquant_operational_card({
            "pair":"EUR/USD","state":"🟢 EXECUTÁVEL","direction":"🟢 COMPRA EUR/USD",
            "executable":True,"priority":92,"quality":88,
            "data_ready":{"sufficient":True,"score":95},"m15":"🟢 CONFIRMADO","gate":"🟢"
        })
        self.assertEqual(row["traffic_light"], "GREEN")
        self.assertEqual(row["action"], "SETUP EXECUTÁVEL")

    def test_not_ready_is_red_even_with_positive_state(self):
        row = atlasquant_operational_card({
            "pair":"GBP/USD","state":"🟢 EXECUTÁVEL","direction":"🟢 COMPRA GBP/USD",
            "executable":True,"data_ready":{"sufficient":False,"score":40}
        })
        self.assertEqual(row["traffic_light"], "RED")
        self.assertEqual(row["action"], "NÃO OPERAR")

    def test_wait_is_yellow(self):
        row = atlasquant_operational_card({
            "pair":"USD/JPY","state":"🟡 AGUARDAR GATILHO","direction":"🔴 VENDA USD/JPY",
            "executable":False,"data_ready":{"sufficient":True,"score":90}
        })
        self.assertEqual(row["traffic_light"], "YELLOW")
        self.assertEqual(row["action"], "AGUARDAR CONFIRMAÇÃO")

    def test_hard_block_is_red(self):
        row = atlasquant_operational_card({
            "pair":"USD/CAD","state":"🔴 BLOQUEADO","direction":"⚪ AGUARDAR",
            "executable":False,"data_ready":{"sufficient":True,"score":90}
        })
        self.assertEqual(row["traffic_light"], "RED")


if __name__ == "__main__":
    unittest.main()
