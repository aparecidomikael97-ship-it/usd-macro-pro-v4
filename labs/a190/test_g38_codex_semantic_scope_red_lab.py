"""G38 Codex audit -> real ExecutionOutbox semantic identity RED/controls.

Staging only; synthetic amounts, actors, no provider or worker.
RED = reproduced local contract gap, NOT duplicate external effect.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.privacy import redact
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_execution_outbox import ExecutionOutbox
from g13_signed_semantic_outbox_bridge_lab import semantic_operation_digest

NOW = datetime(2026,10,24,20,tzinfo=timezone.utc)
SCOPE = Scope("g38-owner","g38-tenant","g38-workspace")
PAYLOAD = {"business_event_id":"synthetic-event-42","amount_minor":1000}


class G38SemanticRED(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="aion-g38-semantic-")
        self.addCleanup(tmp.cleanup)
        self.store=SQLiteChatStore(Path(tmp.name)/"outbox.sqlite3")
        self.addCleanup(self.store.close)
        self.outbox=ExecutionOutbox(self.store,SCOPE)

    def stage(self, outbox=None, **kwargs):
        options=dict(intent_ref="request-A",action="synthetic_no_provider",
            payload=PAYLOAD,aggregate_key="synthetic-invoice-group",
            policy_version="policy-v1",authorization_ref="auth-v1",
            created_at=NOW,valid_until=NOW+timedelta(minutes=5))
        options.update(kwargs)
        # G57: fixtures with an explicitly declared business event must bind
        # it to the tenant-wide semantic reservation. The old bypass RED is
        # retained in Git history; do not reproduce unsafe admissions here.
        raw=options.get("payload") or {}
        if "business_event_id" in raw:
            options["semantic_event_id_lab"]=raw["business_event_id"]
        return (outbox or self.outbox).enqueue(**options)

    def digest(self, scope, payload):
        return semantic_operation_digest(scope,
            business_event_id="synthetic-event-42",
            action="synthetic_no_provider",
            aggregate_key="synthetic-invoice-group",
            payload=payload)

    def test_01_same_request_id_is_idempotent(self):
        a,b=self.stage(),self.stage()
        self.assertEqual(a["idempotency_key"],b["idempotency_key"])
        self.assertEqual(b["enqueue_state"],"IDEMPOTENT")
        self.assertEqual(len(self.outbox.list()),1)

    def test_02_different_requests_same_business_event_denied_g57(self):
        a=self.stage(intent_ref="request-A")
        with self.assertRaisesRegex(ValueError,"semantic business event collision"):
            self.stage(intent_ref="request-B")
        self.assertEqual(len(self.outbox.list()),1)
        print("G57_G38_REQUEST_ALIAS_GREEN=SECOND_LOCAL_ROW_DENIED")

    def test_03_same_business_event_in_other_workspace_denied_g57(self):
        self.stage()
        alternate=Scope(SCOPE.owner_id,SCOPE.tenant_id,"g38-other-workspace")
        foreign=ExecutionOutbox(self.store,alternate)
        with self.assertRaisesRegex(ValueError,"semantic business event collision"):
            self.stage(outbox=foreign)
        self.assertEqual(len(foreign.list()),0)
        self.assertEqual(len(self.outbox.list()),1)
        print("G57_G38_WORKSPACE_ALIAS_GREEN=CROSS_WORKSPACE_DENIED")

    def test_04_g13_semantic_digest_same_across_workspace_red(self):
        alternate=Scope(SCOPE.owner_id,SCOPE.tenant_id,"g38-other-workspace")
        self.assertEqual(self.digest(SCOPE,PAYLOAD),self.digest(alternate,PAYLOAD))
        print("G38_SCOPE_MISMATCH_RED=BRIDGE_DIGEST_SHARED_OUTBOX_KEYS_DIFFER")

    def test_05_redacted_token_content_collapses_digest_red(self):
        p1={"business_event_id":"synthetic-event-42","token":"synthetic-alpha"}
        p2={"business_event_id":"synthetic-event-42","token":"synthetic-bravo"}
        self.assertNotEqual(p1,p2)
        self.assertEqual(redact(p1),redact(p2))
        self.assertEqual(self.digest(SCOPE,p1),self.digest(SCOPE,p2))
        print("G38_REDACTED_DIGEST_RED=DIFFERENT_RAW_PAYLOADS_SAME_PROJECTED_ID")

    def test_06_redacted_token_content_collapses_outbox_key(self):
        a=self.stage(payload={"token":"synthetic-alpha"})
        b=self.stage(payload={"token":"synthetic-bravo"})
        self.assertEqual(a["idempotency_key"],b["idempotency_key"])
        self.assertEqual(b["enqueue_state"],"IDEMPOTENT")
        self.assertEqual(len(self.outbox.list()),1)

    def test_07_nonredacted_business_amount_change_is_blocked(self):
        self.stage()
        # Tenant-wide event collision is checked before intent-ref collision.
        with self.assertRaisesRegex(ValueError,"semantic business event collision"):
            self.stage(payload={"business_event_id":"synthetic-event-42","amount_minor":2000})

    def test_08_nonredacted_business_event_change_same_request_denies(self):
        self.stage()
        with self.assertRaisesRegex(ValueError,"idempotency collision"):
            self.stage(payload={"business_event_id":"synthetic-event-43","amount_minor":1000})

    def test_09_redaction_must_not_be_mistaken_for_sha_collision(self):
        p1={"token":"synthetic-alpha","amount_minor":1000}
        p2={"token":"synthetic-bravo","amount_minor":1000}
        self.assertEqual(redact(p1),redact(p2))
        p3={"token":"synthetic-bravo","amount_minor":2000}
        self.assertNotEqual(redact(p1),redact(p3))

    def test_10_changed_authorization_metadata_returns_stored_decision_red(self):
        self.stage()
        replay=self.stage(authorization_ref="auth-v2")
        self.assertEqual(replay["enqueue_state"],"IDEMPOTENT")
        self.assertEqual(replay["decision"]["authorization_ref"],"auth-v1")
        print("G38_REPLAY_AUTH_RED=OLD_AUTH_DECISION_REPRESENTED_AS_IDEMPOTENT")

    def test_11_scope_isolation_requires_semantic_reservation(self):
        self.stage()
        alternate=Scope(SCOPE.owner_id,SCOPE.tenant_id,"g38-workspace-2")
        other=ExecutionOutbox(self.store,alternate)
        with self.assertRaisesRegex(ValueError,"semantic business event collision"):
            self.stage(outbox=other)
        self.assertEqual(self.outbox.effect_count(),0)
        self.assertEqual(other.effect_count(),0)
        self.assertEqual(len(self.outbox.list())+len(other.list()),1)

    def test_12_staging_never_transmits(self):
        for name in ("request-A","request-B","request-C"):
            self.stage(intent_ref=name,payload={
                "business_event_id":"synthetic-event-"+name,
                "amount_minor":1000,
            })
        self.assertEqual(self.outbox.effect_count(),0)
        self.assertEqual(len(self.outbox.list()),3)
        self.assertTrue(all(not row["executes_action"] for row in self.outbox.list()))


if __name__=="__main__":
    unittest.main()
