"""One-step Windows time/MT5 orchestration tests using fake, local inputs."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from atlasquant_mt5_xauusd_one_step_lab import (
    W32TIME_READONLY_QUERY, inspect_windows_time_status_lab as inspect,
    run_xauusd_one_step_lab as run,
)
from test_atlasquant_mt5_xauusd_closedbar_capture_lab import (
    AT, FakeMT5, WIN_TERMINAL,
)

ENGLISH_GOOD = """Leap Indicator: 0(no warning)
Stratum: 2 (secondary reference)
Last Successful Sync Time: 11/10/2026 11:59:00 AM
Source: time.windows.com,0x9
Phase Offset: -0.03125s
Last Sync Error: 0 (The command completed successfully.)
Time since Last Good Sync Time: 30.5s
"""

PORTUGUESE_GOOD = """Indicador de Salto: 0(sem aviso)
Camada: 2
Origem: pool.ntp.org,0x9
Deslocamento de fase: 0,016s
Último erro de sincronização: 0 (concluído)
Tempo desde a última sincronização bem-sucedida: 21,5s
"""


class XauUsdOneStepLabTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="xau_one_step_synthetic_")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "AtlasQuant" / "LAB" / "MT5_Snapshots"
        self.api = FakeMT5()

    def execute(self, text=ENGLISH_GOOD, returncode=0):
        return run(self.api, terminal_path=WIN_TERMINAL, output_root=self.root,
                   clock=lambda: AT, status_text=text,
                   status_returncode=returncode)

    def assert_never_trade(self, result):
        self.assertFalse(result["os_clock_independently_authenticated"])
        self.assertFalse(result["pepperstone_broker_identity_independently_authenticated"])
        self.assertFalse(result["historical_point_in_time_verified"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertIsNone(result["gold_bias"])
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["publishable"])
        self.assertFalse(result["can_feed_live_radar"])
        for call in self.api.calls:
            self.assertIn(call[0], {"initialize", "terminal_info", "symbol_info",
                                    "copy_rates_from_pos", "shutdown"})

    def test_official_read_only_query_no_resync_or_config(self):
        self.assertEqual(W32TIME_READONLY_QUERY,
                         ("w32tm", "/query", "/status", "/verbose"))

    def test_eng_os_time_candidate_not_independently_attested(self):
        result = inspect(ENGLISH_GOOD, returncode=0)
        self.assertTrue(result["clock_sync_candidate"])
        self.assertEqual(result["state"], "LAB_WINDOWS_TIME_OS_SYNC_CANDIDATE_UNATTESTED")
        self.assertEqual(result["phase_offset_seconds_magnitude"], 0.03125)
        self.assertEqual(result["time_since_last_good_sync_seconds"], 30.5)
        self.assertFalse(result["clock_utc_independently_attested"])

    def test_ptbr_time_service_evidence_is_supported(self):
        result = inspect(PORTUGUESE_GOOD, returncode=0)
        self.assertTrue(result["clock_sync_candidate"], result)
        self.assertEqual(result["time_since_last_good_sync_seconds"], 21.5)

    def test_one_step_passes_collects_and_independently_audits_3700(self):
        result = self.execute()
        self.assertEqual(result["state"],
                         "LAB_XAUUSD_ONE_STEP_LOCAL_ARCHIVE_READY_UNATTESTED")
        self.assertEqual(result["verified_local_bars"], 3700)
        self.assertEqual(result["mt5_capture"]["series_count"], 3)
        self.assertEqual(result["archive_audit"]["verified_series"], 3)
        self.assertTrue(Path(result["archive_directory"]).exists())
        self.assertEqual(self.api.calls[-1], ("shutdown",))
        self.assert_never_trade(result)

    def test_ptbr_os_status_can_pass_synthetic_one_step(self):
        result = self.execute(text=PORTUGUESE_GOOD)
        self.assertEqual(result["verified_local_bars"], 3700)
        self.assert_never_trade(result)

    def test_local_cmos_clock_does_not_initialize_mt5(self):
        status = ENGLISH_GOOD.replace("time.windows.com,0x9", "Local CMOS Clock")
        result = self.execute(text=status)
        self.assertIn("NO_NONLOCAL_TIME_SOURCE", result["reason"])
        self.assertEqual(self.api.calls, [])
        self.assertFalse(self.root.exists())
        self.assert_never_trade(result)

    def test_leap_unsynchronized_blocks_before_mt5(self):
        status = ENGLISH_GOOD.replace("Leap Indicator: 0", "Leap Indicator: 3")
        result = self.execute(text=status)
        self.assertIn("W32TIME_LEAP_OR_LAST_SYNC_ERROR", result["reason"])
        self.assertEqual(self.api.calls, [])

    def test_nonzero_sync_error_blocks_before_mt5(self):
        status = ENGLISH_GOOD.replace("Last Sync Error: 0", "Last Sync Error: 1")
        result = self.execute(text=status)
        self.assertIn("W32TIME_LEAP_OR_LAST_SYNC_ERROR", result["reason"])
        self.assertEqual(self.api.calls, [])

    def test_over_hour_old_sync_blocks_before_mt5(self):
        status = ENGLISH_GOOD.replace("30.5s", "3600.1s")
        result = self.execute(text=status)
        self.assertIn("W32TIME_LAST_GOOD_SYNC_TOO_OLD", result["reason"])
        self.assertEqual(self.api.calls, [])

    def test_offset_over_one_second_blocks_before_mt5(self):
        status = ENGLISH_GOOD.replace("-0.03125s", "-1.001s")
        result = self.execute(text=status)
        self.assertIn("W32TIME_PHASE_OFFSET_TOO_LARGE", result["reason"])
        self.assertEqual(self.api.calls, [])

    def test_missing_verbose_sync_elapsed_blocks_before_mt5(self):
        status = ENGLISH_GOOD.replace("Time since Last Good Sync Time: 30.5s", "")
        result = self.execute(text=status)
        self.assertIn("W32TIME_LAST_GOOD_SYNC_TOO_OLD", result["reason"])
        self.assertEqual(self.api.calls, [])

    def test_missing_verbose_phase_offset_blocks_before_mt5(self):
        status = ENGLISH_GOOD.replace("Phase Offset: -0.03125s", "")
        result = self.execute(text=status)
        self.assertIn("W32TIME_PHASE_OFFSET_TOO_LARGE", result["reason"])
        self.assertEqual(self.api.calls, [])

    def test_failed_os_time_query_blocks_before_mt5(self):
        result = self.execute(returncode=1)
        self.assertIn("W32TIME_STATUS_UNAVAILABLE", result["reason"])
        self.assertEqual(self.api.calls, [])

    def test_empty_os_time_query_blocks(self):
        result = self.execute(text="")
        self.assertIn("W32TIME_STATUS_UNAVAILABLE", result["reason"])
        self.assertEqual(self.api.calls, [])

    def test_mt5_not_connected_blocks_even_after_w32time_candidate(self):
        self.api.connected = False
        result = self.execute()
        self.assertTrue(result["clock_preflight"]["clock_sync_candidate"])
        self.assertIn("MT5_CAPTURE_BLOCKED:MT5_TERMINAL_NOT_CONNECTED", result["reason"])
        self.assertFalse(self.root.exists())
        self.assert_never_trade(result)

    def test_incomplete_w1_archive_never_written(self):
        self.api.series_by_frame[self.api.TIMEFRAME_W1].pop()
        result = self.execute()
        self.assertIn("MT5_CAPTURE_BLOCKED:W1:CLOSED_BAR_COUNT_INCOMPLETE", result["reason"])
        self.assertFalse(self.root.exists())

    def test_independent_audit_failure_fails_closed_and_keeps_archive(self):
        with patch("atlasquant_mt5_xauusd_one_step_lab.audit_xauusd_closedbar_archive_lab",
                   return_value={"status": "LOCAL_XAUUSD_ARCHIVE_FAIL"}):
            result = self.execute()
        self.assertEqual(result["reason"], "XAUUSD_ARCHIVE_INDEPENDENT_AUDIT_FAILED")
        self.assertEqual(result["verified_local_bars"], 0)
        self.assertTrue(Path(result["archive_directory"]).exists())
        self.assert_never_trade(result)

    def test_second_run_same_utc_second_never_overwrites_archive(self):
        first = self.execute()
        before = (Path(first["archive_directory"]) / "xauusd_manifest.json").read_bytes()
        second = self.execute()
        self.assertIn("CAPTURE_RUN_DIRECTORY_ALREADY_EXISTS_NO_OVERWRITE", second["reason"])
        self.assertEqual((Path(first["archive_directory"]) / "xauusd_manifest.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
