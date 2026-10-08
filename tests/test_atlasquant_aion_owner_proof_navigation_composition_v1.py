"""Offline adversarial composition checks: ephemeral owner key, temporary nonce DB."""
from __future__ import annotations

import base64
from dataclasses import replace
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from atlasquant_aion_owner_proof_navigation_composition_v1 import (
    TrustedOwnerHostPolicy, plan_verified_owner_greeting,
    request_verified_owner_navigation,
)
from atlasquant_aion_trusted_owner_host_crypto_proof_v1 import (
    SCHEMA, PURPOSE, SQLiteOwnerNonceRegistry, signing_message,
)


def digest(data: bytes) -> str:
    return "sha256:" + sha256(data).hexdigest()


class OwnerProofNavigationCompositionTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(prefix="aion-ci-composition-")
        self.addCleanup(temp.cleanup)
        self.db_path = str(Path(temp.name) / "consumed.sqlite3")
        self.signer = Ed25519PrivateKey.generate()
        self.pub = self.signer.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.session = digest(b"host-authenticated-session-fixture")
        self.device = digest(b"host-registered-device-fixture")
        self.now = 2000000000
        self.policy = TrustedOwnerHostPolicy(
            pinned_owner_public_key=self.pub,
            expected_pinned_key_fingerprint=digest(self.pub),
            expected_session_binding_digest=self.session,
            expected_device_binding_digest=self.device,
            expected_issuer="ci-owner-issuer",
            expected_audience="aion-host-ci",
            device="DESKTOP",
            nonce_registry=SQLiteOwnerNonceRegistry(self.db_path),
        )
        self.access = {
            "allowed": True, "mode": "AUTHENTICATED", "role": "ADMIN",
            "session": {
                "username": "mikael", "role": "ADMIN",
                "permissions": ["app:read", "aion:admin"],
                "credential_fingerprint": "ci-only-nonsecret",
            },
        }
        self.payload = {
            "schema": SCHEMA, "purpose": PURPOSE, "principal": "HUMAN_OWNER",
            "subject": "mikael", "issuer": "ci-owner-issuer",
            "audience": "aion-host-ci",
            "session_binding_digest": self.session,
            "device_binding_digest": self.device,
            "key_fingerprint": digest(self.pub),
            "nonce": "c" * 64, "issued_at": self.now,
            "expires_at": self.now + 110,
        }

    def sign(self, p=None, signer=None):
        p = self.payload if p is None else p
        signer = self.signer if signer is None else signer
        return base64.b64encode(signer.sign(signing_message(p))).decode("ascii")

    def request(self, text="AION, abre Trader", *, state=None, payload=None,
                signature=None, access=None, policy=None, now=None):
        state = {} if state is None else state
        r = request_verified_owner_navigation(
            state, self.access if access is None else access,
            self.payload if payload is None else payload,
            self.sign() if signature is None else signature,
            policy=self.policy if policy is None else policy,
            now_epoch=self.now + 10 if now is None else now,
            text=text,
        )
        return state, r

    def assert_denied_unchanged(self, state, result):
        self.assertEqual(result["state"], "BLOCKED")
        self.assertFalse(result["owner_ready"])
        self.assertFalse(result["navigation_requested"])
        self.assertFalse(result["external_action_authorized"])
        self.assertFalse(result["execution_confirmed"])
        self.assertFalse(result["trusted_host_attached"])
        self.assertEqual(state, {})

    def test_signed_owner_requests_only_navigation_not_execution(self):
        state, r = self.request()
        self.assertEqual(r["state"], "INTERNAL_NAVIGATION_REQUESTED", r)
        self.assertEqual(r["target"], "trader")
        self.assertTrue(r["proof_consumed"])
        self.assertFalse(r["navigation_confirmed"])
        self.assertFalse(r["execution_confirmed"])
        self.assertFalse(r["external_action_authorized"])
        self.assertNotIn("owner_assertion", r)
        self.assertNotEqual(state, {})

    def test_valid_greeting_is_display_only(self):
        r = plan_verified_owner_greeting(
            self.access, self.payload, self.sign(),
            policy=self.policy, now_epoch=self.now + 10,
            now=datetime(2026, 10, 8, 9, 0),
            timezone_name="America/Cuiaba",
        )
        self.assertEqual(r["state"], "OWNER_ENTRY_READY")
        self.assertTrue(r["greeting_display_only"])
        self.assertFalse(r["greeting_spoken"])
        self.assertFalse(r["microphone_active"])
        self.assertFalse(r["trusted_host_attached"])
        self.assertFalse(r["navigation_confirmed"])
        self.assertIn("Mikael", r["greeting_text"])
        self.assertNotIn("owner_assertion", r)

    def test_replay_of_same_proof_blocks_navigation(self):
        self.assertEqual(self.request()[1]["state"], "INTERNAL_NAVIGATION_REQUESTED")
        state, r = self.request()
        self.assert_denied_unchanged(state, r)
        self.assertEqual(r["proof_reason"], "REPLAY_OR_STORE_FAILURE")

    def test_greeting_proof_cannot_be_reused_for_command(self):
        welcome = plan_verified_owner_greeting(
            self.access, self.payload, self.sign(),
            policy=self.policy, now_epoch=self.now + 10,
        )
        self.assertEqual(welcome["state"], "OWNER_ENTRY_READY")
        state, r = self.request()
        self.assert_denied_unchanged(state, r)

    def test_wrong_signature_or_unpinned_key_denied(self):
        wrong = Ed25519PrivateKey.generate()
        for name, policy, signature in (
            ("wrong_signer", self.policy, self.sign(signer=wrong)),
            ("untrusted_pin", replace(self.policy, expected_pinned_key_fingerprint=digest(b"x")), self.sign()),
        ):
            with self.subTest(name=name):
                state, r = self.request(policy=policy, signature=signature)
                self.assert_denied_unchanged(state, r)

    def test_wrong_session_device_or_issuer_denied(self):
        for field, value in (
            ("expected_session_binding_digest", digest(b"changed")),
            ("expected_device_binding_digest", digest(b"changed")),
            ("expected_issuer", "other-issuer"),
            ("expected_audience", "other-audience"),
        ):
            with self.subTest(field=field):
                state, r = self.request(policy=replace(self.policy, **{field: value}))
                self.assert_denied_unchanged(state, r)

    def test_expired_proof_denied(self):
        state, r = self.request(now=self.now + 140)
        self.assert_denied_unchanged(state, r)
        self.assertEqual(r["proof_reason"], "PROOF_EXPIRED_OR_FUTURE")

    def test_non_owner_admin_denied_without_state_mutation(self):
        access = {
            **self.access, "session": {**self.access["session"], "username": "delegated-admin"}
        }
        state, r = self.request(access=access)
        self.assert_denied_unchanged(state, r)
        self.assertEqual(r["proof_reason"], "AUTHENTICATED_OWNER_SESSION_REQUIRED")

    def test_non_admin_denied(self):
        access = {**self.access, "role": "USER"}
        state, r = self.request(access=access)
        self.assert_denied_unchanged(state, r)

    def test_external_apps_and_multi_commands_never_mutate(self):
        for i, text in enumerate((
            "AION abre WhatsApp", "AION abre Spotify e toca música",
            "abre ChatGPT", "AION, abre Trader; apaga tudo",
            "abre Trader e Investimentos", "https://example.com",
        )):
            with self.subTest(text=text):
                payload = dict(self.payload, nonce=f"{i+1:064x}")
                signature = self.sign(payload)
                state, r = self.request(text, payload=payload, signature=signature)
                self.assert_denied_unchanged(state, r)
                self.assertFalse(r["external_action_authorized"])

    def test_bad_policy_invalid_device_fails_closed(self):
        state, r = self.request(policy=replace(self.policy, device="BROWSER"))
        self.assert_denied_unchanged(state, r)
        self.assertEqual(r["proof_reason"], "TRUSTED_DEVICE_REQUIRED")

    def test_untrusted_policy_object_fails_closed(self):
        state, r = self.request(policy={"device": "DESKTOP"})
        self.assert_denied_unchanged(state, r)
        self.assertEqual(r["proof_reason"], "TRUSTED_HOST_POLICY_REQUIRED")

    def test_no_nonce_registry_fails_closed(self):
        state, r = self.request(policy=replace(self.policy, nonce_registry=None))
        self.assert_denied_unchanged(state, r)
        self.assertEqual(r["proof_reason"], "DURABLE_REPLAY_STORE_REQUIRED")

    def test_bad_command_rejected_before_nonce_is_burned(self):
        state, r = self.request(text=" " * 200)
        self.assert_denied_unchanged(state, r)
        self.assertEqual(r["reason"], "FRESH_SINGLE_TEXT_COMMAND_REQUIRED")
        state, r = self.request()
        self.assertEqual(r["state"], "INTERNAL_NAVIGATION_REQUESTED")

    def test_mobile_uses_trusted_device_and_internal_routes(self):
        policy = replace(self.policy, device="MOBILE")
        state, r = self.request(text="AION, abre Investimentos", policy=policy)
        self.assertEqual(r["state"], "INTERNAL_NAVIGATION_REQUESTED")
        self.assertEqual(r["target"], "investimentos")
        self.assertFalse(r["navigation_confirmed"])

    def test_existing_session_state_unchanged_for_denied_proof(self):
        state = {"user_private_state": "unchanged"}
        r = request_verified_owner_navigation(
            state, self.access, self.payload, self.sign(signer=Ed25519PrivateKey.generate()),
            policy=self.policy, now_epoch=self.now + 10, text="AION, abre Trader",
        )
        self.assertEqual(r["state"], "BLOCKED")
        self.assertEqual(state, {"user_private_state": "unchanged"})

    def test_no_client_selected_device_or_owner_flag_argument(self):
        import inspect
        sig = inspect.signature(request_verified_owner_navigation)
        self.assertNotIn("trusted_host_owner", sig.parameters)
        self.assertNotIn("owner_assertion", sig.parameters)
        self.assertNotIn("device", sig.parameters)


if __name__ == "__main__":
    unittest.main()
