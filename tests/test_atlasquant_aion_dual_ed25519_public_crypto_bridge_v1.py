"""Ephemeral disposable-CI Ed25519 test key pairs ONLY, never owner keys.

Each private key exists in this runner's process memory solely to sign
synthetic test-vector role hashes. No private key bytes are exported,
logged, stored, uploaded, enrolled or present in production modules.
"""
from __future__ import annotations

import copy
import hashlib
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

import atlasquant_aion_dual_ed25519_public_crypto_bridge_v1 as bridge
from atlasquant_aion_independent_ed25519_trirole_bridge_contract_v1 import (
    SCHEMA as PROPOSAL_SCHEMA, build_unsigned_three_role_challenge,
)

OWNER_ROLE = "HUMAN_OWNER_ED25519"
COLLECTOR_ROLE = "COLLECTOR_ED25519"
HOST_ROLE = "HOST_ECDSA_P256"
NONCE = "ba" * 32


def digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


class DisposablePair:
    def __init__(self):
        # CI-only, volatile, never exported or written. Not an AION key.
        self._private = Ed25519PrivateKey.generate()
        self.public_bytes = self._private.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw)
        self.public_hex = self.public_bytes.hex()
        self.fingerprint = digest(self.public_bytes)

    def sign_intent(self, intent: dict) -> str:
        msg=bytes.fromhex(intent["unsigned_message_sha256"][7:])
        return self._private.sign(msg).hex()


class DualEd25519MathematicalBridgeTests(unittest.TestCase):
    def setUp(self):
        self.owner = DisposablePair()
        self.collector = DisposablePair()
        self.proposal = {
            "schema": PROPOSAL_SCHEMA,
            "owner": {
                "role": OWNER_ROLE, "algorithm":"Ed25519",
                "public_key_sha256": self.owner.fingerprint,
                "custody_boundary":"OWNER_HELD_INDEPENDENT_DEVICE_CANDIDATE",
                "custodian_id":"ci-owner-example-01",
                "verification_state":"NOT_CRYPTOGRAPHICALLY_VERIFIED",
            },
            "collector": {
                "role": COLLECTOR_ROLE, "algorithm":"Ed25519",
                "public_key_sha256": self.collector.fingerprint,
                "custody_boundary":"SEPARATE_COLLECTOR_SIGNER_DOMAIN_CANDIDATE",
                "custodian_id":"ci-collector-example-01",
                "verification_state":"NOT_CRYPTOGRAPHICALLY_VERIFIED",
            },
            "host": {
                "role": HOST_ROLE, "algorithm":"ECDSA_P256_SHA256",
                "public_key_sha256":"sha256:"+"c"*64,
                "custody_boundary":"WINDOWS_PLATFORM_TPM_P256_CANDIDATE_UNATTESTED",
                "custodian_id":"ci-host-example-01",
                "verification_state":"NOT_CRYPTOGRAPHICALLY_VERIFIED",
            },
            "collector_binary_sha256":"sha256:"+"d"*64,
            "policy_sha256":"sha256:"+"e"*64,
            "policy_generation":7,
            "estimated_monthly_brl":0,
        }

    def payload(self, *, nonce=NONCE, proposal=None):
        proposal = copy.deepcopy(self.proposal) if proposal is None else copy.deepcopy(proposal)
        plan=build_unsigned_three_role_challenge(proposal,nonce)
        self.assertEqual(plan["state"],"THREE_UNSIGNED_ROLE_CHALLENGES_UNTRUSTED")
        return {
            "proposal":proposal,"nonce":nonce,
            "owner_public_key_hex":self.owner.public_hex,
            "collector_public_key_hex":self.collector.public_hex,
            "owner_signature_hex":self.owner.sign_intent(
                plan["role_messages"][OWNER_ROLE]),
            "collector_signature_hex":self.collector.sign_intent(
                plan["role_messages"][COLLECTOR_ROLE]),
        }

    def check(self, payload):
        return bridge.verify_dual_ed25519_public_signatures_untrusted(**payload)

    def assert_no_authority(self,result):
        for field in bridge._FALSE_GATES:
            self.assertIs(result[field],False,field)
        self.assertIs(result["not_an_enrollment_or_replay_protection_proof"],True)
        self.assertFalse(result["installer_authorized"])
        self.assertFalse(result["safe_to_resume"])

    def test_two_valid_distinct_role_signatures_pass_math_only(self):
        result=self.check(self.payload())
        self.assertEqual(result["state"],bridge.CANDIDATE,result)
        self.assertTrue(result["owner_signature_mathematically_valid"])
        self.assertTrue(result["collector_signature_mathematically_valid"])
        self.assertTrue(result["proposal_fingerprints_match_public_keys_untrusted"])
        self.assert_no_authority(result)

    def test_digest_domains_are_different(self):
        result=self.check(self.payload())
        self.assertNotEqual(result["owner_intent_sha256"],result["collector_intent_sha256"])
        self.assertRegex(result["canonical_transcript_sha256"],r"^sha256:[0-9a-f]{64}$")
        self.assert_no_authority(result)

    def test_valid_mathematical_owner_is_not_authenticated_owner(self):
        result=self.check(self.payload())
        self.assertTrue(result["owner_signature_mathematically_valid"])
        self.assertFalse(result["human_owner_identity_authenticated"])
        self.assertFalse(result["trusted_owner_public_key_pinned"])
        self.assertFalse(result["owner_authorization_for_execution"])
        self.assert_no_authority(result)

    def test_valid_two_signatures_not_independent_custody_proof(self):
        result=self.check(self.payload())
        self.assertFalse(result["independent_signer_custody_verified"])
        self.assertFalse(result["key_enrollment_verified"])
        self.assertFalse(result["signed_collector_witness_approved"])
        self.assert_no_authority(result)

    def test_host_p256_remains_unattested(self):
        result=self.check(self.payload())
        for field in ("tpm_p256_key_present","p256_host_signature_verified",
                      "p256_tpm_origin_attested","p256_nonexportability_verified",
                      "independent_host_identity_attested"):
            self.assertFalse(result[field])
        self.assert_no_authority(result)

    def test_owner_signature_tampered_rejected(self):
        p=self.payload()
        sig=p["owner_signature_hex"]
        p["owner_signature_hex"]=("0" if sig[0]!="0" else "1")+sig[1:]
        r=self.check(p)
        self.assertEqual(r["reason"],"OWNER_ED25519_SIGNATURE_INVALID")
        self.assertFalse(r["owner_signature_mathematically_valid"])
        self.assert_no_authority(r)

    def test_collector_signature_tampered_rejected(self):
        p=self.payload()
        sig=p["collector_signature_hex"]
        p["collector_signature_hex"]=("0" if sig[0]!="0" else "1")+sig[1:]
        r=self.check(p)
        self.assertEqual(r["reason"],"COLLECTOR_ED25519_SIGNATURE_INVALID")
        self.assertFalse(r["collector_signature_mathematically_valid"])
        self.assert_no_authority(r)

    def test_swapped_signatures_rejected(self):
        p=self.payload()
        p["owner_signature_hex"],p["collector_signature_hex"]=(
            p["collector_signature_hex"],p["owner_signature_hex"])
        r=self.check(p)
        self.assertEqual(r["state"],"BLOCKED")
        self.assert_no_authority(r)

    def test_swapped_public_keys_rejected_against_proposal(self):
        p=self.payload()
        p["owner_public_key_hex"],p["collector_public_key_hex"]=(
            p["collector_public_key_hex"],p["owner_public_key_hex"])
        r=self.check(p)
        self.assertEqual(r["reason"],"PROPOSAL_PUBLIC_KEY_FINGERPRINT_MISMATCH")
        self.assert_no_authority(r)

    def test_same_public_key_for_both_roles_rejected(self):
        p=self.payload()
        p["collector_public_key_hex"]=p["owner_public_key_hex"]
        r=self.check(p)
        self.assertEqual(r["reason"],"DUPLICATE_OWNER_COLLECTOR_PUBLIC_KEY")
        self.assert_no_authority(r)

    def test_owner_signature_cannot_satisfy_collector_role(self):
        p=self.payload()
        p["collector_signature_hex"]=p["owner_signature_hex"]
        r=self.check(p)
        self.assertEqual(r["reason"],"COLLECTOR_ED25519_SIGNATURE_INVALID")
        self.assert_no_authority(r)

    def test_signing_host_role_digest_with_ed25519_not_owner_approval(self):
        p=self.payload()
        plan=build_unsigned_three_role_challenge(self.proposal,NONCE)
        p["owner_signature_hex"]=self.owner.sign_intent(plan["role_messages"][HOST_ROLE])
        r=self.check(p)
        self.assertEqual(r["reason"],"OWNER_ED25519_SIGNATURE_INVALID")
        self.assert_no_authority(r)

    def test_nonce_changed_after_signatures_rejected(self):
        p=self.payload()
        p["nonce"]="bb"*32
        r=self.check(p)
        self.assertEqual(r["reason"],"OWNER_ED25519_SIGNATURE_INVALID")
        self.assert_no_authority(r)

    def test_same_signed_nonce_is_replayable_in_this_untrusted_verifier(self):
        p=self.payload()
        a=self.check(p)
        b=self.check(p)
        self.assertEqual(a["state"],bridge.CANDIDATE)
        self.assertEqual(b["state"],bridge.CANDIDATE)
        self.assertFalse(b["durable_nonce_issued_and_consumed"])
        self.assertFalse(b["replay_protection_verified"])
        self.assert_no_authority(b)

    def test_policy_digest_mutation_after_signatures_rejected(self):
        p=self.payload()
        q=copy.deepcopy(p)
        q["proposal"]["policy_sha256"]="sha256:"+"f"*64
        r=self.check(q)
        self.assertEqual(r["reason"],"OWNER_ED25519_SIGNATURE_INVALID")
        self.assert_no_authority(r)

    def test_policy_generation_mutation_after_signatures_rejected(self):
        p=self.payload()
        q=copy.deepcopy(p)
        q["proposal"]["policy_generation"]=8
        r=self.check(q)
        self.assertEqual(r["reason"],"OWNER_ED25519_SIGNATURE_INVALID")
        self.assert_no_authority(r)

    def test_collector_binary_hash_mutation_rejected(self):
        p=self.payload()
        q=copy.deepcopy(p)
        q["proposal"]["collector_binary_sha256"]="sha256:"+"0"*64
        r=self.check(q)
        self.assertEqual(r["reason"],"OWNER_ED25519_SIGNATURE_INVALID")
        self.assert_no_authority(r)

    def test_host_public_key_fingerprint_mutation_rejected(self):
        p=self.payload()
        q=copy.deepcopy(p)
        q["proposal"]["host"]["public_key_sha256"]="sha256:"+"a"*64
        r=self.check(q)
        self.assertEqual(r["reason"],"OWNER_ED25519_SIGNATURE_INVALID")
        self.assert_no_authority(r)

    def test_forged_owner_public_key_claim_rejected(self):
        p=self.payload()
        q=copy.deepcopy(p)
        q["proposal"]["owner"]["public_key_sha256"]="sha256:"+"f"*64
        r=self.check(q)
        self.assertEqual(r["reason"],"PROPOSAL_PUBLIC_KEY_FINGERPRINT_MISMATCH")
        self.assert_no_authority(r)

    def test_forged_collector_public_key_claim_rejected(self):
        p=self.payload()
        q=copy.deepcopy(p)
        q["proposal"]["collector"]["public_key_sha256"]="sha256:"+"f"*64
        r=self.check(q)
        self.assertEqual(r["reason"],"PROPOSAL_PUBLIC_KEY_FINGERPRINT_MISMATCH")
        self.assert_no_authority(r)

    def test_forged_trusted_enrollment_flags_rejected(self):
        for flag in ("owner_identity_authenticated","trusted_key_enrolled",
                     "installer_authorized","host_tpm_attested"):
            p=self.payload()
            p["proposal"][flag]=True
            with self.subTest(flag=flag):
                r=self.check(p)
                self.assertEqual(r["reason"],"PROPOSAL_OR_CHALLENGE_NOT_VALIDATED")
                self.assert_no_authority(r)

    def test_self_claimed_verified_custody_rejected(self):
        p=self.payload()
        p["proposal"]["owner"]["verification_state"]="VERIFIED"
        r=self.check(p)
        self.assertEqual(r["state"],"BLOCKED")
        self.assert_no_authority(r)

    def test_shared_custodian_id_rejected(self):
        p=self.payload()
        p["proposal"]["collector"]["custodian_id"]=p["proposal"]["owner"]["custodian_id"]
        r=self.check(p)
        self.assertEqual(r["state"],"BLOCKED")
        self.assert_no_authority(r)

    def test_swapped_role_fingerprints_in_proposal_rejected(self):
        p=self.payload()
        x=p["proposal"]
        x["owner"]["public_key_sha256"],x["collector"]["public_key_sha256"]=(
            x["collector"]["public_key_sha256"],x["owner"]["public_key_sha256"])
        r=self.check(p)
        self.assertEqual(r["reason"],"PROPOSAL_PUBLIC_KEY_FINGERPRINT_MISMATCH")
        self.assert_no_authority(r)

    def test_malformed_hex_input_rejected(self):
        for field,bad in (
            ("owner_public_key_hex",None),
            ("collector_public_key_hex",True),
            ("owner_public_key_hex","00"),
            ("collector_public_key_hex","F"*64),
            ("owner_signature_hex","ab"),
            ("collector_signature_hex","G"*128),
            ("owner_signature_hex","a"*127),
            ("collector_signature_hex","a"*129),
            ("owner_public_key_hex",0),
        ):
            with self.subTest(field=field,bad=bad):
                p=self.payload()
                p[field]=bad
                r=self.check(p)
                self.assertEqual(r["reason"],"MALFORMED_DUAL_SIGNATURE_REQUEST")
                self.assert_no_authority(r)

    def test_invalid_nonce_rejected_without_crypto(self):
        for nonce in (None,True,0,"A"*64,"a"*63,"z"*64,"ba"*33):
            with self.subTest(nonce=nonce):
                p=self.payload()
                p["nonce"]=nonce
                r=self.check(p)
                self.assertEqual(r["reason"],"PROPOSAL_OR_CHALLENGE_NOT_VALIDATED")
                self.assert_no_authority(r)

    def test_role_substitution_to_host_p256_rejected(self):
        p=self.payload()
        p["proposal"]["collector"]["algorithm"]="ECDSA_P256_SHA256"
        r=self.check(p)
        self.assertEqual(r["state"],"BLOCKED")
        self.assert_no_authority(r)

    def test_no_p256_signature_can_replace_missing_owner_signature(self):
        p=self.payload()
        p["owner_signature_hex"]="0"*128
        r=self.check(p)
        self.assertEqual(r["reason"],"OWNER_ED25519_SIGNATURE_INVALID")
        self.assert_no_authority(r)

    def test_p256_signed_flag_extra_field_rejected(self):
        p=self.payload()
        p["proposal"]["host"]["signature_verified"]=True
        r=self.check(p)
        self.assertEqual(r["state"],"BLOCKED")
        self.assert_no_authority(r)

    def test_cannot_claim_approval_on_disposable_ci_signatures(self):
        r=self.check(self.payload())
        for k in ("owner_authorization_for_execution","collector_launch_authorized",
                  "key_creation_authorized","key_enrollment_authorized",
                  "installer_authorized","build_authorized",
                  "deploy_authorized","safe_to_resume"):
            self.assertIs(r[k],False)
        self.assert_no_authority(r)

    def test_no_signatures_or_private_keys_leak_in_sanitized_result(self):
        p=self.payload()
        r=self.check(p)
        self.assertNotIn(p["owner_signature_hex"],str(r))
        self.assertNotIn(p["collector_signature_hex"],str(r))
        self.assertNotIn(p["owner_public_key_hex"],str(r))
        self.assertNotIn(p["collector_public_key_hex"],str(r))
        self.assert_no_authority(r)

    def test_absent_proposal_rejected(self):
        p=self.payload()
        for value in (None,{},[],"signed",True,0):
            with self.subTest(value=value):
                q=dict(p,proposal=value)
                r=self.check(q)
                self.assertEqual(r["state"],"BLOCKED")
                self.assert_no_authority(r)

    def test_budget_constraint_preserved(self):
        p=self.payload()
        p["proposal"]["estimated_monthly_brl"]=201
        r=self.check(p)
        self.assertEqual(r["reason"],"PROPOSAL_OR_CHALLENGE_NOT_VALIDATED")
        self.assert_no_authority(r)


if __name__ == "__main__":
    unittest.main()
