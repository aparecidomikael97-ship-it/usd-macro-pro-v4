import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from atlasquant_aion_clock import greeting_period
from atlasquant_aion_workspaces import (
    AION_PERSONAS,
    NEVER_FROM_WORKSPACE,
    admin_brief_lines,
    admin_greeting,
    authorize_workspace_action,
    capability_snapshot,
    developer_step_allowed,
    developer_trust_policy,
    greeting_for,
    persona_for_workspace,
    workspace_context_key,
)

ADMIN = {"role": "ADMIN", "session": {"username": "mikael", "role": "ADMIN"}}
USER = {"role": "USER", "session": {"username": "cliente", "role": "USER"}}


class PersonaTests(unittest.TestCase):
    def test_personas_map_to_existing_console_workspaces(self):
        from atlasquant_aion_admin import AION_WORKSPACES
        self.assertEqual(
            [p["id"] for p in AION_PERSONAS],
            ["trader", "admin", "developer", "video", "business", "laboratory", "investments", "central"],
        )
        for item in AION_PERSONAS:
            if item["id"] == "investments":
                self.assertEqual(item["workspace"], "Investimentos")
            else:
                self.assertIn(item["workspace"], AION_WORKSPACES)
            self.assertEqual(persona_for_workspace(item["workspace"])["id"], item["id"])

    def test_context_keys_are_isolated_per_persona(self):
        a = workspace_context_key("trader", "last question")
        b = workspace_context_key("developer", "last question")
        self.assertNotEqual(a, b)
        self.assertTrue(a.startswith("aion_ctx::trader::"))
        with self.assertRaises(KeyError):
            workspace_context_key("root", "x")
        with self.assertRaises(ValueError):
            workspace_context_key("trader", "  ")

    def test_no_persona_scope_contains_forbidden_actions(self):
        for item in AION_PERSONAS:
            self.assertFalse(set(item["actions"]) & NEVER_FROM_WORKSPACE, item["id"])

    def test_capabilities_are_connected_only_with_explicit_runtime_evidence(self):
        snapshot = capability_snapshot("trader", {
            "radar": {"truth_state": "CONFIRMED", "source": "atlasquant_radar_board"},
            "macro": True,
            "risk": False,
        })
        self.assertEqual(snapshot["persona"], "trader")
        self.assertEqual(snapshot["connected"], 2)
        self.assertFalse(snapshot["executes_action"])
        self.assertFalse(snapshot["real_orders_enabled"])
        states = {row["capability"]: row["state"] for row in snapshot["capabilities"]}
        self.assertEqual(states["radar"], "CONNECTED")
        self.assertEqual(states["risk"], "UNAVAILABLE")
        self.assertEqual(states["calendar"], "UNAVAILABLE")
        self.assertEqual(capability_snapshot("root", {})["state"], "BLOCKED")


class AuthorizationTests(unittest.TestCase):
    def test_real_trade_merge_deploy_and_secrets_are_always_denied(self):
        flags = {k: True for k in ("real_broker_execution", "production_deploy", "auto_merge")}
        for pid in [p["id"] for p in AION_PERSONAS]:
            for action in NEVER_FROM_WORKSPACE:
                out = authorize_workspace_action(pid, action, ADMIN, approved=True, feature_flags=flags)
                self.assertFalse(out["allowed"], (pid, action))
                self.assertFalse(out["executes_action"])

    def test_out_of_scope_action_is_denied_even_for_admin(self):
        out = authorize_workspace_action("trader", "publish_social", ADMIN, approved=True,
                                         feature_flags={"social_publish": True})
        self.assertFalse(out["allowed"])
        self.assertEqual(out["layer"], "scope")

    def test_scope_never_widens_guardian(self):
        out = authorize_workspace_action("video", "publish_social", ADMIN, approved=True)
        self.assertFalse(out["allowed"])
        self.assertEqual(out["layer"], "guardian")
        out = authorize_workspace_action("admin", "save_checkpoint", ADMIN, approved=False)
        self.assertFalse(out["allowed"])

    def test_non_admin_cannot_use_sensitive_actions(self):
        out = authorize_workspace_action("admin", "save_checkpoint", USER, approved=True)
        self.assertFalse(out["allowed"])

    def test_unknown_persona_fails_closed(self):
        self.assertFalse(authorize_workspace_action("god", "read", ADMIN)["allowed"])

    def test_read_is_allowed_for_admin(self):
        self.assertTrue(authorize_workspace_action("trader", "read", ADMIN)["allowed"])


class GreetingTests(unittest.TestCase):
    def test_workspace_and_central_share_one_clock(self):
        cuiaba = ZoneInfo("America/Cuiaba")
        samples = (
            (datetime(2026, 9, 27, 11, 59, tzinfo=cuiaba), "Bom dia"),
            (datetime(2026, 9, 27, 12, 0, tzinfo=cuiaba), "Boa tarde"),
            (datetime(2026, 9, 27, 17, 59, tzinfo=cuiaba), "Boa tarde"),
            (datetime(2026, 9, 27, 18, 0, tzinfo=cuiaba), "Boa noite"),
            (datetime(2026, 9, 27, 11, 0, tzinfo=timezone.utc), "Bom dia"),
            (datetime(2026, 9, 27, 17, 0, tzinfo=timezone.utc), "Boa tarde"),
            (datetime(2026, 9, 27, 23, 30, tzinfo=timezone.utc), "Boa noite"),
            (datetime(2026, 9, 27, 4, 0, tzinfo=timezone.utc), "Boa noite"),
            (datetime(2026, 9, 27, 18, 0), "Boa noite"),
        )
        for moment, expected in samples:
            with self.subTest(moment=moment.isoformat()):
                self.assertEqual(greeting_for(moment, timezone_name="America/Cuiaba"), expected)
                self.assertEqual(greeting_period(moment, timezone_name="America/Cuiaba"), expected)
                self.assertEqual(
                    greeting_for(moment, timezone_name="America/Cuiaba"),
                    greeting_period(moment, timezone_name="America/Cuiaba"),
                )
        split = datetime(2026, 6, 15, 15, 30, tzinfo=timezone.utc)
        self.assertEqual(greeting_for(split, timezone_name="Not/AZone"), "Bom dia")
        self.assertEqual(greeting_period(split, timezone_name="Not/AZone"), "Bom dia")
        with patch.dict(os.environ, {"ATLASQUANT_TIMEZONE": "Invalid/Zone"}):
            self.assertEqual(greeting_for(split), greeting_period(split))
            self.assertEqual(greeting_for(split), "Bom dia")
        source = Path("atlasquant_aion_workspaces.py").read_text(encoding="utf-8")
        self.assertNotIn("timedelta(hours=-3)", source)
        self.assertIn("return greeting_period(now, timezone_name=timezone_name)", source)
        self.assertNotIn("real_orders_enabled = True", source)
        self.assertNotIn("save_checkpoint", source)

    def test_greeting_is_admin_only(self):
        now = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(admin_greeting(ADMIN, "Mikael", now), "Bom dia, Mikael.")
        self.assertEqual(admin_greeting(USER, "Mikael", now), "")
        self.assertEqual(admin_greeting(ADMIN, "", now), "Bom dia, Administrador.")

    def test_brief_never_invents_missing_counts(self):
        lines = admin_brief_lines({})
        self.assertIn("Runtime: não confirmado.", lines)
        self.assertTrue(any("não confirmado" in x and "Aprovação" in x for x in lines))
        self.assertEqual(lines[-1], "Ordens reais: bloqueadas.")
        lines = admin_brief_lines({"runtime_status": "CONFIRMED", "approval_count": 2, "incident_count": True,
                                   "primary": {"next_action": "Revisar checks."}})
        self.assertIn("Runtime: CONFIRMED.", lines)
        self.assertIn("2 aprovação(ões) pendente(s).", lines)
        self.assertTrue(any(x.startswith("Incidente(s) aberto(s): não confirmado") for x in lines))
        self.assertIn("Próxima ação sugerida: Revisar checks.", lines)


class DeveloperPolicyTests(unittest.TestCase):
    def test_policy_never_allows_auto_merge_deploy_or_self_escalation(self):
        policy = developer_trust_policy()
        self.assertFalse(policy["auto_merge"])
        self.assertFalse(policy["auto_deploy"])
        self.assertFalse(policy["self_escalation"])
        self.assertEqual(policy["max_autonomous_level"], 1)
        self.assertTrue(any("Merge automático" in x for x in policy["forbidden"]))
        self.assertTrue(any("git revert" in x for x in policy["rollback"]))

    def test_levels_above_draft_need_a_human(self):
        self.assertTrue(developer_step_allowed(0))
        self.assertTrue(developer_step_allowed(1))
        self.assertFalse(developer_step_allowed(2))
        self.assertTrue(developer_step_allowed(2, human_approved=True))
        self.assertFalse(developer_step_allowed(4, human_approved=True))
        self.assertFalse(developer_step_allowed("x", human_approved=True))
        for flag in ("false", "true", "yes", "no", 1, 0, None):
            self.assertFalse(developer_step_allowed(2, human_approved=flag))
        self.assertFalse(developer_step_allowed(True))
        self.assertFalse(developer_step_allowed(False, human_approved=True))
        self.assertFalse(developer_step_allowed("2", human_approved=True))


class ConsoleWiringTests(unittest.TestCase):
    def test_console_renders_brief_policy_and_session_username(self):
        from atlasquant_aion_admin import _display_name
        src = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("_render_admin_brief(access_map, executive_snapshot)", src)
        self.assertIn("Política de confiança e rollback do AION Desenvolvedor", src)
        self.assertIn("Personas AION e onde cada uma trabalha", src)
        from unittest import mock
        with mock.patch("atlasquant_aion_admin._secret", return_value=""):
            self.assertEqual(_display_name(ADMIN), "mikael")
            self.assertEqual(_display_name({"role": "ADMIN"}), "Administrador")
        with mock.patch("atlasquant_aion_admin._secret", return_value="Mikael"):
            self.assertEqual(_display_name(ADMIN), "Mikael")


if __name__ == "__main__":
    unittest.main()
