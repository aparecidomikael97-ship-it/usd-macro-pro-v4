"""Root/epoch mathematical candidates are never admission or owner consent."""
from copy import deepcopy
import unittest
from atlasquant_aion_first_install_preparation_v4.signed_anchors import pin_digest
from atlasquant_aion_first_install_preparation_v5.epoch_root_reference import (
    OLD_DOMAIN,NEW_DOMAIN,review_fixture_transition,
)
from tests.aion_signed_anchor_fixtures_v4 import AnchorFixture

class EpochRootV5Tests(unittest.TestCase):
    def setUp(self):
        self.fx=AnchorFixture();self.addCleanup(self.fx.close)
        self.old=self.fx.pins[0]
        self.new=deepcopy(self.old)
        self.new.update(key_id="fixture-new-key",key_generation=2,
                        public_key_hex=self.fx.pins[1]["public_key_hex"],
                        operator_alias="fixture-new-operator",
                        administrative_domain_alias="fixture-new-domain")
        self.transition={
            "schema":"AION_V5_ROOT_EPOCH_TRANSITION_FIXTURE",
            "mode":"SYNTHETIC_ONLY",
            "scope":{key:self.old[key] for key in
                     ("owner_id","tenant_id","workspace_id","ledger_id","witness_id")},
            "old_epoch":1,"new_epoch":2,
            "old_pin_digest":pin_digest(self.old),
            "new_pin_digest":pin_digest(self.new),
            "old_head_digest":"a"*64,
            "new_genesis_digest":"b"*64,
            "authorization_claim":"FIXTURE_UNVERIFIED_OWNER_APPROVAL",
            "operation_id":"fixture-transition-1",
            "reason":"SIMULATED_PLANNED_ROTATION",
        }
        self.sign(self.transition)
    def sign(self,d):
        original={k:v for k,v in d.items() if k not in ("old_signature","new_signature")}
        d["old_signature"]=self.fx.sign(original,0,OLD_DOMAIN)["signature"]
        d["new_signature"]=self.fx.sign(original,1,NEW_DOMAIN)["signature"]
        return d
    def check(self,d=None,**kw):
        args=dict(old_pin=self.old,new_pin=self.new,
                  expected_old_pin_digest=pin_digest(self.old),
                  expected_new_pin_digest=pin_digest(self.new),
                  revoked_keys=[],revoked_operators=[])
        args.update(kw)
        out=review_fixture_transition(d or self.transition,**args)
        self.assertEqual(out["status"],"HARD_NO_GO")
        self.assertIs(out["installer_authorized"],False)
        self.assertIs(out["epoch_transition_authorized"],False)
        self.assertIs(out["root_trust_verified"],False)
        return out
    def test_two_valid_signatures_still_no_enrollment(self):
        out=self.check()
        self.assertEqual(out["state"],"REFERENCE_DUAL_SIGNATURE_MATH_UNTRUSTED")
        self.assertFalse(out["transition_persisted"])
        self.assertFalse(out["independent_custody_verified"])
    def test_epoch_downgrade_jump_boolean_block(self):
        for value in (0,1,3,True,"2"):
            with self.subTest(value=value):
                d=deepcopy(self.transition);d["new_epoch"]=value;self.sign(d)
                self.assertEqual(self.check(d)["state"],"BLOCKED")
    def test_changed_scope_even_with_two_signatures_blocks(self):
        d=deepcopy(self.transition)
        d["scope"]["tenant_id"]="fixture-foreign"
        self.sign(d)
        self.assertEqual(self.check(d)["state"],"BLOCKED")
    def test_spoofed_new_pin_and_expected_pair_blocks(self):
        self.assertEqual(self.check(expected_new_pin_digest="a"*64)["state"],"BLOCKED")
        new=deepcopy(self.new);new["public_key_hex"]="0"*64
        self.assertEqual(self.check(new_pin=new)["state"],"BLOCKED")
    def test_revoked_or_unknown_revocation_blocks(self):
        self.assertEqual(self.check(revoked_keys=[self.old["key_id"]])["state"],"BLOCKED")
        self.assertEqual(self.check(revoked_operators=[self.new["operator_alias"]])["state"],"BLOCKED")
        self.assertEqual(self.check(revoked_keys=None)["state"],"BLOCKED")
    def test_old_signature_altered_and_replay_wrong_generation(self):
        d=deepcopy(self.transition);d["old_signature"]="0"*128
        self.assertEqual(self.check(d)["state"],"BLOCKED")
        n=deepcopy(self.new);n["key_generation"]=1
        self.assertEqual(self.check(new_pin=n,expected_new_pin_digest=pin_digest(n))["state"],"BLOCKED")
    def test_claim_of_real_owner_authority_never_valid(self):
        d=deepcopy(self.transition);d["authorization_claim"]="REAL_OWNER_APPROVED"
        self.sign(d)
        self.assertEqual(self.check(d)["state"],"BLOCKED")

if __name__=="__main__":
    unittest.main()
