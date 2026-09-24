import unittest
from datetime import datetime, timezone

from atlasquant_aion_entitlements import (
    approve_entitlement_request,
    entitlement_activation_preflight,
    entitlement_effective,
    entitlement_summary,
    mark_entitlement_from_provider_evidence,
    new_entitlement_request,
    normalize_entitlement,
    upsert_entitlement,
)


class AtlasQuantAionEntitlementsTests(unittest.TestCase):
    def setUp(self):
        self.admin={"role":"ADMIN","username":"admin.test"}

    def test_new_request_is_draft_and_never_changes_account_or_role(self):
        item=new_entitlement_request(
            "cliente.01",
            scope="APP_ACCESS",
            source_kind="MANUAL_GRANT",
            note="cortesia futura",
        )
        self.assertEqual(item["status"],"DRAFT")
        self.assertFalse(item["approval"]["approved"])
        self.assertFalse(item["provider_evidence"]["confirmed"])
        self.assertFalse(item["effects"]["account_registry_changed"])
        self.assertFalse(item["effects"]["role_changed"])
        self.assertFalse(item["effects"]["payment_executed"])
        self.assertFalse(item["effects"]["trading_permission_changed"])

    def test_approval_requires_admin_and_does_not_activate(self):
        item=new_entitlement_request("cliente.01")
        with self.assertRaises(PermissionError):
            approve_entitlement_request(item,{"role":"USER"})
        approved=approve_entitlement_request(item,self.admin)
        self.assertEqual(approved["status"],"APPROVED")
        self.assertTrue(approved["approval"]["approved"])
        self.assertFalse(entitlement_effective(approved)["effective"])

    def test_activation_preflight_is_double_locked_and_non_executing(self):
        item=approve_entitlement_request(new_entitlement_request("cliente.01"),self.admin)
        no_flag=entitlement_activation_preflight(
            item,self.admin,
            feature_flags={"entitlement_activation":False},
            approved=True,
        )
        self.assertFalse(no_flag["allowed"])
        no_click=entitlement_activation_preflight(
            item,self.admin,
            feature_flags={"entitlement_activation":True},
            approved=False,
        )
        self.assertFalse(no_click["allowed"])
        ready=entitlement_activation_preflight(
            item,self.admin,
            feature_flags={"entitlement_activation":True},
            approved=True,
        )
        self.assertTrue(ready["allowed"])
        self.assertFalse(ready["executes_entitlement"])
        self.assertFalse(ready["changes_account_registry"])
        self.assertFalse(ready["changes_role"])

    def test_confirmed_active_state_requires_provider_evidence(self):
        approved=approve_entitlement_request(new_entitlement_request("cliente.01"),self.admin)
        with self.assertRaises(ValueError):
            mark_entitlement_from_provider_evidence(
                approved,
                {"confirmed":True,"provider":"billing"},
            )
        active=mark_entitlement_from_provider_evidence(
            approved,
            {
                "confirmed":True,
                "provider":"subscription_registry",
                "external_id":"ent-123",
                "event_id":"evt-456",
            },
        )
        self.assertEqual(active["status"],"ACTIVE_CONFIRMED")
        self.assertTrue(active["provider_evidence"]["confirmed"])
        self.assertTrue(entitlement_effective(active)["effective"])

    def test_normalization_downgrades_unproven_active_claim(self):
        item=new_entitlement_request("cliente.01")
        item["status"]="ACTIVE_CONFIRMED"
        normalized=normalize_entitlement(item)
        self.assertEqual(normalized["status"],"DRAFT")
        item=approve_entitlement_request(item,self.admin)
        item["status"]="ACTIVE_CONFIRMED"
        normalized=normalize_entitlement(item)
        self.assertEqual(normalized["status"],"APPROVED")

    def test_window_blocks_future_and_expired_effective_access(self):
        item=new_entitlement_request(
            "cliente.01",
            starts_at="2026-10-01T00:00:00+00:00",
            expires_at="2026-10-31T00:00:00+00:00",
        )
        item=approve_entitlement_request(item,self.admin)
        item=mark_entitlement_from_provider_evidence(
            item,
            {"confirmed":True,"provider":"registry","external_id":"x-1"},
        )
        before=entitlement_effective(
            item,now=datetime(2026,9,30,tzinfo=timezone.utc),
        )
        self.assertFalse(before["effective"])
        self.assertIn("NOT_STARTED",before["reasons"])
        during=entitlement_effective(
            item,now=datetime(2026,10,15,tzinfo=timezone.utc),
        )
        self.assertTrue(during["effective"])
        after=entitlement_effective(
            item,now=datetime(2026,11,1,tzinfo=timezone.utc),
        )
        self.assertFalse(after["effective"])
        self.assertIn("EXPIRED",after["reasons"])

    def test_summary_and_upsert(self):
        a=new_entitlement_request("cliente.01",created_at="2026-09-24T12:00:00Z")
        b=new_entitlement_request("cliente.02",created_at="2026-09-24T12:01:00Z")
        b=approve_entitlement_request(b,self.admin)
        rows=upsert_entitlement([],a)
        rows=upsert_entitlement(rows,b)
        summary=entitlement_summary(rows)
        self.assertEqual(summary["records"],2)
        self.assertEqual(summary["approved"],1)
        self.assertEqual(summary["active_confirmed"],0)


if __name__=="__main__":
    unittest.main()
