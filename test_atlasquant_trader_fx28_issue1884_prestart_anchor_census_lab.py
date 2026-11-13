"""Frozen 672 FX28 NY17 campaign slots vs untrusted GitHub comment snapshots.

Fixtures are synthetic, not actual posted forecasts and not financial signals.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import unittest

from atlasquant_trader_fx28_issue1884_prestart_anchor_census_lab import (
    ANCHOR_HEADER, CAMPAIGN_ID,
    inspect_fx28_issue1884_prestart_anchor_snapshot_lab as inspect,
)

UTC=timezone.utc
PRESTART=datetime(2026,11,13,11,21,tzinfo=UTC)
FIRST=datetime(2026,11,15,22,tzinfo=UTC)
POST_FIRST=datetime(2026,11,15,22,1,tzinfo=UTC)
END=datetime(2026,12,12,0,tzinfo=UTC)


def anchor(horizon="D1", *,
           start="2026-11-15T22:00:00Z",
           end="2026-11-16T22:00:00Z",
           cid=10001,
           created_at=None,updated_at=None,
           digest="a"*64):
    body="\n".join((
        ANCHOR_HEADER,
        "campaign_id="+CAMPAIGN_ID,
        "horizon="+horizon,
        "start_utc="+start,
        "end_utc="+end,
        "pairs=28",
        "roster_sha256="+digest,
        "research_only=true",
        "trade_authorized=false",
    ))
    return {
        "id":cid,"url":(
            "https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4"
            f"/issues/1884#issuecomment-{cid}"
        ),
        "body":body,
        "created_at":created_at,
        "updated_at":updated_at,
    }


def weekly(cid=10002, **kwargs):
    return anchor(
        horizon="W1",
        start="2026-11-15T22:00:00Z",
        end="2026-11-20T22:00:00Z",
        cid=cid,
        **kwargs,
    )


class Issue1884PrestartCensusTests(unittest.TestCase):
    def check(self, comments=None, now=PRESTART):
        return inspect(
            issue_comment_snapshots=[] if comments is None else comments,
            inspected_at_utc=now,
        )

    def safe(self,r):
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["raw_roster_json_independently_preserved"])
        self.assertFalse(r["github_comment_metadata_independently_authenticated"])
        self.assertFalse(r["issuer_macro_data_first_seen_authenticated"])
        self.assertFalse(r["broker_ny17_first_last_m15_authenticated"])
        self.assertEqual(r["directional_forecasts_independently_witnessed"],0)
        self.assertIsNone(r["validated_directional_accuracy"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertEqual(r["http_requests"],0)
        self.assertEqual(r["files_written"],0)
        self.assertEqual(r["new_cost_brl"],0)
        for row in r["window_states"]:
            self.assertFalse(row["pre_event_forecast_independently_witnessed"])

    def test_actual_issue_1884_audit_notes_do_not_claim_forecast_roster(self):
        comments=[
            {"id":6840355769,"body":"Aviso pré-campanha: gaps W1; sem forecast."},
            {"id":6840654280,"body":"Estado pré-evento: ainda sem previsão."},
        ]
        r=self.check(comments)
        self.safe(r)
        self.assertEqual(r["state"],"LAB_ISSUE1884_672_SLOT_ANCHOR_CENSUS_NO_GO")
        self.assertEqual(r["snapshot_comments_examined"],2)
        self.assertEqual(r["generic_calendar_or_audit_comments_ignored"],2)
        self.assertEqual(r["well_formed_hash_only_anchor_comments"],0)
        self.assertEqual(r["future_not_due_pair_slots"],672)
        self.assertEqual(r["due_without_independent_pre_event_witness_pair_slots"],0)
        self.assertEqual(r["first_d1_window_state"],"FUTURE_WINDOW_NOT_DUE")
        self.assertEqual(r["first_w1_window_state"],"FUTURE_WINDOW_NOT_DUE")
        self.assertTrue(r["all_672_slots_accounted_for"])

    def test_first_d1_w1_without_any_anchor_after_start_stays_56_due(self):
        r=self.check(now=POST_FIRST)
        self.safe(r)
        self.assertEqual(r["due_without_independent_pre_event_witness_pair_slots"],56)
        self.assertEqual(r["future_not_due_pair_slots"],616)
        self.assertEqual(r["first_d1_window_state"],
                         "DUE_NO_INDEPENDENT_PRE_EVENT_WITNESS")
        self.assertEqual(r["first_w1_window_state"],
                         "DUE_NO_INDEPENDENT_PRE_EVENT_WITNESS")
        self.assertEqual(len(r["window_states"]),24)

    def test_end_campaign_denominator_all_due_no_claims_not_accuracy(self):
        r=self.check(now=END)
        self.safe(r)
        self.assertEqual(r["future_not_due_pair_slots"],0)
        self.assertEqual(r["due_without_independent_pre_event_witness_pair_slots"],672)
        self.assertTrue(r["all_672_slots_accounted_for"])
        self.assertEqual(len(r["window_states"]),24)

    def test_exact_hash_anchor_without_server_clock_is_untrusted(self):
        r=self.check(comments=[anchor(),weekly()])
        self.safe(r)
        self.assertEqual(r["well_formed_hash_only_anchor_comments"],2)
        self.assertEqual(r["anchor_claims_missing_server_timestamps"],2)
        self.assertEqual(r["future_hash_anchor_claim_only_pair_slots"],56)
        self.assertEqual(r["first_d1_window_state"],
                         "PRESTART_ANCHOR_CLAIM_ONLY_UNVERIFIED")
        self.assertEqual(r["first_w1_window_state"],
                         "PRESTART_ANCHOR_CLAIM_ONLY_UNVERIFIED")
        self.assertEqual(r["future_not_due_pair_slots"],672)

    def test_claimed_prestart_creation_and_update_still_not_independent(self):
        c=anchor(created_at="2026-11-13T11:11:00Z",
                 updated_at="2026-11-13T11:11:00Z")
        r=self.check(comments=[c])
        self.safe(r)
        self.assertEqual(r["anchor_claims_missing_server_timestamps"],0)
        self.assertEqual(r["first_d1_window_state"],
                         "PRESTART_ANCHOR_CLAIM_ONLY_UNVERIFIED")

    def test_edited_or_late_anchor_after_deadline_does_not_replace_absent_witness(self):
        for c in (
            anchor(created_at="2026-11-15T22:00:00Z",
                   updated_at="2026-11-15T22:00:00Z"),
            anchor(created_at="2026-11-14T08:00:00Z",
                   updated_at="2026-11-15T22:00:00Z"),
        ):
            with self.subTest(c=c["created_at"]):
                r=self.check(comments=[c],now=POST_FIRST)
                self.safe(r)
                self.assertEqual(r["anchor_claims_late_or_edited"],1)
                self.assertEqual(r["due_without_independent_pre_event_witness_pair_slots"],56)
                self.assertEqual(r["due_hash_anchor_claim_only_pair_slots"],28)
                self.assertEqual(r["first_d1_window_state"],
                                 "DUE_ANCHOR_CLAIM_ONLY_NO_WITNESS")

    def test_noncanonical_or_unknown_start_cannot_claim_an_actual_window(self):
        for field,val in (
            ("start_utc","2026-11-15T23:00:00Z"),
            ("end_utc","2026-11-16T23:00:00Z"),
            ("horizon","MN1"),
            ("pairs","27"),
            ("research_only","false"),
            ("trade_authorized","true"),
        ):
            with self.subTest(field=field):
                c=anchor()
                if field in ("start_utc","end_utc","horizon"):
                    c["body"]=c["body"].replace(field+"="+{
                        "start_utc":"2026-11-15T22:00:00Z",
                        "end_utc":"2026-11-16T22:00:00Z","horizon":"D1"
                    }[field],field+"="+val)
                else:
                    orig={"pairs":"28","research_only":"true",
                          "trade_authorized":"false"}[field]
                    c["body"]=c["body"].replace(field+"="+orig,field+"="+val)
                r=self.check(comments=[c])
                self.safe(r)
                self.assertEqual(r["state"],"LAB_ISSUE1884_ANCHOR_CENSUS_BLOCKED")

    def test_malformed_digest_and_wrong_campaign_rejected(self):
        for replace in (
            ("roster_sha256="+"a"*64, "roster_sha256=BAD"),
            ("campaign_id="+CAMPAIGN_ID, "campaign_id=FAKE"),
        ):
            c=anchor()
            c["body"]=c["body"].replace(*replace)
            r=self.check(comments=[c])
            self.safe(r)
            self.assertEqual(r["reason"],
                             "MALFORMED_COMMITMENT_MARKER_NOT_ACCEPTABLE")

    def test_wrong_issue_url_or_forged_comment_id_blocks(self):
        for change in (
            {"url":"https://github.com/other/repo/issues/1884#issuecomment-10001"},
            {"url":"https://github.com/aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1917#issuecomment-10001"},
            {"id":True},
        ):
            c=anchor()
            c.update(change)
            r=self.check(comments=[c])
            self.safe(r)
            self.assertEqual(r["state"],"LAB_ISSUE1884_ANCHOR_CENSUS_BLOCKED")

    def test_api_url_exact_location_is_allowed_as_claim_not_proof(self):
        c=anchor()
        c["url"]=(
            "https://api.github.com/repos/"
            "aparecidomikael97-ship-it/usd-macro-pro-v4/issues/comments/10001")
        r=self.check(comments=[c])
        self.safe(r)
        self.assertEqual(r["well_formed_hash_only_anchor_comments"],1)

    def test_duplicate_same_window_anchor_never_multiples_28_opportunities(self):
        c1=anchor(cid=10001)
        c2=anchor(cid=10002,digest="b"*64)
        r=self.check(comments=[c1,c2])
        self.safe(r)
        self.assertEqual(r["ambiguous_duplicate_window_anchor_claims"],1)
        self.assertEqual(r["future_hash_anchor_claim_only_pair_slots"],28)
        self.assertEqual(r["future_not_due_pair_slots"],672)
        self.assertEqual(r["first_d1_window_state"],
                         "AMBIGUOUS_ANCHORS_UNVERIFIED")

    def test_duplicate_same_comment_id_is_rejected(self):
        c=anchor()
        r=self.check(comments=[c,deepcopy(c)])
        self.safe(r)
        self.assertEqual(r["reason"],
                         "UNKNOWN_WINDOW_OR_DUPLICATE_OR_INVALID_COMMENT_ID")

    def test_future_server_timestamp_claim_is_rejected_as_unreliable(self):
        c=anchor(created_at="2026-11-14T00:00:00Z",
                 updated_at="2026-11-14T00:00:00Z")
        r=self.check(comments=[c])
        self.safe(r)
        self.assertEqual(r["reason"],"COMMENT_TIMESTAMP_CLAIMS_INCOHERENT")

    def test_incoherent_created_after_updated_rejected(self):
        c=anchor(created_at="2026-11-13T11:19:00Z",
                 updated_at="2026-11-13T11:18:00Z")
        r=self.check(comments=[c])
        self.safe(r)
        self.assertEqual(r["reason"],"COMMENT_TIMESTAMP_CLAIMS_INCOHERENT")

    def test_bad_comments_or_clock_block_without_losing_governance(self):
        for cs in (42,{"body":"bad"},[None],[{"id":1,"body":None}]):
            r=self.check(comments=cs)
            self.safe(r)
            self.assertEqual(r["state"],"LAB_ISSUE1884_ANCHOR_CENSUS_BLOCKED")
        for now in (None,PRESTART.replace(tzinfo=None),PRESTART.replace(microsecond=1)):
            r=self.check(now=now)
            self.safe(r)
            self.assertEqual(r["state"],"LAB_ISSUE1884_ANCHOR_CENSUS_BLOCKED")

    def test_long_or_wrong_header_body_block(self):
        c=anchor()
        c["body"]+="\nUnexpected: python output"
        r=self.check(comments=[c])
        self.safe(r)
        self.assertEqual(r["reason"],
                         "MALFORMED_COMMITMENT_MARKER_NOT_ACCEPTABLE")
        c=anchor()
        c["body"]="x"*20_001
        r=self.check(comments=[c])
        self.safe(r)
        self.assertEqual(r["reason"],"COMMENT_BODY_OVERSIZED")

    def test_28_pair_universe_and_fixed_24_windows(self):
        r=self.check()
        self.safe(r)
        self.assertEqual(len(r["window_states"]),24)
        self.assertEqual(sum(row["pair_slots"] for row in r["window_states"]),672)
        self.assertEqual(len({(row["horizon"],row["window_start_utc"])
                              for row in r["window_states"]}),24)
        self.assertEqual(r["expected_pair_horizon_slots"],672)


if __name__=="__main__":
    unittest.main()
