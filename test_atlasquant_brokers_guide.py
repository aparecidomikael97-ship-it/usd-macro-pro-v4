import unittest
from atlasquant_brokers_guide import brokers_guide_catalog, brokers_guide_minimum_ready

class BrokersGuideTests(unittest.TestCase):
    def test_minimum_guide_is_ready(self):
        self.assertTrue(brokers_guide_minimum_ready())
        self.assertEqual({x["id"] for x in brokers_guide_catalog()},
                         {"difference","compatibility","paper","credentials","live"})

    def test_guide_does_not_claim_live_connection(self):
        text=" ".join(i for s in brokers_guide_catalog() for i in s["items"]).casefold()
        self.assertIn("não representa conexão ativa",text)
        self.assertIn("trading real permanece desativado",text)
        self.assertIn("resultados simulados não garantem",text)

    def test_security_guidance_protects_credentials(self):
        text=" ".join(i for s in brokers_guide_catalog() for i in s["items"]).casefold()
        self.assertIn("nunca cole senha",text)
        self.assertIn("armazenamento de secrets",text)
        self.assertIn("permissões mínimas",text)

if __name__=="__main__":
    unittest.main()
