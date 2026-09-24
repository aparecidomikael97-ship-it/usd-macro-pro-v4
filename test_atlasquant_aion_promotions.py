import unittest
from datetime import datetime, timezone

from atlasquant_aion_promotions import (
    activation_preflight,
    approve_campaign,
    campaign_availability,
    code_digest,
    confirm_redemption_from_provider,
    generate_promo_code,
    mark_active_from_provider_evidence,
    new_campaign,
    new_redemption_request,
    promotions_summary,
    upsert_campaign,
)


class AtlasQuantAionPromotionsTests(unittest.TestCase):
    def setUp(self):
        self.admin={"role":"ADMIN","username":"admin.test"}

    def test_code_generation_is_public_but_checkpoint_only_needs_digest(self):
        code=generate_promo_code("AQ",10)
        self.assertTrue(code.startswith("AQ-"))
        self.assertGreaterEqual(len(code),9)
        self.assertEqual(len(code_digest(code)),64)

    def test_new_campaign_returns_plaintext_once_and_does_not_store_it(self):
        campaign,code=new_campaign(
            "Semana grátis",
            benefit_type="TRIAL_DAYS",
            benefit_value=7,
            max_uses=25,
        )
        self.assertIn("AQ-",code)
        self.assertFalse(campaign["code"]["plaintext_stored"])
        self.assertNotIn(code,str(campaign))
        self.assertEqual(campaign["benefit"]["value"],7)
        self.assertEqual(campaign["status"],"DRAFT")

    def test_activation_requires_admin_approval_flag_and_guardian_approval(self):
        campaign,_=new_campaign("Teste")
        blocked=activation_preflight(
            campaign,self.admin,
            feature_flags={"promotion_activation":True},
            approved=True,
        )
        self.assertFalse(blocked["allowed"])
        approved=approve_campaign(campaign,self.admin)
        no_click=activation_preflight(
            approved,self.admin,
            feature_flags={"promotion_activation":True},
            approved=False,
        )
        self.assertFalse(no_click["allowed"])
        ready=activation_preflight(
            approved,self.admin,
            feature_flags={"promotion_activation":True},
            approved=True,
        )
        self.assertTrue(ready["allowed"])
        self.assertFalse(ready["executes_activation"])

    def test_active_status_requires_provider_evidence(self):
        campaign,_=new_campaign("Teste")
        approved=approve_campaign(campaign,self.admin)
        with self.assertRaises(ValueError):
            mark_active_from_provider_evidence(
                approved,
                {"confirmed":True,"provider":"billing"},
            )
        active=mark_active_from_provider_evidence(
            approved,
            {
                "confirmed":True,
                "provider":"subscription_registry",
                "external_id":"promo-123",
            },
        )
        self.assertEqual(active["status"],"ACTIVE")
        self.assertTrue(active["provider_activation"]["confirmed"])

    def test_redemption_preflight_never_grants_entitlement_by_itself(self):
        campaign,code=new_campaign("Teste",max_uses=2)
        approved=approve_campaign(campaign,self.admin)
        active=mark_active_from_provider_evidence(
            approved,
            {
                "confirmed":True,
                "provider":"subscription_registry",
                "external_id":"promo-123",
            },
        )
        req=new_redemption_request(
            active,
            username="cliente.01",
            code=code,
            now=datetime.now(timezone.utc),
        )
        self.assertTrue(req["available_preflight"])
        self.assertFalse(req["entitlement"]["granted"])
        confirmed=confirm_redemption_from_provider(
            req,
            {
                "confirmed":True,
                "provider":"subscription_registry",
                "external_id":"grant-456",
            },
        )
        self.assertTrue(confirmed["entitlement"]["granted"])

    def test_wrong_code_and_expired_campaign_are_blocked(self):
        campaign,code=new_campaign(
            "Teste",
            starts_at="2026-09-01T00:00:00+00:00",
            expires_at="2026-09-10T00:00:00+00:00",
        )
        approved=approve_campaign(campaign,self.admin)
        active=mark_active_from_provider_evidence(
            approved,
            {
                "confirmed":True,
                "provider":"subscription_registry",
                "external_id":"promo-123",
            },
        )
        expired=campaign_availability(
            active,
            code=code,
            now=datetime(2026,9,12,tzinfo=timezone.utc),
        )
        self.assertFalse(expired["available"])
        self.assertIn("EXPIRED",expired["reasons"])
        wrong=campaign_availability(
            active,
            code="AQ-WRONGCODE",
            now=datetime(2026,9,5,tzinfo=timezone.utc),
        )
        self.assertFalse(wrong["available"])
        self.assertIn("CODE_INVALID",wrong["reasons"])

    def test_summary_and_upsert(self):
        a,_=new_campaign("A",created_at="2026-09-23T20:00:00Z")
        b,_=new_campaign("B",created_at="2026-09-23T20:01:00Z")
        b=approve_campaign(b,self.admin)
        rows=upsert_campaign([],a)
        rows=upsert_campaign(rows,b)
        summary=promotions_summary(rows,[])
        self.assertEqual(summary["campaigns"],2)
        self.assertEqual(summary["approved"],1)
        self.assertEqual(summary["active"],0)


if __name__=="__main__":
    unittest.main()
