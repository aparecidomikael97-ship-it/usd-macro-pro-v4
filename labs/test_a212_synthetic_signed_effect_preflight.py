"""A212 synthetic-only Ed25519 tests; keys exist only in test memory."""
import base64
from dataclasses import FrozenInstanceError
import json
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from labs.a212_synthetic_signed_effect_preflight import (
    SCHEMA, DOMAIN, signing_message, decode_strict_json_receipt,
    preflight_signed_synthetic_effect,
)


class A212SyntheticEffectSignatureTests(unittest.TestCase):
    def setUp(self):
        self.test_signer = Ed25519PrivateKey.generate()
        self.test_pubkey = self.test_signer.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.expected = {
            "owner_id": "synthetic-owner",
            "tenant_id": "synthetic-tenant",
            "workspace_id": "synthetic-workspace",
            "operation_kind": "SYNTHETIC_EFFECT",
            "intent_digest": "a" * 64,
            "idempotency_key": "b" * 64,
            "provider_id": "fake-provider",
            "witness_root_id": "fake-root",
            "witness_checkpoint_hash": "c" * 64,
            "receipt_nonce_hex": "d" * 64,
            "subject_digest": "e" * 64,
        }
        self.statement = {
            "schema": SCHEMA,
            **self.expected,
            "provider_event_id": "fake-event-001",
            "effect_ref": "fake-effect-001",
            "effect_state": "EFFECT_CONFIRMED",
            "occurred_at": "2026-10-28T11:00:00Z",
            "witness_sequence": 21,
        }
        self.receipt = self.sign(self.statement)

    def sign(self, statement):
        signature = self.test_signer.sign(signing_message(statement))
        return {
            **statement, "signature_b64": base64.b64encode(signature).decode("ascii"),
        }

    def assess(self, receipt=None, expected=None, pubkey=None, **overrides):
        args = {
            "expected": self.expected if expected is None else expected,
            "candidate_pubkey_bytes": self.test_pubkey if pubkey is None else pubkey,
            "authorized_at": "2026-10-28T10:00:00Z",
            "observed_at": "2026-10-28T12:00:00Z",
            "last_witness_sequence": 20,
            "seen_provider_event_ids": [],
            "seen_receipt_nonces": [],
        }
        args.update(overrides)
        return preflight_signed_synthetic_effect(
            self.receipt if receipt is None else receipt, **args,
        )

    def assert_denied(self, code, **kwargs):
        outcome = self.assess(**kwargs)
        self.assertEqual(outcome.code, code)
        self.assertFalse(outcome.may_confirm)
        self.assertFalse(outcome.mathematically_valid_signature)

    def test_01_valid_crypto_math_does_not_confirm_effect(self):
        outcome = self.assess()
        self.assertTrue(outcome.mathematically_valid_signature)
        self.assertFalse(outcome.may_confirm)
        self.assertEqual(
            outcome.code, "SIGNATURE_MATH_OK_EXTERNAL_EFFECT_AND_CUSTODY_UNPROVEN",
        )
        self.assertEqual(len(outcome.statement_digest), 64)

    def test_02_fabricated_provider_effect_signed_by_test_key_not_authority(self):
        fake_effects = []
        self.assertEqual(fake_effects, [])
        self.assertTrue(self.assess().mathematically_valid_signature)
        self.assertFalse(self.assess().may_confirm)

    def test_03_modified_effect_ref_breaks_signature(self):
        self.assert_denied(
            "SIGNATURE_MATH_NOT_VALID",
            receipt={**self.receipt, "effect_ref": "altered-effect"},
        )

    def test_04_modified_provider_event_breaks_signature(self):
        self.assert_denied(
            "SIGNATURE_MATH_NOT_VALID",
            receipt={**self.receipt, "provider_event_id": "altered-event"},
        )

    def test_05_unconfirmed_claim_is_rejected(self):
        self.assert_denied(
            "EFFECT_NOT_CONFIRMED",
            receipt={**self.receipt, "effect_state": "PENDING"},
        )

    def test_06_resigned_wrong_intent_does_not_rebind(self):
        self.assert_denied(
            "SIGNED_CAUSAL_BINDING_MISMATCH",
            receipt=self.sign({**self.statement, "intent_digest": "f" * 64}),
        )

    def test_07_resigned_wrong_nonce_does_not_rebind(self):
        self.assert_denied(
            "SIGNED_CAUSAL_BINDING_MISMATCH",
            receipt=self.sign({**self.statement, "receipt_nonce_hex": "f" * 64}),
        )

    def test_08_resigned_wrong_idempotency_does_not_rebind(self):
        self.assert_denied(
            "SIGNED_CAUSAL_BINDING_MISMATCH",
            receipt=self.sign({**self.statement, "idempotency_key": "f" * 64}),
        )

    def test_09_scope_fields_bound_even_after_resign(self):
        for field in ("owner_id", "tenant_id", "workspace_id"):
            with self.subTest(field=field):
                self.assert_denied(
                    "SIGNED_CAUSAL_BINDING_MISMATCH",
                    receipt=self.sign({**self.statement, field: "intruder"}),
                )

    def test_10_wrong_provider_after_resign(self):
        self.assert_denied(
            "SIGNED_CAUSAL_BINDING_MISMATCH",
            receipt=self.sign({**self.statement, "provider_id": "other-provider"}),
        )

    def test_11_wrong_operation_after_resign(self):
        self.assert_denied(
            "SIGNED_CAUSAL_BINDING_MISMATCH",
            receipt=self.sign({**self.statement, "operation_kind": "OTHER_EFFECT"}),
        )

    def test_12_wrong_subject_after_resign(self):
        self.assert_denied(
            "SIGNED_CAUSAL_BINDING_MISMATCH",
            receipt=self.sign({**self.statement, "subject_digest": "f" * 64}),
        )

    def test_13_wrong_checkpoint_after_resign(self):
        self.assert_denied(
            "SIGNED_CAUSAL_BINDING_MISMATCH",
            receipt=self.sign({**self.statement, "witness_checkpoint_hash": "f" * 64}),
        )

    def test_14_wrong_witness_root_after_resign(self):
        self.assert_denied(
            "SIGNED_CAUSAL_BINDING_MISMATCH",
            receipt=self.sign({**self.statement, "witness_root_id": "other-root"}),
        )

    def test_15_replayed_provider_event(self):
        self.assert_denied(
            "PROVIDER_EVENT_REPLAY",
            seen_provider_event_ids=["fake-event-001"],
        )

    def test_16_replayed_nonce(self):
        self.assert_denied(
            "RECEIPT_NONCE_REPLAY",
            seen_receipt_nonces=["d" * 64],
        )

    def test_17_stale_witness_sequence(self):
        self.assert_denied("STALE_WITNESS_SEQUENCE", last_witness_sequence=21)

    def test_18_large_sequence_gap_not_external_proof(self):
        alt = self.sign({**self.statement, "witness_sequence": 100})
        outcome = self.assess(receipt=alt)
        self.assertTrue(outcome.mathematically_valid_signature)
        self.assertFalse(outcome.may_confirm)

    def test_19_boolean_witness_sequence_invalid(self):
        self.assert_denied(
            "INVALID_WITNESS_SEQUENCE",
            receipt={**self.receipt, "witness_sequence": True},
        )

    def test_20_invalid_floor(self):
        self.assert_denied("INVALID_SEQUENCE_FLOOR", last_witness_sequence=True)

    def test_21_future_event_outside_observation(self):
        receipt = self.sign({
            **self.statement, "occurred_at": "2026-10-28T13:00:00Z",
        })
        self.assert_denied("EFFECT_TIME_OUTSIDE_AUTHORIZATION", receipt=receipt)

    def test_22_event_prior_to_authorization(self):
        receipt = self.sign({
            **self.statement, "occurred_at": "2026-10-28T09:00:00Z",
        })
        self.assert_denied("EFFECT_TIME_OUTSIDE_AUTHORIZATION", receipt=receipt)

    def test_23_invalid_time_window(self):
        self.assert_denied("INVALID_TIME_WINDOW", authorized_at="invalid")

    def test_24_malformed_signature_base64(self):
        self.assert_denied(
            "INVALID_SIGNATURE_ENCODING",
            receipt={**self.receipt, "signature_b64": "!!!"},
        )

    def test_25_wrong_signature_size(self):
        self.assert_denied(
            "INVALID_SIGNATURE_ENCODING",
            receipt={**self.receipt, "signature_b64": base64.b64encode(b"short").decode()},
        )

    def test_26_invalid_caller_supplied_public_key(self):
        self.assert_denied("INVALID_UNATTESTED_PUBLIC_KEY", pubkey=b"bad")

    def test_27_wrong_test_key_causes_math_failure(self):
        other = Ed25519PrivateKey.generate().public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw,
        )
        self.assert_denied("SIGNATURE_MATH_NOT_VALID", pubkey=other)

    def test_28_domain_separation_rejects_signature_over_plain_json(self):
        payload = json.dumps(
            self.statement, sort_keys=True,
            ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")
        raw_sig = self.test_signer.sign(payload)
        self.assert_denied(
            "SIGNATURE_MATH_NOT_VALID",
            receipt={**self.receipt, "signature_b64": base64.b64encode(raw_sig).decode()},
        )
        self.assertTrue(DOMAIN.startswith(b"ATLASQUANT-AION"))

    def test_29_self_claimed_verification_flag_not_in_schema(self):
        self.assert_denied(
            "RECEIPT_ENVELOPE_NOT_EXACT",
            receipt={**self.receipt, "independently_verified": True},
        )

    def test_30_missing_expectation_field(self):
        expectation = dict(self.expected)
        expectation.pop("owner_id")
        self.assert_denied("EXPECTATION_ENVELOPE_NOT_EXACT", expected=expectation)

    def test_31_duplicate_json_field_is_rejected(self):
        with self.assertRaises(ValueError):
            decode_strict_json_receipt('{"schema":"a","schema":"b"}')

    def test_32_non_finite_json_constant_rejected(self):
        with self.assertRaises(ValueError):
            decode_strict_json_receipt('{"x":NaN}')

    def test_33_oversized_json_rejected(self):
        with self.assertRaises(ValueError):
            decode_strict_json_receipt('{"padding":"' + ("x" * 9000) + '"}')

    def test_34_strict_json_roundtrip(self):
        parsed = decode_strict_json_receipt(json.dumps(self.receipt))
        self.assertEqual(parsed, self.receipt)
        self.assertTrue(self.assess(receipt=parsed).mathematically_valid_signature)

    def test_35_deterministic_signed_bytes_ignore_key_order(self):
        reordered = dict(reversed(list(self.statement.items())))
        self.assertEqual(signing_message(self.statement), signing_message(reordered))

    def test_36_signed_statement_rejects_unexpected_field(self):
        with self.assertRaises(ValueError):
            signing_message({**self.statement, "unknown": "value"})

    def test_37_invalid_history_rejected(self):
        self.assert_denied("INVALID_NONCE_HISTORY", seen_receipt_nonces=[True])

    def test_38_invalid_event_history_rejected(self):
        self.assert_denied("INVALID_EVENT_HISTORY", seen_provider_event_ids=[True])

    def test_39_result_is_immutable(self):
        outcome = self.assess()
        with self.assertRaises(FrozenInstanceError):
            outcome.may_confirm = True
        self.assertFalse(outcome.may_confirm)


if __name__ == "__main__":
    unittest.main()
