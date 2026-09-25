from __future__ import annotations
import unittest

from atlasquant_aion_portable import default_portable_core, new_connector
from atlasquant_aion_tool_hub import (
    default_tool_hub, plan_tool_call, tool_hub_summary,
)


class AtlasQuantAionToolHubTests(unittest.TestCase):
    def setUp(self):
        self.admin={"role":"ADMIN","username":"admin"}

    def test_default_hub_is_local_and_non_executing(self):
        hub=default_tool_hub()
        summary=tool_hub_summary(hub,default_portable_core())
        self.assertGreaterEqual(summary["local_ready"],2)
        self.assertEqual(summary["active_external_tools"],0)
        self.assertFalse(summary["auto_execute"])

    def test_external_source_cannot_command_local_tool(self):
        plan=plan_tool_call(
            "aion.memory.search",
            hub=default_tool_hub(),
            portable_core=default_portable_core(),
            access=self.admin,
            source_kind="EXTERNAL_AI",
            authenticated_admin=False,
            scope="Buscar memória.",
            uncertainty_pct=5,
            impact="LOW",
        )
        self.assertEqual(plan["state"],"BLOCK")
        self.assertIn("SOURCE_HAS_NO_COMMAND_AUTHORITY",plan["blockers"])
        self.assertFalse(plan["tool_called"])

    def test_registered_but_not_activated_connector_stays_blocked(self):
        core=default_portable_core()
        connector=new_connector(
            "github-dev",
            label="GitHub Dev",
            protocol="MCP",
            workspace_id="development",
            state="READY",
            scopes=["repo:read"],
        )
        core["connectors"]=[connector]
        hub=default_tool_hub()
        hub["tools"].append({
            "tool_id":"dev.repo.read",
            "label":"Repo read",
            "workspace_id":"development",
            "connector_id":"github-dev",
            "kind":"READ",
            "guardian_action":"read",
            "state":"CONFIGURED",
            "required_scopes":["repo:read"],
            "external_side_effects":False,
        })
        plan=plan_tool_call(
            "dev.repo.read",
            hub=hub,
            portable_core=core,
            access=self.admin,
            source_kind="ADMIN",
            authenticated_admin=True,
            scope="Ler repositório.",
            uncertainty_pct=0,
            impact="LOW",
        )
        self.assertEqual(plan["state"],"BLOCK")
        self.assertIn("CONNECTOR_NOT_ACTIVATED",plan["blockers"])

    def test_sensitive_checkpoint_tool_still_requires_guardian_approval(self):
        plan=plan_tool_call(
            "aion.checkpoint.prepare_save",
            hub=default_tool_hub(),
            portable_core=default_portable_core(),
            access=self.admin,
            source_kind="ADMIN",
            authenticated_admin=True,
            approved=False,
            scope="Preparar checkpoint.",
            tests=[{"state":"PASS"}],
            rollback_plan="Restaurar versão anterior.",
            uncertainty_pct=5,
            impact="MEDIUM",
            reversible=True,
        )
        self.assertEqual(plan["state"],"BLOCK")
        self.assertIn("GUARDIAN_DENIED",plan["blockers"])


if __name__=="__main__":
    unittest.main()
