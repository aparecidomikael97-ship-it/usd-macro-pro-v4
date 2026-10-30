"""A324: full evidence triage against actual A323 synthetic SQLite.

All keys, custody receipts, claimed channels and time are created in a
single Python process. A local match is never independent external custody.
"""
import copy
from contextlib import closing
import sqlite3
import unittest
from unittest.mock import patch

from labs.a317_detached_signed_intent_anchor_lab import encode, sha
from labs.a321_signed_high_water_fork_detection_lab import (
    signing_bytes as a321_signing_bytes,
)
from labs.a324_recovery_evidence_triage_lab import (
    SCHEMA, RECEIPT_FIELDS, MAX_CLAIMED_RECEIPT_AGE,
    investigate_recovery_evidence,
)
from labs.test_a323_readonly_recovery_reconciliation_lab import (
    A323ReadOnlyRecoveryTests,
)


class A324RecoveryEvidenceTriageTests(unittest.TestCase):
    def setUp(self):
        source = A323ReadOnlyRecoveryTests(
            methodName="test_matched_genesis_signatures_and_local_db_still_hold"
        )
        source.setUp()
        self.addCleanup(source.doCleanups)
        self.source = source
        self.genesis = source.genesis
        self.history = source.history
        self.local_path = source.path
        self.receipts = self.make_receipts()
        self.now = 10070

    def make_receipts(self):
        receipts = []
        for i, checkpoint in enumerate(self.history["checkpoints"][-1]):
            channel = "claimed-channel-" + str(i)
            when = 10055 + i
            who = checkpoint["custodian_id"]
            receipt = {
                "custodian_id": who,
                "claimed_received_at": when,
                "claimed_channel_id": channel,
                "checkpoint_sha256": sha(encode(checkpoint)),
                "root_generation": checkpoint["root_generation"],
                "incident_epoch": checkpoint["incident_epoch"],
                "sequence": checkpoint["sequence"],
                "head_sha256": checkpoint["head_sha256"],
                "intent_digest": checkpoint["intent_digest"],
                "decision": "HOLD_ONLY",
            }
            receipt["claimed_receipt_digest"] = sha(encode({
                "checkpoint_sha256": receipt["checkpoint_sha256"],
                "custodian_id": who,
                "claimed_channel_id": channel,
                "claimed_received_at": when,
            }))
            receipts.append(receipt)
        return receipts

    def call(self, **kwargs):
        data = {
            "genesis_package": self.genesis,
            "history_package": self.history,
            "local_db_path": self.local_path,
            "witness_receipts": self.receipts,
            "declared_now_epoch": self.now,
        }
        data.update(kwargs)
        return investigate_recovery_evidence(**data)

    def assert_never_authorize(self, report):
        self.assertEqual(report["schema"], SCHEMA)
        self.assertTrue(report["research_only"])
        self.assertTrue(report["synthetic_only"])
        self.assertTrue(report["investigation_only"])
        self.assertFalse(report["external_custodians_independently_authenticated"])
        self.assertFalse(report["delivery_channel_independently_authenticated"])
        self.assertFalse(report["trusted_clock_and_receipt_freshness_proven"])
        self.assertFalse(report["high_water_off_host_immutable_proven"])
        self.assertFalse(report["provider_outcome_verified"])
        self.assertFalse(report["real_semantic_idempotence_proven"])
        self.assertFalse(report["can_resolve_unknown_commit"])
        self.assertFalse(report["can_restore"])
        self.assertFalse(report["can_resume"])
        self.assertFalse(report["can_replay"])
        self.assertFalse(report["can_resend"])
        self.assertFalse(report["can_auto_retry"])
        self.assertFalse(report["can_authorize_real_effect"])
        self.assertEqual(report["automatic_retries"], 0)
        self.assertTrue(report["zero_auto_resend"])
        self.assertTrue(report["hard_no_go"])
        self.assertEqual(report["p0_homologated"], 0)
        self.assertTrue(report["no_worker_deploy_provider_orders"])
        self.assertFalse(report["new_paid_services"])

    def assert_hold(self, result, issue, status=None):
        self.assertIn(issue, result["reasons"])
        if status is not None:
            self.assertEqual(result["status"], status)
        self.assert_never_authorize(result)

    def test_two_coherent_receipts_still_held_without_authentic_custodians(self):
        report = self.call()
        self.assertEqual(report["status"], "LAB_COHERENT_EVIDENCE_STILL_HOLD")
        self.assertEqual(report["claimed_receipts_checked"], 2)
        self.assertTrue(report["synthetic_local_reconciliation_consistent"])
        self.assert_hold(report, "EXTERNAL_INDEPENDENCE_UNPROVEN")

    def test_strict_receipt_fields_and_fixed_freshness_window(self):
        self.assertEqual(set(self.receipts[0]), RECEIPT_FIELDS)
        self.assertEqual(MAX_CLAIMED_RECEIPT_AGE, 120)

    def test_no_witness_receipts_means_wait_do_not_recover(self):
        self.assert_hold(
            self.call(witness_receipts=[]),
            "TWO_CUSTODIAN_DELIVERIES_REQUIRED",
            "LAB_INVESTIGATE_EVIDENCE_HOLD",
        )

    def test_one_witness_receipt_cannot_authorize(self):
        self.assert_hold(
            self.call(witness_receipts=self.receipts[:1]),
            "TWO_CUSTODIAN_DELIVERIES_REQUIRED",
        )

    def test_missing_genesis_never_falls_back_to_local(self):
        self.assert_hold(
            self.call(genesis_package=None), "GENESIS_EVIDENCE_MISSING"
        )

    def test_missing_signed_history_never_falls_back_to_local(self):
        self.assert_hold(
            self.call(history_package=None), "SIGNED_HISTORY_MISSING"
        )

    def test_false_go_field_on_receipt_refused(self):
        receipts = copy.deepcopy(self.receipts)
        receipts[0]["can_resume"] = True
        self.assert_hold(
            self.call(witness_receipts=receipts), "RECEIPT_SHAPE_INVALID"
        )

    def test_changed_receipt_decision_refused(self):
        receipts = copy.deepcopy(self.receipts)
        receipts[1]["decision"] = "GO"
        self.assert_hold(
            self.call(witness_receipts=receipts), "RECEIPT_SHAPE_INVALID"
        )

    def test_same_claimed_custodian_twice_is_not_quorum(self):
        receipts = copy.deepcopy(self.receipts)
        receipts[1] = copy.deepcopy(receipts[0])
        self.assert_hold(
            self.call(witness_receipts=receipts), "DUPLICATE_CUSTODIAN_CLAIM",
            "LAB_INVESTIGATE_CONFLICT_HOLD",
        )

    def test_same_claimed_delivery_channel_is_conflict(self):
        receipts = copy.deepcopy(self.receipts)
        receipts[1]["claimed_channel_id"] = receipts[0]["claimed_channel_id"]
        self.assert_hold(
            self.call(witness_receipts=receipts),
            "SHARED_DECLARED_DELIVERY_CHANNEL",
            "LAB_INVESTIGATE_CONFLICT_HOLD",
        )

    def test_unrecognized_custodian_claim_is_conflict(self):
        receipts = copy.deepcopy(self.receipts)
        receipts[1]["custodian_id"] = "unknown"
        self.assert_hold(
            self.call(witness_receipts=receipts), "UNKNOWN_CUSTODIAN_CLAIM",
        )

    def test_rewritten_head_claim_conflicts_with_signed_checkpoint(self):
        receipts = copy.deepcopy(self.receipts)
        receipts[0]["head_sha256"] = "f" * 64
        self.assert_hold(
            self.call(witness_receipts=receipts),
            "CLAIMED_HEAD_SHA256_CONFLICT",
            "LAB_INVESTIGATE_CONFLICT_HOLD",
        )

    def test_rewritten_intent_claim_conflicts(self):
        receipts = copy.deepcopy(self.receipts)
        receipts[0]["intent_digest"] = "0" * 64
        self.assert_hold(
            self.call(witness_receipts=receipts),
            "CLAIMED_INTENT_DIGEST_CONFLICT",
        )

    def test_rewritten_sequence_claim_conflicts(self):
        receipts = copy.deepcopy(self.receipts)
        receipts[0]["sequence"] -= 1
        self.assert_hold(
            self.call(witness_receipts=receipts), "CLAIMED_SEQUENCE_CONFLICT"
        )

    def test_changed_signed_checkpoint_digest_conflicts(self):
        receipts = copy.deepcopy(self.receipts)
        receipts[0]["checkpoint_sha256"] = "0" * 64
        self.assert_hold(
            self.call(witness_receipts=receipts),
            "SIGNED_CHECKPOINT_DIGEST_MISMATCH",
        )

    def test_envelope_digest_detects_claimed_delivery_edit(self):
        receipts = copy.deepcopy(self.receipts)
        receipts[1]["claimed_received_at"] += 1
        self.assert_hold(
            self.call(witness_receipts=receipts),
            "RECEIPT_ENVELOPE_DIGEST_MISMATCH",
        )

    def test_invalid_receipt_clock_is_denied(self):
        receipts = copy.deepcopy(self.receipts)
        receipts[0]["claimed_received_at"] = True
        self.assert_hold(
            self.call(witness_receipts=receipts), "RECEIPT_SHAPE_INVALID"
        )

    def test_claimed_delayed_receipt_is_investigation_not_retry(self):
        # One minute signed validity is no proof of fresh delivery.
        self.assert_hold(
            self.call(declared_now_epoch=10200),
            "RECEIPT_DELAYED_OR_STALE",
            "LAB_INVESTIGATE_EVIDENCE_HOLD",
        )

    def test_claimed_receipt_after_signed_expiry_is_investigation(self):
        receipts = copy.deepcopy(self.receipts)
        receipts[0]["claimed_received_at"] = 10100
        receipts[0]["claimed_receipt_digest"] = sha(encode({
            "checkpoint_sha256": receipts[0]["checkpoint_sha256"],
            "custodian_id": receipts[0]["custodian_id"],
            "claimed_channel_id": receipts[0]["claimed_channel_id"],
            "claimed_received_at": receipts[0]["claimed_received_at"],
        }))
        self.assert_hold(
            self.call(witness_receipts=receipts, declared_now_epoch=10101),
            "RECEIPT_AFTER_SIGNED_WINDOW",
        )

    def test_future_dated_receipt_stays_on_hold(self):
        self.assert_hold(
            self.call(declared_now_epoch=10040),
            "RECEIPT_TIME_INCONSISTENT",
        )

    def test_missing_local_sqlite_stays_on_hold(self):
        absent = self.local_path.parent / "nonexistent.sqlite"
        self.assertFalse(absent.exists())
        self.assert_hold(
            self.call(local_db_path=absent),
            "A323_EVIDENCE_NOT_CONCLUSIVE",
        )
        self.assertFalse(absent.exists())

    def test_local_sqlite_rollback_is_conflict_not_resend(self):
        self.source.write_local_state(sequence=21)
        self.assert_hold(
            self.call(),
            "A323_RECOVERY_CONFLICT",
            "LAB_INVESTIGATE_CONFLICT_HOLD",
        )

    def test_local_sqlite_ahead_of_witnesses_is_conflict(self):
        self.source.write_local_state(sequence=23)
        self.assert_hold(
            self.call(),
            "LOCAL_AHEAD_OF_CLAIMED_WITNESSES",
            "LAB_INVESTIGATE_CONFLICT_HOLD",
        )

    def test_signed_checkpoint_fork_is_conflict(self):
        history = copy.deepcopy(self.history)
        evidence = history["checkpoints"][-1][1]
        evidence["head_sha256"] = "a" * 64
        evidence["signature_hex"] = self.source.f.witnesses[
            evidence["custodian_id"]
        ].sign(a321_signing_bytes(evidence)).hex()
        receipts = copy.deepcopy(self.receipts)
        receipts[1]["head_sha256"] = evidence["head_sha256"]
        receipts[1]["checkpoint_sha256"] = sha(encode(evidence))
        receipts[1]["claimed_receipt_digest"] = sha(encode({
            "checkpoint_sha256": receipts[1]["checkpoint_sha256"],
            "custodian_id": receipts[1]["custodian_id"],
            "claimed_channel_id": receipts[1]["claimed_channel_id"],
            "claimed_received_at": receipts[1]["claimed_received_at"],
        }))
        self.assert_hold(
            self.call(history_package=history, witness_receipts=receipts),
            "A323_RECOVERY_CONFLICT",
            "LAB_INVESTIGATE_CONFLICT_HOLD",
        )

    def test_reopened_incident_freezes_before_reading_receipts(self):
        with patch(
            "labs.a324_recovery_evidence_triage_lab.verify_recovery_hold"
        ) as spy:
            res = self.call(incident_reopened=True)
        spy.assert_not_called()
        self.assert_hold(res, "INCIDENT_REOPENED", "LAB_PROCEDURAL_HOLD")

    def test_operations_other_than_investigate_are_forbidden(self):
        for command in ("RESTORE", "RESEND", "RETRY", "DEPLOY",
                        "RESTART_WORKER", "AUTHORIZE_EFFECT", "OBSERVE_ONLY"):
            with self.subTest(command=command):
                self.assert_hold(
                    self.call(operation=command),
                    "ACTION_REQUEST_DENIED",
                    "LAB_PROCEDURAL_HOLD",
                )

    def test_invalid_clock_and_control_types_fail_closed(self):
        for value in (None, True, 1.0, -1, "10070", []):
            with self.subTest(value=repr(value)):
                self.assert_hold(
                    self.call(declared_now_epoch=value),
                    "CONTROL_SHAPE_INVALID",
                )

    def test_unknown_commit_cannot_be_marked_resolved_by_receipt_fields(self):
        receipts = copy.deepcopy(self.receipts)
        receipts[0]["provider_ack_verified"] = True
        self.assert_hold(
            self.call(witness_receipts=receipts),
            "RECEIPT_SHAPE_INVALID",
        )

    def test_repeated_triage_does_not_mutate_sqlite(self):
        with closing(sqlite3.connect(str(self.local_path))) as db:
            before = db.execute(
                "SELECT * FROM a323_recovery_state"
            ).fetchall()
        for _ in range(3):
            self.assert_never_authorize(self.call())
        with closing(sqlite3.connect(str(self.local_path))) as db:
            after = db.execute(
                "SELECT * FROM a323_recovery_state"
            ).fetchall()
        self.assertEqual(before, after)

    def test_all_custody_pins_and_evidence_can_be_reminted_locally(self):
        """P0-3/P0-4 gap: all proof may be forged by the same host."""
        self.source.f.old["high_water_sequence"] = 0
        self.source.f.old["high_water_sha256"] = "0" * 64
        self.source.f.candidate["high_water_sequence"] = 0
        self.source.f.candidate["high_water_sha256"] = "0" * 64
        self.source.f.candidate["previous_manifest_sha256"] = sha(
            encode(self.source.f.old)
        )
        self.source.f.recreate_ceremony()
        self.source.f.base["sequence"] = 0
        self.source.f.base["head_sha256"] = "0" * 64
        self.source.f.checkpoints = self.source.f.mint_checkpoints()
        self.genesis = self.source.make_genesis_package()
        self.history = self.source.make_history_package()
        self.source.write_local_state()
        self.receipts = self.make_receipts()
        coherent = self.call()
        self.assertEqual(
            coherent["status"], "LAB_COHERENT_EVIDENCE_STILL_HOLD"
        )
        self.assertTrue(coherent["synthetic_local_reconciliation_consistent"])
        self.assert_never_authorize(coherent)


if __name__ == "__main__":
    unittest.main()
