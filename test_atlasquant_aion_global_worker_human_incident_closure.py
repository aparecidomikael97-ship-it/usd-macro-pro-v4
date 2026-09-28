import unittest
from datetime import datetime, timezone
from pathlib import Path

from atlasquant_aion_global_worker_human_incident_closure import (
    CONFIRMATION_PHRASE,
    human_closure_summary,
    prepare_human_incident_closure,
    record_human_incident_closure,
)


NOW = datetime(2026, 9, 28, 18, 0, tzinfo=timezone.utc)


def _assessment(**extra):
    base = {
        "status": "CLOSURE_REVIEW_READY",
        "closure_review_ready": True,
        "closure_package_digest": "c" * 64,
        "incident_evidence_digest": "i" * 64,
        "remediation_digest": "r" * 64,
        "assessed_at": "2026-09-28T17:50:00+00:00",
        "incident_closed": False,
        "automatic_closure": False,
        "human_closure_required": True,
        "reactivation_authorized": False,
    }
    base.update(extra)
    return base


class HumanIncidentClosureCeremonyTests(unittest.TestCase):
    def test_prepare_requires_closure_review_ready(self):
        result = prepare_human_incident_closure(
            _assessment(
                status="CLOSURE_BLOCKED",
                closure_review_ready=False,
            ),
            now=NOW,
        )
        self.assertEqual(result["status"], "CLOSURE_NOT_READY")
        self.assertFalse(result["ceremony_ready"])
        self.assertFalse(result["human_closure_decision_recorded"])

    def test_prepare_requires_bound_evidence(self):
        result = prepare_human_incident_closure(
            _assessment(closure_package_digest=""),
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "BOUND_CLOSURE_EVIDENCE_REQUIRED")

    def test_prepare_is_session_only_and_no_authority(self):
        result = prepare_human_incident_closure(_assessment(), now=NOW)
        self.assertEqual(result["status"], "CEREMONY_READY")
        self.assertTrue(result["ceremony_ready"])
        self.assertFalse(result["persistent"])
        self.assertTrue(result["session_only"])
        self.assertFalse(result["authoritative_incident_closed"])
        self.assertFalse(result["reactivation_authorized"])
        self.assertFalse(result["executes_action"])

    def test_all_acknowledgements_are_required(self):
        result = record_human_incident_closure(
            _assessment(),
            human_confirmation=True,
            evidence_acknowledged=True,
            reactivation_separation_acknowledged=False,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=NOW,
        )
        self.assertEqual(result["status"], "CONFIRMATION_REQUIRED")
        self.assertEqual(
            result["reason"],
            "ALL_HUMAN_ACKNOWLEDGEMENTS_REQUIRED",
        )
        self.assertFalse(result["human_closure_decision_recorded"])

    def test_exact_phrase_is_required(self):
        result = record_human_incident_closure(
            _assessment(),
            human_confirmation=True,
            evidence_acknowledged=True,
            reactivation_separation_acknowledged=True,
            confirmation_phrase="vamos la",
            now=NOW,
        )
        self.assertEqual(result["status"], "CONFIRMATION_REQUIRED")
        self.assertEqual(
            result["reason"],
            "EXACT_HUMAN_CLOSURE_CONFIRMATION_REQUIRED",
        )
        self.assertFalse(result["human_closure_decision_recorded"])

    def test_valid_ceremony_records_human_decision_only(self):
        result = record_human_incident_closure(
            _assessment(),
            human_confirmation=True,
            evidence_acknowledged=True,
            reactivation_separation_acknowledged=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            operator_note="Evidência revisada pelo ADMIN.",
            now=NOW,
        )
        self.assertEqual(
            result["status"],
            "HUMAN_CLOSURE_DECISION_RECORDED_SESSION_ONLY",
        )
        self.assertTrue(result["human_closure_decision_recorded"])
        self.assertEqual(result["human_closure_decision"], "APPROVED")
        self.assertTrue(result["closure_record_id"].startswith("GW-CLOSE-"))
        self.assertTrue(result["closure_record_digest"])
        self.assertFalse(result["authoritative_incident_closed"])
        self.assertFalse(result["shared_incident_record_modified"])
        self.assertFalse(result["persistent"])
        self.assertTrue(result["session_only"])
        self.assertFalse(result["reactivation_authorized"])
        self.assertTrue(result["reactivation_separate_ceremony_required"])
        self.assertFalse(result["feature_flag_modified"])
        self.assertFalse(result["runtime_modified"])
        self.assertFalse(result["real_trading_enabled"])
        self.assertFalse(result["executes_action"])

    def test_closure_does_not_authorize_reactivation(self):
        result = record_human_incident_closure(
            _assessment(),
            human_confirmation=True,
            evidence_acknowledged=True,
            reactivation_separation_acknowledged=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=NOW,
        )
        self.assertFalse(result["reactivation_authorized"])
        self.assertTrue(result["reactivation_separate_ceremony_required"])
        self.assertFalse(result["global_worker_tick_executed"])

    def test_ceremony_digest_is_deterministic(self):
        first = prepare_human_incident_closure(_assessment(), now=NOW)
        second = prepare_human_incident_closure(_assessment(), now=NOW)
        self.assertEqual(first["ceremony_digest"], second["ceremony_digest"])

    def test_record_digest_is_deterministic_for_same_inputs_and_time(self):
        kwargs = dict(
            human_confirmation=True,
            evidence_acknowledged=True,
            reactivation_separation_acknowledged=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            operator_note="reviewed",
            now=NOW,
        )
        first = record_human_incident_closure(_assessment(), **kwargs)
        second = record_human_incident_closure(_assessment(), **kwargs)
        self.assertEqual(
            first["closure_record_digest"],
            second["closure_record_digest"],
        )

    def test_summary_never_claims_authoritative_closure(self):
        record = record_human_incident_closure(
            _assessment(),
            human_confirmation=True,
            evidence_acknowledged=True,
            reactivation_separation_acknowledged=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=NOW,
        )
        summary = human_closure_summary(record)
        self.assertTrue(summary["human_closure_decision_recorded"])
        self.assertFalse(summary["authoritative_incident_closed"])
        self.assertFalse(summary["persistent"])
        self.assertFalse(summary["reactivation_authorized"])
        self.assertFalse(summary["real_trading_enabled"])

    def test_admin_ui_exposes_human_closure_truth_boundary(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Cerimônia humana de fechamento do incidente", source)
        self.assertIn("ENCERRAR INCIDENTE WORKER GLOBAL", source)
        self.assertIn("decisão humana registrada", source)
        self.assertIn("fechamento autoritativo persistido: NÃO", source)
        self.assertIn("reativação autorizada: NÃO", source)

    def test_module_has_no_mutation_apis(self):
        source = Path(
            "atlasquant_aion_global_worker_human_incident_closure.py"
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
