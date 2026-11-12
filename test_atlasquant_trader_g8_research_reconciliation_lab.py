"""Offline checks preventing drift between G8 sources and the 28-pair view."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_g8_official_research_coverage_lab import (
    inspect_g8_official_research_coverage_lab,
)
from atlasquant_trader_g8_publication_evidence_audit_lab import (
    SOURCE_CATALOGS,
    inspect_g8_publication_evidence_lab,
)
from atlasquant_trader_g8_research_reconciliation_lab import (
    inspect_g8_research_reconciliation_lab,
)


def at(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class G8ResearchReconciliationTests(unittest.TestCase):
    def inspect(self, stamp: str = "2026-11-08T12:00:00Z", horizon: str = "D1") -> dict:
        return inspect_g8_research_reconciliation_lab(
            decision_at_utc=at(stamp), horizon=horizon)

    def test_all_17_source_research_keys_reconcile_across_28_pairs(self) -> None:
        r = self.inspect()
        self.assertEqual(r["state"], "LAB_RESEARCH_METADATA_RECONCILED_UNATTESTED")
        self.assertEqual(r["source_records"], 17)
        self.assertEqual(r["research_available_records"], 17)
        self.assertEqual((r["currency_count"], r["pair_count"]), (8, 28))
        self.assertEqual(set(r["currencies"]), set(CURRENCIES))
        self.assertEqual(set(r["pairs"]), set(OFFICIAL_PAIRS))
        self.assertEqual((r["two_sided_research_pairs"],
                          r["one_sided_research_pairs"],
                          r["zero_sided_research_pairs"]), (28, 0, 0))

    def test_early_decision_has_no_research_or_backtest_authority(self) -> None:
        r = self.inspect("2026-08-01T00:00:00Z")
        self.assertTrue(r["research_metadata_reconciled"])
        self.assertEqual(r["research_available_records"], 0)
        self.assertEqual(r["zero_sided_research_pairs"], 28)
        self.assertFalse(r["backtest_approved"])

    def test_midperiod_covers_only_documented_sides(self) -> None:
        r = self.inspect("2026-10-25T00:00:00Z")
        self.assertTrue(r["research_metadata_reconciled"])
        self.assertLess(r["two_sided_research_pairs"], 28)
        self.assertEqual(sum(r[k] for k in (
            "two_sided_research_pairs", "one_sided_research_pairs",
            "zero_sided_research_pairs")), 28)
        self.assertTrue(any(row["missing_research_families"]
                            for row in r["currencies"].values()))

    def test_every_source_floor_preserves_reconciliation(self) -> None:
        for catalog in SOURCE_CATALOGS:
            for key, row in catalog.items():
                floor = at(row["availability_floor_utc"])
                with self.subTest(source=key):
                    before = inspect_g8_research_reconciliation_lab(
                        decision_at_utc=floor-timedelta(seconds=1), horizon="D1")
                    after = inspect_g8_research_reconciliation_lab(
                        decision_at_utc=floor, horizon="D1")
                    self.assertTrue(before["research_metadata_reconciled"])
                    self.assertTrue(after["research_metadata_reconciled"])
                    self.assertGreater(after["research_available_records"],
                                       before["research_available_records"])
                    self.assertFalse(after["backtest_approved"])

    def test_pair_rows_are_never_actionable(self) -> None:
        r = self.inspect()
        for pair, row in r["pairs"].items():
            with self.subTest(pair=pair):
                self.assertEqual(row["operational_bias"], "AGUARDAR")
                self.assertFalse(row["backtest_approved"])
                self.assertFalse(row["historical_pit_verified"])

    def test_evidence_research_is_not_independent_pit(self) -> None:
        r = self.inspect()
        self.assertTrue(r["research_metadata_reconciled"])
        self.assertFalse(r["independent_source_attestation"])
        self.assertFalse(r["historical_point_in_time_verified"])
        self.assertIsNone(r["directional_probability"])
        self.assertIsNone(r["validated_accuracy"])
        self.assertFalse(r["trade_authorized"])

    def test_d1_w1_dont_change_source_claims(self) -> None:
        d, w = self.inspect(horizon="D1"), self.inspect(horizon="W1")
        self.assertEqual(d["pairs"], w["pairs"])
        self.assertEqual(d["currencies"], w["currencies"])
        self.assertEqual(d["horizon"], "D1")
        self.assertEqual(w["horizon"], "W1")

    def test_utc_offset_normalized(self) -> None:
        a = self.inspect()
        b = inspect_g8_research_reconciliation_lab(
            decision_at_utc=datetime(2026, 11, 8, 8, tzinfo=timezone(timedelta(hours=-4))),
            horizon="D1")
        self.assertEqual(a, b)

    def test_bad_clock_or_horizon_fails_closed(self) -> None:
        for clock, horizon in (
            (datetime(2026, 11, 8), "D1"),
            (at("2026-11-08T12:00:00Z").replace(microsecond=1), "D1"),
            (at("2026-11-08T12:00:00Z"), "M15"),
        ):
            with self.subTest(clock=clock, horizon=horizon):
                r = inspect_g8_research_reconciliation_lab(
                    decision_at_utc=clock, horizon=horizon)
                self.assertEqual(r["state"], "LAB_RESEARCH_RECONCILIATION_BLOCKED")

    def test_currency_research_key_tampering_is_blocked(self) -> None:
        fake = deepcopy(inspect_g8_official_research_coverage_lab(
            decision_at_utc=at("2026-11-08T12:00:00Z"), horizon="D1"))
        fake["currencies"]["GBP"]["family_research_keys"]["POLICY"] = []
        with patch("atlasquant_trader_g8_research_reconciliation_lab."
                   "inspect_g8_official_research_coverage_lab", return_value=fake):
            r = self.inspect()
        self.assertEqual(r["state"], "LAB_RESEARCH_RECONCILIATION_BLOCKED")
        self.assertIn("GBP:RESEARCH_KEYS_MISMATCH", r["problems"])
        self.assertEqual(r["pair_count"], 0)

    def test_pair_state_tampering_is_blocked(self) -> None:
        fake = deepcopy(inspect_g8_official_research_coverage_lab(
            decision_at_utc=at("2026-11-08T12:00:00Z"), horizon="D1"))
        pair = next(iter(fake["pairs"]))
        fake["pairs"][pair]["backtest_approved"] = True
        with patch("atlasquant_trader_g8_research_reconciliation_lab."
                   "inspect_g8_official_research_coverage_lab", return_value=fake):
            r = self.inspect()
        self.assertEqual(r["state"], "LAB_RESEARCH_RECONCILIATION_BLOCKED")
        self.assertIn(f"{pair}:PAIR_COVERAGE_MISMATCH", r["problems"])

    def test_summary_pair_count_tampering_is_blocked(self) -> None:
        fake = deepcopy(inspect_g8_official_research_coverage_lab(
            decision_at_utc=at("2026-11-08T12:00:00Z"), horizon="D1"))
        fake["two_sided_research_pairs"] = 27
        with patch("atlasquant_trader_g8_research_reconciliation_lab."
                   "inspect_g8_official_research_coverage_lab", return_value=fake):
            r = self.inspect()
        self.assertEqual(r["state"], "LAB_RESEARCH_RECONCILIATION_BLOCKED")
        self.assertIn("PAIR_TOTALS_MISMATCH", r["problems"])

    def test_upstream_claiming_backtest_approval_is_rejected(self) -> None:
        fake = deepcopy(inspect_g8_publication_evidence_lab(
            decision_at_utc=at("2026-11-08T12:00:00Z"), horizon="D1"))
        fake["historical_backtest_approved"] = True
        with patch("atlasquant_trader_g8_research_reconciliation_lab."
                   "inspect_g8_publication_evidence_lab", return_value=fake):
            r = self.inspect()
        self.assertEqual(r["reason"], "UPSTREAM_RESEARCH_NOT_IN_SAFE_STATE")

    def test_upstream_claiming_point_in_time_history_is_rejected(self) -> None:
        fake = deepcopy(inspect_g8_official_research_coverage_lab(
            decision_at_utc=at("2026-11-08T12:00:00Z"), horizon="D1"))
        fake["original_point_in_time_vintage_attested"] = True
        with patch("atlasquant_trader_g8_research_reconciliation_lab."
                   "inspect_g8_official_research_coverage_lab", return_value=fake):
            r = self.inspect()
        self.assertEqual(r["reason"], "UPSTREAM_RESEARCH_NOT_IN_SAFE_STATE")

    def test_attested_source_in_research_inventory_fails_closed(self) -> None:
        fake = deepcopy(inspect_g8_publication_evidence_lab(
            decision_at_utc=at("2026-11-08T12:00:00Z"), horizon="D1"))
        key = "GBP_CPI_2026_09"
        fake["sources"][key]["historical_vintage_attested"] = True
        with patch("atlasquant_trader_g8_research_reconciliation_lab."
                   "inspect_g8_publication_evidence_lab", return_value=fake):
            r = self.inspect()
        self.assertEqual(r["reason"], "SOURCE_CLAIM_OUTSIDE_UNATTESTED_RESEARCH_SCOPE")

    def test_no_network_scheduler_or_money(self) -> None:
        r = self.inspect()
        self.assertEqual(r["http_requests"], 0)
        self.assertEqual(r["new_cost_brl"], 0)
        self.assertFalse(r["worker_enabled"] or r["scheduler_enabled"])


if __name__ == "__main__":
    unittest.main()
