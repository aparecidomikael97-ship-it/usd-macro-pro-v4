import unittest

from pair_intelligence_v110 import atlasquant_operational_card, atlasquant_basic_table


class AtlasQuantOperationalCardsTests(unittest.TestCase):
    def test_green_requires_executable_and_ready(self):
        row = atlasquant_operational_card({
            "pair":"EUR/USD","state":"🟢 EXECUTÁVEL","direction":"🟢 COMPRA EUR/USD",
            "executable":True,"priority":92,"quality":88,
            "data_ready":{"sufficient":True,"score":95},"m15":"🟢 CONFIRMADO","gate":"🟢"
        })
        self.assertEqual(row["traffic_light"], "GREEN")
        self.assertEqual(row["action"], "MOTOR EXECUTÁVEL")

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

    def test_basic_table_preserves_all_rows(self):
        packs=[
            {
                "pair":"EUR/USD","state":"🟡 AGUARDAR","direction":"🟢 COMPRA EUR/USD",
                "priority":80,"data_ready":{"sufficient":True,"score":90},
                "m15":"AGUARDAR","gate":"WAIT",
            },
            {
                "pair":"GBP/USD","state":"🔴 BLOQUEADO","direction":"⚪ AGUARDAR",
                "priority":60,"data_ready":{"sufficient":False,"score":40},
                "m15":"N/D","gate":"BLOCK",
            },
        ]
        table=atlasquant_basic_table(packs)
        self.assertEqual(len(table),2)
        self.assertEqual(list(table["Par"]),["EUR/USD","GBP/USD"])

    def test_basic_table_never_marks_insufficient_data_ready(self):
        table=atlasquant_basic_table([{
            "pair":"USD/JPY","state":"🟡 AGUARDAR","direction":"🔴 VENDA USD/JPY",
            "priority":70,"data_ready":{"sufficient":False,"score":55},
            "m15":"AGUARDAR","gate":"WAIT",
        }])
        self.assertEqual(table.iloc[0]["Pronto?"],"NÃO")


    def test_green_card_wording_does_not_claim_final_safety_permission(self):
        row=atlasquant_operational_card({
            "pair":"EUR/USD","state":"🟢 EXECUTÁVEL","direction":"🟢 COMPRA EUR/USD",
            "executable":True,"data_ready":{"sufficient":True,"score":95}
        })
        self.assertEqual(row["traffic_light"],"GREEN")
        self.assertEqual(row["action"],"MOTOR EXECUTÁVEL")
        self.assertNotEqual(row["action"],"ORDEM LIBERADA")



if __name__ == "__main__":
    unittest.main()
