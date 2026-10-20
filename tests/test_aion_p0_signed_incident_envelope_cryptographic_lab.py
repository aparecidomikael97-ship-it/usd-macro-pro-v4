"""Ed25519 incident-signature anti-replay LAB: cryptographic shape is NOT trust.

Generates TEST-ONLY ephemeral keys. No real signer, enrollment, verifier-issued
nonce, durable off-host replay guard, first effect, Worker or live network.
A cryptographically valid signature MUST STILL RETURN BLOCKED.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

import atlasquant_aion_p0_signed_incident_envelope_lab as lab
from atlasquant_aion_p0_incident_external_witness_proposal_lab import NO_GO_FLAGS


class SignedIncidentLabOnlyContracts(unittest.TestCase):
    def setUp(self):
        self.private=Ed25519PrivateKey.generate()  # fixture only
        self.public=self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.packet={
            "schema":lab.SCHEMA,
            "issuer_id":"issuer.lab.mock",
            "key_id":"key.lab.mock",
            "scope":"repo/lab-tenant/lab-workspace",
            "nonce":"challenge-from-mock-observer-001",
            "epoch":7,
            "sequence":110,
            "credential_revocation_epoch":4,
            "head_digest":"a"*64,
            "incident_state":"NO_OPEN_INCIDENTS",
            "issued_at":"2026-10-20T12:00:00Z",
            "expires_at":"2026-10-20T12:03:00Z",
        }
        self.local_head={
            k:self.packet[k] for k in
            ("epoch","sequence","credential_revocation_epoch","head_digest")
        }
        self.expected={
            "expected_issuer":self.packet["issuer_id"],
            "expected_scope":self.packet["scope"],
            "expected_nonce":self.packet["nonce"],
            "now_utc":"2026-10-20T12:01:00Z",
            "observed_head":self.local_head,
        }

    def signed(self,packet=None,domain=lab.DOMAIN,raw=None):
        payload=raw if raw is not None else lab.canonical_json_lab(
            self.packet if packet is None else packet)
        return payload,self.private.sign(domain+payload)

    def verify(self,payload=None,signature=None,public_key=None,**changes):
        signed_payload,sig=self.signed() if payload is None else (payload,signature)
        params={**self.expected,**changes}
        return lab.inspect_signed_incident_envelope_lab(
            signed_payload,sig if signature is None else signature,
            self.public if public_key is None else public_key,
            **params
        )

    def denied(self,result):
        self.assertEqual(result["status"],"BLOCKED")
        self.assertIs(result["allowed"],False)
        self.assertIs(result["simulation_only"],True)
        self.assertEqual(tuple(sorted(set(result["blockers"]))),result["blockers"])
        self.assertIn("OUT_OF_BAND_SIGNER_NOT_ENROLLED",result["blockers"])
        self.assertIn("INDEPENDENT_LATEST_HEAD_NOT_AUTHENTICATED",result["blockers"])
        self.assertIn("EXTERNAL_NONCE_REPLAY_GUARD_NOT_ENROLLED",result["blockers"])
        self.assertFalse(result["external_signature_trust_verified"])
        self.assertFalse(result["external_highwater_authenticated"])
        for k in NO_GO_FLAGS:
            self.assertIs(result[k],False,k)
        return result

    def test_01_valid_ed25519_signature_is_only_mathematics_no_real_trust(self):
        r=self.denied(self.verify())
        self.assertTrue(r["signature_mathematically_valid_with_caller_key_in_lab"])
        self.assertEqual(len(r["blockers"]),3)

    def test_02_wrong_public_key_rejected(self):
        unrelated=Ed25519PrivateKey.generate().public_key().public_bytes(
            serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        self.assertIn("SIGNATURE_INVALID",
                      self.denied(self.verify(public_key=unrelated))["blockers"])

    def test_03_changed_signed_body_rejected(self):
        p,s=self.signed()
        changed=p.replace(b'"sequence":110',b'"sequence":111')
        self.assertIn("SIGNATURE_INVALID",
                      self.denied(self.verify(changed,s))["blockers"])

    def test_04_reuse_signed_envelope_still_not_freshness_proof(self):
        p,s=self.signed()
        a=self.denied(self.verify(p,s))
        b=self.denied(self.verify(p,s))
        self.assertEqual(a,b)
        self.assertTrue(a["signature_mathematically_valid_with_caller_key_in_lab"])
        self.assertFalse(a["external_highwater_authenticated"])

    def test_05_signature_domain_separation_rejects_same_data_other_protocol(self):
        p,s=self.signed(domain=b"ANOTHER_PROTOCOL\x00")
        self.assertIn("SIGNATURE_INVALID",
                      self.denied(self.verify(p,s))["blockers"])

    def test_06_no_public_key_enrollment_cannot_be_trusted(self):
        self.denied(self.verify())
        self.assertFalse(self.verify()["external_signature_trust_verified"])

    def test_07_correct_signature_wrong_expected_issuer_denied(self):
        r=self.denied(self.verify(expected_issuer="wrong-issuer"))
        self.assertIn("EXPECTED_BINDING_MISMATCH:issuer_id",r["blockers"])

    def test_08_correct_signature_wrong_expected_scope_denied(self):
        r=self.denied(self.verify(expected_scope="wrong-repo/tenant"))
        self.assertIn("EXPECTED_BINDING_MISMATCH:scope",r["blockers"])

    def test_09_correct_signature_old_nonce_denied(self):
        r=self.denied(self.verify(expected_nonce="another-nonce"))
        self.assertIn("EXPECTED_BINDING_MISMATCH:nonce",r["blockers"])

    def test_10_future_issued_timestamp_denied(self):
        r=self.denied(self.verify(now_utc="2026-10-20T11:59:59Z"))
        self.assertIn("TIME_WINDOW_UNSAFE",r["blockers"])

    def test_11_expired_timestamp_denied(self):
        r=self.denied(self.verify(now_utc="2026-10-20T12:03:00Z"))
        self.assertIn("TIME_WINDOW_UNSAFE",r["blockers"])

    def test_12_huge_validly_signed_time_window_denied(self):
        p={**self.packet,"expires_at":"2026-10-20T14:00:00Z"}
        payload,signature=self.signed(p)
        r=self.denied(self.verify(payload,signature))
        self.assertIn("TIME_WINDOW_UNSAFE",r["blockers"])

    def test_13_malformed_signed_time_string_denied(self):
        p={**self.packet,"issued_at":"2026-10-20T12:00:00+00:00"}
        payload,sig=self.signed(p)
        self.assertIn("TIME_FORMAT_INVALID",
                      self.denied(self.verify(payload,sig))["blockers"])

    def test_14_boolean_epoch_not_accepted_as_integer(self):
        for field in ("epoch","sequence","credential_revocation_epoch"):
            with self.subTest(field=field):
                p={**self.packet,field:True}
                payload,sig=self.signed(p)
                r=self.denied(self.verify(payload,sig))
                self.assertIn("FIELD_INVALID:"+field,r["blockers"])

    def test_15_negative_and_zero_epoch_not_accepted(self):
        for value in (0,-1,2**63,1.5,"7"):
            with self.subTest(value=value):
                p={**self.packet,"epoch":value}
                payload,sig=self.signed(p)
                self.assertIn("FIELD_INVALID:epoch",
                     self.denied(self.verify(payload,sig))["blockers"])

    def test_16_head_local_sequence_rollback_mismatch(self):
        head={**self.local_head,"sequence":109}
        r=self.denied(self.verify(observed_head=head))
        self.assertIn("LOCAL_HEAD_MISMATCH:sequence",r["blockers"])

    def test_17_head_local_credential_revocation_mismatch(self):
        head={**self.local_head,"credential_revocation_epoch":5}
        r=self.denied(self.verify(observed_head=head))
        self.assertIn("LOCAL_HEAD_MISMATCH:credential_revocation_epoch",r["blockers"])

    def test_18_head_fork_digest_mismatch(self):
        head={**self.local_head,"head_digest":"b"*64}
        r=self.denied(self.verify(observed_head=head))
        self.assertIn("LOCAL_HEAD_MISMATCH:head_digest",r["blockers"])

    def test_19_no_external_head_denied_even_for_valid_signature(self):
        r=self.denied(self.verify(observed_head=None))
        self.assertIn("EXTERNAL_HEAD_NOT_READ",r["blockers"])

    def test_20_caller_provided_matching_local_head_does_not_prove_real_readback(self):
        self.denied(self.verify(observed_head=dict(self.local_head)))
        self.assertFalse(self.verify()["external_highwater_authenticated"])

    def test_21_open_incident_signed_correctly_still_denied(self):
        p={**self.packet,"incident_state":"OPEN_INCIDENT"}
        payload,sig=self.signed(p)
        r=self.denied(self.verify(payload,sig))
        self.assertIn("INCIDENT_UNSAFE_OR_UNKNOWN",r["blockers"])

    def test_22_unknown_incident_signed_correctly_denied(self):
        p={**self.packet,"incident_state":"UNKNOWN"}
        payload,sig=self.signed(p)
        self.assertIn("INCIDENT_UNSAFE_OR_UNKNOWN",
            self.denied(self.verify(payload,sig))["blockers"])

    def test_23_raw_duplicate_json_keys_rejected_even_if_signed(self):
        payload,_=self.signed()
        duplicated=payload[:-1]+b',"nonce":"challenge-from-mock-observer-001"}'
        signature=self.private.sign(lab.DOMAIN+duplicated)
        self.assertIn("ENVELOPE_PARSE_INVALID",
            self.denied(self.verify(duplicated,signature))["blockers"])

    def test_24_noncanonical_whitespace_rejected_even_if_signed(self):
        payload=json.dumps(self.packet,sort_keys=True).encode()
        sig=self.private.sign(lab.DOMAIN+payload)
        self.assertIn("ENVELOPE_NOT_CANONICAL",
            self.denied(self.verify(payload,sig))["blockers"])

    def test_25_unknown_field_rejected_even_if_signed(self):
        payload,sig=self.signed({**self.packet,"local_override":True})
        self.assertIn("ENVELOPE_FIELDS_MISMATCH",
            self.denied(self.verify(payload,sig))["blockers"])

    def test_26_oversized_nested_json_payload_rejected(self):
        payload=b"["*3000+b"0"+b"]"*3000
        sig=b"x"*64
        self.assertIn("ENVELOPE_BYTES_INVALID",
            self.denied(self.verify(payload,sig))["blockers"])

    def test_27_invalid_signature_and_public_key_lengths_blocked(self):
        for bad_sig,bad_pub in ((b"",self.public),(b"x"*64,b""),(b"x"*63,self.public)):
            with self.subTest(s=len(bad_sig),p=len(bad_pub)):
                r=self.denied(self.verify(signature=bad_sig,public_key=bad_pub))
                self.assertTrue(any(k in r["blockers"] for k in
                    ("SIGNATURE_BYTES_INVALID","PUBLIC_KEY_BYTES_INVALID")))

    def test_28_input_types_not_coerced_and_do_not_call_attacker_repr(self):
        class Evil:
            def __bytes__(self): raise AssertionError("bytes coerced")
            def __str__(self): raise AssertionError("str coerced")
        for data,signature,public in (
            (Evil(),b"x"*64,self.public),(b"{}",Evil(),self.public),
            (b"{}",b"x"*64,Evil())
        ):
            with self.subTest(name=type(data).__name__+type(signature).__name__):
                self.denied(self.verify(data,signature,public))

    def test_29_source_and_expected_binding_stable(self):
        data=deepcopy(self.packet)
        expected=deepcopy(self.expected)
        p,s=self.signed()
        for _ in range(3):
            self.denied(self.verify(p,s))
        self.assertEqual(data,self.packet)
        self.assertEqual(expected,self.expected)

    def test_30_no_real_enrollment_or_send_code_in_lab_module(self):
        src=(Path(__file__).resolve().parents[1]/
             "atlasquant_aion_p0_signed_incident_envelope_lab.py").read_text()
        for prohibited in ("boto3.", "requests.post(", "dispatch_claimed(",
                           "write_repository_feature_flag_enabled(",
                           "Ed25519PrivateKey.generate(", "worker_arming_allowed\": True"):
            self.assertNotIn(prohibited,src)
        self.denied(self.verify())


if __name__=="__main__":
    unittest.main()
