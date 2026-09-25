import unittest

from atlasquant_operational_state import (
    OPERATIONAL_SPINE_CSS,
    normalize_bias,
    normalize_freshness,
    normalize_operational_state,
    operational_presentation,
    operational_strip_html,
)


class AtlasQuantOperationalStateTests(unittest.TestCase):
    def test_bias_is_descriptive_only(self):
        self.assertEqual(normalize_bias("COMPRA EUR/USD"),"COMPRA")
        self.assertEqual(normalize_bias("SELL GBP/USD"),"VENDA")
        self.assertEqual(normalize_bias("sem lado"),"NEUTRO")

    def test_unknown_freshness_fails_closed(self):
        fresh=normalize_freshness()
        self.assertEqual(fresh["code"],"UNKNOWN")
        self.assertTrue(fresh["requires_revalidation"])
        self.assertIn("NÃO CONFIRMADO",fresh["label"])

    def test_current_freshness_requires_explicit_current_evidence(self):
        fresh=normalize_freshness(
            temporal_code="CURRENT",
            reference_display="24/09/2026 21:00 UTC",
        )
        self.assertEqual(fresh["label"],"ATUAL")
        self.assertFalse(fresh["requires_revalidation"])

    def test_descriptive_executable_state_without_authorization_stays_unauthorized(self):
        state=normalize_operational_state("🟢 EXECUTÁVEL",authorized=False)
        self.assertEqual(state["state"],"CONTEXTO ALINHADO")
        self.assertEqual(state["authorization"],"NÃO AUTORIZADA")
        self.assertFalse(state["authorized"])

    def test_authorization_is_downgraded_when_freshness_is_not_current(self):
        model=operational_presentation(
            pair="EUR/USD",
            bias="COMPRA EUR/USD",
            state="🟢 EXECUTÁVEL",
            quality=88,
            data_score=91,
            temporal_code="EXPIRED",
            reference_display="24/09/2026 18:00 UTC",
            authorized=True,
            evidence_source="teste",
        )
        self.assertFalse(model["authorized"])
        self.assertEqual(model["authorization"],"NÃO AUTORIZADA")
        self.assertEqual(model["state"],"REVALIDAR")
        self.assertTrue(model["requires_revalidation"])
        self.assertFalse(model["real_orders_enabled"])
        self.assertFalse(model["automatic_execution"])

    def test_current_explicit_authorization_can_be_presentationally_authorized(self):
        model=operational_presentation(
            pair="USD/CHF",
            bias="COMPRA",
            state="🟢 EXECUTÁVEL",
            quality=90,
            data_score=92,
            temporal_code="CURRENT",
            reference_display="24/09/2026 21:00 UTC",
            authorized=True,
            evidence_source="Painel Mestre",
        )
        self.assertTrue(model["authorized"])
        self.assertEqual(model["authorization"],"AUTORIZADA PELO ESTADO ATUAL")
        self.assertFalse(model["real_orders_enabled"])

    def test_unknown_numeric_values_remain_nd_instead_of_fake_zero(self):
        model=operational_presentation(
            pair="EUR/USD",
            bias="NEUTRO",
            state="AGUARDAR",
            quality=None,
            data_score=None,
        )
        self.assertIsNone(model["quality"])
        self.assertIsNone(model["data_score"])
        html=operational_strip_html(model)
        self.assertGreaterEqual(html.count("N/D"),2)

    def test_html_escapes_external_text_and_is_mobile_responsive(self):
        model=operational_presentation(
            pair="<script>EUR/USD</script>",
            state="AGUARDAR",
            evidence_source="<b>fonte</b>",
        )
        html=operational_strip_html(model)
        self.assertNotIn("<script>",html)
        self.assertNotIn("<b>fonte</b>",html)
        self.assertIn("&lt;script&gt;",html)
        self.assertIn("@media(max-width:760px)",OPERATIONAL_SPINE_CSS)
        self.assertIn("@media(max-width:430px)",OPERATIONAL_SPINE_CSS)
        self.assertIn("grid-template-columns:1fr",OPERATIONAL_SPINE_CSS)


if __name__=="__main__":
    unittest.main()
