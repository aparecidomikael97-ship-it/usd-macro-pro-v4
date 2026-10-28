"""A208 LAB: independent receipt preflight contract, no external effects.

The apparently valid signature is intentionally fabricated. A structural
preflight may mark its SHAPE valid but must NEVER grant confirmation authority.
"""
import base64
from dataclasses import FrozenInstanceError
import json
import unittest

from labs.a208_independent_receipt_preflight import (
    SCHEMA,
    ReceiptPreflight,
    parse_receipt_json,
    preflight_receipt,
)


class A208IndependentReceiptContractTests(unittest.TestCase):
    def setUp(self):
        self.expected = {
            "owner_id": "synthetic-owner",
            "tenant_id": "synthetic-tenant",
            "workspace_id": "synthetic-workspace",
            "idempotency_key": "a" * 64,
            "intent_digest": "b" * 64,
            "provider_id": "synthetic-provider",
            "witness_root_id": "UNANCHORED-FAKE-ROOT",
        }
        self.receipt = {
            **self.expected,
            "schema": SCHEMA,
            "provider_event_id": "synthetic-event-01",
            "effect_ref": "synthetic-effect-01",
            "effect_state": "EFFECT_CONFIRMED",
            "occurred_at": "2026-10-28T11:00:00+00:00",
            "witness_sequence": 9,
            "witness_signature_b64": base64.b64encode(b"F" * 64).decode(),
        }

    def assess(self, receipt=None, *, expected=None, floor=8,
               authorized="2026-10-28T10:59:00Z",
               observed="2026-10-28T11:01:00Z"):
        return preflight_receipt(
            self.receipt if receipt is None else receipt,
            expected=self.expected if expected is None else expected,
            observed_at=observed,
            authorized_at=authorized,
            last_witness_sequence=floor,
        )

    def test_01_plausible_but_forged_signature_never_confers_authority(self):
        result = self.assess()
        self.assertTrue(result.structural_valid)
        self.assertFalse(result.may_confirm)
        self.assertEqual(result.code, "STRUCTURE_OK_EXTERNAL_CUSTODY_UNVERIFIED")

    def test_02_self_asserted_verified_flag_is_rejected(self):
        receipt = {**self.receipt, "verified": True}
        result = self.assess(receipt)
        self.assertFalse(result.structural_valid)
        self.assertFalse(result.may_confirm)

    def test_03_wrong_scope_intent_provider_or_root_is_rejected(self):
        for field in self.expected:
            with self.subTest(field=field):
                receipt = {**self.receipt, field: "different"}
                result = self.assess(receipt)
                self.assertFalse(result.structural_valid)
                self.assertFalse(result.may_confirm)

    def test_04_missing_expected_independent_root_must_not_pass(self):
        expected = {**self.expected}
        del expected["witness_root_id"]
        result = self.assess(expected=expected)
        self.assertEqual(result.code, "UNTRUSTED_OR_MISSING_EXPECTATION")
        self.assertFalse(result.may_confirm)

    def test_05_replay_or_rollback_sequence_is_rejected(self):
        for floor in (9, 10, 500):
            with self.subTest(floor=floor):
                result = self.assess(floor=floor)
                self.assertEqual(result.code, "STALE_OR_REPLAYED_SEQUENCE")
                self.assertFalse(result.may_confirm)

    def test_06_bool_or_negative_sequence_is_rejected(self):
        for seq in (True, False, 0, -1, "9"):
            with self.subTest(seq=seq):
                result = self.assess({**self.receipt, "witness_sequence": seq})
                self.assertEqual(result.code, "INVALID_WITNESS_SEQUENCE")
                self.assertFalse(result.may_confirm)

    def test_07_invalid_sequence_floor_is_rejected(self):
        for floor in (True, False, -1, "8"):
            with self.subTest(floor=floor):
                result = self.assess(floor=floor)
                self.assertEqual(result.code, "UNTRUSTED_SEQUENCE_FLOOR")
                self.assertFalse(result.may_confirm)

    def test_08_bad_signature_encoding_or_length_is_rejected(self):
        for sig in ("!", "", "AAAA", None, "x" * 8193):
            with self.subTest(sig=str(sig)[:24]):
                result = self.assess({**self.receipt, "witness_signature_b64": sig})
                self.assertFalse(result.structural_valid)
                self.assertFalse(result.may_confirm)

    def test_09_future_predated_or_naive_time_is_rejected(self):
        for stamp in (
            "2026-10-28T11:02:00+00:00",
            "2026-10-28T10:58:00Z",
            "2026-10-28T11:00:00",
            "not-a-time",
        ):
            with self.subTest(stamp=stamp):
                result = self.assess({**self.receipt, "occurred_at": stamp})
                self.assertFalse(result.structural_valid)
                self.assertFalse(result.may_confirm)

    def test_10_missing_or_extra_fields_rejected(self):
        missing = {k: v for k, v in self.receipt.items() if k != "effect_ref"}
        for item in (missing, {**self.receipt, "host_approved": True}, {}):
            result = self.assess(item)
            self.assertEqual(result.code, "RECEIPT_FIELDS_NOT_EXACT")
            self.assertFalse(result.may_confirm)

    def test_11_nonconfirmation_state_rejected(self):
        receipt = {**self.receipt, "effect_state": "SENT"}
        self.assertEqual(self.assess(receipt).code, "NOT_A_CONFIRMED_EFFECT")

    def test_12_invalid_hashes_and_keys_rejected(self):
        for field in ("intent_digest", "idempotency_key"):
            with self.subTest(field=field):
                bad = {**self.receipt, field: "A" * 64}
                expected = {**self.expected, field: "A" * 64}
                self.assertEqual(
                    self.assess(bad, expected=expected).code,
                    "INVALID_INTENT_DIGEST_OR_KEY",
                )

    def test_13_duplicate_json_object_key_is_rejected(self):
        raw = '{"schema":"A","schema":"B"}'
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            parse_receipt_json(raw)

    def test_14_nonobject_and_malformed_json_rejected(self):
        for raw in ('[]', 'null', '{bad-json}'):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    parse_receipt_json(raw)

    def test_15_roundtrip_json_still_does_not_verify_signature(self):
        parsed = parse_receipt_json(json.dumps(self.receipt))
        self.assertEqual(parsed, self.receipt)
        self.assertFalse(self.assess(parsed).may_confirm)

    def test_16_result_is_immutable_and_never_grants_authority(self):
        result = self.assess()
        with self.assertRaises(FrozenInstanceError):
            result.may_confirm = True
        self.assertFalse(result.may_confirm)


if __name__ == "__main__":
    unittest.main()
