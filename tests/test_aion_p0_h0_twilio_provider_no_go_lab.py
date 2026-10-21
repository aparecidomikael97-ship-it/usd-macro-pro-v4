"""Twilio Messages provider-fit NO-GO documentation and REAL Outbox hardstop drift.

Structural assertions are NOT provider attestation and do not unlock H0.
Behavioral Outbox rollback and A79 regressions run in the paired workflow.
No HTTP requests, Twilio credentials, provisioning or external effects.
"""
from __future__ import annotations

from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/"docs"/"aion"/"p0-h0-twilio-programmable-messaging-provider-no-go-20261021.md"
OUTBOX=ROOT/"atlasquant_aion_execution_outbox.py"

class TwilioH0DocumentationAndSourceDenial(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=DOC.read_text(encoding="utf-8")
        cls.src=OUTBOX.read_text(encoding="utf-8")
        cls.dispatch=cls.src.split("    def dispatch_claimed(",1)[1].split("    def reconcile(",1)[0]
        cls.reconcile=cls.src.split("    def reconcile(",1)[1].split("    def effect_count(",1)[0]
        cls.confirm=cls.src.split("    def _confirm(",1)[1].split("    def dispatch_claimed(",1)[0]
        cls.claim=cls.src.split("    def claim_next(",1)[1].split("    def _authorization_gate(",1)[0]
        cls.reclaim=cls.src.split("    def release_expired_claims(",1)[1].split("    def claim_next(",1)[0]

    def test_01_scope_is_twilio_message_create_not_conversations_orchestrator(self):
        self.assertIn("Twilio Programmable Messaging",self.doc)
        self.assertIn("POST /2010-04-01/Accounts/{AccountSid}/Messages.json",self.doc)
        self.assertIn("Twilio Conversations Orchestrator",self.doc)

    def test_02_provider_decision_is_hard_no_go_not_conditional_auto_send(self):
        self.assertIn("HARD NO-GO",self.doc)
        self.assertIn("ZERO_AUTO_RESEND",self.doc)
        self.assertIn("UNKNOWN_BLOCKED",self.doc)

    def test_03_support_answer_explicitly_limits_classic_message_idempotency(self):
        self.assertIn("não oferece tokens de idempotência",self.doc)
        self.assertIn("declaração do atendimento",self.doc)

    def test_04_official_message_endpoint_and_history_links_present(self):
        self.assertIn("https://www.twilio.com/docs/messaging/api/message-resource",self.doc)
        self.assertIn("DateSent",self.doc)
        self.assertIn("next_page_uri",self.doc)

    def test_05_empty_history_is_not_no_effect_receipt(self):
        self.assertIn("resultado vazio",self.doc)
        self.assertIn("não elimina",self.doc)
        self.assertIn("404",self.doc)

    def test_06_scheduling_cancellation_does_not_fence_an_immediate_message(self):
        self.assertIn("https://www.twilio.com/docs/messaging/features/message-scheduling",self.doc)
        self.assertIn("queued",self.doc)
        self.assertIn("agendada",self.doc)

    def test_07_distinguish_other_twilio_idempotency_endpoint(self):
        self.assertIn("https://www.twilio.com/docs/conversations/orchestrator/concepts/async-operations",self.doc)
        self.assertIn("não",self.doc)

    def test_08_do_not_confuse_sent_with_device_delivery(self):
        self.assertIn("https://www.twilio.com/docs/messaging/guides/outbound-message-status-in-status-callbacks",self.doc)
        self.assertIn("upstream",self.doc)
        self.assertIn("destinatário",self.doc)

    def test_09_non_enrolled_producer_denies_before_adapter_send_property(self):
        deny=self.dispatch.index('raise PermissionError("INDEPENDENT_PRODUCER_NOT_ENROLLED")')
        descriptor=self.dispatch.index('getattr(adapter, "send", None)')
        self.assertLess(deny,descriptor)

    def test_10_reconcile_denies_before_adapter_reconcile_property(self):
        deny=self.reconcile.index('raise PermissionError("INDEPENDENT_PRODUCER_NOT_ENROLLED")')
        descriptor=self.reconcile.index('getattr(adapter, "reconcile", None)')
        self.assertLess(deny,descriptor)

    def test_11_private_confirm_cannot_approve_callback_boolean(self):
        self.assertIn('raise PermissionError("INDEPENDENT_PRODUCER_RECEIPT_NOT_ENROLLED")',self.confirm)

    def test_12_actual_first_claim_local_fifo_still_restricts_ordinal_one(self):
        self.assertIn("AND d.aggregate_seq=1",self.claim)

    def test_13_expired_pre_dispatch_lease_cannot_contain_send_marker(self):
        for token in ("AND dispatch_started_at=''", "AND sent_at=''",
                      "AND confirmed_at=''", "AND effect_ref=''"):
            self.assertIn(token,self.reclaim)

    def test_14_docs_require_real_provider_proof_and_owner_before_homologation(self):
        self.assertIn("autorização HUMAN_OWNER",self.doc)
        self.assertIn("ensaio físico",self.doc)
        self.assertIn("0/6 P0",self.doc)


if __name__=="__main__":
    unittest.main()
