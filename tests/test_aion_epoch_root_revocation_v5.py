"""Explicit fixture candidates never activate institutional roots or epochs."""
from copy import deepcopy
from contextlib import closing
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from atlasquant_aion_first_install_preparation_v5.contracts import digest, KINDS
from atlasquant_aion_first_install_preparation_v5.storage import AdmissionStorage
from tests.aion_receipt_admission_fixtures_v5 import AdmissionFixture

class ControlTests(unittest.TestCase):
    def setUp(self):self.f=AdmissionFixture();self.addCleanup(self.f.close)
    def blocked(self,out):self.assertEqual(out['state'],'BLOCKED',out)
    def control(self,event):return self.f.store.control(event,retained=self.f.retained)
    def test_epoch_candidate_is_durable_but_not_activated(self):
        e=self.f.control_event();out=self.control(e)
        self.assertEqual(out['state'],'REFERENCE_DURABLE_ADMISSION_UNTRUSTED');self.assertTrue(out['candidate_only'])
        self.assertEqual(self.f.store.config['config']['epoch'],1);self.assertFalse(out['root_trust_verified'])
        self.assertIn('EPOCH_NEXT:1',self.f.store.read(self.f.retained)['snapshot']['candidates'])

    def test_competing_epoch_transition_and_replay_block(self):
        e=self.f.control_event();self.control(e);self.blocked(self.control(e))
        other=self.f.control_event(event_id='fixture-competing');self.blocked(self.control(other))

    def test_epoch_jump_regression_forged_scope_approval_and_unknown_proofs(self):
        e=self.f.control_event()
        mutations=[('proposed_epoch',3),('proposed_epoch',0),('root_generation',True),('epoch',True),
            ('root_id','fixture-substitute'),('emitter','fixture-impostor'),('algorithm','RSA'),('schema','UNKNOWN')]
        for key,value in mutations:
            with self.subTest(field=key,value=value):
                bad=deepcopy(e);bad[key]=value;self.blocked(self.control(self.f.sign_control(bad)))
        for field in ('scope','owner_approval','required_proofs'):
            with self.subTest(field=field):
                bad=deepcopy(e)
                if field=='scope':bad[field]['tenant_id']='fixture-foreign'
                elif field=='owner_approval':bad[field]['state']='USER_APPROVED'
                else:bad[field]['institutional_custody']='VERIFIED'
                self.blocked(self.control(self.f.sign_control(bad)))

    def test_root_dual_signature_candidate_no_pin_activation(self):
        key=Ed25519PrivateKey.generate();e=self.f.control_event('ROOT_ROTATION',new_key=key)
        out=self.control(e);self.assertEqual(out['state'],'REFERENCE_DURABLE_ADMISSION_UNTRUSTED')
        self.assertTrue(out['candidate_only']);self.assertEqual(self.f.store.config['root']['generation'],1)
        self.assertFalse(out['human_consent_verified']);self.assertFalse(out['witness_key_enrollment_verified'])

    def test_incomplete_rotation_and_downgrade_block(self):
        key=Ed25519PrivateKey.generate();e=self.f.control_event('ROOT_ROTATION',new_key=key)
        for field,value in [('new_signature',None),('signature','00'*64)]:
            with self.subTest(field=field):bad=deepcopy(e);bad[field]=value;self.blocked(self.control(bad))
        bad=deepcopy(e);bad['new_root']['generation']=1;self.blocked(self.control(self.f.sign_control(bad,key)))

    def test_root_revocation_blocks_mathematically_valid_receipt(self):
        self.f.issue();out=self.control(self.f.control_event('CUSTODY_COMPROMISE'))
        self.assertEqual(out['state'],'REFERENCE_DURABLE_ADMISSION_UNTRUSTED');self.blocked(self.f.admit())
        self.assertEqual(self.f.store.read(self.f.retained)['snapshot']['root_state'],'FIXTURE_REVOKED')

    def test_witness_and_operator_revocation_persist_and_block(self):
        for kind,object_name in [('WITNESS_KEY_REVOCATION','key_id'),('OPERATOR_REVOCATION','operator_alias')]:
            with self.subTest(kind=kind):
                f=AdmissionFixture()
                try:
                    f.issue();e=f.control_event(kind);e['affected_object']=f.anchor.pins[1][object_name]
                    e['owner_approval']['event_digest']=digest({k:v for k,v in e.items() if k not in ('signature','new_signature','owner_approval')})
                    out=f.store.control(f.sign_control(e),retained=f.retained)
                    self.assertEqual(out['state'],'REFERENCE_DURABLE_ADMISSION_UNTRUSTED');self.blocked(f.admit())
                finally:f.close()

    def test_all_control_contracts_remain_fixture_only(self):
        for kind in sorted(KINDS):
            with self.subTest(kind=kind):
                f=AdmissionFixture()
                try:
                    key=Ed25519PrivateKey.generate() if kind=='ROOT_ROTATION' else None
                    out=f.store.control(f.control_event(kind,new_key=key),retained=f.retained)
                    self.assertEqual(out['state'],'REFERENCE_DURABLE_ADMISSION_UNTRUSTED')
                    for name in ('installation_authorized','worker_authorized','deploy_authorized','spending_approved','root_trust_verified'):
                        self.assertFalse(out[name])
                finally:f.close()

    def test_caller_repin_existing_database_rejected(self):
        changed=deepcopy(self.f.config);changed['root']['generation']=2
        with self.assertRaises(ValueError):AdmissionStorage(self.f.path,config=changed,expected_config_digest=digest(changed))

    def test_three_fabricated_domains_do_not_prove_custody(self):
        self.f.issue();out=self.f.admit()
        self.assertEqual(out['state'],'REFERENCE_DURABLE_ADMISSION_UNTRUSTED')
        for key in ('independent_custody_verified','independent_administrative_domains_verified',
                    'institutional_identity_verified','trusted_clock_verified','owner_identity_verified'):
            self.assertFalse(out[key])

    def test_restore_erased_revocation_detected_against_newer_reference(self):
        backup=self.f.path.with_suffix('.backup')
        with closing(sqlite3.connect(self.f.path)) as src,closing(sqlite3.connect(backup)) as dest:src.backup(dest)
        out=self.control(self.f.control_event('CUSTODY_COMPROMISE'));newer=out['retained_reference']
        with closing(sqlite3.connect(backup)) as src,closing(sqlite3.connect(self.f.path)) as dest:src.backup(dest)
        self.blocked(self.f.store.read(newer))
        # KNOWN NEGATIVE: privileged joint restoration of DB AND reference.
        restored=self.f.store.read(self.f.retained)
        self.assertEqual(restored['state'],'REFERENCE_LOCAL_SNAPSHOT_UNTRUSTED')
        self.assertEqual(restored['snapshot']['root_state'],'FIXTURE_ACTIVE')
        self.assertFalse(restored['independent_monotonicity_verified'])

    def test_control_stale_cas_and_wrong_parent(self):
        e=self.f.control_event();self.f.issue();self.blocked(self.control(e))
        e=self.f.control_event();e['previous_commitment']['local_head_sha256']='e'*64
        self.blocked(self.control(self.f.sign_control(e)))

if __name__=='__main__':unittest.main()
