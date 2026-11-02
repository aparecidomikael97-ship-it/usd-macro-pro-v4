"""Synthetic offline checks for M15 -> H1/H4 research aggregation."""
import copy
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_m15_broker_export_lab import (
    SCHEMA, STATE, audit_m15_broker_export_lab,
)

NOW = datetime(2026, 11, 2, 22, tzinfo=timezone.utc)
START = datetime(2026, 10, 30, 8, tzinfo=timezone.utc)


def fixture():
    pairs = {}
    for index, pair in enumerate(OFFICIAL_PAIRS):
        base = Decimal("1.20") + Decimal(index) / 100
        bars = []
        for minute in range(16):
            op = base + Decimal(minute) / 10000
            bars.append({
                "open_at_utc": (START + timedelta(minutes=15 * minute)).isoformat(),
                "open": str(op),
                "high": str(op + Decimal("0.0005")),
                "low": str(op - Decimal("0.0005")),
                "close": str(op + Decimal("0.0002")),
            })
        pairs[pair] = bars
    return {
        "state": STATE, "source_id": "synthetic-lab",
        "source_url": "https://example.invalid/research",
        "exported_at_utc": "2026-11-02T21:00:00Z",
        "time_basis": "UTC_DECLARED_UNATTESTED",
        "price_kind": "BID_OHLC_UNVERIFIED",
        "license_status": "UNREVIEWED_PERSONAL_LAB_ONLY",
        "pairs": pairs,
    }


def audit(data=None, at=NOW):
    return audit_m15_broker_export_lab(fixture() if data is None else data, evaluated_at=at)


class M15BrokerExportLabTests(unittest.TestCase):
    def test_all_28_pairs_four_hours_and_eight_currencies_have_structure_only(self):
        r = audit()
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["state"], "LAB_M15_H1_H4_STRUCTURALLY_COMPLETE_UNTRUSTED")
        self.assertEqual(r["pair_coverage"], 28)
        self.assertEqual(r["m15_count"], 448)
        self.assertEqual(len(CURRENCIES), 8)
        self.assertEqual(len(r["derived_h1"]), 28)
        self.assertEqual(len(r["derived_h4"]), 28)
        self.assertEqual(len(r["derived_h1"]["EUR/USD"]), 4)

    def test_h1_h4_are_exact_aggregates_with_origin_label(self):
        r = audit()
        raw = fixture()["pairs"]["EUR/USD"]
        first_h1 = r["derived_h1"]["EUR/USD"][0]
        last_h4 = r["derived_h4"]["EUR/USD"]
        self.assertEqual(first_h1["open"], raw[0]["open"])
        self.assertEqual(first_h1["close"], raw[3]["close"])
        self.assertEqual(Decimal(first_h1["high"]),
                         max(Decimal(x["high"]) for x in raw[:4]))
        self.assertEqual(Decimal(first_h1["low"]),
                         min(Decimal(x["low"]) for x in raw[:4]))
        self.assertEqual(last_h4["close"], raw[-1]["close"])
        self.assertEqual(last_h4["start_at_utc"], "2026-10-30T08:00:00+00:00")
        self.assertEqual(last_h4["end_at_utc"], "2026-10-30T12:00:00+00:00")
        self.assertIn("UNVERIFIED", last_h4["origin"])

    def test_missing_pair_and_inverted_symbol_denied(self):
        for replacement in (None, "JPY/USD"):
            d = fixture()
            sample = d["pairs"].pop("USD/JPY")
            if replacement is not None:
                d["pairs"][replacement] = sample
            self.assertEqual(audit(d)["state"], "LAB_M15_EXPORT_QUARANTINED")

    def test_partial_or_extra_candles_denied(self):
        for size in (15, 17):
            d = fixture()
            candles = d["pairs"]["EUR/USD"]
            if size == 15:
                candles.pop()
            else:
                candles.append(copy.deepcopy(candles[-1]))
            self.assertEqual(audit(d)["state"], "LAB_M15_EXPORT_QUARANTINED")

    def test_duplicate_or_skipped_timestamp_denied(self):
        d = fixture()
        d["pairs"]["EUR/USD"][4]["open_at_utc"] = d["pairs"]["EUR/USD"][3]["open_at_utc"]
        self.assertEqual(audit(d)["state"], "LAB_M15_EXPORT_QUARANTINED")
        d = fixture()
        d["pairs"]["EUR/USD"][5]["open_at_utc"] = (
            START + timedelta(minutes=15 * 6)).isoformat()
        self.assertEqual(audit(d)["state"], "LAB_M15_EXPORT_QUARANTINED")

    def test_all_pairs_must_share_same_utc_start(self):
        d = fixture()
        for b in d["pairs"]["GBP/JPY"]:
            stamp = datetime.fromisoformat(b["open_at_utc"])
            b["open_at_utc"] = (stamp + timedelta(hours=4)).isoformat()
        self.assertEqual(audit(d)["state"], "LAB_M15_EXPORT_QUARANTINED")

    def test_h4_utc_anchor_explicit_cannot_guess_broker_session(self):
        d = fixture()
        for candles in d["pairs"].values():
            for b in candles:
                stamp = datetime.fromisoformat(b["open_at_utc"])
                b["open_at_utc"] = (stamp + timedelta(hours=1)).isoformat()
        self.assertEqual(audit(d)["state"], "LAB_M15_EXPORT_QUARANTINED")

    def test_unclosed_final_bar_cannot_be_used(self):
        d = fixture()
        d["exported_at_utc"] = "2026-10-30T11:59:59Z"
        self.assertEqual(audit(d)["state"], "LAB_M15_EXPORT_QUARANTINED")

    def test_unzoned_and_non_utc_candle_rejected(self):
        for t in ("2026-10-30T08:00:00", "2026-10-30T10:00:00+02:00"):
            d = fixture()
            d["pairs"]["EUR/USD"][0]["open_at_utc"] = t
            self.assertEqual(audit(d)["state"], "LAB_M15_EXPORT_QUARANTINED")

    def test_malformed_prices_not_coerced_to_valid(self):
        for value in ("NaN", "Inf", "0", "-5", "10001", None, True, 1.1):
            d = fixture()
            d["pairs"]["EUR/USD"][0]["close"] = value
            self.assertEqual(audit(d)["state"], "LAB_M15_EXPORT_QUARANTINED", repr(value))

    def test_ohlc_extremes_are_checked(self):
        d = fixture()
        d["pairs"]["EUR/USD"][0]["high"] = "0.0001"
        self.assertIn("OHLC", audit(d)["reason"])

    def test_unknown_candle_field_or_trade_claim_denied(self):
        d = fixture()
        d["pairs"]["EUR/USD"][0]["BUY"] = True
        self.assertEqual(audit(d)["state"], "LAB_M15_EXPORT_QUARANTINED")
        d = fixture()
        d["trade_authorized"] = True
        self.assertEqual(audit(d)["state"], "LAB_M15_EXPORT_QUARANTINED")

    def test_rights_time_basis_and_price_claims_are_fail_closed(self):
        for field, new in (("state", "REAL_VALIDATED"),
                           ("license_status", "COMMERCIAL_APPROVED"),
                           ("time_basis", "BROKER_CLOCK_CERTIFIED"),
                           ("price_kind", "EXECUTABLE_BID_ASK")):
            d = fixture()
            d[field] = new
            self.assertEqual(audit(d)["state"], "LAB_M15_EXPORT_QUARANTINED")

    def test_no_non_https_or_credentials_in_attribution(self):
        for url in ("http://example.invalid", "https://a:b@example.invalid",
                    "https://example.invalid:notaport/x",
                    "https://example.invalid:1234/x", "https://example.invalid/x#frag"):
            d = fixture()
            d["source_url"] = url
            self.assertEqual(audit(d)["state"], "LAB_M15_EXPORT_QUARANTINED", url)

    def test_future_export_and_naive_evaluation_denied(self):
        d = fixture()
        d["exported_at_utc"] = "2026-11-03T09:00:00Z"
        self.assertEqual(audit(d)["state"], "LAB_M15_EXPORT_QUARANTINED")
        with self.assertRaises(ValueError):
            audit(at=datetime(2026, 11, 2, 22))

    def test_no_synthetic_result_allows_real_bias_oos_or_trading(self):
        for r in (audit(), audit({})):
            self.assertIsNone(r["real_currency_strength"])
            self.assertIsNone(r["real_bias_28_pairs"])
            self.assertEqual(r["independent_spot_quotes_verified"], 0)
            for flag in ("source_identity_attested", "broker_clock_attested",
                         "point_in_time_capture_attested", "commercial_license_verified",
                         "bid_ask_spread_verified", "can_feed_live_radar",
                         "can_feed_real_oos", "backtest_oos_authorized",
                         "trade_authorized", "worker_enabled", "scheduler_enabled"):
                self.assertFalse(r[flag], flag)


if __name__ == "__main__":
    unittest.main()
