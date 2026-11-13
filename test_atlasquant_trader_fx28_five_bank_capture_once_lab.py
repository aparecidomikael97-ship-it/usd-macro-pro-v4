"""All fixtures are synthetic; no HTTPS, bank origin or real AM12 run."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from atlasquant_trader_fx28_five_bank_capture_once_lab import (
    _STEPS, _ORDER, collect_five_missing_policy_sources_once_lab as run,
)

UTC = timezone.utc
START = datetime(2026, 11, 13, 15, 50, tzinfo=UTC)


def archive(*, checked=(), missing_folder=False):
    good = set(checked)
    return {
        "state": ("LAB_FX28_POLICY_ARCHIVE_PARTIAL_OR_REJECTED_NO_GO"
                  if not missing_folder else "LAB_FX28_POLICY_ARCHIVE_REPLAY_BLOCKED"),
        "reason": ("ARCHIVE_MISSING_REJECTED_OR_NOT_YET_CAPTURED"
                   if not missing_folder else "LOCAL_ISSUER_ARCHIVE_FOLDER_MISSING"),
        "currencies_locally_checked": sorted(good),
        "pairs_with_both_policy_originals_locally_checked":
            len(good)*(len(good)-1)//2,
    }


class Clock:
    def __init__(self, start=START):
        self.start = start
        self.calls = 0
    def __call__(self):
        t = self.start + timedelta(seconds=self.calls)
        self.calls += 1
        return t


class FakeSteps:
    def __init__(self, broken=None, behavior=None):
        self.calls = []
        self.broken = broken
        self.behavior = behavior
    def build(self):
        mapping = {}
        for currency in _ORDER:
            _real_col, _real_inspect, _real_save, src_key, state = _STEPS[currency]
            def collect(c=currency):
                self.calls.append(("get", c))
                if c == self.broken and self.behavior == "network":
                    raise OSError("synthetic 403/timeout")
                finished = ("2026-11-13T16:50:00Z"
                            if c == self.broken and self.behavior == "future"
                            else "2026-11-13T15:50:00Z")
                return (b"<html>NOT A BANK SOURCE</html>",
                        {"finished_at_utc": finished})
            def check(*, receipt, decision_at_utc, c=currency, **kwargs):
                self.calls.append(("validator", c))
                if c == self.broken and self.behavior == "rejected":
                    return {"state":"BLOCKED","trade_authorized":False,
                            "publishable":False}
                return {"state":_STEPS[c][4],"trade_authorized":False,
                        "publishable":False}
            def save(*, body, receipt, local_appdata, c=currency):
                self.calls.append(("saver", c))
                if c == self.broken and self.behavior == "write_error":
                    raise OSError("synthetic disk error")
                return (Path(local_appdata)/"fake.html",
                        Path(local_appdata)/"fake.receipt.json")
            mapping[currency] = (collect, check, save, src_key, state)
        return mapping


class FivePolicyCollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.fake = FakeSteps()

    def call(self, *, capture=True, before=None, after=None,
             clock=None, steps=None, root=None):
        before = archive(missing_folder=True) if before is None else before
        after = archive(checked=_ORDER) if after is None else after
        with patch("atlasquant_trader_fx28_five_bank_capture_once_lab.replay",
                   side_effect=[before,after]) as spy:
            result = run(
                capture_missing=capture,
                local_appdata=self.root if root is None else root,
                decision_clock=clock or Clock(),
                steps=steps if steps is not None else self.fake.build())
        return result, spy.call_count

    def safe(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        for k in ("trade_authorized", "publishable", "live_alert_allowed",
                  "scheduler_enabled", "worker_enabled", "fx_direction_admissible",
                  "historical_pit_cpi_bilateral_verified",
                  "issuer_origin_independently_authenticated",
                  "first_seen_independently_authenticated"):
            self.assertFalse(r[k], k)
        self.assertIsNone(r["directional_bias"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertEqual(r["new_cost_brl"], 0)
        self.assertLessEqual(r["https_gets_attempted_or_started"], 5)

    def test_01_default_no_flag_zero_reads_or_http(self):
        result, calls = self.call(capture=False)
        self.safe(result)
        self.assertEqual(calls, 0)
        self.assertEqual(self.fake.calls, [])
        self.assertEqual(result["state"], "LAB_FX28_FIVE_SOURCE_CAPTURE_NO_ACTION")

    def test_02_string_true_is_not_explicit_permission(self):
        for bad in ("true", 1, None, 0, [], {}):
            with self.subTest(bad=bad):
                result, calls = self.call(capture=bad)
                self.safe(result)
                self.assertEqual(calls, 0)
                self.assertEqual(result["https_gets_attempted_or_started"], 0)

    def test_03_empty_archive_five_bounded_gets_validate_save_and_replay(self):
        result, calls = self.call()
        self.safe(result)
        self.assertEqual(calls,2)
        self.assertEqual(result["https_gets_attempted_or_started"],5)
        self.assertEqual(result["state"],"LAB_FX28_FIVE_SOURCE_CAPTURE_LOCAL_REPLAY_ONLY_NO_GO")
        self.assertEqual(result["replayed_currency_count_after_run"],5)
        self.assertEqual(result["pairs_with_both_policy_originals_locally_checked_after_run"],10)
        self.assertEqual(
            [c for op,c in self.fake.calls if op=="get"], list(_ORDER))
        self.assertEqual(
            [c for op,c in self.fake.calls if op=="saver"], list(_ORDER))
        self.assertTrue(all(v=="SAVED_AND_LOCALLY_REPLAYED_ONLY_NO_GO"
                            for v in result["currency_results"].values()))

    def test_04_already_locally_checked_issuer_skipped_no_get(self):
        result,_ = self.call(
            before=archive(checked=("GBP","JPY")),
            after=archive(checked=_ORDER))
        self.safe(result)
        self.assertEqual(result["https_gets_attempted_or_started"],3)
        self.assertEqual([c for op,c in self.fake.calls if op=="get"],
                         ["CHF","AUD","NZD"])
        self.assertEqual(result["currency_results"]["GBP"],
                         "SKIPPED_ALREADY_LOCALLY_CHECKED")
        self.assertEqual(result["currency_results"]["JPY"],
                         "SKIPPED_ALREADY_LOCALLY_CHECKED")

    def test_05_rba_403_no_retry_no_bypass_other_four_continue(self):
        self.fake=FakeSteps("AUD","network")
        r,_=self.call(after=archive(checked=("GBP","JPY","CHF","NZD")))
        self.safe(r)
        self.assertEqual(r["https_gets_attempted_or_started"],5)
        self.assertEqual(r["currency_results"]["AUD"],"FETCH_VALIDATE_OR_SAVE_FAILED")
        self.assertEqual([c for op,c in self.fake.calls if op=="get"].count("AUD"),1)
        self.assertIn(("get","NZD"),self.fake.calls)
        self.assertNotIn(("saver","AUD"),self.fake.calls)
        self.assertEqual(r["state"],"LAB_FX28_FIVE_SOURCE_CAPTURE_PARTIAL_OR_BLOCKED_NO_GO")

    def test_06_validator_rejection_prevents_save(self):
        self.fake=FakeSteps("CHF","rejected")
        r,_=self.call(after=archive(checked=("GBP","JPY","AUD","NZD")))
        self.safe(r)
        self.assertEqual(r["currency_results"]["CHF"],"ISSUER_BYTES_OR_RECEIPT_REJECTED")
        self.assertNotIn(("saver","CHF"),self.fake.calls)

    def test_07_future_timestamp_blocks_source(self):
        self.fake=FakeSteps("JPY","future")
        r,_=self.call(after=archive(checked=("GBP","CHF","AUD","NZD")))
        self.safe(r)
        self.assertEqual(r["currency_results"]["JPY"],"CAPTURE_CLAIMED_FUTURE_OR_CLOCK_REWIND")
        self.assertNotIn(("validator","JPY"),self.fake.calls)
        self.assertNotIn(("saver","JPY"),self.fake.calls)

    def test_08_saver_error_does_not_promote_source(self):
        self.fake=FakeSteps("NZD","write_error")
        r,_=self.call(after=archive(checked=("GBP","JPY","CHF","AUD")))
        self.safe(r)
        self.assertEqual(r["currency_results"]["NZD"],"FETCH_VALIDATE_OR_SAVE_FAILED")
        self.assertEqual(r["state"],"LAB_FX28_FIVE_SOURCE_CAPTURE_PARTIAL_OR_BLOCKED_NO_GO")

    def test_09_save_success_is_not_replay_success(self):
        r,_=self.call(after=archive(checked=("GBP","JPY","CHF","AUD")))
        self.safe(r)
        self.assertEqual(r["currency_results"]["NZD"],"SAVED_BUT_REPLAY_DID_NOT_ACCEPT")
        self.assertEqual(r["state"],"LAB_FX28_FIVE_SOURCE_CAPTURE_PARTIAL_OR_BLOCKED_NO_GO")

    def test_10_bad_root_prevents_any_http(self):
        for bad in ("", ".", "relative", None):
            with self.subTest(root=bad):
                r,calls=self.call(root=bad)
                self.safe(r)
                self.assertEqual(calls,0)
                self.assertEqual(r["https_gets_attempted_or_started"],0)
        self.assertEqual(self.fake.calls,[])

    def test_11_local_lab_dir_symlink_refused_before_any_network(self):
        base=Path(self.tmp.name)
        actual=base/"actual";actual.mkdir()
        (base/"AtlasQuant").symlink_to(actual, target_is_directory=True)
        r,calls=self.call(root=str(base))
        self.safe(r)
        self.assertEqual(calls,0)
        self.assertEqual(self.fake.calls,[])

    def test_12_preflight_replay_corrupt_blocks_all_gets(self):
        bad=archive()
        bad["state"]="LAB_FX28_POLICY_ARCHIVE_REPLAY_BLOCKED"
        bad["reason"]="LOCAL_LAB_DIRECTORY_SYMLINK_REFUSED"
        r,calls=self.call(before=bad)
        self.safe(r)
        self.assertEqual(calls,1)
        self.assertEqual(r["reason"],"PRECHECK_ARCHIVE_REPLAY_BLOCKED")
        self.assertEqual(r["https_gets_attempted_or_started"],0)
        self.assertEqual(self.fake.calls,[])

    def test_13_post_capture_clock_naive_blocks_source_and_replay(self):
        seq=iter([START,START.replace(tzinfo=None)] * 6)
        r,calls=self.call(clock=lambda:next(seq),after=archive())
        self.safe(r)
        self.assertEqual(r["currency_results"]["GBP"],"POST_CAPTURE_CLOCK_INVALID")
        self.assertNotIn(("saver","GBP"),self.fake.calls)
        self.assertEqual(calls,2)

    def test_14_clock_rewind_blocks_source(self):
        seq=iter([START,START-timedelta(seconds=5)]*6)
        r,_=self.call(clock=lambda:next(seq),after=archive())
        self.safe(r)
        self.assertEqual(r["currency_results"]["GBP"],
                         "CAPTURE_CLAIMED_FUTURE_OR_CLOCK_REWIND")
        self.assertNotIn(("saver","GBP"),self.fake.calls)

    def test_15_invalid_clock_before_preflight_blocks_without_io(self):
        for bad in (None, START.replace(tzinfo=None),
                    START.replace(microsecond=1)):
            with self.subTest(time=bad):
                r,calls=self.call(clock=lambda:bad)
                self.safe(r)
                self.assertEqual(calls,0)
                self.assertEqual(r["https_gets_attempted_or_started"],0)

    def test_16_invalid_provider_map_blocks_without_get(self):
        mapping=self.fake.build()
        del mapping["AUD"]
        r,calls=self.call(steps=mapping)
        self.safe(r)
        self.assertEqual(r["reason"],"INVALID_ISSUER_COLLECTOR_MAPPING")
        self.assertEqual(calls,1)
        self.assertEqual(self.fake.calls,[])

    def test_17_when_all_five_already_checked_zero_http(self):
        r,calls=self.call(before=archive(checked=_ORDER),after=archive(checked=_ORDER))
        self.safe(r)
        self.assertEqual(calls,2)
        self.assertEqual(r["https_gets_attempted_or_started"],0)
        self.assertEqual(self.fake.calls,[])
        self.assertEqual(r["state"],"LAB_FX28_FIVE_SOURCE_CAPTURE_LOCAL_REPLAY_ONLY_NO_GO")

    def test_18_finish_later_than_preflight_but_before_postclock_is_valid(self):
        self.fake=FakeSteps()
        # Capture finishes at initial UTC second. Post-capture local clock
        # is one second later; the audit must use a NEW later time too.
        clock=Clock()
        r,calls=self.call(clock=clock)
        self.safe(r)
        self.assertEqual(calls,2)
        self.assertEqual(clock.calls,7)
        self.assertEqual(r["currency_results"]["AUD"],
                         "SAVED_AND_LOCALLY_REPLAYED_ONLY_NO_GO")


if __name__ == "__main__":
    unittest.main()
