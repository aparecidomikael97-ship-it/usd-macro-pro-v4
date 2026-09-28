import unittest
from datetime import datetime, timezone
from pathlib import Path

from atlasquant_aion_global_worker_recovery_drill import (
    CONFIRMATION_PHRASE,
    prepare_global_worker_recovery_drill,
    recovery_drill_summary,
    simulate_global_worker_recovery_drill,
)


NOW = datetime(2026, 9, 28, 17, 30, tzinfo=timezone.utc)


def _supervision(
    posture,
    *,
    severity="HIGH",
    safety_stop=True,
    incident_open=True,
    evidence_digest="abcdef1234567890abcdef1234567890",
):
    return {
        "posture": posture,
        "severity": severity,
        "incident_open": incident_open,
        "evidence_digest": evidence_digest,
        "safety_stop_recommended": safety_stop,
        "automatic_containment": False,
        "automatic_feature_flag_mutation": False,
        "automatic_checkpoint_mutation": False,
        "real_trading_enabled": False,
    }


class GlobalWorkerRecoveryDrillTests(unittest.TestCase):
    def test_timeout_drill_is_ready_and_manual_stop_only(self):
        plan = prepare_global_worker_recovery_drill(
            _supervision("INCIDENT_LIVE_TIMEOUT"),
            now=NOW,
        )
        self.assertEqual(plan["status"], "DRILL_READY")
        self.assertEqual(plan["scenario"], "LIVE_TIMEOUT")
        self.assertTrue(plan["simulation_only"])
        self.assertTrue(plan["safety_stop_recommended"])
        self.assertFalse(plan["executes_action"])
        self.assertTrue(
            any(
                row["stage"] == "MANUAL_SAFETY_STOP"
                and row["expected"] == "ADMIN_CEREMONY_REQUIRED"
                and row["executes_action"] is False
                for row in plan["stages"]
            )
        )

    def test_stale_lease_drill_contains_fencing_diagnostic(self):
        plan = prepare_global_worker_recovery_drill(
            _supervision("INCIDENT_STALE_LEASE"),
            now=NOW,
        )
        self.assertEqual(plan["scenario"], "STALE_LEASE")
        self.assertTrue(
            any(
                "fencing token" in item.lower()
                for item in plan["acceptance_criteria"]
            )
        )
        self.assertTrue(
            any(
                row["expected"] == "REVIEW_LEASE_OWNER_EXPIRY_HEARTBEAT_AND_FENCING"
                for row in plan["stages"]
            )
        )

    def test_unsafe_receipt_drill_is_critical_and_preserves_receipt(self):
        plan = prepare_global_worker_recovery_drill(
            _supervision(
                "INCIDENT_UNSAFE_RECEIPT",
                severity="CRITICAL",
            ),
            now=NOW,
        )
        self.assertEqual(plan["scenario"], "UNSAFE_RECEIPT")
        self.assertEqual(plan["severity"], "CRITICAL")
        self.assertTrue(
            any(
                "receipt inseguro" in item.lower()
                for item in plan["acceptance_criteria"]
            )
        )
        self.assertFalse(plan["automatic_containment"])

    def test_generic_blocked_drill_does_not_require_automatic_stop(self):
        plan = prepare_global_worker_recovery_drill(
            _supervision(
                "INCIDENT_VERIFICATION_BLOCKED",
                safety_stop=False,
            ),
            now=NOW,
        )
        self.assertEqual(plan["scenario"], "VERIFICATION_BLOCKED")
        self.assertFalse(plan["safety_stop_recommended"])
        self.assertTrue(
            any(
                row["stage"] == "CONFIRM_SAFE_FLAG_POSTURE"
                for row in plan["stages"]
            )
        )

    def test_healthy_or_closed_report_does_not_create_drill(self):
        healthy = prepare_global_worker_recovery_drill(
            _supervision(
                "HEALTHY_LIVE_IDLE",
                severity="INFO",
                safety_stop=False,
                incident_open=False,
            ),
            now=NOW,
        )
        self.assertEqual(healthy["status"], "NO_DRILL_REQUIRED")
        self.assertFalse(healthy["executes_action"])

    def test_missing_evidence_digest_blocks_drill(self):
        result = prepare_global_worker_recovery_drill(
            _supervision(
                "INCIDENT_LIVE_TIMEOUT",
                evidence_digest="",
            ),
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "SUPERVISION_EVIDENCE_DIGEST_REQUIRED")

    def test_exact_confirmation_phrase_is_required(self):
        report = _supervision("INCIDENT_LIVE_TIMEOUT")
        result = simulate_global_worker_recovery_drill(
            report,
            confirmation=True,
            confirmation_phrase="vamos la",
            now=NOW,
        )
        self.assertEqual(result["status"], "CONFIRMATION_REQUIRED")
        self.assertFalse(result["drill_completed"])

    def test_simulation_completes_without_real_containment(self):
        report = _supervision("INCIDENT_UNSAFE_RECEIPT", severity="CRITICAL")
        result = simulate_global_worker_recovery_drill(
            report,
            confirmation=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=NOW,
        )
        self.assertEqual(result["status"], "DRILL_COMPLETED_SIMULATION_ONLY")
        self.assertTrue(result["drill_completed"])
        self.assertTrue(result["simulation_only"])
        self.assertFalse(result["real_incident_contained"])
        self.assertFalse(result["real_recovery_confirmed"])
        self.assertFalse(result["reactivation_authorized"])
        self.assertFalse(result["feature_flag_modified"])
        self.assertFalse(result["runtime_modified"])
        self.assertFalse(result["executes_action"])

    def test_all_stages_are_simulation_only(self):
        plan = prepare_global_worker_recovery_drill(
            _supervision("INCIDENT_STALE_LEASE"),
            now=NOW,
        )
        self.assertGreaterEqual(len(plan["stages"]), 5)
        for stage in plan["stages"]:
            self.assertEqual(stage["mode"], "SIMULATION")
            self.assertFalse(stage["executes_action"])

    def test_plan_digest_is_deterministic(self):
        first = prepare_global_worker_recovery_drill(
            _supervision("INCIDENT_LIVE_TIMEOUT"),
            now=NOW,
        )
        second = prepare_global_worker_recovery_drill(
            _supervision("INCIDENT_LIVE_TIMEOUT"),
            now=NOW,
        )
        self.assertEqual(first["plan_digest"], second["plan_digest"])

    def test_summary_never_claims_real_recovery(self):
        result = simulate_global_worker_recovery_drill(
            _supervision("INCIDENT_LIVE_TIMEOUT"),
            confirmation=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=NOW,
        )
        summary = recovery_drill_summary(result)
        self.assertTrue(summary["drill_completed"])
        self.assertTrue(summary["simulation_only"])
        self.assertFalse(summary["real_incident_contained"])
        self.assertFalse(summary["real_recovery_confirmed"])
        self.assertFalse(summary["reactivation_authorized"])
        self.assertFalse(summary["real_trading_enabled"])

    def test_admin_ui_marks_drill_as_simulation_only(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Drill de recuperação do Worker Global", source)
        self.assertIn("SIMULAÇÃO SOMENTE", source)
        self.assertIn("SIMULAR RECUPERACAO WORKER GLOBAL", source)
        self.assertIn("recuperação real: NÃO", source)
        self.assertIn("reativação autorizada: NÃO", source)

    def test_recovery_drill_has_no_mutation_apis(self):
        source = Path(
            "atlasquant_aion_global_worker_recovery_drill.py"
        ).read_text(encoding="utf-8")
        for banned in (
            "requests.put(",
            "requests.post(",
            "requests.patch(",
            "requests.delete(",
            "save_runtime_checkpoint(",
            "activate_global_worker_feature_flag(",
            "deactivate_global_worker_feature_flag(",
            "run_global_worker_once(",
            "worker_tick(",
            "workflow_dispatch",
            "subprocess.",
            "os.system(",
        ):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
