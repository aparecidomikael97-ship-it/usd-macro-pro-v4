"""A161 RED-first: foreign dictionary key collision must be a denial, never an exception.

All signatures and pins are in-memory synthetic LAB fixtures. No authority.
"""
from __future__ import annotations

import unittest

from test_aion_p0_h0_dual_signed_witness_transcript_lab import (
    H0TwoSignedIndependentRolesLAB, NOW,
)
from atlasquant_aion_p0_h0_dual_signed_witness_transcript_lab import (
    AUTHORITY_FALSE, PERMANENT_GAPS, inspect_dual_signed_witness_lab,
)


class HostileCollisionKey(str):
    """Safe at dict construction, hostile if the inspector compares a key."""

    __hash__ = str.__hash__

    def __new__(cls, name):
        obj = super().__new__(cls, name)
        obj.armed = False
        return obj

    def __eq__(self, other):
        if self.armed:
            raise RuntimeError("UNTRUSTED_KEY_EQ_WAS_INVOKED")
        return False


def add_hostile_key(mapping, colliding_name):
    key = HostileCollisionKey(colliding_name)
    mapping[key] = "hostile-extra-field"
    key.armed = True


class A161HostileDictionaryKeysLAB(unittest.TestCase):
    def setUp(self):
        self.fixture = H0TwoSignedIndependentRolesLAB(
            "test_01_valid_dual_cryptography_has_zero_operational_authority"
        )
        self.fixture.setUp()

    def check(self, reservation, readback, pinned, expected):
        actual = inspect_dual_signed_witness_lab(
            reservation, readback, pinned, now_utc=NOW,
        )
        self.assertEqual(actual["state"], "HARD_NO_GO")
        self.assertIs(actual["allowed"], False)
        self.assertIs(actual["simulation_only"], True)
        self.assertIs(actual["signature_bytes_valid_under_caller_supplied_keys"], False)
        self.assertEqual(actual["blockers"], PERMANENT_GAPS)
        self.assertIn(expected, actual["defects"])
        for flag in AUTHORITY_FALSE:
            self.assertIs(actual[flag], False, flag)

    def test_01_hostile_colliding_pinned_key_denies(self):
        a, b = self.fixture.packet()
        pinned = self.fixture.pins.copy()
        add_hostile_key(pinned, "issuer_id")
        self.check(a, b, pinned, "CALLER_PINS_INVALID")

    def test_02_hostile_colliding_reservation_envelope_key_denies(self):
        a, b = self.fixture.packet()
        add_hostile_key(a, "payload")
        self.check(a, b, self.fixture.pins, "RESERVATION_ENVELOPE_SHAPE_INVALID")

    def test_03_hostile_colliding_readback_envelope_key_denies(self):
        a, b = self.fixture.packet()
        add_hostile_key(b, "signature_b64url")
        self.check(a, b, self.fixture.pins, "READBACK_ENVELOPE_SHAPE_INVALID")

    def test_04_hostile_colliding_reservation_payload_key_denies(self):
        a, b = self.fixture.packet()
        add_hostile_key(a["payload"], "schema")
        self.check(a, b, self.fixture.pins, "RESERVATION_TRANSCRIPT_INVALID")

    def test_05_hostile_colliding_readback_payload_key_denies(self):
        a, b = self.fixture.packet()
        add_hostile_key(b["payload"], "kind")
        self.check(a, b, self.fixture.pins, "READBACK_TRANSCRIPT_INVALID")


if __name__ == "__main__":
    unittest.main()
