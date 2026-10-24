"""G21 read-only bridge against actual AION SQLiteChatStore + ExecutionOutbox."""
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


NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
ROOT = "g21-synthetic-only-root"
SCOPE = Scope("g21-owner", "g21-tenant", "g21-workspace")


class FakeWitness:
    """Synthetic test double: verify() is NOT cryptographic verification."""
    def __init__(self, statement, verified=True, offline=False):
        self.statement = statement
        self.verified = verified
        self.offline = offline

    def attest_latest(self, semantic_key):
        if self.offline:
            raise TimeoutError("synthetic witness unavailable")
        return self.statement

    def verify(self, statement, pinned_root_id):
        return self.verified


def envelope(row):
    return {
        "semantic_key": row["idempotency_key"],
        "sequence": row["attempts"] + 1,
        "phase": "UNCERTAIN" if row["state"] == "UNCERTAIN" else "RESERVED",
        "outbox_state": row["state"],
        "outbox_idempotency_key": row["idempotency_key"],
        "outbox_attempts": row["attempts"],
    }


def witness_for(row, *, sequence=None, digest=None, verified=True, offline=False):
    doc = envelope(row)
    statement = WitnessAttestation(
        semantic_key=row["idempotency_key"],
        sequence=doc["sequence"] if sequence is None else sequence,
        phase=doc["phase"],
        journal_digest=canonical_hash(doc) if digest is None else digest,
        trust_root_id=ROOT,
        signed_statement=b"synthetic-fake-signature",
    )
    return FakeWitness(statement, verified=verified, offline=offline)


class G21RealOutboxReadOnlyBridge(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aion-g21-real-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "aion.sqlite3"
        self.store = SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        self.outbox = ExecutionOutbox(self.store, SCOPE)
        self.item = self.outbox.enqueue(
            intent_ref="g21-intent-1",
            action="synthetic_no_send",
            payload={"synthetic": True},
            aggregate_key="g21-aggregate",
            policy_version="g21-policy",
            authorization_ref="g21-placeholder",
            created_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )
        self.key = self.item["idempotency_key"]

    def read_row(self):
        return self.outbox.get(self.key)

    def admit(self, witness, *, key=None, root=ROOT):
        return inspect_outbox_recovery(
            outbox=self.outbox,
            idempotency_key=self.key if key is None else key,
            witness=witness,
            pinned_root_id=root,
        )

    def deny(self, fragment, witness, **kwargs):
        with self.assertRaisesRegex(RecoveryDenied, fragment):
            self.admit(witness, **kwargs)

    def test_01_real_outbox_matching_synthetic_witness_uncertain_only(self):
        self.assertEqual(self.admit(witness_for(self.read_row())),
                         Admission.UNCERTAIN)

    def test_02_real_outbox_no_witness_denies(self):
        self.deny("INDEPENDENT_WITNESS_MISSING", None)

    def test_03_real_outbox_offline_witness_denies(self):
        self.deny("INDEPENDENT_WITNESS_UNAVAILABLE",
                  witness_for(self.read_row(), offline=True))

    def test_04_real_outbox_fake_signature_rejected_when_verifier_denies(self):
        self.deny("WITNESS_SIGNATURE_UNTRUSTED",
                  witness_for(self.read_row(), verified=False))

    def test_05_real_outbox_missing_pinned_root_denies(self):
        self.deny("INDEPENDENT_PINNED_ROOT_MISSING",
                  witness_for(self.read_row()), root="")

    def test_06_real_outbox_wrong_pinned_root_denies(self):
        self.deny("WITNESS_ROOT_MISMATCH",
                  witness_for(self.read_row()), root="other")

    def test_07_real_outbox_sequence_rollback_denies(self):
        self.deny("LOCAL_SEQUENCE_MISMATCH",
                  witness_for(self.read_row(), sequence=999))

    def test_08_real_outbox_changed_digest_denies(self):
        self.deny("LOCAL_DIGEST_MISMATCH",
                  witness_for(self.read_row(), digest="0" * 64))

    def test_09_real_outbox_missing_row_denies(self):
        self.deny("G21_REAL_OUTBOX_ROW_MISSING",
                  witness_for(self.read_row()), key="not-present")

    def test_10_real_outbox_read_does_not_claim_or_dispatch(self):
        before = self.read_row()
        self.assertEqual(self.admit(witness_for(before)), Admission.UNCERTAIN)
        self.assertEqual(self.read_row(), before)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_11_reopen_real_outbox_after_restart_remains_uncertain(self):
        # The same SQLite file can be read by another store instance; this
        # is NOT an adversarial restart witness or H0 proof.
        other_store = SQLiteChatStore(self.path)
        try:
            other_outbox = ExecutionOutbox(other_store, SCOPE)
            self.assertEqual(
                inspect_outbox_recovery(
                    outbox=other_outbox,
                    idempotency_key=self.key,
                    witness=witness_for(self.read_row()),
                    pinned_root_id=ROOT,
                ),
                Admission.UNCERTAIN,
            )
        finally:
            other_store.close()

    def test_12_real_outbox_recovery_without_external_proof_denies(self):
        self.deny("INDEPENDENT_WITNESS_MISSING", None)


if __name__ == "__main__":
    unittest.main()
