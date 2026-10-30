"""A320 LAB: claimed two-custodian offline ceremony with a real A319 check.

No human identity, independent transport, physical custody, trusted clock,
external high-water or provider outcome is established in this test runner.
The synthetic signers can all be recreated by the same Python process.
"""
import copy
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from labs.a317_detached_signed_intent_anchor_lab import sha, encode
from labs.a319_offline_root_continuity_lab import (
    SCHEMA as A319_SCHEMA, authorization_bytes,
)
from labs.a320_offline_custody_ceremony_lab import (
    SCHEMA, PRECOMMIT_FIELDS, ALL_FIELDS, TRANSITION_KEYS,
    signable_bytes, verify_offline_custody_ceremony,
)


def public_hex(key):
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()


class A320OfflineCustodyCeremonyTests(unittest.TestCase):
    def setUp(self):
        self.old_signers = {
            "synthetic-old-A": Ed25519PrivateKey.generate(),
            "synthetic-old-B": Ed25519PrivateKey.generate(),
        }
        self.new_signers = {
            "synthetic-new-A": Ed25519PrivateKey.generate(),
            "synthetic-new-B": Ed25519PrivateKey.generate(),
        }
        self.custodians = {
            "lab-custodian-A": Ed25519PrivateKey.generate(),
            "lab-custodian-B": Ed25519PrivateKey.generate(),
        }
        self.old = {
            "schema": A319_SCHEMA, "generation": 5,
            "roots": {k: public_hex(v) for k, v in self.old_signers.items()},
            "revoked_root_ids": [], "high_water_sequence": 20,
            "high_water_sha256": "a" * 64, "incident_epoch": 3,
        }
        self.next = {
            **copy.deepcopy(self.old), "generation": 6,
            "roots": {k: public_hex(v) for k, v in self.new_signers.items()},
            "revoked_root_ids": sorted(self.old["roots"]),
            "previous_manifest_sha256": sha(encode(self.old)),
            "challenge_nonce": "b" * 64,
            "issued_at": 10000, "expires_at": 10100,
            "decision": "HOLD_ONLY",
        }
        self.pins = {k: public_hex(v) for k, v in self.custodians.items()}
        self.resign_transition()
        self.precommit = self.make_precommit()
        self.packets = self.make_packets()

    def resign_transition(self):
        self.transition = {
            "previous_manifest": self.old,
            "candidate_manifest": self.next,
            "pinned_previous_digest": sha(encode(self.old)),
            "old_root_signatures": {
                k: key.sign(
                    authorization_bytes(self.next, new_root=False)
                ).hex() for k, key in self.old_signers.items()
            },
            "new_root_signatures": {
                k: key.sign(
                    authorization_bytes(self.next, new_root=True)
                ).hex() for k, key in self.new_signers.items()
            },
            "expected_nonce": "b" * 64,
            "expected_incident_epoch": 3,
            "observed_clock_epoch": 10040,
        }

    def make_precommit(self):
        return {
            "schema": SCHEMA, "ceremony_id": "a320-lab-ceremony",
            "candidate_manifest_sha256": sha(encode(self.next)),
            "previous_manifest_sha256": sha(encode(self.old)),
            "root_generation": self.next["generation"],
            "incident_epoch": self.next["incident_epoch"],
            "high_water_sequence": self.next["high_water_sequence"],
            "high_water_sha256": self.next["high_water_sha256"],
            "challenge_nonce": self.next["challenge_nonce"],
            "recorded_at": 9990,
        }

    def make_packets(self):
        records = []
        for i, (name, key) in enumerate(sorted(self.custodians.items())):
            packet = {
                **self.precommit,
                "custodian_id": name,
                "custody_domain": "domain-" + str(i),
                "channel_id": "offline-channel-" + str(i),
                "device_id": "offline-device-" + str(i),
                "evidence_digest": sha(("different-artifact-" + str(i)).encode()),
                "witnessed_at": 10020 + i,
                "decision": "HOLD_ONLY",
            }
            packet["signature_hex"] = key.sign(
                signable_bytes(packet)
            ).hex()
            records.append(packet)
        return records

    def resign_packets(self):
        for packet in self.packets:
            packet["signature_hex"] = self.custodians[
                packet["custodian_id"]
            ].sign(signable_bytes(packet)).hex()

    def verify(self, **kwargs):
        data = {
            "transition_request": self.transition,
            "offline_precommit": self.precommit,
            "custodian_packets": self.packets,
            "custodian_pins": self.pins,
        }
        data.update(kwargs)
        return verify_offline_custody_ceremony(**data)

    def assert_hold(self, r):
        self.assertEqual(r["schema"], SCHEMA)
        self.assertTrue(r["research_only"])
        self.assertTrue(r["synthetic_only"])
        self.assertFalse(r["physical_separation_independently_verified"])
        self.assertFalse(r["independent_custodian_identity_authenticated"])
        self.assertFalse(r["external_precommit_authenticated"])
        self.assertFalse(r["trusted_receipt_delivery_verified"])
        self.assertFalse(r["custodian_keys_independently_pinned"])
        self.assertFalse(r["trusted_clock_or_timestamp_verified"])
        self.assertFalse(r["external_high_water_proven"])
        self.assertFalse(r["durable_off_host_intent_custody_proven"])
        self.assertFalse(r["external_provider_ack_proven"])
        self.assertFalse(r["semantic_exactly_once_proven"])
        self.assertFalse(r["can_authorize_real_effect"])
        self.assertFalse(r["can_resume"])
        self.assertFalse(r["can_resend"])
        self.assertFalse(r["can_auto_retry"])
        self.assertEqual(r["automatic_retries"], 0)
        self.assertTrue(r["zero_auto_resend"])
        self.assertTrue(r["hard_no_go"])
        self.assertEqual(r["p0_homologated"], 0)
        self.assertTrue(r["no_worker_deploy_provider_orders"])
        self.assertFalse(r["new_paid_services"])

    def assert_veto(self, result, issue):
        self.assertEqual(result["status"], "LAB_CUSTODY_CEREMONY_VETO")
        self.assertIn(issue, result["issues"])
        self.assert_hold(result)

    def test_coherent_two_packets_still_not_independent_custody(self):
        result = self.verify()
        self.assertEqual(result["status"],
                         "LAB_TWO_CUSTODY_PACKETS_COHERENT_BUT_UNVERIFIED")
        self.assertEqual(result["mathematically_valid_custodian_signatures"], 2)
        self.assertTrue(result["root_rotation_mathematically_consistent"])
        self.assertTrue(result["packet_consistency_observed"])
        self.assertFalse(result["external_precommit_authenticated"])
        self.assert_hold(result)

    def test_strict_packet_and_precommit_field_sets(self):
        self.assertEqual(set(self.precommit), PRECOMMIT_FIELDS)
        self.assertEqual(set(self.packets[0]), ALL_FIELDS)
        self.assertEqual(set(self.transition), TRANSITION_KEYS)

    def test_first_bootstrap_without_precommit_is_denied(self):
        self.assert_veto(self.verify(offline_precommit=None),
                         "PRECOMMIT_MISSING_OR_MALFORMED")

    def test_precommit_not_a_substitute_for_independent_source(self):
        result = self.verify()
        self.assertTrue(result["packet_consistency_observed"])
        self.assertFalse(result["external_precommit_authenticated"])
        self.assertFalse(result["custodian_keys_independently_pinned"])
        self.assert_hold(result)

    def test_missing_second_custodian_denied(self):
        self.assert_veto(self.verify(custodian_packets=self.packets[:1]),
                         "EXACT_TWO_CUSTODIAN_PACKETS_REQUIRED")

    def test_missing_second_custodian_pin_denied(self):
        self.assert_veto(self.verify(custodian_pins={
            "lab-custodian-A": self.pins["lab-custodian-A"]
        }), "EXACT_TWO_CUSTODIAN_PINS_REQUIRED")

    def test_same_key_twice_denied_even_if_names_differ(self):
        pins = dict(self.pins)
        pins["lab-custodian-B"] = pins["lab-custodian-A"]
        self.assert_veto(self.verify(custodian_pins=pins),
                         "CUSTODIAN_PINS_REUSED")

    def test_same_custody_domain_claim_denied(self):
        self.packets[1]["custody_domain"] = self.packets[0]["custody_domain"]
        self.resign_packets()
        self.assert_veto(self.verify(), "CUSTODY_DOMAIN_REUSED")

    def test_same_delivery_channel_claim_denied(self):
        self.packets[1]["channel_id"] = self.packets[0]["channel_id"]
        self.resign_packets()
        self.assert_veto(self.verify(), "DELIVERY_CHANNEL_REUSED")

    def test_same_media_device_claim_denied(self):
        self.packets[1]["device_id"] = self.packets[0]["device_id"]
        self.resign_packets()
        self.assert_veto(self.verify(), "MEDIA_DEVICE_REUSED")

    def test_copied_evidence_artifact_fingerprint_denied(self):
        self.packets[1]["evidence_digest"] = self.packets[0]["evidence_digest"]
        self.resign_packets()
        self.assert_veto(self.verify(), "EVIDENCE_DIGEST_REUSED")

    def test_same_signer_id_claim_denied(self):
        self.packets[1]["custodian_id"] = self.packets[0]["custodian_id"]
        self.packets[1]["signature_hex"] = self.custodians[
            self.packets[0]["custodian_id"]
        ].sign(signable_bytes(self.packets[1])).hex()
        self.assert_veto(self.verify(), "CUSTODIAN_ID_REUSED")

    def test_identity_not_in_pinned_custodian_set_denied(self):
        self.packets[1]["custodian_id"] = "unknown-witness"
        self.assert_veto(self.verify(), "CUSTODIAN_NOT_IN_PINSET")

    def test_wrong_public_key_denied(self):
        pins = dict(self.pins)
        pins["lab-custodian-B"] = public_hex(Ed25519PrivateKey.generate())
        self.assert_veto(self.verify(custodian_pins=pins),
                         "CUSTODIAN_SIGNATURE_INVALID")

    def test_signature_changed_after_signing_denied(self):
        self.packets[0]["signature_hex"] = "0" * 128
        self.assert_veto(self.verify(), "CUSTODIAN_SIGNATURE_INVALID")

    def test_signed_statement_cannot_authorize_go(self):
        self.packets[0]["decision"] = "GO_DEPLOY"
        self.assert_veto(self.verify(), "CUSTODIAN_PACKET_INVALID")

    def test_extra_release_field_denied(self):
        self.packets[0]["can_resume"] = True
        self.assert_veto(self.verify(), "CUSTODIAN_PACKET_INVALID")

    def test_custodian_packet_precommit_tampering_denied(self):
        self.packets[0]["root_generation"] += 1
        self.resign_packets()
        self.assert_veto(self.verify(), "CUSTODIAN_PACKET_PRECOMMIT_MISMATCH")

    def test_precommit_must_match_manifest_hash(self):
        pre = dict(self.precommit)
        pre["candidate_manifest_sha256"] = "0" * 64
        self.assert_veto(self.verify(offline_precommit=pre),
                         "PRECOMMIT_CANDIDATE_MANIFEST_SHA256_MISMATCH")

    def test_previous_manifest_hash_tampering_denied(self):
        pre = dict(self.precommit)
        pre["previous_manifest_sha256"] = "f" * 64
        self.assert_veto(self.verify(offline_precommit=pre),
                         "PRECOMMIT_PREVIOUS_MANIFEST_SHA256_MISMATCH")

    def test_precommit_after_candidate_issuance_is_denied(self):
        pre = dict(self.precommit)
        pre["recorded_at"] = 10001
        self.assert_veto(self.verify(offline_precommit=pre),
                         "PRECOMMIT_NOT_BEFORE_ROTATION")

    def test_witness_receipt_before_precommit_denied(self):
        self.packets[1]["witnessed_at"] = 9980
        self.resign_packets()
        self.assert_veto(self.verify(), "CUSTODIAN_PACKET_BEFORE_PRECOMMIT")

    def test_witness_receipt_after_expiry_denied(self):
        self.packets[0]["witnessed_at"] = 10101
        self.resign_packets()
        self.assert_veto(self.verify(), "CUSTODIAN_PACKET_EXPIRED")

    def test_manifest_incident_epoch_does_not_match_precommit(self):
        pre = dict(self.precommit)
        pre["incident_epoch"] += 1
        self.assert_veto(self.verify(), "LAB_CUSTODY_CEREMONY_VETO") if False else self.assert_veto(
            self.verify(offline_precommit=pre),
            "PRECOMMIT_INCIDENT_EPOCH_MISMATCH",
        )

    def test_failed_root_rotation_cannot_be_bypassed_by_two_packets(self):
        transition = dict(self.transition)
        transition["pinned_previous_digest"] = "f" * 64
        self.assert_veto(self.verify(transition_request=transition),
                         "A319_ROTATION_MATHEMATICS_DENIED")

    def test_old_root_signature_missing_denied_even_if_packets_valid(self):
        transition = dict(self.transition)
        transition["old_root_signatures"] = {}
        self.assert_veto(self.verify(transition_request=transition),
                         "A319_ROTATION_MATHEMATICS_DENIED")

    def test_invalid_transition_envelope_denied(self):
        self.assert_veto(self.verify(transition_request={"status": "GO"}),
                         "ROOT_TRANSITION_ENVELOPE_INVALID")

    def test_noncanonical_pin_types_never_crash_or_grant_authority(self):
        for pins in (None, [], {"lab-A": []}, {"A": True, "B": b"0"}):
            with self.subTest(pins=repr(pins)):
                r = self.verify(custodian_pins=pins)
                self.assertEqual(r["status"], "LAB_CUSTODY_CEREMONY_VETO")
                self.assert_hold(r)

    def test_falsified_all_evidence_on_same_host_can_still_pass_math(self):
        """Known false positive: two Python keys do not create 2 custodians."""
        self.custodians = {
            "fictional-custodian-X": Ed25519PrivateKey.generate(),
            "fictional-custodian-Y": Ed25519PrivateKey.generate(),
        }
        self.pins = {k: public_hex(v) for k, v in self.custodians.items()}
        self.packets = self.make_packets()
        r = self.verify()
        self.assertEqual(r["status"],
                         "LAB_TWO_CUSTODY_PACKETS_COHERENT_BUT_UNVERIFIED")
        self.assertTrue(r["packet_consistency_observed"])
        self.assertFalse(r["physical_separation_independently_verified"])
        self.assertFalse(r["trusted_receipt_delivery_verified"])
        self.assert_hold(r)

    def test_falsified_root_history_and_custodian_proof_still_not_external(self):
        """Caller can self-create both root generations, pins and precommit."""
        self.old["high_water_sequence"] = 0
        self.old["high_water_sha256"] = "0" * 64
        self.next["high_water_sequence"] = 0
        self.next["high_water_sha256"] = "0" * 64
        self.next["previous_manifest_sha256"] = sha(encode(self.old))
        self.resign_transition()
        self.precommit = self.make_precommit()
        self.packets = self.make_packets()
        r = self.verify()
        self.assertTrue(r["packet_consistency_observed"])
        self.assertFalse(r["external_high_water_proven"])
        self.assertFalse(r["durable_off_host_intent_custody_proven"])
        self.assert_hold(r)


if __name__ == "__main__":
    unittest.main()
