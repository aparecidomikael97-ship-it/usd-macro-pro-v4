"""No-trade regression checks for MT5 + official-page EUR/USD context."""
from datetime import timedelta
from pathlib import Path
import json
import unittest

from atlasquant_trader_eurusd_mt5_official_context_lab import (
    inspect_eurusd_mt5_official_context_lab as inspect,
)
from atlasquant_trader_mt5_readonly_snapshot_lab import collect_mt5_fx_snapshot_lab
from test_atlasquant_trader_mt5_readonly_snapshot_lab import FakeMT5, NOW

CASEBOOK = (Path(__file__).resolve().parent / "docs" / "continuidade" /
            "TRADER_EURUSD_20261106_FOUR_OFFICIAL_DOCUMENTS_ASOF_CASE_LAB.json")
ASOF = NOW + timedelta(hours=1)


def _raw(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")


def snapshot():
    return collect_mt5_fx_snapshot_lab(FakeMT5(), captured_at_utc=NOW)


class EURUSDOfficialContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.casebook = CASEBOOK.read_bytes()

    def run_case(self, *, snap=None, casebook=None, asof=ASOF):
        return inspect(mt5_snapshot_raw=_raw(snapshot() if snap is None else snap),
                       official_casebook_raw=self.casebook if casebook is None else casebook,
                       as_of_utc=asof)

    def assert_wait(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["fx_bias"])
        self.assertEqual(r["validated_prediction_count"], 0)
        self.assertIsNone(r["validated_accuracy"])
        self.assertFalse(r["can_feed_live_radar"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])

    def test_four_official_pages_meet_28_broker_histories_not_direction(self):
        r = self.run_case()
        self.assertEqual(r["state"], "LAB_EURUSD_PRICE_AND_OFFICIAL_PAGES_VISIBLE_UNATTESTED_NO_BIAS")
        self.assertEqual(r["price_pairs_validated"], 28)
        self.assertEqual(r["official_document_refs_visible"], 4)
        self.assertTrue(r["eurusd_d1_recent"])
        self.assertTrue(r["eurusd_w1_recent"])
        self.assertFalse(r["eurusd_m15_recent"])
        self.assertFalse(r["inflation_reference_periods_match"])
        self.assertFalse(r["inflation_methodologies_comparable"])
        self.assertFalse(r["rate_instruments_directly_comparable"])
        self.assertFalse(r["next_us_cpi_oct2026_headline_yoy_eligible"])
        self.assertIsNone(r["next_us_cpi_oct2026_actual"])
        names = {d["record_id"] for d in r["documents"]}
        self.assertEqual(names, {
            "USD_BLS_CPI_SEP2026", "USD_FED_OCT2026_FOMC",
            "EUR_ECB_OCT2026_POLICY_DECISION", "EUR_EUROSTAT_OCT2026_HICP_FLASH",
        })
        self.assert_wait(r)

    def test_corrupt_official_casebook_cannot_be_laundered(self):
        altered = self.casebook.replace(b'"3.7"', b'"3.8"', 1)
        r = self.run_case(casebook=altered)
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assertEqual(r["official_document_refs_visible"], 0)
        self.assert_wait(r)

    def test_unfinished_or_forged_broker_history_cannot_attach_docs(self):
        d = snapshot()
        d["pairs"]["EURUSD"]["M15"]["bars"][-1]["open"] = 99.0
        r = self.run_case(snap=d)
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assertEqual(r["official_document_refs_visible"], 0)
        self.assert_wait(r)

    def test_pre_snapshot_research_clock_blocks(self):
        r = self.run_case(asof=NOW - timedelta(minutes=1))
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assert_wait(r)

    def test_no_naive_clock(self):
        r = self.run_case(asof=ASOF.replace(tzinfo=None))
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assert_wait(r)


if __name__ == "__main__":
    unittest.main()
