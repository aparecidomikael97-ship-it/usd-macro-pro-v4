"""A123 OFFLINE adversarial fixture. Passing counterexamples do NOT certify safety."""
from __future__ import annotations
import multiprocessing as mp
from copy import deepcopy
from contextlib import contextmanager
from dataclasses import replace
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from contract import AdmissionFixture, Denied, FakeSender, Intent, LocalToySigner, ToyVault, Uncertain, production_eligible


@contextmanager
def opened_sqlite(path):
    db=sqlite3.connect(path)
    try:
        with db:
            yield db
    finally:
        db.close()


def contender(args):
    ledger,vault_path,intent=args
    fake=FakeSender([])
    g=AdmissionFixture(ledger,ToyVault(vault_path,LocalToySigner()),sender=fake)
    try:
        g.issue_once(intent,nonce=f"ISSUE-PROC-NONCE-{os.getpid()}")
        return len(fake.sink)
    except (Denied,Uncertain):
        return 0


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger=str(Path(self.tmp.name)/"custodian_ledger.db")
        self.vaultpath=str(Path(self.tmp.name)/"worm_simulation.db")
        self.signer=LocalToySigner()
        self.vault=ToyVault(self.vaultpath,self.signer)
        self.sender=FakeSender([])
        self.g=AdmissionFixture(self.ledger,self.vault,sender=self.sender)
        self.intent=Intent("MESSAGE-0001","OWNER-1","TENANT-A","WORK-1","ACCOUNT-X","SMS", "DEST-HEX-AAA","BODY-HEX-AAA",1)

    def prepared(self):
        self.g.prepare(self.intent)

    def issued(self):
        self.prepared()
        return self.g.issue_once(self.intent)

    def test_01_allows_preparation_with_binding(self):
        proof=self.g.prepare(self.intent)
        self.assertEqual(proof["kind"],"ANCHOR")
        self.assertEqual(self.g.status(self.intent),"PREPARED")
        self.assertFalse(self.vault.verify_receipt(self.intent,proof,kind="ANCHOR")["provider_effect_proven"])

    def test_02_issuance_marks_unknown_before_fake_call(self):
        outcome=self.issued()
        self.assertEqual(outcome["status"],"UNKNOWN")
        self.assertEqual(len(self.sender.sink),1)
        self.assertEqual(self.g.status(self.intent),"UNKNOWN_CONSUMED")

    def test_03_second_issue_never_auto_resends(self):
        self.issued()
        with self.assertRaises(Denied):self.g.issue_once(self.intent)
        self.assertEqual(len(self.sender.sink),1)

    def test_04_preparation_cannot_reopen_consumed(self):
        self.issued()
        with self.assertRaises(Denied):self.g.prepare(self.intent)

    def test_05_reject_tenant_swap(self):
        self.prepared()
        with self.assertRaises(Denied):self.g.issue_once(replace(self.intent,tenant="TENANT-B"))

    def test_06_reject_destination_swap(self):
        self.prepared()
        with self.assertRaises(Denied):self.g.issue_once(replace(self.intent,destination_digest="DEST-B"))

    def test_07_reject_payload_swap(self):
        self.prepared()
        with self.assertRaises(Denied):self.g.issue_once(replace(self.intent,payload_digest="PAY-B"))

    def test_08_reject_epoch_replay(self):
        self.prepared()
        with self.assertRaises(Denied):self.g.issue_once(replace(self.intent,epoch=2))

    def test_09_reject_wrong_account_and_owner(self):
        self.prepared()
        for changed in [replace(self.intent,account="ACCOUNT-Y"),replace(self.intent,owner="OWNER-Y")]:
            with self.assertRaises(Denied):self.g.issue_once(changed)

    def test_10_no_unenrolled_operation(self):
        with self.assertRaises(Denied):self.g.issue_once(self.intent)

    def test_11_enrollment_mock_off(self):
        self.g.enrolled=False
        with self.assertRaises(Denied):self.g.prepare(self.intent)

    def test_12_vault_offline_before_prepare(self):
        self.vault.online=False
        with self.assertRaises(Denied):self.g.prepare(self.intent)
        self.assertEqual(len(self.sender.sink),0)

    def test_13_prepare_crash_before_anchor_can_resume(self):
        with self.assertRaises(Uncertain):self.g.prepare(self.intent,cut="after_local_prepare")
        self.assertEqual(self.g.status(self.intent),"PENDING_ANCHOR")
        self.g.prepare(self.intent)
        self.assertEqual(self.g.status(self.intent),"PREPARED")

    def test_14_prepare_crash_after_anchor_can_resume(self):
        with self.assertRaises(Uncertain):self.g.prepare(self.intent,cut="after_vault_anchor")
        self.g.prepare(self.intent)
        with opened_sqlite(self.vaultpath) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM events WHERE kind='ANCHOR'").fetchone()[0],1)

    def test_15_prepare_crash_after_commit_can_resume(self):
        with self.assertRaises(Uncertain):self.g.prepare(self.intent,cut="after_prepare_commit")
        self.g.prepare(self.intent)
        self.assertEqual(self.g.status(self.intent),"PREPARED")

    def test_16_issue_crash_after_local_marker_is_no_retry(self):
        self.prepared()
        with self.assertRaises(Uncertain):self.g.issue_once(self.intent,cut="after_local_issue")
        with self.assertRaises(Denied):self.g.issue_once(self.intent)
        self.assertEqual(len(self.sender.sink),0)

    def test_17_issue_crash_after_worm_mark_is_no_retry(self):
        self.prepared()
        with self.assertRaises(Uncertain):self.g.issue_once(self.intent,cut="after_vault_issue")
        with self.assertRaises(Denied):self.g.issue_once(self.intent)
        self.assertEqual(len(self.sender.sink),0)

    def test_18_issue_crash_before_sender_is_no_retry(self):
        self.prepared()
        with self.assertRaises(Uncertain):self.g.issue_once(self.intent,cut="before_sender")
        with self.assertRaises(Denied):self.g.issue_once(self.intent)
        self.assertEqual(len(self.sender.sink),0)

    def test_19_issue_crash_after_sender_is_no_retry(self):
        self.prepared()
        with self.assertRaises(Uncertain):self.g.issue_once(self.intent,cut="after_sender")
        with self.assertRaises(Denied):self.g.issue_once(self.intent)
        self.assertEqual(len(self.sender.sink),1)

    def test_20_response_timeout_is_unknown_and_no_retry(self):
        self.sender.behavior="timeout"
        self.prepared()
        with self.assertRaises(Uncertain):self.g.issue_once(self.intent)
        self.assertEqual(self.g.status(self.intent),"UNKNOWN_CONSUMED")
        with self.assertRaises(Denied):self.g.issue_once(self.intent)
        self.assertEqual(len(self.sender.sink),1)

    def test_21_five_xx_failure_no_retry(self):
        self.sender.behavior="5xx"
        self.prepared()
        with self.assertRaises(Uncertain):self.g.issue_once(self.intent)
        with self.assertRaises(Denied):self.g.issue_once(self.intent)

    def test_22_signer_down_on_issue_no_sender(self):
        self.prepared()
        self.signer.available=False
        with self.assertRaises(Denied):self.g.issue_once(self.intent)
        self.assertEqual(len(self.sender.sink),0)
        self.signer.available=True
        self.g.issue_once(self.intent)
        self.assertEqual(len(self.sender.sink),1)

    def test_23_signer_fails_after_db_mark_blocks_retry(self):
        self.prepared()
        # Simulate signature failure during ISSUE append, after local consumed marker.
        original=self.signer.sign
        def fail_for_issue(payload):
            if payload["kind"]=="ISSUE_ONCE":raise Uncertain("SIGNER_CRASH")
            return original(payload)
        self.signer.sign=fail_for_issue
        with self.assertRaises(Uncertain):self.g.issue_once(self.intent)
        self.signer.sign=original
        self.assertEqual(self.g.status(self.intent),"UNKNOWN_CONSUMED")
        with self.assertRaises(Denied):self.g.issue_once(self.intent)
        self.assertEqual(len(self.sender.sink),0)

    def test_24_vault_offline_after_db_mark_no_effect(self):
        self.prepared()
        original=self.vault.record
        def outage(intent,kind,nonce,**kw):
            if kind=="ISSUE_ONCE":raise Denied("OFFLINE_AFTER_LEDGER_COMMIT")
            return original(intent,kind,nonce,**kw)
        self.vault.record=outage
        with self.assertRaises(Denied):self.g.issue_once(self.intent)
        self.assertEqual(self.g.status(self.intent),"UNKNOWN_CONSUMED")
        self.assertEqual(len(self.sender.sink),0)

    def test_25_fake_receipt_modified_rejected(self):
        proof=self.g.prepare(self.intent)
        fake=deepcopy(proof);fake["signature"]="00"*32
        with self.assertRaises(Denied):self.vault.verify_receipt(self.intent,fake,kind="ANCHOR")

    def test_26_receipt_cross_tenant_rejected(self):
        proof=self.g.prepare(self.intent)
        with self.assertRaises(Denied):self.vault.verify_receipt(replace(self.intent,tenant="B"),proof,kind="ANCHOR")

    def test_27_provider_commit_claim_never_derived(self):
        outcome=self.issued()
        result=self.vault.verify_receipt(self.intent,outcome["admission_receipt"],kind="ISSUE_ONCE")
        self.assertFalse(result["provider_effect_proven"])
        self.assertFalse(result["no_effect_fenced_post_handoff"])
        with self.assertRaises(Denied):self.vault.verify_receipt(self.intent,outcome["admission_receipt"],kind="COMMITTED_EFFECT")

    def test_28_audit_event_tamper_rejected(self):
        self.prepared()
        with opened_sqlite(self.vaultpath) as db:
            db.execute("UPDATE events SET kind='FAKE_EFFECT_PROVEN' WHERE seq=1")
        with self.assertRaises(Denied):self.vault.attest(self.intent,"ANCHOR")

    def test_29_deleted_audit_event_rejected(self):
        self.prepared()
        with opened_sqlite(self.vaultpath) as db:
            db.execute("DELETE FROM events WHERE seq=1")
        with self.assertRaises(Denied):self.vault.attest(self.intent,"ANCHOR")

    def test_30_replay_nonce_denied(self):
        self.prepared()
        with self.assertRaises(Denied):self.vault.record(self.intent,"ISSUE_ONCE","PREPARE-NONCE-00001")

    def test_31_pre_fence_then_issue_denied(self):
        self.prepared()
        fence=self.g.pre_fence(self.intent)
        self.assertFalse(fence["no_effect_fenced_post_handoff"])
        with self.assertRaises(Denied):self.g.issue_once(self.intent)
        self.assertEqual(len(self.sender.sink),0)

    def test_32_issue_then_pre_fence_denied(self):
        self.issued()
        with self.assertRaises(Denied):self.g.pre_fence(self.intent)

    def test_33_simulated_worm_rollback_with_surviving_local_marker_denies(self):
        self.prepared()
        backup=Path(self.tmp.name)/"vault-backup.db"
        shutil.copy2(self.vaultpath,backup)
        self.g.issue_once(self.intent)
        shutil.copy2(backup,self.vaultpath)
        with self.assertRaises(Denied):self.g.issue_once(self.intent)
        self.assertEqual(len(self.sender.sink),1)

    def test_34_simulated_local_rollback_with_surviving_vault_mark_denies(self):
        self.prepared()
        backup=Path(self.tmp.name)/"ledger-backup.db"
        shutil.copy2(self.ledger,backup)
        self.g.issue_once(self.intent)
        shutil.copy2(backup,self.ledger)
        with self.assertRaises(Denied):self.g.issue_once(self.intent)
        self.assertEqual(len(self.sender.sink),1)

    def test_35_known_counterexample_joint_rollback_allows_duplicate(self):
        """Expected PASS when proving NOT independent custody; remains P0 OPEN."""
        self.prepared()
        bakl=Path(self.tmp.name)/"ledger.pre.db";bakv=Path(self.tmp.name)/"vault.pre.db"
        shutil.copy2(self.ledger,bakl);shutil.copy2(self.vaultpath,bakv)
        self.g.issue_once(self.intent)
        self.assertEqual(len(self.sender.sink),1)
        shutil.copy2(bakl,self.ledger);shutil.copy2(bakv,self.vaultpath)
        self.g.issue_once(self.intent,nonce="ISSUE-NONCE-0000002")
        self.assertEqual(len(self.sender.sink),2)  # COUNTEREXAMPLE, NOT CERTIFICATION

    def test_36_key_rotated_without_verifier_fails_closed(self):
        self.prepared()
        self.signer.key_id="NEW-KEY-WITHOUT-TRUST"
        with self.assertRaises(Denied):self.g.issue_once(self.intent)
        self.assertEqual(len(self.sender.sink),0)

    def test_37_zero_prod_permission(self):
        self.assertIs(production_eligible(),False)

    @unittest.skipUnless("fork" in mp.get_all_start_methods(),"single-host fork-only synthetic test")
    def test_38_32_local_processes_only_one_issues(self):
        self.prepared()
        ctx=mp.get_context("fork")
        with ctx.Pool(32) as pool:
            issued=pool.map(contender,[(self.ledger,self.vaultpath,self.intent)]*32)
        self.assertEqual(sum(issued),1)
        with opened_sqlite(self.vaultpath) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM events WHERE kind='ISSUE_ONCE'").fetchone()[0],1)


if __name__=="__main__":unittest.main()
