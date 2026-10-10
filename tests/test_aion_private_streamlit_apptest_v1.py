"""Real Streamlit AppTest login/session/policy isolation, synthetic data only."""
from __future__ import annotations

import json
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from atlasquant_access_control import hash_password
from atlasquant_private_read_gate_v1 import PENDING_KEYS, QUARANTINE_KEY, SCOPE_KEY

FIXTURE = Path(__file__).with_name("aion_private_streamlit_apptest_app_v1.py")
PRIVATE_MARKER = "A_PRIVATE_SAMPLE_DO_NOT_SHOW_TO_B"
PASSWORD_A = "Synthetic-A-Secret-123!"
PASSWORD_B = "Synthetic-B-Secret-123!"


class PrivateSessionAppTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Deterministic development-only hashes. They cannot unlock any real
        # account and are never sent outside this in-process AppTest.
        password_a = hash_password(PASSWORD_A, salt=b"fixture-salt-a00", iterations=200000)
        password_b = hash_password(PASSWORD_B, salt=b"fixture-salt-b00", iterations=200000)
        cls.user_registry = json.dumps({"users": {
            "admin.aaa": {"role": "ADMIN", "password_hash": password_a, "active": True},
            "admin.bbb": {"role": "ADMIN", "password_hash": password_b, "active": True},
        }})

    def setUp(self):
        self.environment = patch.dict(os.environ, {
            "ATLASQUANT_ENV": "TEST",
            "ATLASQUANT_AUTH_REQUIRED": "true",
            "ATLASQUANT_BOOTSTRAP_PREVIEW": "false",
            "ATLASQUANT_USERS_JSON": self.user_registry,
            "ATLASQUANT_PRIVATE_MEMBERSHIPS_JSON": json.dumps({"tenant_one": ["admin.aaa", "admin.bbb"]}),
            "ATLASQUANT_PRIVATE_WORKSPACE_ID": "tenant_one",
            "ATLASQUANT_PRIVATE_POLICY_GENERATION": "7",
            # No GitHub tokens or private credentials are available to this test.
            "GITHUB_TOKEN_HISTORICO": "",
            "GITHUB_TOKEN": "",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.http = patch("requests.sessions.Session.request",
                          side_effect=AssertionError("NETWORK_FORBIDDEN"))
        self.http.start()
        self.addCleanup(self.http.stop)

    @staticmethod
    def button(at, key):
        buttons = [item for item in at.button if item.key == key]
        if len(buttons) != 1:
            raise AssertionError("Expected one Streamlit button " + key
                                 + ", found " + repr([(b.label, b.key) for b in at.button]))
        return buttons[0]

    @staticmethod
    def text_input(at, label):
        fields = [item for item in at.text_input if item.label == label]
        if len(fields) != 1:
            raise AssertionError("Expected one Streamlit text input " + label)
        return fields[0]

    @staticmethod
    def rendered(at):
        return "\n".join(str(x.value) for x in at.text)

    def run_app(self):
        at = AppTest.from_file(str(FIXTURE), default_timeout=30).run()
        self.assertEqual(list(at.exception), [], list(at.exception))
        return at

    def login(self, at, username, password):
        self.text_input(at, "Usuário").set_value(username)
        self.text_input(at, "Senha").set_value(password)
        submit = [b for b in at.button if b.label == "Entrar"]
        self.assertEqual(len(submit), 1, [(b.label, b.key) for b in at.button])
        submit[0].click().run()
        self.assertFalse(list(at.exception), list(at.exception))
        return at

    def seed(self, at):
        self.button(at, "fixture_private_seed").click().run()
        self.assertFalse(list(at.exception), list(at.exception))
        self.assertIn(PRIVATE_MARKER, self.rendered(at))
        self.assertTrue(at.session_state.get(SCOPE_KEY))

    def test_A_logout_B_login_same_workspace_never_reuses_A_cached_data(self):
        at = self.run_app()
        self.assertNotIn("PRIVATE_READ=ALLOWED", self.rendered(at))
        self.login(at, "admin.aaa", PASSWORD_A)
        self.assertIn("PRIVATE_READ=ALLOWED", self.rendered(at))
        self.seed(at)
        a_scope = at.session_state[SCOPE_KEY]
        self.button(at, "atlasquant_logout").click().run()
        self.assertFalse(list(at.exception), list(at.exception))
        self.assertNotIn(PRIVATE_MARKER, self.rendered(at))
        self.assertNotIn("atlasquant_shadow_samples", at.session_state)
        self.login(at, "admin.bbb", PASSWORD_B)
        self.assertIn("PRIVATE_READ=ALLOWED", self.rendered(at))
        self.assertNotIn(PRIVATE_MARKER, self.rendered(at))
        self.assertNotIn("atlasquant_shadow_samples", at.session_state)
        self.assertNotEqual(a_scope, at.session_state[SCOPE_KEY])

    def test_policy_generation_rotation_evicts_old_cached_private_rows(self):
        at = self.login(self.run_app(), "admin.aaa", PASSWORD_A)
        self.seed(at)
        old_scope = at.session_state[SCOPE_KEY]
        os.environ["ATLASQUANT_PRIVATE_POLICY_GENERATION"] = "8"
        at.run()
        self.assertFalse(list(at.exception), list(at.exception))
        self.assertIn("PRIVATE_READ=ALLOWED", self.rendered(at))
        self.assertNotIn(PRIVATE_MARKER, self.rendered(at))
        self.assertNotEqual(old_scope, at.session_state[SCOPE_KEY])

    def test_session_idle_expiry_evicts_old_rows_and_requires_login(self):
        at = self.login(self.run_app(), "admin.aaa", PASSWORD_A)
        self.seed(at)
        session = dict(at.session_state["atlasquant_access_session"])
        session["authenticated_at"] = time.time() - 10810
        session["last_seen"] = time.time() - 10800
        at.session_state["atlasquant_access_session"] = session
        at.run()
        self.assertFalse(list(at.exception), list(at.exception))
        self.assertNotIn(PRIVATE_MARKER, self.rendered(at))
        self.assertNotIn("atlasquant_shadow_samples", at.session_state)
        self.assertNotIn("atlasquant_access_session", at.session_state)
        self.assertNotIn("PRIVATE_READ=ALLOWED", self.rendered(at))

    def test_revoked_A_session_evicts_private_rows_without_B_hydration(self):
        at = self.login(self.run_app(), "admin.aaa", PASSWORD_A)
        self.seed(at)
        configured = json.loads(self.user_registry)
        configured["users"]["admin.aaa"]["active"] = False
        os.environ["ATLASQUANT_USERS_JSON"] = json.dumps(configured)
        at.run()
        self.assertFalse(list(at.exception), list(at.exception))
        self.assertNotIn(PRIVATE_MARKER, self.rendered(at))
        self.assertNotIn("atlasquant_shadow_samples", at.session_state)
        self.assertNotIn("PRIVATE_READ=ALLOWED", self.rendered(at))

    def test_AUTH_REQUIRED_false_does_not_grant_private_read_or_cache(self):
        os.environ["ATLASQUANT_AUTH_REQUIRED"] = "false"
        at = self.run_app()
        at.session_state["atlasquant_shadow_samples"] = [{"secret": PRIVATE_MARKER}]
        at.session_state["atlasquant_shadow_hydrated"] = True
        at.run()
        self.assertFalse(list(at.exception), list(at.exception))
        self.assertIn("PRIVATE_READ=DENIED", self.rendered(at))
        self.assertNotIn(PRIVATE_MARKER, self.rendered(at))
        self.assertNotIn("atlasquant_shadow_samples", at.session_state)

    def test_session_only_research_capture_does_not_reseed_denied_cache(self):
        os.environ["ATLASQUANT_AUTH_REQUIRED"] = "false"
        at = self.run_app()
        self.button(at, "fixture_local_capture").click().run()
        self.assertFalse(list(at.exception), list(at.exception))
        self.assertIn("LOCAL_CAPTURE=ACCESS_DENIED", self.rendered(at))
        self.assertNotIn("atlasquant_research_evidence_records", at.session_state)

    def test_uncertain_A_write_survives_as_quarantine_but_never_leaks_to_B(self):
        at = self.login(self.run_app(), "admin.aaa", PASSWORD_A)
        self.seed(at)
        at.session_state["atlasquant_shadow_persistence_status"] = {
            "reason": "UNKNOWN_OUTCOME", "write_attempted": True,
            "reconciliation_required": True,
        }
        self.button(at, "atlasquant_logout").click().run()
        self.assertFalse(list(at.exception), list(at.exception))
        self.assertTrue(at.session_state[QUARANTINE_KEY])
        self.assertEqual(at.session_state[PENDING_KEYS[0]]["reason"], "UNKNOWN_OUTCOME")
        self.assertNotIn(PRIVATE_MARKER, self.rendered(at))
        self.login(at, "admin.bbb", PASSWORD_B)
        self.assertIn("PRIVATE_READ=DENIED", self.rendered(at))
        self.assertNotIn(PRIVATE_MARKER, self.rendered(at))
        self.assertNotIn("atlasquant_shadow_samples", at.session_state)

    def test_A_tenant_switch_to_B_tenant_denies_old_scope_then_grants_B_clean_scope(self):
        os.environ["ATLASQUANT_PRIVATE_MEMBERSHIPS_JSON"] = json.dumps({
            "tenant_one": ["admin.aaa"],
            "tenant_two": ["admin.bbb"],
        })
        at = self.login(self.run_app(), "admin.aaa", PASSWORD_A)
        self.seed(at)
        a_scope = at.session_state[SCOPE_KEY]
        # Switching server-side tenant with A still logged in is never a
        # migration of cached A data into B's workspace.
        os.environ["ATLASQUANT_PRIVATE_WORKSPACE_ID"] = "tenant_two"
        at.run()
        self.assertFalse(list(at.exception), list(at.exception))
        self.assertIn("PRIVATE_READ=DENIED", self.rendered(at))
        self.assertNotIn(PRIVATE_MARKER, self.rendered(at))
        self.assertNotIn("atlasquant_shadow_samples", at.session_state)
        self.button(at, "atlasquant_logout").click().run()
        self.login(at, "admin.bbb", PASSWORD_B)
        self.assertIn("PRIVATE_READ=ALLOWED", self.rendered(at))
        self.assertNotIn(PRIVATE_MARKER, self.rendered(at))
        self.assertNotIn("atlasquant_shadow_samples", at.session_state)
        self.assertNotEqual(a_scope, at.session_state[SCOPE_KEY])



if __name__ == "__main__":
    unittest.main()
