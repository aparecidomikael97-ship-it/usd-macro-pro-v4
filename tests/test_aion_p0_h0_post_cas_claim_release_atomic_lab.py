"""AION P0/H0 RED-FIRST: post-CAS SQLite claim and expiry are atomic.

A hostile SQLite AFTER UPDATE trigger mutates Outbox/decision material within
the claim_next or release_expired_claims transaction. All cases use actual
SQLiteChatStore + ExecutionOutbox in isolated temporary SQLite files.
Expected: fail before COMMIT and preserve original persistent transaction
snapshot. Neither test nor product contacts a real provider or starts Worker.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox

NOW = datetime(2026, 10, 21, 17, 30, tzinfo=timezone.utc)
SCOPE = Scope("postcas-owner", "postcas-tenant", "postcas-workspace")
CLAIM_DENY = "OUTBOX_CLAIM_POST_CAS_INTEGRITY_MISMATCH"
RELEASE_DENY = "OUTBOX_RELEASE_POST_CAS_INTEGRITY_MISMATCH"


class PostCASOutboxIntegrityLab(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="aion-p0-postcas-sqlite-")
        self.addCleanup(temp.cleanup)
        self.store = SQLiteChatStore(Path(temp.name) / "postcas.sqlite3")
        self.addCleanup(self.store.close)
        self.db = self.store.db
        self.box = ExecutionOutbox(self.store, SCOPE)
        self.key = self._enqueue("one")

    def _enqueue(self, label):
        return self.box.enqueue(
            intent_ref="intent-"+label,
            action="stage_lab_only",
            payload={"label":label,"test_only":True},
            aggregate_key="independent-aggregate-"+label,
            policy_version="lab-policy",
            authorization_ref="lab-approval-not-authenticated",
            created_at=NOW,valid_until=NOW+timedelta(minutes=5),
        )["idempotency_key"]

    def _trigger(self, transition, sql):
        condition=(
            "OLD.state IN ('PENDING','RETRY') AND NEW.state='CLAIMED'"
            if transition == "claim"
            else "OLD.state='CLAIMED' AND NEW.state='RETRY'"
        )
        self.db.executescript(
            "CREATE TRIGGER aion_lab_after_cas_change "
            "AFTER UPDATE OF state ON action_outbox "
            "WHEN "+condition+" BEGIN "+sql+"; END;"
        )

    def _mutate(self, transition, clause, *, table="action_outbox"):
        target=(
            "NEW.idempotency_key"
            if table=="action_outbox"
            else "NEW.decision_id"
        )
        selector=("idempotency_key" if table=="action_outbox" else "decision_id")
        self._trigger(
            transition,
            "UPDATE "+table+" SET "+clause+" WHERE "+selector+"="+target,
        )

    def _effect(self, transition):
        self._trigger(
            transition,
            "INSERT INTO action_effects "
            "(idempotency_key,owner,tenant,workspace,effect_ref,confirmed_at,data) "
            "VALUES (NEW.idempotency_key,NEW.owner,NEW.tenant,NEW.workspace,"
            "'unverified-lab-effect','2026-10-21T17:30:01+00:00','{}')",
        )

    def _dump(self):
        return tuple(self.db.iterdump())

    def _raw_state(self,key=None):
        return self.db.execute(
            "SELECT state,attempts,lease_owner,lease_until,dispatch_started_at,"
            "sent_at,confirmed_at,effect_ref,last_error FROM action_outbox "
            "WHERE idempotency_key=?",
            (self.key if key is None else key,),
        ).fetchone()

    def _assert_denied_claim(self, reason=CLAIM_DENY):
        before=self._dump()
        snapshot=tuple(self._raw_state())
        with self.assertRaisesRegex(PermissionError,reason):
            self.box.claim_next("lab-worker",now=NOW,lease_seconds=10)
        self.assertEqual(self._dump(),before)
        self.assertEqual(tuple(self._raw_state()),snapshot)
        self.assertEqual(self.box.effect_count(),0)
        self.assertEqual(self.box.get(self.key)["state"],"PENDING")

    def _claimed(self):
        first=self.box.claim_next("lab-worker",now=NOW,lease_seconds=10)
        self.assertIsNotNone(first)
        self.assertEqual(first["state"],"CLAIMED")
        self.assertEqual(first["local_integrity"],"MATCH")

    def _assert_denied_release(self, reason=RELEASE_DENY):
        before=self._dump()
        prior=tuple(self._raw_state())
        with self.assertRaisesRegex(PermissionError,reason):
            self.box.release_expired_claims(now=NOW+timedelta(seconds=20))
        self.assertEqual(self._dump(),before)
        self.assertEqual(tuple(self._raw_state()),prior)
        self.assertEqual(self.box.effect_count(),0)
        self.assertEqual(self.box.get(self.key)["state"],"CLAIMED")

    def test_01_healthy_first_claim_still_local_and_unprivileged(self):
        self._claimed()
        row=self.box.get(self.key)
        self.assertEqual(row["attempts"],1)
        self.assertEqual(row["lease_owner"],"lab-worker")
        self.assertEqual(row["lease_until"],(NOW+timedelta(seconds=10)).isoformat())
        self.assertFalse(row["executes_action"])
        self.assertEqual(self.box.effect_count(),0)

    def test_02_claim_rejects_forged_grants_authority_after_update(self):
        self._mutate("claim","data=replace(data,'\"grants_authority\":false','\"grants_authority\":true')",table="action_decisions")
        self._assert_denied_claim()

    def test_03_claim_rejects_malformed_decision_after_update(self):
        self._mutate("claim","data='{'",table="action_decisions")
        self._assert_denied_claim()

    def test_04_claim_rejects_changed_authorization_column(self):
        self._mutate("claim","authorization_ref='forged-approval'",table="action_decisions")
        self._assert_denied_claim()

    def test_05_claim_rejects_changed_deadline_column(self):
        self._mutate("claim","valid_until='2099-01-01T00:00:00+00:00'",table="action_decisions")
        self._assert_denied_claim()

    def test_06_claim_rejects_changed_decision_owner(self):
        self._mutate("claim","owner='forged-owner'",table="action_decisions")
        self._assert_denied_claim()

    def test_07_claim_rejects_forged_uncertain_state(self):
        self._mutate("claim","state='UNCERTAIN'")
        self._assert_denied_claim()

    def test_08_claim_rejects_forged_confirmed_state(self):
        self._mutate("claim","state='CONFIRMED',effect_ref='fake'")
        self._assert_denied_claim()

    def test_09_claim_rejects_inflated_attempts(self):
        self._mutate("claim","attempts=99")
        self._assert_denied_claim()

    def test_10_claim_rejects_changed_lease_owner(self):
        self._mutate("claim","lease_owner='foreign-worker'")
        self._assert_denied_claim()

    def test_11_claim_rejects_changed_lease_deadline(self):
        self._mutate("claim","lease_until='2099-01-01T00:00:00+00:00'")
        self._assert_denied_claim()

    def test_12_claim_rejects_injected_dispatch_marker(self):
        self._mutate("claim","dispatch_started_at='2026-10-21T17:30:02+00:00'")
        self._assert_denied_claim()

    def test_13_claim_rejects_injected_sent_marker(self):
        self._mutate("claim","sent_at='2026-10-21T17:30:02+00:00'")
        self._assert_denied_claim()

    def test_14_claim_rejects_injected_effect_ledger(self):
        self._effect("claim")
        self._assert_denied_claim()

    def test_15_clean_expired_claim_can_release_and_no_auto_send(self):
        self._claimed()
        self.assertEqual(self.box.release_expired_claims(now=NOW+timedelta(seconds=20)),1)
        obj=self.box.get(self.key)
        self.assertEqual(obj["state"],"RETRY")
        self.assertEqual(obj["attempts"],1)
        self.assertEqual(obj["lease_owner"],"")
        self.assertEqual(obj["lease_until"],"")
        self.assertEqual(obj["local_integrity"],"MATCH")
        self.assertFalse(obj["executes_action"])
        self.assertEqual(self.box.effect_count(),0)

    def test_16_release_rejects_forged_decision_json_post_update(self):
        self._claimed()
        self._mutate("release","data='{}'",table="action_decisions")
        self._assert_denied_release()

    def test_17_release_rejects_changed_decision_owner_post_update(self):
        self._claimed()
        self._mutate("release","owner='foreign-owner'",table="action_decisions")
        self._assert_denied_release()

    def test_18_release_rejects_forged_action_column_post_update(self):
        self._claimed()
        self._mutate("release","action='FORGED'",table="action_decisions")
        self._assert_denied_release()

    def test_19_release_rejects_regressed_claimed_state(self):
        self._claimed()
        self._mutate("release","state='CLAIMED'")
        self._assert_denied_release()

    def test_20_release_rejects_forged_uncertain_state(self):
        self._claimed()
        self._mutate("release","state='UNCERTAIN'")
        self._assert_denied_release()

    def test_21_release_rejects_increased_attempts(self):
        self._claimed()
        self._mutate("release","attempts=999")
        self._assert_denied_release()

    def test_22_release_rejects_lease_owner_after_clear(self):
        self._claimed()
        self._mutate("release","lease_owner='forged-lease-holder'")
        self._assert_denied_release()

    def test_23_release_rejects_lease_deadline_after_clear(self):
        self._claimed()
        self._mutate("release","lease_until='2099-01-01T00:00:00+00:00'")
        self._assert_denied_release()

    def test_24_release_rejects_effect_reference_after_clear(self):
        self._claimed()
        self._mutate("release","effect_ref='forged-effect'")
        self._assert_denied_release()

    def test_25_release_rejects_dispatch_marker_after_clear(self):
        self._claimed()
        self._mutate("release","dispatch_started_at='2026-10-21T17:30:02+00:00'")
        self._assert_denied_release()

    def test_26_release_rejects_effect_ledger_after_clear(self):
        self._claimed()
        self._effect("release")
        self._assert_denied_release()

    def test_27_batch_release_is_atomic_if_one_candidate_is_corrupted(self):
        self._claimed()
        other_key=self._enqueue("two")
        other=self.box.claim_next("lab-worker",now=NOW,lease_seconds=10)
        self.assertEqual(other["idempotency_key"],other_key)
        self._trigger(
            "release",
            "UPDATE action_outbox SET attempts=777 "
            "WHERE idempotency_key=NEW.idempotency_key "
            "AND NEW.idempotency_key='"+self.key+"'",
        )
        before=self._dump()
        with self.assertRaisesRegex(PermissionError,RELEASE_DENY):
            self.box.release_expired_claims(now=NOW+timedelta(seconds=20))
        self.assertEqual(self._dump(),before)
        self.assertEqual(self.box.get(other_key)["state"],"CLAIMED")
        self.assertEqual(self.box.get(self.key)["state"],"CLAIMED")
        self.assertEqual(self.box.effect_count(),0)

    def test_28_pre_dispatch_boundary_after_dispatch_never_released(self):
        self._claimed()
        with self.db:
            self.db.execute(
                "UPDATE action_outbox SET dispatch_started_at=? WHERE idempotency_key=?",
                (NOW.isoformat(),self.key),
            )
        before=self._dump()
        self.assertEqual(self.box.release_expired_claims(now=NOW+timedelta(seconds=20)),0)
        self.assertEqual(self._dump(),before)
        self.assertEqual(self.box.get(self.key)["state"],"CLAIMED")
        self.assertEqual(self.box.effect_count(),0)

    def test_29_no_release_before_expiry(self):
        self._claimed()
        before=self._dump()
        self.assertEqual(self.box.release_expired_claims(now=NOW+timedelta(seconds=5)),0)
        self.assertEqual(self._dump(),before)

    def test_30_second_claim_after_clean_release_is_only_local_claim(self):
        self._claimed()
        self.assertEqual(self.box.release_expired_claims(now=NOW+timedelta(seconds=20)),1)
        claimed=self.box.claim_next("another-local-worker",now=NOW+timedelta(seconds=21),lease_seconds=10)
        self.assertEqual(claimed["state"],"CLAIMED")
        self.assertEqual(claimed["attempts"],2)
        self.assertEqual(claimed["lease_owner"],"another-local-worker")
        self.assertEqual(self.box.effect_count(),0)
        self.assertFalse(claimed["executes_action"])

    def test_31_existing_parent_transaction_rejected_before_claim_release(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            with self.assertRaisesRegex(RuntimeError,"OUTBOX_NESTED_TRANSACTION_UNSUPPORTED"):
                self.box.claim_next("worker",now=NOW)
            with self.assertRaisesRegex(RuntimeError,"OUTBOX_NESTED_TRANSACTION_UNSUPPORTED"):
                self.box.release_expired_claims(now=NOW)
            self.assertTrue(self.db.in_transaction)
        finally:
            self.db.rollback()


if __name__=="__main__":
    unittest.main()
