"""Synthetic-only contracts for pre-release PPI MT5 + evidence readiness.

Fake MT5 never touches a real terminal and must NEVER call copy_rates,
symbol_select, account_info, orders, or any position-related method.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from atlasquant_trader_ppi_preflight_lab import (
    SOURCES, inspect_ppi_seven_fx_readiness_lab as inspect,
)
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import (
    EVENT_UTC, LAST_REQUIRED_CLOSE_UTC, USD_FX,
)
from test_atlasquant_trader_ppi_mt5_m15_capture_lab import FakeMT5, TERMINAL

ASOF = EVENT_UTC - timedelta(days=1)


class PreflightTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.td = self.root / "td.html"
        self.te = self.root / "te.html"
        self.td.write_bytes(b"synthetic td research text only")
        self.te.write_bytes(b"synthetic trading economics text")
        self.sources = {
            "TD_ECONOMICS": sha256(self.td.read_bytes()).hexdigest(),
            "TRADING_ECONOMICS": sha256(self.te.read_bytes()).hexdigest(),
        }
        self.api = FakeMT5()
        self.api.visible = set(USD_FX)

    def check(self, *, now=ASOF, api=None, td=None, te=None,
              calendar_state="LAB_PPI_THREE_OFFICIAL_SCHEDULES_LOCAL_SHA_MATCH_NO_GO"):
        with patch.dict(SOURCES, self.sources, clear=True):
            with patch(
                "atlasquant_trader_ppi_preflight_lab."
                "inspect_ppi_three_official_schedule_files_lab",
                return_value={"state": calendar_state},
            ):
                out = inspect(
                    api=self.api if api is None else api,
                    terminal_path=TERMINAL,
                    td_html_path=self.td if td is None else td,
                    te_html_path=self.te if te is None else te,
                    official_calendar_archive_root=self.root,
                    as_of_utc=now,
                )
        self.assertEqual(out["operational_bias"], "AGUARDAR")
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["publishable"])
        self.assertFalse(out["data_capture_performed"])
        self.assertFalse(out["symbol_visibility_changed"])
        self.assertFalse(out["broker_or_active_quote_server_independently_authenticated"])
        self.assertFalse(out["forecast_accuracy_measured"])
        self.assertFalse(out["pre_event_directional_forecast_registered"])
        self.assertFalse(out["account_information_read"])
        self.assertFalse(out["positions_or_orders_read"])
        self.assertEqual(out["orders_sent"], 0)
        self.assertEqual(out["m15_candles_read"], 0)
        self.assertEqual(out["tick_quotes_read"], 0)
        self.assertEqual((out["http_requests"], out["file_writes"], out["new_cost_brl"]),
                         (0, 0, 0))
        return out

    def test_all_seven_visible_pre_event_still_never_requests_bars(self):
        out = self.check()
        self.assertEqual(out["state"], "LAB_PPI_PREFLIGHT_7FX_VISIBLE_READONLY_WAIT")
        self.assertEqual(out["mt5_symbols_checked"], 7)
        self.assertEqual(out["seven_canonical_symbols_spec_consistent"], 7)
        self.assertEqual(out["td_te_source_hashes_matched_locally"], 2)
        self.assertEqual(out["official_partial_schedule_html_hashes_matched_locally"], 3)
        self.assertEqual(out["hidden_symbols"], [])
        self.assertTrue(out["frozen_pre_event_protocol_checked"])
        self.assertEqual(out["local_clock_phase_claim"], "PRE_RELEASE")
        self.assertEqual(
            {x[0] for x in self.api.calls},
            {"initialize", "terminal_info", "symbol_info", "shutdown"},
        )

    def test_three_hidden_symbols_reported_without_auto_select(self):
        self.api.visible -= {"NZDUSD", "USDCHF", "USDCAD"}
        out = self.check()
        self.assertEqual(
            out["hidden_symbols"], ["NZDUSD", "USDCHF", "USDCAD"])
        self.assertEqual(out["seven_canonical_symbols_spec_consistent"], 7)
        self.assertEqual(len(out["visible_symbols"]), 4)
        self.assertEqual(
            out["reason"], "SEVEN_FX_VISIBILITY_INCOMPLETE_MANUAL_SHOW_ALL_REQUIRED")
        self.assertNotIn("symbol_select", [x[0] for x in self.api.calls])
        self.assertEqual(out["state"], "LAB_PPI_PREFLIGHT_VISIBILITY_OR_SPEC_INCOMPLETE_NO_GO")

    def test_wrong_symbol_base_or_quote_blocks(self):
        self.api.specs["GBPUSD"]["currency_profit"] = "EUR"
        out = self.check()
        self.assertEqual(out["missing_or_invalid_symbols"], ["GBPUSD"])
        self.assertEqual(out["reason"], "SEVEN_FX_IDENTITY_OR_PRECISION_INCOMPLETE")

    def test_missing_td_hash_refuses_before_mt5_connection(self):
        self.td.write_bytes(b"fake refreshed forecast")
        out = self.check()
        self.assertEqual(out["td_te_source_hashes_matched_locally"], 1)
        self.assertEqual(out["reason"],
                         "PRE_EVENT_TD_TE_ORIGINAL_SOURCE_BYTES_MISSING_OR_CHANGED")
        self.assertEqual(self.api.calls, [])

    def test_wrong_te_bytes_fail_even_if_calendar_looks_good(self):
        self.te.write_bytes(b"bad")
        out = self.check()
        self.assertEqual(out["state"], "LAB_PPI_PREFLIGHT_BLOCKED")
        self.assertEqual(out["mt5_symbols_checked"], 0)
        self.assertEqual(self.api.calls, [])

    def test_actual_te_like_html_size_1_4mb_remains_accepted(self):
        # A real saved TE HTML has ~1.4 MB. A smaller arbitrary cap had
        # incorrectly blocked its valid frozen SHA before reaching MT5.
        self.te.write_bytes(b"x" * 1_401_914)
        self.sources["TRADING_ECONOMICS"] = sha256(self.te.read_bytes()).hexdigest()
        out = self.check()
        self.assertEqual(out["td_te_source_hashes_matched_locally"], 2)
        self.assertEqual(out["mt5_symbols_checked"], 7)
        self.assertEqual(out["state"], "LAB_PPI_PREFLIGHT_7FX_VISIBLE_READONLY_WAIT")

    def test_extremely_oversized_html_blocks_before_mt5(self):
        self.te.write_bytes(b"x" * 2_000_001)
        self.sources["TRADING_ECONOMICS"] = sha256(self.te.read_bytes()).hexdigest()
        out = self.check()
        self.assertEqual(out["reason"],
                         "PRE_EVENT_TD_TE_ORIGINAL_SOURCE_BYTES_MISSING_OR_CHANGED")
        self.assertEqual(self.api.calls, [])

    def test_missing_official_archives_cannot_be_hidden(self):
        out = self.check(calendar_state="LAB_OFFICIAL_CALENDAR_ARCHIVE_BLOCKED")
        self.assertEqual(out["reason"],
                         "OFFICIAL_COMPETING_CALENDAR_ARCHIVES_MISSING_OR_CHANGED")
        self.assertEqual(self.api.calls, [])

    def test_mt5_not_connected_does_not_read_symbols(self):
        self.api.connected = False
        out = self.check()
        self.assertEqual(out["reason"], "MT5_NOT_CONNECTED_NO_MARKET_DATA_READ")
        self.assertEqual(self.api.calls, [("initialize", TERMINAL, 10000)])

    def test_terminal_connected_false_after_initialize_fails(self):
        self.api.terminal_info = lambda: None
        out = self.check()
        self.assertEqual(out["reason"], "MT5_TERMINAL_NOT_CONNECTED")
        self.assertEqual(out["mt5_symbols_checked"], 0)
        self.assertEqual(self.api.calls[-1], ("shutdown",))

    def test_asof_requires_timezone(self):
        for wrong in (None, "2026-11-11", ASOF.replace(tzinfo=None)):
            with self.subTest(wrong=wrong):
                out = self.check(now=wrong)
                self.assertEqual(out["reason"], "INVALID_INPUT_OR_CLOCK")
        self.assertEqual(self.api.calls, [])

    def test_h4_not_closed_is_only_wait_not_read_prices(self):
        out = self.check(now=EVENT_UTC+timedelta(minutes=1))
        self.assertEqual(out["local_clock_phase_claim"], "POST_RELEASE_WAIT_M15_H4_CLOSE")
        self.assertFalse(out["data_capture_performed"])

    def test_after_h4_phase_still_no_actual_data_or_trade(self):
        out = self.check(now=LAST_REQUIRED_CLOSE_UTC+timedelta(seconds=1))
        self.assertEqual(
            out["local_clock_phase_claim"],
            "POST_H4_WINDOW_CLOSED_ELIGIBLE_FOR_MANUAL_CAPTURE_CHECKS",
        )
        self.assertEqual(out["m15_candles_read"], 0)

    def test_no_source_file_symlink_accepted(self):
        original = self.root / "td-original.html"
        self.td.rename(original)
        self.td.symlink_to(original)
        out = self.check()
        self.assertEqual(out["reason"],
                         "PRE_EVENT_TD_TE_ORIGINAL_SOURCE_BYTES_MISSING_OR_CHANGED")

    def test_subsecond_inspection_clock_is_allowed(self):
        out = self.check(now=ASOF.replace(microsecond=123456))
        self.assertEqual(out["state"], "LAB_PPI_PREFLIGHT_7FX_VISIBLE_READONLY_WAIT")


if __name__ == "__main__":
    unittest.main()
