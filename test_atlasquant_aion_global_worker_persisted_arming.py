import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from atlasquant_aion_global_worker import stage_arm_global_worker
from atlasquant_aion_global_worker_arming import (
    CONFIRMATION_PHRASE as ARM_PHRASE,
    approve_global_worker_arming_plan,
    prepare_global_worker_arming_plan,
)
from atlasquant_aion_global_worker_persisted_arming import (
    CONFIRMATION_PHRASE,
    approve_persisted_arming_plan,
    persisted_arming_transition_required,
    persist_staged_global_arming,
    prepare_persisted_arming_plan,
    read_repository_feature_flag,
    validate_persisted_arming_approval,
)
from atlasquant_aion_memory import (
    RuntimeConfig,
    checkpoint_integrity_report,
    ensure_operating_checkpoint,
    save_runtime_checkpoint,
)


NOW = datetime(2026, 9, 28, 15, 0, tzinfo=timezone.utc)


def _access(username="mikael", fingerprint="persist-admin-fingerprint-1234567890"):
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


def _config(token="test-token"):
    return RuntimeConfig(
        token=token,
        repo="owner/repo",
        branch="atlasquant-runtime",
    )


def _source_checkpoint():
    return ensure_operating_checkpoint({})


def _staged_armed(source=None):
    source = deepcopy(source or _source_checkpoint())
    access = _access()
    plan = prepare_global_worker_arming_plan(
        access,
        source,
        max_jobs=5,
        lease_seconds=600,
        approval_ttl_seconds=900,
        now=NOW,
    )
    approved = approve_global_worker_arming_plan(
        access,
        plan["plan"],
        confirmation=True,
        confirmation_phrase=ARM_PHRASE,
        now=NOW,
    )
    staged = stage_arm_global_worker(
        access,
        source,
        confirmation=True,
        arming_approval=approved["approval"],
        max_jobs=5,
        lease_seconds=600,
        now=NOW,
    )
    assert staged["status"] == "STAGED_ARMED"
    return staged["checkpoint"]


def _runtime(source=None, sha="runtime-sha-1"):
    cp = deepcopy(source or _source_checkpoint())
    return {
        "status": "CONFIRMED",
        "checkpoint": cp,
        "sha": sha,
        "integrity": checkpoint_integrity_report(cp),
        "source": "GitHub:atlasquant-runtime:dados/aion/checkpoint_master.json",
    }


def _safe_flag(state="UNSET"):
    return {
        "status": "CONFIRMED",
        "state": state,
        "safe_for_arming_persistence": state in {"UNSET", "DISABLED"},
        "variable_present": state != "UNSET",
        "raw_value_exposed": False,
    }


class PersistedGlobalWorkerArmingTests(unittest.TestCase):
    def setUp(self):
        self.access = _access()
        self.source = _source_checkpoint()
        self.working = _staged_armed(self.source)
        self.runtime = _runtime(self.source)

    def persistence_plan(self, *, ttl=600):
        result = prepare_persisted_arming_plan(
            self.access,
            self.working,
            self.runtime,
            _safe_flag(),
            ttl_seconds=ttl,
            now=NOW,
        )
        self.assertEqual(result["status"], "PERSISTENCE_PLAN_READY")
        return result["plan"]

    def persistence_approval(self, *, ttl=600):
        plan = self.persistence_plan(ttl=ttl)
        result = approve_persisted_arming_plan(
            self.access,
            plan,
            confirmation=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=NOW,
        )
        self.assertEqual(result["status"], "APPROVED_FOR_PERSISTENCE")
        return result["approval"]

    def test_transition_required_only_for_new_or_changed_armed_state(self):
        self.assertTrue(
            persisted_arming_transition_required(self.working, self.source)
        )
        self.assertFalse(
            persisted_arming_transition_required(self.working, self.working)
        )
        nonarmed = deepcopy(self.source)
        self.assertFalse(
            persisted_arming_transition_required(nonarmed, self.source)
        )

    def test_transition_required_when_armed_contract_changes(self):
        persisted = deepcopy(self.working)
        changed = deepcopy(self.working)
        changed["aion_global_worker_v1"]["max_jobs"] = 4
        changed["aion_global_worker_v1"]["resource_budgets"]["max_jobs_per_tick"] = 4
        self.assertTrue(
            persisted_arming_transition_required(changed, persisted)
        )

    def test_feature_flag_reader_requires_authoritative_token(self):
        result = read_repository_feature_flag(_config(token=""))
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertFalse(result["safe_for_arming_persistence"])

    def test_feature_flag_reader_proves_unset_without_exposing_value(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "total_count": 1,
            "variables": [{"name": "OTHER_FLAG", "value": "secret-ish"}],
        }
        with patch(
            "atlasquant_aion_global_worker_persisted_arming.github_get",
            return_value=response,
        ) as get:
            result = read_repository_feature_flag(_config())
        get.assert_called_once()
        self.assertEqual(result["status"], "CONFIRMED")
        self.assertEqual(result["state"], "UNSET")
        self.assertTrue(result["safe_for_arming_persistence"])
        self.assertFalse(result["raw_value_exposed"])
        self.assertNotIn("value", result)

    def test_feature_flag_reader_distinguishes_disabled_and_enabled(self):
        for raw, expected, safe in (
            ("0", "DISABLED", True),
            ("false", "DISABLED", True),
            ("1", "ENABLED", False),
            ("true", "ENABLED", False),
        ):
            response = Mock()
            response.raise_for_status.return_value = None
            response.json.return_value = {
                "variables": [
                    {
                        "name": "ATLASQUANT_AION_GLOBAL_WORKER_ENABLED",
                        "value": raw,
                    }
                ]
            }
            with patch(
                "atlasquant_aion_global_worker_persisted_arming.github_get",
                return_value=response,
            ):
                result = read_repository_feature_flag(_config())
            self.assertEqual(result["state"], expected)
            self.assertEqual(result["safe_for_arming_persistence"], safe)

    def test_persistence_plan_binds_working_digest_runtime_sha_and_rollback(self):
        plan = self.persistence_plan()
        self.assertEqual(plan["source_runtime_sha"], "runtime-sha-1")
        self.assertTrue(plan["working_checkpoint_digest"])
        self.assertTrue(plan["source_runtime_checkpoint_digest"])
        self.assertTrue(plan["arming_plan_digest"])
        self.assertTrue(plan["arming_approval_digest"])
        self.assertTrue(plan["arm_digest"])
        self.assertEqual(plan["feature_flag_state"], "UNSET")
        self.assertTrue(plan["feature_flag_proof_required_again_before_write"])
        self.assertTrue(plan["feature_flag_proof_required_after_write"])
        self.assertEqual(
            plan["rollback"]["source_runtime_sha"],
            "runtime-sha-1",
        )
        self.assertTrue(
            plan["rollback"]["automatic_on_post_write_flag_violation"]
        )
        self.assertFalse(plan["runtime_modified"])
        self.assertFalse(plan["feature_flag_modified"])

    def test_persistence_plan_blocks_when_flag_not_proven_disabled(self):
        result = prepare_persisted_arming_plan(
            self.access,
            self.working,
            self.runtime,
            {
                "status": "CONFIRMED",
                "state": "ENABLED",
                "safe_for_arming_persistence": False,
            },
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "FEATURE_FLAG_NOT_PROVEN_DISABLED")

    def test_persistence_plan_blocks_without_new_armed_transition(self):
        runtime = _runtime(self.working)
        result = prepare_persisted_arming_plan(
            self.access,
            self.working,
            runtime,
            _safe_flag(),
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "NO_NEW_ARMED_TRANSITION")

    def test_wrong_persistence_phrase_and_confirmation_are_blocked(self):
        plan = self.persistence_plan()
        no_confirm = approve_persisted_arming_plan(
            self.access,
            plan,
            confirmation=False,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=NOW,
        )
        self.assertEqual(no_confirm["reason"], "EXPLICIT_CONFIRMATION_REQUIRED")
        wrong = approve_persisted_arming_plan(
            self.access,
            plan,
            confirmation=True,
            confirmation_phrase="PERSISTIR",
            now=NOW,
        )
        self.assertEqual(wrong["reason"], "CONFIRMATION_PHRASE_MISMATCH")

    def test_persistence_approval_expires_and_binds_runtime_sha(self):
        approval = self.persistence_approval(ttl=300)
        expired = validate_persisted_arming_approval(
            self.access,
            self.working,
            self.runtime,
            approval,
            now=NOW + timedelta(seconds=301),
        )
        self.assertEqual(expired["reason"], "PERSISTENCE_APPROVAL_EXPIRED")

        changed_runtime = deepcopy(self.runtime)
        changed_runtime["sha"] = "runtime-sha-2"
        changed = validate_persisted_arming_approval(
            self.access,
            self.working,
            changed_runtime,
            approval,
            now=NOW,
        )
        self.assertEqual(
            changed["reason"],
            "PERSISTENCE_APPROVAL_RUNTIME_SHA_CHANGED",
        )

    def test_persistence_approval_binds_exact_working_checkpoint(self):
        approval = self.persistence_approval()
        changed = deepcopy(self.working)
        changed["unrelated_change"] = True
        result = validate_persisted_arming_approval(
            self.access,
            changed,
            self.runtime,
            approval,
            now=NOW,
        )
        self.assertEqual(
            result["reason"],
            "PERSISTENCE_APPROVAL_WORKING_CHECKPOINT_CHANGED",
        )

    def test_direct_generic_save_blocks_new_armed_transition_before_put(self):
        with patch(
            "atlasquant_aion_memory.load_runtime_checkpoint",
            return_value=self.runtime,
        ), patch(
            "requests.put"
        ) as put:
            result = save_runtime_checkpoint(
                self.working,
                _config(),
                approved=True,
                expected_sha="runtime-sha-1",
            )
        put.assert_not_called()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("Persisted Arming Ceremony", result["reason"])

    def test_generic_save_blocks_mutated_armed_contract_even_if_already_armed(self):
        persisted = deepcopy(self.working)
        changed = deepcopy(self.working)
        changed["aion_global_worker_v1"]["max_jobs"] = 4
        changed["aion_global_worker_v1"]["resource_budgets"]["max_jobs_per_tick"] = 4
        raw = changed["aion_global_worker_v1"]
        candidate = dict(raw)
        candidate.pop("digest", None)
        from atlasquant_aion_core_intelligence.evidence import digest as evidence_digest
        raw["digest"] = evidence_digest(candidate)

        runtime = _runtime(persisted)
        with patch(
            "atlasquant_aion_memory.load_runtime_checkpoint",
            return_value=runtime,
        ), patch(
            "requests.put"
        ) as put:
            result = save_runtime_checkpoint(
                changed,
                _config(),
                approved=True,
                expected_sha=runtime["sha"],
            )
        put.assert_not_called()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("Persisted Arming Ceremony", result["reason"])

    def test_guarded_persist_requires_second_confirmation(self):
        approval = self.persistence_approval()
        with patch(
            "atlasquant_aion_global_worker_persisted_arming.save_runtime_checkpoint"
        ) as save:
            result = persist_staged_global_arming(
                self.access,
                self.working,
                self.runtime,
                approval,
                _config(),
                confirmation=False,
                now=NOW,
            )
        save.assert_not_called()
        self.assertEqual(result["reason"], "SECOND_EXPLICIT_CONFIRMATION_REQUIRED")

    def test_guarded_persist_rechecks_flag_before_write(self):
        approval = self.persistence_approval()
        with patch(
            "atlasquant_aion_global_worker_persisted_arming.save_runtime_checkpoint"
        ) as save:
            result = persist_staged_global_arming(
                self.access,
                self.working,
                self.runtime,
                approval,
                _config(),
                confirmation=True,
                flag_reader=lambda *args, **kwargs: {
                    "status": "CONFIRMED",
                    "state": "ENABLED",
                    "safe_for_arming_persistence": False,
                },
                now=NOW,
            )
        save.assert_not_called()
        self.assertEqual(
            result["reason"],
            "FEATURE_FLAG_NOT_PROVEN_DISABLED_BEFORE_WRITE",
        )

    def test_guarded_persist_success_uses_authorized_transition_and_keeps_flag_separate(self):
        approval = self.persistence_approval()
        calls = []
        def fake_save(checkpoint, config, **kwargs):
            calls.append((deepcopy(checkpoint), dict(kwargs)))
            return {
                "status": "CONFIRMED",
                "saved": True,
                "verified": True,
                "sha": "armed-sha-2",
                "checkpoint": deepcopy(self.working),
            }

        with patch(
            "atlasquant_aion_global_worker_persisted_arming.save_runtime_checkpoint",
            side_effect=fake_save,
        ):
            result = persist_staged_global_arming(
                self.access,
                self.working,
                self.runtime,
                approval,
                _config(),
                confirmation=True,
                flag_reader=lambda *args, **kwargs: _safe_flag("UNSET"),
                now=NOW,
            )

        self.assertEqual(result["status"], "CONFIRMED")
        self.assertTrue(result["saved"])
        self.assertTrue(result["verified"])
        self.assertTrue(result["arming_persisted"])
        self.assertEqual(result["feature_flag_state"], "UNSET")
        self.assertFalse(result["feature_flag_modified"])
        self.assertFalse(result["global_worker_executed"])
        self.assertFalse(result["real_trading_enabled"])
        self.assertFalse(result["rollback_performed"])
        self.assertEqual(len(calls), 1)
        self.assertTrue(
            calls[0][1]["allow_global_arming_transition"]
        )
        self.assertEqual(
            calls[0][1]["expected_sha"],
            "runtime-sha-1",
        )

    def test_post_write_armed_state_mismatch_triggers_rollback(self):
        approval = self.persistence_approval()
        calls = []
        mismatched = deepcopy(self.working)
        mismatched["aion_global_worker_v1"]["arm_digest"] = "different-arm"
        raw = mismatched["aion_global_worker_v1"]
        candidate = dict(raw)
        candidate.pop("digest", None)
        from atlasquant_aion_core_intelligence.evidence import digest as evidence_digest
        raw["digest"] = evidence_digest(candidate)

        def fake_save(checkpoint, config, **kwargs):
            calls.append((deepcopy(checkpoint), dict(kwargs)))
            if len(calls) == 1:
                return {
                    "status": "CONFIRMED",
                    "saved": True,
                    "verified": True,
                    "sha": "armed-sha-2",
                    "checkpoint": mismatched,
                }
            return {
                "status": "CONFIRMED",
                "saved": True,
                "verified": True,
                "sha": "rollback-sha-3",
                "checkpoint": deepcopy(self.source),
            }

        with patch(
            "atlasquant_aion_global_worker_persisted_arming.save_runtime_checkpoint",
            side_effect=fake_save,
        ):
            result = persist_staged_global_arming(
                self.access,
                self.working,
                self.runtime,
                approval,
                _config(),
                confirmation=True,
                flag_reader=lambda *args, **kwargs: _safe_flag("UNSET"),
                now=NOW,
            )

        self.assertEqual(result["status"], "ROLLED_BACK")
        self.assertEqual(
            result["reason"],
            "PERSISTED_ARMED_STATE_DID_NOT_MATCH_STAGED_STATE",
        )
        self.assertTrue(result["rollback_performed"])
        self.assertEqual(len(calls), 2)

    def test_post_write_enabled_flag_triggers_automatic_cas_rollback(self):
        approval = self.persistence_approval()
        flag_reads = iter([
            _safe_flag("UNSET"),
            {
                "status": "CONFIRMED",
                "state": "ENABLED",
                "safe_for_arming_persistence": False,
            },
        ])
        calls = []
        def fake_save(checkpoint, config, **kwargs):
            calls.append((deepcopy(checkpoint), dict(kwargs)))
            if len(calls) == 1:
                return {
                    "status": "CONFIRMED",
                    "saved": True,
                    "verified": True,
                    "sha": "armed-sha-2",
                    "checkpoint": deepcopy(self.working),
                }
            return {
                "status": "CONFIRMED",
                "saved": True,
                "verified": True,
                "sha": "rollback-sha-3",
                "checkpoint": deepcopy(self.source),
            }

        with patch(
            "atlasquant_aion_global_worker_persisted_arming.save_runtime_checkpoint",
            side_effect=fake_save,
        ):
            result = persist_staged_global_arming(
                self.access,
                self.working,
                self.runtime,
                approval,
                _config(),
                confirmation=True,
                flag_reader=lambda *args, **kwargs: next(flag_reads),
                now=NOW,
            )

        self.assertEqual(result["status"], "ROLLED_BACK")
        self.assertTrue(result["rollback_performed"])
        self.assertFalse(result["saved"])
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0][1]["allow_global_arming_transition"])
        self.assertNotIn("allow_global_arming_transition", calls[1][1])
        self.assertEqual(calls[1][1]["expected_sha"], "armed-sha-2")
        self.assertEqual(calls[1][0], self.source)

    def test_post_write_flag_violation_reports_critical_when_rollback_fails(self):
        approval = self.persistence_approval()
        flag_reads = iter([
            _safe_flag("DISABLED"),
            {
                "status": "ERROR",
                "state": "UNKNOWN",
                "safe_for_arming_persistence": False,
            },
        ])
        calls = []
        def fake_save(checkpoint, config, **kwargs):
            calls.append((deepcopy(checkpoint), dict(kwargs)))
            if len(calls) == 1:
                return {
                    "status": "CONFIRMED",
                    "saved": True,
                    "verified": True,
                    "sha": "armed-sha-2",
                    "checkpoint": deepcopy(self.working),
                }
            return {
                "status": "CONFLICT",
                "saved": False,
                "verified": False,
                "reason": "runtime changed",
            }

        with patch(
            "atlasquant_aion_global_worker_persisted_arming.save_runtime_checkpoint",
            side_effect=fake_save,
        ):
            result = persist_staged_global_arming(
                self.access,
                self.working,
                self.runtime,
                approval,
                _config(),
                confirmation=True,
                flag_reader=lambda *args, **kwargs: next(flag_reads),
                now=NOW,
            )

        self.assertEqual(result["status"], "CRITICAL_ROLLBACK_FAILED")
        self.assertFalse(result["rollback_performed"])
        self.assertTrue(result["saved"])

    def test_admin_ui_blocks_generic_save_and_exposes_second_ceremony(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Persisted Arming Ceremony", source)
        self.assertIn("Verificar feature flag antes da persistência", source)
        self.assertIn("Gerar plano de persistência ARMED", source)
        self.assertIn("Criar autorização de persistência", source)
        self.assertIn("PERSISTIR WORKER GLOBAL ARMADO", source)
        self.assertIn("SEGUNDA CONFIRMAÇÃO", source)
        self.assertIn("Persistir ARMED no Checkpoint Mestre", source)
        self.assertIn(
            "O save genérico está BLOQUEADO",
            source,
        )
        self.assertIn(
            "or persisted_arm_required",
            source,
        )

    def test_persisted_arming_module_never_mutates_repository_variable(self):
        source = Path(
            "atlasquant_aion_global_worker_persisted_arming.py"
        ).read_text(encoding="utf-8")
        for banned in (
            "requests.put(",
            "requests.post(",
            "requests.patch(",
            "requests.delete(",
            "/actions/variables/",
            "set_repository_variable",
            "update_repository_variable",
        ):
            self.assertNotIn(banned, source)
        self.assertNotIn("requests.get(", source)
        self.assertIn("github_get(", source)

    def test_other_admin_cannot_use_persistence_ticket(self):
        approval = self.persistence_approval()
        other = _access(
            username="other",
            fingerprint="other-persist-fingerprint-9999999",
        )
        result = validate_persisted_arming_approval(
            other,
            self.working,
            self.runtime,
            approval,
            now=NOW,
        )
        self.assertEqual(
            result["reason"],
            "PERSISTENCE_APPROVAL_CONTEXT_MISMATCH",
        )


if __name__ == "__main__":
    unittest.main()
