import unittest

from atlasquant_aion_operations import new_task
from atlasquant_aion_secretary import executive_briefing


class AtlasQuantAionSecretaryTests(unittest.TestCase):
    def test_unconfirmed_external_sections_are_not_invented(self):
        brief=executive_briefing(
            system_context={"truth_state":"CONFIRMED","source_build":"abc","environment":"PRODUCTION"},
            market_context={"truth_state":"UNKNOWN","summary":"EURUSD compra"},
            clients_context={"truth_state":"UNKNOWN","new_clients":99},
            content_context={"truth_state":"UNKNOWN","waiting_approval":12},
        )
        self.assertEqual(brief["system"]["build"],"abc")
        self.assertEqual(brief["market"]["truth_state"],"UNKNOWN")
        self.assertEqual(brief["market"]["summary"],"")
        self.assertIsNone(brief["clients"]["new_clients"])
        self.assertIsNone(brief["content"]["waiting_approval"])

    def test_confirmed_sections_are_reported(self):
        task=new_task("Revisar interface",domain="development")
        brief=executive_briefing(
            tasks=[task],
            market_context={"truth_state":"CONFIRMED","summary":"Sem oportunidade liberada"},
            clients_context={"truth_state":"CONFIRMED","new_clients":2},
            content_context={"truth_state":"CONFIRMED","waiting_approval":3},
        )
        self.assertEqual(brief["tasks"]["active"],1)
        self.assertEqual(brief["market"]["summary"],"Sem oportunidade liberada")
        self.assertEqual(brief["clients"]["new_clients"],2)
        self.assertEqual(brief["content"]["waiting_approval"],3)
        self.assertFalse(brief["real_orders_enabled"])


if __name__=="__main__":
    unittest.main()
