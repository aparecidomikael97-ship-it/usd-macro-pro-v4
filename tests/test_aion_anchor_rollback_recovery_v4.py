from contextlib import closing
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import unittest
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric import ec
from atlasquant_aion_first_install_preparation.contracts import AUTHORITY_FIELDS
from atlasquant_aion_first_install_preparation_v3.webauthn_ledger_reference import ReferenceWebAuthnLedger
from atlasquant_aion_first_install_preparation_v4.commitments import capture_ledger_reference,commitment_digest,ZERO
from atlasquant_aion_first_install_preparation_v4.signed_anchors import pin_digest,READ_DOMAIN
from atlasquant_aion_first_install_preparation_v4.recovery_bridge import (
    compare_anchors_reference,reconcile_anchored_operation_reference,FixtureReadFile)
from tests.aion_signed_anchor_fixtures_v4 import AnchorFixture
from tests.aion_webauthn_ledger_fixtures_v3 import CHILD
from tests import test_aion_webauthn_recovery_v3 as fault_helpers

class AnchorRecoveryTests(unittest.TestCase):
    def setUp(self):self.f=AnchorFixture();self.addCleanup(self.f.close)
    def compare(self,members,*,causal=True,path=None):
        kwargs=dict(config=self.f.config,members=members,now=1000,revoked_keys=[],revoked_operators=[])
        if causal:out=reconcile_anchored_operation_reference(path or self.f.ledger.path,causal=self.f.causal,**kwargs)
        else:out=compare_anchors_reference(path or self.f.ledger.path,**kwargs)
        self.assertEqual(out['status'],'HARD_NO_GO')
        for k in AUTHORITY_FIELDS:self.assertIs(out[k],False)
        if 'safe_to_resume' in out:self.assertIs(out['safe_to_resume'],False)
        return out
    def backup(self,name='backup.db'):
        path=Path(self.f.ledger.tmp.name)/name;shutil.copyfile(self.f.ledger.path,path);return path

    def test_positive_causal_math_never_external_trust(self):
        self.f.consume();out=self.compare(self.f.members())
        self.assertEqual(out['state'],'REFERENCE_ANCHORED_CAUSAL_MATH_UNTRUSTED')
        for key in ['root_trust_verified','external_anchor_verified','independent_administrative_domains_verified','latest_head_independently_verified','rollback_protection_production_verified']:
            self.assertFalse(out[key])

    def test_A_complete_local_restore_retained_signed_heads_detected(self):
        self.f.ledger.issue(self.f.request);before=self.backup()
        self.f.ledger.ledger.confirm_assertion_reference(self.f.request,self.f.packet,attempt_id='fixture-attempt',now=1000)
        members=self.f.members();paths=self.f.public_files(members)
        shutil.copyfile(before,self.f.ledger.path)
        for member,path in zip(members,paths):member['response']=FixtureReadFile(path).read_reference()
        # The local snapshot first fails causal readback; pure state comparison
        # independently detects the retained head mismatch.
        self.assertNotEqual(self.compare(members)['state'],'REFERENCE_ANCHORED_CAUSAL_MATH_UNTRUSTED')
        self.assertEqual(self.compare(members,causal=False)['state'],'BLOCKED')
        self.assertEqual(self.f.ledger.rows('challenges')[0]['state'],'ISSUED')

    def test_B_joint_restore_selfconsistent_known_limit_not_independence(self):
        self.f.consume();before=self.backup();old=self.f.members();paths=self.f.public_files(old)
        witnesses=[Path(str(p)+'.old') for p in paths]
        for path,backup in zip(paths,witnesses):shutil.copyfile(path,backup)
        pin=sha256(self.f.ledger.credential['public_key_cose']).hexdigest()
        self.f.ledger.ledger.revoke_credential_reference('fixture-credential',generation=1,expected_key_sha256=pin,operation_id='fixture-revoke')
        latest=self.f.members();self.f.public_files(latest)
        shutil.copyfile(before,self.f.ledger.path)
        for path,backup in zip(paths,witnesses):shutil.copyfile(backup,path)
        for member,path in zip(old,paths):member['response']=FixtureReadFile(path).read_reference()
        out=self.compare(old);self.assertEqual(out['state'],'REFERENCE_ANCHORED_CAUSAL_MATH_UNTRUSTED')
        self.assertFalse(out['rollback_protection_production_verified'])
        self.assertFalse(out['independent_administrative_domains_verified'])
        self.assertEqual(self.compare(latest,causal=False)['state'],'BLOCKED')

    def test_C_same_sequence_divergent_histories_no_majority(self):
        branch=self.backup('fork.db');self.f.consume()
        fork=ReferenceWebAuthnLedger(branch,scope=self.f.ledger.scope)
        other=self.f.ledger.request_for(2);packet=self.f.ledger.packet(other)
        fork.issue_challenge_reference(other,generation=1,rp_id='offline-fixture.invalid',origin='https://offline-fixture.invalid',operation_id='fixture-fork-issue',now=1000)
        fork.confirm_assertion_reference(other,packet,attempt_id='fixture-fork-attempt',now=1000)
        members=self.f.members()
        divergent=self.f.capture(2,commitment_digest(self.f.floors[2]),path=branch)
        self.assertEqual(divergent['sequence'],members[0]['response']['commitment']['sequence'])
        self.assertNotEqual(divergent['state_digest'],members[0]['response']['commitment']['state_digest'])
        members[2]['response']=self.f.response(2,members[2]['query'],divergent)
        self.assertEqual(self.compare(members)['state'],'BLOCKED')
        self.assertEqual(self.compare(self.f.members(),causal=False,path=branch)['state'],'BLOCKED')

    def test_D_signed_old_anchor_with_new_floor_blocked(self):
        self.f.consume();new=self.f.members()
        old=deepcopy(new)
        for i,member in enumerate(old):
            member['floor']=new[i]['response']['commitment']
            member['response']=self.f.response(i,member['query'],self.f.floors[i])
        self.assertEqual(self.compare(old)['state'],'BLOCKED')

    def test_E_witness_absent_no_local_success_fallback(self):
        self.f.consume();members=self.f.members();members[2]['response']=None
        self.assertEqual(self.compare(members)['state'],'UNKNOWN_OUTCOME')

    def test_F_wrong_tenant_valid_signature_rejected_before_local_read(self):
        self.f.consume();members=self.f.members()
        bad=deepcopy(members[0]['response']);bad['commitment']['tenant_id']='fixture-other'
        members[0]['response']=self.f.sign(bad,0,READ_DOMAIN)
        with patch('atlasquant_aion_first_install_preparation_v4.recovery_bridge.capture_ledger_reference',side_effect=AssertionError('MUST_NOT_READ')) as read:
            self.assertEqual(self.compare(members)['state'],'BLOCKED');read.assert_not_called()

    def test_G_revocation_erased_by_restore_new_anchor_detects(self):
        self.f.consume();before=self.backup()
        self.f.ledger.ledger.revoke_credential_reference('fixture-credential',generation=1,expected_key_sha256=sha256(self.f.ledger.credential['public_key_cose']).hexdigest(),operation_id='fixture-revoke')
        members=self.f.members();revoked=members[0]['response']['commitment']['generation_revocation_digest']
        shutil.copyfile(before,self.f.ledger.path)
        self.assertEqual(self.f.ledger.rows('credentials')[0]['state'],'ACTIVE')
        self.assertNotEqual(self.f.capture(0,ZERO)['generation_revocation_digest'],revoked)
        self.assertEqual(self.compare(members)['state'],'BLOCKED')

    def test_H_rotation_erased_by_restore_generation_rejected(self):
        self.f.consume();before=self.backup()
        key=ec.generate_private_key(ec.SECP256R1());credential=self.f.ledger.make_credential(key,generation=2)
        self.f.ledger.ledger.rotate_credential_reference(self.f.ledger.request['binding'],credential,operation_id='fixture-rotation',expected_generation=1,expected_key_sha256=sha256(self.f.ledger.credential['public_key_cose']).hexdigest(),decision='SIMULATE_ROTATION_ONLY')
        members=self.f.members();shutil.copyfile(before,self.f.ledger.path)
        self.assertEqual(self.f.ledger.rows('credentials')[0]['generation'],1)
        self.assertEqual(self.compare(members)['state'],'BLOCKED')

    def test_I_counter_and_challenge_restore_detected(self):
        self.f.ledger.issue(self.f.request);before=self.backup()
        self.f.ledger.ledger.confirm_assertion_reference(self.f.request,self.f.packet,attempt_id='fixture-attempt',now=1000)
        members=self.f.members();shutil.copyfile(before,self.f.ledger.path)
        self.assertEqual(self.f.ledger.rows('credentials')[0]['sign_count'],1)
        self.assertEqual(self.f.ledger.rows('challenges')[0]['state'],'ISSUED')
        self.assertEqual(self.compare(members,causal=False)['state'],'BLOCKED')

    def test_J_three_files_keys_same_administration_not_quorum(self):
        self.f.consume();members=self.f.members();paths=self.f.public_files(members)
        for member,path in zip(members,paths):
            member['pin']['operator_alias']='fixture-shared-operator';member['pin']['administrative_domain_alias']='fixture-shared-admin'
            member['expected_pin_digest']=pin_digest(member['pin']);member['response']=FixtureReadFile(path).read_reference()
        self.assertEqual(self.compare(members)['state'],'BLOCKED')

    def test_valid_signatures_wrong_state_digest_cannot_confirm(self):
        self.f.consume();members=self.f.members()
        for i,member in enumerate(members):
            bad=deepcopy(member['response']);bad['commitment']['state_digest']='a'*64
            member['response']=self.f.sign(bad,i,READ_DOMAIN)
        self.assertEqual(self.compare(members)['state'],'BLOCKED')

    def test_floor_ancestry_not_only_sequence_or_claimed_parent(self):
        self.f.consume();members=self.f.members()
        for i,member in enumerate(members):
            member['floor']['local_head_sha256']='a'*64
            commitment=deepcopy(member['response']['commitment']);commitment['previous_commitment_digest']=commitment_digest(member['floor'])
            member['response']=self.f.response(i,member['query'],commitment)
        self.assertEqual(self.compare(members)['state'],'BLOCKED')

    def test_unknown_after_commit_causal_recovery_does_not_resend(self):
        self.f.ledger.issue(self.f.request);ledger=self.f.ledger.ledger;original=ledger.connect;calls=0
        def connect(**kw):
            nonlocal calls
            db=original(**kw)
            if kw.get('read_only'):return db
            calls+=1;return fault_helpers.Fault(db,when='after') if calls==2 else db
        with patch.object(ledger,'connect',side_effect=connect):
            out=ledger.confirm_assertion_reference(self.f.request,self.f.packet,attempt_id='fixture-attempt',now=1000)
        self.assertEqual(out['state'],'UNKNOWN_OUTCOME')
        events=len(self.f.ledger.rows('events'));recovered=self.compare(self.f.members())
        self.assertEqual(recovered['state'],'REFERENCE_ANCHORED_CAUSAL_MATH_UNTRUSTED');self.assertEqual(len(self.f.ledger.rows('events')),events)
        self.assertEqual(ledger.confirm_assertion_reference(self.f.request,self.f.packet,attempt_id='fixture-attempt',now=1000)['state'],'BLOCKED')

    def test_pending_admission_absence_not_proof_of_success_or_retry(self):
        self.f.ledger.issue(self.f.request);ledger=self.f.ledger.ledger;original=ledger.connect;calls=0
        def connect(**kw):
            nonlocal calls
            db=original(**kw)
            if kw.get('read_only'):return db
            calls+=1;return fault_helpers.Fault(db,when='before') if calls==2 else db
        with patch.object(ledger,'connect',side_effect=connect):ledger.confirm_assertion_reference(self.f.request,self.f.packet,attempt_id='fixture-attempt',now=1000)
        self.assertEqual(self.compare(self.f.members())['state'],'RECONCILIATION_REQUIRED')
        self.assertEqual(ledger.confirm_assertion_reference(self.f.request,self.f.packet,attempt_id='fixture-attempt',now=1000)['state'],'BLOCKED')

    def test_readonly_recovery_events_file_unchanged(self):
        self.f.consume();members=self.f.members();before=self.f.ledger.path.read_bytes();events=len(self.f.ledger.rows('events'))
        self.compare(members);self.compare(members)
        self.assertEqual(self.f.ledger.path.read_bytes(),before);self.assertEqual(len(self.f.ledger.rows('events')),events)

    def test_other_process_commit_crash_then_anchor_compare(self):
        self.f.ledger.issue(self.f.request);p=self.f.ledger.publish_input(self.f.request,self.f.packet)
        child=subprocess.run([sys.executable,'-B','-c',CHILD,str(p),'crash','fixture-attempt'],capture_output=True,text=True,timeout=30)
        self.assertEqual(child.returncode,23,child.stderr)
        self.assertEqual(self.compare(self.f.members())['state'],'REFERENCE_ANCHORED_CAUSAL_MATH_UNTRUSTED')

    def test_four_processes_one_consumption_anchored_readback(self):
        self.f.ledger.issue(self.f.request);p=self.f.ledger.publish_input(self.f.request,self.f.packet)
        children=[subprocess.Popen([sys.executable,'-B','-c',CHILD,str(p),'confirm','fixture-attempt'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(4)]
        outcomes=[]
        for child in children:
            out,err=child.communicate(timeout=30);self.assertEqual(child.returncode,0,err);outcomes.append(json.loads(out)['state'])
        self.assertEqual(outcomes.count('REFERENCE_DURABLE_RECEIPT_UNTRUSTED'),1)
        self.assertEqual(len(self.f.ledger.rows('attempts')),1)
        self.assertEqual(self.compare(self.f.members())['state'],'REFERENCE_ANCHORED_CAUSAL_MATH_UNTRUSTED')

    def test_three_processes_verify_math_still_same_administrator_blocked(self):
        self.f.consume();members=self.f.members()
        for member in members:
            member['pin']['operator_alias']='fixture-shared-operator';member['expected_pin_digest']=pin_digest(member['pin'])
        code='import json,sys;from atlasquant_aion_first_install_preparation_v4.signed_anchors import verify_fresh_read_reference;p=json.load(open(sys.argv[1],encoding="utf-8"));print(json.dumps(verify_fresh_read_reference(**p)))'
        children=[]
        for i,member in enumerate(members):
            p=Path(self.f.ledger.tmp.name)/('public-process-'+str(i)+'.json')
            cfg=self.f.cfg(i)
            payload={**member,'config':cfg,'now':1000,'revoked_keys':[],'revoked_operators':[]};payload.pop('floor',None)
            payload['floor']=member['floor'];payload.pop('expected_pin_digest',None);payload['expected_pin_digest']=member['expected_pin_digest'];payload.pop('pin',None);payload['pin']=member['pin']
            p.write_text(json.dumps(payload),encoding='utf-8')
            children.append(subprocess.Popen([sys.executable,'-B','-c',code,str(p)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True))
        for child in children:
            out,err=child.communicate(timeout=30);self.assertEqual(child.returncode,0,err)
            reply=json.loads(out);self.assertEqual(reply['state'],'REFERENCE_FRESH_READ_MATH_UNTRUSTED');self.assertFalse(reply['root_trust_verified'])
        self.assertEqual(self.compare(members)['state'],'BLOCKED')

    def test_incomplete_wrong_causal_and_missing_db_no_confirmation(self):
        self.f.consume();members=self.f.members()
        for field,value in [('request_digest','a'*64),('operation_id','fixture-other')]:
            with self.subTest(field=field):
                old=dict(self.f.causal);self.f.causal[field]=value
                self.assertNotEqual(self.compare(members)['state'],'REFERENCE_ANCHORED_CAUSAL_MATH_UNTRUSTED');self.f.causal=old
        missing=Path(self.f.ledger.tmp.name)/'missing.db'
        self.assertEqual(self.compare(members,path=missing)['state'],'UNKNOWN_OUTCOME');self.assertFalse(missing.exists())

    def test_single_ro_snapshot_coherent_during_concurrent_commit(self):
        from atlasquant_aion_first_install_preparation_v4 import commitments
        original=commitments._rows;fired=False
        def rows(db,table,order):
            nonlocal fired
            if table=='credentials' and not fired:
                fired=True;self.assertEqual(self.f.consume()['state'],'REFERENCE_DURABLE_RECEIPT_UNTRUSTED')
            return original(db,table,order)
        with patch.object(commitments,'_rows',side_effect=rows):
            out=capture_ledger_reference(self.f.ledger.path,config=self.f.config,previous_commitment_digest=ZERO)
        self.assertEqual(out['state'],'REFERENCE_SNAPSHOT_UNTRUSTED')
        self.assertEqual(out['commitment']['sequence'],self.f.floors[0]['sequence'])
        self.assertEqual(out['commitment']['credential_state_digest'],self.f.floors[0]['credential_state_digest'])
        self.assertEqual(out['commitment']['causal_operations_digest'],self.f.floors[0]['causal_operations_digest'])
        self.assertGreater(self.f.capture(0,ZERO)['sequence'],out['commitment']['sequence'])

    def test_uniform_trust_flags_false_for_errors_unknown_and_math(self):
        from atlasquant_aion_first_install_preparation_v4.outcomes import NO_TRUST,result
        for out in [result('UNKNOWN_OUTCOME',root_trust_verified=True,safe_to_resume=True),
                    capture_ledger_reference('missing-fixture.db',config=self.f.config,previous_commitment_digest=ZERO),
                    compare_anchors_reference(self.f.ledger.path,config=self.f.config,members=None,now=1000)]:
            for key in NO_TRUST:self.assertIs(out[key],False,key)

    def test_snapshot_close_error_positive_and_absent_cause_uncertain(self):
        from atlasquant_aion_first_install_preparation_v3 import ledger_storage
        self.f.consume();original=ledger_storage.LedgerStorage.connect
        def connect(reader,**kw):
            return fault_helpers.Fault(original(reader,**kw),when='normal',close_fail=True)
        for causal in [self.f.causal,{**self.f.causal,'operation_id':'fixture-missing'}]:
            with self.subTest(causal=causal['operation_id']):
                with patch.object(ledger_storage.LedgerStorage,'connect',new=connect):
                    out=capture_ledger_reference(self.f.ledger.path,config=self.f.config,previous_commitment_digest=ZERO,causal=causal)
                self.assertEqual(out['state'],'UNKNOWN_OUTCOME');self.assertNotIn('SECRET',str(out))

if __name__=='__main__':unittest.main()
