"""A190 G36 — read-only recovery against separate-PROCESS synthetic witness.

All SQLite data and signing keys remain same-host and attacker-copyable.
The witness accepts caller-provided snapshot digests. Passing tests do NOT
establish independent first-send custody or verified external effects.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import shutil
import sqlite3
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from g20_independent_witness_recovery_contract_lab import Admission, RecoveryDenied
from g36_subprocess_witness_custody_lab import (
    ROOT, call_witness, inspect_outbox_against_subprocess_witness,
    outbox_snapshot_digest,
)

SCOPE = Scope("g36-owner", "g36-tenant", "g36-workspace")
NOW = datetime(2026, 10, 24, 16, tzinfo=timezone.utc)
WORKER = "g36-synthetic-worker"


class TrapAdapter:
    def __init__(self):
        self.send_lookups = 0

    @property
    def send(self):
        self.send_lookups += 1
        raise AssertionError("G36_NO_PROVIDER_ACCESS")


class G36SubprocessWitnessRecovery(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="aion-g36-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.local_file = root / "host" / "outbox.sqlite3"
        self.local_file.parent.mkdir()
        self.witness_dir = root / "witness"
        self.store = SQLiteChatStore(self.local_file)
        self.addCleanup(lambda: self.store.close())
        self.outbox = ExecutionOutbox(self.store, SCOPE)
        init = call_witness(self.witness_dir, "init")
        self.pin = bytes.fromhex(init["public_key"])
        self.root_id = init["root_id"]
        self.trap = TrapAdapter()

    def stage(self, *, intent_ref="invoice-42"):
        return self.outbox.enqueue(
            intent_ref=intent_ref, action="synthetic_no_provider",
            payload={"invoice": "invoice-42", "amount_minor": 1000},
            aggregate_key="synthetic-business-aggregate",
            policy_version="policy-v1", authorization_ref="auth-v1",
            created_at=NOW, valid_until=NOW + timedelta(minutes=5),
        )

    def observe(self):
        return call_witness(self.witness_dir, "observe", {
            "snapshot_digest": outbox_snapshot_digest(self.outbox),
        })

    def proof(self, challenge):
        return call_witness(self.witness_dir, "attest", {
            "nonce": challenge.hex(),
        })

    def check(self, *, response=None, nonce=None, key=None, root=None):
        ch = os.urandom(32) if nonce is None else nonce
        result = self.proof(ch) if response is None else response
        return inspect_outbox_against_subprocess_witness(
            outbox=self.outbox, response=result, challenge=ch,
            pinned_root_id=self.root_id if root is None else root,
            pinned_public_key=self.pin if key is None else key,
        )

    def become_uncertain(self):
        row = self.outbox.claim_next(WORKER, now=NOW, lease_seconds=60)
        decision = row["decision"]
        result = self.outbox.dispatch_claimed(
            row["idempotency_key"], worker_id=WORKER,
            authorize=lambda _: {
                "allowed": True, "actor_id": SCOPE.owner_id,
                "policy_version": decision["policy_version"],
                "authorization_ref": decision["authorization_ref"],
            },
            adapter=self.trap, now=NOW + timedelta(seconds=1),
        )
        self.assertEqual(result["state"], "UNCERTAIN")
        self.assertEqual(self.trap.send_lookups, 0)
        self.assertEqual(self.outbox.effect_count(), 0)
        return result

    def reopen_host(self):
        self.store.close()
        self.store = SQLiteChatStore(self.local_file)
        self.outbox = ExecutionOutbox(self.store, SCOPE)

    def test_01_no_observation_denies(self):
        self.stage()
        with self.assertRaisesRegex(RecoveryDenied, "G36_WITNESS_PROCESS_DENIED"):
            self.check()

    def test_02_observe_matching_live_outbox_only_uncertain(self):
        self.stage()
        self.observe()
        self.assertEqual(self.check(), Admission.UNCERTAIN)
        print("G36_SUBPROCESS_MATCH_GREEN=SIGNED_TIP_ONLY_UNCERTAIN")

    def test_03_same_digest_observed_twice_is_idempotent(self):
        self.stage()
        initial = self.observe()
        again = self.observe()
        self.assertEqual(initial["sequence"], again["sequence"])
        self.assertTrue(again["idempotent"])

    def test_04_unobserved_claim_and_uncertain_transitions_denied(self):
        self.stage()
        self.observe()
        self.become_uncertain()
        with self.assertRaisesRegex(RecoveryDenied, "G36_LOCAL_SNAPSHOT_BEHIND_OR_DIVERGENT"):
            self.check()
        print("G36_UNANCHORED_STATE_GREEN=UNCERTAIN_DENIED_UNTIL_WITNESS_OBSERVES")

    def test_05_latest_observation_after_uncertain_only_uncertain(self):
        self.stage()
        self.observe()
        self.become_uncertain()
        head = self.observe()
        self.assertEqual(head["sequence"], 2)
        self.assertEqual(self.check(), Admission.UNCERTAIN)
        self.assertEqual(self.trap.send_lookups, 0)

    def test_06_host_reopen_with_durable_witness_valid_only_uncertain(self):
        self.stage()
        self.observe()
        self.become_uncertain()
        self.observe()
        self.reopen_host()
        self.assertEqual(self.outbox.list()[0]["state"], "UNCERTAIN")
        self.assertEqual(self.check(), Admission.UNCERTAIN)
        self.assertIsNone(self.outbox.claim_next(WORKER, now=NOW + timedelta(minutes=2)))
        print("G36_RESTART_GREEN=HOST_REOPEN_TIP_MATCH_ZERO_AUTO_RESEND")

    def test_07_old_host_sqlite_snapshot_denied_if_witness_retained(self):
        self.stage()
        self.observe()
        self.store.close()
        saved = self.local_file.parent / "old-host.sqlite3"
        shutil.copyfile(self.local_file, saved)
        self.reopen_host()
        self.become_uncertain()
        self.observe()
        self.store.close()
        shutil.copyfile(saved, self.local_file)
        self.reopen_host()
        self.assertEqual(self.outbox.list()[0]["state"], "PENDING")
        with self.assertRaisesRegex(RecoveryDenied, "G36_LOCAL_SNAPSHOT_BEHIND_OR_DIVERGENT"):
            self.check()
        print("G36_HOST_ROLLBACK_GREEN=RETAINED_TIP_DETECTS_OLD_OUTBOX")

    def test_08_same_host_corollback_of_witness_and_outbox_red(self):
        self.stage()
        self.observe()
        self.store.close()
        old_host = self.local_file.parent / "old-host.sqlite3"
        old_witness = self.witness_dir / "old-witness.sqlite3"
        shutil.copyfile(self.local_file, old_host)
        shutil.copyfile(self.witness_dir / "custody.sqlite3", old_witness)
        self.reopen_host()
        self.become_uncertain()
        latest = self.observe()
        self.assertEqual(latest["sequence"], 2)
        self.store.close()
        shutil.copyfile(old_host, self.local_file)
        shutil.copyfile(old_witness, self.witness_dir / "custody.sqlite3")
        self.reopen_host()
        self.assertEqual(self.check(), Admission.UNCERTAIN)
        print("G36_SAME_HOST_COROLLBACK_RED=DB_AND_WITNESS_OLD_STATE_ACCEPTED")

    def test_09_wrong_public_key_denies(self):
        self.stage()
        self.observe()
        with self.assertRaisesRegex(RecoveryDenied, "G36_INVALID_PINNED_SIGNATURE"):
            self.check(key=b"\x00" * 32)

    def test_10_wrong_root_denies(self):
        self.stage()
        self.observe()
        with self.assertRaisesRegex(RecoveryDenied, "G36_ROOT_UNTRUSTED"):
            self.check(root="wrong-root")

    def test_11_replayed_old_nonce_denies(self):
        self.stage()
        self.observe()
        challenge = os.urandom(32)
        proof = self.proof(challenge)
        with self.assertRaisesRegex(RecoveryDenied, "G36_CHALLENGE_MISMATCH"):
            self.check(response=proof, nonce=os.urandom(32))

    def test_12_signature_tamper_denies(self):
        self.stage()
        self.observe()
        nonce = os.urandom(32)
        signed = self.proof(nonce)
        broken = dict(signed)
        broken["signature"] = "00" * 64
        with self.assertRaisesRegex(RecoveryDenied, "G36_INVALID_PINNED_SIGNATURE"):
            self.check(response=broken, nonce=nonce)

    def test_13_no_witness_response_denies(self):
        self.stage()
        with self.assertRaisesRegex(RecoveryDenied, "G36_WITNESS_MISSING"):
            inspect_outbox_against_subprocess_witness(
                outbox=self.outbox, response=None, challenge=os.urandom(32),
                pinned_root_id=self.root_id, pinned_public_key=self.pin,
            )

    def test_14_process_restarted_and_key_pinned_unchanged(self):
        self.stage()
        self.observe()
        next_init = call_witness(self.witness_dir, "init")
        self.assertEqual(next_init["public_key"], self.pin.hex())
        self.assertEqual(self.check(), Admission.UNCERTAIN)

    def test_15_bad_digest_observation_denied(self):
        with self.assertRaisesRegex(RecoveryDenied, "G36_WITNESS_PROCESS_DENIED"):
            call_witness(self.witness_dir, "observe", {
                "snapshot_digest": "not-a-digest",
            })

    def test_16_bad_nonce_denied(self):
        self.observe()
        with self.assertRaisesRegex(RecoveryDenied, "G36_WITNESS_PROCESS_DENIED"):
            call_witness(self.witness_dir, "attest", {"nonce": "bad"})

    def test_17_latest_row_direct_tamper_denied_by_chain_self_check(self):
        self.stage()
        self.observe()
        with sqlite3.connect(self.witness_dir / "custody.sqlite3") as db:
            db.execute("UPDATE witness_log SET snapshot_digest=?", ("f" * 64,))
        with self.assertRaisesRegex(RecoveryDenied, "G36_WITNESS_PROCESS_DENIED"):
            self.check()

    def test_18_host_can_submit_dishonest_digest_to_witness_red(self):
        self.stage()
        local = outbox_snapshot_digest(self.outbox)
        fake = "a" * 64 if local != "a" * 64 else "b" * 64
        observed = call_witness(self.witness_dir, "observe", {"snapshot_digest": fake})
        self.assertEqual(observed["snapshot_digest"], fake)
        with self.assertRaisesRegex(RecoveryDenied, "G36_LOCAL_SNAPSHOT_BEHIND_OR_DIVERGENT"):
            self.check()
        print("G36_UNTRUSTED_OBSERVATION_RED=WITNESS_SIGNED_HOST_SUPPLIED_FALSE_TIP")

    def test_19_two_alias_intent_refs_both_recorded_no_semantic_unification_red(self):
        first = self.stage()
        second = self.stage(intent_ref="different-caller-request-id")
        self.assertNotEqual(first["idempotency_key"], second["idempotency_key"])
        self.assertEqual(len(self.outbox.list()), 2)
        self.observe()
        self.assertEqual(self.check(), Admission.UNCERTAIN)
        print("G36_SEMANTIC_ALIAS_RED=TWO_CALLER_REFS_ONE_BUSINESS_OPERATION")

    def test_20_witness_reset_with_new_key_denied_by_pinned_root(self):
        self.stage()
        self.observe()
        shutil.rmtree(self.witness_dir)
        new_pin = bytes.fromhex(call_witness(self.witness_dir, "init")["public_key"])
        self.assertNotEqual(new_pin, self.pin)
        self.observe()
        with self.assertRaisesRegex(RecoveryDenied, "G36_INVALID_PINNED_SIGNATURE"):
            self.check()
        print("G36_PIN_RESET_GREEN=NEW_WITNESS_KEY_NOT_PINNED")


if __name__ == "__main__":
    unittest.main()
