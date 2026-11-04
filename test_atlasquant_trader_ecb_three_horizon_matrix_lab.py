"""D1/W1/MN1 reference rankings must never impersonate live Forex bias."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import unittest

from atlasquant_ecb_g8_reference_lab import analyze_ecb_reference_xml
from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_ecb_three_horizon_matrix_lab import (
    SCHEMA, HORIZONS, build_ecb_three_horizon_reference_matrix_lab,
)

NOW = datetime(2026, 11, 4, 21, tzinfo=timezone.utc)
FIXES = {
    "USD": 1.12, "JPY": 178.3, "GBP": 0.85, "CHF": 0.93,
    "AUD": 1.60, "CAD": 1.55, "NZD": 1.99,
}


def xml_history(rows):
    body = "".join(
        '<Cube time="' + date + '">' + "".join(
            '<Cube currency="' + key + '" rate="' + str(rate) + '"/>'
            for key, rate in rates.items()
        ) + '</Cube>'
        for date, rates in rows
    )
    return ('<Envelope xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">'
            '<Cube>' + body + '</Cube></Envelope>').encode("utf-8")


def sample():
    return xml_history([
        ("2026-10-01", {**FIXES, "USD": 1.13}),
        ("2026-10-27", {**FIXES, "USD": 1.09}),
        ("2026-11-02", {**FIXES, "USD": 1.12}),
        ("2026-11-03", {**FIXES, "USD": 1.11}),
    ])


def build(xml=None, *, at=NOW):
    return build_ecb_three_horizon_reference_matrix_lab(sample() if xml is None else xml,
                                                        at=at)


def horizon(result, pair="EUR/USD", frame="D1"):
    return next(p for p in result["pair_rows"] if p["pair"] == pair)["horizons"][frame]


class ECBThreeHorizonMatrixLabTests(unittest.TestCase):
    def test_28_pairs_three_horizons_eight_currencies_reference_only(self):
        raw = sample()
        before = deepcopy(raw)
        result = build(raw)
        self.assertEqual(raw, before)
        self.assertEqual((result["schema"], result["state"]),
                         (SCHEMA, "LAB_EXPOST_REFERENCE_MATRIX_ONLY"))
        self.assertEqual((result["pair_count"], result["currency_count"],
                          result["horizon_count"]), (28, 8, 3))
        self.assertEqual({r["pair"] for r in result["pair_rows"]}, set(OFFICIAL_PAIRS))
        for row in result["pair_rows"]:
            self.assertFalse(row["trade_authorized"])
            self.assertEqual(set(row["horizons"]), set(HORIZONS))
            for frame in row["horizons"].values():
                self.assertEqual(frame["operational_bias"], "AGUARDAR")
                self.assertEqual(frame["reason_for_currency_strength"], "NAO_COMPROVADA")
                self.assertFalse(frame["reference_is_executable_quote"])

    def test_daily_weekly_monthly_reference_changes_can_disagree(self):
        result = build()
        d = horizon(result, frame="D1")
        w = horizon(result, frame="W1")
        m = horizon(result, frame="MN1")
        self.assertLess(d["observed_reference_change_pct"], 0)
        self.assertGreater(w["observed_reference_change_pct"], 0)
        self.assertLess(m["observed_reference_change_pct"], 0)
        self.assertEqual(d["historical_reference_relation"],
                         "QUOTE_OUTPERFORMED_IN_REFERENCE")
        self.assertEqual(w["historical_reference_relation"],
                         "BASE_OUTPERFORMED_IN_REFERENCE")
        self.assertEqual(m["actual_elapsed_calendar_days"], 33)
        self.assertEqual(m["start_reference_date"], "2026-10-01")
        self.assertEqual(m["end_reference_date"], "2026-11-03")

    def test_monthly_relative_order_and_28_derived_returns(self):
        result = build()
        for frame in HORIZONS:
            ranking = result["currency_ranking_by_horizon"][frame]
            self.assertEqual(set(entry["currency"] for entry in ranking), set(CURRENCIES))
            self.assertEqual([x["rank"] for x in ranking], list(range(1, 9)))
            self.assertEqual(len(result["horizon_top10_reference_only"][frame]), 10)
            self.assertTrue(all(x["observed_only_not_macro_cause"] for x in ranking))
        self.assertEqual(result["derived_non_eur_crosses"], 21)
        self.assertEqual(result["direct_eur_reference_legs_per_day"], 7)

    def test_insufficient_month_history_does_not_invent_reference_anchors(self):
        raw = xml_history([
            ("2026-10-27", FIXES), ("2026-11-02", FIXES),
            ("2026-11-03", {**FIXES, "USD": 1.11}),
        ])
        result = build(raw)
        self.assertEqual(result["state"], "LAB_EXPOST_REFERENCE_MATRIX_ONLY")
        self.assertEqual(horizon(result, frame="MN1")["research_state"],
                         "INSUFFICIENT_REFERENCE_HISTORY")
        self.assertIsNone(horizon(result, frame="MN1")["observed_reference_change_pct"])
        self.assertEqual(result["currency_ranking_by_horizon"]["MN1"], [])
        self.assertEqual(horizon(result, frame="MN1")["operational_bias"], "AGUARDAR")

    def test_monthly_anchor_more_than_seven_days_past_target_is_rejected(self):
        raw = xml_history([
            ("2026-09-21", FIXES), ("2026-11-02", FIXES),
            ("2026-11-03", {**FIXES, "USD": 1.11}),
        ])
        result = build(raw)
        self.assertEqual(result["state"], "LAB_EXPOST_REFERENCE_MATRIX_ONLY")
        self.assertEqual(horizon(result, frame="MN1")["research_state"],
                         "INSUFFICIENT_REFERENCE_HISTORY")

    def test_weekly_anchor_14_days_old_is_not_mislabeled_as_one_week(self):
        raw = xml_history([
            ("2026-10-01", FIXES),
            ("2026-10-20", {**FIXES, "USD": 1.09}),
            ("2026-11-02", FIXES),
            ("2026-11-03", {**FIXES, "USD": 1.11}),
        ])
        result = build(raw)
        self.assertEqual(result["state"], "LAB_EXPOST_REFERENCE_MATRIX_ONLY")
        self.assertEqual(horizon(result, frame="W1")["research_state"],
                         "INSUFFICIENT_REFERENCE_HISTORY")
        self.assertIsNone(horizon(result, frame="W1")["observed_reference_change_pct"])
        self.assertEqual(result["currency_ranking_by_horizon"]["W1"], [])
        self.assertEqual(horizon(result, frame="MN1")["research_state"],
                         "EXPOST_REFERENCE_ONLY")
        self.assertEqual(horizon(result, frame="W1")["operational_bias"], "AGUARDAR")

    def test_weekly_actual_eight_day_reference_window_is_transparent(self):
        raw = xml_history([
            ("2026-10-26", FIXES),
            ("2026-11-02", FIXES),
            ("2026-11-03", {**FIXES, "USD": 1.11}),
        ])
        adapter = analyze_ecb_reference_xml(raw, now=NOW)
        self.assertEqual(adapter["research_windows"]["W1"]["state"], "RESEARCH_ONLY")
        self.assertEqual(adapter["research_windows"]["W1"]["target_calendar_days"], 7)
        self.assertEqual(adapter["research_windows"]["W1"]["anchor_slippage_calendar_days"], 1)
        self.assertEqual(adapter["research_windows"]["W1"]["calendar_days_between_fixes"], 8)

    def test_last_two_reference_days_cannot_be_fourteen_day_daily_return(self):
        raw = xml_history([
            ("2026-10-15", FIXES), ("2026-11-03", {**FIXES, "USD": 1.11}),
        ])
        result = build(raw)
        self.assertEqual(result["state"], "LAB_BLOCKED")
        self.assertIn("LAST_TWO_REFERENCE_DATES_TOO_FAR_APART_FOR_D1",
                      result["reason"])
        self.assertEqual(result["pair_rows"], [])

    def test_bad_xml_missing_rate_future_date_and_zero_rate_are_blocked(self):
        bad_sets = [b"", b"<xml>",
                    xml_history([("2026-11-02", FIXES),
                                 ("2026-11-06", {**FIXES, "USD": 1.11})]),
                    xml_history([("2026-11-02", FIXES),
                                 ("2026-11-03", {**FIXES, "USD": 0})]),
                    xml_history([("2026-11-02", FIXES),
                                 ("2026-11-03", {k: v for k, v in FIXES.items()
                                                 if k != "JPY"})])]
        for raw in bad_sets:
            with self.subTest(raw=raw[:50]):
                out = build(raw)
                self.assertEqual(out["state"], "LAB_BLOCKED")
                self.assertFalse(out["publishable"])

    def test_old_history_not_mislabeled_as_fresh_or_live(self):
        later = datetime(2026, 12, 1, 21, tzinfo=timezone.utc)
        out = build(at=later)
        self.assertTrue(out["reference_age_over_four_days"])
        self.assertGreater(out["reference_age_days"], 4)
        self.assertFalse(out["calendar_and_news_realtime_verified"])
        self.assertFalse(out["three_daily_updates_verified"])
        self.assertEqual(out["operational_bias"], "AGUARDAR")

    def test_same_day_reference_not_available_before_european_publication(self):
        raw = xml_history([
            ("2026-11-03", FIXES),
            ("2026-11-04", {**FIXES, "USD": 1.11}),
        ])
        before = datetime(2026, 11, 4, 14, 59, tzinfo=timezone.utc)
        after = datetime(2026, 11, 4, 15, 1, tzinfo=timezone.utc)
        early = build(raw, at=before)
        self.assertEqual(early["state"], "LAB_BLOCKED")
        self.assertIn("SAME_DAY_FIX_BEFORE_USUAL_ECB_PUBLICATION", early["reason"])
        allowed = build(raw, at=after)
        self.assertEqual(allowed["state"], "LAB_EXPOST_REFERENCE_MATRIX_ONLY")
        self.assertEqual(allowed["reference_age_days"], 0)
        self.assertFalse(allowed["ecb_original_bytes_authenticated"])
        self.assertEqual(allowed["operational_bias"], "AGUARDAR")

    def test_summer_daylight_saving_shifts_publication_guard_in_utc(self):
        raw = xml_history([
            ("2026-06-30", FIXES),
            ("2026-07-01", {**FIXES, "USD": 1.11}),
        ])
        early = build(raw, at=datetime(2026, 7, 1, 13, 59, tzinfo=timezone.utc))
        late = build(raw, at=datetime(2026, 7, 1, 14, 1, tzinfo=timezone.utc))
        self.assertEqual(early["state"], "LAB_BLOCKED")
        self.assertIn("SAME_DAY_FIX_BEFORE_USUAL_ECB_PUBLICATION", early["reason"])
        self.assertEqual(late["state"], "LAB_EXPOST_REFERENCE_MATRIX_ONLY")
        self.assertEqual(late["reference_age_days"], 0)
        self.assertFalse(late["publishable"])

    def test_forged_weekend_fix_is_rejected_not_used_as_daily_strength(self):
        raw = xml_history([
            ("2026-11-06", FIXES),
            ("2026-11-07", {**FIXES, "USD": 1.11}),
        ])
        result = build(raw, at=datetime(2026, 11, 9, 18, tzinfo=timezone.utc))
        self.assertEqual(result["state"], "LAB_BLOCKED")
        self.assertIn("NON_WORKING_WEEKEND_REFERENCE_DATE", result["reason"])

    def test_forged_older_weekend_anchor_cannot_distort_month_strength(self):
        raw = xml_history([
            ("2026-10-03", FIXES),  # historical Saturday, not just latest
            ("2026-11-02", FIXES),
            ("2026-11-03", {**FIXES, "USD": 1.11}),
        ])
        result = build(raw)
        self.assertEqual(result["state"], "LAB_BLOCKED")
        self.assertIn("NON_WORKING_WEEKEND_REFERENCE_DATE", result["reason"])

    def test_adapter_mn1_and_matrix_use_same_window_values(self):
        raw = sample()
        adapter = analyze_ecb_reference_xml(raw, now=NOW)
        matrix = build(raw)
        self.assertEqual(set(adapter["research_windows"]), set(HORIZONS))
        for frame in HORIZONS:
            for pair in OFFICIAL_PAIRS:
                self.assertEqual(
                    horizon(matrix, pair, frame)["observed_reference_change_pct"],
                    adapter["research_windows"][frame]["pair_returns_pct"][pair],
                )

    def test_nonnormalized_clock_refused(self):
        with self.assertRaises(ValueError):
            build(at=datetime(2026, 11, 4, 21))

    def test_cost_worker_merge_not_touched_by_research_output(self):
        out = build()
        for flag in ("ecb_original_bytes_authenticated", "independent_fx_price_verified",
                     "macro_causation_verified", "prediction_backtested_oos",
                     "can_feed_live_radar", "publishable", "trade_authorized",
                     "worker_enabled", "scheduler_enabled"):
            self.assertFalse(out[flag], flag)
        self.assertEqual((out["external_http_requests"], out["new_cost_brl"]), (0, 0))


if __name__ == "__main__":
    unittest.main()
