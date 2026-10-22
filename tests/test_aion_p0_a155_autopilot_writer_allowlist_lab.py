"""A155 — Autopilot generic GitHub Contents writer path-allowlist attacks.

AST-extract just the production gh_put_bytes function. Do NOT import the
scheduled Autopilot module (which has heavy imports/job side effects).
Every HTTP dependency is an in-memory MagicMock: no GitHub requests,
provider, account, filesystem write, Worker or external transaction.
"""
from __future__ import annotations

import ast
import base64
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "autopilot_v107.py"
EXPECTED = frozenset({
    "dados/scanner_tecnico_v934.json",
    "dados/autopilot_daily_cache_v107.json",
    "dados/atlasquant_research_timeframes_v1.json",
    "dados/twelve_series_v1108.json",
    "dados/master_market_map_v102.json",
    "dados/currency_news_current_v107.json",
    "dados/aion_live_event_journal_v1.json",
    "dados/currency_news_validation_v1061.csv",
    "dados/atlasquant_signal_lifecycle_v1.json",
    "dados/atlasquant_home_snapshot_v1.json",
    "dados/atlasquant_quota_shadow_v1.json",
    "dados/autopilot_status_v107.json",
})

def isolated_writer():
    source = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(SOURCE))
    defs = [n for n in tree.body if isinstance(n, ast.FunctionDef)
            and n.name == "gh_put_bytes"]
    assert len(defs) == 1, "Autopilot byte writer is not unique"
    request = MagicMock()
    request.get.return_value.status_code = 404
    request.put.return_value.status_code = 201
    headers = MagicMock(return_value={"Authorization": "synthetic-only"})
    clock = SimpleNamespace(sleep=MagicMock())
    values = {
        "TOKEN": "synthetic-not-a-token",
        "REPO": "synthetic/repo",
        "BRANCH": "atlasquant-runtime",
        "AUTOPILOT_ALLOWED_GITHUB_WRITE_PATHS": EXPECTED,
        "requests": request, "gh_headers": headers, "time": clock,
        "base64": base64, "re": re,
    }
    exec(compile(ast.Module(body=defs, type_ignores=[]),
                 str(SOURCE), "exec"), values)
    return values["gh_put_bytes"], request, headers, clock


class A155AutopilotDestinationAllowlistLAB(unittest.TestCase):
    def deny(self, path):
        fn, requests, headers, clock = isolated_writer()
        ok, message = fn(path, b"synthetic", "A155 synthetic check")
        self.assertFalse(ok, (path, message))
        self.assertIn("not authorized", message)
        requests.get.assert_not_called()
        requests.put.assert_not_called()
        headers.assert_not_called()
        clock.sleep.assert_not_called()

    def allow(self, path):
        fn, requests, headers, clock = isolated_writer()
        ok, message = fn(path, b"{}", "A155 synthetic check")
        self.assertTrue(ok, (path, message))
        requests.get.assert_called_once()
        requests.put.assert_called_once()
        self.assertIn("/contents/" + path, requests.put.call_args.args[0])
        self.assertEqual(requests.put.call_args.kwargs["json"]["branch"], "atlasquant-runtime")
        clock.sleep.assert_not_called()

    # Legitimate 12 scheduled destinations. No implicit blanket "dados/" grant.
    def test_01_scanner_path_remains_writable(self):
        self.allow("dados/scanner_tecnico_v934.json")

    def test_02_daily_cache_path_remains_writable(self):
        self.allow("dados/autopilot_daily_cache_v107.json")

    def test_03_research_timeframes_path_remains_writable(self):
        self.allow("dados/atlasquant_research_timeframes_v1.json")

    def test_04_twelve_series_path_remains_writable(self):
        self.allow("dados/twelve_series_v1108.json")

    def test_05_master_market_map_path_remains_writable(self):
        self.allow("dados/master_market_map_v102.json")

    def test_06_currency_news_path_remains_writable(self):
        self.allow("dados/currency_news_current_v107.json")

    def test_07_aion_observational_event_journal_path_remains_writable(self):
        self.allow("dados/aion_live_event_journal_v1.json")

    def test_08_news_validation_csv_path_remains_writable(self):
        self.allow("dados/currency_news_validation_v1061.csv")

    def test_09_signal_lifecycle_path_remains_writable(self):
        self.allow("dados/atlasquant_signal_lifecycle_v1.json")

    def test_10_home_snapshot_path_remains_writable(self):
        self.allow("dados/atlasquant_home_snapshot_v1.json")

    def test_11_quota_shadow_path_remains_writable(self):
        self.allow("dados/atlasquant_quota_shadow_v1.json")

    def test_12_status_path_remains_writable(self):
        self.allow("dados/autopilot_status_v107.json")

    # Previously accepted by the old generic "starts with dados/" gate.
    def test_13_cannot_write_arbitrary_dados_file(self):
        self.deny("dados/attacker_created.json")

    def test_14_cannot_write_other_aion_checkpoint_namespace_file(self):
        self.deny("dados/aion/second_checkpoint.json")

    def test_15_cannot_write_other_aion_runtime_state(self):
        self.deny("dados/aion/runtime_state.json")

    def test_16_cannot_write_aion_outbox_state(self):
        self.deny("dados/aion_execution_outbox.json")

    def test_17_cannot_write_different_aion_event_journal_version(self):
        self.deny("dados/aion_live_event_journal_v2.json")

    def test_18_cannot_write_other_telemetry_file(self):
        self.deny("dados/telemetry_unreviewed.json")

    def test_19_cannot_write_feedback_csv_owned_by_other_writer(self):
        self.deny("dados/feedback_v104.csv")

    def test_20_cannot_write_flight_recorder_owned_by_other_writer(self):
        self.deny("dados/atlasquant_flight_recorder.jsonl")

    def test_21_cannot_write_input_file_only_read_by_autopilot(self):
        self.deny("dados/autopilot_inputs_v107.json")

    def test_22_cannot_write_known_good_path_with_extra_suffix(self):
        self.deny("dados/autopilot_status_v107.json.bak")

    def test_23_cannot_write_known_good_path_with_alt_extension(self):
        self.deny("dados/autopilot_status_v107.txt")

    def test_24_cannot_write_similar_sibling_path(self):
        self.deny("dados/autopilot_status_v108.json")

    def test_25_cannot_write_fake_directory_below_approved_filename(self):
        self.deny("dados/autopilot_status_v107.json/extra.json")

    def test_26_cannot_write_original_master_checkpoint(self):
        self.deny("dados/aion/checkpoint_master.json")

    def test_27_cannot_write_nested_checkpoint_with_renamed_parent(self):
        self.deny("dados/aion2/checkpoint_master.json")

    def test_28_cannot_write_pseudo_checkpoint_different_extension(self):
        self.deny("dados/aion/checkpoint_master.json.bak")

    def test_29_cannot_escape_with_dot_segments(self):
        self.deny("dados/cache/../aion/checkpoint_master.json")

    def test_30_cannot_escape_with_dot_current_dir(self):
        self.deny("dados/./autopilot_status_v107.json")

    def test_31_cannot_escape_with_empty_segment(self):
        self.deny("dados//autopilot_status_v107.json")

    def test_32_cannot_escape_with_backslash(self):
        self.deny("dados\\autopilot_status_v107.json")

    def test_33_cannot_escape_with_percent_encoded_slash(self):
        self.deny("dados%2Fautopilot_status_v107.json")

    def test_34_cannot_escape_with_double_encoded_slash(self):
        self.deny("dados%252Fautopilot_status_v107.json")

    def test_35_cannot_escape_with_query(self):
        self.deny("dados/autopilot_status_v107.json?ref=main")

    def test_36_cannot_escape_with_fragment(self):
        self.deny("dados/autopilot_status_v107.json#main")

    def test_37_cannot_escape_with_leading_slash(self):
        self.deny("/dados/autopilot_status_v107.json")

    def test_38_cannot_escape_with_trailing_slash(self):
        self.deny("dados/autopilot_status_v107.json/")

    def test_39_cannot_escape_by_case_change(self):
        self.deny("Dados/autopilot_status_v107.json")

    def test_40_cannot_escape_with_unicode_confusables(self):
        self.deny("dados/autopilot_status_v107.jsоn")

    def test_41_cannot_escape_with_newline(self):
        self.deny("dados/autopilot_status_v107.json\n")

    def test_42_nonstring_none_denied_before_network(self):
        self.deny(None)

    def test_43_nonstring_int_denied_before_network(self):
        self.deny(123)

    def test_44_nonstring_bytes_denied_before_network(self):
        self.deny(b"dados/autopilot_status_v107.json")

    def test_45_nonstring_bool_denied_before_network(self):
        self.deny(True)

    def test_46_nonstring_list_denied_before_network(self):
        self.deny(["dados/autopilot_status_v107.json"])

    def test_47_allowed_destinations_equal_scheduled_output_contract(self):
        self.assertEqual(len(EXPECTED), 12)
        # The imported constants must not silently drift to a novel path.
        for source_path, variable in (
            ("twelve_cache_v1108.py", "SERIES_PATH"),
            ("atlasquant_signal_lifecycle.py", "SIGNAL_LIFECYCLE_PATH"),
        ):
            tree = ast.parse((ROOT / source_path).read_text(encoding="utf-8"))
            values = [n.value for n in tree.body
                      if isinstance(n, ast.Assign) and any(
                          isinstance(t, ast.Name) and t.id == variable
                          for t in n.targets)]
            self.assertEqual(len(values), 1)
            resolved = ast.literal_eval(values[0])
            self.assertIn(resolved, EXPECTED)

    def test_48_broad_policy_counterexample_is_not_considered_enrollment(self):
        # The earlier startswith("dados/") rule accepted this syntactically
        # valid path, despite belonging to another operational namespace.
        attack = "dados/aion/external_source_snapshot.json"
        self.assertTrue(attack.startswith("dados/"))
        self.assertRegex(attack, r"^[A-Za-z0-9_./-]+$")
        self.deny(attack)


if __name__ == "__main__":
    unittest.main()
