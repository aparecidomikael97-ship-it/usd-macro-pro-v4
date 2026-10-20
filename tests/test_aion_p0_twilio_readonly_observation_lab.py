"""AION P0 LAB — Twilio advisory observation is NOT autonomous effect proof.

Official Twilio Message Resource observations are useful to humans for
reconciliation. No Twilio account, API key, live Message SID, cryptographic
webhook validation, provider enrollment or real outgoing call is present.
Green tests NEVER certify all 32 canonical ERROR or approve any resend.
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
OBSERVATIONS = ROOT / "docs/aion/AION_P0_TWILIO_READONLY_OBSERVATION_MATRIX_20261020.json"
ORIGINAL = ROOT / "docs/aion/AION_P0_QUALITY_CANONICAL_85_FAILURES_CASE_REGISTRY_20261019.json"
NOW = fx.NOW


class TwilioReadOnlyObservationEvidenceLAB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(OBSERVATIONS.read_text(encoding="utf-8"))
        cls.registry = json.loads(ORIGINAL.read_text(encoding="utf-8"))
        cls.cases = cls.policy["cases"]
        cls.by_id = {row["case_id"]: row for row in cls.cases}

    def test_01_exact_22_scenarios_unique_and_source_linked(self):
        self.assertEqual(len(self.cases), 22)
        self.assertEqual(len(self.by_id), 22)
        self.assertEqual(self.policy["provider"],
                         "Twilio Programmable Messaging REST Messages resource (SMS/WhatsApp via Twilio only)")
        self.assertEqual(len(set(self.policy["source_urls"])), 6)
        for row in self.cases:
            with self.subTest(case=row["case_id"]):
                self.assertIn(row["source_url"], self.policy["source_urls"])
                self.assertTrue(row["source_url"].startswith("https://"))
                self.assertTrue(row["observation_meaning"])
                self.assertEqual(row["aion_classification"].endswith("_HOLD"), True)

    def test_02_no_scenario_is_trusted_effect_or_terminal_absence_fence(self):
        flags = (
            "provider_account_enrollment_verified",
            "exact_original_intent_bound",
            "independently_authenticated_committed_effect_receipt",
            "terminal_no_effect_fence_verified",
            "safe_automatic_resend",
            "effect_execution_authorized",
            "original_quality_case_closed",
        )
        for row in self.cases:
            with self.subTest(case=row["case_id"]):
                for flag in flags:
                    self.assertIs(row[flag], False, (row["case_id"], flag))
                self.assertIs(row["human_review_required"], True)
        self.assertIs(self.policy["no_auto_resend_after_unknown"], True)
        self.assertEqual(self.policy["canonical_32_errors"], "OPEN_NOT_WAIVED")

    def test_03_status_vocab_is_twilio_lifecycle_not_action_authority(self):
        statuses = {row["twilio_status"] for row in self.cases
                    if row["category"] == "SID_STATUS"}
        self.assertEqual(statuses, {"queued", "accepted", "scheduled",
            "sending", "sent", "delivered", "read", "failed",
            "undelivered", "canceled"})
        self.assertTrue(self.policy["status_terms_are_delivery_lifecycle_not_full_effect_proof"])
        for case in ("FETCH_SENT", "FETCH_DELIVERED", "FETCH_READ",
                     "FETCH_FAILED", "FETCH_UNDELIVERED", "SCHEDULED_CANCELED"):
            with self.subTest(case=case):
                self.assertIs(self.by_id[case]["safe_automatic_resend"], False)
                self.assertIs(self.by_id[case]["terminal_no_effect_fence_verified"], False)

    def test_04_list_filters_and_missing_sid_do_not_certify_absence(self):
        for case in ("UNKNOWN_CREATE_TIMEOUT", "UNKNOWN_CREATE_HTTP_500",
                     "UNKNOWN_CREATE_CONNECTION_RESET", "LIST_FILTERS_ZERO_RESULTS",
                     "LIST_FILTERS_SINGLE_MATCH", "LIST_FILTERS_MULTIPLE_MATCHES"):
            with self.subTest(case=case):
                self.assertFalse(self.by_id[case]["safe_automatic_resend"])
                self.assertFalse(self.by_id[case]["independently_authenticated_committed_effect_receipt"])

    def test_05_callback_signature_is_not_independent_causal_attestation(self):
        for case in ("CALLBACK_WITH_SELF_ATTESTED_SIGNATURE",
                     "CALLBACK_WITH_SDK_VALID_SIGNATURE",
                     "CALLBACK_INITIAL_STATUS_MISSING"):
            with self.subTest(case=case):
                row = self.by_id[case]
                self.assertEqual(row["aion_classification"], "WEBHOOK_METADATA_HOLD")
                self.assertIs(row["independently_authenticated_committed_effect_receipt"], False)
                self.assertIs(row["effect_execution_authorized"], False)

    def test_06_scheduled_cancel_is_not_general_no_effect_fence(self):
        row = self.by_id["SCHEDULED_CANCELED"]
        self.assertEqual(row["twilio_status"], "canceled")
        self.assertIn("scheduled", row["observation_meaning"])
        self.assertIs(row["terminal_no_effect_fence_verified"], False)
        self.assertIs(row["safe_automatic_resend"], False)

    def test_07_source_contracts_remain_unverified_not_claimed_absent_everywhere(self):
        self.assertEqual(self.policy["create_idempotency_contract_in_primary_docs"], "NOT_ESTABLISHED")
        self.assertEqual(self.policy["producer_enforced_terminal_no_effect_fence_in_primary_docs"],
                         "NOT_ESTABLISHED")
        self.assertEqual(self.policy["authenticated_outcome_bound_to_aion_intent_and_epoch"],
                         "NOT_ESTABLISHED")
        for key in ("network_requests_performed",):
            self.assertEqual(self.policy[key], 0)
        for key in ("account_or_issuer_enrolled", "secrets_loaded",
                    "message_created", "message_scheduled", "message_canceled"):
            self.assertIs(self.policy[key], False)

    def test_08_legacy_23_8_1_quality_errors_unchanged(self):
        rows = [e for e in self.registry["entries"] if
                e["module"].endswith(("_execution_outbox", "_execution_saga"))]
        self.assertEqual(len(rows), 32)
        self.assertEqual(Counter(e["exception"].split(": ")[-1] for e in rows), {
            "INDEPENDENT_PRODUCER_NOT_ENROLLED": 23,
            "INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED": 8,
            "INDEPENDENT_PRODUCER_NO_EFFECT_FENCE_NOT_ENROLLED": 1,
        })
        self.assertEqual(set(e["triage_status"] for e in rows), {"OPEN_NOT_WAIVED"})


class _HostileTwilioAdapter:
    # Claimed enrollment, SID and callback are self-attested test-only fields.
    producer_enrolled = True
    twilio_status = "delivered"
    message_sid = "SM" + ("a" * 32)
    webhook_signature_valid = True
    authoritative_absence = True
    confirmed = True
    effect_ref = "SELF_ATTESTED_NOT_AION_PROOF"

    def __init__(self):
        self.adapter_reads = 0

    @property
    def send(self):
        self.adapter_reads += 1
        raise AssertionError("Twilio send property accessed without enrollment")

    @property
    def reconcile(self):
        self.adapter_reads += 1
        raise AssertionError("Twilio reconcile property accessed without enrollment")


class TwilioObservationActualAIONBoundaryLAB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fixture = fx.ExecutionSagaTests()
        self.fixture.setUp()
        self.store,self.outbox,self.budget,self.saga = (
            self.fixture._components(self.tmp.name))
        self.addCleanup(self.store.close)
        self.fixture._create(self.saga)
        first = self.fixture._enqueue_forward(self.saga)
        self.key = first["outbox"]["idempotency_key"]

    def test_09_self_attested_twilio_send_never_crosses_adapter_descriptor(self):
        lease = self.outbox.claim_next(
            "twilio-lab-only", now=NOW+timedelta(seconds=1),
            lease_seconds=60)
        self.assertEqual(lease["idempotency_key"], self.key)
        adapter = _HostileTwilioAdapter()
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$"
        ):
            self.outbox.dispatch_claimed(
                self.key, worker_id="twilio-lab-only",
                adapter=adapter, authorize=fx.policy(self.fixture.scope),
                cumulative_authority_guard=lambda decision:
                    self.saga.authority_guard(decision, now=NOW),
                now=NOW+timedelta(seconds=2))
        self.assertEqual(adapter.adapter_reads, 0)
        self.assertEqual(self.outbox.get(self.key)["state"], "BLOCKED_PRODUCER")
        self.assertEqual(self.outbox.effect_count(), 0)

    def test_10_readonly_fetch_or_list_claim_cannot_reconcile_sent_unknown(self):
        for state in ("SENT", "UNCERTAIN"):
            with self.subTest(state=state):
                with self.store.db:
                    self.store.db.execute(
                        "UPDATE action_outbox SET state=? WHERE idempotency_key=?",
                        (state,self.key))
                before = self.outbox.get(self.key)
                adapter = _HostileTwilioAdapter()
                callback = []
                def authorize(decision):
                    callback.append(True)
                    raise AssertionError("untrusted callback accessed")
                with self.assertRaisesRegex(
                    PermissionError, "^INDEPENDENT_PRODUCER_NOT_ENROLLED$"
                ):
                    self.outbox.reconcile(
                        self.key, adapter=adapter, authorize=authorize,
                        now=NOW+timedelta(seconds=3))
                self.assertEqual(adapter.adapter_reads, 0)
                self.assertEqual(callback, [])
                self.assertEqual(self.outbox.get(self.key), before)
                self.assertEqual(self.outbox.effect_count(), 0)

    def test_11_twilio_looking_sid_local_confirmed_is_not_effect_receipt(self):
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='CONFIRMED',effect_ref=? "
                "WHERE idempotency_key=?",
                (_HostileTwilioAdapter.message_sid,self.key))
        saga_before = self.saga.get("saga-1")
        with self.assertRaisesRegex(
            PermissionError, "^INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED$"
        ):
            self.saga.sync_forward_outcome("saga-1","one",
                now=NOW+timedelta(seconds=1))
        self.assertEqual(self.saga.get("saga-1"), saga_before)
        self.assertEqual(self.outbox.effect_count(),0)

    def test_12_failed_or_revoked_local_status_is_not_twilio_terminal_fence(self):
        for state in ("FAILED","REVOKED","BLOCKED_REAPPROVAL"):
            with self.subTest(state=state):
                with self.store.db:
                    self.store.db.execute(
                        "UPDATE action_outbox SET state=?,last_error=? "
                        "WHERE idempotency_key=?",
                        (state,"TWILIO_STATUS_NOT_A_TERMINAL_FENCE",self.key))
                snap=self.saga.get("saga-1")
                with self.assertRaisesRegex(
                    PermissionError,
                    "^INDEPENDENT_PRODUCER_NO_EFFECT_FENCE_NOT_ENROLLED$"
                ):
                    self.saga.sync_forward_outcome("saga-1","one",
                        now=NOW+timedelta(seconds=1))
                self.assertEqual(self.saga.get("saga-1"),snap)
                self.assertEqual(self.outbox.effect_count(),0)

    def test_13_ambiguous_twilio_effect_still_blocks_retry_and_fifo(self):
        first=self.outbox.get(self.key)
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='UNCERTAIN' "
                "WHERE idempotency_key=?", (self.key,))
        second=self.outbox.enqueue(
            intent_ref="local-intent-second",
            action="local_stage_only",
            payload={"kind":"not-a-send"},
            aggregate_key=first["aggregate_key"],
            policy_version=first["decision"]["policy_version"],
            authorization_ref="LOCAL_NOT_EXTERNAL_APPROVAL",
            created_at=NOW,
            valid_until=NOW+timedelta(minutes=5),
        )
        self.assertEqual(self.outbox.get(second["idempotency_key"])["state"],"PENDING")
        self.assertIsNone(self.outbox.claim_next(
            "twilio-not-resend",now=NOW+timedelta(seconds=2)))
        self.assertEqual(self.outbox.effect_count(),0)


if __name__=="__main__":
    unittest.main()
