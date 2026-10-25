"""AION A190 G53 LAB: direct synthetic _confirm must be terminal-immutable.

All effects are local SQLite fixtures, NOT authentic receipts or provider sends.
Tests are committed BEFORE the candidate patch for falsifiable RED/GREEN.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 25, 17, tzinfo=timezone.utc)
SCOPE = Scope("g53-owner", "g53-tenant", "g53-space")


class G53DirectConfirmImmutability(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="g53-direct-confirm-")
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "synthetic.sqlite3"
        self.store = SQLiteChatStore(self.path)
        self.addCleanup(self.store.close)
        # Intentionally leave both optional integrity/CAS flags DISABLED.
        self.outbox = ExecutionOutbox(self.store, SCOPE)
        self.key = self.outbox.enqueue(
            intent_ref="g53-local-intent", action="synthetic_no_provider",
            payload={"amount_minor": 17}, aggregate_key="g53-lab",
            policy_version="p1", authorization_ref="synthetic-ref",
            created_at=NOW, valid_until=NOW + timedelta(minutes=5),
        )["idempotency_key"]

    def phase(self, phase):
        if phase not in {"UNCERTAIN", "SENT", "PENDING", "CLAIMED",
                         "FAILED", "REVOKED", "BLOCKED_REAPPROVAL", "RETRY"}:
            raise ValueError("fixture phase")
        self.store.db.execute(
            "UPDATE action_outbox SET state=? WHERE idempotency_key=?",
            (phase, self.key))
        self.store.db.commit()

    def local_confirm(self, ref="synthetic-effect-1", at=None, result=None):
        return self.outbox._confirm(
            self.key, effect_ref=ref,
            confirmed_at=at or NOW + timedelta(minutes=1),
            result=result,
        )

    def current(self):
        return self.outbox.get(self.key)

    def ledger(self):
        return self.store.db.execute(
            "SELECT effect_ref,confirmed_at,data FROM action_effects "
            "WHERE idempotency_key=? AND owner=? AND tenant=? AND workspace=?",
            (self.key, SCOPE.owner_id, SCOPE.tenant_id, SCOPE.workspace_id),
        ).fetchall()

    def test_01_allowed_synthetic_uncertain_local_confirmation(self):
        self.phase("UNCERTAIN")
        got = self.local_confirm()
        self.assertEqual(got["state"], "CONFIRMED")
        self.assertEqual(len(self.ledger()), 1)
        self.assertEqual(self.ledger()[0]["effect_ref"], "synthetic-effect-1")
        print("G53_UNCERTAIN_GREEN=ONE_LOCAL_EFFECT")

    def test_02_allowed_synthetic_sent_local_confirmation(self):
        self.phase("SENT")
        got = self.local_confirm()
        self.assertEqual(got["state"], "CONFIRMED")
        self.assertEqual(len(self.ledger()), 1)

    def test_03_same_receipt_reconfirm_preserves_original_timestamp(self):
        self.phase("UNCERTAIN")
        self.local_confirm(result={"synthetic": "initial"})
        before = self.current()
        ledger_before = tuple(self.ledger()[0])
        got = self.local_confirm(
            at=NOW+timedelta(hours=4), result={"synthetic":"replayed"})
        self.assertEqual(got["confirmed_at"], before["confirmed_at"])
        self.assertEqual(got["effect_ref"], before["effect_ref"])
        self.assertEqual(tuple(self.ledger()[0]), ledger_before)
        self.assertEqual(len(self.ledger()), 1)
        print("G53_RECONFIRM_GREEN=ORIGINAL_RECEIPT_IMMUTABLE")

    def test_04_confirmed_row_conflicting_reference_denied(self):
        self.phase("UNCERTAIN")
        self.local_confirm()
        before = self.current()
        with self.assertRaises((ValueError, RuntimeError)):
            self.local_confirm(ref="second-effect",at=NOW+timedelta(hours=2))
        self.assertEqual(self.current(), before)
        self.assertEqual(len(self.ledger()), 1)

    def test_05_confirmed_row_missing_ledger_denied(self):
        self.phase("UNCERTAIN")
        self.local_confirm()
        self.store.db.execute(
            "DELETE FROM action_effects WHERE idempotency_key=?", (self.key,))
        self.store.db.commit()
        before = self.current()
        with self.assertRaisesRegex(
            RuntimeError, "G42_CONFIRMED_LEDGER_INVARIANT_DENY"):
            self.local_confirm(at=NOW+timedelta(hours=2))
        self.assertEqual(self.current(), before)
        self.assertEqual(len(self.ledger()), 0)
        print("G53_MISSING_LEDGER_GREEN=DENY_NOT_REPAIR")

    def test_06_confirmed_row_conflicting_ledger_time_denied(self):
        self.phase("UNCERTAIN")
        self.local_confirm()
        self.store.db.execute(
            "UPDATE action_effects SET confirmed_at=? WHERE idempotency_key=?",
            ("1999-01-01T00:00:00+00:00", self.key))
        self.store.db.commit()
        before = self.current()
        ledger_before = tuple(self.ledger()[0])
        with self.assertRaisesRegex(
            RuntimeError, "G42_CONFIRMED_LEDGER_INVARIANT_DENY"):
            self.local_confirm()
        self.assertEqual(self.current(), before)
        self.assertEqual(tuple(self.ledger()[0]), ledger_before)
        print("G53_CONTRADICTORY_LEDGER_GREEN=DENY_WITHOUT_REPAIR")

    def test_07_all_invalid_direct_phases_denied_without_ledger(self):
        for phase in ("PENDING", "CLAIMED", "RETRY", "FAILED",
                      "REVOKED", "BLOCKED_REAPPROVAL"):
            with self.subTest(phase=phase):
                self.phase(phase)
                before = self.current()
                with self.assertRaisesRegex(
                    RuntimeError, "G42_UNSAFE_PRECONFIRM_PHASE_DENY"):
                    self.local_confirm()
                self.assertEqual(self.current(), before)
                self.assertEqual(len(self.ledger()), 0)
                self.assertFalse(self.store.db.in_transaction)
        print("G53_TERMINAL_GREEN=NO_RESURRECT_OR_PREMATURE_EFFECT")

    def test_08_nonterminal_row_with_orphan_effect_denied(self):
        self.phase("UNCERTAIN")
        self.local_confirm()
        self.phase("SENT")
        before = self.current()
        ledger_before = tuple(self.ledger()[0])
        with self.assertRaisesRegex(
            RuntimeError, "G53_NONCONFIRMED_HAS_EFFECT_DENY"):
            self.local_confirm(at=NOW+timedelta(hours=3))
        self.assertEqual(self.current(), before)
        self.assertEqual(tuple(self.ledger()[0]), ledger_before)
        print("G53_ORPHAN_LEDGER_GREEN=DENY_INCONSISTENT_PHASE")

    def test_09_direct_confirm_without_effect_does_not_mutate(self):
        self.phase("UNCERTAIN")
        before = self.current()
        with self.assertRaises((ValueError, TypeError)):
            self.local_confirm(ref="")
        self.assertEqual(self.current(), before)
        self.assertEqual(len(self.ledger()), 0)

    def test_10_scoped_confirmation_cannot_read_other_owners_effect(self):
        self.phase("UNCERTAIN")
        foreign = ExecutionOutbox(
            self.store, Scope("foreign-owner","foreign-tenant","foreign-space"))
        before = self.current()
        with self.assertRaises(Exception):
            foreign._confirm(self.key,effect_ref="foreign-local",
                             confirmed_at=NOW+timedelta(minutes=1))
        self.assertEqual(self.current(), before)
        self.assertEqual(len(self.ledger()), 0)

    def test_11_db_is_usable_after_rejected_terminal_confirmation(self):
        self.phase("REVOKED")
        with self.assertRaisesRegex(
            RuntimeError, "G42_UNSAFE_PRECONFIRM_PHASE_DENY"):
            self.local_confirm()
        self.assertFalse(self.store.db.in_transaction)
        self.assertEqual(self.current()["state"], "REVOKED")
        self.assertEqual(len(self.ledger()), 0)


if __name__ == "__main__":
    unittest.main()
