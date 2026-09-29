import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from atlasquant_aion_global_worker_recovery_closure import (
    CONFIRMATION_PHRASE,
    assess_incident_closure_readiness,
    closure_review_record,
    prepare_remediation_evidence,
)


INCIDENT_AT = datetime(2026, 9, 28, 17, 0, tzinfo=timezone.utc)
REVIEWED_AT = INCIDENT_AT + timedelta(minutes=10)
CURRENT_AT = INCIDENT_AT + timedelta(minutes=20)
INCIDENT_DIGEST = "a" * 64


def _supervision(
    posture="INCIDENT_LIVE_TIMEOUT",
    *,
    generated_at=INCIDENT_AT,
    digest=INCIDENT_DIGEST,
):
    return {
        "posture": posture,
        "severity": "CRITICAL" if posture == "INCIDENT_UNSAFE_RECEIPT" else "HIGH",
        "incident_open": True,
        "generated_at": generated_at.isoformat(),
        "evidence_digest": digest,
        "safety_stop_recommended": True,
    }


def _flag(state="DISABLED", *, checked_at=CURRENT_AT):
    return {
        "status": "CONFIRMED",
        "state": state,
        "checked_at": checked_at.isoformat(),
        "updated_at": checked_at.isoformat(),
        "raw_value_exposed": False,
    }


def _live(status="NOT_ENABLED", *, checked_at=CURRENT_AT, **extra):
    base = {
        "status": status,
        "checked_at": checked_at.isoformat(),
        "live_confirmed": status in {
            "LIVE_CONFIRMED_IDLE",
            "LIVE_CONFIRMED_WITH_WORK",
        },
        "heartbeat_confirmed": status in {
            "LIVE_CONFIRMED_IDLE",
            "LIVE_CONFIRMED_WITH_WORK",
        },
        "tick_confirmed": status in {
            "LIVE_CONFIRMED_IDLE",
            "LIVE_CONFIRMED_WITH_WORK",
        },
        "stale_lease": False,
        "inflight_reconciliation_required": False,
        "unsafe_receipts_after_activation": 0,
    }
    base.update(extra)
    return base


def _remediation(supervision, *, now=REVIEWED_AT, phrase=CONFIRMATION_PHRASE, **overrides):
    args = {
        "root_cause_identified": True,
        "corrective_action_verified": True,
        "regression_check_passed": True,
        "evidence_preserved": True,
        "reviewer_confirmed": True,
        "confirmation_phrase": phrase,
        "now": now,
    }
    args.update(overrides)
    return prepare_remediation_evidence(supervision, **args)


class GlobalWorkerRecoveryClosureTests(unittest.TestCase):
    def test_remediation_evidence_is_bound_to_incident_and_session_only(self):
        incident = _supervision()
        result = _remediation(incident)
        self.assertEqual(result["status"], "CONFIRMED")
        self.assertTrue(result["confirmed"])
        self.assertEqual(result["incident_evidence_digest"], INCIDENT_DIGEST)
        self.assertFalse(result["persistent"])
        self.assertTrue(result["session_only"])
        self.assertFalse(result["incident_closed"])
        self.assertFalse(result["automatic_closure"])
        self.assertFalse(result["executes_action"])

    def test_exact_remediation_phrase_is_required(self):
        result = _remediation(
            _supervision(),
            phrase="vamos la",
        )
        self.assertEqual(result["status"], "CONFIRMATION_REQUIRED")
        self.assertEqual(
            result["reason"],
            "EXACT_REMEDIATION_CONFIRMATION_REQUIRED",
        )
        self.assertFalse(result["confirmed"])

    def test_all_remediation_checks_are_required(self):
        result = _remediation(
            _supervision(),
            regression_check_passed=False,
        )
        self.assertEqual(result["status"], "CONFIRMATION_REQUIRED")
        self.assertEqual(result["reason"], "ALL_REMEDIATION_CHECKS_REQUIRED")

    def test_remediation_must_postdate_incident(self):
        result = _remediation(
            _supervision(),
            now=INCIDENT_AT,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["reason"],
            "REMEDIATION_EVIDENCE_MUST_POSTDATE_INCIDENT",
        )

    def test_no_supported_open_incident_means_no_evidence_package(self):
        incident = _supervision()
        incident["incident_open"] = False
        result = _remediation(incident)
        self.assertEqual(result["status"], "NO_OPEN_SUPPORTED_INCIDENT")

    def test_disabled_safe_state_plus_remediation_is_ready_for_human_review(self):
        incident = _supervision("INCIDENT_LIVE_TIMEOUT")
        remediation = _remediation(incident)
        result = assess_incident_closure_readiness(
            incident,
            _live("NOT_ENABLED"),
            _flag("DISABLED"),
            remediation,
            now=CURRENT_AT,
        )
        self.assertEqual(result["status"], "CLOSURE_REVIEW_READY")
        self.assertTrue(result["closure_review_ready"])
        self.assertTrue(result["real_recovery_evidence_confirmed"])
        self.assertFalse(result["real_recovery_confirmed"])
        self.assertFalse(result["incident_closed"])
        self.assertFalse(result["automatic_closure"])
        self.assertTrue(result["human_closure_required"])
        self.assertTrue(result["closure_package_digest"])

    def test_healthy_live_state_can_support_review_after_verified_remediation(self):
        incident = _supervision("INCIDENT_LIVE_TIMEOUT")
        remediation = _remediation(incident)
        result = assess_incident_closure_readiness(
            incident,
            _live("LIVE_CONFIRMED_IDLE"),
            _flag("ENABLED"),
            remediation,
            now=CURRENT_AT,
        )
        self.assertEqual(result["status"], "CLOSURE_REVIEW_READY")
        self.assertTrue(result["current_state"]["healthy_live"])
        self.assertFalse(result["reactivation_authorized"])

    def test_stale_lease_still_present_blocks_closure(self):
        incident = _supervision("INCIDENT_STALE_LEASE")
        remediation = _remediation(incident)
        result = assess_incident_closure_readiness(
            incident,
            _live(
                "LIVE_CONFIRMED_IDLE",
                stale_lease=True,
            ),
            _flag("ENABLED"),
            remediation,
            now=CURRENT_AT,
        )
        self.assertEqual(result["status"], "CLOSURE_BLOCKED")
        self.assertIn("STALE_LEASE_STILL_PRESENT", result["blockers"])
        self.assertFalse(result["closure_review_ready"])

    def test_inflight_incident_requires_reconciliation_before_closure_review(self):
        incident = _supervision("INCIDENT_INFLIGHT_RECONCILIATION")
        remediation = _remediation(incident)
        result = assess_incident_closure_readiness(
            incident,
            _live(
                "BLOCKED_INFLIGHT_RECONCILIATION",
                inflight_reconciliation_required=True,
            ),
            _flag("ENABLED"),
            remediation,
            now=CURRENT_AT,
        )
        self.assertEqual(result["status"], "CLOSURE_BLOCKED")
        self.assertIn(
            "INFLIGHT_RECONCILIATION_STILL_REQUIRED",
            result["blockers"],
        )
        self.assertFalse(result["closure_review_ready"])
        self.assertFalse(result["incident_closed"])
        self.assertFalse(result["automatic_closure"])

    def test_reconciled_inflight_incident_can_become_ready_for_human_review(self):
        incident = _supervision("INCIDENT_INFLIGHT_RECONCILIATION")
        remediation = _remediation(incident)
        result = assess_incident_closure_readiness(
            incident,
            _live(
                "LIVE_CONFIRMED_IDLE",
                inflight_reconciliation_required=False,
            ),
            _flag("ENABLED"),
            remediation,
            now=CURRENT_AT,
        )
        self.assertEqual(result["status"], "CLOSURE_REVIEW_READY")
        self.assertTrue(result["closure_review_ready"])
        self.assertTrue(result["real_recovery_evidence_confirmed"])
        self.assertFalse(result["real_recovery_confirmed"])
        self.assertTrue(result["human_closure_required"])
        self.assertFalse(result["reactivation_authorized"])

    def test_unsafe_receipt_still_present_blocks_closure(self):
        incident = _supervision("INCIDENT_UNSAFE_RECEIPT")
        remediation = _remediation(incident)
        result = assess_incident_closure_readiness(
            incident,
            _live(
                "LIVE_CONFIRMED_WITH_WORK",
                unsafe_receipts_after_activation=1,
            ),
            _flag("ENABLED"),
            remediation,
            now=CURRENT_AT,
        )
        self.assertEqual(result["status"], "CLOSURE_BLOCKED")
        self.assertIn("UNSAFE_RECEIPT_STILL_PRESENT", result["blockers"])

    def test_verification_still_blocked_prevents_closure(self):
        incident = _supervision("INCIDENT_VERIFICATION_BLOCKED")
        remediation = _remediation(incident)
        result = assess_incident_closure_readiness(
            incident,
            _live("BLOCKED"),
            _flag("ENABLED"),
            remediation,
            now=CURRENT_AT,
        )
        self.assertEqual(result["status"], "CLOSURE_BLOCKED")
        self.assertIn("VERIFICATION_STILL_BLOCKED", result["blockers"])

    def test_mismatched_remediation_binding_blocks_closure(self):
        incident = _supervision()
        other = _supervision(digest="b" * 64)
        remediation = _remediation(other)
        result = assess_incident_closure_readiness(
            incident,
            _live("NOT_ENABLED"),
            _flag("DISABLED"),
            remediation,
            now=CURRENT_AT,
        )
        self.assertIn(
            "REMEDIATION_INCIDENT_BINDING_MISMATCH",
            result["blockers"],
        )
        self.assertFalse(result["closure_review_ready"])

    def test_fresh_current_evidence_is_required(self):
        incident = _supervision()
        remediation = _remediation(incident)
        result = assess_incident_closure_readiness(
            incident,
            _live("NOT_ENABLED", checked_at=INCIDENT_AT),
            _flag("DISABLED", checked_at=INCIDENT_AT),
            remediation,
            now=CURRENT_AT,
        )
        self.assertIn("FRESH_CURRENT_EVIDENCE_REQUIRED", result["blockers"])

    def test_safe_disable_without_remediation_is_contained_not_closed(self):
        incident = _supervision()
        result = assess_incident_closure_readiness(
            incident,
            _live("NOT_ENABLED"),
            _flag("DISABLED"),
            {},
            now=CURRENT_AT,
        )
        self.assertEqual(result["status"], "CONTAINED_AWAITING_REMEDIATION")
        self.assertFalse(result["closure_review_ready"])
        self.assertFalse(result["incident_closed"])

    def test_closure_review_record_never_marks_closed(self):
        incident = _supervision()
        remediation = _remediation(incident)
        assessment = assess_incident_closure_readiness(
            incident,
            _live("NOT_ENABLED"),
            _flag("DISABLED"),
            remediation,
            now=CURRENT_AT,
        )
        record = closure_review_record(assessment)
        self.assertEqual(
            record["status"],
            "READY_FOR_HUMAN_CLOSURE_REVIEW",
        )
        self.assertFalse(record["incident_closed"])
        self.assertFalse(record["automatic_closure"])
        self.assertTrue(record["human_closure_required"])
        self.assertFalse(record["persistent"])
        self.assertFalse(record["executes_action"])

    def test_admin_ui_distinguishes_review_ready_from_closed(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Evidência de recuperação / fechamento", source)
        self.assertIn("CONFIRMAR EVIDENCIA DE REMEDIACAO WORKER GLOBAL", source)
        self.assertIn("pronto para revisão humana", source)
        self.assertIn("incidente encerrado automaticamente: NÃO", source)
        self.assertIn("reativação autorizada: NÃO", source)

    def test_closure_module_has_no_mutation_apis(self):
        source = Path(
            "atlasquant_aion_global_worker_recovery_closure.py"
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
