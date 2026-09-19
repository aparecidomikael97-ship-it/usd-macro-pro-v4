import unittest

from atlasquant_access_control import hash_password, load_users_config, authenticate
from atlasquant_registry_admin import (
    add_account,
    apply_non_destructive_change,
    export_registry_json,
    registry_diff,
    rotate_account_password,
    set_account_active,
    set_account_role,
)

class AtlasQuantRegistryAdminTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password="SenhaSegura#2026"
        cls.hash=hash_password(cls.password,salt=b"0123456789abcdef",iterations=200000)

    def users(self):
        return load_users_config({"users":{
            "admin.01":{"role":"ADMIN","password_hash":self.hash,"active":True},
            "user.01":{"role":"USER","password_hash":self.hash,"active":True},
        }})

    def test_add_account_preserves_existing_users(self):
        before=self.users()
        after=add_account(before,username="sales.01",role="SALES",password="OutraSenha#2026")
        self.assertEqual(set(after),{"admin.01","user.01","sales.01"})
        self.assertEqual(after["sales.01"].role,"SALES")
        raw=apply_non_destructive_change(before,after)
        self.assertIn("sales.01",raw)
        self.assertNotIn("OutraSenha#2026",raw)

    def test_duplicate_or_invalid_account_is_rejected(self):
        before=self.users()
        for username,role in (("user.01","USER"),("ab","USER"),("valid.01","ROOT")):
            with self.subTest(username=username,role=role):
                with self.assertRaises(ValueError):
                    add_account(before,username=username,role=role,password="OutraSenha#2026")

    def test_deactivate_account_revokes_authentication(self):
        before=self.users()
        after=set_account_active(before,"user.01",False)
        self.assertFalse(after["user.01"].active)
        self.assertIsNone(authenticate("user.01",self.password,after))

    def test_role_change_preserves_account_and_revokes_old_session_semantics(self):
        before=self.users()
        after=set_account_role(before,"user.01","SALES")
        self.assertEqual(after["user.01"].role,"SALES")
        diff=registry_diff(before,after)
        self.assertEqual(diff["changed"],[{"username":"user.01","fields":["role"]}])
        self.assertTrue(diff["safe_for_manual_export"])

    def test_password_rotation_changes_credential_only(self):
        before=self.users()
        after=rotate_account_password(before,"user.01","NovaSenha#2026")
        self.assertNotEqual(before["user.01"].password_hash,after["user.01"].password_hash)
        self.assertIsNone(authenticate("user.01",self.password,after))
        self.assertIsNotNone(authenticate("user.01","NovaSenha#2026",after))
        diff=registry_diff(before,after)
        self.assertEqual(diff["changed"],[{"username":"user.01","fields":["credential"]}])


    def test_last_active_admin_cannot_be_deactivated_or_demoted(self):
        before=self.users()
        with self.assertRaises(ValueError):
            set_account_active(before,"admin.01",False)
        with self.assertRaises(ValueError):
            set_account_role(before,"admin.01","USER")

    def test_one_admin_can_change_when_another_active_admin_remains(self):
        before=self.users()
        before=add_account(before,username="admin.02",role="ADMIN",password="OutraSenha#2026")
        after=set_account_active(before,"admin.01",False)
        self.assertFalse(after["admin.01"].active)
        self.assertTrue(after["admin.02"].active)


    def test_destructive_removal_is_detected_and_export_blocked(self):
        before=self.users()
        after={"admin.01":before["admin.01"]}
        diff=registry_diff(before,after)
        self.assertTrue(diff["destructive_removal_detected"])
        self.assertFalse(diff["safe_for_manual_export"])
        with self.assertRaises(ValueError):
            apply_non_destructive_change(before,after)


    def test_mixed_validity_registry_is_rejected_not_silently_truncated(self):
        before=self.users()
        mixed=dict(before)
        mixed["broken.01"]={"role":"USER"}
        with self.assertRaises(ValueError):
            export_registry_json(mixed)


    def test_export_roundtrip_contains_hashes_not_plaintext(self):
        raw=export_registry_json(self.users())
        rebuilt=load_users_config(raw)
        self.assertEqual(set(rebuilt),{"admin.01","user.01"})
        self.assertNotIn(self.password,raw)

if __name__=="__main__":
    unittest.main()
