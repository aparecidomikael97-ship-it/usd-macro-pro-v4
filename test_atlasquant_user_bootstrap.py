import unittest

from atlasquant_user_bootstrap import generate_record
from atlasquant_access_control import load_users_config, authenticate

class AtlasQuantUserBootstrapTests(unittest.TestCase):
    def test_bootstrap_output_contains_hash_not_plaintext(self):
        password="SenhaSegura#2026"
        raw=generate_record("admin.01","ADMIN",password,password)
        self.assertNotIn(password,raw)
        self.assertIn("pbkdf2_sha256",raw)
        users=load_users_config(raw)
        session=authenticate("admin.01",password,users)
        self.assertIsNotNone(session)
        self.assertEqual(session["role"],"ADMIN")

    def test_confirmation_mismatch_fails(self):
        with self.assertRaises(ValueError):
            generate_record("admin.01","ADMIN","SenhaSegura#2026","OutraSenha#2026")

if __name__=="__main__":
    unittest.main()
