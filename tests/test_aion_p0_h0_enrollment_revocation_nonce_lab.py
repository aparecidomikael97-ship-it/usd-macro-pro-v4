"""P0/H0 offline synthetic enrollment + revocation + custodian evidence tests.

All results MUST be HARD_NO_GO, including three perfect Ed25519 signatures.
"""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_p0_h0_enrollment_revocation_nonce_lab import (
    SCHEMA, DOMAIN, ENROLL_SCHEMA, REVOCATION_SCHEMA, NONCE_SCHEMA,
    AUTHORITY_FALSE, PERMANENT_BLOCKERS, canonical_bytes,
    inspect_enrollment_revocation_nonce_lab as inspect,
)

NOW = "2026-10-21T09:00:12Z"


def enc(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def pub(k: Ed25519PrivateKey) -> str:
    return enc(k.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw))


def envelope(k, payload):
    return {"payload": deepcopy(payload), "signature_b64url": enc(k.sign(canonical_bytes(payload)))}


class EnrollmentRevocationNonceLabTest(unittest.TestCase):
    def setUp(self):
        self.root = Ed25519PrivateKey.generate()
        self.custodian = Ed25519PrivateKey.generate()
        self.writer = Ed25519PrivateKey.generate()
        self.reader = Ed25519PrivateKey.generate()
        self.a = {
            "schema": ENROLL_SCHEMA, "issuer_id": "issuer-lab-001",
            "scope_digest": "a" * 64, "registry_epoch": 5, "registry_seq": 100,
            "registry_version_id": "registry-version-001",
            "signed_at_utc": "2026-10-21T09:00:00Z",
            "roles": [
                {"role": "reservation_signer", "key_id": "writer-key-001",
                 "public_key_b64url": pub(self.writer), "key_epoch": 5, "status": "ACTIVE"},
                {"role": "readback_witness", "key_id": "reader-key-001",
                 "public_key_b64url": pub(self.reader), "key_epoch": 5, "status": "ACTIVE"},
            ],
        }
        self.b = {
            "schema": REVOCATION_SCHEMA, "issuer_id": "issuer-lab-001",
            "scope_digest": "a" * 64, "registry_epoch": 5, "registry_seq": 101,
            "enrollment_sha256": "", "signed_at_utc": "2026-10-21T09:00:03Z",
            "revoked_key_ids": [], "active_key_ids": ["reader-key-001", "writer-key-001"],
        }
        self.c = {
            "schema": NONCE_SCHEMA, "issuer_id": "issuer-lab-001",
            "scope_digest": "a" * 64, "request_id": "request-lab-001",
            "intent_id": "intent-lab-001", "challenge_nonce": "challenge-lab-001",
            "registry_epoch": 5, "registry_seq": 101,
            "revocation_sha256": "", "custody_counter": 500,
            "issued_at_utc": "2026-10-21T09:00:05Z",
            "expires_at_utc": "2026-10-21T09:00:25Z",
            "head_digest": "b" * 64, "head_sequence": 5000,
        }
        self.pins = {
            "registry_root_public_key_b64url": pub(self.root),
            "custodian_public_key_b64url": pub(self.custodian),
            "issuer_id": "issuer-lab-001", "scope_digest": "a"*64,
            "request_id": "request-lab-001", "intent_id": "intent-lab-001",
            "challenge_nonce": "challenge-lab-001",
            "minimum_registry_epoch": 5, "minimum_registry_seq": 101,
            "minimum_custody_counter": 500,
            "expected_head_digest": "b"*64, "expected_head_sequence": 5000,
        }

    def packet(self):
        # Creates a coherent freshly-signed synthetic chain from current fields.
        self.b["enrollment_sha256"] = hashlib.sha256(canonical_bytes(self.a)).hexdigest()
        self.c["revocation_sha256"] = hashlib.sha256(canonical_bytes(self.b)).hexdigest()
        return (envelope(self.root, self.a), envelope(self.root, self.b),
                envelope(self.custodian, self.c))

    def check(self, aa=None, bb=None, cc=None, pins=None, now=NOW, defect=None, crypto=None):
        a,b,c = self.packet()
        result = inspect(a if aa is None else aa, b if bb is None else bb,
                         c if cc is None else cc, self.pins if pins is None else pins,
                         now_utc=now)
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["state"], "HARD_NO_GO")
        self.assertIs(result["allowed"], False)
        self.assertIs(result["simulation_only"], True)
        self.assertEqual(result["blockers"], PERMANENT_BLOCKERS)
        for flag in AUTHORITY_FALSE:
            self.assertIs(result[flag], False, flag)
        if defect:
            self.assertIn(defect, result["findings"])
        if crypto is not None:
            self.assertIs(result["synthetic_signatures_valid_under_caller_keys"], crypto)
        return result

    def test_01_all_three_valid_signatures_never_grant_authority(self):
        result = self.check(crypto=True)
        self.assertEqual(result["findings"], ())
        self.assertIs(result["synthetic_policy_consistent_lab"], True)

    def test_02_modified_enrollment_signature_fails(self):
        a,b,c = self.packet()
        a["payload"]["registry_seq"] += 1
        self.check(aa=a,bb=b,cc=c,defect="ENROLLMENT_SIGNATURE_INVALID",crypto=False)

    def test_03_modified_revocation_signature_fails(self):
        a,b,c = self.packet()
        b["payload"]["registry_seq"] += 1
        self.check(aa=a,bb=b,cc=c,defect="REVOCATION_SIGNATURE_INVALID",crypto=False)

    def test_04_modified_challenge_signature_fails(self):
        a,b,c = self.packet()
        c["payload"]["custody_counter"] += 1
        self.check(aa=a,bb=b,cc=c,defect="CHALLENGE_SIGNATURE_INVALID",crypto=False)

    def test_05_changed_caller_request_pin_fails(self):
        p = deepcopy(self.pins); p["request_id"] = "request-lab-evil"
        self.check(pins=p,defect="CHALLENGE_PIN_MISMATCH:request_id",crypto=True)

    def test_06_root_custodian_key_reuse_rejected(self):
        p = deepcopy(self.pins)
        p["custodian_public_key_b64url"] = p["registry_root_public_key_b64url"]
        self.check(pins=p,defect="PINNED_REGISTRY_CUSTODIAN_KEY_REUSE",crypto=False)

    def test_07_attacker_chooses_new_valid_keys_still_blocked(self):
        root=Ed25519PrivateKey.generate()
        cust=Ed25519PrivateKey.generate()
        p=deepcopy(self.pins)
        p["registry_root_public_key_b64url"]=pub(root)
        p["custodian_public_key_b64url"]=pub(cust)
        self.b["enrollment_sha256"]=hashlib.sha256(canonical_bytes(self.a)).hexdigest()
        self.c["revocation_sha256"]=hashlib.sha256(canonical_bytes(self.b)).hexdigest()
        result=self.check(
            aa=envelope(root,self.a), bb=envelope(root,self.b),
            cc=envelope(cust,self.c), pins=p,crypto=True)
        self.assertEqual(result["findings"], ())
        self.assertIs(result["registry_root_out_of_band_authenticated"], False)

    def test_08_wrong_caller_registry_root_fails_signature(self):
        p=deepcopy(self.pins); p["registry_root_public_key_b64url"]=pub(Ed25519PrivateKey.generate())
        self.check(pins=p,defect="ENROLLMENT_SIGNATURE_INVALID",crypto=False)

    def test_09_enrollment_schema_unknown(self):
        self.a["schema"]="WRONG_SCHEMA"; self.check(defect="ENROLLMENT_PAYLOAD_INVALID",crypto=False)

    def test_10_revocation_schema_unknown(self):
        self.b["schema"]="WRONG_SCHEMA"; self.check(defect="REVOCATION_PAYLOAD_INVALID",crypto=False)

    def test_11_challenge_schema_unknown(self):
        self.c["schema"]="WRONG_SCHEMA"; self.check(defect="CHALLENGE_PAYLOAD_INVALID",crypto=False)

    def test_12_duplicate_signer_role_rejected(self):
        self.a["roles"][1]["role"]="reservation_signer"
        self.check(defect="ENROLLMENT_PAYLOAD_INVALID",crypto=False)

    def test_13_same_key_id_for_both_roles_rejected(self):
        self.a["roles"][1]["key_id"]=self.a["roles"][0]["key_id"]
        self.check(defect="ENROLLMENT_PAYLOAD_INVALID",crypto=False)

    def test_14_same_public_key_for_both_roles_rejected(self):
        self.a["roles"][1]["public_key_b64url"]=self.a["roles"][0]["public_key_b64url"]
        self.check(defect="ENROLLMENT_PAYLOAD_INVALID",crypto=False)

    def test_15_key_epoch_drift_rejected(self):
        self.a["roles"][1]["key_epoch"]=4
        self.check(defect="ENROLLMENT_PAYLOAD_INVALID",crypto=False)

    def test_16_inactive_enrollment_role_not_accepted(self):
        self.a["roles"][1]["status"]="REVOKED"
        self.b["active_key_ids"]=["writer-key-001"]
        self.check(defect="ENROLLED_ROLE_REVOKED_OR_INACTIVE",crypto=True)

    def test_17_revoked_signer_cannot_be_active(self):
        self.b["revoked_key_ids"]=["writer-key-001"]
        self.b["active_key_ids"]=["reader-key-001"]
        self.check(defect="ENROLLED_KEY_REVOKED",crypto=True)

    def test_18_absent_active_role_key_rejected(self):
        self.b["active_key_ids"]=["reader-key-001"]
        self.check(defect="ACTIVE_ROLE_KEYSET_NOT_MATCHED",crypto=True)

    def test_19_unsorted_active_keys_rejected(self):
        self.b["active_key_ids"]=["writer-key-001","reader-key-001"]
        self.check(defect="REVOCATION_PAYLOAD_INVALID",crypto=False)

    def test_20_duplicate_revocation_list_rejected(self):
        self.b["revoked_key_ids"]=["old-key-001","old-key-001"]
        self.check(defect="REVOCATION_PAYLOAD_INVALID",crypto=False)

    def test_21_key_both_active_and_revoked_rejected(self):
        self.b["revoked_key_ids"]=["writer-key-001"]
        self.check(defect="REVOCATION_PAYLOAD_INVALID",crypto=False)

    def test_22_enrollment_hash_not_bound_rejected(self):
        a,b,c=self.packet()
        b["payload"]["enrollment_sha256"]="f"*64
        b=envelope(self.root,b["payload"])
        self.check(aa=a,bb=b,cc=c,defect="REVOCATION_NOT_BOUND_TO_ENROLLMENT",crypto=True)

    def test_23_revocation_hash_not_bound_rejected(self):
        a,b,c=self.packet()
        c["payload"]["revocation_sha256"]="f"*64
        c=envelope(self.custodian,c["payload"])
        self.check(aa=a,bb=b,cc=c,defect="CHALLENGE_NOT_BOUND_TO_REVOCATION",crypto=True)

    def test_24_challenge_sequence_not_current_revocation(self):
        self.c["registry_seq"]=100
        self.check(defect="CHALLENGE_NOT_BOUND_TO_REVOCATION_SEQUENCE",crypto=True)

    def test_25_registry_seq_below_caller_minimum(self):
        self.b["registry_seq"]=100
        self.c["registry_seq"]=100
        self.check(defect="REVOCATION_SEQ_BELOW_CALLER_MINIMUM",crypto=True)

    def test_26_revocation_same_sequence_as_enrollment_rejected(self):
        self.b["registry_seq"]=100
        self.c["registry_seq"]=100
        self.check(defect="REVOCATION_NOT_AFTER_ENROLLMENT",crypto=True)

    def test_27_nonce_counter_below_caller_minimum(self):
        self.c["custody_counter"]=499
        self.check(defect="CUSTODY_COUNTER_BELOW_CALLER_MINIMUM",crypto=True)

    def test_28_head_seq_drift_rejected(self):
        self.c["head_sequence"]=4999
        self.check(defect="CHALLENGE_HEAD_BINDING_MISMATCH",crypto=True)

    def test_29_head_digest_drift_rejected(self):
        self.c["head_digest"]="c"*64
        self.check(defect="CHALLENGE_HEAD_BINDING_MISMATCH",crypto=True)

    def test_30_request_id_drift_rejected(self):
        self.c["request_id"]="request-lab-wrong"
        self.check(defect="CHALLENGE_PIN_MISMATCH:request_id",crypto=True)

    def test_31_intent_id_drift_rejected(self):
        self.c["intent_id"]="intent-lab-wrong"
        self.check(defect="CHALLENGE_PIN_MISMATCH:intent_id",crypto=True)

    def test_32_challenge_nonce_drift_rejected(self):
        self.c["challenge_nonce"]="nonce-lab-wrong"
        self.check(defect="CHALLENGE_PIN_MISMATCH:challenge_nonce",crypto=True)

    def test_33_enrollment_scope_drift_rejected(self):
        self.a["scope_digest"]="d"*64
        self.check(defect="ENROLLMENT_PIN_MISMATCH:scope_digest",crypto=True)

    def test_34_revocation_issuer_drift_rejected(self):
        self.b["issuer_id"]="issuer-lab-evil"
        self.check(defect="REVOCATION_PIN_MISMATCH:issuer_id",crypto=True)

    def test_35_revocation_epoch_drift_rejected(self):
        self.b["registry_epoch"]=4
        self.check(defect="REVOCATION_REGISTRY_EPOCH_MISMATCH",crypto=True)

    def test_36_future_nonce_not_fresh(self):
        self.check(now="2026-10-21T09:00:02Z",defect="CALLER_TIME_OR_NONCE_WINDOW_INVALID",crypto=True)

    def test_37_expired_nonce_cannot_be_replayed(self):
        self.check(now="2026-10-21T09:03:00Z",defect="CALLER_TIME_OR_NONCE_WINDOW_INVALID",crypto=True)

    def test_38_overlong_nonce_ttl_rejected(self):
        self.c["expires_at_utc"]="2026-10-21T09:04:00Z"
        self.check(defect="CALLER_TIME_OR_NONCE_WINDOW_INVALID",crypto=True)

    def test_39_very_stale_revocation_to_challenge_rejected(self):
        self.b["signed_at_utc"]="2026-10-21T08:55:00Z"
        self.check(defect="CALLER_TIME_OR_NONCE_WINDOW_INVALID",crypto=True)

    def test_40_revocation_earlier_than_enrollment_rejected(self):
        self.b["signed_at_utc"]="2026-10-21T08:59:00Z"
        self.check(defect="CALLER_TIME_OR_NONCE_WINDOW_INVALID",crypto=True)

    def test_41_duplicate_valid_packet_has_no_durable_nonce_proof(self):
        first=self.check(crypto=True)
        second=self.check(crypto=True)
        self.assertEqual(first,second)
        self.assertIs(first["nonce_atomically_consumed"], False)

    def test_42_hostile_schema_object_does_not_escape_validator(self):
        class Evil:
            def __eq__(self, other): return True
        a,b,c=self.packet()
        a["payload"]["schema"]=Evil()
        self.check(aa=a,bb=b,cc=c,defect="ENROLLMENT_PAYLOAD_INVALID",crypto=False)

    def test_43_hostile_dict_subclass_does_not_execute(self):
        class Evil(dict):
            def __getitem__(self,key): raise RuntimeError("unsafe")
        a,b,c=self.packet()
        self.check(cc=Evil(c),aa=a,bb=b,defect="CHALLENGE_ENVELOPE_SHAPE_INVALID",crypto=False)

    def test_44_padded_signature_alias_rejected(self):
        a,b,c=self.packet()
        c["signature_b64url"]+="="
        self.check(aa=a,bb=b,cc=c,defect="CHALLENGE_PUBLIC_KEY_OR_SIGNATURE_ENCODING_INVALID",crypto=False)

    def test_45_noncanonical_signature_base64_bits_rejected(self):
        a,b,c=self.packet()
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        final=c["signature_b64url"][-1]
        idx=alphabet.index(final)
        mutated=alphabet[(idx & ~15)|((idx+1)&15)]
        self.assertNotEqual(mutated,final)
        c["signature_b64url"]=c["signature_b64url"][:-1]+mutated
        self.check(aa=a,bb=b,cc=c,defect="CHALLENGE_PUBLIC_KEY_OR_SIGNATURE_ENCODING_INVALID",crypto=False)

    def test_46_bool_is_not_int_sequence(self):
        self.b["registry_seq"]=True
        self.check(defect="REVOCATION_PAYLOAD_INVALID",crypto=False)

    def test_47_nan_and_nested_fields_rejected_before_json(self):
        a,b,c=self.packet()
        a["payload"]["registry_epoch"]=float("nan")
        self.check(aa=a,bb=b,cc=c,defect="ENROLLMENT_PAYLOAD_INVALID",crypto=False)
        a["payload"]["registry_epoch"]={"claimed": 5}
        self.check(aa=a,bb=b,cc=c,defect="ENROLLMENT_PAYLOAD_INVALID",crypto=False)

    def test_48_added_execution_permission_field_rejected(self):
        a,b,c=self.packet()
        c["payload"]["effect_allowed"]=True
        self.check(aa=a,bb=b,cc=c,defect="CHALLENGE_PAYLOAD_INVALID",crypto=False)

    def test_49_pins_have_unknown_claim_field(self):
        p=deepcopy(self.pins);p["issuer_enrolled"]=True
        self.check(pins=p,defect="CALLER_PINS_INVALID",crypto=False)

    def test_50_not_plain_caller_pins(self):
        class Evil(dict):
            def __getitem__(self,key): raise RuntimeError("unsafe")
        self.check(pins=Evil(self.pins),defect="CALLER_PINS_INVALID",crypto=False)

    def test_51_invalid_calendar_date_rejected(self):
        self.a["signed_at_utc"]="2026-02-30T09:00:00Z"
        self.check(defect="ENROLLMENT_PAYLOAD_INVALID",crypto=False)

    def test_52_root_public_key_padding_alias_rejected(self):
        p=deepcopy(self.pins);p["registry_root_public_key_b64url"]+="="
        self.check(pins=p,defect="PINNED_SIGNER_ENCODING_INVALID",crypto=False)

    def test_53_replaced_role_public_key_has_no_independent_proof(self):
        self.a["roles"][0]["public_key_b64url"]=pub(Ed25519PrivateKey.generate())
        # A new well-formed public key in a synthetic registry does not prove
        # independent enrollment or possession by a genuine provider.
        # Cross-check against dual-witness transcript is a separate future gate.
        result=self.check(crypto=True)
        self.assertIs(result["issuer_independently_enrolled"],False)

    def test_54_domain_separated_canonical_serialization(self):
        self.assertEqual(
            canonical_bytes({"z":2,"a":"á"}),
            DOMAIN+b'{"a":"\\u00e1","z":2}',
        )

    def test_55_registry_epoch_below_caller_minimum(self):
        p=deepcopy(self.pins);p["minimum_registry_epoch"]=6
        self.check(pins=p,defect="REGISTRY_EPOCH_BELOW_CALLER_MINIMUM",crypto=True)

    def test_56_missing_nonce_signed_receipt_never_promotes(self):
        a,b,_=self.packet()
        self.check(aa=a,bb=b,cc={},defect="CHALLENGE_ENVELOPE_SHAPE_INVALID",crypto=False)


if __name__ == "__main__":
    unittest.main()
