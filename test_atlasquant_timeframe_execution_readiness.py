import unittest

from atlasquant_timeframe_execution_readiness import (
    SUPPORTED_TIMEFRAMES,
    PAPER_GATE_SUPPORTED,
    execution_readiness_for_pair,
    execution_readiness_summary,
)


def bar(ts="2026-09-21T12:00:00Z"):
    return {"datetime":ts,"open":1.0,"high":1.1,"low":0.9,"close":1.0}


class TimeframeExecutionReadinessTests(unittest.TestCase):
    def setUp(self):
        self.scanner={"resultados":{"EUR/USD":{"tecnico":{"cache_v110":{
            "m15":[bar()],"h1":[bar()],"h4":[bar()],
        }}}}}
        self.research={"pairs":{"EUR/USD":{
            "M30":[bar()],"D1":[bar()],"W1":[bar()],
        }}}

    def test_all_requested_timeframes_are_visible(self):
        self.assertEqual(SUPPORTED_TIMEFRAMES,("M15","M30","H1","H4","D1","W1"))

    def test_data_availability_alone_never_enables_unsupported_paper_timeframe(self):
        pack=execution_readiness_for_pair("EUR/USD",self.scanner,self.research)
        self.assertTrue(pack["timeframes"]["M30"]["exact_execution_data"])
        self.assertFalse(pack["timeframes"]["M30"]["can_execute_paper"])
        self.assertFalse(pack["timeframes"]["H4"]["can_execute_paper"])
        self.assertFalse(pack["timeframes"]["D1"]["can_execute_paper"])
        self.assertFalse(pack["timeframes"]["W1"]["can_execute_paper"])
        self.assertIn("CONTRATO_DE_GATILHO_AINDA_NAO_IMPLEMENTADO",pack["timeframes"]["W1"]["reasons"])

    def test_current_paper_support_remains_m15_h1_only(self):
        self.assertEqual(PAPER_GATE_SUPPORTED,{"M15","H1"})
        pack=execution_readiness_for_pair("EUR/USD",self.scanner,self.research)
        self.assertTrue(pack["timeframes"]["M15"]["can_execute_paper"])
        self.assertTrue(pack["timeframes"]["H1"]["can_execute_paper"])
        self.assertEqual(pack["timeframes"]["H1"]["required_context"],["H4","D1"])

    def test_missing_exact_frame_fails_closed(self):
        pack=execution_readiness_for_pair("EUR/USD",{"resultados":{}},{"pairs":{}})
        for tf in SUPPORTED_TIMEFRAMES:
            self.assertFalse(pack["timeframes"][tf]["can_execute_paper"])
            self.assertIn("SEM_CANDLES_EXATOS",pack["timeframes"][tf]["reasons"])

    def test_summary_is_observational_and_never_enables_orders(self):
        summary=execution_readiness_summary(self.scanner,self.research)
        self.assertEqual(summary["by_timeframe"]["M30"]["pairs_with_exact_data"],1)
        self.assertEqual(summary["by_timeframe"]["M30"]["pairs_paper_ready"],0)
        self.assertTrue(summary["safety"]["alignment_required"])
        self.assertTrue(summary["safety"]["research_only_for_unsupported_timeframes"])
        self.assertFalse(summary["safety"]["automatic_execution"])
        self.assertFalse(summary["safety"]["real_orders_enabled"])


if __name__=="__main__":
    unittest.main()
