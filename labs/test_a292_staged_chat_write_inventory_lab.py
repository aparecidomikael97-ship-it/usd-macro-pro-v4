"""A292 isolated LAB regression: all six staged-chat write entrypoints."""
import unittest

from labs.a292_staged_chat_write_inventory_lab import (
    DIRECT_DML, SCHEMA, SOURCE, WRITE_ENTRYPOINTS,
    inspect_store_writers, probe_one_writer_ack_boundary,
    probe_real_raw_helper_bypasses, probe_all_six_normal_writers,
)


class A292WriteInventoryStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")

    def test_staged_store_inventory_matches_six_known_writers(self):
        result = inspect_store_writers()
        self.assertTrue(result["valid_contract"], result["issues"])
        self.assertEqual(result["write_entrypoints"], sorted(WRITE_ENTRYPOINTS))
        self.assertEqual(
            result["direct_dml_by_method"],
            {key: list(value) for key, value in sorted(DIRECT_DML.items())},
        )
        self.assertEqual(
            result["unguarded_private_helpers"], ["_save_record", "_update"]
        )
        self.assertFalse(result["complete_path_proof"])
        self.assertTrue(result["static_only"])

    def test_inventory_reserves_maintenance_paths(self):
        paths = inspect_store_writers()["separate_maintenance_scope"]
        for method in (
            "__init__", "backup_to", "restore_from_backup",
            "_wal_checkpoint_under_lifecycle_lock",
        ):
            self.assertIn(method, paths)

    def test_new_rogue_sql_writer_is_detected(self):
        mutated = (
            self.source
            + "\n    def a292_rogue(self):\n"
            + "        self.db.execute('DELETE FROM messages')\n"
        )
        result = inspect_store_writers(source=mutated)
        self.assertFalse(result["valid_contract"])
        self.assertIn("DIRECT_DML_METHOD_SET_OR_SQL_CHANGED", result["issues"])

    def test_removed_local_lock_on_archiver_is_detected(self):
        original = "    @_local_commit_gate\n    def archive_conversation("
        replacement = "    def archive_conversation("
        self.assertIn(original, self.source)
        result = inspect_store_writers(
            source=self.source.replace(original, replacement, 1)
        )
        self.assertFalse(result["valid_contract"])
        self.assertIn(
            "WRITER_MISSING_LOCAL_LOCK:archive_conversation",
            result["issues"],
        )

    def test_removed_direct_commit_fence_is_detected(self):
        original = "            self._commit_fenced_chat_write()"
        self.assertIn(original, self.source)
        result = inspect_store_writers(
            source=self.source.replace(
                original, "            self.db.commit()", 1
            )
        )
        self.assertFalse(result["valid_contract"])
        self.assertIn("UNEXPECTED_DIRECT_COMMIT_SINK", result["issues"])
        self.assertIn(
            "WRITER_MISSING_COMMIT_FENCE:create_conversation",
            result["issues"],
        )

    def test_dynamic_sql_mutation_is_detected(self):
        original = (
            'sql, args = "SELECT * FROM messages WHERE cid=?", [conversation_id]'
        )
        self.assertIn(original, self.source)
        mutated = self.source.replace(
            original,
            'sql, args = "DELETE FROM messages WHERE cid=?", [conversation_id]',
            1,
        )
        result = inspect_store_writers(source=mutated)
        self.assertFalse(result["valid_contract"])
        self.assertIn("DIRECT_DML_METHOD_SET_OR_SQL_CHANGED", result["issues"])

    def test_new_unknown_sql_is_denied(self):
        mutated = (
            self.source
            + "\n    def a292_unknown_sql(self, q):\n"
            + "        self.db.execute(q)\n"
        )
        result = inspect_store_writers(source=mutated)
        self.assertFalse(result["valid_contract"])
        self.assertIn("UNRESOLVED_SQL:a292_unknown_sql", result["issues"])

    def test_bad_source_type_and_size_are_rejected(self):
        for invalid in (None, 1, b"not source", "x" * 200001):
            if invalid is None:
                continue
            with self.subTest(invalid=type(invalid).__name__):
                with self.assertRaises(ValueError):
                    inspect_store_writers(source=invalid)

    def test_syntax_fault_is_marked_invalid(self):
        result = inspect_store_writers(source="class SQLiteChatStore(\n")
        self.assertFalse(result["valid_contract"])
        self.assertEqual(result["issues"], ["SOURCE_SYNTAX_INVALID"])

    def test_missing_store_class_is_marked_invalid(self):
        result = inspect_store_writers(source="class AnotherStore: pass\n")
        self.assertFalse(result["valid_contract"])
        self.assertEqual(
            result["issues"], ["SQLITE_CHAT_STORE_CLASS_NOT_UNIQUE"]
        )

    def test_duplicate_store_class_is_marked_invalid(self):
        result = inspect_store_writers(source=self.source + (
            "\nclass SQLiteChatStore:\n    pass\n"
        ))
        self.assertFalse(result["valid_contract"])
        self.assertEqual(
            result["issues"], ["SQLITE_CHAT_STORE_CLASS_NOT_UNIQUE"]
        )


class A292RealStagedChatWriteTests(unittest.TestCase):
    def test_six_real_writers_publish_six_markers_on_ack(self):
        result = probe_all_six_normal_writers()
        self.assertTrue(result["six_distinct_writers_executed"])
        self.assertEqual(result["local_commit_markers_published"], 6)
        self.assertEqual(result["message_count"], 1)
        self.assertEqual(
            result["record_kinds"],
            {"attachment": 1, "checkpoint": 1, "summary": 1},
        )
        self.assertTrue(result["archived"])
        self.assertTrue(result["pending_marker_absent_after_acks"])
        self.assertTrue(result["health_healthy_after_ack"])

    def test_all_six_writers_lost_ack_before_and_after_commit(self):
        for writer in sorted(WRITE_ENTRYPOINTS):
            for phase in ("before", "after"):
                with self.subTest(writer=writer, phase=phase):
                    result = probe_one_writer_ack_boundary(
                        writer=writer, phase=phase
                    )
                    expected = int(phase == "after")
                    self.assertEqual(result["baseline_effect_count"], 0)
                    self.assertEqual(result["first_effect_count"], expected)
                    self.assertTrue(result["uncertain_error_raised"])
                    self.assertTrue(result["health_failed_sticky"])
                    self.assertTrue(result["pending_marker_persisted"])
                    self.assertTrue(result["automatic_retry_denied"])
                    self.assertEqual(
                        result["effect_count_after_denied_retry"], expected
                    )
                    self.assertTrue(result["restart_refused_pending_marker"])
                    self.assertEqual(result["p0_homologated"], 0)
                    self.assertFalse(result["can_authorize_send"])

    def test_raw_python_helpers_bypass_ordinary_store_fence(self):
        result = probe_real_raw_helper_bypasses()
        self.assertTrue(result["raw_update_helper_changed_title"])
        self.assertTrue(
            result["raw_save_record_helper_inserted_checkpoint"]
        )
        self.assertTrue(result["pending_commit_marker_absent"])
        self.assertTrue(result["strict_local_health_still_green"])
        self.assertTrue(result["unrestricted_same_process_helper_access"])
        self.assertFalse(result["complete_path_proof"])

    def test_all_simulations_refuse_real_world_effects(self):
        result = probe_one_writer_ack_boundary(
            writer="create_conversation", phase="before"
        )
        self.assertEqual(result["schema"], SCHEMA)
        self.assertTrue(result["research_only"])
        self.assertTrue(result["real_native_sqlite"])
        self.assertTrue(result["zero_auto_resend"])
        self.assertTrue(result["no_provider_worker_deploy_orders"])
        self.assertFalse(result["independent_owner_proof"])
        self.assertFalse(result["native_fd_authenticated"])
        self.assertFalse(result["off_host_rollback_witness"])

    def test_reject_unknown_writer_and_invalid_phase(self):
        for writer in ("raw", None, "", 1):
            with self.subTest(writer=writer):
                with self.assertRaises(ValueError):
                    probe_one_writer_ack_boundary(writer=writer)
        for phase in ("commit", None, "", 1):
            with self.subTest(phase=phase):
                with self.assertRaises(ValueError):
                    probe_one_writer_ack_boundary(phase=phase)


if __name__ == "__main__":
    unittest.main()
