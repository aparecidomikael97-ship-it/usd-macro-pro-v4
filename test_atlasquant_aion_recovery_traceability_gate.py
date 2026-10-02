import unittest

from atlasquant_aion_memory import (
    checkpoint_integrity_report,
    checkpoint_source_digest,
    default_checkpoint,
)
from atlasquant_aion_local_traceability import (
    build_local_traceability,
    local_contract_fingerprint,
)
from atlasquant_aion_recovery_traceability_gate import (
    recovery_traceability_policy,
    recovery_traceability_readiness,
)

REV = "a" * 40
CUR_SHA = "b" * 40

def _current():
    cp = default_checkpoint()
    return {
        "status": "CONFIRMED",
        "sha": CUR_SHA,
        "checkpoint": cp,
        "integrity": checkpoint_integrity_report(cp),
    }

def _candidate():
    cp = default_checkpoint()
    cp["aion"]["priority"] = "historical recovery"
    return {
        "status": "CONFIRMED",
        "revision": REV,
        "checkpoint": cp,
        "integrity": checkpoint_integrity_report(cp),
        "digest": checkpoint_source_digest(cp),
    }

def _envelope(*, safe=True, tool_id="aion.checkpoint.inspect"):
    return {
        "tool_id": tool_id,
        "request_id": "recovery-trace-1",
        "workspace_id": "administration",
        "kind": "READ",
        "contract_fingerprint": local_contract_fingerprint(),
        "state": "SUCCESS",
        "result": {},
        "preflight": {"state": "READY_FOR_EXECUTOR", "blockers": []},

        "provenance": {
            "source_module": "atlasquant_aion_local_executor",
            "source_function": "_test_recovery",
            "input_scope": "local",
            "local_only": True,
        },
        "truth": {"status": "CONFIRMED", "freshness": "FRESH"},
        "security": {
            "network_called": False if safe else True,
            "connector_called": False,
            "external_side_effects": False if safe else True,
            "permissions_expanded": False,
            "secrets_included": False,
        },
        "executes_action": False,
        "external_action_executed": False,
        "real_orders_enabled": False,
        "tool_output_is_authority": False,
    }

def _trace(*, safe=True, tool_id="aion.checkpoint.inspect", conflict=False):
    synthesis = {
        "items": [{

            "tool_id": tool_id,
            "state": "SUCCESS",
            "truth_status": "CONFIRMED",
            "freshness": "FRESH",
            "execution_confirmed": True,
            "content_confirmed": True,
            "blockers": [],
        }],
        "conflicts": [f"{tool_id}:RECOVERY_CONFLICT"] if conflict else [],
        "truth": {"status": "UNKNOWN" if conflict else "CONFIRMED"},
        "security": {"state": "SAFE_LOCAL"},
    }
    return build_local_traceability(
        [_envelope(safe=safe, tool_id=tool_id)],
        synthesis=synthesis,
    )

class RecoveryTraceabilityGateTests(unittest.TestCase):
    def test_policy_never_authorizes_restore(self):
        policy = recovery_traceability_policy()
        self.assertTrue(policy["explicit_admin_approval_required"])
        self.assertFalse(policy["automatic_restore"])
        self.assertFalse(policy["automatic_retry"])
        self.assertFalse(policy["execution_authority"])

    def test_clean_recovery_is_ready_for_admin_review_only(self):
        result = recovery_traceability_readiness(
            _current(), _candidate(), _trace()
        )
        self.assertEqual(result["state"], "READY_FOR_ADMIN_REVIEW")
        self.assertEqual(result["blockers"], [])
        self.assertFalse(result["recovery_authorized"])
        self.assertFalse(result["checkpoint_saved"])
        self.assertFalse(result["external_action_executed"])
        self.assertTrue(result["receipt"]["requires_explicit_admin_approval"])
        self.assertTrue(result["receipt_digest"].startswith("sha256:"))

    def test_tampered_candidate_blocks(self):
        candidate = _candidate()
        candidate["digest"] = "0" * 64
        result = recovery_traceability_readiness(
            _current(), candidate, _trace()
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("RECOVERY_PREFLIGHT_BLOCKED", result["blockers"])

    def test_unsafe_trace_blocks(self):
        result = recovery_traceability_readiness(
            _current(), _candidate(), _trace(safe=False)
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("TRACEABILITY_SECURITY_BLOCK", result["blockers"])

    def test_trace_conflict_blocks(self):
        result = recovery_traceability_readiness(
            _current(), _candidate(), _trace(conflict=True)
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("TRACEABILITY_CONFLICT", result["blockers"])

    def test_non_checkpoint_trace_blocks(self):
        result = recovery_traceability_readiness(
            _current(),
            _candidate(),
            _trace(tool_id="aion.tasks.summary"),
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("CHECKPOINT_TRACE_REQUIRED", result["blockers"])

    def test_empty_trace_blocks(self):
        result = recovery_traceability_readiness(
            _current(),
            _candidate(),
            build_local_traceability([]),
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("TRACEABILITY_EVIDENCE_REQUIRED", result["blockers"])

    def test_receipt_is_deterministic(self):
        current = _current()
        candidate = _candidate()
        trace = _trace()
        first = recovery_traceability_readiness(current, candidate, trace)
        second = recovery_traceability_readiness(current, candidate, trace)
        self.assertEqual(first["receipt_digest"], second["receipt_digest"])
        self.assertEqual(first["receipt"], second["receipt"])

if __name__ == "__main__":
    unittest.main()
