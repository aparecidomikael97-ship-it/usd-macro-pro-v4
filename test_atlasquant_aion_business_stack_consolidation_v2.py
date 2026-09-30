import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_stack_consolidation_v2 import (
    CANONICAL_STACK,
    REQUIRED_CHECKS,
    administrative_options,
    canonical_stack_manifest,
    consolidation_preview,
    frozen_green_evidence,
    release_bundle_manifest,
    rollback_integration_plan,
    validate_stack,
)


class BusinessStackConsolidationV2Tests(unittest.TestCase):
    def test_canonical_stack_is_394_through_412_and_fully_linear(self):
        manifest = canonical_stack_manifest()
        self.assertEqual([row["pr"] for row in manifest], list(range(394, 413)))
        self.assertEqual(len(manifest), 19)
        self.assertEqual(manifest[0]["base_branch"], "main")
        for index in range(1, len(manifest)):
            self.assertEqual(manifest[index]["base_branch"], manifest[index - 1]["head_branch"])

    def test_frozen_green_snapshot_is_ready_for_admin_review_only(self):
        validation = validate_stack(frozen_green_evidence())
        self.assertEqual(validation["state"], "READY_FOR_ADMIN_REVIEW")
        self.assertTrue(validation["complete"])
        self.assertEqual(validation["passed_count"], 19)
        self.assertEqual(validation["blocked_count"], 0)
        self.assertFalse(validation["merge_authorized"])
        self.assertFalse(validation["deploy_authorized"])
        self.assertFalse(validation["runtime_activation_authorized"])
        self.assertFalse(validation["executes_action"])

    def test_failed_check_or_wrong_sha_blocks_consolidation(self):
        rows = frozen_green_evidence()
        rows[3]["checks"][REQUIRED_CHECKS[0]] = "failure"
        rows[10]["head_sha"] = "0" * 40
        validation = validate_stack(rows)
        self.assertEqual(validation["state"], "BLOCKED")
        self.assertFalse(validation["complete"])
        self.assertGreaterEqual(validation["blocked_count"], 2)

    def test_non_boolean_draft_or_mergeable_does_not_pass(self):
        rows = frozen_green_evidence()
        rows[5]["draft"] = "true"
        rows[6]["mergeable"] = "true"
        validation = validate_stack(rows)
        self.assertEqual(validation["state"], "BLOCKED")
        self.assertFalse(validation["rows"][5]["draft_ok"])
        self.assertFalse(validation["rows"][6]["mergeable_ok"])

    def test_preview_is_ordered_but_never_authorizes_merge(self):
        preview = consolidation_preview(validate_stack(frozen_green_evidence()))
        self.assertEqual(preview["state"], "ADMIN_DECISION_REQUIRED")
        self.assertEqual([row["pr"] for row in preview["sequence"]], list(range(394, 413)))
        self.assertEqual(preview["strategy"], "STACKED_ORDER_OLDEST_TO_NEWEST")
        self.assertTrue(preview["final_main_ci_required"])
        self.assertTrue(preview["runtime_posture_recheck_required"])
        self.assertFalse(preview["merge_authorized"])
        self.assertFalse(preview["auto_merge_enabled"])
        self.assertFalse(preview["deploy_authorized"])

    def test_bundle_and_rollback_plan_are_review_only(self):
        validation = validate_stack(frozen_green_evidence())
        bundle = release_bundle_manifest(validation)
        rollback = rollback_integration_plan(validation)
        self.assertEqual(bundle["state"], "BUNDLE_FROZEN_FOR_REVIEW")
        self.assertEqual(len(bundle["bundle_digest"]), 64)
        self.assertEqual(len(bundle["payload"]["stack"]), 19)
        self.assertFalse(bundle["merge_authorized"])
        self.assertFalse(bundle["deploy_authorized"])
        self.assertEqual(rollback["state"], "ROLLBACK_PLAN_READY")
        self.assertGreaterEqual(len(rollback["steps"]), 6)
        self.assertFalse(rollback["automatic_rollback"])
        self.assertFalse(rollback["production_write"])
        self.assertFalse(rollback["executes_action"])

    def test_admin_options_do_not_execute_any_action(self):
        options = administrative_options(validate_stack(frozen_green_evidence()))
        self.assertEqual(
            [row["id"] for row in options],
            ["KEEP_DRAFT_STACK","FREEZE_BUNDLE","REQUEST_MERGE_AUTHORIZATION"],
        )
        self.assertTrue(all(row["available"] for row in options))
        self.assertTrue(all(not row["executes_action"] for row in options))

    def test_module_has_no_github_network_process_or_ui_imports(self):
        source = Path("atlasquant_aion_business_stack_consolidation_v2.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for banned in ("requests","urllib","httpx","socket","subprocess","openai","streamlit","github"):
            self.assertNotIn(banned, imported)


if __name__ == "__main__":
    unittest.main()
