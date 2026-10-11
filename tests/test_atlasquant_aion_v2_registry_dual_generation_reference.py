"""Synthetic two-signer generation checkpoint and owner rotation threat tests."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_v2_four_role_key_enrollment_reference import (
    ROLES, ROSTER_SCHEMA, PURPOSE as ROSTER_PURPOSE, ZERO,
    owner_approval_transcript, role_pop_transcript, roster_sha256,
)
from atlasquant_aion_v2_registry_dual_generation_reference import (
    HEAD_SCHEMA, PURPOSE, DOMAIN, MATCH, TRANSITION,
    canonical_registry_read, revoked_set_sha256,
    review_dual_registry_generation, review_anchored_rotation_preflight,
)


def pin(key, role):
    return {
        "key_id":"fixture-"+role.lower(),
        "public_key_hex":key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex(),
    }


def fp(public_pin):
    return sha256(bytes.fromhex(public_pin["public_key_hex"])).hexdigest()


class DualRegistryGenerationTests(unittest.TestCase):
    def setUp(self):
        self.keys={role:Ed25519PrivateKey.generate() for role in ROLES}
        self.pins={r:pin(self.keys[r],r) for r in ROLES}
        self.domains={
            "HUMAN_OWNER":"ci-owner-presence-not-enrolled",
            "COLLECTOR":"ci-collector-fixture",
            "PRIMARY_WITNESS":"ci-primary-domain",
            "SECONDARY_ANCHOR":"ci-second-domain",
        }
        self.roster=self.mkroster(self.pins)
        self.qcount=0

    def mkroster(self,pins,*,generation=1,previous=ZERO,
                 revoked=None,nonce=None):
        return {
            "schema":ROSTER_SCHEMA,
            "purpose":ROSTER_PURPOSE,
            "generation":generation,
            "previous_roster_sha256":previous,
            "owner_id":"owner","tenant_id":"tenant",
            "workspace_id":"workspace",
            "challenge_nonce_hex":nonce or "ab"*32,
            "pins":deepcopy(pins),"admin_domains":deepcopy(self.domains),
            "revoked_public_key_sha256":sorted(revoked or []),
        }

    def owner_envelope(self,roster,*,old_owner=None,keyset=None):
        keys=keyset or self.keys
        return {
            "roster":roster,
            "owner_approval_signature_hex":(
                old_owner or self.keys["HUMAN_OWNER"]
            ).sign(owner_approval_transcript(roster)).hex(),
            "pop_signatures_hex":{
                role:keys[role].sign(role_pop_transcript(roster,role)).hex()
                for role in ROLES
            },
        }

    def rotate(self,roles=("COLLECTOR",)):
        keys=dict(self.keys)
        pins=deepcopy(self.pins)
        revoked=[]
        for role in roles:
            revoked.append(fp(pins[role]))
            keys[role]=Ed25519PrivateKey.generate()
            pins[role]=pin(keys[role],role+"-v2")
        proposed=self.mkroster(
            pins,generation=2,previous=roster_sha256(self.roster),
            revoked=revoked,nonce="cd"*32,
        )
        return self.owner_envelope(proposed,keyset=keys),keys,proposed

    def query(self,role,*,floor=4):
        self.qcount+=1
        return {
            "owner_id":"owner","tenant_id":"tenant","workspace_id":"workspace",
            "challenge_nonce_hex":f"{self.qcount:064x}",
            "minimum_registry_epoch":floor,
        }

    def signed(self,role,q,roster,*,key=None,epoch=4,generation=None):
        generation=roster["generation"] if generation is None else generation
        payload={
            "schema":HEAD_SCHEMA,"purpose":PURPOSE,
            "role":role,"signer_key_id":self.pins[role]["key_id"],
            "owner_id":q["owner_id"],"tenant_id":q["tenant_id"],
            "workspace_id":q["workspace_id"],
            "challenge_nonce_hex":q["challenge_nonce_hex"],
            "minimum_registry_epoch":q["minimum_registry_epoch"],
            "registry_epoch":epoch,"generation":generation,
            "roster_sha256":roster_sha256(roster),
            "revoked_set_sha256":revoked_set_sha256(
                roster["revoked_public_key_sha256"]
            ),
            "previous_roster_sha256":roster["previous_roster_sha256"],
        }
        signer=key or self.keys[role]
        return {"payload":payload,"signature_hex":signer.sign(
            canonical_registry_read(payload)).hex()}

    def pair(self,roster=None,*,secondary_roster=None):
        roster=self.roster if roster is None else roster
        secondary_roster=roster if secondary_roster is None else secondary_roster
        pq=self.query("PRIMARY_WITNESS")
        aq=self.query("SECONDARY_ANCHOR")
        return (
            pq,self.signed("PRIMARY_WITNESS",pq,roster),
            aq,self.signed("SECONDARY_ANCHOR",aq,secondary_roster),
        )

    def review(self,pq,pr,aq,ar,*,local=None,authority=None):
        o=review_dual_registry_generation(
            local_roster=self.roster if local is None else local,
            authority_roster=self.roster if authority is None else authority,
            primary_read=pr,primary_query=pq,
            secondary_read=ar,secondary_query=aq,
        )
        self.assertFalse(o["owner_presence_verified"])
        self.assertFalse(o["trusted_human_owner_consent"])
        self.assertFalse(o["registry_dual_domain_cas_committed"])
        self.assertFalse(o["model_invocation_authorized"])
        self.assertFalse(o["safe_to_resume"])
        self.assertFalse(o["network_called"])
        return o

    def preflight(self,pq,pr,aq,ar,envelope):
        o=review_anchored_rotation_preflight(
            previous_roster=self.roster, proposed_envelope=envelope,
            primary_read=pr,primary_query=pq,
            secondary_read=ar,secondary_query=aq,
            expected_admin_domains=self.domains,
        )
        self.assertFalse(o["registry_write_persisted"])
        self.assertFalse(o["revocation_effective_in_production"])
        return o

    def test_matching_signed_generation_math_only(self):
        p,r,a,s=self.pair()
        result=self.review(p,r,a,s)
        self.assertEqual(result["state"],MATCH)
        self.assertEqual(result["matched_roster_sha256"],roster_sha256(self.roster))
        self.assertTrue(DOMAIN.endswith(b"\x00"))
        self.assertFalse(result["independent_freshness_verified"])

    def test_rotation_is_preflight_only(self):
        p,r,a,s=self.pair()
        e,keys,new=self.rotate()
        o=self.preflight(p,r,a,s,e)
        self.assertEqual(o["state"],TRANSITION)
        self.assertEqual(o["matched_roster_sha256"],roster_sha256(new))
        self.assertFalse(o["registry_write_persisted"])
        self.assertEqual(self.review(p,r,a,s)["state"],MATCH)

    def test_owner_key_rotation_needs_old_owner_approval(self):
        e,keys,new=self.rotate(("HUMAN_OWNER",))
        p,r,a,s=self.pair()
        self.assertEqual(self.preflight(p,r,a,s,e)["state"],TRANSITION)
        forged=deepcopy(e)
        forged["owner_approval_signature_hex"]=keys["HUMAN_OWNER"].sign(
            owner_approval_transcript(new)
        ).hex()
        self.assertEqual(self.preflight(p,r,a,s,forged)["state"],"BLOCKED")

    def test_revocation_removal_blocks_rotation(self):
        p,r,a,s=self.pair()
        e,keys,new=self.rotate(("PRIMARY_WITNESS",))
        altered=deepcopy(new)
        altered["revoked_public_key_sha256"]=[]
        bad=self.owner_envelope(altered,keyset=keys)
        self.assertEqual(self.preflight(p,r,a,s,bad)["state"],"BLOCKED")

    def test_local_rollback_after_two_signed_new_generation_blocks(self):
        e,keys,new=self.rotate()
        p,r,a,s=self.pair(new)
        o=self.review(p,r,a,s,local=self.roster,authority=self.roster)
        self.assertEqual(o["reason"],"LOCAL_REGISTRY_ROLLBACK_BEHIND_SIGNED_HEADS")

    def test_primary_ahead_secondary_stale_blocks(self):
        e,keys,new=self.rotate()
        p,r,a,s=self.pair(new,secondary_roster=self.roster)
        self.assertEqual(self.review(p,r,a,s)["reason"],
                         "PRIMARY_REGISTRY_AHEAD_OF_SECOND_ANCHOR")

    def test_primary_restored_old_but_second_new_blocks(self):
        e,keys,new=self.rotate()
        p,r,a,s=self.pair(self.roster,secondary_roster=new)
        self.assertEqual(self.review(p,r,a,s)["reason"],
                         "PRIMARY_REGISTRY_ROLLBACK")

    def test_fork_same_generation_different_signed_roster_hash_blocks(self):
        p,r,a,s=self.pair()
        fork=deepcopy(s)
        fork["payload"]["roster_sha256"]="f"*64
        fork["signature_hex"]=self.keys["SECONDARY_ANCHOR"].sign(
            canonical_registry_read(fork["payload"])
        ).hex()
        self.assertEqual(self.review(p,r,a,fork)["reason"],
                         "SAME_GENERATION_REGISTRY_FORK")

    def test_revocation_digest_fork_blocks_without_trusting_local(self):
        p,r,a,s=self.pair()
        fork=deepcopy(s)
        fork["payload"]["revoked_set_sha256"]="f"*64
        fork["signature_hex"]=self.keys["SECONDARY_ANCHOR"].sign(
            canonical_registry_read(fork["payload"])
        ).hex()
        self.assertEqual(self.review(p,r,a,fork)["reason"],
                         "SAME_GENERATION_REGISTRY_FORK")

    def test_stale_local_revocations_not_accepted_when_both_heads_new(self):
        e,keys,new=self.rotate()
        p,r,a,s=self.pair(new)
        altered=deepcopy(new)
        altered["revoked_public_key_sha256"]=[]
        self.assertEqual(self.review(p,r,a,s,local=altered)["state"],"BLOCKED")

    def test_signed_challenge_replay_with_new_nonce_blocks(self):
        p,r,a,s=self.pair()
        changed=deepcopy(a)
        changed["challenge_nonce_hex"]="ef"*32
        self.assertEqual(self.review(p,r,changed,s)["reason"],
                         "SECONDARY_READ_SIGNED_CHALLENGE_OR_SCOPE_MISMATCH")

    def test_downgrade_minimum_registry_epoch_blocks(self):
        p,r,a,s=self.pair()
        changed=deepcopy(p)
        changed["minimum_registry_epoch"]=1
        self.assertEqual(self.review(changed,r,a,s)["reason"],
                         "PRIMARY_READ_SIGNED_CHALLENGE_OR_SCOPE_MISMATCH")

    def test_epoch_split_brain_blocks(self):
        p,r,a,s=self.pair()
        changed=deepcopy(s)
        changed["payload"]["registry_epoch"]=5
        changed["signature_hex"]=self.keys["SECONDARY_ANCHOR"].sign(
            canonical_registry_read(changed["payload"])
        ).hex()
        self.assertEqual(self.review(p,r,a,changed)["reason"],
                         "REGISTRY_EPOCH_SPLIT_BRAIN")

    def test_missing_secondary_read_and_bad_signature_blocks(self):
        p,r,a,s=self.pair()
        self.assertEqual(self.review(p,r,a,None)["state"],"BLOCKED")
        broken=deepcopy(s)
        broken["signature_hex"]="0"*128
        self.assertEqual(self.review(p,r,a,broken)["reason"],
                         "SECONDARY_READ_SIGNATURE_MATH_INVALID")

    def test_rotation_from_unanchored_previous_blocks(self):
        p,r,a,s=self.pair()
        e,keys,new=self.rotate()
        broken=deepcopy(s)
        broken["payload"]["generation"]=2
        broken["signature_hex"]=self.keys["SECONDARY_ANCHOR"].sign(
            canonical_registry_read(broken["payload"])
        ).hex()
        self.assertEqual(self.preflight(p,r,a,broken,e)["reason"],
                         "PREVIOUS_REGISTRY_NOT_DOUBLE_ANCHORED")

    def test_genesis_fake_owner_and_both_anchor_pins_pass_math_negative_control(self):
        attack={role:Ed25519PrivateKey.generate() for role in ROLES}
        fakepins={role:pin(attack[role],role) for role in ROLES}
        attacker_roster=self.mkroster(fakepins)
        pq=self.query("PRIMARY_WITNESS")
        aq=self.query("SECONDARY_ANCHOR")
        pr=self.signed("PRIMARY_WITNESS",pq,attacker_roster,
                       key=attack["PRIMARY_WITNESS"])
        ar=self.signed("SECONDARY_ANCHOR",aq,attacker_roster,
                       key=attack["SECONDARY_ANCHOR"])
        out=self.review(pq,pr,aq,ar,local=attacker_roster,
                        authority=attacker_roster)
        self.assertEqual(out["state"],MATCH)
        self.assertFalse(out["trusted_owner_enrollment_verified"])
        self.assertFalse(out["registry_generation_antirollback_production_verified"])

    def test_caller_replaces_both_old_heads_and_roster_can_pass_math(self):
        e,keys,new=self.rotate()
        # Two newer witnesses signed the new state, but attacker can feed
        # a fully restored older roster and both original signed READs.
        p,r,a,s=self.pair()
        self.assertEqual(self.review(p,r,a,s)["state"],MATCH)
        self.assertFalse(self.review(p,r,a,s)[
            "registry_generation_antirollback_production_verified"])

    def test_cross_tenant_service_roles_cannot_swap_signatures(self):
        p,r,a,s=self.pair()
        changed=deepcopy(a)
        changed["tenant_id"]="other"
        self.assertEqual(self.review(p,r,changed,s)["state"],"BLOCKED")
        swapped=self.review(p,s,a,r)
        self.assertEqual(swapped["state"],"BLOCKED")

    def test_invalid_extra_and_missing_authority_fields_block(self):
        p,r,a,s=self.pair()
        for f in s["payload"]:
            with self.subTest(field=f):
                bad=deepcopy(s)
                bad["payload"].pop(f)
                self.assertEqual(self.review(p,r,a,bad)["state"],"BLOCKED")
        extra=deepcopy(s)
        extra["payload"]["request_approved"]=True
        self.assertEqual(self.review(p,r,a,extra)["state"],"BLOCKED")

    def test_proposed_owner_forgery_and_reused_role_key_block(self):
        p,r,a,s=self.pair()
        e,keys,new=self.rotate()
        forged=deepcopy(e)
        forged["owner_approval_signature_hex"]="0"*128
        self.assertEqual(self.preflight(p,r,a,s,forged)["state"],"BLOCKED")
        broken=deepcopy(e)
        broken["roster"]["pins"]["COLLECTOR"]=deepcopy(
            broken["roster"]["pins"]["PRIMARY_WITNESS"]
        )
        self.assertEqual(self.preflight(p,r,a,s,broken)["state"],"BLOCKED")

    def test_no_network_or_cloud_execution_for_math_matches(self):
        p,r,a,s=self.pair()
        with patch("requests.post",side_effect=AssertionError("network")), \
             patch("atlasquant_aion_provider.execute_openai_answer",
                   side_effect=AssertionError("model")):
            self.assertEqual(self.review(p,r,a,s)["state"],MATCH)
        self.assertFalse(self.review(p,r,a,s)["paid_dispatch_performed"])


if __name__=="__main__":
    unittest.main()
