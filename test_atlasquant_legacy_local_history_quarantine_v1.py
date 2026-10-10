"""Isolated source + behavior checks for unscoped Parquet history quarantine.

The local history files are never opened, written, deleted or migrated here.
This suite extracts the actual definitions from the production entrypoint,
but never executes its entire UI or public-provider initialization.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parent
ENTRY = ROOT / "usd_macro_pro_v4_cloud.py"
SRC = ENTRY.read_text(encoding="utf-8")
TREE = ast.parse(SRC, filename=str(ENTRY))


class FakeDataFrame:
    def __init__(self, columns=None, *, empty=True):
        self.columns = list(columns or [])
        self.empty = empty


class PrivateParquetQuarantineTests(unittest.TestCase):
    def extract(self, name, extra=None):
        matches = [x for x in TREE.body if isinstance(x, ast.FunctionDef) and x.name == name]
        self.assertEqual(len(matches), 1, name)
        source = ast.fix_missing_locations(
            ast.Module(body=[ast.ImportFrom(module="__future__",
                                            names=[ast.alias(name="annotations")],
                                            level=0), matches[0]], type_ignores=[]))
        space = {"pd": SimpleNamespace(DataFrame=FakeDataFrame),
                 "private_read_allowed": Mock(return_value=False),
                 "_github_ler_csv_v84": Mock(side_effect=AssertionError("REMOTE_READ")),
                 "_normalizar_tipos_sinais_v1072": Mock(side_effect=AssertionError("NORMALIZER")),
                 **(extra or {})}
        exec(compile(source, str(ENTRY), "exec"), space)
        return space[name], space

    def test_entrypoint_private_gate_runs_before_optional_components_and_market_data(self):
        gate = SRC.find("_ATLASQUANT_ACCESS = render_access_gate()")
        next_import = SRC.find("from compact_ui_v1107 import apply_compact_theme")
        self.assertGreaterEqual(gate, 0)
        self.assertLess(gate, next_import)
        self.assertIn("st.stop()", SRC[gate:next_import])

    def test_no_parquet_read_write_remains_in_live_entrypoint_source(self):
        forbidden = [
            node for node in ast.walk(TREE)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("read_parquet", "to_parquet")
        ]
        self.assertEqual(forbidden, [])

    def test_untrusted_legacy_history_read_returns_empty_typed_table_without_io(self):
        reader, scope = self.extract("_carregar_sinais_v82")
        value = reader()
        self.assertIsInstance(value, FakeDataFrame)
        self.assertTrue(value.empty)
        self.assertIn("par", value.columns)
        self.assertIn("versao_coleta", value.columns)
        scope["_github_ler_csv_v84"].assert_not_called()

    def test_even_valid_admin_does_not_reenable_local_fallback(self):
        reader, scope = self.extract("_carregar_sinais_v82", {
            "private_read_allowed": Mock(return_value=True),
            "_github_ler_csv_v84": Mock(return_value=FakeDataFrame()),
        })
        value = reader()
        self.assertTrue(value.empty)
        scope["_github_ler_csv_v84"].assert_called_once_with()

    def test_private_history_writer_cannot_write_local_or_github_even_for_admin(self):
        writer, scope = self.extract("_salvar_sinais_v82", {
            "private_read_allowed": Mock(return_value=True),
        })
        self.assertIs(writer(FakeDataFrame()), False)
        scope["private_read_allowed"].assert_not_called()

    def test_legacy_snapshot_and_signal_calls_have_no_local_side_effect(self):
        cases = (
            ("salvar_snapshot", (FakeDataFrame(),), str),
            ("carregar_snapshots", (), FakeDataFrame),
            ("registrar_sinal", ("EUR/USD", .75, .8, .5, 1.0, 24), tuple),
            ("carregar_sinais", (), FakeDataFrame),
            ("atualizar_resultado", ("synthetic-id", 1.0), str),
        )
        for func, args, result_type in cases:
            with self.subTest(func=func):
                fn, _ = self.extract(func)
                result = fn(*args)
                self.assertIsInstance(result, result_type)
                if isinstance(result, FakeDataFrame):
                    self.assertTrue(result.empty)
                elif isinstance(result, tuple):
                    self.assertEqual(result, (False, "HARD_DENIED"))
                else:
                    self.assertIn("HARD_DENIED", result)

    def test_migration_button_never_reads_disk_or_claims_success(self):
        self.assertIn('key="v841_sync_github"', SRC)
        self.assertIn("HARD_DENIED: arquivos Parquet legados", SRC)
        self.assertNotIn("pd.read_parquet", SRC)
        self.assertNotIn("pd.DataFrame.to_parquet", SRC)

    def test_local_files_preserved_and_not_deleted_by_any_quarantine_code(self):
        self.assertIn('HIST_SCORES = "historico_scores_v5.parquet"', SRC)
        self.assertIn('HIST_SINAIS = "historico_sinais_v5.parquet"', SRC)
        self.assertIn('ARQ_SINAIS_V82 = "dados/sinais_v82.parquet"', SRC)
        local = ["salvar_snapshot", "carregar_snapshots", "registrar_sinal",
                 "carregar_sinais", "atualizar_resultado", "_carregar_sinais_v82",
                 "_salvar_sinais_v82"]
        for name in local:
            fn = next(x for x in TREE.body
                      if isinstance(x, ast.FunctionDef) and x.name == name)
            calls = [x for x in ast.walk(fn)
                     if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)
                     and x.func.attr in ("unlink", "remove", "rmdir", "rename", "replace")]
            self.assertEqual(calls, [], name)


if __name__ == "__main__":
    unittest.main()
