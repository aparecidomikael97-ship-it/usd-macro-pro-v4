"""A275: Radar non-FX watchlist has separated TF evidence and zero orders."""
from datetime import datetime, timedelta, timezone
import inspect
import unittest
from unittest import mock

from atlasquant_radar_board import INDEX_UNIVERSE
from atlasquant_aion_trader_nonfx import (
    SCHEMA, SYMBOLS, FUTURE_ROOTS, nonfx_readonly_overlay,
)
from atlasquant_aion_trader_timeframes import NO_SEPARATE, INVALID
from atlasquant_aion_trader_observation import trader_readonly_observation
from labs.test_a269_trader_closed_mtf_evidence import NOW, evidence
from labs.test_a268_trader_readonly_observation import _resident, _row
import atlasquant_trader_resident


def _symbol(board, symbol):
    return next(row for row in board["rows"] if row["symbol"] == symbol)


class A275NonFxReadOnlyTests(unittest.TestCase):
    def test_01_watchlist_reuses_exact_radar_universe(self):
        self.assertEqual(SYMBOLS, tuple(code for code, _ in INDEX_UNIVERSE))
        self.assertEqual(SYMBOLS, (
            "DXY", "US30", "NAS100", "SPX500", "IBOV", "WIN", "WDO",
        ))
        self.assertEqual(FUTURE_ROOTS, {"WIN", "WDO"})

    def test_02_missing_evidence_never_invents_a_quote(self):
        board = nonfx_readonly_overlay(now=NOW)
        self.assertEqual(board["schema"], SCHEMA)
        self.assertEqual(board["expected_symbols"], 7)
        self.assertEqual(len(board["rows"]), 7)
        self.assertTrue(board["input_root_valid"])
        self.assertEqual(board["mtf_coverage"], {
            tf: 0 for tf in ("M5", "M15", "M30", "H1", "H4", "D1")
        })
        self.assertTrue(all(
            all(status == NO_SEPARATE for status in row["timeframes"].values())
            for row in board["rows"]
        ))

    def test_03_h1_never_implies_other_timeframes(self):
        board = nonfx_readonly_overlay(
            {"NAS100": {"H1": evidence("H1")}}, now=NOW,
        )
        row = _symbol(board, "NAS100")
        self.assertEqual(row["timeframes"]["H1"],
                         "INPUT_FRESH_CLOSED_H1_UNATTESTED")
        self.assertTrue(all(
            row["timeframes"][tf] == NO_SEPARATE
            for tf in ("M5", "M15", "M30", "H4", "D1")
        ))
        self.assertEqual(board["mtf_coverage"]["H1"], 1)

    def test_04_seven_claims_do_not_become_seven_verified_feeds(self):
        board = nonfx_readonly_overlay({
            symbol: {"M5": evidence("M5")} for symbol in SYMBOLS
        }, now=NOW)
        self.assertEqual(board["mtf_coverage"]["M5"], 7)
        self.assertFalse(board["mtf_coverage_is_external_attestation"])
        self.assertFalse(board["provider_symbols_authenticated"])
        self.assertTrue(all(not r["authorizes_order"] for r in board["rows"]))

    def test_05_unknown_fx_or_provider_alias_does_not_enter_non_fx(self):
        for alien in ("EURUSD", "US100", "WINZ26", "FX:DXY", "CRYPTO:BTC"):
            with self.subTest(symbol=alien):
                board = nonfx_readonly_overlay(
                    {alien: {"M5": evidence("M5")}}, now=NOW,
                )
                self.assertFalse(board["input_root_valid"])
                self.assertEqual(len(board["rows"]), 7)
                self.assertTrue(all(
                    r["timeframes"]["M5"] == INVALID for r in board["rows"]
                ))

    def test_06_malformed_or_stale_tf_never_current(self):
        wrong = evidence("M15")
        wrong["source"] = "VERIFIED"
        stale = evidence("H4")
        stale["bars"][0]["closed_at"] = (NOW - timedelta(days=3)).isoformat()
        stale["bars"][-1]["closed_at"] = (NOW - timedelta(days=2)).isoformat()
        board = nonfx_readonly_overlay({
            "US30": {"M15": wrong}, "IBOV": {"H4": stale},
        }, now=NOW)
        self.assertEqual(_symbol(board, "US30")["timeframes"]["M15"], INVALID)
        self.assertEqual(_symbol(board, "IBOV")["timeframes"]["H4"],
                         "HISTORICAL_ONLY")

    def test_07_win_wdo_are_not_tradeable_expiry_mapped_contracts(self):
        board = nonfx_readonly_overlay({
            "WIN": {"M15": evidence("M15")},
            "WDO": {"M15": evidence("M15")},
        }, now=NOW)
        for symbol in ("WIN", "WDO"):
            row = _symbol(board, symbol)
            self.assertEqual(row["asset_class"], "FUTURE_ROOT")
            self.assertFalse(row["specific_contract_expiry_selected"])
            self.assertFalse(row["provider_mapping_verified"])
            self.assertFalse(row["authorizes_order"])
        self.assertFalse(board["futures_expiry_resolved"])

    def test_08_without_new_argument_previous_fx_board_is_exactly_equal(self):
        old = trader_readonly_observation(_resident(_row()), now=NOW)
        same = trader_readonly_observation(
            _resident(_row()), now=NOW, non_fx_evidence=None,
        )
        self.assertEqual(old, same)
        self.assertNotIn("non_fx_observation", old)
        self.assertEqual(old["fresh_m15_pairs"], 1)

    def test_09_explicit_empty_overlay_does_not_change_fx_28_rows(self):
        old = trader_readonly_observation(_resident(_row()), now=NOW)
        new = trader_readonly_observation(
            _resident(_row()), now=NOW, non_fx_evidence={},
        )
        overlay = new.pop("non_fx_observation")
        self.assertEqual(new, old)
        self.assertEqual(overlay["expected_symbols"], 7)
        self.assertEqual(overlay["mtf_coverage"]["M15"], 0)
        self.assertTrue(overlay["no_orders"] and overlay["no_alerts"])

    def test_10_resident_hydration_opt_in_adds_overlay_without_provider_call(self):
        session = {}
        resident = _resident(_row())
        current = datetime.now(timezone.utc)
        with mock.patch.object(
            atlasquant_trader_resident, "resident_trader_state",
            return_value=resident,
        ) as load:
            atlasquant_trader_resident.hydrate_trader_resident_state(
                session, {"only_mock": True},
                non_fx_evidence={"DXY": {"M5": evidence("M5", date=current)}},
            )
        load.assert_called_once()
        board = session["atlasquant_aion_trader_observation"]
        self.assertEqual(board["non_fx_observation"]["mtf_coverage"]["M5"], 1)
        self.assertEqual(len(board["rows"]), 28)
        self.assertFalse(board["mode"]["authorizes_send"])

    def test_11_invalid_resident_refresh_clears_nonfx_as_well(self):
        session = {
            "atlasquant_aion_trader_observation": {
                "non_fx_observation": {"mtf_coverage": {"M5": 7}}
            }
        }
        with mock.patch.object(
            atlasquant_trader_resident, "resident_trader_state",
            side_effect=ValueError("invalid"),
        ):
            atlasquant_trader_resident.hydrate_trader_resident_state(
                session, {}, non_fx_evidence={"DXY": {"M5": evidence("M5")}},
            )
        self.assertNotIn("atlasquant_aion_trader_observation", session)

    def test_12_no_external_connectors_orders_or_automatic_alerts(self):
        import atlasquant_aion_trader_nonfx as module
        code = inspect.getsource(module)
        for phrase in (
            "import requests", "import socket", "import ccxt",
            "import MetaTrader5", "fetch_candles(", "adapter.send(",
            "ExecutionOutbox(", "resample(",
        ):
            self.assertNotIn(phrase, code)
        board = nonfx_readonly_overlay(now=NOW)
        self.assertTrue(board["no_orders"])
        self.assertTrue(board["no_new_data_calls"])
        self.assertFalse(board["authorizes_send"])
        self.assertEqual(board["p0_homologated"], 0)


if __name__ == "__main__":
    unittest.main()
