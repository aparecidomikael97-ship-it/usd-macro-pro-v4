from contextlib import closing
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import unittest
from unittest.mock import patch
from atlasquant_aion_first_install_preparation.contracts import AUTHORITY_FIELDS
from atlasquant_aion_first_install_preparation_v3.webauthn_ledger_reference import ReferenceWebAuthnLedger,attempt_binding
from atlasquant_aion_first_install_preparation_v3.ledger_storage import read_receipt_reference,Refusal
from tests.aion_webauthn_ledger_fixtures_v3 import LedgerFixture,CHILD

class Fault:
    def __init__(self,db,*,when='after',write_fail=False,rollback_fail=False,close_fail=False):
        self.db=db;self.when=when;self.write_fail=write_fail;self.rollback_fail=rollback_fail;self.close_fail=close_fail
    def __getattr__(self,name):return getattr(self.db,name)
    def execute(self,sql,*args):
        if self.write_fail and sql.startswith('UPDATE credentials SET sign_count'):
            self.db.execute(sql,*args);raise sqlite3.OperationalError('SECRET_WRITE_FAULT')
        return self.db.execute(sql,*args)
    def commit(self):
        if self.when=='after':self.db.commit()
        if self.when in ('after','before'):raise sqlite3.OperationalError('SECRET_COMMIT_FAULT')
        return self.db.commit()
    def rollback(self):
        if self.rollback_fail:raise sqlite3.OperationalError('SECRET_ROLLBACK_FAULT')
        return self.db.rollback()
    def close(self):
        self.db.close()
        if self.close_fail:raise sqlite3.OperationalError('SECRET_CLOSE_FAULT')

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.f=LedgerFixture();self.addCleanup(self.f.close)
        self.request=self.f.request_for();self.f.issue(self.request);self.packet=self.f.packet(self.request)
        self.bound=attempt_binding(self.request,self.packet)[1]
    def confirm(self):return self.f.ledger.confirm_assertion_reference(self.request,self.packet,attempt_id='fixture-attempt',now=1000)
    def read(self,**kw):
        return read_receipt_reference(self.f.path,scope=self.f.scope,namespace='CONSUMPTION',operation_id='fixture-attempt',expected_request_digest=self.bound['request_digest'],minimum_sequence=0,**kw)
    def fault(self,**kw):
        original=self.f.ledger.connect;writes=0
        def connect(**options):
            nonlocal writes
            db=original(**options)
            if options.get('read_only'):return db
            writes+=1
            return Fault(db,**kw) if writes==2 else db
        return patch.object(self.f.ledger,'connect',side_effect=connect)
    def check_blocked_retry(self):
        count=len(self.f.rows('receipts'));self.assertEqual(self.confirm()['state'],'BLOCKED');self.assertEqual(len(self.f.rows('receipts')),count)

    def test_commit_ack_lost_actual_effect_independent_readback(self):
        with self.fault(when='after'):out=self.confirm()
        self.assertEqual(out['state'],'UNKNOWN_OUTCOME');self.assertNotIn('SECRET',str(out))
        self.assertEqual(self.f.rows('challenges')[0]['state'],'CONSUMED');self.assertEqual(self.f.rows('credentials')[0]['sign_count'],2)
        self.assertEqual(self.read()['state'],'REFERENCE_DURABLE_RECEIPT_UNTRUSTED');self.check_blocked_retry()
        for k in AUTHORITY_FIELDS:self.assertIs(out[k],False)

    def test_before_commit_pending_quarantine_and_no_counter_update(self):
        with self.fault(when='before'):out=self.confirm()
        self.assertEqual(out['state'],'UNKNOWN_OUTCOME');self.assertEqual(self.read()['state'],'RECONCILIATION_REQUIRED')
        self.assertEqual(self.f.rows('credentials')[0]['sign_count'],1)
        self.assertEqual(self.f.rows('challenges')[0]['state'],'ATTEMPT_PENDING');self.check_blocked_retry()

    def test_during_write_rollback_preserves_pending_admission(self):
        with self.fault(when='normal',write_fail=True):out=self.confirm()
        self.assertEqual(out['state'],'RECONCILIATION_REQUIRED');self.assertEqual(self.f.rows('credentials')[0]['sign_count'],1)
        self.assertEqual(self.f.rows('challenges')[0]['state'],'ATTEMPT_PENDING');self.check_blocked_retry()

    def test_rollback_failure_remains_unknown(self):
        with self.fault(when='normal',write_fail=True,rollback_fail=True):out=self.confirm()
        self.assertEqual(out['state'],'UNKNOWN_OUTCOME');self.assertNotIn('SECRET',str(out));self.check_blocked_retry()

    def test_close_after_commit_lost_confirmation(self):
        with self.fault(when='normal',close_fail=True):out=self.confirm()
        self.assertEqual(out['state'],'UNKNOWN_OUTCOME');self.assertEqual(self.read()['state'],'REFERENCE_DURABLE_RECEIPT_UNTRUSTED');self.check_blocked_retry()

    def test_admission_commit_ack_lost_no_consumption(self):
        original=self.f.ledger.connect
        def connect(**kw):
            db=original(**kw);return db if kw.get('read_only') else Fault(db,when='after')
        with patch.object(self.f.ledger,'connect',side_effect=connect):out=self.confirm()
        self.assertEqual(out['state'],'UNKNOWN_OUTCOME');self.assertEqual(self.f.rows('attempts')[0]['state'],'PENDING')
        self.assertEqual(self.read()['state'],'RECONCILIATION_REQUIRED');self.check_blocked_retry()

    def test_before_begin_and_missing_database_do_not_create_readback(self):
        with patch.object(self.f.ledger,'connect',side_effect=sqlite3.OperationalError('SECRET_OPEN')):
            self.assertEqual(self.confirm()['state'],'RECONCILIATION_REQUIRED')
        missing=Path(self.f.tmp.name)/'missing.db'
        out=read_receipt_reference(missing,scope=self.f.scope,namespace='CONSUMPTION',operation_id='fixture-attempt',expected_request_digest=self.bound['request_digest'],minimum_sequence=0)
        self.assertEqual(out['state'],'UNKNOWN_OUTCOME');self.assertFalse(missing.exists())

    def test_missing_active_store_never_silently_rebootstrapped_by_write(self):
        self.f.path.unlink();self.assertEqual(self.confirm()['state'],'RECONCILIATION_REQUIRED');self.assertFalse(self.f.path.exists())

    def test_real_sqlite_lock_no_automatic_retry(self):
        with closing(sqlite3.connect(self.f.path,isolation_level=None)) as blocker:
            blocker.execute('BEGIN IMMEDIATE')
            self.assertEqual(self.confirm()['state'],'RECONCILIATION_REQUIRED');blocker.rollback()
        self.assertEqual(self.f.rows('attempts'),[])

    def test_corrupt_database_and_scope_rejected(self):
        self.f.path.write_bytes(b'corrupted fixture SQLite')
        self.assertEqual(self.read()['state'],'UNKNOWN_OUTCOME')
        with self.assertRaises(Refusal):ReferenceWebAuthnLedger(self.f.path,scope=self.f.scope)

    def test_mutated_counter_generation_and_receipt_detected(self):
        self.confirm()
        for sql in ["UPDATE credentials SET sign_count=0","UPDATE credentials SET generation=2","UPDATE receipts SET request_digest='bad'","UPDATE attempts SET consumed_counter=99"]:
            with self.subTest(sql=sql):
                backup=Path(self.f.tmp.name)/'saved.db';shutil.copyfile(self.f.path,backup)
                with closing(sqlite3.connect(self.f.path,isolation_level=None)) as db:db.execute(sql)
                self.assertEqual(self.read()['state'],'BLOCKED');shutil.copyfile(backup,self.f.path)

    def test_restored_whole_db_requires_external_floor_known_negative(self):
        backup=Path(self.f.tmp.name)/'old-local.db';shutil.copyfile(self.f.path,backup)
        consumed=self.confirm();floor=consumed['local_head_sequence']
        shutil.copyfile(backup,self.f.path)
        out=read_receipt_reference(self.f.path,scope=self.f.scope,namespace='CONSUMPTION',operation_id='fixture-attempt',expected_request_digest=self.bound['request_digest'],minimum_sequence=floor)
        self.assertEqual(out['state'],'BLOCKED')
        self.assertEqual(self.read()['state'],'RECONCILIATION_REQUIRED')
        # Local self-consistency cannot prove a privileged whole-file restore.
        replay=self.confirm();self.assertEqual(replay['state'],'REFERENCE_DURABLE_RECEIPT_UNTRUSTED')
        self.assertFalse(replay['independent_rollback_protection_verified'])
        for k in AUTHORITY_FIELDS:self.assertIs(replay[k],False)

    def test_readback_is_readonly_file_and_events_unchanged(self):
        self.confirm();before=self.f.path.read_bytes();count=len(self.f.rows('events'))
        self.read();self.read();self.assertEqual(self.f.path.read_bytes(),before);self.assertEqual(len(self.f.rows('events')),count)

    def test_abrupt_exit_after_commit_other_process_readback(self):
        p=self.f.publish_input(self.request,self.packet)
        crashed=subprocess.run([sys.executable,'-B','-c',CHILD,str(p),'crash','fixture-attempt'],capture_output=True,text=True,timeout=30)
        self.assertEqual(crashed.returncode,23,crashed.stderr)
        recovered=subprocess.run([sys.executable,'-B','-c',CHILD,str(p),'read','fixture-attempt'],capture_output=True,text=True,timeout=30)
        self.assertEqual(recovered.returncode,0,recovered.stderr)
        import json
        self.assertEqual(json.loads(recovered.stdout)['state'],'REFERENCE_DURABLE_RECEIPT_UNTRUSTED');self.check_blocked_retry()

    def test_processes_same_challenge_single_consumption(self):
        import json
        p=self.f.publish_input(self.request,self.packet)
        children=[subprocess.Popen([sys.executable,'-B','-c',CHILD,str(p),'confirm','fixture-process-'+str(i)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for i in range(4)]
        states=[]
        for child in children:
            out,err=child.communicate(timeout=30);self.assertEqual(child.returncode,0,err);states.append(json.loads(out)['state'])
        self.assertEqual(states.count('REFERENCE_DURABLE_RECEIPT_UNTRUSTED'),1)
        self.assertEqual(len(self.f.rows('attempts')),1);self.assertEqual(self.f.rows('credentials')[0]['sign_count'],2)

    def test_processes_different_operations_same_counter_single_winner(self):
        import json
        second=self.f.request_for(2);self.f.issue(second,index=2)
        first_file=self.f.publish_input(self.request,self.packet)
        p1=Path(self.f.tmp.name)/'first-public.json';shutil.copyfile(first_file,p1)
        p2=self.f.publish_input(second,self.f.packet(second))
        children=[subprocess.Popen([sys.executable,'-B','-c',CHILD,str(path),'confirm',ident],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for path,ident in [(p1,'fixture-op-a'),(p2,'fixture-op-b')]]
        states=[]
        for child in children:
            out,err=child.communicate(timeout=30);self.assertEqual(child.returncode,0,err);states.append(json.loads(out)['state'])
        self.assertEqual(states.count('REFERENCE_DURABLE_RECEIPT_UNTRUSTED'),1)
        self.assertEqual(sum(r['state']=='CONSUMED' for r in self.f.rows('challenges')),1)

    def test_revocation_rotation_process_crash_after_commit(self):
        from cryptography.hazmat.primitives.asymmetric import ec
        import json
        code='''
import json,sys,os
from atlasquant_aion_first_install_preparation_v3.webauthn_ledger_reference import ReferenceWebAuthnLedger
p=json.load(open(sys.argv[1],encoding="utf-8"));ledger=ReferenceWebAuthnLedger(p["path"],scope=p["scope"])
original=ledger.connect
class Crash:
 def __init__(self,db):self.db=db
 def __getattr__(self,name):return getattr(self.db,name)
 def commit(self):self.db.commit();os._exit(23)
def connect(**kw):
 db=original(**kw)
 return db if kw.get('read_only') else Crash(db)
ledger.connect=connect
if p['kind']=='REVOKE':ledger.revoke_credential_reference('fixture-credential',generation=1,expected_key_sha256=p['old_pin'],operation_id='fixture-mutation')
else:
 cred=p['credential'];cred['public_key_cose']=bytes.fromhex(cred['public_key_cose'])
 ledger.rotate_credential_reference(p['binding'],cred,operation_id='fixture-mutation',expected_generation=1,expected_key_sha256=p['old_pin'],decision='SIMULATE_ROTATION_ONLY')
'''
        for kind in ['REVOKE','ROTATE']:
            with self.subTest(kind=kind):
                fixture=LedgerFixture()
                try:
                    key=ec.generate_private_key(ec.SECP256R1());cred=fixture.make_credential(key,generation=2)
                    pin=sha256(fixture.credential['public_key_cose']).hexdigest()
                    public={**cred,'public_key_cose':cred['public_key_cose'].hex()}
                    path=Path(fixture.tmp.name)/'public-mutation.json'
                    path.write_text(json.dumps(dict(kind=kind,path=str(fixture.path),scope=fixture.scope,old_pin=pin,credential=public,binding=fixture.request['binding'])),encoding='utf-8')
                    crashed=subprocess.run([sys.executable,'-B','-c',code,str(path)],capture_output=True,text=True,timeout=30)
                    self.assertEqual(crashed.returncode,23,crashed.stderr)
                    expected=fixture.mutation_digest(kind,'fixture-mutation')
                    read=read_receipt_reference(fixture.path,scope=fixture.scope,namespace=kind,operation_id='fixture-mutation',expected_request_digest=expected,minimum_sequence=2)
                    self.assertEqual(read['state'],'REFERENCE_DURABLE_RECEIPT_UNTRUSTED')
                    restarted=ReferenceWebAuthnLedger(fixture.path,scope=fixture.scope)
                    if kind=='REVOKE':
                        self.assertEqual(restarted.revoke_credential_reference('fixture-credential',generation=1,expected_key_sha256=pin,operation_id='fixture-mutation')['state'],'BLOCKED')
                        self.assertEqual(fixture.rows('credentials')[0]['state'],'REVOKED')
                    else:
                        self.assertEqual(restarted.rotate_credential_reference(fixture.request['binding'],cred,operation_id='fixture-mutation',expected_generation=1,expected_key_sha256=pin,decision='SIMULATE_ROTATION_ONLY')['state'],'BLOCKED')
                        self.assertEqual([r['generation'] for r in fixture.rows('credentials')],[1,2])
                finally:fixture.close()

    def test_no_positive_confirmation_if_postcommit_readback_fails(self):
        original=self.f.ledger.connect;reads=0
        def connect(**kw):
            nonlocal reads
            if kw.get('read_only'):
                reads+=1
                if reads==2:raise sqlite3.OperationalError('SECRET_READBACK')
            return original(**kw)
        with patch.object(self.f.ledger,'connect',side_effect=connect):
            # read_receipt_reference constructs its own reader, so inject at
            # the independent storage boundary rather than a writer handle.
            from atlasquant_aion_first_install_preparation_v3 import ledger_storage
            real=ledger_storage.LedgerStorage.connect
            independent_reads=0
            def independent(reader,**options):
                nonlocal independent_reads
                if options.get('read_only'):
                    independent_reads+=1
                    if independent_reads==2:raise sqlite3.OperationalError('SECRET_READBACK')
                return real(reader,**options)
            with patch.object(ledger_storage.LedgerStorage,'connect',new=independent):out=self.confirm()
        self.assertEqual(out['state'],'UNKNOWN_OUTCOME');self.assertEqual(self.f.rows('challenges')[0]['state'],'CONSUMED')
        self.check_blocked_retry()

if __name__=='__main__':unittest.main()
