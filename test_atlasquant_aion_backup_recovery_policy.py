import ast
import tempfile
import unittest
from pathlib import Path

from atlasquant_aion_backup_recovery_policy import (
    audit_repository_backup_readiness,
    backup_recovery_policy,
    backup_set_review,
    define_recovery_targets,
    prepare_restore_drill,
    restore_drill_verification_template,
)


class AionBackupRecoveryPolicyTests(unittest.TestCase):
    def test_policy_requires_separate_layers_and_no_auto_restore(self):
        row = backup_recovery_policy()
        self.assertIn(
            "SECONDARY_COPY_SEPARATE_FROM_PRIMARY_REFERENCE",
            row["required_backup_layers"],
        )
        self.assertTrue(row["runtime_checkpoint_kept_separate_from_source_archive"])
        self.assertFalse(row["automatic_restore"])
        self.assertEqual(row["rpo_rto_state"], "ADMIN_TARGETS_REQUIRED")

    def test_repository_backup_controls_are_verified(self):
        row = audit_repository_backup_readiness()
        self.assertEqual(row["state"], "REPOSITORY_BACKUP_CONTROLS_VERIFIED")
        self.assertTrue(row["workflow_markers_verified"])
        self.assertTrue(row["checkpoint_latest_valid"])
        self.assertTrue(row["runtime_recovery_module_present"])
        self.assertFalse(row["runtime_checkpoint_in_source_archive_required"])

    def test_recovery_targets_require_explicit_numbers(self):
        ok = define_recovery_targets(
            rpo_target_hours=24,
            rto_target_hours=4,
        )
        self.assertEqual(ok["state"], "RECOVERY_TARGETS_DEFINED")
        self.assertTrue(ok["targets_are_internal_planning_not_sla"])

        bad = define_recovery_targets(
            rpo_target_hours=None,
            rto_target_hours=4,
        )
        self.assertEqual(bad["state"], "RECOVERY_TARGETS_INVALID")

    def test_backup_set_requires_distinct_secondary_copy(self):
        targets = define_recovery_targets(
            rpo_target_hours=24,
            rto_target_hours=4,
        )
        row = backup_set_review(
            source_sha="a" * 40,
            source_backup_ref="github-artifact://source",
            checkpoint_digest="b" * 64,
            runtime_checkpoint_history_ref="github-runtime-history://checkpoint",
            secondary_copy_ref="local-export://offline-copy",
            recovery_targets=targets,
            operator="mikael",
        )
        self.assertEqual(row["state"], "BACKUP_SET_REVIEW_READY")
        self.assertFalse(row["backup_created"])
        self.assertFalse(row["restore_authorized"])

        duplicate = backup_set_review(
            source_sha="a" * 40,
            source_backup_ref="github-artifact://source",
            checkpoint_digest="b" * 64,
            runtime_checkpoint_history_ref="github-runtime-history://checkpoint",
            secondary_copy_ref="github-artifact://source",
            recovery_targets=targets,
            operator="mikael",
        )
        self.assertEqual(duplicate["state"], "BACKUP_SET_INCOMPLETE")
        self.assertIn("secondary_copy_is_distinct", duplicate["blockers"])

    def test_restore_drill_is_non_production_and_nonexecuting(self):
        targets = define_recovery_targets(
            rpo_target_hours=24,
            rto_target_hours=4,
        )
        backup = backup_set_review(
            source_sha="a" * 40,
            source_backup_ref="github-artifact://source",
            checkpoint_digest="b" * 64,
            runtime_checkpoint_history_ref="github-runtime-history://checkpoint",
            secondary_copy_ref="local-export://offline-copy",
            recovery_targets=targets,
            operator="mikael",
        )
        drill = prepare_restore_drill(
            backup,
            target_environment="sandbox",
            reason="quarterly recovery rehearsal",
        )
        self.assertEqual(drill["state"], "RESTORE_DRILL_READY")
        self.assertTrue(drill["simulation_only"])
        self.assertFalse(drill["production_restore_allowed"])
        self.assertFalse(drill["restore_authorized"])
        self.assertFalse(drill["files_written"])

    def test_production_restore_drill_is_blocked(self):
        targets = define_recovery_targets(
            rpo_target_hours=24,
            rto_target_hours=4,
        )
        backup = backup_set_review(
            source_sha="a" * 40,
            source_backup_ref="github-artifact://source",
            checkpoint_digest="b" * 64,
            runtime_checkpoint_history_ref="github-runtime-history://checkpoint",
            secondary_copy_ref="local-export://offline-copy",
            recovery_targets=targets,
            operator="mikael",
        )
        drill = prepare_restore_drill(
            backup,
            target_environment="production",
            reason="test",
        )
        self.assertEqual(drill["state"], "RESTORE_DRILL_BLOCKED")

    def test_restore_verification_requires_no_production_write(self):
        row = restore_drill_verification_template()
        self.assertIn("no_production_write", row["required_checks"])
        self.assertFalse(row["automatic_restore"])
        self.assertFalse(row["production_restore_authorized"])

    def test_admin_exposes_backup_recovery_view(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("29 · Backup & Recovery", source)
        self.assertIn("aion_backup_recovery_policy", source)

    def test_module_has_no_network_or_executor_imports(self):
        source = Path("atlasquant_aion_backup_recovery_policy.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for banned in (
            "requests",
            "urllib",
            "httpx",
            "socket",
            "subprocess",
            "github",
            "paramiko",
            "docker",
            "kubernetes",
        ):
            self.assertNotIn(banned, imported)


if __name__ == "__main__":
    unittest.main()
