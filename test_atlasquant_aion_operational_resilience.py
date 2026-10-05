from __future__ import annotations
import unittest

from atlasquant_aion_operational_resilience import (
    disaster_recovery_runbook,
    evaluate_operational_resilience,
    normalize_resilience_policy,
)

SCOPE = {"owner_id": "owner-a", "tenant_id": "tenant-a", "workspace_id": "ws-a"}
CHECKED = "2026-10-05T12:30:00Z"
DIGEST = "a" * 64


def policy(**overrides):
    row = {
        "state": "VERIFIED",
        "policy_id": "ops-v1",
        "revision": 1,
        **SCOPE,
        "availability_slo_pct": 99.0,
        "max_error_budget_burn_pct": 80.0,
        "rpo_seconds": 300,
        "rto_seconds": 900,
        "max_drill_age_seconds": 86400,
        "max_heartbeat_age_seconds": 120,
        "min_successful_drills": 1,
        "required_components": ["checkpoint", "durable_tasks", "journal"],
    }
    row.update(overrides)
    return row


def services():
    return [
        {
            **SCOPE,
            "component": name,
            "state": "HEALTHY",
            "availability_pct": 99.9,
            "error_budget_burn_pct": 10,
            "heartbeat_at": "2026-10-05T12:29:30Z",
            "evidence_refs": [f"health:{name}"],
        }
        for name in ("checkpoint", "durable_tasks", "journal")
    ]


def backups(**overrides):
    row = {
        **SCOPE,
        "backup_id": "backup-1",
        "completed_at": "2026-10-05T12:28:00Z",
        "source_revision": "rev-42",
        "source_digest": DIGEST,
        "integrity_state": "VERIFIED",
        "encrypted": True,
        "key_available": True,
        "key_ref": "tenant-key-v2",
        "evidence_refs": ["backup:integrity", "backup:manifest"],
    }
    row.update(overrides)
    return [row]


def drills(**overrides):
    row = {
        **SCOPE,
        "drill_id": "drill-1",
        "backup_id": "backup-1",
        "started_at": "2026-10-05T12:10:00Z",
        "completed_at": "2026-10-05T12:20:00Z",
        "recovered_revision": "rev-42",
        "recovered_digest": DIGEST,
        "integrity_state": "VERIFIED",
        "application_boot_ok": True,
        "health_check_ok": True,
        "production_mutation": False,
        "provider_called": False,
        "external_action_executed": False,
        "evidence_refs": ["drill:restore", "drill:health"],
    }
    row.update(overrides)
    return [row]


def evaluate(**overrides):
    args = {
        "trusted_scope": SCOPE,
        "policy": policy(),
        "service_observations": services(),
        "backups": backups(),
        "recovery_drills": drills(),
        "checked_at": CHECKED,
    }
    args.update(overrides)
    return evaluate_operational_resilience(**args)


class AionOperationalResilienceTests(unittest.TestCase):
    def test_complete_staging_evidence_reaches_admin_review_only(self):
        out = evaluate()
        self.assertEqual(out["state"], "READY_FOR_ADMIN_REVIEW")
        self.assertTrue(out["requires_admin_review"])
        self.assertFalse(out["release_claim_allowed"])
        self.assertFalse(out["recovery_authorized"])
        self.assertFalse(out["production_restore_executed"])
        self.assertFalse(out["executes_action"])

    def test_policy_must_be_verified_scope_bound_and_complete(self):
        crossed = normalize_resilience_policy(
            policy(tenant_id="tenant-b"),
            trusted_scope=SCOPE,
        )
        missing = policy()
        missing.pop("rto_seconds")
        incomplete = normalize_resilience_policy(missing, trusted_scope=SCOPE)
        unverified = normalize_resilience_policy(
            policy(state="DRAFT"),
            trusted_scope=SCOPE,
        )
        self.assertIn("POLICY_SCOPE_MISMATCH", crossed["blockers"])
        self.assertIn("RTO_POLICY_INVALID", incomplete["blockers"])
        self.assertIn("POLICY_NOT_VERIFIED", unverified["blockers"])

    def test_missing_required_component_blocks(self):
        rows = [row for row in services() if row["component"] != "journal"]
        out = evaluate(service_observations=rows)
        self.assertIn("REQUIRED_COMPONENT_MISSING:journal", out["blockers"])
        self.assertEqual(out["state"], "BLOCKED")

    def test_slo_and_error_budget_breaches_block(self):
        rows = services()
        rows[0]["availability_pct"] = 98.0
        rows[1]["error_budget_burn_pct"] = 81.0
        out = evaluate(service_observations=rows)
        self.assertTrue(any("AVAILABILITY_SLO_BREACH" in x for x in out["blockers"]))
        self.assertTrue(any("ERROR_BUDGET_EXHAUSTED" in x for x in out["blockers"]))

    def test_stale_heartbeat_blocks(self):
        rows = services()
        rows[0]["heartbeat_at"] = "2026-10-05T12:20:00Z"
        out = evaluate(service_observations=rows)
        self.assertTrue(any("HEARTBEAT_STALE" in x for x in out["blockers"]))

    def test_backup_age_beyond_rpo_blocks(self):
        out = evaluate(backups=backups(completed_at="2026-10-05T12:20:00Z"))
        self.assertTrue(any("RPO_BREACH" in x for x in out["blockers"]))

    def test_backup_integrity_encryption_and_key_are_mandatory(self):
        bad = backups(
            integrity_state="UNKNOWN",
            encrypted=False,
            key_available=False,
            key_ref="",
        )
        out = evaluate(backups=bad)
        joined = " ".join(out["blockers"])
        self.assertIn("BACKUP_INTEGRITY_NOT_VERIFIED", joined)
        self.assertIn("BACKUP_ENCRYPTION_REQUIRED", joined)
        self.assertIn("BACKUP_KEY_UNAVAILABLE", joined)
        self.assertIn("BACKUP_KEY_REF_REQUIRED", joined)

    def test_drill_cannot_succeed_against_invalid_backup(self):
        out = evaluate(
            backups=backups(integrity_state="UNKNOWN"),
            recovery_drills=drills(),
        )
        joined = " ".join(out["blockers"])
        self.assertIn("BACKUP_REFERENCE_NOT_READY", joined)
        self.assertEqual(out["successful_drills"], 0)

    def test_restore_duration_beyond_rto_blocks(self):
        out = evaluate(recovery_drills=drills(started_at="2026-10-05T11:50:00Z"))
        self.assertTrue(any("RTO_BREACH" in x for x in out["blockers"]))

    def test_restore_must_recover_exact_backup_revision_and_digest(self):
        out = evaluate(recovery_drills=drills(
            recovered_revision="rev-evil",
            recovered_digest="b" * 64,
        ))
        joined = " ".join(out["blockers"])
        self.assertIn("RECOVERED_REVISION_MISMATCH", joined)
        self.assertIn("RECOVERED_DIGEST_MISMATCH", joined)

    def test_drill_cannot_touch_production_or_external_provider(self):
        out = evaluate(recovery_drills=drills(
            production_mutation=True,
            provider_called=True,
            external_action_executed=True,
        ))
        joined = " ".join(out["blockers"])
        self.assertIn("DRILL_PRODUCTION_MUTATION_FORBIDDEN", joined)
        self.assertIn("DRILL_PROVIDER_CALL_FORBIDDEN", joined)
        self.assertIn("DRILL_EXTERNAL_ACTION_FORBIDDEN", joined)

    def test_textual_booleans_fail_closed(self):
        out = evaluate(recovery_drills=drills(
            application_boot_ok="true",
            health_check_ok=1,
            production_mutation="false",
        ))
        joined = " ".join(out["blockers"])
        self.assertIn("RESTORED_APPLICATION_BOOT_NOT_VERIFIED", joined)
        self.assertIn("RESTORED_HEALTH_NOT_VERIFIED", joined)
        self.assertIn("DRILL_PRODUCTION_MUTATION_FORBIDDEN", joined)

    def test_future_or_invalid_timestamps_fail_closed(self):
        out = evaluate(
            backups=backups(completed_at="2026-10-05T12:31:00Z"),
            recovery_drills=drills(completed_at="not-a-time"),
        )
        joined = " ".join(out["blockers"])
        self.assertIn("BACKUP_TIMESTAMP_INVALID", joined)
        self.assertIn("DRILL_TIMESTAMP_INVALID", joined)

    def test_cross_scope_evidence_never_counts(self):
        rows = services()
        rows[0]["tenant_id"] = "tenant-b"
        out = evaluate(
            service_observations=rows,
            backups=backups(tenant_id="tenant-b"),
            recovery_drills=drills(tenant_id="tenant-b"),
        )
        self.assertTrue(any("SCOPE_MISMATCH" in x for x in out["blockers"]))
        self.assertEqual(out["state"], "BLOCKED")

    def test_missing_evidence_refs_blocks(self):
        rows = services()
        rows[0]["evidence_refs"] = []
        out = evaluate(
            service_observations=rows,
            backups=backups(evidence_refs=[]),
            recovery_drills=drills(evidence_refs=[]),
        )
        joined = " ".join(out["blockers"])
        self.assertIn("SERVICE_EVIDENCE_REQUIRED", joined)
        self.assertIn("BACKUP_EVIDENCE_REQUIRED", joined)
        self.assertIn("DRILL_EVIDENCE_REQUIRED", joined)

    def test_insufficient_successful_drills_blocks(self):
        out = evaluate(
            policy=policy(min_successful_drills=2),
            recovery_drills=drills(),
        )
        self.assertIn("SUCCESSFUL_DRILL_COUNT_INSUFFICIENT", out["blockers"])

    def test_malformed_collections_and_scope_fail_closed_without_exception(self):
        out = evaluate_operational_resilience(
            trusted_scope=["not", "a", "mapping"],
            policy="not-a-policy",
            service_observations="not-a-list",
            backups=123,
            recovery_drills={"not": "a-list"},
            checked_at=CHECKED,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("TRUSTED_SCOPE_REQUIRED", out["blockers"])

    def test_malformed_evidence_collections_are_explicitly_blocked(self):
        out = evaluate(
            service_observations="bad",
            backups="bad",
            recovery_drills="bad",
        )
        self.assertIn("SERVICE_OBSERVATIONS_COLLECTION_INVALID", out["blockers"])
        self.assertIn("BACKUPS_COLLECTION_INVALID", out["blockers"])
        self.assertIn("RECOVERY_DRILLS_COLLECTION_INVALID", out["blockers"])

    def test_runbook_is_plan_only(self):
        ready = evaluate()
        plan = disaster_recovery_runbook(ready)
        self.assertEqual(plan["state"], "PLAN_READY")
        self.assertTrue(plan["requires_human_owner"])
        self.assertTrue(plan["requires_incident_control_gate"])
        self.assertFalse(plan["automatic_restore"])
        self.assertFalse(plan["executes_action"])


if __name__ == "__main__":
    unittest.main()
