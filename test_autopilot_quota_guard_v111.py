import unittest

import pandas as pd

import autopilot_quota_guard_v111 as guard


class TestAutopilotQuotaGuardV111(unittest.TestCase):
    def setUp(self):
        guard._M15_SOURCE_CACHE.clear()
        self._original_fetch = guard._ORIGINAL_TD_FETCH

    def tearDown(self):
        guard._ORIGINAL_TD_FETCH = self._original_fetch
        guard._M15_SOURCE_CACHE.clear()

    @staticmethod
    def _m15_frame(periods: int = 1200) -> pd.DataFrame:
        dt = pd.date_range("2026-01-01T00:00:00Z", periods=periods, freq="15min")
        rows = []
        for i, ts in enumerate(dt):
            op = 1.10000 + i * 0.00001
            cl = op + 0.00001
            rows.append(
                {
                    "datetime": ts,
                    "open": op,
                    "high": cl + 0.00002,
                    "low": op - 0.00002,
                    "close": cl,
                }
            )
        return pd.DataFrame(rows)

    def test_one_m15_request_serves_m15_h1_h4(self):
        calls = []
        source = self._m15_frame()

        def fake_fetch(pair, interval, outputsize):
            calls.append((pair, interval, int(outputsize)))
            return source.copy(), ""

        guard._ORIGINAL_TD_FETCH = fake_fetch

        m15, e15 = guard.quota_saver_td_fetch("EUR/USD", "15min", 500)
        h1, e1 = guard.quota_saver_td_fetch("EUR/USD", "1h", 100)
        h4, e4 = guard.quota_saver_td_fetch("EUR/USD", "4h", 100)

        self.assertEqual(e15, "")
        self.assertEqual(e1, "")
        self.assertEqual(e4, "")
        self.assertFalse(m15.empty)
        self.assertGreaterEqual(len(h1), 60)
        self.assertGreaterEqual(len(h4), 60)
        self.assertEqual(
            calls,
            [("EUR/USD", "15min", guard.M15_DERIVATION_OUTPUTSIZE)],
        )

    def test_incomplete_h1_bucket_is_discarded(self):
        source = self._m15_frame(8)
        # Remove 00:15. The 00:00 H1 bucket is therefore incomplete;
        # the 01:00 bucket remains complete and must be the only one returned.
        source = source[source["datetime"] != pd.Timestamp("2026-01-01T00:15:00Z")].reset_index(drop=True)

        def fake_fetch(pair, interval, outputsize):
            return source.copy(), ""

        guard._ORIGINAL_TD_FETCH = fake_fetch
        h1, err = guard.quota_saver_td_fetch("EUR/USD", "1h", 100)

        self.assertEqual(err, "")
        self.assertEqual(len(h1), 1)
        self.assertEqual(pd.Timestamp(h1.iloc[0]["datetime"]), pd.Timestamp("2026-01-01T01:00:00Z"))

    def test_open_m15_candle_is_not_used_in_derived_bucket(self):
        source = self._m15_frame(5)
        # Directly exercise the strict helper with a deterministic clock.
        derived = guard.derive_from_m15(
            source,
            "1h",
            now_utc="2026-01-01T01:05:00Z",
        )
        # 01:00 candle is still open until 01:15, so only 00:00 H1 is valid.
        self.assertEqual(len(derived), 1)
        self.assertEqual(pd.Timestamp(derived.iloc[0]["datetime"]), pd.Timestamp("2026-01-01T00:00:00Z"))

    def test_d1_still_uses_original_provider_fetch(self):
        calls = []
        source = self._m15_frame(320)

        def fake_fetch(pair, interval, outputsize):
            calls.append((pair, interval, int(outputsize)))
            return source.copy(), ""

        guard._ORIGINAL_TD_FETCH = fake_fetch
        frame, err = guard.quota_saver_td_fetch("GBP/USD", "1day", 320)

        self.assertEqual(err, "")
        self.assertFalse(frame.empty)
        self.assertEqual(calls, [("GBP/USD", "1day", 320)])

    def test_daily_quota_reason_is_labeled_as_daily(self):
        old_reason = guard.base._TD_DAILY_BLOCK_REASON
        old_type = guard.base._TD_BLOCK_TYPE
        try:
            guard.base._TD_DAILY_BLOCK_REASON = (
                "You have run out of API credits for the day. "
                "801 API credits were used, with the current limit being 800."
            )
            guard.base._TD_BLOCK_TYPE = "429_PERSISTENTE"
            guard._normalize_quota_block_type()
            self.assertEqual(guard.base._TD_BLOCK_TYPE, "COTA_DIARIA")
        finally:
            guard.base._TD_DAILY_BLOCK_REASON = old_reason
            guard.base._TD_BLOCK_TYPE = old_type


if __name__ == "__main__":
    unittest.main()