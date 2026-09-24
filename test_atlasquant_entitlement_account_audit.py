import unittest
from datetime import datetime, timezone

from atlasquant_access_control import hash_password, load_users_config
from atlasquant_aion_entitlements import (
    approve_entitlement_request,
    mark_entitlement_from_provider_evidence,
    new_entitlement_request,
)
from atlasquant_entitlement_account_audit import (
    audit_account_entitlements,
    audit_requires_review,
)


class AtlasQuantEntitlementAccountAuditTests(unittest.TestCase):
    def setUp(self):
        encoded=hash_password(
            "SenhaSegura#2026",
            salt=b"0123456789abcdef",
            iterations=200000,
        )
        self.users=load_users_config({"users":{
            "cliente.01":{"role":"USER","password_hash":encoded,"active":True},
            "cliente.02":{"role":"USER","password_hash":encoded,"active":True},
            "admin.01":{"role":"ADMIN","password_hash":encoded,"active":True},
            "sales.01":{"role":"SALES","password_hash":encoded,"active":True},
            "off.01":{"role":"USER","password_hash":encoded,"active":False},
        }})
        self.admin={"role":"ADMIN","username":"admin.01"}
        self.now=datetime(2026,9,24,tzinfo=timezone.utc)

    def _active(self,subject,*,external_id):
        item=new_entitlement_request(
            subject,
            scope="APP_ACCESS",
            created_at=f"2026-09-24T00:00:0{external_id[-1] if external_id[-1].isdigit() else '0'}Z",
        )
        item=approve_entitlement_request(item,self.admin)
        return mark_entitlement_from_provider_evidence(
            item,
            {
                "confirmed":True,
                "provider":"subscription_registry",
                "external_id":external_id,
            },
        )

    def test_user_with_effective_entitlement_is_confirmed_but_not_enforced(self):
        report=audit_account_entitlements(
            self.users,
            [self._active("cliente.01",external_id="ent-1")],
            now=self.now,
        )
        row=next(x for x in report["account_rows"] if x["username"]=="cliente.01")
        self.assertEqual(row["state"],"ENTITLEMENT_EFFECTIVE")
        self.assertEqual(report["effective_user_accounts"],1)
        self.assertFalse(report["enforcement_enabled"])
        self.assertFalse(report["authentication_changed"])
        self.assertFalse(row["account_changed"])
        self.assertFalse(row["role_changed"])

    def test_missing_entitlement_is_review_signal_not_access_revocation(self):
        report=audit_account_entitlements(self.users,[],now=self.now)
        row=next(x for x in report["account_rows"] if x["username"]=="cliente.01")
        self.assertEqual(row["state"],"NO_EFFECTIVE_ENTITLEMENT")
        self.assertEqual(report["user_accounts_without_effective_entitlement"],2)
        self.assertTrue(audit_requires_review(report))
        self.assertFalse(report["automatic_revocation"])

    def test_admin_sales_and_inactive_accounts_are_not_expected_commercial_users(self):
        report=audit_account_entitlements(self.users,[],now=self.now)
        states={x["username"]:x["state"] for x in report["account_rows"]}
        self.assertEqual(states["admin.01"],"INTERNAL_ROLE_EXEMPT")
        self.assertEqual(states["sales.01"],"INTERNAL_ROLE_EXEMPT")
        self.assertEqual(states["off.01"],"ACCOUNT_INACTIVE")
        self.assertEqual(report["active_user_accounts"],2)

    def test_duplicate_effective_entitlements_are_flagged(self):
        a=self._active("cliente.01",external_id="ent-1")
        b=self._active("cliente.01",external_id="ent-2")
        report=audit_account_entitlements(self.users,[a,b],now=self.now)
        row=next(x for x in report["account_rows"] if x["username"]=="cliente.01")
        self.assertEqual(row["state"],"DUPLICATE_EFFECTIVE_ENTITLEMENTS")
        self.assertEqual(row["effective_entitlements"],2)
        self.assertEqual(report["duplicate_effective_user_accounts"],1)

    def test_orphan_effective_entitlement_is_flagged_without_creating_account(self):
        orphan=self._active("cliente.99",external_id="ent-9")
        report=audit_account_entitlements(self.users,[orphan],now=self.now)
        self.assertEqual(report["orphan_effective_entitlements"],1)
        self.assertEqual(report["orphan_rows"][0]["state"],"ORPHAN_EFFECTIVE_ENTITLEMENT")
        self.assertFalse(report["automatic_provisioning"])
        self.assertNotIn("cliente.99",{x["username"] for x in report["account_rows"]})

    def test_other_scope_does_not_satisfy_app_access(self):
        item=new_entitlement_request(
            "cliente.01",
            scope="ACADEMY_ONLY",
            created_at="2026-09-24T00:00:00Z",
        )
        item=approve_entitlement_request(item,self.admin)
        item=mark_entitlement_from_provider_evidence(
            item,
            {"confirmed":True,"provider":"registry","external_id":"academy-1"},
        )
        report=audit_account_entitlements(self.users,[item],now=self.now)
        row=next(x for x in report["account_rows"] if x["username"]=="cliente.01")
        self.assertEqual(row["state"],"NO_EFFECTIVE_ENTITLEMENT")


if __name__=="__main__":
    unittest.main()
