"""LAB — Twilio Classic/Bulk product isolation, no producer or idempotency proof.

This suite deliberately classifies ALL observations as insufficient to grant
an external effect. It is not a provider integration or positive enrollment.
Tests use test-only placeholder operation IDs and Messages and never access
Twilio, run the Worker, schedule messages, or transmit data.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from collections import Counter
from datetime import timedelta
from pathlib import Path

from aion_chat.store import SQLiteChatStore
import test_atlasquant_aion_execution_saga as fx

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/aion/AION_P0_TWILIO_CLASSIC_BULK_CROSS_PRODUCT_MATRIX_20261020.json"
ORIGINAL = ROOT / "docs/aion/AION_P0_QUALITY_CANONICAL_85_FAILURES_CASE_REGISTRY_20261019.json"
NOW = fx.NOW


class TwilioCrossProductContractEvidenceLAB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(MATRIX.read_text(encoding="utf-8"))
        cls.original = json.loads(ORIGINAL.read_text(encoding="utf-8"))
        cls.rows = cls.doc["observations"]
        cls.by_id = {r["case_id"]: r for r in cls.rows}

    def test_01_24_scenarios_unique_and_scoped_to_three_products(self):
        self.assertEqual(len(self.rows), 24)
        self.assertEqual(len(self.by_id), 24)
        self.assertEqual(dict(Counter(r["product"] for r in self.rows)), {
            "CLASSIC": 6, "BULK_BETA": 16, "OTHER_TWILIO_PRODUCT": 2})
        self.assertIn("2010-04-01", self.doc["classic_api"])
        self.assertIn("comms.twilio.com", self.doc["bulk_api"])

    def test_02_all_24_records_prohibit_effect_resend_and_p0_closure(self):
        negative = ("original_intent_causal_receipt_verified",
                    "producer_trust_root_enrolled",
                    "no_effect_fence_verified", "auto_resend_permitted",
                    "executed_external_effect",
                    "case_closes_canonical_quality_error")
        for r in self.rows:
            with self.subTest(r["case_id"]):
                self.assertEqual(r["provider_terminal_no_effect_fence"],
                                 "NOT_ESTABLISHED")
                self.assertEqual(r["idempotency_guarantee_for_target_send"],
                                 "NOT_ESTABLISHED")
                for field in negative:
                    self.assertIs(r[field], False)
                self.assertIs(r["manual_review_before_any_future_action"], True)

    def test_03_202_accepted_and_operation_id_are_not_commit_receipts(self):
        row = self.by_id["BULK_CREATE_202_OPERATION_ID"]
        self.assertEqual(row["product"], "BULK_BETA")
        self.assertIs(self.doc["bulk_202_accepted_is_effect_receipt"], False)
        self.assertIs(self.doc["bulk_operation_id_is_idempotency_key"], False)
        self.assertIs(row["original_intent_causal_receipt_verified"], False)

    def test_04_lost_bulk_ack_is_not_retriable_just_as_classic_lost_sid(self):
        for case in ("CLASSIC_TIMEOUT_WITHOUT_SID",
                     "BULK_TIMEOUT_WITHOUT_OPERATION_ID"):
            with self.subTest(case):
                self.assertIs(self.by_id[case]["auto_resend_permitted"], False)
                self.assertEqual(self.by_id[case]["triage_state"],
                                 "READ_ONLY_OBSERVATION_HOLD")

    def test_05_bulk_aggregate_completion_not_all_message_attempt_proof(self):
        for case in ("BULK_OPERATION_COMPLETED",
                     "BULK_MULTI_RECIPIENT",
                     "BULK_FALLBACK_MANY_SIDS"):
            with self.subTest(case):
                row = self.by_id[case]
                self.assertIs(row["original_intent_causal_receipt_verified"], False)
                self.assertIs(row["auto_resend_permitted"], False)

    def test_06_other_twilio_api_idempotency_cannot_transfer_to_messaging(self):
        self.assertIs(self.doc["cross_product_idempotency_inheritance_allowed"],
                      False)
        self.assertIs(self.doc["other_twilio_products_are_not_transferable"],
                      True)
        for case in ("CONVERSATIONS_CONFIG_IDEMPOTENCY",
                     "TWILIO_INSIGHTS_IDEMPOTENCY"):
            with self.subTest(case):
                row=self.by_id[case]
                self.assertEqual(row["product"], "OTHER_TWILIO_PRODUCT")
                self.assertEqual(row["triage_state"],
                                 "CROSS_PRODUCT_INFERENCE_FORBIDDEN")
                self.assertIs(row["auto_resend_permitted"], False)

    def test_07_429_retry_after_does_not_override_aion_unknown_post_freeze(self):
        row=self.by_id["BULK_RATE_LIMIT_429"]
        self.assertIn("rate-limit", row["documented_observation"])
        self.assertFalse(row["auto_resend_permitted"])

    def test_08_bulk_500_explicit_no_retry_observed(self):
        row=self.by_id["BULK_SERVER_500_NO_RETRY"]
        self.assertIn("not to retry", row["documented_observation"])
        self.assertFalse(row["auto_resend_permitted"])

    def test_09_bulk_public_beta_lacks_sla_and_is_not_h0_approval(self):
        self.assertIs(self.doc["bulk_public_beta_no_sla"], True)
        row=self.by_id["BULK_PUBLIC_BETA_NO_SLA"]
        self.assertIn("beta", row["documented_observation"])
        self.assertFalse(row["executed_external_effect"])

    def test_10_all_sources_are_product_specific_official_https(self):
        allowed=set(self.doc["sources"].values())
        self.assertEqual(len(self.doc["sources"]), 10)
        for r in self.rows:
            with self.subTest(r["case_id"]):
                self.assertIn(r["official_source_url"], allowed)
                self.assertTrue(r["official_source_url"].startswith(
                    "https://www.twilio.com/docs/"))
        for r in self.rows:
            if r["product"]=="OTHER_TWILIO_PRODUCT":
                self.assertIn("docs/",r["official_source_url"])

    def test_11_both_twilio_products_leave_canonical_32_errors_open(self):
        canonical=[e for e in self.original["entries"]
                   if e["module"].endswith(("_execution_outbox","_execution_saga"))]
        self.assertEqual(len(canonical), 32)
        self.assertEqual(set(e["triage_status"] for e in canonical),
                         {"OPEN_NOT_WAIVED"})
        self.assertEqual(self.doc["canonical_cases_closed"],0)
        self.assertIs(self.doc["issuer_trust_root_enrolled"],False)
        self.assertIs(self.doc["worker_activated"],False)


class _SelfAssertedBulkAdapter:
    operation_id="comms_operation_01h9krwprkeee8fzqspvwy6nq8"
    message_id="comms_message_01h9krwprkeee8fzqspvwy6nq8"
    message_status="DELIVERED"
    operation_status="COMPLETED"
    webhook_verified=True
    idempotency_key_valid=True
    producer_enrolled=True
    no_effect_fenced=True
    def __init__(self):
        self.reads=0
    @property
    def send(self):
        self.reads+=1
        raise AssertionError("Untrusted bulk adapter.send was accessed")
    @property
    def reconcile(self):
        self.reads+=1
        raise AssertionError("Untrusted bulk adapter.reconcile accessed")


class TwilioCrossProductActualCoreDenialLAB(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        fixture=fx.ExecutionSagaTests()
        fixture.setUp()
        self.fixture=fixture
        self.store,self.outbox,self.budget,self.saga=fixture._components(
            self.tmp.name)
        self.addCleanup(self.store.close)
        fixture._create(self.saga)
        first=fixture._enqueue_forward(self.saga)
        self.key=first["outbox"]["idempotency_key"]

    def test_12_fake_bulk_operation_cannot_enable_create_dispatch(self):
        claim=self.outbox.claim_next("bulk-lab",now=NOW+timedelta(seconds=1),
                                    lease_seconds=60)
        self.assertEqual(claim["idempotency_key"],self.key)
        adapter=_SelfAssertedBulkAdapter()
        with self.assertRaisesRegex(PermissionError,
                                    "^INDEPENDENT_PRODUCER_NOT_ENROLLED$"):
            self.outbox.dispatch_claimed(
                self.key,worker_id="bulk-lab",adapter=adapter,
                authorize=fx.policy(self.fixture.scope),
                cumulative_authority_guard=lambda decision:
                    self.saga.authority_guard(decision,now=NOW),
                now=NOW+timedelta(seconds=2))
        self.assertEqual(adapter.reads,0)
        self.assertEqual(self.outbox.get(self.key)["state"],"BLOCKED_PRODUCER")
        self.assertEqual(self.outbox.effect_count(),0)

    def test_13_fake_bulk_operation_cannot_reconcile_unknown_effect(self):
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='UNCERTAIN' "
                "WHERE idempotency_key=?", (self.key,))
        adapter=_SelfAssertedBulkAdapter()
        before=self.outbox.get(self.key)
        with self.assertRaisesRegex(PermissionError,
                                    "^INDEPENDENT_PRODUCER_NOT_ENROLLED$"):
            self.outbox.reconcile(
                self.key,adapter=adapter,
                authorize=lambda decision:True,
                now=NOW+timedelta(seconds=2))
        self.assertEqual(self.outbox.get(self.key),before)
        self.assertEqual(adapter.reads,0)
        self.assertEqual(self.outbox.effect_count(),0)

    def test_14_fake_bulk_delivered_state_cannot_supply_saga_receipt(self):
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='CONFIRMED',effect_ref=? "
                "WHERE idempotency_key=?",
                (_SelfAssertedBulkAdapter.message_id,self.key))
        before=self.saga.get("saga-1")
        with self.assertRaisesRegex(
            PermissionError,"^INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED$"):
            self.saga.sync_forward_outcome("saga-1","one",
                now=NOW+timedelta(seconds=1))
        self.assertEqual(self.saga.get("saga-1"),before)
        self.assertEqual(self.outbox.effect_count(),0)


if __name__=="__main__":
    unittest.main()
