"""Brazil pre-Copom reported Focus revision / Reuters meeting-poll separation."""
from __future__ import annotations

import copy
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from atlasquant_trader_brazil_focus_secondary_triage_lab import (
    SCHEMA, STATE, DENIED, REPORTED_NEW, REUTERS_REPORTED_POLL,
    triage_reported_focus_revision_lab as triage,
)

NOW = datetime(2026, 11, 3, 16, tzinfo=timezone.utc)


def find(r, indicator, period):
    return next(x for x in r["revision_rows"]
                if x["indicator"] == indicator and x["target_period"] == period)


class BrazilFocusSecondaryTriageLabTests(unittest.TestCase):
    def test_eight_annual_new_medians_are_secondary_documentary_only(self):
        r = triage(at=NOW)
        self.assertEqual((r["schema"], r["state"]), (SCHEMA, STATE))
        self.assertEqual(r["revision_count"], 8)
        self.assertEqual(len(r["revision_rows"]), 8)
        self.assertEqual(r["new_reported_focus_reference"], "2026-10-30")
        self.assertEqual(r["old_focus_reference"], "2026-10-23")
        self.assertFalse(r["focus_new_original_pdf_authenticated"])
        self.assertFalse(r["focus_new_odataset_original_authenticated"])

    def test_2026_ipca_higher_by_three_hundredths_of_point(self):
        x = find(triage(at=NOW), "IPCA", "2026")
        self.assertEqual(x["old_official_value"], "5.19")
        self.assertEqual(x["new_secondary_report_value"], "5.22")
        self.assertEqual(Decimal(x["signed_revision"]), Decimal("0.03"))
        self.assertEqual(x["signed_revision_unit"], "PERCENTAGE_POINTS")

    def test_2027_ipca_higher_by_042_percentage_point(self):
        x = find(triage(at=NOW), "IPCA", "2027")
        self.assertEqual(x["old_official_value"], "4.34")
        self.assertEqual(x["new_secondary_report_value"], "4.76")
        self.assertEqual(Decimal(x["signed_revision"]), Decimal("0.42"))

    def test_2026_year_end_selic_not_copom_meeting_rate(self):
        x = find(triage(at=NOW), "SELIC", "2026")
        self.assertEqual(x["target_type"], "YEAR_END_POLICY_TARGET")
        self.assertEqual((x["old_official_value"], x["new_secondary_report_value"]),
                         ("13.25", "13.50"))
        self.assertEqual(Decimal(x["signed_revision"]), Decimal("0.25"))
        self.assertFalse(x["is_next_meeting_consensus"])

    def test_2027_year_end_selic_not_current_policy_rate(self):
        x = find(triage(at=NOW), "SELIC", "2027")
        self.assertEqual((x["old_official_value"], x["new_secondary_report_value"]),
                         ("11.75", "12.50"))
        self.assertEqual(Decimal(x["signed_revision"]), Decimal("0.75"))
        self.assertFalse(x["is_next_meeting_consensus"])

    def test_2026_annual_fx_is_december_average_not_usdbrl_spot(self):
        x = find(triage(at=NOW), "FX_BRL_PER_USD", "2026")
        self.assertEqual(x["target_type"], "DECEMBER_AVERAGE_FX")
        self.assertEqual((x["old_official_value"], x["new_secondary_report_value"]),
                         ("5.05", "5.34"))
        self.assertEqual(Decimal(x["signed_revision"]), Decimal("0.29"))
        self.assertEqual(x["signed_revision_unit"], "BRL_PER_USD")
        self.assertFalse(x["is_fx_spot_quote"])

    def test_2027_fx_december_average(self):
        x = find(triage(at=NOW), "FX_BRL_PER_USD", "2027")
        self.assertEqual((x["old_official_value"], x["new_secondary_report_value"]),
                         ("5.15", "5.40"))
        self.assertEqual(Decimal(x["signed_revision"]), Decimal("0.25"))

    def test_2026_gdp_reduced(self):
        x = find(triage(at=NOW), "REAL_GDP", "2026")
        self.assertEqual((x["old_official_value"], x["new_secondary_report_value"]),
                         ("1.80", "1.76"))
        self.assertEqual(Decimal(x["signed_revision"]), Decimal("-0.04"))
        self.assertEqual(x["direction_of_revision"], "DOWN")

    def test_2027_gdp_reduced(self):
        x = find(triage(at=NOW), "REAL_GDP", "2027")
        self.assertEqual((x["old_official_value"], x["new_secondary_report_value"]),
                         ("1.31", "1.20"))
        self.assertEqual(Decimal(x["signed_revision"]), Decimal("-0.11"))
        self.assertEqual(x["direction_of_revision"], "DOWN")

    def test_poll_33_of_48_is_respondent_share_not_market_probability(self):
        poll = triage(at=NOW)["meeting_survey"]
        self.assertEqual(poll["target_meeting"], "2026-11-04")
        self.assertEqual(poll["hold_responses"], 33)
        self.assertEqual(poll["all_respondents"], 48)
        self.assertEqual(poll["hold_respondent_share_pct"], "68.75")
        self.assertFalse(poll["hold_respondent_share_is_event_probability"])
        self.assertIsNone(poll["market_implied_probability"])

    def test_reuters_meeting_poll_not_identical_to_2026_focus_year_end(self):
        r = triage(at=NOW)
        x = find(r, "SELIC", "2026")
        self.assertEqual(r["meeting_survey"]["survey_current_selic_pct_aa"], "13.75")
        self.assertEqual(x["new_secondary_report_value"], "13.50")
        self.assertIn("different date", r["meeting_survey"]["explicit_difference_from_focus"])
        self.assertIsNone(r["meeting_consensus_from_two_distinct_sources_agreed"])

    def test_source_urls_are_explicitly_secondary(self):
        r = triage(at=NOW)
        self.assertEqual(len(r["new_focus_secondary_source_urls"]), 2)
        self.assertTrue(all(x.startswith("https://") for x in r["new_focus_secondary_source_urls"]))
        self.assertIn("reuters.com", r["meeting_survey"]["source_url"])
        self.assertTrue(r["requires_official_focus_pdf_or_odata"])

    def test_no_new_report_claims_source_origin_attested(self):
        r = triage(at=NOW)
        self.assertIsNone(r["focus_new_original_pdf_sha256"])
        self.assertFalse(r["new_source_publication_time_independently_attested"])
        self.assertTrue(all(not x["new_report_is_primary_source_authenticated"]
                            for x in r["revision_rows"]))

    def test_cannot_backdate_nov3_research_to_nov2(self):
        r = triage(at=datetime(2026, 11, 2, 23, 59, tzinfo=timezone.utc))
        self.assertEqual(r["state"], DENIED)
        self.assertFalse(r["trade_authorized"])

    def test_can_evaluate_on_research_date_without_inventing_precise_capture(self):
        r = triage(at=datetime(2026,11,3,0,tzinfo=timezone.utc))
        self.assertEqual(r["state"], STATE)
        self.assertFalse(r["new_source_publication_time_independently_attested"])
        self.assertFalse(r["can_feed_live_radar"])

    def test_clock_without_timezone_rejected(self):
        with self.assertRaises(ValueError):
            triage(at=datetime(2026,11,3,15))

    def test_forged_ninth_indicator_rejected(self):
        payload = list(REPORTED_NEW) + [("CPI", "OTHER", "2026", "9", "PCT")]
        self.assertEqual(triage(at=NOW, new_reports=payload)["state"], DENIED)

    def test_forged_new_selic_and_exchange_rate_rejected(self):
        for index in (2,4):
            new = list(REPORTED_NEW)
            row = list(new[index])
            row[3] = "99.99"
            new[index] = tuple(row)
            self.assertEqual(triage(at=NOW, new_reports=new)["state"], DENIED)

    def test_fake_changed_indicator_unit_or_period_rejected(self):
        for col, replacement in ((0,"UNEMPLOYMENT"), (1,"MONTH_END"), (2,"2028"), (4,"POINTS")):
            new = list(REPORTED_NEW)
            row = list(new[0])
            row[col] = replacement
            new[0] = tuple(row)
            self.assertEqual(triage(at=NOW, new_reports=new)["state"], DENIED)

    def test_missing_and_reordered_rows_are_refused(self):
        self.assertEqual(triage(at=NOW, new_reports=REPORTED_NEW[:-1])["state"], DENIED)
        self.assertEqual(triage(at=NOW, new_reports=list(reversed(REPORTED_NEW)))["state"], DENIED)

    def test_forged_reuters_poll_sample_counts_refused(self):
        for field,value in (
            ("hold_at_current_rate_responses", 48),
            ("total_responses", 33),
            ("current_selic_pct_aa", "13.50"),
            ("respondents_meeting_expectation", "CUT_13_50"),
        ):
            p = copy.deepcopy(REUTERS_REPORTED_POLL)
            p[field] = value
            self.assertEqual(triage(at=NOW, reuters_poll=p)["state"], DENIED)

    def test_poll_extra_probabilities_or_performance_not_admitted(self):
        for field in ("likelihood_pct", "directional_probability", "brazil_fiscal_sentiment"):
            p = copy.deepcopy(REUTERS_REPORTED_POLL)
            p[field] = 100
            self.assertEqual(triage(at=NOW, reuters_poll=p)["state"], DENIED)

    def test_no_future_copom_result_allowed(self):
        p = copy.deepcopy(REUTERS_REPORTED_POLL)
        p["copom_actual"] = "13.50"
        r = triage(at=NOW, reuters_poll=p)
        self.assertEqual(r["state"], DENIED)
        self.assertFalse(r["copom_result_known"])

    def test_none_and_bad_new_report_shapes_denied(self):
        for new in ([], {}, "5.22", [1]*8, [None]*8):
            self.assertEqual(triage(at=NOW, new_reports=new)["state"], DENIED)

    def test_invalid_poll_shape_denied(self):
        for poll in ([], {}, 1, "wrong", {"hold_at_current_rate_responses":33}):
            self.assertEqual(triage(at=NOW, reuters_poll=poll)["state"], DENIED)

    def test_no_bias_trading_paid_data_or_render_changes(self):
        r = triage(at=NOW)
        self.assertEqual(r["real_fx_or_index_bias"], "AGUARDAR")
        self.assertIsNone(r["probability_calibrated"])
        self.assertIsNone(r["next_copom_consensus_percent_from_focus"])
        self.assertIsNone(r["market_implied_copom_probability"])
        for f in (
            "can_feed_live_radar", "can_feed_real_oos",
            "trade_authorized", "worker_enabled", "scheduler_enabled",
            "render_configuration_changed", "paid_provider_approved",
        ):
            self.assertFalse(r[f], f)


if __name__ == "__main__":
    unittest.main()
