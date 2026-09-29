import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from atlasquant_aion_global_worker import stage_arm_global_worker
from atlasquant_aion_global_worker_arming import (
    CONFIRMATION_PHRASE,
    approve_global_worker_arming_plan,
    prepare_global_worker_arming_plan,
)
from atlasquant_aion_global_worker_readiness import (
    activation_readiness_snapshot,
    feature_flag_state,
    fetch_recent_autopilot_pulses,
    protocol_shadow_probe,
    pulse_health,
    runtime_posture,
    workflow_contract,
)
from atlasquant_aion_memory import (
    RuntimeConfig,
    checkpoint_integrity_report,
    ensure_operating_checkpoint,
)


NOW = datetime(2026, 9, 28, 13, 30, tzinfo=timezone.utc)


def _config():
    return RuntimeConfig(
        token="test-token",
        repo="owner/repo",
        branch="atlasquant-runtime",
    )


def _access():
    return {
        "allowed": True,
        "mode": "AUTHENTICATED",
        "role": "ADMIN",
        "session": {
            "username": "mikael",
            "role": "ADMIN",
            "credential_fingerprint": "readiness-admin-fingerprint-1234567890",
            "permissions": ["app:read", "admin:read", "aion:admin"],
        },
    }


def _runtime(checkpoint=None):
    cp = ensure_operating_checkpoint(checkpoint or {})
    return {
        "status": "CONFIRMED",
        "source": "GitHub:atlasquant-runtime:dados/aion/checkpoint_master.json",
        "checkpoint": cp,
        "sha": "abc123runtime",
        "integrity": checkpoint_integrity_report(cp),
    }


def _workflow():
    return """name: AtlasQuant - Automatic Scanner + Autopilot
on:
  schedule:
    - cron: "7,37 * * * *"
permissions:
  contents: write
jobs:
  autopilot:
    env:
      GITHUB_DATA_BRANCH: "atlasquant-runtime"
    steps:
      - name: AION Global Worker tick
        if: ${{ vars.ATLASQUANT_AION_GLOBAL_WORKER_ENABLED == '1' }}
        run: python atlasquant_aion_global_worker.py --tick
"""


def _pulses(now=NOW):
    return [
        {
            "id": idx,
            "event": "schedule",
            "status": "completed",
            "conclusion": "success",
            "created_at": (now - timedelta(minutes=idx * 30)).isoformat(),
        }
        for idx in range(1, 6)
    ]


class GlobalWorkerActivationReadinessTests(unittest.TestCase):
    def test_feature_flag_state_is_strict(self):
        self.assertEqual(feature_flag_state(""), "UNSET")
        self.assertEqual(feature_flag_state("0"), "DISABLED")
        self.assertEqual(feature_flag_state("false"), "DISABLED")
        self.assertEqual(feature_flag_state("1"), "ENABLED")
        self.assertEqual(feature_flag_state("true"), "ENABLED")
        self.assertEqual(feature_flag_state("banana"), "INVALID")

    def test_workflow_contract_reuses_single_existing_cron(self):
        report = workflow_contract(_workflow())
        self.assertEqual(report["state"], "PASS")
        self.assertEqual(report["cron_count"], 1)
        self.assertTrue(report["existing_pulse_reused"])
        self.assertFalse(report["additional_cron_detected"])
        self.assertTrue(report["feature_flag_condition_present"])
        self.assertTrue(report["runtime_branch_explicit"])

    def test_workflow_contract_rejects_second_cron(self):
        source = _workflow() + '\n    - cron: "*/5 * * * *"\n'
        report = workflow_contract(source)
        self.assertEqual(report["state"], "FAIL")
        self.assertTrue(report["additional_cron_detected"])

    def test_pulse_health_requires_recent_successful_schedule_runs(self):
        healthy = pulse_health(_pulses(), now=NOW)
        self.assertEqual(healthy["state"], "PASS")
        stale = pulse_health(
            [
                {
                    "event": "schedule",
                    "status": "completed",
                    "conclusion": "success",
                    "created_at": (NOW - timedelta(hours=3, minutes=i)).isoformat(),
                }
                for i in range(5)
            ],
            now=NOW,
        )
        self.assertEqual(stale["state"], "BLOCKED")

    def test_pulse_health_allows_fresh_active_run_after_recent_successes(self):
        rows = _pulses()
        rows.insert(
            0,
            {
                "event": "schedule",
                "status": "in_progress",
                "conclusion": "",
                "created_at": (NOW - timedelta(minutes=2)).isoformat(),
            },
        )
        report = pulse_health(rows, now=NOW)
        self.assertEqual(report["state"], "PASS")
        self.assertTrue(report["latest_is_active"])
        self.assertEqual(report["latest_status"], "in_progress")
        self.assertEqual(report["latest_completed_conclusion"], "success")

    def test_pulse_health_blocks_fresh_completed_failure(self):
        rows = _pulses()
        rows.insert(
            0,
            {
                "event": "schedule",
                "status": "completed",
                "conclusion": "failure",
                "created_at": (NOW - timedelta(minutes=2)).isoformat(),
            },
        )
        report = pulse_health(rows, now=NOW)
        self.assertEqual(report["state"], "BLOCKED")
        self.assertFalse(report["latest_is_active"])
        self.assertEqual(report["latest_conclusion"], "failure")

    def test_pulse_health_blocks_stale_active_run(self):
        rows = _pulses()
        rows.insert(
            0,
            {
                "event": "schedule",
                "status": "in_progress",
                "conclusion": "",
                "created_at": (NOW - timedelta(hours=2)).isoformat(),
            },
        )
        report = pulse_health(rows, now=NOW)
        self.assertEqual(report["state"], "BLOCKED")
        self.assertGreater(report["stale_active_count"], 0)

    def test_protocol_shadow_probe_is_in_memory_and_passes(self):
        report = protocol_shadow_probe(now=NOW)
        self.assertEqual(report["state"], "PASS")
        self.assertTrue(all(report["checks"].values()))
        self.assertFalse(report["network_called"])
        self.assertFalse(report["runtime_modified"])
        self.assertFalse(report["feature_flag_modified"])

    def test_runtime_posture_accepts_confirmed_runtime_without_global_namespace(self):
        report = runtime_posture(_runtime(), _config())
        self.assertEqual(report["state"], "PASS")
        self.assertEqual(report["runtime_branch"], "atlasquant-runtime")
        self.assertTrue(report["runtime_branch_safe"])
        self.assertEqual(report["global_worker_namespace"], "ABSENT")
        self.assertEqual(report["global_worker_state"], "ABSENT")

    def test_readiness_before_arming_is_safe_and_explicit(self):
        report = activation_readiness_snapshot(
            runtime_result=_runtime(),
            config=_config(),
            feature_flag_raw="",
            workflow_text=_workflow(),
            pulse_rows=_pulses(),
            now=NOW,
        )
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["activation_stage"], "READY_FOR_ADMIN_ARMING")
        self.assertEqual(report["feature_flag"]["state"], "UNSET")
        self.assertFalse(report["feature_flag"]["value_exposed"])
        self.assertTrue(report["read_only"])
        self.assertFalse(report["runtime_modified"])
        self.assertFalse(report["worker_armed_by_this_check"])

    def test_enabled_flag_without_persisted_arming_is_blocked(self):
        report = activation_readiness_snapshot(
            runtime_result=_runtime(),
            config=_config(),
            feature_flag_raw="1",
            workflow_text=_workflow(),
            pulse_rows=_pulses(),
            now=NOW,
        )
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["activation_stage"], "BLOCKED")
        self.assertIn(
            "FEATURE_FLAG_ENABLED_WITHOUT_PERSISTED_ARMING",
            report["blockers"],
        )
        self.assertIn(
            "FEATURE_FLAG_ENABLED_WHILE_KILL_SWITCH_ACTIVE",
            report["blockers"],
        )

    def test_persisted_armed_state_with_disabled_flag_is_ready_for_flag_enable(self):
        access = _access()
        checkpoint = {}
        plan = prepare_global_worker_arming_plan(
            access,
            checkpoint,
            max_jobs=5,
            lease_seconds=600,
            approval_ttl_seconds=900,
            now=NOW,
        )
        approved = approve_global_worker_arming_plan(
            access,
            plan["plan"],
            confirmation=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=NOW,
        )
        staged = stage_arm_global_worker(
            access,
            checkpoint,
            confirmation=True,
            arming_approval=approved["approval"],
            max_jobs=5,
            lease_seconds=600,
            now=NOW,
        )
        report = activation_readiness_snapshot(
            runtime_result=_runtime(staged["checkpoint"]),
            config=_config(),
            feature_flag_raw="0",
            workflow_text=_workflow(),
            pulse_rows=_pulses(),
            now=NOW,
        )
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["activation_stage"], "READY_FOR_FLAG_ENABLE")
        self.assertEqual(report["runtime"]["global_worker_state"], "ARMED")
        self.assertFalse(report["runtime"]["global_kill_switch"])

    def test_invalid_flag_blocks_readiness(self):
        report = activation_readiness_snapshot(
            runtime_result=_runtime(),
            config=_config(),
            feature_flag_raw="maybe",
            workflow_text=_workflow(),
            pulse_rows=_pulses(),
            now=NOW,
        )
        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("FEATURE_FLAG_INVALID", report["blockers"])

    def test_runtime_mismatch_blocks_readiness(self):
        bad = _runtime()
        bad["checkpoint"]["operating"]["task_digest"] = "tampered"
        report = activation_readiness_snapshot(
            runtime_result=bad,
            config=_config(),
            feature_flag_raw="0",
            workflow_text=_workflow(),
            pulse_rows=_pulses(),
            now=NOW,
        )
        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("RUNTIME_POSTURE_NOT_CONFIRMED", report["blockers"])

    def test_unsafe_code_branch_is_blocked(self):
        cfg = RuntimeConfig(
            token="test-token",
            repo="owner/repo",
            branch="main",
        )
        report = runtime_posture(_runtime(), cfg)
        self.assertEqual(report["state"], "BLOCKED")
        self.assertFalse(report["runtime_branch_safe"])

    def test_pulse_api_reader_uses_get_only_and_sanitizes_rows(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "workflow_runs": [
                {
                    "id": 99,
                    "name": "Other Scheduled Workflow",
                    "path": ".github/workflows/other.yml",
                    "event": "schedule",
                    "status": "completed",
                    "conclusion": "success",
                    "created_at": "2026-09-28T13:05:00Z",
                    "updated_at": "2026-09-28T13:06:00Z",
                    "head_sha": "b" * 40,
                },
                {
                    "id": 11,
                    "name": "AtlasQuant - Automatic Scanner + Autopilot",
                    "path": ".github/workflows/autopilot-v107.yml",
                    "event": "schedule",
                    "status": "completed",
                    "conclusion": "success",
                    "created_at": "2026-09-28T13:00:00Z",
                    "updated_at": "2026-09-28T13:02:00Z",
                    "head_sha": "a" * 40,
                    "secret_field": "must-not-pass-through",
                }
            ]
        }
        with patch(
            "atlasquant_aion_global_worker_readiness.github_get",
            return_value=response,
        ) as get:
            result = fetch_recent_autopilot_pulses(
                _config(),
                token="token",
            )
        get.assert_called_once()
        args, kwargs = get.call_args
        self.assertTrue(str(args[0]).endswith("/actions/runs"))
        self.assertNotIn("event", kwargs["params"])
        self.assertEqual(kwargs["params"]["branch"], "main")
        self.assertGreaterEqual(kwargs["params"]["per_page"], 50)
        self.assertEqual(result["status"], "CONFIRMED")
        self.assertEqual(len(result["runs"]), 1)
        self.assertEqual(result["runs"][0]["id"], 11)
        self.assertNotIn("secret_field", result["runs"][0])
        self.assertEqual(result["runs"][0]["head_sha"], "a" * 40)

    def test_pulse_api_reader_fails_closed_when_autopilot_is_absent(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "workflow_runs": [
                {
                    "id": 99,
                    "name": "Other Scheduled Workflow",
                    "path": ".github/workflows/other.yml",
                    "event": "schedule",
                    "status": "completed",
                    "conclusion": "success",
                    "created_at": "2026-09-28T13:05:00Z",
                }
            ]
        }
        with patch(
            "atlasquant_aion_global_worker_readiness.github_get",
            return_value=response,
        ):
            result = fetch_recent_autopilot_pulses(
                _config(),
                token="token",
            )
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["runs"], [])
        self.assertIn("not found", result["reason"])

    def test_readiness_module_has_no_write_or_activation_api(self):
        source = Path(
            "atlasquant_aion_global_worker_readiness.py"
        ).read_text(encoding="utf-8")
        for banned in (
            "requests.put(",
            "requests.post(",
            "requests.patch(",
            "requests.delete(",
            "requests.get(",
            "save_runtime_checkpoint(",
            "_persist_runtime_checkpoint_cas(",
            "run_global_worker_once(",
            "os.system(",
            "subprocess.",
        ):
            self.assertNotIn(banned, source)
        self.assertIn("github_get(", source)

    def test_readiness_workflow_is_read_only_and_unscheduled(self):
        source = Path(
            ".github/workflows/aion-global-worker-readiness.yml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("schedule:", source)
        self.assertIn("contents: read", source)
        self.assertIn("actions: read", source)
        self.assertNotIn("contents: write", source)
        self.assertIn("GLOBAL_WORKER_FLAG_STATE", source)
        self.assertIn("name: AION global worker readiness", source)
        self.assertIn(
            "python atlasquant_aion_global_worker_readiness.py --check-runtime",
            source,
        )


if __name__ == "__main__":
    unittest.main()
