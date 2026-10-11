from copy import deepcopy
import json
from pathlib import Path
import unittest
from atlasquant_aion_first_install_preparation.contracts import AUTHORITY_FIELDS
from atlasquant_aion_first_install_preparation_v4.signed_anchors import verify_fresh_read_reference,READ_DOMAIN,pin_digest
from atlasquant_aion_first_install_preparation_v4.recovery_bridge import FixtureReadFile,review_enrollment_blueprint
from tests.aion_signed_anchor_fixtures_v4 import AnchorFixture

class FreshnessTests(unittest.TestCase):
    def setUp(self):
        self.f=AnchorFixture();self.addCleanup(self.f.close);self.f.consume()
        self.query=self.f.query(0);self.response=self.f.response(0,self.query)
        self.options=dict(query=self.query,pin=self.f.pins[0],expected_pin_digest=pin_digest(self.f.pins[0]),config=self.f.cfg(0),floor=self.f.floors[0],now=1000,consumed_nonces=[],revoked_keys=[],revoked_operators=[])
    def review(self,response=None,**overrides):
        out=verify_fresh_read_reference(self.response if response is None else response,**{**self.options,**overrides})
        for k in AUTHORITY_FIELDS:self.assertIs(out[k],False)
        return out
    def test_valid_fresh_signature_not_trusted_time_or_independence(self):
        out=self.review();self.assertEqual(out['state'],'REFERENCE_FRESH_READ_MATH_UNTRUSTED')
        for k in ['root_trust_verified','trusted_clock_verified','latest_head_independently_verified','durable_nonce_consumption_verified']:self.assertFalse(out[k])
    def test_expiry_clock_key_and_nonce_unknown(self):
        for override in [dict(now=1050),dict(now=999),dict(now=True),dict(now=1100),dict(consumed_nonces=None),dict(consumed_nonces=[self.query['nonce']]),dict(consumed_nonces=['bad']),dict(consumed_nonces=[self.query['nonce']]*2)]:
            with self.subTest(override=list(override)):self.assertEqual(self.review(**override)['state'],'BLOCKED')
    def test_signed_old_response_and_nonce_swap(self):
        for field,value in [('nonce','a'*64),('issued_at',990),('expires_at',1040),('clock_provenance','REAL_CLOCK'),('witness_id','fixture-other'),('root_provenance_digest','a'*64),('key_generation',2)]:
            with self.subTest(field=field):
                r=deepcopy(self.response);r[field]=value;r=self.f.sign(r,0,READ_DOMAIN)
                self.assertEqual(self.review(r)['state'],'BLOCKED')
    def test_signed_current_nonce_old_anchor_with_new_floor(self):
        r=self.f.response(0,self.query,self.f.floors[0])
        self.assertEqual(self.review(r,floor=self.response['commitment'])['state'],'BLOCKED')
    def test_unknown_response_has_no_local_fallback(self):
        out=verify_fresh_read_reference(None,**self.options)
        self.assertEqual(out['state'],'UNKNOWN_OUTCOME');self.assertFalse(out['automatic_retry_authorized'])
    def test_duplicate_json_nan_malformed_and_oversize_reader(self):
        p=Path(self.f.ledger.tmp.name)/'public-read.json'
        for raw in [b'{',b'{"nonce":"a","nonce":"b"}',b'{"field":NaN}',b'x'*4097,b'\xff',b'['*2000+b']'*2000]:
            with self.subTest(size=len(raw)):
                p.write_bytes(raw);self.assertIsNone(FixtureReadFile(p).read_reference())
        p.write_text(json.dumps(self.response),encoding='utf-8');self.assertEqual(FixtureReadFile(p).read_reference(),self.response)
    def test_enrollment_blueprint_unknown_only(self):
        b=dict(schema='AION_WITNESS_ENROLLMENT_BLUEPRINT_V4',mode='SYNTHETIC_ONLY',root_id='fixture-root',root_public_key_hex='a'*64,
            witness_authorization='UNKNOWN',institutional_identity='UNKNOWN',custody_evidence='UNKNOWN',independent_receipt_channel='UNKNOWN',revocation_channel='UNKNOWN',operator_separation_evidence='UNKNOWN',root_rotation='EXPLICIT_SEPARATE_OWNER_APPROVAL_REQUIRED',exceptional_recovery='EXPLICIT_SEPARATE_OWNER_APPROVAL_REQUIRED')
        self.assertEqual(review_enrollment_blueprint(b)['state'],'REFERENCE_BLUEPRINT_UNTRUSTED')
        for field in ['mode','institutional_identity','custody_evidence','root_rotation','worker_authorized']:
            with self.subTest(field=field):
                bad=dict(b);bad[field]='VERIFIED';self.assertEqual(review_enrollment_blueprint(bad)['state'],'BLOCKED')

if __name__=='__main__':unittest.main()
