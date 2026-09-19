import unittest

from atlasquant_sales_center import (
    commercial_readiness,
    onboarding_steps,
    sales_access_allowed,
    sales_launch_summary,
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


    def test_mismatched_sales_session_role_is_denied(self):
        forged={"role":"SALES","session":{"username":"user.01","role":"USER"}}
        empty_name={"role":"SALES","session":{"username":"","role":"SALES"}}
        self.assertFalse(sales_access_allowed(forged))
        self.assertFalse(sales_access_allowed(empty_name))


    def test_commercial_readiness_distinguishes_internal_guide_from_external_features(self):
        status=commercial_readiness({"registry":{"TOTAL":7}})
        self.assertEqual(status["active_accounts"],7)
        self.assertTrue(status["academy_text_ready"])
        self.assertTrue(status["academy_video_scripts_ready"])
        self.assertTrue(status["academy_video_scripts_ready"])
        self.assertFalse(status["academy_ready"])
        self.assertTrue(status["voice_contract_ready"])
        self.assertFalse(status["voice_ready"])
        self.assertTrue(status["brokers_guide_ready"])
        self.assertFalse(status["native_stores_ready"])
        self.assertFalse(status["payments_integrated"])
        self.assertFalse(status["broker_execution_enabled"])
        self.assertFalse(status["real_orders_enabled"])
        self.assertTrue(status["sales_role_isolation_verified"])
        self.assertTrue(status["account_revocation_verified"])
        self.assertTrue(status["account_admin_verified"])
        self.assertTrue(status["audit_manifest_verified"])

    def test_corrupt_account_count_fails_closed(self):
        for bad in (-1,float("nan"),float("inf"),"bad",True):
            with self.subTest(bad=bad):
                status=commercial_readiness({"registry":{"TOTAL":bad}})
                self.assertEqual(status["active_accounts"],0)

    def test_onboarding_distinguishes_text_academy_from_pending_videos(self):
        rows=onboarding_steps()
        by={row["Item"]:row for row in rows}
        self.assertEqual(by["Academy"]["Status"],"TEXTO + ROTEIROS PRONTOS · VÍDEOS PENDENTES")
        self.assertEqual(by["Assistente de voz"]["Status"],"INFRA PRONTA · PROVEDOR PENDENTE")
        self.assertEqual(by["Corretoras & plataformas"]["Status"],"GUIA INFORMATIVO PRONTO")


    def test_text_academy_does_not_fake_full_commercial_academy(self):
        status=commercial_readiness({"registry":{"TOTAL":1}})
        self.assertTrue(status["academy_text_ready"])
        self.assertFalse(status["academy_ready"])
        self.assertTrue(status["voice_contract_ready"])
        self.assertFalse(status["voice_ready"])



    def test_sales_launch_summary_is_conservative(self):
        self.assertEqual(sales_launch_summary({})["label"],"SEGURANÇA A REVISAR")
        secure={"sales_role_isolation_verified":True,"account_revocation_verified":True,"account_admin_verified":True,"audit_manifest_verified":True}
        self.assertEqual(sales_launch_summary(secure)["label"],"DISTRIBUIÇÃO BLOQUEADA")
        self.assertEqual(sales_launch_summary({**secure,"pwa_ready":True})["label"],"PRÉ-LANÇAMENTO")
        self.assertEqual(sales_launch_summary({**secure,"pwa_ready":True,"payments_integrated":True,"academy_ready":True})["label"],"REVISÃO COMERCIAL")



    def test_commercial_security_evidence_is_code_verified_not_login_inferred(self):
        status=commercial_readiness({"role":"ADMIN","session":{"username":"admin.01","role":"ADMIN"},"registry":{"TOTAL":1}})
        self.assertTrue(status["sales_role_isolation_verified"])
        self.assertTrue(status["account_revocation_verified"])
        self.assertTrue(status["account_admin_verified"])
        self.assertTrue(status["audit_manifest_verified"])
        self.assertFalse(status["payments_integrated"])
        self.assertFalse(status["academy_ready"])



    def test_internal_security_collector_never_marks_external_launch_items_ready(self):
        from atlasquant_commercial_security_evidence import collect_commercial_security_evidence
        evidence=collect_commercial_security_evidence()
        self.assertTrue(evidence["sales_role_isolated_ok"])
        self.assertTrue(evidence["account_revocation_ok"])
        self.assertTrue(evidence["account_admin_ok"])
        self.assertTrue(evidence["audit_manifest_ok"])
        self.assertFalse(evidence["external_legal_verified"])
        self.assertFalse(evidence["external_data_licensing_verified"])
        self.assertFalse(evidence["external_billing_verified"])



    def test_sales_checklist_surfaces_internal_security_controls(self):
        from pathlib import Path
        src=Path("atlasquant_sales_center.py").read_text(encoding="utf-8")
        self.assertIn("Isolamento SALES",src)
        self.assertIn("Revogação de conta/sessão",src)
        self.assertIn("Auditoria administrativa",src)
        self.assertNotIn("private_access_ok=True",src)
        self.assertNotIn("account_admin_ok=True",src)


if __name__=="__main__":
    unittest.main()
