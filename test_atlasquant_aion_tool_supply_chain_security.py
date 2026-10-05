from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from atlasquant_aion_credential_proxy import (
    CredentialLeakError,
    CredentialProxy,
)
from atlasquant_aion_portable import default_portable_core
from atlasquant_aion_tool_hub import (
    default_tool_hub,
    normalize_tool_hub,
    plan_tool_call,
    tool_hub_summary,
)
from atlasquant_aion_tool_sandbox import validate_egress_request
from atlasquant_aion_tool_supply_chain import (
    PINNED_REGISTRY_DIGEST,
    enrich_tool_contract,
    registry_integrity_report,
    tool_contract_issues,
)
from atlasquant_aion_vault import (
    default_vault,
    new_vault_entry,
    upsert_vault_entry,
    vault_export_manifest,
    vault_summary,
)


NOW = datetime(2026, 10, 5, 6, 0, tzinfo=timezone.utc)
ADMIN = {"role": "ADMIN", "username": "mikael"}


def staging_probe():
    # Reviewed contract fixture only. It is deliberately NOT present in the
    # persistent/default Tool Hub, so it cannot become runtime authority.
    base = {
        "tool_id": "aion.staging.credential_probe",
        "label": "staging credential probe",
        "workspace_id": "development",
        "connector_id": "staging-proxy",
        "kind": "READ",
        "guardian_action": "read",
        "state": "DISABLED",
        "required_scopes": ["probe:read"],
        "external_side_effects": False,
    }
    return enrich_tool_contract(base, base)


def fake_ready_preflight(tool):
    return {
        "state": "READY_FOR_EXECUTOR",
        "tool": deepcopy(tool),
        "connector": {
            "required": True,
            "configured": True,
            "activated": True,
            "reason": "TEST_ONLY_ACTIVATED_PROXY",
        },
        "supply_chain": {
            "state": "VERIFIED",
            "contract_hash": tool["contract_hash"],
            "schema_hash": tool["schema_hash"],
            "issues": [],
        },
        "executes_action": False,
    }


def scoped_vault():
    entry = new_vault_entry(
        "staging-probe-secret",
        kind="SECRET_REF",
        backend="EXTERNAL_VAULT",
        locator_ref="secret/staging/aion/probe",
        allowed_tool_ids=["aion.staging.credential_probe"],
        credential_scopes=["probe:read"],
        label="staging probe credential reference",
    )
    vault = default_vault()
    vault["entries"] = upsert_vault_entry(vault["entries"], entry)
    return vault


class ClosedToolRegistryTests(unittest.TestCase):
    def test_registry_pin_is_verified_and_default_hub_is_fully_accounted(self):
        report = registry_integrity_report()
        self.assertEqual(report["state"], "VERIFIED")
        self.assertEqual(report["digest"], PINNED_REGISTRY_DIGEST)
        self.assertEqual(report["tool_count"], 13)
        self.assertFalse(report["automatic_tool_registration"])

        hub = default_tool_hub()
        summary = tool_hub_summary(hub, default_portable_core())
        self.assertEqual(len(hub["tools"]), 12)
        self.assertEqual(summary["supply_chain_verified"], 12)
        self.assertEqual(summary["supply_chain_blocked"], 0)
        self.assertEqual(summary["registry_state"], "VERIFIED")


    def test_schema_drift_breaks_the_pinned_contract(self):
        legacy = next(
            item for item in default_tool_hub()["tools"]
            if item["tool_id"] == "aion.memory.search"
        )
        secured = enrich_tool_contract(legacy, legacy)
        self.assertEqual(secured["supply_chain_state"], "VERIFIED")
        mutated = deepcopy(secured)
        mutated["input_schema"]["properties"]["query"]["maxLength"] = 501
        issues = tool_contract_issues(mutated)
        self.assertIn("TOOL_CONTRACT_DRIFT", issues)

    def test_version_owner_or_scope_drift_is_blocked(self):
        legacy = next(
            item for item in default_tool_hub()["tools"]
            if item["tool_id"] == "aion.memory.search"
        )
        secured = enrich_tool_contract(legacy, legacy)
        for field, value in (
            ("version", "1.0.1"),
            ("owner", "unreviewed-owner"),
        ):
            with self.subTest(field=field):
                mutated = deepcopy(secured)
                mutated[field] = value
                self.assertIn(
                    "TOOL_CONTRACT_DRIFT",
                    tool_contract_issues(mutated),
                )

        # Authority-relevant legacy fields are also contract-bound at preflight.
        hub = default_tool_hub()
        target = next(
            item for item in hub["tools"]
            if item["tool_id"] == "aion.memory.search"
        )
        target["required_scopes"] = ["memory:read", "secrets:read"]
        plan = plan_tool_call(
            "aion.memory.search",
            hub=hub,
            portable_core=default_portable_core(),
            access=ADMIN,
            source_kind="ADMIN",
            authenticated_admin=True,
            scope="read only",
            uncertainty_pct=0,
            impact="LOW",
            reversible=True,
        )
        self.assertEqual(plan["state"], "BLOCK")
        self.assertIn("TOOL_CONTRACT_DRIFT", plan["blockers"])

    def test_runtime_tool_injection_never_becomes_registered_by_appearing_in_hub(self):
        hub = default_tool_hub()
        hub["tools"].append({
            "tool_id": "third.party.shadow",
            "label": "shadow",
            "workspace_id": "development",
            "connector_id": "third-party",
            "kind": "READ",
            "guardian_action": "read",
            "state": "CONFIGURED",
            "required_scopes": ["repo:read"],
            "external_side_effects": False,
        })
        plan = plan_tool_call(
            "third.party.shadow",
            hub=hub,
            portable_core=default_portable_core(),
            access=ADMIN,
            source_kind="ADMIN",
            authenticated_admin=True,
            scope="read only",
            uncertainty_pct=0,
            impact="LOW",
            reversible=True,
        )
        self.assertEqual(plan["state"], "BLOCK")
        self.assertIn("TOOL_NOT_IN_CLOSED_REGISTRY", plan["blockers"])
        self.assertIn("TOOL_SUPPLY_CHAIN_UNVERIFIED", plan["blockers"])
        self.assertFalse(plan["tool_called"])

    def test_staging_probe_is_reviewed_but_absent_from_runtime_hub(self):
        tool = staging_probe()
        self.assertEqual(tool["supply_chain_state"], "VERIFIED")
        self.assertTrue(tool["registry_approved"])
        self.assertEqual(tool["state"], "DISABLED")
        self.assertEqual(tool["sandbox_profile"], "THIRD_PARTY_EGRESS_PROXY")
        self.assertNotIn(
            tool["tool_id"],
            {item["tool_id"] for item in default_tool_hub()["tools"]},
        )
        plan = plan_tool_call(
            tool["tool_id"],
            hub=default_tool_hub(),
            portable_core=default_portable_core(),
            access=ADMIN,
            source_kind="ADMIN",
            authenticated_admin=True,
            scope="staging probe",
            uncertainty_pct=0,
            impact="LOW",
            reversible=True,
        )
        self.assertEqual(plan["state"], "BLOCK")
        self.assertEqual(plan["reason"], "TOOL_NOT_REGISTERED")
        self.assertFalse(plan["executes_action"])
    def test_declared_schema_hash_cannot_spoof_real_schema(self):
        tool = staging_probe()
        mutated = deepcopy(tool)
        mutated["input_schema"]["required"] = []
        mutated["declared_schema_hash"] = tool["schema_hash"]
        enriched = enrich_tool_contract(mutated, mutated)
        issues = tool_contract_issues(enriched)
        self.assertIn("TOOL_CONTRACT_DRIFT", issues)
        self.assertIn("TOOL_DECLARED_SCHEMA_HASH_MISMATCH", issues)


class SandboxSsrfTests(unittest.TestCase):
    def setUp(self):
        self.tool = staging_probe()

    def test_allowed_host_with_public_post_dns_ip_passes(self):
        out = validate_egress_request(
            self.tool,
            "https://api.example.com/v1/items",
            ["8.8.8.8", "1.1.1.1"],
        )
        self.assertEqual(out["state"], "ALLOW")
        self.assertTrue(out["dns_rebinding_checked"])
        self.assertTrue(out["private_network_blocked"])

    def test_ssrf_private_metadata_loopback_and_rebinding_are_blocked(self):
        cases = (
            ("https://127.0.0.1/admin", ["127.0.0.1"]),
            ("https://169.254.169.254/latest/meta-data", ["169.254.169.254"]),
            ("https://10.0.0.1/internal", ["10.0.0.1"]),
            ("https://api.example.com/v1", ["127.0.0.1"]),
            ("https://api.example.com/v1", ["169.254.169.254"]),
            ("https://api.example.com/v1", ["::1"]),
        )
        for url, ips in cases:
            with self.subTest(url=url, ips=ips):
                with self.assertRaises(PermissionError):
                    validate_egress_request(self.tool, url, ips)

    def test_url_confusion_unlisted_host_http_and_custom_port_are_blocked(self):
        cases = (
            "https://api.example.com@169.254.169.254/latest",
            "http://api.example.com/v1",
            "https://evil.example/v1",
            "https://api.example.com:8443/v1",
            "https://2130706433/",
        )
        for url in cases:
            with self.subTest(url=url):
                with self.assertRaises(PermissionError):
                    validate_egress_request(self.tool, url, ["8.8.8.8"])


class CredentialProxyTests(unittest.TestCase):
    def setUp(self):
        self.tool = staging_probe()
        self.vault = scoped_vault()
        self.calls = []

        def resolver(backend, locator):
            self.calls.append((backend, locator))
            return "synthetic-staging-secret-value"

        self.proxy = CredentialProxy(
            self.vault,
            resolver,
            environment="STAGING",
        )

    def test_vault_manifest_contains_scope_but_never_secret_value(self):
        summary = vault_summary(self.vault)
        self.assertEqual(summary["scoped_secret_refs"], 1)
        self.assertEqual(summary["unscoped_secret_refs"], 0)
        exported = vault_export_manifest(self.vault)
        row = exported["entries"][0]
        self.assertEqual(
            row["allowed_tool_ids"],
            ["aion.staging.credential_probe"],
        )
        self.assertEqual(row["credential_scopes"], ["probe:read"])
        self.assertNotIn("synthetic-staging-secret-value", str(exported))
        self.assertFalse(exported["contains_secret_values"])

    def test_handle_is_opaque_and_does_not_contain_locator_or_secret(self):
        issued = self.proxy.issue_handle(
            self.tool,
            requested_scopes=["probe:read"],
            ttl_seconds=60,
            now=NOW,
        )
        rendered = str(issued)
        self.assertTrue(issued["opaque"])
        self.assertFalse(issued["contains_secret"])
        self.assertFalse(issued["contains_locator"])
        self.assertNotIn("secret/staging/aion/probe", rendered)
        self.assertNotIn("synthetic-staging-secret-value", rendered)
        self.assertEqual(self.calls, [])

    def test_secret_is_resolved_only_after_preflight_and_ssrf_checks(self):
        issued = self.proxy.issue_handle(
            self.tool,
            requested_scopes=["probe:read"],
            now=NOW,
        )
        with self.assertRaises(PermissionError):
            self.proxy.invoke_egress(
                issued["handle"],
                self.tool,
                url="https://api.example.com/v1",
                resolved_ips=["127.0.0.1"],
                preflight=fake_ready_preflight(self.tool),
                callback=lambda secret, ctx: {"ok": True},
                now=NOW + timedelta(seconds=1),
            )
        self.assertEqual(self.calls, [])

        # Invalid attempts do not consume or resolve the handle.
        out = self.proxy.invoke_egress(
            issued["handle"],
            self.tool,
            url="https://api.example.com/v1",
            resolved_ips=["8.8.8.8"],
            preflight=fake_ready_preflight(self.tool),
            callback=lambda secret, ctx: {
                "ok": secret.startswith("synthetic-"),
                "host": ctx["egress"]["host"],
            },
            now=NOW + timedelta(seconds=2),
        )
        self.assertEqual(out["state"], "COMPLETED")
        self.assertFalse(out["credential_exposed_to_model"])
        self.assertFalse(out["credential_in_result"])
        self.assertEqual(len(self.calls), 1)

        with self.assertRaises(PermissionError):
            self.proxy.invoke_egress(
                issued["handle"],
                self.tool,
                url="https://api.example.com/v1",
                resolved_ips=["8.8.8.8"],
                preflight=fake_ready_preflight(self.tool),
                callback=lambda secret, ctx: {"ok": True},
                now=NOW + timedelta(seconds=3),
            )

    def test_non_ready_or_mismatched_preflight_never_resolves_secret(self):
        for mutate in ("blocked", "wrong-tool", "wrong-contract"):
            proxy_calls = []
            proxy = CredentialProxy(
                self.vault,
                lambda backend, locator: proxy_calls.append((backend, locator)) or "secret-value",
                environment="STAGING",
            )
            issued = proxy.issue_handle(
                self.tool,
                requested_scopes=["probe:read"],
                now=NOW,
            )
            gate = fake_ready_preflight(self.tool)
            if mutate == "blocked":
                gate["state"] = "BLOCK"
            elif mutate == "wrong-tool":
                gate["tool"]["tool_id"] = "other.tool"
            else:
                gate["tool"]["contract_hash"] = "0" * 64
            with self.subTest(mutate=mutate):
                with self.assertRaises(PermissionError):
                    proxy.invoke_egress(
                        issued["handle"],
                        self.tool,
                        url="https://api.example.com/v1",
                        resolved_ips=["8.8.8.8"],
                        preflight=gate,
                        callback=lambda secret, ctx: {"ok": True},
                        now=NOW + timedelta(seconds=1),
                    )
                self.assertEqual(proxy_calls, [])

    def test_callback_cannot_return_secret_to_model_side(self):
        issued = self.proxy.issue_handle(
            self.tool,
            requested_scopes=["probe:read"],
            now=NOW,
        )
        with self.assertRaises(CredentialLeakError):
            self.proxy.invoke_egress(
                issued["handle"],
                self.tool,
                url="https://api.example.com/v1",
                resolved_ips=["8.8.8.8"],
                preflight=fake_ready_preflight(self.tool),
                callback=lambda secret, ctx: {"result": secret},
                now=NOW + timedelta(seconds=1),
            )
        self.assertEqual(len(self.calls), 1)

    def test_expired_handle_wrong_scope_and_unscoped_vault_fail_closed(self):
        issued = self.proxy.issue_handle(
            self.tool,
            requested_scopes=["probe:read"],
            ttl_seconds=1,
            now=NOW,
        )
        with self.assertRaises(PermissionError):
            self.proxy.invoke_egress(
                issued["handle"],
                self.tool,
                url="https://api.example.com/v1",
                resolved_ips=["8.8.8.8"],
                preflight=fake_ready_preflight(self.tool),
                callback=lambda secret, ctx: {"ok": True},
                now=NOW + timedelta(seconds=2),
            )
        self.assertEqual(self.calls, [])

        with self.assertRaises(PermissionError):
            self.proxy.issue_handle(
                self.tool,
                requested_scopes=["probe:write"],
                now=NOW,
            )

        unscoped = default_vault()
        unscoped["entries"] = [
            new_vault_entry(
                "staging-probe-secret",
                kind="SECRET_REF",
                backend="EXTERNAL_VAULT",
                locator_ref="secret/staging/aion/probe",
            )
        ]
        proxy = CredentialProxy(unscoped, lambda backend, locator: "secret")
        with self.assertRaises(PermissionError):
            proxy.issue_handle(
                self.tool,
                requested_scopes=["probe:read"],
                now=NOW,
            )

    def test_proxy_and_sandbox_modules_have_no_network_client(self):
        for name in (
            "atlasquant_aion_credential_proxy.py",
            "atlasquant_aion_tool_sandbox.py",
        ):
            source = Path(name).read_text(encoding="utf-8")
            with self.subTest(name=name):
                self.assertNotIn("import requests", source)
                self.assertNotIn("import socket", source)
                self.assertNotIn("import subprocess", source)
                self.assertNotIn("urlopen(", source)
                self.assertNotIn("Popen(", source)
                self.assertNotIn("os.system", source)


if __name__ == "__main__":
    unittest.main()
