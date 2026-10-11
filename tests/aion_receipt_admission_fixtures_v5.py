"""Synthetic public fixture documents; secret keys exist in test memory only."""
from copy import deepcopy
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from atlasquant_aion_runtime_source_boundary_ref_v1 import canonical_bytes
from atlasquant_aion_first_install_preparation_v3.ledger_storage import ZERO
from atlasquant_aion_first_install_preparation_v4.commitments import commitment_digest
from atlasquant_aion_first_install_preparation_v4.signed_anchors import pin_digest
from atlasquant_aion_first_install_preparation_v5.contracts import READ_DOMAIN,CONTROL_DOMAIN,PROOFS,digest
from atlasquant_aion_first_install_preparation_v5.admission import ReferenceReceiptAdmission
from tests.aion_signed_anchor_fixtures_v4 import AnchorFixture

class AdmissionFixture:
    def __init__(self):
        self.anchor=AnchorFixture();self.root_key=Ed25519PrivateKey.generate()
        self.path=Path(self.anchor.ledger.tmp.name)/'fixture-admission.db'
        public=self.root_key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex()
        self.config=dict(config=deepcopy(self.anchor.config),root=dict(root_id='fixture-root',generation=1,
            public_key_hex=public,provenance='FIXTURE_UNENROLLED'),members=[dict(pin=deepcopy(p),
            expected_pin_digest=pin_digest(p),floor=deepcopy(f)) for p,f in zip(self.anchor.pins,self.anchor.floors)],
            required_proofs=deepcopy(PROOFS))
        self.store=ReferenceReceiptAdmission(self.path,config=self.config,expected_config_digest=digest(self.config))
        self.retained=dict(sequence=0,head=ZERO,config_digest=digest(self.config))
        self.anchor.consume();self.bindings=[];self.receipts=[]
        for i in range(3):
            q=self.anchor.query(i);c=self.anchor.capture(i,commitment_digest(self.anchor.floors[i]))
            b=dict(query=q,root_id='fixture-root',root_generation=1,expected_pin_digest=pin_digest(self.anchor.pins[i]),
                minimum_sequence=self.anchor.floors[i]['sequence'],challenge='fixture-read-challenge',operation='fixture-causal-read',
                attempt_id='fixture-read-attempt',expected_commitment_digest=commitment_digest(c),
                previous_receipt_digest=ZERO,revocation_head=ZERO,causal=deepcopy(self.anchor.causal))
            self.bindings.append(b)
            r=dict(schema='AION_SIGNED_QUERY_RECEIPT_V5',algorithm='Ed25519',binding_digest=digest(b),
                receipt_id='fixture-read-receipt-'+str(i),response=self.anchor.response(i,q,c))
            self.receipts.append(self.sign_receipt(r,i))
    def sign_receipt(self,r,i):
        r=deepcopy(r);r['signature']=self.anchor.keys[i].sign(canonical_bytes(r,domain=READ_DOMAIN)).hex();return r
    def close(self):self.anchor.close()
    def issue(self):
        return self.store.issue(self.bindings,operation_id='fixture-issue',retained=self.retained,now=1000)
    def admit(self,**kwargs):
        return self.store.admit(self.bindings,self.receipts,operation_id='fixture-admit',retained=self.retained,
            now=1000,ledger_path=self.anchor.ledger.path,causal=self.anchor.causal,**kwargs)
    def control_event(self,kind='EPOCH_NEXT',event_id='fixture-control',new_key=None):
        snapshot=self.store.read(self.retained);head=snapshot['retained_reference'];old=snapshot['snapshot']['floors'][0]['commitment']
        new=deepcopy(old)
        if kind=='EPOCH_NEXT':new['epoch']+=1
        root=None
        if new_key is not None:
            public=new_key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex()
            root=dict(root_id='fixture-root-next',generation=2,public_key_hex=public,provenance='FIXTURE_UNENROLLED')
        e=dict(schema='AION_CONTROL_CANDIDATE_V5',algorithm='Ed25519',event_id=event_id,kind=kind,
            scope={k:self.config['config'][k] for k in ('owner_id','tenant_id','workspace_id','ledger_id')},
            root_id='fixture-root',root_generation=1,emitter='fixture-root',affected_object='fixture-root',epoch=1,
            proposed_epoch=2 if kind=='EPOCH_NEXT' else 1,causal_sequence=head['sequence'],previous_commitment=deepcopy(old),
            initial_commitment=new,reason='fixture-laboratory-only',new_root=root,proposed_identity=None,required_proofs=deepcopy(PROOFS))
        if kind in ('WITNESS_REPLACEMENT','ADMIN_TRANSFER'):
            e['proposed_identity']=dict(witness_id='fixture-replacement-witness',key_id='fixture-replacement-key',
                operator_alias='fixture-replacement-operator',administrative_domain_alias='fixture-replacement-domain',
                public_key_hex=self.config['members'][0]['pin']['public_key_hex'],generation=2)
        e['owner_approval']=dict(state='SIMULATED_ONLY',event_digest=digest(e))
        return self.sign_control(e,new_key)
    def sign_control(self,e,new_key=None):
        e=deepcopy(e)
        unsigned={k:v for k,v in e.items() if k not in ('signature','new_signature')}
        e['signature']=self.root_key.sign(canonical_bytes(unsigned,domain=CONTROL_DOMAIN)).hex()
        e['new_signature']=None if new_key is None else new_key.sign(canonical_bytes(unsigned,domain=CONTROL_DOMAIN)).hex()
        return e

CHILD=r'''
import json,sys,os,sqlite3
from atlasquant_aion_first_install_preparation_v5.admission import ReferenceReceiptAdmission
from atlasquant_aion_first_install_preparation_v5.contracts import digest
x=json.load(open(sys.argv[1],encoding='utf-8'));s=ReferenceReceiptAdmission(x['path'],config=x['config'],expected_config_digest=digest(x['config']),timeout=1)
if sys.argv[2]=='control':
 print(json.dumps(s.control(x['event'],retained=x['retained'])));sys.exit(0)
if sys.argv[2]=='crash':
 original=s.connect
 class Fault:
  def __init__(self,c):self.c=c
  def __getattr__(self,n):return getattr(self.c,n)
  def commit(self):
   self.c.commit()
   if self.c.execute("SELECT 1 FROM journal WHERE operation_id='fixture-admit'").fetchone():os._exit(23)
 def connect(**kw):
  c=original(**kw);return c if kw.get('read_only') else Fault(c)
 s.connect=connect
out=s.admit(x['bindings'],x['receipts'],operation_id='fixture-admit',retained=x['retained'],now=1000,ledger_path=x['ledger_path'],causal=x['causal'])
print(json.dumps(out))
'''
