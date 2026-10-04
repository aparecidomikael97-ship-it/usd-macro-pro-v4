from __future__ import annotations

import unittest

from atlasquant_aion_durable_tasks import (
    DurableTaskError,
    new_durable_task,
    update_step,
    upsert_durable_task,
)
from atlasquant_aion_observability import core_health_snapshot, sanitize_metadata
from atlasquant_aion_role_authority import authority_for_role, evaluate_role_authority
from atlasquant_aion_unified_runtime import AionResponse


class AtlasQuantAionCoreHardeningV24Tests(unittest.TestCase):
    def test_confusable_or_unknown_role_cannot_gain_authority(self):
        with self.assertRaises(ValueError):
            authority_for_role("\u043erchestrator")  # Cyrillic small o.
        with self.assertRaises(ValueError):
            authority_for_role("admin")

    def test_approval_requires_exact_boolean_true(self):
        waiting = evaluate_role_authority(
            "prime",
            "REQUIRES_APPROVAL",
            explicit_human_approval=1,
        )
        self.assertEqual(waiting["status"], "WAITING_HUMAN_APPROVAL")
        self.assertFalse(waiting["explicit_human_approval"])
        approved = evaluate_role_authority(
            "prime",
            "REQUIRES_APPROVAL",
            explicit_human_approval=True,
        )
        self.assertEqual(
            approved["status"],
            "APPROVAL_PRESENT_EXECUTION_GATE_STILL_REQUIRED",
        )
        self.assertFalse(approved["execution_allowed"])
        self.assertFalse(approved["external_action_executed"])

    def test_stale_durable_writer_is_rejected_at_state_commit_boundary(self):
        base = new_durable_task(
            "Concurrency contract",
            objective="Prove optimistic revision conflict.",
            steps=[{"step_id": "local", "title": "Local read", "guardian_action": "read"}],
            created_at="2026-10-04T02:00:00+00:00",
        )
        revision = base["revision"]
        writer_a = update_step(
            base,
            "local",
            "RUNNING",
            expected_revision=revision,
            access={"role": "ADMIN"},
            approved=True,
            changed_at="2026-10-04T02:01:00+00:00",
        )
        writer_b = update_step(
            base,
            "local",
            "RUNNING",
            expected_revision=revision,
            access={"role": "ADMIN"},
            approved=True,
            changed_at="2026-10-04T02:01:01+00:00",
        )
        persisted = upsert_durable_task([base], writer_a, expected_revision=revision)
        with self.assertRaises(DurableTaskError) as caught:
            upsert_durable_task(persisted, writer_b, expected_revision=revision)
        self.assertEqual(caught.exception.result["error_code"], "REVISION_CONFLICT")

    def test_nested_observability_metadata_redacts_secret_families(self):
        cleaned = sanitize_metadata({
            "safe": {
                "api_key": "secret-a",
                "nested": [{"private_key": "secret-b"}, {"cookie": "secret-c"}],
            },
            "password": "secret-d",
        })
        rendered = repr(cleaned)
        for secret in ("secret-a", "secret-b", "secret-c", "secret-d"):
            self.assertNotIn(secret, rendered)
        self.assertIn("[REDACTED]", rendered)

    def test_health_snapshot_fails_closed_on_unknown_evidence(self):
        snap = core_health_snapshot(core_version="2.2A")
        self.assertEqual(snap["integrity_state"], "UNKNOWN")
        self.assertTrue(snap["health_snapshot_is_read_only"])
        self.assertFalse(snap["external_action_executed"])
        self.assertFalse(snap["execution_allowed"])
        self.assertFalse(snap["executes_provider_call"])
        self.assertFalse(snap["executes_billing"])
        self.assertFalse(snap["real_orders_enabled"])

    def test_health_snapshot_degrades_on_tamper_or_mismatch(self):
        snap = core_health_snapshot(
            core_version="2.2A",
            schema_version="V22",
            journal_status="TAMPER_DETECTED",
            checkpoint_status="VALID",
            recovery_status="RECOVERED",
            memory_status="VALIDATED",
            audit_chain_status="MISMATCH",
            pending_missions=-3,
            blocked_missions=2,
            waiting_approval=1,
            ready_handoffs=4,
        )
        self.assertEqual(snap["integrity_state"], "DEGRADED")
        self.assertEqual(snap["pending_missions"], 0)
        self.assertEqual(snap["blocked_missions"], 2)

    def test_health_snapshot_only_reports_ok_when_every_subsystem_is_explicitly_good(self):
        snap = core_health_snapshot(
            core_version="2.2A",
            schema_version="V22",
            journal_status="VALID",
            checkpoint_status="VALIDATED",
            recovery_status="RECOVERED",
            memory_status="HEALTHY",
            audit_chain_status="VERIFIED",
        )
        self.assertEqual(snap["integrity_state"], "OK")

    def test_runtime_response_security_defaults_remain_fail_closed(self):
        fields = AionResponse.__dataclass_fields__
        self.assertIs(fields["external_action_executed"].default, False)
        self.assertIs(fields["real_orders_enabled"].default, False)


if __name__ == "__main__":
    unittest.main()
