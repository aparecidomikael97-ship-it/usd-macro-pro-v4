import unittest
from datetime import datetime, timezone

from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_nightshift_bridge import validate_runtime_rows
from atlasquant_aion_core_runtime_bridge import handle_runtime_intent

NOW = datetime(2026, 10, 1, 20, 0, tzinfo=timezone.utc)

def _access():
    return {
        "allowed": True, "mode": "AUTHENTICATED", "role": "ADMIN",
        "session": {
            "username": "mikael", "role": "ADMIN",
            "credential_fingerprint": "a1b2c3d4e5f60718293a4b5c",
            "permissions": ["app:read", "admin:read", "aion:admin"],
        },
    }

class NightshiftRuntimeBridgeTests(unittest.TestCase):
    def test_valid_runtime_evidence_is_read_only_and_non_executing(self):
        result = validate_runtime_rows(
            tenant_id="tenant:test",
            runtime_domain=Domain.ADMIN,
            rows=[{
                "claim": "build",
                "value": "abc123",
                "truth_state": "CONFIRMED",
                "source": "runtime",
                "source_ref": "runtime-build:abc123",
                "time_sensitive": False,
            }],
            now=NOW,
        )
        self.assertEqual(result["status"], "VALIDATED")
        self.assertEqual(result["accepted_evidence"], 1)
        self.assertFalse(result["memory_auto_write"])
        self.assertFalse(result["external_persisted"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["external_action_executed"])

    def test_missing_provenance_reference_fails_closed(self):
        result = validate_runtime_rows(
            tenant_id="tenant:test",
            runtime_domain=Domain.ADMIN,
            rows=[{"claim": "build", "source": "runtime", "source_ref": ""}],
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["accepted_evidence"], 0)
        self.assertGreaterEqual(result["rejected_rows"], 1)

    def test_runtime_exposes_nightshift_veto_without_authorizing_action(self):
        result = handle_runtime_intent(
            _access(),
            "qual é o estado do sistema",
            system_context={"core_evidence": [{
                "claim": "build", "value": "abc123", "truth_state": "CONFIRMED",
                "source": "runtime", "source_ref": "", "time_sensitive": False,
            }]},
            now=NOW,
        )
        self.assertEqual(result["nightshift_validation"]["status"], "BLOCKED")
        self.assertTrue(result["evidence"]["nightshift_veto"])
        self.assertEqual(result["truth_state"], "UNKNOWN")
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["external_action_executed"])

    def test_unmapped_domain_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "NIGHTSHIFT_DOMAIN_UNMAPPED"):
            validate_runtime_rows(
                tenant_id="tenant:test",
                runtime_domain="UNKNOWN_DOMAIN",
                rows=[],
                now=NOW,
            )

    def test_trust_assessment_is_deterministic_for_same_inputs(self):
        rows=[{
            "claim": "build", "truth_state": "CONFIRMED",
            "source": "runtime", "source_ref": "runtime-build:abc",
            "time_sensitive": False,
        }]
        a = validate_runtime_rows(
            tenant_id="tenant:test", runtime_domain=Domain.ADMIN, rows=rows, now=NOW
        )
        b = validate_runtime_rows(
            tenant_id="tenant:test", runtime_domain=Domain.ADMIN, rows=rows, now=NOW
        )
        self.assertEqual(a["assessments"], b["assessments"])

if __name__ == "__main__":
    unittest.main()
