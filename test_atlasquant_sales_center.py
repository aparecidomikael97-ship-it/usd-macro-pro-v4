import unittest

from atlasquant_sales_center import (
    commercial_readiness,
    onboarding_steps,
    sales_access_allowed,
)

class AtlasQuantSalesCenterTests(unittest.TestCase):
    def test_sales_and_admin_authenticated_sessions_are_allowed(self):
        sales={"role":"SALES","session":{"username":"sales.01","role":"SALES"}}
        admin={"role":"ADMIN","session":{"username":"admin.01","role":"ADMIN"}}
        user={"role":"USER","session":{"username":"user.01","role":"USER"}}
        self.assertTrue(sales_access_allowed(sales))
        self.assertTrue(sales_access_allowed(admin))
        self.assertFalse(sales_access_allowed(user))
        self.assertFalse(sales_access_allowed({"role":"SALES","session":None}))

    def test_commercial_readiness_never_claims_future_features_ready(self):
        status=commercial_readiness({"registry":{"TOTAL":7}})
        self.assertEqual(status["active_accounts"],7)
        self.assertFalse(status["academy_ready"])
        self.assertFalse(status["voice_ready"])
        self.assertFalse(status["brokers_guide_ready"])
        self.assertFalse(status["native_stores_ready"])
        self.assertFalse(status["payments_integrated"])
        self.assertFalse(status["broker_execution_enabled"])
        self.assertFalse(status["real_orders_enabled"])

    def test_corrupt_account_count_fails_closed(self):
        for bad in (-1,float("nan"),float("inf"),"bad",True):
            with self.subTest(bad=bad):
                status=commercial_readiness({"registry":{"TOTAL":bad}})
                self.assertEqual(status["active_accounts"],0)

    def test_onboarding_keeps_education_and_voice_planned(self):
        rows=onboarding_steps()
        by={row["Item"]:row for row in rows}
        self.assertEqual(by["Academy"]["Status"],"PLANEJADO")
        self.assertEqual(by["Assistente de voz"]["Status"],"PLANEJADO")
        self.assertEqual(by["Corretoras & plataformas"]["Status"],"PLANEJADO")

if __name__=="__main__":
    unittest.main()
