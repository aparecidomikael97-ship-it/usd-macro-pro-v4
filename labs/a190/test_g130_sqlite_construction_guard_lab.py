"""G130: no new direct SQLite store constructors without human review.

All checks static and offline. In particular none of them can authenticate a
HUMAN_OWNER, provider, native VFS SQLite handle or hostile local administrator.
"""
import unittest

from scripts import aion_sqlite_entrypoints_inventory_lab as inventory


class G130StoreConstructionGrowthTests(unittest.TestCase):
    def test_01_new_class_construction_detected(self):
        nodes = inventory.scan_source(
            "from atlasquant_aion_nonce_registry import PersistentNonceRegistry\n"
            "new_registry = PersistentNonceRegistry('/tmp/demo.db')\n"
        )
        constructors = [item for item in nodes if item["kind"] == "store_constructor"]
        self.assertEqual(len(constructors), 1)
        self.assertEqual(constructors[0]["symbol"], "PersistentNonceRegistry")
        print("G130_NEW_NONCE_STORE_CONSTRUCTOR=DETECTED")

    def test_02_injected_annotation_is_not_a_constructor(self):
        source = (
            "from atlasquant_aion_durable_execution_kernel import DurableExecutionStore\n"
            "def use_existing(store: DurableExecutionStore):\n"
            "    return store\n"
        )
        self.assertFalse(
            [item for item in inventory.scan_source(source)
             if item["kind"] == "store_constructor"]
        )

    def test_03_new_nonreviewed_site_is_refused(self):
        expanded = inventory.new_unreviewed_constructors(
            {"atlasquant_aion_global_worker.py::CoreStore": 1}
        )
        self.assertEqual(
            expanded, {"atlasquant_aion_global_worker.py::CoreStore": 1}
        )

    def test_04_extra_call_in_reviewed_module_is_refused(self):
        site = "aion_chat/staged_store.py::SQLiteChatStore"
        expanded = inventory.new_unreviewed_constructors({site: 3})
        self.assertEqual(expanded, {site: 3})

    def test_05_same_or_smaller_legacy_calls_are_not_new_growth(self):
        site = "aion_chat/staged_store.py::SQLiteChatStore"
        self.assertFalse(inventory.new_unreviewed_constructors({site: 2}))
        self.assertFalse(inventory.new_unreviewed_constructors({site: 1}))
        # This classification never declares the existing site secure.

    def test_06_real_repo_has_no_unreviewed_constructor_growth_at_this_sha(self):
        result = inventory.audit()
        self.assertEqual(result["status"], "INVENTORY_ONLY_NOT_P0")
        self.assertGreaterEqual(result["production_python_files_scanned"], 500)
        self.assertFalse(result["new_or_expanded_unreviewed_store_constructors"])
        self.assertFalse(result["new_or_expanded_unreviewed_direct_sqlite_calls"])
        self.assertTrue(result["legacy_store_constructor_calls"])
        print("G130_KNOWN_SQLITE_CONSTRUCTORS=REVIEW_DEBT_NOT_P0")
        print("G130_NEW_UNREVIEWED_CONSTRUCTORS=ZERO_THIS_SHA")


if __name__ == "__main__":
    unittest.main()
