"""Synthetic SDMX-shaped ECB CSV tests. No live ECB API or market accuracy."""
import csv
from datetime import datetime, timezone
from io import StringIO
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_ecb_reference_expost_lab import (
    describe_ecb_g8_reference_change_lab,
)

PREV = "2026-10-29"
CURRENT = "2026-10-30"
CAPTURED = datetime(2026, 10, 30, 18, 30, tzinfo=timezone.utc)
EVALUATED = datetime(2026, 11, 2, 18, tzinfo=timezone.utc)
RATES = {"USD": 1.10, "JPY": 165.0, "GBP": .84, "CHF": .92,
         "CAD": 1.50, "AUD": 1.70, "NZD": 1.85}
LATEST = {"USD": 1.12, "JPY": 163.0, "GBP": .83, "CHF": .93,
          "CAD": 1.49, "AUD": 1.72, "NZD": 1.88}
COLS = ("KEY", "FREQ", "CURRENCY", "CURRENCY_DENOM", "EXR_TYPE",
        "EXR_SUFFIX", "TIME_PERIOD", "OBS_VALUE")


def make_csv(prices1=None, prices2=None, *, date1=PREV, date2=CURRENT):
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLS)
    writer.writeheader()
    for period, values in ((date1, prices1 or RATES), (date2, prices2 or LATEST)):
        for c in sorted(values):
            writer.writerow({"KEY": f"D.{c}.EUR.SP00.A", "FREQ": "D",
                             "CURRENCY": c, "CURRENCY_DENOM": "EUR",
                             "EXR_TYPE": "SP00", "EXR_SUFFIX": "A",
                             "TIME_PERIOD": period, "OBS_VALUE": str(values[c])})
    return buf.getvalue()


def payload(text=None):
    return {"state": "LAB_SYNTHETIC_ECB_CSV", "csv_text": make_csv() if text is None else text}


def audit(p=None, *, prev=PREV, cur=CURRENT, captured=CAPTURED, at=EVALUATED):
    return describe_ecb_g8_reference_change_lab(
        payload() if p is None else p, previous=prev, current=cur,
        declared_captured_at=captured, evaluated_at=at)


class ECBReferenceExpostLabTests(unittest.TestCase):
    def test_exact_g8_and_28_reference_changes_from_seven_eur_rates(self):
        out = audit()
        self.assertEqual(out["state"], "LAB_SYNTHETIC_ECB_EXPOST_ONLY")
        self.assertEqual(set(out["currency_relative_moves_bp"]), set(CURRENCIES))
        self.assertEqual(set(out["pair_reference_moves_bp"]), set(OFFICIAL_PAIRS))
        self.assertEqual(out["observed_ecb_eur_reference_series"], 7)
        self.assertEqual(out["algebraically_derived_other_pairs"], 21)
        self.assertEqual(out["independent_spot_quotes_verified"], 0)
        self.assertAlmostEqual(sum(out["currency_relative_moves_bp"].values()), 0, places=3)

    def test_usdjpy_base_quote_direction_is_negative_when_jpy_strengthens(self):
        out = audit()
        self.assertLess(out["pair_reference_moves_bp"]["USD/JPY"]
                        ["relative_reference_change_bp"], 0)
        self.assertGreater(out["pair_reference_moves_bp"]["EUR/USD"]
                           ["relative_reference_change_bp"], 0)
        self.assertEqual(out["pair_reference_moves_bp"]["USD/JPY"]["origin"],
                         "DERIVED_FROM_ECB_EUR_REFERENCE_QUOTES")
        self.assertEqual(out["pair_reference_moves_bp"]["EUR/USD"]["origin"],
                         "EUR_QUOTE_REFERENCE_NOT_SPOT_CLOSE")

    def test_relative_pair_changes_equal_currency_factor_differences(self):
        out = audit()
        factors = out["currency_relative_moves_bp"]
        for pair, record in out["pair_reference_moves_bp"].items():
            a, b = pair.split("/")
            self.assertAlmostEqual(record["relative_reference_change_bp"],
                                   factors[a] - factors[b], places=4)

    def test_ecb_quoted_original_values_preserved_and_source_attribution(self):
        out = audit()
        self.assertEqual(out["eur_quoted_rates"][PREV]["JPY"], 165.0)
        self.assertEqual(out["eur_quoted_rates"][CURRENT]["USD"], 1.12)
        self.assertIn("BCE/ECB", out["source_attribution"])
        self.assertFalse(out["real_historical_data_verified"])

    def test_no_live_forecast_trade_execution_or_accuracy_claim(self):
        out = audit()
        for flag in ("actual_ecb_publication_proven",
                     "declared_capture_independently_attested",
                     "live_bias_validated", "accuracy_proven",
                     "future_return_backtested", "feed_enabled",
                     "worker_enabled", "scheduler_enabled",
                     "trade_authorized"):
            self.assertFalse(out[flag], flag)
        self.assertEqual(out["forecasts_issued"], 0)
        self.assertTrue(out["ecb_reference_rates_informational_only"])

    def test_before_conservative_18_local_clock_gate_is_blocked(self):
        early = datetime(2026, 10, 30, 16, 59, tzinfo=timezone.utc)
        out = audit(captured=early)
        self.assertEqual(out["state"], "LAB_REFUSED_UNVERIFIED_ECB_REFERENCE")

    def test_hypothetical_publication_boundary_is_not_actual_receipt_proof(self):
        out = audit(captured=datetime(2026, 10, 30, 17, tzinfo=timezone.utc))
        self.assertEqual(out["state"], "LAB_SYNTHETIC_ECB_EXPOST_ONLY")
        self.assertFalse(out["actual_ecb_publication_proven"])
        self.assertFalse(out["declared_capture_independently_attested"])

    def test_summer_dst_18_local_gate_uses_16_utc_not_17_utc(self):
        text = make_csv(date1="2026-07-09", date2="2026-07-10")
        data = payload(text)
        too_early = audit(data, prev="2026-07-09", cur="2026-07-10",
                          captured=datetime(2026, 7, 10, 15, 59, tzinfo=timezone.utc))
        self.assertEqual(too_early["state"], "LAB_REFUSED_UNVERIFIED_ECB_REFERENCE")
        eligible = audit(data, prev="2026-07-09", cur="2026-07-10",
                         captured=datetime(2026, 7, 10, 16, tzinfo=timezone.utc))
        self.assertEqual(eligible["state"], "LAB_SYNTHETIC_ECB_EXPOST_ONLY")
        self.assertEqual(eligible["hypothetical_publication_not_before_utc"],
                         "2026-07-10T16:00:00+00:00")

    def test_no_weekend_date_misread_as_ecb_workday(self):
        out = audit(prev="2026-10-30", cur="2026-10-31")
        self.assertEqual(out["state"], "LAB_REFUSED_UNVERIFIED_ECB_REFERENCE")

    def test_friday_to_monday_gap_is_allowed_if_rates_complete(self):
        text = make_csv(date1="2026-10-30", date2="2026-11-02")
        out = audit(payload(text), prev="2026-10-30", cur="2026-11-02",
                    captured=datetime(2026, 11, 2, 18, tzinfo=timezone.utc))
        self.assertEqual(out["state"], "LAB_SYNTHETIC_ECB_EXPOST_ONLY")
        self.assertFalse(out["actual_ecb_publication_proven"])

    def test_missing_currency_day_refuses_entire_reconstruction(self):
        for missing_day in (PREV, CURRENT):
            text = make_csv()
            lines = text.splitlines()
            lines = [line for line in lines if not
                     (f"D.JPY.EUR.SP00.A" in line and missing_day in line)]
            out = audit(payload("\n".join(lines)))
            self.assertEqual(out["state"], "LAB_REFUSED_UNVERIFIED_ECB_REFERENCE")
            self.assertEqual(out["pair_reference_moves_bp"], {})

    def test_duplicate_currency_on_one_day_refuses(self):
        text = make_csv()
        duplicate = next(line for line in text.splitlines()
                         if "D.USD.EUR.SP00.A" in line and PREV in line)
        out = audit(payload(text + duplicate + "\n"))
        self.assertEqual(out["state"], "LAB_REFUSED_UNVERIFIED_ECB_REFERENCE")

    def test_no_crosses_when_wrong_csv_series_metadata(self):
        for old, new in (("D.USD.EUR.SP00.A", "D.USD.USD.SP00.A"),
                         ("D.USD.EUR.SP00.A", "D.USD.EUR.SP10.A"),
                         ("D.USD.EUR.SP00.A", "D.USD.EUR.SP00.B")):
            text = make_csv().replace(old, new, 1)
            self.assertEqual(audit(payload(text))["state"],
                             "LAB_REFUSED_UNVERIFIED_ECB_REFERENCE")

    def test_reverse_quote_denominator_is_rejected(self):
        text = make_csv().replace(",EUR,SP00,A,", ",USD,SP00,A,", 1)
        self.assertEqual(audit(payload(text))["state"],
                         "LAB_REFUSED_UNVERIFIED_ECB_REFERENCE")

    def test_nonpositive_nonfinite_or_invalid_rates_rejected(self):
        for value in (0, -5, float("inf"), float("nan"), "missing", 1_000_000):
            data = dict(LATEST)
            data["USD"] = value
            out = audit(payload(make_csv(prices2=data)))
            self.assertEqual(out["state"], "LAB_REFUSED_UNVERIFIED_ECB_REFERENCE")

    def test_excessive_reference_change_rejected_without_clipping(self):
        data = dict(LATEST)
        data["USD"] = 5.0
        out = audit(payload(make_csv(prices2=data)))
        self.assertEqual(out["state"], "LAB_REFUSED_UNVERIFIED_ECB_REFERENCE")

    def test_only_offline_synthetic_envelope_accepted(self):
        for changed in ({}, {"state": "LIVE_ECB_DATA", "csv_text": make_csv()},
                        {"state": "LAB_SYNTHETIC_ECB_CSV", "csv_text": ""}):
            self.assertEqual(audit(changed)["state"],
                             "LAB_REFUSED_UNVERIFIED_ECB_REFERENCE")

    def test_capture_later_than_evaluation_rejected(self):
        late = EVALUATED.replace(day=3)
        self.assertEqual(audit(captured=late)["state"],
                         "LAB_REFUSED_UNVERIFIED_ECB_REFERENCE")

    def test_naive_timestamps_are_not_tolerated(self):
        with self.assertRaises(ValueError):
            audit(captured=datetime(2026, 10, 30, 18))
        with self.assertRaises(ValueError):
            audit(at=datetime(2026, 11, 2, 18))

    def test_no_future_observation_or_reversed_order(self):
        for prior, current in (("2026-10-30", "2026-10-29"),
                               ("2026-10-30", "2026-10-30"),
                               ("2026-10-29", "2026-11-03")):
            self.assertEqual(audit(prev=prior, cur=current)["state"],
                             "LAB_REFUSED_UNVERIFIED_ECB_REFERENCE")

    def test_header_required_no_overrides(self):
        bad = make_csv().replace("OBS_VALUE", "UNKNOWN_VALUE")
        self.assertEqual(audit(payload(bad))["state"],
                         "LAB_REFUSED_UNVERIFIED_ECB_REFERENCE")


if __name__ == "__main__":
    unittest.main()
