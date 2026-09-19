import json
import unittest

from atlasquant_account_portal import (
    account_summary,
    build_provisioning_record,
    merge_provisioning_records,
    password_policy,
    provisioning_json,
    role_sections,
)
from atlasquant_access_control import load_users_config, authenticate

class AtlasQuantAccountPortalTests(unittest.TestCase):
    def test_role_sections_are_strictly_bounded(self):
        self.assertEqual(role_sections("USER"),("account",))
        self.assertEqual(role_sections("SALES"),("account","sales"))
        self.assertEqual(role_sections("ADMIN"),("account","sales","admin"))
        self.assertEqual(role_sections("ROOT"),())

    def test_password_policy_requires_length_case_digit_and_symbol(self):
        self.assertTrue(password_policy("SenhaSegura#2026")["valid"])
        for bad in ("curta","semmaiuscula#2026","SEMMINUSCULA#2026","SemNumero#","SemSimbolo2026"):
            with self.subTest(bad=bad):
                self.assertFalse(password_policy(bad)["valid"])

    def test_admin_can_generate_hash_only_record(self):
        record=build_provisioning_record("cliente.01","USER","SenhaSegura#2026")
        user=record["cliente.01"]
        self.assertEqual(user["role"],"USER")
        self.assertNotIn("password",user)
        self.assertTrue(user["password_hash"].startswith("pbkdf2_sha256$"))
        self.assertNotIn("SenhaSegura#2026",user["password_hash"])

    def test_generated_record_roundtrips_through_access_control(self):
        record=build_provisioning_record("vendas.01","SALES","SenhaSegura#2026")
        raw=provisioning_json(record)
        users=load_users_config(raw)
        session=authenticate("vendas.01","SenhaSegura#2026",users)
        self.assertIsNotNone(session)
        self.assertEqual(session["role"],"SALES")


    def test_manual_plaintext_or_invalid_provisioning_record_is_rejected(self):
        invalid_plain={"bad.user":{"role":"USER","password":"plaintext","active":True}}
        invalid_role={"bad.user":{"role":"ROOT","password_hash":"pbkdf2_sha256$200000$00$00","active":True}}
        for record in (invalid_plain,invalid_role):
            with self.subTest(record=record):
                with self.assertRaises(ValueError):
                    provisioning_json(record)
                with self.assertRaises(ValueError):
                    merge_provisioning_records(record)

    def test_duplicate_provisioning_records_fail_closed(self):
        a=build_provisioning_record("cliente.01","USER","SenhaSegura#2026")
        b=build_provisioning_record("cliente.01","SALES","OutraSenha#2026")
        with self.assertRaises(ValueError):
            merge_provisioning_records(a,b)

    def test_account_summary_never_promotes_open_mode_to_admin(self):
        open_summary=account_summary({"allowed":True,"mode":"OPEN","role":"OPEN"})
        self.assertFalse(open_summary["authenticated"])
        self.assertNotIn("admin",open_summary["sections"])
        admin_summary=account_summary({
            "allowed":True,
            "mode":"AUTHENTICATED",
            "role":"ADMIN",
            "session":{"username":"admin.01","role":"ADMIN"},
        })
        self.assertTrue(admin_summary["authenticated"])
        self.assertIn("admin",admin_summary["sections"])


    def test_admin_summary_receives_safe_registry_counts(self):
        summary=account_summary({
            "allowed":True,
            "mode":"AUTHENTICATED",
            "role":"ADMIN",
            "session":{"username":"admin.01","role":"ADMIN"},
            "registry":{"USER":4,"SALES":2,"ADMIN":1,"TOTAL":7},
        })
        self.assertEqual(summary["registry"]["TOTAL"],7)
        self.assertEqual(summary["registry"]["SALES"],2)
        self.assertNotIn("password",str(summary).lower())



    def test_corrupt_registry_counts_are_sanitized(self):
        summary=account_summary({
            "allowed":True,
            "mode":"AUTHENTICATED",
            "role":"ADMIN",
            "session":{"username":"admin.01","role":"ADMIN"},
            "registry":{"USER":float("nan"),"SALES":-1,"ADMIN":"bad","TOTAL":float("inf")},
        })
        self.assertFalse(summary["registry_valid"])
        self.assertEqual(summary["registry"],{"USER":0,"SALES":0,"ADMIN":0,"TOTAL":0})

    def test_mismatched_declared_and_session_role_fails_closed(self):
        summary=account_summary({
            "allowed":True,
            "mode":"AUTHENTICATED",
            "role":"ADMIN",
            "session":{"username":"user.01","role":"USER"},
        })
        self.assertEqual(summary["role"],"INVALID")
        self.assertFalse(summary["authenticated"])
        self.assertNotIn("admin",summary["sections"])

    def test_portal_source_never_writes_secrets_or_enables_live_trading(self):
        from pathlib import Path
        src=Path("atlasquant_account_portal.py").read_text(encoding="utf-8")
        self.assertNotIn("st.secrets[",src)
        self.assertNotIn("requests.",src)
        self.assertNotIn("real_orders=True",src)
        self.assertIn('"Trading real","DESATIVADO"',src)

    def test_invalid_provisioning_inputs_are_rejected(self):
        cases=[
            ("ab","USER","SenhaSegura#2026"),
            ("cliente","ROOT","SenhaSegura#2026"),
            ("cliente","USER","fraca"),
        ]
        for username,role,password in cases:
            with self.subTest(username=username,role=role):
                with self.assertRaises(ValueError):
                    build_provisioning_record(username,role,password)

if __name__=="__main__":
    unittest.main()
