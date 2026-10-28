"""A211 LAB — synthetic fork/rollback examples, no external attestation."""
from dataclasses import FrozenInstanceError
import unittest

from labs.a211_claimed_witness_coherence import (
    SCHEMA, compare_claimed_witness_checkpoints,
)


class A211ClaimedWitnessCoherenceTests(unittest.TestCase):
    def setUp(self):
        base = {
            "schema": SCHEMA,
            "ledger_id": "synthetic-ledger",
            "owner_root_fingerprint": "1" * 64,
            "sequence": 21,
            "commit_hash": "c" * 64,
            "parent_hash": "b" * 64,
            "subject_digest": "d" * 64,
        }
        self.host = base
        self.a = {**base, "observer_id": "synthetic-observer-A"}
        self.b = {**base, "observer_id": "synthetic-observer-B"}
        self.floor = {
            **base, "sequence": 20,
            "commit_hash": "b" * 64, "parent_hash": "a" * 64,
        }

    def compare(self, *, host=None, a=None, b=None, floor=None):
        return compare_claimed_witness_checkpoints(
            self.host if host is None else host,
            self.a if a is None else a,
            self.b if b is None else b,
            self.floor if floor is None else floor,
        )

    def check_denial(self, expected, **kwargs):
        result = self.compare(**kwargs)
        self.assertFalse(result.may_confirm)
        self.assertFalse(result.structurally_coherent)
        self.assertEqual(result.code, expected)

    def test_01_matching_next_checkpoint_never_confirms(self):
        result = self.compare()
        self.assertTrue(result.structurally_coherent)
        self.assertFalse(result.may_confirm)
        self.assertEqual(result.code, "SHAPE_COHERENT_INDEPENDENCE_UNPROVEN")
        self.assertEqual(len(result.comparison_digest), 64)

    def test_02_matching_floor_never_confirms(self):
        self.assertTrue(self.compare(
            host=self.floor,
            a={**self.floor, "observer_id": "synthetic-observer-A"},
            b={**self.floor, "observer_id": "synthetic-observer-B"},
        ).structurally_coherent)

    def test_03_host_rollback_detected(self):
        self.check_denial("HOST_BEHIND_WITNESS", host=self.floor)

    def test_04_witness_lag_detected(self):
        old = self.floor
        self.check_denial(
            "WITNESS_NOT_CAUGHT_UP",
            a={**old, "observer_id": "synthetic-observer-A"},
            b={**old, "observer_id": "synthetic-observer-B"},
        )

    def test_05_two_witnesses_fork_same_height(self):
        self.check_denial("WITNESS_FORK_DETECTED", b={**self.b, "commit_hash": "e" * 64})

    def test_06_two_witnesses_parent_disagreement(self):
        self.check_denial("WITNESS_FORK_DETECTED", b={**self.b, "parent_hash": "e" * 64})

    def test_07_two_witnesses_height_disagreement(self):
        self.check_denial("WITNESS_HEIGHT_DISAGREEMENT", b={**self.b, "sequence": 22})

    def test_08_host_and_witness_fork(self):
        self.check_denial("HOST_WITNESS_FORK_DETECTED", host={**self.host, "commit_hash": "e" * 64})

    def test_09_host_and_witness_parent_conflict(self):
        self.check_denial("HOST_PARENT_CONFLICT", host={**self.host, "parent_hash": "e" * 64})

    def test_10_rollback_below_floor_even_if_all_claimed_witnesses_agree(self):
        old = {**self.floor, "sequence": 19, "commit_hash": "9" * 64}
        self.check_denial(
            "OBSERVED_ROLLBACK_BELOW_FLOOR",
            host=old,
            a={**old, "observer_id": "synthetic-observer-A"},
            b={**old, "observer_id": "synthetic-observer-B"},
        )

    def test_11_no_forged_gap_two_steps_after_floor(self):
        future = {**self.host, "sequence": 22}
        self.check_denial(
            "UNVERIFIED_HISTORY_GAP",
            host=future,
            a={**future, "observer_id": "synthetic-observer-A"},
            b={**future, "observer_id": "synthetic-observer-B"},
        )

    def test_12_parent_chain_break(self):
        bad = {**self.host, "parent_hash": "9" * 64}
        self.check_denial(
            "PARENT_CHAIN_BREAK",
            host=bad,
            a={**bad, "observer_id": "synthetic-observer-A"},
            b={**bad, "observer_id": "synthetic-observer-B"},
        )

    def test_13_floor_fork_at_same_height(self):
        self.check_denial(
            "FLOOR_FORK_DETECTED",
            floor={**self.host, "commit_hash": "e" * 64},
        )

    def test_14_extra_self_asserted_crypto_flag_rejected(self):
        self.check_denial(
            "WITNESS_ENVELOPE_INVALID",
            a={**self.a, "signature_verified": True},
        )

    def test_15_same_observer_id_rejected(self):
        self.check_denial(
            "SAME_CLAIMED_OBSERVER",
            b={**self.b, "observer_id": "synthetic-observer-A"},
        )

    def test_16_two_faked_names_are_still_not_independence(self):
        outcome = self.compare(b={**self.b, "observer_id": "forged-independence"})
        self.assertTrue(outcome.structurally_coherent)
        self.assertFalse(outcome.may_confirm)

    def test_17_invalid_host_envelope(self):
        self.check_denial("HOST_OR_FLOOR_ENVELOPE_INVALID", host={"sequence": 21})

    def test_18_invalid_owner_floor(self):
        self.check_denial("HOST_OR_FLOOR_ENVELOPE_INVALID", floor={**self.floor, "schema": "wrong"})

    def test_19_invalid_witness_hash(self):
        self.check_denial("WITNESS_ENVELOPE_INVALID", b={**self.b, "commit_hash": "NOTHEX"})

    def test_20_bool_sequence_rejected(self):
        self.check_denial("WITNESS_ENVELOPE_INVALID", b={**self.b, "sequence": True})

    def test_21_ledger_scope_is_mandatory(self):
        self.check_denial("LEDGER_SCOPE_CONFLICT", b={**self.b, "ledger_id": "other-ledger"})

    def test_22_root_pinning_is_mandatory(self):
        self.check_denial(
            "OWNER_ROOT_CONFLICT",
            b={**self.b, "owner_root_fingerprint": "3" * 64},
        )

    def test_23_subject_binding_is_mandatory(self):
        self.check_denial("SUBJECT_CONFLICT", b={**self.b, "subject_digest": "e" * 64})

    def test_24_order_of_keys_does_not_change_digest(self):
        first = self.compare()
        second = self.compare(
            host=dict(reversed(list(self.host.items()))),
            a=dict(reversed(list(self.a.items()))),
        )
        self.assertEqual(first.comparison_digest, second.comparison_digest)

    def test_25_fake_root_change_on_every_copy_still_no_authority(self):
        fresh_root = "f" * 64
        result = self.compare(
            host={**self.host, "owner_root_fingerprint": fresh_root},
            a={**self.a, "owner_root_fingerprint": fresh_root},
            b={**self.b, "owner_root_fingerprint": fresh_root},
            floor={**self.floor, "owner_root_fingerprint": fresh_root},
        )
        self.assertTrue(result.structurally_coherent)
        self.assertFalse(result.may_confirm)

    def test_26_immutable_result_cannot_promote(self):
        result = self.compare()
        with self.assertRaises(FrozenInstanceError):
            result.may_confirm = True
        self.assertFalse(result.may_confirm)

    def test_27_missing_observer_id_rejected(self):
        self.check_denial(
            "WITNESS_ENVELOPE_INVALID",
            b={k: v for k, v in self.b.items() if k != "observer_id"},
        )


if __name__ == "__main__":
    unittest.main()
