import unittest

from atlasquant_aion_orchestrator import orchestrate
from atlasquant_aion_specialists import plan_specialist_dispatch, specialist_catalog


class AionSpecialistTests(unittest.TestCase):
    def test_catalog_reuses_shared_infrastructure(self):
        catalog = specialist_catalog()
        ids = {row["specialist"] for row in catalog["specialists"]}
        self.assertTrue({"core", "dev", "research", "market", "risk", "lab", "invest", "business", "studio", "admin"}.issubset(ids))
        self.assertFalse(catalog["duplicate_infrastructure_created"])
        self.assertTrue(all(not row["independent_permissions"] for row in catalog["specialists"]))

    def test_core_to_specialist_dispatch_is_selective(self):
        plan = orchestrate(
            "Explique o Radar Forex",
            context={"role": "USER", "domain_hint": "market"},
        )
        dispatch = plan_specialist_dispatch(plan)
        self.assertEqual(dispatch["state"], "READY")
        self.assertEqual(dispatch["specialist"], "market")
        self.assertEqual(dispatch["module"], "atlasquant_radar_board")
        self.assertFalse(dispatch["provider_called"])
        self.assertFalse(dispatch["tool_called"])

    def test_unavailable_provider_or_tool_has_safe_fallback(self):
        plan = orchestrate(
            "Pesquise documentação",
            context={"role": "USER"},
            requested_capability="research.synthesize",
        )
        dispatch = plan_specialist_dispatch(
            plan,
            runtime_availability={
                "research": "UNAVAILABLE",
                "aion.memory.search": "UNAVAILABLE",
            },
        )
        self.assertEqual(dispatch["state"], "DEGRADED_SAFE")
        self.assertIn("SPECIALIST_UNAVAILABLE", dispatch["blockers"])
        self.assertIn("TOOL_UNAVAILABLE", dispatch["blockers"])
        self.assertFalse(dispatch["fallback"]["may_invent_missing_result"])
        self.assertFalse(dispatch["permissions_expanded"])

    def test_invalid_capability_never_dispatches(self):
        plan = orchestrate(
            "use algo inexistente",
            context={"role": "ADMIN"},
            requested_capability="missing.capability",
        )
        dispatch = plan_specialist_dispatch(plan)
        self.assertEqual(dispatch["state"], "DEGRADED_SAFE")
        self.assertIn("SPECIALIST_NOT_REGISTERED", dispatch["blockers"])


if __name__ == "__main__":
    unittest.main()
