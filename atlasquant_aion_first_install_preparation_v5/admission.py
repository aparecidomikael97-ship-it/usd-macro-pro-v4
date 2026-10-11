"""Three-witness local admission; reuse V4 crypto and causal single-snapshot read.

No majority, network, signer, productive trust enrollment, retry or lease release.
The only positive decision is historical, local, experimental admission.
"""
from copy import deepcopy
from cryptography.exceptions import InvalidSignature
from atlasquant_aion_first_install_preparation.contracts import integer
from atlasquant_aion_first_install_preparation_v3.ledger_storage import Refusal
from atlasquant_aion_first_install_preparation_v4.commitments import commitment_digest, comparable_state
from atlasquant_aion_first_install_preparation_v4.recovery_bridge import compare_anchors_reference
from .contracts import (binding_contract, receipt_contract, control_contract, digest, alias,
                        outcome, REVOKING)
from .storage import AdmissionStorage, LIMIT

class ReferenceReceiptAdmission(AdmissionStorage):
    def _commit_read(self,op,request,retained,callback):
        out=self.transaction(op,digest(request),retained,callback)
        if out['state']!='REFERENCE_LOCAL_COMMIT_UNTRUSTED':return out
        return self.reconcile(op,digest(request),out['retained_reference'])

    def _bindings(self,bindings,state):
        if type(bindings) is not list or len(bindings)!=3:raise Refusal('ALL_WITNESSES_REQUIRED')
        if state['root_state']!='FIXTURE_ACTIVE':raise Refusal('ROOT_REVOKED_OR_UNKNOWN')
        root=self.config['root'];cfg=self.config['config']
        for i,b in enumerate(bindings):
            binding_contract(b);query=b['query'];pin=self.config['members'][i]['pin'];floor=state['floors'][i]
            if (b['root_id']!=root['root_id'] or b['root_generation']!=root['generation']
                    or b['expected_pin_digest']!=self.config['members'][i]['expected_pin_digest']
                    or b['minimum_sequence']!=floor['commitment']['sequence']
                    or b['previous_receipt_digest']!=floor['receipt_digest']
                    or b['revocation_head']!=state['revocation_head']):
                raise Refusal('ROOT_FLOOR_RECEIPT_OR_REVOCATION_STALE')
            expected={**cfg,'witness_id':pin['witness_id']}
            for key in expected.keys()-{'epoch'}:
                if query[key]!=expected[key]:raise Refusal('QUERY_SCOPE_MISMATCH')
            for key in ('key_id','key_generation','root_provenance_digest'):
                if query[key]!=pin[key]:raise Refusal('QUERY_PIN_SUBSTITUTED')
            if query['minimum_epoch']!=cfg['epoch']:raise Refusal('UNESTABLISHED_EPOCH')
            if any(r['affected_object'] in (root['root_id'],pin['key_id'],pin['operator_alias'],
                    'fixture-generation-'+str(root['generation'])) for r in state['revocations']):
                raise Refusal('REVOCATION_BLOCKS_ADMISSION')
        for field in ('attempt_id','challenge','operation'):
            if len({b[field] for b in bindings})!=1:raise Refusal('CAUSAL_BUNDLE_DIVERGENCE')
        if len({b['query']['nonce'] for b in bindings})!=3:raise Refusal('NONCE_NOT_DISTINCT')
        if any(b['causal']!=bindings[0]['causal'] for b in bindings[1:]):raise Refusal('CAUSAL_EXPECTATION_DIVERGENCE')

    def issue(self,bindings,*,operation_id,retained,now):
        try:
            alias(operation_id)
            if type(bindings) is not list or len(bindings)!=3:raise Refusal('THREE_BINDINGS_REQUIRED')
            for b in bindings:binding_contract(b)
            bindings=deepcopy(bindings)
            def change(state,head):
                self._bindings(bindings,state)
                if not integer(now) or len(state['nonces'])+3>96:raise Refusal('ISSUE_BOUND_OR_CLOCK')
                for b in bindings:
                    q=b['query'];n=q['nonce']
                    if (n in state['nonces'] or not q['issued_at']<=now<q['expires_at']
                            or any(row['binding']['attempt_id']==b['attempt_id'] for row in state['nonces'].values())):
                        # Same causal attempt is permitted for its own three witnesses below,
                        # but cannot be reissued as another operation.
                        raise Refusal('ISSUANCE_REPLAY_OR_EXPIRY')
                for b in bindings:state['nonces'][b['query']['nonce']]=dict(binding=b,state='ISSUED',reservation_digest=None)
            return self._commit_read(operation_id,bindings,retained,change)
        except (ValueError,TypeError,KeyError,RecursionError):return outcome('BLOCKED','ISSUE_CONTRACT_REJECTED')

    def _verify_receipts(self,bindings,receipts,state,*,now,ledger_path,causal):
        self._bindings(bindings,state)
        if type(receipts) is not list or len(receipts)!=3:raise Refusal('ALL_RECEIPTS_REQUIRED')
        members=[];commitments=[]
        for i,(b,r) in enumerate(zip(bindings,receipts)):
            if b['causal']!=causal:raise Refusal('UNBOUND_CAUSAL_READ_EXPECTATION')
            pin=self.config['members'][i]['pin'];receipt_contract(r,b,pin)
            c=r['response']['commitment']
            if commitment_digest(c)!=b['expected_commitment_digest'] or r['receipt_id'] in state['receipts']:
                raise Refusal('COMMITMENT_CONFLICT_OR_RECEIPT_REPLAY')
            commitments.append(c)
            members.append(dict(pin=pin,expected_pin_digest=b['expected_pin_digest'],query=b['query'],
                                response=r['response'],floor=state['floors'][i]['commitment'],consumed_nonces=[]))
        if len({r['receipt_id'] for r in receipts})!=3 or any(comparable_state(c)!=comparable_state(commitments[0]) for c in commitments[1:]):
            raise Refusal('RECEIPT_OR_WITNESS_DIVERGENCE')
        # Known revocations are already checked from verified local journal above.
        # V4 validates all signatures and freshness BEFORE its read-only V3 snapshot.
        check=compare_anchors_reference(ledger_path,config=self.config['config'],members=members,now=now,
                                       revoked_keys=[],revoked_operators=[],causal=causal)
        expected='REFERENCE_ANCHORED_CAUSAL_MATH_UNTRUSTED' if causal is not None else 'REFERENCE_STATE_ANCHOR_MATH_UNTRUSTED'
        if check['state']!=expected:raise Refusal('SIGNED_STATE_OR_CAUSAL_READ_NOT_VERIFIED')

    def admit(self,bindings,receipts,*,operation_id,retained,now,ledger_path,causal=None):
        try:
            alias(operation_id)
            if type(bindings) is not list or len(bindings)!=3 or type(receipts) is not list or len(receipts)!=3:
                raise Refusal('THREE_BINDINGS_AND_RECEIPTS_REQUIRED')
            for i,(b,r) in enumerate(zip(bindings,receipts)):
                binding_contract(b);receipt_contract(r,b,self.config['members'][i]['pin'])
            bindings=deepcopy(bindings);receipts=deepcopy(receipts)
            request=dict(bindings=bindings,receipts=receipts,causal=causal)
            request_digest=digest(request)
            def reserve(state,head):
                self._verify_receipts(bindings,receipts,state,now=now,ledger_path=ledger_path,causal=causal)
                for b in bindings:
                    row=state['nonces'].get(b['query']['nonce'])
                    if row is None or row['state']!='ISSUED' or row['binding']!=b:raise Refusal('NONCE_NOT_ISSUED_OR_UNAVAILABLE')
                for b in bindings:
                    row=state['nonces'][b['query']['nonce']];row['state']='RESERVED';row['reservation_digest']=request_digest
            reserved=self._commit_read(operation_id+'-reserve',request,retained,reserve)
            if reserved['state']!='REFERENCE_DURABLE_ADMISSION_UNTRUSTED':return reserved
            def consume(state,head):
                # Recheck under SQLite writer lock after reservation: revocation,
                # clock, parent and local causal state may have changed meanwhile.
                self._verify_receipts(bindings,receipts,state,now=now,ledger_path=ledger_path,causal=causal)
                if len(state['receipts'])+3>96:raise Refusal('RECEIPT_BOUND')
                for i,(b,r) in enumerate(zip(bindings,receipts)):
                    row=state['nonces'].get(b['query']['nonce'])
                    if row is None or row['state']!='RESERVED' or row['reservation_digest']!=request_digest or row['binding']!=b:
                        raise Refusal('RESERVATION_CONFLICT')
                    row['state']='CONSUMED'
                    receipt_hash=digest(r)
                    state['receipts'][r['receipt_id']]=dict(receipt=r,binding_digest=digest(b),
                        receipt_digest=receipt_hash,admission_operation=operation_id,causal=causal)
                    state['floors'][i]=dict(commitment=r['response']['commitment'],receipt_id=r['receipt_id'],
                        root_id=b['root_id'],root_generation=b['root_generation'],
                        receipt_digest=receipt_hash,previous_receipt_digest=b['previous_receipt_digest'])
            out=self._commit_read(operation_id,request,reserved['retained_reference'],consume)
            if out['state']=='REFERENCE_DURABLE_ADMISSION_UNTRUSTED':
                out['local_nonce_consumption_verified']=True
                out['historical_admission_only']=True
            return out
        except (ValueError,TypeError,KeyError,InvalidSignature,OverflowError,RecursionError):
            return outcome('BLOCKED','ADMISSION_CONTRACT_OR_SIGNATURE_REJECTED')

    def quarantine(self,bindings,*,operation_id,retained):
        try:
            alias(operation_id)
            def change(state,head):
                if type(bindings) is not list or len(bindings)!=3:raise Refusal('THREE_BINDINGS_REQUIRED')
                for b in bindings:
                    binding_contract(b);row=state['nonces'].get(b['query']['nonce'])
                    if row is None or row['binding']!=b or row['state'] not in ('ISSUED','RESERVED'):
                        raise Refusal('QUARANTINE_REPLAY_OR_CONFLICT')
                for b in bindings:state['nonces'][b['query']['nonce']]['state']='QUARANTINED'
            return self._commit_read(operation_id,bindings,retained,change)
        except (ValueError,TypeError,KeyError,RecursionError):return outcome('BLOCKED','QUARANTINE_CONTRACT_REJECTED')

    def control(self,event,*,retained):
        try:
            control_contract(event,self.config);event=deepcopy(event)
            def change(state,head):
                if state['root_state']!='FIXTURE_ACTIVE' or event['causal_sequence']!=head['sequence']:
                    raise Refusal('CONTROL_ROOT_REVOKED_OR_CAS_STALE')
                if event['previous_commitment']!=state['floors'][0]['commitment']:
                    raise Refusal('CONTROL_FINAL_HEAD_CONFLICT')
                if event['kind'] in REVOKING:
                    state['revocations'].append(event);state['revocation_head']=digest(event)
                    root=self.config['root'];obj=event['affected_object']
                    if obj in (root['root_id'],'fixture-generation-'+str(root['generation'])):
                        state['root_state']='FIXTURE_REVOKED'
                else:
                    slot=event['kind']+':'+str(event['epoch'])
                    if slot in state['candidates']:raise Refusal('COMPETING_TRANSITION_OR_REPLAY')
                    state['candidates'][slot]=event
                # CANDIDATE ONLY: no config/epoch/root pin is installed or activated.
            out=self._commit_read(event['event_id'],event,retained,change)
            if out['state']=='REFERENCE_DURABLE_ADMISSION_UNTRUSTED':out['candidate_only']=event['kind'] not in REVOKING
            return out
        except (ValueError,TypeError,KeyError,InvalidSignature,OverflowError,RecursionError):
            return outcome('BLOCKED','CONTROL_CANDIDATE_REJECTED')
