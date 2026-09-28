import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from atlasquant_aion_core_intelligence.evidence import digest
from atlasquant_aion_global_worker_durable_incident_closure import (
    LEDGER_NAMESPACE,
    build_durable_closure_checkpoint,
)
from atlasquant_aion_global_worker_human_incident_closure import (
    CONFIRMATION_PHRASE as HUMAN_CLOSE_PHRASE,
    record_human_incident_closure,
)
from atlasquant_aion_global_worker_incident_reconciliation import (
    closed_incident_rows,
    reconcile_global_worker_incident_center,
)
from atlasquant_aion_global_worker_supervision import supervise_global_worker
from atlasquant_aion_memory import ensure_operating_checkpoint


BASE = datetime(2026, 9, 28, 19, 0, tzinfo=timezone.utc)


def _flag(state="ENABLED"):
    return {
        "status": "CONFIRMED",
        "state": state,
    }


def _live_timeout(*, runtime_id="gha-100"):
    return {
        "status": "LIVE_EVIDENCE_TIMEOUT",
        "reason": "HEARTBEAT_TIMEOUT",
        "live_confirmed": False,
        "heartbeat_confirmed": False,
        "tick_confirmed": False,
        "work_receipt_confirmed": False,
        "unsafe_receipts_after_activation": 0,
        "stale_lease": False,
        "last_runtime_id": runtime_id,
        "last_heartbeat_at": "",
        "last_tick_at": "",
    }


def _unsafe_receipt(*, runtime_id="gha-200"):
    return {
        "status": "BLOCKED_UNSAFE_RECEIPT",
        "reason": "UNSAFE_RECEIPT",
        "live_confirmed": False,
        "heartbeat_confirmed": True,
        "tick_confirmed": True,
        "work_receipt_confirmed": True,
        "unsafe_receipts_after_activation": 1,
        "stale_lease": False,
        "last_runtime_id": runtime_id,
        "last_heartbeat_at": "2026-09-28T18:58:00+00:00",
        "last_tick_at": "2026-09-28T18:59:00+00:00",
    }


def _supervision(live=None, *, now=BASE):
    return supervise_global_worker(
        live or _live_timeout(),
        _flag(),
        now=now,
    )


def _human_record_for(supervision, *, recorded_at):
    assessment = {
        "status": "CLOSURE_REVIEW_READY",
        "closure_review_ready": True,
        "closure_package_digest": "c" * 64,
        "incident_evidence_digest": supervision["evidence_digest"],
        "remediation_digest": "r" * 64,
        "assessed_at": (recorded_at - timedelta(minutes=1)).isoformat(),
        "incident_closed": False,
        "automatic_closure": False,
        "human_closure_required": True,
        "reactivation_authorized": False,
    }
    result = record_human_incident_closure(
        assessment,
        human_confirmation=True,
        evidence_acknowledged=True,
        reactivation_separation_acknowledged=True,
        confirmation_phrase=HUMAN_CLOSE_PHRASE,
        operator_note="Revisado pelo ADMIN.",
        now=recorded_at,
    )
    assert result["status"] == "HUMAN_CLOSURE_DECISION_RECORDED_SESSION_ONLY"
    return result


def _runtime_with_closure(supervision, *, recorded_at, persisted_at):
    cp = ensure_operating_checkpoint({})
    human = _human_record_for(supervision, recorded_at=recorded_at)
    durable = build_durable_closure_checkpoint(
        cp,
        human,
        actor_id="admin-1",
        source_runtime_sha="runtime-sha-1",
        source_runtime_checkpoint_digest="source-digest",
        feature_flag_state="DISABLED",
        now=persisted_at,
    )
    return {
        "status": "CONFIRMED",
        "checkpoint": durable,
        "sha": "runtime-sha-2",
    }


def _empty_snapshot():
    return {
        "schema": "ATLASQUANT_AION_INCIDENT_CENTER_V1",
        "incidents": [],
        "total": 0,
        "counts": {
            "INFO": 0,
            "LOW": 0,
            "MEDIUM": 0,
            "HIGH": 0,
            "CRITICAL": 0,
        },
        "highest_severity": "INFO",
        "has_critical": False,
        "rollback_review_recommended": False,
        "rollback_reasons": [],
        "automatic_containment": False,
        "automatic_rollback": False,
        "real_orders_enabled": False,
        "executes_action": False,
    }


class GlobalWorkerIncidentReconciliationTests(unittest.TestCase):
    def test_open_incident_without_closure_remains_open(self):
        supervision = _supervision(now=BASE)
        result = reconcile_global_worker_incident_center(
            _empty_snapshot(),
            supervision,
            {
                "status": "CONFIRMED",
                "checkpoint": ensure_operating_checkpoint({}),
                "sha": "runtime-sha-1",
            },
            now=BASE,
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["incidents"][0]["status"], "OPEN")
        self.assertEqual(
            result["global_worker_reconciliation"]["state"],
            "OPEN",
        )
        self.assertFalse(
            result["global_worker_reconciliation"]["reactivation_authorized"]
        )

    def test_exact_incident_observed_before_closure_becomes_closed_history(self):
        supervision = _supervision(now=BASE)
        runtime = _runtime_with_closure(
            supervision,
            recorded_at=BASE + timedelta(minutes=5),
            persisted_at=BASE + timedelta(minutes=10),
        )
        result = reconcile_global_worker_incident_center(
            _empty_snapshot(),
            supervision,
            runtime,
            now=BASE + timedelta(minutes=11),
        )
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["closed_total"], 1)
        self.assertEqual(
            result["closed_incidents"][0]["status"],
            "CLOSED_HUMAN_VERIFIED",
        )
        self.assertEqual(
            result["global_worker_reconciliation"]["state"],
            "CLOSED_HISTORY_RECOGNIZED",
        )

    def test_same_evidence_after_closure_is_reopened_not_hidden(self):
        original = _supervision(now=BASE)
        runtime = _runtime_with_closure(
            original,
            recorded_at=BASE + timedelta(minutes=5),
            persisted_at=BASE + timedelta(minutes=10),
        )
        recurrence = _supervision(
            _live_timeout(),
            now=BASE + timedelta(minutes=20),
        )
        self.assertEqual(
            recurrence["evidence_digest"],
            original["evidence_digest"],
        )
        result = reconcile_global_worker_incident_center(
            _empty_snapshot(),
            recurrence,
            runtime,
            now=BASE + timedelta(minutes=20),
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["incidents"][0]["status"], "REOPENED")
        self.assertTrue(result["incidents"][0]["recurrence_detected"])
        self.assertEqual(
            result["global_worker_reconciliation"]["state"],
            "REOPENED",
        )

    def test_new_evidence_after_prior_closure_stays_open(self):
        original = _supervision(_live_timeout(runtime_id="gha-100"), now=BASE)
        runtime = _runtime_with_closure(
            original,
            recorded_at=BASE + timedelta(minutes=5),
            persisted_at=BASE + timedelta(minutes=10),
        )
        new_incident = _supervision(
            _unsafe_receipt(runtime_id="gha-200"),
            now=BASE + timedelta(minutes=20),
        )
        self.assertNotEqual(
            new_incident["evidence_digest"],
            original["evidence_digest"],
        )
        result = reconcile_global_worker_incident_center(
            _empty_snapshot(),
            new_incident,
            runtime,
            now=BASE + timedelta(minutes=20),
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(
            result["incidents"][0]["status"],
            "OPEN_NEW_AFTER_CLOSURE",
        )
        self.assertTrue(
            result["incidents"][0]["new_incident_after_closure"]
        )
        self.assertEqual(
            result["global_worker_reconciliation"]["state"],
            "NEW_INCIDENT_AFTER_CLOSURE",
        )

    def test_runtime_unavailable_fails_open(self):
        supervision = _supervision(now=BASE)
        result = reconcile_global_worker_incident_center(
            _empty_snapshot(),
            supervision,
            {"status": "ERROR", "checkpoint": None},
            now=BASE,
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["incidents"][0]["status"], "OPEN")
        self.assertEqual(
            result["incidents"][0]["closure_reconciliation"],
            "UNAVAILABLE_FAIL_OPEN",
        )
        self.assertTrue(
            result["global_worker_reconciliation"]["fail_open"]
        )

    def test_ledger_digest_mismatch_fails_open(self):
        supervision = _supervision(now=BASE)
        runtime = _runtime_with_closure(
            supervision,
            recorded_at=BASE + timedelta(minutes=5),
            persisted_at=BASE + timedelta(minutes=10),
        )
        broken = deepcopy(runtime)
        broken["checkpoint"][LEDGER_NAMESPACE]["digest"] = "broken"
        result = reconcile_global_worker_incident_center(
            _empty_snapshot(),
            supervision,
            broken,
            now=BASE + timedelta(minutes=11),
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["incidents"][0]["status"], "OPEN")
        self.assertEqual(
            result["global_worker_reconciliation"]["state"],
            "FAIL_OPEN",
        )

    def test_individual_durable_record_tamper_fails_open(self):
        supervision = _supervision(now=BASE)
        runtime = _runtime_with_closure(
            supervision,
            recorded_at=BASE + timedelta(minutes=5),
            persisted_at=BASE + timedelta(minutes=10),
        )
        broken = deepcopy(runtime)
        ledger = broken["checkpoint"][LEDGER_NAMESPACE]
        ledger["records"][0]["persisted_by"] = "tampered"
        payload = dict(ledger)
        payload.pop("digest", None)
        ledger["digest"] = digest(payload)

        result = reconcile_global_worker_incident_center(
            _empty_snapshot(),
            supervision,
            broken,
            now=BASE + timedelta(minutes=11),
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["incidents"][0]["status"], "OPEN")
        self.assertEqual(
            result["global_worker_reconciliation"]["durable_history_state"],
            "BLOCKED",
        )

    def test_no_current_incident_still_shows_durable_closed_history(self):
        incident = _supervision(now=BASE)
        runtime = _runtime_with_closure(
            incident,
            recorded_at=BASE + timedelta(minutes=5),
            persisted_at=BASE + timedelta(minutes=10),
        )
        healthy = supervise_global_worker(
            {"status": "NOT_ENABLED"},
            _flag("DISABLED"),
            now=BASE + timedelta(minutes=20),
        )
        result = reconcile_global_worker_incident_center(
            _empty_snapshot(),
            healthy,
            runtime,
            now=BASE + timedelta(minutes=20),
        )
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["closed_total"], 1)
        self.assertEqual(
            result["global_worker_reconciliation"]["state"],
            "NO_GLOBAL_WORKER_INCIDENT",
        )

    def test_base_incidents_are_preserved(self):
        base = _empty_snapshot()
        base["incidents"] = [{
            "incident_id": "INC-OTHER",
            "kind": "ENGINE",
            "severity": "CRITICAL",
            "title": "Other",
            "detail": "Other incident",
            "source": "test",
            "evidence_state": "CONFIRMED",
            "status": "OPEN",
            "response_key": "engine",
        }]
        supervision = _supervision(now=BASE)
        result = reconcile_global_worker_incident_center(
            base,
            supervision,
            {
                "status": "CONFIRMED",
                "checkpoint": ensure_operating_checkpoint({}),
                "sha": "runtime-sha-1",
            },
            now=BASE,
        )
        ids = {row["incident_id"] for row in result["incidents"]}
        self.assertEqual(ids, {"INC-OTHER", "INC-AION-GW-" + supervision["evidence_digest"][:12].upper()})
        self.assertEqual(result["total"], 2)
        self.assertTrue(result["has_critical"])

    def test_closed_rows_never_authorize_reactivation(self):
        supervision = _supervision(now=BASE)
        runtime = _runtime_with_closure(
            supervision,
            recorded_at=BASE + timedelta(minutes=5),
            persisted_at=BASE + timedelta(minutes=10),
        )
        result = reconcile_global_worker_incident_center(
            _empty_snapshot(),
            supervision,
            runtime,
            now=BASE + timedelta(minutes=11),
        )
        rows = closed_incident_rows(result)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Reativação autorizada"], "NÃO")

    def test_admin_ui_exposes_reconciliation_and_closed_history(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Reconciliação Worker Global", source)
        self.assertIn("Histórico de incidentes fechados", source)
        self.assertIn("REOPENED", source)
        self.assertIn("reativação autorizada: NÃO", source)

    def test_module_is_read_only(self):
        source = Path(
            "atlasquant_aion_global_worker_incident_reconciliation.py"
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
