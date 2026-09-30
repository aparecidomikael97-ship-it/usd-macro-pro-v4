import ast
import hashlib
import json
import unittest
from pathlib import Path

from atlasquant_aion_business_team_access_sandbox_lifecycle_authorization import (
    SCHEMA as AUTH_SCHEMA,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_evidence_ledger import (
    GENESIS_DIGEST,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_materialization import (
    SCHEMA as MATERIALIZATION_SCHEMA,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_plan import (
    LIFECYCLE_STEP_IDS,
    REQUIRED_ACKNOWLEDGEMENTS as LIFECYCLE_ACKS,
    REQUIRED_DECISION_TOKEN as LIFECYCLE_TOKEN,
    SCHEMA as PLAN_SCHEMA,
)
from atlasquant_aion_business_team_access_step1_decision_record import (
    REQUIRED_ACKNOWLEDGEMENTS as STEP1_ACKS,
    SCHEMA as STEP1_DECISION_SCHEMA,
    validate_step1_decision_record,
)
from atlasquant_aion_business_team_access_step1_execution_envelope import (
    OBSERVATION_SCHEMA,
    build_step1_execution_envelope,
    execution_observation_template,
    step1_execution_envelope_policy,
    verify_step1_execution_envelope,
    verify_step1_execution_envelope_source_binding,
)
from atlasquant_aion_business_team_access_step1_preflight_package import (
    SCHEMA as PACKET_SCHEMA,
)


STEP1_TOKEN = (
    "AUTHORIZE_SANDBOX_LIFECYCLE_STEP_1_"
    "CREATE_INDIVIDUAL_SANDBOX_ACCOUNT"
)


def _digest(value):
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _plan():
    steps = [
        {
            "order": i,
            "id": step_id,
            "mutation": i in {1, 2, 4, 6, 7, 8},
            "requires_manual_apply": True,
            "evidence_required": ["proof"],
        }
        for i, step_id in enumerate(LIFECYCLE_STEP_IDS, start=1)
    ]
    payload = {
        "baseline_evidence_digest": "a" * 64,
        "baseline_acceptance_record_digest": "b" * 64,
        "test_username": "sandbox.operador.demo",
        "tenant_ids": ["tenant-a"],
        "factor_type": "PASSKEY",
        "requested_by": "admin.demo",
        "steps": steps,
    }
    return {
        "schema": PLAN_SCHEMA,
        "state": "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_EXECUTION_DECISION",
        **payload,
        "plan_digest": _digest(payload),
        "required_decision_token": LIFECYCLE_TOKEN,
        "required_acknowledgements": list(LIFECYCLE_ACKS),
        "decision_recorded": False,
        "account_creation_authorized": False,
        "mfa_enrollment_authorized": False,
        "registry_write_authorized": False,
        "session_revocation_authorized": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


def _materialization():
    plan = _plan()
    payload = {
        "operator_session_id": "c" * 32,
        "baseline_evidence_digest": "a" * 64,
        "baseline_acceptance_record_digest": "b" * 64,
        "plan_digest": plan["plan_digest"],
        "test_username": plan["test_username"],
        "tenant_ids": plan["tenant_ids"],
        "factor_type": plan["factor_type"],
        "requested_by": plan["requested_by"],
    }
    return {
        "schema": MATERIALIZATION_SCHEMA,
        "state": "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_PLAN_REVIEW",
        "operator_session_id": "c" * 32,
        "baseline_evidence_digest": "a" * 64,
        "baseline_acceptance_record_digest": "b" * 64,
        "plan_digest": plan["plan_digest"],
        "materialization_digest": _digest(payload),
        "plan": plan,
        "lifecycle_authorization_recorded": False,
        "lifecycle_execution_authorized": False,
        "automatic_step_execution": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


def _packet(materialization):
    plan = materialization["plan"]
    materialization_digest = materialization["materialization_digest"]
    plan_digest = plan["plan_digest"]
    authorization_record_digest = "d" * 64
    authorization_package_digest = "e" * 64
    session_id = materialization["operator_session_id"]
    baseline_digest = materialization["baseline_evidence_digest"]
    observer = "admin.demo"

    ledger_payload = {
        "plan_digest": plan_digest,
        "authorization_record_digest": authorization_record_digest,
        "authorization_package_digest": authorization_package_digest,
        "materialization_digest": materialization_digest,
        "entries": [],
        "completed_count": 0,
        "chain_head_digest": GENESIS_DIGEST,
    }
    ledger_digest = _digest(ledger_payload)

    preflight_payload = {
        "plan_digest": plan_digest,
        "authorization_record_digest": authorization_record_digest,
        "authorization_package_digest": authorization_package_digest,
        "materialization_digest": materialization_digest,
        "ledger_digest": ledger_digest,
        "chain_head_digest": GENESIS_DIGEST,
        "target_step_order": 1,
        "target_step_id": LIFECYCLE_STEP_IDS[0],
        "baseline_evidence_digest": baseline_digest,
        "requested_by": observer,
    }
    preflight_digest = _digest(preflight_payload)

    packet_payload = {
        "materialization_digest": materialization_digest,
        "plan_digest": plan_digest,
        "authorization_record_digest": authorization_record_digest,
        "authorization_package_digest": authorization_package_digest,
        "ledger_digest": ledger_digest,
        "preflight_digest": preflight_digest,
        "operator_session_id": session_id,
        "baseline_evidence_digest": baseline_digest,
        "observation_observed_at": "2026-09-30T21:45:00+00:00",
        "observation_observed_by": observer,
        "evaluated_at": "2026-09-30T21:50:00+00:00",
        "target_step_order": 1,
        "target_step_id": LIFECYCLE_STEP_IDS[0],
    }

    return {
        "schema": PACKET_SCHEMA,
        "state": "READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_1_DECISION_PACKET",
        "ledger": {
            "state": "READY_FOR_FIRST_SANDBOX_LIFECYCLE_STEP",
            "ledger_digest": ledger_digest,
            "completed_count": 0,
            "entries": [],
            "chain_head_digest": GENESIS_DIGEST,
            "next_expected_step_order": 1,
            "next_expected_step_id": LIFECYCLE_STEP_IDS[0],
        },
        "preflight": {
            "state": "READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_DECISION",
            "preflight_digest": preflight_digest,
            "target_step_order": 1,
            "target_step_id": LIFECYCLE_STEP_IDS[0],
            "step_execution_authorized": False,
            "automatic_execution_authorized": False,
            "automatic_ledger_append": False,
            "executor_enabled": False,
            "production_authorized": False,
            "executes_action": False,
        },
        "step1_packet_digest": _digest(packet_payload),
        **packet_payload,
        "required_step_decision_token": STEP1_TOKEN,
        "manual_decision_recorded": False,
        "step_execution_authorized": False,
        "automatic_execution_authorized": False,
        "automatic_ledger_append": False,
        "executor_enabled": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


def _decision(packet):
    raw = {
        "schema": STEP1_DECISION_SCHEMA,
        "decision": STEP1_TOKEN,
        "step1_packet_digest": packet["step1_packet_digest"],
        "target_step_order": 1,
        "target_step_id": LIFECYCLE_STEP_IDS[0],
        "decided_by": "admin.demo",
        "decided_at": "2026-09-30T21:52:00+00:00",
        "sandbox_only": True,
        "production_targeted": False,
        "secret_material_included": False,
        "automatic_execution_requested": False,
        "automatic_ledger_append_requested": False,
        "executor_enable_requested": False,
        "acknowledgements": {
            name: True for name in STEP1_ACKS
        },
    }
    return validate_step1_decision_record(packet, raw)


def _observation():
    return {
        "schema": OBSERVATION_SCHEMA,
        "operator_session_id": "c" * 32,
        "baseline_evidence_digest_observed": "a" * 64,
        "observed_at": "2026-09-30T21:53:00+00:00",
        "observed_by": "admin.demo",
        "target_username": "sandbox.operador.demo",
        "target_account_absent_verified": True,
        "identity_provider_account_lookup_verified": True,
        "tenant_scope_verified": True,
        "sandbox_health_verified": True,
        "oidc_verified": True,
        "registry_schema_verified": True,
        "secrets_local": True,
        "production_targets_absent": True,
        "cleanup_path_ready": True,
        "secret_material_included": False,
        "production_targeted": False,
        "external_mutations_executed": False,
    }


class TeamAccessStep1ExecutionEnvelopeTests(unittest.TestCase):
    def test_policy_is_non_executing(self):
        policy = step1_execution_envelope_policy()
        self.assertTrue(policy["post_decision_observation_required"])
        self.assertTrue(policy["target_account_absence_required"])
        self.assertFalse(policy["manual_apply_eligible"])
        self.assertFalse(policy["provider_command_generated"])
        self.assertFalse(policy["physical_execution_performed"])
        self.assertFalse(policy["executor_enabled"])
        self.assertFalse(policy["production_authorized"])

    def test_observation_template_fails_closed(self):
        row = execution_observation_template()
        self.assertFalse(row["target_account_absent_verified"])
        self.assertFalse(row["identity_provider_account_lookup_verified"])
        self.assertFalse(row["sandbox_health_verified"])
        self.assertFalse(row["external_mutations_executed"])

    def test_valid_inputs_prepare_manual_apply_envelope_only(self):
        materialization = _materialization()
        packet = _packet(materialization)
        decision = _decision(packet)
        result = build_step1_execution_envelope(
            materialization,
            packet,
            decision,
            _observation(),
            prepared_at="2026-09-30T21:54:00+00:00",
        )
        self.assertEqual(
            result["state"],
            "READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_1_APPLY",
        )
        self.assertTrue(all(result["gates"].values()))
        self.assertTrue(result["manual_apply_eligible"])
        self.assertEqual(
            result["target_step_id"], LIFECYCLE_STEP_IDS[0]
        )
        self.assertEqual(
            result["target_username"], "sandbox.operador.demo"
        )
        self.assertTrue(result["execution_envelope_digest"])
        self.assertFalse(result["provider_command_generated"])
        self.assertFalse(result["physical_execution_performed"])
        self.assertFalse(result["ledger_append_authorized"])
        self.assertFalse(result["automatic_execution_authorized"])
        self.assertFalse(result["executor_enabled"])
        self.assertFalse(result["production_authorized"])

    def test_ready_envelope_has_recomputable_integrity(self):
        materialization = _materialization()
        packet = _packet(materialization)
        decision = _decision(packet)
        result = build_step1_execution_envelope(
            materialization,
            packet,
            decision,
            _observation(),
            prepared_at="2026-09-30T21:54:00+00:00",
        )
        binding = verify_step1_execution_envelope(result)
        self.assertTrue(binding["binding_match"])
        self.assertEqual(
            binding["state"], "STEP1_EXECUTION_ENVELOPE_BINDING_MATCH"
        )
        source = verify_step1_execution_envelope_source_binding(
            materialization,
            packet,
            decision,
            result,
        )
        self.assertTrue(source["binding_match"])

    def test_tampered_observation_breaks_envelope_integrity(self):
        materialization = _materialization()
        packet = _packet(materialization)
        decision = _decision(packet)
        result = build_step1_execution_envelope(
            materialization,
            packet,
            decision,
            _observation(),
            prepared_at="2026-09-30T21:54:00+00:00",
        )
        result["execution_observation"][
            "target_account_absent_verified"
        ] = False
        binding = verify_step1_execution_envelope(result)
        self.assertFalse(binding["binding_match"])
        self.assertIn("observation_digest_integrity", binding["blockers"])

    def test_tampered_envelope_digest_or_source_breaks_binding(self):
        materialization = _materialization()
        packet = _packet(materialization)
        decision = _decision(packet)
        result = build_step1_execution_envelope(
            materialization,
            packet,
            decision,
            _observation(),
            prepared_at="2026-09-30T21:54:00+00:00",
        )
        result["execution_envelope_digest"] = "1" * 64
        binding = verify_step1_execution_envelope(result)
        self.assertFalse(binding["binding_match"])

        result = build_step1_execution_envelope(
            materialization,
            packet,
            decision,
            _observation(),
            prepared_at="2026-09-30T21:54:00+00:00",
        )
        changed = _materialization()
        changed["materialization_digest"] = "2" * 64
        source = verify_step1_execution_envelope_source_binding(
            changed,
            packet,
            decision,
            result,
        )
        self.assertFalse(source["binding_match"])

    def test_observation_must_be_after_decision(self):
        materialization = _materialization()
        packet = _packet(materialization)
        decision = _decision(packet)
        observation = _observation()
        observation["observed_at"] = "2026-09-30T21:51:59+00:00"
        result = build_step1_execution_envelope(
            materialization,
            packet,
            decision,
            observation,
            prepared_at="2026-09-30T21:54:00+00:00",
        )
        self.assertIn("observation_after_decision", result["blockers"])

    def test_stale_decision_or_observation_blocks(self):
        materialization = _materialization()
        packet = _packet(materialization)
        decision = _decision(packet)
        result = build_step1_execution_envelope(
            materialization,
            packet,
            decision,
            _observation(),
            prepared_at="2026-09-30T21:55:01+00:00",
        )
        self.assertIn("decision_still_fresh", result["blockers"])
        self.assertIn("execution_observation_fresh", result["blockers"])

    def test_existing_target_account_blocks(self):
        materialization = _materialization()
        packet = _packet(materialization)
        observation = _observation()
        observation["target_account_absent_verified"] = False
        result = build_step1_execution_envelope(
            materialization,
            packet,
            _decision(packet),
            observation,
            prepared_at="2026-09-30T21:54:00+00:00",
        )
        self.assertIn(
            "target_account_absent_verified", result["blockers"]
        )
        self.assertFalse(result["manual_apply_eligible"])

    def test_session_or_baseline_drift_blocks(self):
        materialization = _materialization()
        packet = _packet(materialization)
        observation = _observation()
        observation["operator_session_id"] = "f" * 32
        observation["baseline_evidence_digest_observed"] = "9" * 64
        result = build_step1_execution_envelope(
            materialization,
            packet,
            _decision(packet),
            observation,
            prepared_at="2026-09-30T21:54:00+00:00",
        )
        self.assertIn("observation_session_matches", result["blockers"])
        self.assertIn("observation_baseline_matches", result["blockers"])

    def test_module_has_no_network_process_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_team_access_step1_execution_envelope.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertFalse(
            imported.intersection(
                {"requests", "httpx", "socket", "subprocess", "docker"}
            )
        )


if __name__ == "__main__":
    unittest.main()
