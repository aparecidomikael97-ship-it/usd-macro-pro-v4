"""Offline adversarial two-signature H0 witness protocol: NEVER AUTHORIZE."""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_p0_h0_dual_signed_witness_transcript_lab import (
    DOMAIN, RESERVE_SCHEMA, READ_SCHEMA, RESERVATION, READBACK,
    canonical_bytes, inspect_dual_signed_witness_lab as inspect,
    PERMANENT_GAPS, AUTHORITY_FALSE,
)

NOW = "2026-10-20T19:00:10Z"


def enc(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def pk(secret):
    return enc(secret.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw))


def signed(secret, payload):
    return {"payload": deepcopy(payload),
            "signature_b64url": enc(secret.sign(canonical_bytes(payload)))}


class H0TwoSignedIndependentRolesLAB(unittest.TestCase):
    def setUp(self):
        self.writer=Ed25519PrivateKey.generate()
        self.reader=Ed25519PrivateKey.generate()
        self.reserve = {
            "schema": RESERVE_SCHEMA, "kind": RESERVATION,
            "issuer_id":"issuer-lab-001", "key_id":"writer-key-lab-001",
            "scope_digest":"a"*64, "request_id":"request-lab-001",
            "intent_id":"intent-lab-001", "attempt_nonce":"nonce-attempt-lab-001",
            "epoch":8, "sequence":101, "head_digest":"b"*64,
            "version_id":"version-lab-101", "issued_at_utc":"2026-10-20T19:00:00Z",
        }
        self.read = {
            **{k:v for k,v in self.reserve.items() if k not in ("schema","kind","key_id","issued_at_utc")},
            "schema":READ_SCHEMA, "kind":READBACK, "key_id":"reader-key-lab-001",
            "reservation_sha256":hashlib.sha256(canonical_bytes(self.reserve)).hexdigest(),
            "challenge_nonce":"readback-challenge-lab-001",
            "observed_at_utc":"2026-10-20T19:00:05Z",
        }
        self.pins={
            "reservation_public_key_b64url":pk(self.writer),
            "readback_public_key_b64url":pk(self.reader),
            "reservation_key_id":"writer-key-lab-001",
            "readback_key_id":"reader-key-lab-001",
            "issuer_id":"issuer-lab-001", "scope_digest":"a"*64,
            "request_id":"request-lab-001", "intent_id":"intent-lab-001",
            "attempt_nonce":"nonce-attempt-lab-001",
            "challenge_nonce":"readback-challenge-lab-001",
            "minimum_epoch":8, "minimum_sequence":101,
            "expected_version_id":"version-lab-101", "expected_head_digest":"b"*64,
        }

    def packet(self):
        return signed(self.writer,self.reserve),signed(self.reader,self.read)

    def check(self, a=None,b=None,p=None,now=NOW):
        aa,bb=self.packet()
        return inspect(aa if a is None else a,bb if b is None else b,
                       self.pins if p is None else p,now_utc=now)

    def deny(self,result,expected=None,crypto=None):
        self.assertEqual(result["state"],"HARD_NO_GO")
        self.assertIs(result["allowed"],False)
        self.assertIs(result["simulation_only"],True)
        self.assertEqual(result["blockers"],PERMANENT_GAPS)
        for flag in AUTHORITY_FALSE:
            self.assertIs(result[flag],False,flag)
        if expected:
            self.assertIn(expected,result["defects"])
        if crypto is not None:
            self.assertIs(result["signature_bytes_valid_under_caller_supplied_keys"],crypto)
        return result

    def test_01_valid_dual_cryptography_has_zero_operational_authority(self):
        x=self.deny(self.check(),crypto=True)
        self.assertEqual(x["defects"],())
        self.assertIs(x["signed_transcripts_consistent_lab"],True)

    def test_02_writer_signed_bytes_cannot_be_modified(self):
        a,b=self.packet()
        a["payload"]["sequence"]=102
        self.deny(self.check(a,b), "RESERVATION_SIGNATURE_INVALID",False)

    def test_03_readback_signed_bytes_cannot_be_modified(self):
        a,b=self.packet()
        b["payload"]["sequence"]=102
        self.deny(self.check(a,b),"READBACK_SIGNATURE_INVALID",False)

    def test_04_no_padded_alias_for_signature(self):
        a,b=self.packet()
        a["signature_b64url"]+="=="
        self.deny(self.check(a,b),"RESERVATION_SIGNATURE_OR_PUBLIC_KEY_ENCODING_INVALID",False)

    def test_05_no_modified_unused_base64_padding_bits(self):
        a,b=self.packet()
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        old=a["signature_b64url"][-1]
        idx=alphabet.index(old)
        # A 64-byte Ed25519 signature has FOUR unused pad bits in the last Base64URL sextet.
        changed=alphabet[(idx & ~3) | ((idx+1) & 3)]
        self.assertNotEqual(changed,old)
        a["signature_b64url"]=a["signature_b64url"][:-1]+changed
        self.deny(self.check(a,b),"RESERVATION_SIGNATURE_OR_PUBLIC_KEY_ENCODING_INVALID",False)

    def test_06_same_public_key_for_both_roles_rejected(self):
        p=deepcopy(self.pins)
        p["readback_public_key_b64url"]=p["reservation_public_key_b64url"]
        self.deny(self.check(p=p),"CLAIMED_WITNESS_ROLES_NOT_SEPARATE")

    def test_07_same_key_id_for_two_roles_rejected(self):
        p=deepcopy(self.pins)
        p["readback_key_id"]=p["reservation_key_id"]
        self.deny(self.check(p=p),"CLAIMED_WITNESS_ROLES_NOT_SEPARATE")

    def test_08_swapping_signatures_between_roles_is_invalid(self):
        a,b=self.packet()
        a["signature_b64url"],b["signature_b64url"]=b["signature_b64url"],a["signature_b64url"]
        self.deny(self.check(a,b),"RESERVATION_SIGNATURE_INVALID",False)

    def test_09_challenge_nonce_bound_to_fixture(self):
        self.read["challenge_nonce"]="wrong-readback-challenge-001"
        self.deny(self.check(),"READBACK_CHALLENGE_MISMATCH",True)

    def test_10_signed_readback_must_bind_reservation_digest(self):
        self.read["reservation_sha256"]="e"*64
        self.deny(self.check(),"READBACK_NOT_BOUND_TO_RESERVATION",True)

    def test_11_signatures_do_not_override_minimum_sequence(self):
        self.reserve["sequence"]=99
        self.read["sequence"]=99
        self.read["reservation_sha256"]=hashlib.sha256(canonical_bytes(self.reserve)).hexdigest()
        self.deny(self.check(),"SIGNED_HEAD_BELOW_CALLER_MINIMUM",True)

    def test_12_epoch_rollback_detected_against_supplied_minimum(self):
        self.reserve["epoch"]=7
        self.read["epoch"]=7
        self.read["reservation_sha256"]=hashlib.sha256(canonical_bytes(self.reserve)).hexdigest()
        self.deny(self.check(),"SIGNED_HEAD_BELOW_CALLER_MINIMUM",True)

    def test_13_forked_signed_head_refused(self):
        self.read["head_digest"]="f"*64
        self.deny(self.check(),"SIGNED_HEAD_BINDING_MISMATCH:head_digest",True)

    def test_14_signed_version_id_drift_rejected(self):
        self.read["version_id"]="version-lab-102"
        self.deny(self.check(),"SIGNED_HEAD_BINDING_MISMATCH:version_id",True)

    def test_15_issuer_role_key_id_mismatch_rejected(self):
        self.read["key_id"]="attacker-readback-key"
        self.deny(self.check(),"ROLE_KEY_BINDING_MISMATCH",True)

    def test_16_request_id_binding_cannot_be_changed_with_valid_signature(self):
        self.reserve["request_id"]="request-lab-evil"
        self.read["request_id"]="request-lab-evil"
        self.read["reservation_sha256"]=hashlib.sha256(canonical_bytes(self.reserve)).hexdigest()
        self.deny(self.check(),"PIN_BINDING_MISMATCH:request_id",True)

    def test_17_signed_attempt_nonce_binding_mismatch(self):
        self.read["attempt_nonce"]="nonce-attempt-lab-evil"
        self.deny(self.check(),"PIN_BINDING_MISMATCH:attempt_nonce",True)

    def test_18_expired_synthetic_readback_window(self):
        self.deny(self.check(now="2026-10-20T19:03:00Z"),
                  "CALLER_TIME_OR_OBSERVATION_WINDOW_INVALID",True)

    def test_19_future_observation_under_caller_clock(self):
        self.deny(self.check(now="2026-10-20T19:00:03Z"),
                  "CALLER_TIME_OR_OBSERVATION_WINDOW_INVALID",True)

    def test_20_issued_after_observation_invalid(self):
        self.reserve["issued_at_utc"]="2026-10-20T19:00:09Z"
        self.read["reservation_sha256"]=hashlib.sha256(canonical_bytes(self.reserve)).hexdigest()
        self.deny(self.check(),"CALLER_TIME_OR_OBSERVATION_WINDOW_INVALID",True)

    def test_21_bool_is_not_integer_epoch_in_pins(self):
        p=deepcopy(self.pins)
        p["minimum_epoch"]=True
        self.deny(self.check(p=p),"PIN_FIELD_INVALID:minimum_epoch",False)

    def test_22_untrusted_self_enrollment_with_new_valid_keys_is_still_no_go(self):
        new_writer=Ed25519PrivateKey.generate()
        new_reader=Ed25519PrivateKey.generate()
        p=deepcopy(self.pins)
        p["reservation_public_key_b64url"]=pk(new_writer)
        p["readback_public_key_b64url"]=pk(new_reader)
        a=signed(new_writer,self.reserve)
        b=signed(new_reader,self.read)
        x=self.deny(self.check(a,b,p),crypto=True)
        self.assertIs(x["signed_transcripts_consistent_lab"],True)
        self.assertIs(x["issuer_independently_enrolled"],False)

    def test_23_unknown_transcript_field_fails_closed(self):
        a,b=self.packet()
        a["payload"]["execution_allowed"]=True
        self.deny(self.check(a,b),"RESERVATION_TRANSCRIPT_INVALID",False)

    def test_24_unknown_signature_wrapper_field_fails_closed(self):
        a,b=self.packet()
        b["signature_valid"]=True
        self.deny(self.check(a,b),"READBACK_ENVELOPE_SHAPE_INVALID",False)

    def test_25_invalid_public_key_b64url_fails_closed(self):
        p=deepcopy(self.pins)
        p["reservation_public_key_b64url"]="x"*43
        self.deny(self.check(p=p),"PINNED_KEY_ENCODING_INVALID",False)

    def test_26_object_subclass_rejected_without_evaluation(self):
        class HostileDict(dict):
            def __getitem__(self,key):
                raise RuntimeError("unsafe mapping access")
        a,b=self.packet()
        self.deny(self.check(a=HostileDict(a)),"RESERVATION_ENVELOPE_SHAPE_INVALID",False)

    def test_27_nan_and_nested_payload_rejected_without_serialization(self):
        a,b=self.packet()
        a["payload"]["sequence"]=float("nan")
        self.deny(self.check(a,b),"RESERVATION_TRANSCRIPT_INVALID",False)
        a["payload"]["sequence"]={"__float__":"1"}
        self.deny(self.check(a,b),"RESERVATION_TRANSCRIPT_INVALID",False)

    def test_28_bad_issued_calendar_is_rejected(self):
        self.reserve["issued_at_utc"]="2026-02-30T19:00:00Z"
        self.deny(self.check(),"RESERVATION_TRANSCRIPT_INVALID",False)

    def test_29_domain_tag_not_generic_owner_or_provider_signature(self):
        self.assertTrue(canonical_bytes(self.reserve).startswith(DOMAIN))
        self.assertNotEqual(
            canonical_bytes(self.reserve),
            __import__("json").dumps(self.reserve,sort_keys=True).encode(),
        )
        self.deny(self.check(),crypto=True)

    def test_30_identical_packet_repeated_has_no_freshness_or_replay_proof(self):
        once=self.deny(self.check(),crypto=True)
        twice=self.deny(self.check(),crypto=True)
        self.assertEqual(once,twice)
        self.assertIs(once["external_nonce_durably_reserved"],False)
        self.assertIs(once["first_external_effect_allowed"],False)


    def test_31_hostile_reservation_schema_must_not_escape_as_exception(self):
        class HostileField:
            def __eq__(self,other):
                return True
            def __ne__(self,other):
                return False
        a,b=self.packet()
        a["payload"]["schema"]=HostileField()
        self.deny(self.check(a,b),"RESERVATION_TRANSCRIPT_INVALID",False)

    def test_32_hostile_readback_kind_must_not_escape_as_exception(self):
        class HostileField:
            def __eq__(self,other):
                return True
            def __ne__(self,other):
                return False
        a,b=self.packet()
        b["payload"]["kind"]=HostileField()
        self.deny(self.check(a,b),"READBACK_TRANSCRIPT_INVALID",False)

    def test_33_all_15_signature_aliases_in_unused_base64_bits_denied(self):
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        original_a,original_b=self.packet()
        original=original_a["signature_b64url"][-1]
        idx=alphabet.index(original)
        base=idx & ~15  # 512 bits: 2 useful, 4 unused in final sextet
        aliases=[alphabet[base+i] for i in range(16)
                 if alphabet[base+i]!=original]
        self.assertEqual(len(aliases),15)
        for suffix in aliases:
            with self.subTest(alias=suffix):
                a=deepcopy(original_a)
                a["signature_b64url"]=a["signature_b64url"][:-1]+suffix
                self.deny(self.check(a,original_b),
                          "RESERVATION_SIGNATURE_OR_PUBLIC_KEY_ENCODING_INVALID",False)

    def test_34_canonical_json_interoperability_known_minimal_vector(self):
        # A fixed expected byte vector independent of signing implementation.
        self.assertEqual(
            canonical_bytes({"z":2,"a":"á"}),
            DOMAIN + b'{"a":"\\u00e1","z":2}',
        )



if __name__=="__main__":
    unittest.main()
