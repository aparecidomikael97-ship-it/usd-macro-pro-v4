import unittest
from pathlib import Path

from atlasquant_aion_global_worker_supervision import (
    append_supervision_history,
    operational_incident,
    supervise_global_worker,
    supervision_history_summary,
)


def _flag(state="ENABLED"):
    return {
        "status": "CONFIRMED",
        "state": state,
        "raw_value_exposed": False,
    }


def _live(status, **extra):
    base = {
        "status": status,
        "reason": "",
        "live_confirmed": status in {
            "LIVE_CONFIRMED_IDLE",
            "LIVE_CONFIRMED_WITH_WORK",
        },
        "heartbeat_confirmed": status not in {
            "NOT_ENABLED",
            "AWAITING_LIVE_EVIDENCE",
            "LIVE_EVIDENCE_TIMEOUT",
        },
        "tick_confirmed": status in {
            "LIVE_CONFIRMED_IDLE",
            "LIVE_CONFIRMED_WITH_WORK",
        },
        "work_receipt_confirmed": status == "LIVE_CONFIRMED_WITH_WORK",
        "unsafe_receipts_after_activation": 0,
        "stale_lease": False,
        "inflight_reconciliation_required": False,
        "inflight_owner": "",
        "inflight_fencing_token": 0,
        "inflight_since": "",
        "last_runtime_id": "gha-123-1",
        "last_heartbeat_at": "2026-09-28T16:30:00+00:00",
        "last_tick_at": "2026-09-28T16:30:00+00:00",
    }
    base.update(extra)
    return base


class GlobalWorkerOperationalSupervisionTests(unittest.TestCase):
    def test_disabled_flag_forces_safe_standby_for_stale_healthy_ui(self):
        report = supervise_global_worker(
            _live("LIVE_CONFIRMED_IDLE"),
            _flag("DISABLED"),
        )
        self.assertEqual(report["posture"], "STANDBY_SAFE")
        self.assertEqual(report["live_status"], "NOT_ENABLED")
        self.assertFalse(report["incident_open"])
        self.assertFalse(report["safety_stop_recommended"])

    def test_live_idle_is_healthy(self):
        report = supervise_global_worker(
            _live("LIVE_CONFIRMED_IDLE"),
            _flag(),
        )
        self.assertEqual(report["posture"], "HEALTHY_LIVE_IDLE")
        self.assertEqual(report["severity"], "INFO")
        self.assertFalse(report["incident_open"])
        self.assertFalse(report["safety_stop_recommended"])
        self.assertFalse(report["real_trading_enabled"])

    def test_live_work_is_healthy(self):
        report = supervise_global_worker(
            _live("LIVE_CONFIRMED_WITH_WORK"),
            _flag(),
        )
        self.assertEqual(report["posture"], "HEALTHY_LIVE_WORK")
        self.assertFalse(report["incident_open"])
        self.assertTrue(report["evidence"]["work_receipt_confirmed"])

    def test_pending_is_low_severity_without_stop_recommendation(self):
        report = supervise_global_worker(
            _live("AWAITING_LIVE_EVIDENCE"),
            _flag(),
        )
        self.assertEqual(report["posture"], "ACTIVATION_PENDING")
        self.assertEqual(report["severity"], "LOW")
        self.assertFalse(report["incident_open"])
        self.assertFalse(report["safety_stop_recommended"])

    def test_heartbeat_only_is_pending_not_live(self):
        report = supervise_global_worker(
            _live(
                "LIVE_HEARTBEAT_CONFIRMED_AWAITING_TICK",
                live_confirmed=False,
                tick_confirmed=False,
            ),
            _flag(),
        )
        self.assertEqual(report["posture"], "ACTIVATION_PENDING")
        self.assertFalse(report["incident_open"])
        self.assertFalse(report["evidence"]["tick_confirmed"])

    def test_timeout_is_high_incident_and_recommends_manual_stop(self):
        report = supervise_global_worker(
            _live(
                "LIVE_EVIDENCE_TIMEOUT",
                reason="NO_SHARED_HEARTBEAT_AFTER_ACTIVATION_TIMEOUT",
                live_confirmed=False,
                heartbeat_confirmed=False,
                tick_confirmed=False,
            ),
            _flag(),
        )
        self.assertEqual(report["posture"], "INCIDENT_LIVE_TIMEOUT")
        self.assertEqual(report["severity"], "HIGH")
        self.assertTrue(report["incident_open"])
        self.assertTrue(report["safety_stop_recommended"])
        self.assertFalse(report["safety_stop_automatic"])
        self.assertTrue(
            any("desativação de segurança" in x for x in report["recovery_steps"])
        )

    def test_stale_lease_is_high_incident(self):
        report = supervise_global_worker(
            _live(
                "BLOCKED_STALE_LEASE",
                reason="GLOBAL_WORKER_LEASE_EXPIRED_WITH_OWNER",
                stale_lease=True,
                live_confirmed=False,
            ),
            _flag(),
        )
        self.assertEqual(report["posture"], "INCIDENT_STALE_LEASE")
        self.assertEqual(report["severity"], "HIGH")
        self.assertTrue(report["incident_open"])
        self.assertTrue(report["safety_stop_recommended"])

    def test_inflight_reconciliation_is_high_incident_without_auto_retry(self):
        report = supervise_global_worker(
            _live(
                "BLOCKED_INFLIGHT_RECONCILIATION",
                reason="GLOBAL_WORKER_INFLIGHT_TICK_REQUIRES_RECONCILIATION",
                live_confirmed=False,
                inflight_reconciliation_required=True,
                inflight_owner="gha-crashed",
                inflight_fencing_token=7,
                inflight_since="2026-09-28T16:25:00+00:00",
            ),
            _flag(),
        )
        self.assertEqual(report["posture"], "INCIDENT_INFLIGHT_RECONCILIATION")
        self.assertEqual(report["severity"], "HIGH")
        self.assertTrue(report["incident_open"])
        self.assertTrue(report["safety_stop_recommended"])
        self.assertFalse(report["safety_stop_automatic"])
        self.assertTrue(report["evidence"]["inflight_reconciliation_required"])
        self.assertEqual(report["evidence"]["inflight_owner"], "gha-crashed")
        self.assertEqual(report["evidence"]["inflight_fencing_token"], 7)
        self.assertTrue(any("retry automático" in x for x in report["recovery_steps"]))
        self.assertFalse(report["automatic_containment"])

    def test_unsafe_receipt_is_critical(self):
        report = supervise_global_worker(
            _live(
                "BLOCKED_UNSAFE_RECEIPT",
                reason="GLOBAL_WORKER_RECEIPT_REPORTED_EXTERNAL_OR_TRADING_EFFECT",
                unsafe_receipts_after_activation=1,
                live_confirmed=False,
            ),
            _flag(),
        )
        self.assertEqual(report["posture"], "INCIDENT_UNSAFE_RECEIPT")
        self.assertEqual(report["severity"], "CRITICAL")
        self.assertTrue(report["incident_open"])
        self.assertTrue(report["safety_stop_recommended"])
        self.assertEqual(report["evidence"]["unsafe_receipts"], 1)

    def test_disabled_flag_does_not_erase_existing_unsafe_incident(self):
        report = supervise_global_worker(
            _live(
                "BLOCKED_UNSAFE_RECEIPT",
                reason="unsafe",
                unsafe_receipts_after_activation=1,
                live_confirmed=False,
            ),
            _flag("DISABLED"),
        )
        self.assertEqual(report["posture"], "INCIDENT_UNSAFE_RECEIPT")
        self.assertTrue(report["incident_open"])
        self.assertFalse(report["safety_stop_recommended"])

    def test_generic_blocked_is_high_and_manual_review(self):
        report = supervise_global_worker(
            _live("BLOCKED", reason="evidence invalid", live_confirmed=False),
            _flag(),
        )
        self.assertEqual(report["posture"], "INCIDENT_VERIFICATION_BLOCKED")
        self.assertEqual(report["severity"], "HIGH")
        self.assertTrue(report["requires_human_review"])
        self.assertFalse(report["automatic_containment"])

    def test_incident_proposal_is_read_only(self):
        supervision = supervise_global_worker(
            _live(
                "LIVE_EVIDENCE_TIMEOUT",
                reason="timeout",
                live_confirmed=False,
            ),
            _flag(),
        )
        result = operational_incident(supervision)
        self.assertEqual(result["status"], "INCIDENT_PROPOSED")
        incident = result["incident"]
        self.assertEqual(incident["severity"], "HIGH")
        self.assertTrue(incident["safety_stop_recommended"])
        self.assertFalse(incident["automatic_containment"])
        self.assertFalse(incident["automatic_rollback"])
        self.assertFalse(incident["real_orders_enabled"])
        self.assertFalse(result["executes_action"])

    def test_healthy_state_does_not_propose_incident(self):
        supervision = supervise_global_worker(
            _live("LIVE_CONFIRMED_IDLE"),
            _flag(),
        )
        result = operational_incident(supervision)
        self.assertEqual(result["status"], "NO_INCIDENT")
        self.assertIsNone(result["incident"])

    def test_evidence_digest_is_deterministic(self):
        first = supervise_global_worker(
            _live("LIVE_CONFIRMED_IDLE"),
            _flag(),
        )
        second = supervise_global_worker(
            _live("LIVE_CONFIRMED_IDLE"),
            _flag(),
        )
        self.assertEqual(
            first["evidence_digest"],
            second["evidence_digest"],
        )

    def test_admin_ui_exposes_supervision_without_auto_containment(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Supervisão operacional", source)
        self.assertIn("Safety-stop recomendado", source)
        self.assertIn("Checklist de recuperação do Worker Global", source)
        self.assertIn("contenção automática: NÃO", source)
        self.assertIn("alteração automática da feature flag: NÃO", source)


    def test_history_is_deduplicated_and_bounded(self):
        first = supervise_global_worker(
            _live("LIVE_EVIDENCE_TIMEOUT", reason="timeout", live_confirmed=False),
            _flag(),
        )
        history = append_supervision_history([], first, max_entries=2)
        history = append_supervision_history(history, first, max_entries=2)
        self.assertEqual(len(history), 1)

        second = supervise_global_worker(
            _live("BLOCKED_STALE_LEASE", reason="stale", stale_lease=True),
            _flag(),
        )
        third = supervise_global_worker(
            _live(
                "BLOCKED_UNSAFE_RECEIPT",
                reason="unsafe",
                unsafe_receipts_after_activation=1,
                live_confirmed=False,
            ),
            _flag(),
        )
        history = append_supervision_history(history, second, max_entries=2)
        history = append_supervision_history(history, third, max_entries=2)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[-1]["severity"], "CRITICAL")
        self.assertFalse(history[-1]["automatic_feature_flag_mutation"])

    def test_history_summary_is_session_only(self):
        report = supervise_global_worker(
            _live("BLOCKED_UNSAFE_RECEIPT", reason="unsafe", live_confirmed=False),
            _flag(),
        )
        history = append_supervision_history([], report)
        summary = supervision_history_summary(history)
        self.assertEqual(summary["observations"], 1)
        self.assertEqual(summary["incidents"], 1)
        self.assertEqual(summary["critical_incidents"], 1)
        self.assertFalse(summary["persistent"])
        self.assertFalse(summary["feature_flag_modified"])

    def test_admin_ui_exposes_supervision_history_without_auto_containment(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Histórico de supervisão do Worker Global", source)
        self.assertIn("append_supervision_history", source)
        self.assertIn("contenção automática: NÃO", source)
        self.assertIn("alteração automática da feature flag: NÃO", source)

    def test_supervisor_has_no_mutation_apis(self):
        source = Path(
            "atlasquant_aion_global_worker_supervision.py"
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
            "subprocess.",
            "os.system(",
        ):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
