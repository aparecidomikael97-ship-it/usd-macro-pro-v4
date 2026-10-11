from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import unittest
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric import ec
from fido2 import cbor
from atlasquant_aion_first_install_preparation.contracts import AUTHORITY_FIELDS
from atlasquant_aion_first_install_preparation_v3.webauthn_ledger_reference import ReferenceWebAuthnLedger
from tests.aion_webauthn_ledger_fixtures_v3 import LedgerFixture

class CredentialRegistryTests(unittest.TestCase):
    def setUp(self):self.f=LedgerFixture();self.addCleanup(self.f.close)
    def rotate(self,**kw):
        self.newkey=ec.generate_private_key(ec.SECP256R1())
        self.newcred=self.f.make_credential(self.newkey,generation=2)
        options=dict(operation_id='fixture-rotation',expected_generation=1,
            expected_key_sha256=sha256(self.f.credential['public_key_cose']).hexdigest(),decision='SIMULATE_ROTATION_ONLY')
        options.update(kw)
        return self.f.ledger.rotate_credential_reference(self.f.request['binding'],self.newcred,**options)

    def test_monotonic_rotation_retains_history(self):
        self.assertEqual(self.rotate()['state'],'REFERENCE_DURABLE_RECEIPT_UNTRUSTED')
        rows=self.f.rows('credentials');self.assertEqual([r['generation'] for r in rows],[1,2])
        self.assertEqual([r['state'] for r in rows],['RETIRED','ACTIVE'])
        request=self.f.request_for();self.f.issue(request,generation=2)
        packet=self.f.packet(request,key=self.newkey)
        out=self.f.ledger.confirm_assertion_reference(request,packet,attempt_id='fixture-new-key',now=1000)
        self.assertEqual(out['state'],'REFERENCE_DURABLE_RECEIPT_UNTRUSTED')
        for k in AUTHORITY_FIELDS:self.assertIs(out[k],False)

    def test_old_challenge_and_key_after_rotation_blocked(self):
        request=self.f.request_for();self.f.issue(request);packet=self.f.packet(request)
        self.rotate()
        self.assertEqual(self.f.ledger.confirm_assertion_reference(request,packet,attempt_id='fixture-old',now=1000)['state'],'BLOCKED')
        self.assertEqual(self.f.issue(self.f.request_for(2),index=2,generation=1)['state'],'BLOCKED')
        self.f.issue(self.f.request_for(3),index=3,generation=2)
        self.assertEqual(self.f.ledger.confirm_assertion_reference(self.f.request_for(3),self.f.packet(self.f.request_for(3)),attempt_id='fixture-old-key',now=1000)['state'],'BLOCKED')

    def test_rotation_wrong_pin_generation_authority(self):
        for override in [dict(expected_key_sha256='f'*64),dict(expected_generation=2),dict(expected_generation=True),dict(decision='HUMAN_OWNER'),dict(decision='APPROVED')]:
            with self.subTest(override=list(override)):
                self.assertEqual(self.rotate(**override)['state'],'BLOCKED');self.assertEqual(len(self.f.rows('credentials')),1)

    def test_key_replacement_register_and_same_key_rotation_blocked(self):
        key=ec.generate_private_key(ec.SECP256R1());new=self.f.make_credential(key,generation=1)
        self.assertEqual(self.f.ledger.register_credential_reference(self.f.request['binding'],new,operation_id='fixture-replace')['state'],'BLOCKED')
        same=dict(self.f.credential);same['generation']=2
        self.assertEqual(self.f.ledger.rotate_credential_reference(self.f.request['binding'],same,operation_id='fixture-same-key',expected_generation=1,expected_key_sha256=sha256(self.f.credential['public_key_cose']).hexdigest(),decision='SIMULATE_ROTATION_ONLY')['state'],'BLOCKED')

    def test_revocation_restart_and_no_reenable(self):
        cid=self.f.credential['credential_id'];pin=sha256(self.f.credential['public_key_cose']).hexdigest()
        out=self.f.ledger.revoke_credential_reference(cid,generation=1,expected_key_sha256=pin,operation_id='fixture-revoke')
        self.assertEqual(out['state'],'REFERENCE_DURABLE_RECEIPT_UNTRUSTED')
        self.f.ledger=ReferenceWebAuthnLedger(self.f.path,scope=self.f.scope)
        self.assertEqual(self.f.issue(self.f.request_for())['state'],'BLOCKED')
        self.assertEqual(self.f.ledger.register_credential_reference(self.f.request['binding'],self.f.credential,operation_id='fixture-reenable')['state'],'BLOCKED')
        self.assertEqual(self.rotate()['state'],'REFERENCE_DURABLE_RECEIPT_UNTRUSTED')
        self.assertEqual([r['state'] for r in self.f.rows('credentials')],['REVOKED','ACTIVE'])

    def test_wrong_tenant_registration_and_unknown_revocation(self):
        bind=deepcopy(self.f.request['binding']);bind['tenant_id']='fixture-other'
        self.assertEqual(self.f.ledger.register_credential_reference(bind,self.f.credential,operation_id='fixture-other')['state'],'BLOCKED')
        self.assertEqual(self.f.ledger.revoke_credential_reference('fixture-unknown',generation=1,expected_key_sha256='a'*64,operation_id='fixture-revoke')['state'],'BLOCKED')

    def test_recheck_rotation_between_admission_and_consumption(self):
        request=self.f.request_for();self.f.issue(request);packet=self.f.packet(request)
        original=self.f.ledger._committed
        def committed(namespace,*args):
            out=original(namespace,*args)
            if namespace=='ADMISSION':self.assertEqual(self.rotate()['state'],'REFERENCE_DURABLE_RECEIPT_UNTRUSTED')
            return out
        with patch.object(self.f.ledger,'_committed',side_effect=committed):
            out=self.f.ledger.confirm_assertion_reference(request,packet,attempt_id='fixture-race',now=1000)
        self.assertEqual(out['state'],'BLOCKED')
        self.assertEqual(self.f.rows('challenges')[0]['state'],'QUARANTINED')
        self.assertEqual(self.f.rows('credentials')[0]['sign_count'],1)

    def test_recheck_revocation_between_admission_and_consumption(self):
        request=self.f.request_for();self.f.issue(request);packet=self.f.packet(request)
        original=self.f.ledger._committed
        def committed(namespace,*args):
            out=original(namespace,*args)
            if namespace=='ADMISSION':
                self.f.ledger.revoke_credential_reference('fixture-credential',generation=1,expected_key_sha256=sha256(self.f.credential['public_key_cose']).hexdigest(),operation_id='fixture-revoke')
            return out
        with patch.object(self.f.ledger,'_committed',side_effect=committed):
            self.assertEqual(self.f.ledger.confirm_assertion_reference(request,packet,attempt_id='fixture-race',now=1000)['state'],'BLOCKED')
        self.assertEqual(self.f.rows('attempts')[0]['state'],'QUARANTINED')

    def test_synced_zero_be_bs_do_not_establish_no_cloning(self):
        key=ec.generate_private_key(ec.SECP256R1());cred=self.f.make_credential(key,generation=2,backup=True,count=0)
        self.f.ledger.rotate_credential_reference(self.f.request['binding'],cred,operation_id='fixture-sync-rotate',expected_generation=1,expected_key_sha256=sha256(self.f.credential['public_key_cose']).hexdigest(),decision='SIMULATE_ROTATION_ONLY')
        for index,flags in [(1,0x0d),(2,0x1d),(3,0x0d)]:
            with self.subTest(flags=flags):
                request=self.f.request_for(index);self.f.issue(request,index=index,generation=2)
                out=self.f.ledger.confirm_assertion_reference(request,self.f.packet(request,key=key,count=0,flags=flags),attempt_id='fixture-sync-'+str(index),now=1000)
                self.assertEqual(out['state'],'REFERENCE_DURABLE_RECEIPT_UNTRUSTED');self.assertFalse(out['cloning_absence_verified'])
                self.assertEqual(out['counter_assurance'],'NONE_FOR_ZERO')
        row=self.f.rows('credentials')[-1];self.assertEqual(row['sign_count'],0);self.assertEqual(row['backup_state'],0)

    def test_malformed_cose_and_private_fields_cannot_register(self):
        original=cbor.decode(self.f.credential['public_key_cose'])
        for k,v in [(3,-8),(-1,2),(-4,b'x'*32),(-2,b'x')]:
            with self.subTest(field=k):
                changed=dict(original);changed[k]=v;cred=dict(self.f.credential);cred['public_key_cose']=cbor.encode(changed)
                self.assertEqual(self.f.ledger.register_credential_reference(self.f.request['binding'],cred,operation_id='fixture-cose')['state'],'BLOCKED')
        cred=dict(self.f.credential);cred['pin']='SECRET_SENTINEL'
        out=self.f.ledger.register_credential_reference(self.f.request['binding'],cred,operation_id='fixture-private')
        self.assertEqual(out['state'],'BLOCKED');self.assertNotIn('SECRET_SENTINEL',str(out))

    def test_competing_rotations_single_generation_winner(self):
        candidates=[self.f.make_credential(ec.generate_private_key(ec.SECP256R1()),generation=2) for _ in range(2)]
        def rotate(pair):
            index,cred=pair
            return self.f.ledger.rotate_credential_reference(self.f.request['binding'],cred,operation_id='fixture-rotation-'+str(index),expected_generation=1,expected_key_sha256=sha256(self.f.credential['public_key_cose']).hexdigest(),decision='SIMULATE_ROTATION_ONLY')
        with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(rotate,enumerate(candidates)))
        self.assertEqual(sum(x['state']=='REFERENCE_DURABLE_RECEIPT_UNTRUSTED' for x in out),1)
        self.assertEqual([r['generation'] for r in self.f.rows('credentials')],[1,2])

    def test_revoke_consume_race_consume_never_after_revocation(self):
        request=self.f.request_for();self.f.issue(request);packet=self.f.packet(request)
        def run(index):
            if index==0:return self.f.ledger.confirm_assertion_reference(request,packet,attempt_id='fixture-race',now=1000)
            return self.f.ledger.revoke_credential_reference('fixture-credential',generation=1,expected_key_sha256=sha256(self.f.credential['public_key_cose']).hexdigest(),operation_id='fixture-race-revoke')
        with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(run,range(2)))
        self.assertEqual(self.f.rows('credentials')[0]['state'],'REVOKED')
        receipts=self.f.rows('receipts');revoked=next(r['sequence'] for r in receipts if r['namespace']=='REVOKE')
        consumed=[r['sequence'] for r in receipts if r['namespace']=='CONSUMPTION']
        if consumed:self.assertLess(consumed[0],revoked)
        for out in outcomes:
            for k in AUTHORITY_FIELDS:self.assertIs(out[k],False)

if __name__=='__main__':unittest.main()
