import unittest

from atlasquant_aion_business import (
    approve_product,
    business_metrics_digest,
    business_metrics_views,
    business_summary,
    coverage_snapshot,
    customer_economics,
    funnel_snapshot,
    marketplace_preflight,
    mark_listing_live_from_evidence,
    new_business_metrics,
    new_product_candidate,
    normalize_products,
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

    def test_funnel_never_fills_missing_data_or_starts_campaign(self):
        empty=funnel_snapshot()
        self.assertEqual(empty["state"],"NOT_CONFIGURED")
        self.assertIsNone(empty["order_rate_pct"])
        self.assertFalse(empty["automatic_campaign"])
        confirmed=funnel_snapshot(visits=1000,leads=100,checkouts=25,orders=10,source="analytics export")
        self.assertEqual(confirmed["truth_state"],"CONFIRMED")
        self.assertEqual(confirmed["order_rate_pct"],1.0)
        invalid=funnel_snapshot(visits=10,leads=20,checkouts=2,orders=1,source="x")
        self.assertEqual(invalid["truth_state"],"UNKNOWN")

    def test_cac_and_ltv_require_real_inputs_and_source(self):
        empty=customer_economics()
        self.assertIsNone(empty["cac"])
        self.assertIsNone(empty["ltv"])
        self.assertEqual(empty["state"],"NOT_CONFIGURED")
        result=customer_economics(
            marketing_cost=100,acquired_customers=10,
            gross_profit_per_order=20,average_orders_per_customer=3,
            source="campaign export",
        )
        self.assertEqual(result["cac"],10.0)
        self.assertEqual(result["ltv"],60.0)
        self.assertEqual(result["ltv_cac_ratio"],6.0)
        self.assertFalse(result["paid_action"])

    def test_business_metrics_keep_financial_concepts_separate_and_provenance_bound(self):
        empty=business_metrics_views({})
        self.assertEqual(empty["metrics"]["state"],"NOT_CONFIGURED")
        self.assertIsNone(empty["finance"]["revenue"])
        self.assertEqual(empty["funnel"]["state"],"NOT_CONFIGURED")

        record=new_business_metrics(
            source="marketplace export 2026-09",
            truth_state="CONFIRMED",
            recorded_by="admin.test",
            visits=1000,
            leads=100,
            checkouts=25,
            orders=10,
            marketing_cost=200,
            acquired_customers=10,
            gross_profit_per_order=40,
            average_orders_per_customer=2,
            revenue=5000,
            costs=3200,
            gross_profit=1800,
            net_profit=1200,
            available_cash=700,
        )
        views=business_metrics_views(record)
        self.assertEqual(views["metrics"]["state"],"READY")
        self.assertEqual(views["funnel"]["order_rate_pct"],1.0)
        self.assertEqual(views["customers"]["cac"],20.0)
        self.assertEqual(views["customers"]["ltv"],80.0)
        self.assertEqual(views["finance"]["revenue"],5000.0)
        self.assertEqual(views["finance"]["gross_profit"],1800.0)
        self.assertEqual(views["finance"]["net_profit"],1200.0)
        self.assertEqual(views["finance"]["available_cash"],700.0)
        self.assertNotEqual(views["finance"]["revenue"],views["finance"]["net_profit"])
        self.assertFalse(record["automatic_publish"])
        self.assertFalse(record["automatic_payment"])
        self.assertFalse(record["automatic_investment"])
        self.assertEqual(
            business_metrics_digest(record),
            business_metrics_digest(record),
        )

        unconfirmed=new_business_metrics(
            source="anotação manual",
            truth_state="HYPOTHESIS",
            visits=100,
            leads=10,
            checkouts=5,
            orders=2,
        )
        unconfirmed_views=business_metrics_views(unconfirmed)
        self.assertEqual(unconfirmed_views["metrics"]["state"],"UNCONFIRMED")
        self.assertEqual(unconfirmed_views["funnel"]["state"],"NOT_CONFIGURED")

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

    def test_product_generator_is_not_consumed_past_normalization_bound(self):
        from atlasquant_aion_business import MAX_PRODUCTS

        consumed={"count":0}
        def rows():
            for index in range(MAX_PRODUCTS*2+1):
                if index>=MAX_PRODUCTS*2:
                    raise AssertionError("product iterable consumed past bound")
                consumed["count"]+=1
                yield {}

        normalized=normalize_products(rows())
        self.assertEqual(normalized,[])
        self.assertEqual(consumed["count"],MAX_PRODUCTS*2)

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
