"""Offline ONS /previous-link identity and calendar-only guard tests."""
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_ons_gbp_archived_link_catalog_lab import (
    LISTING_URL, SCHEMA, plan_ons_gbp_archived_source_leads_lab as plan,
)

EVALUATED = datetime(2026, 11, 5, 13, tzinfo=timezone.utc)


def clock(month=10, day=20, hour=12, tz=timezone.utc):
    return datetime(2026, month, day, hour, tzinfo=tz)


def run(asof=None, evaluated=EVALUATED, version_id=None):
    return plan(historical_as_of_utc=clock() if asof is None else asof,
                evaluated_at_utc=evaluated, version_id=version_id)


class ArchivedOnsLinksTests(unittest.TestCase):
    def assert_no_bias(self, r):
        for field in (
            "source_bytes_downloaded", "original_archived_payload_verified",
            "official_origin_independently_verified",
            "individual_publication_instant_verified",
            "historical_point_in_time_available_verified",
            "commercial_redistribution_rights_verified", "usable_for_backtest",
            "trade_authorized", "can_feed_live_radar", "worker_enabled",
            "scheduler_enabled", "publishable",
        ):
            self.assertIs(r[field], False, field)
        self.assertIsNone(r["fx_bias"])
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertEqual((r["external_http_requests"], r["new_cost_brl"]), (0, 0))

    def test_all_four_versions_exact_ids_and_supersession_dates(self):
        r = run()
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["state"], "LAB_ONS_PREVIOUS_LINK_LEADS_QUARANTINED")
        self.assertEqual(r["catalog_entries_count"], 4)
        self.assertEqual([(x["version_id"], x["superseded_on_calendar_date_only"])
                          for x in r["catalog_entries"]], [
            ("v131", "2026-10-21"), ("v130", "2026-09-16"),
            ("v129", "2026-08-19"), ("v128", "2026-07-22"),
        ])
        self.assert_no_bias(r)

    def test_urls_are_pinned_to_real_official_page_paths(self):
        r = run()
        self.assertEqual(r["source_listing_url"], LISTING_URL)
        for x in r["catalog_entries"]:
            self.assertEqual(
                x["official_archive_download_url_candidate"],
                "https://www.ons.gov.uk/generator?format=csv&uri=%2Feconomy%2F"
                "inflationandpriceindices%2Ftimeseries%2Fd7g7%2Fmm23%2Fprevious%2F"
                + x["version_id"],
            )
            self.assertIs(x["superseded_is_not_publication_instant"], True)
            self.assertIs(x["historical_availability_proven"], False)
            self.assertIs(x["original_bytes_observed"], False)

    def test_before_october_supersession_is_only_a_candidate(self):
        x = run(version_id="v131")["catalog_entries"][0]
        self.assertEqual(x["status_relative_to_historical_cutoff"],
                         "BEFORE_SUPERSESSION_UPPER_BOUND_ONLY_NO_PROOF")

    def test_october_supersession_day_is_ambiguous_at_any_hour(self):
        for hour in (0, 6, 12, 23):
            x = run(asof=clock(10, 21, hour), version_id="v131")["catalog_entries"][0]
            self.assertEqual(x["status_relative_to_historical_cutoff"],
                             "SUPERSESSION_DAY_INTRADAY_AMBIGUOUS_BLOCKED")

    def test_after_supersession_not_current_but_still_no_pit_proof(self):
        r = run(asof=clock(10, 22), version_id="v131")
        x = r["catalog_entries"][0]
        self.assertEqual(x["status_relative_to_historical_cutoff"],
                         "AFTER_SUPERSESSION_NOT_CURRENT_VINTAGE")
        self.assert_no_bias(r)

    def test_mid_september_same_day_ambiguous_for_older_vintage(self):
        x = run(asof=clock(9, 16, 23), version_id="v130")["catalog_entries"][0]
        self.assertEqual(x["status_relative_to_historical_cutoff"],
                         "SUPERSESSION_DAY_INTRADAY_AMBIGUOUS_BLOCKED")

    def test_old_vintage_cannot_masquerade_as_current_in_october(self):
        rows = {x["version_id"]: x for x in run()["catalog_entries"]}
        self.assertEqual(rows["v130"]["status_relative_to_historical_cutoff"],
                         "AFTER_SUPERSESSION_NOT_CURRENT_VINTAGE")
        self.assertEqual(rows["v131"]["status_relative_to_historical_cutoff"],
                         "BEFORE_SUPERSESSION_UPPER_BOUND_ONLY_NO_PROOF")

    def test_before_july_all_four_only_have_supersession_upper_bounds(self):
        r = run(asof=clock(7, 21))
        for x in r["catalog_entries"]:
            self.assertEqual(x["status_relative_to_historical_cutoff"],
                             "BEFORE_SUPERSESSION_UPPER_BOUND_ONLY_NO_PROOF")
        self.assert_no_bias(r)

    def test_asof_datetime_normalizes_timezone(self):
        plus_four = timezone(timedelta(hours=4))
        r = run(asof=clock(10, 20, 16, tz=plus_four))
        self.assertEqual(r["as_of_utc"], clock().isoformat())

    def test_future_cutoff_is_rejected(self):
        r = run(asof=datetime(2026, 12, 1, tzinfo=timezone.utc))
        self.assertEqual(r["reason"], "INVALID_CUTOFF_OR_VERSION")
        self.assert_no_bias(r)

    def test_naive_asof_and_evaluation_rejected(self):
        self.assertEqual(run(asof=datetime(2026, 10, 20))["state"], "LAB_BLOCKED")
        self.assertEqual(run(evaluated=datetime(2026, 11, 5))["state"], "LAB_BLOCKED")

    def test_missing_or_invalid_clock_rejected(self):
        self.assertEqual(run(asof="2026-10-20")["state"], "LAB_BLOCKED")
        self.assertEqual(run(evaluated=None)["state"], "LAB_BLOCKED")

    def test_unknown_version_or_malicious_version_rejected(self):
        for val in ("v132", "v0131", "v131?x=1", "../v131", "V131", 131, True):
            self.assertEqual(run(version_id=val)["reason"],
                             "INVALID_CUTOFF_OR_VERSION")

    def test_single_version_selection_is_not_reordering(self):
        for expected in ("v131", "v130", "v129", "v128"):
            r = run(version_id=expected)
            self.assertEqual(r["catalog_entries_count"], 1)
            self.assertEqual(r["catalog_entries"][0]["version_id"], expected)
            self.assert_no_bias(r)

    def test_before_after_and_same_day_all_preserve_no_go(self):
        for dt in (clock(7, 1), clock(7, 22), clock(8, 19),
                   clock(9, 16), clock(10, 21), clock(11, 1)):
            self.assert_no_bias(run(asof=dt))


if __name__ == "__main__":
    unittest.main()
