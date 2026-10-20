"""18 offline AWS KMS Ed25519 RAW interoperability proposal negatives.

Keys are ephemeral local unittest fixtures. No boto3, AWS credentials,
Sign/Verify network operations, object storage, user enrollment or expenses.
The checks ALWAYS block authority, even when Ed25519 math succeeds.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from atlasquant_aion_p0_kms_ed25519_raw_interop_lab import (
    FIELDS, REQ, review_kms_ed25519_raw_proposal_lab as inspect,
)
from atlasquant_aion_p0_signed_incident_envelope_lab import (
    DOMAIN,SCHEMA,canonical_json_lab,
)
from atlasquant_aion_p0_incident_external_witness_proposal_lab import NO_GO_FLAGS


class KmsRawModeReadOnlyLAB(unittest.TestCase):
    def setUp(self):
        key=Ed25519PrivateKey.generate()
        self.key=key
        self.public=key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.packet={
            "schema":SCHEMA,"issuer_id":"synthetic-issuer-001",
            "key_id":"synthetic-kms-key-001",
            "scope":"lab/repo/tenant/workspace",
            "nonce":"lab-external-freshness-unverified-001",
            "epoch":4,"sequence":22,"credential_revocation_epoch":2,
            "head_digest":"a"*64,
            "incident_state":"NO_OPEN_INCIDENTS",
            "issued_at":"2026-10-20T12:00:00Z",
            "expires_at":"2026-10-20T12:03:00Z",
        }
        self.payload=canonical_json_lab(self.packet)
        self.signature=key.sign(DOMAIN+self.payload)
        self.proposal={
            **REQ,"kms_key_id":"arn:aws:kms:us-east-1:000000000000:key/synthetic",
            "signing_region":"us-east-1",
            "public_key_sha256":sha256(self.public).hexdigest(),
            "signed_message_sha256":sha256(DOMAIN+self.payload).hexdigest(),
        }
        self.head={k:self.packet[k] for k in (
            "epoch","sequence","credential_revocation_epoch","head_digest")}
        self.kw={
            "expected_issuer":self.packet["issuer_id"],
            "expected_scope":self.packet["scope"],
            "expected_nonce":self.packet["nonce"],
            "now_utc":"2026-10-20T12:01:00Z",
            "observed_head":self.head,
        }

    def observe(self,proposal=None,body=None,sign=None,pub=None,**changes):
        return inspect(
            self.proposal if proposal is None else proposal,
            self.payload if body is None else body,
            self.signature if sign is None else sign,
            self.public if pub is None else pub,
            **{**self.kw,**changes}
        )

    def deny(self,result):
        self.assertEqual(result["status"],"BLOCKED")
        self.assertIs(result["allowed"],False)
        self.assertTrue(result["simulation_only"])
        self.assertEqual(tuple(sorted(set(result["blockers"]))),result["blockers"])
        for field in NO_GO_FLAGS:
            self.assertIs(result[field],False,field)
        for field in ("aws_api_called","aws_key_created","external_signer_verified",
                      "latest_head_authenticated","external_revocation_authenticated",
                      "external_nonce_replay_fenced"):
            self.assertIs(result[field],False,field)
        self.assertIn("OUT_OF_BAND_PUBLIC_KEY_ENROLLMENT_NOT_ATTESTED",result["blockers"])
        self.assertIn("INDEPENDENT_KMS_KEY_OWNERSHIP_NOT_VERIFIED",result["blockers"])
        return result

    def test_01_matching_raw_ed25519_config_and_math_still_no_go(self):
        r=self.deny(self.observe())
        self.assertTrue(r["crypto_valid_with_supplied_key_only_lab"])
        self.assertFalse(any(k.startswith("AWS_KMS_MODE_NOT_COMPATIBLE") for k in r["blockers"]))

    def test_02_kms_ed25519_prehash_digest_mode_not_equivalent(self):
        p={**self.proposal,"message_type":"DIGEST",
           "signing_algorithm":"ED25519_PH_SHA_512"}
        r=self.deny(self.observe(p))
        self.assertIn("AWS_KMS_MODE_NOT_COMPATIBLE:message_type",r["blockers"])
        self.assertIn("AWS_KMS_MODE_NOT_COMPATIBLE:signing_algorithm",r["blockers"])

    def test_03_ed25519_raw_algorithm_digest_mode_also_not_equivalent(self):
        r=self.deny(self.observe({**self.proposal,"message_type":"DIGEST"}))
        self.assertIn("AWS_KMS_MODE_NOT_COMPATIBLE:message_type",r["blockers"])

    def test_04_ecdsa_p256_is_not_ed25519_signature_contract(self):
        r=self.deny(self.observe({**self.proposal,"key_spec":"ECC_NIST_P256",
                                  "signing_algorithm":"ECDSA_SHA_256"}))
        self.assertIn("AWS_KMS_MODE_NOT_COMPATIBLE:key_spec",r["blockers"])

    def test_05_kms_encrypt_decrypt_not_sign_verify(self):
        r=self.deny(self.observe({**self.proposal,"key_usage":"ENCRYPT_DECRYPT"}))
        self.assertIn("AWS_KMS_MODE_NOT_COMPATIBLE:key_usage",r["blockers"])

    def test_06_wrong_hash_of_domain_plus_payload_denied(self):
        r=self.deny(self.observe({**self.proposal,"signed_message_sha256":"0"*64}))
        self.assertIn("SIGNED_MESSAGE_DIGEST_MISMATCH",r["blockers"])

    def test_07_wrong_key_thumbprint_denied(self):
        r=self.deny(self.observe({**self.proposal,"public_key_sha256":"0"*64}))
        self.assertIn("LOCAL_KEY_FINGERPRINT_MISMATCH",r["blockers"])

    def test_08_attacker_replaces_key_and_thumbprint_still_no_external_trust(self):
        attacker=Ed25519PrivateKey.generate()
        public=attacker.public_key().public_bytes(
            serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        signature=attacker.sign(DOMAIN+self.payload)
        p={**self.proposal,"public_key_sha256":sha256(public).hexdigest()}
        r=self.deny(self.observe(p,sign=signature,pub=public))
        self.assertTrue(r["crypto_valid_with_supplied_key_only_lab"])

    def test_09_original_signature_with_unrelated_public_key_denied(self):
        attacker=Ed25519PrivateKey.generate()
        public=attacker.public_key().public_bytes(
            serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        p={**self.proposal,"public_key_sha256":sha256(public).hexdigest()}
        r=self.deny(self.observe(p,pub=public))
        self.assertIn("ENVELOPE:SIGNATURE_INVALID",r["blockers"])

    def test_10_payload_tampering_breaks_digest_and_signature(self):
        changed=self.payload.replace(b'"sequence":22',b'"sequence":23')
        r=self.deny(self.observe(body=changed))
        self.assertIn("SIGNED_MESSAGE_DIGEST_MISMATCH",r["blockers"])
        self.assertIn("ENVELOPE:SIGNATURE_INVALID",r["blockers"])

    def test_11_unknown_fields_do_not_silently_enable_runtime(self):
        r=self.deny(self.observe({**self.proposal,"allow_worker":True}))
        self.assertIn("PROPOSAL_FIELDS_NOT_EXACT",r["blockers"])

    def test_12_boolean_and_object_fields_are_rejected_without_coercion(self):
        class Hostile:
            def __str__(self):raise AssertionError("untrusted str invoked")
            def __eq__(self,_):raise AssertionError("untrusted equality invoked")
        for k,v in (
            ("key_spec",Hostile()),("message_type",True),
            ("kms_key_id",Hostile()),("public_key_sha256",Hostile())
        ):
            with self.subTest(key=k):
                r=self.deny(self.observe({**self.proposal,k:v}))
                self.assertTrue(any(k in reason for reason in r["blockers"]))

    def test_13_invalid_public_key_or_signature_size(self):
        for pub,signature in ((b"short",self.signature),(self.public,b"bad")):
            with self.subTest(keylen=len(pub),siglen=len(signature)):
                r=self.deny(self.observe(pub=pub,sign=signature))
                self.assertTrue(any(k in r["blockers"] for k in (
                    "ED25519_PUBLIC_KEY_BYTES_INVALID","SIGNATURE_BYTES_INVALID")))

    def test_14_4096_byte_kms_raw_message_cap_includes_domain_prefix(self):
        huge=b"x"*(4096-len(DOMAIN)+1)
        self.assertLessEqual(len(huge),4096)
        r=self.deny(self.observe(body=huge))
        self.assertIn("KMS_RAW_MESSAGE_GT_4096",r["blockers"])

    def test_15_expired_timestamp_never_becomes_issuer_identity(self):
        r=self.deny(self.observe(now_utc="2026-10-20T12:04:00Z"))
        self.assertIn("ENVELOPE:TIME_WINDOW_UNSAFE",r["blockers"])

    def test_16_local_head_rollback_mismatch_cannot_enable_readiness(self):
        h={**self.head,"sequence":21}
        r=self.deny(self.observe(observed_head=h))
        self.assertIn("ENVELOPE:LOCAL_HEAD_MISMATCH:sequence",r["blockers"])

    def test_17_self_reported_zero_network_or_no_incident_is_not_proof(self):
        r=self.deny(self.observe())
        self.assertFalse(r["external_signer_verified"])
        self.assertFalse(r["latest_head_authenticated"])
        self.assertFalse(r["external_nonce_replay_fenced"])

    def test_18_lab_module_has_no_aws_sdk_or_production_activation(self):
        root=Path(__file__).resolve().parents[1]
        src=(root/"atlasquant_aion_p0_kms_ed25519_raw_interop_lab.py").read_text()
        self.assertEqual(frozenset(self.proposal),FIELDS)
        for prohibited in ("import boto3","boto3.client(","requests.post(",
                           "kms.sign(","kms.create_key(","dispatch_claimed(",
                           "write_repository_feature_flag_enabled("):
            self.assertNotIn(prohibited,src)
        self.deny(self.observe())


if __name__=="__main__":
    unittest.main()
