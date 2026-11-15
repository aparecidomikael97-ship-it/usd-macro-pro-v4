"""Only synthetically constructed GitHub-shaped metadata; ZERO live API or MT5."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from copy import deepcopy
from dataclasses import replace
import unittest

from atlasquant_trader_fx28_sunday_open_external_witness_contract_lab import (
    inspect_fx28_sunday_open_external_witness_lab as inspect,
    HEADER,
)
from atlasquant_trader_fx28_sunday_open_poll_bracket_contract_lab import (
    EMPTY, BAR, ERROR, EXPECTED_TERMINAL,
)
from test_atlasquant_trader_fx28_sunday_open_poll_bracket_contract_lab import (
    NOMINAL, NOW, poll,
)

UTC=timezone.utc
REPO="aparecidomikael97-ship-it/usd-macro-pro-v4"
ISSUE=1884


def stamp(dt):
    return dt.isoformat().replace("+00:00","Z")


def receipt(cid, body, created, observed):
    return {
        "id":cid,
        "body":body,
        "url":f"https://api.github.com/repos/{REPO}/issues/comments/{cid}",
        "html_url":f"https://github.com/{REPO}/issues/{ISSUE}#issuecomment-{cid}",
        "created_at":stamp(created),
        "updated_at":stamp(created),
        "locally_observed_at_utc":observed,
    }


class SundayWitnessTests(unittest.TestCase):
    def setUp(self):
        self.before=poll(True)
        self.after=poll(False,mode=BAR,bar=NOMINAL+timedelta(minutes=15))

    def inspect(self, *, before=None, after=None, prior=None, later=None,
                nominal=NOMINAL, now=NOW):
        return inspect(
            research_sunday_start_utc=nominal,
            prior_cohort=self.before if before is None else before,
            later_cohort=self.after if after is None else after,
            inspected_at_utc=now,
            github_prior_comment=prior,
            github_later_comment=later,
        )

    def safe(self, result):
        self.assertFalse(result["github_comment_source_independently_authenticated"])
        self.assertFalse(result["external_first_seen_witness_independently_verified"])
        self.assertFalse(result["pepperstone_broker_authenticated"])
        self.assertFalse(result["market_open_time_authenticated"])
        self.assertFalse(result["mt5_poll_times_independently_verified"])
        self.assertFalse(result["original_672_campaign_slots_modified"])
        self.assertFalse(result["original_20261115_m15_retried"])
        self.assertFalse(result["raw_prices_published"])
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["publishable"])
        self.assertFalse(result["scheduler_enabled"])
        self.assertTrue(result["caller_supplied_github_data_not_live_api"])
        self.assertTrue(result["matching_hash_cannot_prove_witness_created_then"])
        self.assertIsNone(result["validated_accuracy"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertEqual((result["http_requests"],result["mt5_calls"],
                          result["file_writes"]),(0,0,0))
        self.assertEqual(result["operational_bias"],"AGUARDAR")

    def fixtures(self):
        unsigned=self.inspect()
        self.assertEqual(unsigned["cohort_claims_canonicalized"],2)
        b=unsigned["prepared_comment_bodies"]
        prior=receipt(800001,b["PRIOR"],
                      NOMINAL+timedelta(minutes=31),
                      NOMINAL+timedelta(minutes=32))
        later=receipt(800002,b["LATER"],
                      NOMINAL+timedelta(minutes=46),
                      NOMINAL+timedelta(minutes=47))
        return prior,later,unsigned

    def test_01_prepared_hashes_do_not_mean_posted_on_github(self):
        result=self.inspect()
        self.safe(result)
        self.assertEqual(result["state"],
            "LAB_FX28_SUNDAY_OPEN_UNPUBLISHED_HASH_ONLY_NO_GO")
        self.assertEqual(set(result["metadata_digests"]),{"PRIOR","LATER"})
        self.assertNotEqual(result["metadata_digests"]["PRIOR"],
                            result["metadata_digests"]["LATER"])
        self.assertTrue(all(body.startswith(HEADER+"\n")
                            for body in result["prepared_comment_bodies"].values()))
        self.assertTrue(all("raw_prices_disclosed=false" in body
                            for body in result["prepared_comment_bodies"].values()))

    def test_02_two_eligible_synthetic_github_receipts_only_documentary(self):
        a,b,_=self.fixtures()
        r=self.inspect(prior=a,later=b)
        self.safe(r)
        self.assertEqual(r["state"],
            "LAB_FX28_SUNDAY_OPEN_TWO_GITHUB_METADATA_BINDINGS_CLAIM_ONLY_NO_GO")
        self.assertTrue(r["comment_metadata_structurally_matched"])
        self.assertTrue(r["prior_witness_claim_created_before_later_poll"])

    def test_03_comment_digest_tamper_blocks(self):
        a,b,_=self.fixtures()
        a["body"]=a["body"].replace("metadata_sha256=","metadata_sha256=0")
        r=self.inspect(prior=a,later=b)
        self.safe(r)
        self.assertEqual(r["reason"],"COMMENT_HASH_ID_URL_OR_TIMESTAMP_CLAIM_MISMATCH")

    def test_04_poll_metadata_changes_after_digest_fails(self):
        a,b,_=self.fixtures()
        change=list(self.after)
        change[0]=replace(change[0],market_watch_visible_claim=False)
        r=self.inspect(after=change,prior=a,later=b)
        self.assertEqual(r["reason"],"INVALID_OR_UNVERIFIED_TWO_POLL_RESEARCH")
        self.safe(r)

    def test_05_valid_but_changed_local_poll_time_breaks_hash(self):
        a,b,_=self.fixtures()
        change=list(self.before)
        change[0]=replace(change[0],started_at_utc=
                          change[0].started_at_utc+timedelta(seconds=1))
        r=self.inspect(before=change,prior=a,later=b)
        self.safe(r)
        self.assertEqual(r["reason"],"COMMENT_HASH_ID_URL_OR_TIMESTAMP_CLAIM_MISMATCH")

    def test_06_missing_one_comment_blocks_not_partial_verified(self):
        a,b,_=self.fixtures()
        r=self.inspect(prior=a)
        self.safe(r)
        self.assertEqual(r["reason"],"BOTH_GITHUB_COMMENT_RECORDS_REQUIRED")

    def test_07_wrong_issue_url_blocks(self):
        a,b,_=self.fixtures()
        b["html_url"]=b["html_url"].replace("/1884#","/1885#")
        self.assertEqual(self.inspect(prior=a,later=b)["reason"],
                         "COMMENT_HASH_ID_URL_OR_TIMESTAMP_CLAIM_MISMATCH")

    def test_08_duplicate_ids_block(self):
        a,b,_=self.fixtures()
        b["id"]=a["id"]
        b["url"]=a["url"]
        b["html_url"]=a["html_url"]
        self.assertEqual(self.inspect(prior=a,later=b)["reason"],
                         "COMMENT_HASH_ID_URL_OR_TIMESTAMP_CLAIM_MISMATCH")

    def test_09_edited_github_body_timestamp_blocks(self):
        a,b,_=self.fixtures()
        a["updated_at"]=stamp(NOMINAL+timedelta(minutes=33))
        self.assertEqual(self.inspect(prior=a,later=b)["reason"],
                         "COMMENT_HASH_ID_URL_OR_TIMESTAMP_CLAIM_MISMATCH")

    def test_10_prior_comment_created_after_second_poll_begins_blocks(self):
        a,b,_=self.fixtures()
        a["created_at"]=stamp(NOMINAL+timedelta(minutes=45))
        a["updated_at"]=a["created_at"]
        a["locally_observed_at_utc"]=NOMINAL+timedelta(minutes=46)
        self.assertEqual(self.inspect(prior=a,later=b)["reason"],
                         "GITHUB_WITNESS_CLAIM_NOT_IN_TWO_POLL_TIME_ORDER")

    def test_11_prior_comment_first_observed_after_later_poll_blocks(self):
        a,b,_=self.fixtures()
        a["locally_observed_at_utc"]=NOMINAL+timedelta(minutes=46)
        self.assertEqual(self.inspect(prior=a,later=b)["reason"],
                         "GITHUB_WITNESS_CLAIM_NOT_IN_TWO_POLL_TIME_ORDER")

    def test_12_prior_created_before_poll_completed_blocks(self):
        a,b,_=self.fixtures()
        a["created_at"]=stamp(NOMINAL+timedelta(minutes=29))
        a["updated_at"]=a["created_at"]
        self.assertEqual(self.inspect(prior=a,later=b)["reason"],
                         "GITHUB_WITNESS_CLAIM_NOT_IN_TWO_POLL_TIME_ORDER")

    def test_13_later_comment_created_before_later_poll_completes_blocks(self):
        a,b,_=self.fixtures()
        b["created_at"]=stamp(NOMINAL+timedelta(minutes=43))
        b["updated_at"]=b["created_at"]
        self.assertEqual(self.inspect(prior=a,later=b)["reason"],
                         "GITHUB_WITNESS_CLAIM_NOT_IN_TWO_POLL_TIME_ORDER")

    def test_14_naive_or_fractional_server_timestamp_blocks(self):
        for bad in ("2026-12-13T22:31:00","2026-12-13T22:31:00.1Z",
                    "2026-12-13T22:31:60Z","2026-12-13 22:31:00Z"):
            with self.subTest(bad=bad):
                a,b,_=self.fixtures()
                a["created_at"]=bad
                a["updated_at"]=bad
                r=self.inspect(prior=a,later=b)
                self.safe(r)
                self.assertEqual(r["reason"],
                    "COMMENT_HASH_ID_URL_OR_TIMESTAMP_CLAIM_MISMATCH")

    def test_15_nonstring_created_at_even_if_datetime_plausible_blocks(self):
        a,b,_=self.fixtures()
        a["created_at"]=NOMINAL+timedelta(minutes=31)
        a["updated_at"]=a["created_at"]
        self.assertEqual(self.inspect(prior=a,later=b)["reason"],
                         "COMMENT_HASH_ID_URL_OR_TIMESTAMP_CLAIM_MISMATCH")

    def test_16_github_created_in_future_relative_to_inspection_blocks(self):
        a,b,_=self.fixtures()
        b["created_at"]=stamp(NOW+timedelta(minutes=1))
        b["updated_at"]=b["created_at"]
        self.assertEqual(self.inspect(prior=a,later=b)["reason"],
                         "COMMENT_HASH_ID_URL_OR_TIMESTAMP_CLAIM_MISMATCH")

    def test_17_server_updated_before_created_blocks(self):
        a,b,_=self.fixtures()
        a["updated_at"]=stamp(NOMINAL+timedelta(minutes=30))
        self.assertEqual(self.inspect(prior=a,later=b)["reason"],
                         "COMMENT_HASH_ID_URL_OR_TIMESTAMP_CLAIM_MISMATCH")

    def test_18_one_unknown_api_result_blocks_even_signed_claims(self):
        a,b,_=self.fixtures()
        before=list(self.before)
        before[0]=replace(before[0],api_result_kind=ERROR)
        self.assertEqual(self.inspect(before=before,prior=a,later=b)["reason"],
                         "INVALID_OR_UNVERIFIED_TWO_POLL_RESEARCH")

    def test_19_still_empty_in_both_can_prepare_metadata_but_no_broker_claim(self):
        r=self.inspect(after=poll(False))
        self.safe(r)
        self.assertEqual(r["cohort_claims_canonicalized"],2)
        self.assertEqual(r["state"],
                         "LAB_FX28_SUNDAY_OPEN_UNPUBLISHED_HASH_ONLY_NO_GO")

    def test_20_original_20261115_campaign_never_eligible(self):
        nominal=datetime(2026,11,15,22,tzinfo=UTC)
        r=self.inspect(nominal=nominal)
        self.safe(r)
        self.assertEqual(r["reason"],"INVALID_OR_UNVERIFIED_TWO_POLL_RESEARCH")

    def test_21_cannot_substitute_end_of_history(self):
        before=list(self.before)
        before[0]=replace(before[0],
            requested_history_end_at_utc=NOMINAL+timedelta(hours=3))
        self.assertEqual(self.inspect(before=before)["reason"],
                         "INVALID_OR_UNVERIFIED_TWO_POLL_RESEARCH")


if __name__=="__main__":
    unittest.main(verbosity=2)
