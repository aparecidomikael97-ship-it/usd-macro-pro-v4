import base64
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import unittest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from fido2 import cbor
from fido2.cose import ES256
from atlasquant_aion_first_install_preparation.contracts import AUTHORITY_FIELDS, digest
from atlasquant_aion_first_install_preparation_v2.webauthn_reference import (
    challenge_for, verify_assertion_reference, verify_signature_reference)
from tests.test_aion_first_install_preparation_v1 import intent, scope

class WebAuthnReferenceTests(unittest.TestCase):
    def setUp(self):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.request = intent()
        self.cose = cbor.encode(ES256.from_cryptography_key(self.key.public_key()))
        self.credential = dict(schema="AION_WEBAUTHN_DISPOSABLE_CREDENTIAL_V2",role="OWNER_CEREMONY_FIXTURE",
            scope_digest=digest(scope()),credential_id=scope()["credential_id"],public_key_cose=self.cose,
            generation=3,backup_eligible=False,stored_sign_count=1,expires_at=1100)
        self.client = dict(type="webauthn.get",challenge=challenge_for(self.request),origin="https://offline-fixture.invalid")
        self.packet = self.sign()
        self.options = dict(expected_binding=scope(),expected_public_key_sha256=sha256(self.cose).hexdigest(),
            expected_generation=3,rp_id="offline-fixture.invalid",origin="https://offline-fixture.invalid",now=1000,
            revoked_credentials=[],consumed_challenges=[])

    def sign(self, *, raw=None, auth=None):
        raw = json.dumps(self.client,separators=(",",":")).encode() if raw is None else raw
        auth = sha256(b"offline-fixture.invalid").digest()+bytes([5])+(2).to_bytes(4,"big") if auth is None else auth
        return dict(client_data_json=raw,authenticator_data=auth,
            signature=self.key.sign(auth+sha256(raw).digest(),ec.ECDSA(hashes.SHA256())),credential_id=scope()["credential_id"])

    def review(self):
        out=verify_assertion_reference(self.request,self.packet,self.credential,**self.options)
        self.assertEqual(out["status"],"HARD_NO_GO")
        for key in AUTHORITY_FIELDS:self.assertIs(out[key],False)
        return out

    def blocked(self):self.assertEqual(self.review()["state"],"BLOCKED")

    def test_positive_real_signature_no_authority(self):
        self.assertTrue(self.review()["cryptographic_signature_valid"])

    def test_public_yubico_vector(self):
        p=Path(__file__).parent/'fixtures'/'aion_webauthn_yubico_es256_v2.json'
        vector=json.loads(p.read_text(encoding='utf-8'))
        out=verify_signature_reference(*(bytes.fromhex(vector[k]) for k in ('public_key_cose','message','signature')))
        self.assertTrue(out['cryptographic_signature_valid'])
        for k in AUTHORITY_FIELDS:self.assertIs(out[k],False)
        payload={k:vector[k] for k in ('public_key_cose','message','signature')}
        self.assertEqual(sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest(),vector['vector_sha256'])

    def test_signed_wrong_client_fields(self):
        for field,value in [('type','webauthn.create'),('challenge','x'*43),('origin','https://other.invalid'),('crossOrigin',True),('topOrigin','https://offline-fixture.invalid')]:
            with self.subTest(field=field):
                old=deepcopy(self.client);self.client[field]=value;self.packet=self.sign();self.blocked();self.client=old

    def test_signed_malformed_json(self):
        for raw in [b'{',b'[]',b'null',b'\xff',b'{"type":"webauthn.get","type":"webauthn.get"}',b'{"x":NaN}',b'['*2000+b']'*2000,b' '*4097]:
            with self.subTest(length=len(raw)):
                self.packet=self.sign(raw=raw);self.blocked()

    def test_signed_flags(self):
        for flags in [0,1,4,7,0x45,0x85,0x15,0x25,0x0d]:
            with self.subTest(flags=flags):
                self.packet=self.sign(auth=sha256(b'offline-fixture.invalid').digest()+bytes([flags])+b'\0\0\0\2');self.blocked()

    def test_zero_counter_synced_is_no_assurance(self):
        self.credential.update(backup_eligible=True,stored_sign_count=0)
        self.packet=self.sign(auth=sha256(b'offline-fixture.invalid').digest()+bytes([0x1d])+b'\0'*4)
        self.assertEqual(self.review()['counter_assurance'],'NONE')
        self.options['consumed_challenges']=[challenge_for(self.request)];self.blocked()

    def test_counter_nonincrease_and_overflow(self):
        for count in [0,1]:
            with self.subTest(count=count):
                self.packet=self.sign(auth=sha256(b'offline-fixture.invalid').digest()+bytes([5])+count.to_bytes(4,'big'));self.blocked()
        self.credential['stored_sign_count']=True;self.blocked()

    def test_scope_operation_after_consent(self):
        for field in ['owner_id','tenant_id','workspace_id','device_id','credential_id','operation','artifact_sha256']:
            with self.subTest(field=field):
                old=deepcopy(self.request);self.request['binding'][field]='INSTALL' if field=='operation' else 'f'*64 if field=='artifact_sha256' else 'other';self.blocked();self.request=old

    def test_request_changed_even_same_scope(self):
        for field,value in [('request_id','other'),('nonce','c'*64),('expires_at',1099)]:
            with self.subTest(field=field):
                old=deepcopy(self.request);self.request[field]=value;self.blocked();self.request=old

    def test_revocation_expiry_replay_unknown(self):
        for field,value in [('now',1100),('now',989),('now',True),('revoked_credentials',None),('revoked_credentials',[scope()['credential_id']]),('consumed_challenges',None),('consumed_challenges',[challenge_for(self.request)])]:
            with self.subTest(field=field):
                old=deepcopy(self.options);self.options[field]=value;self.blocked();self.options=old

    def test_admin_unregistered_rotated(self):
        for field,value in [('role','ADMIN'),('credential_id','other-tenant'),('generation',4),('generation',True),('expires_at',999),('scope_digest','f'*64)]:
            with self.subTest(field=field):
                old=deepcopy(self.credential);self.credential[field]=value;self.blocked();self.credential=old

    def test_cose_private_duplicate_curve_alg(self):
        original=cbor.decode(self.cose)
        for field,value in [(-4,b'x'*32),(3,-8),(-1,2),(-2,b'x'),(1,True)]:
            with self.subTest(field=field):
                key=dict(original);key[field]=value;self.credential['public_key_cose']=cbor.encode(key)
                self.options['expected_public_key_sha256']=sha256(self.credential['public_key_cose']).hexdigest();self.blocked()
        for raw in [b'\xa6'+self.cose[1:]+b'\x01\x02',self.cose+b'\0',b'\xff',b'x'*257]:
            with self.subTest(raw_length=len(raw)):
                self.credential['public_key_cose']=raw;self.options['expected_public_key_sha256']=sha256(raw).hexdigest();self.blocked()

    def test_signature_key_pin_and_auth_bounds(self):
        self.options['expected_public_key_sha256']='f'*64;self.blocked()
        self.options['expected_public_key_sha256']=sha256(self.cose).hexdigest()
        for field,value in [('signature',b'bad'),('signature',b'x'*81),('authenticator_data',b'x'*38),('authenticator_data',b'x'*37),('client_data_json','text')]:
            with self.subTest(field=field):
                self.packet=self.sign();self.packet[field]=value;self.blocked()

    def test_real_rp_and_unknown_fields_refused(self):
        self.options['rp_id']='real.example';self.blocked()
        self.options['rp_id']='offline-fixture.invalid';self.packet['installation_authorized']=True;self.blocked()

if __name__=='__main__':unittest.main()
