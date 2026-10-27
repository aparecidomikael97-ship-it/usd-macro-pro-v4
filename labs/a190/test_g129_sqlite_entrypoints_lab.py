"""G129 scanner invariants and actual repository audit; never a P0 acceptance."""
from collections import Counter
import unittest

from scripts import aion_sqlite_entrypoints_inventory_lab as scanner


class G129SQLiteEntrypointInventoryTests(unittest.TestCase):
    def kinds(self, source):
        return Counter(x["kind"] for x in scanner.scan_source(source))

    def test_01_real_sqlite3_call_is_visible(self):
        actual = self.kinds("import sqlite3\nsqlite3.connect('test.db')\n")
        self.assertEqual(actual["native_connect"], 1)
        self.assertEqual(actual["native_connect_reference"], 1)

    def test_02_alias_module_connect_is_visible(self):
        actual = self.kinds("import sqlite3 as s\ns.connect('test.db')\n")
        self.assertEqual(actual["native_connect"], 1)

    def test_03_from_import_alias_connect_is_visible(self):
        actual = self.kinds(
            "from sqlite3 import connect as c\nconn = c('test.db')\n"
        )
        self.assertEqual(actual["native_connect"], 1)

    def test_04_comments_and_strings_are_not_calls(self):
        actual = self.kinds(
            "import sqlite3\n# sqlite3.connect('db')\n"
            "value = \"sqlite3.connect('db')\"\n"
        )
        self.assertEqual(actual["native_connect"], 0)

    def test_05_other_library_connect_is_not_classified_as_sqlite(self):
        actual = self.kinds("import psycopg\npsycopg.connect('postgres')\n")
        self.assertEqual(actual["native_connect"], 0)

    def test_06_native_factory_reference_is_not_a_native_open(self):
        actual = self.kinds(
            "import sqlite3\nfactory = sqlite3.connect\n"
            "if factory is sqlite3.connect: pass\n"
        )
        self.assertEqual(actual["native_connect"], 0)
        self.assertEqual(actual["native_connect_reference"], 2)

    def test_07_constructor_call_is_a_distinct_review_surface(self):
        actual = scanner.scan_source(
            "SQLiteChatStore('/tmp/safe.db')\n"
            "OperationScopedSQLiteChatStore('/tmp/safe.db')\n"
            "CoreStore('/tmp/core.db')\n"
        )
        symbols = {
            item["symbol"] for item in actual
            if item["kind"] == "store_constructor"
        }
        self.assertEqual(
            symbols,
            {"SQLiteChatStore", "OperationScopedSQLiteChatStore", "CoreStore"},
        )

    def test_08_test_and_lab_files_not_counted_as_production(self):
        self.assertFalse(scanner.is_production_path("labs/a190/test_g129.py"))
        self.assertFalse(scanner.is_production_path("tests/test_store.py"))
        self.assertFalse(scanner.is_production_path("aion_chat/uncertain_lab.py"))
        self.assertFalse(scanner.is_production_path("lab_a183_external.py"))
        self.assertFalse(scanner.is_production_path("scripts/aion_scan.py"))
        self.assertTrue(scanner.is_production_path("aion_chat/store.py"))
        self.assertTrue(
            scanner.is_production_path("atlasquant_aion_durable_execution_kernel.py")
        )

    def test_09_known_debt_is_not_automatically_p0(self):
        self.assertEqual(len(scanner.REVIEWED_NATIVE_OPEN_MAX), 5)
        result = scanner.audit()
        self.assertEqual(result["status"], "INVENTORY_ONLY_NOT_P0")
        self.assertGreaterEqual(result["production_python_files_scanned"], 500)
        self.assertFalse(result["new_or_expanded_unreviewed_direct_sqlite_calls"])
        self.assertTrue(result["legacy_direct_sqlite_calls"])
        self.assertTrue(
            all(
                path in scanner.REVIEWED_NATIVE_OPEN_MAX
                for path in result["legacy_direct_sqlite_calls"]
            )
        )
        print("G129_EXISTING_NATIVE_SQLITE_DEBT=TRACKED_NOT_P0")
        print("G129_NEW_UNREVIEWED_NATIVE_SQLITE_CALLS=ZERO_AT_THIS_SHA")


if __name__ == "__main__":
    unittest.main()
