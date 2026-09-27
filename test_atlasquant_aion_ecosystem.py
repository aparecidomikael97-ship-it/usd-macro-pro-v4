import unittest

from atlasquant_aion_capabilities import DEFAULT_CAPABILITIES
from atlasquant_aion_ecosystem import (
    FORBIDDEN_ACTIONS,
    OFFICIAL_AREA_IDS,
    ecosystem_area,
    ecosystem_capabilities,
    ecosystem_integrity_report,
    ecosystem_persona,
    ecosystem_registry,
    ecosystem_specialist,
    persona_catalog,
    portable_workspaces,
    specialist_modules,
)
from atlasquant_aion_portable import DEFAULT_WORKSPACES, default_portable_core
from atlasquant_aion_specialists import SPECIALIST_MODULES, specialist_catalog
from atlasquant_aion_workspaces import (
    AION_PERSONAS,
    PERSONA_CAPABILITIES,
    authorize_workspace_action,
    capability_snapshot,
)

ADMIN = {"role": "ADMIN", "session": {"username": "mikael", "role": "ADMIN"}}


class EcosystemRegistryTests(unittest.TestCase):
    def test_registry_contains_exactly_the_eight_official_areas(self):
        registry = ecosystem_registry()
        ids = [area["area_id"] for area in registry["areas"]]
        self.assertEqual(ids, list(OFFICIAL_AREA_IDS))
        self.assertEqual(len(ids), 8)

    def test_workspace_ids_are_unique(self):
        ids = [area["workspace_id"] for area in ecosystem_registry()["areas"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_persona_ids_are_unique(self):
        ids = [area["persona_id"] for area in ecosystem_registry()["areas"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_investments_links_workspace_persona_specialist_and_capability(self):
        area = ecosystem_area("investments")
        self.assertIsNotNone(area)
        self.assertEqual(area["workspace_id"], "investments")
        self.assertEqual(area["persona_id"], "investments")
        self.assertEqual(area["label"], "Investimentos")
        self.assertEqual(area["kind"], "INVESTMENTS")
        self.assertTrue(area["admin_only"])
        self.assertIn("invest", area["specialist_ids"])
        self.assertIn("invest.compare", area["capability_ids"])
        self.assertEqual(ecosystem_specialist("invest")["module"], "atlasquant_investment_ecosystem")
        self.assertFalse(ecosystem_specialist("invest")["independent_permissions"])
        persona = ecosystem_persona("investments")
        self.assertEqual(persona["title"], "AION Investimentos")
        self.assertEqual(persona["purpose"], "Comparar produtos e cenários com evidência; nunca movimentar dinheiro.")
        self.assertEqual(persona["allowed_actions"], ("read", "summarize", "search", "draft"))

    def test_default_workspaces_are_derived_and_include_investments(self):
        self.assertEqual(DEFAULT_WORKSPACES, portable_workspaces())
        ids = [item["workspace_id"] for item in DEFAULT_WORKSPACES]
        self.assertEqual(ids[0], "central")
        self.assertIn("investments", ids)
        self.assertIn("laboratory", ids)
        investments = next(item for item in DEFAULT_WORKSPACES if item["workspace_id"] == "investments")
        self.assertEqual(set(investments), {
            "workspace_id", "label", "kind", "state", "isolated_context", "admin_only", "entry_key",
        })
        self.assertTrue(investments["admin_only"])
        self.assertTrue(investments["isolated_context"])

    def test_personas_are_derived_and_include_investments(self):
        self.assertEqual(AION_PERSONAS, persona_catalog())
        ids = [item["id"] for item in AION_PERSONAS]
        self.assertIn("investments", ids)
        self.assertEqual(PERSONA_CAPABILITIES["investments"], (
            "products", "rates", "liquidity", "risk", "income", "comparison", "sources",
        ))
        trader = next(item for item in AION_PERSONAS if item["id"] == "trader")
        self.assertEqual(set(trader), {"id", "title", "workspace", "domain", "purpose", "actions"})
        self.assertEqual(trader["actions"], ("read", "summarize", "search", "draft"))
        admin = next(item for item in AION_PERSONAS if item["id"] == "admin")
        self.assertEqual(admin["actions"], (
            "read", "summarize", "search", "draft", "save_checkpoint", "restore_checkpoint",
        ))

    def test_specialist_modules_only_reference_known_specialists(self):
        known = {row["specialist_id"] for row in ecosystem_registry()["specialists"]}
        self.assertEqual(SPECIALIST_MODULES, specialist_modules())
        self.assertTrue(set(SPECIALIST_MODULES) <= known)
        self.assertEqual(set(SPECIALIST_MODULES), known)
        for specialist_id, module in SPECIALIST_MODULES.items():
            self.assertEqual(ecosystem_specialist(specialist_id)["module"], module)
            self.assertTrue(module)

    def test_default_capabilities_use_existing_specialists(self):
        known = set(SPECIALIST_MODULES)
        self.assertGreaterEqual(len(DEFAULT_CAPABILITIES), 13)
        for capability in DEFAULT_CAPABILITIES:
            self.assertIn(capability.specialist, known, capability.capability_id)

    def test_every_canonical_capability_belongs_to_at_least_one_area(self):
        assigned = []
        for area_id in OFFICIAL_AREA_IDS:
            assigned.extend(ecosystem_capabilities(area_id))
        for capability in DEFAULT_CAPABILITIES:
            self.assertIn(capability.capability_id, assigned, capability.capability_id)

    def test_no_area_enables_forbidden_actions_or_authority(self):
        blocked = {"real_trade", "merge_main", "deploy_production", "read_secret", "write_secret"}
        self.assertEqual(blocked, set(FORBIDDEN_ACTIONS))
        for area in ecosystem_registry()["areas"]:
            self.assertFalse(set(area["allowed_actions"]) & blocked, area["area_id"])
            self.assertIs(area["external_action_authority"], False)
            self.assertIs(area["real_trading_enabled"], False)

    def test_authorize_workspace_action_still_blocks_forbidden_actions(self):
        flags = {k: True for k in ("real_broker_execution", "production_deploy", "auto_merge")}
        for action in FORBIDDEN_ACTIONS:
            out = authorize_workspace_action(
                "investments", action, ADMIN, approved=True, feature_flags=flags,
            )
            self.assertFalse(out["allowed"], action)
            self.assertFalse(out["executes_action"])
            self.assertEqual(out["layer"], "scope")

    def test_investments_capability_snapshot_requires_explicit_evidence(self):
        bare = capability_snapshot("investments")
        self.assertEqual(bare["state"], "UNAVAILABLE")
        self.assertEqual(bare["connected"], 0)
        self.assertTrue(all(row["state"] == "UNAVAILABLE" for row in bare["capabilities"]))
        self.assertFalse(bare["executes_action"])
        self.assertFalse(bare["real_orders_enabled"])
        confirmed = capability_snapshot("investments", {
            "comparison": {"truth_state": "CONFIRMED", "source": "explicit-evidence"},
        })
        states = {row["capability"]: row["state"] for row in confirmed["capabilities"]}
        self.assertEqual(states["comparison"], "CONNECTED")
        self.assertEqual(states["products"], "UNAVAILABLE")
        self.assertEqual(confirmed["state"], "CONNECTED")

    def test_default_portable_core_keeps_investments_offline(self):
        state = default_portable_core()
        ids = [item["workspace_id"] for item in state["workspaces"]]
        self.assertIn("investments", ids)
        self.assertEqual(state["connectors"], [])
        self.assertIs(state["real_trading_enabled"], False)
        self.assertIs(state["external_connectors_default_enabled"], False)
        investments = next(item for item in state["workspaces"] if item["workspace_id"] == "investments")
        self.assertIs(investments["real_trading_enabled"], False)
        self.assertIs(investments["external_action_authority"], False)

    def test_specialist_catalog_does_not_duplicate_infrastructure(self):
        catalog = specialist_catalog()
        self.assertIs(catalog["duplicate_infrastructure_created"], False)
        self.assertGreaterEqual(catalog["specialist_count"], 12)
        for row in catalog["specialists"]:
            self.assertIs(row["independent_permissions"], False)
            self.assertIs(row["shared_infrastructure"], True)

    def test_default_integrity_report_is_valid(self):
        report = ecosystem_integrity_report()
        self.assertEqual(report["schema"], "ATLASQUANT_AION_ECOSYSTEM_V1")
        self.assertEqual(report["state"], "VALID", report["errors"])
        self.assertEqual(report["areas"], 8)
        self.assertEqual(report["workspaces"], 8)
        self.assertEqual(report["personas"], 8)
        self.assertEqual(report["specialists"], 12)
        self.assertEqual(report["capabilities"], len(DEFAULT_CAPABILITIES))
        self.assertEqual(report["errors"], [])
        self.assertIs(report["real_trading_enabled"], False)
        self.assertIs(report["external_action_authority"], False)


class EcosystemIntegrityFailureTests(unittest.TestCase):
    def test_missing_specialist_is_invalid(self):
        registry = ecosystem_registry()
        registry["areas"][0]["specialist_ids"] = tuple(registry["areas"][0]["specialist_ids"]) + ("ghost",)
        report = ecosystem_integrity_report(registry)
        self.assertEqual(report["state"], "INVALID")
        self.assertTrue(any("specialist ausente" in error for error in report["errors"]))
        self.assertIs(report["real_trading_enabled"], False)

    def test_missing_capability_is_invalid(self):
        registry = ecosystem_registry()
        registry["areas"][0]["capability_ids"] = tuple(registry["areas"][0]["capability_ids"]) + ("missing.capability",)
        report = ecosystem_integrity_report(registry)
        self.assertEqual(report["state"], "INVALID")
        self.assertTrue(any("capability ausente" in error for error in report["errors"]))

    def test_duplicate_workspace_is_invalid(self):
        registry = ecosystem_registry()
        extra = dict(registry["areas"][0])
        extra["area_id"] = "central_copy"
        extra["persona_id"] = "central_copy"
        extra["entry_key"] = "central_copy"
        registry["areas"].append(extra)
        report = ecosystem_integrity_report(registry)
        self.assertEqual(report["state"], "INVALID")
        self.assertTrue(any(error.startswith("workspace duplicado:") for error in report["errors"]))

    def test_duplicate_persona_is_invalid(self):
        registry = ecosystem_registry()
        extra = dict(registry["areas"][1])
        extra["area_id"] = "atlasquant_copy"
        extra["workspace_id"] = "atlasquant_copy"
        extra["entry_key"] = "atlasquant_copy"
        registry["areas"].append(extra)
        report = ecosystem_integrity_report(registry)
        self.assertEqual(report["state"], "INVALID")
        self.assertTrue(any(error.startswith("persona duplicada:") for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
