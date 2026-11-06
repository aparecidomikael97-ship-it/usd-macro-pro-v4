"""No-lookahead checks for documentary NFP, Reuters survey, ADP and JOLTS."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import unittest

from atlasquant_trader_us_nfp_prepost_pit_lab import (
    EXPECTED, KIND, RECORDS, SCHEMA,
    inspect_us_nfp_oct2026_prepost_lab as inspect,
)

RAW = Path(__file__).resolve().parent.joinpath(
    "docs/continuidade/TRADER_US_NFP_OCT2026_PREPOST_DOCUMENTARY_CASE_LAB.json"
).read_bytes()
Z = timezone.utc


def clock(day, hour, minute=0, second=0):
    return datetime(2026, 11, day, hour, minute, second, tzinfo=Z)


def encoded(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def audit(*, at=None, obj=None):
    return inspect(RAW if obj is None else encoded(obj),
                   as_of_utc=at if at is not None else clock(6, 14))


class UsNfpPrePostDocumentaryTests(unittest.TestCase):
    def assert_closed(self, out):
        for field in ("adp_and_nfp_populations_identical",
                      "jolts_and_nfp_periods_identical",
                      "pre_release_survey_page_historically_witnessed",
                      "bls_release_original_bytes_authenticated",
                      "consensus_data_product_license_verified",
                      "market_price_reaction_independently_verified",
                      "surprise_transmission_to_usd_direction_verified",
                      "forward_predictive_accuracy_verified", "trade_authorized",
                      "can_feed_live_radar", "publishable", "worker_enabled",
                      "scheduler_enabled"):
            self.assertIs(out[field], False, field)
        for field in ("validated_accuracy", "market_surprise_independently_verified",
                      "policy_repricing_impulse", "usd_strength", "fx_bias"):
            self.assertIsNone(out[field], field)
        self.assertEqual(out["validated_prediction_count"], 0)
        self.assertEqual(out["operational_bias"], "AGUARDAR")
        self.assertEqual((out["http_requests"], out["new_cost_brl"]), (0, 0))

    def test_fixed_casebook_preserves_four_distinct_source_roles(self):
        self.assertEqual(json.loads(RAW), EXPECTED)
        self.assertEqual(EXPECTED["schema"], SCHEMA)
        self.assertEqual(EXPECTED["data_kind"], KIND)
        self.assertEqual(len(RECORDS), 4)
        self.assertEqual(len({r["document_role"] for r in RECORDS}), 4)
        self.assertFalse(EXPECTED["original_source_bytes_archived"])
        self.assertFalse(EXPECTED["pre_event_page_capture_independently_witnessed"])
        self.assertFalse(EXPECTED["source_content_product_license_verified"])

    def test_before_jolts_none_documented_for_this_case(self):
        out = audit(at=clock(3, 14, 59, 59))
        self.assertEqual(out["documentary_records_not_before_asof"], [])
        self.assertEqual(len(out["future_documentary_records_excluded"]), 4)
        self.assertIsNone(out["documentary_nfp_forecast_persons"])
        self.assertIsNone(out["documentary_nfp_actual_persons"])
        self.assert_closed(out)

    def test_jolts_from_november_third_cannot_count_as_nfp_forecast(self):
        out = audit(at=clock(3, 15))
        self.assertEqual(out["documentary_records_not_before_asof"],
                         ["BLS_SEP2026_JOLTS_RELEASE"])
        self.assertFalse(out["reuters_pre_release_survey_document_present"])
        self.assertIsNone(out["nfp_result_minus_reuters_survey_persons_unverified"])
        self.assert_closed(out)

    def test_adp_available_before_reuters_survey_but_not_nfp_consensus(self):
        before = audit(at=clock(4, 13, 14, 59))
        after = audit(at=clock(4, 13, 15))
        self.assertEqual(len(before["documentary_records_not_before_asof"]), 1)
        self.assertEqual(len(after["documentary_records_not_before_asof"]), 2)
        self.assertFalse(after["reuters_pre_release_survey_document_present"])
        self.assertEqual(after["pre_release_independent_leads_available_as_documents"],
                         ["BLS_SEP2026_JOLTS_RELEASE", "ADP_OCT2026_PRIVATE_PAYROLL_RELEASE"])
        self.assert_closed(after)

    def test_reuters_conservative_not_before_1400_november_four(self):
        before = audit(at=clock(4, 13, 59, 59))
        after = audit(at=clock(4, 14))
        self.assertFalse(before["reuters_pre_release_survey_document_present"])
        self.assertTrue(after["reuters_pre_release_survey_document_present"])
        self.assertEqual(after["documentary_nfp_forecast_persons"], "65000")
        self.assertIsNone(after["documentary_nfp_actual_persons"])
        self.assert_closed(after)

    def test_forecast_visible_on_november_fifth_but_no_outcome_known(self):
        out = audit(at=clock(5, 12))
        self.assertEqual(out["state"], "LAB_PRE_RELEASE_CONTEXT_ONLY_NO_OUTCOME")
        self.assertEqual(out["documentary_nfp_forecast_persons"], "65000")
        self.assertEqual(out["pre_release_independent_leads_available_as_documents"],
                         ["BLS_SEP2026_JOLTS_RELEASE", "ADP_OCT2026_PRIVATE_PAYROLL_RELEASE"])
        self.assertIsNone(out["nfp_result_minus_reuters_survey_persons_unverified"])
        self.assert_closed(out)

    def test_one_second_before_bls_embargo_no_actual_or_gap(self):
        out = audit(at=clock(6, 13, 29, 59))
        self.assertFalse(out["bls_nfp_result_after_release_document_present"])
        self.assertIsNone(out["documentary_nfp_actual_persons"])
        self.assertIsNone(out["unemployment_result_minus_reuters_survey_pp_unverified"])
        self.assert_closed(out)

    def test_at_bls_embargo_documentary_arithmetic_plus_100000_and_minus_point_one(self):
        out = audit(at=clock(6, 13, 30))
        self.assertEqual(out["state"], "LAB_POST_RELEASE_SURVEY_GAP_ARITHMETIC_UNATTESTED")
        self.assertEqual(out["documentary_nfp_forecast_persons"], "65000")
        self.assertEqual(out["documentary_nfp_actual_persons"], "165000")
        self.assertEqual(out["nfp_result_minus_reuters_survey_persons_unverified"], "100000")
        self.assertEqual(out["unemployment_result_minus_reuters_survey_pp_unverified"], "-0.1")
        self.assertEqual(out["future_documentary_records_excluded"], [])
        self.assertEqual(out["casebook_sha256"], sha256(RAW).hexdigest())
        self.assert_closed(out)

    def test_28_fx_pairs_are_not_a_claim_of_28_independent_us_sources(self):
        out = audit()
        self.assertEqual(out["usd_canonical_pair_count"], 7)
        self.assertIsNone(out["usd_strength"])
        self.assertIsNone(out["fx_bias"])
        self.assert_closed(out)

    def test_actual_and_reuters_forecast_are_same_period_but_adp_and_jolts_are_not(self):
        self.assertEqual(RECORDS[2]["reference_period"], "2026-10")
        self.assertEqual(RECORDS[3]["reference_period"], "2026-10")
        self.assertEqual(RECORDS[0]["reference_period"], "2026-09")
        self.assertEqual(RECORDS[1]["reported_values"],
                         {"private_payroll_change_persons": "86000"})
        self.assertEqual(RECORDS[2]["reported_values"]["nonfarm_payroll_forecast_persons_sa"], "65000")
        self.assert_closed(audit())

    def test_mutating_numbers_times_source_or_license_is_rejected(self):
        for idx,field,value in (
            (0,"public_not_before_utc","2026-11-02T15:00:00Z"),
            (1,"source_url","https://faked.example"),
            (2,"public_not_before_utc","2026-11-06T14:00:00Z"),
            (2,"reported_values",{"nonfarm_payroll_forecast_persons_sa":"165000"}),
            (3,"reported_values",{"nonfarm_payroll_actual_persons_sa":"65000"}),
            (3,"reference_period","2026-09"),
        ):
            obj = deepcopy(EXPECTED)
            obj["records"][idx][field] = value
            self.assertEqual(audit(obj=obj)["state"], "LAB_BLOCKED", field)
        obj = deepcopy(EXPECTED)
        obj["source_content_product_license_verified"] = True
        self.assertEqual(audit(obj=obj)["state"], "LAB_BLOCKED")

    def test_no_extra_probability_or_trade_authority_can_be_inserted(self):
        obj = deepcopy(EXPECTED)
        obj["probability_of_usd_rise"] = "0.9"
        self.assertEqual(audit(obj=obj)["state"], "LAB_BLOCKED")
        obj = deepcopy(EXPECTED)
        obj["records"].append(deepcopy(obj["records"][0]))
        self.assertEqual(audit(obj=obj)["state"], "LAB_BLOCKED")

    def test_duplicate_json_malformed_nan_and_naive_asof_blocked(self):
        for candidate in (b'{', b'\xff', b'{"schema":NaN}',
                          RAW[:-2] + b',"schema":"OVERRIDE"}'):
            out = inspect(candidate, as_of_utc=clock(6, 14))
            self.assertEqual(out["state"], "LAB_BLOCKED")
            self.assert_closed(out)
        for invalid_time in (None, "2026-11-06", clock(6, 14).replace(tzinfo=None)):
            out = inspect(RAW, as_of_utc=invalid_time)
            self.assertEqual(out["state"], "LAB_BLOCKED")
            self.assert_closed(out)

    def test_timezone_aware_brazilian_clock_same_event_boundary(self):
        mana = timezone(timedelta(hours=-4))
        out = inspect(RAW, as_of_utc=clock(6, 13, 30).astimezone(mana))
        self.assertEqual(out["nfp_result_minus_reuters_survey_persons_unverified"], "100000")
        self.assert_closed(out)


if __name__ == "__main__":
    unittest.main()
