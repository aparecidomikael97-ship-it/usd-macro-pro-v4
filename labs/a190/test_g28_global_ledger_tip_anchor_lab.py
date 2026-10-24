"""G28 adversarial global-tip harness: cross-key rollback fail-closed.

Signed anchor is only another synthetic in-process object.
No external independent counter, operational first-send, or real provider.
"""
from pathlib import Path
import shutil
import tempfile
import unittest
from dataclasses import replace

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from g20_independent_witness_recovery_contract_lab import Admission, RecoveryDenied, canonical_hash
from g24_challenge_bound_witness_lab import new_challenge
from g27_durable_sqlite_custody_lab import DurableCustodyLab
from g28_global_ledger_tip_anchor_lab import (
    GlobalTip, SignedGlobalTip, SimulatedExternalAnchor,
    inspect_recovery_against_anchor, read_local_tip,
)

ROOT = "G28_SIMULATED_OUTSIDE_HOST_PIN"
FIRST = "tenant:invoice:42"
SECOND = "tenant:invoice:43"


def journal(key, seq):
    return {"semantic_key": key, "sequence": seq, "phase": "UNCERTAIN"}


class G28GlobalTip(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="aion-g28-")
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.path = self.dir / "host-custody.sqlite3"
        self.private = Ed25519PrivateKey.generate()
        self.public = self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.db = DurableCustodyLab(self.path, self.private, ROOT)
        self.addCleanup(lambda: self.db.close())
        self.anchor = SimulatedExternalAnchor(self.private, ROOT)
        self.db.reserve(FIRST, "UNCERTAIN", canonical_hash(journal(FIRST, 1)))
        self.anchor.advance(read_local_tip(self.db))
        self.challenge = new_challenge()

    def second(self):
        self.db.reserve(SECOND, "UNCERTAIN", canonical_hash(journal(SECOND, 2)))
        return read_local_tip(self.db)

    def check(self, anchor=None, db=None, response=None, challenge=None, pub=None, root=ROOT):
        obj = self.anchor if anchor is None else anchor
        local = self.db if db is None else db
        nonce = self.challenge if challenge is None else challenge
        signed = obj.challenge_attestation(nonce) if response is None else response
        return inspect_recovery_against_anchor(
            custody=local, attestation=signed,
            verifier_challenge=nonce,
            pinned_public_key=self.public if pub is None else pub,
            pinned_root_id=root,
        )

    def deny(self, message, **kwargs):
        with self.assertRaisesRegex(RecoveryDenied, message):
            self.check(**kwargs)

    def test_01_one_record_tip_matches(self):
        self.assertEqual(self.check(), Admission.UNCERTAIN)

    def test_02_second_reservation_new_anchor_matches(self):
        self.anchor.advance(self.second())
        self.assertEqual(self.check(), Admission.UNCERTAIN)

    def test_03_second_reservation_not_anchored_denies(self):
        self.second()
        self.deny("G28_GLOBAL_SEQUENCE_MISMATCH")
        print("G28_NONATOMIC_GAP_RED=LOCAL_COMMIT_AHEAD_OF_ANCHOR_DENIED")

    def test_04_older_anchor_cannot_overwrite_latest(self):
        old = read_local_tip(self.db)
        self.anchor.advance(self.second())
        with self.assertRaisesRegex(RecoveryDenied, "G28_NON_MONOTONIC_ANCHOR_ADVANCE"):
            self.anchor.advance(old)

    def test_05_cross_semantic_key_rollback_detected_when_anchor_retained(self):
        self.db.close()
        old_path = self.dir / "old.sqlite3"
        shutil.copyfile(self.path, old_path)
        self.db = DurableCustodyLab(self.path, self.private, ROOT)
        self.anchor.advance(self.second())
        self.db.close()
        shutil.copyfile(old_path, self.path)
        self.db = DurableCustodyLab(self.path, self.private, ROOT)
        self.deny("G28_GLOBAL_SEQUENCE_MISMATCH")
        print("G28_CROSS_KEY_ROLLBACK_GREEN=GLOBAL_ANCHOR_DETECTS_MISSING_OTHER_INTENT")

    def test_06_same_host_anchor_rollback_red(self):
        self.db.close()
        old_path = self.dir / "old.sqlite3"
        shutil.copyfile(self.path, old_path)
        old_anchor = SimulatedExternalAnchor(self.private, ROOT)
        old_anchor.advance(read_local_tip(self.db_open_old()))
        self.db = DurableCustodyLab(self.path, self.private, ROOT)
        self.anchor.advance(self.second())
        self.db.close()
        shutil.copyfile(old_path, self.path)
        self.db = DurableCustodyLab(self.path, self.private, ROOT)
        self.assertEqual(self.check(anchor=old_anchor), Admission.UNCERTAIN)
        print("G28_CO_ROLLBACK_RED=HOST_CAN_RESTORE_DB_AND_ANCHOR")

    def db_open_old(self):
        # A short-lived read-only-in-intent handle (closed by test cleanup).
        with DurableCustodyLab(self.path, self.private, ROOT) as read_db:
            return _TipOnly(read_local_tip(read_db))

    def test_07_anchor_unavailable_denies(self):
        with self.assertRaisesRegex(RecoveryDenied, "G28_ANCHOR_UNAVAILABLE"):
            inspect_recovery_against_anchor(
                custody=self.db, attestation=None,
                verifier_challenge=self.challenge,
                pinned_public_key=self.public, pinned_root_id=ROOT,
            )

    def test_08_invalid_root_denies(self):
        self.deny("G28_ROOT_MISMATCH", root="other")

    def test_09_unpinned_key_denies(self):
        self.deny("G28_TRUST_ROOT_UNPROVISIONED", pub=b"short")

    def test_10_wrong_key_denies(self):
        other = Ed25519PrivateKey.generate()
        pub = other.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.deny("G28_ANCHOR_SIGNATURE_INVALID", pub=pub)

    def test_11_signature_mutation_denies(self):
        good = self.anchor.challenge_attestation(self.challenge)
        bad = replace(good, signature=bytes([good.signature[0] ^ 1]) + good.signature[1:])
        self.deny("G28_ANCHOR_SIGNATURE_INVALID", response=bad)

    def test_12_replay_old_response_to_new_challenge_denies(self):
        response = self.anchor.challenge_attestation(self.challenge)
        self.deny("G28_CHALLENGE_MISMATCH", response=response, challenge=new_challenge())

    def test_13_signed_tip_counter_mutation_denies(self):
        good = self.anchor.challenge_attestation(self.challenge)
        bad = replace(good, tip=replace(good.tip, sequence=99))
        self.deny("G28_ANCHOR_SIGNATURE_INVALID", response=bad)

    def test_14_signed_tip_digest_mutation_denies(self):
        good = self.anchor.challenge_attestation(self.challenge)
        bad = replace(good, tip=replace(good.tip, ledger_digest="0"*64))
        self.deny("G28_ANCHOR_SIGNATURE_INVALID", response=bad)

    def test_15_same_sequence_conflicting_tip_denies(self):
        tip = read_local_tip(self.db)
        with self.assertRaisesRegex(RecoveryDenied, "G28_NON_MONOTONIC_ANCHOR_ADVANCE"):
            self.anchor.advance(replace(tip, ledger_digest="f"*64))

    def test_16_anchor_has_no_tip_denies(self):
        missing = SimulatedExternalAnchor(self.private, ROOT)
        with self.assertRaisesRegex(RecoveryDenied, "G28_ANCHOR_MISSING"):
            missing.challenge_attestation(self.challenge)

    def test_17_anchor_sequence_gap_denies(self):
        with self.assertRaisesRegex(RecoveryDenied, "G28_CANDIDATE_SEQUENCE_GAP"):
            self.anchor.advance(GlobalTip(9, 2, "a"*64))

    def test_18_matching_anchor_never_authorizes_send(self):
        self.assertNotEqual(self.check(), "SEND")


class _TipOnly:
    def __init__(self, tip):
        self.tip = tip


if __name__ == "__main__":
    unittest.main()
