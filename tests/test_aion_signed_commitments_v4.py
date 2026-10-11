from copy import deepcopy
from hashlib import sha256
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from atlasquant_aion_first_install_preparation.contracts import AUTHORITY_FIELDS
from atlasquant_aion_first_install_preparation_v4.commitments import commitment_digest,domain_digest,DOMAIN,commitment_contract
from atlasquant_aion_first_install_preparation_v4.signed_anchors import verify_anchor_reference,ANCHOR_DOMAIN,pin_digest
from tests.aion_signed_anchor_fixtures_v4 import AnchorFixture

class SignedCommitmentTests(unittest.TestCase):
    def setUp(self):
        self.f=AnchorFixture();self.addCleanup(self.f.close);self.f.consume();self.anchor=self.f.anchor(0)
        self.options=dict(pin=self.f.pins[0],expected_pin_digest=pin_digest(self.f.pins[0]),config=self.f.cfg(0),
            floor=self.f.floors[0],revoked_keys=[],revoked_operators=[])
    def review(self,envelope=None,**overrides):
        out=verify_anchor_reference(self.anchor if envelope is None else envelope,**{**self.options,**overrides})
        self.assertEqual(out['status'],'HARD_NO_GO')
        for k in AUTHORITY_FIELDS:self.assertIs(out[k],False)
        return out
    def test_valid_signature_only_mathematics_distinct_digests(self):
        out=self.review();self.assertEqual(out['state'],'REFERENCE_SIGNED_ANCHOR_MATH_UNTRUSTED')
        self.assertFalse(out['root_trust_verified']);self.assertFalse(out['latest_head_independently_verified'])
        self.assertEqual(len({out['commitment_digest'],out['signed_receipt_digest'],out['commitment']['state_digest'],out['commitment']['local_head_sha256']}),4)
    def test_invalid_signature_public_key_and_unauthorized_algorithm(self):
        for field,value in [('signature','0'*128),('signature','f'*127),('algorithm','ES256'),('key_id','fixture-wrong'),('key_generation',True),('key_generation',2)]:
            with self.subTest(field=field):
                a=deepcopy(self.anchor);a[field]=value;self.assertEqual(self.review(a)['state'],'BLOCKED')
        pin=deepcopy(self.f.pins[0]);pin['public_key_hex']='a'*64
        self.assertEqual(self.review(pin=pin,expected_pin_digest=pin_digest(pin))['state'],'BLOCKED')
    def test_hold_domain_not_web_authn(self):
        from atlasquant_aion_v2_external_witness_rollback_reference import DOMAIN as HOLD_DOMAIN
        wrong=self.f.sign(self.anchor,0,HOLD_DOMAIN)
        self.assertEqual(self.review(wrong)['state'],'BLOCKED')
        self.assertNotEqual(domain_digest(self.anchor['commitment'],HOLD_DOMAIN),commitment_digest(self.anchor['commitment']))
    def test_boolean_oversize_extra_and_schema_fields(self):
        for field,value in [('sequence',True),('epoch',True),('schema','HOLDS'),('ledger_schema','HOLDS'),('state_digest','x'*64),('ledger_id','x'*121),('worker_authorized',True)]:
            with self.subTest(field=field):
                a=deepcopy(self.anchor);a['commitment'][field]=value
                self.assertEqual(self.review(a)['state'],'BLOCKED')
    def test_signed_wrong_scope_ledger_policy_witness_epoch(self):
        for field,value in [('tenant_id','fixture-other'),('owner_id','fixture-other'),('workspace_id','fixture-other'),('ledger_id','fixture-other'),('policy_version',2),('witness_id','fixture-other'),('epoch',0),('epoch',2)]:
            with self.subTest(field=field):
                a=deepcopy(self.anchor);a['commitment'][field]=value;a=self.f.sign(a,0,ANCHOR_DOMAIN)
                self.assertEqual(self.review(a)['state'],'BLOCKED')
    def test_old_correct_signature_not_current_floor(self):
        old=self.f.anchor(0,self.f.floors[0]);self.assertEqual(self.review(old)['state'],'REFERENCE_SIGNED_ANCHOR_MATH_UNTRUSTED')
        newer=self.anchor['commitment'];self.assertEqual(self.review(old,floor=newer)['state'],'BLOCKED')
    def test_same_epoch_sequence_fork_and_parent_mismatch(self):
        for field in ['local_head_sha256','credential_state_digest','generation_revocation_digest','challenge_state_digest','causal_operations_digest','previous_commitment_digest']:
            with self.subTest(field=field):
                a=deepcopy(self.anchor);a['commitment'][field]='e'*64;a=self.f.sign(a,0,ANCHOR_DOMAIN)
                self.assertEqual(self.review(a,floor=self.anchor['commitment'])['state'],'BLOCKED')
        a=deepcopy(self.anchor);a['commitment']['previous_commitment_digest']='a'*64;a=self.f.sign(a,0,ANCHOR_DOMAIN)
        self.assertEqual(self.review(a)['state'],'BLOCKED')
    def test_key_operator_revoked_unknown_and_pin_substitution(self):
        for override in [dict(revoked_keys=None),dict(revoked_operators=None),dict(revoked_keys=[self.f.pins[0]['key_id']]),dict(revoked_operators=[self.f.pins[0]['operator_alias']])]:
            with self.subTest(override=list(override)):self.assertEqual(self.review(**override)['state'],'BLOCKED')
        p=deepcopy(self.f.pins[0]);p['root_provenance_digest']='a'*64
        self.assertEqual(self.review(pin=p)['state'],'BLOCKED')
    def test_caller_replaces_entire_fixture_root_cannot_get_authority(self):
        key=Ed25519PrivateKey.generate();p=deepcopy(self.f.pins[0])
        p['public_key_hex']=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex()
        from atlasquant_aion_runtime_source_boundary_ref_v1 import canonical_bytes
        a=deepcopy(self.anchor);a['signature']=key.sign(canonical_bytes(a,domain=ANCHOR_DOMAIN)).hex()
        self.assertEqual(self.review(a,pin=p)['state'],'BLOCKED')
        out=self.review(a,pin=p,expected_pin_digest=pin_digest(p));self.assertEqual(out['state'],'REFERENCE_SIGNED_ANCHOR_MATH_UNTRUSTED')
        self.assertFalse(out['root_trust_verified'])
    def test_payload_changed_after_signature(self):
        a=deepcopy(self.anchor);a['commitment']['state_digest']='b'*64
        self.assertEqual(self.review(a)['state'],'BLOCKED')
    def test_canonical_order_deterministic_and_real_signature_reuse(self):
        c=self.anchor['commitment'];self.assertEqual(commitment_digest(c),commitment_digest(dict(reversed(list(c.items())))))
        self.assertEqual(self.review()['state'],'REFERENCE_SIGNED_ANCHOR_MATH_UNTRUSTED')

if __name__=='__main__':unittest.main()
