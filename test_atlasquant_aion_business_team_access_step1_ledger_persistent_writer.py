import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from atlasquant_aion_business_team_access_sandbox_lifecycle_evidence_ledger import (
    GENESIS_DIGEST,
    SCHEMA as LEDGER_SCHEMA,
)
from atlasquant_aion_business_team_access_step1_ledger_append_contract import (
    REQUIRED_ACKNOWLEDGEMENTS,
    build_ledger_append_decision_request,
)
from atlasquant_aion_business_team_access_step1_ledger_persistent_writer import (
    LOCK_NAME,
    MAX_PREFLIGHT_STATE,
    apply_step1_ledger_persistence,
    build_ledger_writer_preflight,
    canonical_json,
    claim_local_writer_lock,
    evaluate_future_persistence_authorization,
    genesis_logical_payload,
    ledger_writer_policy,
    recalculable_digest,
    recheck_writer_preflight,
    release_local_writer_lock,
)
from validate_team_access_step1_ledger_writer_preflight import BANNER, main


def _review():
    return {
        "receipt_review_digest": "b" * 64,
        "canonical_lifecycle_receipt": {
            "state": "SANDBOX_LIFECYCLE_STEP_EVIDENCE_RECEIPT_READY",
            "receipt_digest": "c" * 64,
            "step_order": 1,
            "step_id": "CREATE_INDIVIDUAL_SANDBOX_ACCOUNT",
            "previous_entry_digest": GENESIS_DIGEST,
            "mutation_observed": True,
            "sandbox_only": True,
            "production_targeted": False,
            "secret_material_included": False,
        },
        "ledger_preview": {
            "state": "READY_FOR_NEXT_SANDBOX_LIFECYCLE_STEP",
            "ledger_digest": "d" * 64,
            "completed_count": 1,
            "next_expected_step_order": 2,
            "next_expected_step_id": "ENROLL_STRONG_AUTH",
            "automatic_next_step_authorized": False,
            "executor_enabled": False,
            "production_authorized": False,
            "executes_action": False,
        },
        "ledger_append_authorized": False,
        "ledger_append_performed": False,
        "automatic_ledger_append": False,
        "step2_execution_authorized": False,
    }


def _genesis_document():
    document = {
        "schema": LEDGER_SCHEMA,
        "state": "READY_FOR_FIRST_SANDBOX_LIFECYCLE_STEP",
        "plan_digest": "1" * 64,
        "authorization_record_digest": "2" * 64,
        "authorization_package_digest": "3" * 64,
        "materialization_digest": "4" * 64,
        "entries": [],
        "completed_count": 0,
        "chain_head_digest": GENESIS_DIGEST,
        "next_expected_step_order": 1,
        "next_expected_step_id": "CREATE_INDIVIDUAL_SANDBOX_ACCOUNT",
        "executor_enabled": False,
        "production_authorized": False,
        "executes_action": False,
    }
    document["ledger_digest"] = recalculable_digest(
        genesis_logical_payload(document)
    )
    return document


def _packet(ledger_digest):
    return {
        "observation_observed_by": "admin.demo",
        "ledger": {
            "state": "READY_FOR_FIRST_SANDBOX_LIFECYCLE_STEP",
            "ledger_digest": ledger_digest,
            "completed_count": 0,
            "entries": [],
            "chain_head_digest": GENESIS_DIGEST,
            "next_expected_step_order": 1,
            "next_expected_step_id": "CREATE_INDIVIDUAL_SANDBOX_ACCOUNT",
        },
    }


def _record(packet, review):
    request = build_ledger_append_decision_request(packet, review)
    return {
        "decision": request["required_decision_token"],
        "receipt_review_digest": request["receipt_review_digest"],
        "canonical_receipt_digest": request["canonical_receipt_digest"],
        "source_ledger_digest": request["source_ledger_digest"],
        "target_ledger_digest": request["target_ledger_digest"],
        "decided_by": "admin.demo",
        "decided_at": "2026-09-30T23:00:00+00:00",
        "sandbox_only": True,
        "production_targeted": False,
        "automatic_ledger_append_requested": False,
        "step2_execution_requested": False,
        "secret_material_included": False,
        "acknowledgements": {name: True for name in REQUIRED_ACKNOWLEDGEMENTS},
    }


class Step1LedgerPersistentWriterTests(unittest.TestCase):
    def setUp(self):
        self.p1 = patch(
            "atlasquant_aion_business_team_access_step1_ledger_append_contract."
            "verify_step1_preflight_package",
            return_value={"binding_match": True},
        )
        self.p2 = patch(
            "atlasquant_aion_business_team_access_step1_ledger_append_contract."
            "verify_provider_receipt_review",
            return_value={"binding_match": True},
        )
        self.p1.start()
        self.p2.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "sandbox"
        self.root.mkdir()
        self.ledger = self.root / "lifecycle-ledger.json"
        self.document = _genesis_document()
        self.ledger.write_text(
            json.dumps(self.document, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.before = self.ledger.read_bytes()
        self.packet = _packet(self.document["ledger_digest"])
        self.review = _review()
        self.record = _record(self.packet, self.review)

    def tearDown(self):
        self.p2.stop()
        self.p1.stop()
        self.tmp.cleanup()

    def _preflight(self, **overrides):
        payload = {
            "allowed_root": self.root,
            "ledger_path": self.ledger,
            "step1_preflight_packet": self.packet,
            "receipt_review": self.review,
            "decision_record": self.record,
            "mode": "PLAN_ONLY",
        }
        payload.update(overrides)
        return build_ledger_writer_preflight(**payload)

    def _assert_unchanged(self):
        self.assertEqual(self.ledger.read_bytes(), self.before)

    def test_plan_only_does_not_write_the_ledger(self):
        plan = self._preflight()
        self.assertEqual(plan["state"], MAX_PREFLIGHT_STATE)
        self.assertEqual(plan["mode"], "PLAN_ONLY")
        self.assertFalse(plan["persistence_authorized"])
        self.assertFalse(plan["ledger_write_performed"])
        self.assertFalse(plan["ready_means_write_permission"])
        self.assertEqual(plan["banner"], "PERSISTENCE NOT AUTHORIZED")
        self.assertEqual(plan["source_ledger_path"], "lifecycle-ledger.json")
        refused = apply_step1_ledger_persistence(
            allowed_root=self.root,
            ledger_path=self.ledger,
            plan=plan,
        )
        self.assertEqual(refused["state"], "STEP1_LEDGER_PERSISTENCE_APPLY_REFUSED")
        self.assertFalse(refused["ledger_write_performed"])
        self._assert_unchanged()
        self.assertFalse((self.root / LOCK_NAME).exists())

    def test_wrong_source_digest_hard_fails(self):
        self.packet = _packet("a" * 64)
        self.record = _record(self.packet, self.review)
        plan = self._preflight()
        self.assertIn("source_ledger_digest", plan["blockers"])
        self.assertNotEqual(plan["state"], MAX_PREFLIGHT_STATE)
        self.assertFalse(plan["persistence_authorized"])
        self._assert_unchanged()

    def test_wrong_decision_digest_hard_fails(self):
        plan = self._preflight(decision_review={
            "ledger_append_decision_digest": "e" * 64,
        })
        self.assertIn("decision_digest", plan["blockers"])
        self.assertFalse(plan["ledger_write_performed"])
        self._assert_unchanged()

    def test_wrong_target_digest_hard_fails(self):
        self.record = dict(self.record)
        self.record["target_ledger_digest"] = "e" * 64
        plan = self._preflight()
        self.assertIn("target_ledger_digest", plan["blockers"])
        self.assertIn("decision_not_verified", plan["blockers"])
        self.assertFalse(plan["persistence_authorized"])
        self._assert_unchanged()

    def test_duplicate_receipt_hard_fails(self):
        self.document["entries"] = [{
            "step_order": 1,
            "previous_entry_digest": GENESIS_DIGEST,
            "receipt_digest": "c" * 64,
        }]
        self.ledger.write_text(json.dumps(self.document), encoding="utf-8")
        self.before = self.ledger.read_bytes()
        plan = self._preflight()
        self.assertIn("duplicate_receipt", plan["blockers"])
        self.assertFalse(plan["ledger_write_performed"])
        self._assert_unchanged()

    def test_non_genesis_ledger_hard_fails(self):
        self.document["state"] = "READY_FOR_NEXT_SANDBOX_LIFECYCLE_STEP"
        self.document["completed_count"] = 1
        self.ledger.write_text(json.dumps(self.document), encoding="utf-8")
        self.before = self.ledger.read_bytes()
        plan = self._preflight()
        self.assertIn("source_ledger_not_genesis", plan["blockers"])
        self.assertFalse(plan["persistence_authorized"])
        self._assert_unchanged()

    def test_held_lock_and_second_claim_hard_fail(self):
        first = claim_local_writer_lock(self.root)
        self.assertTrue(first["acquired"])
        self.assertFalse(first["wrote_ledger"])
        plan = self._preflight()
        self.assertIn("writer_lock_held", plan["blockers"])
        self.assertEqual(plan["lock_status"], "HELD")
        second = claim_local_writer_lock(self.root)
        self.assertFalse(second["acquired"])
        self.assertEqual(second["reason"], "writer_lock_held")
        self._assert_unchanged()
        release_local_writer_lock(self.root)
        self.assertFalse((self.root / LOCK_NAME).exists())

    def test_bytes_changed_after_preflight_hard_fail(self):
        plan = self._preflight()
        self.assertEqual(plan["state"], MAX_PREFLIGHT_STATE)
        self.ledger.write_bytes(self.before + b" ")
        rechecked = recheck_writer_preflight(
            plan,
            allowed_root=self.root,
            ledger_path=self.ledger,
        )
        self.assertEqual(rechecked["state"], "SOURCE_CHANGED_AFTER_PREFLIGHT")
        self.assertIn("source_changed_after_preflight", rechecked["blockers"])
        self.assertFalse(rechecked["persistence_authorized"])
        self.assertFalse(rechecked["ledger_write_performed"])

    def test_symlink_hard_fails(self):
        real = self.root / "real-ledger.json"
        real.write_bytes(self.before)
        link = self.root / "linked-ledger.json"
        link.symlink_to(real)
        plan = self._preflight(ledger_path=link)
        self.assertIn("symlink", plan["blockers"])
        self.assertEqual(real.read_bytes(), self.before)
        self.assertFalse(plan["ledger_write_performed"])

    def test_path_outside_allowed_root_hard_fails(self):
        outside_root = Path(self.tmp.name) / "other"
        outside_root.mkdir()
        outside = outside_root / "lifecycle-ledger.json"
        outside.write_bytes(self.before)
        before = outside.read_bytes()
        plan = self._preflight(ledger_path=outside)
        self.assertIn("path_not_allowed", plan["blockers"])
        self.assertEqual(outside.read_bytes(), before)
        self.assertFalse(plan["persistence_authorized"])

    def test_canonicalization_is_deterministic(self):
        left = canonical_json({"b": 1, "a": {"d": 2, "c": 3}})
        right = canonical_json({"a": {"c": 3, "d": 2}, "b": 1})
        self.assertEqual(left, right)
        self.assertEqual(left, '{"a":{"c":3,"d":2},"b":1}')

    def test_digest_is_recalculable(self):
        payload = genesis_logical_payload(self.document)
        first = recalculable_digest(payload)
        second = recalculable_digest(json.loads(canonical_json(payload)))
        self.assertEqual(first, second)
        self.assertEqual(first, self.document["ledger_digest"])
        changed = dict(payload)
        changed["plan_digest"] = "9" * 64
        self.assertNotEqual(recalculable_digest(changed), first)

    def test_rollback_plan_is_consistent_and_not_executed(self):
        plan = self._preflight()
        rollback = plan["rollback_strategy"]
        atomic = plan["atomic_write_strategy"]
        self.assertEqual(rollback["method"], "PREIMAGE_BACKUP_BEFORE_REPLACE")
        self.assertTrue(rollback["backup_relative_path"].endswith(".bak"))
        self.assertNotIn("..", rollback["backup_relative_path"])
        self.assertEqual(rollback["source_bytes_digest"], plan["source_bytes_digest"])
        self.assertFalse(rollback["backup_created"])
        self.assertFalse(rollback["executed"])
        self.assertEqual(atomic["method"], "TEMP_FILE_FSYNC_ATOMIC_REPLACE")
        self.assertFalse(atomic["executed"])
        self.assertEqual(plan["atomic_write_status"], "PLANNED_NOT_EXECUTED")
        self.assertEqual(plan["rollback_readiness"], "PLAN_ONLY")
        self._assert_unchanged()

    def test_secret_material_is_absent_from_output(self):
        self.document["note"] = "password=hunter2"
        self.ledger.write_text(json.dumps(self.document), encoding="utf-8")
        self.before = self.ledger.read_bytes()
        plan = self._preflight()
        rendered = json.dumps(plan)
        self.assertIn("secret_material", plan["blockers"])
        self.assertNotIn("hunter2", rendered)
        self.assertNotIn("password=hunter2", rendered)
        self.assertFalse(plan["ledger_write_performed"])
        self._assert_unchanged()

    def test_step2_stays_blocked(self):
        plan = self._preflight()
        policy = ledger_writer_policy()
        self.assertEqual(plan["expected_next_lifecycle_step"], "ENROLL_STRONG_AUTH")
        self.assertEqual(plan["expected_completed_count"], 1)
        self.assertEqual(plan["expected_receipt_count"], 1)
        self.assertEqual(plan["current_receipt_count"], 0)
        self.assertFalse(plan["step2_execution_authorized"])
        self.assertFalse(plan["executor_enabled"])
        self.assertFalse(plan["production_authorized"])
        self.assertFalse(plan["deploy_authorized"])
        self.assertFalse(plan["external_runtime_authorized"])
        self.assertFalse(policy["step2_execution_authorized"])
        self.assertFalse(policy["apply_command_available"])
        self.assertFalse(policy["next_step_authorized"])

    def test_generic_language_does_not_authorize_persistence(self):
        plan = self._preflight()
        now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
        for phrase in ("ok", "vamos lá", "pode seguir"):
            result = evaluate_future_persistence_authorization(
                plan,
                {
                    "phrase": phrase,
                    "source_ledger_digest": plan["source_ledger_digest"],
                    "target_ledger_digest": plan["target_ledger_digest"],
                    "canonical_receipt_digest": plan["canonical_receipt_digest"],
                    "ledger_append_decision_digest": plan["ledger_append_decision_digest"],
                    "admin_id": "admin.demo",
                    "session_id": "session-1",
                    "issued_at": "2026-10-01T12:00:00+00:00",
                    "nonce": "nonce-unique-0001",
                    "proof_method": "FIDO2",
                },
                now=now,
            )
            self.assertIn("generic_language", result["blockers"])
            self.assertFalse(result["persistence_authorized"])
            self.assertFalse(result["generic_language_is_authorization"])
            self.assertFalse(result["cryptographic_proof_verified"])
            self.assertFalse(result["ledger_write_performed"])
        self._assert_unchanged()

    def test_future_binding_records_without_verifying_proof(self):
        plan = self._preflight()
        now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
        result = evaluate_future_persistence_authorization(
            plan,
            {
                "source_ledger_digest": plan["source_ledger_digest"],
                "target_ledger_digest": plan["target_ledger_digest"],
                "canonical_receipt_digest": plan["canonical_receipt_digest"],
                "ledger_append_decision_digest": plan["ledger_append_decision_digest"],
                "admin_id": plan["expected_admin_id"],
                "session_id": "session-1",
                "issued_at": "2026-10-01T12:00:00+00:00",
                "nonce": "nonce-unique-0001",
                "proof_method": "WINDOWS_HELLO",
                "cryptographic_proof": {"assertion": "not-verified-in-v1"},
            },
            now=now,
        )
        self.assertEqual(
            result["state"],
            "FUTURE_STRONG_AUTH_BINDING_RECORDED_NOT_VERIFIED",
        )
        self.assertFalse(result["cryptographic_proof_verified"])
        self.assertFalse(result["strong_auth_verifier_implemented"])
        self.assertFalse(result["facial_recognition_accepted"])
        self.assertFalse(result["persistence_authorized"])
        self.assertFalse(result["step2_execution_authorized"])
        self._assert_unchanged()

    def test_cli_is_plan_only_and_refuses_apply(self):
        packet_path = self.root / "packet.json"
        review_path = self.root / "review.json"
        record_path = self.root / "record.json"
        output_path = self.root / "writer-plan.json"
        packet_path.write_text(json.dumps(self.packet), encoding="utf-8")
        review_path.write_text(json.dumps(self.review), encoding="utf-8")
        record_path.write_text(json.dumps(self.record), encoding="utf-8")
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = main([
                "--allowed-root", str(self.root),
                "--ledger", str(self.ledger),
                "--step1-preflight", str(packet_path),
                "--receipt-review", str(review_path),
                "--decision-record", str(record_path),
                "--output", str(output_path),
            ])
        self.assertEqual(code, 0)
        self.assertIn(BANNER, stdout.getvalue())
        self.assertTrue(output_path.is_file())
        saved = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["state"], MAX_PREFLIGHT_STATE)
        self.assertFalse(saved["ledger_write_performed"])
        self._assert_unchanged()
        refused = main([
            "--allowed-root", str(self.root),
            "--ledger", str(self.ledger),
            "--step1-preflight", str(packet_path),
            "--receipt-review", str(review_path),
            "--decision-record", str(record_path),
            "--apply",
        ])
        self.assertEqual(refused, 2)
        self._assert_unchanged()
        self.assertEqual(BANNER, "PLAN ONLY — NO LEDGER WRITE PERFORMED")


if __name__ == "__main__":
    unittest.main()
