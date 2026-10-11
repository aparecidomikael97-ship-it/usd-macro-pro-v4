"""Real SQLite, real restart/process contention; injected ACK/close failures."""
from copy import deepcopy
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest
from unittest.mock import patch
from atlasquant_aion_first_install_preparation_v5.admission import ReferenceReceiptAdmission
from atlasquant_aion_first_install_preparation_v5.contracts import digest
from tests.aion_receipt_admission_fixtures_v5 import AdmissionFixture, CHILD

class Fault:
    def __init__(self,db,*,target='fixture-admit',close_error=False,before=False):
        self.db=db;self.target=target;self.close_error=close_error;self.before=before;self.hit=False
    def __getattr__(self,name):return getattr(self.db,name)
    def commit(self):
        hit=self.db.execute('SELECT 1 FROM journal WHERE operation_id=?',(self.target,)).fetchone()
        if hit and self.before:raise sqlite3.OperationalError('FIXTURE_BEFORE_COMMIT')
        self.db.commit();self.hit=bool(hit)
        if hit and not self.close_error:raise sqlite3.OperationalError('FIXTURE_ACK_LOST')
    def close(self):
        self.db.close()
        if self.close_error and self.hit:raise sqlite3.OperationalError('FIXTURE_CLOSE_LOST')

class RecoveryTests(unittest.TestCase):
    def setUp(self):self.f=AdmissionFixture();self.addCleanup(self.f.close)
    def request(self):return dict(bindings=self.f.bindings,receipts=self.f.receipts,causal=self.f.anchor.causal)
    def fault(self,**kw):
        original=self.f.store.connect
        def connect(**options):
            db=original(**options);return db if options.get('read_only') else Fault(db,**kw)
        return patch.object(self.f.store,'connect',side_effect=connect)
    def data(self):
        x=dict(path=str(self.f.path),config=self.f.config,bindings=self.f.bindings,receipts=self.f.receipts,
            retained=self.f.retained,ledger_path=str(self.f.anchor.ledger.path),causal=self.f.anchor.causal)
        p=self.f.path.with_suffix('.public.json');p.write_text(json.dumps(x),encoding='utf-8');return p
    def assert_unknown(self,out):self.assertEqual(out['state'],'UNKNOWN_OUTCOME',out);self.assertFalse(out['automatic_retry_allowed'])

    def test_consumption_commit_ack_lost_readback_no_repeat(self):
        self.f.issue()
        with self.fault():out=self.f.admit()
        self.assert_unknown(out)
        read=self.f.store.reconcile('fixture-admit',digest(self.request()),self.f.retained)
        self.assertEqual(read['state'],'REFERENCE_DURABLE_ADMISSION_UNTRUSTED')
        self.assertEqual(len(read['snapshot']['receipts']),3);self.assertEqual(self.f.admit()['state'],'BLOCKED')

    def test_reservation_ack_lost_never_auto_resumes(self):
        self.f.issue()
        with self.fault(target='fixture-admit-reserve'):out=self.f.admit()
        self.assert_unknown(out);state=self.f.store.read(self.f.retained)['snapshot']
        self.assertEqual({v['state'] for v in state['nonces'].values()},{'RESERVED'});self.assertEqual(len(state['receipts']),0)
        self.assertEqual(self.f.admit()['state'],'BLOCKED')
        self.assertEqual(self.f.store.reconcile('fixture-admit',digest(self.request()),self.f.retained)['state'],'RECONCILIATION_REQUIRED')

    def test_before_consumption_commit_no_partial_effects_reserved(self):
        self.f.issue()
        with self.fault(before=True):out=self.f.admit()
        self.assert_unknown(out);state=self.f.store.read(self.f.retained)['snapshot']
        self.assertEqual(len(state['receipts']),0);self.assertEqual({v['state'] for v in state['nonces'].values()},{'RESERVED'})
        self.assertEqual([f['receipt_id'] for f in state['floors']],[None]*3)

    def test_close_after_commit_unknown_readback_confirmed_local(self):
        self.f.issue()
        with self.fault(close_error=True):out=self.f.admit()
        self.assert_unknown(out);self.assertEqual(len(self.f.store.read(self.f.retained)['snapshot']['receipts']),3)
        self.assertEqual(self.f.admit()['state'],'BLOCKED')

    def test_independent_read_close_failure_never_positive(self):
        self.f.issue();self.f.admit();original=self.f.store.connect
        class CloseFault:
            def __init__(self,c):self.c=c
            def __getattr__(self,k):return getattr(self.c,k)
            def close(self):self.c.close();raise sqlite3.OperationalError('FIXTURE_CLOSE')
        with patch.object(self.f.store,'connect',side_effect=lambda **kw:CloseFault(original(**kw))):
            self.assert_unknown(self.f.store.reconcile('fixture-admit',digest(self.request()),self.f.retained))

    def test_restart_preserves_consumption_and_no_retry(self):
        self.f.issue();self.f.admit();s=ReferenceReceiptAdmission(self.f.path,config=self.f.config,expected_config_digest=digest(self.f.config))
        out=s.admit(self.f.bindings,self.f.receipts,operation_id='fixture-new-process-request',retained=self.f.retained,
            now=1000,ledger_path=self.f.anchor.ledger.path,causal=self.f.anchor.causal)
        self.assertEqual(out['state'],'BLOCKED');self.assertEqual(len(s.read(self.f.retained)['snapshot']['receipts']),3)

    def test_actual_process_exit_after_native_commit(self):
        self.f.issue();p=self.data()
        out=subprocess.run([sys.executable,'-B','-c',CHILD,str(p),'crash'],capture_output=True,text=True,timeout=30)
        self.assertEqual(out.returncode,23,out.stderr)
        read=self.f.store.reconcile('fixture-admit',digest(self.request()),self.f.retained)
        self.assertEqual(read['state'],'REFERENCE_DURABLE_ADMISSION_UNTRUSTED');self.assertEqual(len(read['snapshot']['receipts']),3)
        self.assertEqual(self.f.admit()['state'],'BLOCKED')

    def test_four_processes_once_only(self):
        self.f.issue();p=self.data()
        workers=[subprocess.Popen([sys.executable,'-B','-c',CHILD,str(p),'normal'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(4)]
        results=[]
        try:
            for process in workers:
                stdout,stderr=process.communicate(timeout=30);self.assertEqual(process.returncode,0,stderr)
                results.append(json.loads(stdout)['state'])
        finally:
            for process in workers:
                if process.poll() is None:process.kill();process.communicate()
        self.assertEqual(results.count('REFERENCE_DURABLE_ADMISSION_UNTRUSTED'),1,results)
        self.assertEqual(len(self.f.store.read(self.f.retained)['snapshot']['receipts']),3)

    def test_real_writer_lock_no_hidden_success(self):
        self.f.issue()
        with closing(sqlite3.connect(self.f.path,isolation_level=None)) as db:
            db.execute('BEGIN IMMEDIATE');out=self.f.admit();db.rollback()
        self.assertEqual(out['state'],'RECONCILIATION_REQUIRED');self.assertEqual(len(self.f.store.read(self.f.retained)['snapshot']['receipts']),0)

    def test_missing_store_read_does_not_create(self):
        absent=self.f.path.with_name('missing.db');self.f.store.path=absent
        self.assert_unknown(self.f.store.read(self.f.retained));self.assertFalse(absent.exists())

    def test_corrupt_store_fails_closed(self):
        corrupt=self.f.path.with_name('corrupt.db');corrupt.write_bytes(b'not sqlite');self.f.store.path=corrupt
        self.assert_unknown(self.f.store.read(self.f.retained))

    def test_removed_constraints_same_columns_and_added_trigger_block(self):
        with closing(sqlite3.connect(self.f.path)) as db:
            db.execute('ALTER TABLE journal RENAME TO obsolete')
            db.execute('CREATE TABLE journal (sequence INTEGER,operation_id TEXT,request_digest TEXT,previous_digest TEXT,state_json TEXT,event_digest TEXT)')
            db.execute('DROP TABLE obsolete');db.commit()
        self.assertEqual(self.f.store.read(self.f.retained)['state'],'BLOCKED')

    def test_added_trigger_is_not_part_of_contract(self):
        with closing(sqlite3.connect(self.f.path)) as db:
            db.execute('CREATE TRIGGER unexpected AFTER INSERT ON journal BEGIN SELECT 1; END');db.commit()
        self.assertEqual(self.f.store.read(self.f.retained)['state'],'BLOCKED')

    def test_old_floor_new_receipt_rollback_detected_joint_restore_known_negative(self):
        self.f.issue();backup=self.f.path.with_suffix('.backup')
        with closing(sqlite3.connect(self.f.path)) as src,closing(sqlite3.connect(backup)) as dest:src.backup(dest)
        admitted=self.f.admit();newer=admitted['retained_reference']
        with closing(sqlite3.connect(backup)) as src,closing(sqlite3.connect(self.f.path)) as dest:src.backup(dest)
        self.assertEqual(self.f.store.read(newer)['state'],'BLOCKED')
        # Restoring every administrator-controlled reference erases the evidence.
        self.assertEqual(self.f.store.read(self.f.retained)['state'],'REFERENCE_LOCAL_SNAPSHOT_UNTRUSTED')
        second=self.f.admit();self.assertEqual(second['state'],'REFERENCE_DURABLE_ADMISSION_UNTRUSTED')
        self.assertFalse(second['independent_monotonicity_verified'])

    def test_reconciliation_is_read_only_and_interruption_unknown(self):
        self.f.issue();self.f.admit()
        before=self.f.store.read(self.f.retained)['retained_reference']
        self.f.store.reconcile('fixture-admit',digest(self.request()),self.f.retained)
        after=self.f.store.read(self.f.retained)['retained_reference'];self.assertEqual(before,after)
        with patch.object(self.f.store,'connect',side_effect=sqlite3.OperationalError('FIXTURE_INTERRUPTED')):
            self.assert_unknown(self.f.store.reconcile('fixture-admit',digest(self.request()),self.f.retained))

    def test_revocation_after_reservation_blocks_second_transaction(self):
        self.f.issue();original=self.f.store._commit_read;injected=False
        def hook(op,request,retained,callback):
            nonlocal injected
            out=original(op,request,retained,callback)
            if op=='fixture-admit-reserve' and not injected:
                injected=True;e=self.f.control_event('CUSTODY_COMPROMISE')
                control=self.f.store.control(e,retained=self.f.retained)
                self.assertEqual(control['state'],'REFERENCE_DURABLE_ADMISSION_UNTRUSTED')
            return out
        with patch.object(self.f.store,'_commit_read',side_effect=hook):out=self.f.admit()
        self.assertEqual(out['state'],'BLOCKED');s=self.f.store.read(self.f.retained)['snapshot']
        self.assertEqual(len(s['receipts']),0);self.assertEqual({r['state'] for r in s['nonces'].values()},{'RESERVED'})

    def test_epoch_control_ack_loss_and_concurrent_cas(self):
        e=self.f.control_event()
        with self.fault(target=e['event_id']):out=self.f.store.control(e,retained=self.f.retained)
        self.assert_unknown(out)
        self.assertEqual(self.f.store.reconcile(e['event_id'],digest(e),self.f.retained)['state'],'REFERENCE_DURABLE_ADMISSION_UNTRUSTED')
        self.assertEqual(self.f.store.control(e,retained=self.f.retained)['state'],'BLOCKED')

    def test_errors_do_not_contain_exception_text(self):
        with patch.object(self.f.store,'connect',side_effect=sqlite3.OperationalError('SECRET_FIXTURE_NEVER_EXPOSE')):
            out=self.f.store.read(self.f.retained)
        self.assertNotIn('SECRET_FIXTURE_NEVER_EXPOSE',json.dumps(out))

    def test_two_actual_processes_competing_epoch_cas(self):
        first=self.f.control_event(event_id='fixture-epoch-first');second=self.f.control_event(event_id='fixture-epoch-second')
        base=json.loads(self.data().read_text());paths=[]
        for i,event in enumerate((first,second)):
            p=self.f.path.with_name('control-'+str(i)+'.json');p.write_text(json.dumps({**base,'event':event}),encoding='utf-8');paths.append(p)
        workers=[subprocess.Popen([sys.executable,'-B','-c',CHILD,str(p),'control'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for p in paths]
        results=[]
        try:
            for process in workers:
                out,err=process.communicate(timeout=30);self.assertEqual(process.returncode,0,err);results.append(json.loads(out)['state'])
        finally:
            for process in workers:
                if process.poll() is None:process.kill();process.communicate()
        self.assertEqual(results.count('REFERENCE_DURABLE_ADMISSION_UNTRUSTED'),1,results)
        self.assertEqual(len(self.f.store.read(self.f.retained)['snapshot']['candidates']),1)

    def test_two_actual_processes_rotation_vs_revocation(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        events=[self.f.control_event('ROOT_ROTATION','fixture-rotate',Ed25519PrivateKey.generate()),
                self.f.control_event('CUSTODY_COMPROMISE','fixture-revoke')]
        base=json.loads(self.data().read_text());paths=[]
        for i,event in enumerate(events):
            p=self.f.path.with_name('root-control-'+str(i)+'.json');p.write_text(json.dumps({**base,'event':event}),encoding='utf-8');paths.append(p)
        workers=[subprocess.Popen([sys.executable,'-B','-c',CHILD,str(p),'control'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for p in paths]
        results=[]
        try:
            for process in workers:
                out,err=process.communicate(timeout=30);self.assertEqual(process.returncode,0,err);results.append(json.loads(out)['state'])
        finally:
            for process in workers:
                if process.poll() is None:process.kill();process.communicate()
        self.assertEqual(results.count('REFERENCE_DURABLE_ADMISSION_UNTRUSTED'),1,results)
        self.assertEqual(self.f.store.config['root']['generation'],1)

if __name__=='__main__':unittest.main()
