import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from atlasquant_aion_global_worker import stage_arm_global_worker
from atlasquant_aion_global_worker_arming import (
    CONFIRMATION_PHRASE as ARM_PHRASE,
    approve_global_worker_arming_plan,
    prepare_global_worker_arming_plan,
)
from atlasquant_aion_global_worker_activation import (
    CONFIRMATION_PHRASE as ACTIVATE_PHRASE,
    READY_STAGE,
    activate_global_worker_feature_flag,
    approve_global_worker_activation_plan,
    prepare_global_worker_activation_plan,
)
from atlasquant_aion_global_worker_durable_incident_closure import (
    build_durable_closure_checkpoint,
)
from atlasquant_aion_global_worker_human_incident_closure import (
    CONFIRMATION_PHRASE as CLOSE_PHRASE,
    record_human_incident_closure,
)
from atlasquant_aion_global_worker_incident_reconciliation import (
    reconcile_global_worker_incident_center,
)
from atlasquant_aion_global_worker_reactivation_gate import (
    BLOCKED_STATUS,
    NOT_REQUIRED_STATUS,
    READY_STATUS,
    assess_post_incident_reactivation_gate,
    gate_integrity,
    reactivation_gate_requirement,
    validate_reactivation_gate_for_execution,
    validate_reactivation_gate_for_plan,
)
from atlasquant_aion_global_worker_supervision import supervise_global_worker
from atlasquant_aion_memory import (
    RuntimeConfig,
    ensure_operating_checkpoint,
)


NOW = datetime(2026, 9, 28, 20, 0, tzinfo=timezone.utc)


def _access():
    return {
        "allowed": True,
        "mode": "AUTHENTICATED",
        "role": "ADMIN",
        "session": {
            "username": "mikael",
            "role": "ADMIN",
            "credential_fingerprint": "reactivation-gate-admin-1234567890",
            "permissions": ["app:read", "admin:read", "aion:admin"],
        },
    }


def _config():
    return RuntimeConfig(
        token="test-token",
        repo="owner/repo",
        branch="atlasquant-runtime",
    )


def _safe_flag(state="DISABLED"):
    return {
        "status": "CONFIRMED",
        "state": state,
        "safe_for_arming_persistence": state in {"UNSET", "DISABLED"},
        "variable_present": state != "UNSET",
        "raw_value_exposed": False,
    }


def _readiness(state="DISABLED"):
    return {
        "status": "PASS",
        "activation_stage": READY_STAGE,
        "blockers": [],
        "checked_at": NOW.isoformat(),
        "runtime": {
            "state": "PASS",
            "checkpoint_integrity": "CONFIRMED",
            "global_worker_state": "ARMED",
            "global_kill_switch": False,
        },
        "feature_flag": {
            "name": "ATLASQUANT_AION_GLOBAL_WORKER_ENABLED",
            "state": state,
            "value_exposed": False,
        },
        "flag_evidence": _safe_flag(state),
        "pulse": {"state": "PASS"},
        "shadow_protocol": {"state": "PASS"},
        "read_only": True,
        "runtime_modified": False,
        "feature_flag_modified": False,
    }


def _armed_checkpoint():
    access = _access()
    source = ensure_operating_checkpoint({})
    plan = prepare_global_worker_arming_plan(
        access,
        source,
        max_jobs=5,
        lease_seconds=600,
        approval_ttl_seconds=900,
        now=NOW - timedelta(hours=1),
    )
    approved = approve_global_worker_arming_plan(
        access,
        plan["plan"],
        confirmation=True,
        confirmation_phrase=ARM_PHRASE,
        now=NOW - timedelta(hours=1),
    )
    staged = stage_arm_global_worker(
        access,
        source,
        confirmation=True,
        arming_approval=approved["approval"],
        max_jobs=5,
        lease_seconds=600,
        now=NOW - timedelta(hours=1),
    )
    assert staged["status"] == "STAGED_ARMED"
    return staged["checkpoint"]


def _timeout_supervision(*, now):
    return supervise_global_worker(
        {
            "status": "LIVE_EVIDENCE_TIMEOUT",
            "reason": "HEARTBEAT_TIMEOUT",
            "live_confirmed": False,
            "heartbeat_confirmed": False,
            "tick_confirmed": False,
            "work_receipt_confirmed": False,
            "unsafe_receipts_after_activation": 0,
            "stale_lease": False,
            "last_runtime_id": "gha-incident-1",
            "last_heartbeat_at": "",
            "last_tick_at": "",
        },
        _safe_flag("ENABLED"),
        now=now,
    )


def _post_incident_runtime():
    cp = _armed_checkpoint()
    incident = _timeout_supervision(now=NOW - timedelta(minutes=40))
    assessment = {
        "status": "CLOSURE_REVIEW_READY",
        "closure_review_ready": True,
        "closure_package_digest": "c" * 64,
        "incident_evidence_digest": incident["evidence_digest"],
        "remediation_digest": "r" * 64,
        "assessed_at": (NOW - timedelta(minutes=30)).isoformat(),
        "incident_closed": False,
        "automatic_closure": False,
        "human_closure_required": True,
        "reactivation_authorized": False,
    }
    human = record_human_incident_closure(
        assessment,
        human_confirmation=True,
        evidence_acknowledged=True,
        reactivation_separation_acknowledged=True,
        confirmation_phrase=CLOSE_PHRASE,
        operator_note="Incidente revisado.",
        now=NOW - timedelta(minutes=25),
    )
    assert human["status"] == "HUMAN_CLOSURE_DECISION_RECORDED_SESSION_ONLY"
    durable = build_durable_closure_checkpoint(
        cp,
        human,
        actor_id="admin-1",
        source_runtime_sha="runtime-pre-close",
        source_runtime_checkpoint_digest="source-digest",
        feature_flag_state="DISABLED",
        now=NOW - timedelta(minutes=20),
    )
    runtime = {
        "status": "CONFIRMED",
        "checkpoint": durable,
        "sha": "runtime-post-incident-sha",
    }
    return runtime, incident


def _safe_reconciled_snapshot(runtime):
    healthy = supervise_global_worker(
        {"status": "NOT_ENABLED"},
        _safe_flag("DISABLED"),
        now=NOW,
    )
    return reconcile_global_worker_incident_center(
        {},
        healthy,
        runtime,
        now=NOW,
    )


class PostIncidentReactivationGateTests(unittest.TestCase):
    def test_gate_not_required_without_durable_incident_history(self):
        runtime = {
            "status": "CONFIRMED",
            "checkpoint": _armed_checkpoint(),
            "sha": "runtime-no-history",
        }
        requirement = reactivation_gate_requirement(runtime)
        self.assertFalse(requirement["required"])
        gate = assess_post_incident_reactivation_gate(
            runtime,
            {},
            _readiness(),
            _safe_flag(),
            now=NOW,
        )
        self.assertEqual(gate["status"], NOT_REQUIRED_STATUS)
        self.assertTrue(gate["gate_ready"])
        self.assertTrue(gate["activation_plan_allowed"])
        self.assertFalse(gate["reactivation_authorized"])

    def test_post_incident_gate_ready_only_after_reconciled_closed_history(self):
        runtime, _ = _post_incident_runtime()
        snapshot = _safe_reconciled_snapshot(runtime)
        gate = assess_post_incident_reactivation_gate(
            runtime,
            snapshot,
            _readiness(),
            _safe_flag(),
            now=NOW,
        )
        self.assertEqual(gate["status"], READY_STATUS)
        self.assertTrue(gate["gate_required"])
        self.assertTrue(gate["gate_ready"])
        self.assertTrue(gate["activation_plan_allowed"])
        self.assertEqual(gate_integrity(gate)["state"], "MATCH")
        self.assertFalse(gate["reactivation_authorized"])

    def test_missing_reconciliation_blocks_post_incident_gate(self):
        runtime, _ = _post_incident_runtime()
        gate = assess_post_incident_reactivation_gate(
            runtime,
            {},
            _readiness(),
            _safe_flag(),
            now=NOW,
        )
        self.assertEqual(gate["status"], BLOCKED_STATUS)
        self.assertIn(
            "GLOBAL_WORKER_RECONCILIATION_REQUIRED",
            gate["blockers"],
        )

    def test_open_or_reopened_global_worker_incident_blocks(self):
        runtime, incident = _post_incident_runtime()
        reopened = deepcopy(incident)
        reopened["generated_at"] = NOW.isoformat()
        snapshot = reconcile_global_worker_incident_center(
            {},
            reopened,
            runtime,
            now=NOW,
        )
        self.assertEqual(
            snapshot["global_worker_reconciliation"]["state"],
            "REOPENED",
        )
        gate = assess_post_incident_reactivation_gate(
            runtime,
            snapshot,
            _readiness(),
            _safe_flag(),
            now=NOW,
        )
        self.assertEqual(gate["status"], BLOCKED_STATUS)
        self.assertIn(
            "ACTIVE_GLOBAL_WORKER_INCIDENT_PRESENT",
            gate["blockers"],
        )

    def test_fail_open_reconciliation_blocks(self):
        runtime, _ = _post_incident_runtime()
        snapshot = _safe_reconciled_snapshot(runtime)
        snapshot["global_worker_reconciliation"]["fail_open"] = True
        gate = assess_post_incident_reactivation_gate(
            runtime,
            snapshot,
            _readiness(),
            _safe_flag(),
            now=NOW,
        )
        self.assertEqual(gate["status"], BLOCKED_STATUS)
        self.assertIn(
            "GLOBAL_WORKER_RECONCILIATION_FAIL_OPEN",
            gate["blockers"],
        )

    def test_latest_durable_closure_must_appear_in_closed_history(self):
        runtime, _ = _post_incident_runtime()
        snapshot = _safe_reconciled_snapshot(runtime)
        snapshot["closed_incidents"] = []
        gate = assess_post_incident_reactivation_gate(
            runtime,
            snapshot,
            _readiness(),
            _safe_flag(),
            now=NOW,
        )
        self.assertEqual(gate["status"], BLOCKED_STATUS)
        self.assertIn(
            "LATEST_DURABLE_CLOSURE_NOT_RECONCILED",
            gate["blockers"],
        )

    def test_readiness_and_disabled_flag_are_required(self):
        runtime, _ = _post_incident_runtime()
        snapshot = _safe_reconciled_snapshot(runtime)
        bad_readiness = _readiness()
        bad_readiness["activation_stage"] = "BLOCKED"
        gate = assess_post_incident_reactivation_gate(
            runtime,
            snapshot,
            bad_readiness,
            _safe_flag("ENABLED"),
            now=NOW,
        )
        self.assertEqual(gate["status"], BLOCKED_STATUS)
        self.assertIn(
            "ACTIVATION_READINESS_NOT_READY",
            gate["blockers"],
        )
        self.assertIn(
            "FEATURE_FLAG_NOT_PROVEN_DISABLED",
            gate["blockers"],
        )

    def test_gate_plan_validation_binds_runtime_readiness_and_flag(self):
        runtime, _ = _post_incident_runtime()
        readiness = _readiness()
        flag = _safe_flag()
        gate = assess_post_incident_reactivation_gate(
            runtime,
            _safe_reconciled_snapshot(runtime),
            readiness,
            flag,
            now=NOW,
        )
        valid = validate_reactivation_gate_for_plan(
            runtime,
            readiness,
            flag,
            gate,
            now=NOW,
        )
        self.assertEqual(valid["state"], "READY")

        changed = deepcopy(runtime)
        changed["sha"] = "different"
        blocked = validate_reactivation_gate_for_plan(
            changed,
            readiness,
            flag,
            gate,
            now=NOW,
        )
        self.assertEqual(
            blocked["reason"],
            "POST_INCIDENT_GATE_RUNTIME_SHA_CHANGED",
        )

    def test_expired_gate_blocks_plan(self):
        runtime, _ = _post_incident_runtime()
        readiness = _readiness()
        flag = _safe_flag()
        gate = assess_post_incident_reactivation_gate(
            runtime,
            _safe_reconciled_snapshot(runtime),
            readiness,
            flag,
            ttl_seconds=120,
            now=NOW,
        )
        result = validate_reactivation_gate_for_plan(
            runtime,
            readiness,
            flag,
            gate,
            now=NOW + timedelta(seconds=121),
        )
        self.assertEqual(
            result["reason"],
            "POST_INCIDENT_REACTIVATION_GATE_EXPIRED",
        )

    def test_activation_plan_blocks_post_incident_history_without_gate(self):
        runtime, _ = _post_incident_runtime()
        result = prepare_global_worker_activation_plan(
            _access(),
            runtime,
            _readiness(),
            _safe_flag(),
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("POST_INCIDENT", result["reason"])

    def test_activation_plan_binds_green_post_incident_gate(self):
        runtime, _ = _post_incident_runtime()
        readiness = _readiness()
        flag = _safe_flag()
        gate = assess_post_incident_reactivation_gate(
            runtime,
            _safe_reconciled_snapshot(runtime),
            readiness,
            flag,
            now=NOW,
        )
        result = prepare_global_worker_activation_plan(
            _access(),
            runtime,
            readiness,
            flag,
            reactivation_gate=gate,
            now=NOW,
        )
        self.assertEqual(result["status"], "ACTIVATION_PLAN_READY")
        plan = result["plan"]
        self.assertTrue(plan["post_incident_gate_required"])
        self.assertEqual(
            plan["post_incident_latest_closure_record_id"],
            gate["latest_closure_record_id"],
        )
        self.assertFalse(plan["feature_flag_modified"])

    def test_final_activation_execution_requires_fresh_gate(self):
        runtime, _ = _post_incident_runtime()
        readiness = _readiness()
        flag = _safe_flag()
        gate = assess_post_incident_reactivation_gate(
            runtime,
            _safe_reconciled_snapshot(runtime),
            readiness,
            flag,
            now=NOW,
        )
        plan_result = prepare_global_worker_activation_plan(
            _access(),
            runtime,
            readiness,
            flag,
            reactivation_gate=gate,
            now=NOW,
        )
        approval_result = approve_global_worker_activation_plan(
            _access(),
            plan_result["plan"],
            confirmation=True,
            confirmation_phrase=ACTIVATE_PHRASE,
            now=NOW,
        )
        approval = approval_result["approval"]
        writes = []

        result = activate_global_worker_feature_flag(
            _access(),
            runtime,
            approval,
            _config(),
            confirmation=True,
            reactivation_gate=None,
            flag_reader=lambda *args, **kwargs: _safe_flag(),
            flag_writer=lambda *args, **kwargs: writes.append(1),
            runtime_reader=lambda *args, **kwargs: deepcopy(runtime),
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["reason"],
            "FRESH_POST_INCIDENT_GATE_INTEGRITY_MISMATCH",
        )
        self.assertEqual(writes, [])

    def test_execution_validation_rejects_reopened_gate(self):
        runtime, incident = _post_incident_runtime()
        readiness = _readiness()
        flag = _safe_flag()
        safe_gate = assess_post_incident_reactivation_gate(
            runtime,
            _safe_reconciled_snapshot(runtime),
            readiness,
            flag,
            now=NOW,
        )
        plan_result = prepare_global_worker_activation_plan(
            _access(),
            runtime,
            readiness,
            flag,
            reactivation_gate=safe_gate,
            now=NOW,
        )
        approval = approve_global_worker_activation_plan(
            _access(),
            plan_result["plan"],
            confirmation=True,
            confirmation_phrase=ACTIVATE_PHRASE,
            now=NOW,
        )["approval"]

        reopened = deepcopy(incident)
        reopened["generated_at"] = (NOW + timedelta(seconds=10)).isoformat()
        reopened_snapshot = reconcile_global_worker_incident_center(
            {},
            reopened,
            runtime,
            now=NOW + timedelta(seconds=10),
        )
        blocked_gate = assess_post_incident_reactivation_gate(
            runtime,
            reopened_snapshot,
            readiness,
            flag,
            now=NOW + timedelta(seconds=10),
        )
        self.assertEqual(blocked_gate["status"], BLOCKED_STATUS)
        result = validate_reactivation_gate_for_execution(
            runtime,
            flag,
            approval,
            blocked_gate,
            now=NOW + timedelta(seconds=10),
        )
        self.assertEqual(
            result["reason"],
            "FRESH_POST_INCIDENT_GATE_INTEGRITY_MISMATCH",
        )

    def test_admin_ui_rechecks_gate_before_activation(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Post-incident gate", source)
        self.assertIn("Gate pós-incidente verde", source)
        self.assertIn("gate pós-incidente fresco", source)
        self.assertIn("Nenhuma feature flag foi alterada", source)
        self.assertIn("reactivation_gate=fresh_reactivation_gate", source)

    def test_gate_module_is_read_only(self):
        source = Path(
            "atlasquant_aion_global_worker_reactivation_gate.py"
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
