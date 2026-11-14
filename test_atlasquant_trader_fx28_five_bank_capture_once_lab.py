"""All fixtures are synthetic; no HTTPS, bank origin or real AM12 run."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from atlasquant_trader_fx28_five_bank_capture_once_lab import (
    _STEPS, _ORDER, collect_five_missing_policy_sources_once_lab as run,
)

UTC = timezone.utc
START = datetime(2026, 11, 13, 15, 50, tzinfo=UTC)


def archive(*, checked=(), missing_folder=False, at=None, undated=()):
    good = set(checked)
    # Fake locally stamped receipts; never issuer-published timestamps.
    stamp = at if at is not None else "2026-11-13T15:00:00Z"
    return {
        "state": ("LAB_FX28_POLICY_ARCHIVE_PARTIAL_OR_REJECTED_NO_GO"
                  if not missing_folder else "LAB_FX28_POLICY_ARCHIVE_REPLAY_BLOCKED"),
        "reason": ("ARCHIVE_MISSING_REJECTED_OR_NOT_YET_CAPTURED"
                   if not missing_folder else "LOCAL_ISSUER_ARCHIVE_FOLDER_MISSING"),
        "currencies_locally_checked": sorted(good),
        "currency_archive_status": {
            c: {"selected_local_capture_utc_claim":
                (None if c in undated else stamp)}
            for c in good
        },
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
                    raise OSError("synthetic network/timeout")
                if c == self.broken and self.behavior == "http_403":
                    raise HTTPError("https://example.invalid/issuer", 403,
                                    "synthetic access denied", None, None)
                if c == self.broken and self.behavior == "url_error":
                    raise URLError("synthetic TLS or transport")
                finished = ("2026-11-13T16:50:00Z"
                            if c == self.broken and self.behavior == "future"
                            else "2026-11-13T15:50:00Z")
                return (b"<html>NOT A BANK SOURCE</html>",
                        {"finished_at_utc": finished})
            def check(*, receipt, decision_at_utc, c=currency, **kwargs):
                self.calls.append(("validator", c))
                if c == self.broken and self.behavior == "rejected":
                    return {"state":"BLOCKED","reason":"SYNTHETIC_INVALID_POLICY_DATA",
                            "trade_authorized":False,"publishable":False}
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
        self.assertIsInstance(r["failure_diagnostics_by_currency"], dict)
        for c, reason in r["failure_diagnostics_by_currency"].items():
            self.assertIn(c, _ORDER)
            self.assertIsInstance(reason, str)
            self.assertTrue(reason)
            # The diagnostic must not contain raw exceptions, URLs, or bodies.
            self.assertNotIn("http://", reason.lower())
            self.assertNotIn("https://", reason.lower())

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
        self.assertEqual(r["failure_diagnostics_by_currency"]["AUD"],
                         "FETCH_TRANSPORT_OR_RESPONSE_EXCEPTION")
        self.assertEqual([c for op,c in self.fake.calls if op=="get"].count("AUD"),1)
        self.assertIn(("get","NZD"),self.fake.calls)
        self.assertNotIn(("saver","AUD"),self.fake.calls)
        self.assertEqual(r["state"],"LAB_FX28_FIVE_SOURCE_CAPTURE_PARTIAL_OR_BLOCKED_NO_GO")

    def test_06_validator_rejection_prevents_save(self):
        self.fake=FakeSteps("CHF","rejected")
        r,_=self.call(after=archive(checked=("GBP","JPY","AUD","NZD")))
        self.safe(r)
        self.assertEqual(r["currency_results"]["CHF"],"ISSUER_BYTES_OR_RECEIPT_REJECTED")
        self.assertEqual(r["failure_diagnostics_by_currency"]["CHF"],
                         "VALIDATOR_REJECTED_SYNTHETIC_INVALID_POLICY_DATA")
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
        self.assertEqual(r["failure_diagnostics_by_currency"]["NZD"],
                         "LAB_LOCAL_SAVE_EXCEPTION")
        self.assertEqual(r["state"],"LAB_FX28_FIVE_SOURCE_CAPTURE_PARTIAL_OR_BLOCKED_NO_GO")

    def test_09_save_success_is_not_replay_success(self):
        r,_=self.call(after=archive(checked=("GBP","JPY","CHF","AUD")))
        self.safe(r)
        self.assertEqual(r["currency_results"]["NZD"],"SAVED_BUT_REPLAY_DID_NOT_ACCEPT")
        self.assertEqual(r["state"],"LAB_FX28_FIVE_SOURCE_CAPTURE_PARTIAL_OR_BLOCKED_NO_GO")

    def test_10_bad_root_prevents_any_http(self):
        for bad in ("", ".", "relative"):
            with self.subTest(root=bad):
                r,calls=self.call(root=bad)
                self.safe(r)
                self.assertEqual(calls,0)
                self.assertEqual(r["https_gets_attempted_or_started"],0)
        # The helper uses None to mean "use the temp directory"; test a
        # genuinely missing LOCALAPPDATA with a direct invocation.
        with patch("atlasquant_trader_fx28_five_bank_capture_once_lab.replay") as spy:
            missing=run(capture_missing=True,local_appdata=None,
                        decision_clock=Clock(),steps=self.fake.build())
        self.safe(missing)
        spy.assert_not_called()
        self.assertEqual(missing["https_gets_attempted_or_started"],0)
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

    def test_19_stale_but_valid_source_is_not_skipped(self):
        before=archive(checked=("GBP","JPY"),
                       at="2026-11-11T15:50:00Z")
        after=archive(checked=_ORDER)
        report,_=self.call(before=before,after=after)
        self.safe(report)
        self.assertIn("GBP",report["previously_checked_but_stale_or_undated_codes"])
        self.assertIn("JPY",report["previously_checked_but_stale_or_undated_codes"])
        self.assertEqual(report["https_gets_attempted_or_started"],5)
        self.assertIn(("get","GBP"),self.fake.calls)
        self.assertIn(("get","JPY"),self.fake.calls)
        self.assertEqual(report["recent_local_capture_claim_count_after_run"],5)
        self.assertEqual(report["recent_two_source_pair_coverage_after_run"],10)

    def test_20_just_under_24h_can_skip_but_older_cannot(self):
        before=archive(checked=("GBP",),
                       at="2026-11-12T15:50:00Z")
        r,_=self.call(before=before)
        self.safe(r)
        self.assertEqual(r["currency_results"]["GBP"],
                         "SKIPPED_ALREADY_LOCALLY_CHECKED")
        self.assertNotIn(("get","GBP"),self.fake.calls)
        self.fake=FakeSteps()
        old=archive(checked=("GBP",),
                    at="2026-11-12T15:49:59Z")
        r,_=self.call(before=old)
        self.safe(r)
        self.assertIn(("get","GBP"),self.fake.calls)
        self.assertIn("GBP",r["previously_checked_but_stale_or_undated_codes"])

    def test_21_missing_local_capture_claim_is_not_fresh(self):
        before=archive(checked=("CHF",),undated=("CHF",))
        r,_=self.call(before=before)
        self.safe(r)
        self.assertIn(("get","CHF"),self.fake.calls)
        self.assertIn("CHF",r["previously_checked_but_stale_or_undated_codes"])

    def test_22_future_local_stamp_cannot_trigger_skip(self):
        before=archive(checked=("NZD",),
                       at="2026-11-13T16:00:00Z")
        r,_=self.call(before=before)
        self.safe(r)
        self.assertIn(("get","NZD"),self.fake.calls)
        self.assertEqual(r["https_gets_attempted_or_started"],5)

    def test_23_recent_counts_never_promote_stale_post_run_sources(self):
        before=archive(checked=_ORDER)
        after=archive(checked=_ORDER,
                      at="2026-11-10T15:50:00Z")
        r,_=self.call(before=before,after=after)
        self.safe(r)
        self.assertEqual(r["https_gets_attempted_or_started"],0)
        self.assertEqual(r["replayed_currency_count_after_run"],5)
        self.assertEqual(r["recent_local_capture_claim_count_after_run"],0)
        self.assertEqual(r["recent_two_source_pair_coverage_after_run"],0)
        self.assertEqual(r["state"],
                         "LAB_FX28_FIVE_SOURCE_CAPTURE_PARTIAL_OR_BLOCKED_NO_GO")
        self.assertEqual(r["reason"],
                         "LOCAL_CAPTURE_FRESHNESS_CLAIM_MISSING_OR_STALE")

    def test_24_partially_recent_after_replay_fails_completion(self):
        before=archive(checked=_ORDER)
        after=archive(checked=_ORDER,
                      undated=("AUD",))
        r,_=self.call(before=before,after=after)
        self.safe(r)
        self.assertEqual(r["recent_local_capture_claim_count_after_run"],4)
        self.assertEqual(r["recent_two_source_pair_coverage_after_run"],6)
        self.assertEqual(r["state"],
                         "LAB_FX28_FIVE_SOURCE_CAPTURE_PARTIAL_OR_BLOCKED_NO_GO")
        self.assertEqual(r["currency_results"]["AUD"],
                         "SKIPPED_ALREADY_LOCALLY_CHECKED")
        self.assertEqual(r["reason"],
                         "LOCAL_CAPTURE_FRESHNESS_CLAIM_MISSING_OR_STALE")

    def test_25_corrupt_capture_stamp_never_skips_or_falsifies_fresh(self):
        for bad in ("2026-02-30T15:50:00Z",
                    "2026-11-13T25:50:00Z",
                    "2026-11-13T15:50:00",
                    True,"future","2026-11-13T15:50:00+00:00"):
            with self.subTest(bad=bad):
                self.fake=FakeSteps()
                report,_=self.call(
                    before=archive(checked=("GBP",),at=bad))
                self.safe(report)
                self.assertIn(("get","GBP"),self.fake.calls)
                self.assertIn(
                    "GBP",report["previously_checked_but_stale_or_undated_codes"])

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


    def test_26_exact_http_403_code_no_retry_no_raw_message(self):
        self.fake=FakeSteps("CHF","http_403")
        r,_=self.call(after=archive(checked=("GBP","JPY","AUD","NZD")))
        self.safe(r)
        self.assertEqual(r["currency_results"]["CHF"],
                         "FETCH_VALIDATE_OR_SAVE_FAILED")
        self.assertEqual(r["failure_diagnostics_by_currency"]["CHF"],
                         "OFFICIAL_HTTP_STATUS_403")
        self.assertEqual([c for op,c in self.fake.calls if op=="get"].count("CHF"),1)
        self.assertNotIn(("saver","CHF"),self.fake.calls)

    def test_27_tls_or_url_error_not_misreported_as_disk_error(self):
        self.fake=FakeSteps("NZD","url_error")
        r,_=self.call(after=archive(checked=("GBP","JPY","CHF","AUD")))
        self.safe(r)
        self.assertEqual(r["failure_diagnostics_by_currency"]["NZD"],
                         "OFFICIAL_URL_TLS_OR_NETWORK_FAILURE")
        self.assertEqual([c for op,c in self.fake.calls if op=="get"].count("NZD"),1)

    def test_28_success_and_skips_are_local_only_diagnostics(self):
        r,_=self.call(before=archive(checked=("GBP",)),
                      after=archive(checked=_ORDER))
        self.safe(r)
        self.assertEqual(r["failure_diagnostics_by_currency"]["GBP"],
                         "RECENT_LOCAL_DOCUMENT_REUSED_NO_NEW_REQUEST")
        self.assertEqual(r["failure_diagnostics_by_currency"]["AUD"],
                         "LOCAL_REPLAY_PASSED_NOT_FIRST_SEEN_OR_ISSUER_PROOF")
        self.assertFalse(r["trade_authorized"])
        self.assertIsNone(r["calibrated_probability"])


if __name__ == "__main__":
    unittest.main()
