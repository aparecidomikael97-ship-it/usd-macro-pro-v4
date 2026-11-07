"""Offline coverage join tests: all macro and price data are synthetic."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import unittest

from atlasquant_trader_g8_macro_asof_lab import ENVELOPE
from atlasquant_trader_mt5_readonly_snapshot_lab import collect_mt5_fx_snapshot_lab
from atlasquant_trader_mt5_macro_join_lab import join_mt5_macro_lab
from test_atlasquant_trader_mt5_readonly_snapshot_lab import FakeMT5, NOW


DECISION = NOW + timedelta(hours=1)


def _raw(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def snapshot():
    return collect_mt5_fx_snapshot_lab(FakeMT5(), captured_at_utc=NOW)


def synthetic_macro(pair="EUR/USD", *, decision=DECISION):
    base, quote = pair.split("/")
    rows = []
    for cur in (base, quote):
        for indicator in ("CPI_YOY", "POLICY_RATE"):
            rows.append({
                "currency": cur, "indicator": indicator,
                "observation_period": "2026-10", "value": "2.5",
                "published_at_utc": "2026-10-29T12:00:00Z",
                "captured_at_utc": "2026-10-29T12:05:00Z",
                "source_type": ("OFFICIAL_STATISTICS_OFFICE" if indicator == "CPI_YOY"
                                else "CENTRAL_BANK"),
                "source_sha256": "a" * 64,
            })
    return _raw({
        "schema": ENVELOPE, "pair": pair,
        "decision_at_utc": decision.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "records": rows,
    })


class MT5MacroJoinTests(unittest.TestCase):
    def join(self, data=None, macro=None, when=DECISION):
        return join_mt5_macro_lab(
            snapshot_raw=_raw(snapshot() if data is None else data),
            macro_raw_by_pair={} if macro is None else macro,
            decision_at_utc=when,
        )

    def assert_no_signal(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["fx_bias"])
        self.assertIsNone(result["validated_accuracy"])
        self.assertEqual(result["validated_prediction_count"], 0)
        for field in ("trade_authorized", "can_feed_live_radar", "worker_enabled",
                      "scheduler_enabled", "publishable", "macro_source_independently_authenticated",
                      "broker_quote_source_independently_authenticated"):
            self.assertIs(result[field], False, field)

    def test_realistic_full_price_no_macro_remains_wait(self):
        r = self.join()
        self.assertEqual(r["state"], "LAB_PRICE_MACRO_COVERAGE_AUDITED_UNATTESTED")
        self.assertEqual(r["price_pairs_validated"], 28)
        self.assertEqual(r["macro_pairs_structurally_complete"], 0)
        self.assertEqual((r["m15_recent_pairs"], r["d1_recent_pairs"],
                          r["w1_recent_pairs"]), (0, 28, 28))
        self.assertEqual(len(r["pairs"]), 28)
        self.assertTrue(all(row["macro_state"] == "MISSING"
                            and row["research_bias"] == "AGUARDAR"
                            for row in r["pairs"].values()))
        self.assert_no_signal(r)

    def test_macro_two_sides_accepts_structure_but_not_authenticity(self):
        macro = synthetic_macro("EUR/USD")
        r = self.join(macro={"EUR/USD": macro})
        self.assertEqual(r["macro_pairs_structurally_complete"], 1)
        self.assertEqual(r["pairs"]["EUR/USD"]["macro_state"], "TWO_SIDED_UNATTESTED")
        self.assertEqual(r["pairs"]["EUR/USD"]["macro_bytes_sha256"], sha256(macro).hexdigest())
        self.assertEqual(r["pairs"]["GBP/USD"]["macro_state"], "MISSING")
        self.assert_no_signal(r)

    def test_macro_wrong_clock_cannot_be_joined(self):
        macro = synthetic_macro(decision=DECISION + timedelta(hours=1))
        r = self.join(macro={"EUR/USD": macro})
        self.assertEqual(r["macro_pairs_structurally_complete"], 0)
        self.assertEqual(r["pairs"]["EUR/USD"]["macro_state"], "INVALID_OR_CLOCK_MISMATCH")
        self.assert_no_signal(r)

    def test_capture_after_decision_rejected_as_lookahead(self):
        r = self.join(when=NOW - timedelta(hours=1))
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assertEqual(r["reason"], "DECISION_PRECEDES_SNAPSHOT_COLLECTION")
        self.assert_no_signal(r)

    def test_changing_any_ohlc_outside_range_blocks(self):
        d = snapshot()
        d["pairs"]["EURUSD"]["M15"]["bars"][-1]["high"] = 0.1
        r = self.join(data=d)
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assertEqual(r["price_pairs_validated"], 0)
        self.assert_no_signal(r)

    def test_forged_count_or_authorized_flag_blocks(self):
        for edit in (lambda d: d.update(validated_bars=1),
                     lambda d: d.update(trade_authorized=True),
                     lambda d: d["pairs"].pop("CHFJPY"),
                     lambda d: d["pairs"]["EURUSD"]["D1"].update(closed_bars=29)):
            d = snapshot()
            edit(d)
            r = self.join(data=d)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_no_signal(r)

    def test_duplicate_snapshot_json_key_rejected(self):
        d = _raw(snapshot())
        modified = d.replace(b'"schema":', b'"schema":"FAKE","schema":', 1)
        r = join_mt5_macro_lab(snapshot_raw=modified, macro_raw_by_pair={}, decision_at_utc=DECISION)
        self.assertEqual(r["state"], "LAB_BLOCKED")

    def test_extra_macro_pair_rejected(self):
        r = self.join(macro={"USD/EUR": synthetic_macro()})
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assert_no_signal(r)

    def test_missing_timezone_rejected(self):
        r = self.join(when=DECISION.replace(tzinfo=None))
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assert_no_signal(r)


if __name__ == "__main__":
    unittest.main()
