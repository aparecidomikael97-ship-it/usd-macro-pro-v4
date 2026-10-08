"""Offline adversarial tests: owner host entry and same-session navigation."""
from datetime import datetime
import unittest

from atlasquant_aion_owner_host_entry_navigation_bridge_v1 import (
    SCHEMA, prepare_owner_host_entry, route_owner_text_navigation,
)


def admin(**overrides):
    session = {
        "username": "mikael", "role": "ADMIN",
        "permissions": ["app:read", "aion:admin"],
        "credential_fingerprint": "synthetic-fingerprint",
    }
    session.update(overrides.pop("session", {}))
    result = {"allowed": True, "mode": "AUTHENTICATED", "role": "ADMIN", "session": session}
    result.update(overrides)
    return result


def owner(**overrides):
    assertion = {
        "verified": True, "principal": "HUMAN_OWNER",
        "subject": "mikael", "issuer": "trusted-test-issuer",
    }
    assertion.update(overrides)
    return assertion


def route(text, *, access=None, assertion=None, trusted=True, device="DESKTOP", session=None):
    state = {} if session is None else session
    result = route_owner_text_navigation(
        state, admin() if access is None else access,
        owner() if assertion is None else assertion,
        trusted_host_owner=trusted, text=text, device=device,
    )
    return state, result


class OwnerHostEntryAndNavigationTests(unittest.TestCase):
    def test_entry_requires_explicit_host_trust(self):
        result = prepare_owner_host_entry(admin(), owner())
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["reason"], "TRUSTED_OWNER_HOST_REQUIRED")
        self.assertNotIn("greeting_text", result)

    def test_true_boolean_required_not_truthy_string(self):
        result = prepare_owner_host_entry(admin(), owner(), trusted_host_owner="true")
        self.assertEqual(result["reason"], "TRUSTED_OWNER_HOST_REQUIRED")

    def test_owner_binding_requires_verified_assertion(self):
        for assertion in (
            None,
            owner(verified=False),
            owner(principal="ADMIN"),
            owner(subject="other"),
            owner(issuer=""),
        ):
            with self.subTest(assertion=assertion):
                result = prepare_owner_host_entry(
                    admin(), assertion, trusted_host_owner=True,
                )
                self.assertEqual(result["reason"], "HUMAN_OWNER_BINDING_REQUIRED")

    def test_admin_alone_is_never_owner(self):
        result = prepare_owner_host_entry(admin(), None, trusted_host_owner=True)
        self.assertFalse(result["owner_ready"])

    def test_denied_role_and_session_fail_closed(self):
        for access in (
            admin(allowed=False), admin(mode="PREVIEW"), admin(role="USER"),
            admin(session={"role": "USER"}), admin(session={"credential_fingerprint": ""}),
            admin(session={"permissions": ["app:read"]}),
            None,
        ):
            with self.subTest(access=access):
                result = prepare_owner_host_entry(
                    access, owner(), trusted_host_owner=True,
                )
                self.assertEqual(result["state"], "BLOCKED")

    def test_valid_entry_greeting_is_display_only(self):
        result = prepare_owner_host_entry(
            admin(), owner(), trusted_host_owner=True,
            now=datetime(2026, 10, 8, 9, 0), timezone_name="America/Cuiaba",
        )
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["state"], "OWNER_ENTRY_READY")
        self.assertTrue(result["owner_ready"])
        self.assertIn("Mikael", result["greeting_text"])
        self.assertIn("bom dia", result["greeting_text"].casefold())
        self.assertTrue(result["binding_digest"].startswith("sha256:"))
        self.assertTrue(result["greeting_display_only"])
        for key in ("greeting_spoken", "microphone_active", "external_action_authorized", "execution_confirmed", "executes_external_action"):
            self.assertFalse(result[key], key)

    def test_entry_does_not_return_credentials_or_raw_assertion(self):
        result = prepare_owner_host_entry(
            admin(session={"credential_fingerprint": "do-not-expose"}),
            owner(), trusted_host_owner=True,
        )
        self.assertNotIn("do-not-expose", repr(result))
        self.assertNotIn("trusted-test-issuer", repr(result))

    def test_owner_attestation_required_to_route(self):
        for trust, access, assertion, reason in (
            (False, admin(), owner(), "TRUSTED_OWNER_HOST_REQUIRED"),
            ("yes", admin(), owner(), "TRUSTED_OWNER_HOST_REQUIRED"),
            (True, admin(), None, "HUMAN_OWNER_BINDING_REQUIRED"),
            (True, admin(allowed=False), owner(), "HUMAN_OWNER_BINDING_REQUIRED"),
            (True, admin(session={"permissions": []}), owner(), "HUMAN_OWNER_BINDING_REQUIRED"),
            (True, admin(), owner(subject="other"), "HUMAN_OWNER_BINDING_REQUIRED"),
        ):
            with self.subTest(reason=reason,trust=trust,assertion=assertion):
                state = {}
                response = route_owner_text_navigation(
                    state, access, assertion,
                    trusted_host_owner=trust, text="AION, abre Trader", device="DESKTOP",
                )
                self.assertEqual(response["reason"], reason)
                self.assertEqual(state, {})

    def test_supported_internal_navigation_desktop_and_mobile(self):
        examples = {
            "AION, abre Trader": "trader",
            "AION abre a aba Trader": "trader",
            "abre negócios": "negocios",
            "AION entra no AtlasQuant": "central",
            "AION, abre Investimentos": "investimentos",
            "abre AION": "aion",
        }
        for device in ("MOBILE", "DESKTOP"):
            for prompt, target in examples.items():
                with self.subTest(device=device,prompt=prompt):
                    state, response = route(prompt, device=device)
                    self.assertEqual(response["state"], "INTERNAL_NAVIGATION_REQUESTED", response)
                    self.assertEqual(response["target"], target)
                    self.assertTrue(response["navigation_requested"])
                    self.assertFalse(response["navigation_confirmed"])
                    self.assertFalse(response["execution_confirmed"])
                    self.assertFalse(response["external_action_authorized"])
                    self.assertNotEqual(state, {})

    def test_business_reuses_existing_workspace_bridge(self):
        state, result = route("AION, abre Negócios")
        self.assertEqual(result["target"], "negocios")
        self.assertEqual(state["aion_admin_workspace_jump"], "💼 Negócios")

    def test_atlasquant_targets_central_root(self):
        state, result = route("entra no AtlasQuant")
        self.assertEqual(result["target"], "central")
        self.assertEqual(state["atlasquant_central_choice"], "central_root")

    def test_trader_uses_existing_radar_request(self):
        state, result = route("abre trader")
        self.assertEqual(result["target"], "trader")
        self.assertEqual(state["atlasquant_guided_revalidation_request"]["surface"], "home_radar")

    def test_advanced_trader_respects_current_mode(self):
        state = {"atlasquant_experience_mode": "Avançado"}
        _, result = route("abre Trader",session=state)
        self.assertEqual(result["state"], "INTERNAL_NAVIGATION_REQUESTED")
        self.assertEqual(state["atlasquant_guided_revalidation_request"]["surface"], "advanced_radar")

    def test_external_apps_are_not_dispatched(self):
        for text in (
            "AION abre ChatGPT", "abre WhatsApp", "abre Spotify",
            "AION abre Spotify e toca sertanejo", "abra o Google Chrome",
            "abre powershell", "abre cmd",
        ):
            with self.subTest(text=text):
                state, result = route(text)
                self.assertEqual(result["reason"], "INTERNAL_SINGLE_NAVIGATION_ONLY")
                self.assertEqual(state, {})

    def test_high_risk_and_compound_commands_rejected(self):
        for text in (
            "abre trader e faz pix", "abre trader; apagar arquivos",
            "abre trader e abre whatsapp", "abre investimentos e compra 10 ações",
            "abre atlasquant depois transfere dinheiro",
            "abre trader\nabre spotify", "abre /trader", "abre trader?",
            "abre central", "navega para trader",
            "AION abre trader e faz deploy",
        ):
            with self.subTest(text=text):
                state, result = route(text)
                self.assertEqual(result["state"], "BLOCKED", result)
                self.assertEqual(state, {})

    def test_injection_cannot_bypass_exact_grammar(self):
        for text in (
            "aion aion abre trader", "aion, abre trader --force",
            "abre trader or 1=1", "abre http://trader", "abre trader\\",
            "abre trader\x00", "abre trader. pronto", "abre tradeR <script>",
        ):
            with self.subTest(text=text):
                state, result = route(text)
                self.assertEqual(result["state"], "BLOCKED")
                self.assertEqual(state, {})

    def test_invalid_device_and_missing_command_are_blocked(self):
        for device in ("TABLET", "WEB", "", True, None):
            with self.subTest(device=device):
                state, result = route("abre trader",device=device)
                self.assertEqual(result["reason"], "SUPPORTED_DEVICE_REQUIRED")
                self.assertEqual(state, {})
        for text in ("", " "*10, "a"*161, None, True):
            with self.subTest(text=text):
                state, result = route(text)
                self.assertEqual(result["state"], "BLOCKED")
                self.assertEqual(state, {})

    def test_untrusted_session_state_denied_without_write(self):
        result = route_owner_text_navigation(
            None, admin(), owner(), trusted_host_owner=True,
            text="abre trader", device="DESKTOP",
        )
        self.assertEqual(result["reason"], "TRUSTED_SESSION_STATE_REQUIRED")

    def test_route_unknown_type_not_interpreted_as_command(self):
        for value in ({"text":"abre trader"},["abre trader"],0):
            with self.subTest(value=value):
                state, result = route(value)
                self.assertEqual(result["state"], "BLOCKED")
                self.assertEqual(state, {})

    def test_navigation_does_not_claim_physical_completion(self):
        _, result = route("AION abre investimentos")
        self.assertFalse(result["navigation_confirmed"])
        self.assertFalse(result["execution_confirmed"])
        self.assertFalse(result["executes_external_action"])
        self.assertFalse(result["auto_retry"])

    def test_state_is_never_used_as_standalone_authority(self):
        state = {"owner_ready": True, "authenticated": True}
        result = route_owner_text_navigation(
            state, admin(), owner(verified=False), trusted_host_owner=True,
            text="abre Trader", device="DESKTOP",
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(state, {"owner_ready": True, "authenticated": True})


if __name__ == "__main__":
    unittest.main()
