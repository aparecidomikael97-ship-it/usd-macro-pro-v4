"""Pure synthetic tests; no MT5, network, real forecasts or trading."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest
from atlasquant_trader_first_cohort_readiness_lab import inspect_first_cohort_readiness_lab

UTC=timezone.utc
NOW=datetime(2026,11,9,15,tzinfo=UTC)
CUR=("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD")

def fixture():
    sha=lambda v: v*64
    a={"schema":"ATLASQUANT_MT5_BACKTEST_GAP_GUARD_LAB_V1","pairs":28,"files":84,"bars":103600,
       "errors":[],"status":"CALENDAR_CONTIGUOUS_UNATTESTED","blocked_interval_counts":{}}
    broker={x:{"observed_at_utc":NOW-timedelta(hours=1),
               "target_open_utc":NOW+timedelta(days=1 if x=="D1" else 6),
               "document_sha256":sha("a")} for x in ("D1","W1")}
    macro={cur:{"published_at_utc":NOW-timedelta(days=20),
                "captured_at_utc":NOW-timedelta(days=19),
                "source_sha256":sha("b"),"indicator":"BOTH_DOCUMENTED"} for cur in CUR}
    roster={"state":"LAB_ROSTER_HASHED_UNATTESTED","sha256":sha("c"),
            "full_28fx_d1_w1_roster_checked":True}
    census={"state":"LAB_FULL_CENSUS_HASHED_UNATTESTED","sha256":sha("d"),
            "slots_recorded":56,"full_28fx_d1_w1_roster_checked":True,
            "awaiting_count":46,"hypotheses_count":10}
    github={"state":"LAB_GITHUB_TWO_ANCHOR_CHRONOLOGY_CLAIM_ONLY",
            "roster_anchor_body":"\n".join(("slots_expected=56","roster_sha256="+sha("c"))),
            "census_anchor_body":"\n".join(("slots_expected=56","roster_sha256="+sha("c"),"census_sha256="+sha("d"))),
            "roster_precedes_first_decision_claim":True,"census_precedes_target_claim":True}
    return dict(as_of_utc=NOW,decision_frozen_at=NOW-timedelta(minutes=30),archive_audit=a,broker_session=broker,
                macro_receipts=macro,roster_report=roster,census_report=census,
                github_anchor_report=github)

class ReadinessTests(unittest.TestCase):
    def assert_no_trade(self,r):
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["broker_session_source_authenticated"])
        self.assertFalse(r["macro_originals_authenticated"])
        self.assertFalse(r["github_comments_authenticated_here"])
        self.assertFalse(r["prospective_predictions_anchored_independently"])
        self.assertFalse(r["out_of_sample_accuracy_validated"])
        self.assertIsNone(r["validated_directional_accuracy"])
        self.assertIsNone(r["calibrated_direction_probability"])
        self.assertEqual((r["http_requests"],r["file_writes"],r["new_cost_brl"]),(0,0,0))

    def test_missing_everything_blocks(self):
        r=inspect_first_cohort_readiness_lab(as_of_utc=NOW)
        self.assertEqual(r["state"],"LAB_FIRST_COHORT_BLOCKED")
        self.assertEqual(len(r["blockers"]),7)
        self.assertIn("FROZEN_56_SLOT_ROSTER_MISSING",r["blockers"])
        self.assertIn("TWO_GITHUB_PRECOMMIT_ANCHORS_MISSING",r["blockers"])
        self.assert_no_trade(r)

    def test_documentary_only_can_never_allow_market_use(self):
        r=inspect_first_cohort_readiness_lab(**fixture())
        self.assertEqual(r["state"],"LAB_DOCUMENTARY_INPUT_INVENTORY_COMPLETE_UNATTESTED")
        self.assertEqual(r["reportable_coverage"]["registered_slots"],56)
        self.assertEqual(r["blockers"],[])
        self.assert_no_trade(r)

    def test_invalid_asof(self):
        for value in (None, "2026-11-09", NOW.replace(tzinfo=None),NOW+timedelta(microseconds=1)):
            with self.subTest(value=value):
                d=fixture();d["as_of_utc"]=value
                r=inspect_first_cohort_readiness_lab(**d)
                self.assertEqual(r["blockers"],["INVALID_AS_OF_CLOCK"])
                self.assert_no_trade(r)

    def test_bad_archive_and_gaps(self):
        for change in ({"files":83},{"errors":["BAD"]},{"blocked_interval_counts":{"REVIEW_UNEXPLAINED":1},"status":"BLOCKED_UNVERIFIED_GAPS"}):
            with self.subTest(change=change):
                d=fixture();d["archive_audit"].update(change)
                r=inspect_first_cohort_readiness_lab(**d)
                self.assertEqual(r["state"],"LAB_FIRST_COHORT_BLOCKED")
                self.assert_no_trade(r)

    def test_future_or_missing_broker_clocks(self):
        for value in (None,{}, {"D1":{},"W1":{}}):
            with self.subTest(value=value):
                d=fixture();d["broker_session"]=value
                r=inspect_first_cohort_readiness_lab(**d)
                self.assertTrue(any("BROKER" in x for x in r["blockers"]))
        d=fixture();d["broker_session"]["D1"]["target_open_utc"]=NOW
        self.assertIn("D1_BROKER_CLOCK_PIT_OR_HASH_INVALID",inspect_first_cohort_readiness_lab(**d)["blockers"])

    def test_only_eight_macros_accepted(self):
        d=fixture();del d["macro_receipts"]["JPY"]
        r=inspect_first_cohort_readiness_lab(**d)
        self.assertIn("EIGHT_CURRENCY_MACRO_RECEIPTS_MISSING",r["blockers"])
        d=fixture();d["macro_receipts"]["USD"]["captured_at_utc"]=NOW+timedelta(seconds=1)
        r=inspect_first_cohort_readiness_lab(**d)
        self.assertIn("USD_MACRO_RECEIPT_PIT_OR_SOURCE_INVALID",r["blockers"])

    def test_no_roster_or_census(self):
        d=fixture();d["roster_report"]=None;d["census_report"]=None
        r=inspect_first_cohort_readiness_lab(**d)
        self.assertIn("FROZEN_56_SLOT_ROSTER_MISSING",r["blockers"])
        self.assertIn("FROZEN_56_DECISION_CENSUS_MISSING",r["blockers"])
        self.assert_no_trade(r)

    def test_census_wait_must_balance(self):
        for awaiting,hypotheses in ((57,0),(50,5),(True,55),(-1,57)):
            with self.subTest(awaiting=awaiting,hypotheses=hypotheses):
                d=fixture();d["census_report"]["awaiting_count"]=awaiting
                d["census_report"]["hypotheses_count"]=hypotheses
                r=inspect_first_cohort_readiness_lab(**d)
                self.assertIn("CENSUS_ABSTENTION_ACCOUNTING_INVALID",r["blockers"])

    def test_modified_github_hashes(self):
        for field,body in (("roster_anchor_body","other"),("census_anchor_body","other")):
            with self.subTest(field=field):
                d=fixture();d["github_anchor_report"][field]=body
                r=inspect_first_cohort_readiness_lab(**d)
                self.assertIn("GITHUB_ANCHOR_HASHES_OR_CHRONOLOGY_INVALID",r["blockers"])
        d=fixture();d["github_anchor_report"]["state"]="LAB_GITHUB_CENSUS_ANCHOR_BLOCKED"
        self.assertIn("TWO_GITHUB_PRECOMMIT_ANCHORS_MISSING",inspect_first_cohort_readiness_lab(**d)["blockers"])

    def test_macro_captured_after_prediction_freeze_is_rejected(self):
        d=fixture()
        d["macro_receipts"]["USD"]["captured_at_utc"]=NOW-timedelta(minutes=1)
        self.assertIn("USD_MACRO_RECEIPT_PIT_OR_SOURCE_INVALID",
            inspect_first_cohort_readiness_lab(**d)["blockers"])

    def test_missing_or_future_freeze_clock_blocks(self):
        for clock in (None,NOW+timedelta(seconds=2),NOW.replace(tzinfo=None)):
            d=fixture();d["decision_frozen_at"]=clock
            r=inspect_first_cohort_readiness_lab(**d)
            self.assertIn("CENSUS_FREEZE_CLOCK_MISSING_OR_FUTURE",r["blockers"])
            self.assert_no_trade(r)

    def test_broker_clock_observed_after_freeze_is_rejected(self):
        d=fixture();d["broker_session"]["W1"]["observed_at_utc"]=NOW-timedelta(minutes=1)
        r=inspect_first_cohort_readiness_lab(**d)
        self.assertIn("W1_BROKER_CLOCK_PIT_OR_HASH_INVALID",r["blockers"])

    def test_invalid_recipient_types_fail_closed(self):
        for key in ("archive_audit","broker_session","macro_receipts","roster_report","census_report","github_anchor_report"):
            d=fixture();d[key]=True
            r=inspect_first_cohort_readiness_lab(**d)
            self.assertNotEqual(r["blockers"],[])
            self.assert_no_trade(r)

if __name__=="__main__": unittest.main()
