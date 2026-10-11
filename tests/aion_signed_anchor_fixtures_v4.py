"""Public disposable anchor fixtures. PRIVATE Ed25519 keys stay in test memory."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from atlasquant_aion_runtime_source_boundary_ref_v1 import canonical_bytes
from atlasquant_aion_first_install_preparation_v3.ledger_storage import ZERO
from atlasquant_aion_first_install_preparation_v3.webauthn_ledger_reference import attempt_binding
from atlasquant_aion_first_install_preparation_v4.commitments import capture_ledger_reference,commitment_digest
from atlasquant_aion_first_install_preparation_v4.signed_anchors import ANCHOR_DOMAIN,READ_DOMAIN,pin_digest
from tests.aion_webauthn_ledger_fixtures_v3 import LedgerFixture

class AnchorFixture:
    def __init__(self):
        self.ledger=LedgerFixture();self.config={**self.ledger.scope,'ledger_id':'fixture-ledger',
            'epoch':1,'policy_id':'fixture-anchor-policy','policy_version':1,'witness_id':'fixture-witness-0'}
        self.keys=[Ed25519PrivateKey.generate() for _ in range(3)]
        self.pins=[]
        for i,key in enumerate(self.keys):
            raw=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
            self.pins.append(dict(schema='AION_WEBAUTHN_FIXTURE_PIN_V4',mode='FIXTURE_UNENROLLED',
                **self.ledger.scope,ledger_id='fixture-ledger',witness_id='fixture-witness-'+str(i),
                operator_alias='fixture-operator-'+str(i),administrative_domain_alias='fixture-admin-'+str(i),
                key_id='fixture-witness-key-'+str(i),key_generation=1,public_key_hex=raw.hex(),algorithm='Ed25519',
                policy_id='fixture-anchor-policy',policy_version=1,root_provenance_digest='f'*64,
                revocation='SIMULATED_NOT_REVOKED',expires_at=1100))
        self.floors=[self.capture(i,ZERO) for i in range(3)]
        self.request=self.ledger.request_for();self.packet=self.ledger.packet(self.request)
        self.causal=dict(namespace='CONSUMPTION',operation_id='fixture-attempt',request_digest=attempt_binding(self.request,self.packet)[1]['request_digest'])

    def close(self):self.ledger.close()
    def cfg(self,i):return {**self.config,'witness_id':self.pins[i]['witness_id']}
    def capture(self,i,previous,*,path=None):
        out=capture_ledger_reference(path or self.ledger.path,config=self.cfg(i),previous_commitment_digest=previous)
        if out['state']!='REFERENCE_SNAPSHOT_UNTRUSTED':raise AssertionError(out)
        return out['commitment']
    def consume(self):
        self.ledger.issue(self.request)
        return self.ledger.ledger.confirm_assertion_reference(self.request,self.packet,attempt_id='fixture-attempt',now=1000)
    def sign(self,record,index,domain):
        record=deepcopy(record);record['signature']=self.keys[index].sign(canonical_bytes(record,domain=domain)).hex();return record
    def anchor(self,index,commitment=None):
        commitment=commitment or self.capture(index,commitment_digest(self.floors[index]))
        return self.sign(dict(schema='AION_WEBAUTHN_SIGNED_ANCHOR_V4',algorithm='Ed25519',key_id=self.pins[index]['key_id'],
            key_generation=1,commitment=commitment),index,ANCHOR_DOMAIN)
    def query(self,index,*,nonce=None):
        p=self.pins[index]
        return dict(schema='AION_WEBAUTHN_FRESH_READ_QUERY_V4',**self.ledger.scope,ledger_id=p['ledger_id'],
            witness_id=p['witness_id'],policy_id=p['policy_id'],policy_version=1,minimum_epoch=1,
            key_id=p['key_id'],key_generation=1,root_provenance_digest=p['root_provenance_digest'],
            nonce=nonce or f'{index+100:064x}',issued_at=1000,expires_at=1050,clock_provenance='FIXTURE_CLOCK')
    def response(self,index,query,commitment=None):
        commitment=commitment or self.capture(index,commitment_digest(self.floors[index]))
        return self.sign(dict(schema='AION_WEBAUTHN_FRESH_READ_RESPONSE_V4',algorithm='Ed25519',
            **{k:query[k] for k in ('key_id','key_generation','witness_id','nonce','issued_at','expires_at',
                'root_provenance_digest','clock_provenance')},commitment=commitment),index,READ_DOMAIN)
    def members(self):
        out=[]
        for i,pin in enumerate(self.pins):
            q=self.query(i)
            out.append(dict(pin=deepcopy(pin),expected_pin_digest=pin_digest(pin),query=q,response=self.response(i,q),
                floor=deepcopy(self.floors[i]),consumed_nonces=[]))
        return out
    def public_files(self,members):
        paths=[]
        for i,member in enumerate(members):
            p=Path(self.ledger.tmp.name)/('public-witness-'+str(i)+'.json')
            p.write_text(json.dumps(member['response']),encoding='utf-8');paths.append(p)
        return paths
