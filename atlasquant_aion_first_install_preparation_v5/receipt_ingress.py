"""Strict bounded public fixture receipt JSON. No file/network IO or trust claim."""
import json
from atlasquant_aion_first_install_preparation.contracts import exact, digest_value
from atlasquant_aion_first_install_preparation_v2.webauthn_reference import _pairs
from atlasquant_aion_first_install_preparation_v3.ledger_storage import Refusal, canonical
from atlasquant_aion_first_install_preparation_v4.signed_anchors import READ_FIELDS
from atlasquant_aion_first_install_preparation_v4.commitments import commitment_contract

def decode_fixture_receipt(raw):
    if type(raw) is not bytes or not 1<=len(raw)<=8192:raise Refusal('RECEIPT_BYTES_BOUND')
    try:
        value=json.loads(raw.decode('utf-8'),object_pairs_hook=_pairs,
            parse_constant=lambda _:(_ for _ in ()).throw(Refusal('NONFINITE_JSON')))
        exact(value,{'schema','algorithm','binding_digest','receipt_id','response','signature'})
        exact(value['response'],READ_FIELDS);commitment_contract(value['response']['commitment'])
        if (raw!=canonical(value).encode('ascii') or value['schema']!='AION_SIGNED_QUERY_RECEIPT_V5'
                or value['algorithm']!='Ed25519' or not digest_value(value['binding_digest'])):
            raise Refusal('CANONICAL_CLOSED_RECEIPT_REQUIRED')
        return value
    except (ValueError,TypeError,KeyError,UnicodeError,RecursionError):
        raise Refusal('FIXTURE_JSON_REJECTED') from None
