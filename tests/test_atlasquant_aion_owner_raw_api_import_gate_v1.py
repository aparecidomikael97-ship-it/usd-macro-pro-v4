"""CI-only mutation fixtures for owner raw API import boundary; no code execution."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from atlasquant_aion_owner_raw_api_import_gate_v1 import (
    INTERNAL_MODULES,
    PERMITTED_IMPORTERS,
    inspect_python_source,
    scan_production_checkout,
)

BRIDGE = "atlasquant_aion_owner_host_entry_navigation_bridge_v1"
PROOF = "atlasquant_aion_trusted_owner_host_crypto_proof_v1"
COMPOSE = "atlasquant_aion_owner_proof_navigation_composition_v1"
INTENT = "atlasquant_aion_owner_signed_intent_guard_v1"
REGISTRY = "atlasquant_aion_owner_signed_key_registry_preflight_v1"
ROOTED = "atlasquant_aion_rooted_owner_signed_ui_preflight_v1"


class OwnerRawImportBoundaryTest(TestCase):
    def find(self, text, path="atlasquant_central_hub_ui.py"):
        return inspect_python_source(text, path)

    def test_policy_contains_all_six_owner_sensitive_modules(self):
        self.assertEqual(INTERNAL_MODULES, {BRIDGE, PROOF, COMPOSE, INTENT, REGISTRY, ROOTED})
        self.assertEqual(set(PERMITTED_IMPORTERS), set(INTERNAL_MODULES))

    def test_actual_existing_ui_imports_remain_allowed(self):
        source = (
            "from atlasquant_navigation_bridge import request_return_to_aion\n"
            "from atlasquant_aion_clock import greeting_period\n"
        )
        self.assertEqual(self.find(source), [])

    def test_direct_raw_bridge_import_from_ui_blocked(self):
        failures = self.find(f"from {BRIDGE} import route_owner_text_navigation")
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].module, BRIDGE)

    def test_direct_proof_verifier_import_from_ui_blocked(self):
        failures = self.find(f"from {PROOF} import verify_host_owner_proof")
        self.assertEqual(failures[0].module, PROOF)

    def test_direct_composition_import_from_ui_blocked(self):
        failures = self.find(f"from {COMPOSE} import request_verified_owner_navigation")
        self.assertEqual(failures[0].module, COMPOSE)

    def test_direct_intent_import_from_ui_blocked(self):
        failures = self.find(f"from {INTENT} import request_intent_bound_navigation")
        self.assertEqual(failures[0].module, INTENT)

    def test_direct_registry_import_from_ui_blocked(self):
        failures = self.find(f"from {REGISTRY} import verify_owner_registry_for_host_review")
        self.assertEqual(failures[0].module, REGISTRY)

    def test_direct_rooted_preflight_import_from_ui_blocked(self):
        failures = self.find(f"from {ROOTED} import request_rooted_owner_navigation")
        self.assertEqual(failures[0].module, ROOTED)

    def test_import_alias_does_not_hide_raw_module(self):
        violations = self.find(f"import {COMPOSE} as hidden\nhidden.request_verified_owner_navigation")
        self.assertEqual(violations[0].module, COMPOSE)

    def test_submodule_qualifier_cannot_hide_protected_root(self):
        violations = self.find(f"import {REGISTRY}.internal as alternative")
        self.assertEqual(violations[0].module, REGISTRY)

    def test_importlib_literal_cannot_bypass(self):
        violations = self.find(f'import importlib\nimportlib.import_module("{ROOTED}")')
        self.assertEqual(violations[0].module, ROOTED)
        self.assertEqual(violations[0].code, "PROTECTED_DYNAMIC_IMPORT")

    def test_builtins_import_literal_cannot_bypass(self):
        violations = self.find(f'__import__("{BRIDGE}")')
        self.assertEqual(violations[0].module, BRIDGE)

    def test_runpy_module_literal_cannot_bypass(self):
        violations = self.find(f'import runpy\nrunpy.run_module("{PROOF}")')
        self.assertEqual(violations[0].module, PROOF)

    def test_find_spec_literal_cannot_bypass(self):
        violations = self.find(f'import importlib.util\nimportlib.util.find_spec("{INTENT}")')
        self.assertEqual(violations[0].module, INTENT)

    def test_importlib_named_keyword_cannot_bypass(self):
        violations = self.find(f'importlib.import_module(name="{ROOTED}")')
        self.assertEqual(violations[0].module, ROOTED)

    def test_run_path_literal_file_loading_is_blocked(self):
        violation = self.find(
            f'import runpy\nrunpy.run_path("native/{ROOTED}.py")'
        )
        self.assertEqual(violation[0].module, ROOTED)

    def test_run_path_windows_file_loading_is_blocked(self):
        violation = self.find(
            f'import runpy\nrunpy.run_path(r"C:\\atlasquant\\{PROOF}.py")'
        )
        self.assertEqual(violation[0].module, PROOF)

    def test_file_location_literal_is_blocked(self):
        violation = self.find(
            f'import importlib.util\n'
            f'importlib.util.spec_from_file_location("helper", "{REGISTRY}.py")'
        )
        self.assertEqual(violation[0].module, REGISTRY)

    def test_literal_exec_code_with_protected_import_is_blocked(self):
        violation = self.find(
            f'exec("from {INTENT} import request_intent_bound_navigation")'
        )
        self.assertEqual(violation[0].module, INTENT)

    def test_unrelated_exec_literal_remains_unrestricted_by_this_policy(self):
        self.assertEqual(self.find('exec("x = 4")'), [])

    def test_unfiltered_pr_workflow_is_protected_against_regression(self):
        # Test reads only the workflow file present in the scratch CI checkout.
        path = Path(".github/workflows/aion-owner-raw-api-import-boundary-v1.yml")
        if not path.exists():
            self.skipTest("workflow file not part of isolated fixture run")
        workflow = path.read_text(encoding="utf-8")
        self.assertIn("on:\n  pull_request:", workflow)
        self.assertNotIn("\n    paths:", workflow)
        self.assertNotIn("\n    paths-ignore:", workflow)

    def test_package_relative_import_cannot_bypass(self):
        violations = self.find(f"from . import {REGISTRY}")
        self.assertEqual(violations[0].module, REGISTRY)

    def test_explicit_relative_path_cannot_bypass(self):
        violations = self.find(f"from .{INTENT} import request_intent_bound_navigation")
        self.assertEqual(violations[0].module, INTENT)

    def test_import_alias_is_reported_once(self):
        violations = self.find(f"from {REGISTRY} import a, b, c")
        self.assertEqual(len(violations), 1)

    def test_multiple_protected_imports_are_both_reported(self):
        violations = self.find(f"import {INTENT}\nimport {ROOTED}")
        self.assertEqual([x.line for x in violations], [1, 2])
        self.assertEqual([x.module for x in violations], [INTENT, ROOTED])

    def test_documented_internal_dependency_bridge_allowed(self):
        self.assertEqual(
            self.find(
                f"from {BRIDGE} import prepare_owner_host_entry",
                "atlasquant_aion_owner_proof_navigation_composition_v1.py",
            ), [],
        )

    def test_documented_internal_dependency_proof_allowed(self):
        self.assertEqual(
            self.find(
                f"from {PROOF} import signing_message",
                "atlasquant_aion_owner_signed_intent_guard_v1.py",
            ), [],
        )

    def test_documented_internal_dependency_registry_allowed(self):
        self.assertEqual(
            self.find(
                f"from {REGISTRY} import verify_owner_registry_for_host_review",
                "atlasquant_aion_rooted_owner_signed_ui_preflight_v1.py",
            ), [],
        )

    def test_allowlisted_file_cannot_import_extra_protected_module(self):
        violations = self.find(
            f"from {ROOTED} import request_rooted_owner_navigation",
            "atlasquant_aion_owner_signed_intent_guard_v1.py",
        )
        self.assertEqual(violations[0].module, ROOTED)

    def test_own_module_cannot_import_rooted_facade(self):
        violations = self.find(
            f"from {ROOTED} import request_rooted_owner_navigation",
            "atlasquant_aion_rooted_owner_signed_ui_preflight_v1.py",
        )
        self.assertEqual(violations[0].module, ROOTED)

    def test_new_host_adapter_requires_explicit_allowlist_review(self):
        violations = self.find(
            f"from {ROOTED} import request_rooted_owner_navigation",
            "atlasquant_owner_secure_real_host.py",
        )
        self.assertEqual(violations[0].module, ROOTED)

    def test_non_owner_navigation_is_not_indiscriminately_blocked(self):
        self.assertEqual(self.find(
            "from atlasquant_navigation_bridge import request_investments_page\n"
            "def route(state):\n"
            "    return request_investments_page(state)\n"
        ), [])

    def test_syntax_error_fails_closed(self):
        violations = self.find("from broken import (((\n")
        self.assertEqual(violations[0].code, "PYTHON_PARSE_FAILURE")

    def test_non_string_source_fails_closed(self):
        with self.assertRaises(ValueError):
            inspect_python_source(None, "atlasquant_central_hub_ui.py")

    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):
            self.find(f"import {ROOTED}", "../atlasquant_central_hub_ui.py")

    def test_checkout_scans_root_py_and_nested_production_modules(self):
        with TemporaryDirectory(prefix="aion-antibypass-ci-") as base:
            root = Path(base)
            (root / "atlasquant_central_hub_ui.py").write_text(
                f"from {ROOTED} import request_rooted_owner_navigation\n",
                encoding="utf-8",
            )
            (root / "native").mkdir()
            (root / "native" / "agent_ui.py").write_text(
                f"import {PROOF}\n", encoding="utf-8",
            )
            count, findings = scan_production_checkout(root)
            self.assertEqual(count, 2)
            self.assertEqual({x.module for x in findings}, {PROOF, ROOTED})

    def test_checkout_excludes_test_fixtures_not_runtime(self):
        with TemporaryDirectory(prefix="aion-antibypass-ci-") as base:
            root = Path(base)
            (root / "tests").mkdir()
            (root / "tests" / "test_fixtures.py").write_text(
                f"from {ROOTED} import request_rooted_owner_navigation\n",
                encoding="utf-8",
            )
            (root / "test_owner.py").write_text(f"import {ROOTED}\n", encoding="utf-8")
            (root / "app.py").write_text("import os\n", encoding="utf-8")
            count, findings = scan_production_checkout(root)
            self.assertEqual(count, 1)
            self.assertEqual(findings, [])

    def test_checkout_reports_unparseable_production_module(self):
        with TemporaryDirectory(prefix="aion-antibypass-ci-") as base:
            root = Path(base)
            (root / "app.py").write_text("def a(\n", encoding="utf-8")
            count, findings = scan_production_checkout(root)
            self.assertEqual(count, 1)
            self.assertEqual(findings[0].code, "PYTHON_PARSE_FAILURE")

    def test_checkout_does_not_execute_imported_code(self):
        with TemporaryDirectory(prefix="aion-antibypass-ci-") as base:
            root = Path(base)
            marker = root / "should_not_exist"
            (root / "app.py").write_text(
                f"from pathlib import Path\nPath({str(marker)!r}).write_text('BAD')\n"
                f"import {ROOTED}\n", encoding="utf-8"
            )
            _, findings = scan_production_checkout(root)
            self.assertTrue(findings)
            self.assertFalse(marker.exists())

    def test_policy_is_exact_per_file_not_prefix_or_suffix(self):
        violations = self.find(
            f"from {REGISTRY} import verify_owner_registry_for_host_review",
            "experimental/atlasquant_aion_rooted_owner_signed_ui_preflight_v1.py",
        )
        self.assertEqual(len(violations), 1)

    def test_whitelisted_code_still_requires_explicit_policy_per_module(self):
        for module in INTERNAL_MODULES:
            with self.subTest(module=module):
                self.assertIn(module, PERMITTED_IMPORTERS)
                self.assertNotIn(
                    "atlasquant_central_hub_ui.py",
                    PERMITTED_IMPORTERS[module],
                )
