"""BLS CPI-U parser tests with fabricated API payloads, never real values."""
import json
import unittest

from atlasquant_trader_us_bls_cpi_yoy_snapshot_lab import (
    interpret_bls_cpi_u_snapshot_lab as parse,
)


def data_row(year, month, value, *, footnotes=None):
    names = ("January", "February", "March", "April", "May", "June",
             "July", "August", "September", "October", "November", "December")
    return {"year": str(year), "period": f"M{month:02d}",
            "periodName": names[month - 1], "value": str(value),
            "footnotes": [] if footnotes is None else footnotes}


def payload(rows=None, *, series_id="CUUR0000SA0", status="REQUEST_SUCCEEDED",
            container="dict", messages=None):
    if rows is None:
        rows = [data_row(2026, 9, "315.000"), data_row(2025, 9, "300.000")]
    res = {"series": [{"seriesID": series_id, "data": rows}]}
    root = {"status": status, "message": [] if messages is None else messages,
            "Results": res if container == "dict" else [res]}
    return json.dumps(root, sort_keys=True).encode("utf-8")


class BLSYoYLabTests(unittest.TestCase):
    def no_go(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        for key in ("derived_value_is_official_published_yoy",
                    "local_response_hash_verified", "issuer_first_release_authenticated",
                    "revisions_independently_audited", "historical_point_in_time_eligible",
                    "comparable_with_eurostat_without_methodology_checks",
                    "can_feed_macro_bias", "trade_authorized", "publishable",
                    "scheduler_enabled", "worker_enabled"):
            self.assertIs(r[key], False, key)
        self.assertEqual(r["http_requests"], 0)
        self.assertEqual(r["file_writes"], 0)
        self.assertEqual(r["new_cost_brl"], 0)

    def test_two_index_levels_generate_derived_rate_not_direction(self):
        r = parse(payload(), reference_period="2026-09")
        self.assertEqual(r["state"], "LAB_BLS_CPI_U_DERIVED_YOY_FROM_MUTABLE_API_BYTES_UNATTESTED")
        self.assertEqual(r["current_index_level_claim"], "315.000")
        self.assertEqual(r["previous_year_index_level_claim"], "300.000")
        self.assertEqual(r["previous_year_reference_period"], "2025-09")
        self.assertEqual(r["derived_yoy_percent"], "5.000")
        self.no_go(r)

    def test_official_example_response_array_container(self):
        r = parse(payload(container="array"), reference_period="2026-09")
        self.assertEqual(r["derived_yoy_percent"], "5.000")
        self.no_go(r)

    def test_same_month_year_ago_not_previous_month(self):
        rows = [data_row(2026, 9, "330"), data_row(2026, 8, "300"),
                data_row(2025, 9, "320")]
        r = parse(payload(rows), reference_period="2026-09")
        self.assertEqual(r["derived_yoy_percent"], "3.125")
        self.no_go(r)

    def test_same_month_missing_rejects_even_when_previous_month_present(self):
        rows = [data_row(2026, 9, "330"), data_row(2026, 8, "300")]
        r = parse(payload(rows), reference_period="2026-09")
        self.assertEqual(r["reason"], "TARGET_OR_PRIOR_YEAR_SAME_MONTH_INDEX_MISSING")
        self.no_go(r)

    def test_future_target_not_conjured_from_latest(self):
        r = parse(payload(), reference_period="2026-10")
        self.assertEqual(r["state"], "LAB_BLS_CPI_SNAPSHOT_BLOCKED")
        self.assertIsNone(r["derived_yoy_percent"])
        self.no_go(r)

    def test_duplicate_series_vintage_is_rejected(self):
        rows = [data_row(2026, 9, "315"), data_row(2025, 9, "300"),
                data_row(2026, 9, "315")]
        r = parse(payload(rows), reference_period="2026-09")
        self.assertEqual(r["reason"], "DUPLICATE_MONTH_OR_AMBIGUOUS_VINTAGE")
        self.no_go(r)

    def test_wrong_series_or_api_failure(self):
        for data in (payload(series_id="CUSR0000SA0"),
                     payload(status="REQUEST_FAILED"),
                     payload(messages=["failed"])):
            with self.subTest(data=data[:50]):
                self.assertEqual(parse(data, reference_period="2026-09")["state"],
                                 "LAB_BLS_CPI_SNAPSHOT_BLOCKED")

    def test_reject_preliminary_or_nonempty_footnote(self):
        rows = [data_row(2026, 9, "315", footnotes=[{"code": "P", "text": "Preliminary"}]),
                data_row(2025, 9, "300")]
        r = parse(payload(rows), reference_period="2026-09")
        self.assertEqual(r["state"], "LAB_BLS_CPI_SNAPSHOT_BLOCKED")
        self.no_go(r)

    def test_reject_broken_numbers_and_period_names(self):
        variants = (("value", "NaN"), ("value", "-4"), ("value", "315,00"),
                    ("value", "0"), ("periodName", "October"),
                    ("period", "M13"), ("year", "2025"))
        for key, value in variants:
            with self.subTest(key=key, value=value):
                rows = [data_row(2026, 9, "315"), data_row(2025, 9, "300")]
                rows[0][key] = value
                self.assertEqual(parse(payload(rows), reference_period="2026-09")["state"],
                                 "LAB_BLS_CPI_SNAPSHOT_BLOCKED")

    def test_json_duplicate_property_fails_closed(self):
        raw = payload().decode("utf-8").replace(
            '"status": "REQUEST_SUCCEEDED"',
            '"status": "REQUEST_SUCCEEDED", "status": "REQUEST_SUCCEEDED"',
        )
        self.assertEqual(parse(raw.encode(), reference_period="2026-09")["state"],
                         "LAB_BLS_CPI_SNAPSHOT_BLOCKED")

    def test_non_json_utf8_and_size_limit_fail_closed(self):
        for raw, period in ((b"bad", "2026-09"), (b"\xff", "2026-09"),
                            (b"", "2026-09"), (payload(), "2026-Q3"),
                            (payload(), None), (b"x" * 524289, "2026-09")):
            with self.subTest(period=period):
                r = parse(raw, reference_period=period)
                self.assertEqual(r["state"], "LAB_BLS_CPI_SNAPSHOT_BLOCKED")
                self.no_go(r)

    def test_input_byte_string_unchanged(self):
        raw = payload()
        before = bytes(raw)
        r = parse(raw, reference_period="2026-09")
        self.assertEqual(raw, before)
        self.no_go(r)


if __name__ == "__main__":
    unittest.main()
