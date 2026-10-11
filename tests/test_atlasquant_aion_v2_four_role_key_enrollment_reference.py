"""Adversarial ephemeral Ed25519 four-role roster reference; zero real keys."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_v2_four_role_key_enrollment_reference import (
    CANDIDATE, FALSE_GATES, ROLES, ROSTER_SCHEMA, PURPOSE, ZERO,
    owner_approval_transcript, role_pop_transcript, roster_sha256,
    review_four_role_roster,
)


def pin(key, role):
    pub=key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {"key_id":"fixture-"+role.lower(),"public_key_hex":pub.hex()}


def fingerprint(pin_value):
    return sha256(bytes.fromhex(pin_value["public_key_hex"])).hexdigest()


class FourRoleEnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.keys={role:Ed25519PrivateKey.generate() for role in ROLES}
        self.pins={role:pin(self.keys[role],role) for role in ROLES}
        self.domains={
            "HUMAN_OWNER":"fixture-personal-device",
            "COLLECTOR":"fixture-isolated-signing-host",
            "PRIMARY_WITNESS":"fixture-cloud-domain-a",
            "SECONDARY_ANCHOR":"fixture-cloud-domain-b",
        }
        self.nonce="ab"*32
        self.initial=self.roster(self.pins)
        self.envelope=self.sign(self.initial,self.keys)

    def roster(self,pins,*,generation=1,previous=ZERO,revoked=None,
               nonce=None,domains=None):
        return {
            "schema":ROSTER_SCHEMA,
            "purpose":PURPOSE,
            "generation":generation,
            "previous_roster_sha256":previous,
            "owner_id":"owner",
            "tenant_id":"tenant",
            "workspace_id":"workspace",
            "challenge_nonce_hex":self.nonce if nonce is None else nonce,
            "pins":deepcopy(pins),
            "admin_domains":deepcopy(
                self.domains if domains is None else domains
            ),
            "revoked_public_key_sha256":sorted(revoked or []),
        }

    def sign(self,roster,keys,*,owner_key=None):
        return {
            "roster":deepcopy(roster),
            "owner_approval_signature_hex":(
                owner_key or keys["HUMAN_OWNER"]
            ).sign(owner_approval_transcript(roster)).hex(),
            "pop_signatures_hex":{
                role:keys[role].sign(role_pop_transcript(roster,role)).hex()
                for role in ROLES
            },
        }

    def review(self,envelope=None,*,generation=1,previous=None,
               trusted_owner=None,nonce=None,domains=None):
        result=review_four_role_roster(
            self.envelope if envelope is None else envelope,
            expected_owner_pin=self.pins["HUMAN_OWNER"] if trusted_owner is None else trusted_owner,
            expected_admin_domains=self.domains if domains is None else domains,
            expected_generation=generation,
            expected_previous_roster=previous,
            expected_owner_id="owner",
            expected_tenant_id="tenant",
            expected_workspace_id="workspace",
            expected_challenge_nonce_hex=self.nonce if nonce is None else nonce,
        )
        for field,value in FALSE_GATES.items():
            self.assertIs(result[field],value,field)
        return result

    def rotate(self,roles=("COLLECTOR",),*,nonce="cd"*32):
        next_keys=dict(self.keys)
        next_pins=deepcopy(self.pins)
        revoked=[]
        for role in roles:
            revoked.append(fingerprint(self.pins[role]))
            next_keys[role]=Ed25519PrivateKey.generate()
            next_pins[role]=pin(next_keys[role],role+"-v2")
        roster=self.roster(
            next_pins,generation=2,previous=roster_sha256(self.initial),
            revoked=revoked,nonce=nonce,
        )
        envelope=self.sign(
            roster,next_keys,owner_key=self.keys["HUMAN_OWNER"],
        )
        return envelope,next_keys,roster

    def test_distinct_genesis_all_four_proofs_math_only(self):
        result=self.review()
        self.assertEqual(result["state"],CANDIDATE)
        self.assertEqual(result["roster_sha256"],roster_sha256(self.initial))
        self.assertFalse(result["physical_key_enrollment_performed"])
        self.assertFalse(result["genesis_owner_identity_verified"])

    def test_genesis_self_signed_attacker_root_math_can_pass_negative_control(self):
        attacker_keys={r:Ed25519PrivateKey.generate() for r in ROLES}
        attacker_pins={r:pin(attacker_keys[r],r) for r in ROLES}
        fake_roster=self.roster(attacker_pins)
        fake_envelope=self.sign(fake_roster,attacker_keys)
        result=self.review(
            fake_envelope,trusted_owner=attacker_pins["HUMAN_OWNER"],
        )
        self.assertEqual(result["state"],CANDIDATE)
        self.assertFalse(result["public_key_registry_protected"])
        self.assertFalse(result["trusted_human_owner_consent"])

    def test_switch_or_reuse_key_across_roles_rejected_even_if_resigned(self):
        p=deepcopy(self.pins)
        p["COLLECTOR"]=deepcopy(p["HUMAN_OWNER"])
        p["COLLECTOR"]["key_id"]="fixture-collector-colliding"
        r=self.roster(p)
        self.assertEqual(self.review({"roster":r,
              "owner_approval_signature_hex":"0"*128,
              "pop_signatures_hex":{}},)["reason"],
              "KEY_ROLE_REUSE_OR_INVALID_PIN")

    def test_duplicate_admin_domain_claim_is_blocked(self):
        d=deepcopy(self.domains)
        d["SECONDARY_ANCHOR"]=d["PRIMARY_WITNESS"]
        self.assertEqual(self.review(domains=d)["reason"],
                         "TRUSTED_REFERENCE_INPUTS_INVALID")
        r=self.roster(self.pins,domains=d)
        self.assertEqual(self.review(self.sign(r,self.keys))["state"],"BLOCKED")

    def test_genesis_wrong_previous_hash_or_generation_blocked(self):
        for f,v in (
            ("previous_roster_sha256","f"*64),
            ("generation",2),
            ("revoked_public_key_sha256",["f"*64]),
        ):
            with self.subTest(field=f):
                r=deepcopy(self.initial)
                r[f]=v
                e=self.sign(r,self.keys)
                self.assertEqual(self.review(e)["state"],"BLOCKED")

    def test_witness_pop_replaced_with_another_role_signature_fails(self):
        e=deepcopy(self.envelope)
        e["pop_signatures_hex"]["PRIMARY_WITNESS"]=e[
            "pop_signatures_hex"]["COLLECTOR"]
        self.assertEqual(self.review(e)["reason"],
                         "ROLE_PROOF_OF_POSSESSION_INVALID")

    def test_missing_pop_and_owner_approval_signature_rejected(self):
        e=deepcopy(self.envelope)
        e["pop_signatures_hex"].pop("SECONDARY_ANCHOR")
        self.assertEqual(self.review(e)["reason"],"ALL_FOUR_ROLE_PROOFS_REQUIRED")
        e=deepcopy(self.envelope)
        e["owner_approval_signature_hex"]="0"*128
        self.assertEqual(self.review(e)["reason"],
                         "PRIOR_OWNER_SIGNATURE_MATH_INVALID")

    def test_signed_challenge_replay_and_modified_scope_rejected(self):
        self.assertEqual(self.review(nonce="cd"*32)["state"],"BLOCKED")
        r=deepcopy(self.initial)
        r["workspace_id"]="another-workspace"
        self.assertEqual(self.review(self.sign(r,self.keys))["state"],"BLOCKED")
        r=deepcopy(self.initial)
        r["admin_domains"]["PRIMARY_WITNESS"]="attacker-cloud"
        self.assertEqual(self.review(self.sign(r,self.keys))["state"],"BLOCKED")

    def test_successful_collector_rotation_requires_old_owner_and_revocation(self):
        e,keys,r=self.rotate()
        result=self.review(e,generation=2,previous=self.initial,
                           nonce="cd"*32)
        self.assertEqual(result["state"],CANDIDATE)
        self.assertIn(fingerprint(self.pins["COLLECTOR"]),
                      r["revoked_public_key_sha256"])
        self.assertFalse(result["revocation_replicated_to_witnesses"])

    def test_owner_rotation_requires_prior_owner_and_new_owner_pop(self):
        e,keys,r=self.rotate(("HUMAN_OWNER",))
        self.assertEqual(self.review(
            e,generation=2,previous=self.initial,nonce="cd"*32
        )["state"],CANDIDATE)
        forged=self.sign(r,keys)  # NEW owner approving without old root
        self.assertEqual(self.review(
            forged,generation=2,previous=self.initial,nonce="cd"*32
        )["reason"],"PRIOR_OWNER_SIGNATURE_MATH_INVALID")

    def test_replaced_old_key_not_revoked_must_block(self):
        e,keys,r=self.rotate(("SECONDARY_ANCHOR",))
        r["revoked_public_key_sha256"]=[]
        e=self.sign(r,keys)
        self.assertEqual(self.review(
            e,generation=2,previous=self.initial,nonce="cd"*32
        )["reason"],"PREVIOUS_OR_REPLACED_KEY_NOT_REVOKED")

    def test_rotated_key_replay_as_another_role_fails(self):
        e,keys,r=self.rotate()
        r["pins"]["PRIMARY_WITNESS"]=deepcopy(r["pins"]["COLLECTOR"])
        e=self.sign(r,keys)
        self.assertEqual(self.review(
            e,generation=2,previous=self.initial,nonce="cd"*32
        )["reason"],"KEY_ROLE_REUSE_OR_INVALID_PIN")

    def test_same_keys_new_generation_refused_as_empty_rotation(self):
        roster=self.roster(
            self.pins,generation=2,previous=roster_sha256(self.initial),
            nonce="cd"*32,
        )
        e=self.sign(roster,self.keys)
        self.assertEqual(self.review(
            e,generation=2,previous=self.initial,nonce="cd"*32
        )["reason"],"NO_KEY_ROTATION_IN_NEW_GENERATION")

    def test_generation_downgrade_and_wrong_prior_roster_blocked(self):
        e,keys,r=self.rotate()
        prior=deepcopy(self.initial)
        prior["challenge_nonce_hex"]="bb"*32
        self.assertEqual(self.review(
            e,generation=2,previous=prior,nonce="cd"*32
        )["state"],"BLOCKED")
        self.assertEqual(self.review(
            e,generation=3,previous=self.initial,nonce="cd"*32
        )["state"],"BLOCKED")
        self.assertEqual(self.review(
            e,generation=2,previous=None,nonce="cd"*32
        )["state"],"BLOCKED")

    def test_authority_flag_and_unknown_field_injection_fail(self):
        r=deepcopy(self.initial)
        r["safe_to_resume"]=True
        self.assertEqual(self.review(self.sign_fail_placeholder(r))["state"],
                         "BLOCKED")
        for field in self.initial:
            with self.subTest(field=field):
                bad=deepcopy(self.envelope)
                bad["roster"].pop(field)
                self.assertEqual(self.review(bad)["state"],"BLOCKED")

    def sign_fail_placeholder(self,r):
        return {
            "roster":r,
            "owner_approval_signature_hex":"0"*128,
            "pop_signatures_hex":{},
        }

    def test_unsupported_role_or_wrong_domain_signature_never_authorized(self):
        with self.assertRaises(ValueError):
            role_pop_transcript(self.initial,"ADMIN")
        self.assertFalse(self.review()["model_invocation_authorized"])

    def test_no_network_private_key_generation_or_writes_in_production_module(self):
        with patch("requests.post",side_effect=AssertionError("network")), \
             patch("atlasquant_aion_provider.execute_openai_answer",
                   side_effect=AssertionError("provider")):
            self.assertEqual(self.review()["state"],CANDIDATE)
        self.assertFalse(self.review()["network_called"])

    def test_malformed_pin_types_revocations_and_boolean_generation_blocked(self):
        self.assertEqual(self.review(generation=True)["state"],"BLOCKED")
        r=deepcopy(self.initial)
        r["revoked_public_key_sha256"]=["b"*64,"a"*64]
        self.assertEqual(self.review(self.sign(r,self.keys))["state"],"BLOCKED")
        r=deepcopy(self.initial)
        r["pins"]["COLLECTOR"]["public_key_hex"]=True
        self.assertEqual(self.review(self.sign_fail_placeholder(r))["state"],
                         "BLOCKED")


if __name__ == "__main__":
    unittest.main()
