import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_runtime_readiness import (
    CERTIFICATION_DECISION_SCHEMA,
    business_runtime_approval_packet,
    business_runtime_posture,
    business_sandbox_readiness,
    normalize_certification_decision,
)


SHA = "586c00915909dce3bc8fc329ca8f2c2f12dbacf4"
FP = "d3a595856d9877e031b104e94b42bb96f304ab2261032db1478a01a045f56a3e"


def _certificate(**updates):
    data = {
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
    data.update(updates)
    return data


def _readiness(**updates):
    args = {
        "certification_decision": _certificate(),
        "expected_sha": SHA,
        "expected_fingerprint": FP,
        "sandbox_isolated": True,
        "external_network_disabled": True,
        "payment_disabled": True,
        "publication_disabled": True,
        "deploy_disabled": True,
        "real_trading_disabled": True,
        "audit_enabled": True,
        "rollback_ready": True,
        "kill_switch_ready": True,
    }
    args.update(updates)
    return business_sandbox_readiness(**args)


class BusinessRuntimeReadinessTests(unittest.TestCase):
    def test_certification_decision_requires_exact_verified_safe_record(self):
        cert = normalize_certification_decision(_certificate())
        self.assertTrue(cert["valid"])
        self.assertEqual(cert["state"], "CERTIFIED")
        for key, value in (
            ("human_review_verified", "true"),
            ("ci_evidence_verified", 1),
            ("runtime_activated", True),
            ("merge_authorized", True),
            ("payment_authorized", True),
            ("reviewed_sha", "bad"),
            ("evidence_fingerprint", "bad"),
        ):
            with self.subTest(key=key):
                rejected = normalize_certification_decision(_certificate(**{key: value}))
                self.assertFalse(rejected["valid"])
                self.assertEqual(rejected["state"], "REJECTED")

    def test_certified_business_can_only_become_sandbox_ready(self):
        result = _readiness()
        self.assertEqual(result["state"], "SANDBOX_READY")
        self.assertTrue(result["sandbox_ready"])
        self.assertTrue(result["runtime_approval_required"])
        self.assertFalse(result["production_runtime_allowed"])
        self.assertFalse(result["runtime_capability_available"])
        self.assertFalse(result["runtime_activated"])
        self.assertEqual(result["plan"]["mode"], "SANDBOX_ONLY")
        self.assertEqual(result["plan"]["allowed_actions"], ["read", "analyze", "draft"])
        for action in ("external_contact", "sign_contract", "payment", "publish", "deploy", "real_trade"):
            self.assertIn(action, result["plan"]["denied_actions"])
        self.assertTrue(result["plan_digest"])

    def test_any_missing_safety_gate_fails_closed(self):
        cases = (
            ("sandbox_isolated", False),
            ("external_network_disabled", False),
            ("payment_disabled", "true"),
            ("publication_disabled", 1),
            ("deploy_disabled", None),
            ("real_trading_disabled", False),
            ("audit_enabled", False),
            ("rollback_ready", False),
            ("kill_switch_ready", False),
            ("expected_sha", "0" * 40),
            ("expected_fingerprint", "0" * 64),
        )
        for key, value in cases:
            with self.subTest(key=key):
                result = _readiness(**{key: value})
                self.assertEqual(result["state"], "NOT_ELIGIBLE")
                self.assertFalse(result["sandbox_ready"])
                self.assertFalse(result["runtime_activated"])
                self.assertFalse(result["production_runtime_allowed"])

    def test_approval_packet_never_approves_runtime(self):
        ready = _readiness()
        packet = business_runtime_approval_packet(
            ready,
            requested_by="Mikael",
            reason="Prepare future controlled BUSINESS sandbox runtime review.",
        )
        self.assertEqual(packet["state"], "RUNTIME_APPROVAL_REQUIRED")
        self.assertTrue(packet["eligible_for_human_runtime_review"])
        self.assertEqual(packet["approval_scope"], "RUNTIME_ACTIVATION_ONLY")
        self.assertFalse(packet["runtime_activation_approved"])
        self.assertFalse(packet["runtime_activated"])
        self.assertFalse(packet["external_actions_authorized"])
        self.assertFalse(packet["payment_authorized"])
        self.assertFalse(packet["publication_authorized"])
        self.assertFalse(packet["deploy_authorized"])
        self.assertFalse(packet["real_trading_authorized"])
        self.assertTrue(packet["packet_digest"])

    def test_invalid_readiness_cannot_create_runtime_review_packet(self):
        blocked = _readiness(kill_switch_ready=False)
        packet = business_runtime_approval_packet(
            blocked,
            requested_by="Mikael",
            reason="test",
        )
        self.assertEqual(packet["state"], "BLOCKED")
        self.assertFalse(packet["eligible_for_human_runtime_review"])
        self.assertFalse(packet["runtime_activation_approved"])
        self.assertEqual(packet["packet_digest"], "")

    def test_posture_reports_approval_required_but_runtime_off(self):
        ready = _readiness()
        packet = business_runtime_approval_packet(
            ready,
            requested_by="Mikael",
            reason="Sandbox review only.",
        )
        posture = business_runtime_posture(ready, packet)
        self.assertEqual(posture["certification_state"], "CERTIFIED")
        self.assertEqual(posture["sandbox_state"], "SANDBOX_READY")
        self.assertEqual(posture["runtime_state"], "RUNTIME_APPROVAL_REQUIRED")
        self.assertFalse(posture["runtime_capability_available"])
        self.assertFalse(posture["runtime_activated"])
        self.assertFalse(posture["external_actions_enabled"])
        self.assertFalse(posture["payment_enabled"])
        self.assertFalse(posture["publication_enabled"])
        self.assertFalse(posture["deploy_enabled"])
        self.assertFalse(posture["real_trading_enabled"])

    def test_module_has_no_network_process_or_external_sdk_imports(self):
        source = Path("atlasquant_aion_business_runtime_readiness.py").read_text(encoding="utf-8")
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
