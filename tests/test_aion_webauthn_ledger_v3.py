from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
import json
import unittest
from cryptography.hazmat.primitives.asymmetric import ec
from atlasquant_aion_first_install_preparation.contracts import AUTHORITY_FIELDS,digest
from atlasquant_aion_first_install_preparation_v3.webauthn_ledger_reference import ReferenceWebAuthnLedger,attempt_binding
from atlasquant_aion_first_install_preparation_v3.ledger_storage import read_receipt_reference
from tests.aion_webauthn_ledger_fixtures_v3 import LedgerFixture

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.f=LedgerFixture();self.addCleanup(self.f.close)
        self.request=self.f.request_for();self.assertEqual(self.f.issue(self.request)['state'],'REFERENCE_DURABLE_RECEIPT_UNTRUSTED')
        self.packet=self.f.packet(self.request)

    def check(self,out):
        self.assertEqual(out['status'],'HARD_NO_GO')
        for k in AUTHORITY_FIELDS:self.assertIs(out[k],False,k)
        return out

    def confirm(self,*,request=None,packet=None,attempt='fixture-attempt',now=1000):
        return self.check(self.f.ledger.confirm_assertion_reference(request or self.request,
            self.packet if packet is None else packet,attempt_id=attempt,now=now))

    def test_consumption_and_counter_in_one_durable_boundary(self):
        out=self.confirm();self.assertEqual(out['state'],'REFERENCE_DURABLE_RECEIPT_UNTRUSTED')
        self.assertEqual(out['operation_kind'],'CONSUMPTION');self.assertFalse(out['cloning_absence_verified'])
        self.assertEqual(self.f.rows('challenges')[0]['state'],'CONSUMED')
        self.assertEqual(self.f.rows('credentials')[0]['sign_count'],2)
        self.assertEqual(self.f.rows('attempts')[0]['consumed_counter'],2)

    def test_invalid_signature_no_consumption_no_admission(self):
        packet=deepcopy(self.packet);packet['signature']=self.f.packet(self.request,key=ec.generate_private_key(ec.SECP256R1()))['signature']
        self.assertEqual(self.confirm(packet=packet)['state'],'BLOCKED')
        self.assertEqual(self.f.rows('challenges')[0]['state'],'ISSUED');self.assertEqual(self.f.rows('attempts'),[])

    def test_restart_and_expiration_never_reactivate(self):
        self.confirm();self.f.ledger=ReferenceWebAuthnLedger(self.f.path,scope=self.f.scope)
        for now in [1000,1100,1200]:
            with self.subTest(now=now):self.assertEqual(self.confirm(attempt='fixture-repeat-'+str(now),now=now)['state'],'BLOCKED')
        self.assertEqual(self.f.issue(self.request,index=10)['state'],'BLOCKED')
        self.assertEqual(len(self.f.rows('attempts')),1)

    def test_reused_nonce_or_request_id_changed_payload_cannot_issue(self):
        second=self.f.request_for(2)
        for field in ['nonce','request_id']:
            with self.subTest(field=field):
                changed=deepcopy(second);changed[field]=self.request[field]
                self.assertEqual(self.f.issue(changed,index=2)['state'],'BLOCKED')
        self.assertEqual(len(self.f.rows('challenges')),1)

    def test_same_attempt_different_payload_rejected_and_readback_bound(self):
        self.confirm();changed=self.f.packet(self.request,count=3)
        self.assertEqual(self.confirm(packet=changed)['state'],'BLOCKED')
        bound=attempt_binding(self.request,changed)[1]
        self.assertEqual(self.f.ledger.reconcile_attempt_reference(attempt_id='fixture-attempt',expected_request_digest=bound['request_digest'],minimum_sequence=0)['state'],'BLOCKED')

    def test_wrong_owner_tenant_workspace_device_operation(self):
        for field,value in [('owner_id','fixture-other'),('tenant_id','fixture-other'),('workspace_id','fixture-other'),('device_id','fixture-other'),('credential_id','fixture-other'),('operation','INSTALL'),('artifact_sha256','c'*64)]:
            with self.subTest(field=field):
                changed=deepcopy(self.request);changed['binding'][field]=value
                self.assertEqual(self.confirm(request=changed)['state'],'BLOCKED')
        self.assertEqual(self.f.rows('attempts'),[])

    def test_signed_wrong_rp_origin_challenge_and_duplicates(self):
        client=json.loads(self.packet['client_data_json'])
        for field,value in [('type','webauthn.create'),('challenge','x'*43),('origin','https://other.invalid'),('crossOrigin',True)]:
            with self.subTest(field=field):
                bad=dict(client);bad[field]=value
                p=self.f.packet(self.request,raw=json.dumps(bad).encode());self.assertEqual(self.confirm(packet=p)['state'],'BLOCKED')
        for raw in [b'{',b'\xff',b'[]',b'{"type":"webauthn.get","type":"webauthn.get"}',b'x'*4097]:
            with self.subTest(size=len(raw)):
                self.assertEqual(self.confirm(packet=self.f.packet(self.request,raw=raw))['state'],'BLOCKED')
        auth=sha256(b'other.invalid').digest()+bytes([5])+b'\0\0\0\2'
        self.assertEqual(self.confirm(packet=self.f.packet(self.request,auth=auth))['state'],'BLOCKED')
        self.assertEqual(self.f.rows('attempts'),[])

    def test_known_monotonic_counter_repetition_blocked(self):
        self.confirm();new=self.f.request_for(2);self.f.issue(new,index=2)
        self.assertEqual(self.confirm(request=new,packet=self.f.packet(new,count=2),attempt='fixture-second')['state'],'BLOCKED')
        self.assertEqual(self.confirm(request=new,packet=self.f.packet(new,count=3),attempt='fixture-second')['state'],'REFERENCE_DURABLE_RECEIPT_UNTRUSTED')

    def test_unexpected_flags_and_counter_zero_after_increment(self):
        for flags,count in [(1,2),(4,2),(0x0d,2),(0x15,2),(0x85,2),(5,0)]:
            with self.subTest(flags=flags,count=count):
                self.assertEqual(self.confirm(packet=self.f.packet(self.request,flags=flags,count=count))['state'],'BLOCKED')

    def test_two_threads_same_challenge_single_effect(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            out=list(pool.map(lambda i:self.f.ledger.confirm_assertion_reference(self.request,self.packet,attempt_id='fixture-thread-'+str(i),now=1000),range(2)))
        self.assertEqual(sum(x['state']=='REFERENCE_DURABLE_RECEIPT_UNTRUSTED' for x in out),1)
        self.assertEqual(len(self.f.rows('attempts')),1)
        for x in out:self.check(x)

    def test_two_operations_same_counter_single_update(self):
        second=self.f.request_for(2);self.f.issue(second,index=2);packet2=self.f.packet(second)
        def run(pair):
            req,packet,ident=pair
            return self.f.ledger.confirm_assertion_reference(req,packet,attempt_id=ident,now=1000)
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(run,[(self.request,self.packet,'fixture-first'),(second,packet2,'fixture-second')]))
        self.assertEqual(sum(x['state']=='REFERENCE_DURABLE_RECEIPT_UNTRUSTED' for x in outcomes),1)
        self.assertEqual(self.f.rows('credentials')[0]['sign_count'],2)
        self.assertEqual(sum(r['state']=='CONSUMED' for r in self.f.rows('challenges')),1)

    def test_unknown_credential_and_wrong_ledger_scope(self):
        bad=self.f.request_for(3);bad['binding']['credential_id']='fixture-unknown'
        self.assertEqual(self.f.issue(bad,index=3)['state'],'BLOCKED')
        bound=attempt_binding(self.request,self.packet)[1]
        out=read_receipt_reference(self.f.path,scope={**self.f.scope,'tenant_id':'fixture-other'},namespace='CONSUMPTION',operation_id='fixture-attempt',expected_request_digest=bound['request_digest'],minimum_sequence=0)
        self.assertEqual(out['state'],'BLOCKED')

    def test_administrative_claims_do_not_register_owner(self):
        for role in ['ADMIN','HUMAN_OWNER','OWNER']:
            with self.subTest(role=role):
                cred=dict(self.f.credential);cred['role']=role
                self.assertEqual(self.f.ledger.register_credential_reference(self.request['binding'],cred,operation_id='fixture-spoof')['state'],'BLOCKED')
        self.confirm()
        from atlasquant_aion_first_install_preparation.contracts import production_authority
        self.check(production_authority(self.f.rows('attempts')))

if __name__=='__main__':unittest.main()
