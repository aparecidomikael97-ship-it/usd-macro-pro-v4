import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_runtime_readiness import (
    CERTIFICATION_DECISION_SCHEMA,
    business_sandbox_readiness,
)
from atlasquant_aion_business_sandbox_harness import (
    MAX_CASES,
    create_business_sandbox_session,
    run_business_sandbox_case,
    sandbox_batch,
)

SHA = "586c00915909dce3bc8fc329ca8f2c2f12dbacf4"
FP = "d3a595856d9877e031b104e94b42bb96f304ab2261032db1478a01a045f56a3e"


def _readiness():
    cert = {
        "schema": CERTIFICATION_DECISION_SCHEMA,
        "specialist": "BUSINESS",
        "state": "CERTIFIED",
        "reviewed_sha": SHA,
        "evidence_fingerprint": FP,
        "human_review_verified": True,
        "ci_evidence_verified": True,
        "runtime_activated": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "external_contact_authorized": False,
        "contract_signature_authorized": False,
        "payment_authorized": False,
        "publication_authorized": False,
        "spend_authorized": False,
        "real_trading_authorized": False,
    }
    return business_sandbox_readiness(
        cert,
        expected_sha=SHA,
        expected_fingerprint=FP,
        sandbox_isolated=True,
        external_network_disabled=True,
        payment_disabled=True,
        publication_disabled=True,
        deploy_disabled=True,
        real_trading_disabled=True,
        audit_enabled=True,
        rollback_ready=True,
        kill_switch_ready=True,
    )


def _session():
    return create_business_sandbox_session(
        _readiness(),
        tenant_id="tenant-a",
        workspace_id="business-sandbox",
        actor_id="mikael",
        session_id="session-1",
    )


class BusinessSandboxHarnessTests(unittest.TestCase):
    def test_session_opens_only_for_sandbox_ready_posture(self):
        session = _session()
        self.assertEqual(session["state"], "OPEN")
        self.assertEqual(session["mode"], "SIMULATION_ONLY")
        self.assertTrue(session["session_digest"])
        self.assertFalse(session["provider_called"])
        self.assertFalse(session["network_called"])
        self.assertFalse(session["external_write"])
        self.assertFalse(session["runtime_activated"])
        blocked = create_business_sandbox_session(
            {"schema": "bad", "state": "SANDBOX_READY"},
            tenant_id="x", workspace_id="y", actor_id="z", session_id="s",
        )
        self.assertEqual(blocked["state"], "BLOCKED")

    def test_lead_qualification_is_deterministic_and_side_effect_free(self):
        result = run_business_sandbox_case(
            _session(),
            case_type="LEAD_QUALIFICATION",
            data={
                "name": "Empresa X",
                "contact": "contato@example.com",
                "need": "automatizar atendimento",
                "budget_confirmed": True,
                "urgency": "alta",
            },
        )
        self.assertEqual(result["state"], "COMPLETED")
        self.assertEqual(result["result"]["score"], 100)
        self.assertEqual(result["result"]["band"], "HOT")
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["runtime_activated"])
        self.assertFalse(result["payment_executed"])
        self.assertFalse(result["publication_executed"])

    def test_faq_uses_only_approved_fixture_facts(self):
        result = run_business_sandbox_case(
            _session(),
            case_type="FAQ_DRAFT",
            data={
                "question": "Como funciona?",
                "approved_facts": [
                    "O serviço começa com diagnóstico.",
                    "A implantação depende do escopo aprovado.",
                ],
            },
        )
        self.assertEqual(result["result"]["state"], "DRAFT")
        self.assertTrue(result["result"]["uses_only_approved_facts"])
        self.assertIn("diagnóstico", result["result"]["answer_draft"])

    def test_followup_is_draft_never_sent(self):
        result = run_business_sandbox_case(
            _session(),
            case_type="FOLLOWUP_DRAFT",
            data={
                "name": "Cliente",
                "context": "o diagnóstico inicial",
                "next_step": "revisar a proposta",
            },
        )
        self.assertEqual(result["result"]["state"], "DRAFT")
        self.assertTrue(result["result"]["requires_human_review"])
        self.assertFalse(result["result"]["sent"])
        self.assertFalse(result["external_action_executed"])

    def test_business_radar_surfaces_simple_alerts(self):
        result = run_business_sandbox_case(
            _session(),
            case_type="BUSINESS_RADAR",
            data={
                "leads_open": 42,
                "avg_response_hours": 3.5,
                "abandoned_quotes": 8,
            },
        )
        alerts = result["result"]["alerts"]
        self.assertIn("RESPONSE_TIME_HIGH", alerts)
        self.assertIn("ABANDONED_QUOTES_PRESENT", alerts)
        self.assertIn("LEAD_BACKLOG_HIGH", alerts)
        self.assertEqual(result["result"]["simple_summary"], "attention_required")

    def test_denied_external_actions_fail_closed(self):
        for action in ("external_contact", "sign_contract", "payment", "publish", "deploy", "real_trade"):
            with self.subTest(action=action):
                result = run_business_sandbox_case(
                    _session(),
                    case_type="FOLLOWUP_DRAFT",
                    data={"context": "x", "next_step": "y"},
                    requested_action=action,
                )
                self.assertEqual(result["state"], "BLOCKED")
                self.assertEqual(result["reason"], "ACTION_DENIED")
                self.assertFalse(result["external_action_executed"])
                self.assertFalse(result["runtime_activated"])

    def test_unknown_case_and_batch_overflow_fail_closed(self):
        unknown = run_business_sandbox_case(
            _session(),
            case_type="SEND_WHATSAPP",
            data={},
        )
        self.assertEqual(unknown["state"], "BLOCKED")
        self.assertEqual(unknown["reason"], "CASE_NOT_ALLOWED")

        cases = [{"case_type": "LEAD_QUALIFICATION", "data": {}} for _ in range(MAX_CASES + 1)]
        batch = sandbox_batch(_session(), cases)
        self.assertEqual(batch["state"], "BLOCKED")
        self.assertEqual(batch["reason"], "CASE_LIMIT_EXCEEDED")
        self.assertEqual(batch["count"], 0)
        self.assertFalse(batch["runtime_activated"])

    def test_module_has_no_network_process_or_external_sdk_imports(self):
        source = Path("atlasquant_aion_business_sandbox_harness.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.append(node.module or "")
        for banned in ("requests", "urllib", "httpx", "socket", "subprocess", "openai"):
            self.assertNotIn(banned, names)


if __name__ == "__main__":
    unittest.main()
