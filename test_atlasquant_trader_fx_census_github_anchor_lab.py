"""Synthetic external-anchor gate tests: NO real GitHub comments and NO FX data."""
from dataclasses import replace
from datetime import timedelta
import unittest

from test_atlasquant_trader_fx_trial_census_lab import (
    PLAN_AT, DECISION_AT, FREEZE_AT, D1_START, plan, census,
)
from atlasquant_trader_fx_census_github_anchor_lab import (
    GitHubCommentClaim, inspect_two_stage_github_anchor_claims_lab as inspect,
    prepare_roster_github_anchor_lab as prepare_roster,
    prepare_census_github_anchor_lab as prepare_census,
)

REPO = "aparecidomikael97-ship-it/usd-macro-pro-v4"
ISSUE = 1851


def fixture():
    r = plan()["frozen"]
    c = census(r)["frozen"]
    first = prepare_roster(roster=r, repository_full_name=REPO,
                           issue_number=ISSUE, prepared_at=PLAN_AT + timedelta(minutes=1))
    second = prepare_census(roster=r, census=c, repository_full_name=REPO,
                            issue_number=ISSUE, prepared_at=FREEZE_AT + timedelta(minutes=1))
    assert first["state"] == "LAB_ROSTER_ANCHOR_TEXT_PREPARED_NOT_POSTED"
    assert second["state"] == "LAB_CENSUS_ANCHOR_TEXT_PREPARED_NOT_POSTED"
    prep={"roster_anchor_body": first["roster_anchor_body"],
          "census_anchor_body": second["census_anchor_body"]}
    def receipt(stage, identifier, when):
        return GitHubCommentClaim(
            comment_id=identifier,
            api_url=f"https://api.github.com/repos/{REPO}/issues/comments/{identifier}",
            html_url=f"https://github.com/{REPO}/pull/{ISSUE}#issuecomment-{identifier}",
            body=prep[f"{stage.lower()}_anchor_body"], created_at=when,
            updated_at=when, retrieved_at=when + timedelta(minutes=1),
        )
    first=receipt("ROSTER", 101, PLAN_AT+timedelta(minutes=30))
    second=receipt("CENSUS", 102, FREEZE_AT+timedelta(minutes=30))
    return r, c, prep, first, second


def trial(roster=None, census_blob=None, roster_comment=None, census_comment=None,
          repo=REPO, issue=ISSUE, when=D1_START):
    r,c,_,a,b=fixture()
    return inspect(roster=roster if roster is not None else r,
                   census=census_blob if census_blob is not None else c,
                   repository_full_name=repo, issue_number=issue,
                   roster_comment=a if roster_comment is None else roster_comment,
                   census_comment=b if census_comment is None else census_comment,
                   inspected_at=when)


class TwoPhaseAnchorTests(unittest.TestCase):
    def safe(self,v):
        self.assertFalse(v["external_precommitment_verified"])
        self.assertFalse(v["github_comment_fields_independently_authenticated"])
        self.assertIsNone(v["validated_directional_accuracy"])
        self.assertIsNone(v["calibrated_direction_probability"])
        self.assertEqual(v["operational_bias"],"AGUARDAR")
        self.assertFalse(v["publishable"])
        self.assertFalse(v["trade_authorized"])
        self.assertFalse(v["live_alert_allowed"])
        self.assertEqual((v["http_requests"],v["file_writes"],v["new_cost_brl"]),(0,0,0))

    def test_prepares_two_different_exact_bodies(self):
        r,c,p,a,b=fixture()
        self.assertIn("slots_expected=56",p["roster_anchor_body"])
        self.assertIn("roster_sha256="+r.sha256,p["roster_anchor_body"])
        self.assertNotIn("census_sha256=",p["roster_anchor_body"])
        self.assertIn("census_sha256="+c.sha256,p["census_anchor_body"])
        self.assertNotIn('"side"',p["census_anchor_body"])
        self.assertEqual(len(p),2)
        self.safe(trial())

    def test_consistent_claims_are_never_independent_verification(self):
        v=trial()
        self.assertEqual(v["state"],"LAB_GITHUB_TWO_ANCHOR_CHRONOLOGY_CLAIM_ONLY")
        self.assertTrue(v["roster_precedes_first_decision_claim"])
        self.assertTrue(v["census_precedes_target_claim"])
        self.assertTrue(v["comment_fields_crosschecked_documentary_only"])
        self.safe(v)

    def test_reordered_data_same_hash_and_body(self):
        r,c,p,a,b=fixture()
        p_roster=prepare_roster(roster=r,repository_full_name=REPO,
                                issue_number=ISSUE,prepared_at=PLAN_AT+timedelta(minutes=2))
        p_census=prepare_census(roster=r,census=c,repository_full_name=REPO,
                                issue_number=ISSUE,prepared_at=FREEZE_AT+timedelta(minutes=2))
        self.assertEqual(p_roster["roster_anchor_body"],p["roster_anchor_body"])
        self.assertEqual(p_census["census_anchor_body"],p["census_anchor_body"])

    def test_fabricated_future_anchor_rejected(self):
        r,c,p,a,b=fixture()
        for t in (D1_START,D1_START+timedelta(minutes=1)):
            bad=replace(b,created_at=t,updated_at=t,retrieved_at=t+timedelta(minutes=1))
            with self.subTest(t=t):
                v=trial(census_comment=bad,when=D1_START+timedelta(days=1))
                self.assertEqual(v["state"],"LAB_GITHUB_CENSUS_ANCHOR_BLOCKED")
                self.safe(v)

    def test_roster_after_first_decision_rejected(self):
        _,_,_,a,_=fixture()
        later=DECISION_AT+timedelta(minutes=1)
        v=trial(roster_comment=replace(a,created_at=later,updated_at=later,
                                       retrieved_at=later+timedelta(minutes=1)))
        self.assertEqual(v["reason"],"ROSTER_ANCHOR_MISSING_LATE_EDITED_OR_MISMATCHED")
        self.safe(v)

    def test_roster_same_second_as_first_decision_is_not_proof(self):
        _,_,_,a,_=fixture()
        self.assertEqual(trial(roster_comment=replace(a,created_at=DECISION_AT,
            updated_at=DECISION_AT,retrieved_at=DECISION_AT+timedelta(minutes=1)))["reason"],
                         "ROSTER_NOT_STRICTLY_BEFORE_FIRST_DECISION")

    def test_roster_can_be_prepared_before_census_exists(self):
        r=plan()["frozen"]
        v=prepare_roster(roster=r,repository_full_name=REPO,issue_number=ISSUE,
                         prepared_at=PLAN_AT+timedelta(minutes=5))
        self.assertEqual(v["state"],"LAB_ROSTER_ANCHOR_TEXT_PREPARED_NOT_POSTED")
        self.assertIsNone(v["census_anchor_body"])
        self.safe(v)

    def test_roster_prior_to_declared_plan_rejected(self):
        _,_,_,a,_=fixture()
        earlier=PLAN_AT-timedelta(minutes=1)
        v=trial(roster_comment=replace(a,created_at=earlier,updated_at=earlier,
                                       retrieved_at=PLAN_AT))
        self.assertEqual(v["reason"],"ROSTER_ANCHOR_MISSING_LATE_EDITED_OR_MISMATCHED")
        self.safe(v)

    def test_census_before_local_freeze_rejected(self):
        _,_,_,_,b=fixture()
        early=FREEZE_AT-timedelta(minutes=1)
        v=trial(census_comment=replace(b,created_at=early,updated_at=early,
                                       retrieved_at=FREEZE_AT))
        self.assertEqual(v["reason"],"CENSUS_ANCHOR_MISSING_LATE_EDITED_OR_MISMATCHED")

    def test_edited_comments_rejected(self):
        _,_,_,a,b=fixture()
        for field in ("roster", "census"):
            with self.subTest(field=field):
                if field=="roster":
                    v=trial(roster_comment=replace(a,updated_at=a.created_at+timedelta(seconds=1)))
                else:
                    v=trial(census_comment=replace(b,updated_at=b.created_at+timedelta(seconds=1)))
                self.assertEqual(v["state"],"LAB_GITHUB_CENSUS_ANCHOR_BLOCKED")
                self.safe(v)

    def test_body_one_byte_changed_rejected(self):
        _,_,_,a,b=fixture()
        for field in ("roster","census"):
            with self.subTest(field=field):
                v=(trial(roster_comment=replace(a,body=a.body+"X")) if field=="roster"
                   else trial(census_comment=replace(b,body=b.body+"X")))
                self.assertEqual(v["state"],"LAB_GITHUB_CENSUS_ANCHOR_BLOCKED")

    def test_rehashed_modified_census_still_mismatched_to_original_body(self):
        r,c,_,_,_=fixture()
        from dataclasses import replace as dc_replace
        from test_atlasquant_trader_fx_trial_census_lab import decisions, FREEZE_AT as f_at
        vals=decisions(r)
        vals[0]=dc_replace(vals[0],abstention_reason="STALE_DATA")
        altered=census(r,vals,at=f_at)["frozen"]
        self.assertNotEqual(altered.sha256,c.sha256)
        v=trial(census_blob=altered)
        self.assertEqual(v["state"],"LAB_GITHUB_CENSUS_ANCHOR_BLOCKED")
        self.safe(v)

    def test_url_and_repository_binding(self):
        _,_,_,a,b=fixture()
        for bad in ("https://github.com/wrong/pull/1851#issuecomment-101",
                    f"https://github.com/{REPO}/pull/1850#issuecomment-101"):
            with self.subTest(bad=bad):
                self.assertEqual(trial(roster_comment=replace(a,html_url=bad))["state"],
                                 "LAB_GITHUB_CENSUS_ANCHOR_BLOCKED")
        self.assertEqual(trial(repo="other/repository")["state"],"LAB_GITHUB_CENSUS_ANCHOR_BLOCKED")

    def test_wrong_issue_or_comment_id_rejected(self):
        _,_,_,a,b=fixture()
        for issue in (1850,0,True,"1851"):
            self.assertEqual(trial(issue=issue)["state"],"LAB_GITHUB_CENSUS_ANCHOR_BLOCKED")
        self.assertEqual(trial(roster_comment=replace(a,comment_id=102))["state"],
                         "LAB_GITHUB_CENSUS_ANCHOR_BLOCKED")

    def test_comment_id_not_reused(self):
        _,_,_,a,b=fixture()
        conflict=replace(b,comment_id=a.comment_id,api_url=a.api_url,html_url=a.html_url)
        self.assertEqual(trial(census_comment=conflict)["reason"],
                         "REUSED_COMMENT_OR_INVALID_ANCHOR_ORDER")

    def test_roster_and_census_anchor_order(self):
        _,_,_,a,b=fixture()
        later=FREEZE_AT+timedelta(minutes=31)
        # Must be more recent than roster but at/after frozen census.
        v=trial(census_comment=replace(b,created_at=later,updated_at=later,
                                       retrieved_at=later+timedelta(minutes=1)))
        self.assertEqual(v["state"],"LAB_GITHUB_TWO_ANCHOR_CHRONOLOGY_CLAIM_ONLY")

    def test_retrospective_claimed_fetch_fails(self):
        _,_,_,_,b=fixture()
        late=replace(b,retrieved_at=D1_START+timedelta(minutes=1))
        v=trial(census_comment=late,when=D1_START+timedelta(hours=1))
        self.assertEqual(v["reason"],"ANCHOR_NOT_OBSERVED_BEFORE_FIRST_TARGET")

    def test_retrieved_before_comment_creation_fails(self):
        _,_,_,a,b=fixture()
        v=trial(roster_comment=replace(a,retrieved_at=a.created_at-timedelta(seconds=1)))
        self.assertEqual(v["state"],"LAB_GITHUB_CENSUS_ANCHOR_BLOCKED")

    def test_inspection_before_retrieval_fails(self):
        v=trial(when=PLAN_AT)
        self.assertEqual(v["state"],"LAB_GITHUB_CENSUS_ANCHOR_BLOCKED")

    def test_prepare_after_target_start_fails(self):
        r,c,_,_,_=fixture()
        v=prepare_census(roster=r,census=c,repository_full_name=REPO,issue_number=ISSUE,
                  prepared_at=D1_START)
        self.assertEqual(v["reason"],"CENSUS_ANCHOR_PREPARATION_OUTSIDE_FUTURE_WINDOW")
        v2=prepare_roster(roster=r,repository_full_name=REPO,issue_number=ISSUE,
                  prepared_at=D1_START)
        self.assertEqual(v2["reason"],"ROSTER_ANCHOR_PREPARATION_OUTSIDE_FUTURE_WINDOW")

    def test_source_mismatch_or_missing_is_blocked(self):
        r,c,_,_,_=fixture()
        for rr,cc in ((r,None),(None,c),(None,None)):
            with self.subTest(rr=bool(rr),cc=bool(cc)):
                self.assertEqual(prepare_census(roster=rr,census=cc,repository_full_name=REPO,
                           issue_number=ISSUE,prepared_at=FREEZE_AT)["state"],
                           "LAB_GITHUB_CENSUS_ANCHOR_BLOCKED")

    def test_wrong_date_precision_or_naive_date(self):
        _,_,_,a,b=fixture()
        for bad in (a.created_at.replace(tzinfo=None),a.created_at+timedelta(microseconds=1)):
            with self.subTest(date=bad):
                self.assertEqual(trial(roster_comment=replace(a,created_at=bad))["state"],
                                 "LAB_GITHUB_CENSUS_ANCHOR_BLOCKED")

    def test_does_not_contact_github_or_issue_signal(self):
        _,_,_,_,_=fixture()
        v=trial()
        self.safe(v)


if __name__=="__main__":
    unittest.main()
