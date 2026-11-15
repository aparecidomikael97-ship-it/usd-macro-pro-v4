"""Offline Github REST mock pages. NEVER sends HTTP or calls MetaTrader 5."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
import unittest

from atlasquant_trader_fx28_sunday_open_github_rest_inventory_lab import (
    API, HEADER, inspect_sunday_open_github_rest_pages_lab as inspect,
    collect_sunday_open_public_github_once_lab as collect,
)

UTC = timezone.utc
TODAY = datetime(2026,11,15,23,30,tzinfo=UTC)
FUTURE = datetime(2026,12,13,23,30,tzinfo=UTC)
REPO="aparecidomikael97-ship-it/usd-macro-pro-v4"
ISSUE=1884
NOMINAL=datetime(2026,12,13,22,tzinfo=UTC)


def comment(cid, body="NOT_A_SUNDAY_WITNESS", created="2026-11-15T22:01:00Z"):
    return {
        "id":cid,
        "body":body,
        "created_at":created,
        "updated_at":created,
        "url":f"https://api.github.com/repos/{REPO}/issues/comments/{cid}",
        "html_url":f"https://github.com/{REPO}/issues/{ISSUE}#issuecomment-{cid}",
        "issue_url":f"https://api.github.com/repos/{REPO}/issues/{ISSUE}",
    }


def body(phase="PRIOR", hashvalue="a"*64, nominal="2026-12-13T22:00:00Z"):
    return "\n".join((
        HEADER, "nominal_start_utc="+nominal, "cohort="+phase,
        "pair_count=28", "metadata_sha256="+hashvalue,
        "raw_prices_disclosed=false", "research_only=true",
        "trade_authorized=false",
    ))


def raw(rows):
    return json.dumps(rows,sort_keys=True,separators=(",",":")).encode("utf-8")


class FakeResponse:
    def __init__(self,url,contents,*,status=200,mime="application/json",final=None):
        self.status=status
        self.headers={"Content-Type":mime}
        self.url=url
        self.final=final
        self.contents=contents
    def __enter__(self):
        return self
    def __exit__(self,*_):
        return False
    def geturl(self):
        return self.final or self.url
    def read(self,_limit):
        return self.contents


class GithubSundayRestInventoryTests(unittest.TestCase):
    def check(self, pages, *, at=TODAY):
        return inspect(raw_pages=tuple(raw(p) for p in pages),
                       observed_at_utc=at)

    def safe(self,r):
        for flag in ("github_comments_independently_authenticated",
                     "github_comment_first_seen_independently_witnessed",
                     "pepperstone_source_authenticated","broker_session_open_verified",
                     "terminal_poll_time_authenticated",
                     "prediction_precommit_verified","forecast_accuracy_validated",
                     "trade_authorized","publishable","scheduler_enabled",
                     "original_campaign_672_slots_modified",
                     "original_20261115_m15_retried",
                     "raw_comment_bodies_exposed","raw_ohlc_prices_exposed"):
            self.assertFalse(r[flag],flag)
        self.assertIsNone(r["validated_accuracy"])
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertEqual((r["mt5_calls"],r["file_writes"],r["new_cost_brl"]), (0,0,0))

    def two_cohorts(self):
        return [comment(1000001,body("PRIOR"),"2026-12-13T22:31:00Z"),
                comment(1000002,body("LATER","b"*64),"2026-12-13T22:46:00Z")]

    def test_01_119_comments_no_witness_is_not_broker_evidence(self):
        rows=[comment(100000+i) for i in range(119)]
        r=self.check([rows[:100],rows[100:]])
        self.safe(r)
        self.assertEqual(r["state"],"LAB_FX28_SUNDAY_GITHUB_REST_RECEIPTS_METADATA_ONLY_NO_GO")
        self.assertEqual((r["pages_inspected"],r["comments_inspected"]),(2,119))
        self.assertEqual(r["header_exact_matches"],0)
        self.assertEqual(r["completed_two_phase_metadata_sets"],0)

    def test_02_prior_and_later_valid_documentary_receipts(self):
        r=self.check([self.two_cohorts()],at=FUTURE)
        self.safe(r)
        self.assertEqual(r["header_exact_matches"],2)
        self.assertEqual(r["prior_metadata_receipt_claims"],1)
        self.assertEqual(r["later_metadata_receipt_claims"],1)
        self.assertEqual(r["completed_two_phase_metadata_sets"],1)
        self.assertEqual(r["complete_prior_later_cohort_pairs_claim_only"],28)
        self.assertEqual(len(r["candidate_receipt_metadata"]),2)
        self.assertTrue(all(not x["independently_attested"]
                            for x in r["candidate_receipt_metadata"]))

    def test_03_one_prior_without_later_not_completed(self):
        r=self.check([[self.two_cohorts()[0]]],at=FUTURE)
        self.safe(r)
        self.assertEqual(r["completed_two_phase_metadata_sets"],0)

    def test_04_missing_or_noncanonical_body_rejected(self):
        for bad in (body().replace("pair_count=28","pair_count=27"),
                    body()+"\nopen=1.2345",
                    body().replace("raw_prices_disclosed=false","raw_prices_disclosed=true"),
                    body().replace("research_only=true","research_only=false"),
                    body().replace("metadata_sha256=","metadata_sha256=0"),
                    body(nominal="2026-11-15T22:00:00Z")):
            with self.subTest(bad=bad[-30:]):
                r=self.check([[comment(999999,bad)]],at=FUTURE)
                self.safe(r)
                self.assertEqual(r["reason"],"MALFORMED_OR_UNSAFE_SUNDAY_RECEIPT_BODY")

    def test_05_comment_marked_edited_rejected(self):
        rws=self.two_cohorts()
        rws[0]["updated_at"]="2026-12-13T22:32:00Z"
        self.assertEqual(self.check([rws],at=FUTURE)["reason"],
                         "COMMENT_OUTSIDE_RESEARCH_WINDOW_OR_EDITED")

    def test_06_both_phases_wrong_order_rejected(self):
        rws=self.two_cohorts()
        rws[0]["created_at"]="2026-12-13T22:47:00Z"
        rws[0]["updated_at"]=rws[0]["created_at"]
        self.assertEqual(self.check([rws],at=FUTURE)["reason"],
                         "REVERSED_TWO_PHASE_GITHUB_CREATED_CLOCK")

    def test_07_too_late_after_5h15_outside_plan(self):
        rws=self.two_cohorts()
        rws[1]["created_at"]="2026-12-14T03:16:00Z"
        rws[1]["updated_at"]=rws[1]["created_at"]
        r=self.check([rws],at=FUTURE+timedelta(hours=5))
        self.assertEqual(r["reason"],"COMMENT_OUTSIDE_RESEARCH_WINDOW_OR_EDITED")

    def test_08_duplicate_cohort_is_unsafe(self):
        rws=self.two_cohorts()
        extra=comment(1000003,body("PRIOR","c"*64),"2026-12-13T22:35:00Z")
        self.assertEqual(self.check([rws+[extra]],at=FUTURE)["reason"],
                         "DUPLICATE_SUNDAY_COHORT_RECEIPT")

    def test_09_comment_id_reordered_or_duplicate(self):
        for rws in ([comment(202),comment(201)],
                    [comment(202),comment(202)]):
            self.assertEqual(self.check([rws])["reason"],
                             "GITHUB_ISSUE_COMMENT_ID_URL_CLOCK_OR_BODY_INVALID")

    def test_10_url_points_to_wrong_issue(self):
        x=comment(300)
        x["issue_url"]=x["issue_url"].replace("/1884","/1885")
        self.assertEqual(self.check([[x]])["reason"],
                         "GITHUB_ISSUE_COMMENT_ID_URL_CLOCK_OR_BODY_INVALID")

    def test_11_nonstring_created_or_timestamp_in_future(self):
        for bad in (None,"2026-11-15T22:01:00.000Z",
                    "2026-11-16T22:01:00Z"):
            x=comment(300)
            x["created_at"]=bad
            self.assertEqual(self.check([[x]])["reason"],
                             "GITHUB_ISSUE_COMMENT_ID_URL_CLOCK_OR_BODY_INVALID")

    def test_12_rfc3339_no_fractional_or_offset_allowed(self):
        rws=self.two_cohorts()
        rws[0]["created_at"]="2026-12-13T22:31:00+00:00"
        self.assertEqual(self.check([rws],at=FUTURE)["reason"],
                         "GITHUB_ISSUE_COMMENT_ID_URL_CLOCK_OR_BODY_INVALID")

    def test_13_early_nonfinal_page_rejected(self):
        r=self.check([[comment(1) for _ in range(99)],[comment(100)]])
        self.assertEqual(r["reason"],"INCOMPLETE_GITHUB_PAGINATION_NO_GO")

    def test_14_100_without_final_page_rejected(self):
        r=self.check([[comment(i) for i in range(1,101)]])
        self.assertEqual(r["reason"],"INCOMPLETE_GITHUB_PAGINATION_NO_GO")

    def test_15_100_plus_empty_terminal_page_allowed(self):
        r=self.check([[comment(i) for i in range(1,101)],[]])
        self.safe(r)
        self.assertEqual((r["comments_inspected"],r["pages_inspected"]),(100,2))

    def test_16_json_duplicate_object_keys_rejected(self):
        duplicate=b'[{"id":1,"id":2}]'
        r=inspect(raw_pages=[duplicate],observed_at_utc=TODAY)
        self.assertEqual(r["reason"],
                         "INVALID_DUPLICATE_OVERSIZED_OR_UNDECODABLE_GITHUB_PAGES")

    def test_17_json_nonfinite_constant_rejected(self):
        r=inspect(raw_pages=[b'[NaN]'],observed_at_utc=TODAY)
        self.assertEqual(r["reason"],
                         "INVALID_DUPLICATE_OVERSIZED_OR_UNDECODABLE_GITHUB_PAGES")

    def test_18_raw_page_invalid_type_rejected(self):
        r=inspect(raw_pages=["[]"],observed_at_utc=TODAY)
        self.assertEqual(r["reason"],
                         "INVALID_DUPLICATE_OVERSIZED_OR_UNDECODABLE_GITHUB_PAGES")

    def test_19_no_public_network_without_explicit_permission(self):
        calls=[]
        def opener(*args,**kwargs):
            calls.append((args,kwargs))
            raise RuntimeError("SHOULD_NEVER_BE_CALLED")
        r=collect(allow_read_public_github=False,request_open=opener)
        self.safe(r)
        self.assertEqual(r["http_request_attempts"],0)
        self.assertFalse(calls)

    def test_20_pinned_get_2_pages_with_fake_transport_not_called_live(self):
        first=[comment(i) for i in range(1,101)]
        second=[comment(i) for i in range(101,120)]
        expected=[raw(first),raw(second)]
        requests=[]
        class Opener:
            def __call__(self,request,timeout):
                assert request.get_method()=="GET"
                assert timeout==12
                assert request.full_url==(f"{API}?per_page=100&page={len(requests)+1}")
                requests.append(request.full_url)
                return FakeResponse(request.full_url,expected[len(requests)-1])
        r=collect(allow_read_public_github=True,request_open=Opener(),
                  observed_clock=lambda:TODAY)
        self.safe(r)
        self.assertEqual(r["http_request_attempts"],2)
        self.assertEqual(r["comments_inspected"],119)
        self.assertFalse(r["live_https_get_completed"])
        self.assertTrue(r["snapshot_origin_is_caller_supplied"])
        self.assertEqual(len(requests),2)

    def test_21_bad_mime_fails_without_retries(self):
        calls=[]
        def opener(req,timeout):
            calls.append(req.full_url)
            return FakeResponse(req.full_url,b'[]',mime="text/html")
        r=collect(allow_read_public_github=True,request_open=opener)
        self.assertEqual(r["reason"],"UNTRUSTED_HTTPS_STATUS_TYPE_URL_OR_SIZE")
        self.assertEqual(len(calls),1)

    def test_22_redirect_to_other_host_rejected(self):
        calls=[]
        def opener(req,timeout):
            calls.append(req.full_url)
            return FakeResponse(req.full_url,b'[]',
                                final="https://evil.example/false")
        r=collect(allow_read_public_github=True,request_open=opener)
        self.assertEqual(r["reason"],"UNTRUSTED_HTTPS_STATUS_TYPE_URL_OR_SIZE")
        self.assertEqual(len(calls),1)

    def test_23_http_500_rejected(self):
        def opener(req,timeout):
            return FakeResponse(req.full_url,b'[]',status=500)
        r=collect(allow_read_public_github=True,request_open=opener)
        self.assertEqual(r["reason"],"UNTRUSTED_HTTPS_STATUS_TYPE_URL_OR_SIZE")

    def test_24_transport_exception_no_retry(self):
        calls=[]
        def opener(req,timeout):
            calls.append(req.full_url)
            raise OSError("SIMULATED_NETWORK_OFFLINE")
        r=collect(allow_read_public_github=True,request_open=opener)
        self.assertEqual(r["reason"],"PUBLIC_GITHUB_HTTPS_READ_FAILED_NO_RETRY")
        self.assertEqual(len(calls),1)

    def test_25_wrong_window_before_frozen_cannot_scan(self):
        r=inspect(raw_pages=[b'[]'],
                  observed_at_utc=datetime(2026,11,14,0,tzinfo=UTC))
        self.assertEqual(r["reason"],"INVALID_GITHUB_REST_PAGES_OR_INSPECTION_CLOCK")


if __name__=="__main__":
    unittest.main(verbosity=2)
