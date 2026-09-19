import unittest
from atlasquant_commercial_launch_guard import CommercialEvidence, assess_commercial_launch

class AtlasQuantCommercialLaunchGuardTests(unittest.TestCase):
    def evidence(self, **kw):
        data=dict(
            private_access_ok=True,
            account_admin_ok=True,
            distribution_ok=True,
            terms_privacy_ok=True,
            data_licensing_ok=True,
            support_ok=True,
            academy_minimum_ok=True,
            billing_ok=True,
            sales_role_isolated_ok=True,
            account_revocation_ok=True,
            audit_manifest_ok=True,
        )
        data.update(kw)
        return CommercialEvidence(**data)

    def assert_never_changes_trading_or_launches_automatically(self, out):
        self.assertTrue(out["manual_launch_required"])
        self.assertFalse(out["automatic_launch"])
        self.assertFalse(out["legal_certification"])
        self.assertFalse(out["trading_permission_changed"])

    def test_complete_evidence_is_reviewable_but_never_auto_launches(self):
        out=assess_commercial_launch(self.evidence())
        self.assertEqual(out["status"],"REVIEWABLE")
        self.assert_never_changes_trading_or_launches_automatically(out)

    def test_any_missing_requirement_blocks_public_launch(self):
        for field in (
            "private_access_ok","account_admin_ok","distribution_ok",
            "terms_privacy_ok","data_licensing_ok","support_ok",
            "academy_minimum_ok","billing_ok",
        ):
            with self.subTest(field=field):
                out=assess_commercial_launch(self.evidence(**{field:False}))
                self.assertEqual(out["status"],"BLOCKED")
                self.assertTrue(out["blockers"])
                self.assert_never_changes_trading_or_launches_automatically(out)

    def test_account_security_evidence_is_required_for_launch(self):
        for field in ("sales_role_isolated_ok","account_revocation_ok","audit_manifest_ok"):
            with self.subTest(field=field):
                out=assess_commercial_launch(self.evidence(**{field:False}))
                self.assertEqual(out["status"],"BLOCKED")
                self.assert_never_changes_trading_or_launches_automatically(out)

    def test_omitted_security_evidence_blocks_by_default(self):
        e=CommercialEvidence(
            private_access_ok=True,account_admin_ok=True,distribution_ok=True,
            terms_privacy_ok=True,data_licensing_ok=True,support_ok=True,
            academy_minimum_ok=True,billing_ok=True,
        )
        out=assess_commercial_launch(e)
        self.assertEqual(out["status"],"BLOCKED")
        self.assertTrue(any("SALES" in x for x in out["blockers"]))
        self.assertTrue(any("Revogação" in x for x in out["blockers"]))
        self.assertTrue(any("Auditoria" in x for x in out["blockers"]))
        self.assert_never_changes_trading_or_launches_automatically(out)

    def test_non_boolean_evidence_fails_closed_for_every_launch_flag(self):
        for field in (
            "private_access_ok","account_admin_ok","distribution_ok",
            "terms_privacy_ok","data_licensing_ok","support_ok",
            "academy_minimum_ok","billing_ok","sales_role_isolated_ok",
            "account_revocation_ok","audit_manifest_ok",
        ):
            for bad in (1,0,"true","false",None,[],{}):
                with self.subTest(field=field,bad=bad):
                    out=assess_commercial_launch(self.evidence(**{field:bad}))
                    self.assertEqual(out["status"],"BLOCKED")
                    self.assertTrue(any("Flag inválida: "+field == x for x in out["blockers"]))
                    self.assert_never_changes_trading_or_launches_automatically(out)

if __name__=="__main__":
    unittest.main()
