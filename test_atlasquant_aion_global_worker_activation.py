import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from atlasquant_aion_global_worker import (
    GLOBAL_WORKER_NAMESPACE,
    stage_arm_global_worker,
)
from atlasquant_aion_global_worker_arming import (
    CONFIRMATION_PHRASE as ARM_PHRASE,
    approve_global_worker_arming_plan,
    prepare_global_worker_arming_plan,
)
from atlasquant_aion_global_worker_activation import (
    CONFIRMATION_PHRASE,
    DEACTIVATION_PHRASE,
    READY_STAGE,
    activate_global_worker_feature_flag,
    approval_integrity,
    approve_global_worker_activation_plan,
    collect_activation_readiness_evidence,
    deactivate_global_worker_feature_flag,
    force_disable_repository_feature_flag,
    plan_integrity,
    prepare_global_worker_activation_plan,
    validate_global_worker_activation_approval,
    write_repository_feature_flag_enabled,
)
from atlasquant_aion_memory import (
    RuntimeConfig,
    checkpoint_source_digest,
    ensure_operating_checkpoint,
)


NOW = datetime(2026, 9, 28, 16, 0, tzinfo=timezone.utc)


def _access(username="mikael", fingerprint="activation-admin-fingerprint-1234567890"):
    return {
        "allowed": True,
        "mode": "AUTHENTICATED",
        "role": "ADMIN",
        "session": {
            "username": username,
            "role": "ADMIN",
            "credential_fingerprint": fingerprint,
            "permissions": ["app:read", "admin:read", "aion:admin"],
        },
    }


def _config():
    return RuntimeConfig(
        token="test-token",
        repo="owner/repo",
        branch="atlasquant-runtime",
    )


def _safe_flag(state="UNSET"):
    return {
        "status": "CONFIRMED",
        "state": state,
        "safe_for_arming_persistence": state in {"UNSET", "DISABLED"},
        "variable_present": state != "UNSET",
        "raw_value_exposed": False,
    }


class GlobalWorkerActivationCeremonyTests(unittest.TestCase):
    def setUp(self):
        self.access = _access()
        source = ensure_operating_checkpoint({})
        plan = prepare_global_worker_arming_plan(
            self.access,
            source,
            max_jobs=5,
            lease_seconds=600,
            approval_ttl_seconds=900,
            now=NOW,
        )
        self.assertEqual(plan["status"], "PLAN_READY")
        approved = approve_global_worker_arming_plan(
            self.access,
            plan["plan"],
            confirmation=True,
            confirmation_phrase=ARM_PHRASE,
            now=NOW,
        )
        self.assertEqual(approved["status"], "APPROVED_FOR_STAGING")
        staged = stage_arm_global_worker(
            self.access,
            source,
            confirmation=True,
            arming_approval=approved["approval"],
            max_jobs=5,
            lease_seconds=600,
            now=NOW,
        )
        self.assertEqual(staged["status"], "STAGED_ARMED")
        self.armed = staged["checkpoint"]
        self.runtime = {
            "status": "CONFIRMED",
            "checkpoint": deepcopy(self.armed),
            "sha": "runtime-armed-sha-1",
        }
        self.readiness = {
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
                "state": "UNSET",
                "value_exposed": False,
            },
            "pulse": {"state": "PASS"},
            "shadow_protocol": {"state": "PASS"},
            "read_only": True,
            "runtime_modified": False,
            "feature_flag_modified": False,
        }

    def plan(self, *, runtime=None, readiness=None, flag=None, ttl=600):
        result = prepare_global_worker_activation_plan(
            self.access,
            runtime or self.runtime,
            readiness or self.readiness,
            flag or _safe_flag("UNSET"),
            ttl_seconds=ttl,
            now=NOW,
        )
        self.assertEqual(result["status"], "ACTIVATION_PLAN_READY")
        return result["plan"]

    def approval(self, *, plan=None):
        activation_plan = plan or self.plan()
        result = approve_global_worker_activation_plan(
            self.access,
            activation_plan,
            confirmation=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=NOW,
        )
        self.assertEqual(result["status"], "APPROVED_FOR_ACTIVATION")
        return result["approval"]

    def test_plan_is_read_only_and_bound_to_persisted_armed_runtime(self):
        before = deepcopy(self.runtime)
        result = prepare_global_worker_activation_plan(
            self.access,
            self.runtime,
            self.readiness,
            _safe_flag("UNSET"),
            ttl_seconds=600,
            now=NOW,
        )
        self.assertEqual(result["status"], "ACTIVATION_PLAN_READY")
        self.assertEqual(self.runtime, before)
        self.assertFalse(result["runtime_checkpoint_modified"])
        self.assertFalse(result["feature_flag_modified"])
        self.assertFalse(result["global_worker_executed"])
        plan = result["plan"]
        self.assertEqual(plan_integrity(plan)["state"], "MATCH")
        self.assertEqual(plan["runtime_sha"], "runtime-armed-sha-1")
        self.assertEqual(
            plan["runtime_checkpoint_digest"],
            checkpoint_source_digest(self.armed),
        )
        self.assertEqual(plan["readiness_stage"], READY_STAGE)
        self.assertTrue(plan["requires_live_evidence_after_activation"])
        self.assertTrue(plan["activation_does_not_execute_worker_tick"])
        self.assertFalse(plan["real_trading_enabled"])

    def test_plan_blocks_when_runtime_is_not_persisted_armed(self):
        runtime = {
            "status": "CONFIRMED",
            "checkpoint": {},
            "sha": "runtime-sha",
        }
        result = prepare_global_worker_activation_plan(
            self.access,
            runtime,
            self.readiness,
            _safe_flag("UNSET"),
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "PERSISTED_ARMED_STATE_REQUIRED")

    def test_plan_blocks_when_kill_switch_is_active(self):
        runtime = deepcopy(self.runtime)
        raw = runtime["checkpoint"][GLOBAL_WORKER_NAMESPACE]
        raw["kill_switch"] = True
        candidate = dict(raw)
        candidate.pop("digest", None)
        from atlasquant_aion_core_intelligence.evidence import digest
        raw["digest"] = digest(candidate)
        result = prepare_global_worker_activation_plan(
            self.access,
            runtime,
            self.readiness,
            _safe_flag("UNSET"),
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(
            result["reason"],
            {"GLOBAL_KILL_SWITCH_MUST_BE_OFF", "GLOBAL_WORKER_STATE_INVALID"},
        )

    def test_plan_blocks_if_lease_is_already_owned(self):
        runtime = deepcopy(self.runtime)
        raw = runtime["checkpoint"][GLOBAL_WORKER_NAMESPACE]
        raw["lease"] = {
            "owner": "unexpected-runtime",
            "token": "token",
            "fencing_token": 1,
            "acquired_at": NOW.isoformat(),
            "heartbeat_at": NOW.isoformat(),
            "expires_at": (NOW + timedelta(minutes=10)).isoformat(),
        }
        candidate = dict(raw)
        candidate.pop("digest", None)
        from atlasquant_aion_core_intelligence.evidence import digest
        raw["digest"] = digest(candidate)
        result = prepare_global_worker_activation_plan(
            self.access,
            runtime,
            self.readiness,
            _safe_flag("UNSET"),
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["reason"],
            "GLOBAL_LEASE_MUST_BE_EMPTY_BEFORE_ACTIVATION",
        )

    def test_plan_requires_ready_for_flag_enable_evidence(self):
        readiness = deepcopy(self.readiness)
        readiness["activation_stage"] = "READY_FOR_ADMIN_ARMING"
        result = prepare_global_worker_activation_plan(
            self.access,
            self.runtime,
            readiness,
            _safe_flag("UNSET"),
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["reason"],
            "READINESS_NOT_READY_FOR_FLAG_ENABLE",
        )

    def test_plan_blocks_enabled_or_changed_flag_evidence(self):
        enabled = prepare_global_worker_activation_plan(
            self.access,
            self.runtime,
            self.readiness,
            {
                "status": "CONFIRMED",
                "state": "ENABLED",
                "safe_for_arming_persistence": False,
            },
            now=NOW,
        )
        self.assertEqual(enabled["status"], "BLOCKED")
        self.assertEqual(enabled["reason"], "FEATURE_FLAG_NOT_PROVEN_DISABLED")

        readiness = deepcopy(self.readiness)
        readiness["feature_flag"]["state"] = "DISABLED"
        changed = prepare_global_worker_activation_plan(
            self.access,
            self.runtime,
            readiness,
            _safe_flag("UNSET"),
            now=NOW,
        )
        self.assertEqual(changed["status"], "BLOCKED")
        self.assertEqual(changed["reason"], "READINESS_FLAG_EVIDENCE_CHANGED")

    def test_wrong_phrase_and_expired_plan_do_not_create_ticket(self):
        plan = self.plan()
        wrong = approve_global_worker_activation_plan(
            self.access,
            plan,
            confirmation=True,
            confirmation_phrase="ATIVAR",
            now=NOW,
        )
        self.assertEqual(wrong["status"], "BLOCKED")
        self.assertEqual(wrong["reason"], "CONFIRMATION_PHRASE_MISMATCH")

        short = self.plan(ttl=300)
        expired = approve_global_worker_activation_plan(
            self.access,
            short,
            confirmation=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=NOW + timedelta(seconds=301),
        )
        self.assertEqual(expired["status"], "BLOCKED")
        self.assertEqual(expired["reason"], "ACTIVATION_PLAN_EXPIRED")

    def test_activation_ticket_is_integrity_protected_and_scope_bound(self):
        ticket = self.approval()
        self.assertEqual(approval_integrity(ticket)["state"], "MATCH")
        self.assertEqual(ticket["runtime_sha"], "runtime-armed-sha-1")
        other = _access("other", "other-activation-fingerprint-999999")
        result = validate_global_worker_activation_approval(
            other,
            self.runtime,
            ticket,
            now=NOW,
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["reason"], "ACTIVATION_APPROVAL_CONTEXT_MISMATCH")

    def test_ticket_fails_if_runtime_sha_or_digest_changes(self):
        ticket = self.approval()
        changed_sha = deepcopy(self.runtime)
        changed_sha["sha"] = "runtime-armed-sha-2"
        result = validate_global_worker_activation_approval(
            self.access,
            changed_sha,
            ticket,
            now=NOW,
        )
        self.assertEqual(
            result["reason"],
            "ACTIVATION_APPROVAL_RUNTIME_SHA_CHANGED",
        )

        changed_cp = deepcopy(self.runtime)
        changed_cp["checkpoint"]["other"] = "change"
        result = validate_global_worker_activation_approval(
            self.access,
            changed_cp,
            ticket,
            now=NOW,
        )
        self.assertEqual(
            result["reason"],
            "ACTIVATION_APPROVAL_RUNTIME_DIGEST_CHANGED",
        )

    def test_writer_creates_when_unset_and_updates_when_disabled(self):
        create = Mock()
        create.raise_for_status.return_value = None
        with patch(
            "atlasquant_aion_global_worker_activation.github_post",
            return_value=create,
        ) as post:
            result = write_repository_feature_flag_enabled(
                _config(),
                "UNSET",
            )
        post.assert_called_once()
        self.assertEqual(result["status"], "WRITE_ACCEPTED")
        self.assertTrue(result["modified"])
        self.assertFalse(result["raw_value_exposed"])

        update = Mock()
        update.raise_for_status.return_value = None
        with patch(
            "atlasquant_aion_global_worker_activation.github_patch",
            return_value=update,
        ) as patch_call:
            result = write_repository_feature_flag_enabled(
                _config(),
                "DISABLED",
            )
        patch_call.assert_called_once()
        self.assertEqual(result["status"], "WRITE_ACCEPTED")

    def test_safety_disabler_falls_back_to_create_disabled_when_missing(self):
        missing = Mock(status_code=404)
        created = Mock(status_code=201)
        created.raise_for_status.return_value = None
        with patch(
            "atlasquant_aion_global_worker_activation.github_patch",
            return_value=missing,
        ) as patch_call, patch(
            "atlasquant_aion_global_worker_activation.github_post",
            return_value=created,
        ) as post:
            result = force_disable_repository_feature_flag(_config())
        patch_call.assert_called_once()
        post.assert_called_once()
        self.assertEqual(result["status"], "DISABLED")
        self.assertTrue(result["modified"])

    def test_activation_requires_final_confirmation_before_any_reads_or_writes(self):
        ticket = self.approval()
        with patch(
            "atlasquant_aion_global_worker_activation.load_runtime_checkpoint"
        ) as reader:
            result = activate_global_worker_feature_flag(
                self.access,
                self.runtime,
                ticket,
                _config(),
                confirmation=False,
                now=NOW,
            )
        reader.assert_not_called()
        self.assertEqual(
            result["reason"],
            "FINAL_EXPLICIT_CONFIRMATION_REQUIRED",
        )

    def test_activation_reloads_runtime_and_blocks_stale_ticket_before_flag_write(self):
        ticket = self.approval()
        changed = deepcopy(self.runtime)
        changed["sha"] = "new-runtime-sha"
        writer = Mock()
        result = activate_global_worker_feature_flag(
            self.access,
            self.runtime,
            ticket,
            _config(),
            confirmation=True,
            runtime_reader=lambda *args, **kwargs: changed,
            flag_reader=lambda *args, **kwargs: _safe_flag("UNSET"),
            flag_writer=writer,
            now=NOW,
        )
        writer.assert_not_called()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["reason"],
            "ACTIVATION_APPROVAL_RUNTIME_SHA_CHANGED",
        )

    def test_activation_blocks_if_flag_changes_before_write(self):
        ticket = self.approval()
        writer = Mock()
        result = activate_global_worker_feature_flag(
            self.access,
            self.runtime,
            ticket,
            _config(),
            confirmation=True,
            runtime_reader=lambda *args, **kwargs: deepcopy(self.runtime),
            flag_reader=lambda *args, **kwargs: _safe_flag("DISABLED"),
            flag_writer=writer,
            now=NOW,
        )
        writer.assert_not_called()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["reason"],
            "ACTIVATION_APPROVAL_FLAG_STATE_CHANGED",
        )

    def test_success_enables_only_flag_and_requires_future_live_evidence(self):
        ticket = self.approval()
        flags = iter([
            _safe_flag("UNSET"),
            {
                "status": "CONFIRMED",
                "state": "ENABLED",
                "safe_for_arming_persistence": False,
            },
        ])
        runtime_reads = iter([
            deepcopy(self.runtime),
            deepcopy(self.runtime),
        ])
        result = activate_global_worker_feature_flag(
            self.access,
            self.runtime,
            ticket,
            _config(),
            confirmation=True,
            runtime_reader=lambda *args, **kwargs: next(runtime_reads),
            flag_reader=lambda *args, **kwargs: next(flags),
            flag_writer=lambda *args, **kwargs: {
                "status": "WRITE_ACCEPTED",
                "modified": True,
            },
            now=NOW,
        )
        self.assertEqual(result["status"], "ACTIVATED_PENDING_LIVE_EVIDENCE")
        self.assertTrue(result["feature_flag_modified"])
        self.assertFalse(result["global_worker_executed"])
        self.assertFalse(result["live_heartbeat_confirmed"])
        self.assertFalse(result["live_receipt_confirmed"])
        self.assertFalse(result["runtime_checkpoint_modified"])
        self.assertFalse(result["real_trading_enabled"])
        self.assertEqual(
            result["next_required_evidence"],
            "GLOBAL_WORKER_LIVE_HEARTBEAT_AND_RECEIPT",
        )

    def test_runtime_change_after_flag_write_rolls_activation_back(self):
        ticket = self.approval()
        changed = deepcopy(self.runtime)
        changed["sha"] = "changed-after-write"
        flags = iter([
            _safe_flag("UNSET"),
            {
                "status": "CONFIRMED",
                "state": "ENABLED",
                "safe_for_arming_persistence": False,
            },
            _safe_flag("DISABLED"),
        ])
        runtime_reads = iter([
            deepcopy(self.runtime),
            changed,
        ])
        result = activate_global_worker_feature_flag(
            self.access,
            self.runtime,
            ticket,
            _config(),
            confirmation=True,
            runtime_reader=lambda *args, **kwargs: next(runtime_reads),
            flag_reader=lambda *args, **kwargs: next(flags),
            flag_writer=lambda *args, **kwargs: {
                "status": "WRITE_ACCEPTED",
                "modified": True,
            },
            flag_disabler=lambda *args, **kwargs: {
                "status": "DISABLED",
                "modified": True,
            },
            now=NOW,
        )
        self.assertEqual(result["status"], "ACTIVATION_ROLLED_BACK")
        self.assertEqual(result["reason"], "RUNTIME_CHANGED_DURING_ACTIVATION")
        self.assertTrue(result["rollback_verified_safe"])
        self.assertFalse(result["global_worker_executed"])

    def test_failed_post_write_flag_verification_rolls_back(self):
        ticket = self.approval()
        flags = iter([
            _safe_flag("UNSET"),
            {
                "status": "ERROR",
                "state": "UNKNOWN",
                "safe_for_arming_persistence": False,
            },
            _safe_flag("DISABLED"),
        ])
        result = activate_global_worker_feature_flag(
            self.access,
            self.runtime,
            ticket,
            _config(),
            confirmation=True,
            runtime_reader=lambda *args, **kwargs: deepcopy(self.runtime),
            flag_reader=lambda *args, **kwargs: next(flags),
            flag_writer=lambda *args, **kwargs: {
                "status": "WRITE_ACCEPTED",
                "modified": True,
            },
            flag_disabler=lambda *args, **kwargs: {
                "status": "DISABLED",
                "modified": True,
            },
            now=NOW,
        )
        self.assertEqual(result["status"], "ACTIVATION_ROLLED_BACK")
        self.assertEqual(
            result["reason"],
            "FEATURE_FLAG_ENABLE_NOT_CONFIRMED_AFTER_WRITE",
        )

    def test_uncertain_write_that_observes_enabled_attempts_safety_disable(self):
        ticket = self.approval()
        flags = iter([
            _safe_flag("UNSET"),
            {
                "status": "CONFIRMED",
                "state": "ENABLED",
                "safe_for_arming_persistence": False,
            },
            _safe_flag("DISABLED"),
        ])
        result = activate_global_worker_feature_flag(
            self.access,
            self.runtime,
            ticket,
            _config(),
            confirmation=True,
            runtime_reader=lambda *args, **kwargs: deepcopy(self.runtime),
            flag_reader=lambda *args, **kwargs: next(flags),
            flag_writer=lambda *args, **kwargs: {
                "status": "ERROR",
                "modified": False,
                "reason": "TimeoutError",
            },
            flag_disabler=lambda *args, **kwargs: {
                "status": "DISABLED",
                "modified": True,
            },
            now=NOW,
        )
        self.assertEqual(result["status"], "ACTIVATION_ROLLED_BACK")
        self.assertEqual(
            result["reason"],
            "FEATURE_FLAG_WRITE_OUTCOME_UNCERTAIN_AND_ENABLED",
        )

    def test_critical_status_when_safety_disable_cannot_be_confirmed(self):
        ticket = self.approval()
        flags = iter([
            _safe_flag("UNSET"),
            {
                "status": "CONFIRMED",
                "state": "ENABLED",
                "safe_for_arming_persistence": False,
            },
            {
                "status": "ERROR",
                "state": "UNKNOWN",
                "safe_for_arming_persistence": False,
            },
        ])
        result = activate_global_worker_feature_flag(
            self.access,
            self.runtime,
            ticket,
            _config(),
            confirmation=True,
            runtime_reader=lambda *args, **kwargs: deepcopy(self.runtime),
            flag_reader=lambda *args, **kwargs: next(flags),
            flag_writer=lambda *args, **kwargs: {
                "status": "ERROR",
                "modified": False,
            },
            flag_disabler=lambda *args, **kwargs: {
                "status": "ERROR",
                "modified": False,
            },
            now=NOW,
        )
        self.assertEqual(
            result["status"],
            "CRITICAL_ACTIVATION_ROLLBACK_FAILED",
        )

    def test_deactivation_requires_exact_phrase_and_confirms_disabled_state(self):
        wrong = deactivate_global_worker_feature_flag(
            self.access,
            _config(),
            confirmation=True,
            confirmation_phrase="DESATIVAR",
            flag_reader=lambda *args, **kwargs: {
                "status": "CONFIRMED",
                "state": "ENABLED",
            },
        )
        self.assertEqual(wrong["status"], "BLOCKED")

        flags = iter([
            {
                "status": "CONFIRMED",
                "state": "ENABLED",
            },
            _safe_flag("DISABLED"),
        ])
        result = deactivate_global_worker_feature_flag(
            self.access,
            _config(),
            confirmation=True,
            confirmation_phrase=DEACTIVATION_PHRASE,
            flag_reader=lambda *args, **kwargs: next(flags),
            flag_disabler=lambda *args, **kwargs: {
                "status": "DISABLED",
                "modified": True,
            },
        )
        self.assertEqual(result["status"], "DISABLED")
        self.assertTrue(result["feature_flag_modified"])
        self.assertFalse(result["global_worker_executed"])

    def test_live_readiness_collector_is_read_only_and_can_return_ready_for_flag_enable(self):
        workflow = """name: AtlasQuant - Automatic Scanner + Autopilot
on:
  schedule:
    - cron: "7,37 * * * *"
permissions:
  contents: write
jobs:
  x:
    env:
      GITHUB_DATA_BRANCH: "atlasquant-runtime"
    steps:
      - name: AION Global Worker tick
        if: ${{ vars.ATLASQUANT_AION_GLOBAL_WORKER_ENABLED == '1' }}
        run: python atlasquant_aion_global_worker.py --tick
"""
        temp = Path("activation-readiness-workflow-test.yml")
        temp.write_text(workflow, encoding="utf-8")
        try:
            pulses = [
                {
                    "event": "schedule",
                    "status": "completed",
                    "conclusion": "success",
                    "created_at": (NOW - timedelta(minutes=minutes)).isoformat(),
                }
                for minutes in (10, 40, 70, 100, 130)
            ]
            result = collect_activation_readiness_evidence(
                _config(),
                self.runtime,
                now=NOW,
                flag_reader=lambda *args, **kwargs: _safe_flag("UNSET"),
                pulse_reader=lambda *args, **kwargs: {
                    "status": "CONFIRMED",
                    "runs": pulses,
                },
                workflow_path=str(temp),
            )
        finally:
            temp.unlink(missing_ok=True)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["activation_stage"], READY_STAGE)
        self.assertTrue(result["read_only"])
        self.assertFalse(result["runtime_modified"])
        self.assertFalse(result["feature_flag_modified"])
        self.assertFalse(result["global_worker_executed"])

    def test_admin_ui_exposes_guarded_activation_and_safety_stop(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Global Worker Activation Ceremony", source)
        self.assertIn("Verificar readiness atual para ativação", source)
        self.assertIn("Gerar plano de ativação", source)
        self.assertIn("ATIVAR WORKER GLOBAL", source)
        self.assertIn("Criar autorização de ativação", source)
        self.assertIn("CONFIRMAÇÃO FINAL", source)
        self.assertIn("Habilitar Worker Global (feature flag)", source)
        self.assertIn("ACTIVATED_PENDING_LIVE_EVIDENCE", source)
        self.assertIn("DESATIVAR WORKER GLOBAL", source)
        self.assertIn("Desativar feature flag do Worker Global", source)
        self.assertIn('guardian_decision(\n                "write_runtime"', source)

    def test_activation_module_does_not_touch_checkpoint_or_execute_worker(self):
        source = Path(
            "atlasquant_aion_global_worker_activation.py"
        ).read_text(encoding="utf-8")
        for banned in (
            "requests.put(",
            "requests.delete(",
            "save_runtime_checkpoint(",
            "run_global_worker_once(",
            "worker_tick(",
            "subprocess.",
            "os.system(",
            "/dispatches",
            "real_trade(",
            "payment_executed = True",
            "publication_executed = True",
        ):
            self.assertNotIn(banned, source)
        self.assertNotIn("requests.post(", source)
        self.assertNotIn("requests.patch(", source)
        self.assertIn("github_post(", source)
        self.assertIn("github_patch(", source)


if __name__ == "__main__":
    unittest.main()
