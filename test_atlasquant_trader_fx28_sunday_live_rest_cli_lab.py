"""Offline tests for a *real executable* CLI; no GitHub network in tests."""
from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
import unittest

from atlasquant_trader_fx28_github_rest_comment_inventory_lab import (
    inspect_github_rest_comment_pages_lab as parse_rest,
)
from atlasquant_trader_fx28_sunday_rest_source_bridge_lab import main
from test_atlasquant_trader_fx28_github_rest_comment_inventory_lab import (
    fixture_comment, pages, witness,
)

UTC = timezone.utc
PREFLIGHT = datetime(2026, 11, 15, 10, tzinfo=UTC)
FIRST_OPEN = datetime(2026, 11, 15, 22, tzinfo=UTC)


def run(argv,reader,now=PREFLIGHT):
    buf=StringIO()
    with redirect_stdout(buf):
        code=main(argv,get_inventory=reader,observed_clock=lambda:now)
    output=buf.getvalue().strip().splitlines()
    return code, json.loads(output[-1]) if output[-1].startswith("{") else output[-1]


def clean_rest(now=PREFLIGHT):
    report = parse_rest(
        raw_pages=pages(fixture_comment(
            body="Narrative comment only. Never a precommit.",
            created="2026-11-14T13:00:00Z",
            updated="2026-11-14T13:00:00Z")),
        observed_at_utc=now)
    report["http_requests_started"] = 1  # synthetic injected REST reader
    return report


class SundayLiveReadonlyCliTests(unittest.TestCase):
    def test_01_no_flag_never_reads_github(self):
        called=[]
        def fake(**kw):
            called.append(kw)
            raise AssertionError("network happened without explicit flag")
        ret,out=run([],fake)
        self.assertEqual(ret,2)
        self.assertFalse(out["github_comments_observed"])
        self.assertEqual(out["network_requests"],0)
        self.assertEqual(called,[])

    def test_02_explicit_read_one_reader_no_am12_no_witness(self):
        inv=clean_rest()
        inv["http_requests_started"]=1
        called=[]
        def fake(**kwargs):
            called.append(kwargs)
            return inv
        ret,out=run(["--read-public-github"],fake)
        self.assertEqual(ret,0)
        self.assertEqual(called,[{"inspect_public_github":True}])
        self.assertEqual(out["github_rest_gets_attempted_claim"],1)
        self.assertEqual(out["http_requests"],1)
        self.assertEqual(out["http_requests_provenance"],
             "GITHUB_REST_COLLECTOR_ATTEMPTED_GETS_NOT_NETWORK_INDEPENDENT_ATTESTATION")
        self.assertEqual(out["rest_comment_count_observed_claim"],1)
        self.assertEqual(out["rest_exact_headers_observed_claim"],0)
        self.assertEqual(out["ledger_slots_accounted"],672)
        self.assertEqual(out["first_56_slots_due_now"],0)
        self.assertEqual(out["first_56_slots_not_yet_due"],56)
        self.assertEqual(out["local_documentation_status"],
                         "UNKNOWN_NO_CURRENT_AM12_SOURCE_REPORT")
        self.assertFalse(out["am12_directly_contacted"])
        self.assertFalse(out["raw_issue_comment_bodies_disclosed"])
        self.assertEqual(out["operational_bias"],"AGUARDAR")
        self.assertFalse(out["trade_authorized"])
        self.assertNotIn("Narrative comment only",json.dumps(out))

    def test_03_even_an_exact_sha_header_does_not_become_forecast(self):
        at=PREFLIGHT+timedelta(minutes=1)
        inv=parse_rest(
            raw_pages=pages(fixture_comment(
                body=witness(horizon="D1"),
                created="2026-11-15T10:00:00Z",
                updated="2026-11-15T10:00:00Z")),
            observed_at_utc=at)
        inv["http_requests_started"]=1
        ret,out=run(["--read-public-github"],
                    lambda **kwargs:inv,now=at)
        self.assertEqual(ret,0)
        self.assertEqual(out["rest_first_window_candidate_count_claim"],1)
        self.assertFalse(out["rest_candidate_roster_bytes_authenticated"])
        self.assertFalse(out["all_56_first_window_forecasts_authenticated"])
        self.assertEqual(out["first_56_slots_due_now"],0)

    def test_04_http_error_return_fail_closed_not_zero_witness(self):
        def fake(**kw):
            raise OSError("failed to fetch")
        ret,out=run(["--read-public-github"],fake)
        self.assertEqual(ret,2)
        self.assertEqual(out["state"],
                         "LAB_SUNDAY_FX28_PUBLIC_REST_READ_EXCEPTION_NO_GO")
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["rest_witnesses_independently_attested"])

    def test_05_invalid_rest_snapshot_blocked_without_missing_forecast_claim(self):
        ret,out=run(["--read-public-github"],
                    lambda **kw:{"state":"FAILED"})
        self.assertEqual(ret,2)
        self.assertIn("BLOCKED",out["state"])
        self.assertIsNone(out["rest_comment_count_observed_claim"])
        self.assertTrue(out["no_supplied_witness_never_proves_github_absence"])
        self.assertEqual(out["ledger_slots_accounted"],672)

    def test_06_snapshot_more_than_ten_minutes_old_fails_closed(self):
        inv=clean_rest()
        ret,out=run(["--read-public-github"],lambda **kw:inv,
                    now=PREFLIGHT+timedelta(minutes=11))
        self.assertEqual(ret,2)
        self.assertEqual(
            out["reason"],"GITHUB_REST_REPORT_OBSERVATION_CLOCK_MISSING_OR_STALE")

    def test_07_explicit_only_before_06_no_prewindow_abstain_claim(self):
        at=PREFLIGHT-timedelta(seconds=1)
        inv=clean_rest(at)
        ret,out=run(["--read-public-github"],lambda **kw:inv,now=at)
        self.assertEqual(ret,0)
        self.assertEqual(out["first_window_phase"],
                         "NOT_ELIGIBLE_BEFORE_FIRST_12H")
        self.assertEqual(out["ledger_past_no_supplied_witness"],0)

    def test_08_explicit_on_open_18_is_not_early_witness(self):
        inv=clean_rest(FIRST_OPEN)
        ret,out=run(["--read-public-github"],lambda **kw:inv,now=FIRST_OPEN)
        self.assertEqual(ret,0)
        self.assertEqual(out["first_56_slots_due_now"],56)
        self.assertEqual(out["ledger_past_no_supplied_witness"],56)
        self.assertFalse(out["all_56_first_window_forecasts_authenticated"])
        self.assertTrue(out["no_supplied_witness_never_proves_github_absence"])

    def test_09_bad_callable_rejected_before_http(self):
        code,_=run(["--read-public-github"],None)
        self.assertEqual(code,2)

    def test_10_naive_inspection_clock_blocked(self):
        inv=clean_rest()
        ret,out=run(["--read-public-github"],lambda **kw:inv,
                    now=PREFLIGHT.replace(tzinfo=None))
        self.assertEqual(ret,2)
        self.assertEqual(out["state"],
                         "LAB_SUNDAY_FX28_CROSS_SOURCE_PREFLIGHT_BLOCKED_NO_GO")

    def test_11_zero_or_forged_rest_request_count_never_success(self):
        for invalid in (None, 0, -1, 6, True, "1"):
            with self.subTest(value=invalid):
                inv=clean_rest()
                inv["http_requests_started"]=invalid
                ret,out=run(["--read-public-github"],lambda **kw:inv)
                self.assertEqual(ret,2)
                self.assertEqual(
                    out["state"],"LAB_SUNDAY_FX28_GITHUB_HTTP_COUNT_INVALID_NO_GO")
                self.assertIsNone(out["http_requests"])
                self.assertEqual(out["reason"],
                    "REST_READER_REQUEST_COUNT_MISSING_ZERO_OR_UNBOUNDED")
                self.assertFalse(out["trade_authorized"])

    def test_12_two_pages_are_counted_without_exaggerating_source_validity(self):
        inv=clean_rest()
        inv["http_requests_started"]=2
        ret,out=run(["--read-public-github"],lambda **kw:inv)
        self.assertEqual(ret,0)
        self.assertEqual(out["http_requests"],2)
        self.assertEqual(out["github_rest_gets_attempted_claim"],2)
        self.assertFalse(out["all_56_first_window_forecasts_authenticated"])

    def test_13_reader_never_writes_or_orders_even_if_comments_count_positive(self):
        inv=clean_rest()
        inv["comments_reconciled"]=1
        ret,out=run(["--read-public-github"],lambda **kw:inv)
        self.assertEqual(ret,0)
        self.assertEqual(out["file_writes"],0)
        self.assertFalse(out["worker_enabled"])
        self.assertFalse(out["scheduler_enabled"])
        self.assertFalse(out["live_alert_allowed"])
        self.assertFalse(out["publishable"])


if __name__=="__main__":
    unittest.main()
