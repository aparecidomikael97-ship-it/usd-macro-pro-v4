from contextlib import closing
from copy import deepcopy
from pathlib import Path
import sqlite3
import subprocess
import sys
import json
import unittest
from unittest.mock import patch
from atlasquant_aion_first_install_preparation.contracts import AUTHORITY_FIELDS
from atlasquant_aion_first_install_preparation_v2.causal_readback_reference import (
    read_operation_reference, reconcile_simulated_domains, SimulatedProvider, attempt_simulated_once)
from atlasquant_aion_v2_isolated_sqlite_witness_cas_reference import ReferenceIsolatedSqliteWitnessCAS, _digest
from atlasquant_aion_v2_one_shot_unknown_outcome_journal_reference import ReferenceOneShotUnknownOutcomeJournal
from tests import test_atlasquant_aion_v2_isolated_sqlite_witness_cas_reference as cas_fixtures
from tests import test_atlasquant_aion_v2_one_shot_unknown_outcome_journal_reference as journal_fixtures

class CausalRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=cas_fixtures.IsolatedWitnessTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.q,self.r,self.n=self.fixture.candidate()
        f=self.fixture
        self.inputs=dict(operation_id='op-1',expected_query=self.q,signed_read=self.r,
            signed_next_collector_receipt=self.n,witness_public_pin=f.witness_pin,collector_public_pin=f.collector_pin)
        self.read_options=dict(config=f.config,genesis_head=f.genesis,operation_id='op-1',expected_query=self.q,
            signed_read=self.r,signed_next_collector_receipt=self.n,minimum_sequence=2,minimum_epoch=6)

    def read(self,**override):
        out=read_operation_reference(self.fixture.witness_path,**{**self.read_options,**override})
        for k in AUTHORITY_FIELDS:self.assertIs(out[k],False)
        return out

    def test_readback_after_lost_ack_does_not_append(self):
        provider=SimulatedProvider(self.fixture.service,fault='LOST_ACK')
        with self.assertRaises(OSError):provider.write_reference(**self.inputs)
        for _ in range(3):self.assertEqual(self.read()['state'],'REFERENCE_CAUSAL_MATCH_UNTRUSTED')
        self.assertEqual(self.fixture.service.snapshot()['local_reference_appends'],1)
        self.assertEqual(provider.write_attempts,1)

    def test_postcommit_error_same_causal_read(self):
        provider=SimulatedProvider(self.fixture.service,fault='AFTER_COMMIT')
        with self.assertRaises(OSError):provider.write_reference(**self.inputs)
        self.assertEqual(self.read()['state'],'REFERENCE_CAUSAL_MATCH_UNTRUSTED')

    def test_three_fake_success_acks_do_not_confirm(self):
        j=journal_fixtures.OneShotUnknownOutcomeTests();j.setUp();self.addCleanup(j.tearDown)
        j.intent['full_provider_request_sha256']=_digest(self.inputs);j.journal.prepare_reference_only(j.intent)
        providers=[SimulatedProvider(self.fixture.service,fault='FAKE_SUCCESS') for _ in range(3)]
        self.assertEqual(attempt_simulated_once(j.journal,j.intent,providers,self.inputs)['state'],'RECONCILIATION_REQUIRED')
        self.assertEqual(self.read(minimum_sequence=1)['state'],'RECONCILIATION_REQUIRED')
        self.assertEqual(attempt_simulated_once(j.journal,j.intent,providers,self.inputs)['state'],'BLOCKED')
        self.assertEqual([p.write_attempts for p in providers],[1,1,1])

    def test_recovery_interrupted_claim_not_released(self):
        j=journal_fixtures.OneShotUnknownOutcomeTests();j.setUp();self.addCleanup(j.tearDown)
        j.intent['full_provider_request_sha256']=_digest(self.inputs);j.journal.prepare_reference_only(j.intent)
        providers=[SimulatedProvider(self.fixture.service,fault='LOST_ACK') for _ in range(3)]
        attempt_simulated_once(j.journal,j.intent,providers,self.inputs)
        with patch('atlasquant_aion_first_install_preparation_v2.causal_readback_reference.sqlite3.connect',side_effect=sqlite3.OperationalError('INTERRUPTED')):
            self.assertEqual(self.read()['state'],'UNKNOWN_OUTCOME')
        self.assertEqual(attempt_simulated_once(j.journal,j.intent,providers,self.inputs)['state'],'BLOCKED')
        self.assertEqual([p.write_attempts for p in providers],[1,0,0])

    def test_unknown_types_history_bound_no_success(self):
        self.assertEqual(self.read(minimum_sequence=True)['state'],'BLOCKED')
        self.assertEqual(self.read(expected_query=None)['state'],'BLOCKED')
        self.assertEqual(self.read(expected_query={'large':'x'*33000})['state'],'BLOCKED')
        self.assertEqual(reconcile_simulated_domains(None)['state'],'UNKNOWN_OUTCOME')

    def test_fake_ack_and_precommit_never_confirm(self):
        for fault in ['FAKE_SUCCESS','BEFORE_COMMIT']:
            with self.subTest(fault=fault):
                p=SimulatedProvider(self.fixture.service,fault=fault)
                if fault=='BEFORE_COMMIT':
                    with self.assertRaises(OSError):p.write_reference(**self.inputs)
                else:p.write_reference(**self.inputs)
                self.assertEqual(self.read(minimum_sequence=1)['state'],'RECONCILIATION_REQUIRED')

    def test_payload_operation_and_scope_conflicts(self):
        self.fixture.service.cas_reference_only(**self.inputs)
        changed=deepcopy(self.q);changed['tenant_id']='other'
        for overrides in [dict(expected_query=changed),dict(operation_id='op-other'),dict(config={**self.fixture.config,'tenant_id':'other'})]:
            with self.subTest(overrides=list(overrides)):
                self.assertNotEqual(self.read(**overrides)['state'],'REFERENCE_CAUSAL_MATCH_UNTRUSTED')

    def test_restored_head_epoch_and_fork(self):
        self.fixture.service.cas_reference_only(**self.inputs)
        self.assertEqual(self.read(minimum_sequence=3)['state'],'BLOCKED')
        self.assertEqual(self.read(minimum_epoch=7)['state'],'BLOCKED')
        self.fixture.service.db.execute("UPDATE witness_ref_appends SET snapshot_sha256=?",('f'*64,))
        self.assertEqual(self.read()['state'],'UNKNOWN_OUTCOME')

    def test_read_failure_never_retry(self):
        with patch('atlasquant_aion_first_install_preparation_v2.causal_readback_reference.sqlite3.connect',side_effect=sqlite3.OperationalError('PRIVATE_SECRET')):
            out=self.read();self.assertEqual(out['state'],'UNKNOWN_OUTCOME');self.assertNotIn('PRIVATE_SECRET',str(out))

    def test_missing_read_does_not_create_file(self):
        path=Path(self.fixture.tmp.name)/'missing.db'
        out=read_operation_reference(path,**self.read_options)
        self.assertEqual(out['state'],'UNKNOWN_OUTCOME');self.assertFalse(path.exists())

    def test_read_uses_new_thread_connection(self):
        from concurrent.futures import ThreadPoolExecutor
        self.fixture.service.cas_reference_only(**self.inputs)
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(lambda _:self.read(),range(2)))
        self.assertTrue(all(o['state']=='REFERENCE_CAUSAL_MATCH_UNTRUSTED' for o in outcomes))

    def observations(self):
        return [dict(domain='fixture-'+str(i),controller='controller-'+str(i),key_pin='key-'+str(i),read=self.read()) for i in range(3)]

    def test_three_separate_files_causal_match_still_no_authority(self):
        observations=[]
        for i in range(3):
            path=Path(self.fixture.tmp.name)/('domain-'+str(i)+'.db')
            with closing(ReferenceIsolatedSqliteWitnessCAS(path,config=self.fixture.config,genesis_head=self.fixture.genesis)) as cas:
                cas.cas_reference_only(**self.inputs)
            read=read_operation_reference(path,**self.read_options)
            observations.append(dict(domain='fixture-'+str(i),controller='controller-'+str(i),key_pin='key-'+str(i),read=read))
        out=reconcile_simulated_domains(observations)
        self.assertEqual(out['reference_outcome'],'CONFIRMED')
        self.assertFalse(out['independent_administrative_domains_verified'])
        for k in AUTHORITY_FIELDS:self.assertIs(out[k],False)

    def test_same_authority_conflict_revocation_unknown(self):
        self.fixture.service.cas_reference_only(**self.inputs)
        for field in ['domain','controller','key_pin']:
            with self.subTest(field=field):
                obs=self.observations();obs[1][field]=obs[0][field];self.assertEqual(reconcile_simulated_domains(obs)['state'],'BLOCKED')
        obs=self.observations();obs[1]['read']['current_head']['sequence']=99
        self.assertEqual(reconcile_simulated_domains(obs)['state'],'BLOCKED')
        for revoked in [True,None]:
            with self.subTest(revoked=revoked):self.assertEqual(reconcile_simulated_domains(self.observations(),revoked=revoked)['state'],'BLOCKED')
        for state in ['UNKNOWN_OUTCOME','RECONCILIATION_REQUIRED','STALE','CONFIRMED','BLOCKED']:
            with self.subTest(state=state):
                obs=self.observations();obs[0]['read']['state']=state
                self.assertNotEqual(reconcile_simulated_domains(obs)['state'],'REFERENCE_CONFIRMED_UNTRUSTED')

    def test_durable_claim_restart_denies_all_second_writes(self):
        j=journal_fixtures.OneShotUnknownOutcomeTests();j.setUp();self.addCleanup(j.tearDown)
        j.intent['full_provider_request_sha256']=_digest(self.inputs)
        j.journal.prepare_reference_only(j.intent)
        providers=[SimulatedProvider(self.fixture.service,fault='LOST_ACK') for _ in range(3)]
        out=attempt_simulated_once(j.journal,j.intent,providers,self.inputs)
        self.assertEqual(out['state'],'UNKNOWN_OUTCOME')
        with closing(ReferenceOneShotUnknownOutcomeJournal(j.path,config=j.config)) as reopened:
            self.assertEqual(attempt_simulated_once(reopened,j.intent,providers,self.inputs)['state'],'BLOCKED')
        self.assertEqual([p.write_attempts for p in providers],[1,0,0])
        self.assertEqual(self.read()['state'],'REFERENCE_CAUSAL_MATCH_UNTRUSTED')

    def test_durable_payload_mismatch_no_write(self):
        j=journal_fixtures.OneShotUnknownOutcomeTests();j.setUp();self.addCleanup(j.tearDown)
        j.journal.prepare_reference_only(j.intent)
        providers=[SimulatedProvider(self.fixture.service) for _ in range(3)]
        self.assertEqual(attempt_simulated_once(j.journal,j.intent,providers,self.inputs)['state'],'BLOCKED')
        self.assertEqual([p.write_attempts for p in providers],[0,0,0])

    def test_crash_commit_then_other_process_read_only_recovery(self):
        from tests.test_aion_first_install_reference_processes_v1 import CHILD
        p=Path(self.fixture.tmp.name)/'public-process-input.json'
        args={k:v for k,v in self.inputs.items() if k!='operation_id'}
        p.write_text(json.dumps(dict(path=str(self.fixture.witness_path),config=self.fixture.config,
            genesis=self.fixture.genesis,args=args,read=self.read_options)),encoding='utf-8')
        crashed=subprocess.run([sys.executable,'-B','-c',CHILD,str(p),'op-1','crash'],capture_output=True,text=True,timeout=30)
        self.assertEqual(crashed.returncode,23)
        read_code='import json,sys;from atlasquant_aion_first_install_preparation_v2.causal_readback_reference import read_operation_reference;p=json.load(open(sys.argv[1],encoding="utf-8"));print(json.dumps(read_operation_reference(p["path"],**p["read"])))'
        recovered=subprocess.run([sys.executable,'-B','-c',read_code,str(p)],capture_output=True,text=True,timeout=30)
        self.assertEqual(recovered.returncode,0,recovered.stderr)
        self.assertEqual(json.loads(recovered.stdout)['state'],'REFERENCE_CAUSAL_MATCH_UNTRUSTED')
        self.assertEqual(self.fixture.service.snapshot()['local_reference_appends'],1)

    def test_competing_processes_one_durable_claim(self):
        j=journal_fixtures.OneShotUnknownOutcomeTests();j.setUp();self.addCleanup(j.tearDown)
        j.journal.prepare_reference_only(j.intent)
        p=Path(self.fixture.tmp.name)/'journal-public-input.json'
        p.write_text(json.dumps(dict(path=str(j.path),config=j.config,intent=j.intent)),encoding='utf-8')
        code='import json,sys;from atlasquant_aion_v2_one_shot_unknown_outcome_journal_reference import ReferenceOneShotUnknownOutcomeJournal;p=json.load(open(sys.argv[1],encoding="utf-8"));j=ReferenceOneShotUnknownOutcomeJournal(p["path"],config=p["config"]);print(json.dumps(j.claim_reference_only(intent=p["intent"])));j.close()'
        children=[subprocess.Popen([sys.executable,'-B','-c',code,str(p)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(4)]
        states=[]
        for child in children:
            out,err=child.communicate(timeout=30);self.assertEqual(child.returncode,0,err);states.append(json.loads(out)['state'])
        from atlasquant_aion_v2_one_shot_unknown_outcome_journal_reference import LOCAL_CLAIM, REPLAY_BLOCKED
        self.assertEqual(states.count(LOCAL_CLAIM),1);self.assertEqual(states.count(REPLAY_BLOCKED),3)

if __name__=='__main__':unittest.main()
