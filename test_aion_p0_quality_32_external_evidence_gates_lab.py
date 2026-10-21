"""P0 LAB — provenance and negative gates for 32 historical Quality ERROR.

No positive independent receipt is known/enrolled. Passing these tests only
validates triage traceability and current fail-closed negative controls; it
does not certify any of the original 32 methods or authorize external calls.
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import tempfile
import unittest
from collections import Counter
from datetime import timedelta
from pathlib import Path

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
import test_atlasquant_aion_execution_saga as fx

ROOT = Path(__file__).resolve().parent
CANONICAL = ROOT / "docs/aion/AION_P0_QUALITY_CANONICAL_85_FAILURES_CASE_REGISTRY_20261019.json"
MATRIX = ROOT / "docs/aion/AION_P0_32_EXTERNAL_PRODUCER_EVIDENCE_MATRIX_20261020.json"
NOW = fx.NOW

# Immutable Git blobs from the original Quality-85/32 evidence inventory.
# original_source_line refers to THIS historical code, never moving HEAD.
# Current code is independently checked below for unchanged method/class IDs.
PINNED_ORIGINAL_TEST_BLOBS = {
    "test_atlasquant_aion_execution_outbox":
        "4d085850cdf9a5cf79fb4ad77a9656e8c3942dee",
    "test_atlasquant_aion_execution_saga":
        "1a88dafab65085867619aaa601d671bc41f2c23a",
}


def _original_test_source(module: str) -> str:
    blob = PINNED_ORIGINAL_TEST_BLOBS[module]
    # Git's content-addressed blob is the actual original tracked source.
    # A missing or inaccessible object fails the audit (no fallback).
    result = subprocess.run(
        ["git", "cat-file", "blob", blob],
        cwd=ROOT, check=True, capture_output=True,
    )
    return result.stdout.decode("utf-8")


class ProducerEvidenceCaseIntegrityLAB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = json.loads(CANONICAL.read_text(encoding="utf-8"))
        cls.matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
        cls.registry = [row for row in cls.canonical["entries"]
                        if row["module"].endswith(
                            ("_execution_outbox", "_execution_saga"))]
        cls.rows = cls.matrix["cases"]

    @staticmethod
    def identity(row):
        return (row["module"], row.get("class_name", row.get("test_class")),
                row.get("test_method", row.get("case")),
                row.get("subtest_context"))

    def test_01_all_32_canonical_cases_preserved_one_to_one(self):
        self.assertEqual(len(self.registry), 32)
        self.assertEqual(len(self.rows), 32)
        expected = Counter(self.identity(x) for x in self.registry)
        observed = Counter(self.identity(x) for x in self.rows)
        self.assertEqual(expected, observed)
        self.assertEqual(len(observed), 32)
        self.assertEqual(len({x["case_id"] for x in self.rows}), 32)

    def test_02_exact_23_8_1_observed_gate_distribution(self):
        target = {
            "PRE_ADAPTER_PRODUCER_ENROLLMENT": 23,
            "CAUSAL_COMMITTED_EFFECT_RECEIPT": 8,
            "TERMINAL_NO_EFFECT_FENCE": 1,
        }
        self.assertEqual(dict(Counter(
            x["observed_gate"] for x in self.rows)), target)
        self.assertEqual(self.matrix["gate_counts"], target)
        self.assertEqual(self.canonical["quality_total"], 6562)
        self.assertEqual((self.canonical["fail_total"],
                          self.canonical["error_total"]), (51, 34))

    def test_03_observed_exceptions_are_not_rewritten(self):
        canonical = {self.identity(x): x for x in self.registry}
        for row in self.rows:
            with self.subTest(case=row["case_id"]):
                original = canonical[self.identity(row)]
                self.assertEqual(original["exception"],
                                 row["observed_error"])
                self.assertEqual(original["kind"], "ERROR")
                self.assertEqual(original["triage_status"], "OPEN_NOT_WAIVED")
                self.assertEqual(row["status"], "OPEN_NOT_WAIVED")

    def test_04_source_lines_ground_all_named_original_methods(self):
        # Line numbers in the ORIGINAL historical matrix are frozen.
        # Updating tests must not rewrite the immutable record's positions;
        # verify those coordinates against the pinned Git blobs instead.
        original_sources = {
            module: _original_test_source(module).splitlines()
            for module in PINNED_ORIGINAL_TEST_BLOBS
        }
        for row in self.rows:
            with self.subTest(case=row["case_id"]):
                module = row["module"]
                file = ROOT / (module + ".py")
                self.assertTrue(file.is_file())
                lines = original_sources[module]
                line_no = row["original_source_line"]
                self.assertGreater(line_no, 0)
                self.assertLessEqual(line_no, len(lines))
                self.assertRegex(
                    lines[line_no - 1],
                    r"^\s+def\s+" + re.escape(row["test_method"]) + r"\(",
                )
                previous = "\n".join(lines[:line_no - 1])
                classes = re.findall(r"^class\s+(\w+)\(", previous, re.M)
                self.assertTrue(classes)
                self.assertEqual(classes[-1], row["class_name"])

                # The CURRENT source must still define the same method in the
                # same class: moved lines are OK, removed tests are NOT.
                tree = ast.parse(file.read_text(encoding="utf-8"))
                methods = {
                    item.name
                    for node in tree.body
                    if isinstance(node, ast.ClassDef)
                    and node.name == row["class_name"]
                    for item in node.body
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                self.assertIn(row["test_method"], methods)

    def test_05_no_fictional_trust_enrollment_or_historical_waiver(self):
        self.assertEqual(self.matrix["status"],
                         "HARD_NO_GO__ALL_OPEN_NOT_WAIVED")
        self.assertIs(self.matrix["external_authority_enrolled"], False)
        self.assertIs(self.matrix["real_producer_receipts_validated"], False)
        self.assertIs(self.matrix["automated_retry_authorized"], False)
        self.assertIs(self.matrix["human_owner_proof_verified"], False)
        for row in self.rows:
            with self.subTest(case=row["case_id"]):
                self.assertIs(row["historical_equivalence_proven"], False)
                self.assertIs(row["independent_enrollment_available"], False)
                self.assertIs(row["authenticated_receipt_available"], False)
                self.assertEqual(row["safe_lab_evidence_scope"],
                                 "NEGATIVE_BOUNDARY_ONLY_NOT_ORIGINAL_TEST_PASS")
                self.assertGreater(len(row["exit_evidence_missing"]), 50)


class _HostileAdapter:
    # Even looking up a property can execute arbitrary code: do not touch.
    producer_enrolled = True
    issuer_root_verified = True
    causal_receipt_verified = True
    terminal_no_effect_fence = True

    def __init__(self):
        self.reads = 0

    @property
    def send(self):
        self.reads += 1
        raise AssertionError("untrusted adapter.send descriptor accessed")

    @property
    def reconcile(self):
        self.reads += 1
        raise AssertionError("untrusted adapter.reconcile descriptor accessed")


class ProducerEvidenceActualGateLAB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fx = fx.ExecutionSagaTests()
        self.fx.setUp()
        self.store, self.outbox, self.budget, self.saga = self.fx._components(
            self.tmp.name)
        self.addCleanup(self.store.close)
        self.fx._create(self.saga)
        self.first = self.fx._enqueue_forward(self.saga)
        self.key = self.first["outbox"]["idempotency_key"]

    def test_06_missing_producer_blocks_dispatch_before_adapter_properties(self):
        row = self.outbox.claim_next(
            "evidence-worker", now=NOW + timedelta(seconds=1),
            lease_seconds=60)
        self.assertIsNotNone(row)
        adapter = _HostileAdapter()
        with self.assertRaisesRegex(
                PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$"):
            self.outbox.dispatch_claimed(
                self.key,
                worker_id="evidence-worker",
                authorize=fx.policy(self.fx.scope),
                cumulative_authority_guard=lambda decision:
                    self.saga.authority_guard(decision, now=NOW),
                adapter=adapter, now=NOW + timedelta(seconds=2))
        self.assertEqual(adapter.reads, 0)
        self.assertEqual(self.outbox.get(self.key)["state"], "BLOCKED_PRODUCER")
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_07_uncertain_and_sent_cannot_reconcile_from_adapter_claims(self):
        for state in ("UNCERTAIN", "SENT"):
            with self.subTest(state=state):
                with self.store.db:
                    self.store.db.execute(
                        "UPDATE action_outbox SET state=? WHERE idempotency_key=?",
                        (state, self.key))
                before = self.outbox.get(self.key)
                adapter = _HostileAdapter()
                callbacks = []
                def authorize(decision):
                    callbacks.append(True)
                    raise AssertionError("untrusted callback accessed")
                with self.assertRaisesRegex(
                        PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$"):
                    self.outbox.reconcile(
                        self.key, adapter=adapter, authorize=authorize,
                        now=NOW + timedelta(seconds=3))
                self.assertEqual(adapter.reads, 0)
                self.assertEqual(callbacks, [])
                self.assertEqual(self.outbox.get(self.key), before)
                self.assertEqual(self.outbox.effect_count(), 0)

    def test_08_local_confirmed_effect_claim_is_not_real_receipt(self):
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='CONFIRMED',"
                "effect_ref='FAKE_SQL_NOT_EXTERNAL_PROOF' "
                "WHERE idempotency_key=?", (self.key,))
        before = self.saga.get("saga-1")
        budget_before = self.budget.snapshot("saga-1", now=NOW)
        with self.assertRaisesRegex(
                PermissionError, "^INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED$"):
            self.saga.sync_forward_outcome(
                "saga-1", "one", now=NOW + timedelta(seconds=2))
        self.assertEqual(self.saga.get("saga-1"), before)
        self.assertEqual(self.budget.snapshot("saga-1", now=NOW),
                         budget_before)
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_09_local_negative_cannot_become_terminal_no_effect_fence(self):
        for state in ("FAILED", "REVOKED", "BLOCKED_REAPPROVAL"):
            with self.subTest(state=state):
                with self.store.db:
                    self.store.db.execute(
                        "UPDATE action_outbox SET state=?,"
                        "last_error='FAKE_LOCAL_NOT_A_PRODUCER_FENCE' "
                        "WHERE idempotency_key=?", (state,self.key))
                before = self.saga.get("saga-1")
                with self.assertRaisesRegex(
                        PermissionError,
                        "^INDEPENDENT_PRODUCER_NO_EFFECT_FENCE_NOT_ENROLLED$"):
                    self.saga.sync_forward_outcome(
                        "saga-1", "one", now=NOW + timedelta(seconds=2))
                self.assertEqual(self.saga.get("saga-1"), before)
                self.assertEqual(self.outbox.effect_count(), 0)

    def test_10_uncertainty_remains_non_terminal_and_non_resendable(self):
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='UNCERTAIN' "
                "WHERE idempotency_key=?", (self.key,))
        result = self.saga.sync_forward_outcome(
            "saga-1", "one", now=NOW + timedelta(seconds=1))
        self.assertEqual(result["state"], "RECONCILIATION_REQUIRED")
        self.assertIs(result["executes_action"], False)
        self.assertIsNone(self.outbox.claim_next(
            "new-worker", now=NOW + timedelta(seconds=2)))
        self.assertEqual(self.outbox.get(self.key)["state"], "UNCERTAIN")
        self.assertEqual(self.outbox.effect_count(), 0)


if __name__ == "__main__":
    unittest.main()
