import unittest
from pathlib import Path

from atlasquant_sales_visibility import sales_menu_policy


class SalesVisibilityTests(unittest.TestCase):
    def test_default_preserves_current_visible_locked_user_experience(self):
        policy = sales_menu_policy({"role": "USER"})
        self.assertTrue(policy["visible"])
        self.assertFalse(policy["authorized"])
        self.assertFalse(policy["authorization_changed"])

    def test_hide_policy_changes_visibility_not_authorization(self):
        policy = sales_menu_policy({"role": "USER"}, "HIDE_FROM_USER")
        self.assertFalse(policy["visible"])
        self.assertFalse(policy["authorized"])
        for role in ("SALES", "ADMIN"):
            allowed = sales_menu_policy({"role": role}, "HIDE_FROM_USER")
            self.assertTrue(allowed["visible"])
            self.assertTrue(allowed["authorized"])

    def test_unknown_policy_falls_back_to_existing_behavior(self):
        self.assertEqual(sales_menu_policy({"role": "USER"}, "x")["policy"], "VISIBLE_LOCKED")

    def test_entrypoint_uses_policy_but_preserves_page_authorization(self):
        src = Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertIn("ATLASQUANT_SALES_MENU_POLICY", src)
        self.assertIn("VISIBLE_LOCKED", src)
        self.assertIn('item != "💼 Vendas"', src)
        sales = Path("atlasquant_sales_center.py").read_text(encoding="utf-8")
        self.assertIn("Área comercial restrita aos perfis SALES e ADMIN autenticados.", sales)


if __name__ == "__main__":
    unittest.main()
