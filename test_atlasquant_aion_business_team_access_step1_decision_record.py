import ast
import hashlib
import json
import unittest
from pathlib import Path

from atlasquant_aion_business_team_access_sandbox_lifecycle_evidence_ledger import (
    GENESIS_DIGEST,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_plan import (
    LIFECYCLE_STEP_IDS,
)
from atlasquant_aion_business_team_access_step1_decision_record import (
    REQUIRED_ACKNOWLEDGEMENTS,
    SCHEMA,
    step1_decision_record_template,
    step1_decision_requirements,
    validate_step1_decision_record,
    verify_step1_decision_binding,
)
from atlasquant_aion_business_team_access_step1_preflight_package import (
    SCHEMA as PACKET_SCHEMA,
)


TOKEN = (
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


def _packet():
    materialization_digest = "a" * 64
    plan_digest = "b" * 64
    authorization_record_digest = "c" * 64
    authorization_package_digest = "d" * 64
    session_id = "e" * 32
    baseline_digest = "f" * 64
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
        "version": "1",
        "state": "READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_1_DECISION_PACKET",
        "gates": {"all": True},
        "blockers": [],
        "observation_age_seconds": 300,
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
        "required_step_decision_token": TOKEN,
        "manual_apply_required": True,
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


def _record():
    return {
        "schema": SCHEMA,
        "version": "1",
        "decision": TOKEN,
        "step1_packet_digest": _packet()["step1_packet_digest"],
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
            name: True for name in REQUIRED_ACKNOWLEDGEMENTS
        },
    }


class TeamAccessStep1DecisionRecordTests(unittest.TestCase):
    def test_requirements_do_not_accept_generic_language(self):
        req = step1_decision_requirements()
        self.assertFalse(req["generic_language_is_authorization"])
        self.assertFalse(req["decision_record_verified"])
        self.assertFalse(req["manual_step1_execution_authorized"])
        self.assertFalse(req["step_execution_performed"])
        self.assertFalse(req["executor_enabled"])

    def test_template_binds_packet_without_recording_decision(self):
        template = step1_decision_record_template(_packet())
        self.assertEqual(
            template["state"], "EXPLICIT_STEP1_DECISION_RECORD_REQUIRED"
        )
        self.assertEqual(
            template["step1_packet_digest"],
            _packet()["step1_packet_digest"],
        )
        self.assertEqual(template["expected_decided_by"], "admin.demo")
        self.assertEqual(template["decision"], "")
        self.assertTrue(all(
            value is False
            for value in template["acknowledgements"].values()
        ))

    def test_exact_record_authorizes_manual_step1_only(self):
        result = validate_step1_decision_record(_packet(), _record())
        self.assertEqual(
            result["state"],
            "EXPLICIT_SANDBOX_STEP_1_DECISION_RECORD_VERIFIED",
        )
        self.assertTrue(result["decision_record_verified"])
        self.assertTrue(result["manual_step1_execution_authorized"])
        self.assertTrue(result["decision_record_digest"])
        self.assertFalse(result["step_execution_performed"])
        self.assertFalse(result["ledger_append_authorized"])
        self.assertFalse(result["automatic_execution_authorized"])
        self.assertFalse(result["executor_enabled"])
        self.assertFalse(result["production_authorized"])
        self.assertFalse(result["executes_action"])

        binding = verify_step1_decision_binding(_packet(), result)
        self.assertTrue(binding["binding_match"])
        self.assertTrue(binding["manual_step1_execution_authorized"])
        self.assertFalse(binding["step_execution_performed"])

    def test_generic_language_is_rejected(self):
        row = _record()
        row["decision"] = "vamos lá"
        result = validate_step1_decision_record(_packet(), row)
        self.assertEqual(
            result["state"], "SANDBOX_STEP_1_DECISION_RECORD_REJECTED"
        )
        self.assertIn("decision_token_exact", result["blockers"])
        self.assertFalse(result["manual_step1_execution_authorized"])

    def test_stale_packet_or_observation_is_rejected(self):
        row = _record()
        row["decided_at"] = "2026-09-30T22:10:01+00:00"
        result = validate_step1_decision_record(_packet(), row)
        self.assertIn("packet_still_fresh", result["blockers"])
        self.assertIn("observation_still_fresh", result["blockers"])

    def test_packet_tamper_is_rejected(self):
        packet = _packet()
        packet["ledger"]["completed_count"] = 1
        result = validate_step1_decision_record(packet, _record())
        self.assertIn("packet_binding_match", result["blockers"])

    def test_missing_acknowledgement_is_rejected(self):
        row = _record()
        row["acknowledgements"]["POST_STEP_RECEIPT_REQUIRED"] = False
        result = validate_step1_decision_record(_packet(), row)
        self.assertIn("acknowledgements_complete", result["blockers"])
        self.assertIn(
            "POST_STEP_RECEIPT_REQUIRED",
            result["missing_acknowledgements"],
        )

    def test_tampered_verified_record_breaks_binding(self):
        result = validate_step1_decision_record(_packet(), _record())
        result["decided_by"] = "outro.admin"
        binding = verify_step1_decision_binding(_packet(), result)
        self.assertFalse(binding["binding_match"])

    def test_module_has_no_network_process_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_team_access_step1_decision_record.py"
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
