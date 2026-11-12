"""Synthetic offline BLS CUSR0000SA0 CPI-U SA monthly bridge tests."""
from datetime import datetime, timedelta, timezone
import json
import unittest

from atlasquant_trader_bls_cpi_sa_previous_bridge_lab import (
    API_URL, SERIES_ID, bridge_previous_cpi_sa_mom_before_event_lab as bridge,
    parse_current_bls_cpi_sa_index_lab as parse,
)

UTC = timezone.utc
OBSERVED = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
CAPTURED = datetime(2026, 11, 8, 12, 15, tzinfo=UTC)
RELEASE = datetime(2026, 11, 10, 13, 30, tzinfo=UTC)


def row(year, month, value, *, latest=None, footnotes=None):
    result = {"year": str(year), "period": f"M{month:02d}",
              "value": value, "footnotes": [] if footnotes is None else footnotes}
    if latest is not None:
        result["latest"] = latest
    return result


def raw(rows=None, *, sid=SERIES_ID, status="REQUEST_SUCCEEDED", messages=None):
    if rows is None:
        rows = [row(2026, 9, "336.298", latest="true"),
                row(2026, 8, "334.131"), row(2026, 7, "332.813")]
    return json.dumps({"status": status, "message": [] if messages is None else messages,
                       "Results": {"series": [{"seriesID": sid, "data": rows}]}},
                      separators=(",", ":")).encode()


def call_bridge(snapshot=None, **changes):
    kwargs = {
        "observed_at_utc": OBSERVED,
        "forecast_captured_at_utc": CAPTURED,
        "scheduled_release_at_utc": RELEASE,
        "as_of_utc": CAPTURED,
        "target_period": "2026-10",
    }
    kwargs.update(changes)
    return bridge(raw() if snapshot is None else snapshot, **kwargs)


class BlsAdjustedCpiBridgeTests(unittest.TestCase):
    def assert_no_go(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertFalse(r["claimed_api_bytes_publisher_authenticated"])
        self.assertFalse(r["index_vintage_independently_verified"])
        self.assertFalse(r["actual_first_print_independently_verified"])
        self.assertFalse(r["observed_clock_independently_attested"])
        self.assertFalse(r["prior_month_bls_reported_change_verified"])
        self.assertFalse(r["consensus_before_release_verified"])
        self.assertFalse(r["valid_pre_event_forecast"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertIsNone(r["calibrated_direction_probability"])
        self.assertIsNone(r["fx_bias"])
        self.assertIsNone(r["index_bias"])
        self.assertEqual((r["http_requests"], r["file_writes"],
                          r["new_cost_brl"]), (0, 0, 0))
        self.assertTrue(r["research_only"])

    def test_series_is_seasonally_adjusted_distinct_from_unadjusted(self):
        self.assertEqual(SERIES_ID, "CUSR0000SA0")
        self.assertNotIn("CUUR0000SA0", API_URL)
        r = parse(raw(), observed_at_utc=OBSERVED)
        self.assertEqual(r["series_semantics"], "CPI_U_ALL_ITEMS_SA_INDEX_1982_84_100")
        self.assertEqual(r["unit"], "INDEX_LEVEL_NOT_MOM_PERCENT")
        self.assert_no_go(r)

    def test_parse_current_index_and_derive_mom_without_claiming_first_print(self):
        r = parse(raw(), observed_at_utc=OBSERVED)
        self.assertEqual(r["state"], "LAB_BLS_SA_INDEX_CURRENT_RESPONSE_UNVERIFIED")
        self.assertEqual(r["latest_available_index_month"], "2026-09")
        self.assertEqual(r["latest_available_mom_sa_percent_derived"], "0.6")
        self.assertEqual(r["index_months"][0]["month_before"], "2026-08")
        self.assertEqual(r["index_months"][0]["index_level"], "336.298")
        self.assertEqual(r["index_months"][0]["derived_mom_sa_percent_rounded_documentary"], "0.6")
        self.assert_no_go(r)

    def test_prior_context_for_october_never_an_october_actual(self):
        r = call_bridge()
        self.assertEqual(r["state"], "LAB_BLS_SA_PREVIOUS_MOM_DOCUMENTARY_ONLY")
        self.assertEqual(r["target_period"], "2026-10")
        self.assertEqual(r["previous_period"], "2026-09")
        self.assertEqual(r["previous_mom_percent_documentary"], "0.6")
        self.assertEqual(r["previous_mom_source_index_pair"], [
            {"month": "2026-09", "index_level": "336.298"},
            {"month": "2026-08", "index_level": "334.131"},
        ])
        self.assert_no_go(r)

    def test_wrong_unadjusted_series_never_accepted_as_sadj(self):
        r = parse(raw(sid="CUUR0000SA0"), observed_at_utc=OBSERVED)
        self.assertEqual(r["state"], "LAB_BLS_CPI_SA_BLOCKED")
        self.assert_no_go(r)

    def test_future_cpi_month_no_silent_release(self):
        rows = [row(2026, 12, "337.1"), row(2026, 9, "336.298")]
        r = parse(raw(rows), observed_at_utc=OBSERVED)
        self.assertEqual(r["reason"], "BLS_MONTH_IN_FUTURE")
        self.assert_no_go(r)

    def test_october_claim_in_current_snapshot_is_not_previous_october_context(self):
        rows = [row(2026, 10, "337.001"), row(2026, 9, "336.298"),
                row(2026, 8, "334.131")]
        r = call_bridge(raw(rows))
        self.assertEqual(r["state"], "LAB_BLS_SA_PREVIOUS_MONTH_UNAVAILABLE")
        self.assertIsNone(r["previous_mom_percent_documentary"])
        self.assert_no_go(r)

    def test_missing_august_disables_september_mom(self):
        rows = [row(2026, 9, "336.298"), row(2026, 8, "-"),
                row(2026, 7, "332.813")]
        r = parse(raw(rows), observed_at_utc=OBSERVED)
        self.assertIn("2026-08", r["missing_months"])
        self.assertIsNone(r["latest_available_mom_sa_percent_derived"])
        bridged = call_bridge(raw(rows))
        self.assertEqual(bridged["reason"], "MONTH_BEFORE_PREVIOUS_REQUIRED_FOR_MOM")
        self.assertIsNone(bridged["previous_mom_percent_documentary"])
        self.assert_no_go(bridged)

    def test_missing_october_2025_sentinel_is_not_imputed(self):
        rows = [row(2025, 11, "325.063"), row(2025, 10, "-"),
                row(2025, 9, "324.0")]
        r = parse(raw(rows), observed_at_utc=OBSERVED)
        self.assertEqual(r["missing_months"], ["2025-10"])
        self.assertIsNone(r["index_months"][0]["derived_mom_sa_percent_rounded_documentary"])
        self.assert_no_go(r)

    def test_annual_m13_is_not_an_inflation_month(self):
        rows = [row(2026, 9, "336.298"), row(2026, 8, "334.131"),
                {"year": "2025", "period": "M13", "value": "322.0", "footnotes": []}]
        r = parse(raw(rows), observed_at_utc=OBSERVED)
        self.assertEqual(r["state"], "LAB_BLS_SA_INDEX_CURRENT_RESPONSE_UNVERIFIED")
        self.assertEqual(len(r["index_months"]), 2)
        self.assert_no_go(r)

    def test_incorrect_status_messages_or_shape_block(self):
        for b in (raw(status="REQUEST_FAILED"), raw(messages=["review"]),
                  b"broken-json", raw(rows=[]),
                  json.dumps({"status": "REQUEST_SUCCEEDED", "message": [],
                              "Results": {"series": []}}).encode()):
            with self.subTest(body=b[:30]):
                r = parse(b, observed_at_utc=OBSERVED)
                self.assertEqual(r["state"], "LAB_BLS_CPI_SA_BLOCKED")
                self.assert_no_go(r)

    def test_duplicate_or_unsorted_months_block(self):
        for rows in (
            [row(2026, 9, "336"), row(2026, 9, "335")],
            [row(2026, 8, "334"), row(2026, 9, "336")],
        ):
            self.assertEqual(parse(raw(rows), observed_at_utc=OBSERVED)["state"],
                             "LAB_BLS_CPI_SA_BLOCKED")

    def test_non_decimal_negative_zero_or_nonfinite_block(self):
        for invalid in ("NaN", "Infinity", "-20", "0", "10000.0", "x", ".34"):
            with self.subTest(value=invalid):
                r = parse(raw([row(2026, 9, invalid)]), observed_at_utc=OBSERVED)
                self.assertEqual(r["state"], "LAB_BLS_CPI_SA_BLOCKED")

    def test_bad_latest_and_footnote_type_block(self):
        for rows in (
            [row(2026, 9, "336.298", latest="false")],
            [row(2026, 9, "336.298", footnotes="not-a-list")],
            [row(2026, 9, "336.298", footnotes=[{"code": 33}])],
            [row(2026, 9, "336.298", latest="true"),
             row(2026, 8, "334.131", latest="true")],
        ):
            self.assertEqual(parse(raw(rows), observed_at_utc=OBSERVED)["state"],
                             "LAB_BLS_CPI_SA_BLOCKED")

    def test_wrong_target_month_cannot_get_previous_context(self):
        r = call_bridge(target_period="2026-09")
        self.assertEqual(r["state"], "LAB_BLS_SA_PREVIOUS_MONTH_UNAVAILABLE")
        self.assertIsNone(r["previous_mom_percent_documentary"])

    def test_forecast_and_source_times_must_precede_release(self):
        for changes in (
            {"observed_at_utc": CAPTURED + timedelta(minutes=1)},
            {"forecast_captured_at_utc": RELEASE},
            {"scheduled_release_at_utc": CAPTURED - timedelta(minutes=1)},
            {"as_of_utc": CAPTURED - timedelta(seconds=1)},
            {"observed_at_utc": OBSERVED.replace(tzinfo=None)},
            {"as_of_utc": CAPTURED + timedelta(microseconds=1)},
        ):
            with self.subTest(changes=changes):
                r = call_bridge(**changes)
                self.assertEqual(r["state"], "LAB_BLS_CPI_SA_BLOCKED")
                self.assert_no_go(r)

    def test_index_not_available_for_true_previous_predecessor(self):
        rows = [row(2026, 9, "336.298")]
        r = call_bridge(raw(rows))
        self.assertEqual(r["state"], "LAB_BLS_SA_PREVIOUS_MONTH_UNAVAILABLE")
        self.assertIsNone(r["previous_mom_percent_documentary"])

    def test_empty_nonbytes_or_naive_parser_clock_blocked(self):
        for b in (None, b"", {}, raw() * 5000):
            r = parse(b, observed_at_utc=OBSERVED)
            self.assertEqual(r["state"], "LAB_BLS_CPI_SA_BLOCKED")
        self.assertEqual(parse(raw(), observed_at_utc=OBSERVED.replace(tzinfo=None))
                         ["state"], "LAB_BLS_CPI_SA_BLOCKED")


if __name__ == "__main__":
    unittest.main()
