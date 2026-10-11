"""Bounded append journal with immutable bootstrap and exact SQLite constraints.

Reuses V3 native per-call connections and canonical serialization. Its purpose-
specific V3 tables cannot hold atomic three-witness receipts, so V5 has a small
separate closed schema. Neither file is an independent administrative domain.
"""
import json
from pathlib import Path
import sqlite3
from cryptography.exceptions import InvalidSignature
from atlasquant_aion_first_install_preparation.contracts import ContractError
from atlasquant_aion_first_install_preparation_v3.ledger_storage import LedgerStorage, Refusal, ZERO, canonical
from .contracts import configuration, digest, outcome
from atlasquant_aion_first_install_preparation.contracts import exact, token, digest_value, integer
from .contracts import binding_contract, receipt_contract, control_contract
from atlasquant_aion_first_install_preparation_v4.signed_anchors import verify_fresh_read_reference
from atlasquant_aion_first_install_preparation_v4.commitments import commitment_contract, commitment_digest, comparable_state

LIMIT=128
MAX_BYTES=262144
DDL={
    'bootstrap':'singleton INTEGER PRIMARY KEY CHECK(singleton=1),config_json TEXT NOT NULL',
    'current':'singleton INTEGER PRIMARY KEY CHECK(singleton=1),sequence INTEGER NOT NULL CHECK(sequence>=0),head TEXT NOT NULL,state_json TEXT NOT NULL',
    'journal':'sequence INTEGER PRIMARY KEY CHECK(sequence>0),operation_id TEXT UNIQUE NOT NULL,request_digest TEXT NOT NULL,previous_digest TEXT NOT NULL,state_json TEXT NOT NULL,event_digest TEXT UNIQUE NOT NULL',
}

def decode(raw):
    if type(raw) is not str or len(raw)>MAX_BYTES: raise Refusal('STATE_BOUND_EXCEEDED')
    value=json.loads(raw)
    if raw!=canonical(value): raise Refusal('NONCANONICAL_STATE')
    return value

def initial(config):
    return dict(nonces={},receipts={},revocations=[],candidates={},root_state='FIXTURE_ACTIVE',
                revocation_head=ZERO, floors=[dict(commitment=m['floor'],receipt_id=None,
                    root_id=config['root']['root_id'],root_generation=config['root']['generation'],
                    receipt_digest=ZERO,previous_receipt_digest=ZERO) for m in config['members']])

def verify_state(state,previous,config):
    exact(state,{'nonces','receipts','revocations','candidates','root_state','revocation_head','floors'})
    if (type(state['nonces']) is not dict or len(state['nonces'])>96 or type(state['receipts']) is not dict
            or len(state['receipts'])>96 or type(state['revocations']) is not list or len(state['revocations'])>LIMIT
            or type(state['candidates']) is not dict or len(state['candidates'])>LIMIT
            or state['root_state'] not in ('FIXTURE_ACTIVE','FIXTURE_REVOKED')
            or not digest_value(state['revocation_head']) or type(state['floors']) is not list or len(state['floors'])!=3):
        raise Refusal('CLOSED_STATE_BOUND_INVALID')
    allowed={'ISSUED':{'ISSUED','RESERVED','QUARANTINED'},'RESERVED':{'RESERVED','CONSUMED','QUARANTINED'},
             'CONSUMED':{'CONSUMED'},'QUARANTINED':{'QUARANTINED'}}
    for nonce,row in state['nonces'].items():
        exact(row,{'binding','state','reservation_digest'});binding_contract(row['binding'])
        if nonce!=row['binding']['query']['nonce'] or row['state'] not in allowed:
            raise Refusal('NONCE_STATE_INVALID')
        old=previous['nonces'].get(nonce)
        if old is None and row['state']!='ISSUED':raise Refusal('NONCE_NOT_ISSUED')
        if old is not None and (old['binding']!=row['binding'] or row['state'] not in allowed[old['state']]):
            raise Refusal('NONCE_REGRESSION_OR_REBINDING')
        if row['state']=='ISSUED' and row['reservation_digest'] is not None:raise Refusal('UNRESERVED_DIGEST_INVALID')
        if row['state'] in ('RESERVED','CONSUMED') and not digest_value(row['reservation_digest']):
            raise Refusal('RESERVATION_DIGEST_REQUIRED')
    if not previous['nonces'].keys()<=state['nonces'].keys():raise Refusal('NONCE_ERASED')
    new_receipts=[r for rid,r in state['receipts'].items() if rid not in previous['receipts']]
    if new_receipts:
        if len(new_receipts)!=3 or any(comparable_state(r['receipt']['response']['commitment'])!=comparable_state(new_receipts[0]['receipt']['response']['commitment']) for r in new_receipts[1:]):
            raise Refusal('PARTIAL_OR_DIVERGENT_RECEIPT_BUNDLE')
        new_ids={r['receipt']['receipt_id'] for r in new_receipts}
        if {f['receipt_id'] for f in state['floors']}!=new_ids:raise Refusal('PARTIAL_FLOOR_UPDATE')
    for rid,row in state['receipts'].items():
        exact(row,{'receipt','binding_digest','receipt_digest','admission_operation','causal'})
        if (not token(rid) or row['receipt']['receipt_id']!=rid or row['receipt_digest']!=digest(row['receipt'])
                or not token(row['admission_operation']) or not digest_value(row['binding_digest'])):
            raise Refusal('RECEIPT_STATE_INVALID')
        matches=[n for n in state['nonces'].values() if digest(n['binding'])==row['binding_digest']]
        if len(matches)!=1 or matches[0]['state']!='CONSUMED':raise Refusal('RECEIPT_NOT_CONSUMED_ATOMICALLY')
        if rid not in previous['receipts']:
            binding=matches[0]['binding'];query=binding['query']
            indices=[i for i,m in enumerate(config['members']) if m['pin']['witness_id']==query['witness_id']]
            if len(indices)!=1:raise Refusal('RECEIPT_WITNESS_INVALID')
            i=indices[0];member=config['members'][i];pin=member['pin'];floor=previous['floors'][i]
            receipt_contract(row['receipt'],binding,pin)
            if (previous['root_state']!='FIXTURE_ACTIVE' or binding['root_id']!=config['root']['root_id']
                    or binding['root_generation']!=config['root']['generation']
                    or binding['expected_pin_digest']!=member['expected_pin_digest']
                    or binding['minimum_sequence']!=floor['commitment']['sequence']
                    or binding['previous_receipt_digest']!=floor['receipt_digest']
                    or binding['revocation_head']!=previous['revocation_head'] or binding['causal']!=row['causal']
                    or binding['expected_commitment_digest']!=commitment_digest(row['receipt']['response']['commitment'])):
                raise Refusal('RECEIPT_RECONSTRUCTION_BINDING_INVALID')
            revoked=[e['affected_object'] for e in previous['revocations']]
            checked=verify_fresh_read_reference(row['receipt']['response'],query=query,pin=pin,
                expected_pin_digest=member['expected_pin_digest'],config={**config['config'],'witness_id':pin['witness_id']},
                floor=floor['commitment'],now=query['issued_at'],consumed_nonces=[],
                revoked_keys=[v for v in revoked if v==pin['key_id']],revoked_operators=[v for v in revoked if v==pin['operator_alias']])
            if checked['state']!='REFERENCE_FRESH_READ_MATH_UNTRUSTED':raise Refusal('RECEIPT_HISTORY_SIGNATURE_INVALID')
    for rid,row in previous['receipts'].items():
        if state['receipts'].get(rid)!=row:raise Refusal('DURABLE_RECEIPT_CHANGED_OR_ERASED')
    if any(n['state']=='CONSUMED' and not any(r['binding_digest']==digest(n['binding']) for r in state['receipts'].values()) for n in state['nonces'].values()):
        raise Refusal('CONSUMPTION_WITHOUT_RECEIPT')
    if (state['revocations'][:len(previous['revocations'])]!=previous['revocations']
            or len(state['revocations'])<len(previous['revocations'])
            or previous['root_state']=='FIXTURE_REVOKED' and state['root_state']!='FIXTURE_REVOKED'):
        raise Refusal('REVOCATION_ERASED_OR_ROOT_REENABLED')
    expected_revocation=digest(state['revocations'][-1]) if state['revocations'] else ZERO
    if state['revocation_head']!=expected_revocation:raise Refusal('REVOCATION_HEAD_MISMATCH')
    for key,value in previous['candidates'].items():
        if state['candidates'].get(key)!=value:raise Refusal('CANDIDATE_CHANGED_OR_ERASED')
    for event in state['revocations'][len(previous['revocations']):]:control_contract(event,config)
    for key,event in state['candidates'].items():
        if key not in previous['candidates']:control_contract(event,config)
    for i,floor in enumerate(state['floors']):
        exact(floor,{'commitment','receipt_id','root_id','root_generation','receipt_digest','previous_receipt_digest'})
        c=commitment_contract(floor['commitment']);old=previous['floors'][i];root=config['root']
        if floor['root_id']!=root['root_id'] or floor['root_generation']!=root['generation']:
            raise Refusal('FLOOR_ROOT_SUBSTITUTED')
        expected={**config['config'],'witness_id':config['members'][i]['pin']['witness_id']}
        if any(c[k]!=v for k,v in expected.items()):raise Refusal('FLOOR_SCOPE_OR_EPOCH_SUBSTITUTED')
        if c['sequence']<old['commitment']['sequence']:raise Refusal('FLOOR_REGRESSED')
        if c['sequence']==old['commitment']['sequence'] and commitment_digest(c)!=commitment_digest(old['commitment']):
            raise Refusal('FLOOR_SAME_SEQUENCE_FORK')
        if c['sequence']>old['commitment']['sequence'] and c['previous_commitment_digest']!=commitment_digest(old['commitment']):
            raise Refusal('FLOOR_PARENT_INVALID')
        if floor!=old:
            r=state['receipts'].get(floor['receipt_id'])
            if r is None or floor['receipt_digest']!=r['receipt_digest'] or r['receipt']['response']['commitment']!=c or floor['previous_receipt_digest']!=old['receipt_digest']:
                raise Refusal('FLOOR_RECEIPT_CAUSAL_CONFLICT')

class AdmissionStorage:
    # Uses the existing connection implementation; never disables thread affinity.
    connect=LedgerStorage.connect

    def __init__(self,path,*,config,expected_config_digest,timeout=.1):
        config=json.loads(canonical(configuration(config)))
        if digest(config)!=expected_config_digest or type(timeout) not in (float,int) or not 0<=timeout<=2:
            raise Refusal('BOOTSTRAP_EXPECTATION_INVALID')
        self.path=Path(path).resolve();self.timeout=timeout
        self.config=config;self.config_digest=expected_config_digest
        db=None
        try:
            db=self.connect(create=True);db.execute('PRAGMA journal_mode=WAL');db.execute('BEGIN IMMEDIATE')
            found={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if found and found!=set(DDL): raise Refusal('NO_REBOOTSTRAP_UNKNOWN_STORE')
            if not found:
                for name,sql in DDL.items(): db.execute('CREATE TABLE '+name+' ('+sql+')')
                db.execute('INSERT INTO bootstrap VALUES (1,?)',(canonical(config),))
                db.execute('INSERT INTO current VALUES (1,0,?,?)',(ZERO,canonical(initial(config))))
            self.verify(db);db.commit()
        except (sqlite3.Error,ValueError,TypeError,OSError):
            if db is not None and db.in_transaction: db.rollback()
            raise Refusal('BOOTSTRAP_UNAVAILABLE_NO_RETRY') from None
        finally:
            if db is not None: db.close()

    def verify(self,db,retained=None):
        rows=db.execute("SELECT name,sql FROM sqlite_master WHERE type='table'").fetchall()
        if db.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view') LIMIT 1").fetchone():
            raise Refusal('UNEXPECTED_SCHEMA_BEHAVIOR')
        if {r['name']:r['sql'] for r in rows}!={k:'CREATE TABLE '+k+' ('+v+')' for k,v in DDL.items()}:
            raise Refusal('EXACT_SCHEMA_CONSTRAINTS_REQUIRED')
        if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise Refusal('SQLITE_INTEGRITY_INVALID')
        for table,column in (('bootstrap','config_json'),('current','state_json'),('journal','state_json')):
            if db.execute('SELECT 1 FROM '+table+' WHERE length('+column+')>? LIMIT 1',(MAX_BYTES,)).fetchone():
                raise Refusal('ROW_BOUND_EXCEEDED')
        if db.execute('SELECT 1 FROM journal WHERE length(operation_id)>120 OR length(request_digest)!=64 OR length(previous_digest)!=64 OR length(event_digest)!=64 LIMIT 1').fetchone():
            raise Refusal('JOURNAL_FIELD_BOUND_EXCEEDED')
        bootstrap=db.execute('SELECT config_json FROM bootstrap WHERE singleton=1').fetchone()
        if bootstrap is None or bootstrap[0]!=canonical(self.config):raise Refusal('BOOTSTRAP_SUBSTITUTED')
        head=db.execute('SELECT * FROM current WHERE singleton=1').fetchone()
        events=db.execute('SELECT * FROM journal ORDER BY sequence LIMIT ?',(LIMIT+1,)).fetchall()
        if head is None or len(events)>LIMIT:raise Refusal('JOURNAL_BOUND_OR_HEAD_INVALID')
        previous=ZERO;state=initial(self.config);ancestry={0:ZERO}
        for seq,event in enumerate(events,1):
            body={k:event[k] for k in ('sequence','operation_id','request_digest','previous_digest','state_json')}
            if (event['sequence']!=seq or event['previous_digest']!=previous or event['event_digest']!=digest(body)
                    or not token(event['operation_id']) or not digest_value(event['request_digest'])):
                raise Refusal('JOURNAL_CHAIN_INVALID')
            next_state=decode(event['state_json']);verify_state(next_state,state,self.config)
            added=[r for rid,r in next_state['receipts'].items() if rid not in state['receipts']]
            if added:
                bindings=[];receipts=[]
                for member in self.config['members']:
                    matches=[r for r in added if r['receipt']['response']['witness_id']==member['pin']['witness_id']]
                    if len(matches)!=1:raise Refusal('ADMISSION_HISTORY_WITNESS_DIVERGENCE')
                    r=matches[0];receipts.append(r['receipt'])
                    bindings.append(next(n['binding'] for n in next_state['nonces'].values() if digest(n['binding'])==r['binding_digest']))
                    if r['admission_operation']!=event['operation_id']:raise Refusal('ADMISSION_OPERATION_REBOUND')
                if event['request_digest']!=digest(dict(bindings=bindings,receipts=receipts,causal=added[0]['causal'])):
                    raise Refusal('ADMISSION_CAUSAL_DIGEST_CONFLICT')
            state=next_state;previous=event['event_digest'];ancestry[seq]=previous
        if head['sequence']!=len(events) or head['head']!=previous or head['state_json']!=canonical(state):
            raise Refusal('CURRENT_JOURNAL_MISMATCH')
        if retained is not None:
            exact(retained,{'sequence','head','config_digest'})
            if (not integer(retained['sequence'],0,LIMIT) or not digest_value(retained['head'])
                    or retained['config_digest']!=self.config_digest or ancestry.get(retained['sequence'])!=retained['head']):
                raise Refusal('RETAINED_REFERENCE_ROLLBACK_OR_FORK')
        return state,dict(sequence=len(events),head=previous,config_digest=self.config_digest)

    def read(self,retained):
        db=None;out=None
        try:
            if retained is None: raise Refusal('RETAINED_EXPECTATION_REQUIRED')
            db=self.connect(read_only=True);db.execute('BEGIN');state,head=self.verify(db,retained)
            out=outcome('REFERENCE_LOCAL_SNAPSHOT_UNTRUSTED','SAME_DOMAIN_JOURNAL',snapshot=state,retained_reference=head)
        except (ContractError,InvalidSignature):out=outcome('BLOCKED','READ_INTEGRITY_OR_RETAINED_REFERENCE_REJECTED')
        except (sqlite3.Error,ValueError,TypeError,KeyError,OSError,RecursionError):
            out=outcome('UNKNOWN_OUTCOME','READBACK_UNAVAILABLE_NO_RETRY')
        finally:
            if db is not None:
                try:db.close()
                except sqlite3.Error:out=outcome('UNKNOWN_OUTCOME','READ_CLOSE_UNCERTAIN_NO_RETRY')
        return out

    def transaction(self,operation_id,request_digest,retained,callback):
        db=None;attempted=False;out=None
        try:
            if retained is None:raise Refusal('RETAINED_EXPECTATION_REQUIRED')
            db=self.connect();db.execute('BEGIN IMMEDIATE');state,head=self.verify(db,retained)
            if head['sequence']>=LIMIT or db.execute('SELECT 1 FROM journal WHERE operation_id=?',(operation_id,)).fetchone():
                raise Refusal('OPERATION_REPLAY_OR_BOUND')
            callback(state,head)
            raw=canonical(state)
            if len(raw)>MAX_BYTES:raise Refusal('STATE_BOUND_EXCEEDED')
            seq=head['sequence']+1
            body=dict(sequence=seq,operation_id=operation_id,request_digest=request_digest,previous_digest=head['head'],state_json=raw)
            new_head=digest(body)
            db.execute('INSERT INTO journal VALUES (?,?,?,?,?,?)',(seq,operation_id,request_digest,head['head'],raw,new_head))
            changed=db.execute('UPDATE current SET sequence=?,head=?,state_json=? WHERE singleton=1 AND sequence=? AND head=?',
                               (seq,new_head,raw,head['sequence'],head['head'])).rowcount
            if changed!=1:raise Refusal('LOCAL_CAS_FAILED')
            self.verify(db);attempted=True;db.commit()
            out=outcome('REFERENCE_LOCAL_COMMIT_UNTRUSTED','READBACK_STILL_REQUIRED',
                        retained_reference=dict(sequence=seq,head=new_head,config_digest=self.config_digest))
        except (ContractError,InvalidSignature):out=outcome('BLOCKED','LOCAL_CONTRACT_OR_REPLAY_REJECTED')
        except (sqlite3.Error,ValueError,TypeError,KeyError,OSError,OverflowError,RecursionError):
            out=outcome('UNKNOWN_OUTCOME' if attempted else 'RECONCILIATION_REQUIRED','LOCAL_OUTCOME_UNPROVEN_NO_RETRY')
        finally:
            if db is not None:
                try:
                    if db.in_transaction:db.rollback()
                except sqlite3.Error:out=outcome('UNKNOWN_OUTCOME','ROLLBACK_UNCERTAIN_NO_RETRY')
                try:db.close()
                except sqlite3.Error:out=outcome('UNKNOWN_OUTCOME','CLOSE_UNCERTAIN_NO_RETRY')
        return out

    def reconcile(self,operation_id,request_digest,retained):
        # Separate native connection, no constructor, no claim or replay.
        db=None;out=None
        try:
            if retained is None:raise Refusal('RETAINED_EXPECTATION_REQUIRED')
            db=self.connect(read_only=True);db.execute('BEGIN');state,head=self.verify(db,retained)
            row=db.execute('SELECT * FROM journal WHERE operation_id=?',(operation_id,)).fetchone()
            if row is None:out=outcome('RECONCILIATION_REQUIRED','NO_CAUSAL_RECEIPT_NO_RETRY')
            elif row['request_digest']!=request_digest:out=outcome('BLOCKED','CAUSAL_PAYLOAD_CONFLICT')
            else:out=outcome('REFERENCE_DURABLE_ADMISSION_UNTRUSTED','HISTORICAL_LOCAL_COMMIT_ONLY',
                             operation_sequence=row['sequence'],retained_reference=head,snapshot=state,
                             local_persistence_verified=True)
        except (ContractError,InvalidSignature):out=outcome('BLOCKED','READBACK_CONTRACT_OR_INTEGRITY_REJECTED')
        except (sqlite3.Error,ValueError,TypeError,KeyError,OSError,RecursionError):
            out=outcome('UNKNOWN_OUTCOME','RECONCILIATION_UNAVAILABLE_NO_RETRY')
        finally:
            if db is not None:
                try:db.close()
                except sqlite3.Error:out=outcome('UNKNOWN_OUTCOME','READ_CLOSE_UNCERTAIN_NO_RETRY')
        return out
