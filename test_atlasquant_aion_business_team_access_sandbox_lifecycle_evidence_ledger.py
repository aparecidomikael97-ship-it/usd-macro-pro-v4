import ast
import hashlib
import json
import unittest
from pathlib import Path

from atlasquant_aion_business_team_access_sandbox_lifecycle_authorization import (
    SCHEMA as AUTH_SCHEMA,
)
from atlasquant_aion_business_team_access_lifecycle_authorization_package import (
    SCHEMA as PACKAGE_SCHEMA,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_evidence_ledger import (
    GENESIS_DIGEST,
    build_evidence_receipt,
    build_lifecycle_evidence_ledger,
    evidence_receipt_template,
    lifecycle_ledger_template,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_plan import (
    LIFECYCLE_STEP_IDS,
    SCHEMA as PLAN_SCHEMA,
)

def _digest(value):
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _plan():
    steps = []
    mutation_steps = {1, 2, 4, 6, 7, 8}
    for index, step_id in enumerate(LIFECYCLE_STEP_IDS, start=1):
        steps.append({
            "order": index,
            "id": step_id,
            "mutation": index in mutation_steps,
            "requires_manual_apply": True,
            "evidence_required": ["proof"],
        })
    return {
        "schema": PLAN_SCHEMA,
        "state": "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_EXECUTION_DECISION",
        "plan_digest": "a" * 64,
        "baseline_evidence_digest": "b" * 64,
        "baseline_acceptance_record_digest": "e" * 64,
        "steps": steps,
    }


def _auth():
    package_payload = {
        "materialization_digest": "d" * 64,
        "plan_digest": "a" * 64,
        "baseline_evidence_digest": "b" * 64,
        "baseline_acceptance_record_digest": "e" * 64,
        "operator_session_id": "f" * 32,
        "authorization_record_digest": "c" * 64,
        "approved_by": "admin.demo",
        "approved_at": "2026-09-30T21:40:00+00:00",
    }
    return {
        "schema": AUTH_SCHEMA,
        "state": "EXPLICIT_SANDBOX_LIFECYCLE_AUTHORIZATION_RECORD_VERIFIED",
        "authorization_record_verified": True,
        "sandbox_lifecycle_manual_execution_authorized": True,
        "automatic_execution_authorized": False,
        "plan_digest": "a" * 64,
        "baseline_evidence_digest": "b" * 64,
        "record_digest": "c" * 64,
        "approved_by": "admin.demo",
        "approved_at": "2026-09-30T21:40:00+00:00",
        "authorization_package_schema": PACKAGE_SCHEMA,
        "materialization_binding_verified": True,
        "materialization_digest": "d" * 64,
        "baseline_acceptance_record_digest": "e" * 64,
        "operator_session_id": "f" * 32,
        "authorization_package_digest": _digest(package_payload),
        "executor_enabled": False,
        "production_authorized": False,
        "executes_action": False,
    }


def _receipt(order, previous, evidence_seed):
    mutation_steps = {1, 2, 4, 6, 7, 8}
    return build_evidence_receipt(
        _plan(),
        _auth(),
        step_order=order,
        step_id=LIFECYCLE_STEP_IDS[order - 1],
        evidence_digest=evidence_seed * 64,
        observed_at=f"2026-09-30T21:{order:02d}:00+00:00",
        previous_entry_digest=previous,
        mutation_observed=order in mutation_steps,
        sandbox_only=True,
        production_targeted=False,
        secret_material_included=False,
    )


class TeamAccessSandboxLifecycleEvidenceLedgerTests(unittest.TestCase):
    def test_template_starts_at_first_step_without_execution_authority(self):
        ledger = lifecycle_ledger_template()
        self.assertEqual(ledger["next_expected_step_order"], 1)
        self.assertEqual(
            ledger["next_expected_step_id"], LIFECYCLE_STEP_IDS[0]
        )
        self.assertFalse(ledger["executor_enabled"])
        self.assertFalse(ledger["production_authorized"])
        self.assertFalse(ledger["executes_action"])

    def test_receipt_template_binds_expected_step(self):
        row = evidence_receipt_template(_plan(), _auth(), step_order=1)
        self.assertEqual(
            row["state"], "SANDBOX_LIFECYCLE_STEP_EVIDENCE_REQUIRED"
        )
        self.assertEqual(row["step_id"], LIFECYCLE_STEP_IDS[0])
        self.assertEqual(row["plan_digest"], "a" * 64)

    def test_first_receipt_and_partial_ledger_are_chain_bound(self):
        first = _receipt(1, GENESIS_DIGEST, "d")
        self.assertEqual(
            first["state"], "SANDBOX_LIFECYCLE_STEP_EVIDENCE_RECEIPT_READY"
        )
        self.assertTrue(first["receipt_digest"])
        self.assertFalse(first["raw_evidence_stored"])
        ledger = build_lifecycle_evidence_ledger(_plan(), _auth(), [first])
        self.assertEqual(
            ledger["state"], "READY_FOR_NEXT_SANDBOX_LIFECYCLE_STEP"
        )
        self.assertEqual(ledger["completed_count"], 1)
        self.assertEqual(ledger["next_expected_step_order"], 2)
        self.assertEqual(ledger["chain_head_digest"], first["receipt_digest"])
        self.assertFalse(ledger["automatic_next_step_authorized"])

    def test_legacy_authorization_without_materialization_package_blocks(self):
        auth = _auth()
        auth.pop("authorization_package_digest")
        auth.pop("materialization_digest")
        auth.pop("materialization_binding_verified")
        ledger = build_lifecycle_evidence_ledger(_plan(), auth, [])
        self.assertEqual(
            ledger["state"], "SANDBOX_LIFECYCLE_EVIDENCE_LEDGER_BLOCKED"
        )
        self.assertIn("authorization_binding", ledger["blockers"])

    def test_wrong_order_or_chain_blocks(self):
        first = _receipt(1, GENESIS_DIGEST, "d")
        second = _receipt(2, GENESIS_DIGEST, "e")
        ledger = build_lifecycle_evidence_ledger(
            _plan(), _auth(), [first, second]
        )
        self.assertEqual(
            ledger["state"], "SANDBOX_LIFECYCLE_EVIDENCE_LEDGER_BLOCKED"
        )
        self.assertIn("step_2", ledger["blockers"])
        self.assertEqual(ledger["ledger_digest"], "")

    def test_complete_ten_step_chain_requires_review(self):
        receipts = []
        previous = GENESIS_DIGEST
        seeds = ["d", "e", "f", "a", "b", "c", "1", "2", "3", "4"]
        for order in range(1, 11):
            receipt = _receipt(order, previous, seeds[order - 1])
            self.assertEqual(
                receipt["state"],
                "SANDBOX_LIFECYCLE_STEP_EVIDENCE_RECEIPT_READY",
            )
            receipts.append(receipt)
            previous = receipt["receipt_digest"]

        ledger = build_lifecycle_evidence_ledger(
            _plan(), _auth(), receipts
        )
        self.assertEqual(
            ledger["state"],
            "SANDBOX_LIFECYCLE_EVIDENCE_COMPLETE_REVIEW_REQUIRED",
        )
        self.assertEqual(ledger["completed_count"], 10)
        self.assertTrue(ledger["ledger_complete"])
        self.assertTrue(ledger["ledger_digest"])
        self.assertFalse(ledger["production_authorized"])
        self.assertFalse(ledger["executes_action"])

    def test_tampered_receipt_digest_blocks(self):
        first = _receipt(1, GENESIS_DIGEST, "d")
        first["evidence_digest"] = "e" * 64
        ledger = build_lifecycle_evidence_ledger(_plan(), _auth(), [first])
        self.assertEqual(
            ledger["state"], "SANDBOX_LIFECYCLE_EVIDENCE_LEDGER_BLOCKED"
        )
        self.assertIn("receipt_integrity", ledger["entries"][0]["blockers"])

    def test_missing_verified_authorization_blocks(self):
        ledger = build_lifecycle_evidence_ledger(_plan(), {}, [])
        self.assertEqual(
            ledger["state"], "SANDBOX_LIFECYCLE_EVIDENCE_LEDGER_BLOCKED"
        )
        self.assertIn("authorization_binding", ledger["blockers"])

    def test_module_has_no_network_process_or_provider_imports(self):
        source = Path(
            "atlasquant_aion_business_team_access_sandbox_lifecycle_evidence_ledger.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertFalse(
            imported.intersection(
                {"requests", "httpx", "socket", "subprocess", "docker"}
            )
        )


if __name__ == "__main__":
    unittest.main()
