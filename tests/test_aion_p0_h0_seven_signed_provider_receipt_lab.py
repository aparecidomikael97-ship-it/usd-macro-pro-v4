"""Seven signed synthetic H0 documents: math != producer receipt authority."""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import atlasquant_aion_p0_h0_enrollment_revocation_nonce_lab as reg
import atlasquant_aion_p0_h0_dual_signed_witness_transcript_lab as wit
from atlasquant_aion_p0_h0_seven_signed_provider_receipt_lab import (
    SCHEMA, AUTHORITY_FALSE, BLOCKERS,
    PROVIDER_RECEIPT_SCHEMA, PROVIDER_HEAD_SCHEMA,
    inspect_seven_signed_provider_lab as inspect,
)
from test_aion_p0_h0_linked_five_envelopes_lab import (
    H0FiveEnvelopeCrossBindingTests as FiveFixture,
)


def key_public(key):
    return base64.urlsafe_b64encode(key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )).rstrip(b"=").decode("ascii")


def envelope(key, payload):
    return {
        "payload": deepcopy(payload),
        "signature_b64url": base64.urlsafe_b64encode(
            key.sign(reg.canonical_bytes(payload))
        ).rstrip(b"=").decode("ascii"),
    }


class H0SevenSignedProviderCausalReceiptLab(unittest.TestCase):
    def setUp(self):
        self.f = FiveFixture("test_01_five_valid_signatures_with_causal_links_never_authorize")
        self.f.setUp()
        self.effect_key = Ed25519PrivateKey.generate()
        self.head_key = Ed25519PrivateKey.generate()
        a,b,c,d,e = self.f.packet()
        self.receipt = {
            "schema": PROVIDER_RECEIPT_SCHEMA,
            "kind": "COMMITTED_EFFECT", "provider_id": "provider-lab-001",
            "key_id": "provider-receipt-key-001",
            "scope_digest": "a"*64, "request_id": "request-lab-001",
            "intent_id": "intent-lab-001", "attempt_nonce": "attempt-nonce-001",
            "operation_id": "provider-operation-001", "idempotency_ref": "idem-once-001",
            "reservation_sha256": hashlib.sha256(wit.canonical_bytes(d["payload"])).hexdigest(),
            "readback_sha256": hashlib.sha256(wit.canonical_bytes(e["payload"])).hexdigest(),
            "challenge_sha256": hashlib.sha256(reg.canonical_bytes(c["payload"])).hexdigest(),
            "provider_epoch": 9, "provider_sequence": 909,
            "provider_head_digest": "c"*64,
            "issued_at_utc": "2026-10-21T09:00:14Z",
            "effect_applied": True, "fence_applied": False,
            "fence_cutoff_sequence": 0, "future_dispatch_forbidden": True,
        }
        self.head = {
            "schema": PROVIDER_HEAD_SCHEMA,
            "provider_id": "provider-lab-001",
            "key_id": "provider-head-key-001", "scope_digest": "a"*64,
            "request_id": "request-lab-001", "intent_id": "intent-lab-001",
            "attempt_nonce": "attempt-nonce-001", "operation_id": "provider-operation-001",
            "provider_epoch": 9, "provider_sequence": 909,
            "provider_head_digest": "c"*64,
            "receipt_sha256": "", "observed_at_utc": "2026-10-21T09:00:16Z",
        }
        self.pins = {
            "provider_public_key_b64url": key_public(self.effect_key),
            "provider_head_public_key_b64url": key_public(self.head_key),
            "provider_key_id": "provider-receipt-key-001",
            "provider_head_key_id": "provider-head-key-001",
            "provider_id": "provider-lab-001",
            "operation_id": "provider-operation-001",
            "idempotency_ref": "idem-once-001",
            "minimum_provider_epoch": 9,
            "minimum_provider_sequence": 909,
            "expected_provider_head_digest": "c"*64,
        }
        self.now = "2026-10-21T09:00:19Z"

    def packet(self):
        first = self.f.packet()
        # Recalculate causal anchors from CURRENT parent payloads. Mutations
        # that should be caught as cross-layer hash conflicts use packet()
        # first and independently re-sign a tampered provider receipt.
        self.head["receipt_sha256"] = hashlib.sha256(
            reg.canonical_bytes(self.receipt)).hexdigest()
        return (*first, envelope(self.effect_key, self.receipt),
                envelope(self.head_key, self.head))

    def check(self, packet=None, pins=None, now=None, finding=None, linked=None,
              five_ok=None, receipt_ok=None, head_ok=None, kind=None):
        packet = self.packet() if packet is None else packet
        out = inspect(*packet, self.f.pins, self.f.expected,
                      self.pins if pins is None else pins,
                      now_utc=self.now if now is None else now)
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "HARD_NO_GO")
        self.assertIs(out["allowed"], False)
        self.assertTrue(out["simulation_only"])
        self.assertEqual(out["reconciliation_state"], "UNKNOWN_BLOCKED")
        self.assertEqual(out["blockers"], BLOCKERS)
        for flag in AUTHORITY_FALSE:
            self.assertIs(out[flag], False, flag)
        if finding:
            self.assertIn(finding, out["findings"])
        for attribute, expected in (
            ("synthetic_seven_envelopes_linked_lab", linked),
            ("synthetic_five_envelopes_consistent_lab", five_ok),
            ("synthetic_provider_receipt_signature_valid_lab", receipt_ok),
            ("synthetic_provider_head_signature_valid_lab", head_ok),
            ("claimed_provider_outcome_lab_only", kind),
        ):
            if expected is not None:
                self.assertEqual(out[attribute], expected, attribute)
        return out

    def as_fenced(self):
        self.receipt.update(kind="NO_EFFECT_FENCED", effect_applied=False,
                            fence_applied=True, fence_cutoff_sequence=909,
                            future_dispatch_forbidden=True)

    def as_unknown(self):
        self.receipt.update(kind="UNKNOWN", effect_applied=False,
                            fence_applied=False, fence_cutoff_sequence=0,
                            future_dispatch_forbidden=False)

    def test_01_committed_claim_valid_math_still_unknown(self):
        self.assertEqual(self.check(linked=True,five_ok=True,receipt_ok=True,head_ok=True,
                                    kind="COMMITTED_EFFECT")["findings"],())

    def test_02_signed_no_effect_fence_claim_does_not_allow_retry(self):
        self.as_fenced()
        x=self.check(linked=True,kind="NO_EFFECT_FENCED")
        self.assertFalse(x["provider_no_effect_fence_authenticated"])
        self.assertFalse(x["automatic_retry_allowed"])

    def test_03_signed_unknown_never_becomes_no_effect(self):
        self.as_unknown()
        self.check(linked=True,kind="UNKNOWN")

    def test_04_repeated_valid_receipts_cannot_prove_latest_or_consumption(self):
        p=self.packet()
        a=self.check(packet=p,linked=True)
        b=self.check(packet=p,linked=True)
        self.assertEqual(a,b)
        self.assertFalse(a["provider_latest_head_authenticated"])
        self.assertFalse(a["external_nonce_atomically_consumed"])

    def test_05_receipt_signature_tamper(self):
        p=list(self.packet());p[5]["payload"]["provider_sequence"]=910
        self.check(packet=p,finding="PROVIDER_RECEIPT_SIGNATURE_INVALID",linked=False)

    def test_06_head_signature_tamper(self):
        p=list(self.packet());p[6]["payload"]["provider_sequence"]=910
        self.check(packet=p,finding="PROVIDER_HEAD_SIGNATURE_INVALID",linked=False)

    def test_07_absent_receipt_rejected(self):
        p=list(self.packet());p[5]={}
        self.check(packet=p,finding="PROVIDER_RECEIPT_ENVELOPE_SHAPE_INVALID",linked=False)

    def test_08_unknown_receipt_authority_field_rejected(self):
        self.receipt["provider_enrolled"]=True
        self.check(finding="PROVIDER_RECEIPT_PAYLOAD_INVALID",linked=False)

    def test_09_evil_kind_cannot_run_eq(self):
        class Evil:
            def __eq__(self,other):raise RuntimeError("unsafe")
        p=list(self.packet());p[5]["payload"]["kind"]=Evil()
        self.check(packet=p,finding="PROVIDER_RECEIPT_PAYLOAD_INVALID",linked=False)

    def test_10_receipt_signature_padding_alias_rejected(self):
        p=list(self.packet());p[5]["signature_b64url"]+="="
        self.check(packet=p,finding="PROVIDER_RECEIPT_PUBLIC_KEY_OR_SIGNATURE_ENCODING_INVALID",linked=False)

    def test_11_head_noncanonical_signature_padding_bits_rejected(self):
        p=list(self.packet())
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        old=p[6]["signature_b64url"];i=alphabet.index(old[-1])
        p[6]["signature_b64url"]=old[:-1]+alphabet[(i&~15)|((i+1)&15)]
        self.check(packet=p,finding="PROVIDER_HEAD_PUBLIC_KEY_OR_SIGNATURE_ENCODING_INVALID",linked=False)

    def test_12_same_provider_keys_rejected_even_with_signatures(self):
        pins=deepcopy(self.pins)
        pins["provider_head_public_key_b64url"]=pins["provider_public_key_b64url"]
        self.check(pins=pins,finding="PROVIDER_KEYS_NOT_SEPARATED",linked=False)

    def test_13_same_provider_key_ids_rejected(self):
        pins=deepcopy(self.pins);pins["provider_head_key_id"]=pins["provider_key_id"]
        self.check(pins=pins,finding="PROVIDER_KEYS_NOT_SEPARATED",linked=False)

    def test_14_provider_receipt_key_reused_from_registry_root(self):
        self.effect_key=self.f.root
        self.pins["provider_public_key_b64url"]=key_public(self.effect_key)
        self.check(finding="TEST_PROVIDER_OR_WITNESS_KEY_REUSED",linked=False,five_ok=True)

    def test_15_provider_receipt_key_reused_from_reservation_signer(self):
        self.effect_key=self.f.writer
        self.pins["provider_public_key_b64url"]=key_public(self.effect_key)
        self.check(finding="TEST_PROVIDER_OR_WITNESS_KEY_REUSED",linked=False,five_ok=True)

    def test_16_provider_head_key_reused_from_readback_signer(self):
        self.head_key=self.f.reader
        self.pins["provider_head_public_key_b64url"]=key_public(self.head_key)
        self.check(finding="TEST_PROVIDER_OR_WITNESS_KEY_REUSED",linked=False,five_ok=True)

    def test_17_provider_id_binding_wrong(self):
        self.receipt["provider_id"]="provider-other-001"
        self.check(finding="PROVIDER_WITNESS_BINDING_MISMATCH:provider_id",linked=False)

    def test_18_scope_binding_wrong(self):
        self.receipt["scope_digest"]="f"*64
        self.check(finding="PROVIDER_WITNESS_BINDING_MISMATCH:scope_digest",linked=False)

    def test_19_request_binding_wrong(self):
        self.receipt["request_id"]="request-other-001"
        self.check(finding="PROVIDER_WITNESS_BINDING_MISMATCH:request_id",linked=False)

    def test_20_intent_binding_wrong(self):
        self.receipt["intent_id"]="intent-other-001"
        self.check(finding="PROVIDER_WITNESS_BINDING_MISMATCH:intent_id",linked=False)

    def test_21_attempt_nonce_binding_wrong(self):
        self.receipt["attempt_nonce"]="attempt-other-001"
        self.check(finding="PROVIDER_WITNESS_BINDING_MISMATCH:attempt_nonce",linked=False)

    def test_22_operation_binding_wrong(self):
        self.receipt["operation_id"]="operation-other-001"
        self.check(finding="PROVIDER_WITNESS_BINDING_MISMATCH:operation_id",linked=False)

    def test_23_idempotency_ref_mismatch(self):
        self.receipt["idempotency_ref"]="idem-other-001"
        self.check(finding="PROVIDER_IDEMPOTENCY_BINDING_MISMATCH",linked=False)

    def test_24_reservation_sha_wrong_but_resigned(self):
        self.receipt["reservation_sha256"]="f"*64
        self.check(finding="PROVIDER_CAUSAL_HASH_MISMATCH:reservation_sha256",linked=False)

    def test_25_readback_sha_wrong_but_resigned(self):
        self.receipt["readback_sha256"]="f"*64
        self.check(finding="PROVIDER_CAUSAL_HASH_MISMATCH:readback_sha256",linked=False)

    def test_26_challenge_sha_wrong_but_resigned(self):
        self.receipt["challenge_sha256"]="f"*64
        self.check(finding="PROVIDER_CAUSAL_HASH_MISMATCH:challenge_sha256",linked=False)

    def test_27_snapshot_receipt_sha_wrong_but_resigned(self):
        p=list(self.packet());p[6]["payload"]["receipt_sha256"]="f"*64
        p[6]=envelope(self.head_key,p[6]["payload"])
        self.check(packet=p,finding="PROVIDER_HEAD_NOT_BOUND_TO_RECEIPT",linked=False)

    def test_28_snapshot_provider_seq_differs_from_receipt(self):
        self.head["provider_sequence"]=910
        self.check(finding="PROVIDER_HEAD_SEQUENCE_NOT_EXACT_RECEIPT",linked=False)

    def test_29_snapshot_provider_epoch_differs(self):
        self.head["provider_epoch"]=10
        self.check(finding="PROVIDER_EPOCH_DIVERGED",linked=False)

    def test_30_provider_sequence_below_caller_minimum(self):
        self.receipt["provider_sequence"]=908
        self.head["provider_sequence"]=908
        self.check(finding="PROVIDER_SEQUENCE_BELOW_CALLER_MINIMUM",linked=False)

    def test_31_provider_epoch_below_caller_minimum(self):
        self.receipt["provider_epoch"]=8
        self.head["provider_epoch"]=8
        self.check(finding="PROVIDER_EPOCH_BELOW_CALLER_MINIMUM",linked=False)

    def test_32_snapshot_head_digest_conflicts(self):
        self.head["provider_head_digest"]="d"*64
        self.check(finding="PROVIDER_HEAD_DIGEST_DIVERGED",linked=False)

    def test_33_no_effect_claim_without_fence_denied(self):
        self.as_fenced();self.receipt["fence_applied"]=False
        self.check(finding="PROVIDER_RECEIPT_PAYLOAD_INVALID",linked=False)

    def test_34_no_effect_claim_allows_future_send_denied(self):
        self.as_fenced();self.receipt["future_dispatch_forbidden"]=False
        self.check(finding="PROVIDER_RECEIPT_PAYLOAD_INVALID",linked=False)

    def test_35_no_effect_fence_cutoff_behind_receipt_seq_denied(self):
        self.as_fenced();self.receipt["fence_cutoff_sequence"]=908
        self.check(finding="PROVIDER_RECEIPT_PAYLOAD_INVALID",linked=False)

    def test_36_no_effect_claim_with_applied_effect_denied(self):
        self.as_fenced();self.receipt["effect_applied"]=True
        self.check(finding="PROVIDER_RECEIPT_PAYLOAD_INVALID",linked=False)

    def test_37_committed_claim_without_effect_flag_denied(self):
        self.receipt["effect_applied"]=False
        self.check(finding="PROVIDER_RECEIPT_PAYLOAD_INVALID",linked=False)

    def test_38_committed_claim_with_fence_flag_denied(self):
        self.receipt["fence_applied"]=True
        self.check(finding="PROVIDER_RECEIPT_PAYLOAD_INVALID",linked=False)

    def test_39_unknown_claim_without_proof_cannot_claim_no_effect(self):
        self.as_unknown();self.receipt["fence_applied"]=True
        self.check(finding="PROVIDER_RECEIPT_PAYLOAD_INVALID",linked=False)

    def test_40_unknown_claim_cannot_enable_future_send_claim(self):
        self.as_unknown();self.receipt["future_dispatch_forbidden"]=True
        self.check(finding="PROVIDER_RECEIPT_PAYLOAD_INVALID",linked=False)

    def test_41_head_missing_payload(self):
        p=list(self.packet());p[6]={"signature_b64url":p[6]["signature_b64url"]}
        self.check(packet=p,finding="PROVIDER_HEAD_ENVELOPE_SHAPE_INVALID",linked=False)

    def test_42_hostile_dict_subclass_rejected(self):
        class Evil(dict):
            def __getitem__(self,key):raise RuntimeError("unsafe")
        p=list(self.packet());p[5]=Evil(p[5])
        self.check(packet=p,finding="PROVIDER_RECEIPT_ENVELOPE_SHAPE_INVALID",linked=False)

    def test_43_bool_sequence_not_accepted(self):
        self.receipt["provider_sequence"]=True
        self.check(finding="PROVIDER_RECEIPT_PAYLOAD_INVALID",linked=False)

    def test_44_nan_sequence_not_accepted(self):
        self.receipt["provider_sequence"]=float("nan")
        self.check(finding="PROVIDER_RECEIPT_PAYLOAD_INVALID",linked=False)

    def test_45_caller_provider_pins_claim_extra_verified_rejected(self):
        pins=deepcopy(self.pins);pins["provider_independently_verified"]=True
        self.check(pins=pins,finding="PROVIDER_PINS_SHAPE_INVALID",linked=False)

    def test_46_caller_provider_pins_object_not_plain_dict(self):
        class Evil(dict):
            def __getitem__(self,key):raise RuntimeError("unsafe")
        self.check(pins=Evil(self.pins),finding="PROVIDER_PINS_SHAPE_INVALID",linked=False)

    def test_47_invalid_caller_clock_rejected(self):
        self.check(now="2026-02-30T09:00:19Z",finding="CALLER_CLOCK_INVALID",linked=False)

    def test_48_provider_receipt_claim_before_witness_readback_invalid(self):
        self.receipt["issued_at_utc"]="2026-10-21T09:00:08Z"
        self.check(finding="CALLER_PROVIDER_OBSERVATION_WINDOW_INVALID",linked=False)

    def test_49_provider_head_claim_before_receipt_invalid(self):
        self.head["observed_at_utc"]="2026-10-21T09:00:13Z"
        self.check(finding="CALLER_PROVIDER_OBSERVATION_WINDOW_INVALID",linked=False)

    def test_50_head_observed_in_future_invalid(self):
        self.head["observed_at_utc"]="2026-10-21T09:00:20Z"
        self.check(finding="CALLER_PROVIDER_OBSERVATION_WINDOW_INVALID",linked=False)

    def test_51_provider_snapshot_stale_under_caller_clock_invalid(self):
        self.check(now="2026-10-21T09:04:00Z",
                   finding="FIVE:REGISTRY:CALLER_TIME_OR_NONCE_WINDOW_INVALID",linked=False)

    def test_52_parent_revocation_adulterated_blocks_provider_layer(self):
        p=list(self.packet());p[1]["payload"]["registry_seq"]=105
        self.check(packet=p,finding="FIVE:REGISTRY:REVOCATION_SIGNATURE_INVALID",linked=False)

    def test_53_parent_readback_adulterated_blocks_provider_layer(self):
        p=list(self.packet());p[4]["payload"]["sequence"]=1
        self.check(packet=p,finding="FIVE:WITNESS:READBACK_SIGNATURE_INVALID",linked=False)

    def test_54_roll_back_all_claimed_provider_cursors_still_not_trusted(self):
        self.receipt["provider_sequence"]=800
        self.head["provider_sequence"]=800
        self.pins["minimum_provider_sequence"]=800
        self.check(linked=True,kind="COMMITTED_EFFECT")

    def test_55_signed_claim_no_effect_with_unsigned_absence_not_enough(self):
        self.as_fenced()
        x=self.check(linked=True)
        self.assertIs(x["provider_no_effect_fence_authenticated"],False)
        self.assertIs(x["outbox_terminal_transition_allowed"],False)

    def test_56_replacing_provider_root_and_resigning_still_not_authentic(self):
        self.effect_key=Ed25519PrivateKey.generate()
        self.head_key=Ed25519PrivateKey.generate()
        self.pins["provider_public_key_b64url"]=key_public(self.effect_key)
        self.pins["provider_head_public_key_b64url"]=key_public(self.head_key)
        x=self.check(linked=True)
        self.assertIs(x["provider_identity_enrolled_independently"],False)

    def test_57_snapshot_operation_id_differs_from_receipt(self):
        self.head["operation_id"]="provider-other-001"
        self.check(finding="PROVIDER_WITNESS_BINDING_MISMATCH:operation_id",linked=False)

    def test_58_provider_receipt_signer_key_id_mismatch(self):
        self.receipt["key_id"]="provider-other-key"
        self.check(finding="PROVIDER_ROLE_KEY_ID_MISMATCH",linked=False)

    def test_59_provider_head_signer_key_id_mismatch(self):
        self.head["key_id"]="provider-other-key"
        self.check(finding="PROVIDER_ROLE_KEY_ID_MISMATCH",linked=False)

    def test_60_unknown_claim_never_allows_second_send(self):
        self.as_unknown()
        x=self.check(linked=True)
        self.assertFalse(x["automatic_retry_allowed"])
        self.assertFalse(x["first_external_effect_allowed"])


if __name__=="__main__":
    unittest.main()
