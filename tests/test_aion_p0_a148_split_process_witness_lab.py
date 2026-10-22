"""A148 adversarial split-process synthetic witness tests (never real trust)."""
import base64
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aion_p0_a145_checkpoint_verifier_lab import Checkpoint, canonical_history_digest
from aion_p0_a145_authenticated_checkpoint_lab import SignedCheckpoint, checkpoint_payload
from aion_p0_a146_highwater_gate_lab import HighWater
from aion_p0_a146_signed_highwater_lab import (
    SignedHighWater, verify_signed_highwater,
)
from aion_p0_a147_sqlite_crash_journal_lab import (
    JournalUnavailable, SyntheticCrashJournalLAB,
)
from aion_p0_a148_split_process_witness_lab import (
    LAB_MARKER, SeparateProcessWitnessLAB, WitnessUnavailable,
)

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "aion_p0_a148_split_process_witness_lab.py"


def pub(private):
    return private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


class A148SplitProcessWitnessLAB(unittest.TestCase):
    def setUp(self):
        self.lab_flags = patch.dict(os.environ, {
            "AION_LAB_MODE": "1", "AION_WORKER_ENABLED": "0",
            "AION_EXTERNAL_EXECUTION_ENABLED": "0",
        })
        self.lab_flags.start()
        self.addCleanup(self.lab_flags.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.local_root = self.root / "local"
        self.remote_root = self.root / "synthetic_other_process_storage"
        self.local_root.mkdir()
        self.remote_root.mkdir()
        self.cp_signer = Ed25519PrivateKey.generate()
        self.witness_signer = Ed25519PrivateKey.generate()
        self.private_raw = self.witness_signer.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        self.pinned_checkpoint = {"cp": pub(self.cp_signer)}
        self.pinned_witness = {"a148-synthetic-key": pub(self.witness_signer)}
        self.journal = SyntheticCrashJournalLAB.bootstrap_synthetic_lab(
            lab_dir=self.local_root, ledger_id="ledger-A",
        )
        self.witness = SeparateProcessWitnessLAB.bootstrap_synthetic(
            witness_dir=self.remote_root, ledger_id="ledger-A",
            private_key_raw=self.private_raw,
        )

    def request(self, *, operation="read", sequence=None, digest=None,
                expected=None, fault=None, overrides=None, env_overrides=None,
                raw=None):
        body = {"operation": operation, "directory": str(self.remote_root),
                "ledger_id": "ledger-A"}
        if operation == "publish":
            body.update({"sequence": sequence, "history_digest": digest,
                         "expected_sequence": expected})
        if fault is not None:
            body["fault"] = fault
        if overrides:
            body.update(overrides)
        env = dict(os.environ)
        if env_overrides:
            env.update(env_overrides)
        completed = subprocess.run(
            [sys.executable, "-B", str(CLI)],
            input=json.dumps(body) if raw is None else raw,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=ROOT, env=env, timeout=25,
        )
        payload = json.loads(completed.stdout) if completed.stdout.strip() else None
        return completed.returncode, payload, completed.stderr

    def assert_remote_denied(self, result, reason=None):
        code, payload, stderr = result
        self.assertEqual(code, 2, stderr)
        self.assertEqual(payload["marker"], LAB_MARKER)
        self.assertIn("error", payload)
        if reason:
            self.assertIn(reason, payload["error"])

    def read_payload(self):
        code, payload, stderr = self.request()
        self.assertEqual(code, 0, stderr)
        self.assertEqual(payload["marker"], LAB_MARKER)
        return payload

    def decode(self, payload):
        return SignedHighWater(
            HighWater(payload["ledger_id"], payload["sequence"], payload["history_digest"]),
            payload["key_id"], payload["signature_b64"],
        )

    def events(self):
        return self.journal.read_events()

    def anchor(self, events=None):
        events = self.events() if events is None else events
        return HighWater("ledger-A", len(events), canonical_history_digest(events))

    def checkpoint(self, events=None):
        anchor = self.anchor(events)
        cp = Checkpoint(anchor.ledger_id, anchor.sequence, anchor.history_digest)
        signature = base64.b64encode(self.cp_signer.sign(checkpoint_payload(cp))).decode("ascii")
        return SignedCheckpoint(cp, "cp", signature)

    def publish(self, anchor=None, expected=0, fault=None, env_overrides=None):
        anchor = self.anchor() if anchor is None else anchor
        return self.request(
            operation="publish", sequence=anchor.sequence,
            digest=anchor.history_digest, expected=expected,
            fault=fault, env_overrides=env_overrides,
        )

    def publish_ok(self, anchor=None, expected=0):
        result = self.publish(anchor=anchor, expected=expected)
        self.assertEqual(result[0], 0, result)
        return result[1]

    def signed_floor(self, ledger_id):
        self.assertEqual(ledger_id, "ledger-A")
        return self.decode(self.read_payload())

    def assess(self, *, cp=None, reader=None):
        return self.journal.assess_restart(
            checkpoint_envelope=self.checkpoint() if cp is None else cp,
            checkpoint_pinned_keys=self.pinned_checkpoint,
            highwater_pinned_keys=self.pinned_witness,
            read_signed_highwater=self.signed_floor if reader is None else reader,
        )

    def check_signature(self, payload):
        return verify_signed_highwater(
            envelope=self.decode(payload),
            pinned_authorities=self.pinned_witness,
            forbidden_checkpoint_key=pub(self.cp_signer),
        )

    def test_01_genesis_is_signed_in_distinct_process(self):
        payload = self.read_payload()
        self.assertEqual(payload["sequence"], 0)
        self.assertEqual(self.check_signature(payload), self.anchor([]))

    def test_02_publish_signed_increment_visible_to_next_process(self):
        self.journal.reserve_local_uncertain("alpha")
        signed = self.publish_ok()
        self.assertEqual(self.check_signature(signed), self.anchor())
        self.assertEqual(self.read_payload()["sequence"], 1)

    def test_03_equal_cas_is_idempotent(self):
        self.journal.reserve_local_uncertain("alpha")
        self.publish_ok()
        self.publish_ok(expected=1)
        self.assertEqual(self.read_payload()["sequence"], 1)

    def test_04_same_sequence_other_digest_rejected(self):
        bad = HighWater("ledger-A", 0, "a" * 64)
        self.assert_remote_denied(self.publish(bad), "witness_same_sequence_conflict")

    def test_05_stale_cas_rejected(self):
        self.journal.reserve_local_uncertain("alpha")
        self.publish_ok()
        self.assert_remote_denied(self.publish(expected=0), "witness_cas_conflict")

    def test_06_sequence_gap_rejected(self):
        bad = HighWater("ledger-A", 2, "a" * 64)
        self.assert_remote_denied(self.publish(bad), "witness_nonmonotonic_or_gap")

    def test_07_sequence_decrement_rejected(self):
        self.journal.reserve_local_uncertain("alpha")
        self.publish_ok()
        self.assert_remote_denied(self.publish(self.anchor([]), expected=1),
                                  "witness_nonmonotonic_or_gap")

    def test_08_boolean_cas_expected_rejected(self):
        self.assert_remote_denied(self.publish(self.anchor([]), expected=True),
                                  "invalid_cas_expectation")

    def test_09_boolean_sequence_rejected(self):
        self.assert_remote_denied(self.request(
            operation="publish", sequence=True,
            digest=self.anchor([]).history_digest, expected=0,
        ), "invalid_highwater_sequence")

    def test_10_malformed_digest_rejected(self):
        self.assert_remote_denied(self.publish(
            HighWater("ledger-A", 1, "wrong"),
        ), "invalid_highwater_digest")

    def test_11_foreign_ledger_identity_refused(self):
        self.assert_remote_denied(self.request(
            overrides={"ledger_id": "ledger-B"},
        ), "witness_identity_mismatch")

    def test_12_explicit_second_bootstrap_denied(self):
        with self.assertRaisesRegex(WitnessUnavailable, "witness_rebootstrap_forbidden"):
            SeparateProcessWitnessLAB.bootstrap_synthetic(
                witness_dir=self.remote_root, ledger_id="ledger-A",
                private_key_raw=self.private_raw,
            )

    def test_13_deleted_witness_db_is_not_automatically_rebuilt(self):
        self.witness.db_path.unlink()
        self.assert_remote_denied(self.request(), "missing_witness_db_or_key")
        self.assertFalse(self.witness.db_path.exists())

    def test_14_deleted_private_key_is_not_regenerated(self):
        self.witness.key_path.unlink()
        self.assert_remote_denied(self.request(), "missing_witness_db_or_key")
        self.assertFalse(self.witness.key_path.exists())

    def test_15_signer_key_replacement_fails_external_pin(self):
        different = Ed25519PrivateKey.generate().private_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        self.witness.key_path.write_bytes(different)
        payload = self.read_payload()
        from aion_p0_a146_highwater_gate_lab import HighWaterRejected
        with self.assertRaisesRegex(HighWaterRejected, "highwater_signature_mismatch"):
            self.check_signature(payload)

    def test_16_unrelated_pinned_key_denied(self):
        from aion_p0_a146_highwater_gate_lab import HighWaterRejected
        payload = self.read_payload()
        with self.assertRaisesRegex(HighWaterRejected, "highwater_signature_mismatch"):
            verify_signed_highwater(
                envelope=self.decode(payload),
                pinned_authorities={"a148-synthetic-key": pub(Ed25519PrivateKey.generate())},
                forbidden_checkpoint_key=pub(self.cp_signer),
            )

    def test_17_modified_envelope_digest_denied(self):
        from aion_p0_a146_highwater_gate_lab import HighWaterRejected
        payload = self.read_payload()
        payload["history_digest"] = "b" * 64
        with self.assertRaisesRegex(HighWaterRejected, "highwater_signature_mismatch"):
            self.check_signature(payload)

    def test_18_local_commit_before_witness_ack_blocks_restart(self):
        self.journal.reserve_local_uncertain("alpha")
        decision = self.assess()
        self.assertEqual(decision.verdict, "LAB_HARD_BLOCKED")
        self.assertIn("unwitnessed_local_advance", decision.reason)
        self.assertFalse(decision.automatic_retry_allowed)

    def test_19_signed_witness_after_commit_does_not_authorize_execution(self):
        self.journal.reserve_local_uncertain("alpha")
        self.publish_ok()
        decision = self.assess()
        self.assertEqual(decision.verdict, "LAB_QUARANTINE_MANUAL_REVIEW")
        self.assertEqual(decision.reason, "reserved_effect_unknown")
        self.assertFalse(decision.external_execution_allowed)

    def test_20_local_old_snapshot_with_witness_preserved_detects_rollback(self):
        snapshot = self.root / "local_old_snapshot.sqlite3"
        shutil.copyfile(self.journal.path, snapshot)
        self.journal.reserve_local_uncertain("alpha")
        self.publish_ok()
        shutil.copyfile(snapshot, self.journal.path)
        decision = self.assess()
        self.assertEqual(decision.verdict, "LAB_HARD_BLOCKED")
        self.assertIn("signed_checkpoint_rollback", decision.reason)

    def test_21_negative_local_and_witness_db_both_rolled_back(self):
        """NEGATIVE: separate folders + signatures DO NOT guarantee monotonicity."""
        old_local = self.root / "old_local.sqlite3"
        old_remote = self.root / "old_remote.sqlite3"
        shutil.copyfile(self.journal.path, old_local)
        shutil.copyfile(self.witness.db_path, old_remote)
        self.journal.reserve_local_uncertain("alpha")
        self.publish_ok()
        shutil.copyfile(old_local, self.journal.path)
        shutil.copyfile(old_remote, self.witness.db_path)
        self.assertEqual(self.read_payload()["sequence"], 0)
        decision = self.assess()
        self.assertEqual(decision.verdict, "LAB_QUARANTINE_MANUAL_REVIEW")
        self.assertEqual(decision.reason, "read_only_genesis_not_authorized")

    def test_22_witness_unreachable_blocks_without_local_mutation(self):
        self.journal.reserve_local_uncertain("alpha")
        before = self.events()
        self.witness.db_path.unlink()
        decision = self.assess()
        self.assertEqual(decision.verdict, "LAB_HARD_BLOCKED")
        self.assertIn("witness_read_failed", decision.reason)
        self.assertEqual(self.events(), before)

    def test_23_two_process_publishers_one_wins_single_cas(self):
        a = HighWater("ledger-A", 1, "a" * 64)
        b = HighWater("ledger-A", 1, "b" * 64)
        results = []
        def do(candidate):
            results.append(self.publish(candidate))
        threads = [threading.Thread(target=do, args=(candidate,)) for candidate in (a, b)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(sorted(x[0] for x in results), [0, 2], results)
        self.assertEqual(self.read_payload()["sequence"], 1)

    def test_24_witness_crash_before_commit_recovers_old_floor(self):
        self.journal.reserve_local_uncertain("alpha")
        code, payload, err = self.publish(fault="crash_before_commit",
                                         env_overrides={"AION_A148_FAULT_LAB": "1"})
        self.assertEqual(code, 81, err)
        self.assertIsNone(payload)
        self.assertEqual(self.read_payload()["sequence"], 0)
        self.assertEqual(self.assess().verdict, "LAB_HARD_BLOCKED")

    def test_25_witness_crash_after_commit_ack_lost_persists(self):
        self.journal.reserve_local_uncertain("alpha")
        code, payload, err = self.publish(fault="crash_after_commit",
                                         env_overrides={"AION_A148_FAULT_LAB": "1"})
        self.assertEqual(code, 82, err)
        self.assertIsNone(payload)
        self.assertEqual(self.read_payload()["sequence"], 1)
        self.assertEqual(self.assess().verdict, "LAB_QUARANTINE_MANUAL_REVIEW")

    def test_26_local_child_exit_after_commit_remote_witness_still_behind(self):
        code = (
            "import os;"
            "from aion_p0_a147_sqlite_crash_journal_lab import SyntheticCrashJournalLAB;"
            f"SyntheticCrashJournalLAB(lab_dir={str(self.local_root)!r},ledger_id='ledger-A')"
            ".reserve_local_uncertain('child_alpha');"
            "os._exit(48)"
        )
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT,
                                env=dict(os.environ), capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 48, result.stderr)
        self.assertEqual(len(self.events()), 1)
        self.assertEqual(self.assess().verdict, "LAB_HARD_BLOCKED")

    def test_27_duplicate_intent_after_subprocess_restart_no_second_insert(self):
        self.journal.reserve_local_uncertain("alpha")
        self.assertFalse(SyntheticCrashJournalLAB(
            lab_dir=self.local_root, ledger_id="ledger-A",
        ).reserve_local_uncertain("alpha"))
        self.assertEqual(len(self.events()), 1)

    def test_28_second_local_intent_denied_even_after_witness_ack(self):
        self.journal.reserve_local_uncertain("alpha")
        self.publish_ok()
        with self.assertRaisesRegex(JournalUnavailable, "unresolved_first_operation"):
            self.journal.reserve_local_uncertain("beta")

    def test_29_witness_extra_trigger_denies_read(self):
        with closing(sqlite3.connect(self.witness.db_path)) as db:
            db.execute("CREATE TRIGGER extra AFTER UPDATE ON witness_head BEGIN SELECT 1; END")
            db.commit()
        self.assert_remote_denied(self.request(), "unexpected_witness_schema")

    def test_30_witness_identity_tamper_denies_read(self):
        with closing(sqlite3.connect(self.witness.db_path)) as db:
            db.execute("UPDATE witness_head SET ledger_id='ledger-FAKE'")
            db.commit()
        self.assert_remote_denied(self.request(), "witness_identity_mismatch")

    def test_31_unknown_request_field_denied(self):
        self.assert_remote_denied(self.request(overrides={"exec": "forbidden"}),
                                  "invalid_request_shape")

    def test_32_duplicate_json_request_field_denied(self):
        self.assert_remote_denied(self.request(
            raw='{"operation":"read","operation":"publish"}',
        ), "duplicate_request_field")

    def test_33_missing_request_fields_denied(self):
        self.assert_remote_denied(self.request(raw='{"operation":"read"}'),
                                  "missing_request_field")

    def test_34_unsupported_operation_denied(self):
        self.assert_remote_denied(self.request(operation="send-provider"),
                                  "unsupported_operation")

    def test_35_lab_mode_required_in_another_process(self):
        self.assert_remote_denied(self.request(
            env_overrides={"AION_LAB_MODE": "0"},
        ), "lab_mode_required")

    def test_36_worker_flag_must_remain_off(self):
        self.assert_remote_denied(self.request(
            env_overrides={"AION_WORKER_ENABLED": "1"},
        ), "worker_must_be_disabled")

    def test_37_external_execution_flag_must_remain_off(self):
        self.assert_remote_denied(self.request(
            env_overrides={"AION_EXTERNAL_EXECUTION_ENABLED": "1"},
        ), "external_execution_must_be_disabled")

    def test_38_fault_injection_not_available_without_explicit_lab_flag(self):
        self.journal.reserve_local_uncertain("alpha")
        self.assert_remote_denied(self.publish(fault="crash_after_commit"),
                                  "unauthorized_fault_injection")
        self.assertEqual(self.read_payload()["sequence"], 0)

    def test_39_negative_unauthorized_caller_can_advance_synthetic_floor(self):
        """NEGATIVE: no auth on synthetic publish. Not a trusted service."""
        malicious = HighWater("ledger-A", 1, "c" * 64)
        code, payload, err = self.publish(malicious)
        self.assertEqual(code, 0, err)
        self.assertEqual(payload["sequence"], 1)
        self.assertEqual(self.assess().verdict, "LAB_HARD_BLOCKED")

    def test_40_negative_manual_reset_preserves_signing_key_but_loses_floor(self):
        """NEGATIVE: key continuity cannot prove state continuity."""
        saved_key = self.witness.key_path.read_bytes()
        self.journal.reserve_local_uncertain("alpha")
        self.publish_ok()
        self.witness.db_path.unlink()
        self.witness.key_path.unlink()
        reset = SeparateProcessWitnessLAB.bootstrap_synthetic(
            witness_dir=self.remote_root, ledger_id="ledger-A",
            private_key_raw=saved_key,
        )
        self.assertIsInstance(reset, SeparateProcessWitnessLAB)
        payload = self.read_payload()
        self.assertEqual(payload["sequence"], 0)
        self.check_signature(payload)  # valid pinned signature but stale state!
        self.assertEqual(self.assess().verdict, "LAB_HARD_BLOCKED")


if __name__ == "__main__":
    unittest.main()
