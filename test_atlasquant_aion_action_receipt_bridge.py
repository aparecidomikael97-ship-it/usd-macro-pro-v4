from __future__ import annotations

import unittest

from atlasquant_aion_action_receipt_bridge import seal_executor_receipt_envelope
from atlasquant_aion_core_intelligence.context import Context, Domain


class AionActionReceiptBridgeTests(unittest.TestCase):
    def test_envelope_references_child_without_becoming_authority(self):
        ctx = Context(
            tenant_id="tenant-a",
            workspace_id="administration",
            actor_id="admin",
            task_id="task-1",
            domain=Domain.ADMIN,
            role="ADMIN",
        )
        child = {
            "schema": "AION_CORE_EXECUTION_RECEIPT_V1",
            "receipt_id": "RCPT-1",
            "occurrence_key": "occ-1",
            "schedule_id": "sched-1",
            "state": "SUCCEEDED",
            "capability": "ADMINISTRATION",
            "guardian_action": "read",
            "guardian_allowed": True,
            "authorization_digest": "approval-digest",
            "result_digest": "result-digest",
            "started_at": "2026-09-29T12:00:00+00:00",
            "completed_at": "2026-09-29T12:00:00+00:00",
            "reason": "LOCAL_CORE_HANDLER_COMPLETED",
        }
        out = seal_executor_receipt_envelope(child, context=ctx)
        self.assertEqual(out["child_receipt_id"], "RCPT-1")
        self.assertTrue(out["child_fingerprint"])
        self.assertEqual(out["authorization"], "NONE")
        self.assertFalse(out["executes_action"])
        self.assertFalse(out["external_persisted"])
        self.assertEqual(out["receipt"]["tenant_id"], "tenant-a")
        self.assertEqual(out["receipt"]["workspace_id"], "administration")
        self.assertEqual(out["receipt"]["child_receipts"][0]["receipt_id"], "RCPT-1")

    def test_child_secret_fields_are_not_copied_into_envelope(self):
        ctx = Context(
            tenant_id="tenant-a",
            workspace_id="administration",
            actor_id="admin",
            task_id="task-1",
            domain=Domain.ADMIN,
            role="ADMIN",
        )
        child = {
            "schema": "AION_CORE_EXECUTION_RECEIPT_V1",
            "receipt_id": "RCPT-2",
            "occurrence_key": "occ-2",
            "state": "BLOCKED",
            "capability": "CONTENT",
            "guardian_action": "draft",
            "guardian_allowed": False,
            "authorization_digest": "approval-digest",
            "result_digest": "result-digest",
            "completed_at": "2026-09-29T12:00:00+00:00",
            "reason": "token=example-secret-value",
        }
        out = seal_executor_receipt_envelope(child, context=ctx)
        self.assertNotIn("example-secret-value", str(out["receipt"]))
        self.assertIn("[REDACTED]", out["receipt"]["result"])


if __name__ == "__main__":
    unittest.main()
