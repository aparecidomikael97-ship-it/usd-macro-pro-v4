"""All-domain offline anchor comparison; single-snapshot causal readback only.

No majority, write, claim release or local fallback. Files and operators remain
untrusted fixtures even if their labels and public keys differ.
"""
import json
from pathlib import Path
from atlasquant_aion_first_install_preparation.contracts import exact,token
from .outcomes import result
from atlasquant_aion_first_install_preparation_v3.ledger_storage import Refusal
from atlasquant_aion_first_install_preparation_v2.webauthn_reference import _pairs
from .commitments import capture_ledger_reference,comparable_state,commitment_contract
from .signed_anchors import verify_fresh_read_reference,pin_contract,READ_FIELDS

MEMBER_FIELDS=frozenset({"pin","expected_pin_digest","query","response","floor","consumed_nonces"})

class FixtureReadFile:
    """Bounded public synthetic JSON response adapter. Reads, never signs/writes."""
    def __init__(self,path):self.path=Path(path)
    def read_reference(self):
        try:
            with self.path.open('rb') as stream:raw=stream.read(4097)
            if not 1<=len(raw)<=4096:raise Refusal("RESPONSE_BOUND_EXCEEDED")
            value=json.loads(raw.decode('utf-8'),object_pairs_hook=_pairs,
                parse_constant=lambda _:(_ for _ in ()).throw(Refusal("NONFINITE_JSON")))
            exact(value,READ_FIELDS);commitment_contract(value['commitment'])
            return value
        except (OSError,ValueError,TypeError,UnicodeError,RecursionError):return None

def compare_anchors_reference(path,*,config,members,now,revoked_keys=None,revoked_operators=None,causal=None):
    """Pin/scope/signature/freshness before opening local SQLite; no fallback.

    Three is an explicit lab policy, not quorum or proof of three institutions.
    """
    try:
        if type(members) is not list or len(members)!=3:raise Refusal("ALL_THREE_DOMAINS_REQUIRED")
        checked=[];operators=set();domains=set();keys=set();witnesses=set()
        for member in members:
            exact(member,MEMBER_FIELDS);pin=pin_contract(member['pin'])
            cfg={**config,'witness_id':pin['witness_id']}
            out=verify_fresh_read_reference(member['response'],query=member['query'],pin=pin,
                expected_pin_digest=member['expected_pin_digest'],config=cfg,floor=member['floor'],now=now,
                consumed_nonces=member['consumed_nonces'],revoked_keys=revoked_keys,revoked_operators=revoked_operators)
            if out['state']!='REFERENCE_FRESH_READ_MATH_UNTRUSTED':
                return result('UNKNOWN_OUTCOME' if out['state']=='UNKNOWN_OUTCOME' else 'BLOCKED','DOMAIN_READ_NOT_VERIFIED_NO_FALLBACK')
            checked.append(out['commitment']);operators.add(pin['operator_alias'])
            domains.add(pin['administrative_domain_alias']);keys.add(pin['public_key_hex']);witnesses.add(pin['witness_id'])
        if any(len(values)!=3 for values in (operators,domains,keys,witnesses)):
            raise Refusal('SHARED_AUTHORITY_OR_KEY_NOT_INDEPENDENT')
        if any(comparable_state(c)!=comparable_state(checked[0]) for c in checked[1:]):
            raise Refusal('CONFLICTING_DOMAIN_COMMITMENTS')
        # Metadata-only snapshot is explicitly distinct from a causal operation.
        local=capture_ledger_reference(path,config=config,previous_commitment_digest=checked[0]['previous_commitment_digest'],causal=causal)
        if local['state']!='REFERENCE_SNAPSHOT_UNTRUSTED':
            return result(local['state'] if local['state'] in ('BLOCKED','RECONCILIATION_REQUIRED','UNKNOWN_OUTCOME') else 'UNKNOWN_OUTCOME','LOCAL_READ_INCOMPLETE_NO_RETRY')
        if comparable_state(local['commitment'])!=comparable_state(checked[0]):
            raise Refusal('LOCAL_ROLLBACK_FORK_OR_STATE_MISMATCH')
        ancestry={r['sequence']:r['head_digest'] for r in local['local_ancestry']}
        for member in members:
            floor=commitment_contract(member['floor'])
            if ancestry.get(floor['sequence'])!=floor['local_head_sha256']:
                raise Refusal('FLOOR_NOT_IN_LOCAL_CAUSAL_CHAIN')
        return result('REFERENCE_ANCHORED_CAUSAL_MATH_UNTRUSTED' if causal is not None else 'REFERENCE_STATE_ANCHOR_MATH_UNTRUSTED',
            'LAB_MATCH_NOT_INDEPENDENT_EXTERNAL_TRUST',signature_mathematical_valid=True,
            local_persistence_verified=causal is not None,causal_receipt=local['causal_receipt'],
            root_trust_verified=False,external_anchor_verified=False,independent_administrative_domains_verified=False,
            latest_head_independently_verified=False,rollback_protection_production_verified=False,
            trusted_clock_verified=False,safe_to_resume=False)
    except (ValueError,TypeError,KeyError,RecursionError):
        return result('BLOCKED','ANCHOR_RECOVERY_CONTRACT_OR_DIVERGENCE_REJECTED',safe_to_resume=False)

def reconcile_anchored_operation_reference(path,*,config,members,causal,now,
        revoked_keys=None,revoked_operators=None):
    if causal is None:return result('BLOCKED','CAUSAL_EXPECTATION_REQUIRED_NO_RETRY',safe_to_resume=False)
    return compare_anchors_reference(path,config=config,members=members,causal=causal,now=now,
        revoked_keys=revoked_keys,revoked_operators=revoked_operators)

PROVENANCE_FIELDS=frozenset({'schema','mode','root_id','root_public_key_hex','witness_authorization',
    'institutional_identity','custody_evidence','independent_receipt_channel','revocation_channel',
    'operator_separation_evidence','root_rotation','exceptional_recovery'})

def review_enrollment_blueprint(value):
    """Future provenance/custody protocol outline, NOT executed enrollment."""
    try:
        from atlasquant_aion_first_install_preparation.contracts import digest_value
        exact(value,PROVENANCE_FIELDS)
        if (value['schema']!='AION_WITNESS_ENROLLMENT_BLUEPRINT_V4' or value['mode']!='SYNTHETIC_ONLY'
                or not token(value['root_id']) or not value['root_id'].startswith('fixture-')
                or not digest_value(value['root_public_key_hex'])
                or any(value[k]!='UNKNOWN' for k in ('witness_authorization','institutional_identity','custody_evidence',
                    'independent_receipt_channel','revocation_channel','operator_separation_evidence'))
                or value['root_rotation']!='EXPLICIT_SEPARATE_OWNER_APPROVAL_REQUIRED'
                or value['exceptional_recovery']!='EXPLICIT_SEPARATE_OWNER_APPROVAL_REQUIRED'):
            raise Refusal('PROVENANCE_NOT_SYNTHETIC_OR_UNKNOWN')
        return result('REFERENCE_BLUEPRINT_UNTRUSTED','EXTERNAL_ENROLLMENT_NOT_PERFORMED',root_trust_verified=False,
            independent_custody_verified=False,institutional_identity_verified=False)
    except (ValueError,TypeError,KeyError):return result('BLOCKED','ENROLLMENT_BLUEPRINT_REJECTED')
