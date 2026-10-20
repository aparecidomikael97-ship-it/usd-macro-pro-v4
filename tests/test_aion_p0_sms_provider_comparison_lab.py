"""P0 LAB — OneSignal 30-day Create idempotency is NOT an AION effect receipt.

Tests compare endpoint-specific public contracts; no SDK, actual provider,
customer phone, external calls, credentials, Worker or automatic resend.
Green proves only this evidence-policy matrix and current fail-closed gates.
"""
from __future__ import annotations

from collections import Counter
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest

from atlasquant_aion_execution_outbox import ExecutionOutbox
import test_atlasquant_aion_execution_saga as fx

ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/"docs/aion/AION_P0_SMS_PROVIDER_EVIDENCE_COMPARISON_20261020.json"
REG=ROOT/"docs/aion/AION_P0_QUALITY_CANONICAL_85_FAILURES_CASE_REGISTRY_20261019.json"
NOW=fx.NOW

class SMSProviderContractComparisonsLAB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads(FILE.read_text(encoding="utf-8"))
        cls.rows=cls.data["cases"]
        cls.by_id={r["case_id"]:r for r in cls.rows}

    def test_01_exact_inventory_and_product_split(self):
        self.assertEqual(len(self.rows),18)
        self.assertEqual(len(self.by_id),18)
        self.assertEqual(dict(Counter(r["provider"] for r in self.rows)),{
            "ONESIGNAL_SMS_CREATE":11,
            "TWILIO_CLASSIC_MESSAGES":3,
            "TWILIO_BULK_BETA":4,
        })

    def test_02_only_onesignal_has_documented_30_day_create_dedupe(self):
        for row in self.rows:
            with self.subTest(row["case_id"]):
                if row["provider"]=="ONESIGNAL_SMS_CREATE":
                    self.assertIs(row["client_create_deduplication_documented"],True)
                    self.assertEqual(row["client_create_dedupe_lifetime_days"],30)
                else:
                    self.assertIs(row["client_create_deduplication_documented"],False)
                    self.assertIsNone(row["client_create_dedupe_lifetime_days"])

    def test_03_dedupe_does_not_entail_independent_receipt_or_no_effect_fence(self):
        flags=("dedupe_is_full_external_effect_receipt",
               "end_to_end_carrier_at_most_once_proven",
               "independent_issuer_and_scope_enrolled",
               "terminal_no_effect_fence_proven",
               "cryptographic_aion_bound_effect_receipt_proven",
               "auto_resend_authorized",
               "canonical_quality_case_waived")
        for row in self.rows:
            with self.subTest(row["case_id"]):
                for flag in flags:
                    self.assertIs(row[flag],False)
                self.assertIs(row["manual_reconciliation_required"],True)
                self.assertEqual(row["decision"],"HOLD_NO_EXTERNAL_EFFECT")

    def test_04_key_expiry_never_unlocks_resend(self):
        self.assertTrue(self.data["onesignal_original_key_after_expiry_may_create_again"])
        for case in ("OS-03","OS-04","TC-01","TB-02"):
            self.assertFalse(self.by_id[case]["auto_resend_authorized"])
        self.assertEqual(self.data["negative_uncertain_effect_policy"],
                         "ZERO_AUTO_RESEND")

    def test_05_same_key_changed_payload_is_not_same_intended_operation(self):
        row=self.by_id["OS-02"]
        self.assertIn("client MUST reject locally",row["observation"])
        self.assertTrue(self.data["onesignal_first_request_wins_on_key_reuse"])
        self.assertFalse(row["end_to_end_carrier_at_most_once_proven"])

    def test_06_twilio_bulk_operation_id_must_not_inherit_onesignal_key(self):
        self.assertFalse(self.data["twilio_bulk_operation_id_is_client_dedupe_key"])
        self.assertFalse(self.by_id["TB-01"]["client_create_deduplication_documented"])
        self.assertFalse(self.by_id["TC-01"]["client_create_deduplication_documented"])

    def test_07_sources_product_specific_and_no_private_mail_in_repository(self):
        urls=set(self.data["source_urls"].values())
        self.assertEqual(len(urls),8)
        for row in self.rows:
            with self.subTest(row["case_id"]):
                self.assertIn(row["official_url"],urls)
                self.assertTrue(row["official_url"].startswith("https://"))
        self.assertEqual(self.data["external_calls_made"],0)
        self.assertIs(self.data["auth_or_secret_loaded"],False)

    def test_08_historical_32_remain_nonwaived(self):
        data=json.loads(REG.read_text(encoding="utf-8"))
        entries=[x for x in data["entries"] if
                 x["module"].endswith(("_execution_outbox","_execution_saga"))]
        self.assertEqual(len(entries),32)
        self.assertEqual(set(x["triage_status"] for x in entries),
                         {"OPEN_NOT_WAIVED"})
        self.assertEqual(self.data["canonical_outbox_saga_errors_unwaived"],32)
        self.assertIs(self.data["h0_producer_approved"],False)


class _FalseOneSignalAdapter:
    idempotency_key="00000000-0000-4000-8000-000000000000"
    dedupe_window_days=30
    message_status="delivered"
    signed_effect_receipt=True
    provider_enrolled=True
    def __init__(self): self.calls=0
    @property
    def send(self):
        self.calls+=1
        raise AssertionError("OneSignal adapter property access forbidden")
    @property
    def reconcile(self):
        self.calls+=1
        raise AssertionError("OneSignal reconcile access forbidden")

class SMSProviderActualFailClosedLAB(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fx=fx.ExecutionSagaTests()
        self.fx.setUp()
        self.store,self.outbox,self.budget,self.saga=self.fx._components(
            self.tmp.name)
        self.addCleanup(self.store.close)
        self.fx._create(self.saga)
        result=self.fx._enqueue_forward(self.saga)
        self.key=result["outbox"]["idempotency_key"]

    def test_09_self_claimed_onesignal_dedup_never_enrolls_aion_producer(self):
        lease=self.outbox.claim_next(
            "provider-lab-worker", now=NOW+timedelta(seconds=1),
            lease_seconds=60)
        self.assertEqual(lease["idempotency_key"],self.key)
        adapter=_FalseOneSignalAdapter()
        with self.assertRaisesRegex(PermissionError,
                                    "^INDEPENDENT_PRODUCER_NOT_ENROLLED$"):
            self.outbox.dispatch_claimed(
                self.key,worker_id="provider-lab-worker",
                authorize=fx.policy(self.fx.scope),
                adapter=adapter,
                cumulative_authority_guard=lambda d:
                    self.saga.authority_guard(d,now=NOW),
                now=NOW+timedelta(seconds=2))
        self.assertEqual(adapter.calls,0)
        self.assertEqual(self.outbox.get(self.key)["state"],"BLOCKED_PRODUCER")
        self.assertEqual(self.outbox.effect_count(),0)

    def test_10_fake_onesignal_message_id_does_not_prove_commit(self):
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='CONFIRMED',"
                "effect_ref='onesignal-local-not-a-receipt' "
                "WHERE idempotency_key=?", (self.key,))
        before=self.saga.get("saga-1")
        with self.assertRaisesRegex(
            PermissionError,"^INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED$"):
            self.saga.sync_forward_outcome(
                "saga-1","one",now=NOW+timedelta(seconds=1))
        self.assertEqual(self.saga.get("saga-1"),before)
        self.assertEqual(self.outbox.effect_count(),0)

    def test_11_failed_lookup_cannot_fence_future_effect(self):
        with self.store.db:
            self.store.db.execute(
                "UPDATE action_outbox SET state='FAILED',"
                "last_error='404_NO_FENCE' WHERE idempotency_key=?",
                (self.key,))
        with self.assertRaisesRegex(
            PermissionError,
            "^INDEPENDENT_PRODUCER_NO_EFFECT_FENCE_NOT_ENROLLED$"):
            self.saga.sync_forward_outcome(
                "saga-1","one",now=NOW+timedelta(seconds=1))
        self.assertEqual(self.outbox.effect_count(),0)


if __name__=="__main__":
    unittest.main()
