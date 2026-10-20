"""P0 H0 three-domain rollback LAB — local fixtures, NOT trusted anchors.

Domains are ordinary local SQLite files:
 A: executor cursor; B: synthetic CAS custodian; C: synthetic version history.
The scenario isolates which rollback is visible while another file persists.
No file is a remote service, immutable S3 compliance record, enrolled signer,
or proof of provider effect. ALL outcomes are BLOCKED, including exact match.
No network, SDK, Cloudflare, AWS, Twilio, OneSignal, Worker or actual sends.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import hashlib
import shutil
import sqlite3
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from atlasquant_aion_p0_h0_custody_two_domain_model_lab import (
    initialize_model_fixture, reserve_first_attempt_model,
    compare_boot_highwater_model,
)
import test_atlasquant_aion_execution_outbox as outbox_fixture

SCOPE="d"*64
OTHER_SCOPE="e"*64
DIGEST_A=hashlib.sha256(b"fake-h0-first-intent").hexdigest()
DIGEST_B=hashlib.sha256(b"fake-h0-different-intent").hexdigest()
NONCE="fake_nonce_for_one_intent_123456789"
FALSE_FIELDS=(
    "first_effect_allowed", "automatic_retry_allowed", "worker_arming_allowed",
    "independent_issuer_enrolled", "external_highwater_authenticated",
    "third_anchor_immutable_verified", "receipt_verified", "rollback_ruled_out",
)
NOW=outbox_fixture.NOW


def _read(path: Path, query: str, args=()):
    """Explicit read-only SQLite fixture: must not create a missing 'anchor'."""
    if path.is_symlink() or not path.is_file():
        raise OSError("missing/untrusted fixture")
    with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        return db.execute(query,args).fetchall()


def compare_three_fixture_heads(*, local: Path, custody: Path,
                                anchor: Path, pinned_version: str | None,
                                scope: str=SCOPE, claimed_verified=None):
    # claimed_verified is intentionally not inspected (could be hostile).
    out={
        "state":"BLOCKED", "simulation_only":True, "reason":"UNSET",
        **dict.fromkeys(FALSE_FIELDS,False),
        "local_sequence":None, "custody_sequence":None,
        "anchor_sequence":None,
    }
    if type(scope) is not str or len(scope)!=64 or any(c not in "0123456789abcdef" for c in scope):
        out["reason"]="MODEL_SCOPE_INVALID"
        return out
    if type(pinned_version) is not str or not pinned_version:
        out["reason"]="NO_OUT_OF_BAND_VERSION_PIN"
        return out
    try:
        l=_read(local,"SELECT epoch,seq,digest FROM executor_cursor WHERE scope=?",(scope,))
        c=_read(custody,"SELECT epoch,sequence,digest FROM witness_head WHERE scope=?",(scope,))
        a=_read(anchor,"SELECT epoch,seq,digest,ord FROM fake_anchor_versions WHERE scope=? AND version=?",
                (scope,pinned_version))
        latest=_read(anchor,"SELECT version FROM fake_anchor_versions WHERE scope=? ORDER BY ord DESC LIMIT 1",(scope,))
    except (sqlite3.Error,OSError,ValueError,TypeError):
        out["reason"]="FIXTURE_MISSING_OR_UNREADABLE"
        return out
    if len(l)!=1 or len(c)!=1 or len(a)!=1 or len(latest)!=1:
        out["reason"]="MISSING_PINNED_SCOPE_OR_HEAD"
        return out
    if latest[0][0]!=pinned_version:
        out["reason"]="PINNED_VERSION_STALE_ALIAS_OR_NEW_VERSION"
        return out
    le,ls,ld=l[0]
    ce,cs,cd=c[0]
    ae,ass,ad,_=a[0]
    if any(type(v) is not int or v<0 for v in (ls,cs,ass)) or any(type(v) is not int or v<1 for v in (le,ce,ae)):
        out["reason"]="MALFORMED_HEAD"
        return out
    out.update(local_sequence=ls,custody_sequence=cs,anchor_sequence=ass)
    if len({le,ce,ae})!=1:
        out["reason"]="EPOCH_CONFLICT"
    elif ass>ls and ass>cs:
        out["reason"]="EXECUTOR_AND_CUSTODIAN_ROLLBACK_SUSPECTED"
    elif cs>ls and cs==ass:
        out["reason"]="EXECUTOR_ROLLBACK_SUSPECTED"
    elif ls>cs and ls==ass:
        out["reason"]="CUSTODIAN_ROLLBACK_SUSPECTED"
    elif ls==cs==ass and not(ld==cd==ad):
        out["reason"]="SAME_SEQUENCE_DIGEST_FORK"
    elif ls==cs==ass:
        out["reason"]="THREE_LOCAL_FIXTURE_HEADS_MATCH_NOT_AUTHENTICATED"
    else:
        out["reason"]="INCONSISTENT_HEADS_OR_FORK"
    return out


class H0ThreeDomainRollbackLAB(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        self.local=root/"executor.sqlite3"
        self.custody=root/"custody.sqlite3"
        self.anchor=root/"fake_third_anchor.sqlite3"
        initialize_model_fixture(self.custody,SCOPE)
        with closing(sqlite3.connect(self.local)) as db:
            db.execute("CREATE TABLE executor_cursor (scope TEXT PRIMARY KEY,epoch INTEGER,seq INTEGER,digest TEXT)")
            db.execute("INSERT INTO executor_cursor VALUES (?,?,?,?)",
                       (SCOPE,1,0,"0"*64))
            db.commit()
        with closing(sqlite3.connect(self.anchor)) as db:
            db.execute("CREATE TABLE fake_anchor_versions (scope TEXT,version TEXT,epoch INTEGER,seq INTEGER,digest TEXT,ord INTEGER,PRIMARY KEY(scope,version))")
            db.execute("INSERT INTO fake_anchor_versions VALUES (?,?,?,?,?,?)",
                       (SCOPE,"v0",1,0,"0"*64,0))
            db.commit()
        self.backups=root/"backup"
        self.backups.mkdir()
        for n,p in (("local",self.local),("custody",self.custody),("anchor",self.anchor)):
            shutil.copy2(p,self.backups/(n+".sqlite3"))
        self.commit_first()

    def commit_first(self):
        result=reserve_first_attempt_model(
            self.custody,scope=SCOPE,intent="intent-one-00001",
            nonce=NONCE,intent_digest=DIGEST_A,expected_sequence=0,epoch=1)
        self.assertEqual(result["reason"],"MODEL_RESERVED_NOT_AUTHORITY")
        self.assertIs(result["first_effect_allowed"],False)
        with closing(sqlite3.connect(self.local)) as db:
            db.execute("UPDATE executor_cursor SET seq=1,digest=? WHERE scope=?",
                       (DIGEST_A,SCOPE))
            db.commit()
        with closing(sqlite3.connect(self.anchor)) as db:
            db.execute("INSERT INTO fake_anchor_versions VALUES (?,?,?,?,?,?)",
                       (SCOPE,"v1",1,1,DIGEST_A,1))
            db.commit()

    def restore(self,*names):
        items={"local":self.local,"custody":self.custody,"anchor":self.anchor}
        for n in names:
            # Synthetic point-in-time restore from the fixture before commit.
            shutil.copy2(self.backups/(n+".sqlite3"),items[n])

    def inspect(self,*,pinned="v1",scope=SCOPE,claim=None):
        report=compare_three_fixture_heads(
            local=self.local,custody=self.custody,anchor=self.anchor,
            pinned_version=pinned,scope=scope,claimed_verified=claim)
        self.assertEqual(report["state"],"BLOCKED")
        self.assertIs(report["simulation_only"],True)
        for f in FALSE_FIELDS:
            self.assertIs(report[f],False, f)
        return report

    def test_01_clean_three_head_match_remains_no_authority(self):
        self.assertEqual(self.inspect()["reason"],
                         "THREE_LOCAL_FIXTURE_HEADS_MATCH_NOT_AUTHENTICATED")

    def test_02_executor_rollback_detected_with_two_persistent_models(self):
        self.restore("local")
        self.assertEqual(self.inspect()["reason"],
                         "EXECUTOR_ROLLBACK_SUSPECTED")

    def test_03_custodian_point_in_time_restore_detected(self):
        self.restore("custody")
        self.assertEqual(self.inspect()["reason"],
                         "CUSTODIAN_ROLLBACK_SUSPECTED")

    def test_04_both_executor_and_custodian_restore_while_anchor_survives(self):
        self.restore("local","custody")
        r=self.inspect()
        self.assertEqual(r["reason"],
                         "EXECUTOR_AND_CUSTODIAN_ROLLBACK_SUSPECTED")
        self.assertEqual((r["local_sequence"],r["custody_sequence"],
                          r["anchor_sequence"]), (0,0,1))

    def test_05_three_domain_restore_hides_history_without_external_freshness(self):
        self.restore("local","custody","anchor")
        # A fake pin "v0" also rolled back. There is no fourth root.
        self.assertEqual(self.inspect(pinned="v0")["reason"],
                         "THREE_LOCAL_FIXTURE_HEADS_MATCH_NOT_AUTHENTICATED")
        # The original pinned v1, if protected off-host, detects the loss.
        self.assertEqual(self.inspect()["reason"],
                         "MISSING_PINNED_SCOPE_OR_HEAD")

    def test_06_same_sequence_divergent_local_digest_is_fork(self):
        with closing(sqlite3.connect(self.local)) as db:
            db.execute("UPDATE executor_cursor SET digest=?",(DIGEST_B,))
            db.commit()
        self.assertEqual(self.inspect()["reason"],"SAME_SEQUENCE_DIGEST_FORK")

    def test_07_same_sequence_divergent_custody_digest_is_fork(self):
        with closing(sqlite3.connect(self.custody)) as db:
            db.execute("UPDATE witness_head SET digest=?",(DIGEST_B,))
            db.commit()
        self.assertEqual(self.inspect()["reason"],"SAME_SEQUENCE_DIGEST_FORK")

    def test_08_epoch_mismatch_even_with_equal_sequences_is_blocked(self):
        with closing(sqlite3.connect(self.custody)) as db:
            db.execute("UPDATE witness_head SET epoch=2")
            db.commit()
        self.assertEqual(self.inspect()["reason"],"EPOCH_CONFLICT")

    def test_09_newer_anchor_version_makes_old_version_pin_stale(self):
        with closing(sqlite3.connect(self.anchor)) as db:
            db.execute("INSERT INTO fake_anchor_versions VALUES (?,?,?,?,?,?)",
                       (SCOPE,"v2",1,1,DIGEST_B,2))
            db.commit()
        self.assertEqual(self.inspect(pinned="v1")["reason"],
                         "PINNED_VERSION_STALE_ALIAS_OR_NEW_VERSION")
        self.assertEqual(self.inspect(pinned="v2")["reason"],
                         "SAME_SEQUENCE_DIGEST_FORK")

    def test_10_no_pinned_version_is_not_a_trustworthy_latest_alias(self):
        self.assertEqual(self.inspect(pinned=None)["reason"],
                         "NO_OUT_OF_BAND_VERSION_PIN")

    def test_11_missing_anchor_does_not_initialize_fake_fresh_ledger(self):
        self.anchor.unlink()
        self.assertEqual(self.inspect()["reason"],"FIXTURE_MISSING_OR_UNREADABLE")
        self.assertFalse(self.anchor.exists())

    def test_12_third_anchor_corrupt_schema_denied(self):
        with closing(sqlite3.connect(self.anchor)) as db:
            db.execute("DROP TABLE fake_anchor_versions")
            db.commit()
        self.assertEqual(self.inspect()["reason"],"FIXTURE_MISSING_OR_UNREADABLE")

    def test_13_foreign_scope_never_borrows_another_tenants_history(self):
        self.assertEqual(self.inspect(scope=OTHER_SCOPE)["reason"],
                         "MISSING_PINNED_SCOPE_OR_HEAD")

    def test_14_caller_verified_true_claim_never_becomes_an_anchor(self):
        class Hostile:
            def __bool__(self):
                raise AssertionError("caller self-report must not be touched")
            def __getattribute__(self,_):
                raise AssertionError("caller self-report must not be inspected")
        self.assertEqual(self.inspect(claim=Hostile())["reason"],
                         "THREE_LOCAL_FIXTURE_HEADS_MATCH_NOT_AUTHENTICATED")

    def test_15_underlying_two_domain_model_still_denies_first_effect(self):
        r=compare_boot_highwater_model(
            self.custody,scope=SCOPE,local_sequence=1,local_digest=DIGEST_A)
        self.assertEqual(r["state"],"BLOCKED")
        self.assertIs(r["first_effect_allowed"],False)
        self.assertEqual(r["reason"],"MODEL_HEAD_MATCH_ONLY_NO_EXTERNAL_PROOF")

    def test_16_even_all_three_local_database_files_are_not_independent(self):
        out=self.inspect()
        self.assertIs(out["independent_issuer_enrolled"],False)
        self.assertIs(out["third_anchor_immutable_verified"],False)
        self.assertIs(out["external_highwater_authenticated"],False)
        self.assertIs(out["automatic_retry_allowed"],False)


class ActualOutboxLostHistoryAndThreeFixtureBoundaryLAB(unittest.TestCase):
    def test_17_real_outbox_can_recreate_pending_after_sqlite_loss(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            scope=Scope("lab-owner","lab-tenant","lab-workspace")
            first_store=SQLiteChatStore(root/"before.sqlite3")
            try:
                first=ExecutionOutbox(first_store,scope).enqueue(
                    intent_ref="synthetic-intent-001",
                    action="send_sms",
                    payload={"to":"TEST_RECIPIENT","body":"TEST_ONLY"},
                    aggregate_key="customer-1",
                    policy_version="fake-policy", authorization_ref="NOT_APPROVED",
                    created_at=NOW,valid_until=NOW+__import__("datetime").timedelta(minutes=5))
                with first_store.db:
                    first_store.db.execute(
                        "UPDATE action_outbox SET state='UNCERTAIN' WHERE idempotency_key=?",
                        (first["idempotency_key"],))
            finally:
                first_store.close()
            second_store=SQLiteChatStore(root/"after_loss.sqlite3")
            try:
                fresh=ExecutionOutbox(second_store,scope)
                replay=fresh.enqueue(
                    intent_ref="synthetic-intent-001",action="send_sms",
                    payload={"to":"TEST_RECIPIENT","body":"TEST_ONLY"},
                    aggregate_key="customer-1",
                    policy_version="fake-policy", authorization_ref="NOT_APPROVED",
                    created_at=NOW,valid_until=NOW+__import__("datetime").timedelta(minutes=5))
                self.assertEqual(replay["idempotency_key"],first["idempotency_key"])
                self.assertEqual(replay["state"],"PENDING")
                self.assertEqual(replay["enqueue_state"],"ENQUEUED")
                self.assertEqual(fresh.effect_count(),0)
                # NO external dispatch: PENDING after loss is not a safe proof.
            finally:
                second_store.close()


if __name__=="__main__":
    unittest.main()
