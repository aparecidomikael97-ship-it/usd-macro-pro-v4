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

    def test_bootstrap_preview_must_be_explicit_and_has_no_admin_session(self):
        out=panel.evaluate_access(
            required=True,
            users_count=0,
            session=None,
            allow_unconfigured_preview=True,
        )
        self.assertTrue(out["allowed"])
        self.assertEqual(out["mode"],"PREVIEW")
        self.assertEqual(out["reason"],"BOOTSTRAP_PREVIEW_NO_USERS")
        self.assertTrue(out["read_only"])

    def test_bootstrap_preview_never_bypasses_configured_user_login(self):
        out=panel.evaluate_access(
            required=True,
            users_count=1,
            session=None,
            allow_unconfigured_preview=True,
        )
        self.assertFalse(out["allowed"])
        self.assertEqual(out["mode"],"LOGIN")

    def test_required_mode_without_session_demands_login(self):
        out=panel.evaluate_access(required=True,users_count=2,session=None)
        self.assertFalse(out["allowed"])
        self.assertEqual(out["mode"],"LOGIN")

    def test_valid_user_session_can_read_app_but_invalid_role_cannot(self):
        ok=panel.evaluate_access(required=True,users_count=1,session={"role":"USER"})
        bad=panel.evaluate_access(required=True,users_count=1,session={"role":"ROOT"})
        self.assertTrue(ok["allowed"])
        self.assertFalse(bad["allowed"])





    def test_login_throttle_locks_after_five_failures_and_resets_after_window(self):
        state={}
        now=1000.0
        for i in range(5):
            state=panel.record_login_failure(state,now+i)
        locked=panel.throttle_status(state,now+5)
        self.assertTrue(locked["locked"])
        self.assertGreater(locked["retry_after"],0)
        expired=panel.throttle_status(state,now+panel.LOCK_SECONDS+10)
        self.assertFalse(expired["locked"])
        self.assertEqual(expired["attempts"],0)

    def test_corrupt_throttle_state_fails_closed(self):
        status=panel.throttle_status({"attempts":-1,"lock_until":-5},1000.0)
        self.assertTrue(status["locked"])
        self.assertEqual(status["attempts"],panel.MAX_FAILED_ATTEMPTS)


    def test_session_time_contract_expires_idle_and_absolute_age(self):
        now=100000.0
        valid={"authenticated_at":now-60,"last_seen":now-10}
        self.assertTrue(panel.session_time_status(valid,now)["valid"])

        idle={"authenticated_at":now-panel.SESSION_IDLE_SECONDS-10,"last_seen":now-panel.SESSION_IDLE_SECONDS-1}
        self.assertEqual(panel.session_time_status(idle,now)["reason"],"SESSION_IDLE_TIMEOUT")

        old={"authenticated_at":now-panel.SESSION_MAX_SECONDS-1,"last_seen":now-1}
        self.assertEqual(panel.session_time_status(old,now)["reason"],"SESSION_MAX_AGE")

        bad={"authenticated_at":"bad","last_seen":now}
        self.assertFalse(panel.session_time_status(bad,now)["valid"])


    def test_explicit_production_environment_forces_authentication(self):
        def fake_setting(key,default=""):
            if key=="ATLASQUANT_ENV":
                return "PRODUCTION"
            if key=="ATLASQUANT_AUTH_REQUIRED":
                return "false"
            return default
        with patch.object(panel,"_setting",side_effect=fake_setting):
            self.assertTrue(panel.access_required())

    def test_registry_role_counts_exposes_counts_only(self):
        encoded=hash_password("SenhaSegura#2026",salt=b"0123456789abcdef",iterations=200000)
        users=load_users_config({"users":{
            "user.01":{"role":"USER","password_hash":encoded,"active":True},
            "sales.01":{"role":"SALES","password_hash":encoded,"active":True},
            "admin.01":{"role":"ADMIN","password_hash":encoded,"active":True},
            "off.01":{"role":"USER","password_hash":encoded,"active":False},
        }})
        counts=panel.registry_role_counts(users)
        self.assertEqual(counts,{"USER":1,"SALES":1,"ADMIN":1,"TOTAL":3})
        self.assertNotIn("user.01",str(counts))

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