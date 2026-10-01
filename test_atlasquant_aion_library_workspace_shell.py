"""Adversarial tests for AION Library's opt-in, static admin shell."""
import ast
import unittest
from pathlib import Path
from contextlib import nullcontext

from atlasquant_access_control import AccessUser, authenticate, hash_password
from atlasquant_aion_library_workspace_shell import (
    WORKSPACE_LABEL, library_shell_gate, library_workspace_choices, render_library_shell,
)

NOW = 2_000_000_000


def session_time_check(session, now):
    try:
        issued, seen = float(session["authenticated_at"]), float(session["last_seen"])
        ok = 0 < issued <= seen <= now and now - issued <= 43200 and now - seen <= 7200
    except (KeyError, TypeError, ValueError):
        ok = False
    return {"valid": ok}


class FakeStreamlit:
    def __init__(self): self.log=[]
    def __getattr__(self, key):
        if key == "columns":
            return lambda n: [nullcontext() for _ in range(n)]
        if key not in {"subheader", "info", "caption", "metric", "markdown", "warning", "error"}:
            raise AssertionError("unexpected UI API " + key)
        def call(*args, **kwargs):
            self.log.append((key, args, kwargs))
        return call


class LibraryWorkspaceShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.encoded=hash_password("SyntheticLibraryAdminPass#", salt=b"a"*16, iterations=200_000)

    def setUp(self):
        self.users={"admin.1":AccessUser("admin.1", "ADMIN", self.encoded),
                    "user.1":AccessUser("user.1", "USER", self.encoded)}
        session=authenticate("admin.1","SyntheticLibraryAdminPass#",self.users)
        self.assertIsNotNone(session)
        self.access={"allowed": True, "mode":"AUTHENTICATED", "role":"ADMIN",
                     "session": dict(session,authenticated_at=NOW-100,last_seen=NOW-10)}

    def gate(self, **kw):
        args=dict(access=self.access, users=self.users, environment="SANDBOX",
                  preview_flag="true", now=NOW, session_time_check=session_time_check)
        args.update(kw)
        return library_shell_gate(**args)

    def test_sandbox_admin_can_view_static_shell(self):
        v=self.gate()
        self.assertTrue(v["visible"])
        self.assertFalse(v["operational"])
        self.assertFalse(v["document_read_enabled"])
        self.assertFalse(v["index_enabled"])
        self.assertFalse(v["approval_enabled"])
        self.assertFalse(v["upload_enabled"])
        self.assertFalse(v["external_actions_enabled"])

    def test_explicit_flag_required(self):
        for flag in ("", "false", "0", "no", " True;enable", None, True, 1):
            with self.subTest(flag=flag): self.assertFalse(self.gate(preview_flag=flag)["visible"])

    def test_non_sandbox_environments_always_denied(self):
        for env in ("PRODUCTION", "production", "LOCAL", "TEST", "DEV", "", None, 1):
            with self.subTest(env=env): self.assertFalse(self.gate(environment=env)["visible"])

    def test_sandbox_normalization_explicit_only(self):
        self.assertTrue(self.gate(environment=" sandbox ",preview_flag=" ON ")["visible"])

    def test_all_open_preview_login_modes_denied(self):
        for mode in ("OPEN", "PREVIEW", "LOGIN", "LOCKED", None):
            with self.subTest(mode=mode):
                a=dict(self.access,mode=mode)
                self.assertFalse(self.gate(access=a)["visible"])

    def test_missing_or_non_true_allowed_denied(self):
        for value in (None,False,"True",1):
            with self.subTest(value=value):
                a=dict(self.access,allowed=value)
                self.assertFalse(self.gate(access=a)["visible"])

    def test_unsigned_or_malformed_sessions_denied(self):
        for value in (None,{},"admin",["admin"]):
            a=dict(self.access,session=value)
            self.assertFalse(self.gate(access=a)["visible"])

    def test_user_role_cannot_inherit_library_ui(self):
        s=authenticate("user.1","SyntheticLibraryAdminPass#",self.users)
        a=dict(self.access,role="USER",session=dict(s, authenticated_at=NOW-10,last_seen=NOW-1))
        self.assertFalse(self.gate(access=a)["visible"])

    def test_forged_session_admin_role_denied(self):
        s=authenticate("user.1","SyntheticLibraryAdminPass#",self.users)
        a=dict(self.access,session=dict(s,role="ADMIN",authenticated_at=NOW-10,last_seen=NOW-1))
        self.assertFalse(self.gate(access=a)["visible"])

    def test_admin_role_in_access_only_denied(self):
        a=dict(self.access,role="USER")
        self.assertFalse(self.gate(access=a)["visible"])

    def test_unknown_registry_denied(self): self.assertFalse(self.gate(users={})["visible"])

    def test_disabled_or_demoted_admin_denied(self):
        for user in (AccessUser("admin.1","ADMIN",self.encoded,active=False),
                     AccessUser("admin.1","USER",self.encoded)):
            self.assertFalse(self.gate(users={"admin.1":user})["visible"])

    def test_password_rotation_invalidates_shell(self):
        new=hash_password("OtherCredentialPassForTest#",salt=b"b"*16,iterations=200_000)
        self.assertFalse(self.gate(users={"admin.1":AccessUser("admin.1","ADMIN",new)})["visible"])

    def test_bad_fingerprint_denied(self):
        for bad in ("",None,"a"*64, "A"*24):
            a=dict(self.access,session=dict(self.access["session"],credential_fingerprint=bad))
            self.assertFalse(self.gate(access=a)["visible"])

    def test_session_absolute_age_and_idle_denied(self):
        for old in (dict(authenticated_at=NOW-50000,last_seen=NOW-1),
                    dict(authenticated_at=NOW-100,last_seen=NOW-10000),
                    dict(authenticated_at=NOW+100,last_seen=NOW+200)):
            a=dict(self.access,session=dict(self.access["session"],**old))
            self.assertFalse(self.gate(access=a)["visible"])

    def test_missing_checker_fail_closed(self):
        self.assertFalse(self.gate(session_time_check=None)["visible"])
        self.assertFalse(self.gate(session_time_check=lambda *_: (_ for _ in ()).throw(ValueError("internal secret")))["visible"])
        self.assertFalse(self.gate(session_time_check=lambda *_: {"valid":"true"})["visible"])

    def test_invalid_access_and_users_denied(self):
        for x in (None,[],"admin",False):
            self.assertFalse(self.gate(access=x)["visible"])
            self.assertFalse(self.gate(users=x)["visible"])

    def test_options_unchanged_by_default(self):
        base=("🧠 Central", "📈 Trading")
        self.assertIs(library_workspace_choices(standard=base,gate=self.gate(preview_flag="false")),base)

    def test_options_append_only_one_library_in_sandbox(self):
        base=("🧠 Central", "📈 Trading")
        self.assertEqual(library_workspace_choices(standard=base,gate=self.gate()),(*base,WORKSPACE_LABEL))

    def test_unsafe_gate_cannot_show_option(self):
        base=("Central",)
        for bad in ({"visible": True, "operational": True},{"visible": "true", "operational":False},None):
            self.assertEqual(library_workspace_choices(standard=base,gate=bad),base)

    def test_duplicate_or_non_tuple_options_denied(self):
        with self.assertRaises(ValueError): library_workspace_choices(standard=(WORKSPACE_LABEL,),gate=self.gate())
        with self.assertRaises(ValueError): library_workspace_choices(standard=["Central"],gate=self.gate())

    def test_render_static_content_only(self):
        ui=FakeStreamlit()
        self.assertTrue(render_library_shell(ui,gate=self.gate()))
        names=[z[0] for z in ui.log]
        self.assertIn("warning",names)
        self.assertEqual(names.count("metric"),2)
        self.assertNotIn("button",names)
        self.assertNotIn("file_uploader",names)

    def test_render_denies_stale_gate_without_shell(self):
        ui=FakeStreamlit()
        self.assertFalse(render_library_shell(ui,gate=self.gate(environment="PRODUCTION")))
        self.assertEqual([z[0] for z in ui.log],["error"])
        self.assertFalse(render_library_shell(ui,gate={"visible":True,"operational":True}))

    def test_source_has_no_database_network_or_upload(self):
        source=Path(__file__).with_name("atlasquant_aion_library_workspace_shell.py").read_text()
        root=ast.parse(source)
        imported={n.module for n in ast.walk(root) if isinstance(n,ast.ImportFrom)}
        self.assertNotIn("psycopg",imported)
        self.assertNotIn("requests",imported)
        self.assertNotIn("streamlit",imported)
        self.assertNotIn("atlasquant_aion_library_postgres_preview",imported)
        self.assertNotIn("st.file_uploader",source)
        self.assertNotIn("st.button",source)

    def test_valid_shell_never_reports_operational(self):
        for flag in ("true","1","on","yes"):
            v=self.gate(preview_flag=flag)
            self.assertTrue(v["visible"])
            self.assertFalse(v["operational"])
            self.assertEqual(v["reason"],"STATIC_SANDBOX_PREVIEW_ONLY")

    def test_failure_reasons_do_not_expose_secrets(self):
        v=self.gate(session_time_check=lambda *_: (_ for _ in ()).throw(Exception("secret!")))
        self.assertNotIn("secret!",repr(v))


class AdminWiringStaticTests(unittest.TestCase):
    @unittest.skipUnless(Path("atlasquant_aion_admin.py").exists(),"requires complete GitHub checkout")
    def test_existing_nine_workspaces_stay_unchanged_and_library_uses_dynamic_gate(self):
        src=Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("library_workspace_choices(standard=AION_WORKSPACES, gate=library_gate)",src)
        self.assertIn("elif selected_workspace == LIBRARY_WORKSPACE_LABEL:",src)
        self.assertIn("render_library_shell(st, gate=library_gate)",src)
        self.assertIn('"🧠 Central"',src)
        self.assertIn('"🎟️ Promoções"',src)
        self.assertIn("if jump_request in workspace_choices:",src)
        self.assertIn("if not library_gate['visible']",src)
        self.assertIn('"AION_LIBRARY_SHELL_PREVIEW"',src)
        self.assertIn('"ATLASQUANT_ENV"',src)


if __name__ == "__main__": unittest.main()
