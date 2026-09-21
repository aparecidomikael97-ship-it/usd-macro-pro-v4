import unittest

from atlasquant_timeframe_profiles import (
    SUPPORTED_EXECUTION_TIMEFRAMES,
    apply_timeframe_context,
    normalize_execution_timeframe,
    timeframe_profile,
)


class TimeframeProfilesTests(unittest.TestCase):
    def test_required_timeframes_are_supported(self):
        self.assertEqual(
            SUPPORTED_EXECUTION_TIMEFRAMES,
            ("M15","M30","H1","H4","D1","W1"),
        )

    def test_aliases_normalize(self):
        self.assertEqual(normalize_execution_timeframe("30m"),"M30")
        self.assertEqual(normalize_execution_timeframe("1h"),"H1")
        self.assertEqual(normalize_execution_timeframe("daily"),"D1")
        self.assertEqual(normalize_execution_timeframe("weekly"),"W1")

    def test_profiles_cover_intraday_daytrade_swing_and_position(self):
        self.assertEqual(timeframe_profile("M15")["trading_style"],"INTRADAY")
        self.assertEqual(timeframe_profile("M30")["trading_style"],"INTRADAY")
        self.assertEqual(timeframe_profile("H1")["trading_style"],"DAY_TRADE")
        self.assertEqual(timeframe_profile("H4")["trading_style"],"SWING")
        self.assertEqual(timeframe_profile("D1")["trading_style"],"SWING")
        self.assertEqual(timeframe_profile("W1")["trading_style"],"POSITION")

    def test_signal_context_keeps_timeframe_identity(self):
        rows=apply_timeframe_context([{"pair":"EUR/USD","setup":"FVG"}],"H4",overwrite=True)
        self.assertEqual(rows[0]["timeframe"],"H4")
        self.assertEqual(rows[0]["trading_style"],"SWING")

    def test_existing_explicit_timeframe_can_be_preserved(self):
        rows=apply_timeframe_context(
            [{"pair":"EUR/USD","timeframe":"W1","trading_style":"POSITION"}],
            "M15",
            overwrite=False,
        )
        self.assertEqual(rows[0]["timeframe"],"W1")
        self.assertEqual(rows[0]["trading_style"],"POSITION")


if __name__=="__main__":
    unittest.main()
