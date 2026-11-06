"""Synthetic chronological cases. No real forecasts or FX signal."""
from __future__ import annotations

from datetime import datetime, timezone
import unittest

from atlasquant_trader_eurusd_consensus_pit_lab import (
    audit_policy_consensus_pit_lab as audit,
    compare_eurusd_consensus_pit_lab as compare,
)

UTC = timezone.utc
NOW = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)


def dt(day: int, hour: int = 10, month: int = 10) -> datetime:
    return datetime(2026, month, day, hour, tzinfo=UTC)


def candidate(**overrides):
    args = {
        "source_id": "INDEPENDENT_PRE_EVENT_CANDIDATE_EUR",
        "currency": "EUR", "event_date": "2026-10-29",
        "as_of_utc": NOW, "published_at_utc": dt(27),
        "captured_at_utc": dt(28), "publication_kind": "CLAIMED_OBSERVED",
        "raw_document": b"SYNTHETIC STUDY ONLY: not an actual consensus",
        "survey_closed_at_utc": dt(26),
    }
    args.update(overrides)
    return audit(**args)


class ConsensusPitTests(unittest.TestCase):
    def test_early_candidate_still_has_no_pit_proof_or_fx_bias(self):
        r = candidate()
        self.assertEqual(r["state"], "LAB_PRE_EVENT_CHRONOLOGY_PLAUSIBLE_UNVERIFIED")
        self.assertEqual(len(r["document_sha256"]), 64)
        for key in ("pre_event_consensus_verified", "historical_point_in_time_eligible",
                    "public_availability_independently_verified", "trade_authorized",
                    "can_feed_live_radar", "publishable"):
            self.assertFalse(r[key])
        self.assertIsNone(r["market_surprise_bps"])
        self.assertIsNone(r["fx_bias"])

    def test_2026_ecb_sma_october_scheduled_october_thirty_is_post_event(self):
        r = candidate(
            source_id="ECB_SMA_AGGREGATE", event_date="2026-10-29",
            published_at_utc=dt(30), captured_at_utc=dt(31),
            publication_kind="INDICATIVE_SCHEDULE",
        )
        self.assertEqual(r["reason"], "DOCUMENT_NOT_PUBLIC_BEFORE_EVENT_DATE")
        self.assertFalse(r["historical_point_in_time_eligible"])

    def test_new_york_fed_2025_onwards_is_sme_and_results_are_post_event(self):
        r = candidate(
            source_id="NYFED_SME_AGGREGATE", currency="USD",
            event_date="2026-10-28", published_at_utc=dt(30),
            captured_at_utc=dt(31),
        )
        self.assertEqual(r["reason"], "DOCUMENT_NOT_PUBLIC_BEFORE_EVENT_DATE")

    def test_new_york_old_spd_results_also_not_pre_event(self):
        r = candidate(
            source_id="NYFED_SPD_AGGREGATE_LEGACY", currency="USD",
            published_at_utc=dt(20), captured_at_utc=dt(22),
            survey_closed_at_utc=dt(19),
        )
        self.assertEqual(r["reason"], "OFFICIAL_AGGREGATE_NORMALLY_PUBLISHED_POST_EVENT")

    def test_ecb_forged_early_published_time_does_not_override_survey_practice(self):
        r = candidate(source_id="ECB_SMA_AGGREGATE")
        self.assertEqual(r["reason"], "OFFICIAL_AGGREGATE_NORMALLY_PUBLISHED_POST_EVENT")

    def test_ecb_public_ois_aggregates_cannot_imply_same_day_market_consensus(self):
        for source, reason in (
            ("ECB_MMSR_OIS_SPOT_MP_AGGREGATE",
             "OIS_MAINTENANCE_PERIOD_AGGREGATE_RELEASE_LAG"),
            ("ECB_MMSR_OIS_FORWARD_QUARTER_AGGREGATE",
             "OIS_FORWARD_QUARTER_AGGREGATE_RELEASE_LAG"),
            ("ECB_EMMS_OIS_ANNUAL_HISTORY",
             "OIS_ANNUAL_HISTORICAL_UPDATE_NOT_EVENT_CONSENSUS"),
        ):
            with self.subTest(source=source):
                r = candidate(source_id=source)
                self.assertEqual(r["reason"], reason)
                self.assertFalse(r["source_measure_is_event_consensus_verified"])
                self.assertFalse(r["historical_point_in_time_eligible"])

    def test_ecb_realized_estr_and_sovereign_forward_are_not_dfr_expectations(self):
        for source, reason in (
            ("ECB_ESTR_REALIZED_OVERNIGHT", "REALIZED_ESTR_NOT_POLICY_EXPECTATION"),
            ("ECB_YC_SOVEREIGN_BOND_FORWARD",
             "GOVERNMENT_BOND_FORWARD_NOT_OIS_POLICY_EXPECTATION"),
        ):
            with self.subTest(source=source):
                r = candidate(source_id=source)
                self.assertEqual(r["reason"], reason)
                self.assertFalse(r["pre_event_consensus_verified"])
                self.assertIsNone(r["fx_bias"])

    def test_eurex_fst3_price_is_quarter_accrual_not_one_ecb_meeting_consensus(self):
        r = candidate(source_id="EUREX_FST3_DAILY_SETTLEMENT")
        self.assertEqual(
            r["reason"],
            "ESTR_FUTURES_ACCRUAL_NOT_SINGLE_MEETING_DFR_CONSENSUS",
        )
        for key in ("futures_contract_expiry_and_accrual_verified",
                    "historical_price_publication_instant_verified",
                    "market_data_product_license_verified", "trade_authorized"):
            self.assertFalse(r[key])
        self.assertIsNone(r["market_surprise_bps"])

    def test_eurex_public_daily_volume_does_not_substitute_a_settlement_price(self):
        r = candidate(source_id="EUREX_FST3_DAILY_TRADING_STATISTICS")
        self.assertEqual(r["reason"], "FST3_VOLUME_AND_OPEN_INTEREST_NOT_PRICE")
        self.assertFalse(r["source_measure_is_event_consensus_verified"])
        self.assertIsNone(r["fx_bias"])

    def test_ice_report_center_cannot_be_used_as_product_feed_without_permission(self):
        r = candidate(source_id="ICE_REPORT_CENTER_ESTR_FUTURES_SETTLEMENT")
        self.assertEqual(r["reason"], "ICE_MARKET_DATA_PRODUCT_PERMISSION_NOT_VERIFIED")
        self.assertFalse(r["market_data_product_license_verified"])
        self.assertFalse(r["can_feed_live_radar"])
        self.assertIsNone(r["fx_bias"])

    def test_futures_report_after_meeting_fails_chronology_before_semantics(self):
        r = candidate(source_id="EUREX_FST3_DAILY_SETTLEMENT",
                      published_at_utc=dt(30), captured_at_utc=dt(31))
        self.assertEqual(r["reason"], "DOCUMENT_NOT_PUBLIC_BEFORE_EVENT_DATE")

    def test_futures_same_day_ecb_decision_still_needs_witnessed_release_instant(self):
        r = candidate(source_id="EUREX_FST3_DAILY_SETTLEMENT",
                      published_at_utc=dt(29, 8), captured_at_utc=dt(29, 9))
        self.assertEqual(r["reason"], "SAME_DAY_ORDER_NEEDS_WITNESSED_EVENT_TIME")

    def test_questions_published_early_are_not_claimed_consensus_aggregate(self):
        r = candidate(source_id="NYFED_SME_QUESTIONNAIRE", currency="USD")
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assertIsNone(r["document_sha256"])

    def test_scheduled_before_event_is_still_not_a_publication(self):
        r = candidate(publication_kind="INDICATIVE_SCHEDULE")
        self.assertEqual(r["reason"], "SCHEDULE_IS_NOT_ACTUAL_PUBLICATION")

    def test_same_day_publish_even_before_a_claimed_time_requires_event_witness(self):
        r = candidate(published_at_utc=dt(29, 8), captured_at_utc=dt(29, 9))
        self.assertEqual(r["reason"], "SAME_DAY_ORDER_NEEDS_WITNESSED_EVENT_TIME")

    def test_post_event_capture_cannot_recreate_pre_event_availability(self):
        r = candidate(published_at_utc=dt(26), captured_at_utc=dt(30))
        self.assertEqual(r["reason"], "DOCUMENT_NOT_PUBLIC_BEFORE_EVENT_DATE")

    def test_capture_before_claimed_publication_rejected(self):
        r = candidate(published_at_utc=dt(28), captured_at_utc=dt(27))
        self.assertEqual(r["reason"], "DOCUMENT_CAPTURE_BEFORE_CLAIMED_PUBLICATION")

    def test_survey_close_time_is_not_a_publication_time(self):
        r = candidate(survey_closed_at_utc=dt(28))
        self.assertEqual(r["reason"], "SURVEY_CLOSED_AFTER_CLAIMED_PUBLICATION")

    def test_future_claim_relative_to_asof_rejected(self):
        r = candidate(captured_at_utc=dt(6, month=11))
        self.assertEqual(r["reason"], "FUTURE_METADATA_RELATIVE_TO_AS_OF")

    def test_naive_clocks_rejected(self):
        for field in ("as_of_utc", "published_at_utc", "captured_at_utc",
                      "survey_closed_at_utc"):
            with self.subTest(field=field):
                r = candidate(**{field: dt(26).replace(tzinfo=None)})
                self.assertEqual(r["reason"], "INVALID_INPUT")

    def test_bad_dates_and_source_currency_swaps_rejected(self):
        for change in ({"event_date": "2026-10-35"},
                       {"event_date": "2026-2-3"},
                       {"source_id": "NYFED_SME_AGGREGATE"},
                       {"currency": "USD"},
                       {"source_id": ["ECB_SMA_AGGREGATE"]},
                       {"currency": ["EUR"]},
                       {"source_id": None},
                       {"publication_kind": "WITNESSED_BY_CALLER"}):
            with self.subTest(change=change):
                self.assertEqual(candidate(**change)["reason"], "INVALID_INPUT")

    def test_document_bytes_must_be_present_nonempty_and_bounded(self):
        for document in (None, b"", "text not bytes", b"x" * (256 * 1024 + 1)):
            with self.subTest(length=len(document) if document is not None else None):
                self.assertEqual(candidate(raw_document=document)["reason"],
                                 "INVALID_INPUT")

    def test_missing_source_timestamp_cannot_infer_from_survey_window(self):
        r = candidate(published_at_utc=None)
        self.assertEqual(r["reason"], "INVALID_INPUT")

    def test_bilateral_even_both_plausible_still_not_authorized(self):
        e = candidate()
        u = candidate(source_id="INDEPENDENT_PRE_EVENT_CANDIDATE_USD",
                      currency="USD", event_date="2026-10-28",
                      published_at_utc=dt(26), captured_at_utc=dt(27),
                      survey_closed_at_utc=dt(25))
        r = compare(e, u)
        self.assertEqual(r["state"], "LAB_BILATERAL_CONSENSUS_CHRONOLOGY_UNVERIFIED")
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["historical_point_in_time_eligible"])
        self.assertIsNone(r["market_surprise_bps"])

    def test_bilateral_blocked_if_one_post_event(self):
        u = candidate(source_id="NYFED_SME_AGGREGATE", currency="USD",
                      event_date="2026-10-28", published_at_utc=dt(30),
                      captured_at_utc=dt(31))
        r = compare(candidate(), u)
        self.assertEqual(r["state"], "LAB_BILATERAL_CONSENSUS_BLOCKED")
        self.assertEqual(r["usd_reason"], "DOCUMENT_NOT_PUBLIC_BEFORE_EVENT_DATE")

    def test_bilateral_requires_right_currency_and_schema(self):
        r = compare(candidate(), candidate())
        self.assertEqual(r["state"], "LAB_BILATERAL_CONSENSUS_BLOCKED")
        self.assertIsNone(r["eur_reason"])


if __name__ == "__main__":
    unittest.main()
