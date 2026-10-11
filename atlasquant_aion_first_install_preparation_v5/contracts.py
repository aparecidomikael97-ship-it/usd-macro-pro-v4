"""V5 domain-separated, closed contracts; math is never institutional trust."""
from hashlib import sha256
from atlasquant_aion_first_install_preparation.contracts import exact, token, integer, digest_value
from atlasquant_aion_runtime_source_boundary_ref_v1 import canonical_bytes, _verify_sig
from atlasquant_aion_first_install_preparation_v3.ledger_storage import Refusal, ZERO, canonical
from atlasquant_aion_first_install_preparation_v4.commitments import config_contract, commitment_contract, commitment_digest
from atlasquant_aion_first_install_preparation_v4.signed_anchors import pin_contract, pin_digest, query_contract, READ_FIELDS
from atlasquant_aion_first_install_preparation_v4.outcomes import result

READ_DOMAIN = b'AION_SIGNED_QUERY_RECEIPT_V5\0'
CONTROL_DOMAIN = b'AION_SIGNED_CONTROL_CANDIDATE_V5\0'
HASH_DOMAIN = b'AION_LOCAL_ADMISSION_V5\0'
PROOFS = {'institutional_custody': 'UNKNOWN', 'independent_owner_consent': 'UNKNOWN',
          'trusted_time': 'UNKNOWN', 'independent_revocation_channel': 'UNKNOWN'}

def digest(value):
    # Unlike the signing primitive, hashes include ALL signature fields.
    return sha256(HASH_DOMAIN + canonical(value).encode('ascii')).hexdigest()

def alias(value):
    if not token(value) or not value.startswith('fixture-'):
        raise Refusal('SYNTHETIC_ALIAS_REQUIRED')
    return value

def root_contract(value):
    exact(value, {'root_id', 'generation', 'public_key_hex', 'provenance'})
    alias(value['root_id'])
    if not integer(value['generation'], 1, 2**31-1) or not digest_value(value['public_key_hex']) or value['provenance'] != 'FIXTURE_UNENROLLED':
        raise Refusal('ROOT_CONTRACT_INVALID')
    return dict(value)

def configuration(value):
    exact(value, {'config', 'root', 'members', 'required_proofs'})
    cfg = config_contract(value['config']); root_contract(value['root'])
    if value['required_proofs'] != PROOFS or type(value['members']) is not list or len(value['members']) != 3:
        raise Refusal('THREE_FIXTURES_UNKNOWN_PROVENANCE_REQUIRED')
    witnesses=[]; operators=[]; domains=[]; keys=[]
    for member in value['members']:
        exact(member, {'pin', 'expected_pin_digest', 'floor'})
        pin=pin_contract(member['pin']); floor=commitment_contract(member['floor'])
        if pin_digest(pin) != member['expected_pin_digest']:
            raise Refusal('PIN_DIGEST_INVALID')
        expected={**cfg, 'witness_id':pin['witness_id']}
        for key in expected:
            if floor[key] != expected[key]: raise Refusal('FLOOR_SCOPE_INVALID')
        for key in expected.keys()-{'epoch'}:
            if pin[key] != expected[key]: raise Refusal('PIN_SCOPE_INVALID')
        witnesses.append(pin['witness_id']); operators.append(pin['operator_alias'])
        domains.append(pin['administrative_domain_alias']); keys.append(pin['public_key_hex'])
    if any(len(set(items)) != 3 for items in (witnesses, operators, domains, keys)) or witnesses[0] != cfg['witness_id']:
        raise Refusal('FIXTURE_DOMAIN_POLICY_INVALID')
    return value

def binding_contract(value):
    exact(value, {'query', 'root_id', 'root_generation', 'expected_pin_digest', 'minimum_sequence',
                  'challenge', 'operation', 'attempt_id', 'expected_commitment_digest',
                  'previous_receipt_digest', 'revocation_head', 'causal'})
    query_contract(value['query'])
    for key in ('root_id', 'challenge', 'operation', 'attempt_id'): alias(value[key])
    if not integer(value['root_generation'],1,2**31-1) or not integer(value['minimum_sequence'],0,512):
        raise Refusal('BINDING_GENERATION_INVALID')
    for key in ('expected_pin_digest','expected_commitment_digest','previous_receipt_digest','revocation_head'):
        if not digest_value(value[key]): raise Refusal('BINDING_DIGEST_INVALID')
    if value['operation'] not in ('fixture-causal-read','fixture-state-read'):
        raise Refusal('READ_ONLY_OPERATION_REQUIRED')
    causal=value['causal']
    if value['operation']=='fixture-causal-read':
        exact(causal,{'namespace','operation_id','request_digest'})
        alias(causal['operation_id'])
        if causal['namespace']!='CONSUMPTION' or not digest_value(causal['request_digest']):
            raise Refusal('CAUSAL_RECEIPT_EXPECTATION_INVALID')
    elif causal is not None:raise Refusal('UNEXPECTED_CAUSAL_EXPECTATION')
    return value

def receipt_contract(value, binding, pin):
    exact(value, {'schema','algorithm','binding_digest','receipt_id','response','signature'})
    if value['schema'] != 'AION_SIGNED_QUERY_RECEIPT_V5' or value['algorithm'] != 'Ed25519' or value['binding_digest'] != digest(binding):
        raise Refusal('SIGNED_QUERY_BINDING_INVALID')
    alias(value['receipt_id'])
    exact(value['response'], READ_FIELDS)
    commitment_contract(value['response']['commitment'])
    _verify_sig(value, bytes.fromhex(pin['public_key_hex']), READ_DOMAIN)
    return value

KINDS = {'EPOCH_NEXT','ROOT_ROTATION','WITNESS_KEY_REVOCATION','OPERATOR_REVOCATION',
         'CUSTODY_COMPROMISE','OLD_ROOT_LOSS','WITNESS_REPLACEMENT','ADMIN_TRANSFER',
         'GENERATION_REVOCATION','EXCEPTIONAL_RECOVERY'}
REVOKING = KINDS-{'EPOCH_NEXT','ROOT_ROTATION','WITNESS_REPLACEMENT','ADMIN_TRANSFER','EXCEPTIONAL_RECOVERY'}

def control_contract(value, config):
    exact(value, {'schema','algorithm','event_id','kind','scope','root_id','root_generation',
                  'emitter','affected_object','epoch','proposed_epoch','causal_sequence','previous_commitment',
                  'initial_commitment','reason','new_root','proposed_identity','owner_approval','required_proofs','signature','new_signature'})
    if value['schema'] != 'AION_CONTROL_CANDIDATE_V5' or value['algorithm'] != 'Ed25519' or value['kind'] not in KINDS:
        raise Refusal('CONTROL_PROFILE_INVALID')
    for key in ('event_id','root_id','emitter','affected_object','reason'): alias(value[key])
    cfg=config['config'];root=config['root']
    if (value['scope'] != {k:cfg[k] for k in ('owner_id','tenant_id','workspace_id','ledger_id')}
            or value['root_id'] != root['root_id'] or value['root_generation'] != root['generation']
            or value['emitter'] != root['root_id'] or value['epoch'] != cfg['epoch']
            or not integer(value['root_generation'],1) or not integer(value['epoch'],1)
            or not integer(value['causal_sequence'],0,512) or not integer(value['proposed_epoch'],1)
            or value['required_proofs'] != PROOFS):
        raise Refusal('CONTROL_SCOPE_OR_PROOFS_INVALID')
    exact(value['owner_approval'], {'state','event_digest'})
    if value['owner_approval']['state'] != 'SIMULATED_ONLY' or not digest_value(value['owner_approval']['event_digest']):
        raise Refusal('OWNER_APPROVAL_NOT_SIMULATED')
    old=commitment_contract(value['previous_commitment']); new=commitment_contract(value['initial_commitment'])
    for key in cfg:
        if old[key] != cfg[key]: raise Refusal('CONTROL_COMMITMENT_SCOPE_INVALID')
    for key in cfg.keys()-{'epoch'}:
        if new[key] != cfg[key]: raise Refusal('NEW_COMMITMENT_SCOPE_INVALID')
    approval_payload={k:v for k,v in value.items() if k not in ('signature','new_signature','owner_approval')}
    if value['owner_approval']['event_digest'] != digest(approval_payload):
        raise Refusal('SIMULATED_APPROVAL_NOT_EVENT_BOUND')
    if value['kind']=='EPOCH_NEXT':
        if value['proposed_epoch']!=cfg['epoch']+1 or new['epoch'] != value['proposed_epoch'] or value['new_root'] is not None:
            raise Refusal('EPOCH_JUMP_OR_ROOT_SWAP')
    elif value['proposed_epoch'] != cfg['epoch'] or new != old:
        raise Refusal('UNSUPPORTED_EPOCH_CHANGE')
    if value['kind'] in ('WITNESS_REPLACEMENT','ADMIN_TRANSFER'):
        proposed=value['proposed_identity']
        exact(proposed,{'witness_id','key_id','operator_alias','administrative_domain_alias','public_key_hex','generation'})
        for key in ('witness_id','key_id','operator_alias','administrative_domain_alias'):alias(proposed[key])
        if not digest_value(proposed['public_key_hex']) or not integer(proposed['generation'],1):
            raise Refusal('PROPOSED_IDENTITY_INVALID')
    elif value['proposed_identity'] is not None:raise Refusal('UNREQUESTED_IDENTITY_TRANSFER')
    if value['kind']=='ROOT_ROTATION':
        candidate=root_contract(value['new_root'])
        if candidate['generation'] != root['generation']+1 or candidate['public_key_hex']==root['public_key_hex']:
            raise Refusal('ROOT_DOWNGRADE_OR_SAME_KEY')
        unsigned={k:v for k,v in value.items() if k not in ('signature','new_signature')}
        _verify_sig({**unsigned,'signature':value['new_signature']},bytes.fromhex(candidate['public_key_hex']),CONTROL_DOMAIN)
    elif value['new_root'] is not None or value['new_signature'] is not None:
        raise Refusal('UNREQUESTED_NEW_ROOT')
    unsigned={k:v for k,v in value.items() if k not in ('signature','new_signature')}
    _verify_sig({**unsigned,'signature':value['signature']},bytes.fromhex(root['public_key_hex']),CONTROL_DOMAIN)
    return value

def outcome(state,*reasons,**details):
    return result(state,*reasons,**details,root_generation_productive_verified=False,
                  human_consent_verified=False,independent_monotonicity_verified=False,
                  productive_credential_enrolled=False)
