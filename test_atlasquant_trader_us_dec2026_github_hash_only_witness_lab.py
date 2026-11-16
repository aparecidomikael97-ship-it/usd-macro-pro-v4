"""Adversarial offline tests: private physical TD/TE mock files + GitHub REST.

These synthetic documents and mocked REST timestamps are NOT real December
consensus pages or a real GitHub pre-event witness.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import os
import unittest

import atlasquant_trader_us_dec2026_github_hash_only_witness_lab as m
from atlasquant_trader_us_dec2026_consensus_original_one_get_lab import (
    capture_dec2026_one_get_original_lab,
)

UTC = timezone.utc
CPI = "US_CPI_NOV2026"
PPI = "US_PPI_NOV2026"
TD = "TD_ECONOMICS"
TE = "TRADING_ECONOMICS"
CPI_START = datetime(2026, 12, 8, 15, 16, 17, 123456, tzinfo=UTC)
PPI_START = datetime(2026, 12, 11, 15, 16, 17, 123456, tzinfo=UTC)
TD_URL = ("https://economics.td.com/domains/economics.td.com/documents/"
          "reports/bottom-line/tables/2026-12-08/upcoming.htm")
TE_URL = "https://tradingeconomics.com/united-states/calendar"
ID = 7123456789


def fake_doc():
    return (b"<html><body>100 percent synthetic, NOT a real economic "
            b"consensus, not a TD or TE original, no numeric predictions. "
            + b"only SHA mock tests " * 12 + b"</body></html>")


class Response:
    def __init__(self, *, url, body, when, status=200, mime="text/html",
                 server_date=None):
        self.status = status
        self._url = url
        self.body = body
        self.headers = {
            "Content-Type": mime,
            "Date": server_date or format_datetime(
                when.replace(microsecond=0), usegmt=True),
            "Content-Encoding": "identity",
            "Content-Length": str(len(body)),
        }

    def geturl(self):
        return self._url

    def read(self, count):
        return self.body[:count]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Once:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def __call__(self, req, *, timeout):
        self.calls += 1
        assert self.calls == 1, "NO_RETRY"
        assert req.get_method() == "GET"
        assert timeout in (12, 15)
        return self.response


def ticks(start, duration=1):
    seq = iter((start, start + timedelta(seconds=duration)))
    return lambda: next(seq)


class DecemberGithubWitnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self._build()

    def tearDown(self):
        self.tmp.cleanup()

    def _build(self, *, event=CPI, provider=TD, start=CPI_START):
        url = TD_URL if provider == TD else TE_URL
        http = Once(Response(url=url, body=fake_doc(), when=start))
        result = capture_dec2026_one_get_original_lab(
            allow_one_official_get=True,
            confirm_bls_schedule_reviewed=True,
            event_root=event, provider=provider, source_url=url,
            output_root=self.root, open_url=http, clock=ticks(start),
        )
        assert result["original_replayed_from_disk"], result
        self.archive = result["archive_basename"]
        self.event = event
        self.capture_end = start + timedelta(seconds=1)
        self.observed = start + timedelta(minutes=2)
        self.comment_create = start.replace(microsecond=0) + timedelta(minutes=1)

    def prepared(self, *, at=None):
        return m.prepare_dec2026_source_hash_only_commitment_lab(
            archive_root=self.root, archive_basename=self.archive,
            research_cutoff_utc=at or self.observed,
        )

    def entry(self, **overrides):
        p = self.prepared()
        entry = {
            "id": ID,
            "url": f"{m.API_ROOT}/issues/comments/{ID}",
            "html_url": f"https://github.com/{m.REPO}/issues/{m.ISSUE_NUMBER}#issuecomment-{ID}",
            "issue_url": f"{m.API_ROOT}/issues/{m.ISSUE_NUMBER}",
            "created_at": self.comment_create.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "updated_at": self.comment_create.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "body": p["proposed_comment_body_hash_only"],
            "user": {"login": "aparecidomikael97-ship-it"},
        }
        entry.update(overrides)
        return entry

    def raw(self, **overrides):
        return json.dumps(self.entry(**overrides),sort_keys=True).encode()

    def inspect(self, *, raw=None, at=None, comment_id=ID):
        return m.inspect_dec2026_hash_only_github_response_lab(
            archive_root=self.root, archive_basename=self.archive,
            raw_github_comment_json=self.raw() if raw is None else raw,
            observed_at_utc=self.observed if at is None else at,
            expected_comment_id=comment_id,
        )

    def safe(self, result):
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["publishable"])
        self.assertEqual(result["registered_forecasts"], 0)
        self.assertIsNone(result["out_of_sample_accuracy"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertIsNone(result["usd_bias"])
        self.assertFalse(result["economic_consensus_eligible_for_fx_prediction"])
        self.assertFalse(result["publisher_first_seen_independently_authenticated"])
        self.assertFalse(result["consensus_numeric_semantics_authenticated"])
        self.assertFalse(result["original_fx28_672_slots_modified"])
        self.assertEqual(result["file_writes"], 0)
        self.assertEqual(result["operational_bias"], "AGUARDAR")

    def test_01_prepares_only_canonical_hash_body_from_physical_archive(self):
        p = self.prepared()
        self.safe(p)
        self.assertTrue(p["original_and_receipt_local_replay_accepted"])
        self.assertTrue(p["public_hash_only_body_ready"])
        self.assertEqual(len(p["proposed_comment_body_hash_only"].splitlines()), 10)
        self.assertIn("source_html_sha256=", p["proposed_comment_body_hash_only"])
        self.assertIn("source_receipt_sha256=", p["proposed_comment_body_hash_only"])
        self.assertNotIn("synthetic", p["proposed_comment_body_hash_only"])
        self.assertNotIn("99.9", p["proposed_comment_body_hash_only"])
        self.assertFalse(p["exact_hash_only_github_comment_locally_reconciled"])

    def test_02_private_files_not_written_or_posted_by_preparer(self):
        folder = self.root/self.archive
        before = sorted((n.name, sha256(n.read_bytes()).hexdigest())
                        for n in folder.iterdir())
        self.prepared()
        self.assertEqual(before, sorted((n.name, sha256(n.read_bytes()).hexdigest())
                                        for n in folder.iterdir()))

    def test_03_synthetic_caller_supplied_rest_claim_match_is_not_immutable_proof(self):
        result = self.inspect()
        self.safe(result)
        self.assertTrue(result["exact_hash_only_github_comment_locally_reconciled"])
        self.assertFalse(result["github_live_200_pre_freeze_observed"])
        self.assertIn("CLAIM_ONLY", result["state"])

    def test_04_source_html_tampered_blocks(self):
        path = self.root/self.archive/"original.html"
        path.write_bytes(path.read_bytes() + b"x")
        result = self.prepared()
        self.safe(result)
        self.assertFalse(result["public_hash_only_body_ready"])
        self.assertFalse(self.inspect()["exact_hash_only_github_comment_locally_reconciled"])

    def test_05_source_receipt_tampered_blocks(self):
        path = self.root/self.archive/"receipt.json"
        path.write_bytes(path.read_bytes() + b"x")
        self.assertFalse(self.prepared()["public_hash_only_body_ready"])

    def test_06_no_original_private_folder_blocks(self):
        result = m.prepare_dec2026_source_hash_only_commitment_lab(
            archive_root=self.root, archive_basename="no-such-folder",
            research_cutoff_utc=self.observed,
        )
        self.safe(result)
        self.assertFalse(result["public_hash_only_body_ready"])

    def test_07_future_private_original_not_readable_at_past_cutoff(self):
        self.assertFalse(self.prepared(at=self.capture_end-timedelta(microseconds=1))[
            "public_hash_only_body_ready"])

    def test_08_edited_comment_rejected(self):
        created = self.entry()["created_at"]
        later = (self.comment_create + timedelta(seconds=1)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        self.assertNotEqual(created,later)
        self.assertFalse(self.inspect(raw=self.raw(updated_at=later))[
            "exact_hash_only_github_comment_locally_reconciled"])

    def test_09_wrong_source_digest_in_body_rejected(self):
        p = self.prepared()
        wrong = p["proposed_comment_body_hash_only"].replace(
            p["source_html_sha256"], "1"*64)
        self.assertFalse(self.inspect(raw=self.raw(body=wrong))[
            "exact_hash_only_github_comment_locally_reconciled"])

    def test_10_wrong_receipt_digest_in_body_rejected(self):
        p = self.prepared()
        wrong = p["proposed_comment_body_hash_only"].replace(
            p["source_receipt_sha256"], "2"*64)
        self.assertFalse(self.inspect(raw=self.raw(body=wrong))[
            "exact_hash_only_github_comment_locally_reconciled"])

    def test_11_wrong_event_or_provider_in_body_rejected(self):
        for value in ("US_PPI_NOV2026", "TRADING_ECONOMICS"):
            changed = self.prepared()["proposed_comment_body_hash_only"].replace(
                CPI if value.startswith("US_") else TD, value)
            self.assertFalse(self.inspect(raw=self.raw(body=changed))[
                "exact_hash_only_github_comment_locally_reconciled"])

    def test_12_foreign_issue_or_comment_id_rejected(self):
        original = self.entry()
        for entry in (
            self.entry(issue_url=f"{m.API_ROOT}/issues/1884"),
            self.entry(html_url="https://github.com/other/invalid"),
            self.entry(id=ID+1),
        ):
            self.assertNotEqual(entry, original)
            self.assertFalse(self.inspect(raw=json.dumps(entry).encode())[
                "exact_hash_only_github_comment_locally_reconciled"])

    def test_13_foreign_author_rejected(self):
        self.assertFalse(self.inspect(raw=self.raw(user={"login":"attacker"}))[
            "exact_hash_only_github_comment_locally_reconciled"])

    def test_14_server_created_before_private_capture_rejected(self):
        earlier = (self.capture_end - timedelta(seconds=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertFalse(self.inspect(raw=self.raw(created_at=earlier,updated_at=earlier))[
            "exact_hash_only_github_comment_locally_reconciled"])

    def test_15_server_created_same_second_as_microsecond_receipt_rejected(self):
        same = self.capture_end.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertFalse(self.inspect(raw=self.raw(created_at=same,updated_at=same))[
            "exact_hash_only_github_comment_locally_reconciled"])

    def test_16_created_after_observation_rejected(self):
        future = (self.observed + timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertFalse(self.inspect(raw=self.raw(created_at=future,updated_at=future))[
            "exact_hash_only_github_comment_locally_reconciled"])

    def test_17_research_observation_at_freeze_rejected(self):
        freeze = datetime(2026,12,10,12,30,tzinfo=UTC)
        self.assertFalse(self.inspect(at=freeze)[
            "exact_hash_only_github_comment_locally_reconciled"])

    def test_18_commit_created_at_freeze_rejected(self):
        time = datetime(2026,12,10,12,30,tzinfo=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertFalse(self.inspect(raw=self.raw(created_at=time,updated_at=time))[
            "exact_hash_only_github_comment_locally_reconciled"])

    def test_19_duplicate_json_keys_rejected(self):
        raw = self.raw().rstrip(b"}") + b',"id":1}'
        self.assertFalse(self.inspect(raw=raw)[
            "exact_hash_only_github_comment_locally_reconciled"])

    def test_20_malformed_json_or_id_rejected(self):
        for raw in (b"{}", b"\xff"*150, b"["*150, self.raw()):
            out = self.inspect(raw=raw,comment_id=ID if raw!=self.raw() else 0)
            self.safe(out)
            self.assertFalse(out["exact_hash_only_github_comment_locally_reconciled"])

    def test_21_no_explicit_http_permission_has_zero_requests(self):
        opener = Once(Response(
            url=f"{m.API_ROOT}/issues/comments/{ID}",body=self.raw(),
            when=self.observed))
        out = m.read_once_and_check_dec2026_github_hash_witness_lab(
            allow_explicit_read_only_get=False,
            expected_comment_id=ID,
            archive_root=self.root,archive_basename=self.archive,
            request_open=opener,clock=ticks(self.observed),
        )
        self.safe(out)
        self.assertEqual(opener.calls,0)
        self.assertEqual(out["github_rest_gets_attempted"],0)

    def http(self, *, status=200,url=None,mime="application/json",
             when=None,date=None,body=None,clock_start=None,clock_end=None):
        start=self.observed if clock_start is None else clock_start
        end=start+timedelta(seconds=1) if clock_end is None else clock_end
        response=Response(
            url=url or f"{m.API_ROOT}/issues/comments/{ID}",
            body=self.raw() if body is None else body,
            when=start if when is None else when,
            status=status,mime=mime,server_date=date)
        opener=Once(response)
        out=m.read_once_and_check_dec2026_github_hash_witness_lab(
            allow_explicit_read_only_get=True,
            expected_comment_id=ID,
            archive_root=self.root,archive_basename=self.archive,
            request_open=opener,clock=ticks(start,(end-start).total_seconds()),
        )
        return out,opener

    def test_22_mock_https_valid_metadata_is_not_publisher_first_seen(self):
        out, opener=self.http()
        self.safe(out)
        self.assertEqual(opener.calls,1)
        self.assertTrue(out["github_live_200_pre_freeze_observed"])
        self.assertTrue(out["exact_hash_only_github_comment_locally_reconciled"])

    def test_23_mock_https_403_and_301_fail_closed(self):
        for status in (403, 301):
            out,_=self.http(status=status)
            self.safe(out)
            self.assertFalse(out["github_live_200_pre_freeze_observed"])

    def test_24_mock_https_wrong_url_or_mime_fail(self):
        for option in ({"url":"https://api.github.com/other"},
                       {"mime":"text/html"}):
            out,_=self.http(**option)
            self.assertFalse(out["github_live_200_pre_freeze_observed"])

    def test_25_mock_https_http_date_far_outside_clock_fails(self):
        date=format_datetime(self.observed-timedelta(days=3),usegmt=True)
        out,_=self.http(date=date)
        self.assertFalse(out["github_live_200_pre_freeze_observed"])

    def test_26_frozen_read_preflight_zero_requests(self):
        freeze=datetime(2026,12,10,12,30,tzinfo=UTC)
        out,opener=self.http(clock_start=freeze,clock_end=freeze)
        self.safe(out)
        self.assertEqual(opener.calls,0)

    def test_27_http_crossing_freeze_fails(self):
        freeze=datetime(2026,12,10,12,30,tzinfo=UTC)
        out,opener=self.http(
            clock_start=freeze-timedelta(seconds=1),
            clock_end=freeze+timedelta(seconds=1))
        self.assertEqual(opener.calls,1)
        self.assertFalse(out["github_live_200_pre_freeze_observed"])

    def test_28_invalid_token_blocks_before_network(self):
        opener=Once(Response(
            url=f"{m.API_ROOT}/issues/comments/{ID}",body=self.raw(),
            when=self.observed))
        with patch.dict(os.environ,{"GITHUB_TOKEN":"x\nheader"}):
            out=m.read_once_and_check_dec2026_github_hash_witness_lab(
                allow_explicit_read_only_get=True,expected_comment_id=ID,
                archive_root=self.root,archive_basename=self.archive,
                request_open=opener,clock=ticks(self.observed),
            )
        self.safe(out)
        self.assertEqual(opener.calls,0)

    def test_29_ppi_uses_own_december_15_freeze(self):
        self._build(event=PPI,provider=TE,start=PPI_START)
        p=self.prepared()
        self.assertEqual(p["freeze_deadline_utc"],"2026-12-15T12:30:00+00:00")
        self.assertTrue(p["public_hash_only_body_ready"])
        self.assertTrue(self.inspect()["exact_hash_only_github_comment_locally_reconciled"])
        self.assertFalse(self.inspect(
            at=datetime(2026,12,15,12,30,tzinfo=UTC)
        )["exact_hash_only_github_comment_locally_reconciled"])

    def test_30_provider_body_relabelled_as_fx_forecast_is_impossible(self):
        out=self.inspect()
        self.safe(out)
        self.assertNotIn("win_rate",out)
        self.assertNotIn("forex_signal",out)
        self.assertNotIn("order_send",out)


if __name__ == "__main__":
    unittest.main()
