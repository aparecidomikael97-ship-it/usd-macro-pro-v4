"""Real local SQLite/process faults; disposable existing crypto fixtures only."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest

from atlasquant_aion_v2_isolated_sqlite_witness_cas_reference import COMMITTED, REPLAY
from tests import test_atlasquant_aion_v2_isolated_sqlite_witness_cas_reference as fixtures

CHILD = '''
import json,sys,os
from unittest.mock import patch
from atlasquant_aion_v2_isolated_sqlite_witness_cas_reference import ReferenceIsolatedSqliteWitnessCAS
p=json.load(open(sys.argv[1],encoding="utf-8"))
with patch("socket.socket.connect",side_effect=AssertionError("NO_NETWORK")):
 s=ReferenceIsolatedSqliteWitnessCAS(p["path"],config=p["config"],genesis_head=p["genesis"])
 try:
  out=s.cas_reference_only(operation_id=sys.argv[2],**p["args"])
  if len(sys.argv)>3:os._exit(23)
  print(json.dumps(out,sort_keys=True))
 finally:s.close()
'''

class CommitFault:
    def __init__(self,connection,*,after=True,rollback_failure=False):
        self.connection=connection;self.after=after;self.rollback_failure=rollback_failure
    def __getattr__(self,name):return getattr(self.connection,name)
    def commit(self):
        if self.after:self.connection.commit()
        raise sqlite3.OperationalError("SECRET_FAULT_SENTINEL")
    def rollback(self):
        if self.rollback_failure:raise sqlite3.OperationalError("SECRET_ROLLBACK_SENTINEL")
        self.connection.rollback()

class ExistingWitnessProcessTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.IsolatedWitnessTests(methodName='runTest');self.fixture.setUp()
        self.q,self.r,self.n=self.fixture.candidate()
        self.args=dict(expected_query=self.q,signed_read=self.r,witness_public_pin=self.fixture.witness_pin,
                       signed_next_collector_receipt=self.n,collector_public_pin=self.fixture.collector_pin)
        self.input=Path(self.fixture.tmp.name)/'public-fixture.json'
        self.input.write_text(json.dumps(dict(path=str(self.fixture.witness_path),config=self.fixture.config,
                                            genesis=self.fixture.genesis,args=self.args)),encoding='utf-8')
    def tearDown(self):self.fixture.tearDown()
    def process(self,op,crash=False):
        return subprocess.Popen([sys.executable,'-B','-c',CHILD,str(self.input),op]+(['crash'] if crash else []),
                                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    def read(self,p):
        out,err=p.communicate(timeout=60);self.assertEqual(p.returncode,0,err)
        result=json.loads(out);self.assertFalse(result['safe_to_resume']);self.assertFalse(result['provider_called'])
        return result
    def test_different_processes_identical_operation_single_append(self):
        results=[self.read(p) for p in [self.process('same-operation') for _ in range(4)]]
        self.assertEqual(sum(x['state']==COMMITTED for x in results),1)
        self.assertEqual(sum(x['state']==REPLAY for x in results),3)
        self.assertEqual(self.fixture.service.snapshot()['local_reference_appends'],1)
    def test_different_processes_competing_operations_one_cas_winner(self):
        results=[self.read(p) for p in [self.process('operation-'+str(i)) for i in range(4)]]
        self.assertEqual(sum(x['state']==COMMITTED for x in results),1)
        self.assertEqual(sum(x['state']=='BLOCKED' for x in results),3)
    def test_process_exit_after_commit_fresh_readback_no_new_append(self):
        p=self.process('crash-operation',True);p.communicate(timeout=60);self.assertEqual(p.returncode,23)
        self.assertEqual(self.fixture.service.snapshot()['local_reference_appends'],1)
        out=self.read(self.process('crash-operation'));self.assertEqual(out['state'],REPLAY)
        self.assertEqual(out['local_reference_appends'],1)
    def test_commit_completed_error_must_be_unknown_not_claim_rollback(self):
        native=self.fixture.service.db
        self.fixture.service.db=CommitFault(native)
        try:out=self.fixture.service.cas_reference_only(operation_id='lost-ack',**self.args)
        finally:self.fixture.service.db=native
        self.assertEqual(self.fixture.service.snapshot()['local_reference_appends'],1)
        print('REAL_SQLITE_READBACK_APPENDS=1; CALLER_STATE='+out['state'])
        self.assertEqual(out['state'],'UNKNOWN_OUTCOME',out)
        self.assertIsNone(out['local_reference_appends'])
        self.assertNotIn('SECRET_FAULT_SENTINEL',json.dumps(out))
        self.assertFalse(out['safe_to_resume']);self.assertFalse(out['provider_called'])
        self.assertEqual(self.fixture.service.snapshot()['local_reference_appends'],1)
        self.assertEqual(self.read(self.process('lost-ack'))['state'],REPLAY)
        self.assertEqual(self.fixture.service.snapshot()['local_reference_appends'],1)
    def test_commit_error_before_commit_also_requires_independent_readback(self):
        native=self.fixture.service.db;self.fixture.service.db=CommitFault(native,after=False)
        try:out=self.fixture.service.cas_reference_only(operation_id='precommit-fault',**self.args)
        finally:self.fixture.service.db=native
        self.assertEqual(out['state'],'UNKNOWN_OUTCOME');self.assertFalse(out['safe_to_resume'])
        self.assertEqual(self.fixture.service.snapshot()['local_reference_appends'],0)
        # Absence does not grant production permission or automatic re-dispatch.
    def test_rollback_failure_never_escapes_or_claims_definite_absence(self):
        native=self.fixture.service.db;self.fixture.service.db=CommitFault(native,after=False,rollback_failure=True)
        try:out=self.fixture.service.cas_reference_only(operation_id='rollback-fault',**self.args)
        finally:
            self.fixture.service.db=native
            if native.in_transaction:native.rollback()
        self.assertEqual(out['state'],'UNKNOWN_OUTCOME');self.assertIsNone(out['local_reference_appends'])
        self.assertNotIn('SECRET',json.dumps(out))
    def test_other_tenant_cannot_open_existing_witness(self):
        cfg=deepcopy(self.fixture.config);cfg['tenant_id']='tenant-b'
        with self.assertRaises(ValueError):self.fixture.open_service(config=cfg)
    def test_same_operation_payload_changed_after_restart_blocks(self):
        self.assertEqual(self.read(self.process('bound-operation'))['state'],COMMITTED)
        changed=deepcopy(self.args);changed['signed_next_collector_receipt']['signature_hex']='0'*128
        out=self.fixture.service.cas_reference_only(operation_id='bound-operation',**changed)
        self.assertEqual(out['state'],'BLOCKED');self.assertFalse(out['safe_to_resume'])

if __name__=='__main__':unittest.main()
