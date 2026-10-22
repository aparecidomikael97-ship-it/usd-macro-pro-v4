"""A150 adversarial policy pin and expiring lease tests — SYNTHETIC ONLY.

The operator pin is supplied by the test harness outside mutable SQLite.
The clock is test-injected and NOT an independently attested trusted clock.
No provider, Worker, HUMAN_OWNER or real independent witness is simulated.
"""
import base64
from contextlib import closing
from dataclasses import replace
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aion_p0_a145_checkpoint_verifier_lab import canonical_history_digest
from aion_p0_a149_authenticated_cas_lab import (
    A149Denied, PublishRequest, SignedPublishRequest,
    canonical_publish_request, verify_signed_receipt,
)
from aion_p0_a150_pinned_policy_lease_lab import (
    LeasedPinnedWitnessLAB, OperatorPinnedPolicyLAB, MAX_LEASE_SECONDS,
    NANOSECONDS_PER_SECOND,
)

ROOT = Path(__file__).resolve().parent.parent


def raw_private(signer):
    return signer.private_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )


def raw_public(signer):
    return signer.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw,
    )


class SyntheticClock:
    def __init__(self, start=1_800_000_000_000_000_000):
        self.value = start

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds * NANOSECONDS_PER_SECOND


class A150PinnedPolicyLeaseLAB(unittest.TestCase):
    def setUp(self):
        flags = patch.dict(os.environ, {
            "AION_LAB_MODE": "1", "AION_WORKER_ENABLED": "0",
            "AION_EXTERNAL_EXECUTION_ENABLED": "0",
        })
        flags.start()
        self.addCleanup(flags.stop)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.witness_dir = self.root / "witness"
        self.witness_dir.mkdir()
        self.publisher = Ed25519PrivateKey.generate()
        self.witness_signer = Ed25519PrivateKey.generate()
        self.clock = SyntheticClock()
        self.engine = LeasedPinnedWitnessLAB.bootstrap_synthetic(
            witness_dir=self.witness_dir, ledger_id="ledger-A",
            publisher_key_id="publisher-1",
            publisher_public_key=raw_public(self.publisher),
            witness_private_key=raw_private(self.witness_signer),
            clock_ns=self.clock,
            lease_seconds=30,
        )
        self.pin = self.engine.policy
        self.events1 = [{"seq": 1, "intent": "first"}]
        self.events2 = self.events1 + [{"seq": 2, "intent": "second"}]

    def reopen(self, policy=None, clock=None, lease_seconds=30):
        return LeasedPinnedWitnessLAB(
            witness_dir=self.witness_dir, ledger_id="ledger-A",
            pinned_policy=self.pin if policy is None else policy,
            clock_ns=self.clock if clock is None else clock,
            lease_seconds=lease_seconds,
        )

    def signed(self, challenge=None, events=None, signer=None, **changes):
        challenge = challenge if challenge is not None else self.engine.issue_challenge()
        events = self.events1 if events is None else events
        attrs = {
            "ledger_id": challenge["ledger_id"],
            "epoch": challenge["epoch"],
            "publisher_key_id": challenge["publisher_key_id"],
            "challenge_id": challenge["challenge_id"],
            "request_id": secrets.token_hex(16),
            "expected_sequence": challenge["expected_sequence"],
            "expected_digest": challenge["expected_digest"],
            "next_sequence": challenge["expected_sequence"] + 1,
            "next_digest": canonical_history_digest(events),
        }
        attrs.update(changes)
        req = PublishRequest(**attrs)
        signer = self.publisher if signer is None else signer
        signature = base64.b64encode(
            signer.sign(canonical_publish_request(req))
        ).decode("ascii")
        return SignedPublishRequest(req, signature)

    def publish(self, envelope=None):
        return self.engine.publish(
            envelope=self.signed() if envelope is None else envelope,
        )

    def assert_no_advance(self):
        self.assertEqual(self.engine.read_head()["sequence"], 0)

    def test_01_genesis_operator_pin_matches_witness_database(self):
        self.assertEqual(self.engine.read_head()["publisher_public_hex"],
                         self.pin.publisher_public_key.hex())
        self.assertEqual(self.engine.read_head()["epoch"], self.pin.epoch)

    def test_02_pinned_signing_key_differs_from_publisher(self):
        self.assertNotEqual(self.pin.publisher_public_key, self.pin.witness_public_key)

    def test_03_issued_challenge_contains_bounded_lease(self):
        challenge = self.engine.issue_challenge()
        self.assertEqual(challenge["lease_expires_ns"] - challenge["lease_issued_ns"],
                         30 * NANOSECONDS_PER_SECOND)

    def test_04_valid_signed_request_within_lease(self):
        envelope = self.signed()
        self.clock.advance(5)
        result = self.publish(envelope)
        self.assertEqual(result.receipt.sequence, 1)

    def test_05_valid_at_last_nanosecond_before_expiration(self):
        envelope = self.signed()
        self.clock.value += 30 * NANOSECONDS_PER_SECOND - 1
        self.assertEqual(self.publish(envelope).receipt.sequence, 1)

    def test_06_denied_exactly_at_expiry_boundary(self):
        envelope = self.signed()
        self.clock.advance(30)
        with self.assertRaisesRegex(A149Denied, "challenge_lease_expired"):
            self.publish(envelope)
        self.assert_no_advance()

    def test_07_denied_long_after_expiry(self):
        envelope = self.signed()
        self.clock.advance(300)
        with self.assertRaisesRegex(A149Denied, "challenge_lease_expired"):
            self.publish(envelope)
        self.assert_no_advance()

    def test_08_expired_attempt_does_not_consume_challenge(self):
        envelope = self.signed()
        self.clock.advance(31)
        with self.assertRaisesRegex(A149Denied, "challenge_lease_expired"):
            self.publish(envelope)
        with closing(sqlite3.connect(self.engine.db_path)) as db:
            consumed = db.execute(
                "SELECT consumed FROM challenges WHERE challenge_id=?",
                (envelope.request.challenge_id,),
            ).fetchone()[0]
        self.assertEqual(consumed, 0)
        self.assert_no_advance()

    def test_09_expired_challenge_remains_denied_after_reopen(self):
        envelope = self.signed()
        self.clock.advance(31)
        with self.assertRaisesRegex(A149Denied, "challenge_lease_expired"):
            self.reopen().publish(envelope=envelope)

    def test_10_fresh_challenge_after_prior_expiration_works(self):
        old = self.signed()
        self.clock.advance(31)
        with self.assertRaisesRegex(A149Denied, "challenge_lease_expired"):
            self.publish(old)
        self.assertEqual(self.publish().receipt.sequence, 1)

    def test_11_replay_of_consumed_challenge_denied(self):
        envelope = self.signed()
        self.publish(envelope)
        with self.assertRaisesRegex(A149Denied, "challenge_already_consumed"):
            self.reopen().publish(envelope=envelope)

    def test_12_replay_of_consumed_challenge_denied_even_before_expiry(self):
        envelope = self.signed()
        self.publish(envelope)
        self.clock.advance(1)
        with self.assertRaisesRegex(A149Denied, "challenge_already_consumed"):
            self.publish(envelope)

    def test_13_publisher_public_key_changed_in_sqlite_denied_before_publish(self):
        attacker = Ed25519PrivateKey.generate()
        with closing(sqlite3.connect(self.engine.db_path)) as db:
            db.execute("UPDATE witness_meta SET publisher_public_hex=?",
                       (raw_public(attacker).hex(),))
            db.commit()
        with self.assertRaisesRegex(A149Denied, "external_pin_mismatch"):
            self.engine.publish(envelope=self.signed(
                signer=attacker,
                challenge={"ledger_id":"ledger-A","epoch":self.pin.epoch,
                           "publisher_key_id":"publisher-1",
                           "challenge_id":secrets.token_hex(16),
                           "expected_sequence":0,
                           "expected_digest":canonical_history_digest([])}
            ))

    def test_14_pubkey_tamper_denied_on_new_instance(self):
        with closing(sqlite3.connect(self.engine.db_path)) as db:
            db.execute("UPDATE witness_meta SET publisher_public_hex=?", ("a"*64,))
            db.commit()
        with self.assertRaisesRegex(A149Denied, "external_pin_mismatch"):
            self.reopen()

    def test_15_publisher_identity_tamper_denied(self):
        with closing(sqlite3.connect(self.engine.db_path)) as db:
            db.execute("UPDATE witness_meta SET publisher_key_id='attacker'")
            db.commit()
        with self.assertRaisesRegex(A149Denied, "external_pin_mismatch"):
            self.engine.read_head()

    def test_16_epoch_tamper_denied(self):
        with closing(sqlite3.connect(self.engine.db_path)) as db:
            db.execute("UPDATE witness_meta SET epoch=?", (secrets.token_hex(16),))
            db.commit()
        with self.assertRaisesRegex(A149Denied, "external_pin_mismatch"):
            self.reopen()

    def test_17_wrong_operator_publisher_pin_denied(self):
        other = replace(self.pin, publisher_public_key=raw_public(Ed25519PrivateKey.generate()))
        with self.assertRaisesRegex(A149Denied, "external_pin_mismatch"):
            self.reopen(policy=other)

    def test_18_missing_external_policy_denied(self):
        with self.assertRaisesRegex(A149Denied, "external_policy_required"):
            self.reopen(policy="untrusted_policy")

    def test_19_wrong_external_epoch_pin_denied(self):
        bad = replace(self.pin, epoch=secrets.token_hex(16))
        with self.assertRaisesRegex(A149Denied, "external_pin_mismatch"):
            self.reopen(policy=bad)

    def test_20_wrong_external_ledger_denied(self):
        bad = replace(self.pin, ledger_id="ledger-B")
        with self.assertRaisesRegex(A149Denied, "policy_ledger_mismatch"):
            self.reopen(policy=bad)

    def test_21_signer_private_key_replaced_blocks_challenge(self):
        self.engine.key_path.write_bytes(raw_private(Ed25519PrivateKey.generate()))
        with self.assertRaisesRegex(A149Denied, "external_witness_signer_pin_mismatch"):
            self.engine.issue_challenge()
        self.assert_no_advance()

    def test_22_signer_private_key_replaced_blocks_publish(self):
        envelope = self.signed()
        self.engine.key_path.write_bytes(raw_private(Ed25519PrivateKey.generate()))
        with self.assertRaisesRegex(A149Denied, "external_witness_signer_pin_mismatch"):
            self.publish(envelope)
        self.assert_no_advance()

    def test_23_valid_signed_receipt_uses_operator_pinned_witness_key(self):
        signed = self.publish()
        self.assertEqual(verify_signed_receipt(
            envelope=signed, pinned_witness_key=self.pin.witness_public_key,
        ), signed.receipt)

    def test_24_wrong_receipt_trust_anchor_denied(self):
        signed = self.publish()
        with self.assertRaisesRegex(A149Denied, "receipt_signature_invalid"):
            verify_signed_receipt(
                envelope=signed,
                pinned_witness_key=raw_public(Ed25519PrivateKey.generate()),
            )

    def test_25_forged_request_signature_denied(self):
        envelope = self.signed(signer=Ed25519PrivateKey.generate())
        with self.assertRaisesRegex(A149Denied, "publisher_signature_invalid"):
            self.publish(envelope)
        self.assert_no_advance()

    def test_26_stale_challenge_rejected_after_other_publication(self):
        stale = self.signed()
        self.publish()
        with self.assertRaisesRegex(A149Denied, "stale_cas_and_history"):
            self.publish(stale)

    def test_27_same_request_id_cannot_be_used_for_new_challenge(self):
        first = self.signed()
        self.publish(first)
        second = self.signed(
            events=self.events2,
            request_id=first.request.request_id,
        )
        with self.assertRaisesRegex(A149Denied, "request_id_reused"):
            self.publish(second)

    def test_28_monotonic_local_clock_floor_rejects_backward_time(self):
        self.clock.advance(15)
        self.engine.issue_challenge()
        self.clock.advance(-20)
        with self.assertRaisesRegex(A149Denied, "clock_rewind_detected"):
            self.engine.issue_challenge()

    def test_29_clock_rewind_rejects_signed_publish(self):
        envelope = self.signed()
        self.clock.advance(-1)
        with self.assertRaisesRegex(A149Denied, "clock_rewind_detected"):
            self.publish(envelope)

    def test_30_clock_rewind_after_successful_publish_denied(self):
        self.clock.advance(10)
        self.publish()
        self.clock.advance(-11)
        with self.assertRaisesRegex(A149Denied, "clock_rewind_detected"):
            self.engine.issue_challenge()

    def test_31_malformed_clock_type_denied(self):
        self.clock.value = True
        with self.assertRaisesRegex(A149Denied, "invalid_clock_value"):
            self.engine.issue_challenge()

    def test_32_unavailable_clock_denied(self):
        def offline():
            raise OSError("synthetic time unavailable")
        self.engine.clock_ns = offline
        with self.assertRaisesRegex(A149Denied, "lease_clock_unavailable"):
            self.engine.issue_challenge()

    def test_33_missing_lease_row_rejected_on_reopen(self):
        envelope = self.signed()
        with closing(sqlite3.connect(self.engine.db_path)) as db:
            db.execute("DELETE FROM challenge_lease WHERE challenge_id=?",
                       (envelope.request.challenge_id,))
            db.commit()
        with self.assertRaisesRegex(A149Denied, "lease_integrity_failure"):
            self.reopen()

    def test_34_lease_extra_orphan_row_denied(self):
        with closing(sqlite3.connect(self.engine.db_path)) as db:
            db.execute("INSERT INTO challenge_lease VALUES (?,?,?)",
                       (secrets.token_hex(16), self.clock.value,
                        self.clock.value+10*NANOSECONDS_PER_SECOND))
            db.commit()
        with self.assertRaisesRegex(A149Denied, "lease_integrity_failure"):
            self.engine.read_head()

    def test_35_extra_schema_trigger_denied(self):
        with closing(sqlite3.connect(self.engine.db_path)) as db:
            db.execute("CREATE TRIGGER bad AFTER UPDATE ON witness_meta BEGIN SELECT 1; END")
            db.commit()
        with self.assertRaisesRegex(A149Denied, "unexpected_a150_schema_objects"):
            self.reopen()

    def test_36_lease_duration_out_of_allowed_policy_denied(self):
        envelope = self.signed()
        with closing(sqlite3.connect(self.engine.db_path)) as db:
            db.execute("UPDATE challenge_lease SET expires_ns=issued_ns+? WHERE challenge_id=?",
                       ((MAX_LEASE_SECONDS+1)*NANOSECONDS_PER_SECOND,
                        envelope.request.challenge_id))
            db.commit()
        with self.assertRaisesRegex(A149Denied, "lease_integrity_failure"):
            self.engine.read_head()

    def test_37_boolean_lease_seconds_rejected(self):
        with self.assertRaisesRegex(A149Denied, "invalid_lease_seconds"):
            self.reopen(lease_seconds=True)

    def test_38_out_of_range_lease_seconds_rejected(self):
        with self.assertRaisesRegex(A149Denied, "invalid_lease_seconds"):
            self.reopen(lease_seconds=MAX_LEASE_SECONDS+1)

    def test_39_two_parallel_valid_requests_only_one_cas_wins(self):
        first, second = self.signed(), self.signed()
        outcomes = []
        def worker(envelope):
            try:
                self.reopen().publish(envelope=envelope)
                outcomes.append("success")
            except A149Denied:
                outcomes.append("rejected")
        threads = [threading.Thread(target=worker, args=(q,)) for q in (first, second)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(sorted(outcomes), ["rejected","success"])
        self.assertEqual(self.reopen().read_head()["sequence"], 1)

    def test_40_signed_receipt_read_only_after_restart(self):
        envelope = self.signed()
        self.publish(envelope)
        old = self.reopen().read_head()
        retrieved = self.reopen().read_receipt(envelope.request.request_id)
        self.assertEqual(retrieved.receipt.request_id, envelope.request.request_id)
        self.assertEqual(self.reopen().read_head(), old)

    def test_41_negative_snapshot_restores_old_sequence_and_challenge(self):
        # NEGATIVE proof: same machine backup can roll back state and local floor.
        snapshot = self.root / "snapshot.sqlite"
        shutil.copyfile(self.engine.db_path, snapshot)
        envelope = self.signed()
        self.publish(envelope)
        shutil.copyfile(snapshot, self.engine.db_path)
        self.assertEqual(self.reopen().read_head()["sequence"], 0)
        self.assertIsNone(self.reopen().read_receipt(envelope.request.request_id))

    def test_42_negative_caller_supplied_pin_can_be_replaced_with_database(self):
        # NEGATIVE: local operator can replace BOTH SQLite and "out-of-band"
        # in-memory test policy, since we have no external trusted authority.
        attacker = Ed25519PrivateKey.generate()
        with closing(sqlite3.connect(self.engine.db_path)) as db:
            db.execute("UPDATE witness_meta SET publisher_public_hex=?",
                       (raw_public(attacker).hex(),))
            db.commit()
        changed = replace(self.pin, publisher_public_key=raw_public(attacker))
        engine = self.reopen(policy=changed)
        challenge = engine.issue_challenge()
        forged = self.signed(challenge=challenge, signer=attacker)
        self.assertEqual(engine.publish(envelope=forged).receipt.sequence, 1)

    def test_43_negative_clock_spoof_inside_unexpired_window(self):
        # NEGATIVE: clock source is test-supplied; after 100 seconds in real
        # time an attacker could reset it to issued+1 and appear in-window.
        envelope = self.signed()
        issued = self.clock.value
        self.clock.value = issued + NANOSECONDS_PER_SECOND
        self.assertEqual(self.publish(envelope).receipt.sequence, 1)

    def test_44_receipt_does_not_claim_any_external_provider_effect(self):
        receipt = self.publish().receipt
        self.assertEqual(set(receipt.__dataclass_fields__), {
            "ledger_id", "epoch", "request_id", "challenge_id",
            "sequence", "history_digest", "request_digest",
        })

    def test_45_reuse_of_key_material_across_domains_denied(self):
        invalid = replace(self.pin, witness_public_key=self.pin.publisher_public_key)
        with self.assertRaisesRegex(A149Denied, "publisher_witness_key_reused"):
            self.reopen(policy=invalid)

    def test_46_exact_lease_expiration_after_reopen_denies_without_resend(self):
        env = self.signed()
        self.clock.advance(30)
        with self.assertRaisesRegex(A149Denied, "challenge_lease_expired"):
            self.reopen().publish(envelope=env)
        self.assertIsNone(self.reopen().read_receipt(env.request.request_id))

    def test_47_synthetic_lease_expiry_has_no_automatic_reissuance(self):
        env = self.signed()
        self.clock.advance(31)
        with self.assertRaisesRegex(A149Denied, "challenge_lease_expired"):
            self.publish(env)
        self.assertEqual(self.reopen().read_head()["sequence"], 0)

    def test_48_old_engine_api_bypasses_a150_guard_negative(self):
        # NEGATIVE: A149 must not remain an alternate production entry point.
        from aion_p0_a149_authenticated_cas_lab import AuthenticatedWitnessLAB
        with self.assertRaisesRegex(A149Denied, "unexpected_schema_objects"):
            AuthenticatedWitnessLAB(
                witness_dir=self.witness_dir, ledger_id="ledger-A",
            )

    def test_49_declared_publisher_signature_binds_full_digest(self):
        env = self.signed()
        altered = SignedPublishRequest(
            replace(env.request, next_digest="a"*64), env.signature_b64
        )
        with self.assertRaisesRegex(A149Denied, "publisher_signature_invalid"):
            self.publish(altered)

    def test_50_sequential_valid_publisher_updates_use_fresh_lease(self):
        self.publish()
        next_env = self.signed(events=self.events2)
        self.clock.advance(2)
        self.assertEqual(self.publish(next_env).receipt.sequence, 2)


    def test_51_lease_extension_within_global_limit_denied_by_operator_pin(self):
        env = self.signed()
        with closing(sqlite3.connect(self.engine.db_path)) as db:
            db.execute("UPDATE challenge_lease SET expires_ns=issued_ns+? WHERE challenge_id=?",
                       (60*NANOSECONDS_PER_SECOND, env.request.challenge_id))
            db.commit()
        with self.assertRaisesRegex(A149Denied, "lease_integrity_failure"):
            self.reopen()

    def test_52_lease_shrinking_denied_by_operator_pin(self):
        env = self.signed()
        with closing(sqlite3.connect(self.engine.db_path)) as db:
            db.execute("UPDATE challenge_lease SET expires_ns=issued_ns+? WHERE challenge_id=?",
                       (15*NANOSECONDS_PER_SECOND, env.request.challenge_id))
            db.commit()
        with self.assertRaisesRegex(A149Denied, "lease_integrity_failure"):
            self.engine.read_head()

    def test_53_runtime_lease_setting_must_match_enrolled_operator_policy(self):
        with self.assertRaisesRegex(A149Denied, "operator_lease_policy_mismatch"):
            self.reopen(lease_seconds=60)

    def test_54_operator_pin_cannot_declare_boolean_lease(self):
        altered = replace(self.pin, lease_seconds=True)
        with self.assertRaisesRegex(A149Denied, "invalid_external_lease_policy"):
            self.reopen(policy=altered)

    def test_55_operator_lease_pin_mismatch_denied_on_reopen(self):
        altered = replace(self.pin, lease_seconds=60)
        with self.assertRaisesRegex(A149Denied, "operator_lease_policy_mismatch"):
            self.reopen(policy=altered)

    def test_56_negative_attacker_can_shift_both_lease_timestamps_in_mutable_db(self):
        # NEGATIVE proof: exact duration pin cannot stop a DB owner from
        # shifting BOTH issued and expires to a newer artificial interval.
        env = self.signed()
        initial = self.clock.value
        self.clock.advance(40)  # Original 30s lease is expired.
        with closing(sqlite3.connect(self.engine.db_path)) as db:
            db.execute(
                "UPDATE challenge_lease SET issued_ns=?,expires_ns=? WHERE challenge_id=?",
                (initial+20*NANOSECONDS_PER_SECOND,
                 initial+50*NANOSECONDS_PER_SECOND, env.request.challenge_id),
            )
            db.commit()
        # Still accepted in LAB: illustrates need for independently
        # authenticated issued timestamp / tamper-resistant lease register.
        self.assertEqual(self.publish(env).receipt.sequence, 1)

if __name__ == "__main__":
    unittest.main()
