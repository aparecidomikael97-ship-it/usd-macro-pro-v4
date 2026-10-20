"""P0 LAB synthetic pinning ceremony: 30 fail-closed adversarial tests.

All credentials/keys are made in RAM only. An "approved" local pin remains
untrusted since the executor can create/rollback the whole enrollment record.
These tests do not enroll keys, call clouds, or authorize any Worker/provider.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from atlasquant_aion_p0_trust_anchor_bootstrap_preflight_lab import (
    PIN_FIELDS,assess_trust_anchor_bootstrap_lab as assess,
)
from atlasquant_aion_p0_signed_incident_envelope_lab import (
    SCHEMA as ENVELOPE_SCHEMA, DOMAIN, canonical_json_lab,
)
from atlasquant_aion_p0_incident_external_witness_proposal_lab import NO_GO_FLAGS


class TrustAnchorBootstrapNegativeLAB(unittest.TestCase):
    def setUp(self):
        self.key=Ed25519PrivateKey.generate()
        self.pub=self.key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw)
        self.envelope={
            "schema":ENVELOPE_SCHEMA,
            "issuer_id":"lab-issuer-001",
            "key_id":"lab-key-001",
            "scope":"repo/lab-tenant/lab-workspace",
            "nonce":"lab-nonce-000001",
            "epoch":8,
            "sequence":42,
            "credential_revocation_epoch":3,
            "head_digest":"a"*64,
            "incident_state":"NO_OPEN_INCIDENTS",
            "issued_at":"2026-10-20T12:00:00Z",
            "expires_at":"2026-10-20T12:04:00Z",
        }
        self.pin={
            "issuer_id":self.envelope["issuer_id"],
            "scope":self.envelope["scope"],
            "key_id":self.envelope["key_id"],
            "public_key_sha256":sha256(self.pub).hexdigest(),
            "policy_epoch":7,
            "minimum_sequence":39,
            "minimum_revocation_epoch":2,
            "key_status":"ACTIVE",
            "controller_executor":"lab-admin-executor",
            "controller_issuer":"lab-admin-issuer",
            "controller_verifier":"lab-admin-verifier",
            "controller_recovery":"lab-admin-recovery",
        }
        self.head={
            k:self.envelope[k] for k in (
                "epoch","sequence","credential_revocation_epoch","head_digest")
        }

    def signed(self,envelope=None,key=None,domain=DOMAIN):
        blob=canonical_json_lab(self.envelope if envelope is None else envelope)
        return blob,(self.key if key is None else key).sign(domain+blob)

    def check(self,pin=None,envelope=None,pub=None,key=None,head=None,**kw):
        blob,sig=self.signed(envelope,key)
        return assess(
            self.pin if pin is None else pin,blob,sig,
            self.pub if pub is None else pub,
            observed_head=self.head if head is None else head,
            expected_nonce=kw.get("expected_nonce",self.envelope["nonce"]),
            now_utc=kw.get("now_utc","2026-10-20T12:01:00Z"),
        )

    def denied(self,result):
        self.assertEqual(result["status"],"BLOCKED")
        self.assertIs(result["allowed"],False)
        self.assertTrue(result["simulation_only"])
        self.assertEqual(result["blockers"],tuple(sorted(set(result["blockers"]))))
        self.assertIn("OUT_OF_BAND_BOOTSTRAP_NOT_ATTESTED",result["blockers"])
        self.assertIn("LATEST_EXTERNAL_HEAD_NOT_AUTHENTICATED",result["blockers"])
        self.assertIn("PERSISTENT_EXTERNAL_NONCE_REPLAY_GUARD_MISSING",result["blockers"])
        self.assertIn("ISSUER_REVOCATION_STATUS_NOT_AUTHENTICATED",result["blockers"])
        self.assertFalse(result["off_host_root_authenticated"])
        self.assertFalse(result["off_host_revocation_authenticated"])
        self.assertFalse(result["off_host_latest_head_authenticated"])
        self.assertFalse(result["cross_process_nonce_replay_fenced"])
        self.assertFalse(result["can_issue_production_trust_token"])
        for flag in NO_GO_FLAGS:
            self.assertIs(result[flag],False,flag)
        return result

    def test_01_matching_key_signature_and_pin_still_unenrolled(self):
        r=self.denied(self.check())
        self.assertTrue(r["key_fingerprint_matches_caller_pin_lab"])
        self.assertTrue(r["signature_mathematically_valid_with_supplied_key_lab"])
        self.assertFalse(r["off_host_root_authenticated"])

    def test_02_attacker_replaces_key_and_pin_together_signature_valid_but_blocked(self):
        attacker=Ed25519PrivateKey.generate()
        pub=attacker.public_key().public_bytes(serialization.Encoding.Raw,
                                                serialization.PublicFormat.Raw)
        forged_pin={**self.pin,"public_key_sha256":sha256(pub).hexdigest()}
        r=self.denied(self.check(pin=forged_pin,pub=pub,key=attacker))
        self.assertTrue(r["key_fingerprint_matches_caller_pin_lab"])
        self.assertTrue(r["signature_mathematically_valid_with_supplied_key_lab"])

    def test_03_key_substitution_against_unchanged_pin_denied(self):
        attacker=Ed25519PrivateKey.generate()
        pub=attacker.public_key().public_bytes(serialization.Encoding.Raw,
                                                serialization.PublicFormat.Raw)
        r=self.denied(self.check(pub=pub,key=attacker))
        self.assertFalse(r["key_fingerprint_matches_caller_pin_lab"])
        self.assertIn("CANDIDATE_KEY_FINGERPRINT_MISMATCH",r["blockers"])

    def test_04_key_substitution_with_valid_signature_under_wrong_key_does_not_help(self):
        attacker=Ed25519PrivateKey.generate()
        payload,sign=self.signed(key=attacker)
        r=self.denied(assess(self.pin,payload,sign,self.pub,
             observed_head=self.head,expected_nonce=self.envelope["nonce"],
             now_utc="2026-10-20T12:01:00Z"))
        self.assertIn("SIGNED_INSPECTOR:SIGNATURE_INVALID",r["blockers"])

    def test_05_wrong_key_id_even_with_matching_key_and_pin(self):
        r=self.denied(self.check(envelope={**self.envelope,"key_id":"lab-key-002"}))
        self.assertIn("PIN_ENVELOPE_KEY_ID_MISMATCH",r["blockers"])

    def test_06_wrong_scope_even_when_attacker_controls_pin(self):
        p={**self.pin,"scope":"other-repo/workspace"}
        r=self.denied(self.check(pin=p))
        self.assertIn("SIGNED_INSPECTOR:EXPECTED_BINDING_MISMATCH:scope",r["blockers"])

    def test_07_missing_local_pin_has_no_implicit_enrollment(self):
        r=self.denied(self.check(pin={}))
        self.assertIn("PIN_FIELDS_NOT_EXACT",r["blockers"])
        self.assertFalse(r["key_fingerprint_matches_caller_pin_lab"])

    def test_08_pin_subclass_with_hostile_get_not_accessed(self):
        class Hostile(dict):
            def get(self,*a,**kw):
                raise AssertionError("hostile mapping .get")
        r=self.denied(self.check(pin=Hostile(self.pin)))
        self.assertIn("PIN_NOT_PLAIN_DICT",r["blockers"])

    def test_09_unsupported_pin_fields_fail_closed(self):
        r=self.denied(self.check(pin={**self.pin,"production_ready":True}))
        self.assertIn("PIN_FIELDS_NOT_EXACT",r["blockers"])

    def test_10_identical_admin_controllers_rejected(self):
        p={**self.pin,"controller_verifier":self.pin["controller_executor"]}
        r=self.denied(self.check(pin=p))
        self.assertIn("CLAIMED_ADMINISTRATIVE_DOMAINS_OVERLAP",r["blockers"])

    def test_11_distinct_admin_labels_are_not_proof_of_independent_control(self):
        self.denied(self.check())
        self.assertFalse(self.check()["off_host_root_authenticated"])

    def test_12_key_revoke_boolean_claim_is_not_a_valid_key_status(self):
        class Evil:
            def __eq__(self,_):raise AssertionError("untrusted eq")
        for value in (True,1,False,None,Evil(),"active"):
            with self.subTest(type=type(value).__name__):
                r=self.denied(self.check(pin={**self.pin,"key_status":value}))
                self.assertIn("PIN_KEY_STATUS_INVALID",r["blockers"])

    def test_13_explicitly_revoked_key_status_is_blocked(self):
        r=self.denied(self.check(pin={**self.pin,"key_status":"REVOKED"}))
        self.assertIn("PIN_KEY_REVOKED_OR_UNKNOWN",r["blockers"])

    def test_14_unknown_key_status_is_blocked(self):
        r=self.denied(self.check(pin={**self.pin,"key_status":"UNKNOWN"}))
        self.assertIn("PIN_KEY_REVOKED_OR_UNKNOWN",r["blockers"])

    def test_15_rotated_key_pin_while_old_key_still_signing_is_mismatch(self):
        newer=Ed25519PrivateKey.generate()
        new_pub=newer.public_key().public_bytes(
            serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        r=self.denied(self.check(pin={**self.pin,
                            "public_key_sha256":sha256(new_pub).hexdigest()}))
        self.assertIn("CANDIDATE_KEY_FINGERPRINT_MISMATCH",r["blockers"])

    def test_16_rotated_key_and_pin_replaced_simultaneously_still_no_authority(self):
        newer=Ed25519PrivateKey.generate()
        pub=newer.public_key().public_bytes(
            serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        newpin={**self.pin,"public_key_sha256":sha256(pub).hexdigest(),
                "key_id":"lab-key-002"}
        newer_envelope={**self.envelope,"key_id":"lab-key-002"}
        r=self.denied(self.check(pin=newpin,pub=pub,key=newer,envelope=newer_envelope))
        self.assertTrue(r["signature_mathematically_valid_with_supplied_key_lab"])
        self.assertTrue(r["key_fingerprint_matches_caller_pin_lab"])

    def test_17_fingerprint_is_strict_hex64(self):
        for bad in ("",b"x"*32,"A"*64,"g"*64,True,None,17):
            with self.subTest(value=type(bad).__name__):
                r=self.denied(self.check(pin={**self.pin,
                                          "public_key_sha256":bad}))
                self.assertIn("PIN_KEY_FINGERPRINT_INVALID",r["blockers"])

    def test_18_nonexact_public_key_or_signature_blocks(self):
        blob,sig=self.signed()
        for key in (b"",b"x"*31,True,[],None):
            with self.subTest(value=type(key).__name__):
                r=self.denied(assess(self.pin,blob,sig,key,
                  observed_head=self.head,
                  expected_nonce=self.envelope["nonce"],
                  now_utc="2026-10-20T12:01:00Z"))
                self.assertIn("CANDIDATE_KEY_BYTES_INVALID",r["blockers"])

    def test_19_epoch_must_be_positive_int_not_bool_or_float(self):
        for field in ("policy_epoch","minimum_sequence","minimum_revocation_epoch"):
            for value in (0,True,1.1,-1,None,"1"):
                with self.subTest(field=field,value=str(value)):
                    r=self.denied(self.check(pin={**self.pin,field:value}))
                    self.assertIn("PIN_FIELD_INVALID:"+field,r["blockers"])

    def test_20_old_sequence_below_pinned_floor_detected(self):
        env={**self.envelope,"sequence":21}
        head={**self.head,"sequence":21}
        r=self.denied(self.check(envelope=env,head=head))
        self.assertIn("PIN_MONOTONIC_FLOOR_FAILED:sequence",r["blockers"])

    def test_21_old_epoch_below_pinned_policy_floor_detected(self):
        env={**self.envelope,"epoch":4}
        head={**self.head,"epoch":4}
        r=self.denied(self.check(envelope=env,head=head))
        self.assertIn("PIN_MONOTONIC_FLOOR_FAILED:epoch",r["blockers"])

    def test_22_old_revocation_epoch_below_floor_detected(self):
        env={**self.envelope,"credential_revocation_epoch":1}
        head={**self.head,"credential_revocation_epoch":1}
        r=self.denied(self.check(envelope=env,head=head))
        self.assertIn("PIN_MONOTONIC_FLOOR_FAILED:credential_revocation_epoch",
                      r["blockers"])

    def test_23_pin_head_and_signed_envelope_rolled_back_together_cannot_detect_freshness(self):
        env={**self.envelope,"epoch":1,"sequence":1,"credential_revocation_epoch":1,
             "head_digest":"f"*64}
        head={k:env[k] for k in self.head}
        pin={**self.pin,"policy_epoch":1,"minimum_sequence":1,
             "minimum_revocation_epoch":1}
        r=self.denied(self.check(pin=pin,envelope=env,head=head))
        self.assertTrue(r["signature_mathematically_valid_with_supplied_key_lab"])
        self.assertTrue(r["key_fingerprint_matches_caller_pin_lab"])
        self.assertFalse(r["off_host_latest_head_authenticated"])

    def test_24_replay_of_identical_signature_nonce_twice_both_remain_no_go(self):
        first=self.denied(self.check())
        second=self.denied(self.check())
        self.assertEqual(first,second)
        self.assertFalse(first["cross_process_nonce_replay_fenced"])

    def test_25_wrong_expected_nonce_denied_by_signed_envelope(self):
        r=self.denied(self.check(expected_nonce="wrong-nonce-100"))
        self.assertIn("SIGNED_INSPECTOR:EXPECTED_BINDING_MISMATCH:nonce",r["blockers"])

    def test_26_no_external_current_head_reported_not_a_usable_fence(self):
        blob,sig=self.signed()
        r=self.denied(assess(self.pin,blob,sig,self.pub,observed_head=None,
            expected_nonce=self.envelope["nonce"],now_utc="2026-10-20T12:01:00Z"))
        self.assertIn("SIGNED_INSPECTOR:EXTERNAL_HEAD_NOT_READ",r["blockers"])

    def test_27_fake_local_readback_matching_head_not_authenticity(self):
        r=self.denied(self.check())
        self.assertFalse(r["off_host_latest_head_authenticated"])

    def test_28_non_object_or_invalid_signed_envelope_fails_closed(self):
        r=self.denied(assess(self.pin,b"not-json",b"x"*64,self.pub,
            observed_head=self.head,expected_nonce=self.envelope["nonce"],
            now_utc="2026-10-20T12:01:00Z"))
        self.assertTrue(any(x.startswith("SIGNED_INSPECTOR:") for x in r["blockers"]))

    def test_29_no_runtime_or_owner_authority_is_produced(self):
        result=self.denied(self.check())
        self.assertNotIn("authenticated_enrollment_receipt",result)
        self.assertNotIn("owner_identity_verified",result)
        self.assertNotIn("h0_approved",result)
        for key in ("automatic_retry_allowed","first_attempt_cleared","worker_arming_allowed"):
            self.assertIs(result[key],False)

    def test_30_lab_module_cannot_sign_or_call_network_and_does_not_touch_worker(self):
        src=(Path(__file__).resolve().parents[1]/
             "atlasquant_aion_p0_trust_anchor_bootstrap_preflight_lab.py").read_text()
        for forbidden in ("Ed25519PrivateKey.generate(", "boto3.",
             "requests.post(", "write_repository_feature_flag_enabled(",
             "dispatch_claimed(", "https://", "api.twilio.com"):
            self.assertNotIn(forbidden,src)
        self.assertEqual(frozenset(self.pin),PIN_FIELDS)
        self.denied(self.check())


if __name__=="__main__":
    unittest.main()
