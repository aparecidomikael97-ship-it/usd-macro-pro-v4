"""A124 OFFLINE behavioral tests. One explicit PASS proves triple-rollback vulnerability."""
from __future__ import annotations
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'a123_receipts_offline'))

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
from dataclasses import replace
import shutil
import sqlite3
import tempfile
import unittest

from contract import AdmissionFixture, Denied, FakeSender, Intent, LocalToySigner, ToyVault, Uncertain
from witness import SimulatedSurvivingWitness, GuardedAdmissionFixture, production_eligible

class WitnessBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.local=Path(self.temp.name)/'aion.db'
        self.vaultpath=Path(self.temp.name)/'toy_vault.db'
        self.witness=SimulatedSurvivingWitness()
        self.sender=FakeSender([])
        self.a123=AdmissionFixture(self.local,ToyVault(self.vaultpath,LocalToySigner()),sender=self.sender)
        self.guard=GuardedAdmissionFixture(self.a123,self.witness)
        self.intent=Intent('A124-LOGICAL-001','OWNER-A','TENANT-A','WORKSPACE-A','ACCOUNT-A','SMS','DEST-A','PAYLOAD-A',1)

    def prepare(self):
        self.guard.prepare(self.intent)

    def issued(self):
        self.prepare()
        return self.guard.issue_once(self.intent)

    def snapshot_local(self):
        localbak=Path(self.temp.name)/'backup_local.db'
        vaultbak=Path(self.temp.name)/'backup_vault.db'
        shutil.copy2(self.local,localbak)
        shutil.copy2(self.vaultpath,vaultbak)
        return localbak,vaultbak

    def restore_local(self, backup):
        shutil.copy2(backup[0],self.local)
        shutil.copy2(backup[1],self.vaultpath)

    def test_01_unchanged_witness_allows_synthetic_first_issue(self):
        outcome=self.issued()
        self.assertEqual(len(self.sender.sink),1)
        self.assertEqual(outcome['status'],'UNKNOWN')
        self.assertFalse(outcome['provider_effect_proven'])
        self.assertFalse(outcome['no_effect_fenced_post_handoff'])

    def test_02_second_attempt_denied_by_surviving_witness(self):
        self.issued()
        with self.assertRaisesRegex(Denied,'ALREADY_RESERVED'):self.guard.issue_once(self.intent)
        self.assertEqual(len(self.sender.sink),1)

    def test_03_joint_two_db_rollback_rejected_if_witness_survives(self):
        self.prepare()
        backups=self.snapshot_local()
        self.guard.issue_once(self.intent)
        self.restore_local(backups)
        with self.assertRaisesRegex(Denied,'ALREADY_RESERVED'):self.guard.issue_once(self.intent,nonce='A124-WITNESS-REISSUE-2')
        self.assertEqual(len(self.sender.sink),1)

    def test_04_joint_local_rollback_cannot_reprepare(self):
        self.prepare()
        backups=self.snapshot_local()
        self.guard.issue_once(self.intent)
        self.restore_local(backups)
        with self.assertRaisesRegex(Denied,'ALREADY_RESERVED'):self.guard.prepare(self.intent)

    def test_05_witness_offline_fail_closed_before_send(self):
        self.prepare()
        self.witness.online=False
        with self.assertRaisesRegex(Denied,'NOT_AVAILABLE'):self.guard.issue_once(self.intent)
        self.assertEqual(len(self.sender.sink),0)

    def test_06_offline_while_prepare_blocks(self):
        self.witness.online=False
        with self.assertRaises(Denied):self.guard.prepare(self.intent)
        with closing(sqlite3.connect(self.local)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM intents').fetchone()[0],0)

    def test_07_unenrolled_witness_blocks(self):
        self.witness.enrolled=False
        with self.assertRaises(Denied):self.guard.prepare(self.intent)
        self.assertEqual(len(self.sender.sink),0)

    def test_08_signer_not_ready_blocks(self):
        self.prepare()
        self.witness.signer_ready=False
        with self.assertRaises(Denied):self.guard.issue_once(self.intent)
        self.assertEqual(len(self.sender.sink),0)

    def test_09_scope_binding_owner_tenant_workspace_account(self):
        self.issued()
        for attr in ['owner','tenant','workspace','account','destination_digest','payload_digest','epoch']:
            mutated=replace(self.intent,**{attr:(2 if attr=='epoch' else 'SWAPPED')})
            with self.assertRaisesRegex(Denied,'LOGICAL_INTENT_SCOPE_CONFLICT'):
                self.guard.issue_once(mutated,nonce='A124-SWAP-NONCE-123')

    def test_10_independently_attested_nonce_unique(self):
        self.issued()
        second=replace(self.intent,intent_id='A124-LOGICAL-002')
        self.guard.prepare(second,nonce='A124-PREPARE-UNIQUE-02')
        with self.assertRaisesRegex(Denied,'NONCE_REUSED'):
            self.guard.issue_once(second)

    def test_11_forged_receipt_denied(self):
        outcome=self.issued()
        fake=deepcopy(outcome['witness_receipt']); fake['signature']='00'*32
        with self.assertRaises(Denied):self.witness.verify_receipt(self.intent,fake)

    def test_12_truncated_history_rejected_when_head_survives(self):
        self.issued()
        self.witness._history.clear()  # same-admin tampering exposed by other stores
        with self.assertRaises(Denied):self.witness.inspect(self.intent)

    def test_13_index_tampering_rejected(self):
        self.issued()
        self.witness._issued.clear()
        with self.assertRaises(Denied):self.witness.inspect(self.intent)

    def test_14_head_forged_rejected(self):
        self.issued()
        self.witness._head='FORGED-HEAD'
        with self.assertRaises(Denied):self.witness.inspect(self.intent)

    def test_15_issuer_forged_rejected(self):
        self.issued()
        self.witness.issuer='ATTACKER-ISSUER'
        with self.assertRaises(Denied):self.witness.inspect(self.intent)

    def test_16_witness_mark_crash_before_local_issue_never_resend(self):
        self.prepare()
        with self.assertRaises(Uncertain):self.guard.issue_once(self.intent,cut='after_witness_before_a123')
        self.assertEqual(len(self.sender.sink),0)
        self.assertEqual(self.a123.status(self.intent),'PREPARED')
        with self.assertRaises(Denied):self.guard.issue_once(self.intent,nonce='A124-WITNESS-SECOND-1')

    def test_17_local_ledger_cas_fails_after_witness_reserved_no_resend(self):
        self.prepare()
        self.a123.pre_fence(self.intent) # A123 local consumed; witness still unissued
        with self.assertRaises(Denied):self.guard.issue_once(self.intent)
        with self.assertRaises(Denied):self.guard.issue_once(self.intent,nonce='A124-WITNESS-SECOND-2')
        self.assertEqual(len(self.sender.sink),0)

    def test_18_fake_sender_timeout_retains_witness_reservation(self):
        self.sender.behavior='timeout'
        self.prepare()
        with self.assertRaises(Uncertain):self.guard.issue_once(self.intent)
        self.assertEqual(self.witness.inspect(self.intent)['status'],'ISSUE_ONCE_ALREADY_RESERVED')
        with self.assertRaises(Denied):self.guard.issue_once(self.intent,nonce='A124-WITNESS-SECOND-3')
        self.assertEqual(len(self.sender.sink),1)

    def test_19_pre_fence_before_issue_fails_closed(self):
        self.prepare()
        out=self.guard.pre_fence(self.intent)
        self.assertFalse(out['no_effect_fenced_post_handoff'])
        with self.assertRaises(Denied):self.guard.issue_once(self.intent)
        self.assertEqual(len(self.sender.sink),0)

    def test_20_no_pre_fence_after_witness_issue(self):
        self.issued()
        with self.assertRaises(Denied):self.guard.pre_fence(self.intent)

    def test_21_proof_does_not_assert_provider_delivery_or_no_effect(self):
        result=self.issued()
        proof=self.witness.verify_receipt(self.intent,result['witness_receipt'])
        self.assertFalse(proof['provider_effect_proven'])
        self.assertFalse(proof['no_effect_fenced_post_handoff'])

    def test_22_32_threads_one_witness_reservation_and_fake_call(self):
        self.prepare()
        def run(i):
            try:
                self.guard.issue_once(self.intent,nonce='A124-THREAD-%03d-NONCE'%(i))
                return 1
            except (Denied,Uncertain):
                return 0
        with ThreadPoolExecutor(max_workers=32) as exe:
            outcome=list(exe.map(run,range(32)))
        self.assertEqual(sum(outcome),1)
        self.assertEqual(len(self.sender.sink),1)
        self.assertEqual(self.witness.summary()['seq'],1)

    def test_23_alternative_guard_same_witness_denies_duplicate(self):
        self.issued()
        guard2=GuardedAdmissionFixture(self.a123,self.witness)
        with self.assertRaises(Denied):guard2.issue_once(self.intent,nonce='A124-WITNESS-SECOND-4')

    def test_24_no_production_mode(self):
        self.assertFalse(production_eligible())

    def test_25_known_counterexample_restore_all_three_allows_second_fake_send(self):
        """PASS = known critical vulnerability still OPEN; toy witness is same-admin!"""
        self.prepare()
        backup=self.snapshot_local()
        witness_backup=self.witness.snapshot()
        self.guard.issue_once(self.intent)
        self.assertEqual(len(self.sender.sink),1)
        self.restore_local(backup)
        self.witness.restore_as_same_admin_for_attack(witness_backup)
        self.guard.issue_once(self.intent,nonce='A124-WITNESS-ISSUE-SECOND-5')
        self.assertEqual(len(self.sender.sink),2)

    def test_26_replacing_toy_witness_without_trust_root_allows_second_fake_send(self):
        """PASS = another known vulnerability; caller controls witness selection."""
        self.prepare()
        backup=self.snapshot_local()
        self.guard.issue_once(self.intent)
        self.restore_local(backup)
        replacement=SimulatedSurvivingWitness()
        unsafe_guard=GuardedAdmissionFixture(self.a123,replacement)
        unsafe_guard.issue_once(self.intent,nonce='A124-REPLACEMENT-ISSUE')
        self.assertEqual(len(self.sender.sink),2)

    def test_27_empty_unobserved_witness_is_not_no_effect_proof(self):
        state=self.witness.inspect(self.intent)
        self.assertEqual(state['status'],'NO_LOCAL_WITNESS_ISSUE_OBSERVED')
        self.assertFalse(state['no_effect_proven'])

    def test_28_nonce_invalid_denied(self):
        self.prepare()
        with self.assertRaises(Denied):self.guard.issue_once(self.intent,nonce='bad')
        self.assertEqual(len(self.sender.sink),0)

    def test_29_witness_index_signature_cannot_be_recomputed_by_AION_in_real_design(self):
        """The simulated key is available: this is a documented limitation."""
        outcome=self.issued()
        receipt=outcome['witness_receipt']
        self.assertEqual(receipt['signature'],self.witness._sign(receipt['body']))
        self.assertFalse(production_eligible())


    def test_30_known_counterexample_bypass_guard_direct_a123_sender_allows_duplicate(self):
        """PASS = real integration must prevent all direct provider-credential paths."""
        self.prepare()
        backup=self.snapshot_local()
        self.guard.issue_once(self.intent)
        self.restore_local(backup)
        # This is an explicit mock bypass, NOT a permitted production action.
        self.a123.issue_once(self.intent,nonce='A123-UNGUARDED-BYPASS-02')
        self.assertEqual(len(self.sender.sink),2)

    def test_31_cross_intent_witness_receipt_rejected(self):
        result=self.issued()
        other=replace(self.intent,intent_id='A124-OTHER-LOGICAL-ID')
        with self.assertRaises(Denied):
            self.witness.verify_receipt(other,result['witness_receipt'])

if __name__=='__main__': unittest.main()
