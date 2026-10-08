"""Security tests for ephemeral owner signature and SQLite nonce replay protocol."""
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from atlasquant_aion_trusted_owner_host_crypto_proof_v1 import (
    SCHEMA, PURPOSE, MAX_TTL_SECONDS, EXPECTED_FIELDS,
    SQLiteOwnerNonceRegistry, signing_message, verify_host_owner_proof,
)
from atlasquant_aion_owner_host_entry_navigation_bridge_v1 import (
    prepare_owner_host_entry, route_owner_text_navigation,
)


def digest(data: bytes) -> str:
    return "sha256:" + sha256(data).hexdigest()


class OwnerHostCryptoProofTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="aion-owner-proof-ci-")
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "owner-nonces.sqlite3")
        self.db = SQLiteOwnerNonceRegistry(self.path)
        self.signer = Ed25519PrivateKey.generate()
        self.pub = self.signer.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.now = 2000000000
        self.session_digest = digest(b"immutable-ci-session-reference")
        self.device_digest = digest(b"immutable-ci-device-reference")
        self.access = {
            "allowed": True, "mode": "AUTHENTICATED", "role": "ADMIN",
            "session": {
                "username": "mikael",
                "role": "ADMIN",
                "permissions": ["app:read", "aion:admin"],
                "credential_fingerprint": "ephemeral-session-test",
            },
        }
        self.payload = {
            "schema": SCHEMA, "purpose": PURPOSE, "principal": "HUMAN_OWNER",
            "subject": "mikael", "issuer": "ci-owner-key-issuer",
            "audience": "atlasquant-owner-host",
            "session_binding_digest": self.session_digest,
            "device_binding_digest": self.device_digest,
            "key_fingerprint": digest(self.pub),
            "nonce": "b" * 64,
            "issued_at": self.now,
            "expires_at": self.now + 110,
        }

    def sign(self, p=None, signer=None):
        return base64.b64encode(
            (signer or self.signer).sign(signing_message(self.payload if p is None else p))
        ).decode("ascii")

    def verify(self, p=None, signature=None, **changes):
        args = dict(
            pinned_owner_public_key=self.pub,
            expected_pinned_key_fingerprint=digest(self.pub),
            expected_session_binding_digest=self.session_digest,
            expected_device_binding_digest=self.device_digest,
            expected_issuer="ci-owner-key-issuer",
            expected_audience="atlasquant-owner-host",
            now_epoch=self.now + 10,
            nonce_registry=self.db,
        )
        args.update(changes)
        target = self.payload if p is None else p
        return verify_host_owner_proof(
            self.access, target,
            self.sign(target) if signature is None else signature,
            **args,
        )

    def test_crypto_proof_happy_path_is_a_review_candidate_only(self):
        r = self.verify()
        self.assertTrue(r["verified"])
        self.assertEqual(r["state"], "CRYPTO_PROOF_VERIFIED_FOR_TRUSTED_HOST_REVIEW")
        self.assertEqual(r["owner_assertion"]["principal"], "HUMAN_OWNER")
        self.assertEqual(r["owner_assertion"]["subject"], "mikael")
        self.assertEqual(r["owner_key_fingerprint"], digest(self.pub))
        for key in (
            "authorizes_execution", "authorizes_deploy", "authorizes_payment",
            "trusted_host_attached",
        ):
            self.assertIs(r[key], False)

    def test_verified_proof_composes_with_safe_owner_entry(self):
        r = self.verify()
        welcome = prepare_owner_host_entry(
            self.access, r["owner_assertion"],
            trusted_host_owner=(r["verified"] is True),
        )
        self.assertEqual(welcome["state"], "OWNER_ENTRY_READY")
        self.assertFalse(welcome["greeting_spoken"])

    def test_verified_proof_composes_with_safe_navigation(self):
        r = self.verify()
        state = {}
        nav = route_owner_text_navigation(
            state, self.access, r["owner_assertion"],
            trusted_host_owner=(r["verified"] is True),
            text="AION, abre Trader", device="MOBILE",
        )
        self.assertEqual(nav["state"], "INTERNAL_NAVIGATION_REQUESTED")
        self.assertEqual(state["atlasquant_central_choice"], "trader")
        self.assertFalse(nav["navigation_confirmed"])

    def test_identical_signed_proof_replay_rejected(self):
        self.assertTrue(self.verify()["verified"])
        r = self.verify()
        self.assertEqual(r["reason"], "REPLAY_OR_STORE_FAILURE")
        self.assertFalse(r["verified"])

    def test_reopen_durable_store_cannot_restore_nonce(self):
        self.assertTrue(self.verify()["verified"])
        fresh = SQLiteOwnerNonceRegistry(self.path)
        r = self.verify(nonce_registry=fresh)
        self.assertEqual(r["reason"], "REPLAY_OR_STORE_FAILURE")

    def test_signed_new_nonce_can_be_consumed(self):
        self.assertTrue(self.verify()["verified"])
        p = dict(self.payload, nonce="c" * 64)
        self.assertTrue(self.verify(p)["verified"])

    def test_wrong_signature_bytes_are_rejected(self):
        sig = self.sign()
        wrong = sig[:10] + ("B" if sig[10] != "B" else "A") + sig[11:]
        self.assertFalse(self.verify(signature=wrong)["verified"])

    def test_attackers_key_cannot_sign_under_pinned_owner_key(self):
        attacker = Ed25519PrivateKey.generate()
        signature = self.sign(signer=attacker)
        self.assertEqual(self.verify(signature=signature)["reason"], "INVALID_OWNER_SIGNATURE")

    def test_rehashed_attackers_key_cannot_change_out_of_band_pin(self):
        attacker = Ed25519PrivateKey.generate()
        raw = attacker.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        p = dict(self.payload, key_fingerprint=digest(raw))
        result = self.verify(
            p, signature=self.sign(p, signer=attacker),
            pinned_owner_public_key=raw,
        )
        self.assertEqual(result["reason"], "UNPINNED_OWNER_KEY")

    def test_replacement_pin_fingerprint_not_accepted(self):
        self.assertEqual(
            self.verify(expected_pinned_key_fingerprint=digest(b"wrong"))["reason"],
            "UNPINNED_OWNER_KEY",
        )

    def test_subject_mismatch_blocks_even_valid_signature(self):
        p = dict(self.payload, subject="other")
        r = self.verify(p)
        self.assertEqual(r["reason"], "AUTHENTICATED_OWNER_SESSION_REQUIRED")

    def test_admin_permission_absence_blocks_even_valid_signature(self):
        self.access["session"]["permissions"] = ["app:read"]
        r = self.verify()
        self.assertEqual(r["reason"], "AUTHENTICATED_OWNER_SESSION_REQUIRED")

    def test_admin_role_is_not_owner_identity(self):
        self.access["session"]["role"] = "ADMIN"
        p = dict(self.payload, principal="ADMIN")
        self.assertEqual(self.verify(p)["reason"], "INVALID_PAYLOAD")

    def test_not_authenticated_access_blocks(self):
        self.access["mode"] = "GUEST"
        self.assertEqual(self.verify()["reason"], "AUTHENTICATED_OWNER_SESSION_REQUIRED")

    def test_disabled_access_blocks(self):
        self.access["allowed"] = False
        self.assertEqual(self.verify()["reason"], "AUTHENTICATED_OWNER_SESSION_REQUIRED")

    def test_no_key_pin_is_rejected(self):
        self.assertEqual(
            self.verify(pinned_owner_public_key=b"")["reason"], "PUBLIC_KEY_INVALID"
        )

    def test_missing_durable_replay_guard_blocks(self):
        self.assertEqual(
            self.verify(nonce_registry=None)["reason"], "DURABLE_REPLAY_STORE_REQUIRED"
        )

    def test_bad_expiry_blocks(self):
        self.assertEqual(
            self.verify(now_epoch=self.now + 150)["reason"], "PROOF_EXPIRED_OR_FUTURE"
        )

    def test_future_issued_proof_blocks(self):
        self.assertEqual(
            self.verify(now_epoch=self.now - 1)["reason"], "PROOF_EXPIRED_OR_FUTURE"
        )

    def test_oversize_ttl_rejected_at_signing_boundary(self):
        p = dict(self.payload, expires_at=self.now + MAX_TTL_SECONDS + 1)
        with self.assertRaises(ValueError):
            signing_message(p)
        self.assertEqual(self.verify(p, signature=self.sign())["reason"], "INVALID_PAYLOAD")

    def test_signature_does_not_survive_payload_tamper(self):
        sig = self.sign()
        for field, replacement in (
            ("subject", "impostor"),
            ("issuer", "other-issuer"),
            ("audience", "evil-audience"),
            ("nonce", "d"*64),
            ("expires_at", self.now+30),
            ("session_binding_digest", digest(b"other")),
            ("device_binding_digest", digest(b"another")),
        ):
            with self.subTest(field=field):
                p = dict(self.payload, **{field: replacement})
                self.assertFalse(self.verify(p, signature=sig)["verified"])

    def test_claimed_session_binding_mismatch(self):
        p = dict(self.payload, session_binding_digest=digest(b"other"))
        self.assertEqual(self.verify(p)["reason"], "SESSION_OR_DEVICE_MISMATCH")

    def test_claimed_device_binding_mismatch(self):
        p = dict(self.payload, device_binding_digest=digest(b"other"))
        self.assertEqual(self.verify(p)["reason"], "SESSION_OR_DEVICE_MISMATCH")

    def test_host_policy_session_substitution_rejected(self):
        self.assertEqual(self.verify(
            expected_session_binding_digest=digest(b"other")
        )["reason"], "SESSION_OR_DEVICE_MISMATCH")

    def test_host_policy_device_substitution_rejected(self):
        self.assertEqual(self.verify(
            expected_device_binding_digest=digest(b"other")
        )["reason"], "SESSION_OR_DEVICE_MISMATCH")

    def test_host_policy_wrong_issuer(self):
        self.assertEqual(self.verify(expected_issuer="other")["reason"], "WRONG_ISSUER_OR_AUDIENCE")

    def test_host_policy_wrong_audience(self):
        self.assertEqual(self.verify(expected_audience="other")["reason"], "WRONG_ISSUER_OR_AUDIENCE")

    def test_unknown_json_field_rejected(self):
        p = dict(self.payload, extra="ignored")
        self.assertEqual(self.verify(p, signature=self.sign())["reason"], "INVALID_PAYLOAD_SHAPE")

    def test_missing_field_rejected(self):
        p = deepcopy(self.payload)
        p.pop("nonce")
        self.assertEqual(self.verify(p, signature=self.sign())["reason"], "INVALID_PAYLOAD_SHAPE")

    def test_bad_schema_or_purpose_rejected(self):
        for k, v in (("schema", "other"), ("purpose", "deploy-authorize")):
            p = dict(self.payload, **{k: v})
            self.assertEqual(self.verify(p, signature=self.sign())["reason"], "INVALID_PAYLOAD")

    def test_malformed_digest_rejected(self):
        p = dict(self.payload, device_binding_digest="sha256:xyz")
        self.assertEqual(self.verify(p, signature=self.sign())["reason"], "INVALID_PAYLOAD")

    def test_nonce_must_have_256_bit_lowercase_hex(self):
        for invalid in ("abc", "0"*32, "G"*64, "0"*65):
            with self.subTest(nonce=invalid):
                p = dict(self.payload, nonce=invalid)
                self.assertEqual(self.verify(p, signature=self.sign())["reason"], "INVALID_PAYLOAD")

    def test_bad_timestamp_types_fail_closed(self):
        for v in (True, 12.0, "2000000000", None):
            with self.subTest(value=v):
                p = dict(self.payload, issued_at=v)
                self.assertEqual(self.verify(p, signature=self.sign())["reason"], "INVALID_PAYLOAD")

    def test_invalid_now_epoch_is_rejected(self):
        for v in (True, 100.0, "2000000000", None):
            with self.subTest(value=v):
                self.assertEqual(self.verify(now_epoch=v)["reason"], "PROOF_EXPIRED_OR_FUTURE")

    def test_invalid_signature_encodings(self):
        for sig in ("", "x", "not-base64!!!", "AAAA", "A"*200, True):
            with self.subTest(sig=sig):
                self.assertEqual(self.verify(signature=sig)["reason"], "INVALID_OWNER_SIGNATURE")

    def test_store_cannot_use_memory_or_sqlite_uri(self):
        for value in (":memory:", "file:nonce?mode=memory", ""):
            with self.subTest(path=value):
                with self.assertRaises(ValueError):
                    SQLiteOwnerNonceRegistry(value)

    def test_separate_instances_single_noncestore(self):
        first = SQLiteOwnerNonceRegistry(self.path)
        second = SQLiteOwnerNonceRegistry(self.path)
        key = digest(b"same-key")
        self.assertTrue(first.consume_once(key, expires_at=self.now+90, now=self.now))
        self.assertFalse(second.consume_once(key, expires_at=self.now+90, now=self.now))

    def test_nonce_is_not_released_after_expiry(self):
        key = digest(b"never-release")
        self.assertTrue(self.db.consume_once(key, expires_at=self.now+1, now=self.now))
        self.assertFalse(self.db.consume_once(key, expires_at=self.now+1000, now=self.now+2))

    def test_bad_registry_nonce_key_cannot_write(self):
        self.assertFalse(self.db.consume_once("not-sha256", expires_at=self.now+30, now=self.now))

    def test_expired_registry_nonce_cannot_write(self):
        self.assertFalse(self.db.consume_once(digest(b"expired"), expires_at=self.now-1, now=self.now))

    def test_parallel_race_exactly_one_succeeds(self):
        signature = self.sign()
        def attempt(_):
            result = self.verify(signature=signature)
            return result["verified"]
        with ThreadPoolExecutor(max_workers=12) as pool:
            wins = list(pool.map(attempt, range(24)))
        self.assertEqual(wins.count(True), 1)
        self.assertEqual(wins.count(False), 23)

    def test_proof_does_not_expose_private_material(self):
        r = self.verify()
        self.assertNotIn("signature", r)
        self.assertNotIn("private_key", r)
        self.assertNotIn("api_key", r)
        self.assertFalse(r["trusted_host_attached"])

    def test_no_auth_by_self_declared_verified_flag(self):
        p = dict(self.payload, verified=True)
        self.assertEqual(self.verify(p, signature=self.sign())["reason"], "INVALID_PAYLOAD_SHAPE")

    def test_forged_owner_without_any_proof_rejected(self):
        r = verify_host_owner_proof(
            self.access, None, "", pinned_owner_public_key=self.pub,
            expected_pinned_key_fingerprint=digest(self.pub),
            expected_session_binding_digest=self.session_digest,
            expected_device_binding_digest=self.device_digest,
            expected_issuer="ci-owner-key-issuer",
            expected_audience="atlasquant-owner-host",
            now_epoch=self.now, nonce_registry=self.db,
        )
        self.assertFalse(r["verified"])
