"""Conditional macro scenarios, never event predictions or trade signals."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_exante_macro_scenarios_lab import HORIZONS, INDICES
from atlasquant_trader_us_cpi_conditionals_lab import (
    SCHEMA, BRANCHES, build_us_cpi_conditional_impact_lab,
)

CASE = Path(__file__).resolve().parent / "docs" / "continuidade" / "TRADER_CPI_PROSPECTIVE_FREEZE_20261103.json"
BEFORE_EVENT = datetime(2026, 11, 3, 9, 30, tzinfo=timezone.utc)
AFTER_EVENT = datetime(2026, 11, 11, 9, 30, tzinfo=timezone.utc)
UP = "INFLATION_UPSIDE_AND_HAWKISH_REPRICING"
DOWN = "INFLATION_DOWNSIDE_AND_DOVISH_REPRICING"
MIXED = "MIXED_CORE_OR_GEOPOLITICAL_RISK"


def snapshot():
    return json.loads(CASE.read_text(encoding="utf-8"))


def run(book=None, when=BEFORE_EVENT):
    return build_us_cpi_conditional_impact_lab(snapshot() if book is None else book,
                                               evaluated_at=when)


def pairrow(out, branch, horizon, pair):
    return next(x for x in out["pair_scenarios"]
                if (x["branch"], x["horizon"], x["pair"]) == (branch, horizon, pair))


def idxrow(out, branch, horizon, symbol):
    return next(x for x in out["index_scenarios"]
                if (x["branch"], x["horizon"], x["symbol"]) == (branch, horizon, symbol))


class USCPIMacroConditionalImpactTests(unittest.TestCase):
    def test_28_pairs_five_indices_three_horizons_three_branches(self):
        result = run()
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["state"], "LAB_HYPOTHETICAL_UNSELECTED_CPI_BRANCHES_ONLY")
        self.assertEqual(len(result["pair_scenarios"]), 28 * 3 * 3)
        self.assertEqual(len(result["index_scenarios"]), 5 * 3 * 3)
        self.assertEqual({r["pair"] for r in result["pair_scenarios"]}, set(OFFICIAL_PAIRS))
        self.assertEqual({r["symbol"] for r in result["index_scenarios"]}, set(INDICES))
        self.assertEqual({r["horizon"] for r in result["pair_scenarios"]}, set(HORIZONS))
        self.assertEqual({r["branch"] for r in result["pair_scenarios"]}, set(BRANCHES))

    def test_eurusd_conditional_if_usd_hawkish(self):
        self.assertEqual(pairrow(run(), UP, "D1", "EUR/USD")["bias_if_conditions"],
                         "BAIXA_CONDICIONAL")

    def test_eurusd_conditional_if_usd_dovish(self):
        self.assertEqual(pairrow(run(), DOWN, "D1", "EUR/USD")["bias_if_conditions"],
                         "ALTA_CONDICIONAL")

    def test_usdjpy_oriented_usd_base(self):
        self.assertEqual(pairrow(run(), UP, "D1", "USD/JPY")["bias_if_conditions"],
                         "ALTA_CONDICIONAL")
        self.assertEqual(pairrow(run(), DOWN, "D1", "USD/JPY")["bias_if_conditions"],
                         "BAIXA_CONDICIONAL")

    def test_non_usd_pair_not_forced(self):
        for branch in BRANCHES:
            self.assertEqual(pairrow(run(), branch, "D1", "EUR/GBP")["bias_if_conditions"],
                             "AGUARDAR")

    def test_monthly_all_wait_for_longer_context(self):
        result = run()
        self.assertTrue(all(r["bias_if_conditions"] == "AGUARDAR" for r in
                            result["pair_scenarios"] + result["index_scenarios"]
                            if r["horizon"] == "MN1"))

    def test_mixed_branch_all_wait(self):
        result = run()
        self.assertTrue(all(r["bias_if_conditions"] == "AGUARDAR" for r in
                            result["pair_scenarios"] + result["index_scenarios"]
                            if r["branch"] == MIXED))

    def test_weekly_requires_persistent_relative_repricing(self):
        row = pairrow(run(), UP, "W1", "EUR/USD")
        self.assertIn("POLICY_REPRICING_PERSISTS_THROUGH_WEEK", row["condition_chain"])

    def test_us_index_upside_conditional_negative_discount_rate(self):
        row = idxrow(run(), UP, "D1", "NAS100")
        self.assertEqual(row["bias_if_conditions"], "BAIXA_CONDICIONAL")
        self.assertIn("US_REAL_YIELDS_RISE", row["condition_chain"])

    def test_us_index_downside_conditional_growth_veto(self):
        row = idxrow(run(), DOWN, "D1", "SPX500")
        self.assertEqual(row["bias_if_conditions"], "ALTA_CONDICIONAL")
        self.assertIn("US_GROWTH_NOT_REPRICED_AS_RECESSION", row["condition_chain"])

    def test_weekly_index_yield_persistence_independent_from_fx_peers(self):
        row = idxrow(run(), UP, "W1", "US30")
        self.assertIn("US_REAL_YIELD_MOVE_PERSISTS_THROUGH_WEEK", row["condition_chain"])
        self.assertFalse(any("PEER" in c for c in row["condition_chain"]))

    def test_win_wdo_blocked_without_brl_context(self):
        result = run()
        for symbol in ("WIN", "WDO"):
            self.assertTrue(all(r["bias_if_conditions"] == "AGUARDAR" for r in
                                result["index_scenarios"] if r["symbol"] == symbol))

    def test_conditional_direction_requires_all_macro_risk_conditions(self):
        row = pairrow(run(), UP, "D1", "EUR/USD")
        self.assertIn("CORE_CPI_CORROBORATES", row["condition_chain"])
        self.assertIn("USD_EXPECTED_RATE_PATH_MORE_HAWKISH_THAN_PEER", row["condition_chain"])
        self.assertIn("GEOPOLITICS_AND_RISK_DO_NOT_OVERRIDE", row["condition_chain"])

    def test_no_real_branch_is_selected(self):
        out = run()
        self.assertIsNone(out["selected_branch"])
        self.assertEqual(out["bias_primary"], "AGUARDAR")
        self.assertTrue(all(not b["selected"] for b in out["branches"]))
        self.assertTrue(all(not r["branch_selected"] for r in
                            out["pair_scenarios"] + out["index_scenarios"]))

    def test_nowcast_not_consensus_or_real_cpi(self):
        out = run()
        self.assertEqual(out["context_model_nowcast"]["CPI_MOM_SA_PCT"], 0.24)
        self.assertIsNone(out["actual_cpi"])
        self.assertIsNone(out["consensus"])
        self.assertFalse(out["market_consensus_available"])

    def test_no_probability_no_trading(self):
        out = run()
        self.assertFalse(out["accuracy_90_proven"])
        self.assertIsNone(out["market_probability_calibrated"])
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["can_feed_live_radar"])
        self.assertFalse(out["worker_enabled"])
        self.assertFalse(out["scheduler_enabled"])
        self.assertTrue(all(x["probability_calibrated"] is None and not x["trade_authorized"]
                            and not x["entry_signal"] for x in
                            out["pair_scenarios"] + out["index_scenarios"]))

    def test_relative_policy_and_geopolitics_not_verified(self):
        out = run()
        self.assertFalse(out["relative_policy_paths_verified"])
        self.assertFalse(out["geopolitics_alignment_verified"])

    def test_before_observation_denies(self):
        out = run(when=datetime(2026, 11, 2, 10, tzinfo=timezone.utc))
        self.assertEqual(out["state"], "LAB_CPI_CONDITIONAL_FANOUT_BLOCKED")

    def test_after_actual_release_denies_old_pre_event_scenarios(self):
        out = run(when=AFTER_EVENT)
        self.assertEqual(out["state"], "LAB_CPI_CONDITIONAL_FANOUT_BLOCKED")

    def test_fake_actual_in_snapshot_denies(self):
        book = snapshot()
        book["official_release_actual"] = 0.5
        self.assertEqual(run(book)["state"], "LAB_CPI_CONDITIONAL_FANOUT_BLOCKED")

    def test_invalid_vintage_denies(self):
        book = snapshot()
        book["source_reported_update_day"] = "2026-11-20"
        self.assertEqual(run(book)["state"], "LAB_CPI_CONDITIONAL_FANOUT_BLOCKED")

    def test_no_automatic_direction_from_fed_ecb_rate_levels(self):
        out = run()
        self.assertNotIn("rate_level", out)
        self.assertIsNone(out["selected_branch"])
        self.assertTrue(all(r["bias_if_conditions"] == "AGUARDAR" for r in
                            out["pair_scenarios"] if r["horizon"] == "MN1"))


if __name__ == "__main__":
    unittest.main()
