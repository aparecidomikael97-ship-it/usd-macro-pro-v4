"""Synthetic regression tests for the fail-closed tick clock diagnostic."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest

from atlasquant_mt5_tick_timestamp_guard_lab import (
    audit_tick_timestamp_lab, run_readonly_probe,
)


NOW = datetime(2026, 11, 9, 23, 17, 5, tzinfo=timezone.utc)


def audit(tick: int, **overrides):
    args = {
        "before_utc": NOW,
        "after_utc": NOW + timedelta(seconds=2),
        "tick_epoch": tick,
        "terminal_connected": True,
        "symbol_visible": True,
    }
    args.update(overrides)
    return audit_tick_timestamp_lab(**args)


class TickTimeGuardTests(unittest.TestCase):
    def test_future_pepperstone_like_offset_fails_closed(self):
        result = audit(int(NOW.timestamp()) + 7200)
        self.assertEqual(result["reason"], "TICK_TIMESTAMP_IN_FUTURE_RELATIVE_TO_PC")
        self.assertEqual(result["state"], "LAB_TICK_CLOCK_BLOCKED")
        self.assertGreater(result["tick_minus_observation_after_seconds"], 7000)
        self.assertFalse(result["safe_for_point_in_time_join"])
        self.assertFalse(result["trade_authorized"])

    def test_fresh_tick_remains_unattested(self):
        result = audit(int(NOW.timestamp()) + 1)
        self.assertEqual(result["state"], "LAB_TICK_CLOCK_PLAUSIBLE_UNATTESTED")
        self.assertFalse(result["mt5_timestamp_is_utc_attested"])
        self.assertFalse(result["publishable"])

    def test_stale_tick_is_not_called_broker_disconnected(self):
        result = audit(int(NOW.timestamp()) - 360)
        self.assertEqual(result["reason"], "TICK_TIMESTAMP_STALE_OR_MARKET_CLOSED")

    def test_future_tolerance_edge(self):
        result = audit(int((NOW + timedelta(seconds=7)).timestamp()))
        self.assertEqual(result["state"], "LAB_TICK_CLOCK_PLAUSIBLE_UNATTESTED")

    def test_invalid_epoch_rejected(self):
        for value in (True, "7200", 0, -1, None):
            self.assertEqual(audit(value)["reason"], "INVALID_TICK_EPOCH")

    def test_naive_or_inverted_window_rejected(self):
        self.assertEqual(audit(1, before_utc=NOW.replace(tzinfo=None))["reason"], "INVALID_CLOCK_WINDOW")
        self.assertEqual(audit(1, after_utc=NOW - timedelta(seconds=1))["reason"], "INVALID_CLOCK_WINDOW")

    def test_slow_probe_rejected(self):
        self.assertEqual(audit(1, after_utc=NOW + timedelta(seconds=11))["reason"], "PROBE_WINDOW_TOO_LONG")

    def test_disconnected_or_hidden_symbol_rejected(self):
        self.assertEqual(audit(1, terminal_connected=False)["reason"], "TERMINAL_NOT_CONNECTED")
        self.assertEqual(audit(1, symbol_visible=False)["reason"], "SYMBOL_NOT_VISIBLE_NO_AUTO_SELECT")

    def test_unrepresentable_epoch_rejected(self):
        self.assertEqual(audit(10**30)["reason"], "UNREPRESENTABLE_TICK_EPOCH")

    def test_read_only_api_surface_and_shutdown(self):
        class FakeMT5:
            def __init__(self):
                self.calls = []

            def initialize(self, **kw):
                self.calls.append("initialize")
                return True

            def terminal_info(self):
                self.calls.append("terminal_info")
                return SimpleNamespace(connected=True)

            def symbol_info(self, name):
                self.assert_symbol(name)
                self.calls.append("symbol_info")
                return SimpleNamespace(visible=True)

            def symbol_info_tick(self, name):
                self.assert_symbol(name)
                self.calls.append("symbol_info_tick")
                return SimpleNamespace(time=int(NOW.timestamp()))

            def shutdown(self):
                self.calls.append("shutdown")

            @staticmethod
            def assert_symbol(name):
                if name != "EURUSD":
                    raise AssertionError("unexpected symbol")

        api = FakeMT5()
        result = run_readonly_probe(api, terminal_path="C:/mt5/terminal64.exe", clock=lambda: NOW)
        self.assertEqual(result["state"], "LAB_TICK_CLOCK_PLAUSIBLE_UNATTESTED")
        self.assertEqual(api.calls, ["initialize", "terminal_info", "symbol_info", "symbol_info_tick", "shutdown"])

    def test_initialization_failure_has_no_shutdown(self):
        class FailedMT5:
            def initialize(self, **kw):
                return False

            def shutdown(self):
                raise AssertionError("must not shutdown another connection")

        result = run_readonly_probe(FailedMT5(), terminal_path="C:/mt5.exe", clock=lambda: NOW)
        self.assertEqual(result["reason"], "MT5_INITIALIZATION_FAILED")


if __name__ == "__main__":
    unittest.main()
