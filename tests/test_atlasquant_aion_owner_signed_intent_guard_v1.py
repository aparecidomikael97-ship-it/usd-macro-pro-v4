"""Adversarial offline integration tests for domain-separated owner UI intent."""
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

from atlasquant_aion_trusted_owner_host_crypto_proof_v1 import (
    SCHEMA as PROOF_SCHEMA,
    PURPOSE as PROOF_PURPOSE,
    SQLiteOwnerNonceRegistry,
    signing_message,
)
from atlasquant_aion_owner_proof_navigation_composition_v1 import TrustedOwnerHostPolicy
from atlasquant_aion_owner_signed_intent_guard_v1 import (
    SCHEMA, PURPOSE, SCOPE_NAV, SCOPE_GREETING,
    signed_intent_message,
    plan_intent_bound_greeting, request_intent_bound_navigation,
)


def digest(data: bytes) -> str:
    return "sha256:" + sha256(data).hexdigest()


class SignedOwnerIntentTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory(prefix="aion-intent-ci-")
        self.addCleanup(tmp.cleanup)
        self.owner = Ed25519PrivateKey.generate()
        self.pub = self.owner.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.now = 2000000000
        self.session_hash = digest(b"host-session-test-only")
        self.device_hash = digest(b"host-device-test-only")
        self.policy = TrustedOwnerHostPolicy(
            pinned_owner_public_key=self.pub,
            expected_pinned_key_fingerprint=digest(self.pub),
            expected_session_binding_digest=self.session_hash,
            expected_device_binding_digest=self.device_hash,
            expected_issuer="ci-host-issuer",
            expected_audience="ci-host-audience",
            device="DESKTOP",
            nonce_registry=SQLiteOwnerNonceRegistry(str(Path(tmp.name) / "nonces.db")),
        )
        self.access = {
            "allowed": True, "mode": "AUTHENTICATED", "role": "ADMIN",
            "session": {
                "username": "mikael", "role": "ADMIN",
                "permissions": ["app:read", "aion:admin"],
                "credential_fingerprint": "ci-not-a-secret",
            },
        }
        self.proof = {
            "schema": PROOF_SCHEMA, "purpose": PROOF_PURPOSE,
            "principal": "HUMAN_OWNER", "subject": "mikael",
            "issuer": "ci-host-issuer", "audience": "ci-host-audience",
            "session_binding_digest": self.session_hash,
            "device_binding_digest": self.device_hash,
            "key_fingerprint": digest(self.pub),
            "nonce": "d" * 64,
            "issued_at": self.now, "expires_at": self.now + 100,
        }

    def intent(self, command="AION, abre Trader", scope=SCOPE_NAV, proof=None):
        proof = self.proof if proof is None else proof
        return {
            "schema": SCHEMA, "purpose": PURPOSE,
            "scope": scope, "command": command,
            "proof_digest": digest(signing_message(proof)),
            "session_binding_digest": proof["session_binding_digest"],
            "device_binding_digest": proof["device_binding_digest"],
            "device": "DESKTOP", "issuer": proof["issuer"],
            "audience": proof["audience"], "nonce": proof["nonce"],
            "issued_at": proof["issued_at"], "expires_at": proof["expires_at"],
        }

    def proof_signature(self, proof=None, signer=None):
        p = self.proof if proof is None else proof
        return base64.b64encode(
            (self.owner if signer is None else signer).sign(signing_message(p))
        ).decode("ascii")

    def intent_signature(self, intent=None, signer=None):
        i = self.intent() if intent is None else intent
        return base64.b64encode(
            (self.owner if signer is None else signer).sign(signed_intent_message(i))
        ).decode("ascii")

    def nav(self, *, text="AION, abre Trader", intent=None, proof=None,
            intent_sig=None, proof_sig=None, policy=None, access=None, now=None):
        p = self.proof if proof is None else proof
        i = self.intent(proof=p) if intent is None else intent
        state = {}
        if intent_sig is None:
            try:
                intent_sig = self.intent_signature(i)
            except (ValueError, TypeError):
                # Reject malformed envelope at verifier, not at test signer.
                intent_sig = self.intent_signature()
        result = request_intent_bound_navigation(
            state, self.access if access is None else access,
            p, self.proof_signature(p) if proof_sig is None else proof_sig,
            i, intent_sig,
            policy=self.policy if policy is None else policy,
            now_epoch=self.now + 10 if now is None else now,
            text=text,
        )
        return state, result

    def greet(self, *, intent=None, proof=None, intent_sig=None):
        p = self.proof if proof is None else proof
        i = self.intent("", scope=SCOPE_GREETING, proof=p) if intent is None else intent
        return plan_intent_bound_greeting(
            self.access, p, self.proof_signature(p),
            i, self.intent_signature(i) if intent_sig is None else intent_sig,
            policy=self.policy, now_epoch=self.now + 10,
            now=datetime(2026, 10, 8, 9, 30), timezone_name="America/Cuiaba",
        )

    def blocked(self, state, result, reason=None):
        self.assertEqual(state, {})
        self.assertEqual(result["state"], "BLOCKED", result)
        if reason:
            self.assertEqual(result["reason"], reason)
        for key in ("signed_intent_bound", "navigation_requested",
                    "navigation_confirmed", "external_action_authorized",
                    "execution_confirmed", "trusted_host_attached"):
            self.assertFalse(result[key], key)

    def test_valid_signed_exact_route_only_request(self):
        state, r = self.nav()
        self.assertEqual(r["state"], "INTERNAL_NAVIGATION_REQUESTED", r)
        self.assertTrue(r["signed_intent_bound"])
        self.assertEqual(r["target"], "trader")
        self.assertEqual(state["atlasquant_central_choice"], "trader")
        self.assertFalse(r["navigation_confirmed"])
        self.assertFalse(r["execution_confirmed"])
        self.assertFalse(r["external_action_authorized"])
        self.assertNotIn("owner_assertion", r)
        self.assertNotIn("signature", r)

    def test_valid_signed_display_only_greeting(self):
        r = self.greet()
        self.assertEqual(r["state"], "OWNER_ENTRY_READY", r)
        self.assertTrue(r["signed_intent_bound"])
        self.assertTrue(r["greeting_display_only"])
        self.assertFalse(r["greeting_spoken"])
        self.assertFalse(r["microphone_active"])
        self.assertFalse(r["trusted_host_attached"])

    def test_command_substitution_with_original_signature_denied(self):
        state, r = self.nav(text="AION, abre Investimentos")
        self.blocked(state, r, "INTENT_COMMAND_MISMATCH")

    def test_normalization_does_not_invalidate_exact_binding(self):
        state, r = self.nav(text="aion, abre trader")
        self.blocked(state, r, "INTENT_COMMAND_MISMATCH")

    def test_sig_for_investments_with_trader_text_denied(self):
        i = self.intent("AION, abre Investimentos")
        state, r = self.nav(intent=i, text="AION, abre Trader")
        self.blocked(state, r, "INTENT_COMMAND_MISMATCH")

    def test_nav_intent_cannot_authorize_greeting(self):
        i = self.intent()
        r = self.greet(intent=i)
        self.assertEqual(r["state"], "BLOCKED")
        self.assertEqual(r["reason"], "WRONG_INTENT_SCOPE")

    def test_greeting_intent_cannot_authorize_navigation(self):
        i = self.intent("", scope=SCOPE_GREETING)
        state, r = self.nav(intent=i)
        self.blocked(state, r, "WRONG_INTENT_SCOPE")

    def test_proof_digest_swap_is_denied(self):
        i = dict(self.intent(), proof_digest=digest(b"other-proof"))
        state, r = self.nav(intent=i)
        self.blocked(state, r, "INTENT_CONTEXT_MISMATCH")

    def test_nonce_swap_is_denied(self):
        i = dict(self.intent(), nonce="f" * 64)
        state, r = self.nav(intent=i)
        self.blocked(state, r, "INTENT_CONTEXT_MISMATCH")

    def test_session_swap_is_denied(self):
        i = dict(self.intent(), session_binding_digest=digest(b"other-session"))
        state, r = self.nav(intent=i)
        self.blocked(state, r, "INTENT_CONTEXT_MISMATCH")

    def test_device_digest_swap_is_denied(self):
        i = dict(self.intent(), device_binding_digest=digest(b"other-device"))
        state, r = self.nav(intent=i)
        self.blocked(state, r, "INTENT_CONTEXT_MISMATCH")

    def test_device_type_swap_is_denied(self):
        i = dict(self.intent(), device="MOBILE")
        state, r = self.nav(intent=i)
        self.blocked(state, r, "INTENT_CONTEXT_MISMATCH")

    def test_issuer_and_audience_mismatch_denied(self):
        for field in ("issuer", "audience"):
            with self.subTest(field=field):
                i = dict(self.intent(), **{field: "attacker"})
                state, r = self.nav(intent=i)
                self.blocked(state, r, "INTENT_CONTEXT_MISMATCH")

    def test_valid_signature_but_wrong_host_pin_denied(self):
        policy = replace(self.policy, expected_pinned_key_fingerprint=digest(b"fake"))
        state, r = self.nav(policy=policy)
        self.blocked(state, r, "HOST_OWNER_KEY_NOT_PINNED")

    def test_attacker_key_not_authorized_under_owner_pin(self):
        attacker = Ed25519PrivateKey.generate()
        state, r = self.nav(intent_sig=self.intent_signature(signer=attacker))
        self.blocked(state, r, "INTENT_SIGNATURE_INVALID")

    def test_signature_from_other_intent_rejected(self):
        i = self.intent("AION, abre Investimentos")
        state, r = self.nav(intent_sig=self.intent_signature(i))
        self.blocked(state, r, "INTENT_SIGNATURE_INVALID")

    def test_noncanonical_and_malformed_signature_rejected(self):
        for sig in ("", "invalid!", "AAAA", "A" * 200, True):
            with self.subTest(sig=sig):
                state, r = self.nav(intent_sig=sig)
                self.blocked(state, r, "INTENT_SIGNATURE_INVALID")

    def test_absent_or_extra_fields_denied(self):
        i = self.intent()
        variants = ({}, {k: v for k, v in i.items() if k != "scope"}, {**i, "authorizes_deploy": True})
        for item in variants:
            with self.subTest(item=str(item)[:60]):
                state, r = self.nav(intent=item)
                self.blocked(state, r, "INTENT_SHAPE_INVALID")

    def test_unrecognized_scope_and_purpose_denied(self):
        for field, value in (("scope", "DEPLOY"), ("purpose", "TRADING_EXECUTION"), ("schema", "V2")):
            with self.subTest(field=field):
                i = dict(self.intent(), **{field: value})
                state, r = self.nav(intent=i)
                self.blocked(state, r, "INTENT_SHAPE_INVALID")

    def test_expiry_and_future_denied_before_proof_consumption(self):
        state, r = self.nav(now=self.now + 150)
        self.blocked(state, r, "INTENT_EXPIRED_OR_FUTURE")
        state, r = self.nav(now=self.now - 1)
        self.blocked(state, r, "INTENT_EXPIRED_OR_FUTURE")
        self.assertEqual(self.nav()[1]["state"], "INTERNAL_NAVIGATION_REQUESTED")

    def test_signed_replay_cannot_navigate_twice(self):
        self.assertEqual(self.nav()[1]["state"], "INTERNAL_NAVIGATION_REQUESTED")
        state, r = self.nav()
        self.blocked(state, r, "OWNER_PROOF_OR_INTERNAL_ROUTE_DENIED")

    def test_signed_greeting_proof_not_reusable_for_nav(self):
        self.assertEqual(self.greet()["state"], "OWNER_ENTRY_READY")
        state, r = self.nav()
        self.blocked(state, r, "OWNER_PROOF_OR_INTERNAL_ROUTE_DENIED")

    def test_untrusted_admin_session_blocks(self):
        access = dict(self.access, session=dict(self.access["session"], username="delegated-admin"))
        state, r = self.nav(access=access)
        self.blocked(state, r, "OWNER_PROOF_OR_INTERNAL_ROUTE_DENIED")

    def test_wrong_owner_signature_blocks_even_with_valid_intent(self):
        wrong = Ed25519PrivateKey.generate()
        state, r = self.nav(proof_sig=self.proof_signature(signer=wrong))
        self.blocked(state, r, "OWNER_PROOF_OR_INTERNAL_ROUTE_DENIED")

    def test_compound_and_external_signed_commands_still_blocked(self):
        for idx, cmd in enumerate((
            "AION abre WhatsApp", "AION abre Spotify",
            "AION, abre Trader e apaga arquivos",
            "AION abre ChatGPT", "AION abre Trader; abre Negocios",
        )):
            with self.subTest(command=cmd):
                proof = dict(self.proof, nonce=f"{idx+1:064x}")
                intent = self.intent(command=cmd, proof=proof)
                state, r = self.nav(proof=proof, intent=intent, text=cmd)
                self.blocked(state, r, "OWNER_PROOF_OR_INTERNAL_ROUTE_DENIED")

    def test_bad_request_does_not_consume_valid_nonce(self):
        state, r = self.nav(text="AION, abre AION")
        self.blocked(state, r, "INTENT_COMMAND_MISMATCH")
        self.assertEqual(self.nav()[1]["state"], "INTERNAL_NAVIGATION_REQUESTED")

    def test_signed_intent_message_does_not_contain_private_key(self):
        msg = signed_intent_message(self.intent())
        self.assertTrue(msg.startswith(b"ATLASQUANT:AION:OWNER_UI_SIGNED_INTENT:V1\x00"))
        self.assertIn(b"NAVIGATE_INTERNAL", msg)
        self.assertNotIn(b"private_key", msg)

    def test_invalid_intent_not_signable(self):
        for changed in (
            {"nonce": "zz" * 32}, {"issued_at": True},
            {"scope": SCOPE_GREETING}, {"command": "A" * 161},
            {"session_binding_digest": digest(b"x")[:-1]},
        ):
            with self.subTest(changed=changed):
                with self.assertRaises(ValueError):
                    signed_intent_message({**self.intent(), **changed})


if __name__ == "__main__":
    unittest.main()
