import unittest
from datetime import datetime, timedelta, timezone

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_readiness_v1 import SCHEMA, build_trader_readiness

BRT = timezone(timedelta(hours=-3))
AT = datetime(2026, 11, 2, 9, 10, tzinfo=BRT)


def _daily(at=AT, *, complete=True):
    rows = list(OFFICIAL_PAIRS) if complete else list(OFFICIAL_PAIRS)[:7]
    return {
        "state": "VALIDATED_DAILY", "source": "Provedor validado em LAB",
        "as_of": at.isoformat(),
        "pairs": {p: {"change_pct": 0.2, "bias": "NEUTRO"} for p in rows},
        "currencies": {c: {"change_pct": 0.1} for c in CURRENCIES},
    }


def _calendar(at=AT):
    return {
        "state": "READY", "source": "EODHD Economic Events",
        "date": "2026-11-02", "fetched_at": at.isoformat(),
        "events": [{"title": "CPI"}], "truncated": False,
    }


def _tech(at=AT):
    return {
        "state": "VALIDATED_TECHNICAL", "source": "LAB",
        "as_of": at.isoformat(), "symbol": OFFICIAL_PAIRS[0],
        "timeframes": {tf: {"state": "VERIFIED"} for tf in ("D1", "H4", "M15")},
    }


class CheckpointReadinessTests(unittest.TestCase):
    def test_blank_never_implies_signal_or_complete_feed(self):
        model = build_trader_readiness(at=AT)
        self.assertEqual(model["schema"], SCHEMA)
        self.assertEqual(model["forex"]["state"], "SEM DADOS")
        self.assertEqual(model["scanner"]["state"], "SEM LEITURA")
        self.assertEqual(model["calendar"]["state"], "SEM DADOS")
        self.assertEqual(model["decision"]["state"], "AGUARDAR")
        self.assertFalse(model["decision"]["real_orders_enabled"])
        self.assertFalse(model["decision"]["automatic_execution"])
        self.assertEqual(model["home"]["monitored_fx"], 28)
        self.assertEqual(model["home"]["g8_currencies"], 8)

    def test_seven_pairs_do_not_claim_full_28_market(self):
        m = build_trader_readiness(daily_data=_daily(complete=False), at=AT)
        self.assertEqual(m["forex"]["state"], "PARCIAL")
        self.assertEqual(m["forex"]["covered"], 7)
        self.assertIn("7/28", m["forex"]["reason"])
        self.assertEqual(m["decision"]["state"], "AGUARDAR")

    def test_all_pairs_currencies_current_get_coverage_not_trade_authority(self):
        m = build_trader_readiness(daily_data=_daily(), at=AT)
        self.assertEqual(m["forex"]["state"], "COBERTURA COMPLETA")
        self.assertEqual(m["forex"]["covered"], 28)
        self.assertEqual(m["forex"]["currencies_covered"], 8)
        self.assertFalse(m["decision"]["real_orders_enabled"])

    def test_stale_and_future_feed_never_ranked_as_current(self):
        for when in (AT - timedelta(minutes=21), AT + timedelta(minutes=3)):
            with self.subTest(when=when):
                m = build_trader_readiness(daily_data=_daily(when), at=AT)
                self.assertNotEqual(m["forex"]["state"], "COBERTURA COMPLETA")
                self.assertEqual(m["forex"]["covered"], 0)

    def test_calendar_requires_proven_today_fetched_at(self):
        m = build_trader_readiness(calendar_data=_calendar(), at=AT)
        self.assertEqual(m["calendar"]["state"], "VALIDADO")
        for invalid in (
            {**_calendar(), "date": "2026-11-01"},
            {**_calendar(), "fetched_at": ""},
            {**_calendar(), "source": ""},
            {**_calendar(), "truncated": True},
        ):
            with self.subTest(invalid=invalid):
                m = build_trader_readiness(calendar_data=invalid, at=AT)
                self.assertNotEqual(m["calendar"]["state"], "VALIDADO")

    def test_m15_absence_fails_closed_even_if_macro_ready(self):
        t = _tech()
        t["timeframes"]["M15"]["state"] = "MISSING"
        m = build_trader_readiness(technical_data=t, at=AT)
        self.assertEqual(m["scanner"]["state"], "PARCIAL")
        self.assertNotIn("M15", m["scanner"]["timeframes"])
        self.assertIn("AGUARDAR", m["scanner"]["reason"])

    def test_complete_evidence_still_never_approves_orders(self):
        m = build_trader_readiness(
            daily_data=_daily(), calendar_data=_calendar(), technical_data=_tech(), at=AT)
        self.assertEqual(m["scanner"]["state"], "EM ESTUDO")
        self.assertEqual(m["calendar"]["state"], "VALIDADO")
        self.assertEqual(m["forex"]["state"], "COBERTURA COMPLETA")
        self.assertEqual(m["decision"]["state"], "AGUARDAR")
        self.assertEqual(len(m["decision"]["why_not"]), 1)
        self.assertIn("Risco", m["decision"]["why_not"][0])

    def test_invalid_numeric_and_timezone_are_not_accepted(self):
        raw = _daily()
        raw["pairs"][OFFICIAL_PAIRS[0]]["change_pct"] = float("nan")
        m = build_trader_readiness(daily_data=raw, at=AT)
        self.assertEqual(m["forex"]["covered"], 27)
        self.assertEqual(m["forex"]["state"], "PARCIAL")
        with self.assertRaises(ValueError):
            build_trader_readiness(at=datetime(2026, 11, 2, 9, 10))


if __name__ == "__main__":
    unittest.main()
