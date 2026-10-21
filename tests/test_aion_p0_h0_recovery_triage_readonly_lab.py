"""H0 recovery triage against actual local ExecutionOutbox + SQLite fixtures.

44 tests: never dispatch, mutate Outbox, contact provider or authorize retry.
PASS on a rollback symptom is characterization, NOT rollback prevention.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from atlasquant_aion_p0_h0_recovery_triage_readonly_lab import (
    SCHEMA, MANIFEST_SCHEMA, FLAGS_FALSE, BLOCKERS,
    inspect_execution_outbox_recovery_readonly_lab as inspect,
)

SCOPE = Scope("h0-lab-owner", "h0-lab-tenant", "h0-lab-workspace")
OTHER_SCOPE = Scope("h0-other-owner", "h0-other-tenant", "h0-other-workspace")
T0 = datetime(2026, 10, 21, 11, 0, tzinfo=timezone.utc)


class H0ReadOnlyRealOutboxRecoveryLab(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="aion-h0-readonly-recovery-")
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.path = self.dir / "current.sqlite3"
        self.store = SQLiteChatStore(self.path)
        self.addCleanup(self._close_stores)
        self.stores = [self.store]
        self.outbox = ExecutionOutbox(self.store, SCOPE)
        self.keys = []

    def _close_stores(self):
        for store in self.stores:
            try:
                store.close()
            except Exception:
                pass

    def enqueue(self, *, intent="intent-lab-001", aggregate="aggregate-lab-001"):
        obj = self.outbox.enqueue(
            intent_ref=intent, action="H0_LAB_ONLY",
            payload={"simulation_only": True}, aggregate_key=aggregate,
            policy_version="lab-policy", authorization_ref="lab-approval",
            created_at=T0, valid_until=T0 + timedelta(minutes=5),
        )
        key = obj["idempotency_key"]
        self.keys.append(key)
        return key

    def manifest(self, key, *, state="PENDING", attempts=0, dispatch=""):
        return {
            "schema": MANIFEST_SCHEMA,
            "cases": [{
                "idempotency_key": key,
                "last_known_state": state,
                "last_known_attempts": attempts,
                "last_known_dispatch_started_at": dispatch,
            }],
        }

    def snapshot(self, path):
        backup = self.dir / path
        dest = sqlite3.connect(backup)
        try:
            self.store.db.backup(dest)
        finally:
            dest.close()
        return backup

    def restored(self, path):
        st = SQLiteChatStore(path)
        self.stores.append(st)
        return ExecutionOutbox(st, SCOPE)

    def set_state(self, key, state, *, started=""):
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state=?,dispatch_started_at=? "
                "WHERE idempotency_key=?",
                (state, started, key),
            )

    def check(self, manifest, *, outbox=None, expected=None,
              shape_valid=True, regression=None):
        outbox = self.outbox if outbox is None else outbox
        result = inspect(outbox, manifest)
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["state"], "HARD_NO_GO")
        self.assertFalse(result["allowed"])
        self.assertTrue(result["read_only"])
        self.assertTrue(result["simulation_only"])
        self.assertEqual(result["external_truth"], "UNVERIFIED")
        self.assertEqual(result["reconciliation_state"], "UNKNOWN_BLOCKED")
        self.assertEqual(result["blockers"], BLOCKERS)
        self.assertEqual(result["manifest_shape_valid_lab"], shape_valid)
        for k in FLAGS_FALSE:
            self.assertIs(result[k], False, k)
        if expected:
            self.assertEqual(result["observations"][0]["reason"], expected)
        if regression is not None:
            self.assertIs(result["observations"][0]["local_regression_suspected"], regression)
        return result

    def test_01_pending_local_row_is_not_authority(self):
        key = self.enqueue()
        self.check(self.manifest(key), expected="LOCAL_RECORD_NOT_EXTERNAL_AUTHORITY")

    def test_02_claimed_local_row_not_authority(self):
        key=self.enqueue()
        claimed=self.outbox.claim_next("lab-worker",now=T0,lease_seconds=60)
        self.assertEqual(claimed["idempotency_key"],key)
        self.check(self.manifest(key),expected="LOCAL_RECORD_NOT_EXTERNAL_AUTHORITY",regression=False)

    def test_03_unknown_local_row_requires_external_resolution(self):
        key=self.enqueue()
        # Actual first claim increments attempts in the real SQLite Outbox.
        claimed=self.outbox.claim_next("lab-worker",now=T0,lease_seconds=60)
        self.assertEqual(claimed["idempotency_key"],key)
        self.assertEqual(claimed["attempts"],1)
        self.set_state(key,"UNCERTAIN",started=T0.isoformat())
        self.check(self.manifest(key,state="UNCERTAIN",attempts=1,
                                 dispatch=T0.isoformat()),
                   expected="UNKNOWN_EXTERNAL_EFFECT_REQUIRES_PROVIDER_RECONCILIATION")

    def test_04_sent_local_row_requires_provider(self):
        key=self.enqueue()
        self.set_state(key,"SENT",started=T0.isoformat())
        self.check(self.manifest(key),expected="UNKNOWN_EXTERNAL_EFFECT_REQUIRES_PROVIDER_RECONCILIATION")

    def test_05_confirmed_local_row_is_not_provider_origin(self):
        key=self.enqueue()
        self.set_state(key,"CONFIRMED")
        self.check(self.manifest(key),expected="LOCAL_CONFIRMED_NOT_EXTERNAL_PRODUCER_AUTHENTICATION")

    def test_06_unenrolled_producer_remains_blocked(self):
        key=self.enqueue()
        self.set_state(key,"BLOCKED_PRODUCER")
        self.check(self.manifest(key),expected="UNENROLLED_PRODUCER_REMAINS_BLOCKED")

    def test_07_retry_state_still_no_permission(self):
        key=self.enqueue()
        self.set_state(key,"RETRY")
        self.check(self.manifest(key),expected="LOCAL_RECORD_NOT_EXTERNAL_AUTHORITY")

    def test_08_revoked_state_still_no_permission(self):
        key=self.enqueue()
        self.set_state(key,"REVOKED")
        self.check(self.manifest(key),expected="LOCAL_RECORD_NOT_EXTERNAL_AUTHORITY")

    def test_09_failed_state_still_no_permission(self):
        key=self.enqueue()
        self.set_state(key,"FAILED")
        self.check(self.manifest(key),expected="LOCAL_RECORD_NOT_EXTERNAL_AUTHORITY")

    def test_10_reapproval_blocked_still_no_permission(self):
        key=self.enqueue()
        self.set_state(key,"BLOCKED_REAPPROVAL")
        self.check(self.manifest(key),expected="LOCAL_RECORD_NOT_EXTERNAL_AUTHORITY")

    def test_11_rollback_of_unknown_to_pending_detected_with_separate_hint(self):
        key=self.enqueue()
        old=self.snapshot("pending-before-send.sqlite3")
        self.set_state(key,"UNCERTAIN",started=T0.isoformat())
        restored=self.restored(old)
        self.check(self.manifest(key,state="UNCERTAIN",attempts=1,
                                 dispatch=T0.isoformat()),outbox=restored,
                   expected="POSSIBLE_LOCAL_ROLLBACK_OR_STALE_RECLAIM",regression=True)

    def test_12_rollback_before_enqueue_is_missing_not_proof_of_no_effect(self):
        initial=self.snapshot("before-first-enqueue.sqlite3")
        key=self.enqueue()
        self.set_state(key,"UNCERTAIN",started=T0.isoformat())
        restored=self.restored(initial)
        self.check(self.manifest(key,state="UNCERTAIN",attempts=1,
                                 dispatch=T0.isoformat()),outbox=restored,
                   expected="MISSING_LOCAL_INTENT_NOT_EVIDENCE_OF_NO_EFFECT",regression=True)

    def test_13_rollback_both_hint_and_row_undetectable_but_still_denied(self):
        key=self.enqueue()
        old=self.snapshot("pending-self-rollback.sqlite3")
        self.set_state(key,"UNCERTAIN",started=T0.isoformat())
        restored=self.restored(old)
        report=self.check(self.manifest(key,state="PENDING",attempts=0),
                          outbox=restored,
                          expected="LOCAL_RECORD_NOT_EXTERNAL_AUTHORITY",
                          regression=False)
        self.assertFalse(report["independent_rollback_detection"])

    def test_14_dispatch_started_then_snapshot_pending_detected(self):
        key=self.enqueue()
        old=self.snapshot("before-dispatch.sqlite3")
        self.set_state(key,"UNCERTAIN",started=T0.isoformat())
        self.check(self.manifest(key,state="SENT",attempts=0,
                                 dispatch=T0.isoformat()),outbox=self.restored(old),
                   expected="POSSIBLE_LOCAL_ROLLBACK_OR_STALE_RECLAIM")

    def test_15_attemps_decrease_detected(self):
        key=self.enqueue()
        self.check(self.manifest(key,state="PENDING",attempts=2),
                   expected="POSSIBLE_LOCAL_ROLLBACK_OR_STALE_RECLAIM",regression=True)

    def test_16_attempts_not_decreased_is_no_proof(self):
        key=self.enqueue()
        self.check(self.manifest(key,state="PENDING",attempts=0),
                   expected="LOCAL_RECORD_NOT_EXTERNAL_AUTHORITY",regression=False)

    def test_17_previous_uncertain_current_claimed_suspect(self):
        key=self.enqueue()
        self.outbox.claim_next("lab-worker",now=T0,lease_seconds=60)
        self.check(self.manifest(key,state="UNCERTAIN",attempts=1),
                   expected="POSSIBLE_LOCAL_ROLLBACK_OR_STALE_RECLAIM",regression=True)

    def test_18_previous_sent_current_retry_suspect(self):
        key=self.enqueue()
        self.set_state(key,"RETRY")
        self.check(self.manifest(key,state="SENT",attempts=1),
                   expected="POSSIBLE_LOCAL_ROLLBACK_OR_STALE_RECLAIM",regression=True)

    def test_19_previous_confirmed_current_pending_suspect(self):
        key=self.enqueue()
        self.check(self.manifest(key,state="CONFIRMED",attempts=1),
                   expected="POSSIBLE_LOCAL_ROLLBACK_OR_STALE_RECLAIM",regression=True)

    def test_20_previous_blocked_producer_current_pending_suspect(self):
        key=self.enqueue()
        self.check(self.manifest(key,state="BLOCKED_PRODUCER",attempts=0),
                   expected="POSSIBLE_LOCAL_ROLLBACK_OR_STALE_RECLAIM",regression=True)

    def test_21_missing_arbitrary_handle_cannot_prove_no_effect(self):
        key="f"*64
        self.check(self.manifest(key),expected="MISSING_LOCAL_INTENT_NOT_EVIDENCE_OF_NO_EFFECT")

    def test_22_closed_sqlite_is_unavailable_and_denied(self):
        key=self.enqueue()
        self.store.close()
        self.check(self.manifest(key),expected="LOCAL_HISTORY_UNAVAILABLE_OR_CORRUPT")

    def test_23_corrupt_decision_json_unreadable_and_denied(self):
        key=self.enqueue()
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_decisions SET data=? WHERE decision_id=("
                "SELECT decision_id FROM action_outbox WHERE idempotency_key=?)",
                ("{bad-json",key),
            )
        self.check(self.manifest(key),expected="LOCAL_HISTORY_UNAVAILABLE_OR_CORRUPT")

    def test_24_exact_read_only_invariant_sqlite_dump(self):
        key=self.enqueue()
        before=tuple(self.store.db.iterdump())
        self.check(self.manifest(key))
        after=tuple(self.store.db.iterdump())
        self.assertEqual(before,after)
        self.assertEqual(self.outbox.effect_count(),0)

    def test_25_read_only_unknown_preserves_db(self):
        key=self.enqueue()
        self.set_state(key,"UNCERTAIN",started=T0.isoformat())
        before=tuple(self.store.db.iterdump())
        self.check(self.manifest(key),expected="UNKNOWN_EXTERNAL_EFFECT_REQUIRES_PROVIDER_RECONCILIATION")
        self.assertEqual(before,tuple(self.store.db.iterdump()))
        self.assertEqual(self.outbox.effect_count(),0)

    def test_26_read_only_missing_preserves_db(self):
        self.enqueue()
        before=tuple(self.store.db.iterdump())
        self.check(self.manifest("f"*64))
        self.assertEqual(before,tuple(self.store.db.iterdump()))

    def test_27_manifest_unknown_extra_claim_denied(self):
        key=self.enqueue()
        m=self.manifest(key);m["provider_confirmed"]=True
        self.check(m,shape_valid=False,expected="CALLER_HINTS_MALFORMED_OR_UNSAFE")

    def test_28_manifest_unknown_case_field_denied(self):
        key=self.enqueue()
        m=self.manifest(key);m["cases"][0]["retry_authorized"]=True
        self.check(m,shape_valid=False,expected="CALLER_HINTS_MALFORMED_OR_UNSAFE")

    def test_29_manifest_schema_wrong_denied(self):
        key=self.enqueue()
        m=self.manifest(key);m["schema"]="AUTHORIZED"
        self.check(m,shape_valid=False,expected="CALLER_HINTS_MALFORMED_OR_UNSAFE")

    def test_30_manifest_list_subclass_denied(self):
        key=self.enqueue()
        class Evil(list):
            def __iter__(self):raise AssertionError("unsafe")
        m=self.manifest(key);m["cases"]=Evil(m["cases"])
        self.check(m,shape_valid=False,expected="CALLER_HINTS_MALFORMED_OR_UNSAFE")

    def test_31_manifest_dict_subclass_denied(self):
        key=self.enqueue()
        class Evil(dict):
            def __getitem__(self,key):raise AssertionError("unsafe")
        self.check(Evil(self.manifest(key)),shape_valid=False,
                   expected="CALLER_HINTS_MALFORMED_OR_UNSAFE")

    def test_32_manifest_case_dict_subclass_denied(self):
        key=self.enqueue()
        class Evil(dict):
            def __getitem__(self,key):raise AssertionError("unsafe")
        m=self.manifest(key);m["cases"][0]=Evil(m["cases"][0])
        self.check(m,shape_valid=False,expected="CALLER_HINTS_MALFORMED_OR_UNSAFE")

    def test_33_manifest_evil_nonstring_key_denied(self):
        key=self.enqueue()
        class Evil:
            def __hash__(self):return hash("schema")
            def __eq__(self,other):raise AssertionError("unsafe")
        m={Evil():MANIFEST_SCHEMA,"cases":self.manifest(key)["cases"]}
        self.check(m,shape_valid=False,expected="CALLER_HINTS_MALFORMED_OR_UNSAFE")

    def test_34_duplicate_handles_denied(self):
        key=self.enqueue()
        m=self.manifest(key);m["cases"].append(deepcopy(m["cases"][0]))
        self.check(m,shape_valid=False,expected="CALLER_HINTS_MALFORMED_OR_UNSAFE")

    def test_35_unsorted_handles_denied(self):
        key=self.enqueue()
        m=self.manifest(key)
        m["cases"].append(self.manifest("0"*64)["cases"][0])
        self.check(m,shape_valid=False,expected="CALLER_HINTS_MALFORMED_OR_UNSAFE")

    def test_36_empty_cases_denied(self):
        key=self.enqueue()
        m=self.manifest(key);m["cases"]=[]
        self.check(m,shape_valid=False,expected="CALLER_HINTS_MALFORMED_OR_UNSAFE")

    def test_37_more_than_32_cases_denied(self):
        key=self.enqueue()
        m=self.manifest(key)
        m["cases"]=[self.manifest(f"{i:064x}")["cases"][0] for i in range(33)]
        self.check(m,shape_valid=False,expected="CALLER_HINTS_MALFORMED_OR_UNSAFE")

    def test_38_uppercase_hash_handle_denied(self):
        key=self.enqueue()
        m=self.manifest(key);m["cases"][0]["idempotency_key"]=key.upper()
        # If digest is numeric-only, force an uppercase hex letter.
        if m["cases"][0]["idempotency_key"]==key:
            m["cases"][0]["idempotency_key"]="A"*64
        self.check(m,shape_valid=False,expected="CALLER_HINTS_MALFORMED_OR_UNSAFE")

    def test_39_bool_attempt_count_denied(self):
        key=self.enqueue()
        m=self.manifest(key);m["cases"][0]["last_known_attempts"]=True
        self.check(m,shape_valid=False,expected="CALLER_HINTS_MALFORMED_OR_UNSAFE")

    def test_40_negative_attempt_count_denied(self):
        key=self.enqueue()
        m=self.manifest(key);m["cases"][0]["last_known_attempts"]=-1
        self.check(m,shape_valid=False,expected="CALLER_HINTS_MALFORMED_OR_UNSAFE")

    def test_41_huge_attempt_count_denied(self):
        key=self.enqueue()
        m=self.manifest(key);m["cases"][0]["last_known_attempts"]=2**1000
        self.check(m,shape_valid=False,expected="CALLER_HINTS_MALFORMED_OR_UNSAFE")

    def test_42_bad_state_denied(self):
        key=self.enqueue()
        m=self.manifest(key);m["cases"][0]["last_known_state"]="AUTHORIZED"
        self.check(m,shape_valid=False,expected="CALLER_HINTS_MALFORMED_OR_UNSAFE")

    def test_43_malicious_dispatch_timestamp_denied(self):
        key=self.enqueue()
        m=self.manifest(key);m["cases"][0]["last_known_dispatch_started_at"]="2026-10-21T12:00:00+03:00"
        self.check(m,shape_valid=False,expected="CALLER_HINTS_MALFORMED_OR_UNSAFE")

    def test_44_multi_intent_sorted_observation_is_read_only(self):
        a=self.enqueue(intent="intent-lab-001",aggregate="aggregate-lab-001")
        b=self.enqueue(intent="intent-lab-002",aggregate="aggregate-lab-002")
        cases=[self.manifest(k)["cases"][0] for k in sorted((a,b))]
        m={"schema":MANIFEST_SCHEMA,"cases":cases}
        before=tuple(self.store.db.iterdump())
        result=self.check(m)
        self.assertEqual(len(result["observations"]),2)
        self.assertEqual(before,tuple(self.store.db.iterdump()))
        self.assertEqual(self.outbox.effect_count(),0)


if __name__ == "__main__":
    unittest.main()
