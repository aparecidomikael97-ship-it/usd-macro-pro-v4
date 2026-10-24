"""G22: actual AION Outbox + G21 bridge coordinated local rollback RED.

A FakeWitness is controlled by the same hostile host, not independently
trusted. Passing RED tests demonstrates an unresolved weakness, not a fix.
No dispatch/provider and no production changes.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from g20_independent_witness_recovery_contract_lab import (
    Admission, RecoveryDenied, WitnessAttestation, canonical_hash,
)
from g21_real_outbox_witness_recovery_bridge_lab import inspect_outbox_recovery

ROOT = "G22_HOST_CONTROLLED_FAKE_ROOT"
SCOPE = Scope("g22-owner", "g22-tenant", "g22-workspace")
NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)


class HostControlledWitness:
    """Simulated compromised witness. NOT a valid independent trust root."""
    def __init__(self, attestation):
        self.attestation = attestation

    def attest_latest(self, key):
        return self.attestation

    def verify(self, statement, pinned_root_id):
        return True  # Intentional RED: host can claim any signature is valid.


def projection(row):
    return {
        "semantic_key": row["idempotency_key"],
        "sequence": row["attempts"] + 1,
        "phase": "UNCERTAIN" if row["state"] == "UNCERTAIN" else "RESERVED",
        "outbox_state": row["state"],
        "outbox_idempotency_key": row["idempotency_key"],
        "outbox_attempts": row["attempts"],
    }


def forged_witness(row):
    document = projection(row)
    return HostControlledWitness(WitnessAttestation(
        semantic_key=row["idempotency_key"],
        sequence=document["sequence"],
        phase=document["phase"],
        journal_digest=canonical_hash(document),
        trust_root_id=ROOT,
        signed_statement=b"FAKE-HOST-ATTESTATION",
    ))


def enqueue(outbox, intent):
    return outbox.enqueue(
        intent_ref=intent,
        action="synthetic_no_send",
        payload={"synthetic": "g22", "amount": 17},
        aggregate_key="g22-aggregate",
        policy_version="g22-policy",
        authorization_ref="g22-fake-authorization",
        created_at=NOW,
        valid_until=NOW + timedelta(minutes=5),
    )


class G22CoordinatedRollbackRed(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aion-g22-host-red-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "outbox.sqlite3"

    def open_outbox(self):
        store = SQLiteChatStore(self.path)
        return store, ExecutionOutbox(store, SCOPE)

    def test_01_host_can_rewind_both_outbox_and_fake_witness_red(self):
        store, outbox = self.open_outbox()
        try:
            first = enqueue(outbox, "g22-semantic-1")
            first_row = outbox.get(first["idempotency_key"])
            old_witness = forged_witness(first_row)
            # Independent observation: a later local decision exists.
            later = enqueue(outbox, "g22-semantic-2")
            self.assertEqual(len(outbox.list()), 2)
        finally:
            store.close()
        # The host rewrites BOTH local journal and fake witness to old state.
        # Use fresh old DB from before second enqueue, built deterministically
        # with the same synthetic input in a separate temp path.
        old_path = Path(self.temp.name) / "old.sqlite3"
        saved_current = Path(self.temp.name) / "new.sqlite3"
        shutil.copyfile(self.path, saved_current)
        store_old = SQLiteChatStore(old_path)
        try:
            old_outbox = ExecutionOutbox(store_old, SCOPE)
            old_first = enqueue(old_outbox, "g22-semantic-1")
            self.assertEqual(old_first["idempotency_key"], first["idempotency_key"])
        finally:
            store_old.close()
        shutil.copyfile(old_path, self.path)
        restored_store, restored_outbox = self.open_outbox()
        try:
            self.assertEqual(len(restored_outbox.list()), 1)
            self.assertEqual(
                inspect_outbox_recovery(
                    outbox=restored_outbox,
                    idempotency_key=first["idempotency_key"],
                    witness=old_witness,
                    pinned_root_id=ROOT,
                ),
                Admission.UNCERTAIN,
            )
            self.assertEqual(restored_outbox.list()[0]["idempotency_key"],
                             first["idempotency_key"])
            self.assertNotIn(later["idempotency_key"],
                             [item["idempotency_key"] for item in restored_outbox.list()])
            print("G22_COORDINATED_HOST_ROLLBACK_RED=OLD_HISTORY_FAKE_WITNESS_MATCHES")
        finally:
            restored_store.close()

    def test_02_host_can_forge_current_attestation_red(self):
        store, outbox = self.open_outbox()
        try:
            first = enqueue(outbox, "g22-semantic-1")
            witness = forged_witness(outbox.get(first["idempotency_key"]))
            self.assertEqual(inspect_outbox_recovery(
                outbox=outbox,
                idempotency_key=first["idempotency_key"],
                witness=witness,
                pinned_root_id=ROOT,
            ), Admission.UNCERTAIN)
            print("G22_HOST_FORGED_SIGNATURE_RED=FAKE_VERIFY_TRUE_IS_ACCEPTED")
        finally:
            store.close()

    def test_03_independent_witness_absent_still_denies(self):
        store, outbox = self.open_outbox()
        try:
            first = enqueue(outbox, "g22-semantic-1")
            with self.assertRaisesRegex(RecoveryDenied, "INDEPENDENT_WITNESS_MISSING"):
                inspect_outbox_recovery(
                    outbox=outbox,
                    idempotency_key=first["idempotency_key"],
                    witness=None,
                    pinned_root_id=ROOT,
                )
        finally:
            store.close()

    def test_04_host_replay_of_old_journal_cannot_prove_new_intent(self):
        store, outbox = self.open_outbox()
        try:
            first = enqueue(outbox, "g22-semantic-1")
            old = forged_witness(outbox.get(first["idempotency_key"]))
            second = enqueue(outbox, "g22-semantic-2")
            with self.assertRaisesRegex(RecoveryDenied, "WITNESS_SEMANTIC_MISMATCH"):
                inspect_outbox_recovery(
                    outbox=outbox,
                    idempotency_key=second["idempotency_key"],
                    witness=old,
                    pinned_root_id=ROOT,
                )
        finally:
            store.close()

    def test_05_distinct_request_refs_still_create_two_outbox_keys_red(self):
        store, outbox = self.open_outbox()
        try:
            one = enqueue(outbox, "g22-request-A")
            two = enqueue(outbox, "g22-request-B")
            self.assertNotEqual(one["idempotency_key"], two["idempotency_key"])
            self.assertEqual(len(outbox.list()), 2)
            print("G22_SEMANTIC_ALIAS_RED=REAL_OUTBOX_DISTINCT_REQUEST_REFS")
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
