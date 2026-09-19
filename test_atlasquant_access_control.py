import json
import unittest

from atlasquant_access_control import (
    AccessUser, ROLE_PERMISSIONS, authenticate, has_permission,
    hash_password, load_users_config, normalize_role, normalize_username,
    verify_password,
)

class AtlasQuantAccessControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password="SenhaSegura#2026"
        cls.encoded=hash_password(cls.password,salt=b"0123456789abcdef",iterations=200000)

    def test_password_hash_roundtrip_and_wrong_password(self):
        self.assertTrue(verify_password(self.password,self.encoded))
        self.assertFalse(verify_password("senha-errada",self.encoded))
        self.assertNotIn(self.password,self.encoded)

    def test_short_password_and_weak_hash_parameters_are_rejected(self):
        with self.assertRaises(ValueError):
            hash_password("curta")
        with self.assertRaises(ValueError):
            hash_password(self.password,salt=b"short",iterations=200000)
        with self.assertRaises(ValueError):
            hash_password(self.password,salt=b"0123456789abcdef",iterations=1)

    def test_users_config_rejects_plaintext_and_invalid_roles(self):
        raw={
            "users":{
                "admin.ok":{"role":"ADMIN","password_hash":self.encoded,"active":True},
                "plain.user":{"role":"USER","password":"plaintext","password_hash":self.encoded,"active":True},
                "bad.role":{"role":"ROOT","password_hash":self.encoded,"active":True},
            }
        }
        users=load_users_config(raw)
        self.assertEqual(set(users),{"admin.ok"})

    def test_json_config_authenticates_active_user_only(self):
        raw=json.dumps({"users":{
            "sales.user":{"role":"SALES","password_hash":self.encoded,"active":True},
            "off.user":{"role":"USER","password_hash":self.encoded,"active":False},
        }})
        users=load_users_config(raw)
        session=authenticate(" SALES.USER ",self.password,users)
        self.assertIsNotNone(session)
        self.assertEqual(session["role"],"SALES")
        self.assertIsNone(authenticate("off.user",self.password,users))
        self.assertIsNone(authenticate("sales.user","wrong",users))

    def test_permissions_are_role_bounded(self):
        user={"role":"USER"}
        sales={"role":"SALES"}
        admin={"role":"ADMIN"}
        self.assertTrue(has_permission(user,"app:read"))
        self.assertFalse(has_permission(user,"sales:read"))
        self.assertTrue(has_permission(sales,"sales:read"))
        self.assertFalse(has_permission(sales,"admin:read"))
        self.assertTrue(has_permission(admin,"admin:manage_users"))

    def test_invalid_usernames_roles_and_malformed_hash_fail_closed(self):
        self.assertEqual(normalize_username("../admin"),"")
        self.assertEqual(normalize_username("ab"),"")
        self.assertEqual(normalize_role("root"),"")
        self.assertFalse(verify_password(self.password,"plaintext"))
        self.assertEqual(load_users_config("not-json"),{})

if __name__=="__main__":
    unittest.main()
