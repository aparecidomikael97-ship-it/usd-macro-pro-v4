"""G131 offline AST alias-bypass regression: static detection, NOT P0 proof."""
import unittest

from scripts import aion_sqlite_entrypoints_inventory_lab as inventory


def _calls(source, kind):
    return [item for item in inventory.scan_source(source) if item["kind"] == kind]


class G131SQLiteAliasInventoryTests(unittest.TestCase):
    def test_01_direct_import_alias_constructor_is_detected(self):
        code = ("from atlasquant_aion_nonce_registry import PersistentNonceRegistry as Registry\\n"
                "db = Registry('fixture.sqlite3')\\n").replace("\\n", "\n")
        self.assertEqual([x["symbol"] for x in _calls(code, "store_constructor")],
                         ["PersistentNonceRegistry"])
        print("G131_DIRECT_IMPORT_ALIAS=DETECTED")

    def test_02_assignment_alias_constructor_is_detected(self):
        code = "Alias = PersistentNonceRegistry\nthing = Alias('fixture.sqlite3')\n"
        self.assertEqual([x["symbol"] for x in _calls(code, "store_constructor")],
                         ["PersistentNonceRegistry"])

    def test_03_module_attribute_alias_constructor_is_detected(self):
        code = ("import atlasquant_aion_nonce_registry as nonce\n"
                "Alias = nonce.PersistentNonceRegistry\n"
                "thing = Alias('fixture.sqlite3')\n")
        self.assertEqual([x["symbol"] for x in _calls(code, "store_constructor")],
                         ["PersistentNonceRegistry"])

    def test_04_aliased_native_connect_factory_is_detected(self):
        code = ("import sqlite3 as db\n"
                "open_native = db.connect\n"
                "conn = open_native('fixture.sqlite3')\n")
        self.assertEqual(len(_calls(code, "native_connect")), 1)
        print("G131_NATIVE_CONNECT_ALIAS=DETECTED")

    def test_05_chained_constructor_and_module_alias_are_detected(self):
        code = ("import sqlite3\n"
                "db = sqlite3\n"
                "open_db = db.connect\n"
                "other = open_db('fixture.sqlite3')\n"
                "A = PersistentNonceRegistry\n"
                "B = A\n"
                "registry = B('fixture.sqlite3')\n")
        self.assertEqual(len(_calls(code, "native_connect")), 1)
        self.assertEqual([x["symbol"] for x in _calls(code, "store_constructor")],
                         ["PersistentNonceRegistry"])

    def test_06_aliased_stdlib_from_import_is_detected(self):
        code = "from sqlite3 import connect as native_open\nconn = native_open('x')\n"
        self.assertEqual(len(_calls(code, "native_connect")), 1)

    def test_07_annotations_and_strings_do_not_count_as_calls(self):
        code = ("from atlasquant_aion_nonce_registry import PersistentNonceRegistry as N\n"
                "def consume(registry: N):\n"
                "    return {'class_name': 'N'}\n")
        self.assertEqual(_calls(code, "store_constructor"), [])
        self.assertEqual(_calls(code, "native_connect"), [])

    def test_08_existing_repo_has_no_unreviewed_growth(self):
        report = inventory.audit()
        self.assertEqual(report["status"], "INVENTORY_ONLY_NOT_P0")
        self.assertGreaterEqual(report["production_python_files_scanned"], 500)
        self.assertFalse(report["new_or_expanded_unreviewed_direct_sqlite_calls"])
        self.assertFalse(report["new_or_expanded_unreviewed_store_constructors"])
        print("G131_LEXICAL_ALIAS_GROWTH=ZERO_THIS_SHA_NOT_P0")


if __name__ == "__main__":
    unittest.main()
