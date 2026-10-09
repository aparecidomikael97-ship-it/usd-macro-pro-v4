"""RFC 8032 Section 7.1 test vectors, public verification only.

The official test SECRET KEY data is NOT included and NO private keys
are generated, imported, enrolled, created or signed in this test suite.
Only RFC PUBLIC KEY, MESSAGE and SIGNATURE bytes are used.
"""
from __future__ import annotations

import hashlib
import unittest

import atlasquant_aion_ed25519_public_verify_p256_attestation_review_v1 as mod
import atlasquant_aion_independent_ed25519_trirole_bridge_contract_v1 as tri

# RFC8032 §7.1 TEST 1: empty message, PUBLIC KEY and detached signature.
PUB1 = "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
MSG1 = ""
SIG1 = (
    "e5564300c360ac729086e2cc806e828a"
    "84877f1eb8e5d974d873e06522490155"
    "5fb8821590a33bacc61e39701cf9b46b"
    "d25bf5f0595bbe24655141438e7a100b"
)
# RFC8032 §7.1 TEST 2: one-byte message, different public key/signature.
PUB2 = "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c"
MSG2 = "72"
SIG2 = (
    "92a009a9f0d4cab8720e820b5f642540"
    "a2b27b5416503f8fb3762223ebdb69da"
    "085ac1e43e15996e458f3613d0f11d8c"
    "387b2eaeb4302aeeb00d291612bb0c00"
)
# RFC8032 §7.1 TEST 3: two-byte message, third key.
PUB3 = "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025"
MSG3 = "af82"
SIG3 = (
    "6291d657deec24024827e69c3abe01a3"
    "0ce548a284743a445e3680d7db5ac3ac"
    "18ff9b538d16f290ae67f760984dc659"
    "4a7c15e9716ed28dc027beceea1ec40a"
)


_AUTO_CLAIM = object()


def verify(pub=PUB1, sig=SIG1, msg=MSG1,
           role="HUMAN_OWNER_ED25519",
           public_claim=_AUTO_CLAIM, message_claim=_AUTO_CLAIM):
    # Explicit invalid None MUST NOT be substituted with a valid fixture.
    if public_claim is _AUTO_CLAIM:
        public_claim="sha256:"+hashlib.sha256(bytes.fromhex(pub)).hexdigest()
    if message_claim is _AUTO_CLAIM:
        message_claim="sha256:"+hashlib.sha256(bytes.fromhex(msg)).hexdigest()
    return mod.verify_ed25519_public_signature(
        role=role, public_key_hex=pub, signature_hex=sig, message_hex=msg,
        claimed_public_key_sha256=public_claim,
        claimed_message_sha256=message_claim,
    )


class RFC8032PublicVerificationTests(unittest.TestCase):
    def no_auth(self, result):
        for name,value in mod._ALWAYS_FALSE.items():
            self.assertIs(result[name],False,name)

    def test_rfc8032_official_test1_empty_message_valid(self):
        out=verify()
        self.assertEqual(out["state"],"PUBLIC_KEY_SIGNATURE_MATHEMATICALLY_VALID_UNTRUSTED")
        self.assertTrue(out["signature_mathematically_valid"])
        self.assertTrue(out["public_key_fingerprint_matched_claim"])
        self.no_auth(out)

    def test_rfc8032_official_test2_single_byte_valid(self):
        out=verify(PUB2,SIG2,MSG2,"COLLECTOR_ED25519")
        self.assertTrue(out["signature_mathematically_valid"],out)
        self.no_auth(out)

    def test_rfc8032_official_test3_two_byte_valid(self):
        out=verify(PUB3,SIG3,MSG3)
        self.assertTrue(out["signature_mathematically_valid"],out)
        self.no_auth(out)

    def test_valid_signature_is_not_owner_attestation(self):
        out=verify()
        self.assertTrue(out["signature_mathematically_valid"])
        self.assertFalse(out["owner_identity_authenticated"])
        self.assertFalse(out["public_key_pinning_trusted"])
        self.assertFalse(out["owner_approval_authorized"])
        self.no_auth(out)

    def test_valid_signature_is_not_collector_custody_attestation(self):
        out=verify(PUB2,SIG2,MSG2,"COLLECTOR_ED25519")
        self.assertTrue(out["signature_mathematically_valid"])
        self.assertFalse(out["independent_custody_verified"])
        self.assertFalse(out["collector_identity_authenticated"])
        self.no_auth(out)

    def test_key_swapping_fails(self):
        for pub,msg,sig in ((PUB2,MSG1,SIG1),(PUB1,MSG2,SIG2),(PUB3,MSG2,SIG2)):
            with self.subTest(pub=pub[:8]):
                out=verify(pub,sig,msg)
                self.assertFalse(out["signature_mathematically_valid"])
                self.assertEqual(out["state"],"BLOCKED")
                self.no_auth(out)

    def test_message_tampering_fails(self):
        for msg in ("00","01","72","ff","af82"):
            with self.subTest(msg=msg):
                out=verify(PUB1,SIG1,msg)
                self.assertFalse(out["signature_mathematically_valid"])
                self.no_auth(out)

    def test_signature_bitflip_fails(self):
        damaged="f" + SIG1[1:]
        out=verify(PUB1,damaged,MSG1)
        self.assertEqual(out["reason"],"SIGNATURE_VERIFICATION_FAILED")
        self.no_auth(out)

    def test_false_public_key_claim_fails_before_crypto(self):
        out=verify(public_claim="sha256:"+"f"*64)
        self.assertEqual(out["reason"],"CALLER_CLAIMED_FINGERPRINT_MISMATCH")
        self.no_auth(out)

    def test_false_message_claim_fails_before_crypto(self):
        out=verify(message_claim="sha256:"+"f"*64)
        self.assertEqual(out["reason"],"CALLER_CLAIMED_FINGERPRINT_MISMATCH")
        self.no_auth(out)

    def test_reject_wrong_algorithm_role(self):
        for role in ("HOST_ECDSA_P256","OWNER_P256","RSA_PSS",None,True,0,""):
            with self.subTest(role=role):
                out=verify(role=role)
                self.assertEqual(out["state"],"BLOCKED")
                self.no_auth(out)

    def test_bad_public_key_input_fails_closed(self):
        for bad in (None,1,True,"00","G"*64,"a"*63,"a"*65,PUB1.upper()):
            with self.subTest(bad=bad):
                out=mod.verify_ed25519_public_signature(
                    role="HUMAN_OWNER_ED25519",public_key_hex=bad,
                    signature_hex=SIG1,message_hex=MSG1,
                    claimed_public_key_sha256="sha256:"+"0"*64,
                    claimed_message_sha256="sha256:"+"0"*64)
                self.assertEqual(out["state"],"BLOCKED")
                self.no_auth(out)

    def test_signature_length_and_nonhex_rejected(self):
        for sig in (None,"",True,"F"*128,"a"*127,"a"*129,"z"*128,"aa"*65):
            with self.subTest(sig=sig):
                out=mod.verify_ed25519_public_signature(
                    role="HUMAN_OWNER_ED25519",public_key_hex=PUB1,
                    signature_hex=sig,message_hex=MSG1,
                    claimed_public_key_sha256="sha256:"+hashlib.sha256(bytes.fromhex(PUB1)).hexdigest(),
                    claimed_message_sha256="sha256:"+hashlib.sha256(b"").hexdigest())
                self.assertEqual(out["state"],"BLOCKED")
                self.no_auth(out)

    def test_odd_or_uppercase_message_hex_denied(self):
        for msg in ("a","ABC","X"*4,True,None,123,"a"*8194):
            with self.subTest(msg=str(msg)[:16]):
                out=mod.verify_ed25519_public_signature(
                    role="HUMAN_OWNER_ED25519",public_key_hex=PUB1,
                    signature_hex=SIG1,message_hex=msg,
                    claimed_public_key_sha256="sha256:"+hashlib.sha256(bytes.fromhex(PUB1)).hexdigest(),
                    claimed_message_sha256="sha256:"+hashlib.sha256(b"").hexdigest())
                self.assertEqual(out["state"],"BLOCKED")
                self.no_auth(out)

    def test_strict_public_fingerprint_shapes(self):
        for value in (None,0,True,"0"*64,"sha256:"+"A"*64,"sha256:"+"a"*65):
            out=verify(public_claim=value)
            self.assertEqual(out["state"],"BLOCKED")
            self.no_auth(out)

    def test_strict_message_fingerprint_shapes(self):
        for value in (None,0,True,"0"*64,"sha256:"+"A"*64,"sha256:"+"a"*65):
            out=verify(message_claim=value)
            self.assertEqual(out["state"],"BLOCKED")
            self.no_auth(out)

    def test_public_key_hash_claim_not_independent_trust_anchor(self):
        out=verify()
        self.assertTrue(out["public_key_fingerprint_matched_claim"])
        self.assertFalse(out["public_key_pinning_trusted"])
        self.no_auth(out)

    def test_rfc_valid_message_not_role_bound_transcript(self):
        out=verify()
        self.assertTrue(out["signature_mathematically_valid"])
        self.assertFalse(out["nonce_freshness_durably_verified"])
        self.assertFalse(out["anti_replay_durably_verified"])
        self.no_auth(out)

    def test_role_intent_valid_shape_with_wrong_rfc_signature_fails(self):
        intent={
            "algorithm":"Ed25519",
            "role_domain":"AION_OWNER_APPROVAL_V1",
            "unsigned_message_sha256":"sha256:"+"a"*64,
            "signature_present":False,"signature_verified":False,
        }
        out=mod.verify_role_bound_digest_signature(
            role="HUMAN_OWNER_ED25519",public_key_hex=PUB1,
            signature_hex=SIG1,role_intent=intent,
            claimed_public_key_sha256="sha256:"+hashlib.sha256(bytes.fromhex(PUB1)).hexdigest())
        self.assertEqual(out["state"],"BLOCKED")
        self.assertEqual(out["reason"],"SIGNATURE_VERIFICATION_FAILED")
        self.no_auth(out)

    def test_role_intent_fails_cross_role_domain_confusion(self):
        intent={
            "algorithm":"Ed25519",
            "role_domain":"AION_COLLECTOR_INDEPENDENT_WITNESS_V1",
            "unsigned_message_sha256":"sha256:"+"a"*64,
            "signature_present":False,"signature_verified":False,
        }
        out=mod.verify_role_bound_digest_signature(
            role="HUMAN_OWNER_ED25519",public_key_hex=PUB2,
            signature_hex=SIG2,role_intent=intent,
            claimed_public_key_sha256="sha256:"+hashlib.sha256(bytes.fromhex(PUB2)).hexdigest())
        self.assertEqual(out["reason"],"INVALID_ROLE_INTENT_OR_SIGNATURE_REQUEST")
        self.no_auth(out)

    def test_role_intent_fake_signature_verified_claim_denied(self):
        intent={
            "algorithm":"Ed25519","role_domain":"AION_OWNER_APPROVAL_V1",
            "unsigned_message_sha256":"sha256:"+"a"*64,
            "signature_present":True,"signature_verified":True,
        }
        out=mod.verify_role_bound_digest_signature(
            role="HUMAN_OWNER_ED25519",public_key_hex=PUB1,
            signature_hex=SIG1,role_intent=intent,
            claimed_public_key_sha256="sha256:"+hashlib.sha256(bytes.fromhex(PUB1)).hexdigest())
        self.assertEqual(out["state"],"BLOCKED")
        self.no_auth(out)

    def test_role_intent_fails_extra_install_permission(self):
        intent={
            "algorithm":"Ed25519","role_domain":"AION_OWNER_APPROVAL_V1",
            "unsigned_message_sha256":"sha256:"+"a"*64,
            "signature_present":False,"signature_verified":False,
            "installer_authorized":True,
        }
        out=mod.verify_role_bound_digest_signature(
            role="HUMAN_OWNER_ED25519",public_key_hex=PUB1,
            signature_hex=SIG1,role_intent=intent,
            claimed_public_key_sha256="sha256:"+hashlib.sha256(bytes.fromhex(PUB1)).hexdigest())
        self.assertEqual(out["state"],"BLOCKED")
        self.no_auth(out)

    def test_untrusted_p256_evidence_never_attests(self):
        for evidence in (None,True,{},{"signed":True}, {"EKcert_valid":True,"tpm":True}):
            with self.subTest(evidence=evidence):
                out=mod.review_p256_hardware_attestation_requirements(purported_evidence=evidence)
                self.assertEqual(out["state"],"HARDWARE_ATTESTATION_UNIMPLEMENTED_BLOCKED")
                self.assertFalse(out["p256_tpm_origin_verified"])
                self.assertFalse(out["p256_private_key_nonexportability_verified"])
                self.assertFalse(out["host_binding_verified"])
                self.assertFalse(out["installer_authorized"])

    def test_p256_atestation_has_nine_or_more_independent_gates(self):
        out=mod.review_p256_hardware_attestation_requirements()
        self.assertGreaterEqual(len(out["evidence_checks_required"]),9)
        self.assertEqual(len(out["evidence_checks_required"]),
                         len(set(out["evidence_checks_required"])))
        self.assertIn("TPM2_CERTIFY_FOR_EXACT_P256_PUBLIC_KEY",
                      out["evidence_checks_required"])
        self.assertIn("FRESH_NONCE_BOUND_TO_ATTESTATION_AND_SIGNATURE",
                      out["evidence_checks_required"])

    def test_legacy_rsa_enterprise_ca_cannot_claim_p256(self):
        out=mod.review_p256_hardware_attestation_requirements()
        self.assertFalse(out["enterprise_ca_rsa_attestation_is_p256_proof"])
        self.assertFalse(out["windows_platform_ksp_algorithm_listing_is_tpm_proof"])
        self.assertFalse(out["ek_ak_chain_verified"])

    def test_ed25519_validity_has_no_effect_on_p256_attestation(self):
        valid=verify()
        att=mod.review_p256_hardware_attestation_requirements(
            purported_evidence={"ed25519_verifier_result":valid})
        self.assertTrue(valid["signature_mathematically_valid"])
        self.assertFalse(att["p256_tpm_origin_verified"])
        self.assertFalse(att["installer_authorized"])

    def test_no_key_generation_in_test_module(self):
        # RFC public data only; no secret seed strings or sign API.
        self.assertFalse(hasattr(mod,"Ed25519PrivateKey"))
        self.assertFalse(hasattr(mod,"generate_private_key"))


if __name__=="__main__":
    unittest.main()
