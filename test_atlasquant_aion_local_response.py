import unittest

from atlasquant_aion_local_response import compose_local_executive_response


def _synthesis(
    *,
    truth="UNKNOWN",
    freshness="UNVERIFIED",
    security="SAFE_LOCAL",
    items=None,
    conflicts=None,
    next_step="Buscar evidência melhor.",
):
    rows = list(items or [])
    return {
        "schema": "ATLASQUANT_AION_LOCAL_SYNTHESIS_V1",
        "state": "SYNTHESIZED",
        "items": rows,
        "tool_count": len(rows),
        "execution_confirmed_count": sum(1 for row in rows if row.get("execution_confirmed")),
        "content_confirmed_count": sum(1 for row in rows if row.get("content_confirmed")),
        "truth": {"status": truth, "freshness": freshness, "authority": False},
        "conflicts": list(conflicts or []),
        "unknowns": [],
        "security": {
            "state": security,
            "network_called": False if security != "BLOCK" else None,
            "connector_called": False if security != "BLOCK" else None,
            "external_side_effects": False if security != "BLOCK" else None,
            "external_action_executed": False if security != "BLOCK" else None,
            "real_orders_enabled": False if security != "BLOCK" else None,
        },
        "next_step": next_step,
        "tool_output_is_authority": False,
    }


class LocalExecutiveResponseTests(unittest.TestCase):
    def test_unknown_content_never_moves_into_known(self):
        syn = _synthesis(items=[{
            "tool_id": "aion.tasks.summary",
            "state": "SUCCESS",
            "truth_status": "UNKNOWN",
            "freshness": "UNVERIFIED",
            "execution_confirmed": True,
            "content_confirmed": False,
            "blockers": [],
        }])
        out = compose_local_executive_response(syn, summaries=["Tarefas: total 3 · ativas 2."])
        self.assertEqual(out["posture"], "PARTIAL")
        self.assertEqual(len(out["sections"]["known"]), 1)
        self.assertIn("invariantes de segurança", out["sections"]["known"][0])
        self.assertEqual(len(out["sections"]["unknown"]), 1)
        self.assertIn("verdade UNKNOWN", out["sections"]["unknown"][0])
        self.assertFalse(out["truth"]["authority"])
        self.assertFalse(out["tool_output_is_authority"])

    def test_confirmed_fresh_content_is_shown_as_known(self):
        syn = _synthesis(
            truth="CONFIRMED",
            freshness="FRESH",
            items=[{
                "tool_id": "aion.specialists.snapshot",
                "state": "SUCCESS",
                "truth_status": "CONFIRMED",
                "freshness": "FRESH",
                "execution_confirmed": True,
                "content_confirmed": True,
                "blockers": [],
            }],
        )
        out = compose_local_executive_response(
            syn,
            summaries=["Especialista: input READY · verdade CONFIRMED · freshness FRESH."],
        )
        self.assertEqual(out["posture"], "CONFIRMED")
        self.assertTrue(any("Especialista:" in x for x in out["sections"]["known"]))
        self.assertEqual(out["sections"]["unknown"], [])
        self.assertTrue(out["safe_to_display"])

    def test_conflict_is_explicit_and_not_hidden(self):
        syn = _synthesis(
            items=[],
            conflicts=["aion.checkpoint.inspect:INTEGRITY_MISMATCHES=1"],
        )
        out = compose_local_executive_response(syn)
        self.assertEqual(out["posture"], "CONFLICT")
        self.assertEqual(len(out["sections"]["conflicts"]), 1)
        self.assertIn("INTEGRITY_MISMATCHES", out["plain_text"])

    def test_security_block_is_not_safe_to_display_as_normal_content(self):
        syn = _synthesis(security="BLOCK", items=[{
            "tool_id": "aion.tasks.summary",
            "state": "SUCCESS",
            "truth_status": "UNKNOWN",
            "freshness": "UNVERIFIED",
            "execution_confirmed": False,
            "content_confirmed": False,
            "blockers": [],
        }])
        out = compose_local_executive_response(syn, summaries=["Tarefas: total 3."])
        self.assertEqual(out["posture"], "SECURITY_BLOCK")
        self.assertFalse(out["safe_to_display"])
        self.assertTrue(out["sections"]["conflicts"])
        self.assertFalse(out["external_action_executed"])
        self.assertFalse(out["real_orders_enabled"])

    def test_blocked_execution_stays_unknown(self):
        syn = _synthesis(items=[{
            "tool_id": "aion.tasks.summary",
            "state": "BLOCKED",
            "truth_status": "UNKNOWN",
            "freshness": "UNVERIFIED",
            "execution_confirmed": False,
            "content_confirmed": False,
            "blockers": ["GUARDIAN_DENIED"],
        }])
        out = compose_local_executive_response(syn, summaries=["aion.tasks.summary: handler não executado."])
        self.assertIn("GUARDIAN_DENIED", out["sections"]["unknown"][0])
        self.assertEqual(out["truth"]["status"], "UNKNOWN")

    def test_no_data_remains_non_actionable(self):
        out = compose_local_executive_response(_synthesis(items=[]))
        self.assertEqual(out["posture"], "NO_DATA")
        self.assertFalse(out["executes_action"])
        self.assertFalse(out["external_action_executed"])
        self.assertFalse(out["real_orders_enabled"])


if __name__ == "__main__":
    unittest.main()
