"""Mock-only safety tests; never import MetaTrader5 or connect to an account."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import unittest
from zoneinfo import ZoneInfo

from atlasquant_mt5_d1w1_minimal_clock_probe_lab import (
    inspect_mt5_d1w1_clock_lab, run_connected_probe, SCHEMA,
)

UTC = timezone.utc
NY = ZoneInfo("America/New_York")
NOW = datetime(2026, 11, 9, 11, tzinfo=UTC)


@dataclass
class Meta:
    connected: bool = True
    build: int = 6306


@dataclass
class Symbol:
    visible: bool = True


class FakeAPI:
    TIMEFRAME_D1 = 16385
    TIMEFRAME_W1 = 32769

    def __init__(self, *, mismatch=False):
        self.calls = []
        self.mismatch = mismatch
        self.connected = True
        self.visible = True
        self.count_short = False
        self.timestamps_bad = False
        self.open_bar = False
        self.initialize_ok = True
        self.fail = False

    def initialize(self, *, path, timeout):
        self.calls.append(("initialize", path, timeout))
        return self.initialize_ok

    def shutdown(self):
        self.calls.append(("shutdown",))

    def terminal_info(self):
        self.calls.append(("terminal_info",))
        return Meta(connected=self.connected)

    def symbol_info(self, symbol):
        self.calls.append(("symbol_info", symbol))
        return Symbol(visible=self.visible)

    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        self.calls.append(("copy_rates_from_pos", symbol, timeframe, start, count))
        if self.fail:
            raise ValueError("simulated terminal error")
        if self.mismatch:
            final = datetime(2026, 11, 5, tzinfo=UTC) if timeframe == self.TIMEFRAME_D1 else datetime(2026, 10, 25, tzinfo=UTC)
            interval = timedelta(days=1 if timeframe == self.TIMEFRAME_D1 else 7)
        else:
            # Sundays 17 NY are both W1 and D1 markers; D1 other days vary.
            final = datetime(2026, 11, 5, 17, tzinfo=NY) if timeframe == self.TIMEFRAME_D1 else datetime(2026, 11, 1, 17, tzinfo=NY)
            interval = timedelta(days=1 if timeframe == self.TIMEFRAME_D1 else 7)
        # Preserve New York 17:00 across DST; there are no Friday/Saturday
        # D1 opens in the NY-close reference. Don't synthesize market bars then.
        if not self.mismatch and timeframe == self.TIMEFRAME_D1:
            current, chosen = final, []
            while len(chosen) < count:
                if current.weekday() in (6, 0, 1, 2, 3):
                    chosen.append(current)
                current -= interval
            chosen.reverse()
        else:
            chosen = [final-i*interval for i in reversed(range(count))]
        rows = [dict(time=int(x.timestamp())) for x in chosen]
        if self.timestamps_bad:
            rows[-1]["time"] = rows[-2]["time"]
        if self.open_bar:
            rows[-1]["time"] = int(NOW.timestamp())
        return rows[:-1] if self.count_short else rows


class ClockProbeTests(unittest.TestCase):
    def safe(self, r):
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        for key in ("trade_authorized", "publishable", "live_alert_allowed",
                    "pepperstone_server_association_verified", "broker_session_calendar_verified",
                    "server_identity_authenticated", "price_vintage_at_decision_authenticated"):
            self.assertFalse(r[key], key)
        self.assertIsNone(r["validated_directional_accuracy"])
        self.assertIsNone(r["calibrated_direction_probability"])

    def test_read_only_four_series_and_closed_positions(self):
        f = FakeAPI()
        r = run_connected_probe(f, terminal_path="C:/MT5/terminal64.exe", now_utc=NOW, count=3)
        self.safe(r)
        self.assertEqual(r["checked_series"], 4)
        self.assertEqual(r["checked_bar_labels"], 12)
        self.assertEqual(r["terminal_build"], 6306)
        self.assertEqual(sum(1 for x in f.calls if x[0] == "copy_rates_from_pos"), 4)
        self.assertTrue(all(c[3] == 1 for c in f.calls if c[0] == "copy_rates_from_pos"))
        self.assertTrue(set(x[0] for x in f.calls) <= {
            "initialize", "shutdown", "terminal_info", "symbol_info", "copy_rates_from_pos"})
        self.assertEqual(f.calls[-1][0], "shutdown")
        self.assertEqual(r["state"], "LAB_NY_CLOSE_PATTERN_MATCH_UNATTESTED")

    def test_reference_disagreement_is_review_not_rewrite(self):
        f = FakeAPI(mismatch=True)
        r = inspect_mt5_d1w1_clock_lab(f, now_utc=NOW, count=3)
        self.safe(r)
        self.assertEqual(r["state"], "LAB_CLOCK_REFERENCE_DISCREPANCY_NEEDS_SERVER_REVIEW")
        self.assertGreater(r["reference_discrepancy_count"], 0)
        self.assertEqual(r["series"][0]["bar_labels"][-1]["open_utc"], "2026-11-05T00:00:00Z")

    def test_incomplete_mt5_data_blocks(self):
        f = FakeAPI();f.count_short = True
        r = inspect_mt5_d1w1_clock_lab(f, now_utc=NOW)
        self.safe(r);self.assertEqual(r["reason"], "MISSING_CLOSED_BARS_OR_PARTIAL_SERIES")
        self.assertEqual(r["checked_series"], 0)

    def test_invisible_symbols_do_not_autoselect(self):
        f = FakeAPI();f.visible = False
        r = inspect_mt5_d1w1_clock_lab(f, now_utc=NOW)
        self.safe(r);self.assertEqual(r["reason"], "SYMBOL_NOT_VISIBLE_NO_AUTO_SELECT")
        self.assertNotIn("symbol_select",[x[0] for x in f.calls])

    def test_api_disconnected(self):
        f = FakeAPI();f.connected = False
        r = inspect_mt5_d1w1_clock_lab(f, now_utc=NOW)
        self.assertEqual(r["reason"], "TERMINAL_NOT_CONNECTED");self.safe(r)

    def test_non_monotonic(self):
        f = FakeAPI();f.timestamps_bad = True
        r = inspect_mt5_d1w1_clock_lab(f, now_utc=NOW)
        self.assertEqual(r["reason"], "NON_MONOTONIC_OR_INVALID_MT5_TIMES");self.safe(r)

    def test_open_bar_rejected(self):
        f = FakeAPI();f.open_bar = True
        r = inspect_mt5_d1w1_clock_lab(f, now_utc=NOW)
        self.assertEqual(r["reason"], "BAR_NOT_NOMINALLY_CLOSED_AT_OBSERVATION");self.safe(r)

    def test_api_exception_fail_closed(self):
        f = FakeAPI();f.fail=True
        r = run_connected_probe(f,terminal_path="C:/MT5/terminal64.exe",now_utc=NOW)
        self.assertEqual(r["reason"], "MT5_DATA_OR_CLOCK_QUERY_FAILED")
        self.assertEqual(f.calls[-1][0], "shutdown");self.safe(r)

    def test_false_initialization_never_queries(self):
        f=FakeAPI();f.initialize_ok=False
        r=run_connected_probe(f,terminal_path="C:/MT5/terminal64.exe",now_utc=NOW)
        self.assertEqual(r["reason"], "MT5_INITIALIZATION_FAILED")
        self.assertEqual(len(f.calls), 1);self.safe(r)

    def test_invalid_sample_sizes_and_clocks(self):
        for bad in (0, 1, 21, True, 3.3):
            with self.subTest(n=bad):
                r=inspect_mt5_d1w1_clock_lab(FakeAPI(),now_utc=NOW,count=bad)
                self.assertEqual(r["reason"], "INVALID_OBSERVATION_CLOCK_OR_SAMPLE_SIZE")
        r=inspect_mt5_d1w1_clock_lab(FakeAPI(),now_utc=NOW.replace(tzinfo=None))
        self.assertEqual(r["reason"], "INVALID_OBSERVATION_CLOCK_OR_SAMPLE_SIZE")

    def test_deterministic_sha_and_no_secrets(self):
        x=inspect_mt5_d1w1_clock_lab(FakeAPI(),now_utc=NOW,count=2)
        y=inspect_mt5_d1w1_clock_lab(FakeAPI(),now_utc=NOW,count=2)
        self.assertEqual(x["report_sha256_local_only"],y["report_sha256_local_only"])
        self.assertFalse(any(z in str(x).lower() for z in ("account_number", "password", "balance")))
        self.assertIsNotNone(x["report_sha256_local_only"])

    def test_no_external_source_attestation_even_on_full_match(self):
        r=inspect_mt5_d1w1_clock_lab(FakeAPI(),now_utc=NOW)
        self.assertFalse(r["timestamp_represents_actual_session_open_verified"])
        self.assertFalse(r["real_directional_accuracy_validated"])
        self.assertEqual(r["new_cost_brl"],0)

    def test_dst_shift_correctly_retains_new_york_local_17h(self):
        r=inspect_mt5_d1w1_clock_lab(FakeAPI(),now_utc=NOW,count=12)
        self.assertTrue(r["research_only"])
        self.assertEqual(r["state"], "LAB_NY_CLOSE_PATTERN_MATCH_UNATTESTED")
        weeks=r["series"][1]["bar_labels"]
        # The local session is fixed while the UTC epoch varies with DST.
        self.assertTrue(all("T17:00:00" in b["open_new_york"] for b in weeks))
        self.assertTrue(any(b["open_new_york"].endswith("-04:00") for b in weeks))
        self.assertTrue(any(b["open_new_york"].endswith("-05:00") for b in weeks))


if __name__ == "__main__":
    unittest.main()
