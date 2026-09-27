"""Convergence regressions for Checkpoint Mestre V18 and Astra durable hardening."""
from copy import deepcopy
import json
import socket
import subprocess
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

from atlasquant_aion_continuity import (
    MissionTransitionError,
    new_mission,
    transition_mission,
)
from atlasquant_aion_core import guardian_decision
from atlasquant_aion_durable_tasks import (
    DurableTaskError,
    new_durable_task,
    prepare_resume,
    record_resume,
    update_step,
)
from atlasquant_aion_memory import (
    checkpoint_integrity_report,
    checkpoint_source_digest,
    default_checkpoint,
    ensure_operating_checkpoint,
    update_continuity_checkpoint,
    update_durable_tasks_checkpoint,
)
from atlasquant_aion_memory_layers import remember
from atlasquant_aion_observability import events_digest, new_event, normalize_event
from atlasquant_aion_specialist_session import (
    build_specialist_session_snapshot,
    loaded_session_from_checkpoint,
    read_loaded_specialist_snapshot,
)
from atlasquant_aion_status_board import build_master_status_board

ADMIN = {"role": "ADMIN"}
NOW = "2026-09-27T08:00:00+00:00"
CANONICAL_MAIN = "571f9a49e83d8696e3ff13a56b62745da34cc69b"
ROOT = Path(__file__).resolve().parent


def _task(**step_fields):
    return new_durable_task(
        "Local work",
        steps=[{"title": "Inspect", "step_id": "s", **step_fields}],
        checkpoint_digest="cp-a",
        created_at=NOW,
    )


class AionConvergenceTests(unittest.TestCase):
    def test_checkpoint_v18_and_durable_tasks_coexist(self):
        task = record_resume(_task(), expected_revision=1, checkpoint_digest="cp-a")
        checkpoint = update_durable_tasks_checkpoint(default_checkpoint(), records=[task])
        self.assertEqual(checkpoint["checkpoint_version"], 18)
        self.assertIn("memory_layers", checkpoint)
        self.assertEqual(checkpoint["memory_layers"]["schema"], "ATLASQUANT_AION_MEMORY_LAYERS_V1")
        self.assertEqual(checkpoint["durable_tasks"]["records"][0]["state"], task["state"])
        self.assertFalse(checkpoint["durable_tasks"]["records"][0]["automatic_resume_executes"])
        self.assertFalse(checkpoint["aion"]["real_trading"])
        restored = ensure_operating_checkpoint(json.loads(json.dumps(checkpoint)))
        self.assertEqual(restored["checkpoint_version"], 18)
        self.assertEqual(restored["durable_tasks"]["records"][0], task)
        self.assertEqual(checkpoint_integrity_report(restored)["state"], "CONFIRMED")

    def test_legacy_checkpoint_migrates_without_dropping_durable_tasks(self):
        task = record_resume(_task(), expected_revision=1, checkpoint_digest="cp-a")
        mission = new_mission("Keep continuity", created_at=NOW)
        current = update_durable_tasks_checkpoint(default_checkpoint(), records=[task])
        current = update_continuity_checkpoint(current, missions=[mission])
        legacy = json.loads(json.dumps(current))
        legacy["checkpoint_version"] = 17
        legacy.pop("memory_layers")
        upgraded = ensure_operating_checkpoint(legacy)
        self.assertEqual(legacy["checkpoint_version"], 17)
        self.assertNotIn("memory_layers", legacy)
        self.assertEqual(upgraded["checkpoint_version"], 18)
        self.assertEqual(upgraded["memory_layers"]["schema"], "ATLASQUANT_AION_MEMORY_LAYERS_V1")
        self.assertEqual(upgraded["durable_tasks"]["records"][0]["durable_task_id"], task["durable_task_id"])
        self.assertEqual(upgraded["durable_tasks"]["records"][0]["state"], task["state"])
        self.assertEqual(upgraded["durable_tasks"]["records"][0]["steps"], task["steps"])
        self.assertEqual(upgraded["continuity"]["missions"][0]["mission_id"], mission["mission_id"])
        report = checkpoint_integrity_report(legacy)
        self.assertIn(report["state"], {"MIGRATION_REQUIRED", "CONFIRMED"})
        self.assertNotEqual(report["state"], "MISMATCH")

    def test_memory_fabric_does_not_erase_durable_state_machine(self):
        waiting = update_step(_task(), "s", "WAITING_APPROVAL")
        checkpoint = update_durable_tasks_checkpoint(default_checkpoint(), records=[waiting])
        before = deepcopy(checkpoint["durable_tasks"])
        checkpoint["memory_layers"] = remember(
            checkpoint["memory_layers"],
            layer="project",
            content="A maquina de estados duravel permanece intacta.",
            origin="convergence",
            category="continuity",
            truth_state="CONFIRMED",
        )
        merged = ensure_operating_checkpoint(checkpoint)
        self.assertEqual(merged["checkpoint_version"], 18)
        self.assertGreaterEqual(len(merged["memory_layers"]["entries"]), 1)
        self.assertEqual(merged["durable_tasks"]["records"], before["records"])
        self.assertEqual(merged["durable_tasks"]["records"][0]["state"], "WAITING_APPROVAL")
        self.assertEqual(merged["durable_tasks"]["digest"], before["digest"])

    def test_specialist_snapshot_does_not_erase_checkpoint_continuity(self):
        waiting = update_step(_task(), "s", "WAITING_APPROVAL")
        mission = new_mission("Snapshot must not write", created_at=NOW)
        checkpoint = update_durable_tasks_checkpoint(default_checkpoint(), records=[waiting])
        checkpoint["continuity"]["missions"] = [mission]
        before = deepcopy(checkpoint)
        snapshot = loaded_session_from_checkpoint(checkpoint)
        reading = read_loaded_specialist_snapshot("market", snapshot)
        self.assertEqual(checkpoint, before)
        self.assertEqual(checkpoint["continuity"]["missions"][0]["mission_id"], mission["mission_id"])
        self.assertEqual(checkpoint["durable_tasks"]["records"][0]["state"], "WAITING_APPROVAL")
        self.assertEqual(reading["answer_truth"], "UNKNOWN")
        self.assertFalse(reading["answers_user_question"])
        self.assertNotIn("top_10", reading.get("observations") or {})

    def test_sanitization_still_removes_secrets_and_keeps_old_event_digests(self):
        historical = {
            "schema": "ATLASQUANT_AION_OBSERVABILITY_V1",
            "event_id": "EV-LEGACY00000001",
            "event_type": "note",
            "message": "hello",
            "severity": "INFO",
            "source": "AION",
            "truth_state": "CONFIRMED",
            "evidence": {"note": "plain"},
            "created_at": NOW,
        }
        self.assertEqual(normalize_event(historical), historical)
        self.assertEqual(events_digest([historical]), events_digest([normalize_event(historical)]))
        event = new_event(
            "check",
            "token=abcd",
            evidence={"metadata": {"items": [{"api_key": "xy"}], "note": "password=abcd"}},
            created_at=NOW,
            request_id="Bearer zzzzzzzzzzzzz",
        )
        blob = json.dumps(event)
        self.assertNotIn("abcd", blob)
        self.assertNotIn("xy", blob)
        self.assertNotIn("zzzzzzzzzzzzz", blob)
        self.assertIn("[REDACTED]", blob)
        self.assertEqual(event["request_id"], "[REDACTED]")
        self.assertNotIn("task_id", event)

    def test_resume_does_not_execute_and_waiting_approval_is_not_bypassed(self):
        waiting = update_step(_task(), "s", "WAITING_APPROVAL", blocker="Needs review")
        resumed = record_resume(
            waiting,
            expected_revision=waiting["revision"],
            checkpoint_digest="cp-a",
        )
        self.assertEqual(resumed["state"], "WAITING_APPROVAL")
        self.assertEqual(resumed["steps"][0]["state"], "WAITING_APPROVAL")
        self.assertEqual(resumed["steps"][0]["attempts"], waiting["steps"][0]["attempts"])
        self.assertFalse(resumed["automatic_resume_executes"])
        view = prepare_resume(resumed, checkpoint_digest="cp-a")
        self.assertFalse(view["executes_action"])
        self.assertTrue(view["restores_state_only"])
        with self.assertRaises(DurableTaskError) as ctx:
            update_step(resumed, "s", "RUNNING", access=ADMIN)
        self.assertEqual(ctx.exception.result["error_code"], "APPROVAL_REQUIRED")
        self.assertFalse(ctx.exception.result["executes_action"])

    def test_terminal_mission_rejects_inconsistent_active_task_and_reopen(self):
        mission = new_mission("Finish", created_at=NOW)
        running = update_step(_task(), "s", "RUNNING", access=ADMIN)
        done = transition_mission([mission], mission["mission_id"], "IN_PROGRESS")
        done = transition_mission(done, mission["mission_id"], "DONE")
        self.assertEqual(done[0]["status"], "DONE")
        with self.assertRaises(MissionTransitionError) as mission_error:
            transition_mission(done, mission["mission_id"], "IN_PROGRESS")
        self.assertEqual(mission_error.exception.result["error_code"], "INVALID_MISSION_TRANSITION")
        self.assertFalse(mission_error.exception.result["executes_action"])
        checkpoint = update_durable_tasks_checkpoint(default_checkpoint(), records=[running])
        checkpoint["continuity"]["missions"] = done
        running["mission_id"] = mission["mission_id"]
        running["revision"] += 1
        with self.assertRaises(DurableTaskError) as task_error:
            update_durable_tasks_checkpoint(checkpoint, records=[running])
        self.assertEqual(task_error.exception.result["error_code"], "MISSION_TASK_INCONSISTENT")
        self.assertFalse(task_error.exception.result["executes_action"])

    def test_guardian_denies_real_trade_and_snapshot_stays_local(self):
        for flags in ({}, {"real_broker_execution": True}):
            decision = guardian_decision("real_trade", ADMIN, approved=True, feature_flags=flags)
            self.assertFalse(decision["allowed"])
            self.assertEqual(decision["risk"], "REAL_TRADING")
        denied = _task(guardian_action="real_trade")
        with self.assertRaises(DurableTaskError) as ctx:
            update_step(denied, "s", "RUNNING", access=ADMIN, approved=True)
        self.assertEqual(ctx.exception.result["error_code"], "GUARDIAN_DENIED")

        def explode(*_args, **_kwargs):
            raise AssertionError("network call")

        with mock.patch("socket.create_connection", explode), mock.patch("urllib.request.urlopen", explode):
            snapshot = build_specialist_session_snapshot({"origin": "CHECKPOINT", "observed_at": NOW})
            absent = read_loaded_specialist_snapshot("market", None)
            core = read_loaded_specialist_snapshot("core", snapshot)
        self.assertFalse(snapshot["network_called"])
        self.assertFalse(snapshot["provider_called"])
        self.assertFalse(snapshot["secrets_included"])
        self.assertEqual(absent["answer_truth"], "UNKNOWN")
        self.assertEqual(absent["truth_state"], "UNKNOWN")
        self.assertFalse(absent["answers_user_question"])
        self.assertFalse(absent["network_called"])
        self.assertFalse(core["observations"]["real_trade_allowed"])
        self.assertFalse(core["answers_user_question"])
        self.assertIs(socket.create_connection, socket.create_connection)
        self.assertIs(urllib.request.urlopen, urllib.request.urlopen)

    def test_status_board_and_admin_keep_both_stacks(self):
        board = build_master_status_board(
            checkpoint={
                "operating": {"tasks": []},
                "entitlements": {"records": []},
                "continuity": {"missions": [], "handoffs": []},
                "durable_tasks": {"records": []},
                "memory_layers": default_checkpoint()["memory_layers"],
            },
            runtime_result={
                "status": "CONFIRMED",
                "integrity": {"state": "CONFIRMED", "matched": 7, "total": 7},
            },
            provider={"state": "ZERO_COST_LOCAL"},
            feature_flags={},
            system_context={"truth_state": "CONFIRMED", "source_build": "abc123"},
            market_context={"fresh_confirmed": False, "summary": ""},
            account_entitlement_audit={
                "schema": "ATLASQUANT_ENTITLEMENT_ACCOUNT_AUDIT_V1",
                "accounts_total": 0,
                "active_user_accounts": 0,
                "effective_user_accounts": 0,
                "user_accounts_without_effective_entitlement": 0,
                "duplicate_effective_user_accounts": 0,
                "orphan_effective_entitlements": 0,
            },
            working_dirty=False,
        )
        item = next(row for row in board["items"] if row["id"] == "durable_task_continuity")
        self.assertEqual(item["state"], "CONFIRMED")
        self.assertFalse(item["executes_action"])
        market = next(row for row in board["items"] if row["id"] == "market_freshness")
        self.assertEqual(market["state"], "UNKNOWN")
        admin = (ROOT / "atlasquant_aion_admin.py").read_text(encoding="utf-8")
        for marker in (
            "specialist_snapshot",
            "loaded_session_from_checkpoint",
            "memory_layer_summary",
            "answers_user_question",
            "expected_revision=resume.get(\"revision\")",
            "Prepare a retomada da tarefa selecionada primeiro.",
            "Ordens reais",
        ):
            self.assertIn(marker, admin)
        self.assertIn("durable_task_continuity", (ROOT / "atlasquant_aion_status_board.py").read_text(encoding="utf-8"))

    def test_main_and_production_surfaces_stay_untouched(self):
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", CANONICAL_MAIN, "origin/main"],
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(ancestor.returncode, 0)
        diff = subprocess.check_output(
            ["git", "diff", "--name-only", "origin/main"],
            cwd=ROOT,
            text=True,
        )
        forbidden = [
            line for line in diff.splitlines()
            if line == "render.yaml"
            or line.startswith("deploy/")
            or "secret" in line.lower()
        ]
        self.assertEqual(forbidden, [])
        checkpoint = default_checkpoint()
        self.assertFalse(checkpoint["aion"]["real_trading"])
        self.assertFalse(guardian_decision("deploy_production", ADMIN, approved=True)["allowed"])
        self.assertFalse(guardian_decision("merge_main", ADMIN, approved=True)["allowed"])
        self.assertFalse(guardian_decision("real_trade", ADMIN, approved=True)["allowed"])
        # Optimistic revision still refuses a stale checkpoint digest.
        current = update_durable_tasks_checkpoint(checkpoint, records=[_task()])
        with self.assertRaises(DurableTaskError) as ctx:
            update_durable_tasks_checkpoint(
                current,
                records=[_task()],
                expected_checkpoint_digest="stale",
            )
        self.assertEqual(ctx.exception.result["error_code"], "REVISION_CHECKPOINT_CONFLICT")
        self.assertNotEqual(checkpoint_source_digest(current), "stale")


if __name__ == "__main__":
    unittest.main()
