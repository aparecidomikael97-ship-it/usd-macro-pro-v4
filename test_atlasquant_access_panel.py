import unittest
from pathlib import Path
from unittest.mock import patch

import atlasquant_access_panel as panel
from atlasquant_access_control import hash_password, load_users_config, authenticate

class AtlasQuantAccessPanelTests(unittest.TestCase):
    def test_auth_is_disabled_by_default(self):
        with patch.object(panel,"_setting",return_value="false"):
            self.assertFalse(panel.access_required())

    def test_required_mode_without_users_fails_closed(self):
        out=panel.evaluate_access(required=True,users_count=0,session=None)
        self.assertFalse(out["allowed"])
        self.assertEqual(out["reason"],"NO_USERS_CONFIGURED")

    def test_required_mode_without_session_demands_login(self):
        out=panel.evaluate_access(required=True,users_count=2,session=None)
        self.assertFalse(out["allowed"])
        self.assertEqual(out["mode"],"LOGIN")

    def test_valid_user_session_can_read_app_but_invalid_role_cannot(self):
        ok=panel.evaluate_access(required=True,users_count=1,session={"role":"USER"})
        bad=panel.evaluate_access(required=True,users_count=1,session={"role":"ROOT"})
        self.assertTrue(ok["allowed"])
        self.assertFalse(bad["allowed"])


    def test_current_session_must_still_match_configured_user(self):
        encoded=hash_password("SenhaSegura#2026",salt=b"0123456789abcdef",iterations=200000)
        users=load_users_config({"users":{"user.01":{"role":"USER","password_hash":encoded,"active":True}}})
        session=authenticate("user.01","SenhaSegura#2026",users)
        ok=panel.evaluate_access(required=True,users_count=1,session=session,users=users)
        self.assertTrue(ok["allowed"])

        changed=load_users_config({"users":{"user.01":{"role":"SALES","password_hash":encoded,"active":True}}})
        revoked=panel.evaluate_access(required=True,users_count=1,session=session,users=changed)
        self.assertFalse(revoked["allowed"])
        self.assertEqual(revoked["reason"],"SESSION_REVOKED")

    def test_main_app_integrates_gate_and_fail_closed_stop(self):
        src=Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertIn("from atlasquant_access_panel import render_access_gate",src)
        self.assertIn("ATLASQUANT_AUTH_REQUIRED",src)
        self.assertIn("st.stop()",src)
        gate_pos=src.index("render_access_gate()")
        fred_pos=src.index("def _get(")
        self.assertLess(gate_pos,fred_pos)

if __name__=="__main__":
    unittest.main()
