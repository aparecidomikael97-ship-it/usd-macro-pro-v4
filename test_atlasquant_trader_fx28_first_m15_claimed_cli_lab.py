"""Offline tests for the explicit, unscheduled first-M15 one-shot CLI."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from contextlib import redirect_stdout
from io import StringIO
import json

from atlasquant_trader_fx28_first_m15_claimed_cli_lab import (
    execute_cli_lab, main as cli_main, _pinned_mt5_reader_deps_lab,
)
from atlasquant_trader_fx28_first_m15_atomic_claim_lab import CLAIM_NAME, WINDOW
from test_atlasquant_trader_fx28_first_m15_no_duplicate_precheck_lab import (
    StrictMock, TERMINAL, CLOSED,
)
from test_atlasquant_trader_fx28_first_m15_archive_census_readonly_lab import (
    OneCandleMock,
)


class FirstM15ClaimedCliTests(TestCase):
    def setUp(self):
        self.t = TemporaryDirectory(prefix="aq_fx28_cli_lab_")
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name) / "FX28_NY17_M15"
        self.root.mkdir()

    def execute(self, fake, *, mode="capture-once", at=CLOSED,
                confirm=WINDOW, path=TERMINAL):
        return execute_cli_lab(
            mode=mode, root=self.root, terminal_path=path,
            confirm_window=confirm, api=fake, clock=lambda: at,
        )

    def test_preflight_never_contacts_mt5_or_claims(self):
        fake = StrictMock([])
        out = self.execute(fake, mode="preflight")
        self.assertEqual(out["state"], "LAB_FX28_CLI_PREFLIGHT_ONLY_NO_GO")
        self.assertTrue(out["precheck"]["single_attempt_start_precheck_clear"])
        self.assertFalse(fake.calls)
        self.assertFalse((self.root / CLAIM_NAME).exists())

    def test_capture_before_close_never_claims_or_contacts_mt5(self):
        fake = StrictMock([])
        r = self.execute(fake, at=CLOSED - timedelta(minutes=6))
        self.assertEqual(r["reason"], "FIRST_M15_NOT_CLOSED_NO_IO_OR_CLAIM")
        self.assertFalse(fake.calls)
        self.assertFalse((self.root / CLAIM_NAME).exists())

    def test_too_late_does_not_claim_or_query_the_terminal(self):
        late=datetime(2026,11,16,9,0,tzinfo=timezone.utc)
        fake=StrictMock([])
        result=self.execute(fake,at=late)
        self.assertEqual(result["reason"],"TOO_LATE_FOR_PROSPECTIVE_FIRST_M15_NO_BACKFILL_NO_IO")
        self.assertFalse(fake.calls)
        self.assertFalse((self.root/CLAIM_NAME).exists())
    def test_main_late_refuses_without_import_or_claim(self):
        late=datetime(2026,11,16,9,0,tzinfo=timezone.utc)
        fake=StrictMock([])
        args=["--mode","capture-once","--archive-root",str(self.root),
              "--terminal-path",TERMINAL,"--confirm-window",WINDOW]
        stream=StringIO()
        with redirect_stdout(stream):
            code=cli_main(args,api_for_test=fake,clock=lambda:late,environ={})
        self.assertEqual(code,2)
        self.assertEqual(json.loads(stream.getvalue())["reason"],
                         "FIRST_M15_OUTSIDE_BOUNDED_WINDOW_OR_CLOCK_INVALID_NO_IO")
        self.assertFalse(fake.calls)
        self.assertFalse((self.root/CLAIM_NAME).exists())
    def test_clock_is_rechecked_after_claim_before_any_mt5_call(self):
        # Initial CLI gate and exclusive claim happen before a simulated
        # process suspension that crosses the immutable 23:00Z deadline.
        stamps=iter((CLOSED,CLOSED,datetime(2026,11,15,23,0,tzinfo=timezone.utc)))
        fake=StrictMock([])
        result=execute_cli_lab(
            mode="capture-once",root=self.root,terminal_path=TERMINAL,
            confirm_window=WINDOW,api=fake,clock=lambda:next(stamps))
        self.assertEqual(result["reason"],
                         "POST_CLAIM_CAPTURE_START_OUTSIDE_DEADLINE_NO_MT5_NO_RETRY")
        self.assertTrue(result["claim_created"])
        self.assertEqual(fake.calls,[])
        self.assertTrue((self.root/CLAIM_NAME).exists())

    def test_capture_requires_explicit_confirmation(self):
        fake = StrictMock([])
        r = self.execute(fake, confirm=None)
        self.assertEqual(r["reason"], "EXPLICIT_WINDOW_AND_TERMINAL_REQUIRED")
        self.assertFalse(fake.calls)

    def test_one_capture_followed_by_blocked_repeat(self):
        first, second = StrictMock([]), StrictMock([])
        r = self.execute(first)
        self.assertEqual(r["state"], "LAB_CLAIMED_FIRST_M15_ZERO_PRICE_OBSERVED_NO_GO")
        self.assertEqual(first.calls.count("copy_rates_range"), 28)
        self.assertEqual(r["missing_m15_total"], 28)
        self.assertTrue((self.root / CLAIM_NAME).exists())
        blocked = self.execute(second, at=CLOSED + timedelta(minutes=1))
        self.assertFalse(blocked["claim_created"])
        self.assertFalse(second.calls)
        self.assertEqual(len(list(self.root.glob(WINDOW+"_*/manifest.json"))), 1)

    def test_none_query_burns_attempt_and_no_repeat(self):
        failed = self.execute(StrictMock(None))
        self.assertTrue(failed["claim_created"])
        self.assertEqual(failed["collector_reason"], "MT5_HISTORY_QUERY_FAILED_NONE_EURUSD")
        second = StrictMock([])
        r = self.execute(second)
        self.assertFalse(r["claim_created"])
        self.assertFalse(second.calls)

    def test_other_mt5_terminal_path_cannot_capture_first_window(self):
        fake=StrictMock([])
        wrong=r"C:\Program Files\Other Broker MetaTrader 5\terminal64.exe"
        result=self.execute(fake,path=wrong)
        self.assertEqual(result["reason"],"INVALID_CALL_PARAMETERS_NO_CLAIM")
        self.assertFalse(result["claim_created"])
        self.assertEqual(fake.calls,[])
        self.assertFalse((self.root/CLAIM_NAME).exists())

    def test_am12_bundle_path_only_inside_atlasquant_layout(self):
        with TemporaryDirectory() as td:
            parent=Path(td)/"AtlasQuant"
            cli_dir=parent/"lab_capture_modules"
            cli_dir.mkdir(parents=True)
            root=parent/"lab_mt5_reader_deps"
            package=root/"MetaTrader5"
            package.mkdir(parents=True)
            (package/"__init__.py").write_text("# dummy, never imported")
            candidate=cli_dir/"atlasquant_trader_fx28_first_m15_claimed_cli_lab.py"
            self.assertEqual(_pinned_mt5_reader_deps_lab(candidate),root)
            self.assertIsNone(_pinned_mt5_reader_deps_lab(
                Path(td)/"other"/"cli.py"))

    def test_missing_or_linked_mt5_bundle_fails_closed(self):
        with TemporaryDirectory() as td:
            parent=Path(td)/"AtlasQuant"
            cli_dir=parent/"lab_capture_modules"
            cli_dir.mkdir(parents=True)
            root=parent/"lab_mt5_reader_deps"
            package=root/"MetaTrader5"
            candidate=cli_dir/"atlasquant_trader_fx28_first_m15_claimed_cli_lab.py"
            self.assertIsNone(_pinned_mt5_reader_deps_lab(candidate))
            package.mkdir(parents=True)
            self.assertIsNone(_pinned_mt5_reader_deps_lab(candidate))
            (package/"__init__.py").write_text("not an imported package")
            self.assertEqual(_pinned_mt5_reader_deps_lab(candidate),root)

    def test_missing_mt5_api_does_not_create_claim(self):
        r = self.execute(None)
        self.assertEqual(r["reason"], "MT5_API_UNAVAILABLE_NO_CLAIM")
        self.assertFalse((self.root / CLAIM_NAME).exists())

    def test_default_main_is_preflight_with_no_mt5(self):
        stream = StringIO()
        with redirect_stdout(stream):
            rc = cli_main(["--archive-root", str(self.root)],
                          clock=lambda:CLOSED, environ={})
        report = json.loads(stream.getvalue())
        self.assertEqual(rc, 0)
        self.assertEqual(report["state"], "LAB_FX28_CLI_PREFLIGHT_ONLY_NO_GO")
        self.assertFalse((self.root / CLAIM_NAME).exists())

    def test_main_explicit_mock_capture_and_replay_block(self):
        a,b = StrictMock([]),StrictMock([])
        args = ["--mode", "capture-once", "--archive-root", str(self.root),
                "--terminal-path", TERMINAL, "--confirm-window", WINDOW]
        for fake, expected_code in ((a,2),(b,2)):
            stream=StringIO()
            with redirect_stdout(stream):
                rc=cli_main(args,api_for_test=fake,clock=lambda:CLOSED,environ={})
            self.assertEqual(rc,expected_code)
            self.assertFalse(json.loads(stream.getvalue())["trade_authorized"])
        self.assertEqual(a.calls.count("copy_rates_range"),28)
        self.assertFalse(b.calls)

    def test_full_28_nominal_bars_still_only_local_claim_and_no_trade(self):
        fake=OneCandleMock()
        args=["--mode","capture-once","--archive-root",str(self.root),
              "--terminal-path",TERMINAL,"--confirm-window",WINDOW]
        stream=StringIO()
        with redirect_stdout(stream):
            code=cli_main(args,api_for_test=fake,clock=lambda:CLOSED,environ={})
        report=json.loads(stream.getvalue())
        self.assertEqual(code,0)
        self.assertEqual(report["captured_m15_total"],28)
        self.assertEqual(report["missing_m15_total"],0)
        self.assertEqual(report["state"],"LAB_CLAIMED_FIRST_M15_ARCHIVE_CHECKED_NO_GO")
        self.assertFalse(report["trade_authorized"])
        self.assertFalse(report["independent_broker_price_source_attested"])
    def test_partial_27_bars_exits_nonzero_but_keeps_archive(self):
        fake=OneCandleMock(empty_symbol="EURUSD")
        args=["--mode","capture-once","--archive-root",str(self.root),
              "--terminal-path",TERMINAL,"--confirm-window",WINDOW]
        stream=StringIO()
        with redirect_stdout(stream):
            code=cli_main(args,api_for_test=fake,clock=lambda:CLOSED,environ={})
        report=json.loads(stream.getvalue())
        self.assertEqual(code,2)
        self.assertEqual(report["captured_m15_total"],27)
        self.assertEqual(report["missing_m15_total"],1)
        self.assertEqual(report["state"],"LAB_CLAIMED_FIRST_M15_PARTIAL_PRICE_OBSERVED_NO_GO")
        self.assertTrue(Path(report["archive_dir"]).is_dir())
        self.assertFalse(report["trade_authorized"])
    def test_no_env_fails_without_mt5(self):
        fake=StrictMock([])
        stream=StringIO()
        with redirect_stdout(stream):
            rc=cli_main(["--mode","capture-once","--terminal-path",TERMINAL,
                         "--confirm-window",WINDOW],
                        api_for_test=fake,clock=lambda:CLOSED,environ={})
        self.assertEqual(rc,2)
        self.assertFalse(fake.calls)
        self.assertEqual(json.loads(stream.getvalue())["reason"],"LOCALAPPDATA_MISSING_FAIL_CLOSED")


if __name__ == "__main__":
    main(verbosity=2)
