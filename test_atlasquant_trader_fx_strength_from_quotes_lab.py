"""Synthetic-only tests of FX strength reconstruction and point-in-time guards."""
import unittest
from datetime import datetime, timedelta, timezone
from math import exp

from atlasquant_fx_universe import OFFICIAL_PAIRS, CURRENCIES, split_pair
from atlasquant_trader_fx_strength_from_quotes_lab import (
    build_fx_strength_from_quotes_lab,
)

AT = datetime(2026, 11, 2, 15, tzinfo=timezone.utc)
FACTOR_BP = {"D1": {"USD": 70, "JPY": -70, "EUR": 30},
             "W1": {"USD": 180, "JPY": -150, "EUR": 90},
             "MN1": {"USD": 380, "JPY": -300, "EUR": 70}}


def book(h, factors=None):
    days_from_now = {"D1": 0, "W1": 3, "MN1": 5}[h]
    length_days = {"D1": 1, "W1": 7, "MN1": 30}[h]
    observed = AT - timedelta(days=days_from_now, hours=1)
    end = observed - timedelta(hours=1)
    start = end - timedelta(days=length_days)
    latent = {code: float((factors or FACTOR_BP[h]).get(code, 0))
              for code in CURRENCIES}
    pairs = {}
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        pairs[pair] = {"start": 100.0,
                       "end": 100.0 * exp((latent[base] - latent[quote]) / 10000),
                       "source": "LAB - mesma fonte fictícia",
                       "start_at": start.isoformat(), "end_at": end.isoformat()}
    return {"state": "LAB_SYNTHETIC_SPOT",
            "data_kind": "SYNTHETIC_FX_SPOT_CLOSES",
            "source": "LAB - mesma fonte fictícia",
            "as_of": observed.isoformat(), "period_end": end.date().isoformat(),
            "pairs": pairs}


def all_books():
    return {h: book(h) for h in ("D1", "W1", "MN1")}


def view(result, pair="USD/JPY"):
    return next(row for row in result["bias_matrix"]["rows"] if row["pair"] == pair)


class StrengthFromQuotesTests(unittest.TestCase):
    def test_complete_graph_reconstructs_eight_currencies_three_horizons(self):
        out = build_fx_strength_from_quotes_lab(all_books(), at=AT)
        self.assertEqual(out["bias_matrix"]["pair_count"], 28)
        for horizon in ("D1", "W1", "MN1"):
            diag = out["diagnostics"][horizon]
            self.assertEqual(diag["state"], "LAB_COMPUTED")
            self.assertEqual(len(diag["currency_log_return_bp"]), 8)
            self.assertLess(diag["max_residual_bp"], 0.000001)
            self.assertFalse(diag["scaling_calibrated"])

    def test_currency_base_quote_orientation_is_correct_for_usd_jpy(self):
        out = build_fx_strength_from_quotes_lab(all_books(), at=AT)
        self.assertEqual(view(out)["daily_bias"], "ALTA")
        self.assertEqual(view(out)["state"], "TRES_HORIZONTES_ALINHADOS")
        self.assertAlmostEqual(
            out["diagnostics"]["D1"]["raw_log_return_bp"]["USD/JPY"], 140, places=5)
        eurusd = view(out, "EUR/USD")
        self.assertEqual(eurusd["daily_bias"], "BAIXA")

    def test_ranking_reuses_all_28_pairs_without_trade_permission(self):
        out = build_fx_strength_from_quotes_lab(all_books(), at=AT)
        matrix = out["bias_matrix"]
        self.assertEqual({r["pair"] for r in matrix["rows"]}, set(OFFICIAL_PAIRS))
        self.assertLessEqual(len(matrix["top10_observation_only"]), 10)
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["backtested"])
        self.assertFalse(out["macro_confirmed"])
        self.assertIsNone(out["accuracy_probability"])
        self.assertFalse(out["worker_enabled"])
        self.assertFalse(out["scheduler_enabled"])

    def test_weekly_counter_direction_blocks_usdjpy_ranking(self):
        data = all_books()
        data["W1"] = book("W1", {"USD": -160, "JPY": 160})
        out = build_fx_strength_from_quotes_lab(data, at=AT)
        self.assertEqual(view(out)["state"], "CONFLITO_SEMANAL")
        self.assertNotIn("USD/JPY", out["bias_matrix"]["top10_observation_only"])

    def test_monthly_opposes_daily_and_weekly_as_context_only(self):
        data = all_books()
        data["MN1"] = book("MN1", {"USD": -380, "JPY": 300})
        out = build_fx_strength_from_quotes_lab(data, at=AT)
        self.assertEqual(view(out)["state"], "DIARIO_SEMANAL_ALINHADOS_MENSAL_CONTRA")
        self.assertEqual(view(out)["daily_bias"], "ALTA")

    def test_missing_day_means_no_valid_observations(self):
        data = all_books()
        del data["D1"]
        out = build_fx_strength_from_quotes_lab(data, at=AT)
        self.assertEqual(out["bias_matrix"]["top10_observation_only"], [])
        self.assertEqual(view(out)["daily_bias"], "AGUARDAR")

    def test_missing_week_suppresses_top10_without_fabricated_confirmation(self):
        data = all_books()
        del data["W1"]
        out = build_fx_strength_from_quotes_lab(data, at=AT)
        self.assertEqual(out["bias_matrix"]["top10_observation_only"], [])
        self.assertEqual(view(out)["state"], "SEM_CONFIRMACAO_SEMANAL")

    def test_missing_month_keeps_daily_and_weekly_context_open(self):
        data = all_books()
        del data["MN1"]
        out = build_fx_strength_from_quotes_lab(data, at=AT)
        self.assertEqual(view(out)["monthly_bias"], "AGUARDAR")
        self.assertEqual(view(out)["state"], "DIARIO_SEMANAL_ALINHADOS")

    def test_missing_or_extra_pair_never_creates_partial_bias(self):
        for change in ("missing", "extra"):
            data = all_books()
            if change == "missing":
                del data["D1"]["pairs"]["USD/JPY"]
            else:
                data["D1"]["pairs"]["JPY/USD"] = data["D1"]["pairs"]["USD/JPY"]
            out = build_fx_strength_from_quotes_lab(data, at=AT)
            self.assertEqual(out["diagnostics"]["D1"]["state"], "AGUARDAR")
            self.assertEqual(out["bias_matrix"]["top10_observation_only"], [])

    def test_asynchronous_prices_rejected_even_with_same_source(self):
        data = all_books()
        raw = data["D1"]["pairs"]["EUR/USD"]
        raw["end_at"] = (datetime.fromisoformat(raw["end_at"]) +
                         timedelta(seconds=1)).isoformat()
        out = build_fx_strength_from_quotes_lab(data, at=AT)
        self.assertEqual(out["diagnostics"]["D1"]["state"], "AGUARDAR")

    def test_price_source_mismatch_is_not_treated_as_valid(self):
        data = all_books()
        data["D1"]["pairs"]["EUR/USD"]["source"] = "outro-provedor"
        out = build_fx_strength_from_quotes_lab(data, at=AT)
        self.assertEqual(out["diagnostics"]["D1"]["state"], "AGUARDAR")

    def test_triangulation_conflict_exposes_inconsistent_price_snapshot(self):
        data = all_books()
        data["D1"]["pairs"]["EUR/USD"]["end"] *= exp(0.02)
        out = build_fx_strength_from_quotes_lab(data, at=AT)
        self.assertEqual(out["diagnostics"]["D1"]["state"], "AGUARDAR")
        self.assertIn("triangulares", out["diagnostics"]["D1"]["reason"].lower())

    def test_invalid_prices_are_fail_closed(self):
        for invalid in (0, -1, float("nan"), float("inf"), True, "101.0"):
            data = all_books()
            data["D1"]["pairs"]["EUR/USD"]["end"] = invalid
            out = build_fx_strength_from_quotes_lab(data, at=AT)
            self.assertEqual(out["diagnostics"]["D1"]["state"], "AGUARDAR")

    def test_data_after_observation_instant_is_rejected(self):
        data = all_books()
        raw = data["D1"]["pairs"]["USD/JPY"]
        raw["end_at"] = (AT + timedelta(minutes=1)).isoformat()
        out = build_fx_strength_from_quotes_lab(data, at=AT)
        self.assertEqual(out["diagnostics"]["D1"]["state"], "AGUARDAR")

    def test_a_future_observation_timestamp_is_rejected(self):
        data = all_books()
        data["D1"]["as_of"] = (AT + timedelta(minutes=1)).isoformat()
        out = build_fx_strength_from_quotes_lab(data, at=AT)
        self.assertEqual(out["diagnostics"]["D1"]["state"], "AGUARDAR")

    def test_stale_weekly_is_not_reused_as_recent_week(self):
        data = all_books()
        data["W1"]["as_of"] = (AT - timedelta(days=15)).isoformat()
        out = build_fx_strength_from_quotes_lab(data, at=AT)
        self.assertEqual(out["diagnostics"]["W1"]["state"], "AGUARDAR")
        self.assertEqual(out["bias_matrix"]["top10_observation_only"], [])

    def test_unrealistic_timeframe_window_and_wrong_period_end_fail(self):
        data = all_books()
        data["D1"] = book("W1")
        out = build_fx_strength_from_quotes_lab(data, at=AT)
        self.assertEqual(out["diagnostics"]["D1"]["state"], "AGUARDAR")
        data = all_books()
        data["D1"]["period_end"] = "2026-11-09"
        out = build_fx_strength_from_quotes_lab(data, at=AT)
        self.assertEqual(out["diagnostics"]["D1"]["state"], "AGUARDAR")

    def test_dangerously_large_strength_does_not_silently_saturate(self):
        data = all_books()
        data["D1"] = book("D1", {"USD": 400, "JPY": -400})
        out = build_fx_strength_from_quotes_lab(data, at=AT)
        self.assertEqual(out["diagnostics"]["D1"]["state"], "AGUARDAR")
        self.assertEqual(out["bias_matrix"]["top10_observation_only"], [])

    def test_unknown_contract_is_not_ingested_as_real_data(self):
        data = all_books()
        data["D1"]["state"] = "REAL_VERIFIED"
        out = build_fx_strength_from_quotes_lab(data, at=AT)
        self.assertEqual(out["diagnostics"]["D1"]["state"], "AGUARDAR")
        self.assertFalse(out["real_quotes_verified"])

    def test_strips_no_naive_timestamp_and_denies_no_timezone(self):
        data = all_books()
        data["D1"]["pairs"]["USD/JPY"]["start_at"] = "2026-11-01T13:00:00"
        out = build_fx_strength_from_quotes_lab(data, at=AT)
        self.assertEqual(out["diagnostics"]["D1"]["state"], "AGUARDAR")
        with self.assertRaises(ValueError):
            build_fx_strength_from_quotes_lab(all_books(), at=datetime(2026, 11, 2))


if __name__ == "__main__":
    unittest.main()
