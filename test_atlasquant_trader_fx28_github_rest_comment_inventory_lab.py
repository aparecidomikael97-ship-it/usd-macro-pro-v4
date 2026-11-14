"""Adversarial synthetic GitHub REST responses, no external network."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
import unittest
from unittest.mock import patch

from atlasquant_trader_fx28_ny17_forecast_witness_lab import HEADER
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    CAMPAIGN_ID, _nominal_windows,
)
from atlasquant_trader_fx28_github_rest_comment_inventory_lab import (
    ENDPOINT, MAX_PAGE_BYTES, PAGE_SIZE,
    inspect_github_rest_comment_pages_lab as inspect,
    collect_public_github_issue_snapshot_once_lab as collect,
    main,
)

UTC=timezone.utc
BEFORE=datetime(2026,11,15,11,0,tzinfo=UTC)
FIRST=datetime(2026,11,15,22,0,tzinfo=UTC)


def fixture_comment(comment_id=5001, *, body="Normal checkpoint, no witness.",
                    created="2026-11-15T10:30:00Z",
                    updated="2026-11-15T10:30:00Z"):
    return {
        "id":comment_id,"body":body,
        "url":("https://api.github.com/repos/"
               "aparecidomikael97-ship-it/usd-macro-pro-v4/"
               f"issues/comments/{comment_id}"),
        "issue_url":("https://api.github.com/repos/"
                     "aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1884"),
        "html_url":("https://github.com/"
                    "aparecidomikael97-ship-it/usd-macro-pro-v4/"
                    f"issues/1884#issuecomment-{comment_id}"),
        "created_at":created,"updated_at":updated,
    }


def witness(*, horizon="D1", start=None, digest="a"*64):
    if start is None:
        start, end=_nominal_windows(horizon)[0]
    else:
        end=next(e for s,e in _nominal_windows(horizon) if s==start)
    return "\n".join((
        HEADER, "campaign_id="+CAMPAIGN_ID,
        "horizon="+horizon, "start_utc="+start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_utc="+end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pairs=28", "roster_sha256="+digest,
        "research_only=true", "trade_authorized=false",
    ))


def pages(*items):
    return (json.dumps(list(items),sort_keys=True).encode("utf-8"),)


class FakeReply:
    def __init__(self, body, url, *, status=200, media="application/json"):
        self.data=BytesIO(body)
        self.url=url
        self.status=status
        self.headers={"Content-Type":media+"; charset=utf-8"}
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.data.close()
    def geturl(self):
        return self.url
    def read(self,n=-1):
        return self.data.read(n)


class GitHubRawCommentInventoryTests(unittest.TestCase):
    def audit(self, raw=None, now=BEFORE):
        return inspect(
            raw_pages=raw if raw is not None else pages(fixture_comment()),
            observed_at_utc=now)

    def safe(self,r):
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        for x in ("trade_authorized","publishable","live_alert_allowed",
                  "worker_enabled","scheduler_enabled",
                  "canonical_28_pair_roster_bytes_reconciled",
                  "publisher_and_first_seen_cryptographically_attested",
                  "issue_comments_absent_outside_this_source_proven"):
            self.assertFalse(r[x],x)
        self.assertTrue(r["comment_timestamps_are_rest_api_fields_not_immutable_witness"])
        self.assertTrue(r["pre_event_observation_is_required_for_a_real_witness"])
        self.assertEqual(r["independently_authenticated_forecasts"],0)
        self.assertIsNone(r["validated_accuracy"])
        self.assertIsNone(r["calibrated_direction_probability"])
        self.assertEqual((r["file_writes"],r["new_cost_brl"]),(0,0))

    def complete(self,r):
        self.safe(r)
        self.assertEqual(r["state"],
            "LAB_GITHUB_REST_COMMENT_INVENTORY_COMPLETE_METADATA_ONLY_NO_GO")

    def test_01_single_official_comment_no_witness(self):
        r=self.audit()
        self.complete(r)
        self.assertEqual(r["comments_reconciled"],1)
        self.assertEqual(r["pages_reconciled"],1)
        self.assertEqual(r["exact_witness_headers_found"],0)
        self.assertEqual(r["candidate_witness_metadata"],[])

    def test_02_empty_page_not_proof_anywhere_else(self):
        r=self.audit(raw=pages())
        self.complete(r)
        self.assertEqual(r["comments_reconciled"],0)
        self.assertFalse(r["issue_comments_absent_outside_this_source_proven"])

    def test_03_exact_hash_only_commitment_before_window_remains_unverified(self):
        body=witness()
        r=self.audit(raw=pages(fixture_comment(body=body)))
        self.complete(r)
        self.assertEqual(r["exact_witness_headers_found"],1)
        self.assertEqual(r["structural_prewindow_metadata_candidates"],1)
        info=r["candidate_witness_metadata"][0]
        self.assertEqual(info["horizon"],"D1")
        self.assertEqual(info["start_utc"],FIRST.isoformat())
        self.assertEqual(info["roster_sha256_unverified_against_forecast_bytes"],
                         "a"*64)
        self.assertEqual(info["comment_body_sha256_local"],
                         sha256(body.encode()).hexdigest())
        self.assertTrue(info["not_independently_verified_forecast"])

    def test_04_post_window_read_of_old_comment_not_a_prewindow_observation(self):
        body=witness()
        r=self.audit(raw=pages(fixture_comment(body=body)),
                     now=FIRST+timedelta(seconds=1))
        self.complete(r)
        self.assertEqual(r["late_or_post_window_observed_candidates"],1)
        self.assertEqual(r["structural_prewindow_metadata_candidates"],0)
        self.assertIn(
            "OBSERVED_ONLY_AFTER_WINDOW_START_NOT_PRECOMMIT_PROOF",
            r["rejected_candidate_reason_codes"])

    def test_05_prewindow_creation_too_early_or_exact_open_block(self):
        body=witness()
        for created in ("2026-11-15T09:59:59Z",
                        "2026-11-15T22:00:00Z"):
            with self.subTest(created=created):
                rec=fixture_comment(body=body,created=created,updated=created)
                r=self.audit(raw=pages(rec),
                             now=FIRST+timedelta(seconds=1))
                self.complete(r)
                self.assertEqual(r["structural_prewindow_metadata_candidates"],0)
                self.assertIn("COMMENT_CREATED_OUTSIDE_12H_OR_EDITED",
                              r["rejected_candidate_reason_codes"])

    def test_06_edited_after_creation_must_not_count_as_prewindow(self):
        body=witness()
        rec=fixture_comment(body=body,
            updated="2026-11-15T10:45:00Z")
        r=self.audit(raw=pages(rec))
        self.complete(r)
        self.assertEqual(r["structural_prewindow_metadata_candidates"],0)
        self.assertIn("COMMENT_CREATED_OUTSIDE_12H_OR_EDITED",
                      r["rejected_candidate_reason_codes"])

    def test_07_malformed_witness_body_and_spurious_mention_not_eligible(self):
        for body in (witness().replace("pairs=28","pairs=27"),
                     witness().replace("roster_sha256="+"a"*64,
                                        "roster_sha256="+"0"*64),
                     witness()+"\nextra=true",
                     witness().replace("trade_authorized=false",
                                        "trade_authorized=true")):
            with self.subTest(body=body):
                r=self.audit(raw=pages(fixture_comment(body=body)))
                self.complete(r)
                self.assertEqual(r["exact_witness_headers_found"],1)
                self.assertEqual(r["structural_prewindow_metadata_candidates"],0)
        r=self.audit(raw=pages(fixture_comment(
            body="Some notes mentioning "+HEADER)))
        self.complete(r)
        self.assertEqual(r["exact_witness_headers_found"],0)

    def test_08_duplicate_id_or_comment_order_rejected(self):
        records=(fixture_comment(5001),fixture_comment(5001))
        r=self.audit(raw=pages(*records))
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_GITHUB_REST_COMMENT_INVENTORY_BLOCKED_NO_GO")
        records=(fixture_comment(5002),fixture_comment(5001))
        r=self.audit(raw=pages(*records))
        self.safe(r)
        self.assertEqual(r["reason"],"GITHUB_COMMENT_METADATA_MALFORMED")

    def test_09_fake_domain_issue_number_and_modified_api_urls_blocked(self):
        for key,value in (
            ("url","https://api.github.com.evil.example/comment"),
            ("html_url","https://github.com/other/issues/1884#issuecomment-5001"),
            ("issue_url","https://api.github.com/repos/foo/bar/issues/1884"),
            ("created_at","2026-11-17T10:30:00Z"),
            ("updated_at","not-a-timestamp"),
            ("id",True),
        ):
            with self.subTest(key=key):
                rec=fixture_comment()
                rec[key]=value
                r=self.audit(raw=pages(rec))
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_GITHUB_REST_COMMENT_INVENTORY_BLOCKED_NO_GO")

    def test_10_bad_json_duplicate_keys_nan_and_nonlist_block(self):
        for raw in (b'{"fake":"json"}',b'[{"id":1,"id":2}]',
                    b'NaN',b'[] trailing',
                    b'[null]',b'x'*(MAX_PAGE_BYTES+1)):
            with self.subTest(rawprefix=raw[:20]):
                r=self.audit(raw=(raw,))
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_GITHUB_REST_COMMENT_INVENTORY_BLOCKED_NO_GO")

    def test_11_partial_middle_page_or_missing_trailing_page_blocked(self):
        r=self.audit(raw=(pages()[0],pages()[0]))
        self.safe(r)
        self.assertEqual(r["reason"],
                         "INCOMPLETE_OR_EXCESS_GITHUB_COMMENT_PAGINATION")
        full=pages(*[fixture_comment(5000+i) for i in range(PAGE_SIZE)])
        r=self.audit(raw=full)
        self.safe(r)
        self.assertEqual(r["reason"],
                         "INCOMPLETE_OR_EXCESS_GITHUB_COMMENT_PAGINATION")

    def test_12_invalid_local_observation_clock_blocked(self):
        for now in (None,"2026-11-15T11:00:00Z",
                    BEFORE.replace(tzinfo=None),
                    BEFORE+timedelta(microseconds=1)):
            with self.subTest(now=now):
                r=self.audit(now=now)
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_GITHUB_REST_COMMENT_INVENTORY_BLOCKED_NO_GO")

    def test_13_one_bounded_request_and_no_comment_body_printed(self):
        calls=[]
        def opener(req,*,timeout):
            calls.append((req.full_url,req.get_method(),timeout))
            return FakeReply(pages(fixture_comment())[0],req.full_url)
        r=collect(inspect_public_github=True,request_open=opener,
                  observed_clock=lambda: BEFORE)
        self.complete(r)
        self.assertEqual(r["http_requests_started"],1)
        self.assertEqual(calls,[(ENDPOINT+"?per_page=100&page=1","GET",12)])
        self.assertNotIn("Normal checkpoint",json.dumps(r))

    def test_14_two_pages_complete_and_second_request_exact(self):
        calls=[]
        def opener(req,*,timeout):
            calls.append(req.full_url)
            if len(calls)==1:
                raw=pages(*[fixture_comment(5000+i)
                            for i in range(PAGE_SIZE)])[0]
            else:
                raw=pages(fixture_comment(5101))[0]
            return FakeReply(raw,req.full_url)
        r=collect(inspect_public_github=True,request_open=opener,
                  observed_clock=lambda: BEFORE)
        self.complete(r)
        self.assertEqual(r["pages_reconciled"],2)
        self.assertEqual(r["comments_reconciled"],101)
        self.assertEqual(r["http_requests_started"],2)
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[1],ENDPOINT+"?per_page=100&page=2")

    def test_15_http_redirect_nonjson_bad_status_or_oversize_fail(self):
        for config in (
            {"status":301},{"media":"text/html"},
            {"redirect":"https://api.github.com.evil.test/"},
            {"body":b"x"*(MAX_PAGE_BYTES+1)},
        ):
            with self.subTest(config=list(config)):
                def opener(req,*,timeout):
                    return FakeReply(
                        config.get("body",b"[]"),
                        config.get("redirect",req.full_url),
                        status=config.get("status",200),
                        media=config.get("media","application/json"))
                r=collect(inspect_public_github=True,request_open=opener,
                          observed_clock=lambda: BEFORE)
                self.safe(r)
                self.assertEqual(
                    r["state"],"LAB_GITHUB_REST_COMMENT_INVENTORY_BLOCKED_NO_GO")

    def test_16_explicit_flag_required_no_automatic_calls(self):
        with patch(
            "atlasquant_trader_fx28_github_rest_comment_inventory_lab.urlopen"
        ) as opening:
            r=collect(inspect_public_github=False,request_open=opening)
        self.safe(r)
        self.assertEqual(r["http_requests_started"],0)
        opening.assert_not_called()

    def test_17_default_cli_no_http_and_nonzero_exit_not_trading_success(self):
        with patch(
            "atlasquant_trader_fx28_github_rest_comment_inventory_lab.urlopen"
        ) as opening:
            self.assertEqual(main([]),2)
            opening.assert_not_called()

    def test_18_future_claim_does_not_become_first_seen_authority(self):
        r=self.audit(raw=pages(fixture_comment(body=witness())))
        self.complete(r)
        self.assertEqual(r["structural_prewindow_metadata_candidates"],1)
        self.assertFalse(r["canonical_28_pair_roster_bytes_reconciled"])
        self.assertFalse(r["publisher_and_first_seen_cryptographically_attested"])
        self.assertEqual(r["independently_authenticated_forecasts"],0)


    def test_19_preexisting_readonly_token_never_printed_in_public_report(self):
        secret="synthetic-token-NEVER-DISPLAY"
        calls=[]
        def opener(req,*,timeout):
            calls.append(req.get_header("Authorization"))
            return FakeReply(b"[]",req.full_url)
        with patch.dict(os.environ,{"GITHUB_TOKEN":secret}):
            r=collect(inspect_public_github=True,request_open=opener,
                      observed_clock=lambda:BEFORE)
        self.complete(r)
        self.assertEqual(calls,["Bearer "+secret])
        self.assertNotIn(secret,json.dumps(r))
        self.assertEqual(r["http_requests_started"],1)

    def test_20_bad_token_with_crlf_fails_before_request(self):
        for bad in ("line\\nInjected: header","line\\rInjected: header","X"*2049):
            with self.subTest(length=len(bad)):
                opened=[]
                def opener(req,*,timeout):
                    opened.append(req.full_url)
                    raise AssertionError("Should not call")
                with patch.dict(os.environ,{"GITHUB_TOKEN":bad}):
                    r=collect(inspect_public_github=True,request_open=opener,
                              observed_clock=lambda:BEFORE)
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_GITHUB_REST_COMMENT_INVENTORY_BLOCKED_NO_GO")
                self.assertEqual(r["reason"],"UNSAFE_GITHUB_TOKEN_FORMAT_NO_REQUEST")
                self.assertEqual(opened,[])


if __name__=="__main__":
    unittest.main()
