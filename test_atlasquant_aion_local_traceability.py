import unittest
from copy import deepcopy

from atlasquant_aion_local_response import compose_local_executive_response
from atlasquant_aion_local_traceability import SOURCE_CATALOG, build_local_traceability, local_contract_fingerprint
from atlasquant_aion_tool_hub import default_tool_hub


def _envelope(tool_id, *, request_id="req-1", state="SUCCESS", truth="UNKNOWN", freshness="UNVERIFIED", result=None):
    return {
        "tool_id": tool_id,
        "request_id": request_id,
        "workspace_id": "administration",
        "kind": "READ",
        "contract_fingerprint": local_contract_fingerprint(),
        "state": state,
        "result": result or {},
        "preflight": {"state": "READY_FOR_EXECUTOR" if state == "SUCCESS" else "BLOCK", "blockers": [] if state == "SUCCESS" else ["GUARDIAN_DENIED"]},
        "provenance": {"source_module": "atlasquant_aion_local_executor", "source_function": "_test", "input_scope": "local", "local_only": True},
        "truth": {"status": truth, "freshness": freshness},
        "security": {"network_called": False, "connector_called": False, "external_side_effects": False, "permissions_expanded": False, "secrets_included": False},
        "executes_action": False,
        "external_action_executed": False,
        "real_orders_enabled": False,
        "tool_output_is_authority": False,
    }


def _synthesis(tool_id, *, confirmed=False, conflict=False):
    return {
        "items": [{"tool_id": tool_id, "state": "SUCCESS", "truth_status": "CONFIRMED" if confirmed else "UNKNOWN", "freshness": "FRESH" if confirmed else "UNVERIFIED", "execution_confirmed": True, "content_confirmed": confirmed, "blockers": []}],
        "conflicts": [f"{tool_id}:EXPLICIT_CONFLICTS=1"] if conflict else [],
        "truth": {"status": "CONFIRMED" if confirmed and not conflict else "UNKNOWN", "freshness": "FRESH" if confirmed and not conflict else "UNVERIFIED", "authority": False},
        "security": {"state": "SAFE_LOCAL"},
        "tool_count": 1,
        "execution_confirmed_count": 1,
        "content_confirmed_count": 1 if confirmed else 0,
        "next_step": "Revisar evidência.",
        "tool_output_is_authority": False,
    }


class LocalTraceabilityTests(unittest.TestCase):
    def test_catalog_covers_the_eleven_local_tools(self):
        self.assertEqual(len(SOURCE_CATALOG), 11)
        self.assertEqual(len(set(SOURCE_CATALOG)), 11)

    def test_contract_fingerprint_is_deterministic_and_detects_contract_drift(self):
        hub = default_tool_hub()
        first = local_contract_fingerprint(hub)
        again = local_contract_fingerprint(deepcopy(hub))
        self.assertEqual(first, again)
        self.assertRegex(first, r"^AION-LCL-[0-9A-F]{16}$")

        mutated = deepcopy(hub)
        for tool in mutated["tools"]:
            if tool["tool_id"] == "aion.tasks.summary":
                tool["required_scopes"] = ["tasks:read", "unexpected:scope"]
        self.assertNotEqual(first, local_contract_fingerprint(mutated))

    def test_trace_id_is_deterministic_and_excludes_result_payload(self):
        first = _envelope("aion.tasks.summary", result={"senha": "primeiro-segredo"})
        second = _envelope("aion.tasks.summary", result={"senha": "outro-segredo"})
        a = build_local_traceability([first], synthesis=_synthesis("aion.tasks.summary"))
        b = build_local_traceability([second], synthesis=_synthesis("aion.tasks.summary"))
        self.assertEqual(a["records"][0]["trace_id"], b["records"][0]["trace_id"])
        rendered = str(a)
        self.assertNotIn("primeiro-segredo", rendered)
        self.assertNotIn("senha", rendered)
        self.assertFalse(a["raw_result_included"])

    def test_source_mapping_is_explicit(self):
        out = build_local_traceability([_envelope("aion.memory.search")], synthesis=_synthesis("aion.memory.search"))
        row = out["records"][0]
        self.assertEqual(row["source_key"], "canonical_memory")
        self.assertEqual(row["source_label"], "Memória canônica")
        self.assertTrue(row["local_only"])
        self.assertRegex(row["contract_fingerprint"], r"^AION-LCL-[0-9A-F]{16}$")
        self.assertTrue(out["contract_consistent"])
        self.assertFalse(row["authority"])

    def test_unknown_truth_is_not_promoted(self):
        out = build_local_traceability([_envelope("aion.tasks.summary")], synthesis=_synthesis("aion.tasks.summary"))
        row = out["records"][0]
        self.assertEqual(row["truth_status"], "UNKNOWN")
        self.assertFalse(row["content_confirmed"])
        self.assertIn(row["trace_id"], out["unknown_refs"])
        self.assertEqual(out["confirmed_content_refs"], [])

    def test_confirmed_content_gets_reference_without_authority(self):
        out = build_local_traceability(
            [_envelope("aion.specialists.snapshot", truth="CONFIRMED", freshness="FRESH")],
            synthesis=_synthesis("aion.specialists.snapshot", confirmed=True),
        )
        row = out["records"][0]
        self.assertTrue(row["content_confirmed"])
        self.assertIn(row["trace_id"], out["confirmed_content_refs"])
        self.assertFalse(out["tool_output_is_authority"])

    def test_conflict_links_to_source_record(self):
        out = build_local_traceability(
            [_envelope("aion.status.read", truth="CONFIRMED", freshness="FRESH")],
            synthesis=_synthesis("aion.status.read", conflict=True),
        )
        row = out["records"][0]
        self.assertEqual(out["state"], "CONFLICT")
        self.assertTrue(row["conflicts"])
        self.assertEqual(out["conflict_refs"], [row["trace_id"]])

    def test_security_violation_fails_closed(self):
        bad = _envelope("aion.tasks.summary")
        bad["security"]["network_called"] = True
        out = build_local_traceability([bad], synthesis=_synthesis("aion.tasks.summary"))
        self.assertEqual(out["state"], "SECURITY_BLOCK")
        self.assertEqual(out["security"]["state"], "BLOCK")
        self.assertFalse(out["external_action_executed"])

    def test_missing_contract_fingerprint_fails_closed(self):
        item = _envelope("aion.tasks.summary")
        item.pop("contract_fingerprint")
        out = build_local_traceability([item], synthesis=_synthesis("aion.tasks.summary"))
        self.assertEqual(out["state"], "SECURITY_BLOCK")
        self.assertEqual(out["security"]["state"], "BLOCK")
        self.assertFalse(out["contract_consistent"])
        self.assertIn(
            "CONTRACT_FINGERPRINT_INVALID",
            out["records"][0]["security_issues"],
        )

    def test_mixed_contract_fingerprints_fail_closed(self):
        first = _envelope("aion.memory.search")
        second = _envelope("aion.tasks.summary")
        first["contract_fingerprint"] = "AION-LCL-" + ("A" * 16)
        second["contract_fingerprint"] = "AION-LCL-" + ("B" * 16)
        synthesis = {
            "items": [
                {"tool_id": "aion.memory.search", "state": "SUCCESS", "truth_status": "UNKNOWN", "freshness": "UNVERIFIED", "execution_confirmed": True, "content_confirmed": False, "blockers": []},
                {"tool_id": "aion.tasks.summary", "state": "SUCCESS", "truth_status": "UNKNOWN", "freshness": "UNVERIFIED", "execution_confirmed": True, "content_confirmed": False, "blockers": []},
            ],
            "conflicts": [],
        }
        out = build_local_traceability([first, second], synthesis=synthesis)
        self.assertEqual(out["state"], "SECURITY_BLOCK")
        self.assertFalse(out["contract_consistent"])
        self.assertTrue(out["contract_mismatch"])
        self.assertEqual(len(out["contract_fingerprints"]), 2)
        self.assertEqual(out["security"]["state"], "BLOCK")

    def test_executive_response_references_trace_ids(self):
        synthesis = _synthesis("aion.tasks.summary")
        trace = build_local_traceability([_envelope("aion.tasks.summary")], synthesis=synthesis)
        out = compose_local_executive_response(synthesis, summaries=["Tarefas: total 2."], traceability=trace)
        trace_id = trace["records"][0]["trace_id"]
        self.assertIn(trace_id, out["evidence_refs"]["unknown"])
        self.assertIn(trace_id, out["sections"]["unknown"][0])
        self.assertFalse(out["truth"]["authority"])

    def test_no_evidence_is_non_actionable(self):
        out = build_local_traceability([])
        self.assertEqual(out["state"], "NO_EVIDENCE")
        self.assertFalse(out["executes_action"])
        self.assertFalse(out["private_chain_of_thought_exposed"])


if __name__ == "__main__":
    unittest.main()
