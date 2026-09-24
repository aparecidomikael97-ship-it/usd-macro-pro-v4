import unittest

from atlasquant_aion_business import (
    approve_product,
    business_summary,
    coverage_snapshot,
    marketplace_preflight,
    mark_listing_live_from_evidence,
    new_product_candidate,
    trend_assessment,
    unit_economics,
    upsert_product,
)


class AtlasQuantAionBusinessTests(unittest.TestCase):
    def setUp(self):
        self.admin={"role":"ADMIN","username":"admin.test"}

    def test_unit_economics_are_deterministic(self):
        econ=unit_economics(
            sale_price=100,
            unit_cost=40,
            platform_fee_pct=10,
            shipping_cost=8,
            tax_pct=5,
            other_cost=2,
        )
        self.assertEqual(econ["total_cost"],65.0)
        self.assertEqual(econ["net_profit"],35.0)
        self.assertEqual(econ["net_margin_pct"],35.0)
        self.assertTrue(econ["profitable"])

    def test_unknown_research_cannot_be_called_trending(self):
        product=new_product_candidate(
            "Produto X",
            evidence_truth="UNKNOWN",
            trend_note="parece vender bem",
        )
        trend=trend_assessment(product)
        self.assertFalse(trend["can_call_trending"])
        self.assertIn("não confirmada",trend["message"])

    def test_confirmed_source_can_support_trend_claim(self):
        product=new_product_candidate(
            "Produto X",
            evidence_truth="CONFIRMED",
            evidence_source="Fonte oficial",
            trend_note="Demanda cresceu no período observado.",
        )
        trend=trend_assessment(product)
        self.assertTrue(trend["can_call_trending"])
        self.assertFalse(trend["can_call_bestseller"])

    def test_marketplace_preflight_never_executes_listing(self):
        product=approve_product(
            new_product_candidate("Produto",sale_price=100,unit_cost=50),
            self.admin,
        )
        blocked=marketplace_preflight(
            product,self.admin,
            feature_flags={"marketplace_publish":False},
            approved=True,
        )
        self.assertFalse(blocked["allowed"])
        ready=marketplace_preflight(
            product,self.admin,
            feature_flags={"marketplace_publish":True},
            approved=True,
        )
        self.assertTrue(ready["allowed"])
        self.assertFalse(ready["executes_publish"])

    def test_live_listing_requires_connector_evidence(self):
        product=approve_product(
            new_product_candidate("Produto",sale_price=100,unit_cost=50),
            self.admin,
        )
        with self.assertRaises(ValueError):
            mark_listing_live_from_evidence(product,{"confirmed":True,"source":"ml"})
        live=mark_listing_live_from_evidence(
            product,
            {
                "confirmed":True,
                "source":"marketplace_connector",
                "external_id":"MLB123",
            },
        )
        self.assertTrue(live["listing"]["live"])
        self.assertEqual(live["status"],"LIVE")

    def test_coverage_snapshot_uses_admin_input_label(self):
        snap=coverage_snapshot(200,150)
        self.assertEqual(snap["coverage_pct"],75.0)
        self.assertEqual(snap["remaining_to_cover_usd"],50.0)
        self.assertEqual(snap["source"],"ADMIN_INPUT")

    def test_summary_and_upsert(self):
        a=new_product_candidate("A",sale_price=100,unit_cost=50,created_at="2026-09-23T20:00:00Z")
        b=new_product_candidate("B",sale_price=50,unit_cost=70,created_at="2026-09-23T20:01:00Z")
        rows=upsert_product([],a)
        rows=upsert_product(rows,b)
        summary=business_summary(rows)
        self.assertEqual(summary["total"],2)
        self.assertEqual(summary["positive_margin_candidates"],1)


if __name__=="__main__":
    unittest.main()
