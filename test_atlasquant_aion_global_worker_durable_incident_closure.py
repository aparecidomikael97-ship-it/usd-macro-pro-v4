import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from atlasquant_aion_global_worker_durable_incident_closure import (
    CONFIRMATION_PHRASE,
    LEDGER_NAMESPACE,
    approve_durable_closure_plan,
    build_durable_closure_checkpoint,
    durable_record_state,
    load_closure_ledger,
    persist_human_incident_closure_record,
    prepare_durable_closure_plan,
    validate_durable_closure_approval,
)
from atlasquant_aion_global_worker_human_incident_closure import (
    CONFIRMATION_PHRASE as HUMAN_CLOSE_PHRASE,
    record_human_incident_closure,
)
from atlasquant_aion_memory import (
    RuntimeConfig,
    checkpoint_integrity_report,
    ensure_operating_checkpoint,
)


NOW = datetime(2026, 9, 28, 18, 30, tzinfo=timezone.utc)


def _access(username="mikael", fingerprint="durable-close-admin-1234567890"):
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


def _checkpoint():
    return ensure_operating_checkpoint({})


def _runtime(checkpoint=None, sha="runtime-sha-1"):
    cp = deepcopy(checkpoint or _checkpoint())
    return {
        "status": "CONFIRMED",
        "checkpoint": cp,
        "sha": sha,
        "integrity": checkpoint_integrity_report(cp),
        "source": "GitHub:atlasquant-runtime:dados/aion/checkpoint_master.json",
    }


def _flag(state="DISABLED"):
    return {
        "status": "CONFIRMED",
        "state": state,
        "raw_value_exposed": False,
    }


def _assessment():
    return {
        "status": "CLOSURE_REVIEW_READY",
        "closure_review_ready": True,
        "closure_package_digest": "c" * 64,
        "incident_evidence_digest": "i" * 64,
        "remediation_digest": "r" * 64,
        "assessed_at": (NOW - timedelta(minutes=20)).isoformat(),
        "incident_closed": False,
        "automatic_closure": False,
        "human_closure_required": True,
        "reactivation_authorized": False,
    }


def _human_record(note="Evidência revisada."):
    result = record_human_incident_closure(
        _assessment(),
        human_confirmation=True,
        evidence_acknowledged=True,
        reactivation_separation_acknowledged=True,
        confirmation_phrase=HUMAN_CLOSE_PHRASE,
        operator_note=note,
        now=NOW - timedelta(minutes=10),
    )
    assert result["status"] == "HUMAN_CLOSURE_DECISION_RECORDED_SESSION_ONLY"
    return result


class DurableIncidentClosureTests(unittest.TestCase):
    def setUp(self):
        self.access = _access()
        self.source = _checkpoint()
        self.runtime = _runtime(self.source)
        self.human = _human_record()

    def plan(self, *, flag_state="DISABLED", ttl=600):
        result = prepare_durable_closure_plan(
            self.access,
            self.human,
            self.runtime,
            _flag(flag_state),
            ttl_seconds=ttl,
            now=NOW,
        )
        self.assertEqual(result["status"], "DURABLE_CLOSURE_PLAN_READY")
        return result["plan"]

    def approval(self, *, flag_state="DISABLED", ttl=600):
        plan = self.plan(flag_state=flag_state, ttl=ttl)
        result = approve_durable_closure_plan(
            self.access,
            plan,
            confirmation=True,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=NOW,
        )
        self.assertEqual(
            result["status"],
            "APPROVED_FOR_DURABLE_CLOSURE_PERSISTENCE",
        )
        return result["approval"]

    def test_plan_binds_runtime_flag_worker_and_human_record(self):
        plan = self.plan(flag_state="ENABLED")
        self.assertEqual(plan["source_runtime_sha"], "runtime-sha-1")
        self.assertTrue(plan["source_runtime_checkpoint_digest"])
        self.assertTrue(plan["source_worker_state_digest"])
        self.assertTrue(plan["source_ledger_digest"])
        self.assertEqual(
            plan["closure_record_id"],
            self.human["closure_record_id"],
        )
        self.assertEqual(
            plan["closure_record_digest"],
            self.human["closure_record_digest"],
        )
        self.assertEqual(plan["feature_flag_state"], "ENABLED")
        self.assertTrue(plan["feature_flag_must_remain_unchanged"])
        self.assertTrue(plan["worker_state_must_remain_unchanged"])
        self.assertFalse(plan["reactivation_authorized"])

    def test_plan_rejects_tampered_human_closure_record(self):
        changed = deepcopy(self.human)
        changed["operator_note"] = "adulterado"
        result = prepare_durable_closure_plan(
            self.access,
            changed,
            self.runtime,
            _flag(),
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["reason"],
            "HUMAN_CLOSURE_RECORD_INTEGRITY_MISMATCH",
        )

    def test_plan_requires_authoritative_known_flag_state(self):
        result = prepare_durable_closure_plan(
            self.access,
            self.human,
            self.runtime,
            {"status": "ERROR", "state": "UNKNOWN"},
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["reason"],
            "AUTHORITATIVE_FEATURE_FLAG_EVIDENCE_REQUIRED",
        )

    def test_wrong_phrase_and_missing_confirmation_are_blocked(self):
        plan = self.plan()
        no_confirm = approve_durable_closure_plan(
            self.access,
            plan,
            confirmation=False,
            confirmation_phrase=CONFIRMATION_PHRASE,
            now=NOW,
        )
        self.assertEqual(
            no_confirm["reason"],
            "EXPLICIT_CONFIRMATION_REQUIRED",
        )
        wrong = approve_durable_closure_plan(
            self.access,
            plan,
            confirmation=True,
            confirmation_phrase="PERSISTIR",
            now=NOW,
        )
        self.assertEqual(
            wrong["reason"],
            "CONFIRMATION_PHRASE_MISMATCH",
        )

    def test_approval_expires_and_binds_runtime_sha(self):
        approval = self.approval(ttl=300)
        expired = validate_durable_closure_approval(
            self.access,
            self.human,
            self.runtime,
            approval,
            now=NOW + timedelta(seconds=301),
        )
        self.assertEqual(
            expired["reason"],
            "DURABLE_CLOSURE_APPROVAL_EXPIRED",
        )
        changed = deepcopy(self.runtime)
        changed["sha"] = "runtime-sha-2"
        result = validate_durable_closure_approval(
            self.access,
            self.human,
            changed,
            approval,
            now=NOW,
        )
        self.assertEqual(
            result["reason"],
            "DURABLE_CLOSURE_RUNTIME_SHA_CHANGED",
        )

    def test_build_checkpoint_appends_verified_ledger_record(self):
        updated = build_durable_closure_checkpoint(
            self.source,
            self.human,
            actor_id="actor-1",
            source_runtime_sha="runtime-sha-1",
            source_runtime_checkpoint_digest="source-digest",
            feature_flag_state="DISABLED",
            now=NOW,
        )
        ledger, status = load_closure_ledger(updated)
        self.assertEqual(status["state"], "CONNECTED")
        self.assertEqual(ledger["record_count"], 1)
        self.assertEqual(
            ledger["latest_record_id"],
            self.human["closure_record_id"],
        )
        state = durable_record_state(
            updated,
            closure_record_id=self.human["closure_record_id"],
            closure_record_digest=self.human["closure_record_digest"],
        )
        self.assertEqual(state["state"], "PERSISTED")
        row = state["record"]
        self.assertEqual(row["human_closure_decision"], "APPROVED")
        self.assertFalse(
            row["authoritative_incident_center_status_modified"]
        )
        self.assertFalse(row["reactivation_authorized"])
        self.assertFalse(row["global_worker_modified"])

    def test_build_is_idempotent_for_same_record(self):
        first = build_durable_closure_checkpoint(
            self.source,
            self.human,
            actor_id="actor-1",
            source_runtime_sha="runtime-sha-1",
            source_runtime_checkpoint_digest="source-digest",
            feature_flag_state="DISABLED",
            now=NOW,
        )
        second = build_durable_closure_checkpoint(
            first,
            self.human,
            actor_id="actor-1",
            source_runtime_sha="runtime-sha-2",
            source_runtime_checkpoint_digest="other",
            feature_flag_state="DISABLED",
            now=NOW + timedelta(minutes=1),
        )
        self.assertEqual(
            first[LEDGER_NAMESPACE],
            second[LEDGER_NAMESPACE],
        )

    def test_plan_reports_already_persisted_without_new_write_plan(self):
        persisted = build_durable_closure_checkpoint(
            self.source,
            self.human,
            actor_id="actor-1",
            source_runtime_sha="runtime-sha-1",
            source_runtime_checkpoint_digest="source-digest",
            feature_flag_state="DISABLED",
            now=NOW,
        )
        result = prepare_durable_closure_plan(
            self.access,
            self.human,
            _runtime(persisted),
            _flag(),
            now=NOW,
        )
        self.assertEqual(result["status"], "ALREADY_PERSISTED")

    def test_guarded_persist_requires_second_confirmation(self):
        approval = self.approval()
        calls = []
        result = persist_human_incident_closure_record(
            self.access,
            self.human,
            self.runtime,
            approval,
            _config(),
            confirmation=False,
            saver=lambda *args, **kwargs: calls.append((args, kwargs)),
            now=NOW,
        )
        self.assertEqual(
            result["reason"],
            "SECOND_EXPLICIT_CONFIRMATION_REQUIRED",
        )
        self.assertEqual(calls, [])

    def test_guarded_persist_rechecks_flag_before_write(self):
        approval = self.approval(flag_state="DISABLED")
        calls = []
        result = persist_human_incident_closure_record(
            self.access,
            self.human,
            self.runtime,
            approval,
            _config(),
            confirmation=True,
            flag_reader=lambda *args, **kwargs: _flag("ENABLED"),
            saver=lambda *args, **kwargs: calls.append((args, kwargs)),
            now=NOW,
        )
        self.assertEqual(
            result["reason"],
            "FEATURE_FLAG_CHANGED_BEFORE_DURABLE_CLOSURE_WRITE",
        )
        self.assertEqual(calls, [])

    def test_guarded_persist_success_keeps_worker_and_flag_separate(self):
        approval = self.approval(flag_state="ENABLED")
        calls = []

        def fake_save(checkpoint, config, **kwargs):
            calls.append((deepcopy(checkpoint), dict(kwargs)))
            return {
                "status": "CONFIRMED",
                "saved": True,
                "verified": True,
                "sha": "closure-sha-2",
                "checkpoint": deepcopy(checkpoint),
            }

        result = persist_human_incident_closure_record(
            self.access,
            self.human,
            self.runtime,
            approval,
            _config(),
            confirmation=True,
            flag_reader=lambda *args, **kwargs: _flag("ENABLED"),
            saver=fake_save,
            now=NOW,
        )
        self.assertEqual(result["status"], "CONFIRMED")
        self.assertTrue(result["durable_closure_persisted"])
        self.assertTrue(result["shared_closure_record_persisted"])
        self.assertFalse(
            result["authoritative_incident_center_status_modified"]
        )
        self.assertFalse(result["feature_flag_modified"])
        self.assertFalse(result["global_worker_modified"])
        self.assertFalse(result["reactivation_authorized"])
        self.assertFalse(result["real_trading_enabled"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1]["expected_sha"], "runtime-sha-1")
        self.assertNotIn("allow_global_arming_transition", calls[0][1])

    def test_post_write_worker_change_triggers_rollback(self):
        approval = self.approval()
        calls = []

        def fake_save(checkpoint, config, **kwargs):
            calls.append((deepcopy(checkpoint), dict(kwargs)))
            if len(calls) == 1:
                changed = deepcopy(checkpoint)
                changed["aion_global_worker_v1"] = {
                    "state": "ARMED",
                    "unexpected": True,
                }
                return {
                    "status": "CONFIRMED",
                    "saved": True,
                    "verified": True,
                    "sha": "closure-sha-2",
                    "checkpoint": changed,
                }
            return {
                "status": "CONFIRMED",
                "saved": True,
                "verified": True,
                "sha": "rollback-sha-3",
                "checkpoint": deepcopy(self.source),
            }

        result = persist_human_incident_closure_record(
            self.access,
            self.human,
            self.runtime,
            approval,
            _config(),
            confirmation=True,
            flag_reader=lambda *args, **kwargs: _flag("DISABLED"),
            saver=fake_save,
            now=NOW,
        )
        self.assertEqual(result["status"], "ROLLED_BACK")
        self.assertEqual(
            result["reason"],
            "GLOBAL_WORKER_STATE_CHANGED_DURING_CLOSURE_PERSISTENCE",
        )
        self.assertTrue(result["rollback_performed"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1][0], self.source)

    def test_post_write_flag_change_triggers_rollback(self):
        approval = self.approval(flag_state="DISABLED")
        flags = iter([_flag("DISABLED"), _flag("ENABLED")])
        calls = []

        def fake_save(checkpoint, config, **kwargs):
            calls.append((deepcopy(checkpoint), dict(kwargs)))
            if len(calls) == 1:
                return {
                    "status": "CONFIRMED",
                    "saved": True,
                    "verified": True,
                    "sha": "closure-sha-2",
                    "checkpoint": deepcopy(checkpoint),
                }
            return {
                "status": "CONFIRMED",
                "saved": True,
                "verified": True,
                "sha": "rollback-sha-3",
                "checkpoint": deepcopy(self.source),
            }

        result = persist_human_incident_closure_record(
            self.access,
            self.human,
            self.runtime,
            approval,
            _config(),
            confirmation=True,
            flag_reader=lambda *args, **kwargs: next(flags),
            saver=fake_save,
            now=NOW,
        )
        self.assertEqual(result["status"], "ROLLED_BACK")
        self.assertEqual(
            result["reason"],
            "FEATURE_FLAG_CHANGED_DURING_CLOSURE_PERSISTENCE",
        )
        self.assertTrue(result["rollback_performed"])
        self.assertEqual(len(calls), 2)

    def test_failed_rollback_is_reported_critical(self):
        approval = self.approval()
        flags = iter([_flag("DISABLED"), {"status": "ERROR", "state": "UNKNOWN"}])
        calls = []

        def fake_save(checkpoint, config, **kwargs):
            calls.append((deepcopy(checkpoint), dict(kwargs)))
            if len(calls) == 1:
                return {
                    "status": "CONFIRMED",
                    "saved": True,
                    "verified": True,
                    "sha": "closure-sha-2",
                    "checkpoint": deepcopy(checkpoint),
                }
            return {
                "status": "CONFLICT",
                "saved": False,
                "verified": False,
                "reason": "runtime changed",
            }

        result = persist_human_incident_closure_record(
            self.access,
            self.human,
            self.runtime,
            approval,
            _config(),
            confirmation=True,
            flag_reader=lambda *args, **kwargs: next(flags),
            saver=fake_save,
            now=NOW,
        )
        self.assertEqual(result["status"], "CRITICAL_ROLLBACK_FAILED")
        self.assertFalse(result["rollback_performed"])
        self.assertTrue(result["saved"])

    def test_admin_ui_exposes_durable_persistence_as_separate_ceremony(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Persistência durável do fechamento", source)
        self.assertIn(
            "PERSISTIR FECHAMENTO INCIDENTE WORKER GLOBAL",
            source,
        )
        self.assertIn("SEGUNDA CONFIRMAÇÃO", source)
        self.assertIn("Persistir registro humano de fechamento", source)
        self.assertIn("reativação autorizada: NÃO", source)

    def test_module_has_no_flag_worker_or_external_action_mutation_path(self):
        source = Path(
            "atlasquant_aion_global_worker_durable_incident_closure.py"
        ).read_text(encoding="utf-8")
        for banned in (
            "requests.put(",
            "requests.post(",
            "requests.patch(",
            "requests.delete(",
            "activate_global_worker_feature_flag(",
            "deactivate_global_worker_feature_flag(",
            "run_global_worker_once(",
            "worker_tick(",
            "workflow_dispatch",
            "subprocess.",
            "os.system(",
            "allow_global_arming_transition=True",
        ):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
