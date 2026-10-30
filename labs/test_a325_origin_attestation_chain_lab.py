"""A325 LAB: two issuer origin attestations + two custodian delivery signatures.

Every key, "pin", timestamp, source and message is synthetic and created by
this process; even correct Ed25519 quorum is NOT independent off-host proof.
"""
import copy
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from labs import test_a324_recovery_evidence_triage_lab as a324_fixture
from labs.a317_detached_signed_intent_anchor_lab import encode, sha
from labs.a321_signed_high_water_fork_detection_lab import (
    signing_bytes as a321_signing_bytes,
)
from labs.a325_origin_attestation_chain_lab import (
    SCHEMA, ATTEST_FIELDS, ATTEST_SIGNED_FIELDS,
    origin_signing_bytes, receipt_signing_bytes,
    verify_claimed_receipt_origins,
)


def public_hex(key):
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()


class A325OriginAttestationLabTests(unittest.TestCase):
    def setUp(self):
        source = a324_fixture.A324RecoveryEvidenceTriageTests(
            methodName="test_two_coherent_receipts_still_held_without_authentic_custodians"
        )
        source.setUp()
        self.addCleanup(source.doCleanups)
        self.source = source
        self.witness_receipts = copy.deepcopy(source.receipts)
        self.origin_keys = {
            "claimed-origin-A": Ed25519PrivateKey.generate(),
            "claimed-origin-B": Ed25519PrivateKey.generate(),
        }
        self.root_pins = {name: public_hex(key)
                          for name, key in self.origin_keys.items()}
        self.nonce = "9" * 64
        self.now = 10070
        self.issue_attestations()

    def issue_attestations(self):
        latest = {
            proof["custodian_id"]: proof
            for proof in self.source.history["checkpoints"][-1]
        }
        self.delivered_signatures = {}
        self.attestations = []
        for index, receipt in enumerate(self.witness_receipts):
            who = receipt["custodian_id"]
            key = self.source.source.f.witnesses[who]
            proof = latest[who]
            self.delivered_signatures[who] = key.sign(
                receipt_signing_bytes(receipt)
            ).hex()
            authority_id = sorted(self.origin_keys)[index]
            att = {
                "schema": SCHEMA,
                "issuer_id": authority_id, "custodian_id": who,
                "witness_key_hex": public_hex(key),
                "root_generation": proof["root_generation"],
                "incident_epoch": proof["incident_epoch"],
                "checkpoint_sha256": sha(encode(proof)),
                "delivery_receipt_sha256": sha(encode(receipt)),
                "challenge_nonce": self.nonce,
                "issued_at": 10050 + index,
                "expires_at": 10090 + index,
                "decision": "HOLD_ONLY",
            }
            att["signature_hex"] = self.origin_keys[authority_id].sign(
                origin_signing_bytes(att)
            ).hex()
            self.attestations.append(att)

    def resign_attestation(self, index):
        obj = self.attestations[index]
        obj["signature_hex"] = self.origin_keys[obj["issuer_id"]].sign(
            origin_signing_bytes(obj)
        ).hex()

    def verify(self, **extra):
        args = {
            "genesis_package": self.source.genesis,
            "history_package": self.source.history,
            "local_db_path": self.source.local_path,
            "witness_receipts": self.witness_receipts,
            "declared_now_epoch": self.now,
            "origin_attestations": self.attestations,
            "pinned_origin_roots": self.root_pins,
            "signed_delivery_receipts": self.delivered_signatures,
            "expected_nonce": self.nonce,
        }
        args.update(extra)
        return verify_claimed_receipt_origins(**args)

    def assert_hard_no_go(self, data):
        self.assertEqual(data["schema"], SCHEMA)
        self.assertTrue(data["research_only"])
        self.assertTrue(data["synthetic_only"])
        self.assertTrue(data["investigation_only"])
        self.assertFalse(data["origin_pins_independently_provisioned"])
        self.assertFalse(data["issuer_identity_independently_authenticated"])
        self.assertFalse(data["witness_credential_real_world_custody_verified"])
        self.assertFalse(data["delivery_channel_independently_authenticated"])
        self.assertFalse(data["clock_and_nonce_externally_trusted"])
        self.assertFalse(data["off_host_immutable_head_verified"])
        self.assertFalse(data["provider_ack_authenticated"])
        self.assertFalse(data["semantic_exactly_once_proven"])
        self.assertFalse(data["can_restore"])
        self.assertFalse(data["can_resume"])
        self.assertFalse(data["can_replay"])
        self.assertFalse(data["can_resend"])
        self.assertFalse(data["can_auto_retry"])
        self.assertFalse(data["can_authorize_real_effect"])
        self.assertEqual(data["automatic_retries"], 0)
        self.assertTrue(data["zero_auto_resend"])
        self.assertTrue(data["hard_no_go"])
        self.assertEqual(data["p0_homologated"], 0)
        self.assertTrue(data["no_worker_deploy_provider_orders"])
        self.assertFalse(data["new_paid_services"])

    def veto(self, issue, status=None, **extra):
        report = self.verify(**extra)
        self.assertNotEqual(
            report["status"],
            "LAB_ORIGIN_SIGNATURES_MATCH_STILL_NOT_INDEPENDENT",
        )
        if status is not None:
            self.assertEqual(report["status"], status)
        self.assertIn(issue, report["reasons"])
        self.assert_hard_no_go(report)
        return report

    def test_two_issuer_two_delivery_signatures_math_valid_no_authority(self):
        r = self.verify()
        self.assertEqual(
            r["status"], "LAB_ORIGIN_SIGNATURES_MATCH_STILL_NOT_INDEPENDENT"
        )
        self.assertEqual(r["mathematically_verified_issuer_signatures"], 2)
        self.assertEqual(r["mathematically_verified_delivery_signatures"], 2)
        self.assertTrue(r["synthetic_downstream_reconciliation_coherent"])
        self.assert_hard_no_go(r)

    def test_signed_origin_shape_strict_and_separate_signature_domains(self):
        self.assertEqual(set(self.attestations[0]), ATTEST_FIELDS)
        self.assertEqual(len(ATTEST_SIGNED_FIELDS), len(ATTEST_FIELDS) - 1)
        self.assertNotEqual(
            origin_signing_bytes(self.attestations[0]),
            receipt_signing_bytes(self.witness_receipts[0]),
        )

    def test_missing_second_origin_attestation_denied(self):
        self.veto(
            "EXACT_TWO_ORIGIN_AND_DELIVERY_PROOFS_REQUIRED",
            "LAB_ORIGIN_MISSING_HOLD",
            origin_attestations=self.attestations[:1],
        )

    def test_missing_second_delivery_signature_denied(self):
        only = dict(self.delivered_signatures)
        only.pop(self.witness_receipts[1]["custodian_id"])
        self.veto(
            "EXACT_TWO_ORIGIN_AND_DELIVERY_PROOFS_REQUIRED",
            "LAB_ORIGIN_MISSING_HOLD",
            signed_delivery_receipts=only,
        )

    def test_duplicate_origin_root_keys_not_a_quorum(self):
        roots = dict(self.root_pins)
        roots["claimed-origin-B"] = roots["claimed-origin-A"]
        self.veto("ORIGIN_PINSET_INVALID_OR_KEYS_REPEATED", pinned_origin_roots=roots)

    def test_origin_root_identical_to_witness_key_denied(self):
        roots = dict(self.root_pins)
        roots["claimed-origin-A"] = self.attestations[0]["witness_key_hex"]
        self.veto("ORIGIN_ROOT_REUSED_AS_CUSTODIAN_KEY",
                  pinned_origin_roots=roots)

    def test_unknown_origin_issuer_denied_even_if_signature_valid(self):
        att = copy.deepcopy(self.attestations)
        att[1]["issuer_id"] = "unknown-root"
        self.veto("TWO_DISTINCT_PINNED_ISSUERS_REQUIRED",
                  origin_attestations=att)

    def test_same_origin_issuer_double_vote_denied(self):
        att = copy.deepcopy(self.attestations)
        att[1]["issuer_id"] = att[0]["issuer_id"]
        self.veto("TWO_DISTINCT_PINNED_ISSUERS_REQUIRED",
                  origin_attestations=att)

    def test_two_attestations_for_same_witness_denied(self):
        att = copy.deepcopy(self.attestations)
        att[1]["custodian_id"] = att[0]["custodian_id"]
        self.veto("TWO_DISTINCT_PINNED_CUSTODIANS_REQUIRED",
                  origin_attestations=att)

    def test_wrong_declared_origin_public_key_denied(self):
        roots = dict(self.root_pins)
        roots["claimed-origin-A"] = public_hex(Ed25519PrivateKey.generate())
        self.veto("ISSUER_SIGNATURE_INVALID", pinned_origin_roots=roots)

    def test_corrupted_origin_signature_denied(self):
        self.attestations[0]["signature_hex"] = "0" * 128
        self.veto("ISSUER_SIGNATURE_INVALID")

    def test_corrupted_delivery_signature_denied(self):
        key = self.witness_receipts[0]["custodian_id"]
        self.delivered_signatures[key] = "0" * 128
        self.veto("CUSTODIAN_DELIVERY_SIGNATURE_INVALID")

    def test_receipt_edit_after_delivery_signature_is_detected(self):
        self.witness_receipts[0]["head_sha256"] = "e" * 64
        self.veto("CUSTODIAN_DELIVERY_SIGNATURE_INVALID")

    def test_receipt_resigned_but_origin_does_not_match_is_denied(self):
        item = self.witness_receipts[0]
        item["claimed_channel_id"] = "attacker-channel"
        who = item["custodian_id"]
        self.delivered_signatures[who] = self.source.source.f.witnesses[
            who
        ].sign(receipt_signing_bytes(item)).hex()
        self.veto("ORIGIN_DELIVERY_BINDING_MISMATCH")

    def test_origin_key_binding_wrong_even_with_valid_issuer_signature(self):
        self.attestations[0]["witness_key_hex"] = "a" * 64
        self.resign_attestation(0)
        self.veto("ORIGIN_WITNESS_KEY_BINDING_MISMATCH")

    def test_origin_checkpoint_binding_wrong_even_with_resigned_signature(self):
        self.attestations[1]["checkpoint_sha256"] = "f" * 64
        self.resign_attestation(1)
        self.veto("ORIGIN_CHECKPOINT_BINDING_MISMATCH")

    def test_origin_incident_epoch_reopen_denied(self):
        self.attestations[0]["incident_epoch"] += 1
        self.resign_attestation(0)
        self.veto("ORIGIN_INCIDENT_EPOCH_MISMATCH")

    def test_origin_generation_downgrade_denied(self):
        self.attestations[1]["root_generation"] -= 1
        self.resign_attestation(1)
        self.veto("ORIGIN_GENERATION_MISMATCH")

    def test_replayed_nonce_denied_even_if_resigned(self):
        self.attestations[0]["challenge_nonce"] = "8" * 64
        self.resign_attestation(0)
        self.veto("ORIGIN_CHALLENGE_REPLAY_OR_MISMATCH")

    def test_expired_origin_attestation_denied(self):
        self.veto("ORIGIN_ATTESTATION_TIME_INVALID",
                  declared_now_epoch=10096)

    def test_future_origin_attestation_denied(self):
        self.veto("ORIGIN_ATTESTATION_TIME_INVALID",
                  declared_now_epoch=10040)

    def test_issuer_claimed_after_delivery_is_denied(self):
        self.attestations[0]["issued_at"] = 10060
        self.resign_attestation(0)
        self.veto("ORIGIN_ATTESTATION_TIME_INVALID")

    def test_claimed_issuer_before_signed_checkpoint_is_denied(self):
        self.attestations[0]["issued_at"] = 10000
        self.resign_attestation(0)
        self.veto("ORIGIN_ATTESTATION_TIME_INVALID")

    def test_malformed_noncanonical_origin_attestation_denied(self):
        self.attestations[0]["can_resend"] = True
        self.veto("ORIGIN_ATTESTATION_INVALID")

    def test_boolean_generation_rejected_not_coerced(self):
        self.attestations[0]["root_generation"] = True
        self.veto("ORIGIN_ATTESTATION_INVALID")

    def test_invalid_witness_receipt_data_rejected_before_encoding(self):
        receipts = copy.deepcopy(self.witness_receipts)
        receipts[0]["sequence"] = True
        self.veto("DELIVERY_RECEIPT_SHAPE_INVALID",
                  witness_receipts=receipts)

    def test_pretend_provider_ack_cannot_be_inserted(self):
        receipts = copy.deepcopy(self.witness_receipts)
        receipts[0]["provider_ack_verified"] = True
        self.veto("DELIVERY_RECEIPT_SHAPE_INVALID",
                  witness_receipts=receipts)

    def test_reopened_incident_vetoes_before_any_signature_assessment(self):
        self.veto("INCIDENT_REOPENED_FREEZE",
                  "LAB_ORIGIN_PROCEDURAL_HOLD", incident_reopened=True)

    def test_operations_are_never_authorized(self):
        for op in ("RESEND", "REPLAY", "DEPLOY", "RESTORE", "START_WORKER",
                   "INVESTIGATE_ONLY", "GO", ""):
            with self.subTest(operation=op):
                self.veto("ACTION_REQUEST_DENIED", operation=op)

    def test_invalid_clock_types_fail_closed(self):
        for stamp in (None, True, -1, "10070", 1.0, []):
            with self.subTest(stamp=repr(stamp)):
                self.veto("CONTROL_INPUT_INVALID", declared_now_epoch=stamp)

    def test_downstream_sqlite_rollback_still_denies(self):
        self.source.source.write_local_state(sequence=21)
        r = self.veto("A324_EVIDENCE_NOT_COHERENT",
                      "LAB_DOWNSTREAM_EVIDENCE_HOLD")
        self.assertEqual(r["mathematically_verified_issuer_signatures"], 2)
        self.assertEqual(r["mathematically_verified_delivery_signatures"], 2)

    def test_missing_local_sqlite_still_denies_after_crypto_quorum(self):
        missing = self.source.local_path.parent / "not-present.sqlite"
        self.assertFalse(missing.exists())
        self.veto("A324_EVIDENCE_NOT_COHERENT",
                  local_db_path=missing)
        self.assertFalse(missing.exists())

    def test_corrupted_a321_checkpoint_rejected_by_origin_binding(self):
        history = copy.deepcopy(self.source.history)
        history["checkpoints"][-1][0]["signature_hex"] = "0" * 128
        self.veto("ORIGIN_CHECKPOINT_BINDING_MISMATCH",
                  history_package=history)

    def test_complete_local_remint_of_origin_keys_does_not_prove_trust(self):
        """Crucial P0-3/4 counterexample: all pins are attacker controlled."""
        self.origin_keys = {
            "claimed-origin-A": Ed25519PrivateKey.generate(),
            "claimed-origin-B": Ed25519PrivateKey.generate(),
        }
        self.root_pins = {name: public_hex(key)
                          for name, key in self.origin_keys.items()}
        self.issue_attestations()
        r = self.verify()
        self.assertEqual(
            r["status"], "LAB_ORIGIN_SIGNATURES_MATCH_STILL_NOT_INDEPENDENT"
        )
        self.assertFalse(r["origin_pins_independently_provisioned"])
        self.assertFalse(r["issuer_identity_independently_authenticated"])
        self.assert_hard_no_go(r)

    def test_forged_whole_history_sqlite_and_origin_still_hold(self):
        """Full host rewrite remains mathematically self-consistent."""
        f = self.source.source.f
        f.old["high_water_sequence"] = 0
        f.old["high_water_sha256"] = "0" * 64
        f.candidate["high_water_sequence"] = 0
        f.candidate["high_water_sha256"] = "0" * 64
        f.candidate["previous_manifest_sha256"] = sha(encode(f.old))
        f.recreate_ceremony()
        f.base["sequence"] = 0
        f.base["head_sha256"] = "0" * 64
        f.checkpoints = f.mint_checkpoints()
        self.source.source.genesis = self.source.source.make_genesis_package()
        self.source.source.history = self.source.source.make_history_package()
        self.source.genesis = self.source.source.genesis
        self.source.history = self.source.source.history
        self.source.source.write_local_state()
        self.source.receipts = self.source.make_receipts()
        self.witness_receipts = copy.deepcopy(self.source.receipts)
        self.issue_attestations()
        r = self.verify()
        self.assertEqual(
            r["status"], "LAB_ORIGIN_SIGNATURES_MATCH_STILL_NOT_INDEPENDENT"
        )
        self.assertTrue(r["synthetic_downstream_reconciliation_coherent"])
        self.assertFalse(r["off_host_immutable_head_verified"])
        self.assert_hard_no_go(r)



    def test_identical_claims_can_be_replayed_locally_but_never_authorize(self):
        """No external nonce ledger: repeated mathematical checks are not anti-replay."""
        first = self.verify()
        second = self.verify()
        for report in (first, second):
            self.assertEqual(
                report["status"],
                "LAB_ORIGIN_SIGNATURES_MATCH_STILL_NOT_INDEPENDENT",
            )
            self.assert_hard_no_go(report)
            self.assertFalse(report["clock_and_nonce_externally_trusted"])
            self.assertFalse(report["off_host_immutable_head_verified"])

    def test_malformed_outer_envelopes_fail_closed(self):
        cases = (
            ("missing_origins", {"origin_attestations": None}),
            ("origin_string", {"origin_attestations": "two"}),
            ("extra_origin", {"origin_attestations": self.attestations * 2}),
            ("missing_receipts", {"witness_receipts": None}),
            ("receipt_string", {"witness_receipts": "two"}),
            ("pinset_list", {"pinned_origin_roots": []}),
            ("pinset_bad_type", {"pinned_origin_roots": {
                "claimed-origin-A": self.root_pins["claimed-origin-A"],
                "claimed-origin-B": b"not-a-public-key",
            }}),
            ("delivery_signatures_list", {"signed_delivery_receipts": []}),
            ("delivery_signatures_wrong_ids", {"signed_delivery_receipts": {
                "forged-A": "0" * 128, "forged-B": "0" * 128,
            }}),
            ("nonce_wrong_type", {"expected_nonce": True}),
            ("nonce_short", {"expected_nonce": "f" * 63}),
            ("clock_negative", {"declared_now_epoch": -1}),
            ("clock_float", {"declared_now_epoch": 10070.0}),
            ("incident_truthy_string", {"incident_reopened": "false"}),
            ("invalid_operation", {"operation": "RESTORE"}),
            ("history_non_dict", {"history_package": []}),
            ("history_empty_checkpoints", {"history_package": {
                "ceremony_request": {"custodian_pins": {}},
                "checkpoints": [],
            }}),
            ("genesis_missing", {"genesis_package": None}),
        )
        for label, override in cases:
            with self.subTest(case=label):
                report = self.verify(**override)
                self.assertNotEqual(
                    report["status"],
                    "LAB_ORIGIN_SIGNATURES_MATCH_STILL_NOT_INDEPENDENT",
                )
                self.assert_hard_no_go(report)

    def test_attestation_field_type_mutations_fail_closed(self):
        cases = (
            ("schema", "ATLASQUANT_FAKE_GO"),
            ("issuer_id", []),
            ("custodian_id", True),
            ("witness_key_hex", None),
            ("root_generation", 1.25),
            ("incident_epoch", -1),
            ("checkpoint_sha256", "f" * 63),
            ("delivery_receipt_sha256", b"0" * 64),
            ("challenge_nonce", "z" * 64),
            ("issued_at", "10050"),
            ("expires_at", True),
            ("decision", "GO"),
            ("signature_hex", "z" * 128),
        )
        for field, bad in cases:
            with self.subTest(field=field):
                attempts = copy.deepcopy(self.attestations)
                attempts[0][field] = bad
                report = self.verify(origin_attestations=attempts)
                self.assertNotEqual(
                    report["status"],
                    "LAB_ORIGIN_SIGNATURES_MATCH_STILL_NOT_INDEPENDENT",
                )
                self.assert_hard_no_go(report)

    def test_receipt_field_type_mutations_fail_closed(self):
        cases = (
            ("custodian_id", None),
            ("claimed_received_at", []),
            ("claimed_channel_id", True),
            ("claimed_receipt_digest", 123),
            ("checkpoint_sha256", "f" * 63),
            ("root_generation", True),
            ("incident_epoch", -1),
            ("sequence", "23"),
            ("head_sha256", []),
            ("intent_digest", b"0" * 64),
            ("decision", "RESEND"),
        )
        for field, bad in cases:
            with self.subTest(field=field):
                receipts = copy.deepcopy(self.witness_receipts)
                receipts[0][field] = bad
                report = self.verify(witness_receipts=receipts)
                self.assertNotEqual(
                    report["status"],
                    "LAB_ORIGIN_SIGNATURES_MATCH_STILL_NOT_INDEPENDENT",
                )
                self.assert_hard_no_go(report)

    def test_cross_witness_delivery_signature_swap_is_vetoed(self):
        keys = list(self.delivered_signatures)
        swapped = dict(self.delivered_signatures)
        swapped[keys[0]], swapped[keys[1]] = swapped[keys[1]], swapped[keys[0]]
        report = self.verify(signed_delivery_receipts=swapped)
        self.assertIn("CUSTODIAN_DELIVERY_SIGNATURE_INVALID", report["reasons"])
        self.assert_hard_no_go(report)

    def test_proof_order_is_irrelevant_to_quorum_but_not_to_authority(self):
        report = self.verify(
            witness_receipts=list(reversed(self.witness_receipts)),
            origin_attestations=list(reversed(self.attestations)),
        )
        self.assertEqual(
            report["status"], "LAB_ORIGIN_SIGNATURES_MATCH_STILL_NOT_INDEPENDENT"
        )
        self.assert_hard_no_go(report)

    def test_host_resigning_forged_delivery_channel_still_has_no_authority(self):
        """Counterexample: a locally reminted channel claim can stay coherent."""
        receipt = self.witness_receipts[0]
        receipt["claimed_channel_id"] += "-forged-by-host"
        receipt["claimed_receipt_digest"] = sha(encode({
            "checkpoint_sha256": receipt["checkpoint_sha256"],
            "custodian_id": receipt["custodian_id"],
            "claimed_channel_id": receipt["claimed_channel_id"],
            "claimed_received_at": receipt["claimed_received_at"],
        }))
        who = receipt["custodian_id"]
        self.delivered_signatures[who] = self.source.source.f.witnesses[
            who
        ].sign(receipt_signing_bytes(receipt)).hex()
        self.attestations[0]["delivery_receipt_sha256"] = sha(encode(receipt))
        self.resign_attestation(0)
        report = self.verify()
        self.assertEqual(
            report["status"], "LAB_ORIGIN_SIGNATURES_MATCH_STILL_NOT_INDEPENDENT"
        )
        self.assertEqual(report["mathematically_verified_delivery_signatures"], 2)
        self.assertEqual(report["mathematically_verified_issuer_signatures"], 2)
        self.assertFalse(report["delivery_channel_independently_authenticated"])
        self.assert_hard_no_go(report)


if __name__ == "__main__":
    unittest.main()
