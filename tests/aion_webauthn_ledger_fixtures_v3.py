"""Disposable in-memory private keys. Files contain PUBLIC fixtures only."""
from copy import deepcopy
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fido2 import cbor
from fido2.cose import ES256
from atlasquant_aion_first_install_preparation.contracts import digest
from atlasquant_aion_first_install_preparation_v2.webauthn_reference import challenge_for
from atlasquant_aion_first_install_preparation_v3.webauthn_ledger_reference import ReferenceWebAuthnLedger,attempt_binding
from tests.test_aion_first_install_preparation_v1 import intent

class LedgerFixture:
    def __init__(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'fixture-ledger.db'
        self.scope=dict(owner_id='fixture-owner',tenant_id='fixture-tenant',workspace_id='fixture-workspace')
        self.request=intent();self.request['binding'].update(self.scope,device_id='fixture-device',credential_id='fixture-credential')
        self.key=ec.generate_private_key(ec.SECP256R1())
        self.credential=self.make_credential(self.key,generation=1)
        self.ledger=ReferenceWebAuthnLedger(self.path,scope=self.scope,timeout=0.05)
        self.registration=self.ledger.register_credential_reference(self.request['binding'],self.credential,operation_id='fixture-registration')

    def close(self):self.tmp.cleanup()

    def make_credential(self,key,*,generation,backup=False,count=1):
        return dict(schema='AION_WEBAUTHN_DISPOSABLE_CREDENTIAL_V2',role='OWNER_CEREMONY_FIXTURE',
            scope_digest=digest(self.request['binding']),credential_id='fixture-credential',
            public_key_cose=cbor.encode(ES256.from_cryptography_key(key.public_key())),generation=generation,
            backup_eligible=backup,stored_sign_count=count,expires_at=1200)

    def request_for(self,index=1):
        value=deepcopy(self.request);value['request_id']='fixture-request-'+str(index)
        value['nonce']=f'{index:064x}'
        return value

    def issue(self,request,*,index=1,generation=1):
        return self.ledger.issue_challenge_reference(request,generation=generation,rp_id='offline-fixture.invalid',
            origin='https://offline-fixture.invalid',operation_id='fixture-issue-'+str(index),now=1000)

    def packet(self,request,*,key=None,count=2,flags=5,raw=None,auth=None):
        client=dict(type='webauthn.get',challenge=challenge_for(request),origin='https://offline-fixture.invalid')
        raw=json.dumps(client,separators=(',',':')).encode() if raw is None else raw
        auth=sha256(b'offline-fixture.invalid').digest()+bytes([flags])+count.to_bytes(4,'big') if auth is None else auth
        return dict(client_data_json=raw,authenticator_data=auth,
            signature=(key or self.key).sign(auth+sha256(raw).digest(),ec.ECDSA(hashes.SHA256())),
            credential_id='fixture-credential')

    def rows(self,table):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory=sqlite3.Row
            return [dict(r) for r in db.execute('SELECT * FROM '+table)]

    def mutation_digest(self,namespace,operation_id):
        return next(r['request_digest'] for r in self.rows('receipts') if r['namespace']==namespace and r['operation_id']==operation_id)

    def publish_input(self,request,packet):
        p=Path(self.tmp.name)/'PUBLIC-FIXTURE.json'
        p.write_text(json.dumps(dict(path=str(self.path),scope=self.scope,intent=request,
            packet={k:v.hex() if type(v) is bytes else v for k,v in packet.items()},now=1000)),encoding='utf-8')
        return p

CHILD = '''
import json,sys,os
from atlasquant_aion_first_install_preparation_v3.webauthn_ledger_reference import ReferenceWebAuthnLedger,attempt_binding
from atlasquant_aion_first_install_preparation_v3.ledger_storage import read_receipt_reference
p=json.load(open(sys.argv[1],encoding="utf-8"))
packet={k:bytes.fromhex(v) if k!="credential_id" else v for k,v in p["packet"].items()}
if sys.argv[2]=="read":
 bound=attempt_binding(p["intent"],packet)[1]
 print(json.dumps(read_receipt_reference(p["path"],scope=p["scope"],namespace="CONSUMPTION",operation_id=sys.argv[3],expected_request_digest=bound["request_digest"],minimum_sequence=0)))
else:
 ledger=ReferenceWebAuthnLedger(p["path"],scope=p["scope"])
 if sys.argv[2]=="crash":
  original=ledger.connect
  class Crash:
   def __init__(self,db):self.db=db
   def __getattr__(self,name):return getattr(self.db,name)
   def commit(self):
    row=self.db.execute("SELECT 1 FROM receipts WHERE namespace='CONSUMPTION'").fetchone()
    self.db.commit()
    if row:os._exit(23)
  def connect(**kw):
   db=original(**kw)
   return db if kw.get('read_only') else Crash(db)
  ledger.connect=connect
 print(json.dumps(ledger.confirm_assertion_reference(p["intent"],packet,attempt_id=sys.argv[3],now=p["now"])))
'''
