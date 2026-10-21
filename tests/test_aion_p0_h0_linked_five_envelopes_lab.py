"""H0 bridge: five synthetic Ed25519 documents, ALWAYS HARD_NO_GO."""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import atlasquant_aion_p0_h0_enrollment_revocation_nonce_lab as registry
import atlasquant_aion_p0_h0_dual_signed_witness_transcript_lab as witness
from atlasquant_aion_p0_h0_linked_five_envelopes_lab import (
    SCHEMA, AUTHORITY_FALSE, PERMANENT_BLOCKERS,
    inspect_linked_five_envelopes_lab as inspect,
)


def pub(key):
    return base64.urlsafe_b64encode(key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )).rstrip(b"=").decode("ascii")


def signed(key, payload, byte_encoder):
    raw = key.sign(byte_encoder(payload))
    return {"payload": deepcopy(payload),
            "signature_b64url": base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")}


class H0FiveEnvelopeCrossBindingTests(unittest.TestCase):
    def setUp(self):
        self.root = Ed25519PrivateKey.generate()
        self.custodian = Ed25519PrivateKey.generate()
        self.writer = Ed25519PrivateKey.generate()
        self.reader = Ed25519PrivateKey.generate()
        self.enroll = {
            "schema": registry.ENROLL_SCHEMA,
            "issuer_id": "issuer-lab-001", "scope_digest": "a"*64,
            "registry_epoch": 5, "registry_seq": 100,
            "registry_version_id": "registry-version-001",
            "signed_at_utc": "2026-10-21T09:00:00Z",
            "roles": [
                {"role": "reservation_signer", "key_id": "writer-key-001",
                 "public_key_b64url": pub(self.writer), "key_epoch": 5, "status": "ACTIVE"},
                {"role": "readback_witness", "key_id": "reader-key-001",
                 "public_key_b64url": pub(self.reader), "key_epoch": 5, "status": "ACTIVE"},
            ],
        }
        self.revoke = {
            "schema": registry.REVOCATION_SCHEMA, "issuer_id": "issuer-lab-001",
            "scope_digest": "a"*64, "registry_epoch": 5, "registry_seq": 101,
            "enrollment_sha256": "", "signed_at_utc": "2026-10-21T09:00:03Z",
            "revoked_key_ids": [], "active_key_ids": ["reader-key-001", "writer-key-001"],
        }
        self.nonce = {
            "schema": registry.NONCE_SCHEMA, "issuer_id": "issuer-lab-001",
            "scope_digest": "a"*64, "request_id": "request-lab-001",
            "intent_id": "intent-lab-001", "challenge_nonce": "challenge-lab-001",
            "registry_epoch": 5, "registry_seq": 101, "revocation_sha256": "",
            "custody_counter": 500, "issued_at_utc": "2026-10-21T09:00:05Z",
            "expires_at_utc": "2026-10-21T09:00:25Z",
            "head_digest": "b"*64, "head_sequence": 5000,
        }
        self.reserve = {
            "schema": witness.RESERVE_SCHEMA, "kind": witness.RESERVATION,
            "issuer_id": "issuer-lab-001", "key_id": "writer-key-001",
            "scope_digest": "a"*64, "request_id": "request-lab-001",
            "intent_id": "intent-lab-001", "attempt_nonce": "attempt-nonce-001",
            "epoch": 8, "sequence": 5000, "head_digest": "b"*64,
            "version_id": "version-lab-5000", "issued_at_utc": "2026-10-21T09:00:07Z",
        }
        self.read = {
            "schema": witness.READ_SCHEMA, "kind": witness.READBACK,
            **{k:v for k,v in self.reserve.items() if k not in (
                "schema", "kind", "key_id", "issued_at_utc")},
            "key_id": "reader-key-001", "reservation_sha256": "",
            "challenge_nonce": "challenge-lab-001",
            "observed_at_utc": "2026-10-21T09:00:10Z",
        }
        self.pins = {
            "registry_root_public_key_b64url": pub(self.root),
            "custodian_public_key_b64url": pub(self.custodian),
            "issuer_id": "issuer-lab-001", "scope_digest": "a"*64,
            "request_id": "request-lab-001", "intent_id": "intent-lab-001",
            "challenge_nonce": "challenge-lab-001",
            "minimum_registry_epoch": 5, "minimum_registry_seq": 101,
            "minimum_custody_counter": 500, "expected_head_digest": "b"*64,
            "expected_head_sequence": 5000,
        }
        self.expected = {
            "attempt_nonce": "attempt-nonce-001",
            "expected_head_epoch": 8,
            "expected_version_id": "version-lab-5000",
        }
        self.now = "2026-10-21T09:00:12Z"

    def packet(self):
        self.revoke["enrollment_sha256"] = hashlib.sha256(
            registry.canonical_bytes(self.enroll)).hexdigest()
        self.nonce["revocation_sha256"] = hashlib.sha256(
            registry.canonical_bytes(self.revoke)).hexdigest()
        self.read["reservation_sha256"] = hashlib.sha256(
            witness.canonical_bytes(self.reserve)).hexdigest()
        return (
            signed(self.root, self.enroll, registry.canonical_bytes),
            signed(self.root, self.revoke, registry.canonical_bytes),
            signed(self.custodian, self.nonce, registry.canonical_bytes),
            signed(self.writer, self.reserve, witness.canonical_bytes),
            signed(self.reader, self.read, witness.canonical_bytes),
        )

    def check(self, packet=None, pins=None, expected=None, now=None, finding=None,
              linked=None, registry_ok=None, witness_ok=None):
        args = self.packet() if packet is None else packet
        result = inspect(
            *args, self.pins if pins is None else pins,
            self.expected if expected is None else expected,
            now_utc=self.now if now is None else now,
        )
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["state"], "HARD_NO_GO")
        self.assertIs(result["allowed"], False)
        self.assertIs(result["simulation_only"], True)
        self.assertEqual(result["blockers"], PERMANENT_BLOCKERS)
        for flag in AUTHORITY_FALSE:
            self.assertIs(result[flag], False, flag)
        if finding:
            self.assertIn(finding, result["findings"])
        if linked is not None:
            self.assertIs(result["synthetic_five_envelopes_linked_lab"], linked)
        if registry_ok is not None:
            self.assertIs(result["synthetic_registry_chain_consistent_lab"], registry_ok)
        if witness_ok is not None:
            self.assertIs(result["synthetic_witness_pair_consistent_lab"], witness_ok)
        return result

    def test_01_five_valid_signatures_with_causal_links_never_authorize(self):
        self.assertEqual(self.check(linked=True,registry_ok=True,witness_ok=True)["findings"], ())

    def test_02_replay_identical_signed_bundle_is_not_nonce_consumption(self):
        pkt=self.packet()
        a=self.check(packet=pkt,linked=True)
        b=self.check(packet=pkt,linked=True)
        self.assertEqual(a,b)
        self.assertIs(a["nonce_replay_excluded"],False)

    def test_03_reservation_payload_tamper_rejected(self):
        p=list(self.packet());p[3]["payload"]["sequence"]=5001
        self.check(packet=p,finding="WITNESS:RESERVATION_SIGNATURE_INVALID",linked=False)

    def test_04_readback_payload_tamper_rejected(self):
        p=list(self.packet());p[4]["payload"]["sequence"]=5001
        self.check(packet=p,finding="WITNESS:READBACK_SIGNATURE_INVALID",linked=False)

    def test_05_registry_enrollment_signature_tamper_rejected(self):
        p=list(self.packet());p[0]["payload"]["registry_seq"]=102
        self.check(packet=p,finding="REGISTRY:ENROLLMENT_SIGNATURE_INVALID",linked=False)

    def test_06_revocation_signature_tamper_rejected(self):
        p=list(self.packet());p[1]["payload"]["registry_seq"]=102
        self.check(packet=p,finding="REGISTRY:REVOCATION_SIGNATURE_INVALID",linked=False)

    def test_07_custodian_signature_tamper_rejected(self):
        p=list(self.packet());p[2]["payload"]["custody_counter"]=501
        self.check(packet=p,finding="REGISTRY:CHALLENGE_SIGNATURE_INVALID",linked=False)

    def test_08_writer_replaced_in_signed_registry_but_old_writer_signed(self):
        self.enroll["roles"][0]["public_key_b64url"]=pub(Ed25519PrivateKey.generate())
        self.check(finding="WITNESS:RESERVATION_SIGNATURE_INVALID",linked=False,registry_ok=True)

    def test_09_reader_replaced_in_signed_registry_but_old_reader_signed(self):
        self.enroll["roles"][1]["public_key_b64url"]=pub(Ed25519PrivateKey.generate())
        self.check(finding="WITNESS:READBACK_SIGNATURE_INVALID",linked=False,registry_ok=True)

    def test_10_writer_key_id_replaced_in_signed_registry(self):
        self.enroll["roles"][0]["key_id"]="writer-key-other"
        self.revoke["active_key_ids"]=["reader-key-001","writer-key-other"]
        self.check(finding="WITNESS:ROLE_KEY_BINDING_MISMATCH",linked=False,registry_ok=True)

    def test_11_reader_key_id_replaced_in_signed_registry(self):
        self.enroll["roles"][1]["key_id"]="reader-key-other"
        self.revoke["active_key_ids"]=["reader-key-other","writer-key-001"]
        self.check(finding="WITNESS:ROLE_KEY_BINDING_MISMATCH",linked=False,registry_ok=True)

    def test_12_key_reuse_inside_registry_rejected(self):
        self.enroll["roles"][1]["public_key_b64url"]=self.enroll["roles"][0]["public_key_b64url"]
        self.check(finding="REGISTRY:ENROLLMENT_PAYLOAD_INVALID",linked=False)

    def test_13_root_key_equal_writer_role_rejected_even_if_signed(self):
        self.root=self.writer
        self.pins["registry_root_public_key_b64url"]=pub(self.root)
        self.check(finding="ROOT_CUSTODIAN_OR_WITNESS_KEY_REUSED",linked=False,registry_ok=True)

    def test_14_custodian_key_equal_reader_role_rejected_even_if_signed(self):
        self.custodian=self.reader
        self.pins["custodian_public_key_b64url"]=pub(self.custodian)
        self.check(finding="ROOT_CUSTODIAN_OR_WITNESS_KEY_REUSED",linked=False,registry_ok=True)

    def test_15_signed_readback_nonce_differs_from_signed_custody(self):
        self.read["challenge_nonce"]="challenge-other-001"
        self.check(finding="WITNESS:READBACK_CHALLENGE_MISMATCH",linked=False)

    def test_16_signed_readback_nonce_differs_from_resigned_custody(self):
        self.nonce["challenge_nonce"]="challenge-new-001"
        self.pins["challenge_nonce"]="challenge-new-001"
        self.check(finding="WITNESS:READBACK_CHALLENGE_MISMATCH",linked=False)

    def test_17_readback_request_mismatch(self):
        self.read["request_id"]="request-other-001"
        self.check(finding="WITNESS:PIN_BINDING_MISMATCH:request_id",linked=False)

    def test_18_reservation_intent_mismatch(self):
        self.reserve["intent_id"]="intent-other-001"
        self.check(finding="WITNESS:PIN_BINDING_MISMATCH:intent_id",linked=False)

    def test_19_reservation_scope_mismatch(self):
        self.reserve["scope_digest"]="c"*64
        self.check(finding="WITNESS:PIN_BINDING_MISMATCH:scope_digest",linked=False)

    def test_20_readback_issuer_mismatch(self):
        self.read["issuer_id"]="issuer-other-001"
        self.check(finding="WITNESS:PIN_BINDING_MISMATCH:issuer_id",linked=False)

    def test_21_both_signed_witness_heads_differ_from_signed_custodian_sequence(self):
        self.reserve["sequence"]=5001
        self.read["sequence"]=5001
        self.check(finding="RESERVATION_HEAD_SEQUENCE_NOT_IN_SIGNED_CHALLENGE",
                   linked=False,registry_ok=True,witness_ok=True)

    def test_22_both_signed_witness_heads_differ_from_signed_custodian_digest(self):
        self.reserve["head_digest"]="c"*64
        self.read["head_digest"]="c"*64
        self.check(finding="WITNESS:PIN_BINDING_MISMATCH:head_digest",
                   linked=False,registry_ok=True)

    def test_23_signed_head_epoch_above_expected_but_not_exact(self):
        self.reserve["epoch"]=9
        self.read["epoch"]=9
        self.check(finding="HEAD_EPOCH_NOT_EXACT_CALLER_EXPECTATION",
                   linked=False,registry_ok=True,witness_ok=True)

    def test_24_signed_head_epoch_below_expected_rejected(self):
        self.reserve["epoch"]=7
        self.read["epoch"]=7
        self.check(finding="WITNESS:SIGNED_HEAD_BELOW_CALLER_MINIMUM",linked=False)

    def test_25_signed_version_mismatch(self):
        self.reserve["version_id"]="version-lab-other"
        self.read["version_id"]="version-lab-other"
        self.check(finding="WITNESS:PIN_BINDING_MISMATCH:version_id",linked=False)

    def test_26_reservation_signed_before_signed_nonce_issued(self):
        self.reserve["issued_at_utc"]="2026-10-21T09:00:04Z"
        self.check(finding="SIGNED_CHALLENGE_RESERVATION_READBACK_ORDER_INVALID",
                   linked=False,registry_ok=True,witness_ok=True)

    def test_27_readback_after_nonce_expiry_stays_blocked(self):
        self.now="2026-10-21T09:00:30Z"
        self.read["observed_at_utc"]="2026-10-21T09:00:28Z"
        self.check(finding="REGISTRY:CALLER_TIME_OR_NONCE_WINDOW_INVALID",linked=False)

    def test_28_expectations_are_not_authority_and_must_be_exact_shape(self):
        p=deepcopy(self.expected);p["caller_verified"]=True
        self.check(expected=p,finding="CALLER_EXPECTATIONS_INVALID",linked=False)

    def test_29_hostile_expected_epoch_rejected_before_comparison(self):
        class Evil:
            def __eq__(self, other): raise RuntimeError("unsafe")
        p=deepcopy(self.expected);p["expected_head_epoch"]=Evil()
        self.check(expected=p,finding="CALLER_EXPECTATIONS_INVALID",linked=False)

    def test_30_bool_epoch_not_valid(self):
        p=deepcopy(self.expected);p["expected_head_epoch"]=True
        self.check(expected=p,finding="CALLER_EXPECTATIONS_INVALID",linked=False)

    def test_31_bad_caller_clock_rejected(self):
        self.check(now="2026-13-21T09:00:12Z",finding="REGISTRY:CALLER_CLOCK_INVALID",linked=False)

    def test_32_revoked_writer_blocks_integrated_chain(self):
        self.enroll["roles"][0]["status"]="REVOKED"
        self.revoke["active_key_ids"]=["reader-key-001"]
        self.revoke["revoked_key_ids"]=["writer-key-001"]
        self.check(finding="REGISTRY:ENROLLED_ROLE_REVOKED_OR_INACTIVE",linked=False)

    def test_33_revoked_reader_blocks_integrated_chain(self):
        self.enroll["roles"][1]["status"]="REVOKED"
        self.revoke["active_key_ids"]=["writer-key-001"]
        self.revoke["revoked_key_ids"]=["reader-key-001"]
        self.check(finding="REGISTRY:ENROLLED_KEY_REVOKED",linked=False)

    def test_34_old_revocation_sequence_below_caller_minimum_rejected(self):
        self.revoke["registry_seq"]=100
        self.nonce["registry_seq"]=100
        self.check(finding="REGISTRY:REVOCATION_SEQ_BELOW_CALLER_MINIMUM",linked=False)

    def test_35_signed_nonce_custody_counter_below_minimum_rejected(self):
        self.nonce["custody_counter"]=499
        self.check(finding="REGISTRY:CUSTODY_COUNTER_BELOW_CALLER_MINIMUM",linked=False)

    def test_36_hostile_schema_in_readback_rejected_cleanly(self):
        class Evil:
            def __eq__(self, other): return True
        p=list(self.packet());p[4]["payload"]["schema"]=Evil()
        self.check(packet=p,finding="WITNESS:READBACK_TRANSCRIPT_INVALID",linked=False)

    def test_37_hostile_envelope_dict_subclass_rejected(self):
        class Evil(dict):
            def __getitem__(self, key): raise RuntimeError("unsafe")
        p=list(self.packet());p[0]=Evil(p[0])
        self.check(packet=p,finding="REGISTRY:ENROLLMENT_ENVELOPE_SHAPE_INVALID",linked=False)

    def test_38_signature_padding_alias_rejected(self):
        p=list(self.packet());p[3]["signature_b64url"]+="="
        self.check(packet=p,
                   finding="WITNESS:RESERVATION_SIGNATURE_OR_PUBLIC_KEY_ENCODING_INVALID",
                   linked=False)

    def test_39_extra_authority_field_in_signed_readback_rejected(self):
        p=list(self.packet());p[4]["payload"]["effect_allowed"]=True
        self.check(packet=p,finding="WITNESS:READBACK_TRANSCRIPT_INVALID",linked=False)

    def test_40_extra_caller_claim_on_registry_pins_rejected(self):
        p=deepcopy(self.pins);p["independently_enrolled"]=True
        self.check(pins=p,finding="REGISTRY:CALLER_PINS_INVALID",linked=False)

    def test_41_attacker_self_signed_five_consistent_documents_no_authority(self):
        # setUp keys are fully attacker-controlled synthetic test keys.
        x=self.check(linked=True)
        self.assertIs(x["external_issuer_independently_enrolled"],False)
        self.assertIs(x["first_external_effect_allowed"],False)

    def test_42_digest_link_between_reservation_and_readback_rejects_forgery(self):
        self.read["reservation_sha256"]="d"*64
        # packet() intentionally overwrites the fixture's digest, so tamper
        # the already signed readback and re-sign only this layer.
        p=list(self.packet())
        p[4]["payload"]["reservation_sha256"]="d"*64
        p[4]=signed(self.reader,p[4]["payload"],witness.canonical_bytes)
        self.check(packet=p,finding="WITNESS:READBACK_NOT_BOUND_TO_RESERVATION",linked=False)

    def test_43_noncanonical_last_sextet_signature_alias_rejected(self):
        p=list(self.packet())
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        x=p[4]["signature_b64url"];i=alphabet.index(x[-1]);replacement=alphabet[(i&~15)|((i+1)&15)]
        self.assertNotEqual(replacement,x[-1])
        p[4]["signature_b64url"]=x[:-1]+replacement
        self.check(packet=p,
                   finding="WITNESS:READBACK_SIGNATURE_OR_PUBLIC_KEY_ENCODING_INVALID",
                   linked=False)

    def test_44_replay_with_self_rolled_back_caller_head_still_no_real_freshness(self):
        # A caller fully controls the synthetic head expectation and entire
        # signed chain. Coherent replacement is mathematically valid but
        # NEVER an authenticated "latest" external state.
        self.nonce["head_sequence"]=4000
        self.pins["expected_head_sequence"]=4000
        self.reserve["sequence"]=4000
        self.read["sequence"]=4000
        p=self.check(linked=True)
        self.assertIs(p["latest_remote_head_authenticated"],False)
        self.assertIs(p["nonce_replay_excluded"],False)


if __name__ == "__main__":
    unittest.main()
