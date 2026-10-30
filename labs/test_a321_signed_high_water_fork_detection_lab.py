"""A321 LAB: real Ed25519 mathematical sequence/fork counterexamples.

All keys and the alleged independently pinned history are synthetic and
controlled by the test. NO real off-host custody, operation, Worker or resend.
"""
import copy
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from labs.a317_detached_signed_intent_anchor_lab import encode, sha
from labs.a319_offline_root_continuity_lab import (
    SCHEMA as A319_SCHEMA, authorization_bytes,
)
from labs.a320_offline_custody_ceremony_lab import (
    SCHEMA as A320_SCHEMA, signable_bytes as a320_signable,
)
from labs.a321_signed_high_water_fork_detection_lab import (
    SCHEMA, REPORT_FIELDS, signing_bytes, verify_signed_high_water_history,
)


def public_hex(key):
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()


class A321TwoCustodianForkTests(unittest.TestCase):
    def setUp(self):
        self.old_signers = {
            "root-old-A": Ed25519PrivateKey.generate(),
            "root-old-B": Ed25519PrivateKey.generate(),
        }
        self.new_signers = {
            "root-new-A": Ed25519PrivateKey.generate(),
            "root-new-B": Ed25519PrivateKey.generate(),
        }
        self.witnesses = {
            "witness-A": Ed25519PrivateKey.generate(),
            "witness-B": Ed25519PrivateKey.generate(),
        }
        self.old = {
            "schema": A319_SCHEMA, "generation": 5,
            "roots": {k: public_hex(v) for k, v in self.old_signers.items()},
            "revoked_root_ids": [], "high_water_sequence": 20,
            "high_water_sha256": "a" * 64, "incident_epoch": 3,
        }
        self.candidate = {
            **copy.deepcopy(self.old), "generation": 6,
            "roots": {k: public_hex(v) for k, v in self.new_signers.items()},
            "revoked_root_ids": sorted(self.old["roots"]),
            "previous_manifest_sha256": sha(encode(self.old)),
            "challenge_nonce": "b" * 64, "issued_at": 10000,
            "expires_at": 10100, "decision": "HOLD_ONLY",
        }
        self.recreate_ceremony()
        self.base = {
            "generation": 6, "incident_epoch": 3, "sequence": 20,
            "head_sha256": "a" * 64,
        }
        self.challenges = ["c" * 64, "d" * 64]
        self.checkpoints = self.mint_checkpoints()

    def recreate_ceremony(self):
        self.transition = {
            "previous_manifest": self.old,
            "candidate_manifest": self.candidate,
            "pinned_previous_digest": sha(encode(self.old)),
            "old_root_signatures": {
                k: v.sign(authorization_bytes(
                    self.candidate, new_root=False,
                )).hex() for k, v in self.old_signers.items()
            },
            "new_root_signatures": {
                k: v.sign(authorization_bytes(
                    self.candidate, new_root=True,
                )).hex() for k, v in self.new_signers.items()
            },
            "expected_nonce": "b" * 64,
            "expected_incident_epoch": self.candidate["incident_epoch"],
            "observed_clock_epoch": 10040,
        }
        self.pre = {
            "schema": A320_SCHEMA,
            "ceremony_id": "a321-lab-ceremony",
            "candidate_manifest_sha256": sha(encode(self.candidate)),
            "previous_manifest_sha256": sha(encode(self.old)),
            "root_generation": self.candidate["generation"],
            "incident_epoch": self.candidate["incident_epoch"],
            "high_water_sequence": self.candidate["high_water_sequence"],
            "high_water_sha256": self.candidate["high_water_sha256"],
            "challenge_nonce": self.candidate["challenge_nonce"],
            "recorded_at": 9990,
        }
        self.pins = {k: public_hex(v) for k, v in self.witnesses.items()}
        self.packets = []
        for i, (who, key) in enumerate(sorted(self.witnesses.items())):
            packet = {
                **self.pre, "custodian_id": who,
                "custody_domain": "synthetic-domain-" + str(i),
                "channel_id": "synthetic-channel-" + str(i),
                "device_id": "synthetic-device-" + str(i),
                "evidence_digest": sha(("synthetic-evidence-" + str(i)).encode()),
                "witnessed_at": 10020 + i,
                "decision": "HOLD_ONLY",
            }
            packet["signature_hex"] = key.sign(
                a320_signable(packet)
            ).hex()
            self.packets.append(packet)
        self.ceremony = {
            "transition_request": self.transition,
            "offline_precommit": self.pre,
            "custodian_packets": self.packets,
            "custodian_pins": self.pins,
        }

    def mint_checkpoints(self):
        checkpoints = []
        previous_seq = self.candidate["high_water_sequence"]
        prev_hash = self.candidate["high_water_sha256"]
        for index in range(2):
            head = str(index + 1) * 64
            bundle = []
            for who, key in sorted(self.witnesses.items()):
                proof = {
                    "schema": SCHEMA, "custodian_id": who,
                    "root_generation": self.candidate["generation"],
                    "incident_epoch": self.candidate["incident_epoch"],
                    "sequence": previous_seq + 1,
                    "previous_sequence": previous_seq,
                    "previous_head_sha256": prev_hash,
                    "head_sha256": head,
                    "intent_digest": ("e" if index == 0 else "f") * 64,
                    "challenge_nonce": self.challenges[index],
                    "issued_at": 10040 + index * 5,
                    "expires_at": 10090 + index * 5,
                    "decision": "HOLD_ONLY",
                }
                proof["signature_hex"] = key.sign(
                    signing_bytes(proof)
                ).hex()
                bundle.append(proof)
            checkpoints.append(bundle)
            previous_seq += 1
            prev_hash = head
        return checkpoints

    def resign(self, index, which=0):
        proof = self.checkpoints[index][which]
        proof["signature_hex"] = self.witnesses[
            proof["custodian_id"]
        ].sign(signing_bytes(proof)).hex()

    def verify(self, **kwargs):
        options = {
            "ceremony_request": self.ceremony,
            "starting_reference": self.base,
            "checkpoints": self.checkpoints,
            "expected_challenges": self.challenges,
            "observed_clock_epoch": 10060,
        }
        options.update(kwargs)
        return verify_signed_high_water_history(**options)

    def assert_never_go(self, value):
        self.assertEqual(value["schema"], SCHEMA)
        self.assertTrue(value["research_only"])
        self.assertTrue(value["synthetic_only"])
        self.assertFalse(value["actual_custodians_independently_identified"])
        self.assertFalse(value["external_pin_independently_authenticated"])
        self.assertFalse(value["independent_delivery_authenticated"])
        self.assertFalse(value["off_host_high_water_authentic"])
        self.assertFalse(value["immutable_custody_proven"])
        self.assertFalse(value["trusted_nonce_origin_proven"])
        self.assertFalse(value["trusted_clock_proven"])
        self.assertFalse(value["provider_ack_verified"])
        self.assertFalse(value["semantic_exactly_once_proven"])
        self.assertFalse(value["can_authorize_real_effect"])
        self.assertFalse(value["can_resume"])
        self.assertFalse(value["can_resend"])
        self.assertFalse(value["can_auto_retry"])
        self.assertEqual(value["automatic_retries"], 0)
        self.assertTrue(value["zero_auto_resend"])
        self.assertTrue(value["hard_no_go"])
        self.assertEqual(value["p0_homologated"], 0)
        self.assertTrue(value["no_worker_deploy_provider_orders"])
        self.assertFalse(value["new_paid_services"])

    def assert_veto(self, value, issue):
        self.assertEqual(value["status"], "LAB_HIGH_WATER_VETO")
        self.assertIn(issue, value["issues"])
        self.assert_never_go(value)

    def test_two_round_signed_history_valid_math_still_no_external_proof(self):
        r = self.verify()
        self.assertEqual(
            r["status"], "LAB_CONSISTENT_SIGNED_HISTORY_NO_EXTERNAL_CUSTODY"
        )
        self.assertTrue(r["mathematical_chain_consistency_observed"])
        self.assertEqual(r["mathematically_consistent_checkpoints"], 2)
        self.assertEqual(r["issues"], [])
        self.assert_never_go(r)

    def test_one_round_is_supported_without_requiring_operation(self):
        r = self.verify(checkpoints=self.checkpoints[:1],
                        expected_challenges=self.challenges[:1])
        self.assertEqual(r["mathematically_consistent_checkpoints"], 1)
        self.assert_never_go(r)

    def test_exact_signed_fields_required(self):
        self.assertEqual(set(self.checkpoints[0][0]), REPORT_FIELDS)

    def test_untrusted_a320_success_string_cannot_replace_ceremony(self):
        self.assert_veto(
            self.verify(ceremony_request={"status": "success"}),
            "A320_ENVELOPE_INVALID",
        )

    def test_a320_corrupt_packet_signature_rejected(self):
        forged = copy.deepcopy(self.ceremony)
        forged["custodian_packets"][0]["signature_hex"] = "0" * 128
        self.assert_veto(self.verify(ceremony_request=forged),
                         "A320_CEREMONY_VETO")

    def test_a319_corrupt_rotation_cannot_be_ignored(self):
        forged = copy.deepcopy(self.ceremony)
        forged["transition_request"]["pinned_previous_digest"] = "0" * 64
        self.assert_veto(self.verify(ceremony_request=forged),
                         "A320_CEREMONY_VETO")

    def test_wrong_starting_head_rejected(self):
        base = dict(self.base, head_sha256="f" * 64)
        self.assert_veto(self.verify(starting_reference=base),
                         "BASELINE_NOT_LINKED_TO_CEREMONY")

    def test_starting_seq_rollback_rejected(self):
        base = dict(self.base, sequence=19)
        self.assert_veto(self.verify(starting_reference=base),
                         "BASELINE_NOT_LINKED_TO_CEREMONY")

    def test_missing_starting_reference_rejected(self):
        self.assert_veto(self.verify(starting_reference=None),
                         "BASELINE_REFERENCE_INVALID")

    def test_missing_second_signature_in_round_rejected(self):
        bundle = [self.checkpoints[0][:1]]
        self.assert_veto(
            self.verify(checkpoints=bundle, expected_challenges=self.challenges[:1]),
            "EXACT_TWO_SIGNED_CHECKPOINTS_REQUIRED",
        )

    def test_repeat_custodian_id_in_same_round_rejected(self):
        pair = [
            copy.deepcopy(self.checkpoints[0][0]),
            copy.deepcopy(self.checkpoints[0][0]),
        ]
        self.assert_veto(
            self.verify(checkpoints=[pair], expected_challenges=self.challenges[:1]),
            "CHECKPOINT_CUSTODIAN_REUSED",
        )

    def test_unpinned_custodian_rejected(self):
        self.checkpoints[0][1]["custodian_id"] = "unknown"
        self.assert_veto(self.verify(), "CHECKPOINT_CUSTODIAN_NOT_PINNED")

    def test_tampering_signed_head_breaks_signature(self):
        self.checkpoints[0][1]["head_sha256"] = "d" * 64
        self.assert_veto(self.verify(), "CHECKPOINT_SIGNATURE_INVALID")

    def test_two_valid_signatures_disagree_on_same_head(self):
        self.checkpoints[0][1]["head_sha256"] = "d" * 64
        self.resign(0, 1)
        self.assert_veto(self.verify(), "SIGNED_CHECKPOINT_FORK_OR_DISAGREEMENT")

    def test_two_valid_signatures_disagree_on_intent(self):
        self.checkpoints[0][1]["intent_digest"] = "a" * 64
        self.resign(0, 1)
        self.assert_veto(self.verify(), "SIGNED_CHECKPOINT_FORK_OR_DISAGREEMENT")

    def test_signed_sequence_skip_is_rejected(self):
        for j in (0, 1):
            self.checkpoints[0][j]["sequence"] = 22
            self.resign(0, j)
        self.assert_veto(self.verify(), "CHECKPOINT_SEQUENCE_ROLLBACK_OR_GAP")

    def test_signed_sequence_replay_is_rejected(self):
        for j in (0, 1):
            self.checkpoints[0][j]["sequence"] = 20
            self.resign(0, j)
        self.assert_veto(self.verify(), "CHECKPOINT_SEQUENCE_ROLLBACK_OR_GAP")

    def test_previous_sequence_gap_rejected(self):
        for j in (0, 1):
            self.checkpoints[1][j]["previous_sequence"] = 19
            self.resign(1, j)
        self.assert_veto(self.verify(), "PREVIOUS_SEQUENCE_ROLLBACK_OR_GAP")

    def test_previous_hash_rollback_rejected(self):
        for j in (0, 1):
            self.checkpoints[1][j]["previous_head_sha256"] = "a" * 64
            self.resign(1, j)
        self.assert_veto(self.verify(), "PREVIOUS_HEAD_MISMATCH")

    def test_same_head_no_forward_progress_rejected(self):
        for j in (0, 1):
            self.checkpoints[0][j]["head_sha256"] = "a" * 64
            self.resign(0, j)
        self.assert_veto(self.verify(), "NO_FORWARD_HEAD_CHANGE")

    def test_wrong_incident_epoch_rejected(self):
        for j in (0, 1):
            self.checkpoints[0][j]["incident_epoch"] = 4
            self.resign(0, j)
        self.assert_veto(self.verify(), "INCIDENT_EPOCH_ROLLBACK_OR_REOPEN")

    def test_old_root_generation_rejected(self):
        for j in (0, 1):
            self.checkpoints[0][j]["root_generation"] = 5
            self.resign(0, j)
        self.assert_veto(self.verify(), "ROOT_GENERATION_REPLAY_OR_MISMATCH")

    def test_nonce_mismatch_rejected(self):
        for j in (0, 1):
            self.checkpoints[0][j]["challenge_nonce"] = "f" * 64
            self.resign(0, j)
        self.assert_veto(self.verify(), "CHALLENGE_NOT_AUTHORIZED_BY_CALLER")

    def test_duplicate_expected_challenge_rejected(self):
        self.assert_veto(
            self.verify(expected_challenges=["c" * 64, "c" * 64]),
            "CHALLENGE_INVALID_OR_REPLAYED",
        )

    def test_expired_signed_round_rejected(self):
        self.assert_veto(self.verify(observed_clock_epoch=10100),
                         "CHECKPOINT_TIME_INVALID")

    def test_future_dated_signed_round_rejected(self):
        self.assert_veto(self.verify(observed_clock_epoch=10039),
                         "CHECKPOINT_TIME_INVALID")

    def test_extra_go_field_on_signed_report_rejected(self):
        self.checkpoints[0][0]["can_resend"] = True
        self.assert_veto(self.verify(), "CHECKPOINT_FIELDS_INVALID")

    def test_signed_competing_report_detects_equivocation(self):
        rogue = copy.deepcopy(self.checkpoints[0][0])
        rogue["head_sha256"] = "f" * 64
        rogue["signature_hex"] = self.witnesses[
            rogue["custodian_id"]
        ].sign(signing_bytes(rogue)).hex()
        self.assert_veto(
            self.verify(competing_reports=[rogue]),
            "SIGNED_HIGH_WATER_EQUIVOCATION",
        )

    def test_extra_identical_signed_report_is_refused_as_replay(self):
        rogue = copy.deepcopy(self.checkpoints[0][0])
        self.assert_veto(
            self.verify(competing_reports=[rogue]),
            "UNSOLICITED_SIGNED_CHECKPOINT_REPLAY",
        )

    def test_extra_competing_report_by_unpinned_key_is_rejected(self):
        rogue = copy.deepcopy(self.checkpoints[0][0])
        rogue["custodian_id"] = "rogue-witness"
        self.assert_veto(
            self.verify(competing_reports=[rogue]),
            "COMPETING_REPORT_NOT_AUTHENTICATED_BY_DECLARED_PIN",
        )

    def test_revoked_current_custodian_is_denied(self):
        self.assert_veto(
            self.verify(revoked_custodian_ids=["witness-A"]),
            "CUSTODIAN_REVOKED_OR_DUPLICATE",
        )

    def test_malformed_revocation_set_is_denied(self):
        self.assert_veto(
            self.verify(revoked_custodian_ids={"witness-A": True}),
            "CLOCK_COMPETING_OR_REVOCATION_INVALID",
        )

    def test_invalid_clock_type_fails_closed(self):
        self.assert_veto(self.verify(observed_clock_epoch=True),
                         "CLOCK_COMPETING_OR_REVOCATION_INVALID")

    def test_too_many_checkpoints_are_denied(self):
        self.assert_veto(
            self.verify(checkpoints=self.checkpoints * 3,
                        expected_challenges=self.challenges * 3),
            "CHECKPOINT_COUNT_OR_CHALLENGES_INVALID",
        )

    def test_host_can_remint_custodian_keys_and_full_history(self):
        """All keys, signed receipts and supposed reference are self-issued."""
        self.witnesses = {
            "fictional-X": Ed25519PrivateKey.generate(),
            "fictional-Y": Ed25519PrivateKey.generate(),
        }
        self.recreate_ceremony()
        self.checkpoints = self.mint_checkpoints()
        r = self.verify()
        self.assertEqual(
            r["status"], "LAB_CONSISTENT_SIGNED_HISTORY_NO_EXTERNAL_CUSTODY"
        )
        self.assertTrue(r["mathematical_chain_consistency_observed"])
        self.assertFalse(r["actual_custodians_independently_identified"])
        self.assertFalse(r["off_host_high_water_authentic"])
        self.assert_never_go(r)

    def test_host_can_rewind_whole_root_ceremony_and_history(self):
        """Host with total control can fabricate a new consistent baseline."""
        self.old["high_water_sequence"] = 0
        self.old["high_water_sha256"] = "0" * 64
        self.candidate["high_water_sequence"] = 0
        self.candidate["high_water_sha256"] = "0" * 64
        self.candidate["previous_manifest_sha256"] = sha(encode(self.old))
        self.recreate_ceremony()
        self.base["sequence"] = 0
        self.base["head_sha256"] = "0" * 64
        self.checkpoints = self.mint_checkpoints()
        r = self.verify()
        self.assertTrue(r["mathematical_chain_consistency_observed"])
        self.assertFalse(r["external_pin_independently_authenticated"])
        self.assertFalse(r["immutable_custody_proven"])
        self.assert_never_go(r)


if __name__ == "__main__":
    unittest.main()
