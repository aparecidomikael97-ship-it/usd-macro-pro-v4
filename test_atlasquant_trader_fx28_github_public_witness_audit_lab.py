"""Synthetic GitHub REST responses only; no real forecast or external API GET."""
from __future__ import annotations
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import io
import json
from unittest.mock import patch
import unittest

from atlasquant_trader_fx28_ny17_forecast_witness_lab import HEADER
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    _nominal_windows, CAMPAIGN_ID, FROZEN_START_UTC,
)
from atlasquant_trader_fx28_github_public_witness_audit_lab import (
    SCHEMA, REPO, OWNER, ISSUE, _anchor,
    audit_fx28_public_github_witness_snapshot_lab as audit, main,
)

UTC = timezone.utc
NOW = datetime(2026, 11, 13, 19, 5, tzinfo=UTC)
BORN = "2026-11-13T18:30:00Z"


def body(horizon="D1", *, digest="a"*64):
    start, end = _nominal_windows(horizon)[0]
    def stamp(t):
        return t.isoformat().replace("+00:00","Z")
    return "\n".join((
        HEADER, "campaign_id="+CAMPAIGN_ID, "horizon="+horizon,
        "start_utc="+stamp(start), "end_utc="+stamp(end), "pairs=28",
        "roster_sha256="+digest, "research_only=true",
        "trade_authorized=false",
    ))


def comment(cid, text, *, created=BORN, updated=None, login=OWNER):
    return {
        "id":cid, "body":text, "user":{"login":login},
        "url":f"https://api.github.com/repos/{REPO}/issues/comments/{cid}",
        "html_url":f"https://github.com/{REPO}/issues/{ISSUE}#issuecomment-{cid}",
        "created_at":created,
        "updated_at":created if updated is None else updated,
    }


class GithubWitnessAuditTests(unittest.TestCase):
    def run_it(self, comments=None, *, at=NOW, complete=True):
        return audit(
            comments=[] if comments is None else comments,
            observed_at_utc=at, response_complete=complete,
        )

    def safe(self, r):
        self.assertEqual(r["schema"],SCHEMA)
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        for k in ("trade_authorized","publishable","live_alert_allowed",
                  "scheduler_enabled","worker_enabled",
                  "forecasts_pre_event_independently_authenticated",
                  "source_document_sha_was_independently_reproduced",
                  "broker_prices_independently_authenticated",
                  "macro_vintage_point_in_time_authenticated"):
            self.assertFalse(r[k],k)
        self.assertTrue(r["hash_only_comment_is_not_preserved_canonical_28_forecasts"])
        self.assertTrue(r["github_server_metadata_is_not_independent_time_witness"])
        self.assertTrue(r["zero_matching_anchors_is_not_proof_of_no_other_forecasts"])
        self.assertIsNone(r["validated_accuracy"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertEqual(r["http_get_requests"],0)
        self.assertEqual(r["file_writes"],0)
        self.assertEqual(r["new_cost_brl"],0)
        self.assertEqual(r["nominal_windows_total"],24)
        self.assertEqual(r["expected_pair_horizon_slots"],672)

    def blocked(self, *args, **kwargs):
        r=self.run_it(*args,**kwargs)
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_GITHUB_PUBLIC_WITNESS_AUDIT_BLOCKED")
        self.assertEqual(r["source_comments_scanned"],0)
        self.assertEqual(r["strict_pre_event_hash_only_anchor_claims"],0)
        return r

    def test_01_empty_issue_not_proof_of_no_forecasts_elsewhere(self):
        r=self.run_it()
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_FX28_GITHUB_PUBLIC_HASH_ONLY_CENSUS_NO_GO")
        self.assertEqual(r["reason"],
                         "NO_STRICT_PRE_EVENT_HASH_ONLY_ANCHORS_IN_SNAPSHOT")
        self.assertEqual(r["source_comments_scanned"],0)
        self.assertEqual(r["due_nominal_slots"],0)
        self.assertEqual(r["future_nominal_slots"],672)

    def test_02_prose_mentions_are_never_real_anchors(self):
        cs=[comment(10,"## Report\nMention "+HEADER),
            comment(11,"## Tutorial\nExample "+HEADER+"\n..."),
            comment(12,"No commitments")]
        r=self.run_it(cs)
        self.safe(r)
        self.assertEqual(r["source_comments_scanned"],3)
        self.assertEqual(r["marker_mentioned_in_prose_only_comments"],2)
        self.assertEqual(r["strict_anchor_bodies_observed"],0)
        self.assertEqual(r["strict_pre_event_hash_only_anchor_claims"],0)

    def test_03_valid_weak_pre_event_hash_only_is_not_forecast_proof(self):
        r=self.run_it([comment(100,body("D1"))])
        self.safe(r)
        self.assertEqual(r["strict_anchor_bodies_observed"],1)
        self.assertEqual(r["strict_pre_event_hash_only_anchor_claims"],1)
        self.assertEqual(r["future_slots_with_hash_only_claim_in_snapshot"],28)
        self.assertFalse(r["claimed_pre_event_hash_only_windows"][0]
                         ["canonical_roster_bytes_retrieved"])

    def test_04_D1_and_W1_same_start_are_separate_28_slot_windows(self):
        r=self.run_it([comment(100,body("D1")),comment(101,body("W1"))])
        self.safe(r)
        self.assertEqual(r["strict_pre_event_hash_only_anchor_claims"],2)
        self.assertEqual(r["future_slots_with_hash_only_claim_in_snapshot"],56)

    def test_05_comment_posted_at_start_is_too_late(self):
        born="2026-11-15T22:00:00Z"
        r=self.run_it([comment(100,body("D1"),created=born)],
                      at=FROZEN_START_UTC+timedelta(seconds=1))
        self.safe(r)
        self.assertEqual(r["strict_anchor_bodies_observed"],1)
        self.assertEqual(r["rejected_anchor_metadata_or_ambiguous_window"],1)
        self.assertEqual(r["due_nominal_slots"],56)
        self.assertEqual(r["due_slots_without_hash_only_anchor_in_snapshot"],56)

    def test_06_edited_comment_not_a_pre_event_commitment(self):
        r=self.run_it([comment(100,body("D1"),
                               updated="2026-11-13T18:31:00Z")])
        self.safe(r)
        self.assertEqual(r["strict_anchor_bodies_observed"],1)
        self.assertEqual(r["strict_pre_event_hash_only_anchor_claims"],0)
        self.assertEqual(r["rejected_anchor_metadata_or_ambiguous_window"],1)

    def test_07_wrong_author_never_accepted(self):
        r=self.run_it([comment(100,body("D1"),login="anonymous")])
        self.safe(r)
        self.assertEqual(r["strict_pre_event_hash_only_anchor_claims"],0)

    def test_08_wrong_canonical_api_or_html_url_rejected(self):
        for key in ("url","html_url"):
            with self.subTest(key=key):
                cs=[comment(100,body("D1"))]
                cs[0][key]="https://example.org/injected"
                r=self.run_it(cs)
                self.safe(r)
                self.assertEqual(r["strict_pre_event_hash_only_anchor_claims"],0)

    def test_09_changed_protected_body_fields_not_accepted(self):
        original=body("D1")
        for replacement in ("pairs=27","campaign_id=WRONG",
                            "trade_authorized=true","research_only=false"):
            with self.subTest(replacement=replacement):
                name=replacement.split("=")[0]
                old=next(x for x in original.splitlines()
                         if x.startswith(name+"="))
                modified=original.replace(old,replacement)
                self.assertIsNone(_anchor(modified))
                r=self.run_it([comment(100,modified)])
                self.safe(r)
                self.assertEqual(r["marker_mentioned_in_prose_only_comments"],1)

    def test_10_markdown_code_quote_and_extra_lines_rejected(self):
        fence=chr(96)*3
        for text in (fence+"\n"+body("D1")+"\n"+fence,
                     body("D1")+"\n100% win!",
                     "## Project report\n"+body("D1"),
                     "> "+body("D1")):
            with self.subTest(text=text[:16]):
                self.assertIsNone(_anchor(text))
                r=self.run_it([comment(100,text)])
                self.safe(r)
                self.assertEqual(r["strict_pre_event_hash_only_anchor_claims"],0)

    def test_11_two_valid_anchors_same_window_are_ambiguous(self):
        r=self.run_it([comment(100,body("D1")),
                       comment(101,body("D1",digest="b"*64))])
        self.safe(r)
        self.assertEqual(r["strict_anchor_bodies_observed"],2)
        self.assertEqual(r["strict_pre_event_hash_only_anchor_claims"],0)
        self.assertEqual(r["unique_nominal_windows_with_hash_only_claim"],0)
        self.assertEqual(r["rejected_anchor_metadata_or_ambiguous_window"],1)

    def test_12_paginated_or_more_than_100_comments_no_false_absence(self):
        self.blocked([comment(100,body("D1"))],complete=False)
        self.blocked([comment(i,"text") for i in range(1,102)])

    def test_13_malformed_missing_or_duplicated_comment_blocks(self):
        cases=[[None],
               [comment(10,"a"),comment(10,"b")],
               [comment(10,"a",created="bad")],
               [comment(10,"a",updated="2026-11-13T18:29:00Z")],
               [comment(10,42)]]
        for cs in cases:
            with self.subTest(case=str(cs)[:30]):
                r=self.blocked(cs)
                self.assertEqual(r["reason"],"MALFORMED_GITHUB_COMMENT_SNAPSHOT")

    def test_14_invalid_asof_naive_microseconds_and_strings(self):
        for at in (None,1,"2026-11-13T19:05:00Z",
                   NOW.replace(tzinfo=None),NOW.replace(microsecond=1)):
            with self.subTest(at=at):
                self.blocked(at=at)

    def test_15_fake_digests_or_unknown_window_are_not_anchors(self):
        for digest in ("0"*64,"A"*64,"bad","g"*64):
            with self.subTest(digest=digest):
                self.assertIsNone(_anchor(body("D1",digest=digest)))
                r=self.run_it([comment(100,body("D1",digest=digest))])
                self.safe(r)
                self.assertEqual(r["strict_pre_event_hash_only_anchor_claims"],0)
        shifted=body("D1").replace(
            "2026-11-15T22:00:00Z","2026-11-16T22:00:00Z")
        self.assertIsNone(_anchor(shifted))

    def test_16_exact_first_start_debits_56_even_if_only_D1_anchor(self):
        r=self.run_it([comment(100,body("D1"))],at=FROZEN_START_UTC)
        self.safe(r)
        self.assertEqual(r["due_nominal_slots"],56)
        self.assertEqual(r["future_nominal_slots"],616)
        self.assertEqual(r["due_slots_with_hash_only_claim_in_snapshot"],28)
        self.assertEqual(r["due_slots_without_hash_only_anchor_in_snapshot"],28)
        self.assertIsNone(r["validated_accuracy"])

    def test_17_api_list_order_does_not_change_count(self):
        cs=[comment(101,body("W1")),comment(100,body("D1")),
            comment(30,"## Mention "+HEADER)]
        before=deepcopy(cs)
        a=self.run_it(cs)
        b=self.run_it(list(reversed(cs)))
        self.safe(a)
        self.assertEqual(a,b)
        self.assertEqual(cs,before)

    def test_18_default_cli_no_flag_cannot_fetch(self):
        stdout=io.StringIO()
        with patch(
            "atlasquant_trader_fx28_github_public_witness_audit_lab._fetch_public_issue_comments_once"
        ) as fetch:
            with redirect_stdout(stdout):
                code=main([])
        self.assertEqual(code,2)
        fetch.assert_not_called()
        self.assertEqual(json.loads(stdout.getvalue())["http_get_requests"],0)

    def test_19_opt_in_cli_one_public_get_without_go(self):
        stdout=io.StringIO()
        with patch(
            "atlasquant_trader_fx28_github_public_witness_audit_lab._fetch_public_issue_comments_once",
            return_value=([comment(100,"## "+HEADER)],True),
        ) as fetch:
            with redirect_stdout(stdout):
                code=main(["--audit-github-public"])
        self.assertEqual(code,2)
        fetch.assert_called_once()
        r=json.loads(stdout.getvalue())
        self.assertEqual(r["http_get_requests"],1)
        self.assertEqual(r["strict_anchor_bodies_observed"],0)
        self.assertEqual(r["marker_mentioned_in_prose_only_comments"],1)
        self.assertFalse(r["trade_authorized"])

    def test_20_http_exception_blocks_without_retry(self):
        stdout=io.StringIO()
        with patch(
            "atlasquant_trader_fx28_github_public_witness_audit_lab._fetch_public_issue_comments_once",
            side_effect=OSError("synthetic timeout"),
        ) as fetch:
            with redirect_stdout(stdout):
                code=main(["--audit-github-public"])
        self.assertEqual(code,2)
        fetch.assert_called_once()
        r=json.loads(stdout.getvalue())
        self.assertEqual(r["state"],
                         "LAB_FX28_GITHUB_PUBLIC_WITNESS_AUDIT_BLOCKED")
        self.assertEqual(r["http_get_requests"],1)
        self.assertEqual(r["source_comments_scanned"],0)


if __name__=="__main__":
    unittest.main()
