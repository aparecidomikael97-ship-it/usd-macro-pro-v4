import unittest

from atlasquant_aion_local_synthesis import (
    SCHEMA,
    synthesize_local_tool_results,
)


def _envelope(
    tool_id,
    *,
    state="SUCCESS",
    truth="UNKNOWN",
    freshness="UNVERIFIED",
    result=None,
    blockers=None,
):
    return {
        "schema": "ATLASQUANT_AION_LOCAL_TOOL_RESULT_V1",
        "tool_id": tool_id,
        "kind": "READ",
        "state": state,
        "result": result or {},
        "preflight": {
            "state": "READY_FOR_EXECUTOR" if state == "SUCCESS" else "BLOCK",
            "blockers": blockers or [],
        },
        "provenance": {
            "source_module": "atlasquant_aion_local_executor",
            "source_function": "_test",
            "input_scope": "local",
            "local_only": True,
        },
        "truth": {
            "status": truth,
            "freshness": freshness,
            "issues": [],
        },
        "security": {
            "sanitized": True,
            "network_called": False,
            "connector_called": False,
            "external_side_effects": False,
            "permissions_expanded": False,
            "secrets_included": False,
        },
        "executes_action": False,
        "external_action_executed": False,
        "real_orders_enabled": False,
        "tool_output_is_authority": False,
    }


class LocalSynthesisTests(unittest.TestCase):
    def test_success_does_not_promote_unknown_content(self):
        out = synthesize_local_tool_results([
            _envelope("aion.tasks.summary"),
            _envelope("aion.memory.search"),
        ])
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "SYNTHESIZED")
        self.assertEqual(out["execution_confirmed_count"], 2)
        self.assertEqual(out["content_confirmed_count"], 0)
        self.assertEqual(out["truth"]["status"], "UNKNOWN")
        self.assertEqual(len(out["unknowns"]), 2)
        self.assertFalse(out["tool_output_is_authority"])

    def test_confirmed_requires_explicit_truth_and_freshness(self):
        out = synthesize_local_tool_results([
            _envelope("aion.specialists.snapshot", truth="CONFIRMED", freshness="FRESH"),
            _envelope("aion.checkpoint.inspect", truth="CONFIRMED", freshness="NOT_APPLICABLE"),
        ])
        self.assertEqual(out["truth"]["status"], "CONFIRMED")
        self.assertEqual(out["content_confirmed_count"], 2)
        self.assertEqual(out["unknowns"], [])
        self.assertFalse(out["truth"]["authority"])

    def test_unverified_confirmed_content_stays_unknown(self):
        out = synthesize_local_tool_results([
            _envelope("aion.specialists.snapshot", truth="CONFIRMED", freshness="UNVERIFIED"),
        ])
        self.assertEqual(out["truth"]["status"], "UNKNOWN")
        self.assertEqual(out["content_confirmed_count"], 0)
        self.assertEqual(out["unknowns"][0]["reason"], "FRESHNESS_UNVERIFIED")

    def test_explicit_conflict_blocks_aggregate_confirmation(self):
        out = synthesize_local_tool_results([
            _envelope(
                "aion.status.read",
                truth="CONFIRMED",
                freshness="FRESH",
                result={"conflict_count": 2, "conflicts": [{"claim": "release"}]},
            ),
        ])
        self.assertEqual(out["state"], "CONFLICT")
        self.assertEqual(out["truth"]["status"], "UNKNOWN")
        self.assertGreaterEqual(len(out["conflicts"]), 1)
        self.assertIn("conflitantes", out["next_step"])

    def test_integrity_mismatch_is_treated_as_conflict(self):
        out = synthesize_local_tool_results([
            _envelope(
                "aion.checkpoint.inspect",
                truth="CONFIRMED",
                freshness="FRESH",
                result={"integrity": {"mismatches": ["digest"]}},
            ),
        ])
        self.assertEqual(out["state"], "CONFLICT")
        self.assertEqual(out["truth"]["status"], "UNKNOWN")

    def test_blocked_tool_makes_partial_and_keeps_blocker_metadata(self):
        out = synthesize_local_tool_results([
            _envelope("aion.memory.search"),
            _envelope("aion.tasks.summary", state="BLOCKED", blockers=["GUARDIAN_DENIED"]),
        ])
        self.assertEqual(out["state"], "PARTIAL")
        self.assertEqual(out["execution_confirmed_count"], 1)
        self.assertEqual(out["truth"]["status"], "UNKNOWN")
        self.assertEqual(out["items"][1]["blockers"], ["GUARDIAN_DENIED"])

    def test_security_invariant_violation_fails_closed(self):
        bad = _envelope("aion.tasks.summary")
        bad["security"]["network_called"] = True
        out = synthesize_local_tool_results([bad])
        self.assertEqual(out["state"], "SECURITY_BLOCK")
        self.assertEqual(out["security"]["state"], "BLOCK")
        self.assertEqual(out["truth"]["status"], "UNKNOWN")
        self.assertEqual(out["execution_confirmed_count"], 0)
        self.assertIn("não usar o conteúdo", out["next_step"])

    def test_no_results_is_non_actionable(self):
        out = synthesize_local_tool_results([])
        self.assertEqual(out["state"], "NO_RESULTS")
        self.assertEqual(out["truth"]["status"], "UNKNOWN")
        self.assertFalse(out["executes_action"])
        self.assertFalse(out["external_action_executed"])
        self.assertFalse(out["real_orders_enabled"])


if __name__ == "__main__":
    unittest.main()
