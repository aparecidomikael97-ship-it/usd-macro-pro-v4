"""Offline synthetic cases. No market API, no live forecasts, no orders."""
import unittest
from datetime import datetime, timedelta, timezone

from atlasquant_trader_bias_horizons_lab import build_bias_horizons_lab
from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS

NOW = datetime(2026, 11, 2, 15, 0, tzinfo=timezone.utc)


def scores(top="USD", low="JPY"):
    out = {c: 50.0 for c in CURRENCIES}
    out[top] = 85.0
    out[low] = 15.0
    return out


def snapshot(kind, values=None, *, timestamp=None, end=None):
    span = {"D1": 1, "W1": 5, "MN1": 25}[kind]
    day = NOW - timedelta(days=span)
    return {"state": "LAB_SYNTHETIC", "data_kind": "RELATIVE_STRENGTH_INDEX",
            "source": "Amostra sintética", "method_id": "forca-g8-lab-v1",
            "as_of": (timestamp or NOW - timedelta(hours=2)).isoformat(),
            "period_end": end or day.date().isoformat(),
            "strengths": values or scores()}


def batch():
    return {h: snapshot(h) for h in ("D1", "W1", "MN1")}


def row(out, pair="USD/JPY"):
    return next(x for x in out["rows"] if x["pair"] == pair)


class BiasHorizonsLabTests(unittest.TestCase):
    def test_universe_has_exactly_28_unique_pairs_and_eight_currencies(self):
        out = build_bias_horizons_lab(batch(), at=NOW)
        self.assertEqual(out["pair_count"], 28)
        self.assertEqual({x["pair"] for x in out["rows"]}, set(OFFICIAL_PAIRS))
        self.assertEqual(set(out["periods"]["D1"]["scores"]), set(CURRENCIES))

    def test_relative_strength_base_minus_quote_usdjpy(self):
        x = row(build_bias_horizons_lab(batch(), at=NOW))
        self.assertEqual(x["daily_bias"], "ALTA")
        self.assertEqual(x["horizons"]["D1"]["differential"], 70.0)
        self.assertEqual(x["state"], "TRES_HORIZONTES_ALINHADOS")
        self.assertFalse(x["entry_signal"])

    def test_weekly_opposed_does_not_overwrite_daily_and_blocks_ranking(self):
        data = batch()
        data["W1"]["strengths"] = scores(top="JPY", low="USD")
        out = build_bias_horizons_lab(data, at=NOW)
        x = row(out)
        self.assertEqual((x["daily_bias"], x["weekly_bias"]), ("ALTA", "BAIXA"))
        self.assertEqual(x["state"], "CONFLITO_SEMANAL")
        self.assertNotIn("USD/JPY", out["top10_observation_only"])

    def test_monthly_against_daily_weekly_is_context_not_veto(self):
        data = batch()
        data["MN1"]["strengths"] = scores(top="JPY", low="USD")
        out = build_bias_horizons_lab(data, at=NOW)
        self.assertEqual(row(out)["state"], "DIARIO_SEMANAL_ALINHADOS_MENSAL_CONTRA")
        self.assertEqual(row(out)["daily_bias"], "ALTA")
        self.assertIn("USD/JPY", out["top10_observation_only"])

    def test_missing_monthly_does_not_invent_context_or_hide_daily(self):
        data = batch(); del data["MN1"]
        out = build_bias_horizons_lab(data, at=NOW)
        self.assertEqual(row(out)["monthly_bias"], "AGUARDAR")
        self.assertEqual(row(out)["state"], "DIARIO_SEMANAL_ALINHADOS")

    def test_missing_weekly_stops_observation_ranking(self):
        data = batch(); del data["W1"]
        out = build_bias_horizons_lab(data, at=NOW)
        self.assertEqual(row(out)["state"], "SEM_CONFIRMACAO_SEMANAL")
        self.assertEqual(out["top10_observation_only"], [])

    def test_missing_daily_stops_all_candidates(self):
        data = batch(); del data["D1"]
        out = build_bias_horizons_lab(data, at=NOW)
        self.assertEqual(row(out)["daily_bias"], "AGUARDAR")
        self.assertEqual(out["top10_observation_only"], [])

    def test_stale_daily_cannot_be_presented_as_current(self):
        data = batch()
        data["D1"]["as_of"] = (NOW - timedelta(days=4)).isoformat()
        out = build_bias_horizons_lab(data, at=NOW)
        self.assertEqual(row(out)["state"], "SEM_VIES_DIARIO")

    def test_stale_weekly_is_unavailable_but_not_replaced_by_daily(self):
        data = batch()
        data["W1"]["as_of"] = (NOW - timedelta(days=15)).isoformat()
        self.assertEqual(row(build_bias_horizons_lab(data, at=NOW))["state"], "SEM_CONFIRMACAO_SEMANAL")

    def test_wrong_method_prevents_cross_period_comparison(self):
        data = batch(); data["W1"]["method_id"] = "unrelated-v9"
        out = build_bias_horizons_lab(data, at=NOW)
        self.assertEqual(out["periods"]["W1"]["state"], "INDISPONIVEL")
        self.assertEqual(row(out)["state"], "SEM_CONFIRMACAO_SEMANAL")

    def test_boolean_nan_and_invalid_scores_are_rejected(self):
        for invalid in (True, float("nan"), float("inf"), 101.0, "85"):
            data = batch()
            data["D1"]["strengths"] = {**scores(), "USD": invalid}
            out = build_bias_horizons_lab(data, at=NOW)
            self.assertEqual(out["periods"]["D1"]["state"], "INDISPONIVEL")

    def test_unknown_currency_or_missing_currency_cannot_make_28_biases(self):
        for value in ({"XXX": 12.0}, {}):
            data = batch()
            data["D1"]["strengths"] = {**scores(), **value}
            if not value:
                del data["D1"]["strengths"]["USD"]
            out = build_bias_horizons_lab(data, at=NOW)
            self.assertEqual(out["top10_observation_only"], [])

    def test_naive_or_future_timestamps_and_periods_are_rejected(self):
        data = batch(); data["D1"]["as_of"] = "2026-11-02T13:00:00"
        self.assertEqual(build_bias_horizons_lab(data, at=NOW)["top10_observation_only"], [])
        data = batch(); data["D1"]["as_of"] = (NOW + timedelta(hours=2)).isoformat()
        self.assertEqual(build_bias_horizons_lab(data, at=NOW)["top10_observation_only"], [])
        data = batch(); data["D1"]["period_end"] = "2027-01-01"
        self.assertEqual(build_bias_horizons_lab(data, at=NOW)["top10_observation_only"], [])

    def test_daily_neutral_is_not_a_forced_direction(self):
        data = batch()
        data["D1"]["strengths"] = {c: 50.0 for c in CURRENCIES}
        out = build_bias_horizons_lab(data, at=NOW)
        self.assertEqual(out["top10_observation_only"], [])
        self.assertEqual(row(out)["daily_bias"], "NEUTRO")

    def test_no_data_creates_no_bogus_rankings(self):
        out = build_bias_horizons_lab({}, at=NOW)
        self.assertEqual(out["pair_count"], 28)
        self.assertEqual(out["top10_observation_only"], [])
        self.assertTrue(all(x["daily_bias"] == "AGUARDAR" for x in out["rows"]))

    def test_limit_top10_and_never_accuracy_probability(self):
        out = build_bias_horizons_lab(batch(), at=NOW)
        self.assertLessEqual(len(out["top10_observation_only"]), 10)
        self.assertFalse(out["ranking_is_accuracy_probability"])
        self.assertFalse(out["backtested"])
        self.assertFalse(out["real_data_verified"])
        self.assertFalse(out["relative_strength_is_spot_appreciation"])
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["scheduler_enabled"])
        self.assertFalse(out["worker_enabled"])

    def test_requires_timezone_aware_evaluation_instant(self):
        with self.assertRaises(ValueError):
            build_bias_horizons_lab(batch(), at=datetime(2026, 11, 2, 12))


if __name__ == "__main__":
    unittest.main()
