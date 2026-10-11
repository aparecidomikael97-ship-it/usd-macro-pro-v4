"""Adversarial durable query/receipt/floor tests using native SQLite."""
from copy import deepcopy
import sqlite3
import unittest
from contextlib import closing
from unittest.mock import patch
from atlasquant_aion_first_install_preparation_v4.signed_anchors import verify_fresh_read_reference
from atlasquant_aion_first_install_preparation_v5.contracts import digest
from tests.aion_receipt_admission_fixtures_v5 import AdmissionFixture

class DurableAdmissionTests(unittest.TestCase):
    def setUp(self):self.f=AdmissionFixture();self.addCleanup(self.f.close)
    def snapshot(self):return self.f.store.read(self.f.retained)['snapshot']
    def blocked(self,out):self.assertEqual(out['state'],'BLOCKED',out)
    def issued(self):self.assertEqual(self.f.issue()['state'],'REFERENCE_DURABLE_ADMISSION_UNTRUSTED')

    def test_reproduces_v4_stateless_nonce_limitation_and_closes_local_replay(self):
        f=self.f;m=f.anchor.members()[0]
        for _ in range(2):
            out=verify_fresh_read_reference(m['response'],query=m['query'],pin=m['pin'],expected_pin_digest=m['expected_pin_digest'],
                config=f.anchor.cfg(0),floor=m['floor'],now=1000,consumed_nonces=[],revoked_keys=[],revoked_operators=[])
            self.assertEqual(out['state'],'REFERENCE_FRESH_READ_MATH_UNTRUSTED')
        self.issued();self.assertEqual(f.admit()['state'],'REFERENCE_DURABLE_ADMISSION_UNTRUSTED');self.blocked(f.admit())
        self.assertEqual(len(self.snapshot()['receipts']),3)

    def test_atomic_nonce_receipts_and_floor(self):
        self.issued();out=self.f.admit();self.assertTrue(out['local_nonce_consumption_verified'])
        s=self.snapshot();self.assertEqual({v['state'] for v in s['nonces'].values()},{'CONSUMED'})
        self.assertEqual(len(s['receipts']),3)
        for i,floor in enumerate(s['floors']):
            self.assertEqual(floor['receipt_digest'],digest(self.f.receipts[i]))
            self.assertEqual(floor['commitment'],self.f.receipts[i]['response']['commitment'])
        self.assertFalse(out['installation_authorized']);self.assertFalse(out['durable_nonce_consumption_verified'])

    def test_no_issued_nonce_no_admission(self):self.blocked(self.f.admit())
    def test_reissue_same_nonce_and_attempt_never_allowed(self):
        self.issued();self.blocked(self.f.issue())
        for b in self.f.bindings:b['query']['nonce']='a'*63+str(self.f.bindings.index(b))
        self.blocked(self.f.store.issue(self.f.bindings,operation_id='fixture-issue-again',retained=self.f.retained,now=1000))

    def test_wrong_binding_fields_never_reserve(self):
        self.issued();original=deepcopy(self.f.bindings)
        changes={'root_id':'fixture-other-root','root_generation':2,'expected_pin_digest':'a'*64,
            'minimum_sequence':0,'challenge':'fixture-other','operation':'fixture-other','attempt_id':'fixture-other',
            'expected_commitment_digest':'a'*64,'previous_receipt_digest':'a'*64,'revocation_head':'a'*64}
        for key,value in changes.items():
            with self.subTest(field=key):
                self.f.bindings=deepcopy(original);self.f.bindings[0][key]=value;self.blocked(self.f.admit())
                self.assertEqual({v['state'] for v in self.snapshot()['nonces'].values()},{'ISSUED'})

    def test_wrong_query_scope_pin_epoch_and_nonce(self):
        self.issued();original=deepcopy(self.f.bindings)
        for key,value in dict(owner_id='fixture-other',tenant_id='fixture-other',workspace_id='fixture-other',
            ledger_id='fixture-other',witness_id='fixture-other',minimum_epoch=2,key_generation=2,
            nonce='b'*64,root_provenance_digest='b'*64,policy_id='fixture-other',policy_version=2).items():
            with self.subTest(field=key):
                self.f.bindings=deepcopy(original);self.f.bindings[0]['query'][key]=value;self.blocked(self.f.admit())
        self.assertEqual({v['state'] for v in self.snapshot()['nonces'].values()},{'ISSUED'})

    def test_signed_other_query_cannot_consume(self):
        self.issued();self.f.receipts[0]['binding_digest']='c'*64
        self.f.receipts[0]=self.f.sign_receipt(self.f.receipts[0],0);self.blocked(self.f.admit())

    def test_signature_schema_algorithm_and_encoding(self):
        self.issued();original=deepcopy(self.f.receipts)
        for key,value in dict(signature='00'*64,algorithm='RSA',schema='UNKNOWN',receipt_id=7,extra='bad').items():
            with self.subTest(field=key):
                self.f.receipts=deepcopy(original);self.f.receipts[0][key]=value;self.blocked(self.f.admit())

    def test_three_required_no_majority_no_local_fallback(self):
        self.issued();original=deepcopy(self.f.receipts)
        for receipts in (original[:2],original+[original[0]],None):
            with self.subTest(size=None if receipts is None else len(receipts)):
                self.f.receipts=receipts;self.blocked(self.f.admit())
        for i in range(3):
            with self.subTest(missing=i):
                self.f.receipts=deepcopy(original);self.f.receipts[i]['response']=None;self.blocked(self.f.admit())
        self.assertEqual(len(self.snapshot()['receipts']),0)

    def test_expired_nonce_cannot_retry_or_reissue(self):
        self.issued();out=self.f.store.admit(self.f.bindings,self.f.receipts,operation_id='fixture-expired',
            retained=self.f.retained,now=1050,ledger_path=self.f.anchor.ledger.path,causal=self.f.anchor.causal)
        self.blocked(out);self.blocked(self.f.issue())
        q=self.f.store.quarantine(self.f.bindings,operation_id='fixture-expire-quarantine',retained=self.f.retained)
        self.assertEqual(q['state'],'REFERENCE_DURABLE_ADMISSION_UNTRUSTED');self.blocked(self.f.admit())
        self.assertEqual({r['state'] for r in self.snapshot()['nonces'].values()},{'QUARANTINED'})

    def test_unknown_revocation_state_cannot_be_invented(self):
        self.f.config['required_proofs']['independent_revocation_channel']='VERIFIED'
        from atlasquant_aion_first_install_preparation_v5.storage import AdmissionStorage
        with self.assertRaises(ValueError):AdmissionStorage(self.f.path,config=self.f.config,expected_config_digest=digest(self.f.config))

    def test_changed_payload_same_id_and_reconciliation(self):
        self.issued();out=self.f.admit();self.assertEqual(out['state'],'REFERENCE_DURABLE_ADMISSION_UNTRUSTED')
        request=dict(bindings=self.f.bindings,receipts=self.f.receipts,causal=self.f.anchor.causal)
        self.assertEqual(self.f.store.reconcile('fixture-admit',digest(request),self.f.retained)['state'],'REFERENCE_DURABLE_ADMISSION_UNTRUSTED')
        request['causal']['request_digest']='a'*64
        self.blocked(self.f.store.reconcile('fixture-admit',digest(request),self.f.retained))

    def test_causal_read_must_match_persisted_consumption(self):
        self.issued();self.f.anchor.causal['operation_id']='fixture-nonexistent';self.blocked(self.f.admit())
        self.assertEqual(len(self.snapshot()['receipts']),0)

    def test_no_ledger_read_for_wrong_tenant(self):
        self.issued();self.f.bindings[0]['query']['tenant_id']='fixture-foreign'
        with patch('atlasquant_aion_first_install_preparation_v5.admission.compare_anchors_reference',side_effect=AssertionError('NO_READ')):
            self.blocked(self.f.admit())

    def test_retained_floor_required_and_wrong_scope_block(self):
        self.blocked(self.f.store.read(None));bad=deepcopy(self.f.retained);bad['config_digest']='d'*64
        self.blocked(self.f.store.read(bad))

    def test_receipt_received_is_not_admitted(self):
        self.assertEqual(len(self.snapshot()['receipts']),0);self.issued();self.assertEqual(len(self.snapshot()['receipts']),0)

    def test_input_mutation_does_not_change_persisted_binding(self):
        self.issued();self.f.bindings[0]['challenge']='fixture-mutation'
        self.assertEqual(self.snapshot()['nonces'][self.f.bindings[0]['query']['nonce']]['binding']['challenge'],'fixture-read-challenge')

    def test_duplicate_json_rejected_at_existing_v4_reader(self):
        from atlasquant_aion_first_install_preparation_v4.recovery_bridge import FixtureReadFile
        path=self.f.path.with_suffix('.json');path.write_text('{"schema":"x","schema":"y"}',encoding='utf-8')
        self.assertIsNone(FixtureReadFile(path).read_reference())

    def test_higher_epoch_signed_correctly_not_admitted(self):
        self.issued();r=self.f.receipts[0];r['response']['commitment']['epoch']=2
        r['response']=self.f.anchor.sign(r['response'],0,__import__('atlasquant_aion_first_install_preparation_v4.signed_anchors',fromlist=['READ_DOMAIN']).READ_DOMAIN)
        self.f.receipts[0]=self.f.sign_receipt(r,0);self.blocked(self.f.admit())

    def test_local_causal_receipt_erasure_blocks_admission(self):
        self.issued()
        with closing(sqlite3.connect(self.f.anchor.ledger.path)) as db:
            db.execute('DELETE FROM receipts WHERE namespace="CONSUMPTION"');db.commit()
        self.blocked(self.f.admit());self.assertEqual(len(self.snapshot()['receipts']),0)

    def test_valid_signatures_cannot_override_floor_or_parent(self):
        from atlasquant_aion_first_install_preparation_v4.commitments import commitment_digest
        from atlasquant_aion_first_install_preparation_v4.signed_anchors import READ_DOMAIN
        for kind in ('lower','same_sequence_fork','wrong_parent','witness_fork'):
            with self.subTest(kind=kind):
                f=AdmissionFixture()
                try:
                    c=deepcopy(f.receipts[0]['response']['commitment'])
                    if kind=='lower':c['sequence']=0
                    elif kind=='same_sequence_fork':c['sequence']=f.anchor.floors[0]['sequence']
                    elif kind=='wrong_parent':c['previous_commitment_digest']='a'*64
                    else:c['state_digest']='a'*64
                    f.bindings[0]['expected_commitment_digest']=commitment_digest(c)
                    f.receipts[0]['response']['commitment']=c
                    f.receipts[0]['response']=f.anchor.sign(f.receipts[0]['response'],0,READ_DOMAIN)
                    f.receipts[0]['binding_digest']=digest(f.bindings[0]);f.receipts[0]=f.sign_receipt(f.receipts[0],0)
                    self.assertEqual(f.issue()['state'],'REFERENCE_DURABLE_ADMISSION_UNTRUSTED')
                    self.blocked(f.admit());self.assertEqual(len(f.store.read(f.retained)['snapshot']['receipts']),0)
                finally:f.close()

    def test_signed_duplicate_receipt_ids_never_admitted(self):
        self.issued();self.f.receipts[1]['receipt_id']=self.f.receipts[0]['receipt_id']
        self.f.receipts[1]=self.f.sign_receipt(self.f.receipts[1],1);self.blocked(self.f.admit())

    def test_expired_fixture_pin_and_forged_clock_provenance(self):
        self.issued();self.f.bindings[0]['query']['clock_provenance']='TRUSTED_CLOCK'
        self.blocked(self.f.admit())

    def test_receipt_ingress_duplicate_encoding_nonfinite_unknown_schema(self):
        import json
        from atlasquant_aion_first_install_preparation_v3.ledger_storage import canonical
        from atlasquant_aion_first_install_preparation_v5.receipt_ingress import decode_fixture_receipt
        raw=canonical(self.f.receipts[0]).encode('ascii');self.assertEqual(decode_fixture_receipt(raw),self.f.receipts[0])
        for value in (b'{"schema":"x","schema":"y"}',b'[]',b'NaN',b'\xff',b'x'*8193,
                      json.dumps(self.f.receipts[0],indent=2).encode(),raw.replace(b'Ed25519',b'RSA'),
                      raw.replace(b'fixture',b'\\u0066ixture',1)):
            with self.subTest(bytes=len(value)):
                with self.assertRaises(ValueError):decode_fixture_receipt(value)

    def test_next_fresh_receipt_links_existing_floor_and_previous_receipt(self):
        from atlasquant_aion_first_install_preparation_v4.commitments import commitment_digest
        self.issued();first=self.f.admit();s=first['snapshot']
        for i,b in enumerate(self.f.bindings):
            b['query']['nonce']=f'{i+500:064x}';b['attempt_id']='fixture-next-attempt';b['challenge']='fixture-next-challenge'
            floor=s['floors'][i];b['minimum_sequence']=floor['commitment']['sequence'];b['previous_receipt_digest']=floor['receipt_digest']
            b['expected_commitment_digest']=commitment_digest(floor['commitment'])
            r=dict(schema='AION_SIGNED_QUERY_RECEIPT_V5',algorithm='Ed25519',binding_digest=digest(b),
                receipt_id='fixture-next-receipt-'+str(i),response=self.f.anchor.response(i,b['query'],floor['commitment']))
            self.f.receipts[i]=self.f.sign_receipt(r,i)
        issue=self.f.store.issue(self.f.bindings,operation_id='fixture-next-issue',retained=first['retained_reference'],now=1000)
        self.assertEqual(issue['state'],'REFERENCE_DURABLE_ADMISSION_UNTRUSTED')
        second=self.f.store.admit(self.f.bindings,self.f.receipts,operation_id='fixture-next-admit',retained=issue['retained_reference'],
            now=1000,ledger_path=self.f.anchor.ledger.path,causal=self.f.anchor.causal)
        self.assertEqual(second['state'],'REFERENCE_DURABLE_ADMISSION_UNTRUSTED')
        self.assertEqual(len(second['snapshot']['receipts']),6)
        self.assertGreater(second['retained_reference']['sequence'],first['retained_reference']['sequence'])
        self.assertEqual(second['snapshot']['floors'][0]['previous_receipt_digest'],s['floors'][0]['receipt_digest'])

    def test_causal_expectation_cannot_be_removed_or_swapped(self):
        self.issued()
        for causal in (None,{'namespace':'CONSUMPTION','operation_id':'fixture-other','request_digest':'f'*64}):
            with self.subTest(causal=causal):
                out=self.f.store.admit(self.f.bindings,self.f.receipts,operation_id='fixture-admit',retained=self.f.retained,
                    now=1000,ledger_path=self.f.anchor.ledger.path,causal=causal)
                self.blocked(out)
        self.assertEqual(len(self.snapshot()['receipts']),0)

if __name__=='__main__':unittest.main()
