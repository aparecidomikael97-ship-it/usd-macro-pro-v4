"""A209 LAB root provenance tests: no root claim confers external authority."""
import base64
from dataclasses import FrozenInstanceError
import unittest

from labs.a209_root_provenance_gate import (
    SCHEMA, inspect_claimed_root, parse_receipt_json,
)


class A209ClaimedRootIsNeverIndependentProofTests(unittest.TestCase):
    def setUp(self):
        self.owner = "synthetic-owner"
        self.root = "a" * 64
        self.claim = {
            "schema": SCHEMA,
            "owner_id": self.owner,
            "public_root_fingerprint": self.root,
            "claimed_origin": "claimed_external_sealed",
            "ceremony_ref": "synthetic-ceremony-01",
            "external_witness_ref": "synthetic-witness-01",
            "checkpoint_seq": 14,
            "checkpoint_hash": "b" * 64,
            "previous_checkpoint_hash": "c" * 64,
            "sealed_at": "2026-10-28T10:00:00Z",
            "owner_signature_b64": base64.b64encode(b"F" * 64).decode(),
        }

    def assess(self, claim=None, *, owner=None, root=None, floor=13,
               observed="2026-10-28T11:00:00Z"):
        return inspect_claimed_root(
            self.claim if claim is None else claim,
            expected_owner=self.owner if owner is None else owner,
            expected_public_root_fingerprint=self.root if root is None else root,
            last_checkpoint_sequence=floor,
            observed_at=observed,
        )

    def test_01_plausible_offline_origin_is_only_unverified_shape(self):
        result = self.assess()
        self.assertTrue(result.structurally_consistent)
        self.assertFalse(result.independently_attested)
        self.assertFalse(result.may_confirm)
        self.assertEqual(result.code, "ROOT_STRUCTURE_OK_PROVENANCE_UNVERIFIED")

    def test_02_host_controlled_sources_cannot_become_trust_roots(self):
        for source in ("environment", "host_file", "host_callback",
                       "runtime_generated", "local_database"):
            with self.subTest(source=source):
                result = self.assess({**self.claim, "claimed_origin": source})
                self.assertEqual(result.code, "ROOT_SOURCE_CONTROLLED_BY_HOST")
                self.assertFalse(result.may_confirm)

    def test_03_extra_host_approved_flag_is_not_accepted(self):
        result = self.assess({**self.claim, "host_approved": True})
        self.assertEqual(result.code, "ROOT_ENVELOPE_NOT_EXACT")

    def test_04_wrong_owner_is_rejected(self):
        result = self.assess({**self.claim, "owner_id": "different-owner"})
        self.assertEqual(result.code, "OWNER_ROOT_SCOPE_MISMATCH")

    def test_05_owner_expectation_must_be_explicit(self):
        result = self.assess(owner="")
        self.assertEqual(result.code, "UNTRUSTED_OWNER_EXPECTATION")

    def test_06_swapped_root_fingerprint_is_rejected(self):
        result = self.assess({**self.claim, "public_root_fingerprint": "d" * 64})
        self.assertEqual(result.code, "ROOT_FINGERPRINT_MISMATCH")

    def test_07_missing_root_pin_does_not_fail_open(self):
        result = self.assess(root="")
        self.assertEqual(result.code, "UNTRUSTED_ROOT_EXPECTATION")

    def test_08_stale_or_replayed_checkpoint_denied(self):
        for floor in (14, 15, 100):
            with self.subTest(floor=floor):
                result = self.assess(floor=floor)
                self.assertEqual(result.code, "STALE_OR_REPLAYED_ROOT_CHECKPOINT")

    def test_09_bool_negative_or_string_sequence_denied(self):
        for bad in (True, False, 0, -1, "14"):
            with self.subTest(value=bad):
                result = self.assess({**self.claim, "checkpoint_seq": bad})
                self.assertEqual(result.code, "INVALID_CHECKPOINT_SEQUENCE")

    def test_10_untrusted_checkpoint_floor_is_rejected(self):
        for bad in (True, False, -1, "13"):
            with self.subTest(value=bad):
                self.assertEqual(self.assess(floor=bad).code, "UNTRUSTED_CHECKPOINT_FLOOR")

    def test_11_invalid_checkpoint_hash_is_rejected(self):
        for field in ("checkpoint_hash", "previous_checkpoint_hash"):
            with self.subTest(field=field):
                result = self.assess({**self.claim, field: "not-a-hash"})
                self.assertEqual(result.code, "INVALID_CHECKPOINT_HASH")

    def test_12_forged_but_well_formed_signature_never_authorizes(self):
        result = self.assess()
        self.assertEqual(result.code, "ROOT_STRUCTURE_OK_PROVENANCE_UNVERIFIED")
        self.assertFalse(result.may_confirm)

    def test_13_invalid_or_short_signature_rejected(self):
        for sig in ("!", "", "AAAA", None, "x" * 8193):
            with self.subTest(sig=str(sig)[:20]):
                result = self.assess({**self.claim, "owner_signature_b64": sig})
                self.assertFalse(result.structurally_consistent)
                self.assertFalse(result.may_confirm)

    def test_14_sealed_in_future_or_naive_clock_rejected(self):
        for stamp in ("2026-10-28T12:00:00Z", "2026-10-28T10:00:00",
                      "not-a-time"):
            with self.subTest(stamp=stamp):
                result = self.assess({**self.claim, "sealed_at": stamp})
                self.assertFalse(result.structurally_consistent)

    def test_15_invalid_ceremony_or_witness_id_rejected(self):
        for field in ("ceremony_ref", "external_witness_ref"):
            with self.subTest(field=field):
                result = self.assess({**self.claim, field: ""})
                self.assertEqual(result.code, "INVALID_CEREMONY_OR_WITNESS_REF")

    def test_16_unknown_or_unhashable_origin_is_rejected_not_crash(self):
        for origin in ("mystery", [], {"host": "controlled"}, None):
            with self.subTest(origin=origin):
                result = self.assess({**self.claim, "claimed_origin": origin})
                self.assertEqual(result.code, "ROOT_ORIGIN_UNKNOWN")
                self.assertFalse(result.may_confirm)

    def test_17_ambiguous_duplicate_json_keys_rejected(self):
        with self.assertRaises(ValueError):
            parse_receipt_json('{"owner_id":"a","owner_id":"b"}')

    def test_18_result_is_immutable(self):
        result = self.assess()
        with self.assertRaises(FrozenInstanceError):
            result.may_confirm = True
        self.assertFalse(result.may_confirm)


if __name__ == "__main__":
    unittest.main()
