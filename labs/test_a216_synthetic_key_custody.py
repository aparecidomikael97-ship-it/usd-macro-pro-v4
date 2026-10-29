"""A216: 30 real SQLite, two ephemeral synthetic Ed25519 keys, zero effects."""
import base64
from dataclasses import FrozenInstanceError
from datetime import timedelta
from hashlib import sha256
import json
import tempfile
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from labs import test_a202_outbox_dispatch_atomic_cas as a202
from labs.a216_synthetic_key_custody import (
    SCHEMA, custody_signing_message, inspect_synthetic_key_custody,
)
from labs import test_a215_synthetic_origin_bridge as a215_tests


class A216SyntheticKeyCustodyTests(unittest.TestCase):
    def setUp(self):
        self.a215 = a215_tests.A215SyntheticOriginBridgeTests()
        self.a215.setUp()
        self.issuer = Ed25519PrivateKey.generate()
        self.issuer_public = self.issuer.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.issuer_fp = sha256(self.issuer_public).hexdigest()
        self.leaf_fp = sha256(self.a215.pubkey).hexdigest()

    def certificate(self, candidate):
        body = {
            "schema": SCHEMA,
            "owner_id": candidate["owner_id"],
            "tenant_id": candidate["tenant_id"],
            "workspace_id": candidate["workspace_id"],
            "provider_id": candidate["provider_id"],
            "challenge_digest": candidate["challenge_digest"],
            "witness_root_fingerprint": candidate["witness_root_fingerprint"],
            "leaf_key_sha256": self.leaf_fp,
            "issuer_key_sha256": self.issuer_fp,
            "serial_id": "synthetic-serial-001",
            "key_epoch": 1,
            "not_before": (a202.NOW - timedelta(minutes=1)).isoformat(),
            "not_after": (a202.NOW + timedelta(minutes=3)).isoformat(),
            "key_status": "ACTIVE",
        }
        return self.sign_cert(body)

    def sign_cert(self, body):
        sig = self.issuer.sign(custody_signing_message(body))
        return {
            **body,
            "issuer_signature_b64": base64.b64encode(sig).decode("ascii"),
        }

    def inspect(self, outbox, key, candidate, receipt, certificate, **overrides):
        args = {
            "candidate_pubkey_bytes": self.a215.pubkey,
            "provisional_issuer_pubkey_bytes": self.issuer_public,
            "provisional_issuer_fingerprint": self.issuer_fp,
            "receipt_nonce_hex": self.a215.nonce,
            "observed_at": self.a215.observed,
            "last_witness_sequence": 4,
            "seen_provider_event_ids": [],
            "seen_receipt_nonces": [],
            "previous_key_epoch": 0,
            "seen_custody_serial_ids": [],
        }
        args.update(overrides)
        return inspect_synthetic_key_custody(
            outbox.get(key), candidate, receipt, certificate, **args,
        )

    def denial(self, outbox, key, candidate, receipt, certificate, code, **overrides):
        result = self.inspect(
            outbox, key, candidate, receipt, certificate, **overrides,
        )
        self.assertEqual(result.code, code)
        self.assertFalse(result.may_confirm)
        self.assertFalse(result.independent_origin_verified)
        self.assertFalse(result.custody_signature_math_valid)
        return result

    def test_01_two_mathematically_valid_signatures_are_not_independent(self):
        with self.a215.fixture() as (store, outbox, key, adapter):
            c = self.a215.candidate(outbox, key)
            r = self.a215.receipt(c)
            cert = self.certificate(c)
            before = store.db.total_changes
            result = self.inspect(outbox, key, c, r, cert)
            self.assertTrue(result.local_binding_ok)
            self.assertTrue(result.receipt_signature_math_valid)
            self.assertTrue(result.custody_signature_math_valid)
            self.assertFalse(result.independent_origin_verified)
            self.assertFalse(result.may_confirm)
            self.assertEqual(result.code, "SYNTHETIC_TWO_SIGNATURES_VALID_PROVISIONAL_ISSUER_UNTRUSTED")
            self.assertEqual(len(result.custody_digest), 64)
            self.assertEqual(outbox.get(key)["state"], "UNCERTAIN")
            self.assertEqual(store.db.total_changes, before)
            self.assertEqual(outbox.effect_count(), 0)
            self.assertEqual(adapter.send_calls, 1)

    def test_02_sent_stays_sent_without_confirm(self):
        with self.a215.fixture("pending") as (store, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            before = store.db.total_changes
            result = self.inspect(outbox, key, c, self.a215.receipt(c), self.certificate(c))
            self.assertTrue(result.custody_signature_math_valid)
            self.assertFalse(result.may_confirm)
            self.assertEqual(outbox.get(key)["state"], "SENT")
            self.assertEqual(outbox.effect_count(), 0)
            self.assertEqual(store.db.total_changes, before)

    def test_03_forged_but_self_consistent_issuer_is_still_untrusted(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            self.assertTrue(self.inspect(outbox, key, c, self.a215.receipt(c), self.certificate(c)).custody_signature_math_valid)
            self.assertFalse(self.inspect(outbox, key, c, self.a215.receipt(c), self.certificate(c)).independent_origin_verified)

    def test_04_corrupted_issuer_signature(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            cert = self.certificate(c)
            cert["issuer_signature_b64"] = base64.b64encode(b"\x00" * 64).decode()
            self.denial(outbox, key, c, self.a215.receipt(c), cert, "CUSTODY_SIGNATURE_MATH_INVALID")

    def test_05_invalid_issuer_signature_encoding(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            cert = self.certificate(c)
            cert["issuer_signature_b64"] = "not base64."
            self.denial(outbox, key, c, self.a215.receipt(c), cert, "INVALID_ISSUER_SIGNATURE_ENCODING")

    def test_06_changed_owner_scope_denied(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            cert = self.certificate(c)
            cert["owner_id"] = "intruder"
            self.denial(outbox, key, c, self.a215.receipt(c), cert, "CUSTODY_SCOPE_OR_EFFECT_BINDING_MISMATCH")

    def test_07_each_scope_or_effect_field_bound(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            for field in ("tenant_id", "workspace_id", "provider_id", "challenge_digest", "witness_root_fingerprint"):
                with self.subTest(field=field):
                    cert = self.certificate(c)
                    cert[field] = "altered"
                    self.denial(outbox, key, c, self.a215.receipt(c), cert, "CUSTODY_SCOPE_OR_EFFECT_BINDING_MISMATCH")

    def test_08_changed_leaf_fingerprint_even_if_resigned(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            cert = self.certificate(c)
            body = {k: v for k, v in cert.items() if k != "issuer_signature_b64"}
            body["leaf_key_sha256"] = "f" * 64
            self.denial(outbox, key, c, self.a215.receipt(c), self.sign_cert(body), "LEAF_KEY_FINGERPRINT_MISMATCH")

    def test_09_changed_issuer_fingerprint_even_if_resigned(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            cert = self.certificate(c)
            body = {k: v for k, v in cert.items() if k != "issuer_signature_b64"}
            body["issuer_key_sha256"] = "f" * 64
            self.denial(outbox, key, c, self.a215.receipt(c), self.sign_cert(body), "CERTIFICATE_ISSUER_KEY_MISMATCH")

    def test_10_untrusted_issuer_pin_mismatch(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            self.denial(
                outbox, key, c, self.a215.receipt(c), self.certificate(c),
                "UNTRUSTED_PROVISIONAL_PIN_MISMATCH",
                provisional_issuer_fingerprint="f" * 64,
            )

    def test_11_same_issuer_and_receipt_signer_rejected(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            self.denial(
                outbox, key, c, self.a215.receipt(c), self.certificate(c),
                "SAME_SIGNER_AND_PROVISIONAL_ISSUER",
                provisional_issuer_pubkey_bytes=self.a215.pubkey,
            )

    def test_12_bad_provisional_issuer_key_length(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            self.denial(
                outbox, key, c, self.a215.receipt(c), self.certificate(c),
                "INVALID_PROVISIONAL_ISSUER_KEY",
                provisional_issuer_pubkey_bytes=b"short",
            )

    def test_13_expired_cert_at_claimed_effect_time(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            body = {k: v for k, v in self.certificate(c).items() if k != "issuer_signature_b64"}
            body["not_after"] = (a202.NOW - timedelta(seconds=1)).isoformat()
            self.denial(outbox, key, c, self.a215.receipt(c), self.sign_cert(body), "LEAF_CERT_NOT_VALID_AT_CLAIMED_EFFECT_TIME")

    def test_14_certificate_not_yet_valid_at_event(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            body = {k: v for k, v in self.certificate(c).items() if k != "issuer_signature_b64"}
            body["not_before"] = (a202.NOW + timedelta(seconds=1)).isoformat()
            self.denial(outbox, key, c, self.a215.receipt(c), self.sign_cert(body), "LEAF_CERT_NOT_VALID_AT_CLAIMED_EFFECT_TIME")

    def test_15_signed_revocation_flag_blocks_math_result(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            body = {k: v for k, v in self.certificate(c).items() if k != "issuer_signature_b64"}
            body["key_status"] = "REVOKED"
            self.denial(outbox, key, c, self.a215.receipt(c), self.sign_cert(body), "SIGNED_KEY_REVOKED")

    def test_16_unsupported_key_status_denied(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            cert = self.certificate(c)
            cert["key_status"] = "PROVISIONALLY_TRUSTED"
            self.denial(outbox, key, c, self.a215.receipt(c), cert, "INVALID_SIGNED_CUSTODY_INTERVAL")

    def test_17_key_epoch_replay(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            self.denial(
                outbox, key, c, self.a215.receipt(c), self.certificate(c),
                "CUSTODY_EPOCH_REPLAY_OR_ROLLBACK", previous_key_epoch=1,
            )

    def test_18_key_epoch_gap(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            body = {k: v for k, v in self.certificate(c).items() if k != "issuer_signature_b64"}
            body["key_epoch"] = 3
            self.denial(outbox, key, c, self.a215.receipt(c), self.sign_cert(body), "CUSTODY_EPOCH_HISTORY_GAP")

    def test_19_boolean_epoch_floor_invalid(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            self.denial(
                outbox, key, c, self.a215.receipt(c), self.certificate(c),
                "UNTRUSTED_KEY_EPOCH_FLOOR", previous_key_epoch=True,
            )

    def test_20_bool_epoch_not_integer(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            cert = self.certificate(c)
            cert["key_epoch"] = True
            self.denial(outbox, key, c, self.a215.receipt(c), cert, "CUSTODY_EPOCH_REPLAY_OR_ROLLBACK")

    def test_21_serial_replay_denied(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            self.denial(
                outbox, key, c, self.a215.receipt(c), self.certificate(c),
                "CUSTODY_SERIAL_REPLAY",
                seen_custody_serial_ids=["synthetic-serial-001"],
            )

    def test_22_invalid_serial_history(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            self.denial(
                outbox, key, c, self.a215.receipt(c), self.certificate(c),
                "UNTRUSTED_CUSTODY_SERIAL_HISTORY",
                seen_custody_serial_ids=["bad serial /"],
            )

    def test_23_duplicate_json_certificate_keys_denied(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            raw = json.dumps(self.certificate(c))
            bad = raw.replace('"serial_id": "synthetic-serial-001"', '"serial_id": "synthetic-serial-001", "serial_id": "intruder"', 1)
            self.assertNotEqual(raw, bad)
            self.denial(outbox, key, c, self.a215.receipt(c), bad, "AMBIGUOUS_CUSTODY_CERTIFICATE")

    def test_24_self_asserted_independence_extra_field_denied(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            cert = self.certificate(c)
            cert["external_key_verified"] = True
            self.denial(outbox, key, c, self.a215.receipt(c), cert, "CUSTODY_ENVELOPE_NOT_EXACT")

    def test_25_wrong_receipt_signature_blocks_custody_preflight(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            r = self.a215.receipt(c)
            r["signature_b64"] = base64.b64encode(b"\x00" * 64).decode()
            self.denial(
                outbox, key, c, r, self.certificate(c),
                "A215_SYNTHETIC_SIGNATURE_SIGNATURE_MATH_NOT_VALID",
            )

    def test_26_wrong_local_intent_blocks_custody_preflight(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            r = self.a215.receipt(c)
            cert = self.certificate(c)
            c["tenant_id"] = "intruder"
            self.denial(
                outbox, key, c, r, cert,
                "A215_LOCAL_BINDING_ORIGINAL_INTENT_OR_ATTEMPT_MISMATCH",
            )

    def test_27_replay_unchanged_cert_never_writes_or_resends(self):
        with self.a215.fixture() as (store, outbox, key, adapter):
            c = self.a215.candidate(outbox, key)
            r = self.a215.receipt(c)
            cert = self.certificate(c)
            before = store.db.total_changes
            for _ in range(8):
                result = self.inspect(outbox, key, c, r, cert)
                self.assertTrue(result.custody_signature_math_valid)
                self.assertFalse(result.may_confirm)
            self.assertEqual(store.db.total_changes, before)
            self.assertEqual(outbox.effect_count(), 0)
            self.assertEqual(adapter.send_calls, 1)

    def test_28_immutable_result_cannot_promote_authority(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            result = self.inspect(outbox, key, c, self.a215.receipt(c), self.certificate(c))
            with self.assertRaises(FrozenInstanceError):
                result.may_confirm = True
            with self.assertRaises(FrozenInstanceError):
                result.independent_origin_verified = True

    def test_29_cert_as_canonical_json_still_no_authority(self):
        with self.a215.fixture() as (_, outbox, key, _):
            c = self.a215.candidate(outbox, key)
            r = self.a215.receipt(c)
            result = self.inspect(outbox, key, json.dumps(c), json.dumps(r), json.dumps(self.certificate(c)))
            self.assertTrue(result.custody_signature_math_valid)
            self.assertFalse(result.independent_origin_verified)

    def test_30_direct_outbox_confirmation_still_forbidden(self):
        with self.a215.fixture() as (_, outbox, key, _):
            with self.assertRaisesRegex(PermissionError, "INDEPENDENT_EFFECT_RECEIPT_REQUIRED"):
                outbox._confirm(
                    key, effect_ref="fake-two-signature-proof",
                    confirmed_at=a202.NOW, result={"confirmed": True},
                )
            self.assertEqual(outbox.get(key)["state"], "UNCERTAIN")
            self.assertEqual(outbox.effect_count(), 0)


if __name__ == "__main__":
    unittest.main()
