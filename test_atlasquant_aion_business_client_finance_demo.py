import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_client_finance_demo import (
    client_economics,
    normalize_client_finance,
    portfolio_summary,
    pricing_review,
)


def _row(**updates):
    data = {
        "company_name": "Clínica Horizonte Demo",
        "package_label": "AION Business Completo",
        "implementation_revenue": 2500,
        "monthly_revenue": 1800,
        "product_cost": 0,
        "ai_cost": 180,
        "integration_cost": 120,
        "support_cost": 250,
        "media_cost": 0,
        "tool_cost": 90,
        "refunds": 0,
        "tax_estimate": 180,
        "other_costs": 30,
        "payment_state": "CURRENT",
        "monthly_requests": 6000,
        "request_quota": 10000,
        "support_hours": 4,
        "support_hour_quota": 8,
    }
    data.update(updates)
    return data


class BusinessClientFinanceDemoTests(unittest.TestCase):
    def test_finance_model_never_confuses_revenue_with_profit(self):
        result = client_economics(_row())
        eco = result["economics"]
        self.assertEqual(result["state"], "CALCULATED_DEMO")
        self.assertEqual(eco["monthly_revenue"], 1800.0)
        self.assertGreater(eco["total_monthly_costs"], 0)
        self.assertEqual(
            eco["monthly_contribution"],
            round(eco["monthly_revenue"] - eco["total_monthly_costs"], 2),
        )
        self.assertNotEqual(eco["monthly_revenue"], eco["monthly_contribution"])
        self.assertEqual(eco["available_for_reinvestment_state"], "NOT_CALCULATED_HERE")
        self.assertIsNone(eco["available_for_reinvestment"])
        self.assertFalse(result["real_financial_record"])
        self.assertFalse(result["invoice_created"])
        self.assertFalse(result["payment_collected"])
        self.assertFalse(result["money_moved"])
        self.assertFalse(result["executes_action"])

    def test_capacity_watch_and_limit_are_derived_without_side_effects(self):
        watch = client_economics(_row(monthly_requests=8500))
        self.assertEqual(watch["capacity"]["state"], "WATCH")
        self.assertIn("CAPACIDADE_PROXIMA_DO_LIMITE", watch["warnings"])
        limit = client_economics(_row(monthly_requests=12000))
        self.assertEqual(limit["capacity"]["state"], "AT_LIMIT")
        self.assertIn("CAPACIDADE_NO_LIMITE", limit["warnings"])

    def test_negative_margin_is_visible_and_never_auto_changes_price(self):
        result = client_economics(_row(monthly_revenue=400, ai_cost=300, support_cost=300))
        self.assertEqual(result["economics"]["profitability_state"], "NEGATIVE")
        self.assertIn("CUSTO_SUPERA_RECEITA", result["warnings"])
        review = pricing_review(result)
        self.assertEqual(review["state"], "REVIEW_REQUIRED")
        self.assertFalse(review["automatic_price_change"])
        self.assertFalse(review["automatic_charge"])
        self.assertTrue(review["requires_human_review"])
        self.assertFalse(review["executes_action"])

    def test_overdue_is_demo_status_only(self):
        result = client_economics(_row(payment_state="OVERDUE_DEMO"))
        self.assertIn("INADIMPLENCIA_DEMO", result["warnings"])
        self.assertFalse(result["payment_collected"])
        self.assertFalse(result["money_moved"])

    def test_missing_revenue_fails_closed(self):
        result = client_economics(_row(monthly_revenue=None))
        self.assertEqual(result["state"], "INCOMPLETE")
        self.assertEqual(result["economics"], {})
        self.assertFalse(result["executes_action"])

    def test_portfolio_summary_aggregates_demo_only(self):
        rows = [
            client_economics(_row()),
            client_economics(_row(company_name="Imobiliária Demo", monthly_revenue=2200)),
        ]
        summary = portfolio_summary(rows)
        self.assertEqual(summary["client_count"], 2)
        self.assertGreater(summary["monthly_revenue"], 0)
        self.assertGreater(summary["monthly_costs"], 0)
        self.assertFalse(summary["real_financial_record"])
        self.assertFalse(summary["moves_money"])
        self.assertFalse(summary["executes_action"])

    def test_normalizer_rejects_invalid_money(self):
        row = normalize_client_finance(_row(ai_cost=-1, tax_estimate="x"))
        self.assertIsNone(row["ai_cost"])
        self.assertIsNone(row["tax_estimate"])
        self.assertEqual(row["truth_state"], "DEMO_USER_INPUT")
        self.assertFalse(row["real_financial_record"])

    def test_module_has_no_external_io_or_provider_imports(self):
        source = Path("atlasquant_aion_business_client_finance_demo.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for banned in ("requests", "urllib", "httpx", "socket", "subprocess", "openai", "streamlit"):
            self.assertNotIn(banned, imported)


if __name__ == "__main__":
    unittest.main()
