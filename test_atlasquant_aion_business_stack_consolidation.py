import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_stack_consolidation import (
    CANONICAL_STACK,
    REQUIRED_CHECKS,
    administrative_options,
    canonical_stack_manifest,
    consolidation_preview,
    default_green_evidence,
    release_bundle_manifest,
    validate_stack,
)


class BusinessStackConsolidationTests(unittest.TestCase):
    def test_canonical_stack_is_398_through_411_in_order(self):
        manifest = canonical_stack_manifest()
        self.assertEqual([row["pr"] for row in manifest], list(range(398, 412)))
        self.assertEqual(len(manifest), 14)
        for index in range(1, len(manifest)):
            self.assertEqual(manifest[index]["base_branch"], manifest[index - 1]["head_branch"])

    def test_frozen_green_snapshot_is_ready_for_admin_review_only(self):
        validation = validate_stack(default_green_evidence())
        self.assertEqual(validation["state"], "READY_FOR_ADMIN_REVIEW")
        self.assertTrue(validation["complete"])
        self.assertEqual(validation["passed_count"], len(CANONICAL_STACK))
        self.assertEqual(validation["blocked_count"], 0)
        self.assertFalse(validation["merge_authorized"])
        self.assertFalse(validation["deploy_authorized"])
        self.assertFalse(validation["runtime_activation_authorized"])
        self.assertFalse(validation["executes_action"])

    def test_missing_required_check_blocks_stack(self):
        rows = default_green_evidence()
        rows[5]["checks"][REQUIRED_CHECKS[0]] = "failure"
        validation = validate_stack(rows)
        self.assertEqual(validation["state"], "BLOCKED")
        self.assertFalse(validation["complete"])
        self.assertGreaterEqual(validation["blocked_count"], 1)
        self.assertFalse(validation["rows"][5]["required_checks_ok"])

    def test_string_true_does_not_count_as_draft_or_mergeable(self):
        rows = default_green_evidence()
        rows[2]["draft"] = "true"
        rows[2]["mergeable"] = "true"
        validation = validate_stack(rows)
        self.assertEqual(validation["state"], "BLOCKED")
        self.assertFalse(validation["rows"][2]["draft_ok"])
        self.assertFalse(validation["rows"][2]["mergeable_ok"])

    def test_wrong_base_or_sha_blocks_chain(self):
        rows = default_green_evidence()
        rows[7]["base_branch"] = "main"
        rows[8]["head_sha"] = "0" * 40
        validation = validate_stack(rows)
        self.assertEqual(validation["state"], "BLOCKED")
        self.assertFalse(validation["rows"][7]["base_ok"])
        self.assertFalse(validation["rows"][8]["head_sha_ok"])

    def test_consolidation_preview_never_authorizes_merge(self):
        validation = validate_stack(default_green_evidence())
        preview = consolidation_preview(validation)
        self.assertEqual(preview["state"], "ADMIN_DECISION_REQUIRED")
        self.assertEqual(len(preview["sequence"]), 14)
        self.assertEqual(preview["strategy"], "STACKED_ORDER_OLDEST_TO_NEWEST")
        self.assertTrue(preview["post_merge_validation_required"])
        self.assertTrue(preview["final_main_ci_required"])
        self.assertTrue(preview["final_production_sha_verification_required"])
        self.assertFalse(preview["merge_authorized"])
        self.assertFalse(preview["auto_merge_enabled"])
        self.assertFalse(preview["deploy_authorized"])
        self.assertFalse(preview["runtime_activation_authorized"])

    def test_bundle_is_frozen_for_review_with_digest(self):
        bundle = release_bundle_manifest(validate_stack(default_green_evidence()))
        self.assertEqual(bundle["state"], "BUNDLE_FROZEN_FOR_REVIEW")
        self.assertEqual(len(bundle["bundle_digest"]), 64)
        self.assertEqual(len(bundle["payload"]["stack"]), 14)
        self.assertFalse(bundle["merge_authorized"])
        self.assertFalse(bundle["deploy_authorized"])
        self.assertFalse(bundle["executes_action"])

    def test_blocked_validation_cannot_create_sequence_or_bundle(self):
        blocked = validate_stack([])
        preview = consolidation_preview(blocked)
        bundle = release_bundle_manifest(blocked)
        self.assertEqual(preview["state"], "BLOCKED")
        self.assertEqual(preview["sequence"], [])
        self.assertEqual(bundle["state"], "BLOCKED")
        self.assertEqual(bundle["bundle_digest"], "")

    def test_admin_options_are_review_only(self):
        options = administrative_options(validate_stack(default_green_evidence()))
        self.assertEqual(
            [row["id"] for row in options],
            ["KEEP_DRAFT_STACK", "REQUEST_STACK_MERGE_REVIEW", "FREEZE_BUNDLE"],
        )
        self.assertTrue(all(row["available"] for row in options))
        self.assertTrue(all(not row["executes_action"] for row in options))

    def test_module_has_no_github_network_process_or_ui_imports(self):
        source = Path("atlasquant_aion_business_stack_consolidation.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for banned in (
            "requests", "urllib", "httpx", "socket", "subprocess", "openai",
            "streamlit", "github",
        ):
            self.assertNotIn(banned, imported)


if __name__ == "__main__":
    unittest.main()
