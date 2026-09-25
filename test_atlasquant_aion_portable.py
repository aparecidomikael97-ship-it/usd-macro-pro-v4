from __future__ import annotations

import unittest

from atlasquant_aion_portable import (
    central_entry_contract,
    default_portable_core,
    new_connector,
    normalize_portable_core,
    portable_core_summary,
)


class AtlasQuantAionPortableTests(unittest.TestCase):
    def test_atlasquant_is_workspace_not_entire_aion_identity(self):
        state = default_portable_core()
        self.assertEqual(state["identity"], "AION")
        ids = {x["workspace_id"] for x in state["workspaces"]}
        self.assertIn("central", ids)
        self.assertIn("atlasquant", ids)
        self.assertTrue(state["central_shell"]["single_entry"])
        self.assertFalse(state["real_trading_enabled"])

    def test_external_connector_defaults_fail_closed(self):
        connector = new_connector(
            "github-dev",
            label="GitHub Dev",
            protocol="MCP",
            workspace_id="development",
            scopes=["read_repo"],
        )
        self.assertFalse(connector["enabled"])
        self.assertFalse(connector["activation_approved"])
        self.assertTrue(connector["requires_guardian"])
        self.assertFalse(connector["may_expand_own_permissions"])

    def test_connector_rejects_obvious_secret_value_in_secret_refs(self):
        with self.assertRaises(ValueError):
            new_connector(
                "bad-github",
                label="Bad",
                protocol="MCP",
                workspace_id="development",
                secret_refs=[("g" + "hp_" + "synthetic-value")],
            )

    def test_unknown_connector_workspace_is_dropped(self):
        raw = default_portable_core()
        raw["connectors"] = [{
            "connector_id": "x-connector",
            "label": "X",
            "protocol": "API",
            "workspace_id": "does-not-exist",
            "state": "READY",
        }]
        state = normalize_portable_core(raw)
        self.assertEqual(state["connectors"], [])

    def test_single_link_contract_requires_admin(self):
        denied = central_entry_contract(authenticated_admin=False)
        allowed = central_entry_contract(authenticated_admin=True)
        self.assertFalse(denied["allowed"])
        self.assertTrue(allowed["allowed"])
        self.assertEqual(allowed["target_workspace"], "central")
        self.assertFalse(allowed["creates_domain"])

    def test_summary_is_portable_and_no_vendor_lock_requirement(self):
        state = default_portable_core()
        summary = portable_core_summary(state)
        self.assertGreaterEqual(summary["workspaces"], 6)
        self.assertTrue(summary["single_entry"])
        self.assertTrue(summary["pwa_target"])
        self.assertFalse(summary["real_trading_enabled"])


if __name__ == "__main__":
    unittest.main()
